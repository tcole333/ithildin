# Property and Land Records

Tools for parcel, assessment, address, sale, recorder-instrument, tax-status,
geometry, and chain-of-title research across heterogeneous local systems.

**When to read this module:** When researching real-property ownership,
property-owning entities, transfers, mortgages, liens, tax defaults, addresses,
or parcel-to-court links.

## Tool inventory

| Tool | Purpose | Network behavior | Local data |
|---|---|---|---|
| `query_property.py` | Unified local/live property query router | Local by default; named adapters read the catalog | `datasets/property_records.db` |
| `query_dc_property.py` | D.C. assessment/tax accounts, common-ownership polygons, CAMA sales, and Surveyor documents | Four separately attributable official DCGIS ArcGIS components | Assessment, owner, address, sale, tax, and geometry projections plus retained survey observations |
| `query_washington_digital_archives_land.py` | Washington State Archives county-auditor recorded-land title inventory, party index, instrument detail, and official gap routes | Anonymous inventory/title/search/detail requests; listed document generation is a separate site reCAPTCHA queue | Index occurrences, detailed instruments and parties, candidate parcel joins, and metadata-only image objects |
| `query_washington_taxsifter.py` | Eleven Washington county TaxSifter assessor, treasurer, appraisal, and assessor-sale tenants | County-specific anonymous WebForms sessions; ten live tenants and one Mason challenge observation | Account-occurrence-preserving parcel, owner, address, assessment, tax, payment, appraisal, and assessor-sale projection |
| `query_mason_county_tax_parcels.py` | Mason County current assessor/GIS parcel, name, address, value, legal/map-field, and polygon search | Official anonymous ArcGIS MapServer layer; complete FID snapshots replace unsupported offset/order pagination | Feature-occurrence observations plus parcel, assessment, assessor-name, address, alias, and requested-geometry projection when a parcel join identifier exists |
| `query_washington_parcels.py` | Washington statewide normalized parcels, county freshness, county land-use vocabularies, and representation parity | Official Ecology, DNR, and WISAARD ArcGIS services | Structured parcel/assessment/geometry projection plus separately attributable freshness, vocabulary, count, metadata, probe, and parity observations |
| `query_michigan_property_directories.py` | Michigan's official 83-county tax-parcel route directory, platform triage, discovery seeds, and complementary official property routes | One official DTMB HTML directory fetch; manifest and alternatives are network-free | Snapshot-only county route observations; destination capabilities remain separately evidenced |
| `query_wisconsin_parcels.py` | Wisconsin statewide annual parcel, owner-visibility, assessment/tax, geometry, and county-lineage search | Official State Cartographer/WLIP ArcGIS service plus official bulk, county, and transfer-return routes | Structured parcel projection; known non-parcel map rows remain observations |
| `query_wy_dor_parcels.py` | Wyoming DOR annual tax-roll parcel, account, owner/address/value, legal-description, FID, and spatial search for all 23 counties | Official DOR application root and current anonymous ArcGIS layer, with same-publisher downloads and official county-route directory | Every FID remains a feature occurrence; supported annual business keys project once, while occurrence-only rows remain raw evidence |
| `query_ohio_statewide_parcels.py` | Ohio OGRIP statewide parcel identifiers, address observations, land use, geometry, county inventory, and local-CAMA routing | Official anonymous ArcGIS FeatureServer covering all 88 counties | Parcel, address, alias, and requested-geometry projection; county assessment and recorder records remain separate routes |
| `query_ohio_licking_property.py` | Licking County Auditor GIS parcels, assessment-owner/address/value fields, recent-transfer observations, and polygons | Official anonymous county ArcGIS layer with complete ordered paging | Feature occurrences plus parcel, owner, address, value, transfer, and requested-geometry projection; null-parcel rows remain observations |
| `query_ohio_franklin_auditor_bulk.py` | Franklin County Auditor appraisal, tax-accounting, conveyance, GIS, and parcel release discovery and local row streaming | Anonymous official IIS directories, bounded artifact probes, and resumable downloads | Release/artifact/row lineage plus component-specific owner, payment, and explicitly qualified assessor-sale observations |
| `query_ohio_franklin_sales_gis.py` | Franklin County Auditor recent sale occurrences, parcel/conveyance joins, transaction parties, qualification fields, structure context, and points | Official anonymous ArcGIS layer with deterministic exhaustive `OBJECTID` paging | Every GlobalID occurrence plus dated positive-price assessor sale events; raw `ValidSale` remains a qualification and same-Auditor sources remain one evidence lineage |
| `query_ohio_pax_recorders.py` | Delaware and Licking County recorded-instrument detail, party, image metadata, PDF, access-state, and alternative-route research | Delaware anonymous PAX session after disclaimer; Licking account-gated PAX discovery plus anonymous exact-instrument detail/PDF | Instrument and party projection with document artifacts; Licking exact detail retains separate representation provenance on the PAX instrument identity |
| `query_ny_statewide_parcels.py` | New York statewide assessment/owner centroids, public parcel polygons, state-owned parcels, coverage, and exact cross-component identifiers | Three official Statewide Parcel Map Program ArcGIS components plus official bulk, county, deed, and migration routes | One parcel identity across component observations; annual assessment state comes from centroids and available boundary geometry from polygon components |
| `query_ny_salesweb.py` | New York ORPTS real-property transfer search, exact sale detail, reference tables, and CSV export | Official SalesWeb JSON and export services | Transfer observations and parties joined to statewide parcels by published SWIS/print-key identity without treating buyers as current owners |
| `query_census_acs.py` | ACS 5-year demographic, housing, and Census-geography context for parcel and court locations | Official Census metadata and keyed data API, with Census Reporter as a keyless representation of the same release | Release-bound estimates, margins of error, annotations, derived point-estimate rates, and full GEOID/FIPS joins |
| `query_new_jersey_parcels.py` | NJGIN statewide parcel geometry and partially joined MOD-IV assessment search | Official item-resolved NJGIN ArcGIS service plus official bulk and local complements | Structured parcel/assessment/sale-reference projection without inventing source-redacted owners |
| `query_new_jersey_sr1a.py` | New Jersey property-sale release discovery, validation, and fixed-width search | Official Division of Taxation listing, layout, and ZIP releases | Release-bound sale observations with raw-field and normalization provenance |
| `query_new_jersey_tax_court.py` | New Jersey Tax Court current local-property case reports and parcel-candidate fields | Anonymous official S3 manifest plus docketed/open XLSX reports | Docket cases and source-row occurrences in the court sidecar; no municipality or ownership is inferred |
| `query_new_jersey_dca_property.py` | New Jersey DCA property and building registration search | Anonymous official Power Pages OData plus property-detail and official alternative routes | Building-granular regulatory registration events and parties; parcel coordinates remain candidate links |
| `query_montana_cadastral.py` | Montana statewide live parcels, selected CAMA fields, 56-county coverage, and monthly parcel/ORION bulk releases | Official MSL ArcGIS layer and anonymous official bulk directories | Parcel, assessment-roll owner/address/value, and requested geometry projection; nullable `PARCELID` occurrences and bulk records are retained separately |
| `query_virginia_parcels.py` | VGIN statewide parcel identity, geometry, spatial lookup, locality freshness, and local-source routing | Official ArcGIS item resolved to its current FeatureServer plus official bulk and local complements | `VGIN_QPID` parcel projection with typed local joins and separately retained coverage observations |
| `query_va_beach_delinquent_tax.py` | Virginia Beach current delinquent real-estate tax installments, balances, owners, addresses, and related record routes | Official City ArcGIS table updated daily | GPIN parcel join, exact-cent tax event, owner/address observations, and source snapshot |
| `query_palm_beach_property_appraiser.py` | Palm Beach parcel-detail feature occurrences, assessment owners/values, situs and mailing addresses, last-sale labels, legal fields, polygons, statistics, and complementary-source discovery | Anonymous official County FeatureServer; the separately advertised flat-file cloud invitation has an operation-specific consent discrepancy and is not automated | Every OBJECTID occurrence is retained; PARCEL_NUMBER is a non-unique candidate parcel join, PARID stays separate, and requested parcel/assessment/sale/geometry fields project without creating title claims |
| `query_palm_beach_tax_collector.py` | Palm Beach Tax Collector account discovery, exact account state, bills/installments, payment history, bill-detail links, refresh routing, and official field-matched complements | Anonymous official guidance and Aumentum PublicAccessNow read routes | PCN joins parcel sources; AlternateKey, bills, installments, receipts, and payments retain separate identities; mutable tax state is preserved as a retrieved observation |
| `query_palm_beach_tax_deeds.py` | Palm Beach tax-deed case discovery, auction/status observations, exact case details, document inventories, and public PDFs | Anonymous Clerk MVC form/session, native jqGrid pages, exact detail pages, and listed PDF routes | Case occurrences, case/certificate/event/document identities, event parties, exact PCN candidates, available/unavailable document representations, and downloaded artifacts project without title assertions |
| `query_orange_tax_collector.py` | Orange County current tax-account search, bill/certificate history and bill detail, plus two fixed historical bulk roll snapshots | Anonymous GovHub/Algolia search, direct TaxSys HTML, and official Tax Collector ZIP/layout artifacts | The exact 15-digit parcel joins property sources; object IDs, account tokens, bill UUIDs, certificates, receipts, validation numbers, artifact members, and row occurrences retain separate identities |
| `query_palm_beach_official_records.py` | Palm Beach exact recorded-instrument detail, book/page resolution, image retrieval, access routes, and source probe | Official Landmark Web detail/image routes after public acknowledgement; broad discovery is a distinct interactive reCAPTCHA flow | Instrument, party, exact PCN parcel link, deed-sale, image-state, and acquired-page projection |
| `query_broward_official_records.py` | Broward party/parcel/instrument search, detail and PDF retrieval, daily release parsing, and route inventory | Official AcclaimWeb browser session plus caller-supplied County DOC/NME/LNK/LGL/RNG/IMG files | Instrument, party, exact index parcel link, cross-reference, and separate PDF/TIFF artifact projection |
| `query_usvi_property_tax.py` | Territory-wide Capture CAMA owner/parcel/address/legal search, exact tax-year detail, valuation and tax history, and printable bills, receipts, and property cards | Anonymous official ASP.NET WebForms search, detail components, and selected printable HTML | Tax-year parcel snapshots, assessment-roll owner/address/value observations, statements/payments as tax events, and retrieved HTML artifacts; no recorded-title projection |
| `query_nc_property.py` | North Carolina OneMap parcel search | Official ArcGIS query service | Structured projection through generic ingestion |
| `query_bexar_property.py` | Bexar County appraisal, parcel, detail, and deed-history search | Official BCAD ArcGIS and Harris Govern JSON routes | Structured projection through generic ingestion |
| `query_reeves_records.py` | Reeves County recorded-instrument index, OCR, detail, and page-image retrieval | Official Clerk-linked GovOS/Kofile PublicSearch tenant | Structured instrument projection through generic ingestion |
| `query_govos_recorders.py` | Configured county recorder search/detail/page-image adapter | Verified county-specific GovOS/Kofile tenants | Structured instrument projection through generic ingestion |
| `query_denver_property.py` | Denver assessor parcel, address, value, sale, legal-description, geometry, and recorder-reference search | Official Denver Open Data ArcGIS layer | Structured projection through generic ingestion |
| `query_oregon_taxlots.py` | Portland owner-bearing regional taxlots, Metro RLIS public assessment/sales taxlots, and OWRD 13-county public taxlots | Three official ArcGIS source components with shared retrieval and separate provenance | Structured projection through generic ingestion |
| `query_oregon_lane_marion_parcels.py` | Lane parcels, separate rolling recent sales, and Marion parcels with values and latest-sale references | Three official county ArcGIS components; source-specific alternatives stay separately cataloged | Structured parcel and sale projection through generic ingestion |
| `query_oregon_lane_property.py` | Lane Property Account Information search/detail and Tax Map Search locator/PDF components | Anonymous county JSON and cookie-session account pages; ASP.NET WebForms tax-map search and official PDFs | Account/search-index, locator, and document identities remain distinct |
| `query_oregon_marion_downloads.py` | Marion's current/historical assessor sales artifacts and comprehensive assessment snapshot | Official artifact manifest, bounded probes, resumable transfer, ZIP/member inspection, and local CSV search | Occurrence-preserving sale and assessment projection; historical workbook capability remains artifact-specific |
| `query_oregon_jackson_douglas_assessors.py` | Jackson taxlots and Douglas assessor parcels, owners, addresses, values, selected physical fields, and geometry | Two official county ArcGIS layers with county-specific identifiers and complements | Structured parcel, alias, owner, address, assessment, sale-reference, and geometry projection |
| `query_oregon_jackson_property_events.py` | Jackson building permits, land-use permits, and code-compliance observations | Three separately identified official county ArcGIS layers | Structured property-event, party, representation, and exact map-taxlot parcel-link projection |
| `query_oregon_jackson_accela.py` | Jackson Building and Planning record detail, attachments, document metadata, and document binaries | Official anonymous Accela Citizen Access record and document pages | Structured record-detail and document representations joined to the separate ArcGIS event rows |
| `query_oregon_yamhill_property.py` | Yamhill assessment accounts, current and retired taxlots, and assessment permits | Official AscendWeb tenant and three separately attributed county ArcGIS layers | Structured parcel, owner, address, assessment, geometry, property-event, and retained retired-taxlot observations |
| `query_oregon_clackamas_property.py` | Clackamas assessment accounts and CMap taxlots | Official AscendWeb tenant and county CMap ArcGIS layer | Structured parcel, owner, address, assessment, geometry, and exact account/map-taxlot joins |
| `query_oregon_wasco_property.py` | Wasco assessment accounts, taxlots, survey indexes, and selected survey attachments | Official AscendWeb tenant and county ArcGIS layers | Structured parcel/assessment projection plus separately retained survey-index and representation observations |
| `query_oregon_washington_property.py` | Washington County Survey Explorer indexes/documents, survey geometry, current taxlots, situs points, Intermap reports, and WashCoTax accounts/statements | Official county JSON, ArcGIS, legacy report, and anonymous guest-tax routes | Assessor projections from Intermap property/assessment and WashCoTax account records; attributable observations for survey, geometry, tax-map, situs, and document representations |
| `query_oregon_washington_case_permits.py` | Washington County planning casefiles, taxlot project/activity links, building permits, permit reports, Accela CurrentPlanning records/documents, and casefile document routes | Official county JSON applications, anonymous Accela pages, and separately attributed publication/request routes | Dated casefile and permit-report rows project as property events; undated indexes, vocabularies, route catalogs, and document representations remain source observations |
| `query_oregon_multnomah_sail.py` | Multnomah County SAIL tax parcels, survey records, three plat families, road surveys, public-land corners, field books, image viewers, and PDFs | Eight official county ArcGIS components plus exact county image resolution | Tax-parcel assessor projection; separately attributable survey, plat, corner, field-book, viewer, and PDF observations |
| `query_deschutes_dial.py` | Deschutes account detail, tax/payment history, sales, improvements, related accounts, permits, development records, and property-report PDFs | Official DIAL pages plus separately attributed county tax-payment and document-viewer links | Canonical envelopes and caller-selected PDF artifacts |
| `query_deschutes_laserfiche.py` | Deschutes CDD planning, permit, septic, zoning, and development-document metadata and files | DIAL account document index plus official Laserfiche WebLink metadata and electronic/generated-PDF routes | Property-document events, parcel/account joins, representation lineage, and retrieved artifacts |
| `query_oregon_helion_property.py` | Six county Helion/ORCATS Property Search Online account indexes and rich account detail | Official browser-rendered county tenants with source-specific selectors, transport observations, and complements | Structured parcel, owner, address, assessment, and sale projection plus retained full detail |
| `query_oregon_helion_recorder.py` | County-scoped Helion recorded-instrument indexes, exact detail, party/legal/reference fields, and tenant-published document-delivery states | One county-selected session; live challenge state remains tenant-specific | Structured instrument projection through generic ingestion |
| `query_oregon_tax_foreclosures.py` | Tillamook, Marion, Multnomah, and Clackamas foreclosure, redemption, tax-title, and auction publications | Official county landing pages plus selected versioned PDFs | Process-stage tax events, publication artifacts, and text-representation lineage |
| `query_denver_delinquent_tax.py` | Denver annual delinquent-real-property-tax release discovery, verification, download, inspection, and streaming search | Official Treasury publication page and direct XLSX | Caller-selected download or temporary auto-fetch artifact |
| `query_delaware_firstmap.py` | Delaware statewide parcel-PIN, polygon, centroid, and county-routing search | Official FirstMap ArcGIS polygon and centroid layers | Parcel/geometry projection with source-feature preservation |
| `query_arlington_property.py` | Arlington RPC/parcel, owner-mailing-address, assessment, zoning, legal-description, lot, and geometry search | Official Arlington County ArcGIS layer | Structured projection through generic ingestion |
| `query_rrc_bulk.py` | Texas RRC P-4 operator history, P-5 organizations, Wellbore records, and cross-file resolution | Official RRC GoDrive listings and caller-selected bulk downloads | Streams caller-selected local bulk files |
| `query_miami_dade_property.py` | Miami-Dade appraisal search, detail/history, and parcel geometry | Official PA JSON proxy and county ArcGIS layer | Structured projection through generic ingestion |
| `query_miami_dade_recorder.py` | Miami-Dade Official Records instruments, parties, financial detail, and PDFs | Public detail/image routes plus credentialed exact-index API | Structured instrument projection through generic ingestion |
| `query_cook_property.py` | Cook County historical parcel lookup | Official Socrata dataset | Structured projection through generic ingestion |
| `query_md_property.py` | Maryland statewide address and parcel lookup | Official Socrata dataset | Structured projection through generic ingestion |
| `query_md_mdp_parcel_points.py` | Maryland statewide parcel-account, address, land-use, map/plat, and spatial lookup | Official MD iMAP ArcGIS point layer | `ACCTID` joins the same SDAT record represented by the Socrata source; `OBJECTID` retains each ArcGIS occurrence, with point, appraisal, structure, land, zoning, deed/plat-reference, and mailing-address fields |
| `query_md_mdp_property_downloads.py` | Maryland parcel-geodatabase, CAMA-component, and residential-sales release discovery, transfer, and local archive inspection | Official MDP listing with publisher-linked Dropbox files | Release/provider/artifact/member identities and schema contracts are retained; rows are not projected before the acquired table schemas are decoded |
| `query_md_plats.py` | Maryland State Archives recorded plat, subdivision, survey, book/page, right-of-way, and archive-series search | Anonymous Plats.net ASP.NET WebForms search plus session-independent unit pages | `us-md-plats` preserves the county/qualifier/series/unit record, each query result occurrence, metadata-only records, and each PDF/TIFF/JPEG representation without converting plat references or developer/owner display text into title or parcel-owner assertions |
| `query_fl_dor_property.py` | Florida DOR assessment-roll and GIS release discovery/transfer | Official bulk directories | Download destination selected by caller |
| `query_georgia_property_sources.py` | Georgia's official 159-county property-route directory and statewide deed/lien/plat index acquisition handoff | Georgia DOR directory plus GSCCCA information, limited-use account, and login routes | Snapshot-only route and acquisition observations; county parcel and instrument records remain attributable to their source systems |
| `query_massgis_property.py` | MassGIS municipal release discovery/transfer | Official ArcGIS manifest and bulk archives | Download/extraction destination selected by caller |
| `query_harris_property.py` | Harris Central Appraisal District release discovery/transfer | Official JSON manifests and bulk ZIPs | Download destination selected by caller |
| `query_texas_epts.py` | Texas Comptroller EPTS source/schema discovery, request handoff, and local transaction-file inspection/search | Official 52-field manual and Public Information Act request route; no statewide download was found | Preserves delivered artifact/member/row occurrences, property and transaction join candidates, confidentiality states, and county-clerk deed pivots |
| `query_harris_recorder.py` | Harris County real-property instrument index and bulk-product discovery | Official anonymous ASP.NET index plus Clerk product pages | Structured instrument projection through generic ingestion |
| `query_harris_foreclosures.py` | Harris County trustee-sale/foreclosure notices and PDFs | Official anonymous ASP.NET index and document route | Notice/event evidence retained separately from title instruments |
| `query_acris.py` | NYC recorder index and instrument records | Official Socrata datasets | Structured projection for document-shaped envelopes |
| `query_la_property.py` | East Baton Rouge assessment, parcel, and tax-default records | Official Socrata datasets | No |
| `query_orleans_property.py` | Orleans Parish current assessment accounts, owners, addresses, parcels, values, and geometry | Official Property Viewer locator and City TaxParcelQuery ArcGIS layer | Structured projection through generic ingestion |
| `public_records_shapefile.py` | Inspect and stream aligned SHP/SHX/DBF parcel features from local ZIPs or sidecar sets | None; operates on caller-acquired artifacts | Native-CRS geometry, DBF attributes, feature-occurrence identity, conservative parcel joins, and artifact/member/schema-bound cursors |
| `public_records_filegdb.py` | Inspect FileGDB containers and stream feature pages through GDAL OpenFileGDB | Container lineage needs no GDAL; schema inspection uses `ogrinfo` 3.7+ with OpenFileGDB read; feature extraction additionally uses compatible `ogr2ogr` with OpenFileGDB read and GPKG write | Native FID occurrence identity, conservative parcel joins, native-CRS WKB, and artifact/member/layer/schema-bound cursors |
| `public_records_catalog.py` | Source facts, capabilities, routes, reviews, terms snapshots, and probes | None | `datasets/public_records_catalog.db` |
| `public_records_census.py` | Nationwide property/court source-discovery queue | None | Catalog database |
| `public_records_priority.py` | Separate benefit, feasibility, and risk planning metrics | None | Catalog database |
| `public_records_store.py` | Canonical property and state/local-court sidecars | None | `datasets/property_records.db`, `datasets/state_court_records.db` |
| `ingest_property_records.py` | Preserve any canonical envelope and project mapped record families | None | `datasets/property_records.db` |
| `public_records_artifacts.py` | Content-addressed source artifacts, representations, and field evidence | None | `datasets/public_records_artifacts.db`, `datasets/public_records_artifacts/` |
| `public_records_extract.py` | Validate and ingest model/rule-based field extraction | None | Artifact store and `datasets/public_records_review.db` |
| `public_records_entity_candidates.py` | Explainable, reversible entity-link candidates | None | `datasets/public_records_entity_candidates.db` |
| `public_records_search_plan.py` | Reproducible property → recorder → court query plan | None | Reads catalog, profile, and investigation databases |
| `public_records_actions.py` | Plan or enqueue catalog-backed account, request, purchase, and physical-access work | None | `human_actions` in `investigation.db` |
| `public_records_monitor.py` | Explicit source probes and drift comparison | Named probe handlers | Catalog probe history |
| `public_records_eval.py` | Adapter, extraction, and triage evaluation | None | Caller-supplied evaluation bundle |

The source catalog is the shared source of current source facts and
capabilities. Adapters read its route, review, and published limits instead of
carrying a second set of source switches. The catalog does not replace source
adapters: it tells the planner and router what a source can do and how it is
currently reached.

Franklin County's recent sale point layer is documented separately in the
[Franklin Auditor Sales GIS source contract](../sources/ohio-franklin-auditor-sales-gis.md).
It uses GlobalID occurrence identity and a separate
`ConveyanceNum`+`PARCELID` business event, preserves raw sale qualification,
and treats overlapping Auditor bulk, property-portal, and OGRIP values as one
source lineage.

## Initialize and inspect the control plane

```bash
uv run python tools/seed_public_records_catalog.py --json
uv run python tools/seed_public_records_catalog.py --audit \
  --output "$WORKDIR/public-record-catalog-audit.json"
uv run python tools/public_records_catalog.py list --domain property --json
uv run python tools/public_records_catalog.py show us-nc-onemap-parcels --json
uv run python tools/public_records_catalog.py health us-nc-onemap-parcels --json
uv run python tools/public_records_store.py init
uv run python tools/public_records_store.py stats
```

Catalog and probe state distinguish:

- `ok` and `no_results`: a successful source response, with a true zero kept
  distinct from a failure.
- `partial` and `rate_limited`: incomplete coverage with continuation or source
  throttle details.
- `human_required` and `terms_blocked`: the catalog review identifies a human
  workflow or a blocked machine-acquisition path.
- `unavailable` and `source_changed`: transport failure or schema drift,
  reported separately from zero results.
- `restricted`: the requested record or source surface is not publicly
  available.

`uv run python tools/source_report.py check "Public Records Catalog"` reports
the control plane. The full report also includes one catalog-derived entry per
property and state/local-court source, including its reviewed access decision
and latest recorded probe.

## Nationwide census and prioritization

`config/public_records_census.yaml` expands the configured US states,
territories, and record-office roles into independently claimable discovery
targets. Each target can retain multiple catalog sources with their individual
service areas and gaps. Finding a source leaves target coverage `unassessed`;
coverage is evaluated separately so one statewide or local route does not
silently stand in for all county and court systems.

```bash
uv run python tools/public_records_census.py seed
uv run python tools/public_records_priority.py recompute --by methodology-review
uv run python tools/public_records_census.py stats --json
uv run python tools/public_records_census.py list --domain property --state FL \
  --source-presence none --candidate-presence some \
  --output "$WORKDIR/fl-property-candidate-review.json"
uv run python tools/public_records_census.py claim --domain court --state WI \
  --source-presence none --candidate-presence none \
  --by source-researcher --output "$WORKDIR/claimed-source.json"
uv run python tools/public_records_census.py resolve 17 \
  --status source_identified --source-id us-example-source \
  --official-url "https://example.gov/records" --by source-researcher
uv run python tools/public_records_census.py associate 17 \
  --source-id us-example-second-source \
  --coverage '{"counties":["001","003"]}' \
  --coverage-gaps '["remaining counties not yet inventoried"]' \
  --by source-researcher
uv run python tools/public_records_census.py assess-coverage 17 \
  --status partial --gaps '["county systems still unreviewed"]' \
  --by source-researcher
```

`list`, `show`, and `stats` expose source counts, source associations,
`coverage_status`, candidate source IDs from the last priority recomputation,
and recorded gaps. `--source-presence` filters explicit associations;
`--candidate-presence` filters compatible catalog candidates retained in the
priority basis. Use `--source-presence none --candidate-presence some` for
candidate association/integration review and pair `none` with
`--candidate-presence none` for source discovery. `--coverage-status` further
narrows either view. The catalog seed's `--audit` mode compares shared
router IDs and statically discovered source IDs declared by adapter modules
with tracked manifests, live catalog state, reviews, and materialized census
associations without changing the database. Static discovery covers literal
primary, component, and complementary source-ID constants, reports the adapter
path, and does not import or execute source modules.

Priority remains three-dimensional: benefit from current investigative demand,
feasibility from the best cataloged capability path, and risk from uncertainty
or operational friction. The tool stores and explains those dimensions
separately rather than hiding them in a blended score. The CLI recompute result
also returns a non-blocking catalog-audit summary and surfaces drift in its
concise output, making it clear when adapter or manifest changes have not yet
reached the catalog used for ranking. Metrics also expose the active-profile,
input-fingerprint, run, and `as_of` provenance of the stored scores. Compact
census rows retain the same provenance so a ranking produced for another
investigation or older demand inputs is visible during source triage. Address
and lead geography is resolved to structured state, territory, and county
identifiers with its provenance; unmatched inputs remain reported. Geography
changes source ranking, not whether a catalog source remains visible or
eligible for investigation.

```bash
uv run python tools/public_records_priority.py recompute \
  --by roadmap-review
uv run python tools/public_records_priority.py metrics \
  --output "$WORKDIR/public-record-priority-metrics.json"
uv run python tools/public_records_priority.py explain 17 \
  --output "$WORKDIR/public-record-priority-17.json"
```

## Shared adapter families

All adapters emit the `public-records-result/1.0` contract from
`public_records_contract.py`. `public_records_http.py` supplies reusable
Socrata SODA and ArcGIS REST pagination, retry, throttle, schema, cursor, and
failure semantics. `public_records_bulk.py` supplies release manifests,
metadata/range probes, resumable transfer, SHA-256 verification, ZIP
inspection, and extraction for snapshot or incremental feeds.
`public_records_shapefile.py` adds streaming SHP/SHX/DBF decoding for those
local artifacts. It aligns geometry and attribute occurrences by source
position, preserves multipart and Z geometry in the published CRS, and keeps
parcel identifiers as join candidates rather than feature identity.

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

These families preserve source-native fields and schema fingerprints while
leaving jurisdiction-specific normalization to the adapter. A caller-selected
result or transfer ceiling remains explicit in the query; otherwise the family
follows source pagination and the cataloged source facts.
There is no platform-wide `maximum_records_per_run` compatibility setting:
caller limits and endpoint page-size mechanics remain separate and visible.

## Census ACS geographic context

`query_census_acs.py` adds release-specific demographic and housing context to
the geography around a parcel, address, court, or filing pattern. It supports
states, counties, tracts, block groups, places, and ZCTAs. Every observation
retains the ACS vintage, full GEOID, estimate, published margin of error, and
any source annotation. Its derived percentages are labeled point-estimate
rates and keep their numerator and denominator observations.

```bash
uv run python tools/query_census_acs.py county --state 24 \
  --profile population-age --output "$WORKDIR/acs-md-counties.json"
uv run python tools/query_census_acs.py block-group --state 24 --county 005 \
  --profile housing --output "$WORKDIR/acs-baltimore-block-groups.json"
uv run python tools/query_census_acs.py zcta --zcta 21201 \
  --profile income-poverty --output "$WORKDIR/acs-21201.json"
uv run python tools/query_census_acs.py variables B25077 \
  --contains "Median value" --output "$WORKDIR/acs-b25077-variables.json"
uv run python tools/query_census_acs.py routes \
  --output "$WORKDIR/acs-acquisition-routes.json"
uv run python tools/query_census_acs.py probe \
  --output "$WORKDIR/acs-probe.json"
```

When `CENSUS_API_KEY` is present, selective observations can come from the
official data endpoint. Otherwise the adapter uses Census Reporter for the
same named ACS release and records that backend in provenance. This is
transport redundancy, not a second corroborating dataset. Official
table-based summary files provide the bulk route; the Census Geocoder supplies
address-to-GEOID crosswalks; and TIGERweb supplies separately attributable
geography boundaries. The shared search planner emits
`enrich_census_geography` from jurisdiction and address seeds, separate from
owner, instrument, and case searches.

## Unified property queries

The router defaults to the normalized local sidecar. `--source` selects a
cataloged live source.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
# Discover coverage and access status
uv run python tools/query_property.py sources --jurisdiction 37 \
  --output "$WORKDIR/property-sources.json"

# Local normalized observations
uv run python tools/query_property.py owner "SMITH" \
  --output "$WORKDIR/property-owner-local.json"
uv run python tools/query_property.py address "100 MAIN ST" \
  --jurisdiction 37005 --output "$WORKDIR/property-address-local.json"
uv run python tools/query_property.py parcel 3013467134 \
  --jurisdiction 37005 --output "$WORKDIR/property-parcel-local.json"
uv run python tools/query_property.py instrument 2017021700466001 \
  --output "$WORKDIR/property-instrument.json"
uv run python tools/query_property.py chain 3013467134 \
  --jurisdiction 37005 --output "$WORKDIR/property-chain.json"

# Live North Carolina OneMap query, optionally normalized into the sidecar
uv run python tools/query_property.py owner "SMITH" \
  --source us-nc-onemap-parcels --county-fips 005 --limit 25 \
  --output "$WORKDIR/nc-owner.json"
uv run python tools/query_property.py parcel 3013467134 \
  --source us-nc-onemap-parcels --county-fips 005 --geometry --ingest \
  --output "$WORKDIR/nc-parcel.json"

# Live Bexar County lookup through the same router
uv run python tools/query_property.py owner "GRACE CHURCH" \
  --source us-tx-bexar-bcad-property --jurisdiction 48029 \
  --output "$WORKDIR/bexar-owner.json"
uv run python tools/query_property.py parcel 612115 \
  --source us-tx-bexar-bcad-property --geometry --ingest \
  --output "$WORKDIR/bexar-parcel.json"

# Live Orleans Parish current property lookup
uv run python tools/query_property.py owner "CITY OF NEW ORLEANS" \
  --source us-la-orleans-property-viewer --jurisdiction 22071 \
  --output "$WORKDIR/orleans-owner.json"
uv run python tools/query_property.py parcel "<PARCELID>" \
  --source us-la-orleans-property-viewer --geometry --ingest \
  --output "$WORKDIR/orleans-parcel.json"

# Live Miami-Dade PA lookup through the same router
uv run python tools/query_property.py owner "MIAMI-DADE COUNTY" \
  --source us-fl-miami-dade-property-appraiser --jurisdiction 12086 \
  --output "$WORKDIR/miami-owner.json"
uv run python tools/query_property.py parcel 0101000000020 \
  --source us-fl-miami-dade-property-appraiser --geometry --ingest \
  --output "$WORKDIR/miami-parcel.json"

# Denver assessment parcel and recorder-reference join
uv run python tools/query_property.py owner "RODRIGUEZ" \
  --source us-co-denver-parcels --jurisdiction 08031 --limit 25 \
  --output "$WORKDIR/denver-owner.json"
uv run python tools/query_property.py map 0017103008000 \
  --source us-co-denver-parcels --ingest \
  --output "$WORKDIR/denver-parcel-map.json"

# Delaware statewide parcel geometry, joined by county and PIN
uv run python tools/query_property.py parcel 1001300033 \
  --source us-de-firstmap-parcels --jurisdiction 10003 --ingest \
  --output "$WORKDIR/delaware-firstmap-parcel.json"
uv run python tools/query_property.py map 1001300033 \
  --source us-de-firstmap-parcels --county-code 003 --ingest \
  --output "$WORKDIR/delaware-firstmap-map.json"

# Arlington RPC/parcel assessment and geometry
uv run python tools/query_property.py parcel 03-001-009 \
  --source us-va-arlington-property-map --jurisdiction 51013 --ingest \
  --output "$WORKDIR/arlington-parcel.json"
uv run python tools/query_property.py map 03001009 \
  --source us-va-arlington-property-map --ingest \
  --output "$WORKDIR/arlington-map.json"

# Deschutes account detail and native subdivision search
uv run python tools/query_property.py account 135278 \
  --source us-or-deschutes-dial-property --jurisdiction 41017 \
  --output "$WORKDIR/deschutes-dial-account.json"
uv run python tools/query_property.py subdivision "SISTERS" \
  --source us-or-deschutes-dial-property --jurisdiction 41017 \
  --output "$WORKDIR/deschutes-dial-subdivision.json"
```

All router results use the `public-records-result/1.0` envelope. It exposes
`status`, `warnings`, `errors`, `query.fingerprint`, coverage metadata, and any
continuation cursor alongside `records`. `--ingest` retains any result returned
by an actual live adapter, including non-success status observations. Sources
that currently provide only a catalog/action route report ingestion as skipped
because no live envelope was returned.

The local sidecar is a normalized cache rather than a completeness claim. A
local miss is `partial` when the requested jurisdiction has cached material and
`unavailable` when that scope has no observed coverage. The error details
include requested-scope counts, source IDs, matching query evidence, and
catalog/live route guidance. `no_results` is reserved for a preserved source
response whose source ID, jurisdiction, operation, selector, time scope, and
completion state match the local request. This keeps an unobserved cache entry
distinct from a source-authoritative zero.

## District of Columbia property and land records

`query_dc_property.py` exposes four official DCGIS components joined by the
District's Square/Suffix/Lot (`SSL`) identifier:

| Source ID | Native grain | Shared use |
|---|---|---|
| `us-dc-itspe-public-extract` | Assessment/tax account | Assessment roll, assessed owners, mailing and situs addresses, current/prior values, current and ten prior tax periods, and recorder-instrument pivots |
| `us-dc-common-ownership-polygons` | Physical common-ownership polygon | Parcel geometry and its same-lineage ITSPE account view |
| `us-dc-cama-property-sales` | CAMA sale observation | Sale date, price, qualification, sale code, and SSL join |
| `us-dc-surveyor-document-system` | Surveyor document | Survey/plat metadata, book/page fields, SSL join, and official document-viewer link |

The verified live counts were 221,400 ITSPE accounts, 137,400
common-ownership polygons, 421,472 CAMA sale rows, and 184,449 Surveyor
documents. Counts and record values are rolling observations. The account and
polygon layers share ITSPE lineage; their overlapping fields are not
independent corroboration, and the two different record grains are not assumed
to be one-to-one.

The four live components sit under the catalog lineage
`us-dc-itspe-property-lineage`. The property census associations are exact:
ITSPE covers `assessment_roll` and `tax_collection`, while the polygon layer
covers `parcel_geometry` at physical common-ownership-polygon grain. CAMA sale
rows and Surveyor documents remain useful SSL-linked complements but are not
claimed as land-record indexes.

The actual `land_records_index` route is
`us-dc-recorder-of-deeds-public-records`, the Recorder-linked
[PublicSearch portal](https://washington.dc.publicsearch.us/). Its online
coverage begins in August 1921. The portal describes a registered-user route
with free search and image viewing; document downloads are $4 plus a $1.50
transaction charge. The optional $175 monthly subscription changes the
document price to $2 plus the transaction charge. The current adapter covers
the four anonymous DCGIS components and does not yet establish a registered
PublicSearch session. ITSPE instrument numbers, CAMA sales, and Surveyor
documents are valuable pivots while preserving that source distinction.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect component identity and source contracts.
uv run python tools/query_dc_property.py sources \
  --output "$WORKDIR/dc-property-sources.json"
uv run python tools/query_dc_property.py metadata assessment \
  --output "$WORKDIR/dc-itspe-metadata.json"
uv run python tools/query_dc_property.py count geometry \
  --output "$WORKDIR/dc-polygon-count.json"

# Query assessment/tax accounts and common-ownership geometry.
uv run python tools/query_dc_property.py assessment "PAR 01300036" \
  --field ssl --output "$WORKDIR/dc-account.json"
uv run python tools/query_dc_property.py assessment "BRENTWOOD ROAD LLC" \
  --field owner --limit 25 --output "$WORKDIR/dc-owner.json"
uv run python tools/query_dc_property.py geometry "PAR 01300036" \
  --field ssl --geometry --output "$WORKDIR/dc-polygon.json"
uv run python tools/query_dc_property.py point -76.9927 38.9176 \
  --geometry --output "$WORKDIR/dc-point.json"
uv run python tools/query_dc_property.py bbox \
  -77.01 38.90 -76.98 38.94 --geometry \
  --output "$WORKDIR/dc-bbox.json"

# Query source-native sale and survey-document rows.
uv run python tools/query_dc_property.py sales "PAR 01300036" \
  --output "$WORKDIR/dc-sales.json"
uv run python tools/query_dc_property.py surveys "PAR 01300036" \
  --field ssl --output "$WORKDIR/dc-surveys.json"
uv run python tools/query_dc_property.py surveys \
  9B59CB35-62CB-C473-B297-59097C200000 --field document \
  --output "$WORKDIR/dc-survey-document.json"

# Use the shared router and optionally project live rows into the sidecar.
uv run python tools/query_property.py account "PAR 01300036" \
  --source us-dc-itspe-public-extract --jurisdiction 11 --ingest \
  --output "$WORKDIR/dc-shared-account.json"
uv run python tools/query_property.py map "PAR 01300036" \
  --source us-dc-common-ownership-polygons --jurisdiction 11 \
  --geometry --ingest --output "$WORKDIR/dc-shared-map.json"
uv run python tools/query_property.py sale "PAR 01300036" \
  --source us-dc-cama-property-sales --jurisdiction 11 --ingest \
  --output "$WORKDIR/dc-shared-sales.json"
uv run python tools/query_property.py survey \
  9B59CB35-62CB-C473-B297-59097C200000 \
  --source us-dc-surveyor-document-system --jurisdiction 11 --ingest \
  --output "$WORKDIR/dc-shared-survey.json"

# Bounded component and lineage drift checks.
uv run python tools/query_dc_property.py probe assessment \
  --output "$WORKDIR/dc-assessment-probe.json"
uv run python tools/public_records_monitor.py run \
  us-dc-itspe-property-lineage us-dc-itspe-public-extract \
  us-dc-common-ownership-polygons us-dc-cama-property-sales \
  us-dc-surveyor-document-system \
  --output "$WORKDIR/dc-property-monitors.json"
```

Shared ingestion projects ITSPE rows into parcel, assessment, address, owner,
sale, and tax-event tables. Polygon rows add geometry without treating their
repeated ITSPE fields as new corroboration. CAMA rows add separately sourced
sale events joined by SSL, and Surveyor rows remain attributable source
observations rather than recorded instruments. Monitor fingerprints cover
stable component schemas and lineage contracts; current counts and sentinel
values remain rolling observations.

## Washington State Archives recorded-land indexes

`query_washington_digital_archives_land.py` implements Washington State
Archives record series 14 as a multi-county recorded-instrument archive. The
verified inventory contains 26 county-auditor titles and an observed
32,692,605 index rows. That is not statewide coverage: 13 counties have no
verified series-14 title and are routed to their current official recorder
path instead.

Inventory, title metadata, session search/results, and exact record detail are
anonymous operations. A listed digital object has a separate delivery state:
the site sends document generation through `/DigitalObject/QueueStatus` with
the `generateDocument` reCAPTCHA action. The monitor exercises only inventory,
one title, one sentinel search page, and one detail record; it never invokes
that queue. Until document bytes are actually acquired, the object remains
metadata-only with null acquisition time, digest, storage path, and page count,
and the `official_archive_image_uncertified` rights tier.

Each title keeps its own published temporal and image state:
the table therefore preserves the Skamania 2014-2015 gap rather than
normalizing it into continuous coverage.

| County GEOID | County | Published title coverage | Archive image statement |
|---|---|---|---|
| `53001` | Adams | 1988-2026 | Some images |
| `53005` | Benton | 1969-2026 | Some images |
| `53007` | Chelan | 1888-2026 | Some images |
| `53009` | Clallam | 1985-2024 | Some images |
| `53011` | Clark | 1998-2021 | Images not available |
| `53015` | Cowlitz | 1986-2026 | Some images |
| `53021` | Franklin | 1989-2026 | Some images |
| `53027` | Grays Harbor | 1981-Present | Images not available |
| `53029` | Island | 2001-2023 | Some images |
| `53031` | Jefferson | 1981-2026 | Some images |
| `53035` | Kitsap | 1987-2007 | Some images |
| `53039` | Klickitat | 1988-2026 | Some images |
| `53041` | Lewis | 1965-2026 | Images not available |
| `53045` | Mason | 1985-2026 | Images not available |
| `53047` | Okanogan | 1993-2023 | Images not available |
| `53049` | Pacific | 1996-2026 | Images not available |
| `53051` | Pend Oreille | 1996-2026 | Some images |
| `53053` | Pierce | 1984-2026 | Images not available |
| `53059` | Skamania | 2008-2013; 2016-Present | Some images |
| `53061` | Snohomish | Dates not stated in the title | Some images |
| `53063` | Spokane | 1960-2026 | Some images |
| `53067` | Thurston | 1979-2026 | Some images |
| `53071` | Walla Walla | 1986-2026 | Some images |
| `53073` | Whatcom | Dates not stated in the title | Images not available |
| `53075` | Whitman | 1987-2026 | Some images |
| `53077` | Yakima | 1993-2008 | Some images |

Search result rows are indexed-party occurrences. Several rows can point to
the same 32-hex archive record ID, so the adapter preserves both a
source-published party-tuple key and a query-relative ordinal occurrence. A
search row does not create an instrument party. Exact detail creates or
enriches the instrument and reconciles its ordered party list; organization
and person names are kept intact as published. A parcel value on the detail is
a county-scoped join candidate, not a new parcel or current-owner assertion.
Only an exact match or one uniquely punctuation-normalized current
parcel/alias match is linked.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Static and live record-series inventory.
uv run python tools/query_washington_digital_archives_land.py sources \
  --output "$WORKDIR/wa-land-sources.json"
uv run python tools/query_washington_digital_archives_land.py inventory \
  --refresh --output "$WORKDIR/wa-land-inventory.json"

# One title's current metadata and native instrument vocabulary.
uv run python tools/query_washington_digital_archives_land.py metadata \
  --county adams --refresh --output "$WORKDIR/wa-land-adams-title.json"
uv run python tools/query_washington_digital_archives_land.py instruments \
  --county adams --output "$WORKDIR/wa-land-adams-types.json"

# County-scoped party search and exact archived instrument detail.
uv run python tools/query_washington_digital_archives_land.py search \
  --county adams --last-name SMITH --first-name AMOS \
  --start-year 2020 --end-year 2020 --limit 50 \
  --output "$WORKDIR/wa-land-search.json"
uv run python tools/query_washington_digital_archives_land.py detail \
  64742C2528B8C19D43FCC54D20DC97D0 \
  --output "$WORKDIR/wa-land-detail.json"

# The 13 archive gaps and their official county-recorder routes.
uv run python tools/query_washington_digital_archives_land.py alternatives \
  --output "$WORKDIR/wa-land-alternatives.json"

# Shared routing and normalized detail ingestion.
uv run python tools/query_property.py owner "ACME HOLDINGS, LLC" \
  --source us-wa-state-archives-digital-recorded-land \
  --jurisdiction 53001 --search-field company \
  --output "$WORKDIR/wa-land-shared-owner.json"
uv run python tools/query_property.py instrument \
  64742C2528B8C19D43FCC54D20DC97D0 \
  --source us-wa-state-archives-digital-recorded-land \
  --jurisdiction 53001 --ingest \
  --output "$WORKDIR/wa-land-shared-detail.json"

# Bounded anonymous lifecycle monitor.
uv run python tools/public_records_monitor.py run \
  us-wa-state-archives-digital-recorded-land \
  --output "$WORKDIR/wa-land-monitor.json"
```

The uncovered counties are Asotin (`53003`), Columbia (`53013`), Douglas
(`53017`), Ferry (`53019`), Garfield (`53023`), Grant (`53025`), King
(`53033`), Kittitas (`53037`), Lincoln (`53043`), San Juan (`53055`), Skagit
(`53057`), Stevens (`53065`), and Wahkiakum (`53069`). Their county-recorder
routes remain recorded-instrument lineages. Ferry TaxSifter is separately an
assessor parcel/owner/assessment/sale/tax pivot within the county family
described below. The Washington Current Parcels services are a third lineage
for current parcel, assessment, and geometry context. Neither assessor source
substitutes for a recorded instrument.
Monitor hashes cover operation, identity, and observed schemas while growing
title counts, coverage-year labels, search totals, and current record values
remain rolling observations.

## Washington county TaxSifter property family

`query_washington_taxsifter.py` implements the
`us-wa-taxsifter-property-family` routing identity plus eleven county leaf
sources. Washington's Current Parcels `DATA_LINK` values supplied the official
county destinations. The adapter reconciles legacy `taxsifter.com`,
`publicaccessnow.com`, county-hosted root, and county-hosted nested-path
aliases before assigning a leaf source ID.

| County GEOID | Leaf source ID | Current operation state |
|---|---|---|
| `53001` | `us-wa-adams-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53017` | `us-wa-douglas-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53019` | `us-wa-ferry-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53021` | `us-wa-franklin-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53037` | `us-wa-kittitas-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53043` | `us-wa-lincoln-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53045` | `us-wa-mason-county-taxsifter` | JavaScript/cookie challenge observed for the TaxSifter operations |
| `53047` | `us-wa-okanogan-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53049` | `us-wa-pacific-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53059` | `us-wa-skamania-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |
| `53075` | `us-wa-whitman-county-taxsifter` | Search, assessor, treasurer, appraisal, and sales verified live |

A fresh tenant can redirect the first request to `Disclaimer.aspx`. The
working flow posts the source-returned hidden fields and agreement control,
then retries the requested page in the same session. That is an ordinary
session transition, not evidence that the tenant is unavailable. The
lifecycle monitor records a state for every tenant and operation so a Mason
challenge, a live detail page, and an authoritative empty sales response do
not become one family-wide label.

The native general search box accepts parcel, owner-name, and address terms.
Search continuation follows the published total and native pages when the
caller does not select a limit. Account occurrences use leaf `source_id` +
`keyId` + `typeID`; county GEOID + parcel number is a separate cross-source
join. Keeping those identities distinct prevents two portal occurrences from
being collapsed merely because they point at the same parcel.

Assessor detail, appraisal, valuation history, permits, assessor sale history,
and parcel-map pivots share the county assessor lineage. Treasurer balances,
tax rows, and receipts retain the county treasurer lineage. Sales pages
publish a result count, selected-page field, and WebForms pager controls, but
the continuation request has not been established. The adapter therefore
returns every row in the current native response, reports the published count
separately from the returned-row count, and does not invent sales paging.
An authoritative zero-row page remains a successful accessible operation.

Mason's field-oriented official alternatives remain deliberately distinct:

- [Mason County TaxParcels GIS](https://gis.masoncountywa.gov/arcgis/rest/services/MasonCoSite/TaxParcels/MapServer/0)
  provides parcel, assessment, owner, situs, legal, and polygon fields.
- [Mason County Auditor EagleWeb](https://recording.masoncountywa.gov/recorder/web/)
  provides the current grantor/grantee, document, date, and legal-description
  recorded-instrument index.
- [Washington Digital Archives title 56](https://digitalarchives.wa.gov/Collections/TitleInfo/56)
  is an archived publication of the Mason county-auditor recorded-instrument
  lineage.
- [Washington Current Parcels](https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer/0)
  remains the normalized parcel/assessment/geometry representation.

The GIS routes are not Treasurer accounts, and the assessor sale views are not
recorded instruments. EagleWeb and title 56 share a recorder lineage while
retaining different publication identities.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect the whole family or one county's route and operation contract.
uv run python tools/query_washington_taxsifter.py sources \
  --output "$WORKDIR/wa-taxsifter-sources.json"
uv run python tools/query_washington_taxsifter.py metadata --county adams \
  --output "$WORKDIR/wa-taxsifter-adams-metadata.json"
uv run python tools/query_washington_taxsifter.py discover \
  "http://douglaswa.taxsifter.com/Assessor.aspx?keyId=1088458&parcelNumber=07000000504&typeID=1" \
  --output "$WORKDIR/wa-taxsifter-discovery.json"

# Native search, combined account representations, and current sales response.
uv run python tools/query_washington_taxsifter.py search HERCULES \
  --county adams --output "$WORKDIR/wa-taxsifter-owner.json"
uv run python tools/query_washington_taxsifter.py detail 2038010000001 \
  --county adams --output "$WORKDIR/wa-taxsifter-account.json"
uv run python tools/query_washington_taxsifter.py sales \
  --county adams --parcel 2038010000001 \
  --output "$WORKDIR/wa-taxsifter-sales.json"

# Shared routing and structured ingestion.
uv run python tools/query_property.py owner HERCULES \
  --source us-wa-adams-county-taxsifter --jurisdiction 53001 \
  --output "$WORKDIR/wa-taxsifter-shared-owner.json"
uv run python tools/query_property.py parcel 2038010000001 \
  --source us-wa-taxsifter-property-family --county Adams --ingest \
  --output "$WORKDIR/wa-taxsifter-shared-account.json"

# One leaf monitor or the complete tenant-by-operation matrix.
uv run python tools/public_records_monitor.py run \
  us-wa-adams-county-taxsifter \
  --output "$WORKDIR/wa-taxsifter-adams-monitor.json"
uv run python tools/public_records_monitor.py run \
  us-wa-taxsifter-property-family \
  --output "$WORKDIR/wa-taxsifter-family-monitor.json"
```

## Mason County Tax Parcels GIS

`query_mason_county_tax_parcels.py` implements
`us-wa-mason-county-tax-parcels-gis` as the field-oriented substitute for the
challenge-observed Mason TaxSifter route. The official layer publishes current
`LastName`/`FirstName`, situs and mailing fields, market and assessed values,
exemption and assessment labels, acreage, legal/map fields, and parcel
polygons. It does not publish the Auditor's recorded-instrument index or
Treasurer balance/payment history. The published name is retained as an
assessment-roll observation, not treated as a recorded-title conclusion.

The source declares `FID` as its object-ID field and reports a
`maxRecordCount` of 1,000, while explicitly reporting that offset pagination,
server ordering, statistics, and advanced queries are unsupported. The
adapter therefore requests the complete matching FID set with
`returnIdsOnly=true`, sorts that set, and fetches exact `objectIds` batches at
the published service ceiling. A continuation cursor binds the query,
declared schema, complete FID-set fingerprint, and prior FID boundary. It does
not send `resultOffset` or `orderByFields`.

The official ArcGIS GET form was also used for a parameterized check on
2026-07-30. The ID-only response contained 60,522 occurrences spanning
`FID=0` through `FID=60521`, and exact `FID=0` returned the published parcel
fields for `PIN=219010090013`, `TERRA_PIN=21901-00-90013`, and
`Taxlot=0090013`. The count and range are rolling observations, not pinned
schema expectations; `FID=0` is deliberately supported as a valid occurrence.

Feature and parcel identities remain separate:

- `FID` is the source occurrence identity.
- `PIN`, `TERRA_PIN`, and `Taxlot` are preserved as candidate parcel joins.
- The first nonblank candidate provides the normalized parcel key, but
  uniqueness in the layer is not assumed.
- A feature without any candidate join remains an attributable observation
  rather than being assigned an invented parcel.

The county GIS, Washington's normalized statewide parcel representations, the
Mason Auditor EagleWeb index, and Washington Digital Archives title 56 remain
separately attributable. The statewide layer has the same county-assessor
origin and is useful for normalized discovery, not independent corroboration
of the county GIS values. EagleWeb and title 56 supply recorder-instrument
evidence.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect the exact layer schema and published traversal flags.
uv run python tools/query_mason_county_tax_parcels.py metadata \
  --output "$WORKDIR/mason-gis-metadata.json"

# Field, exact parcel, and spatial queries. Omit --limit for exhaustive output.
uv run python tools/query_mason_county_tax_parcels.py owner SMITH \
  --limit 50 --output "$WORKDIR/mason-gis-owner.json"
uv run python tools/query_mason_county_tax_parcels.py parcel 21901-00-90013 \
  --geometry --output "$WORKDIR/mason-gis-parcel.json"
uv run python tools/query_mason_county_tax_parcels.py point -123.10 47.20 \
  --output "$WORKDIR/mason-gis-point.json"

# Shared routing and normalized projection.
uv run python tools/query_property.py address "100 MAIN" \
  --source us-wa-mason-county-tax-parcels-gis --jurisdiction 53045 \
  --limit 50 --ingest --output "$WORKDIR/mason-gis-shared.json"

# Schema, full FID snapshot, and one rolling feature sample.
uv run python tools/public_records_monitor.py run \
  us-wa-mason-county-tax-parcels-gis \
  --output "$WORKDIR/mason-gis-monitor.json"
```

## Washington statewide normalized parcels

`query_washington_parcels.py` keeps six catalog identities around one
Washington State Parcels Project lineage:

| Source ID | Role |
|---|---|
| `us-wa-state-parcels-normalized` | Lineage and representation-health observations |
| `us-wa-current-parcels-ecology` | Normal default parcel representation |
| `us-wa-current-parcels-dnr` | Current public mirror of the same normalized lineage |
| `us-wa-current-parcels-wisaard` | Optional parity representation with an older observed snapshot |
| `us-wa-current-parcels-county-freshness` | Per-county source-file dates |
| `us-wa-current-parcels-county-land-use` | County-native land-use code descriptions |

Ecology and DNR each reported 3,321,859 rows in the verified live snapshot.
WISAARD reported 3,192,327. Representation comparisons are mirror-health
evidence, not independent corroboration: the three services carry the same
normalized state/county lineage. Ecology is the normal query default.

The current Ecology partitions for Grays Harbor (`53027`), Pend Oreille
(`53051`), San Juan (`53055`), and Walla Walla (`53071`) are empty. WISAARD
contains older same-lineage rows for Grays Harbor, San Juan, and Walla Walla;
Pend Oreille remains a gap. The census therefore associates `assessment_roll`
and `parcel_geometry` with Ecology and DNR for the 35 current nonempty county
partitions. It does not claim statewide tax-collection or recorder coverage
from these normalized parcel layers.

Parcel results retain original and normalized parcel IDs, county GEOID, situs
fields, land and building values, DOR and county-native land-use codes,
per-county file date, polygon geometry when requested, and the county
`DATA_LINK`. That link is an official discovery route for county-level owner
or taxpayer, mailing, tax/exemption, sale, and permit detail when the county
publishes it. Owner-related fields are detected from each live schema and any
published values are preserved; the verified schemas had none.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect all three representations and search the normal Ecology default.
uv run python tools/query_washington_parcels.py metadata \
  --representation all --output "$WORKDIR/wa-parcel-metadata.json"
uv run python tools/query_washington_parcels.py search 2038010000001 \
  --field parcel --geometry --output "$WORKDIR/wa-parcel.json"

# Structured counts and spatial searches.
uv run python tools/query_washington_parcels.py count --county King \
  --output "$WORKDIR/wa-king-count.json"
uv run python tools/query_washington_parcels.py point -122.3321 47.6062 \
  --geometry --output "$WORKDIR/wa-point.json"
uv run python tools/query_washington_parcels.py bbox \
  -122.36 47.58 -122.30 47.63 --geometry \
  --output "$WORKDIR/wa-bbox.json"

# Separately attributable companion tables and mirror-health observations.
uv run python tools/query_washington_parcels.py county-freshness \
  --county "San Juan" --output "$WORKDIR/wa-freshness.json"
uv run python tools/query_washington_parcels.py land-use-codes \
  --county Adams --code R --output "$WORKDIR/wa-land-use.json"
uv run python tools/query_washington_parcels.py parity --include-wisaard \
  --output "$WORKDIR/wa-parity.json"
uv run python tools/query_washington_parcels.py probe --operation all \
  --include-wisaard --output "$WORKDIR/wa-probe.json"

# The shared router exposes the same source-specific operations.
uv run python tools/query_property.py parcel 2038010000001 \
  --source us-wa-current-parcels-ecology --jurisdiction 53001 \
  --geometry --ingest --output "$WORKDIR/wa-shared-parcel.json"
uv run python tools/query_property.py count King \
  --source us-wa-current-parcels-dnr --search-field county \
  --output "$WORKDIR/wa-shared-count.json"
uv run python tools/query_property.py point \
  --source us-wa-current-parcels-wisaard \
  --longitude -122.3321 --latitude 47.6062 --geometry \
  --output "$WORKDIR/wa-shared-point.json"
uv run python tools/query_property.py freshness "San Juan" \
  --source us-wa-current-parcels-county-freshness \
  --output "$WORKDIR/wa-shared-freshness.json"
uv run python tools/query_property.py land-use R \
  --source us-wa-current-parcels-county-land-use --county-fips 001 \
  --output "$WORKDIR/wa-shared-land-use.json"
uv run python tools/query_property.py parity wisaard \
  --source us-wa-state-parcels-normalized \
  --output "$WORKDIR/wa-shared-parity.json"
```

Shared ingestion projects `property_parcel` rows into parcel, assessment,
address, owner (when present), alias, and geometry tables. Metadata, counts,
freshness, county land-use vocabulary, probes, and parity remain attributable
source observations. Monitor fingerprints cover stable schemas and source
roles; current counts, file dates, values, and sentinel comparisons remain
rolling observations.

## North Carolina OneMap

`query_nc_property.py` is the first reusable ArcGIS pilot. The official layer
covers all 100 North Carolina counties plus the Eastern Band of Cherokee
Indians and exposes county-supplied parcel, address, assessment, sale, and
geometry fields.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_nc_property.py owner "SMITH" \
  --county-fips 005 --limit 25 --output "$WORKDIR/nc-owner-direct.json"
uv run python tools/query_nc_property.py address "100 MAIN ST" \
  --county-fips 037 --output "$WORKDIR/nc-address-direct.json"
uv run python tools/query_nc_property.py parcel 3013467134 \
  --county-fips 005 --geometry --output "$WORKDIR/nc-parcel-direct.json"
uv run python tools/query_nc_property.py objectid 6061042 \
  --output "$WORKDIR/nc-object.json"
uv run python tools/query_nc_property.py probe \
  --output "$WORKDIR/nc-probe.json"
```

The `owners` field contains assessor-roll observations rather than a title or
beneficial-ownership determination. Geometry is source-provided mapping
geometry rather than a surveyed legal boundary. Results preserve the source's
revision date, county GEOID, raw attributes, schema fingerprint, and warning
text.

Canonical parcel citations have this shape:

```text
PROPERTY:<source_id>/<jurisdiction_geoid>/<record_kind>/<native_id>
```

For example:

```text
PROPERTY:us-nc-onemap-parcels/37005/parcel/3013467134
```

The citation resolver links that source ID to the official OneMap layer.
Registered source IDs link to their official landing pages; other generic
`PROPERTY:` references remain record-only. The renderer does not invent parcel
deep links.

## Bexar Central Appraisal District

`query_bexar_property.py` combines BCAD's complementary official routes under
one catalog source:

- ArcGIS table 9 supplies deterministic, pageable owner, DBA, address,
  property-ID, geographic-ID, assessment, exemption, and jurisdiction search.
- ArcGIS layer 6 adds WGS84 parcel geometry, including batched geometry
  enrichment for multi-record results.
- The Harris Govern JSON service supplies full-text search plus rich property
  detail, values, improvements, land, exemptions, appeals, taxing
  jurisdictions, roll history, and deed history.
- The classic TrueAutomation property page remains a stable fallback link.
- BCAD's Public Information Act form is cataloged as the route for certified,
  historical, GIS, and other requested data products.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_bexar_property.py owner "GRACE CHURCH" \
  --output "$WORKDIR/bcad-owner.json"
uv run python tools/query_bexar_property.py address "STONE OAK PKWY" \
  --output "$WORKDIR/bcad-address.json"
uv run python tools/query_bexar_property.py parcel 612115 --geometry \
  --output "$WORKDIR/bcad-parcel.json"
uv run python tools/query_bexar_property.py geoid 16331-001-0021 \
  --output "$WORKDIR/bcad-geoid.json"
uv run python tools/query_bexar_property.py search '"CORNERSTONE CHURCH"' \
  --output "$WORKDIR/bcad-full-text.json"
uv run python tools/query_bexar_property.py detail 612115 --year 2026 \
  --output "$WORKDIR/bcad-detail.json"
uv run python tools/query_bexar_property.py probe \
  --output "$WORKDIR/bcad-probe.json"
```

The summary table's unique `pacs_prop_id` index supplies the pagination order;
the service's 20,000-record response maximum is represented as an endpoint page
size, not an overall run ceiling. The normalized result keeps the raw formatted
appraisal value alongside an exact numeric projection, preserves all
source-native detail sections, and distinguishes appraisal-roll owner
observations from recorded conveyances. The deed-history rows are evidence
from BCAD's appraisal system; recorder copies and authoritative instrument
images remain Bexar County Clerk records.

## Denver assessor parcels and recorder joins

`query_denver_property.py` queries Denver Open Data's official assessor parcel
layer. It supports assessor-owner, situs-address, schedule/parcel-number, and
ArcGIS object-ID lookups. Normalized rows retain owner and mailing
observations, parsed situs addresses, property and zoning classifications,
appraised/assessed/taxable values, exemptions, physical characteristics, legal
descriptions, the latest published sale observation, and optional source
geometry.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_denver_property.py owner "RODRIGUEZ" --limit 25 \
  --output "$WORKDIR/denver-owner.json"
uv run python tools/query_denver_property.py address "16159 E RANDOLPH PL" \
  --limit 25 --output "$WORKDIR/denver-address.json"
uv run python tools/query_denver_property.py parcel 0017103008000 --geometry \
  --output "$WORKDIR/denver-parcel.json"
uv run python tools/query_denver_property.py objectid 1 \
  --output "$WORKDIR/denver-object.json"
uv run python tools/query_denver_property.py probe \
  --output "$WORKDIR/denver-parcel-probe.json"
uv run python tools/public_records_monitor.py run us-co-denver-parcels \
  --output "$WORKDIR/denver-parcel-monitor.json"
```

The layer's source-native response maximum is 2,000 records and its polygon
coordinates are published in `EPSG:2877`. Continuation state remains visible
when a query spans source pages. `SCHEDNUM` is the primary normalized parcel
identity; a distinct `PARCELNUM` is retained as an alternate identifier.

When the assessor row publishes `RECEPTION_NUM`, the adapter emits a join to
the separate `us-co-denver-recorder-publicsearch` source. That recorder route
adds the indexed instrument, parties, recording detail, OCR, and selected page
images. The parcel layer can publish a sale reception number beyond the
recorder tenant's observed certified-through date, so both source dates remain
part of the evidence rather than forcing the newer parcel observation into an
older recorder snapshot.

## Denver tax, foreclosure, auction, and bulk-record complements

Denver's parcel and recorder adapters are joined to five additional official
property-record sources. These remain distinct native record layers. The
Public Trustee foreclosure portal and Treasury delinquency workbook have
direct adapters; the other complements retain their separately cataloged
routes.

| Source ID | Native record layer | Integration classification | Primary joins |
|---|---|---|---|
| `us-co-denver-public-trustee-gts` | Public Trustee foreclosure file, status history, loan terms, scheduled/sold information, legal description, recorded-instrument references, and the file's TIF/PDF/DOC document index | Implemented direct search/detail/document adapter: `query_denver_foreclosures.py` | Public Trustee number; property address; current owner; NED and deed-of-trust reception numbers; scheduled sale date |
| `us-co-denver-delinquent-real-property-tax-list` | Annual Treasury XLSX covering general real-estate taxes plus published special-assessment, district, sanitary-sewer, and storm-drainage delinquencies | Implemented direct bulk/search adapter: `query_denver_delinquent_tax.py` | Tax year and parcel ID |
| `us-co-denver-spatialest-property-tax` | Daily assessment and tax-account view, address/Parcel ID/schedule-number search, and tax statements by year | Cataloged SPA route; network contract not yet mapped | Parcel ID, schedule number, property address, and tax year |
| `us-co-denver-tax-lien-auction` | Annual hosted parcel listing, tax-lien auction, certificate-of-purchase, redemption, subsequent-tax, and Treasurer's-deed stages | Cataloged seasonal auction route | Tax year and parcel ID |
| `us-co-denver-realforeclose-auctions` | Public Trustee's hosted Thursday mortgage-foreclosure auction | Cataloged auction complement; listing schema not yet verified | Scheduled sale date and property address, with Public Trustee number retained as the intended GTS pivot |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Search one file, use the source's Show All traversal, or apply native fields
uv run python tools/query_denver_foreclosures.py search \
  --foreclosure-number 2026-000418 \
  --output "$WORKDIR/denver-foreclosure.json"
uv run python tools/query_denver_foreclosures.py search \
  --show-all --limit 25 \
  --output "$WORKDIR/denver-foreclosure-page.json"
uv run python tools/query_denver_foreclosures.py search \
  --grantor "SMITH" --sale-from 2026-07-01 --sale-to 2026-07-31 \
  --limit 25 --output "$WORKDIR/denver-foreclosure-grantor.json"

# Fetch all detail sections and the document index separately
uv run python tools/query_denver_foreclosures.py detail 2026-000418 \
  --output "$WORKDIR/denver-foreclosure-detail.json"
uv run python tools/query_denver_foreclosures.py documents 2026-000418 \
  --output "$WORKDIR/denver-foreclosure-documents.json"

# Download one stable document ID returned by `documents`
uv run python tools/query_denver_foreclosures.py download \
  2026-000418 \
  1d69be5337f3de9a8e159ded1fcb7b8729ded0ea2d7c4122295136ffb9ca7118 \
  --destination "$WORKDIR/denver-foreclosure-document.pdf" \
  --output "$WORKDIR/denver-foreclosure-download.json"
uv run python tools/query_denver_foreclosures.py probe \
  --foreclosure-number 2026-000418 \
  --output "$WORKDIR/denver-foreclosure-probe.json"

# Resolve the current official release and verify its complete live contract
uv run python tools/query_denver_delinquent_tax.py discover \
  --output "$WORKDIR/denver-tax-release.json"
uv run python tools/query_denver_delinquent_tax.py probe \
  --output "$WORKDIR/denver-tax-probe.json"

# Retain and inspect a verified workbook
uv run python tools/query_denver_delinquent_tax.py download \
  --destination "$WORKDIR/denver-delinquent-tax.xlsx" \
  --output "$WORKDIR/denver-tax-download.json"
uv run python tools/query_denver_delinquent_tax.py inspect \
  "$WORKDIR/denver-delinquent-tax.xlsx" \
  --output "$WORKDIR/denver-tax-inspection.json"

# Search the current official workbook without first retaining a local copy
uv run python tools/query_denver_delinquent_tax.py search \
  --parcel 05044-12-043-000 \
  --output "$WORKDIR/denver-tax-parcel.json"

# Stream a local artifact with field filters and an optional caller ceiling
uv run python tools/query_denver_delinquent_tax.py search \
  --artifact "$WORKDIR/denver-delinquent-tax.xlsx" \
  --tax-year 2024 --owner "HOLDINGS LLC" --max-records 25 \
  --output "$WORKDIR/denver-tax-owner.json"
uv run python tools/query_denver_delinquent_tax.py search \
  --artifact "$WORKDIR/denver-delinquent-tax.xlsx" \
  --tax-year 2024 --owner "HOLDINGS LLC" \
  --cursor "$DENVER_TAX_CURSOR" \
  --output "$WORKDIR/denver-tax-owner-resumed.json"
```

`discover` resolves the latest tax-year heading and its official XLSX link.
`probe` adds HTTP metadata, signature and full-file hashes, and workbook
schema/count evidence. `download` verifies the workbook before placing it at
the selected destination; `inspect` applies the same workbook contract to a
local artifact. `search` accepts broad text, parcel/account, owner, address,
tax-year, tax-sale, and partial-payment filters. When `--artifact` is omitted,
it discovers and temporarily fetches the current official release. An omitted
`--max-records` returns every matching row; a caller-selected ceiling reports
the continuation cursor when another match remains. Set `DENVER_TAX_CURSOR` to
the exact `next_cursor` returned by that query. The opaque
`denver-delinquent-tax:v1:criteria:<sha256>:artifact:<sha256>:row:N` value is
bound to both the filters and workbook identity, preventing a later annual
release from being mistaken for the same result stream.

The July 29, 2026 live probe resolved the 2024 release as a 984,387-byte
workbook with 8,373 data rows: one row under 2019, eight under 2023, and 8,364
under 2024. The artifact SHA-256 was
`b874a7d4dcf0814cbe044284568ae5ae6e2867e7655ce6f3944bf6f9d3e411b7`;
the parsed workbook-schema fingerprint was
`0e038c4bfc0c29e5073d6561c4e70daa2f4fa89298a409089f241ff9ff324a20`,
and the adapter-schema fingerprint was
`95c965cbadb42c48a66b1d247aa0fec669aa178688432a279f867c52890fffb6`.
The observed 14 columns were owner name, parcel ID, parcel valuation, tax
owed, interest, fees and advertising, total owed, tax-sale indicator,
partial-payment indicator, three additional-owner fields, parcel address, and
legal description. `(tax_year, parcel_id)` was unique across the workbook.

Normalized rows use `property_tax_delinquency` and retain the stable account
key, owner-name list, situs address, tax year, valuation, tax/interest/fees/
total amounts, raw tax-sale and partial-payment indicators, legal description,
artifact hash, source row, and all 14 native fields. The publication describes
the release as covering several delinquency categories, but it does not
identify a category on each workbook row; the normalized row therefore keeps
the release-scope category list separately from its null per-row category.

`query_denver_foreclosures.py` searches by foreclosure number,
borrower/grantor, current owner, street, ZIP code, subdivision, status, NED
date, sold date, scheduled sale date, and expedited-sale flag. An omitted
`--limit` follows every native page. A caller-selected limit returns a
query-bound `denver-gts:v1:page:N:offset:N:...` cursor when another record
remains.

The July 29, 2026 live Show All probe reported 5,062 foreclosure files in
25-row native pages, and traversals through pages 2, 10, and 11 retained the
same total. The adapter also distinguished the portal's valid zero-record
response. `detail` traverses Address, Bankruptcy, Basics, Cure, Deed, Law
Firm, Mailings, Publications, Lienor Redemption, Sale Information,
Withdrawal, and View Documents. The sentinel `2026-000418` exposed 15
documents: 13 TIF entries, one PDF, and one DOC. Retrieving the first TIF entry
through the source viewer returned a valid `application/pdf` artifact.

Search and detail rows use `foreclosure_case` with `index`, `detail`, or
`documents` scope. The Public Trustee number is the stable case identity.
Document IDs are stable hashes of that number and the source filename, and
downloaded rows use `document_artifact`.

The Treasury delinquency page publishes the XLSX independently of the hosted
tax-auction interface. The city describes the list as ordered by parcel ID,
which makes the normalized join:

```text
Denver parcel or Spatialest tax account
  → annual delinquent-tax workbook
  → hosted tax-lien auction
```

The Public Trustee chain uses different native keys:

```text
parcel/address
  → GTS Public Trustee number
  → NED or deed-of-trust reception number
  → Denver recorder instrument
  → scheduled RealForeclose auction
```

Denver's official 2021 records-management audit also reports recorder records
from 1859, more than 11 million online documents, next-day publication, and a
bulk digital-data permit with a monthly fee. Because that permit delivers the
same native recorder corpus, it is represented as the
`request_bulk_files` capability of
`us-co-denver-recorder-publicsearch`, not as a second instrument identity.
Current permit terms remain part of the request.

## Delaware FirstMap and county property complements

`query_delaware_firstmap.py` queries the official statewide parcel-polygon and
centroid layers. An exact `pin` query joins both layers by county and PIN;
`search` and `list` traverse one county and source layer; `objectid` preserves
a source-feature lookup and joins its counterpart when a county/PIN key is
available.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_delaware_firstmap.py pin 1001300033 \
  --county "New Castle" --geometry \
  --output "$WORKDIR/firstmap-parcel.json"
uv run python tools/query_delaware_firstmap.py search 10013 \
  --county "New Castle" --layer polygon --max-records 25 \
  --output "$WORKDIR/firstmap-pin-search.json"
uv run python tools/query_delaware_firstmap.py list \
  --county Sussex --layer centroid --max-records 25 \
  --output "$WORKDIR/firstmap-sussex-centroids.json"
uv run python tools/query_delaware_firstmap.py objectid 1 \
  --layer polygon --geometry \
  --output "$WORKDIR/firstmap-object.json"
uv run python tools/query_delaware_firstmap.py probe \
  --output "$WORKDIR/firstmap-probe.json"
uv run python tools/public_records_monitor.py run us-de-firstmap-parcels \
  --output "$WORKDIR/firstmap-monitor.json"
```

The verified service contained 451,038 polygon features and 450,632 centroid
features, with a source-native page maximum of 2,000. Polygon rows add acreage
and update metadata. Centroid rows add coordinates, ZIP code, census block,
town/community, legislative and school districts, and other geographic routing
fields. The three observed blank-PIN features are retained by source layer and
`OBJECTID`; no parcel identifier is manufactured for them.

FirstMap supplies current parcel identifiers, geometry, and routing fields.
The county systems add different evidence:

| County source | Added fields and records |
|---|---|
| Kent County parcel service | Assessor-owner and address observations, deed references, assessments, characteristics, permits, code violations, surveys, and geometry |
| Sussex County parcels and assessment units | Parcel polygons plus ownership and assessment-unit rows; direct base-PIN table queries retain suffixed condominium units that the published relationship can miss |
| New Castle County parcel detail | Owner, deed and sale history, assessments, tax history, permits, violations, and property characteristics |

The Kent I2, Sussex Landmark, and New Castle PAX recorder routes remain
separate instrument/title sources. Their indexes and documents add recorded
parties and instruments that are not present in FirstMap's geometry layers.

## Montana statewide cadastral layer and monthly bulk releases

`query_montana_cadastral.py` integrates source
`us-mt-msl-cadastral`: the Montana State Library's live statewide parcel layer,
monthly statewide and county parcel archives, and richer county/statewide ORION
SQL database archives. The live adapter searches parcel/geocode, owner/DBA/care
of, site address, property/assessment identifiers, county, tax year, and WGS84
points. It uses snapshot-bound `OBJECTID` keyset traversal and can return parcel
polygons.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_montana_cadastral.py metadata \
  --output "$WORKDIR/montana-cadastral-metadata.json"
uv run python tools/query_montana_cadastral.py owner "EXAMPLE RANCH LLC" \
  --county Petroleum --tax-year 2026 \
  --output "$WORKDIR/montana-owner.json"
uv run python tools/query_montana_cadastral.py parcel 56382732101040000 \
  --geometry --output "$WORKDIR/montana-parcel.json"
uv run python tools/query_montana_cadastral.py point -110.7 46.9 \
  --output "$WORKDIR/montana-point.json"
uv run python tools/query_montana_cadastral.py counties \
  --output "$WORKDIR/montana-county-coverage.json"
uv run python tools/query_montana_cadastral.py releases \
  --output "$WORKDIR/montana-releases.json"
uv run python tools/query_montana_cadastral.py manifest \
  --dataset parcel-shp --county Petroleum \
  --output "$WORKDIR/montana-petroleum-manifest.json"
uv run python tools/query_montana_cadastral.py artifact-probe \
  --dataset orion --county 55 \
  --output "$WORKDIR/montana-orion-probe.json"
uv run python tools/query_property.py map 56382732101040000 \
  --source us-mt-msl-cadastral --jurisdiction 30069 --ingest \
  --output "$WORKDIR/montana-shared-parcel.json"
uv run python tools/public_records_monitor.py run us-mt-msl-cadastral \
  --output "$WORKDIR/montana-monitor.json"
```

The county mapping is explicit: ORION CountyPrefix is not a Census county FIPS code.
For example, ORION prefix `1` is Silver Bow (`30093`), prefix `55` is
Petroleum (`30069`), and prefix `56` is Lincoln (`30053`). The adapter and
catalog carry the complete 56-entry crosswalk, and the live county groups,
parcel directories, and ORION archives currently cover all 56 counties.

`GlobalID` is the preferred source-occurrence identity, with `OBJECTID` retained
as its fallback and transport cursor. `PARCELID` is a separate, nullable parcel
join. The bounded July 30, 2026 observation contained 920,595 features: 886,422
with `PARCELID` and 34,173 without it. A feature without `PARCELID` remains a
source occurrence instead of becoming a fabricated parcel; repeated
GlobalID/OBJECTID occurrences can also remain distinct when they share one
parcel join.

The live owner name and values are an assessment-roll observation, not recorded-title proof.
The ORION archive supplies richer CAMA context, while
county assessor and treasurer systems can supply newer local assessment and tax
detail. County clerk/recorder systems remain the deed, mortgage, lien, and
recorded-instrument sources. Other official complements include PLSS/CadNSDI,
public-lands and conservation-easement layers, historic cadastral releases, and
both statewide and county parcel archives. Rolling bulk aliases are versioned
from dataset, scope, exact filename, publisher modification marker, and listed
byte size rather than treating a mutable filename as a release ID.

## Virginia statewide parcels, local assessment, and land-record complements

`query_virginia_parcels.py` resolves the current parcel FeatureServer from the
official VGIN ArcGIS item instead of pinning the retired DWR service. It
validates the layer schema and statewide statistics before each bounded
operation, queries exact statewide or locality parcel identifiers, performs
point and bounding-box lookups, and reports locality-level coverage and source
dates.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_virginia_parcels.py metadata \
  --output "$WORKDIR/vgin-metadata.json"
uv run python tools/query_virginia_parcels.py parcel 5108700000001 \
  --field vgin-qpid --fips 51087 --geometry \
  --output "$WORKDIR/vgin-qpid.json"
uv run python tools/query_virginia_parcels.py parcel 740-783-1825 \
  --field parcel-id --fips 51087 \
  --output "$WORKDIR/vgin-local-parcel.json"
uv run python tools/query_virginia_parcels.py point -77.6104 37.7099 \
  --geometry --output "$WORKDIR/vgin-point.json"
uv run python tools/query_virginia_parcels.py localities \
  --output "$WORKDIR/vgin-locality-coverage.json"
uv run python tools/query_virginia_parcels.py identity-audit \
  --output "$WORKDIR/vgin-identity-audit.json"
uv run python tools/query_virginia_parcels.py alternatives \
  --output "$WORKDIR/vgin-alternatives.json"
uv run python tools/query_property.py parcel 5108700000001 \
  --source us-va-vgin-parcels --jurisdiction 51087 \
  --search-field vgin-qpid --geometry --ingest \
  --output "$WORKDIR/vgin-shared.json"
uv run python tools/public_records_monitor.py run \
  us-va-vgin-parcels --output "$WORKDIR/vgin-monitor.json"
```

`VGIN_QPID` is the durable statewide parcel identity. `OBJECTID` is retained
as a layer-version locator, while `FIPS + PARCELID` and `FIPS + PTM_ID` are
typed candidate joins to local systems. Continuation state binds the query,
resolved layer, compatible schema, official-item release marker, and matching
count, so a source replacement is visible rather than silently mixing pages.

The verified current layer contained 4,170,691 polygons in 136 source locality
groups: 94 counties, 38 independent cities, and four incorporated towns.
Rappahannock County (`51157`) was absent. Locality source dates are not uniform;
the oldest locality-level latest date was Martinsville City in 2017. Preserve
each row's `FIPS`, `LOCALITY`, and `LASTUPDATE` and use the layer for geometry
and local-source routing, not as a claim that every locality has the same
release date.

The VGIN File Geodatabase, statewide shapefile, and local-schema tables provide
bulk and crosswalk representations of the same VGIN lineage; they do not
independently corroborate a parcel row. Virginia's locality directory routes
the VGIN identifiers to assessors, Commissioners of the Revenue, Treasurers,
and local GIS systems for owner, address, assessment, tax, characteristic,
exemption, and local-sale fields. Circuit Court land-record systems add deeds,
deeds of trust, releases, judgments, wills, financing statements, party
indexes, and images.

### Virginia Beach delinquent real-estate taxes

`query_va_beach_delinquent_tax.py` exposes the City Treasurer's current daily
installment table as source
`us-va-virginia-beach-delinquent-real-estate-taxes`. Search by published
primary owner, mailing or situs address, exact GPIN, bill number, tax year,
installment, district, or total-due range. Omitted limits traverse the complete
source-reported match set with a snapshot-bound `OBJECTID` keyset.

```bash
uv run python tools/query_va_beach_delinquent_tax.py owner "EXAMPLE LLC" \
  --output "$WORKDIR/va-beach-owner.json"
uv run python tools/query_va_beach_delinquent_tax.py parcel 14469645070000 \
  --output "$WORKDIR/va-beach-gpin.json"
uv run python tools/query_va_beach_delinquent_tax.py bill 1125000027 \
  --output "$WORKDIR/va-beach-bill.json"
uv run python tools/query_va_beach_delinquent_tax.py search \
  --tax-year 2025 --min-total-due 1000 \
  --output "$WORKDIR/va-beach-tax-search.json"
uv run python tools/query_va_beach_delinquent_tax.py routes \
  --output "$WORKDIR/va-beach-related-routes.json"

uv run python tools/query_property.py owner "EXAMPLE LLC" \
  --source us-va-virginia-beach-delinquent-real-estate-taxes \
  --jurisdiction 51810 --ingest \
  --output "$WORKDIR/va-beach-shared-owner.json"
uv run python tools/query_property.py event 1125000027 \
  --source us-va-virginia-beach-delinquent-real-estate-taxes \
  --jurisdiction 51810 --ingest \
  --output "$WORKDIR/va-beach-shared-bill.json"
uv run python tools/public_records_monitor.py run \
  us-va-virginia-beach-delinquent-real-estate-taxes \
  --output "$WORKDIR/va-beach-tax-monitor.json"
```

The source occurrence is bill number + installment + GPIN + tax year. GPIN is
the parcel join, while `OBJECTID` is only the ArcGIS transport locator. Tax,
penalty, interest, fee, and total balances are retained as exact integer cents
and reconciled. The table describes membership and balances in the current
daily extract, so ingestion retains the source snapshot.
It does not invent a delinquency-onset date.

The route map keeps the adjacent systems distinct. Manatron supplies detailed
tax-account and limited payment-history context; the assessor supplies
assessment, characteristics, and its current owner observation; the Circuit
Court Clerk's land-record route supplies deeds, deeds of trust, satisfactions,
judgments, and UCC records. Separate Circuit Court and General District Court
case indexes add litigation context, and the Treasurer's page publishes
tax-sale notices and auction links. These complements can fill missing record
roles without turning the daily delinquency table into title, assessment,
complete payment-history, court, or sale-notice evidence.

`query_arlington_property.py` is the implemented richer local example. It
queries Arlington County's Property Map layer by RPC/parcel number, owner
mailing address, or ArcGIS object ID. It retains land, improvement, and total
assessment values; assessment date and change reason; property class, zoning,
neighborhood, map page, exemptions; lot size; legal description; source update
time; and optional Web Mercator geometry.

```bash
uv run python tools/query_arlington_property.py rpc 03001009 --geometry \
  --output "$WORKDIR/arlington-rpc.json"
uv run python tools/query_arlington_property.py parcel 03-001-009 \
  --output "$WORKDIR/arlington-parcel.json"
uv run python tools/query_arlington_property.py address "3905 44TH ST N" \
  --output "$WORKDIR/arlington-mailing-address.json"
uv run python tools/query_arlington_property.py objectid 1 \
  --output "$WORKDIR/arlington-object.json"
uv run python tools/query_arlington_property.py probe \
  --output "$WORKDIR/arlington-probe.json"
uv run python tools/public_records_monitor.py run \
  us-va-arlington-property-map \
  --output "$WORKDIR/arlington-monitor.json"
```

The layer's `address` selector searches the published owner mailing-address
fields. The layer does not publish the owner name, situs address, or sale
fields; the adapter retains those field-presence facts alongside each result.
Its source-native response maximum is 2,000 records. Arlington's related
simple parcel layer adds no distinct search or enrichment fields.

For Arlington, the Circuit Court Clerk's GovOS PublicSearch advertises a
registered, free index from 1869 for deeds, judgments, financing statements,
and wills, with paid document images. Virginia's Secure Remote Access directory
provides the corresponding participating-circuit-court land-record route;
registration, record groups, fees, coverage, and image availability are
published by the individual Clerk.

```bash
uv run python tools/public_records_catalog.py show \
  us-va-vgin-parcels --json
uv run python tools/public_records_actions.py plan \
  us-va-arlington-land-records-publicsearch \
  --operation search_instruments --selector "EXAMPLE HOLDINGS LLC" \
  --output "$WORKDIR/arlington-land-record-index-action.json"
uv run python tools/public_records_actions.py plan \
  us-va-secure-remote-access-land-records \
  --operation search_land_records --selector "Arlington deed or judgment" \
  --court-or-office "Arlington Circuit Court Clerk" \
  --output "$WORKDIR/virginia-sra-action.json"
```

## Reeves County records and Texas assignment complements

`query_reeves_records.py` queries the Reeves County Clerk's linked PublicSearch
tenant. It preserves the native document ID, instrument number and type,
recording and execution dates, book/volume/page, grantors, grantees, legal
descriptions, OCR excerpts, and page count. Exact detail and selected page
images refresh their session URLs at retrieval time while retaining stable
`doc_id` plus `page_number` locators.
An omitted `--limit` exhausts the source-native offsets; an explicit limit
returns a query-bound, source-population-anchored continuation. Resume it with
`--cursor`; `--offset` remains available for an explicitly selected native
starting position.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_reeves_records.py search "THREE RIVERS" \
  --output "$WORKDIR/reeves-party.json"
uv run python tools/query_reeves_records.py search 18-06481 \
  --output "$WORKDIR/reeves-instrument.json"
uv run python tools/query_reeves_records.py search "gathering agreement" \
  --ocr --date-from 2017-01-01 --date-to 2018-12-31 \
  --output "$WORKDIR/reeves-ocr.json"
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
```

The catalog keeps related evidence routes independent:

| Source | Adds |
|---|---|
| Reeves Clerk bulk images | Weekly or monthly recurring image deliveries |
| Culberson historical deeds | Grantor/grantee and book/volume/page discovery plus published deed images through 2009 |
| Culberson Clerk requests | Modern Oil and Gas, Deed of Trust, and other selector-specific copies |
| Texas SOS UCC portal and bulk | Debtor, secured-party, initial filing, amendment, assignment, continuation, and termination records |
| RRC P-4 bulk | Current and historical operator, effective/approval dates, and operator/gatherer/purchaser/nominator or lease-change events |
| RRC P-5 and Wellbore bulk | Operator-name resolution plus lease, well, API, and location joins for P-4 rows |

This produces a field-oriented chain: county instruments establish the
recorded conveyance, UCC records add financing and assignment events, and RRC
records add regulatory operator history. Missing modern Culberson images
remain a concrete Clerk action instead of being treated as a zero-result
search.

## Configured county GovOS/Kofile recorder tenants

`query_govos_recorders.py` applies the same verified GovOS/Kofile protocol and
instrument normalizer to four Pennsylvania recorder tenants, one Delaware
tenant, Denver, and Franklin County, Ohio, while retaining separate source
IDs, county GEOIDs, departments, coverage statements, and health sentinels.
An omitted `--limit` follows native offsets through the complete result set;
an explicit limit returns that slice with a query-bound cursor anchored to the
publisher total and protocol response type. Ingestion
retains every search and detail occurrence. For the normalized instrument,
document detail ranks above the sparser search index and retrieval time breaks
ties within the same representation, so a later index refresh cannot erase
known detail fields.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

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
```

Berks exposes separate `RP` and `MISC` departments; Kent exposes `RP` and
`UCC`; Denver exposes `RP`, `MAR`, and `MISC`. A department can be searchable
even when it has no bootstrap date-range object, so the adapter preserves
those facts independently. Denver marriage-index results remain available
through the direct adapter and canonical envelope but are preserved without
projection into the property sidecar.
Kent's working GovOS corpus is a 2025 slice. The county's I2/USLandRecords
route remains the separately cataloged full-history source.

The catalog also preserves the surrounding discovery and enrichment layers:
PA DEP and PASDA partial statewide parcels, Philadelphia's componentized OPA,
Department of Records, bulk, and recorded-document routes, Allegheny
assessments/sales/liens/parcels, Delaware FirstMap geometry, each Delaware
county's richer parcel system, and the Sussex, Kent, and New Castle recorder
alternatives.

## Philadelphia assessment, history, parcel-map, and deed routes

`query_philadelphia_property.py` keeps three machine-readable city components
separate while joining them through the identifiers the publishers expose:

- OPA current properties: owner and address observations, market value,
  classification, physical characteristics, sale/deed references, and an
  optional property point.
- OPA assessment history: annual source-labeled market and taxable/exempt
  values joined through `parcel_number`.
- Department of Records parcels: deed-description-derived polygons, map/base
  registry numbers, PIN, status, origin/inactive dates, and muniment
  references.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_philadelphia_property.py owner "PENA ROSADO" \
  --output "$WORKDIR/phila-owner.json"
uv run python tools/query_philadelphia_property.py history 341086700 \
  --from-year 2020 --output "$WORKDIR/phila-assessment-history.json"
uv run python tools/query_philadelphia_property.py parcel-shape 062N200131 \
  --by registry --output "$WORKDIR/phila-dor-parcel.json"
uv run python tools/query_philadelphia_property.py alternatives \
  --output "$WORKDIR/phila-property-routes.json"

uv run python tools/query_property.py parcel 341086700 \
  --source us-pa-philadelphia-opa-properties --jurisdiction 42101 --ingest \
  --output "$WORKDIR/phila-current-unified.json"
uv run python tools/query_property.py parcel 341086700 \
  --source us-pa-philadelphia-opa-assessment-history \
  --tax-year 2023 --jurisdiction 42101 --ingest \
  --output "$WORKDIR/phila-history-unified.json"
uv run python tools/query_property.py instrument 062N200131 \
  --source us-pa-philadelphia-dor-parcels --jurisdiction 42101 --ingest \
  --output "$WORKDIR/phila-parcel-map-unified.json"
```

An omitted result limit exhausts each source-reported match set through
ordered `objectid` keysets; an explicit limit returns a query- and
snapshot-bound cursor. Current OPA, its nightly CSV, the CARTO current table,
and the interactive property application represent the same assessment
records through different transports. The catalog records that shared record
identity so they improve availability without being counted as independent
corroboration.

The ingester can receive history before the current row: it creates a
temporary parcel identity that the authoritative current OPA row later adopts
without moving annual assessments to a second parcel. DOR geometry attaches
only when a published registry number or PIN resolves to that OPA identity;
otherwise the complete DOR observation remains available for a later join.
Philadox supplies the 1974-forward recorded-document search, while the
Department of Records copy and City Archives route extends instrument-level
work to older holdings. Atlas remains useful for cross-department permits,
licenses, violations, zoning, and deed context.

## Georgia county property routes and statewide land index

`query_georgia_property_sources.py` preserves two complementary statewide
entry points. Georgia DOR's directory routes each published county to its
assessor or tax system. GSCCCA describes a statewide deed, lien, and plat
index available through a free limited-use account, with summaries but not
document images.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_georgia_property_sources.py directory \
  --county Fulton --output "$WORKDIR/ga-fulton-property-route.json"
uv run python tools/query_georgia_property_sources.py directory qpublic \
  --limit 50 --output "$WORKDIR/ga-qpublic-routes.json"
uv run python tools/query_georgia_property_sources.py platforms \
  --output "$WORKDIR/ga-property-platforms.json"
uv run python tools/query_georgia_property_sources.py handoff \
  --output "$WORKDIR/ga-gsccca-handoff.json"
uv run python tools/query_georgia_property_sources.py probe \
  --source us-ga-dor-county-property-records-directory \
  --output "$WORKDIR/ga-dor-directory-probe.json"

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

The verified DOR snapshot contained 158 of Georgia's 159 counties: White
County was omitted. It routed 133 counties to legacy qPublic, five to
Schneider qPublic, and 20 to county-hosted systems. Atkinson was the only row
where the two published links disagreed; its description link pointed to
Bacon County. Both links remain visible so a later snapshot can resolve the
publisher discrepancy.

GSCCCA states that the consolidated index covers all Georgia counties and deed
index data since at least January 1, 1999, with older material continually
added. Its search dimensions include party, subdivision/unit/block/lot,
county-book-page, dates, party and instrument types, and geographic scope.
The free limited-use account exposes index summaries—parties, property
location, and deed book/page—but not images. County Superior Court clerks
remain the local record and copy route, while DOR's county destinations remain
the complementary assessment and tax route.

## Michigan county parcel directory and official complements

`query_michigan_property_directories.py` validates DTMB's complete 83-county
routing table and preserves each published destination URL. DTMB's
parcel-layer label is recorded as publisher evidence; URL/platform signals and
destination-verified assessment, tax, sale, bulk, and land-record capabilities
remain separate fields.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_michigan_property_directories.py list \
  --county Oakland --output "$WORKDIR/mi-oakland-route.json"
uv run python tools/query_michigan_property_directories.py platforms \
  --output "$WORKDIR/mi-platform-families.json"
uv run python tools/query_michigan_property_directories.py discovery \
  --platform bsa_online --output "$WORKDIR/mi-bsa-candidates.json"
uv run python tools/query_michigan_property_directories.py alternatives \
  --output "$WORKDIR/mi-property-alternatives.json"

uv run python tools/query_property.py discovery \
  --source us-mi-dtmb-tax-parcel-directory --jurisdiction 26125 \
  --search-field county \
  --output "$WORKDIR/mi-shared-directory.json"
uv run python tools/public_records_monitor.py run \
  us-mi-dtmb-tax-parcel-directory \
  --output "$WORKDIR/mi-directory-monitor.json"
```

The catalog separately tracks local assessors for assessment records, county
Registers of Deeds for recorded instruments, LARA plat search and the state
plat ImageServer, DNR's state-land parcel service, Treasury's millage
estimator, and the foreclosing-governmental-unit directory. These add
different fields or scopes; none is treated as a statewide replacement for
the county parcel systems.

For property-related business litigation, the separate
`us-mi-business-court-search` source can add source-published real-estate
category rulings and official PDFs. Join its case-name and case-number
candidates back to MiCOURT or the responsible clerk before treating them as a
canonical trial case. Its selected court facet and filename court-code hint
remain locators, while DTMB, the local assessor, the Register of Deeds, and
plat sources remain the controlling property-record representations.

## Ohio statewide parcels and county assessment/recorder routes

`query_ohio_statewide_parcels.py` queries OGRIP's standardized public parcel
view across all 88 counties. It supports exact state or local parcel IDs,
situs-address, mailing-address, and state land-use searches, county counts,
requested polygon geometry, live metadata, and a static field-oriented source
graph. Omitted record limits traverse the complete native match set; explicit
limits return a query-, schema-, county-, geometry-, and object-ID-bound
continuation.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_statewide_parcels.py parcel \
  39049-010-042534 --geometry \
  --output "$WORKDIR/ohio-parcel.json"
uv run python tools/query_property.py address "W DODRIDGE ST" \
  --source us-oh-ogrip-statewide-parcels --jurisdiction 39049 \
  --output "$WORKDIR/ohio-address.json"
uv run python tools/query_property.py land-use 520 \
  --source us-oh-ogrip-statewide-parcels --jurisdiction 39049 \
  --output "$WORKDIR/ohio-land-use.json"
uv run python tools/query_property.py discovery \
  --source us-oh-ogrip-statewide-parcels \
  --output "$WORKDIR/ohio-source-graph.json"
uv run python tools/public_records_monitor.py run \
  us-oh-ogrip-statewide-parcels \
  --output "$WORKDIR/ohio-monitor.json"

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

uv run python tools/query_ohio_sheriff_sales.py calendar licking \
  --month 2026-07 \
  --output "$WORKDIR/licking-sheriff-calendar.json"
uv run python tools/query_ohio_sheriff_sales.py auctions licking \
  --date 2026-07-30 --case-number 25CV01926 \
  --output "$WORKDIR/licking-realauction.json"
uv run python tools/query_licking_foreclosure_archive.py year \
  --year 2026 --case-number 25CV01926 \
  --output "$WORKDIR/licking-foreclosure-archive.json"
uv run python tools/query_property.py search 25CV01926 \
  --source us-oh-licking-sheriff-realauction \
  --jurisdiction 39089 --search-field case \
  --from-date 2026-07-30 --to-date 2026-07-30 --ingest \
  --output "$WORKDIR/licking-auction-shared.json"
uv run python tools/query_property.py search 25CV01926 \
  --source us-oh-licking-sheriff-foreclosure-archive \
  --jurisdiction 39089 --search-field case --tax-year 2026 --ingest \
  --output "$WORKDIR/licking-archive-shared.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-sheriff-realauction \
  us-oh-delaware-sheriff-realauction \
  us-oh-licking-sheriff-realauction \
  us-oh-licking-sheriff-foreclosure-archive \
  --output "$WORKDIR/ohio-sheriff-sale-monitor.json"
```

`StateParcelID` is the canonical statewide parcel key. County plus
`LocalParcelID` is retained as the local join; `GlobalID` and then `OBJECTID`
identify the published source occurrence. `CurrentTo` records upstream row
freshness separately from ArcGIS service-edit metadata. The projected record
contains parcel/address/geometry context and preserves land-use and area in
the source observation.

### Licking County Auditor GIS

`query_ohio_licking_property.py` provides the structured county-Auditor route
for parcel, assessment-owner, address, value, land-use, recent-transfer,
building, and polygon fields. `GlobalID` identifies the feature occurrence;
`Parcel` is the county business join. Null-parcel features remain source
observations. OGRIP and OnTrac are overlapping county-origin representations;
Recorder instruments are a distinct record domain. See [the source
contract](../sources/ohio-licking-auditor-gis.md).

```bash
uv run python tools/query_ohio_licking_property.py parcel \
  001-000006-01.000 --geometry \
  --output "$WORKDIR/licking-auditor-parcel.json"
uv run python tools/query_ohio_licking_property.py owner "SMITH" \
  --output "$WORKDIR/licking-auditor-owner.json"
uv run python tools/query_ohio_licking_property.py value \
  --field market-total --minimum 1000000 \
  --output "$WORKDIR/licking-auditor-value.json"
uv run python tools/query_ohio_licking_property.py probe \
  --output "$WORKDIR/licking-auditor-probe.json"
```

### Franklin County Auditor bulk releases

`query_ohio_franklin_auditor_bulk.py` keeps five official file families,
their releases, artifacts, and physical rows separately identifiable. Remote
operations discover, probe, and resumably download artifacts. Local
inspection and row streaming cover `parcel`, `value`, `payment`, `transfer`,
`sales`, and `daily-conveyance`. Shared routing uses `--dataset-type` for the
family or row type, `--collection-id` for the release, `--artifact-path` for
the local file, and optional `--artifact-source-url` for its exact official
URL. Raw release rows remain occurrence-keyed; normalized appraisal and daily
sale events use `INSTRUNO` and `CONVEYNUMBER`, respectively, with a semantic
fallback including amount and available parties when those source keys are
absent. Repeated cross-year sale history is attached to a stable parcel-event
anchor and ranked by source release before retrieval time. Franklin annual
and event projections remain on source-owned shells; OGRIP remains a separate
same-lineage representation, independent of ingestion order. See [the source
contract](../sources/ohio-franklin-auditor-bulk.md).

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

Every row retains release ID, artifact SHA-256, archive member and worksheet
when applicable, physical row, raw headers/values, and source fields. Parcel
rows can add assessment-roll owner observations and payment rows can add tax
events. Dated positive-price appraisal Sales rows become sale events while
retaining the native `VALID` code in `qualification_code`; invalid or blank
qualification is not presented as an arm's-length sale. Daily conveyances
require the native `NON-EXEMPT` state, and `SALETYPE` remains asset scope.
Transfer and value rows remain observations with parcel joins and do not
create title or recorded-instrument claims.

The Ohio recorder adapter treats PAX as a shared transport family while
retaining county-specific source components. Delaware supports anonymous
party, instrument, book/page, document-ID, and date search after its
disclaimer. If `--limit` is omitted, the adapter exhausts native result pages;
an explicit limit produces a query-bound continuation. Delaware
`InstrumentReferenceId` is the durable row identity, while instrument number,
book/page, and document ID remain searchable locators.

Licking PAX discovery currently reports that an account is required. A known
instrument number can still be resolved through
`us-oh-licking-county-recorder-instrument-detail`, which publishes anonymous
detail and PDF routes. That source ID describes the acquired representation;
the normalized instrument remains keyed under
`us-oh-licking-county-recorder-pax`. Ingestion therefore deduplicates the two
representations as one instrument while preserving which route supplied each
observation and artifact. The exact route is not a second corroborating
record. Licking County Records & Archives separately covers historical deeds
(1803–1918) and mortgages (1851–1941).

Recorder rows establish that an instrument was indexed and identify its
source-published parties and fields. They do not create current-owner
assertions during ingestion. OGRIP, the county assessor, recorder, tax,
foreclosure, and court components remain independently attributable evidence
domains. Session IDs and tickets used by PAX are transport values and are not
stored as record identities or citation URLs.

The Franklin, Delaware, and Licking sheriff-sale adapters share the verified
RealAuction calendar, preview, listing, status, and native-page traversal
family while retaining a source identity for each county tenant. Their stable
event identity is tenant plus auction AID; a case number can appear in more
than one auction. The shared router exposes `search`, `address`, `parcel`,
`sale`, `event`, `freshness`, `discovery`, and `probe`. An omitted result
limit follows the complete selected native page set, while a caller-supplied
limit returns a selection- and membership-bound continuation.

Licking County's separate JSON foreclosure archive exposes its year inventory,
complete source-reported arrays for a selected year, the rolling current
subset, and exact case lookup. Its shared operations are `search`, `address`,
`parcel`, `sale`, `event`, `releases`, `discovery`, and `probe`. The archive
retains the source case number as its identity; its maximum listed year is
mutable and can gain or correct records.

Both source families project auction and archive detail to neutral
`property_event` observations. Appraisal, bid, deposit, purchaser, and
purchase-price fields remain source-reported event context; ingestion does not
turn them into a completed conveyance, current ownership, or recorded
instrument. Exact normalized case number, event date, and an overlapping
published parcel create a `same_event_candidate` relation between the Licking
representations. All exact candidates are retained when one event has several
matches, the ambiguity remains visible, and the relation is not counted as
independent corroboration.

Published parcel keys are also retained independently of canonical parcel
resolution, so multi-parcel events remain searchable by every listed parcel.
A single exact match to an indexed OGRIP local-parcel alias can attach the
event to that parcel; multiple or absent matches remain unresolved. The
archive and auction records can then be extended with separately attributable
Common Pleas docket, recorder, assessor, and tax records according to the
field needed.

## Wisconsin statewide parcels and transfer complements

`query_wisconsin_parcels.py` searches the official annual statewide parcel
service by published owner name, situs address, owner/tax-bill mailing
address, `STATEID`, local `PARCELID`, or `TAXPARCELID`. Omitted limits traverse
the complete source-reported match set with an ordered `OBJECTID` keyset;
bounded calls return a query-, schema-, release-, and count-bound cursor.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_wisconsin_parcels.py owner "EPSTEIN" \
  --county Adams --output "$WORKDIR/wi-owner.json"
uv run python tools/query_wisconsin_parcels.py parcel 001008015540000 \
  --geometry --output "$WORKDIR/wi-parcel.json"
uv run python tools/query_wisconsin_parcels.py coverage \
  --output "$WORKDIR/wi-coverage.json"
uv run python tools/query_wisconsin_parcels.py alternatives \
  --output "$WORKDIR/wi-property-routes.json"

uv run python tools/query_property.py owner "EPSTEIN" \
  --source us-wi-statewide-parcels --jurisdiction 55001 --ingest \
  --output "$WORKDIR/wi-unified-owner.json"
uv run python tools/public_records_monitor.py run \
  us-wi-statewide-parcels --output "$WORKDIR/wi-monitor.json"
```

The source distinguishes published owners, partial source withholding, full
source withholding, and fields absent from the contributed county row.
Exact known labels for roads, water, rail, and similar map features are
retained as non-parcel observations rather than projected as parcels. The
ingester uses the source's statewide identity while retaining local parcel
and tax IDs as aliases, and keeps the county-contributor lineage and annual
roll year.

The catalog separates resilience from corroboration. Statewide and county
GDB/shapefile downloads, historical releases, and the interactive map are
representations of the same WLIP lineage. County GIS, real-property-lister,
treasurer, and Register of Deeds systems can add fresher local detail and
instrument evidence. DOR Real Estate Transfer Returns add grantor/grantee,
consideration, and recording context; the historical RETR route supports
bulk temporal analysis. The DOR parcel-format reference helps translate
contributor-specific identifiers between these systems.

## Wyoming DOR statewide annual parcels

`query_wy_dor_parcels.py` follows the official DOR parcel-viewer application
to its current annual ArcGIS layer. It searches owner tax-roll observations,
parcel and account numbers, county/jurisdiction, situs and mailing addresses,
legal descriptions, exact FIDs, points, and bounding boxes. Metadata,
identity, county, lineage, app-agreement, and exact-sentinel discovery modes
make the source contract inspectable.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_wy_dor_parcels.py owner "STATE OF WYOMING" \
  --output "$WORKDIR/wy-owner.json"
uv run python tools/query_wy_dor_parcels.py parcel 49720332401200 \
  --jurisdiction Campbell --geometry \
  --output "$WORKDIR/wy-parcel.json"
uv run python tools/query_wy_dor_parcels.py discovery agreement \
  --output "$WORKDIR/wy-app-agreement.json"

uv run python tools/query_property.py owner "STATE OF WYOMING" \
  --source us-wy-dor-statewide-parcels --jurisdiction 56005 --ingest \
  --output "$WORKDIR/wy-unified-owner.json"
uv run python tools/public_records_monitor.py run \
  us-wy-dor-statewide-parcels --output "$WORKDIR/wy-monitor.json"
```

The 2026 layer contains 373,666 feature occurrences across all 23 counties.
Its normalized identity audit found 333,179 full parcel/account occurrences,
37,474 specific-parcel-only occurrences, no observed account-only fallback,
and 3,013 FID-only occurrences. Account-only remains a supported annual key
for future releases. Omitted limits traverse ordered `FID ASC` pages until the
matching source result is exhausted; caller windows return a continuation.

Annual business identity and geometry occurrence identity remain separate.
The largest audited annual tuple appears on 84 FIDs with the same tax-roll
payload and different shape measurements. Ingestion therefore retains every
FID observation and alias while projecting one deterministic annual parcel,
assessment, owner/address set, and lowest-FID geometry representative. FID-only
rows remain occurrence evidence without a parcel shell. This is the concrete
Wyoming application of methodology observation #2169.

Owner names are assessment-roll observations, not recorded title events. The
DOR bulk download is a same-publisher representation of the annual data.
County assessor and treasurer systems add current account and payment detail;
county clerk indexes and instruments add title-event evidence. The catalog and
census expose the statewide roll/geometry roles for every county while keeping
those local complements distinct.

## New York statewide parcels and ORPTS transfer records

`query_ny_statewide_parcels.py` treats the Statewide Parcel Map Program as
three attributable components in one official record lineage. The centroid
component supplies the statewide annual assessment and published owner
snapshot for all 62 counties. Public parcel polygons supply boundary geometry
for the participating 38-county release, while the state-owned component
supplies its separately scoped statewide subset. The adapter reports those
coverage roles independently and exposes the published `SWIS_SBL_ID`,
`SWIS_PRINT_KEY_ID`, and `MUNI_PARCEL_ID` joins.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ny_statewide_parcels.py owner "EXAMPLE LLC" \
  --county Albany --output "$WORKDIR/ny-owner.json"
uv run python tools/query_ny_statewide_parcels.py parcel 010100123456 \
  --id-type swis-print-key --output "$WORKDIR/ny-parcel.json"
uv run python tools/query_ny_statewide_parcels.py point -73.7562 42.6526 \
  --geometry --output "$WORKDIR/ny-boundary.json"
uv run python tools/query_ny_statewide_parcels.py coverage \
  --output "$WORKDIR/ny-coverage.json"
uv run python tools/query_ny_statewide_parcels.py alternatives \
  --output "$WORKDIR/ny-parcel-routes.json"

uv run python tools/query_property.py owner "EXAMPLE LLC" \
  --source us-ny-statewide-parcels --jurisdiction 36001 --ingest \
  --output "$WORKDIR/ny-unified-owner.json"
uv run python tools/public_records_monitor.py run \
  us-ny-statewide-parcels --output "$WORKDIR/ny-parcel-monitor.json"
```

The normalized parcel uses the exact statewide identifiers across all three
components. A centroid observation owns the mutable annual assessment,
mailing, and published-owner snapshot. Polygon observations add their actual
boundary geometry and remain attributable observations; the derived centroid
point does not replace a parcel boundary. Bulk downloads and the public map
are same-lineage acquisition routes. County real-property offices, clerks,
OGS land records, and the assessment coordinate lookup add local detail,
recorded instruments, state-land context, or an alternate address/parcel
pivot.

`query_ny_salesweb.py` covers ORPTS real-property transfers outside New York
City for the source's rolling ten-year window. It searches buyer, seller,
street, tax-map number, book/page, date, price, property class, county,
municipality, and school district; exact detail is keyed by
`saleTranNmbr`. The source's municipality, school, property-class, and
condition reference tables are available through the same adapter.

```bash
uv run python tools/query_ny_salesweb.py search \
  --seller "EXAMPLE LLC" --county Albany --all \
  --output "$WORKDIR/ny-sales.json"
uv run python tools/query_ny_salesweb.py detail 123456789 \
  --output "$WORKDIR/ny-sale-detail.json"
uv run python tools/query_ny_salesweb.py export \
  --county Albany --sale-from 2025-01-01 --sale-to 2025-12-31 \
  --csv-output "$WORKDIR/ny-sales.csv" \
  --output "$WORKDIR/ny-sales-export.json"
uv run python tools/query_property.py instrument 2025/19127 \
  --source us-ny-orpts-sales-web --jurisdiction 36001 --ingest \
  --output "$WORKDIR/ny-book-page.json"
uv run python tools/public_records_monitor.py run \
  us-ny-orpts-sales-web --output "$WORKDIR/ny-salesweb-monitor.json"
```

Sale identity and parcel identity remain separate. The normalized transfer
keeps seller and buyer as grantor and grantee, records the assessment values
observed at sale, and links to a parcel only through the exact published
`SWIS_PRINT_KEY_ID`; it does not turn the buyer into a current-ownership
claim. The CSV is a useful acquired artifact but omits `saleTranNmbr`, so the
JSON search/detail record supplies durable sale identity. ACRIS covers four
New York City boroughs, the Richmond County Clerk covers Staten Island,
county clerks provide instruments and images, and local assessor or archival
routes cover older transfers and fields outside SalesWeb.

The NYC Property Information Portal is the five-borough parcel and assessment
counterpart. Its five DOF ArcGIS layers share the ten-digit BBL while retaining
each layer's `OBJECTID`, `(PARID, TAXYR, PERIOD)` assessment representation,
and full exemption child tuple as separate source occurrences.

```bash
uv run python tools/query_property.py parcel 1013860010 \
  --source us-nyc-property-information-portal --ingest \
  --output "$WORKDIR/nyc-pip-parcel.json"
uv run python tools/query_property.py history 1013860010 \
  --source us-nyc-property-information-portal \
  --output "$WORKDIR/nyc-pip-history.json"
uv run python tools/query_property.py exemptions 1013860010 \
  --source us-nyc-property-information-portal \
  --output "$WORKDIR/nyc-pip-exemptions.json"
uv run python tools/public_records_monitor.py run \
  us-nyc-property-information-portal \
  --output "$WORKDIR/nyc-pip-monitor.json"
```

The shared parcel projection is BBL-only and order independent. Detail owners
remain tax-roll assertions; identical owners and situs addresses deduplicate.
Only current-assessment rows project into the assessment table, using the
highest numeric period and then lowest `OBJECTID` for a tax year; every current
alternative, history representation, exemption, and feature occurrence stays
available in raw provenance. PIP's ACRIS display is the same recording lineage,
while the full four-borough ACRIS and Richmond County Clerk routes are
field-matched recorded-instrument complements.

## New Jersey parcels, MOD-IV, SR1A, and local record routes

`query_new_jersey_parcels.py` resolves the current official NJGIN item before
querying the statewide parcel/MOD-IV layer. It preserves three distinct
states: a parcel with joined MOD-IV fields, a parcel without a joined MOD-IV
row, and source-redacted owner fields. No owner is synthesized from an empty
hosted field.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_new_jersey_parcels.py address "FOREST AVE" \
  --county Essex --output "$WORKDIR/nj-address.json"
uv run python tools/query_new_jersey_parcels.py block-lot \
  --municipality-code 0703 --block 14 --lot 5 \
  --geometry --output "$WORKDIR/nj-block-lot.json"
uv run python tools/query_new_jersey_parcels.py search \
  --has-modiv no --county Essex --output "$WORKDIR/nj-unmatched.json"
uv run python tools/query_new_jersey_parcels.py alternatives \
  --output "$WORKDIR/nj-property-routes.json"

uv run python tools/query_property.py parcel 0703_14_5 \
  --source us-nj-njgin-parcels-modiv --jurisdiction 34013 --ingest \
  --output "$WORKDIR/nj-unified-parcel.json"
uv run python tools/query_property.py point \
  --source us-nj-njgin-parcels-modiv \
  --longitude -74.30143 --latitude 40.55346 \
  --output "$WORKDIR/nj-point.json"
uv run python tools/public_records_monitor.py run \
  us-nj-njgin-parcels-modiv --output "$WORKDIR/nj-monitor.json"
```

The complete MOD-IV table is a separate official component because it
contains assessment rows that do not join to a parcel polygon. NJGIN bulk and
interactive products improve acquisition and verification for the same
parcel lineage; annual Division of Taxation MOD-IV files add year-specific
snapshots. Municipal assessors and County Boards of Taxation add property
record cards, certified lists, corrections, omitted/added assessments, and
appeal records. County clerks/registers and State Archives holdings provide
the deeds, mortgages, releases, assignments, legal descriptions, and
historical title records behind statewide index observations.

`query_new_jersey_sr1a.py` treats the Division of Taxation sale files as a
separate transaction source. It discovers the current release set, validates
ZIP members and the official 663-character layout, and searches grantor,
grantee, property location, block/lot, deed references, dates, prices, and
transfer fees. Cursors are bound to the selected release artifacts.

```bash
uv run python tools/query_new_jersey_sr1a.py manifest \
  --output "$WORKDIR/nj-sr1a-manifest.json"
uv run python tools/query_new_jersey_sr1a.py validate \
  --release sr1a-ytd-2026 \
  --output "$WORKDIR/nj-sr1a-validation.json"
uv run python tools/query_new_jersey_sr1a.py search "EXAMPLE LLC" \
  --field party --county Essex --include-raw-line \
  --output "$WORKDIR/nj-sr1a-party.json"
uv run python tools/query_new_jersey_sr1a.py alternatives \
  --output "$WORKDIR/nj-sr1a-complements.json"
uv run python tools/query_new_jersey_tax_court.py search "EXAMPLE LLC" \
  --field case-title --dataset both \
  --output "$WORKDIR/nj-tax-court-cases.json"
uv run python tools/query_new_jersey_tax_court.py alternatives \
  --output "$WORKDIR/nj-tax-court-complements.json"

uv run python tools/query_property.py owner "EXAMPLE LLC" \
  --source us-nj-treasury-sr1a-sales --jurisdiction 34013 \
  --tax-year 2025 --ingest --output "$WORKDIR/nj-sr1a-unified.json"
uv run python tools/query_property.py parcel 0703_14_6 \
  --source us-nj-treasury-sr1a-sales \
  --output "$WORKDIR/nj-sr1a-parcel-sales.json"
uv run python tools/public_records_monitor.py run \
  us-nj-treasury-sr1a-sales us-nj-tax-court-property-cases \
  us-nj-tax-court-opinions \
  --output "$WORKDIR/nj-property-court-monitor.json"
```

The parser retains each field's raw value and date encoding, and reports which
transfer-fee normalization the release required. Repeated rows across
year-to-date and annual snapshots share a stable sale identity while retaining
their archive, member, row, and record-hash occurrences. Ingestion links exact
municipality/block/lot coordinates to the NJGIN parcel identity, stores
grantor and grantee as transaction parties, and preserves assessment-at-sale
without turning either party into an ownership assertion.

The current Tax Court reports add case caption, docket, entered date, county,
block, lot, unit, and assessment year. They omit municipality, so their parcel
coordinates remain candidates until a municipality-bearing judgment, case
jacket, local assessment record, or other exact crosswalk supplies the missing
join component. Docket identity remains separate from each workbook-row
occurrence, including duplicate and multi-property rows. Historical judgment
lists, GovConnect notices, Case Jacket Public Access, opinions, appeal
statistics, and county tax boards are cataloged as distinct follow-up routes
rather than being hidden behind the current-report adapter. DCA property
registrations, county instruments, local assessment records, and OPRA
custodian routing add regulatory context, title evidence, and defined records
absent from the statewide datasets.

`query_new_jersey_dca_property.py` searches the DCA Bureau of Housing
Inspection registration index at its native building grain. The 13-digit
building registration is the source-record key; its first 10 digits identify
the related property registration. County and municipality lookup IDs come
from the current official search page, and continuation advances by ordered
building registration because the portal's native next link is malformed.

```bash
uv run python tools/query_new_jersey_dca_property.py registration \
  0714002653 --output "$WORKDIR/nj-dca-registration.json"
uv run python tools/query_new_jersey_dca_property.py parcel \
  --county Essex --block 441 --lot 61 \
  --output "$WORKDIR/nj-dca-block-lot.json"
uv run python tools/query_new_jersey_dca_property.py address Broadway \
  --municipality "Newark City" \
  --output "$WORKDIR/nj-dca-address.json"
uv run python tools/query_new_jersey_dca_property.py lookups \
  --county Essex --output "$WORKDIR/nj-dca-lookups.json"
uv run python tools/query_new_jersey_dca_property.py alternatives \
  --output "$WORKDIR/nj-dca-alternatives.json"

uv run python tools/query_property.py account 0714002653 \
  --source us-nj-dca-property-registration --jurisdiction 34 --ingest \
  --output "$WORKDIR/nj-dca-unified.json"
uv run python tools/query_property.py parcel 441/61 \
  --source us-nj-dca-property-registration --jurisdiction 34013 \
  --output "$WORKDIR/nj-dca-parcel.json"
uv run python tools/public_records_monitor.py run \
  us-nj-dca-property-registration \
  --output "$WORKDIR/nj-dca-monitor.json"
```

The registered-owner field is retained as the relationship published in the
DCA regulatory registration, not as a deed-title assertion. The source lacks
the MOD-IV municipality code needed for an exact statewide parcel join, so
county/municipality/block/lot evidence remains with an unresolved candidate
link. NJGIN and local assessment records add parcel and assessment context;
SR1A and county clerk/register records add transfer and recorded-instrument
evidence. The official BHI Active Building report is a same-agency reporting
view over active, non-redacted rows and can add published owner/agent contact,
last cyclical inspection, units, stories, construction, and classification
fields. DCA OPRA and statewide custodian routes cover defined records not
published through the index or report.

For reasoning and valuation analysis,
`query_new_jersey_tax_court_opinions.py` joins its published or unpublished
opinion occurrences to reports and case jackets by normalized docket number.
The opinion document and its retrieval transport remain separate from the
assessment, parcel, sale, and title records that supply property facts; the
seven opinion alternatives and their same-lineage relationships are detailed
in `docs/modules/legal.md`.

## Palm Beach Property Appraiser, Tax Collector, Official Records, and adjacent routes

`query_palm_beach_property_appraiser.py` queries the County's anonymous
`PARCEL_DETAILS` FeatureServer layer. The durable source record is an
`OBJECTID` feature occurrence. `PARCEL_NUMBER` is a candidate exact
tax-account/PCN join whose uniqueness is not assumed; `PARID` remains a
separate published geometry/group identifier until source evidence establishes
another role.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_palm_beach_property_appraiser.py owner SMITH \
  --limit 100 --output "$WORKDIR/pbc-owner.json"
uv run python tools/query_palm_beach_property_appraiser.py parcel \
  04364325000005040 --geometry \
  --output "$WORKDIR/pbc-parcel.json"
uv run python tools/query_palm_beach_property_appraiser.py sale 5021/1011 \
  --field book-page --output "$WORKDIR/pbc-sale.json"
uv run python tools/query_palm_beach_property_appraiser.py bbox \
  -80.15 26.65 -80.05 26.75 --limit 100 \
  --output "$WORKDIR/pbc-bbox.json"
uv run python tools/query_palm_beach_property_appraiser.py discovery \
  --output "$WORKDIR/pbc-source-contract.json"

uv run python tools/query_property.py parcel 04364325000005040 \
  --source us-fl-palm-beach-property-appraiser --jurisdiction 12099 \
  --geometry --ingest --output "$WORKDIR/pbc-unified-parcel.json"
uv run python tools/public_records_monitor.py run \
  us-fl-palm-beach-property-appraiser \
  --output "$WORKDIR/pbc-property-monitor.json"
```

The parcel selector accepts either the published 17 digits or its punctuated
PCN form. A clean numeric `BOOK/PAGE` sale selector is recognized directly;
`--field book-page` remains available when callers want to state that intent
explicitly.

Ordered ArcGIS pagination runs within the maximum matching `OBJECTID` observed
when a scan starts. Omitting `--limit` traverses the complete bounded
population; a bounded response returns a cursor tied to the criteria, declared
schema, population boundary, count, and last occurrence. Repeated parcel
numbers remain separate output and source-observation rows.

The adapter keeps assessment-owner and last-sale labels distinct from recorded
title. A published book/page is an exact pivot to the Clerk adapter, not an
instrument copy. `CONFID_FLG` and blank owner/address values are preserved as
publisher redaction state without assigning an undocumented meaning to the
flag.

The official `PAO.PARCEL_QSALES` layer currently exposes a heavily overlapping
schema and the same rolling row count as `PARCEL_DETAILS`; it is cataloged as a
same-publisher sale-age thematic representation, not independent
corroboration. Exact row and `OBJECTID` parity have not been established, so
the primary adapter ingests `PARCEL_DETAILS` only.

The Property Appraiser's data page advertises free CAMA, NAL, situs, owner, and
vector files. Its current cloud-drive invitation presents consent language
scoped to a particular county audit and mentions confidential or exempt data.
That discrepancy is attached only to the flat-file transfer operation. The
anonymous GIS and Florida DOR bulk roll remain usable field-specific routes.

An official Tax Deeds detail demonstrates the cross-source PCN transform:
`04-36-43-25-00-000-5040` links to the appraiser parameter
`04364325000005040`. Compare the 17 digits after removing punctuation, while
retaining the tax-deed case/event as its own source occurrence.

`query_palm_beach_tax_collector.py` queries the Constitutional Tax Collector's
official Aumentum PublicAccessNow tenant. Its QuickSearch configuration names
the `AUMENTUMTAX` data source and `QuickSearch` view, publishes ten rows per
native page, and sets `maximumRecords` to 300. That value is the publisher's
return-window boundary: a reported total of 300 is `partial`, not proof that
exactly 300 accounts match. The adapter does not add another default result
cap. A caller-selected limit returns a query/settings/total/offset-bound
cursor; the shared router's `--max-records` is also honored as a caller-selected
return bound.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect source configuration and account-refresh routing.
uv run python tools/query_palm_beach_tax_collector.py settings \
  --output "$WORKDIR/pbc-tax-settings.json"
uv run python tools/query_palm_beach_tax_collector.py sync-status \
  --output "$WORKDIR/pbc-tax-refresh-contract.json"

# QuickSearch discovery by the source's actual fields.
uv run python tools/query_palm_beach_tax_collector.py owner SMITH \
  --limit 100 --output "$WORKDIR/pbc-tax-owner.json"
uv run python tools/query_palm_beach_tax_collector.py address \
  "15775 ORANGE" --output "$WORKDIR/pbc-tax-address.json"
uv run python tools/query_palm_beach_tax_collector.py parcel \
  04-36-43-25-00-000-5040 \
  --output "$WORKDIR/pbc-tax-pcn.json"

# Exact account state, bills/installments, and native payment-history pages.
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

# Shared routing, conservative projection, and lifecycle monitoring.
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

The 17-digit PCN is the cross-source parcel join. `AlternateKey` is the
Tax Collector's account locator. Bill ID, bill number, installment, receipt
number, and payment occurrence remain distinct source identities. If
`--alternate-key` is omitted for an exact account operation, the adapter
resolves it through an exact PCN search and requires an unambiguous published
locator.

Account owner labels remain tax-account observations rather than title
conclusions. A payment-history payer remains a payer observation and is never
projected as an owner. `Confidential` and `*******` publisher states are kept
without reconstruction. Current amounts, paid/delinquent status, payment
capability, source messages, and `lastUpdated` are retrieved-state
observations; due dates and effective payment dates retain their own published
roles. This preserves source text such as delinquency or omitted-tax flags
without turning a mutable balance snapshot into a dated event.

Account summary uses tenant modules 462 and 465, bills use module 652, and
payment history uses module 663. Bill-detail module IDs are discovered from
the page because tenant page configuration is not a universal Aumentum
contract. Module 461's sync-status response describes routing from
`RevObjId`/`a` to the account page. It is not treated as a per-account
completion poll; the separate `FetchData` route is a one-shot refresh.

The source's alternatives are field-matched. The Property Appraiser and
Florida DOR roll add assessment, address, value, legal, and geometry context.
Official Records supplies deed, mortgage, party, and recorded-document
evidence. Tax Deeds supplies certificates, cases, auction events, bids,
notices, and case documents. These routes can recover valuable missing fields
without merging their provenance into the Tax Collector account.

`query_palm_beach_tax_deeds.py` searches the Clerk's anonymous tax-deed
portal by certificate, case, PCN, Tax Collector number, applicant, source-
reported owner label, lifecycle status, published auction date, or the current
Lands Available set. Name and status searches use the date range required by
the native form; sale-date choices are discovered live rather than hardcoded.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_palm_beach_tax_deeds.py discovery \
  --output "$WORKDIR/pbc-tax-deed-discovery.json"
uv run python tools/query_palm_beach_tax_deeds.py parcel \
  04-36-43-25-00-000-5040 \
  --output "$WORKDIR/pbc-tax-deed-pcn.json"
uv run python tools/query_palm_beach_tax_deeds.py owner PRIEST \
  --from-date 2023-01-01 --to-date 2024-12-31 \
  --output "$WORKDIR/pbc-tax-deed-owner.json"
uv run python tools/query_palm_beach_tax_deeds.py lands-available \
  --output "$WORKDIR/pbc-lands-available.json"
uv run python tools/query_palm_beach_tax_deeds.py detail 43079 \
  --output "$WORKDIR/pbc-tax-deed-43079.json"
uv run python tools/query_palm_beach_tax_deeds.py document 43079 24748216 \
  --document-output "$WORKDIR/pbc-tax-certificate-24748216.pdf" \
  --output "$WORKDIR/pbc-tax-certificate-24748216.json"

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

The form POST establishes session search state and the jqGrid route reports
record and page totals. With no caller limit, the adapter follows every
reported native page. A bounded continuation is tied to the criteria, grid
schema, native page size, reported totals, and first-page occurrence snapshot;
a completed multi-page traversal checks that first page again.

The portal row ID locates a published case occurrence. Case number, tax
certificate number, reversible 17-digit PCN, auction event, and document
occurrence/image ID remain separate identities. Clerk status is mutable
lifecycle state, and applicant/property-owner labels remain source-reported
event roles rather than current-title conclusions.

Exact detail retains notes and every document-inventory row, including
`Image Not Available`. Before downloading a listed image, the adapter confirms
that the image ID belongs uniquely to that exact case and verifies that the
response is a PDF. These public images are uncertified; the Clerk's certified-
copy service remains a separate route. Property Appraiser, Tax Collector,
Official Records, eCaseView, certified-copy, and legal-notice routes are
reported as field-specific complements.

`query_palm_beach_official_records.py` resolves a known official instrument
number or book/page through the Clerk's deterministic Landmark Web routes. The
normalized record keeps the Clerk's official instrument number as its durable
identity and preserves the portal's internal document ID only as a locator.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_palm_beach_official_records.py instrument \
  19860255822 --output "$WORKDIR/pbc-instrument.json"
uv run python tools/query_palm_beach_official_records.py book-page \
  5021 1011 --output "$WORKDIR/pbc-book-page.json"
uv run python tools/query_palm_beach_official_records.py image \
  --instrument 19860255822 --image-page 1 \
  --document-output "$WORKDIR/pbc-19860255822-page-1.png" \
  --output "$WORKDIR/pbc-image.json"
uv run python tools/query_palm_beach_official_records.py routes \
  --output "$WORKDIR/pbc-routes.json"

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

Instrument ingestion stores grantors and grantees as instrument parties,
links the source-published PCN to the Property Appraiser's normalized
`PARCEL_NUMBER` candidate join, and emits a sale event for an indexed deed
without converting the parties into current-ownership assertions. The join
does not collapse distinct appraiser `OBJECTID` occurrences. Online image
availability is metadata on the instrument; a downloaded PNG page is a
separate content-addressed artifact linked back to it.

Broad party, parcel, legal-description, case-number, and date discovery is a
separate interactive portal operation where reCAPTCHA was observed. The
source-route record therefore also names the Clerk's paid daily index, the
historical index/image archive, Records Service, Property Appraiser, Florida
DOR roll, Tax Collector, Tax Deeds portal, and eCaseView. Those routes add
bulk discovery, unavailable-image recovery, current parcel/value/tax context,
tax-deed proceedings, and underlying court cases while retaining their own
source identities.

## Broward Official Records

`query_broward_official_records.py` uses the County's public AcclaimWeb session
for party, parcel, and exact instrument discovery. Instrument number is the
record identity; result-row transaction IDs and document viewer URLs are
session locators. A PDF acquired from the detail session is stored as a
separate content-addressed artifact.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

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
  --output "$WORKDIR/broward-download.json"

uv run python tools/query_property.py search "EPSTEIN, JEFFREY" \
  --source us-fl-broward-official-records --jurisdiction 12011 \
  --search-field grantor --ingest \
  --output "$WORKDIR/broward-shared-name.json"
uv run python tools/public_records_monitor.py run \
  us-fl-broward-official-records \
  --output "$WORKDIR/broward-monitor.json"
```

The separate County release publishes ten continuous days of verified index
and image files. `bulk` joins DOC instruments, NME parties, LNK
cross-references, and LGL legal/parcel pairs on instrument number; RNG records
the release bounds and IMG contains single-page TIFFs.

```bash
uv run python tools/query_broward_official_records.py bulk \
  "$WORKDIR/07-26-2026doc-ver.txt" \
  --names "$WORKDIR/07-26-2026nme-ver.txt" \
  --links "$WORKDIR/07-26-2026lnk-ver.txt" \
  --legals "$WORKDIR/07-26-2026lgl-ver.txt" \
  --range-file "$WORKDIR/07-26-2026doc-ver-rng.txt" \
  --images "$WORKDIR/07-26-2026img.ZIP" \
  --output "$WORKDIR/broward-daily.json"
```

`routes` keeps four acquisition paths explicit: portal search, the
session-scoped public PDF and online certified-copy flow, the rolling daily
release, and the Search & Copy service for older material. It also lists the
Property Appraiser, Florida DOR roll, tax collector, Clerk case search, and tax
deed systems as complementary sources joined by parcel ID, party name, case
number, book/page, or recording date.

## U.S. Virgin Islands Recorder of Deeds

`query_usvi_recorder.py` follows the anonymous guest workflow on the
CountyFusion tenant linked by the Office of the Lieutenant Governor. It
supports the source's native name, date/type, document-number, book/page, and
legal-field forms. Every source-reported page is traversed before an explicit
caller offset or limit is applied.

Instrument identity is `district + instId`. Instrument number and book/page
remain exact-search and join keys. Detail and page access first reacquire the
instrument through exact number search and then verify district, `instId`, and
instrument number before selecting the session-scoped record.

```bash
uv run python tools/query_property.py search "SMITH" \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" \
  --output "$WORKDIR/usvi-recorder-search.json"
uv run python tools/query_property.py instrument 2026000625 \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
  --ingest --output "$WORKDIR/usvi-recorder-detail.json"
uv run python tools/query_property.py download 2026000625 \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
  --page-number 1 --destination "$WORKDIR/usvi-recorder-page-1.png" \
  --ingest --output "$WORKDIR/usvi-recorder-page.json"
uv run python tools/public_records_monitor.py run \
  us-vi-recorder-of-deeds-countyfusion \
  --output "$WORKDIR/usvi-recorder-monitor.json"
```

Normalization stores Party 1/Party 2, legal descriptions, and dates on the
recorded instrument. It does not infer a parcel, sale, title state, or current
owner. A selected PNG is a nested `document_artifact` with rights tier
`official_host_reference_image_uncertified`, matching the Recorder's statement
that online images are reference material. The monitor uses a fixed
12-request exact-detail sentinel and does not fetch an image.

The newer `usvi.publicsearch.us` portal is an alternate interface from the
same Recorder authority and is therefore not independent corroboration.
Capture CAMA adds assessment, parcel, situs, and tax fields as a separate
field-matched source rather than a substitute for recorded title.

## U.S. Virgin Islands Capture CAMA assessment and tax

`query_usvi_property_tax.py` follows the anonymous territorial Capture CAMA
WebForms workflow. Native owner, formatted-parcel, address, and legal searches
traverse every source-reported `GridView1` page before an explicit caller
window is applied. Exact detail retains the formatted parcel plus tax year as
the observation identity; the changing internal `ParcelId` remains a
tax-year-specific locator.

```bash
uv run python tools/query_property.py owner "SMITH" \
  --source us-vi-property-tax-capture-cama \
  --jurisdiction 78 --tax-year 2026 \
  --output "$WORKDIR/usvi-cama-owner.json"
uv run python tools/query_property.py search "ST JAMES" \
  --source us-vi-property-tax-capture-cama \
  --search-field legal --tax-year 2026 \
  --output "$WORKDIR/usvi-cama-legal.json"
uv run python tools/query_property.py parcel 1-09801-0101-00 \
  --source us-vi-property-tax-capture-cama \
  --tax-year 2026 --ingest \
  --output "$WORKDIR/usvi-cama-parcel.json"
uv run python tools/query_property.py download 1-09801-0101-00 \
  --source us-vi-property-tax-capture-cama \
  --tax-year 2026 --artifact-kind bill --statement 24457395 \
  --destination "$WORKDIR/usvi-cama-bill.html" --ingest \
  --output "$WORKDIR/usvi-cama-bill.json"
uv run python tools/public_records_monitor.py run \
  us-vi-property-tax-capture-cama \
  --output "$WORKDIR/usvi-cama-monitor.json"
```

Normalization creates parcel snapshots by formatted parcel and tax year.
Published owner labels become dated `assessment_roll` assertions tied to that
source version, not recorded-title or beneficial-owner conclusions. Valuation
history projects to assessments; statement, balance, and payment rows project
to tax events; payer names and assessor sales remain in the raw source
observation. Only actually retrieved printable HTML becomes a
`document_artifact`.

The monitor uses a fixed five-request exact parcel/year path and fetches only
the valuation component—no photograph, map, property card, bill, or receipt.
Its stable hash covers routes, fields, paging, identity domains, and complement
relationships; mutable owner/value/balance and child counts are reported
separately.

The Office of the Tax Collector supplies field-matched tax-clearance,
delinquency, payment-plan, and collection services. The Recorder of Deeds
supplies separately attributable instrument, grantor/grantee, recording-date,
and title evidence. `usvi.capturecama.com` is a failover hostname for the same
CAMA tenant, not independent corroboration. The verified source contract and
direct adapter examples are in
[`docs/sources/usvi-capture-cama.md`](../sources/usvi-capture-cama.md).

## Santa Fe County Assessor accounts and parcel geometry

`us-nm-santa-fe-assessor-accounts` queries the anonymous
`LAND/Accounts/MapServer/0` layer behind the county Tax Parcel Viewer. Shared
owner, situs-address, parcel, map, route-discovery, metadata, and probe
operations are available through `query_property.py`; shared `search` also
selects mailing address and `OBJECTID` fields with `--search-field`.

```bash
uv run python tools/query_property.py owner "SANTA FE COUNTY" \
  --source us-nm-santa-fe-assessor-accounts --jurisdiction 35049 \
  --output "$WORKDIR/santa-fe-owner.json"
uv run python tools/query_property.py search "PO BOX 276" \
  --source us-nm-santa-fe-assessor-accounts --search-field mailing \
  --output "$WORKDIR/santa-fe-mailing.json"
uv run python tools/query_property.py parcel 910002704 \
  --source us-nm-santa-fe-assessor-accounts --geometry --ingest \
  --output "$WORKDIR/santa-fe-parcel.json"
uv run python tools/query_property.py discovery routes \
  --source us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-routes.json"
uv run python tools/public_records_monitor.py run \
  us-nm-santa-fe-assessor-accounts \
  --output "$WORKDIR/santa-fe-monitor.json"
```

UPC is the preferred durable account identity, with parcel number as the
fallback. A row containing only an ArcGIS `OBJECTID` is preserved as a feature
occurrence and is not projected as a parcel. Owner names are assessment-roll
observations. The publisher supplies `current` and `prior` assessment groups
without years, so normalized rows preserve those labels as
`source-period:current` and `source-period:prior` rather than assigning a year.
Recorder numbers, book/page, `ADEED`, and `ADHST` remain join hints.

ParcelDownload, the Parcels map layer, and Notice of Value documents are
non-independent Assessor representations. ClerkTrack is the independent
recorded-instrument complement; the Treasurer search is a distinct tax-record
route. The two-request monitor separates stable route, identity, paging, and
lineage contracts from rolling owner, value, and count fields. The full route
map and discovery notes are in
[`docs/sources/santa-fe-county-property.md`](../sources/santa-fe-county-property.md).

## Santa Fe County ClerkTrack recorded instruments

`us-nm-santa-fe-clerktrack-index` follows the County Clerk's published
index-guest WebForms flow. Shared `search` and `owner` routes cover every
verified party, date, instrument, book/page, type, and legal selector.
`instrument` and `detail` reacquire an exact instrument in a fresh session and
verify the visible list/detail identity; `discovery` returns the route lineage.
With no explicit limit, search exhausts all native 25-row pages.

```bash
uv run python tools/query_property.py owner "MAYNARD*" \
  --source us-nm-santa-fe-clerktrack-index --jurisdiction 35049 \
  --output "$WORKDIR/santa-fe-clerk-owner.json"
uv run python tools/query_property.py search "QUITCLAIM DEED" \
  --source us-nm-santa-fe-clerktrack-index \
  --search-field document-type \
  --output "$WORKDIR/santa-fe-clerk-type.json"
uv run python tools/query_property.py detail 1019405 \
  --source us-nm-santa-fe-clerktrack-index --ingest \
  --output "$WORKDIR/santa-fe-clerk-detail.json"
uv run python tools/public_records_monitor.py run \
  us-nm-santa-fe-clerktrack-index \
  --output "$WORKDIR/santa-fe-clerk-monitor.json"
```

Index party displays are retained as aggregate snapshots; detail parties use
the published grantor and grantee roles. Instrument number, book, page,
recording date, type, legal text, descriptions, and Assessor join hints
project as recorded-instrument metadata. Index/detail metadata creates neither
a current-owner/title assertion nor an image artifact.

ClerkTrack detail, document purchase, copy request, and Index Books are
non-independent surfaces from the same Clerk. The Assessor Accounts layer is
independently produced field-matched evidence, while the Treasurer search is a
distinct tax-record complement. The five-request no-image monitor hashes
route, form, identity, paging, reacquisition, and lineage contracts separately
from rolling content. See
[`docs/sources/santa-fe-county-clerktrack.md`](../sources/santa-fe-county-clerktrack.md).

### Texas Railroad Commission bulk records

`query_rrc_bulk.py` implements the three official RRC bulk contracts as
separate, joinable sources:

- P-4 is a 92-byte EBCDIC state-machine format containing lease roots,
  operator history, gatherer/purchaser/nominator rows, remarks, pointers, and
  lease names.
- P-5 resolves RRC organization numbers and status from either the published
  ASCII or 350-byte EBCDIC representation.
- Wellbore Query is a headerless 59-column CSV snapshot with district, lease,
  API, operator, county, well, and location fields.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect the verified layouts and current official release listings.
uv run python tools/query_rrc_bulk.py contracts \
  --output "$WORKDIR/rrc-contracts.json"
uv run python tools/query_rrc_bulk.py releases p4 \
  --output "$WORKDIR/rrc-p4-releases.json"
uv run python tools/query_rrc_bulk.py releases p5 \
  --output "$WORKDIR/rrc-p5-releases.json"
uv run python tools/query_rrc_bulk.py releases wellbore \
  --output "$WORKDIR/rrc-wellbore-releases.json"

# Download only the caller-selected source artifact.
uv run python tools/query_rrc_bulk.py download p5 "$WORKDIR/rrc" \
  --output "$WORKDIR/rrc-p5-download.json"

# Stream and filter files already selected by the caller.
uv run python tools/query_rrc_bulk.py p5 "$WORKDIR/rrc/orf850.txt.gz" \
  --p5-number 028612 --output "$WORKDIR/rrc-operator.json"
uv run python tools/query_rrc_bulk.py p4 "$WORKDIR/rrc/p4f606.ebc.gz" \
  --oil-gas O --district 06 --lease-id 04411 \
  --output "$WORKDIR/rrc-history.json"
uv run python tools/query_rrc_bulk.py wellbore \
  "$WORKDIR/rrc/OG_WELLBORE_EWA_Report_2026-07-02.csv" \
  --operator-number 028612 --output "$WORKDIR/rrc-wells.json"

# Resolve one P-4 lease through P-5 and Wellbore.
uv run python tools/query_rrc_bulk.py resolve \
  --p4 "$WORKDIR/rrc/p4f606.ebc.gz" \
  --p5 "$WORKDIR/rrc/orf850.txt.gz" \
  --wellbore "$WORKDIR/rrc/OG_WELLBORE_EWA_Report_2026-07-02.csv" \
  --oil-gas O --district 06 --lease-id 04411 \
  --output "$WORKDIR/rrc-resolved.json"

# Monitor release metadata without transferring the bulk objects.
uv run python tools/public_records_monitor.py run \
  us-tx-rrc-p4-bulk us-tx-rrc-p5-bulk us-tx-rrc-wellbore-bulk \
  --output "$WORKDIR/rrc-monitor.json"
```

The parsers stream records and do not impose an adapter-wide result ceiling.
`--offset` and `--limit` are explicit caller output windows. Each result keeps
its raw source fields and native record locator. P-4 to P-5 joins use the RRC
organization number; P-4 to Wellbore joins use the source’s oil/gas, district,
and lease identifiers. Name matching remains a reported candidate when those
native keys are absent rather than being promoted to an exact join.

Live contract validation covered a 30,303,110-record P-4 file, both P-5
representations, and a Wellbore snapshot with 1,368,247 data rows. The
Wellbore report occupies 1,368,263 physical lines including its validated
footer. The share returned the complete object to a byte-range request, so
release monitoring uses the listing metadata and leaves large transfers as
explicit download operations.

## Orleans Parish Property Viewer

`query_orleans_property.py` queries the City of New Orleans Property Viewer
through its official ArcGIS locator and tax-parcel services. The rich
`TaxParcelPublishing` layer supplies current account, owner and mailing
fields, site address, property description, assessed and taxable values, tax
amounts, building attributes, source update date, parcel geometry, and
lot/square/block attributes. The live Property Viewer JavaScript currently
loads layer 15 from `dev/property3`; the equivalent `apps/property3` layer is
retained as the canonical mirror, not mislabeled as the deployed route. The
Property Viewer describes weekly data from the Orleans Parish Assessor and
City and uses its composite locator for address, owner, and tax-bill
discovery.

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
uv run python tools/query_orleans_property.py parcel "<PARID>" \
  --id-type parid --output "$WORKDIR/orleans-parid.json"
uv run python tools/query_orleans_property.py search "PERDIDO" \
  --output "$WORKDIR/orleans-search.json"
uv run python tools/public_records_monitor.py run \
  us-la-orleans-property-viewer \
  --output "$WORKDIR/orleans-monitor.json"
```

`TAXBILLID` is the assessment-account identity. `PARCELID`, whose source alias
is GeoPIN, and retained `PARID` support physical-parcel joins. `account` is an
exact Tax Bill ID route through the official locator and parcel layer.
`parcel` treats exactly eight decimal digits as a GeoPIN and other values as a
PARID by default; `--id-type` makes that choice explicit. The layer is a
current City tax-parcel publication; it is not represented as a historical
assessment series or a deed/title source. The catalog records its 1,000-row
endpoint page size, pagination and ordering support, polygon geometry, and
Web Mercator spatial reference. Multiple assessment accounts can share a
GeoPIN, so the adapter retains account and parcel identities separately and
uses the Tax Bill ID as the stable account identity when present.
The source does not index `PARID`, so that exact route can be materially
slower than the indexed GeoPIN path; the Orleans adapter uses a 60-second
default source timeout and still honors an explicit `--timeout`.

The source monitor makes four bounded requests: one known GeoPIN row from the
rich layer, `max(LASTUPDATE)` for freshness, one exact Tax Bill ID locator
candidate, and deployed `dev/property3` layer-15 metadata. A missing sentinel,
locator miss, ArcGIS error, or viewer-schema mismatch records a failed probe;
schema and freshness changes are fingerprinted for drift comparison. The
`apps/property3` mirror is reported separately in probe details.

## Los Angeles County parcel, tax, sale, and recorded-instrument routes

Los Angeles County separates assessment and parcel data from the
Treasurer and Tax Collector's transaction/sale publications and the
Registrar-Recorder's instrument index and copy service. The catalog preserves
those representations and records how fields from one route narrow the next.

| Route | Selectors and returned fields | Coverage and access |
|---|---|---|
| [Assessor Portal](https://portal.assessor.lacounty.gov/) | AIN, address, and map lookup; situs, legal description, land and improvement characteristics, values, base years, and assessment history | Current public parcel/assessment view |
| [County parcel REST layer](https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0) | AIN/APN, situs and legal-description fields, assessment attributes, and geometry | Official queryable layer updated weekly; its published maximum is 1,000 records per response and it supports result-offset pagination |
| [Bulk assessment rolls](https://lacounty.maps.arcgis.com/home/item.html?id=2231275cebd6426897bb9c2a7aaf9840) | Historical roll-year assessment observations keyed by AIN | Downloadable rolls from 2006-present |
| [TTC payment history](https://ttc.lacounty.gov/property-tax-payment-history/) | Exact AIN; payment ID/date, tax year and installment, tax, penalty, cost, and total paid | Anonymous same-session operation with native page totals and a source update date; all pages are followed unless the caller supplies a page bound |
| [TTC auction schedule and publications](https://ttc.lacounty.gov/schedule-of-upcoming-auctions/) | Auction cycle/phase, sale and redemption dates, official result artifacts, AIN/item, purchase price, and excess proceeds | Current schedule plus indexed official PDFs; result rows have resumable caller-selected limits |
| [Annual secured bill](https://propertytax.lacounty.gov/Home/AnnualSecuredProperty) and [TTC bill/request routes](https://ttc.lacounty.gov/request-duplicate-bill/) | Current bill/tax information, duplicate bill, or multi-parcel tax-information request | Useful official complements when transaction history does not answer a current account question |
| [Auction/status and excess-proceeds routes](https://ttc.lacounty.gov/notice-of-auction-or-sale/) | Individual tax-default, redemption/removal information, and linked claim instructions/notices | Parcel-specific follow-on route to the cycle-level sale publications |
| [Registrar-Recorder real-estate records](https://www.lavote.gov/home/recorder/real-estate-records/general-info) | Grantor, grantee, recording year, document type/number, then complete-document copy fulfillment | Records from 1850/1851-present; the public index is available at physical locations rather than as an online name or address search |

The practical join is
`address → AIN/APN → payment or sale event → legal description and likely
event year → grantor/grantee index → recording document number → instrument
copy`. The Assessor, payment history, sale publication, and recorded
instrument retain their own source identity even when their AIN or instrument
fields connect the records. A payment row is historical transaction evidence,
a sale-result row is the published auction result, and the recorded instrument
is the route for the resulting conveyance or encumbrance.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_property.py parcel 2004-001-003 \
  --source us-ca-los-angeles-county-assessor-parcels \
  --jurisdiction 06037 --ingest \
  --output "$WORKDIR/la-assessor-route.json"

uv run python tools/query_property.py account 2004001003 \
  --source us-ca-los-angeles-county-ttc-payment-history \
  --jurisdiction 06037 --ingest \
  --output "$WORKDIR/la-payment-history.json"

uv run python tools/query_property.py event all \
  --source us-ca-los-angeles-county-ttc-tax-sale \
  --jurisdiction 06037 \
  --output "$WORKDIR/la-auction-schedule.json"

uv run python tools/query_property.py search 2025B \
  --source us-ca-los-angeles-county-ttc-tax-sale \
  --process-stage sale-results --jurisdiction 06037 \
  --output "$WORKDIR/la-sale-publications.json"

uv run python tools/query_property.py sale 2025B \
  --source us-ca-los-angeles-county-ttc-tax-sale \
  --jurisdiction 06037 --ingest \
  --output "$WORKDIR/la-sale-results.json"

uv run python tools/query_los_angeles_ttc.py sources \
  --output "$WORKDIR/la-property-source-family.json"

uv run python tools/public_records_search_plan.py "EXAMPLE OWNER" \
  --address "100 MAIN ST, LOS ANGELES, CA" --jurisdiction 06037 \
  --output "$WORKDIR/la-property-plan.json"

uv run python tools/public_records_actions.py plan \
  us-ca-los-angeles-registrar-recorder-real-estate \
  --operation request_instrument_copy \
  --selector "grantor/grantee, recording year, or document number" \
  --requested-field recording_document_number \
  --requested-field complete_document_copy \
  --output "$WORKDIR/la-recorder-action.json"
```

## Orange County recorded instruments and property-tax routes

Orange County, Florida publishes three complementary property-record layers:

| Source ID | Search and release dimensions | Native record identity |
|---|---|---|
| `us-fl-orange-official-records` | Document type/number/date; grantor, grantee, or either party; case number; parcel number; legal description | Recorded instrument keyed by instrument number or book/page |
| `us-fl-orange-tax-collector-property-tax` | Current free-text/owner/address/parcel account search, bill and certificate history, bill detail, and fixed 2020 current/delinquent bulk snapshots | Exact 15-digit parcel join; separate Algolia object, TaxSys token, bill UUID, certificate, receipt, artifact/member, and source-row identities |
| `us-fl-orange-comptroller-tax-deed-sales` | Party, tax-deed application number, status, date, or parcel | Tax-deed application and sale keyed by TDA number, parcel, and sale date |

The Comptroller describes Official Records as the county index and archive for
deeds, mortgages, satisfactions, claims of lien, final judgments and orders,
notices of commencement, declarations of domicile, and other recorded
documents. Its public Tyler search is reached through the Comptroller’s
disclaimer page. A court case number can connect a recorded judgment or order
to my eClerk, but the instrument retains its recorder identity.

The Tax Collector’s current GovHub search is backed by a public Algolia index;
direct anonymous TaxSys pages add bill, certificate, assessment, exemption,
legal-description, location, and tax-line observations. The direct TaxSys
route is the retrieval route; its embedded county-taxes.net path is retained
as portal lineage.

The bulk-download page is a different freshness layer. It labels the current
and delinquent links “Daily,” but it also labels them `as of 02/17/20`, and
both observed ZIPs carry that same 2020 archive date. The current snapshot
contains tax year 2019. The adapter therefore treats the ZIPs as fixed
historical artifacts, not as a current daily feed. A useful join is
`exact 15-digit parcel → current account/bills → historical roll occurrence →
tax-deed application and sale → Official Records instrument and Clerk case`.

```bash
uv run python tools/public_records_catalog.py show \
  us-fl-orange-official-records --json
uv run python tools/public_records_catalog.py show \
  us-fl-orange-tax-collector-property-tax --json
uv run python tools/public_records_catalog.py show \
  us-fl-orange-comptroller-tax-deed-sales --json

uv run python tools/query_orange_tax_collector.py search \
  01-20-27-0000-00001 --limit 15 \
  --output "$WORKDIR/orange-tax-search.json"
uv run python tools/query_orange_tax_collector.py account \
  01-20-27-0000-00001 \
  --output "$WORKDIR/orange-tax-account.json"
uv run python tools/query_orange_tax_collector.py bill \
  01-20-27-0000-00001 ca0e3d54-aad7-11f0-bb75-005056815849 \
  --output "$WORKDIR/orange-tax-bill.json"
uv run python tools/query_orange_tax_collector.py bulk-manifest --verify-page \
  --output "$WORKDIR/orange-tax-bulk-manifest.json"
uv run python tools/query_orange_tax_collector.py bulk-download current \
  "$WORKDIR/TaxPaymentTape.zip" --inspect \
  --output "$WORKDIR/orange-tax-bulk-download.json"
uv run python tools/query_orange_tax_collector.py bulk-search current \
  "$WORKDIR/TaxPaymentTape.zip" --account 01-20-27-0000-00001 \
  --output "$WORKDIR/orange-tax-historical-account.json"

# Shared current and historical routing with conservative projection.
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
```

Normalized ingestion retains every source occurrence before projection. An
exact 15-digit account can create a Tax Collector-attributed parcel shell and
join tax-account owner labels, situs or mailing addresses, bill/payment/
certificate/tax-deed state, and explicitly published historical assessment
values. Payers and certificate buyers remain their source roles and do not
become owners; tax-deed state does not become a recorded instrument. The
monitor checks the current index and account-history contract separately from
bounded content sentinels for the two historical ZIPs. ETag and Last-Modified
remain transport observations rather than content identity.

## Miami-Dade property and Official Records

Miami-Dade uses complementary assessor, geometry, recorder-index, and document
routes. The catalog keeps those routes distinct while the normalized store
joins their records on the exact 13-digit folio and canonical Clerk File
Number.

`query_miami_dade_property.py` combines the Property Appraiser's public JSON
proxy with the county's official parcel layer:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_miami_dade_property.py owner "MIAMI-DADE COUNTY" \
  --output "$WORKDIR/miami-pa-owner.json"
uv run python tools/query_miami_dade_property.py address "111 NW 1 ST" \
  --output "$WORKDIR/miami-pa-address.json"
uv run python tools/query_miami_dade_property.py folio 0101000000020 \
  --output "$WORKDIR/miami-pa-folio.json"
uv run python tools/query_miami_dade_property.py detail 0101000000020 \
  --geometry --output "$WORKDIR/miami-pa-detail.json"
uv run python tools/query_miami_dade_property.py history 0101000000020 \
  --output "$WORKDIR/miami-pa-history.json"
uv run python tools/query_miami_dade_property.py geometry 0101000000020 \
  --output "$WORKDIR/miami-pa-geometry.json"
uv run python tools/query_miami_dade_property.py probe \
  --output "$WORKDIR/miami-pa-probe.json"
```

The normalized detail retains the full assessment and sale histories, deed
book/page references, property characteristics, improvements, legal
description, and WGS84 parcel geometry. Owner display lines remain grouped as
the source presents them; care-of and attention lines are contacts rather than
independent ownership assertions. When a later complete roll observation
changes an owner or situs/mailing address, the prior assertion is closed and
retained as history. Sparse search results do not replace a richer detail
snapshot.

`query_miami_dade_recorder.py` exposes two cataloged Clerk surfaces. The public
surface can hydrate a token already issued by the public search application,
resolve parties and financial detail from a record master ID, list the current
document-type vocabulary, and retrieve a PDF by book/page. The canonical
Official Records source also has exact CFN, book/page, and folio lookups through
the Clerk's credentialed commercial API.

```bash
uv run python tools/query_miami_dade_recorder.py document-types \
  --output "$WORKDIR/miami-recorder-types.json"
uv run python tools/query_miami_dade_recorder.py hydrate-qs "$ISSUED_QS" \
  --output "$WORKDIR/miami-recorder-results.json"
uv run python tools/query_miami_dade_recorder.py parties 50126241 \
  --output "$WORKDIR/miami-recorder-parties.json"
uv run python tools/query_miami_dade_recorder.py financial 50126241 \
  --doc-type "DEED - DEE" --recording-date 2026-01-27 \
  --output "$WORKDIR/miami-recorder-financial.json"
uv run python tools/query_miami_dade_recorder.py image 35134 800 \
  --book-type O --document-output "$WORKDIR/miami-record.pdf" \
  --output "$WORKDIR/miami-recorder-image.json"

# Exact commercial API selectors use MIAMI_DADE_CLERK_AUTH_KEY.
uv run python tools/query_miami_dade_recorder.py cfn 2026 55844 \
  --output "$WORKDIR/miami-recorder-cfn.json"
uv run python tools/query_miami_dade_recorder.py book-page 35134 800 \
  --output "$WORKDIR/miami-recorder-book-page.json"
uv run python tools/query_miami_dade_recorder.py folio 0141380670370 \
  --output "$WORKDIR/miami-recorder-folio.json"
```

Public and commercial observations retain their acquisition-route source IDs,
but instruments from both resolve to the canonical
`us-fl-miami-dade-official-records` identity. The projection preserves CFN
group/party hierarchy, exact folios, source-native dates, book/page, instrument
type, consideration, and conveyance classification. The Clerk's subscribed
daily index/image feeds and the PA file library remain cataloged data-product
routes alongside these implemented query adapters.

## Oregon taxlot sources and fallback graph

`query_oregon_taxlots.py` applies one deterministic ArcGIS retrieval core to
three independently published source components. Every query selects one
source explicitly, and each record retains its publisher, county, source-native
fields, schema fingerprint, and upstream lineage.

| Source ID | Coverage and strongest fields | Important distinction |
|---|---|---|
| `us-or-portland-regional-taxlots` | Clackamas, Multnomah, and Washington owner names and mailing addresses; parcel/account IDs; situs and legal description; building facts; three value years; sale date/price; geometry | `SOURCE` identifies the upstream Metro or Multnomah/county view and is retained as lineage |
| `us-or-metro-rlis-public-taxlots` | Tri-county parcel geometry, account/taxlot IDs, situs, buildings, values, assessed value, sales, and public-ownership classification | Personal owner names are not part of the public layer |
| `us-or-owrd-public-tax-lots` | Thirteen-county parcel discovery, geometry, map-taxlot identifiers, situs, mailing address, acreage, PLSS components, and source dates | Publishes owner mailing fields but not owner names; strongest as a county-routing and spatial complement |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_oregon_taxlots.py sources \
  --output "$WORKDIR/oregon-taxlot-sources.json"
uv run python tools/query_oregon_taxlots.py search "PORTLAND" \
  --source us-or-portland-regional-taxlots --field owner \
  --county Multnomah --output "$WORKDIR/oregon-owner.json"
uv run python tools/query_oregon_taxlots.py search "1430 KILLARNEY" \
  --source us-or-metro-rlis-public-taxlots --field address \
  --output "$WORKDIR/oregon-address.json"
uv run python tools/query_oregon_taxlots.py parcel 21E35BB01800 \
  --source us-or-metro-rlis-public-taxlots --geometry \
  --output "$WORKDIR/oregon-parcel.json"
uv run python tools/query_oregon_taxlots.py probe --all \
  --output "$WORKDIR/oregon-taxlot-probes.json"
```

### Benton County owner parties, bulk snapshots, and assessment maps

`query_oregon_benton_property.py` keeps three machine-readable county
components distinct and links them to the existing account and recorder
sources:

| Source ID | Native record grain | Strongest use |
|---|---|---|
| `us-or-benton-county-taxlot-owners` | One `taxlot_owner_party` ArcGIS row; a taxlot can repeat across owner parties or accounts | Owner/address lookup, account and cadastral identifiers, and optional WGS84 polygon geometry |
| `us-or-benton-county-assessment-bulk` | One current `bulk_release` manifest with `BentonTaxlots.gdb.zip`, `Taxlot.zip`, and `TaxlotOwners.zip` | Reproducible county snapshots and downstream geodatabase/shapefile extraction |
| `us-or-benton-county-assessment-maps` | One `assessment_map` PDF artifact per directory entry | Map sheet, map index, DLC index, and dated-map discovery |

```bash
uv run python tools/query_oregon_benton_property.py owner "NOLAN" \
  --geometry --output "$WORKDIR/benton-owner-parties.json"
uv run python tools/query_oregon_benton_property.py account 802377 \
  --output "$WORKDIR/benton-account-taxlots.json"
uv run python tools/query_oregon_benton_property.py map-taxlot 11513A000100 \
  --geometry --output "$WORKDIR/benton-map-taxlot.json"
uv run python tools/query_oregon_benton_property.py or-taxlot \
  0211.00S05.00W13A0--000000100 \
  --output "$WORKDIR/benton-or-taxlot.json"
uv run python tools/query_oregon_benton_property.py bulk-manifest \
  --output "$WORKDIR/benton-bulk-manifest.json"
uv run python tools/query_oregon_benton_property.py maps \
  --map-number 11513A --match exact \
  --output "$WORKDIR/benton-assessment-maps.json"
uv run python tools/query_oregon_benton_property.py artifact-probe \
  --component bulk --artifact TaxlotOwners.zip \
  --output "$WORKDIR/benton-bulk-artifact-state.json"
uv run python tools/query_property.py parcel 11513A000100 \
  --source us-or-benton-county-taxlot-owners \
  --jurisdiction 41003 --geometry --ingest \
  --output "$WORKDIR/benton-taxlot-unified.json"
uv run python tools/public_records_monitor.py run \
  us-or-benton-county-taxlot-owners \
  us-or-benton-county-assessment-bulk \
  us-or-benton-county-assessment-maps \
  --output "$WORKDIR/benton-property-monitors.json"
```

The unified parcel and map operations default to `MapTaxlot`;
`--search-field account`, `or-taxlot`, or `map-number` selects another native
identifier. Ingestion preserves the owner-party grain, typed account and
cadastral aliases, source-native fields, address roles, and geometry. Bulk
release and map rows remain artifact-metadata observations until a downstream
extractor reads their contents.

The county-linked Helion property source supplies current assessment, tax,
payment, sale, and improvement detail; the county account API adds assessment
and value history; and the Helion recorder supplies recorded-instrument
evidence. These are complements joined by account, map-taxlot, ORTaxlot,
owner, sale, or recording references rather than alternate names for the live
taxlot layer.

### Lincoln County PropertyWeb, taxlots, and recorder

Lincoln County publishes three independently attributable components that
share exact identifiers:

| Source ID | Native record grain | Strongest contribution |
|---|---|---|
| `us-or-lincoln-propertyweb` | Property account search result or full account detail | Owners and addresses, legal description, current and historical values, improvements, land, sales, tax bills, payments, districts, exemptions, and property-document representations |
| `us-or-lincoln-county-taxlots-wfs` | One WFS taxlot-owner geometry feature keyed by `ogc_fid` | `propertyid`, `parcelid`, owner and address fields, acreage, assessor-map links, and optional GeoJSON polygon geometry |
| `us-or-lincoln-helion-recorder` | One recorded instrument | Instrument metadata, parties, consideration, legal fields, related instruments, and the county-published document image or text state |

```bash
uv run python tools/query_oregon_lincoln_propertyweb.py search R452940 \
  --limit 25 --output "$WORKDIR/lincoln-propertyweb-search.json"
uv run python tools/query_oregon_lincoln_propertyweb.py detail \
  R452940 O0064958 \
  --output "$WORKDIR/lincoln-propertyweb-detail.json"
uv run python tools/query_oregon_lincoln_propertyweb.py document \
  appraisal-card 61623 2026 \
  --destination "$WORKDIR/lincoln-appraisal-card.pdf" \
  --output "$WORKDIR/lincoln-appraisal-card-receipt.json"

uv run python tools/query_oregon_lincoln_taxlots.py search R452940 \
  --field property --match exact --geometry \
  --output "$WORKDIR/lincoln-taxlot.json"
uv run python tools/query_property.py map 07-11-03-DC-05800-00 \
  --source us-or-lincoln-county-taxlots-wfs \
  --jurisdiction 41041 --ingest \
  --output "$WORKDIR/lincoln-taxlot-unified.json"

uv run python tools/query_oregon_helion_recorder.py detail \
  --source us-or-lincoln-helion-recorder 2025 1695 \
  --output "$WORKDIR/lincoln-instrument.json"
uv run python tools/public_records_monitor.py run \
  us-or-lincoln-propertyweb \
  us-or-lincoln-county-taxlots-wfs \
  us-or-lincoln-helion-recorder \
  --output "$WORKDIR/lincoln-property-monitors.json"
```

PropertyWeb `property_quick_ref` matches the WFS `propertyid`, and
PropertyWeb `map_number` matches the WFS `parcelid`. Structured ingestion
retains those as typed aliases on separate source snapshots, so a lookup can
connect the account and geometry without converting them into one record.

PropertyWeb sale rows also retain the normalized Helion instrument number.
When both representations are ingested, the exact identifier creates an
`instrument_parcel` link and attaches the assessor-derived sale event to the
recorder instrument. The sale remains an assessment-roll observation and the
Helion row remains a recorded-instrument observation; the link does not count
the two representations as independent corroboration.

The WFS declares EPSG:26915, accepts the adapter's EPSG:4326 request, and
reports GeoJSON coordinates as OGC CRS84. All three values remain in geometry
lineage. PropertyWeb's current generated PDFs use the same anonymous session
for filename generation and retrieval, while historical statements can expose
a direct PDF route; the adapter records which retrieval mode produced each
artifact.

### Yamhill, Clackamas, and Wasco county component families

The three county adapters share transport and projection helpers while keeping
each publisher component independently attributable:

| County | Source components | Useful joins and contribution |
|---|---|---|
| Yamhill (`41071`) | AscendWeb property accounts, current `AT_Taxlots`, retired taxlots, annual assessment permits, and the separately cataloged Helion recorder | Account and normalized map-taxlot connect account, current geometry, lineage, and permit events; recording number connects assessor sale references to recorder evidence |
| Clackamas (`41005`) | AscendWeb property accounts and CMap taxlots | Exact parcel/account and normalized taxlot connect assessment detail to geometry; CMap does not publish an owner field |
| Wasco (`41065`) | AscendWeb property accounts, taxlots, and eight surveyor layers covering road records, file-cabinet surveys, roll maps, commissioner records, land corners, plats, subdivisions, and the survey book | Account and map-taxlot connect assessment detail to the current parcel; survey identities remain separately attributed index observations |

```bash
uv run python tools/query_oregon_yamhill_property.py search "EXAMPLE LLC" \
  --source us-or-yamhill-county-at-taxlots --field owner --geometry \
  --output "$WORKDIR/yamhill-owner-taxlots.json"
uv run python tools/query_oregon_yamhill_property.py search 41270 \
  --source us-or-yamhill-county-ascendweb-property --field account \
  --output "$WORKDIR/yamhill-account.json"
uv run python tools/query_oregon_yamhill_property.py search 41270 \
  --source us-or-yamhill-county-assessment-permits --field account \
  --output "$WORKDIR/yamhill-permits.json"

uv run python tools/query_oregon_clackamas_property.py account 05001234 \
  --geometry --output "$WORKDIR/clackamas-account-joined.json"
uv run python tools/query_oregon_clackamas_property.py search 22E10AB00100 \
  --source us-or-clackamas-county-cmap-taxlots --field map_taxlot --geometry \
  --output "$WORKDIR/clackamas-taxlot.json"

uv run python tools/query_oregon_wasco_property.py account 9450 \
  --geometry --output "$WORKDIR/wasco-account-joined.json"
uv run python tools/query_oregon_wasco_property.py search 12 \
  --source us-or-wasco-county-surveyor-land-corners --field object_id \
  --output "$WORKDIR/wasco-land-corner.json"
uv run python tools/query_oregon_wasco_property.py attachments \
  us-or-wasco-county-surveyor-land-corners 12 \
  --output "$WORKDIR/wasco-land-corner-attachments.json"

uv run python tools/public_records_monitor.py run \
  us-or-yamhill-county-ascendweb-property \
  us-or-clackamas-county-cmap-taxlots \
  us-or-wasco-county-surveyor-land-corners \
  --output "$WORKDIR/oregon-county-component-probes.json"
```

Current assessor and geometry rows project into the property sidecar. Yamhill
permit rows project as property events. Retired Yamhill rows and Wasco survey
rows remain source observations, so a historical index entry is not presented
as current ownership and a survey scan is not presented as a deed or title
record. Land-corner and survey-book attachments retain their separate
representation lineage.

Each adapter also reports official alternatives that add fields or coverage
outside the live component. Yamhill exposes assessment data extracts and a
public-information route, plus Helion recorded instruments. Clackamas exposes
GIS downloads, value history, tax statements, recording research/copies, and
an assessment contact. Wasco exposes the state historical county-records
inventory, the survey service directory, and the separately cataloged Helion
recorder. These routes are complements rather than interchangeable mirrors.

### Washington County Survey Explorer, property, and tax family

Washington County (`41067`) publishes six components with different native
records and exact cross-source joins:

| Source ID | Native contribution |
|---|---|
| `us-or-washington-county-survey-explorer-api` | Survey, plat, taxlot, benchmark, corner, geodetic-control, county-road, and section-map indexes; exact detail; resolved source documents |
| `us-or-washington-county-survey-explorer-arcgis` | Survey Explorer geometry layers for surveys, plats, survey taxlots, corners, controls, roads, sections, and related map features |
| `us-or-washington-county-taxlots` | Current taxlot polygons keyed by `TLNO`, `MAPNO`, and `OBJECTID` |
| `us-or-washington-county-situs-addresses` | Address points keyed by `TAXLOT`, `SERIAL`, `ACCOUNT_ID`, `FULLADDRESS`, and native point identifiers |
| `us-or-washington-county-intermap-property` | Exact legacy parcel, assessment, and tax-map HTML reports keyed by `TLNO` |
| `us-or-washington-county-washcotax` | Exact guest property-tax accounts, published owners, values, legal/improvement/tax/payment sections, statement years, and generated or historical statement PDFs |

```bash
uv run python tools/query_oregon_washington_property.py sources \
  --output "$WORKDIR/washington-property-sources.json"
uv run python tools/query_oregon_washington_property.py survey-search \
  survey 35242 --output "$WORKDIR/washington-survey-search.json"
uv run python tools/query_oregon_washington_property.py survey-detail \
  plat 2026-021 --output "$WORKDIR/washington-plat-detail.json"
uv run python tools/query_oregon_washington_property.py survey-document \
  survey 35242 --destination "$WORKDIR/35242.pdf" \
  --output "$WORKDIR/washington-survey-document.json"
uv run python tools/query_oregon_washington_property.py arcgis \
  survey-taxlots --query 2N2330002700 --field TLID --geometry \
  --output "$WORKDIR/washington-survey-taxlot.json"
uv run python tools/query_oregon_washington_property.py taxlots \
  2N2330002700 --field TLNO --geometry \
  --output "$WORKDIR/washington-current-taxlot.json"
uv run python tools/query_oregon_washington_property.py situs \
  2N2330002700 --field TAXLOT --geometry \
  --output "$WORKDIR/washington-situs.json"
uv run python tools/query_oregon_washington_property.py intermap \
  2N2330002700 --report assessment \
  --output "$WORKDIR/washington-assessment-report.json"
uv run python tools/query_oregon_washington_property.py tax-account R2069997 \
  --output "$WORKDIR/washington-tax-account.json"
uv run python tools/query_oregon_washington_property.py tax-statement \
  R2069997 2025 --destination "$WORKDIR/R2069997-2025.pdf" \
  --output "$WORKDIR/washington-tax-statement.json"
```

The verified join chain is `TLNO/TLID` `2N2330002700` → account
`R2069997`, with situs `TAXLOT`, Intermap `IDValue`, Survey Explorer
`TLID`/`ACCOUNT`, and WashCoTax `PropertyQuickRefID` retaining their native
names. Survey and plat numbers and `DocNumber` connect API detail to the
separate ArcGIS geometry and source-document representations.

Unified routes expose the operation each component supports:

```bash
uv run python tools/query_property.py parcel 2N2330002700 \
  --source us-or-washington-county-taxlots --jurisdiction 41067 \
  --geometry --ingest --output "$WORKDIR/washington-taxlot-unified.json"
uv run python tools/query_property.py address "12311 NW JACKSON QUARRY RD" \
  --source us-or-washington-county-situs-addresses --jurisdiction 41067 \
  --output "$WORKDIR/washington-situs-unified.json"
uv run python tools/query_property.py parcel 2N2330002700 \
  --source us-or-washington-county-intermap-property --jurisdiction 41067 \
  --ingest --output "$WORKDIR/washington-intermap-unified.json"
uv run python tools/query_property.py account R2069997 \
  --source us-or-washington-county-washcotax --jurisdiction 41067 \
  --ingest --output "$WORKDIR/washington-account-unified.json"
uv run python tools/public_records_monitor.py run \
  us-or-washington-county-survey-explorer-api \
  us-or-washington-county-taxlots \
  us-or-washington-county-washcotax \
  --output "$WORKDIR/washington-component-probes.json"
```

Intermap parcel/assessment reports and WashCoTax property-account records
project into assessor snapshots. Survey Explorer records and PDFs, ArcGIS
geometry rows, current taxlot geometry, situs points, Intermap tax-map reports,
and tax-statement PDFs remain attributable source observations. That preserves
the surveyor, geometry, assessment, and document grains while keeping all
native join candidates available.

The component manifest also exposes Portland/Metro regional taxlots, county
recording and copy requests, Assessment and Taxation data requests, Accela
permit/planning records, and older land-use casefiles. These alternatives add
regional fields, recorded instruments, custom extracts, or permit/casefile
coverage when the six direct components do not carry the needed record type.

### Washington County planning casefile, permit, and document family

`query_oregon_washington_case_permits.py` adds six separately attributable
Washington County (`41067`) planning and permit components:

| Source ID | Native contribution |
|---|---|
| `us-or-washington-county-casefiles` | Development casefiles, applications under review, recent decisions, and the staff vocabulary; casefile, submittal, activity, taxlot, and Accela CAP joins |
| `us-or-washington-county-taxlot-project-activity` | Projects and permit activities published for an exact taxlot |
| `us-or-washington-county-building-permits` | Building-permit search rows and the public permit-type vocabulary |
| `us-or-washington-county-permit-reports` | Project, activity, people, inspection, and review reports |
| `us-or-washington-county-accela-current-planning` | Exact CurrentPlanning record detail, attachment listings, document metadata, and listed document binaries |
| `us-or-washington-county-land-use-document-routes` | Case-number routes to current review and decision pages, frequently discussed applications, hearing/CivicWeb packets, legacy Laserfiche, and the permit-records/request page |

```bash
uv run python tools/query_oregon_washington_case_permits.py sources \
  --output "$WORKDIR/washington-case-permit-sources.json"
uv run python tools/query_oregon_washington_case_permits.py case-detail \
  L2500106 --output "$WORKDIR/washington-casefile.json"
uv run python tools/query_oregon_washington_case_permits.py case-search \
  taxlot 2N2330002700 --output "$WORKDIR/washington-taxlot-casefiles.json"
uv run python tools/query_oregon_washington_case_permits.py taxlot-activity \
  2N2330002700 --collection all \
  --output "$WORKDIR/washington-taxlot-activity.json"
uv run python tools/query_oregon_washington_case_permits.py building-search \
  taxlot 2N2330002700 --output "$WORKDIR/washington-building-taxlot.json"
uv run python tools/query_oregon_washington_case_permits.py building-types \
  --output "$WORKDIR/washington-building-types.json"
uv run python tools/query_oregon_washington_case_permits.py permit-report \
  activity HR25-0008 --output "$WORKDIR/washington-activity-report.json"
uv run python tools/query_oregon_washington_case_permits.py accela-record \
  L2500106 --output "$WORKDIR/washington-current-planning.json"
uv run python tools/query_oregon_washington_case_permits.py document-routes \
  L2500106 --output "$WORKDIR/washington-document-routes.json"
```

The native join graph connects casefile `NUMBER_KEY` to the case-number
publication routes, `PARCEL_NO` to the taxlot project/activity report,
`B1_ALT_ID` to permit activity reports, and `ID1/ID2/ID3` to the Accela CAP.
Building `Project` and `PermitNO` connect the building index to project,
inspection, and review reports. These joins preserve each source
representation instead of treating related rows as independent corroboration.

The unified property router exposes the operations that map cleanly to its
selectors:

```bash
uv run python tools/query_property.py event L2500106 \
  --source us-or-washington-county-casefiles --jurisdiction 41067 --ingest \
  --output "$WORKDIR/washington-casefile-unified.json"
uv run python tools/query_property.py parcel 2N2330002700 \
  --source us-or-washington-county-taxlot-project-activity \
  --jurisdiction 41067 \
  --output "$WORKDIR/washington-taxlot-activity-unified.json"
uv run python tools/query_property.py event HR25-0008 \
  --source us-or-washington-county-permit-reports --jurisdiction 41067 \
  --search-field activity --ingest \
  --output "$WORKDIR/washington-activity-unified.json"
uv run python tools/query_property.py event L2500106 \
  --source us-or-washington-county-accela-current-planning \
  --jurisdiction 41067 \
  --output "$WORKDIR/washington-accela-unified.json"
```

Dated casefile, application-review, decision, project, activity, inspection,
and review rows can project into `property_event`. A published taxlot candidate
links an event to an ingested Washington County Intermap parcel only when the
match is exact. Rows without an event date, the staff and permit-type
vocabularies, the people report, Accela detail/document representations, and
the route catalog remain source observations. None of these six sources is
counted as assessment-roll, parcel-geometry, or land-record-index census
coverage; they add planning and permit activity rather than court dockets or
recorded-title instruments.

Access state is retained per operation. Casefile, taxlot activity, all five
permit-report types, building taxlot search and permit types, and the verified
CurrentPlanning record/document routes are anonymous. The source challenge was
observed on building permit-number, type/date/address, and individual-detail
operations, so that state applies to those operations and does not hide the
anonymous building routes.

Component monitors exercise casefile exact/review/decision/staff operations,
taxlot activity, anonymous building taxlot/type operations, all five report
types, and the three-request Accela case/detail/attachment chain. The document
route catalog is a declared adapter record and uses no network request.
Contract and schema hashes exclude rolling counts and native sentinel values.

When an embedded casefile document is not available, the family keeps the
other official routes visible: current-review and decision feeds, the
development-application hub, frequently discussed applications, public
hearing pages, CivicWeb packets, Accela attachments, legacy Laserfiche, and
the permit-records/request route. Each route retains its own provenance and
can supply related material without being presented as the missing
representation itself.

### Multnomah County SAIL property, survey, and image family

The 2026 Survey and Assessor Image Locator (SAIL) publishes eight independent
component records for Multnomah County (`41051`):

| Source ID | Native record and verified count |
|---|---|
| `us-or-multnomah-sail-tax-parcels` | Current assessment/owner/sale tax parcel keyed by `OBJECTID_1`, `PROPID`, `MAPTAXLOT`, and `ALTACCTNUM` (284,039) |
| `us-or-multnomah-sail-survey-records` | Survey index point, surveyor/client/date metadata, and image join keyed by `OBJECTID` and `SURVEYID` (87,179) |
| `us-or-multnomah-sail-subdivision-plats` | Subdivision plat polygon, metadata, and image join (6,314) |
| `us-or-multnomah-sail-partition-plats` | Partition plat polygon, metadata, and image join (4,454) |
| `us-or-multnomah-sail-condominium-plats` | Condominium plat polygon, metadata, and image join (1,720) |
| `us-or-multnomah-sail-road-surveys` | Road-survey polygon, metadata, and image join (4,439) |
| `us-or-multnomah-sail-bearing-tree-public-land-corners` | Bearing-tree/public-land-corner point and document references (8,997) |
| `us-or-multnomah-sail-field-book-quarter-sheets` | Field-book or quarter-sheet footprint and image join (2,714) |

```bash
uv run python tools/query_oregon_multnomah_sail.py sources \
  --output "$WORKDIR/multnomah-sail-sources.json"
uv run python tools/query_oregon_multnomah_sail.py search R330254 \
  --source us-or-multnomah-sail-tax-parcels --field property-id \
  --geometry --output "$WORKDIR/multnomah-sail-tax-parcel.json"
uv run python tools/query_oregon_multnomah_sail.py search 05335 \
  --source us-or-multnomah-sail-survey-records --field survey-id \
  --match exact --geometry \
  --output "$WORKDIR/multnomah-sail-survey.json"
uv run python tools/query_oregon_multnomah_sail.py record 7220 \
  --source us-or-multnomah-sail-survey-records --geometry \
  --output "$WORKDIR/multnomah-sail-survey-row.json"
uv run python tools/query_oregon_multnomah_sail.py image 05335 \
  --source us-or-multnomah-sail-survey-records \
  --output "$WORKDIR/multnomah-sail-image-viewer.json"
uv run python tools/query_oregon_multnomah_sail.py download 05335 \
  --source us-or-multnomah-sail-survey-records \
  --destination "$WORKDIR/05335.pdf" \
  --output "$WORKDIR/multnomah-sail-document.json"
uv run python tools/query_oregon_multnomah_sail.py probe \
  --source us-or-multnomah-sail-survey-records \
  --output "$WORKDIR/multnomah-sail-survey-probe.json"
```

`SURVEYID` joins each of the seven survey/image components to the county image
viewer and its resolved PDF representation. The tax-parcel component retains
`PROPID`, `MAPTAXLOT`, `ALTACCTNUM`, address, `INST_NUM`, legal description,
roll values, building facts, deed/sale fields, geometry, and assessor-map
links. The source-native row, viewer HTML, and downloaded PDF remain distinct
representations.

The unified router exposes owner, address, account, parcel, map, instrument,
and general search operations for the tax-parcel component. Each survey/image
component exposes general search, geometry search, and `SURVEYID` instrument
lookup; exact object-ID lookup and viewer/PDF retrieval stay available through
the direct adapter.

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

The current tax-parcel row projects to the shared assessor grain, including
published owners, addresses, roll values, parcel aliases, geometry, and the
latest deed/sale pivot. Survey, plat, road, corner, field-book, image-viewer,
and PDF records remain source observations. Component monitors run one layer
at a time and keep schema/contract identity separate from current counts,
sentinel rows, and image hashes.

For census accounting, the SAIL tax-parcel component contributes Multnomah
assessment-roll and current parcel-geometry coverage. The separately cataloged
Multnomah Helion recorder contributes the recorded-instrument index. SAIL
survey, plat, road, corner, and field-book collections remain discoverable
components and joins without being counted as either of those record-office
roles.

The county states that the road-survey layer is not a complete collection of
County Road information. The Surveyor assistance route adds records not found
through SAIL. Other complements include MultcoPropTax account/tax/payment
detail, MultcoRecords instruments and copies, DART standard reports and custom
requests, older-record ordering and lobby research, ORMAP assessor maps, and
Portland/Metro regional taxlots. The SAIL and regional taxlot rows can share
county upstream data, so their provenance remains lineage-linked rather than
treated as independent corroboration.

Deschutes has three implemented official sources with different native records:

| Source ID | Native identity and strongest fields | Join and use |
|---|---|---|
| `us-or-deschutes-county-taxlots` | ArcGIS taxlot feature plus eight declared account, retired-number, improvement, mailing, owner, property-class, roll-value, and serial cross-reference tables; keyed `GIS_SALES`; parcel geometry | Use for the parcel/relationship graph and WGS84 geometry |
| `us-or-deschutes-dial-property` | DIAL property account, assessment and tax history, payments, sales, improvements/land, special assessments, related accounts, warnings, service providers, permits, development records, and official report PDFs | Join by DIAL account ID and map/taxlot; retain each page, report, and linked county system as its own source component |
| `us-or-deschutes-cdd-weblink` | Laserfiche document identity, template metadata, case and Accela identifiers, parent folders, recent electronic files, and generated PDFs from historical imaged pages | Discover through a DIAL account, join by account and map/taxlot, and keep Laserfiche entry ID as document identity |

The ArcGIS `GIS_SALES` table remains separate from its eight declared
relationships. DIAL does not replace that parcel graph: an overlapping owner,
value, or sale observation still retains the source URL and schema of the
component that published it.

Lane and Marion add three live ArcGIS components. Lane also publishes a
property-account application and a separate tax-map locator/document system;
Marion adds two public-download families and two separately cataloged Clerk
instrument lineages:

| Source ID | Published contribution | Key complements |
|---|---|---|
| `us-or-lane-county-assessor-parcels` | Weekly-described parcel identity, assessment accounts, owner mailing fields, acreage, zoning/planning, and geometry | Property Account Information, tax-map images, Deeds and Records, and subscribed RLID |
| `us-or-lane-county-recent-property-sales` | Separate rolling three-year sale-analysis rows with account, map-taxlot, deed reference, price, reject code, and geometry | Recorded documents through Deeds and Records; account context through the property portal |
| `us-or-lane-property-account-information` | Account, map-taxlot, address, and taxpayer-name search; account detail with taxpayer, situs and mailing addresses, acreage, tax-code area, property class, receipts, valuation history, and linked representations | Parcel geometry and zoning through the Lane ArcGIS component; recorded title instruments through Deeds and Records; subscribed appraisal/card detail through RLID |
| `us-or-lane-tax-maps` | Map-lot, address, and map-name locator rows plus separately identified official tax-map PDFs | Account and parcel context through the account and ArcGIS components; full image-set and daily, weekly, or monthly update subscriptions through the official ordering route |
| `us-or-marion-county-assessor-parcels` | Parcel/account identity, owners, situs and mailing fields, RMV and assessed values, building/zoning fields, geometry, and latest verified-sale reference | Daily property records, 1940-current annual sales files, monthly assessment download, and custom-data requests |
| `us-or-marion-sales-data` | Current weekly sales CSV plus every officially listed annual/decade artifact back to 1940; sale, account, map-taxlot, assessor deed reference, situs, and transaction-party labels where published | Current parcel/account context through the Marion parcel and Property Records sources; recorded-document verification through the County Clerk |
| `us-or-marion-comprehensive-assessment-download` | Replaceable comprehensive ORCATS ZIP with assessment accounts, parcel/map components, situs, values, physical fields, and `RDATE` data vintage | Current owner/mailing fields through the parcel or Property Records representations; historical sales through the separate sales family; recorder evidence through the County Clerk |
| `us-or-marion-clerk-recorded-documents` | Verified County Clerk Helion search and exact instrument detail, officially described as 1974-present | Current recorder lineage for verifying assessor deed references; the sampled detail had no direct image/OCR/cart link, so official copy and certification remain a separate Clerk representation |
| `us-or-marion-clerk-historical-deeds` | Separate County Clerk historical deed search: county listing 1855-1976, live form wording 1850-1976 | Historical grantor/grantee route with a 1974-1976 overlap that does not merge its source identity with the current index |

```bash
uv run python tools/query_oregon_lane_marion_parcels.py sources \
  --output "$WORKDIR/lane-marion-sources.json"
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

uv run python tools/query_oregon_lane_property.py sources \
  --output "$WORKDIR/lane-account-tax-map-sources.json"
uv run python tools/query_oregon_lane_property.py search 0057313 \
  --source us-or-lane-property-account-information --field account \
  --output "$WORKDIR/lane-account-search.json"
uv run python tools/query_oregon_lane_property.py search \
  "NORTHWEST CLEARWOODS INC" \
  --source us-or-lane-property-account-information --field name \
  --output "$WORKDIR/lane-taxpayer-search.json"
uv run python tools/query_oregon_lane_property.py account 0057313 \
  --output "$WORKDIR/lane-account-detail.json"
uv run python tools/query_oregon_lane_property.py search 1605070001100 \
  --source us-or-lane-tax-maps --field map_lot \
  --output "$WORKDIR/lane-tax-map-locator.json"
uv run python tools/query_oregon_lane_property.py search 16050700 \
  --source us-or-lane-tax-maps --field map_name \
  --output "$WORKDIR/lane-tax-map-name.json"
uv run python tools/query_oregon_lane_property.py download-tax-map 326 \
  --destination "$WORKDIR/lane-tax-map-326.pdf" \
  --output "$WORKDIR/lane-tax-map-download.json"
uv run python tools/query_oregon_lane_property.py probe \
  --source us-or-lane-property-account-information \
  --output "$WORKDIR/lane-account-probe.json"
uv run python tools/query_oregon_lane_property.py probe \
  --source us-or-lane-tax-maps \
  --output "$WORKDIR/lane-tax-map-probe.json"

uv run python tools/query_oregon_marion_downloads.py manifest \
  --output "$WORKDIR/marion-download-manifest.json"
uv run python tools/query_oregon_marion_downloads.py probe \
  --source us-or-marion-sales-data \
  --output "$WORKDIR/marion-sales-probe.json"
uv run python tools/query_oregon_marion_downloads.py download \
  --source us-or-marion-comprehensive-assessment-download \
  --destination "$WORKDIR/marion-comprehensive.zip" \
  --output "$WORKDIR/marion-comprehensive-download.json"
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

Count snapshots, ordered object-ID anchors, source schema, selector, and
geometry choice bind continuation. Lane sale rows join to the parcel component
by account and map-taxlot in the sidecar while retaining their separate source
identity. Lane `address` searches the owner mailing fields published by its
parcel layer; the source does not label them as situs addresses.

The Lane account application's anonymous JSON routes return the complete
source-supplied list for a query. The Kendo grid currently displays five rows
at a time, but that client-side page size is not a source result ceiling.
Accordingly, an omitted `--limit` returns every supplied row. An explicit
window carries a query-bound total and prior-boundary anchor in its
continuation.

The account search index labels both `Tax Payer` and `Owner`; the adapter
retains them as `taxpayer_name` and `owner_index_name`. Those labels are
separate from the grantor/grantee and instrument evidence published by Lane
County Deeds and Records. The account page's tax statements, payment route,
tax map, RLID appraisal page, RLID property-description card, and additional
property-information link are likewise related representations, not copies of
one record.

Tax Map Search is an ASP.NET WebForms application. Map-name mode first changes
the form mode and then submits the search with the refreshed `__VIEWSTATE`,
`__VIEWSTATEGENERATOR`, and `__EVENTVALIDATION` values. Each result row is a
locator occurrence; its `ViewFile.aspx?type=TM&id=...` target is a separate PDF
document identity. The probe validates the returned media type and PDF bytes
in addition to the search response. Lane County also offers an
[approximately 3,500-map image set and update subscriptions](https://www.lanecountyor.gov/government/county_departments/assessment___taxation/tax_maps/ordering_tax_maps)
as an official acquisition alternative.

Live discovery produced several reusable source-review lessons: inspect inline
application JavaScript for anonymous JSON routes; separate presentation page
size from endpoint completeness; refresh form state after a WebForms mode
postback; treat links on rich account pages as candidates for the source graph;
and validate the referenced document bytes during source probes. Lane
[cartography guidance](https://www.lanecountyor.gov/government/county_departments/assessment___taxation/cartography)
describes tax maps as assessment/cadastral material. Deeds and Records supplies
the separately attributable recorded-title evidence, while the ArcGIS parcel
and sales components and subscribed RLID pages retain their own provenance.

The rolling sales monitor uses the current first ordered row as a structural
sentinel rather than freezing a deed that will eventually age out. Counts,
returned identities, values, and edit timestamps remain live observations;
layer identity, record kind, CRS, schema, and sentinel strategy define the
stable contract.

The download manifest is exhaustive over the recognized official listing and
checks continuous calendar coverage from 1940. A publisher-visible release
slot is distinct from the validator/digest occurrence downloaded from that
slot. Archive-member and row occurrences are in turn bound to that artifact,
while the sale identity and parcel/account joins remain separate. This matters
for the current-year file, which is replaced weekly without becoming a new
semantic sale every time.

The 2020 CSV repeats `SALE_DATE` and `DESCRIPTION` in different positions, so
the adapter validates the raw header and assigns canonical columns
positionally. The 2021 and 2022+ layouts have their own schema profiles.
Historical XLS and XLSB artifacts remain listed, transferable, and locally
inspectable with per-artifact/member capability; an unsupported workbook
member does not make the rest of the source unavailable.

Marion County states that owner names and mailing addresses have been omitted
from the comprehensive download since February 1, 2015. The shared ingester
therefore projects its assessment values and situs fields but no owners.
`SALE_GRANTOR`, `SALE_GRANTEE`, `BOOKPG`, and the other latest-sale fields stay
source-labeled assessor observations. They do not establish current ownership,
title, or a verified County Clerk instrument. The current
`us-or-marion-clerk-recorded-documents` route and the separate
`us-or-marion-clerk-historical-deeds` route are therefore full catalog sources,
not uncataloged URL hints or aliases of the assessor downloads. The current
tenant's advanced search and exact detail are integrated through the shared
Helion family under that stable Clerk ID. The historical form is a separate
candidate adapter: its own wording says 1850-1976 while the county listing says
1855-1976, and the 1974-1976 overlap is preserved rather than deduplicated by
source label. The verified assessor form adds account, map-taxlot, situs, and
subdivision pivots. Official counter/mail copies and certification are a
separate Clerk representation because the sampled Helion detail did not expose
a direct image, OCR-text, or cart link.

Jackson and Douglas add two county assessor layers with distinct schemas and
official complements:

| Source ID | Published contribution | Complementary sources |
|---|---|---|
| [`us-or-jackson-county-assessor-taxlots`](https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Taxlots/FeatureServer/2) | Jackson County (`41029`) map/taxlot and account identities, owner and mailing fields, situs, acreage, market and assessed land/improvement values, classifications, selected building fields, tax codes, and polygon geometry | [Assessment maps](https://apps.jacksoncountyor.gov/asmtmaps/Home/Help), [JIM property map](https://apps.jacksoncountyor.gov/gis/helpdocs/JimInstructions.pdf), [assessor data request](https://jacksoncountyor.gov/Document%20Center/Departments/Counsel/Public%20Records%20Request.pdf), and the separately identified [Helion recorder](https://apps.jacksoncountyor.gov/DigitalResearchRoomPublic/) |
| [`us-or-douglas-county-assessor-parcels`](https://gis.co.douglas.or.us/server/rest/services/Parcel/Parcels/FeatureServer/0) | Douglas County (`41019`) parcel and account identities, owner and mailing fields, situs, acreage, assessed and market values, legal description, current-row instrument/sale-date reference, and polygon geometry | [Assessor subscription products](https://fir.co.douglas.or.us/FileRepository/ASSESSOR/Subscriptions/Subscriptions.pdf), including certified rolls, land/improvement segments, three-year sales, map images, and parcel/geoparcel shapefiles |

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

The shared projection retains each county's native parcel/account identity and
adds typed aliases for Jackson map/taxlot forms and normalized Douglas
`TAXID`. Source values and optional polygons become assessment and WGS84
geometry observations. Douglas's published current-row instrument and sale
date become an `assessor_current_parcel_reference` sale observation; the
separate subscription products carry the broader sale-history and roll
components. Jackson's live taxlot layer supplies current assessment context,
while its map, data-request, and recorder sources add spatial, requested-data,
and instrument evidence under their own source identities.

Jackson County's property-event adapter keeps three weekly-described ArcGIS
layers separate:

| Source ID | Native event identity and published fields |
|---|---|
| [`us-or-jackson-county-building-permits`](https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_Building/FeatureServer/1) | Building-permit `PERMITID`, type/description/status and dates, estimated cost, applicant/contractor fields, address, map-taxlot candidate, Accela identifiers/link, and centroid point |
| [`us-or-jackson-county-land-use-permits`](https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_LandUse/FeatureServer/0) | Land-use `PERMITID`, 1980-present layer coverage, type/description/status and dates, applicant fields, address, map-taxlot candidate, Accela identifiers/link, and centroid point |
| [`us-or-jackson-county-code-compliance`](https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_CodeCompliance/FeatureServer/2) | Code-compliance `VIOLATIONID`, case/type/description/status and dates, published owner, address, map-taxlot candidate, related identifiers/link, and centroid point |

```bash
uv run python tools/query_oregon_jackson_property_events.py sources \
  --output "$WORKDIR/jackson-property-event-sources.json"
uv run python tools/query_oregon_jackson_property_events.py search solar \
  --source us-or-jackson-county-building-permits \
  --output "$WORKDIR/jackson-building-solar.json"
uv run python tools/query_oregon_jackson_property_events.py map-taxlot 30-2E-100 \
  --source us-or-jackson-county-land-use-permits --geometry \
  --output "$WORKDIR/jackson-land-use-taxlot.json"
uv run python tools/query_oregon_jackson_property_events.py record 439-24-000123 \
  --source us-or-jackson-county-code-compliance \
  --output "$WORKDIR/jackson-code-record.json"
uv run python tools/query_oregon_jackson_property_events.py probe --all \
  --output "$WORKDIR/jackson-property-event-probes.json"
```

The event projection stores permit and compliance rows as `property_event`
observations rather than title assertions. Identity includes the component
source, Jackson jurisdiction, native permit/violation ID, and ArcGIS
`OBJECTID`, preserving separate layer rows when one native permit appears more
than once. Dates, status, description, cost, address, map-taxlot candidate,
optional point, parties, and linked Accela representation remain structured.
A published map-taxlot links to an assessor parcel only when it resolves to
exactly one Jackson assessor alias; the link records
`exact_published_map_taxlot_alias`, `ambiguous_published_map_taxlot`, or
`unresolved_published_map_taxlot`. Applicants, contractors, and published
code-case owners remain event-party observations.

Jackson's Accela adapter follows the official record links published by the
building and land-use ArcGIS layers. It keeps the source representations
separate:

| Source ID | Accela module | Available representations |
|---|---|---|
| `us-or-jackson-county-accela-building-details` | `Building` | Record detail, processing status, inspections, fees, related records, attachment list, stable document detail, and document binary |
| `us-or-jackson-county-accela-planning-details` | `Planning` | Record detail, processing status, inspections, fees, related records, attachment list, stable document detail, and document binary |

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
  --output "$WORKDIR/jackson-accela-document.json"
uv run python tools/query_oregon_jackson_accela.py download \
  building 26CAP-00000-006GM 16767279 \
  --destination "$WORKDIR/jackson-building-permit.pdf" \
  --output "$WORKDIR/jackson-building-permit-receipt.json"
uv run python tools/query_oregon_jackson_accela.py probe --all \
  --output "$WORKDIR/jackson-accela-probes.json"
```

The three CAP components, agency code, module, and native record number remain
available together. Attachment-list rows retain their stable Accela document
numbers; document metadata and binary downloads are separate representations
joined by that number. The ArcGIS event row remains the spatial/index
representation and is not duplicated as Accela corroboration.

The county's published code-compliance layer currently has no equivalent
anonymous Accela detail representation: its official GIS link reaches Accela
sign-on, while the analogous Citizen Access route returns the tenant error
page. The structured
[`us-or-jackson-county-code-compliance`](https://jcportal.jacksoncountyor.gov/server/rest/services/Property/Permits_CodeCompliance/FeatureServer/2)
layer remains searchable, and the county's
[records-request route](https://jacksoncountyor.gov/Document%20Center/Departments/Counsel/Public%20Records%20Request.pdf)
covers details not published there.

```bash
uv run python tools/query_deschutes_property.py search "VACH" \
  --field owner --output "$WORKDIR/deschutes-owner.json"
uv run python tools/query_deschutes_property.py search "14987 BUGGY WHIP" \
  --field address --output "$WORKDIR/deschutes-address.json"
uv run python tools/query_deschutes_property.py parcel 141031B000700 \
  --geometry --output "$WORKDIR/deschutes-parcel.json"
uv run python tools/query_property.py account 135278 \
  --source us-or-deschutes-county-taxlots --jurisdiction 41017 --ingest \
  --output "$WORKDIR/deschutes-account-unified.json"
uv run python tools/query_deschutes_dial.py search "VACH" \
  --field owner --output "$WORKDIR/deschutes-dial-owner.json"
uv run python tools/query_deschutes_dial.py search "SISTERS" \
  --field subdivision --output "$WORKDIR/deschutes-dial-subdivision.json"
uv run python tools/query_deschutes_dial.py search "PARK NAME" \
  --field mobile-park --output "$WORKDIR/deschutes-dial-mobile-park.json"
uv run python tools/query_deschutes_dial.py account 135278 \
  --output "$WORKDIR/deschutes-dial-account.json"
uv run python tools/query_property.py parcel 141031B000700 \
  --source us-or-deschutes-dial-property --jurisdiction 41017 \
  --output "$WORKDIR/deschutes-dial-taxlot-account.json"
uv run python tools/query_deschutes_dial.py download 135278 ownership \
  --destination "$WORKDIR/deschutes-ownership.pdf" \
  --output "$WORKDIR/deschutes-ownership-receipt.json"
uv run python tools/query_property.py account 135278 \
  --source us-or-deschutes-cdd-weblink --jurisdiction 41017 --ingest \
  --output "$WORKDIR/deschutes-cdd-index.json"
uv run python tools/query_deschutes_laserfiche.py document 1383062 \
  --account 135278 --taxlot 141031B000700 \
  --output "$WORKDIR/deschutes-cdd-document.json"
uv run python tools/query_deschutes_laserfiche.py download 333623 \
  --account 135278 --destination "$WORKDIR/deschutes-cdd-333623.pdf" \
  --output "$WORKDIR/deschutes-cdd-download.json"
uv run python tools/query_deschutes_laserfiche.py probe \
  --output "$WORKDIR/deschutes-cdd-probe.json"
uv run python tools/public_records_monitor.py run \
  us-or-deschutes-dial-property us-or-deschutes-cdd-weblink \
  --output "$WORKDIR/deschutes-monitors.json"
```

The unified DIAL routes map `search`, `owner`, `address`, `subdivision`, and
`mobile-park` to the corresponding source-native result modes. `account`
resolves an account number and `parcel` resolves a map/taxlot into the full
account record. Geometry remains on the separate ArcGIS source.

DIAL returns all 14 account components by default. Every component carries its
own URL, status, and schema fingerprint, so a working account record can remain
available as `partial` when one page changes. Search results come from the
source-returned complete 20-column HTML table and use a cursor bound to the
query, row count, snapshot, schema, and prior boundary row.

Property reports distinguish source links from retrieved PDFs. Ownership,
balance, tax-map, tax-statement, improvement, and ledger reports have verified
direct PDF routes; basic and full reports use the source's generation job and
bounded readiness polling. Recorder and CDD development-document links remain
`external_viewer_link`, while the county tax-payment page is an independently
attributed account component.

The CDD adapter turns the DIAL development-document table into a bounded,
snapshot-bound index of source-native Laserfiche entry IDs. A document query
adds WebLink template metadata and verifies an optional account or map/taxlot
join. Recent records can expose their electronic file directly; older scanned
records use the repository's PDF-generation flow. The download receipt records
the representation mode, byte count, hash, and local path.

WebLink does not expose anonymous repository-wide search or browse in the
observed public session, so DIAL is the primary discovery route. Oregon
ePermitting provides current permit status and selected applicant-facing
documents, the county taxlot service supplies parcel and assessment context,
and the county records-request route covers CDD material absent from the
account-linked repository.

The Helion/ORCATS Property Search Online adapter keeps six assessor and tax
tenants as separate source components. The shared browser protocol is an
implementation detail; each source retains the county's own search menu,
account identity, access observation, and official complements.

| Source ID | Native search options observed | Distinct official complements |
|---|---|---|
| `us-or-umatilla-helion-property` | account, tax account, name, address, map/taxlot, legal | Interactive county map; sales files and assessment reports |
| `us-or-morrow-helion-property` | account, tax account, name, address, map/taxlot, legal | Taxlot maps; tax levy and district reports |
| `us-or-polk-helion-property` | account, tax account, name, address, map/taxlot, legal | GIS and assessment downloads; Assessor taxlot service |
| `us-or-tillamook-helion-property` | account, tax account, name, address, map/taxlot, legal | Prior assessment/tax rolls, tax maps, sales workbooks, foreclosure lists, and county real-property sales |
| `us-or-columbia-helion-property` | tax account, name, address, map/taxlot | Current non-certified web maps; certified-roll tab files; quarterly sales workbooks |
| `us-or-coos-helion-property` | account, tax account, name, address, map/taxlot | County tax, report, foreclosure, and payment routes |

```bash
uv run python tools/query_oregon_helion_property.py sources \
  --output "$WORKDIR/oregon-pso-sources.json"
uv run python tools/query_oregon_helion_property.py search smith \
  --field name --source us-or-morrow-helion-property --limit 10 \
  --output "$WORKDIR/morrow-pso-name.json"
uv run python tools/query_oregon_helion_property.py detail 171 \
  --roll-type R --source us-or-morrow-helion-property \
  --output "$WORKDIR/morrow-pso-account.json"
uv run python tools/query_property.py parcel 2S2627-DA-02000 \
  --source us-or-morrow-helion-property --jurisdiction 41049 \
  --output "$WORKDIR/morrow-pso-map-taxlot.json"
uv run python tools/query_property.py account 171 \
  --source us-or-morrow-helion-property --jurisdiction 41049 --ingest \
  --output "$WORKDIR/morrow-pso-unified.json"
uv run python tools/public_records_monitor.py run \
  us-or-morrow-helion-property \
  --output "$WORKDIR/morrow-pso-monitor.json"
```

The unified router maps `search` and `owner` to the selected tenant's name
index, `address` to its address index, `parcel` to its source-native
map/taxlot index, and `account` to full account detail. The direct adapter
also exposes tax-account and legal-description selectors where the chosen
tenant publishes them. The map/taxlot selector is an identifier search, not
parcel geometry; the table above identifies the county-specific map and GIS
sources that can add geometry or spatial context.

Search results retain the native account, roll type, map/taxlot, owner, situs,
balance-due observation, and a continuation cursor bound to the query and last
emitted result. The rendered applications showed ten results per source page;
the adapter follows the application's page count and emits a cursor when the
caller requests a smaller window. Full detail retains ownership and mailing,
situs addresses, current and historical values, tax balance and payoff data,
payments, sales, improvements, special assessments, notations, account
history, and linked reports/files. The shared projection promotes parcel,
owner, address, assessment, and sale fields while preserving the complete
source record for the additional components.

Live checks verified name paging and account `171/R` detail in Morrow and
account `28102/R` detail in Columbia. Tillamook completed through SignalR long
polling after its websocket handshake returned HTTP 200; that transport event
is a tenant observation, not a different record contract. The monitor hashes
the stable source, page, access-outcome, and native-selector contract while
keeping browser runtime, transport events, and footer text as live details.

The Helion Digital Research Room adapter keeps its registered recorder tenants
separate. They share a form/result/detail implementation, while routing,
projection, and monitoring derive from the tenant registry and retain each
county-native source ID, coverage note, session behavior, index freshness, and
published copy/image/OCR state. Marion uses the pre-existing
`us-or-marion-clerk-recorded-documents` identity rather than a vendor-derived
alias.

```bash
uv run python tools/query_oregon_helion_recorder.py source \
  --source us-or-umatilla-helion-recorder \
  --output "$WORKDIR/umatilla-recorder-source.json"
uv run python tools/query_oregon_helion_recorder.py search \
  --source us-or-umatilla-helion-recorder \
  --year 2026 --document-from 1 --document-to 40 --limit 10 \
  --output "$WORKDIR/umatilla-recorder-search.json"
uv run python tools/query_oregon_helion_recorder.py detail \
  --source us-or-wasco-helion-recorder 2023 2123 \
  --output "$WORKDIR/wasco-recorder-detail.json"
uv run python tools/query_property.py instrument 2023-002123 \
  --source us-or-wasco-helion-recorder --jurisdiction 41065 --ingest \
  --output "$WORKDIR/wasco-recorder-unified.json"
uv run python tools/query_property.py instrument 2026-00001 \
  --source us-or-marion-clerk-recorded-documents --jurisdiction 41047 --ingest \
  --output "$WORKDIR/marion-recorder-unified.json"
uv run python tools/public_records_monitor.py run \
  us-or-wasco-helion-recorder us-or-marion-clerk-recorded-documents \
  --output "$WORKDIR/helion-recorder-monitors.json"
```

Unified `search` and `owner` routes use the selected tenant's party-name
index. `instrument` recognizes a year/document selector such as
`2023-002123`, while other native historic identifiers remain searchable
without being rewritten. The direct adapter exposes the full date,
document-type, party-role, property, subdivision, map, taxlot,
legal-description, comment, and title-detail vocabulary where the selected
tenant's live form offers each field. `probe` returns that tenant's current
form controls and option values. The current Wasco form includes document type
and property ID, while the current Umatilla and Polk forms omit those controls;
their subtype vocabularies also remain independently observed.

Wasco live detail returned the exact deed, five indexed parties, legal fields,
two document pages, and a direct PDF; Umatilla returned a complete 40-row
result snapshot with continuation. Marion completed the disclaimer and
application-proxy redirect into an anonymous session, returned a two-row
continuation, and exposed exact detail without a direct image/OCR/cart link.
Some tenants currently present reCAPTCHA
in their public disclaimer, while the working anonymous tenants remain
machine-queryable through the same family. That state is recorded per tenant,
and county request, office, assessor, GIS, and historical-index routes remain
available as complementary sources.

Recorder search cursors bind the county source, complete native selector set,
source-reported total, and prior native boundary. A resumed query replays the
same selectors in a fresh session and verifies that boundary; count changes
remain explicit partial results rather than being mistaken for complete or
empty retrieval. The 50-row Helion window is a native request size, not an
adapter result ceiling: omitting `--limit` follows the source-reported result
set, while an explicit positive limit returns a resumable cursor when matches
remain.

Oregon county tax-foreclosure publications are a separate event family, not
recorder instruments or current assessor ownership. Four source IDs preserve
the parts of the process that each county actually publishes:

| Source ID | Published stages | Structured extraction |
|---|---|---|
| `us-or-tillamook-tax-foreclosure-publications` | Annual foreclosure lists | Account, property-map ID, published names and mailing lines, court case, judgment, advertising, and deed-to-county dates |
| `us-or-marion-tax-foreclosure-publications` | Current foreclosure list and end-of-redemption notices | End-of-redemption property notices; the current scanned list remains a versioned artifact until a derived text representation is supplied |
| `us-or-multnomah-tax-foreclosure-publications` | Statutory redemption notices, judgment-in-progress announcement, tax-title inventory, and sale authorization | Redemption property notices and tax-title inventory rows; page-only and unparsed artifacts still retain their route and version provenance |
| `us-or-clackamas-tax-foreclosure-publications` | Post-deed auction offerings and results | Auction item, map/taxlot, value, minimum bid, deposit, result, and final bid; the county-described newspaper list remains a distinct publication/request route |

```bash
uv run python tools/query_oregon_tax_foreclosures.py sources \
  --output "$WORKDIR/oregon-tax-foreclosure-sources.json"
uv run python tools/query_oregon_tax_foreclosures.py discover --all \
  --output "$WORKDIR/oregon-tax-foreclosure-routes.json"
uv run python tools/query_property.py owner "EXAMPLE OWNER" \
  --source us-or-tillamook-tax-foreclosure-publications \
  --jurisdiction 41057 --process-stage foreclosure_list_published \
  --ingest --output "$WORKDIR/tillamook-foreclosure-owner.json"
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
uv run python tools/public_records_monitor.py run \
  us-or-multnomah-tax-foreclosure-publications \
  --output "$WORKDIR/multnomah-tax-publication-monitor.json"
```

`--process-stage` selects an exact county publication route. When it is
omitted, the adapter records both the empty request selector and the stage
resolved from the selected route. Each query carries the discovery
`publication_document_id`, page and document URLs, artifact SHA-256, page
count, and a text-representation object whose parent hash is the official
artifact. Embedded PDF text and supplied OCR/transcription therefore remain
distinct representations of the same publication.

The generic ingester projects structured rows as tax-account events using the
exact process-stage value. It also stores the official PDF and text
representation independently of row extraction, so an image-only or currently
unparsed publication is not converted into an authoritative empty list.
Parcel/tax portals, post-deed sales, public-record request routes, and Oregon
foreclosure-surplus notices retain their separate source identities and join
keys.

The monitor fingerprints publisher, county, landing-page roles, supported
stages, join keys, complements, and the PDF/text lineage contract. Landing-page
hashes, current labels and URLs, route counts, and the selected current PDF
hash remain rolling observations; a new publication is ordinary source
activity rather than a source-contract change.

The catalog also preserves adjacent routes:

- `us-or-odf-taxlots-display` has all 36 county display layers and useful
  ORMAP-style schemas. Representative layer queries return ArcGIS's
  unsupported-operation response, so it supplies visual routing and schema
  context rather than record search.
- `us-or-ormap-cadastral-routing` supplies the statewide OR taxlot identifier,
  assessor maps, and county source routing; no statewide bulk API was verified.
- Deschutes's relationship-rich service, Lane's weekly-described parcels and
  separate recent-sales component, and Marion's live parcel layer plus
  official sales/assessment downloads are implemented. Each keeps
  county-native fields, source occurrences, joins, freshness, and complement
  routes.
- Helion Digital Research Room recorder tenants are implemented as registered
  county sources. Property Search Online is implemented separately for six
  assessor/tax tenants; county identities, native selectors, and complementary
  routes stay distinct even where the vendor and join fields overlap.
- Deschutes CDD document links resolve to the county's Laserfiche/WebLink
  viewer. They are retained as account-linked development-document references;
  indexed search and document retrieval are tracked separately in
  infrastructure request #248.
- County foreclosure, redemption, tax-title, sale-result, and delinquency
  publications are versioned process-stage sources. Historic Oregon county
  archives, BLM land records, state-owned-land inventories, and UCC filings
  remain useful pivots when a current assessor or recorder route is sparse.

## Direct query pilots

Use the unified router for normalized local observations and its registered
live routes. Direct adapters expose source-specific selectors and fields.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
# NYC ACRIS recorder parties and instruments
uv run python tools/query_acris.py party "EXAMPLE LLC" \
  --output "$WORKDIR/acris-party.json"

# East Baton Rouge parcel and assessment data
uv run python tools/query_la_property.py owner "EXAMPLE LLC" \
  --parish ebr --output "$WORKDIR/ebr-owner.json"
uv run python tools/query_la_property.py adjudicated "EXAMPLE LLC" \
  --parish ebr --output "$WORKDIR/ebr-tax-default.json"

# Orleans Parish current assessment accounts and parcel geometry
uv run python tools/query_orleans_property.py owner "EXAMPLE LLC" \
  --output "$WORKDIR/orleans-owner.json"
uv run python tools/query_orleans_property.py account "<TAXBILLID>" --geometry \
  --output "$WORKDIR/orleans-account.json"

# Cook County Parcel Universe: parcel history, geography, and tax districts
uv run python tools/query_cook_property.py parcel 01-01-106-009-1001 \
  --output "$WORKDIR/cook-parcel.json"
uv run python tools/query_cook_property.py parcel 0101106009 --tax-year 2025 \
  --output "$WORKDIR/cook-parcel-2025.json"

# Maryland statewide assessment records
uv run python tools/query_md_property.py address "7 TRAYMORE RD" \
  --output "$WORKDIR/md-address.json"
uv run python tools/query_md_property.py parcel 04030311078580 \
  --output "$WORKDIR/md-parcel.json"

# Maryland's official MD iMAP point representation of the same SDAT accounts
# Catalog source: us-md-mdp-parcel-points
uv run python tools/query_md_mdp_parcel_points.py account 1901000047 \
  --geometry --output "$WORKDIR/md-point-account.json"
uv run python tools/query_md_mdp_parcel_points.py query --county-code 19 \
  --map 0042 --output "$WORKDIR/md-point-map.json"
uv run python tools/query_property.py point --source us-md-mdp-parcel-points \
  --longitude -76.63 --latitude 38.30 --county "St. Mary's County" \
  --geometry --output "$WORKDIR/md-point-spatial.json"

# Maryland parcel, CAMA, and residential-sales bulk families
uv run python tools/query_md_mdp_property_downloads.py manifest \
  --source us-md-mdp-parcel-downloads \
  --output "$WORKDIR/md-parcel-releases.json"
uv run python tools/query_md_mdp_property_downloads.py manifest \
  --source us-md-mdp-cama-downloads --component building \
  --output "$WORKDIR/md-cama-building-releases.json"
uv run python tools/query_md_mdp_property_downloads.py prepare \
  --source us-md-mdp-property-sales-downloads \
  --release sales-2026-02 \
  --output "$WORKDIR/md-sales-transfer.json"

# Maryland State Archives Plats.net
uv run python tools/query_md_plats.py search MO --mode advanced \
  --description "Timberland Estates" --include-no-images \
  --output "$WORKDIR/md-plats-search.json"
uv run python tools/query_md_plats.py plat MO C 1136 1 \
  --output "$WORKDIR/md-plat-detail.json"
uv run python tools/query_property.py survey "Timberland Estates" \
  --source us-md-plats --county "Montgomery County" --ingest \
  --output "$WORKDIR/md-plats-shared.json"
```

ACRIS covers the Bronx, Brooklyn, Manhattan, and Queens, not Staten Island.
Recorder parties, assessor owners, and possible beneficial owners are stored as
different assertions. Cook County's Parcel Universe contains historical parcel,
classification, centroid, and district fields but no owner-name or street-
address columns. The Maryland dataset intentionally omits current-owner names;
the adapter keeps `owner_visibility.state=withheld_by_source` while retaining
its parcel, situs, assessment, deed, sale, and historical-grantor fields.
The MD iMAP Parcel Points layer adds a live spatial and planning
representation. Its `ACCTID` is the exact cross-representation account key for
the hidden-owner assessment source, while `OBJECTID` identifies the ArcGIS
feature occurrence. The layer publishes owner-mailing-address fields but no
current-owner-name field; it also adds point geometry, structure, land,
zoning, appraisal, transfer-reference, and deed/plat-reference fields. These
are complementary fields from the same SDAT/MDP lineage rather than a second
independent account of the parcel.

The bulk catalog keeps three source families separately attributable:
`us-md-mdp-parcel-downloads`, `us-md-mdp-cama-downloads`, and
`us-md-mdp-property-sales-downloads`. Parcel and CAMA rows can later join the
SDAT account through `ACCTID`; Building-to-Subareas CAMA joins use `CAMALINK`.
The sales files are residential analytic releases rather than complete deed
history, and `ACCTID` + trade date + consideration is a review candidate rather
than a publisher-issued transaction ID. Release slots, provider links,
downloaded artifact hashes, and archive members retain distinct identities.

Plats.net is a separate State Archives record family. Its stable key is the
county code plus archive qualifier, series, and unit—not the printed plat or
book/page reference. Shared searches include records with no published scan
and, when no caller limit is supplied, follow the source-reported total through
every native page. An explicit limit is the only path that emits a query-bound
continuation. Exact unit pages do not require the search session. Compiled PDFs
and individual direct or microfilm TIFF/JPEG scans remain separate
representations; dates embedded in current artifact paths are observations,
not record identity. MDLandRec, MD iMAP Parcel Points, the CAMA downloads, and
the residential-sales releases remain separately attributable complements for
deeds, parcel/account context, assessment attributes, and sale context.

ACRIS index queries and selected document-image/copy routes are separate
catalog capabilities. Build or enqueue a concrete image action from the
document ID returned by the index:

```bash
uv run python tools/public_records_actions.py plan us-nyc-acris-images \
  --operation open_selected_image --selector 2017021700466001 \
  --output "$WORKDIR/acris-image-plan.json"
uv run python tools/public_records_actions.py enqueue us-nyc-acris-images \
  --operation order_copy --selector 2017021700466001 \
  --output "$WORKDIR/acris-copy-action.json"
```

The catalog records both the public image viewer and City Register
subscription-data-service route described by the viewer's current bandwidth
notice.

Miami-Dade's selective public and credentialed exact-query routes are
implemented above. Its subscribed daily feed, the PA file library, and Harris
County Clerk real-property products are cataloged data-product routes. Their
entries capture index/image contents, product cadence, account/fee facts, and
stable source keys.

```bash
uv run python tools/public_records_catalog.py show \
  us-fl-miami-dade-official-records --json
uv run python tools/public_records_actions.py plan \
  us-fl-miami-dade-official-records \
  --operation request_bulk_files --selector "Miami-Dade deed index" \
  --output "$WORKDIR/miami-recorder-product-plan.json"
uv run python tools/public_records_actions.py plan \
  us-tx-harris-clerk-real-property \
  --operation request_bulk_index --selector "Harris County real-property index" \
  --output "$WORKDIR/harris-recorder-product-plan.json"
```

## State bulk-release pilots

Florida DOR publishes county NAL, SDF, GIS-PIN, and GIS-PAR release files.
`query_fl_dor_property.py` discovers the current official directories at query
time, represents each selected file as a release manifest, and can probe,
dry-run, or transfer it. The catalog source is
`us-fl-dor-property-roll`; its shared operations are `releases`, `manifest`,
`probe`, `download`, and source discovery.

The NAL and SDF schemas distinguish fields numbered in DOR's summary PDFs from
the expanded physical CSV columns in published archives. A download inspects
only the CSV header, reports its field count and fingerprint, and verifies the
columns needed for later projection. The sampled 2026P Baker NAL has 92
documented logical fields and 165 physical columns; its SDF has 14 documented
logical fields and 23 physical columns. Additive columns do not make an
archive invalid. GIS-PIN publishes polygon geometry keyed by `PARCELNO`, which
joins to the NAL `PARCEL_ID`.

```bash
uv run python tools/query_fl_dor_property.py list --type nal \
  --output "$WORKDIR/fl-nal-releases.json"
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
  --type nal --archive "$WORKDIR/fl-baker-nal.zip" \
  --property-db "$WORKDIR/property-records.db" \
  --output "$WORKDIR/fl-baker-nal-ingest.json"
uv run python tools/ingest_fl_dor_property.py ingest \
  --type gis-pin --archive "$WORKDIR/fl-baker-gis-pin.zip" \
  --property-db "$WORKDIR/property-records.db" \
  --output "$WORKDIR/fl-baker-gis-ingest.json"
```

The streaming archive ingester projects NAL parcel, assessment-owner,
address, value, and legal-description observations. SDF rows become
assessment-sale observations and retain book, page, and clerk references;
they do not create recorded-title instruments. GIS-PIN ingestion aligns the
SHP, SHX, DBF, and PRJ members and retains every feature occurrence, including
blank join keys and repeated `PARCELNO` values. Joinable features create
source-attributed parcel shells and native-CRS `parcel_geometry` rows. A single
feature is referenced directly from its evidence observation; multiple
features for one parcel are grouped into an occurrence collection without a
spatial union, so source geometry is not discarded or recast as a surveyed
boundary.

MassGIS publishes municipal parcel snapshots through an official manifest
layer. The adapter resolves the municipality and assessor fiscal year, exposes
shapefile and file-geodatabase artifacts, and supports local archive
inspection/extraction as well as transfer.

```bash
uv run python tools/query_massgis_property.py manifest --town GOSNOLD \
  --output "$WORKDIR/massgis-manifest.json"
uv run python tools/query_massgis_property.py probe --town GOSNOLD \
  --format shapefile --output "$WORKDIR/massgis-probe.json"
uv run python tools/query_massgis_property.py download --town GOSNOLD \
  --format shapefile --destination "$WORKDIR/massgis-gosnold.zip" --dry-run \
  --output "$WORKDIR/massgis-transfer-plan.json"
uv run python tools/query_massgis_property.py inspect \
  "$WORKDIR/massgis-gosnold.zip" \
  --output "$WORKDIR/massgis-archive.json"
```

The Florida and MassGIS adapters use the shared bulk manifest and transfer
family. Release fingerprints, source coverage, artifact metadata, and optional
caller-selected transfer/archive ceilings stay visible in their output.

## Texas HCAD CAMA, HCAD GIS, and TxGIO parcel releases

Harris Central Appraisal District publishes tax-year CAMA manifests for
assessment, ownership, improvement, appraisal deed-reference,
personal-property, and hearing extracts. The catalog identity is
`us-tx-harris-hcad-property`. `query_harris_property.py` represents each
published archive without requiring a full download:

```bash
uv run python tools/query_harris_property.py list \
  --output "$WORKDIR/hcad-years.json"
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
```

The current real-property release has five separately identified artifacts:
`Real_acct_owner.zip`, `Real_acct_ownership_history.zip`,
`Real_building_land.zip`, `Real_jur_exempt.zip`, and
`Code_description_real.zip`. The catalog and monitor preserve the tax-year
certification state, source update date, artifact set, codebook, and transport
observations. Ingestion keeps physical ownership-history occurrences separate
even when their account, date, name, and address values repeat. HCAD deed and
clerk fields are appraisal observations and useful County Clerk pivots; they
do not become controlling recorded-title instruments.

HCAD's separate GIS publication is
`us-tx-harris-hcad-gis`. It combines HCAD's current and 2021–2025 historical
ZIP manifests with an official Harris County GIS MapServer representation of
HCAD parcel data:

```bash
uv run python tools/query_hcad_gis.py releases \
  --output "$WORKDIR/hcad-gis-releases.json"
uv run python tools/query_hcad_gis.py manifest \
  --output "$WORKDIR/hcad-gis-current.json"
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
```

The current bulk manifest was updated 2026-07-24, while the MapServer's
observed assessment field is predominantly tax year 2025 with nulls. Those are
different freshness observations and remain separate. The current
`Parcels.zip` is a FileGDB even though the publication page's category label
says “Shapefiles.” `query_hcad_gis.py inspect` records archive representation
and CRS (EPSG:2278). The source-neutral `public_records_filegdb.py` adds
content-based container lineage without GDAL and, with GDAL 3.7+ plus
OpenFileGDB, structural layer schemas and native-FID feature pages with
native-CRS WKB:

```bash
uv run python tools/public_records_filegdb.py container \
  "$WORKDIR/hcad-parcels.zip" \
  --output "$WORKDIR/hcad-filegdb-container.json"
uv run python tools/public_records_filegdb.py inspect \
  "$WORKDIR/hcad-parcels.zip" \
  --parcel-field HCAD_NUM \
  --output "$WORKDIR/hcad-filegdb-schema.json"
uv run python tools/public_records_filegdb.py features \
  "$WORKDIR/hcad-parcels.zip" --layer Parcels \
  --parcel-field HCAD_NUM --limit 100 \
  --output "$WORKDIR/hcad-filegdb-page.json"
```

Structural layer identity does not change when a caller chooses a different
parcel-join interpretation. Native FID remains the feature occurrence;
`HCAD_NUM` is only a reversible parcel-account candidate. Inspection remains
available with `ogrinfo` alone; feature extraction separately verifies
`ogr2ogr` and its GPKG write support. MapServer query results can separately
project parcel, assessment, owner/address, occurrence, and EPSG:4326 Esri JSON
geometry rows. A source-specific normalized projection from FileGDB feature
pages is still a separate mapping step. The county MapServer is another
official representation of HCAD data, not independent corroboration.

The statewide complement, `us-tx-txgio-land-parcels`, publishes annual TxGIO
collections as county and statewide ZIP resources:

```bash
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
```

The current collection contains 254 resources: 253 county artifacts and one
Texas aggregate. Donley is the observed county gap, so resource count is not
county coverage. The official Texas Comptroller appraisal-district directory
is the alternative route for Donley and for fresher local releases. Local
TxGIO owner, address, parcel, and search operations scan an explicitly
downloaded archive. The `map` result and normalized geometry row retain the
artifact hash, aligned shapefile member, DBF record occurrence, source
projection, and `geometry_decoded=false`; source adapters can now pass the
downloaded artifact to `public_records_shapefile.py` for aligned native-CRS
feature decoding. Repeated or blank parcel join values remain separate feature
occurrences, and source-specific normalized geometry projection remains an
explicit mapping step.
TxGIO's current map service is an interactive representation of the same
dataset and therefore is not a second corroborating source.

HCAD CAMA, HCAD GIS, and TxGIO are routed through `query_property.py` with
exact declared operation sets. Their monitors hash endpoint, schema,
record-identity, and representation contracts while keeping release dates,
counts, artifact metadata, and tax-year values in rolling observations.

## Texas Comptroller EPTS transaction reports

The Texas Comptroller describes Electronic Property Transaction Submission
(EPTS) files collected from appraisal districts and compiled into a statewide
database. The official September 2025 manual defines 52 fields, including
property and school-district identifiers, grantor/grantee roles, sale and deed
dates, consideration, deed locators, appraisal values, and the Field 33 A-Q
confidentiality codes. The agency does not publish that statewide compilation
as a direct download on its data-submission page, so
`us-tx-comptroller-epts` separates acquisition from processing:

```bash
uv run python tools/query_texas_epts.py discover \
  --output "$WORKDIR/texas-epts-source.json"
uv run python tools/query_texas_epts.py schema \
  --output "$WORKDIR/texas-epts-schema.json"
uv run python tools/query_texas_epts.py request-plan \
  --cad-id 101 --cad-id 227 \
  --output "$WORKDIR/texas-epts-request-plan.json"
uv run python tools/query_texas_epts.py inspect \
  "$WORKDIR/epts-delivery.zip" \
  --output "$WORKDIR/texas-epts-inspection.json"
uv run python tools/query_texas_epts.py search \
  "$WORKDIR/epts-delivery.zip" "EXAMPLE LLC" --field party \
  --output "$WORKDIR/texas-epts-results.json"
```

`request-plan` prepares the scope and official CRRS/email handoff without
submitting it. After a caller obtains a delivery, `inspect`, `parse`, and
`search` validate the exact 52-column layout and stream CSV, tab-delimited,
XLSX, or ZIP members. The artifact hash, member, physical/source row, and row
hash identify the published occurrence. `CAD_ID + PROP_ID1_TX` is a reversible
property candidate, while a deed number or volume/page remains a county-clerk
search pivot rather than an instrument copy or title assertion. Multiple-
account rows remain separate, and blanks or source redaction markers covered
by `CNFD_CD` are preserved as explicit field states.

No delivered real-world EPTS specimen was available during implementation.
The first acquired artifact therefore needs an `inspect` receipt before its
records are relied on; the checked-in fixtures exercise the official manual's
contract rather than claiming specimen validation.

## Harris County recorder and foreclosure sources

Harris County's appraisal roll, recorded-instrument index, foreclosure notices,
and court records are separate sources. The shared property router can send an
exact instrument or notice identifier to the correct adapter, while the direct
tools expose the source-specific selectors:

```bash
# Exact instrument or party/legal-description search
uv run python tools/query_harris_recorder.py search \
  --file-number RP-2026-72194 \
  --output "$WORKDIR/harris-instrument.json"
uv run python tools/query_harris_recorder.py search \
  --grantor "EXAMPLE HOLDINGS LLC" --from-date 2026-01-01 \
  --to-date 2026-07-29 \
  --output "$WORKDIR/harris-grantor.json"

# Foreclosure notice index and the Clerk-hosted notice PDF
uv run python tools/query_harris_foreclosures.py search \
  --document-id FRCL-2026-4797 \
  --output "$WORKDIR/harris-foreclosure.json"
uv run python tools/query_harris_foreclosures.py download FRCL-2026-4797 \
  --destination "$WORKDIR/harris-foreclosure.pdf" \
  --output "$WORKDIR/harris-foreclosure-receipt.json"

# Shared exact-identifier routes
uv run python tools/query_property.py instrument RP-2026-72194 \
  --source us-tx-harris-clerk-real-property \
  --output "$WORKDIR/harris-unified-instrument.json"
uv run python tools/query_property.py search FRCL-2026-4797 \
  --source us-tx-harris-clerk-foreclosures \
  --output "$WORKDIR/harris-unified-foreclosure.json"
```

The recorder adapter exposes file/film number, filing date, grantor, grantee,
trustee, instrument type, volume/page, and legal-description fields. The live
index publishes neither a result count nor a paginator; when a query lands on
the observed 200-row boundary the envelope reports that possible
incompleteness. Its image account and pipe-delimited/TIFF bulk products remain
discoverable through `products`.

The foreclosure adapter follows every native result page by default and
retrieves the anonymous Clerk PDF. A foreclosure notice proves that a notice
was filed or a sale advertised; it does not by itself prove a transfer of
title. Join it to the recorder index, HCAD assessment releases, and relevant
District Clerk case metadata using the native names, dates, legal description,
case number, and instrument references each source actually supplies.

## Sidecar evidence model

`datasets/property_records.db` preserves source observations rather than
flattening them into one current-owner row. Its principal record families are:

- jurisdiction and record office;
- parcel snapshots, aliases, addresses, and source geometry;
- assessments, tax events, and sale events;
- recorded instruments, parties, parcel links, and parcel lineage;
- ownership assertions with assertion type, confidence ceiling, and effective
  interval;
- document artifacts and evidence representations with hashes and source state.

A native APN, PIN, BBL, or SSL is unique only within its jurisdiction and
sometimes only within a roll year. The schema preserves execution, recording,
sale, assessment, snapshot, and retrieval dates separately, retains all
co-owners and instrument parties, and models parcel ownership and beneficial
ownership as different assertion types.

The adapter-neutral entry point retains every canonical property envelope and
status, even before a structured mapper exists:

```bash
uv run python tools/ingest_property_records.py ingest \
  --input "$WORKDIR/property-result.json" \
  --output "$WORKDIR/property-ingest.json"
```

Its summary distinguishes `records_ingested` from
`records_preserved_without_projection` and reports whether a structured
projection exists. Current projections include NC OneMap; Denver, Arlington,
Bexar, Miami-Dade, and Orleans assessor/parcel records; Delaware FirstMap;
Cook County Parcel Universe; Maryland assessments and conservative Plats.net
record/artifact observations; the implemented county recorder families; and
direct document-shaped ACRIS envelopes. The Plats.net mapper does not create a
recorded instrument, parcel link, or ownership assertion from plat metadata.
The source-specific NC command remains available:

```bash
uv run python tools/ingest_property_records.py nc-onemap \
  --input "$WORKDIR/nc-parcel-direct.json" \
  --output "$WORKDIR/nc-ingest.json"
```

The ingester is idempotent for the same source observation. The unified router
can run the adapter-neutral path for any live adapter result in one step with
`--ingest`.

Cook County and Maryland results use the same generic command:

```bash
uv run python tools/ingest_property_records.py ingest \
  --input "$WORKDIR/cook-parcel.json" \
  --output "$WORKDIR/cook-ingest.json"

uv run python tools/ingest_property_records.py ingest \
  --input "$WORKDIR/md-parcel.json" \
  --output "$WORKDIR/md-ingest.json"
```

Cook ingestion projects parcel snapshots, address observations, assessments,
and parcel aliases. Maryland ingestion preserves the source's hidden-owner
state and projects the available parcel, address, assessment, and sale
observations without backfilling an owner into the Maryland observation.

## Artifacts and document understanding

`public_records_artifacts.py` stores source bytes by SHA-256 and appends
acquisition, derived-representation, field-evidence, and restriction events.
The source bytes remain distinct from OCR, parsed text, model output, and
validated field assertions.

```bash
uv run python tools/public_records_artifacts.py init
uv run python tools/public_records_artifacts.py put "$WORKDIR/deed.pdf" \
  --source-id us-example-recorder \
  --canonical-ref "PROPERTY:us-example-recorder/99999/instrument/2026-42" \
  --source-url "https://example.gov/record/2026-42" \
  --output "$WORKDIR/deed-artifact.json"
uv run python tools/public_records_artifacts.py verify \
  --output "$WORKDIR/artifact-verification.json"
```

`public_records_extract.py` accepts adapter- and model-neutral extraction JSON.
It validates evidence anchors, quotes, dates, amounts, identifiers, and schema
fields before importing evidence rows. Review thresholds are supplied by the
caller when useful; queue decisions remain append-only.

```bash
uv run python tools/public_records_extract.py validate \
  "$WORKDIR/deed-extraction.json" \
  --output "$WORKDIR/deed-validation.json"
uv run python tools/public_records_extract.py ingest \
  "$WORKDIR/deed-extraction.json" \
  --output "$WORKDIR/deed-extraction-ingest.json"
uv run python tools/public_records_extract.py queue \
  --output "$WORKDIR/public-record-review.json"
uv run python tools/public_records_extract.py decide REVIEW_REF \
  --decision accepted --by analyst \
  --output "$WORKDIR/public-record-review-decision.json"
```

## Search planning, action routing, and entity candidates

Build a deterministic cross-domain plan before a broad search. It merges
explicit selectors with the active profile, known addresses, aliases, and
related entities; inventories every catalog source; and emits dependency-aware
property, recorder, and court query templates. The inventory retains unmatched
sources for gap analysis, while executable templates are limited to sources
whose catalog coverage matches at least one requested jurisdiction and each
template carries only that source's matched jurisdictions. The
`complementary_routes` section expands every catalog-declared relationship
into a field-oriented comparison of roles, supported capabilities, access
mode, coverage start/cadence, jurisdiction fit, and
shared-versus-independent record identity. This
keeps a difficult primary route connected to the sources and request channels
that can still answer parts of the same research question. When a
jurisdiction-matched route has no declared complement, the plan emits a
`complementary_route_not_cataloged` gap so the source review explicitly checks
adjacent indexes, publications, archives, custodians, and useful account or
data-product routes.

```bash
uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
  --alias "Example Holdings" \
  --address "100 Main St, Albany, NY" \
  --jurisdiction 36 \
  --output "$WORKDIR/example-public-record-plan.json"
```

For a catalog route that still needs account setup, feed configuration,
purchase, a records request, or physical retrieval, render the next action or
add it to the shared action queue. Direct adapters remain available whenever
the corresponding route is configured:

```bash
uv run python tools/public_records_actions.py plan us-in-iocs-bulk \
  --operation obtain_feed --selector "civil case metadata" \
  --output "$WORKDIR/indiana-feed-action.json"
uv run python tools/public_records_actions.py enqueue us-ny-nyscef \
  --operation fetch_document --selector "156728/2019 document 42" \
  --output "$WORKDIR/nyscef-document-action.json"
uv run python tools/public_records_actions.py list --status pending \
  --output "$WORKDIR/public-record-actions.json"
```

After observations have been retained, generate entity candidates across
property owners, instrument parties, and court parties. Every candidate keeps
its matching signals and decision history; accept, reject, reopen, and undo
are explicit operations.

```bash
uv run python tools/public_records_entity_candidates.py generate \
  --output "$WORKDIR/public-record-entity-candidates.json"
uv run python tools/public_records_entity_candidates.py list --status open \
  --output "$WORKDIR/open-public-record-candidates.json"
uv run python tools/public_records_entity_candidates.py history CANDIDATE_REF \
  --output "$WORKDIR/public-record-candidate-history.json"
```

## Monitoring and evaluation

The monitor reads current catalog facts and runs an explicitly named,
registered probe handler. Probe observations are immutable and can be compared
for status, artifact, or schema changes. A `run` returns exit code `0` only
when every requested source records `ok` or an authoritative `no_results`;
unhealthy or undispatched probes return `1`, while command and catalog errors
return `2`.

```bash
uv run python tools/public_records_monitor.py plan \
  us-nc-onemap-parcels us-ma-massgis-parcels \
  --output "$WORKDIR/public-record-monitor-plan.json"
uv run python tools/public_records_monitor.py run us-nc-onemap-parcels \
  --output "$WORKDIR/nc-monitor-run.json"
uv run python tools/public_records_monitor.py diff us-nc-onemap-parcels \
  --output "$WORKDIR/nc-monitor-diff.json"
```

The evaluator reports adapter false-zero/barrier handling, extraction
precision/recall and invention counts, protected-field leakage, critical-field
accuracy, and document-triage recall/reduction. It applies any release
thresholds present in the caller's bundle.

```bash
uv run python tools/public_records_eval.py template \
  --output "$WORKDIR/public-record-eval-template.json"
uv run python tools/public_records_eval.py run "$WORKDIR/public-record-gold.json" \
  --output "$WORKDIR/public-record-eval.json"
```

## Cross-domain workflow

Property and court searches are most useful as a reproducible sequence:

1. Generate a `public_records_search_plan.py` plan from names, aliases,
   related entities, jurisdictions, and known addresses.
2. Search relevant parcel and assessment capabilities, then convert hits to
   jurisdiction-scoped parcel IDs, legal descriptions, and predecessor or
   successor parcels.
3. Search both party directions in recorder indexes and follow referenced
   deeds, mortgages, releases, assignments, liens, and lis pendens.
4. Search `query_state_courts.py` for people, owning entities, lenders,
   trustees, counsel, case numbers, addresses, and property identifiers.
5. Retain source artifacts and representations, validate extracted fields,
   and rank filings by relevance to the hypothesis.
6. Generate and review entity-link candidates, preserving distinct source
   observations and provenance.

LLMs can classify documents, propose field mappings, rank likely material
filings, and generate entity-match candidates at scale. Deterministic
validators then check identifiers, dates, amounts, required fields,
restriction states, and source lineage. Candidate matches remain reviewable
and reversible.
