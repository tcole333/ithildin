# Court Records & Legal

Tools for US federal/state court dockets, opinions, judge research, and European Court of Human Rights cases.

**When to read this module:** When running /analyze-case, /deep-investigate (Agent C), or researching litigation history, judicial conflicts of interest, or ECHR proceedings for any entity.

## Tool Inventory

| Tool | Source | Auth | Local Data | Rate Limit |
|------|--------|------|------------|------------|
| `query_state_courts.py` | Unified state/local-court router | Catalog-reviewed per source | `datasets/state_court_records.db` | Source-specific; local by default |
| `public_records_search_plan.py` | Cross-domain property/recorder/court planner | None | Reads catalog and investigation context | Local |
| `public_records_actions.py` | Formal-feed, account, paid, request, and physical-access work planner | Catalog route metadata | `human_actions` in `investigation.db` | Local |
| `public_records_store.py` | Normalized state/local-court evidence sidecar | None | `datasets/state_court_records.db` | Local |
| `ingest_state_court_records.py` | Adapter-neutral court-envelope ingester | None | `datasets/state_court_records.db` | Local |
| `query_florida_acis.py` | Florida Supreme Court and six District Courts of Appeal | None for public search and available public documents | No | Source-managed |
| `query_florida_court_directory_data.py` | Florida court/clerk locations, virtual courtrooms, OSCA request routing, and aggregate trial-court statistical publications | None | No | Current snapshots; exact statistical PDFs by source content ID |
| `query_florida_ninth_opinions.py` | Ninth Judicial Circuit archived appellate, certiorari, and writ opinions for Orange and Osceola Counties | None | No | Source-visible pages with query-bound continuations |
| `query_osceola_courts.py` | Osceola Clerk Benchmark cases, dockets, public document-page metadata, current hearing calendar, and foreclosure schedule | None for public routes | No | Source-native case paging; reports are rolling snapshots |
| `query_georgia_court_directory.py` | Georgia AOC current court-personnel directory and exact public detail views | None | No | Native pages with filter- and page-size-bound continuations |
| `query_georgia_court_access.py` | Georgia AOC eAccess case-search provider routes and eFile provider availability | None for directories; provider account for destination activity | No | Complete current directory snapshots with query- and snapshot-bound local cursors |
| `query_georgia_court_data.py` | Georgia AOC aggregate caseload dashboards, export-request handoff, and annual Superior Court workload assessments | None | No | Query-bound catalog continuations; exact annual PDF validation by publication year |
| `query_vicourts.py` | Virgin Islands Supreme and Superior Courts C-Track portal plus exact numeric legacy files | None | No | 500 rows/page; C-Track search window ends at 10,000 |
| `query_bexar_courts.py` | Bexar County District Clerk Historical Cases | Anonymous public session | No | No published request rate; source-native offset pagination |
| `query_ohio_franklin_probate.py` | Franklin County Probate Court case, attorney, and fiduciary indexes plus exact case/docket/person records | None | No | Native 40-row forward/back indexes; omitted limits exhaust the forward keys |
| `query_los_angeles_court.py` | Los Angeles Superior Court civil Case Summary and current tentative rulings | None | No | All six case sections and all current ruling selections by default |
| `query_los_angeles_name_index.py` | Los Angeles Superior Court paid party-name index, cart preparation, receipt recovery, and saved-result parsing | None for probe; guest receipt or account purchase for results | Purchased pages supplied by the caller | Source coverage and fee schedule; every parsed purchased row is retained |
| `query_los_angeles_probate.py` | Los Angeles Superior Court probate Case Summary, Probate Notes, and Case Calendar | None | No | No adapter result cap; Probate Notes and calendars retain source-stated windows |
| `query_california_opinions.py` | California current published slip and unpublished appellate-opinion indexes, exact details, citings archives, and PDF/DOCX retrieval | None | No | Native 50/100/200-row pages within the published 120-day and unpublished 60-day feeds |
| `query_california_court_directory.py` | California Judicial Branch 58-county superior-court and service-route directory | None | No | Complete current directory snapshot |
| `query_santa_clara_court_records.py` | Santa Clara current tentative-ruling PDFs, requested civil/criminal index products, and public-portal access state | Component-specific | No | Complete current department/product indexes |
| `query_san_diego_court_index.py` | San Diego party/case index, case detail, and five-court-day new-filing lists | None; Court Index uses headed Chrome | No | Complete native pages/partitions unless caller limits |
| `query_fresno_superior_court.py` | Fresno Superior Court daily calendars, tentative rulings, Probate Examiner Notes, portal observation, and acquisition alternatives | Component-specific | No | Current official indexes and selected artifacts are complete by default |
| `query_orange_county_court.py` | Orange County Superior Court six-category hearing calendar and current civil, family, and probate tentative-ruling publications | None for implemented sources | No | Calendar pages and current ruling directories are exhaustive by default |
| `query_riverside_court.py` | Riverside Superior Court four-business-day eCalendar and current tentative-ruling PDF directory | None for implemented sources | No | Complete selected calendar responses and all current directory links by default |
| `query_qld_ecourts.py` | Queensland eCourts Supreme and District Court civil case index, parties, events, and document-list metadata | None | No | Native 20-row pages; exhaustive adaptive partitioning around the 500-result source ceiling |
| `query_san_mateo_midx.py` | San Mateo Superior Court MIDX case and party index | Anonymous public browser session | No | Five-calendar-day filing-date window; opaque pages; all rows by default |
| `query_dc_appellate_cases.py` | D.C. Court of Appeals C-Track case, participant, docket, and filing search | None | No | Native one-based 50-row pages; all pages by default |
| `query_dc_opinions.py` | D.C. Court of Appeals opinions and Memorandum Opinion and Judgment index | None | No | Native zero-based 10-row pages; exhaustive by default |
| `query_dc_superior_calendar.py` | D.C. Superior Court daily/criminal hearings, Tax Division calendar PDFs, and Court of Appeals calendar artifacts | None | No | Native 10-row hearing pages and current REST snapshot are exhaustive by default |
| `query_dc_court_directory_data.py` | D.C. Superior Court and Court of Appeals directories, court contacts, data-request forms, and aggregate report publications | None for published pages and PDFs | No | Complete role-aware directory traversal and complete selected publication catalog |
| `query_md_public_cases.py` | Maryland MDEC rolling Cases Filed reports | None | No | Five current daily PDFs; local result cursors after complete report parsing |
| `query_md_estate_search.py` | Maryland statewide Register of Wills estate cases, parties, status, and docket history | None | No | Native 20-row WebForms pages; fresh-session, query/schema/count/daily-refresh-bound continuation |
| `query_md_estate_notices_claims.py` | Maryland statewide estate legal notices and filed claims | None | No | Native 20-row WebForms pages; query/result-bound continuation, full notice text, and exact claim-detail enrichment |
| `query_md_judgment_liens.py` | Maryland statewide Circuit Court judgment and lien index | None | No | Native 25-row pages and a source-published 500-result boundary |
| `query_md_opinions.py` | Maryland reported and unreported appellate decision indexes and official PDFs | None | No | Complete reported filing-year indexes; complete source-published unreported month indexes with query-bound anchor continuation |
| `query_md_business_opinions.py` | Maryland Business and Technology trial-court opinions, orders, synopses, and source-listed documents | None | No | Complete current 2009-present table and six closed annual archives for 2003-2008; query-bound anchor continuation |
| `query_michigan_appellate.py` | Michigan Judiciary appellate cases, opinions, and orders | None | No | Separate one-based result pages at 10/25/50/100 rows; query-bound continuation |
| `query_michigan_business_court.py` | Michigan Judiciary Business Court document search, facets, and official PDFs | None | No | Fixed eight-row native pages; omitted limits traverse `totalPages`; query-bound continuation |
| `query_washington_courts.py` | Washington official court directory, appellate opinions, current-system routes, document portals, data products, and historical complements | Component-specific | No | Complete selected directory/opinion lists by default; CAPTCHA-gated result routes remain explicit handoffs |
| `query_wisconsin_court_directory.py` | Wisconsin circuit offices, clerks, judges, administrative districts, appellate offices, and state court offices | None | No | Complete selected component snapshots; filtering occurs after complete page retrieval |
| `query_new_jersey_tax_court.py` | New Jersey Tax Court current docketed and open local-property case reports | None | No | Complete selected XLSX traversal; query- and artifact-bound continuation when limited |
| `query_new_jersey_tax_court_opinions.py` | New Jersey Tax Court published and unpublished opinion indexes and documents | None | No | Native 20-row pages; complete selected collections by default with snapshot-bound continuation |
| `query_pa_ujs.py` | Pennsylvania UJS public case indexes and docket/Court Summary PDFs | None | No | Source-native 180-day filed-date partitions; observed no-pager boundary is explicit |
| `query_pa_opinions.py` | Pennsylvania Supreme, Superior, and Commonwealth Court postings/PDFs | None | No | Native 20-row pages; all pages by default |
| `query_delaware_courts.py` | Delaware CourtConnect civil cases, dockets, and judgments | None | No | Native 20-row pages; all pages by default |
| `query_delaware_opinions.py` | Delaware Opinions and Orders metadata/PDF archive | None | No | Native 25/50/100-row pages; all pages by default |
| `query_denver_county_court.py` | Denver County Court daily courtroom/date docket | None | No | One server-rendered result table; optional caller-selected row window |
| `query_colorado_opinions.py` | Colorado appellate historical case-law search plus current Judicial Branch release surfaces | None | No | Native 20-row historical pages traversed against the reported count; current releases use their own page links |
| `query_colorado_court_data.py` | Colorado Judicial reports, dashboards, and compiled/aggregate-data request materials | None | No | Unpaginated official landing pages; exact verified PDF artifact downloads |
| `query_oregon_appellate_calendars.py` | Separate Oregon Supreme Court and Court of Appeals calendar lists, including published Supreme Court brief attachments | None | No | Complete SharePoint continuation traversal; official view limits retained as separate facts |
| `query_oregon_court_calendar.py` | Oregon Circuit and Tax Court hearing calendars, locations, and judicial-officer selectors | Anonymous public session | No | Current/forward 90-day source window; caller-selected paging; explicit source truncation retained |
| `query_oregon_court_directories.py` | Oregon state/local court and judge directories plus local-source discovery | Anonymous public session | No | Complete SharePoint rowsets with query- and snapshot-bound local cursors |
| `query_eugene_municipal_court.py` | Eight Oregon Tyler Municipal Record Search tenants: five public municipal/justice indexes and three directly observed sign-in or missing-route tenants with official alternatives | Component-specific | No | Tenant-bound server-rendered snapshots and direct case/docket access observations |
| `query_oregon_court_documents.py` | Seven official Oregon Law Library opinion, brief, Tax Court, appellate-order, and Multnomah presiding-order collections | None | No | Count-driven CONTENTdm offsets with query-bound overlap cursors and component-specific completeness |
| `query_oregon_smart_search.py` | Oregon Circuit and Tax Court rendered Smart Search contract, live selector sets, and browser-ready search handoffs | None for the public page; the live submission presents reCAPTCHA | No | `prepare` is local; `probe` and `options` render the current official page |
| `query_oregon_ojcin_products.py` | OECI, ACMS, standard reports, approved bulk transfer, and OSCA statewide-data acquisition routes | Public product metadata; acquisition is product-specific | User-supplied delivery paths only | Thirteen official representations in a full probe; delivery inspection is local |
| `query_harris_court_bulk.py` | Harris County District Clerk civil and criminal public datasets | None | No | Complete live artifact catalog; exact artifact selection |
| `query_tax_court.py` | U.S. Tax Court DAWSON public API | None | No | Native 5,000-result search ceilings; docket pages 0–20 at 1,000 rows/page |
| `query_courtlistener.py` | CourtListener/RECAP API (v4) | `COURTLISTENER_TOKEN` in .env | No | Reasonable (API token required) |
| `query_doj_court_records.py` | DOJ Epstein case-grouped court-record release corpus | None | No | One current case-group index; exact case pages exhaust native pagination unless caller-limited |
| `query_ny_attorneys.py` | New York OCA quarterly attorney registrations through official NY Open Data | Optional `NY_OPEN_DATA_APP_TOKEN` | No | All matches by default; query- and snapshot-bound v2 continuation when limited |
| `query_nyscef.py` | NYSCEF portal adapter | Catalog-selected route | No | Source-specific |
| `query_nyscef_fulltext.py` | Local NYSCEF manifest/PDF normalization, page text/OCR, and SQLite FTS5 search | Uses supplied acquired files | Caller-selected SQLite corpus | Incremental by document identity and PDF SHA-256 |
| `query_ny_law_reports.py` | New York Law Reporting Bureau decisions | None | No | Monthly source windows; no adapter result cap |
| `query_ny_column.py` | New York newspaper public notices via Column | None | No | One-indexed pages; 10,000 displayed matches per partition |
| `query_hudoc.py` | HUDOC REST API (undocumented) | None | No | 0.5s between requests |
| `query_military_corrections.py` | DoD Boards of Review Reading Room (boards.law.af.mil) | None | `.cache/military_corrections.db` (SQLite + FTS5) | 2.0s between requests (~0.5 req/sec) |
| `query_military_justice.py` | CAAF + ACCA + NMCCA + AFCCA + CGCCA (HTML/PDF scraping) | None | `datasets/military_justice_cache.db` (SQLite WAL) | 1 req/sec per host (configurable) |

## Unified state/local-court interface

`query_state_courts.py` searches normalized local observations by default and
reads the public-records catalog when a named live source is selected. The
result envelope keeps true zeroes, partial coverage, human actions, terms
blocks, unavailable sources, and later restrictions distinct.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
# Inspect cataloged coverage and reviewed access
uv run python tools/query_state_courts.py sources --jurisdiction 36 \
  --output "$WORKDIR/state-court-sources.json"

# Search the normalized local sidecar
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --output "$WORKDIR/state-court-search.json"
uv run python tools/query_state_courts.py case "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-case.json"
uv run python tools/query_state_courts.py docket "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-docket.json"
uv run python tools/query_state_courts.py documents "2025-CV-000001" \
  --court-id example-circuit \
  --output "$WORKDIR/state-court-documents.json"

# NYSCEF currently resolves to its catalogued human route
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --source us-ny-nyscef --jurisdiction 36 \
  --output "$WORKDIR/nyscef-human-action.json"

# Florida ACIS is a live source route for the statewide appellate courts
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --source us-fl-acis --jurisdiction 12 \
  --output "$WORKDIR/florida-acis-search.json"

# Virgin Islands C-Track is a live territorial court route
uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --source us-vi-c-track --jurisdiction 78 \
  --output "$WORKDIR/vicourts-search.json"
```

The router reports the current catalog state for each selected source. A
successful query with no matching cases is `no_results`; account, feed,
human-action, unavailable, and changed-source routes retain their own result
states instead of being collapsed into a false zero. The normalized court
sidecar preserves courts, cases, parties, attorneys and representations,
judicial assignments, docket entries, events, document artifacts, source
snapshots, and restriction events.

The court store keeps each source-native access, assertion, and restriction
label alongside its canonical category. Known variants such as
`made_nonpublic` and `destroyed` map to serving states, while unfamiliar values
remain queryable through `other` or `unknown` instead of aborting ingestion.

Local sidecar presence in one court or jurisdiction does not establish
coverage elsewhere. A miss in an observed scope is `partial`; a miss outside
observed scope is `unavailable`. Both carry machine-readable scope counts,
matching snapshot evidence, and catalog/action route guidance. An exact
source-query snapshot can support `no_results` when its source, jurisdiction or
court, selector, date filters, and completion state match the request. An exact
known case or document identifier with a non-public current access state
returns `restricted` plus a minimal restriction tombstone; case contents,
parties, docket text, document paths, and artifact bytes are not served in that
tombstone.

Canonical state/local-court citations use:

```text
STATECOURT:<source_id>/<court_id>/<case_number>/<record_kind>[/<native_id>]
```

Generic `STATECOURT:` references link to the official source landing page when
that source ID is registered. They do not invent a case-detail URL. Other
source IDs remain record-only. Later source restriction events update current
serving state while preserving the observation and audit history.

## Census context for local-court analysis

`query_census_acs.py` can attach release-specific population, housing, income,
poverty, age, and race/ethnicity denominators to a court’s county, tract, block
group, place, or ZCTA. The cross-domain planner emits this as
`enrich_census_geography`, using jurisdiction and address seeds rather than
party-name queries. This supports venue context, filing-rate denominators, and
geographic disparity analysis; the resulting ACS estimate describes an area
and does not establish a fact about a party or case. See
`docs/modules/property.md` for commands, margins of error, backend provenance,
Geocoder crosswalks, and TIGERweb boundary joins.

## D.C. Court of Appeals opinions and MOJs

`query_dc_opinions.py` follows the current redesigned D.C. Courts
`opinions-and-memorandum-of-judgments` index. It preserves each disposition's
appeal number or numbers, caption, decision date, disposition, judge,
publication class, full-text state, and official PDF link when the court
publishes one. Published opinions and Memorandum Opinion and Judgment (MOJ)
entries remain distinct: an opinion row can carry a court-hosted PDF, while an
MOJ row carries the index metadata and the full-text state published by this
source.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Direct searches traverse every native page by default.
uv run python tools/query_dc_opinions.py list \
  --query "24-BG-1045" --type opinions \
  --output "$WORKDIR/dc-opinions.json"
uv run python tools/query_dc_opinions.py list \
  --type mojs --date-from 2026-07-01 --date-to 2026-07-31 \
  --output "$WORKDIR/dc-mojs.json"

# Select one zero-based native page when doing a bounded inspection.
uv run python tools/query_dc_opinions.py list \
  --type all --page 7 --page-only \
  --output "$WORKDIR/dc-opinions-page-7.json"

# Unified queries return one native page plus a page:N continuation cursor.
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

The verified index reported 16,313 entries across 1,632 zero-based pages with
10 rows per full page. Its native selectors cover keyword, exact date or date
range, publication type, ordering field, and sort direction. Unified routing
uses one native page at a time so its continuation is composable with other
court sources; the direct command is the exhaustive corpus route.

The index is an appellate disposition and publication source, not the complete
case docket. The separate D.C. Court of Appeals case-search page supplies the
appellate docket complement, D.C. Superior Court eAccess supplies trial-court
records, and CourtListener supplies an independently searchable opinion and
docket complement. Ingestion stores every opinion or MOJ as an appellate
disposition docket entry and creates a document artifact only for a linked
opinion PDF.

## D.C. Court of Appeals case search

`query_dc_appellate_cases.py` implements the Court of Appeals C-Track case
system. Case and participant searches traverse its one-based 50-row pages.
Exact case retrieval keeps appellate and originating-matter numbers, parties,
counsel, docket events, source-internal identifiers, and the filing links
resolved through the source's DWR method. Download receipts verify the
court-returned PDF and retain its hash.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_dc_appellate_cases.py search \
  --caption "Example Holdings" --date-from 2024-01-01 \
  --output "$WORKDIR/dc-appellate-caption.json"
uv run python tools/query_dc_appellate_cases.py search \
  --originating-case-number "DDN 2024-D175" \
  --output "$WORKDIR/dc-appellate-origin.json"
uv run python tools/query_dc_appellate_cases.py participant \
  --last-name "Example" --first-name "Alex" \
  --output "$WORKDIR/dc-appellate-participant.json"
uv run python tools/query_dc_appellate_cases.py case 24-BG-1045 \
  --output "$WORKDIR/dc-appellate-case.json"

# Shared routes keep the native page cursor and can ingest full case children.
uv run python tools/query_state_courts.py search "Example Holdings" \
  --source us-dc-court-of-appeals-case-search --jurisdiction 11 \
  --search-field participant \
  --output "$WORKDIR/dc-appellate-unified-search.json"
uv run python tools/query_state_courts.py case 24-BG-1045 \
  --source us-dc-court-of-appeals-case-search --ingest \
  --output "$WORKDIR/dc-appellate-unified-case.json"
uv run python tools/query_state_courts.py documents 24-BG-1045 \
  --source us-dc-court-of-appeals-case-search \
  --output "$WORKDIR/dc-appellate-documents.json"

uv run python tools/public_records_monitor.py run \
  us-dc-court-of-appeals-case-search \
  --output "$WORKDIR/dc-appellate-monitor.json"
```

The originating trial or agency matter is stored as a related case with an
explicit relationship instead of being folded into the appellate identity.
The opinion/MOJ index and appellate calendars add disposition text and
scheduling. The Superior Court Tyler portal covers civil, civil Tax, probate,
landlord-tenant, and small-claims matters; eAccess covers criminal, criminal
Tax, and Domestic Violence matters. Their currently observed verification
steps are recorded per component and do not describe C-Track availability.

## D.C. court calendars

`query_dc_superior_calendar.py` keeps four official calendar sources distinct:
Today's Superior Court Cases, the Criminal Attorney Case Calendar, Tax
Division calendar PDFs, and Court of Appeals calendar artifacts. The two
Superior Court HTML searches use zero-based 10-row pages and traverse every
advertised page by default. Today's cases also have a complete current-day REST
snapshot; the criminal source separately publishes attorney and courtroom
schedule PDFs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Exhaustive direct searches and the complete current-day snapshot
uv run python tools/query_dc_superior_calendar.py search \
  --case-number "2026-LTB-005132" \
  --output "$WORKDIR/dc-today.json"
uv run python tools/query_dc_superior_calendar.py criminal \
  --case-number "2026 CTF 004287" \
  --output "$WORKDIR/dc-criminal.json"
uv run python tools/query_dc_superior_calendar.py snapshot \
  --output "$WORKDIR/dc-today-snapshot.json"

# Calendar-document indexes
uv run python tools/query_dc_superior_calendar.py artifacts \
  --family criminal --output "$WORKDIR/dc-criminal-pdfs.json"
uv run python tools/query_dc_superior_calendar.py artifacts \
  --family tax --output "$WORKDIR/dc-tax-pdfs.json"
uv run python tools/query_dc_superior_calendar.py appeals \
  --year 2024 --output "$WORKDIR/dc-appeals-calendars.json"

# Shared routing returns one native hearing page and its continuation.
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

Each hearing row is stored at occurrence grain, including its case number,
event timestamp and UTC offset, courtroom, judge, and source-page occurrence.
Repeated charge rows in the criminal calendar remain distinct. Calendar PDFs
remain `court_calendar_artifact` snapshots rather than being recast as case
filings.

These sources are especially useful when the interactive case systems are not
readily queryable. They disclose useful same-day party, defendant, attorney,
charge, judge, and courtroom information, while Portal and eAccess remain the
complementary routes for case histories and available documents. The Court of
Appeals opinion/MOJ index remains the complementary appellate disposition and
published-opinion source.

## D.C. judicial directories and data publications

`query_dc_court_directory_data.py` keeps four official products separate: the
Superior Court judicial directory, the Court of Appeals judicial directory,
the submitted data-request program, and the directly published reports
catalog. Directory searches traverse every advertised role page and reconcile
the resulting judge counts. Shared `query_state_courts.py` searches are
snapshot-only directory lookups; they do not project personnel as cases.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_dc_court_directory_data.py directory \
  --court superior --query Becker \
  --output "$WORKDIR/dc-superior-directory.json"
uv run python tools/query_dc_court_directory_data.py contacts \
  --court all --output "$WORKDIR/dc-court-contacts.json"
uv run python tools/query_dc_court_directory_data.py assignments \
  --output "$WORKDIR/dc-assignments.json"

uv run python tools/query_state_courts.py search Becker \
  --source us-dc-superior-court-judicial-directory \
  --search-field associate \
  --output "$WORKDIR/dc-directory-shared.json"

uv run python tools/query_dc_court_directory_data.py data-request \
  --output "$WORKDIR/dc-data-request.json"
uv run python tools/query_dc_court_directory_data.py reports \
  --section annual-reports --year 2025 \
  --output "$WORKDIR/dc-reports.json"

uv run python tools/public_records_monitor.py run \
  us-dc-superior-court-judicial-directory \
  us-dc-court-of-appeals-judicial-directory \
  us-dc-courts-reports-publication-catalog \
  --output "$WORKDIR/dc-directory-data-monitors.json"
```

The request program is a route for submitted aggregate, case-level, or
research requests, not a direct case/bulk feed. The reports catalog is a
separate aggregate source. Its occurrence-level records preserve the current
2023 narrative label pointing to the 2024 PDF URL and the duplicated 2022
Family Court report instead of silently merging or correcting them.

## Maryland recent cases, estates, judgment/liens, and published decisions

Seven anonymous official sources provide useful Maryland coverage independently
of the general Case Search portal.

`query_md_public_cases.py` discovers the current MDEC Cases Filed reports from
the Judiciary landing page and rolling directory, downloads the source-listed
PDFs, and parses case, caption, type, filing date, court, party name, published
party address, and charge fields. Search can cover the latest report, selected
report dates, every currently listed report, or an acquired local PDF.

`query_md_judgment_liens.py` follows the stateful JSF judgment index in either
person or company mode. It traverses native result pages and retrieves the
original judgment and later modification events for an exact case, including
names for and against, amount, status, entry date, and book/page.

`query_md_estate_search.py` follows the Register of Wills WebForms application
for all 23 counties and Baltimore City. It searches decedents, personal
representatives, or estate numbers and retains filing/death dates, estate type
and status, aliases, representatives and their published addresses, attorneys,
will/probate dates, and every docket row. The stable estate identity is county
plus estate number; numeric `RecordId` and docket `SecId` values remain source
locators.

`query_md_estate_notices_claims.py` follows two additional Register of Wills
WebForms applications. The legal-notice command retains each numeric notice
occurrence, exact source title and variant, complete notice HTML and text, and
the selected county, publication, death-date, party-role, name, and sort
criteria. The claim command supports decedent and filed-by roles, person and
corporation fields, estate number, filed date, county, type, status, and the
source's linked/migrated selectors. It follows every selected result page and
enriches each row from its exact `src` plus `RecordId` detail locator.

`query_md_opinions.py` keeps the Judiciary's reported and unreported appellate
collections separate. Reported decisions use complete filing-year CGI indexes
from 1995 onward. Unreported decisions use complete monthly indexes from
February 2001 onward; linked archive PDFs begin in May 2015, while earlier
rows remain searchable metadata. Opinion and order artifacts retain their
source PDF-path identity, and correction annotations remain attached to the
same document observation rather than creating a new case.

`query_md_business_opinions.py` covers the Business and Technology Case
Management Program's selective trial-court publications. It traverses the
current 2009-present table and the six annual 2003-2008 archives, retaining
publication designations, courts, supplied case numbers, judges, filing dates,
captions, counsel, and every source-listed opinion, order, or synopsis. The
observed archive has 160 publications and 268 attachment references across 267
unique URLs in PDF, DOC, and WPD formats. Source omissions, month-precision
dates, multiple case-number lines, duplicate URLs, doubled path segments, and
filename/designation mismatches remain explicit source states.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_md_public_cases.py reports \
  --output "$WORKDIR/md-current-reports.json"
uv run python tools/query_md_public_cases.py search --all-current \
  --name "Example" --filing-date-from 2026-07-01 \
  --output "$WORKDIR/md-recent-name.json"
uv run python tools/query_md_public_cases.py search --all-current \
  --address "Baltimore" \
  --output "$WORKDIR/md-recent-address.json"

uv run python tools/query_md_judgment_liens.py person "Example" \
  --first-name "Alex" --county "Baltimore City" \
  --output "$WORKDIR/md-person-judgments.json"
uv run python tools/query_md_judgment_liens.py company "Example Holdings LLC" \
  --output "$WORKDIR/md-company-judgments.json"
uv run python tools/query_md_judgment_liens.py detail 03-L-12-005195 \
  --output "$WORKDIR/md-judgment-events.json"

uv run python tools/query_md_estate_search.py decedent Novak \
  --first-name Patricia --county "Baltimore County" \
  --output "$WORKDIR/md-estates.json"
uv run python tools/query_md_estate_search.py representative Novak \
  --county "Baltimore County" --all-results \
  --output "$WORKDIR/md-representative-estates.json"
uv run python tools/query_md_estate_search.py estate 238438 \
  --county "Baltimore County" \
  --output "$WORKDIR/md-estate-index.json"
uv run python tools/query_md_estate_search.py detail 1868548158 \
  --output "$WORKDIR/md-estate-detail.json"
uv run python tools/query_md_estate_search.py routes \
  --output "$WORKDIR/md-estate-routes.json"

uv run python tools/query_md_estate_notices_claims.py notices \
  --county "Montgomery County" --published-from 2026-07-01 \
  --party-type decedent --last-name Smith \
  --output "$WORKDIR/md-estate-notices.json"
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
  --date-from 2026-01-01 --date-to 2026-07-31 --query "Properties" \
  --output "$WORKDIR/md-unreported-opinions.json"
uv run python tools/query_md_opinions.py routes \
  --output "$WORKDIR/md-opinion-routes.json"

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

# Unified source selection and normalization.
uv run python tools/query_state_courts.py search "Baltimore" \
  --source us-md-mdec-public-cases --jurisdiction 24 \
  --search-field address --after 2026-07-01 --ingest \
  --output "$WORKDIR/md-recent-unified.json"
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

The MDEC directory is a rolling recent-filing feed, so its report publication
date, report run time, reporting window, and each case's filing date remain
separate. It is not labeled as a historical docket. Judgment case identity is
also separate from each original or modification event.

Estate continuations bind the query, result schema, reported total, native
position, and source-published daily refresh marker. Resuming creates a fresh
session and replays current WebForms state before moving to the saved native
position. A personal-representative result row still displays the decedent;
the exact detail supplies the published representative observations.

Notice occurrence identity is the numeric notice ID published in the result
card. Because the rolling notice source does not publish a separate refresh
timestamp, continuation binds its effective search window, reported count,
schema, and observed notice IDs/dates. Claim occurrence identity is `src` plus
`RecordId`, independent of the estate number used to join the separately
attributable estate index. Claim continuation also binds the publisher's
current-data marker. Shared ingestion retains both components as source
snapshots so their native fields and identities remain available without
turning a notice or claim occurrence into a generic case row.

Appellate publication rows project onto court plus docket-file/term case
identity, while each reported or unreported disposition and PDF remains a
separate occurrence. The reported CGI supplies a complete selected filing-year
index and sequential source line markers. Unreported indexes are partitioned
by month; pre-May-2015 rows without archive links remain metadata-only rather
than being dropped or represented as missing cases. Shared case and document
lookups match the published case number exactly; free-text search uses the
published metadata fields without treating PDF paths as searchable case text.
Neither collection is labeled as a complete appellate docket.

Business and Technology rows project into normalized cases, one publication
event per case, judicial-officer observations, and separately identified
document artifacts. A publication that supplies multiple case numbers joins
to each one; when the source omits a case number, its publication designation
provides an explicit fallback identity instead of discarding the row. The
publication identity, case identity, and exact attachment URL remain separate.
Monitoring fingerprints stable routes, schemas, identity fields, and document
formats separately from rolling current-table counts and the sampled
publication artifact.

The Register of Wills office directory supplies controlling files, individual
instruments, certified copies, and older or differently indexed records.
Legal notices add publication and creditor-notice dates; the separate claim
search adds claimant and liability pivots. Circuit Court clerks, the AOC data
program, appellate opinions, Business and Technology publications, Case
Search, MDLandRec, Plats.net, SDAT property search, and local finance offices
remain explicit adjacent routes joined by the fields they actually publish.

## New Jersey Tax Court current reports and adjacent records

`query_new_jersey_tax_court.py` discovers the Judiciary's four current
local-property report artifacts through its anonymous S3 object manifest:
docketed and open reports in both XLSX and PDF. Search traverses the selected
XLSX reports completely unless the caller supplies a limit. The current
docketed report contains cases entered in the reporting year; the open report
contains cases currently reported open across filing years.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_new_jersey_tax_court.py manifest \
  --dataset both --format all \
  --output "$WORKDIR/nj-tax-court-artifacts.json"
uv run python tools/query_new_jersey_tax_court.py search "EXAMPLE LLC" \
  --field case-title --dataset both \
  --output "$WORKDIR/nj-tax-court-cases.json"
uv run python tools/query_new_jersey_tax_court.py search \
  --docket 003855-2026 \
  --output "$WORKDIR/nj-tax-court-docket.json"
uv run python tools/query_new_jersey_tax_court.py search \
  --county Bergen --block 100 --lot 2 --assessment-year 2026 \
  --output "$WORKDIR/nj-tax-court-parcel-candidates.json"
uv run python tools/query_new_jersey_tax_court.py validate --dataset both \
  --output "$WORKDIR/nj-tax-court-validation.json"
uv run python tools/query_new_jersey_tax_court.py alternatives \
  --output "$WORKDIR/nj-tax-court-alternatives.json"

uv run python tools/query_state_courts.py search "EXAMPLE LLC" \
  --source us-nj-tax-court-property-cases --jurisdiction 34 \
  --search-field case-title --ingest \
  --output "$WORKDIR/nj-tax-court-unified.json"
uv run python tools/query_state_courts.py case 003855-2026 \
  --source us-nj-tax-court-property-cases --ingest \
  --output "$WORKDIR/nj-tax-court-case.json"
uv run python tools/public_records_monitor.py run \
  us-nj-tax-court-property-cases \
  --output "$WORKDIR/nj-tax-court-monitor.json"
```

The docket number is the stable case identity. Every workbook row is retained
as a distinct source occurrence identified by artifact hash, worksheet, row
number, and row hash. This preserves exact duplicate rows and multiple
property rows for one docket instead of collapsing them during ingestion.
The observed live reports contained 11,294 docketed rows and 39,025 open rows,
including 1,057 exact duplicate occurrences; these counts are rolling source
observations rather than schema constants.

The current workbooks publish county, block, lot, unit, and assessment year,
but not municipality. Those fields are retained as parcel-join candidates;
the current report alone does not supply the municipality needed for a
deterministic NJGIN, MOD-IV, or SR1A join. The raw case title is retained as a
caption and search pivot without being converted into an ownership assertion.

Adjacent routes are cataloged by the information they add. S3 object versions
retain prior versions of the replaceable current keys but do not enumerate the
named monthly judgment archive. The Judiciary browser archive supplies annual
docket and monthly judgment lists; GovConnect notices add report publication
and correction dates; Case Jacket Public Access adds richer proceedings and
property detail; published and unpublished opinions add reasoning and
dispositions; appeal statistics, county tax boards, local assessors, NJGIN,
MOD-IV, and SR1A add aggregate, municipal, parcel, assessment, and transfer
context. Each route keeps its own provenance and record role.

## New Jersey Tax Court opinions

`query_new_jersey_tax_court_opinions.py` traverses the Judiciary's separate
published and unpublished Tax Court indexes, retains the official opinion PDF
URL, and can retrieve one selected document. Search uses the native date and
text filters and follows all 20-row pages by default; a caller-selected limit
returns a continuation bound to the selection, collection totals, first-page
anchors, and last returned page. Exact docket selection scans the selected
index collection and matches every normalized source-visible docket locally.
This includes consolidated secondary dockets that may appear in an index
summary without being returned by the site's native text filter.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_new_jersey_tax_court_opinions.py manifest \
  --output "$WORKDIR/nj-tax-opinion-manifest.json"
uv run python tools/query_new_jersey_tax_court_opinions.py search "Freehold" \
  --collection both --all-pages \
  --output "$WORKDIR/nj-tax-opinions.json"
uv run python tools/query_new_jersey_tax_court_opinions.py search \
  --docket 000052-2025 --collection published \
  --output "$WORKDIR/nj-tax-opinion-docket.json"
uv run python tools/query_new_jersey_tax_court_opinions.py document \
  https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf \
  --metadata-only --output "$WORKDIR/nj-tax-opinion-document.json"
uv run python tools/query_new_jersey_tax_court_opinions.py alternatives \
  --output "$WORKDIR/nj-tax-opinion-routes.json"
uv run python tools/query_new_jersey_tax_court_opinions.py probe \
  --output "$WORKDIR/nj-tax-opinion-probe.json"
uv run python tools/public_records_monitor.py run \
  us-nj-tax-court-opinions \
  --output "$WORKDIR/nj-tax-opinion-monitor.json"
```

The source has three independent identity layers. An index occurrence includes
its collection, source-visible title and docket label, posted date, document
URL, summary, and a duplicate ordinal. The document identity is the exact
official New Jersey Courts URL path. Each normalized docket number identifies
a case, so one document can have multiple index occurrences and can address
multiple cases.

New Jersey Courts remains the publisher in every result. In the July 30, 2026
probe, its edge challenged direct index and PDF requests from the tested
environment. The adapter therefore labels Jina Reader separately when it
renders an official index or extracts text from an official PDF URL. A Reader
extraction is not the original PDF bytes, its hash covers extracted text, and
it is another retrieval path to the same official record rather than
corroboration from a second publisher.

The same probe observed 104 published occurrences across six native pages and
374 unpublished occurrences across 19 pages. These are rolling collection
observations, not fixed coverage or schema values. The monitor fingerprints
the parser, identity, publisher, and transport-role contracts while retaining
current counts, operation states, selected document URL, and content hash in
the rolling observation.

Seven complementary routes remain explicit: New Jersey Courts full-site
search for official full-text and alias discovery; registered Tax Case Public
Access for case jackets and block/lot lookup; current and historical Tax Court
reports for docket, disposition, and property fields; Tax Court Reports and
State Library holdings for reported citations and archive context; state and
local assessment sources for municipality, value, parcel, and sale context;
Rutgers for a separately operated historical discovery copy; and CourtListener
for full-text and citation-graph discovery. Matching official, Rutgers, or
CourtListener copies of the same opinion improve availability without becoming
independent corroboration of that opinion's contents. Property, case-jacket,
and report records retain their own source identities because they add
different evidence.

## Michigan appellate cases, opinions, and orders

`query_michigan_appellate.py` uses the Michigan Judiciary's anonymous page
model and three separately paginated JSON result APIs. Case search retains the
appellate case number, caption, party summary, case status, lower-court labels,
attorneys, and P-numbers. Opinion and order search retains each publication's
case join, release date, decision/publication state, native document identity,
and official PDF URL.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_michigan_appellate.py search \
  --result-type cases --party-name "Example" --limit 100 \
  --output "$WORKDIR/mi-appellate-cases.json"
uv run python tools/query_michigan_appellate.py search insurance \
  --result-type opinions --limit 100 \
  --output "$WORKDIR/mi-appellate-opinions.json"
uv run python tools/query_michigan_appellate.py search \
  --result-type orders --case-id 166702 \
  --output "$WORKDIR/mi-appellate-orders.json"
uv run python tools/query_michigan_appellate.py routes \
  --output "$WORKDIR/mi-court-routes.json"

# Shared selection uses --case-type for the native result category.
uv run python tools/query_state_courts.py search "Example" \
  --source us-mi-appellate-case-opinion-order-search \
  --jurisdiction 26 --case-type opinions --search-field party --ingest \
  --output "$WORKDIR/mi-appellate-unified.json"
uv run python tools/query_state_courts.py case 360440 \
  --source us-mi-appellate-case-opinion-order-search \
  --output "$WORKDIR/mi-appellate-case.json"

uv run python tools/public_records_monitor.py run \
  us-mi-appellate-case-opinion-order-search \
  --output "$WORKDIR/mi-appellate-monitor.json"
```

The source's cross-category overview is a preview, so exhaustive work traverses
cases, opinions, and orders independently. The court code in the official case
route is preferred when source flags conflict. Normalized ingestion keeps case
identity separate from opinion/order event and PDF identity. MiCOURT trial-case
search, its developer API, Business Court rulings, and the trial-court
directory remain independently attributable alternatives joined by the
lower-court label, case number when available, party, attorney P-number, or
document ID.

## Michigan Business Court documents

`query_michigan_business_court.py` queries the Michigan Judiciary's anonymous
Business Court JSON endpoint and validates the linked official PDFs. The
source uses a fixed native page size of eight. Omitted limits traverse
`totalPages`; the observed `hasMoreResults` value is retained but does not
override the verified page/total continuation contract. Explicit limits return
an opaque cursor bound to the full query, sort, category, court, audience, and
native page-size selection.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_michigan_business_court.py categories \
  --output "$WORKDIR/mi-business-categories.json"
uv run python tools/query_michigan_business_court.py sources \
  --output "$WORKDIR/mi-business-courts.json"
uv run python tools/query_michigan_business_court.py search "real estate" \
  --business-court "Real Estate" --sort Newest \
  --output "$WORKDIR/mi-business-results.json"

uv run python tools/query_state_courts.py search "real estate" \
  --source us-mi-business-court-search --jurisdiction 26 \
  --case-type "Real Estate" --ingest \
  --output "$WORKDIR/mi-business-shared.json"
uv run python tools/query_state_courts.py download \
  "https://www.courts.michigan.gov/.../opinion.pdf" \
  --source us-mi-business-court-search \
  --destination "$WORKDIR/mi-business-opinion.pdf" \
  --output "$WORKDIR/mi-business-download.json"
uv run python tools/public_records_monitor.py run \
  us-mi-business-court-search \
  --output "$WORKDIR/mi-business-monitor.json"
```

Each normalized result keeps three identities separate: the official PDF, the
query/page/row occurrence, and every case-number candidate in the source's
case label. A compound label therefore remains multiple candidates rather than
becoming one synthesized case number. Legacy rows that omit the
pleading/order date, case name, and case number still ingest under their
document identity. The shared sidecar uses an abstract publication-collection
court for those candidates; a selected court facet or `cNN` filename prefix
remains locator context and is not stored as the trial-court assignment.
MiCOURT, the trial-court directory or clerk, and the appellate index remain
separately attributable sources for canonical court and case confirmation.

## Denver County Court daily docket

`query_denver_county_court.py` follows the official Denver County Court
courtroom/date form and parses its server-rendered daily docket table. Each row
is normalized as a court-scoped docket entry with case number, defendant,
status, language, case type, scheduled hearing, time, disposition, domestic
violence indicator, counsel, date of birth, charges/violations, courtroom, and
hearing date.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Direct daily-docket search; omit --limit to retain the full returned table.
uv run python tools/query_denver_county_court.py search \
  --courtroom 3A --date 2026-07-29 \
  --output "$WORKDIR/denver-county-docket.json"

# The unified calendar route uses the courtroom as its selector.
uv run python tools/query_state_courts.py calendar 3A \
  --source us-co-denver-county-court-public-docket \
  --jurisdiction 08031 --hearing-date 2026-07-29 --ingest \
  --output "$WORKDIR/denver-county-docket-unified.json"

uv run python tools/query_denver_county_court.py probe \
  --output "$WORKDIR/denver-county-docket-probe.json"
uv run python tools/public_records_monitor.py run \
  us-co-denver-county-court-public-docket \
  --output "$WORKDIR/denver-county-docket-monitor.json"
```

The verified form exposed 35 unique courtrooms and a 14-column result schema.
The portal returns the selected schedule in one response and configures its
table with client-side search/sorting and paging disabled. Direct `--limit`
and `--offset`, or the unified caller limit and continuation cursor, select a
window from that returned schedule; they are not source pagination.

The adapter retains the source's case-history link when present. Direct GETs
to two tested live case-history links returned HTTP 500, so the working
integration treats the daily schedule as the verified route and preserves the
link for later source review. The separate Colorado Judicial Branch docket
search adds broader trial-court coverage plus location, case, party, business,
attorney, and export filters.

## Colorado Judicial Branch statewide docket calendar

`query_colorado_judicial.py` implements the Judicial Branch's anonymous
statewide trial-court docket calendar. `courts` returns the live district,
county, courthouse, court-type, date-range, case-class, party-mode, and
attorney-mode option directory. `search` accepts those source selectors and
follows every native 20-row page unless the caller supplies `--limit`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect current source-native option values before constructing a query.
uv run python tools/query_colorado_judicial.py courts \
  --output "$WORKDIR/colorado-court-directory.json"

# Courthouse/date search. The continuation cursor resumes within a native page.
uv run python tools/query_colorado_judicial.py search \
  --courthouse 16_civil --date 2026-07-29 --limit 25 \
  --output "$WORKDIR/colorado-dockets.json"
uv run python tools/query_colorado_judicial.py search \
  --courthouse 16_civil --date 2026-07-29 \
  --cursor "$COLORADO_CURSOR" \
  --output "$WORKDIR/colorado-dockets-resumed.json"

# The form also exposes case-number, party/business, and attorney selectors.
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

# Source-generated export and contract probe.
uv run python tools/query_colorado_judicial.py export \
  --courthouse 16_civil --date 2026-07-29 \
  "$WORKDIR/colorado-dockets-export" \
  --output "$WORKDIR/colorado-dockets-export-receipt.json"
uv run python tools/query_colorado_judicial.py probe \
  --courthouse 16_civil --date 2026-07-29 \
  --output "$WORKDIR/colorado-docket-probe.json"
```

The verified directory contained 23 judicial districts, 66 county values, and
74 non-placeholder courthouse values. A live Denver civil query returned 56
rows with replayable anonymous GET result URLs and native 20-row pagination.
The result schema supplies date, time, duration, source Name, case number,
hearing type, location, appearance type, and courtroom. An intact zero-result
page is returned as `no_results`; a missing form, result contract, or required
row field is reported as source change rather than as an empty search.
Set `COLORADO_CURSOR` to the exact `next_cursor` returned by the preceding
query. The opaque
`colorado-judicial:v1:query:<sha256>:page:N:row:N` value is bound to the
source-native selectors, so changing a name, court, or date requires a fresh
search.
The unified `query_state_courts.py` name route maps matching `--after DATE`
and `--before DATE` values to this source's exact-date selector. Because the
form has relative windows rather than arbitrary start/end fields, unequal
bounds are reported as unsupported instead of silently becoming the default
one-week query.

Each source row becomes a `docket_entry` with a court-scoped case reference
and stable row identity. Rows for different calendar names on the same
case/date/time/hearing share a stable `hearing_id`, while the source Name is
retained as `calendar_name` without assigning a party role.

The verified result page advertises an export link, but availability varies by
query: the live 56-row Denver civil query returned HTTP 204 through both direct
and browser requests, while a later integrated probe produced an export
artifact for its current query. The `export` operation preserves those states
as either an artifact or `source_export_unavailable` instead of treating HTTP
204 as an empty docket search. The paginated `search` operation remains
independently available.

## Colorado appellate opinions and court-data complements

Two additional Colorado adapters cover adjudicative text, current opinion
releases, aggregate reports, dashboards, and the Judicial Branch's defined
compiled-data request path. They complement the trial-court calendar; none is
presented as the underlying trial docket or a general filing repository.

### Appellate archive and current releases

`query_colorado_opinions.py` coordinates two official source components while
retaining component-level provenance:

| Source ID | Source role | Records supplied |
|---|---|---|
| `us-co-appellate-case-law-search` | Colorado-branded historical case-law search hosted by vLex | Supreme Court and Court of Appeals opinion metadata, indexed full text, and rendered opinion PDFs |
| `us-co-judicial-appellate-opinion-releases` | Current Colorado Judicial Branch release surfaces | Supreme Court opinion releases and Court of Appeals announcement packets |

The Court of Appeals announcement packets are freshness/index artifacts, not
individual opinions. Current release records remain separate from historical
archive records even when both refer to the same case.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Search either historical appellate court by indexed text or docket text.
uv run python tools/query_colorado_opinions.py search "water rights" \
  --court supreme --limit 25 \
  --output "$WORKDIR/colorado-supreme-opinions.json"
uv run python tools/query_colorado_opinions.py docket 25CA0631 \
  --court appeals \
  --output "$WORKDIR/colorado-appeals-docket-opinions.json"

# Inspect current release surfaces without merging them into the archive.
uv run python tools/query_colorado_opinions.py releases \
  --court supreme --year 2026 \
  --output "$WORKDIR/colorado-supreme-releases.json"
uv run python tools/query_colorado_opinions.py releases \
  --court appeals --year 2026 --query "water" \
  --output "$WORKDIR/colorado-appeals-announcements.json"

# Retrieve archive metadata/full text, then download a verified PDF.
uv run python tools/query_colorado_opinions.py document 887202075 \
  --output "$WORKDIR/colorado-opinion-document.json"
uv run python tools/query_colorado_opinions.py download 887202075 \
  "$WORKDIR/colorado-opinion.pdf" \
  --output "$WORKDIR/colorado-opinion-download.json"

uv run python tools/query_colorado_opinions.py probe --component all \
  --output "$WORKDIR/colorado-opinions-probe.json"
```

Historical search uses native 20-row pages plus the source-reported result
count. Omitting `--limit` follows that count; a short intermediate page is not
treated as exhaustion. A caller limit returns a query-bound
`colorado-opinions:v2:query:<sha256>:page:N:row:N:seen:N:anchor:<document-id>`
continuation. The
adapter reports count drift, repeated document identities, an empty page before
the count is reached, or another failure to make progress instead of silently
declaring the traversal complete.

Release continuations use the separate query-bound
`colorado-opinion-releases:v2:query:<sha256>:offset:N:anchor:<sha256>` form.
Court of Appeals
release discovery follows the source's next-page links; the Supreme Court
release page is filtered locally by the requested year or text. Canonical
historical records use `COOPINION:`, current release records use
`COOPINION-RELEASE:`, and downloaded PDFs use
`COOPINION-ARTIFACT:` references.

`download` validates archive document IDs against opinion metadata and accepts
the Supreme Court release-node URL emitted by `releases`, resolving that node
to its opinion PDF. The historical service can regenerate the same PDF with a
different file hash; health monitoring records each observed hash but uses the
stable document identity, full-text hash, media type, and byte length for drift
comparison.

### Reports, dashboards, and compiled-data requests

`query_colorado_court_data.py` builds one live catalog from four distinct
Colorado Judicial components. `us-co-judicial-data-reports` identifies the
adapter/catalog family; each returned record uses the component that actually
published the assertion:

| Component source ID | Role |
|---|---|
| `us-co-judicial-annual-statistical-reports` | Current interactive statistical dashboards and archived fiscal-year annual-report PDFs |
| `us-co-judicial-case-parties-without-representation` | Fiscal-year PDFs on cases and parties without attorney representation; the source reports that Denver County Court is excluded |
| `us-co-judicial-eviction-filings-dashboard` | Public forcible-entry-and-detainer dashboard covering Colorado state courts and Denver County Court |
| `us-co-judicial-compiled-aggregate-data-requests` | CJD 05-01, Addendum A, and the structured compiled/aggregate-data request workflow |

```bash
# Inventory or filter the current official catalog.
uv run python tools/query_colorado_court_data.py catalog \
  --output "$WORKDIR/colorado-court-data-catalog.json"
uv run python tools/query_colorado_court_data.py list \
  --component-source us-co-judicial-annual-statistical-reports \
  --fiscal-year 2024 \
  --output "$WORKDIR/colorado-court-data-fy2024.json"
uv run python tools/query_colorado_court_data.py search eviction \
  --output "$WORKDIR/colorado-eviction-data-routes.json"

# Download an exact cataloged PDF artifact.
uv run python tools/query_colorado_court_data.py download \
  annual-statistical-report-fy-2024 \
  --destination "$WORKDIR/colorado-annual-statistics-fy2024.pdf" \
  --output "$WORKDIR/colorado-annual-statistics-download.json"

uv run python tools/query_colorado_court_data.py probe \
  --output "$WORKDIR/colorado-court-data-probe.json"
```

The 2026-07-29 live catalog contained 18 records: five current statistical
dashboards and four annual-report PDFs for FY 2021–2024; five
cases/parties-without-representation PDFs for FY 2021–2025; one eviction
dashboard; and three compiled-data program records. Power BI entries preserve
their official dashboard URL, but no machine-readable export contract was
verified. `download` therefore accepts exact cataloged PDF artifacts, while
the dashboards remain directly discoverable and usable through their public
interactive pages.

The compiled-data component records the current CJD 05-01 policy, its Addendum
A form, and the request workflow separately. Section 4.30 describes Department
policy not to release the entire case-management system or a substantial
subset as bulk data. Section 4.40 provides a request route for publicly
accessible compiled or aggregate data that is not already remotely available
or contained in an existing report. The same workflow records the monthly
civil-judgment report available from the State Court Administrator's Office
upon request and applicable fees, including case number, creditor and debtor
names and entered addresses, judgment date and amount, and an applicable
satisfaction date.

This is a useful substitution pattern for later source census work: when a
preferred bulk route is not directly distributed, keep the request program,
published reports, and public dashboards as separate sources and compare their
fields to the investigation's actual information need.

## Denver court document and administrative-order complements

The daily County Court table and statewide Judicial Branch docket search are
discovery sources. Three cataloged routes add documents or procedural context
without conflating them with hearing events:

| Source ID | Native route | Record identity and joins |
|---|---|---|
| `us-co-denver-county-court-records-request` | Denver County Court case-copy and certified-copy request route identified by the Judicial Branch public-access guide | Shares the County Court case identity; join on case number, party, and court date |
| `us-co-denver-district-court-records-request` | Clerk record/copy request plus separate FTR and court-reporter transcript forms | Shares the statewide docket case identity; join on case number, case type, filing year, party, hearing date, and requested record |
| `us-co-denver-district-administrative-orders` | Denver District Court's published administrative orders and electronic-filing mandates | Independent court-administration document keyed by order number and document URL |

The District Court form accepts case number, case type, filing year, party
names, and requested record. Published choices include disposition/sentence
orders and court minute orders. The court page separately supplies FTR and
court-reporter transcript channels, so a docket hit can be narrowed to the
specific hearing before a request is planned.

The County Court request route is the direct document complement when the
daily docket identifies a case but its retained case-history link does not
return detail. Both request manifests use the existing native case identity,
so later copies attach to the discovered case instead of creating a second
case.

Administrative orders remain independent because they describe court-wide
procedure rather than one litigated matter. The observed index includes sealed
record access, extreme-risk-protection-order administration, judicial
misconduct complaint procedure, electronic-record copy policy, and local
electronic-filing mandates.

## Virginia case-information, opinion, and land-record routes

Virginia General District Court Case Information now has a direct adapter,
shared `query_state_courts.py` routing, normalized ingestion, and a
stable-contract monitor. A live 2026-07-30 probe enumerated 134
source-published court components. Their three-digit values are application
component codes: retain `013` as `va-gdc-013`, for example, and do not treat it
as a geographic FIPS code.

The source has separate Civil (`V`) and Traffic/Criminal (`T`) divisions. Both
publish name, exact case-number, hearing-date, and service/process routes. Name,
hearing, and service results use native 20-row pages; the source reports no
total. Omitting a limit follows `Next` until it disappears, while a bounded
query returns a criteria-bound replay cursor. Exact case detail preserves
source section states (`published`, `published_empty`, or `not_present`),
including civil party, hearing, service, report, judgment, garnishment, and
appeal sections or traffic/criminal defendant, charge, hearing, service, and
disposition sections. A masked birth year remains a source value with its
publication state rather than being expanded.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Direct source adapter
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

# Shared discovery, case, and calendar routes
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

# Stable contract and rolling source observations
uv run python tools/public_records_monitor.py run \
  us-va-general-district-court-case-information \
  --output "$WORKDIR/va-gdc-monitor.json"
```

Shared `search --search-field` also accepts `case-number`,
`hearing-date`, and `service-process`. Search hits remain source occurrences;
exact case detail supplies the richer party and docket-event projection. The
case-information application does not publish a filing index or filing images,
so other official sources remain separately attributable complements:

| Source ID | Added records |
|---|---|
| `us-va-general-district-court-case-information` | Court-component civil, criminal, and traffic discovery plus case, judgment, service, garnishment, eviction, hearing, disposition, and appeal metadata |
| `us-va-ocis-statewide-search` | Statewide discovery across General District criminal/traffic matters and selected Circuit Court records |
| `us-va-general-district-court-directory` | Districts, court addresses, judges, clerk contacts, hours, local schedules, and local practices |
| `us-va-local-court-clerk-records` | Official or certified case records and copies through the responsible court's Clerk |
| `us-va-circuit-court-case-information` | Civil and criminal case metadata for participating circuit courts, searched by locality, name, case number, or hearing date; the displayed party list can truncate after three names |
| `us-va-appellate-opinions` | Direct Supreme Court and Court of Appeals opinion PDFs, including published and unpublished Court of Appeals decisions |
| `us-va-secure-remote-access-land-records` | Participating Circuit Court Clerk land-record systems for deeds, judgments, wills, marriage licenses, financing statements, and available document images |
| `us-va-virginia-date-of-birth-confirmation` | Registered organizational confirmation of a consenting person's identity against eligible criminal/traffic records |

The opinion archive currently reaches Supreme Court opinions from
1995-06-09, published Court of Appeals opinions from 1995-05-02, and
unpublished Court of Appeals opinions from 2002-03-05. Those PDFs add
adjudicative text and lower-court identifiers to the case-information
metadata. The Secure Remote Access directory routes to each participating
Clerk's registration, record groups, fees, coverage, and image availability.
Arlington's Clerk also advertises its own GovOS registered index from 1869 for
deeds, judgments, financing statements, and wills, with a free index and paid
images.

## Washington court directory, appellate opinions, and source alternatives

`query_washington_courts.py` keeps each official component separately
attributable. The two direct shared routes are the AOC court directory and
Washington appellate slip opinions. The directory exposes county and
organization pages, personnel last-name search, and a statewide PDF. Shared
directory search returns a source snapshot only; it does not create synthetic
cases from judges, clerks, or court contacts.

The opinion component combines court/status-specific RSS feeds with recent,
complete, and by-year lists, exact information sheets, and official PDFs. It
retains the source occurrence, court and every published docket number,
information-page identity, PDF path and hash, author, and concurrence
assignments. A consolidated opinion creates one case projection for each
source-published docket. These are slip opinions and may later be replaced by
the final version in the official reports.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect the component manifest and direct directory records.
uv run python tools/query_washington_courts.py manifest \
  --output "$WORKDIR/wa-court-manifest.json"
uv run python tools/query_washington_courts.py directory-search SMITH \
  --initial J --output "$WORKDIR/wa-directory-smith.json"
uv run python tools/query_washington_courts.py directory-org 190 \
  --output "$WORKDIR/wa-directory-org-190.json"
uv run python tools/query_washington_courts.py directory-pdf \
  "$WORKDIR/wa-court-directory.pdf" \
  --output "$WORKDIR/wa-court-directory-receipt.json"

# Search, resolve, and retrieve official appellate opinion publications.
uv run python tools/query_washington_courts.py opinions-feed div1-published \
  --output "$WORKDIR/wa-opinions-feed.json"
uv run python tools/query_washington_courts.py opinions-list \
  --scope year --year 2025 --query "water" \
  --output "$WORKDIR/wa-opinions-2025.json"
uv run python tools/query_washington_courts.py opinion-detail 883666MAJ \
  --output "$WORKDIR/wa-opinion-detail.json"
uv run python tools/query_washington_courts.py opinion-download 883666MAJ \
  "$WORKDIR/wa-opinion-883666.pdf" \
  --output "$WORKDIR/wa-opinion-download.json"

# Shared directory and opinion routes.
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

uv run python tools/public_records_monitor.py run \
  us-wa-aoc-court-directory \
  --output "$WORKDIR/wa-directory-monitor.json"
uv run python tools/public_records_monitor.py run \
  us-wa-appellate-opinions \
  --output "$WORKDIR/wa-opinions-monitor.json"
```

Other official components cover different field needs and retain their own
access and publication state:

| Source ID | Added information |
|---|---|
| `us-wa-aoc-case-discovery` | Statewide municipal, district, superior, and appellate discovery form and court codes; result execution is a CAPTCHA-backed human route |
| `us-wa-aoc-current-record-routes` | Current routing from court groups to Odyssey, local case-management systems, re:SearchWA, or appellate portals |
| `us-wa-appellate-case-documents` | Exact-case Supreme Court and Court of Appeals party filings and court-issued documents for cases filed from 2020; result execution is CAPTCHA-backed |
| `us-wa-appellate-route-complements` | Supreme Court orders, anticipated opinion filings, calendar and issue pages, plus Court of Appeals briefs |
| `us-wa-jis-link` | Registered subscription case and docket display for participating district, municipal, and superior systems; filed documents are not displayed |
| `us-wa-aoc-public-index-products` | Standard trial-court index products, a live omission list, custom-extract forms, policy, and fee schedule |
| `us-wa-aoc-caseload-products` | Aggregate monthly, year-to-date, annual, and dashboard activity products |
| `us-wa-digital-archives-superior-court-records` | Title-specific historical superior-court collections with search, preview, or fulfillment states |

The AOC components are published by the Washington State Administrative
Office of the Courts and retrieved directly from official court hosts. The
historical Digital Archives component is instead published by Washington
State Archives under the Secretary of State. Transport copies of one official
record are representations, not additional publishers or corroboration.

The tracked source census now associates the directory, appellate-opinion,
statewide trial/appellate discovery, Supreme Court calendar, and bulk-data
program roles with their actual scope and gaps. Trial rulings, complete
hearing-calendar coverage, filed-document coverage, and historical depth
remain separate coverage questions rather than implied by the statewide
labels.

## Florida ACIS appellate records

The official Florida Appellate Case Information System covers the Supreme
Court of Florida and all six District Courts of Appeal. Its public portal says
registration is unnecessary for public search and available public documents;
the adapter uses the same anonymous JSON backend as the portal. This is an
appellate source. Florida trial-court records remain primarily with county
clerks.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Enumerate the seven courts and their stable resource UUIDs
uv run python tools/query_florida_acis.py courts \
  --output "$WORKDIR/acis-courts.json"

# Search public party, case, document, and publication indexes
uv run python tools/query_florida_acis.py party-search "EXAMPLE LLC" \
  --output "$WORKDIR/acis-parties.json"
uv run python tools/query_florida_acis.py case-search "2024-0442" \
  --output "$WORKDIR/acis-cases.json"
uv run python tools/query_florida_acis.py document-search "motion" \
  --output "$WORKDIR/acis-documents.json"
uv run python tools/query_florida_acis.py publications "rules" \
  --output "$WORKDIR/acis-publications.json"

# Enumerate calendar-session types or search appellate events and case hearings
uv run python tools/query_florida_acis.py calendar-types \
  --output "$WORKDIR/acis-calendar-types.json"
uv run python tools/query_florida_acis.py calendar \
  --court "2nd District Court of Appeal" \
  --after 2026-08-19 --before 2026-08-19 \
  --session-type "Oral Argument" \
  --output "$WORKDIR/acis-calendar.json"

# The shared state-court route exposes the same ACIS calendar capability
uv run python tools/query_state_courts.py calendar "*" \
  --source us-fl-acis --court-id "2nd District Court of Appeal" \
  --hearing-date 2026-08-19 --case-type "Oral Argument" \
  --output "$WORKDIR/acis-calendar-shared.json"

# Resolve a case, docket, and the documents listed for it
uv run python tools/query_florida_acis.py case SC2024-0442 \
  --court 68f021c4-6a44-4735-9a76-5360b2e8af13 --documents \
  --output "$WORKDIR/acis-case.json"
uv run python tools/query_florida_acis.py docket SC2024-0442 \
  --court 68f021c4-6a44-4735-9a76-5360b2e8af13 \
  --output "$WORKDIR/acis-docket.json"

# Retrieve selected public artifacts using UUIDs returned by search/detail
uv run python tools/query_florida_acis.py download \
  "<COURT_RESOURCE_UUID>" "<CASE_INSTANCE_UUID>" "<DOCUMENT_LINK_UUID>" \
  "$WORKDIR/acis-document.pdf" \
  --output "$WORKDIR/acis-document.json"
uv run python tools/query_florida_acis.py publication \
  "<COURT_RESOURCE_UUID>" "<PUBLICATION_UUID>" \
  --output "$WORKDIR/acis-publication.json"

# Probe court identity, calendar taxonomy, one event, and its case hearings
uv run python tools/public_records_monitor.py run us-fl-acis \
  --output "$WORKDIR/acis-monitor.json"
```

ACIS records retain the source court UUID, case instance UUID, docket-entry
UUID, calendar-event UUID, hearing occurrence, document-link UUID, publication
UUID, and native case number. Calendar results preserve an event with no
attached case hearings as a complete zero-case event; the default calendar
query hydrates published hearings, while `--events-only` returns event rows
without those detail requests. Document availability and access state are
recorded per source response. The integration does not infer completeness for
records predating migration into ACIS. The monitor fingerprints the durable
directory/calendar contract separately from rolling schedule content.

## Florida court directory and aggregate-data family

`query_florida_court_directory_data.py` keeps four official publications
separately attributable:

| Source ID | Published layer | Shared semantics |
|---|---|---|
| `us-fl-state-court-location-directory` | Current county courthouse, Supreme Court, DCA, clerk, jury, address, and route directory | Searchable snapshot only |
| `us-fl-virtual-courtroom-directory` | Current virtual courtrooms, county participation, named judge/hearing officer when present, jurisdiction links, and live state | Searchable snapshot only; partial personnel roster |
| `us-fl-osca-public-records-request` | Contact and process for records held by OSCA | Searchable request-program snapshot; fulfillment is request-specific |
| `us-fl-trial-court-statistical-reference-guide` | Aggregate fiscal-year statistical publication catalog and official PDFs | Searchable catalog snapshot; exact PDF retrieval uses the direct adapter |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Component identities, relationships, and complementary routes
uv run python tools/query_florida_court_directory_data.py sources \
  --output "$WORKDIR/fl-court-data-sources.json"
uv run python tools/query_florida_court_directory_data.py manifest \
  --output "$WORKDIR/fl-court-data-manifest.json"

# Current directory and request-program snapshots
uv run python tools/query_florida_court_directory_data.py locations \
  --query Miami --output "$WORKDIR/fl-court-locations.json"
uv run python tools/query_florida_court_directory_data.py virtual \
  --judge George --output "$WORKDIR/fl-virtual-courtrooms.json"
uv run python tools/query_florida_court_directory_data.py data-request \
  --output "$WORKDIR/fl-osca-request.json"

# Aggregate publications and one exact, byte-verified official PDF
uv run python tools/query_florida_court_directory_data.py statistics \
  --fiscal-year 2024-25 --section Statistics \
  --output "$WORKDIR/fl-trial-statistics.json"
uv run python tools/query_florida_court_directory_data.py download \
  2472276 "$WORKDIR/fl-overall-statistics.pdf" \
  --output "$WORKDIR/fl-overall-statistics-download.json"

# Shared search is available for all four snapshots/catalogs
uv run python tools/query_state_courts.py search Miami \
  --source us-fl-state-court-location-directory \
  --output "$WORKDIR/fl-location-shared.json"
uv run python tools/query_state_courts.py search 2024-25 \
  --source us-fl-trial-court-statistical-reference-guide \
  --search-field fiscal-year \
  --output "$WORKDIR/fl-statistics-shared.json"

# Each source has an independent one-request monitor
uv run python tools/public_records_monitor.py run \
  us-fl-state-court-location-directory \
  us-fl-virtual-courtroom-directory \
  us-fl-osca-public-records-request \
  us-fl-trial-court-statistical-reference-guide \
  --output "$WORKDIR/fl-court-data-monitor.json"
```

The verified location snapshot published 66 county courthouse rows and omitted
Gadsden County. Ten rows also carried an embedded DCA-region value that
differed from their map category: Charlotte, Collier, Glades, Hardee, Hendry,
Highlands, Lee, and Polk were categorized under the Sixth DCA while retaining
an embedded Second DCA value; Orange and Osceola were categorized under the
Sixth while retaining an embedded Fifth DCA value. The adapter and monitor
retain both publisher fields and report the omission and mismatches as rolling
source observations. They do not synthesize Gadsden or treat the embedded
region as normalized geography.

The Virtual Courtroom Directory is useful for current proceeding routes and
partial personnel context, not a statewide judge roster or case calendar. The
OSCA page covers OSCA-held records; county court files remain with the
applicable court or clerk, for which the Florida Court Clerks public-records
directory is a complementary route. The Statistical Reference Guide provides
aggregate context rather than case rows. Its shared route lists catalog
occurrences; exact PDF selection and saving remain on the direct `download`
command.

## Ninth Judicial Circuit archived appellate opinions

The Ninth Judicial Circuit publishes a keyword-searchable archive of local
circuit-appellate, certiorari, and writ opinions for Orange and Osceola
Counties. Each index occurrence retains its source page and ordinal and links
to a directly validated official PDF. The native document ID is derived from
that official PDF URL; the source does not publish separate case number or
opinion-date fields in the index.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_florida_ninth_opinions.py manifest \
  --output "$WORKDIR/ninth-opinions-manifest.json"
uv run python tools/query_florida_ninth_opinions.py search \
  "Orange County" --limit 50 \
  --output "$WORKDIR/ninth-opinions.json"
uv run python tools/query_state_courts.py search "Orange County" \
  --source us-fl-ninth-circuit-appellate-opinions-archive \
  --output "$WORKDIR/ninth-opinions-shared.json"
uv run python tools/query_florida_ninth_opinions.py download \
  "https://ninthcircuit.org/sites/default/files/06-45.pdf" \
  "$WORKDIR/06-45.pdf" \
  --output "$WORKDIR/ninth-opinion-document.json"
uv run python tools/public_records_monitor.py run \
  us-fl-ninth-circuit-appellate-opinions-archive \
  --output "$WORKDIR/ninth-opinions-monitor.json"
```

This archive is a local appellate publication source. The cataloged Orange
Clerk route supplies an underlying trial-case and docket layer, and Ninth
Circuit division calendars add Orange and Osceola schedule context; the
official Osceola Clerk Benchmark and PERCH/JustFOIA routes are tracked as the
county-specific follow-up for underlying case files. Florida ACIS and the
statewide appellate-opinions search cover the Supreme Court and District
Courts of Appeal. Those complements remain independently attributable and can
be searched when the local archive does not contain the needed record.

## Osceola County Clerk Benchmark records

`query_osceola_courts.py` searches the Clerk's public Benchmark portal by
name, case number, citation number, or arresting-agency case number. Exact
cases expose the source-published summary, parties and attorneys, charges,
events, docket rows, and available document-page metadata. The adapter also
describes the Clerk's view-on-request, older-record, certified-copy, and bulk
routes.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_osceola_courts.py search \
  "2023 CF 001540" --search-mode case-number \
  --output "$WORKDIR/osceola-search.json"
uv run python tools/query_state_courts.py case "2023 CF 001540" \
  --source us-fl-osceola-benchmark-courts --ingest \
  --output "$WORKDIR/osceola-case.json"
uv run python tools/query_state_courts.py docket "2023 CF 001540" \
  --source us-fl-osceola-benchmark-courts \
  --output "$WORKDIR/osceola-docket.json"
uv run python tools/query_state_courts.py documents "2023 CF 001540" \
  --source us-fl-osceola-benchmark-courts \
  --docket-entry-uuid 56773534 \
  --output "$WORKDIR/osceola-documents.json"

uv run python tools/query_osceola_courts.py report calendar \
  --artifact-output "$WORKDIR/osceola-calendar.pdf" \
  --output "$WORKDIR/osceola-calendar.json"
uv run python tools/public_records_monitor.py run \
  us-fl-osceola-benchmark-courts \
  us-fl-osceola-court-hearing-calendar \
  us-fl-osceola-mortgage-foreclosure-schedule \
  --output "$WORKDIR/osceola-monitor.json"
```

The current hearing-calendar PDF and mortgage-foreclosure schedule are
cataloged as separate rolling snapshots. The calendar contributes partial
Florida hearing-calendar coverage; the foreclosure schedule is retained as
its own source and uses the Benchmark case record for cancellation context.

## Georgia AOC Court Personnel Directory

`query_georgia_court_directory.py` searches the Judicial Council of Georgia /
Administrative Office of the Courts' current statewide personnel directory.
Search rows retain the exact native record ID, person name fields, ordinary
city, county, and circuit. Optional detail hydration adds the published
address, phone, fax, conditional email state, and the source's separate Court
Class and Directory Section classifications.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Verified views, fields, classifications, source observations, and complements
uv run python tools/query_georgia_court_directory.py manifest \
  --output "$WORKDIR/ga-court-directory-manifest.json"

# Native filters and paging
uv run python tools/query_georgia_court_directory.py search \
  --directory-section "Superior Court Clerks" \
  --county Fulton --limit 100 \
  --output "$WORKDIR/ga-superior-clerks.json"
uv run python tools/query_georgia_court_directory.py search \
  --court-class Superior --details \
  --output "$WORKDIR/ga-superior-personnel-details.json"

# Resume with the cursor returned by the same filters and page size
uv run python tools/query_georgia_court_directory.py search \
  --directory-section "Superior Court Clerks" \
  --cursor "<NEXT_CURSOR>" --limit 100 \
  --output "$WORKDIR/ga-superior-clerks-next.json"

# Exact current detail by native record ID
uv run python tools/query_georgia_court_directory.py detail \
  "<NATIVE_RECORD_ID>" \
  --output "$WORKDIR/ga-court-personnel-detail.json"

# Shared search, exact detail, and source discovery
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

# Bounded search-plus-detail monitor
uv run python tools/public_records_monitor.py run \
  us-ga-aoc-court-personnel-directory \
  --output "$WORKDIR/ga-court-directory-monitor.json"
```

The records are current directory observations rather than case filings or a
historical personnel roster. The source field labeled Prefix sometimes
contains a job title, so the adapter emits `prefix_or_title`. The native City
filter also searches municipal-judge city fields, while compact search rows
show only the ordinary city; detail records retain those fields separately.
Email is emitted only when the source's display state permits it, while the
underlying source state remains in raw provenance.

For case records, use the AOC eAccess routes and the participating county or
provider systems they identify. AOC eFile maps courts to filing providers;
official local court and county sites add local rosters, calendars, contacts,
and record routes; GSCCCA supplies separately attributable clerk-administered
indices such as the statewide deed/lien/plat index. These are useful
complements, not alternate transports for the personnel directory.

## Georgia AOC eAccess and eFile provider directories

`query_georgia_court_access.py` keeps the AOC's two provider directories as
separate source snapshots. eAccess maps State and Superior Courts to
account-backed case-search routes. eFile records the published availability
state for Odyssey eFileGA, Peach Court, and GreenFiling/InfoTrack.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_georgia_court_access.py search Fulton \
  --source us-ga-aoc-eaccess-court-records-directory \
  --output "$WORKDIR/ga-eaccess-fulton.json"
uv run python tools/query_georgia_court_access.py search "*" \
  --source us-ga-aoc-efile-court-records-directory \
  --provider odyssey_efilega --published-state mandatory \
  --output "$WORKDIR/ga-efile-odyssey.json"
uv run python tools/query_georgia_court_access.py providers \
  --source us-ga-aoc-efile-court-records-directory \
  --output "$WORKDIR/ga-efile-provider-summary.json"

uv run python tools/query_state_courts.py search mandatory \
  --source us-ga-aoc-efile-court-records-directory \
  --search-field published-state \
  --output "$WORKDIR/ga-efile-shared.json"
uv run python tools/query_state_courts.py discovery \
  --source us-ga-aoc-eaccess-court-records-directory \
  --search-field providers \
  --output "$WORKDIR/ga-eaccess-providers-shared.json"
uv run python tools/public_records_monitor.py run \
  us-ga-aoc-eaccess-court-records-directory \
  us-ga-aoc-efile-court-records-directory \
  --output "$WORKDIR/ga-court-access-monitors.json"
```

The current snapshots each contain 230 court rows: 159 Superior Court and 71
State Court entries. eAccess publishes 193 direct-provider routes and 37
provider-selection routes. Two Chatham reSearchGA links use HTTP, and the
provider-selection page's heading says “e-Filing Vendor”; both observations
are retained as published.

For eFile, blank provider cells are represented as `not_listed`. The current
table lists Peach Court as Mandatory for 209 courts, Odyssey eFileGA for 59
Mandatory and 2 Available courts, and GreenFiling/InfoTrack as Available for
59 courts. These rows describe provider availability; they are retained as
source snapshots without creating case or filing records.

## Georgia aggregate caseload dashboards and workload assessments

`query_georgia_court_data.py` exposes two separately attributable aggregate
sources published by the Georgia AOC Office of Research and Data Analysis:
six court-class caseload dashboards and annual Superior Court workload
assessment PDFs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_georgia_court_data.py dashboards Superior \
  --output "$WORKDIR/ga-superior-dashboard.json"
uv run python tools/query_georgia_court_data.py handoff \
  --output "$WORKDIR/ga-dashboard-export-handoff.json"
uv run python tools/query_georgia_court_data.py workloads --year 2024 \
  --output "$WORKDIR/ga-workload-2024.json"
uv run python tools/query_georgia_court_data.py document 2024 \
  --artifact-output "$WORKDIR/ga-workload-2024.pdf" \
  --output "$WORKDIR/ga-workload-2024-document.json"

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
  --output "$WORKDIR/ga-workload-publications-shared.json"
uv run python tools/query_state_courts.py detail 2024 \
  --source us-ga-superior-court-workload-assessments \
  --search-field publication-year \
  --output "$WORKDIR/ga-workload-document-shared.json"
uv run python tools/public_records_monitor.py run \
  us-ga-aoc-caseload-dashboards \
  us-ga-superior-court-workload-assessments \
  --output "$WORKDIR/ga-court-data-monitors.json"
```

The dashboard catalog publishes Superior, State, Magistrate, Probate,
Juvenile, and Municipal Court views. AOC describes their values as
self-reported case counts and states that the Research Office does not collect
individual-case data. The export-request handoff currently offers all six
classes and years 2021–2025; its adapter record preserves the form fields and
`submission_performed=false`.

The verified workload archive contains seven annual publications for
2018–2024. The latest 2024 PDF was 1,032,026 bytes with SHA-256
`21afb894a332aa67bbef46cecfa50a8721fbfee95392d0a711d57a6de8c4c099`.
Publication metadata and validated PDFs share
`GA-AOC-SUPERIOR-WORKLOAD-ASSESSMENT:<YEAR>` identity and remain aggregate
source observations. The personnel directory adds current court contacts;
AOC eAccess and local court/provider routes supply separately attributable
case-level research paths.

## Supreme Court of Georgia recent public docket

`query_georgia_supreme_docket.py` searches the Court's anonymous public-docket
API for cases docketed in the last five years. It supports case number,
caption, party, attorney, lower-court case number plus county, and Court of
Appeals case number. Exact detail adds filing/order, judgment, calendar,
lower-court, and attorney metadata.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_georgia_supreme_docket.py search S26G \
  --field case-number --limit 100 \
  --output "$WORKDIR/ga-supreme-search.json"
uv run python tools/query_georgia_supreme_docket.py detail S26G0537 \
  --output "$WORKDIR/ga-supreme-detail.json"
uv run python tools/query_georgia_supreme_docket.py documents S26G0537 \
  --output "$WORKDIR/ga-supreme-document-handoff.json"
uv run python tools/query_georgia_supreme_docket.py counties \
  --output "$WORKDIR/ga-supreme-counties.json"

uv run python tools/query_state_courts.py search S26G0537 \
  --source us-ga-supreme-court-public-docket \
  --search-field case-number \
  --output "$WORKDIR/ga-supreme-shared-search.json"
uv run python tools/query_state_courts.py docket S26G0537 \
  --source us-ga-supreme-court-public-docket \
  --output "$WORKDIR/ga-supreme-shared-docket.json"
uv run python tools/query_state_courts.py discovery counties \
  --source us-ga-supreme-court-public-docket \
  --output "$WORKDIR/ga-supreme-counties-shared.json"
uv run python tools/public_records_monitor.py run \
  us-ga-supreme-court-public-docket \
  --output "$WORKDIR/ga-supreme-monitor.json"
```

The API returns each search as one complete JSON array; the adapter applies a
query- and snapshot-bound local cursor. Search and exact detail project to the
same appellate case identity. Detail filing/order rows use stable event
identities, attorneys stay explicit without inferred parties, and
county-qualified lower-court numbers become related trial-case pivots.

The API publishes filing metadata rather than document files. `documents`
returns those filing candidates and the Court's Clerk copy-request handoff,
with `request_submitted=false`; it creates no document rows. The source monitor
uses one exact search plus detail and fingerprints the stable API/schema
contract separately from the current case status and row counts.

The Court publishes useful adjacent layers under separate identities:

| Official route | Adds | Coverage difference |
|---|---|---|
| Annual opinions and noteworthy summaries (`us-ga-supreme-court-opinions`) | Opinion PDFs, decision and argument dates, selected summary packets | Decided opinion cases and selected noteworthy matters |
| Annual certiorari grants (`us-ga-supreme-court-certiorari-grants`) | Grant PDFs and Court of Appeals crosswalks | Grants only |
| Annual certiorari denials (`us-ga-supreme-court-certiorari-denials`) | Official denial lists | Denials only |
| Discretionary and interlocutory grant orders (`us-ga-supreme-court-application-grant-orders`) | Direct order PDFs typed by application route | Granted applications only |
| Oral argument calendar | Argument schedule and related-case groupings | Calendared cases only |
| Case announcements | Official announcement documents | Announcement subset |

The four decision-publication collections now have a dedicated adapter and
retain their own source identities. Oral calendars and case announcements
remain separate official complements. None changes the public docket's
five-year case-index scope.

## Supreme Court of Georgia decision publications

`query_georgia_supreme_publications.py` enumerates and normalizes four official
annual source families:

| Source ID | Verified coverage | Adds |
|---|---:|---|
| `us-ga-supreme-court-opinions` | 2017–2026 | Opinions, selected noteworthy-summary packets, decision/argument dates, multi-case captions, and raw revision notes |
| `us-ga-supreme-court-certiorari-grants` | 2022–2026 | Grant PDFs and attributed Court of Appeals case/PDF crosswalks |
| `us-ga-supreme-court-certiorari-denials` | 2022–2026 | Official HTML denial entries and the linked supplement when one is published |
| `us-ga-supreme-court-application-grant-orders` | 2022–2026 | Discretionary and interlocutory application-grant order PDFs |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_georgia_supreme_publications.py search "*" \
  --source us-ga-supreme-court-opinions --year 2026 \
  --output "$WORKDIR/ga-supreme-opinions.json"
uv run python tools/query_georgia_supreme_publications.py search "*" \
  --source us-ga-supreme-court-certiorari-grants \
  --case-number S26G0537 \
  --output "$WORKDIR/ga-supreme-cert-grant.json"
uv run python tools/query_georgia_supreme_publications.py search "*" \
  --source us-ga-supreme-court-application-grant-orders \
  --application-type interlocutory \
  --output "$WORKDIR/ga-supreme-interlocutory-grants.json"

uv run python tools/query_state_courts.py case S26G0537 \
  --source us-ga-supreme-court-certiorari-grants \
  --output "$WORKDIR/ga-supreme-publication-case.json"
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

The verified inventory contains 2,938 opinion/summary occurrences for
2017–2026; 133 grants and 140 Court of Appeals crosswalks for 2022–2026; 1,660
denials with 26 linked supplements for 2022–2026; and 54 application grants
(34 discretionary and 20 interlocutory) for 2022–2026. In the 2026 pages the
corresponding counts were 180 opinions plus 10 summaries, 21 grants plus 23
crosswalks, 259 denials plus two supplements, and five discretionary plus three
interlocutory grants.

All four source IDs expose shared `case`, `discovery`, `documents`, `download`,
`probe`, and `search`. Case-bearing publications become sparse Supreme Court
case shells with typed publication events and the linked official document.
HTML-only denial entries do not produce a document row. Joint opinions and
orders preserve all case numbers under one publication identity, while
existing richer case fields and the absence of published party data are
preserved.

Certiorari grant rows preserve the Supreme Court case-to-Court of Appeals case
crosswalk. A linked Court of Appeals PDF stays attributed to the originating
appellate court; its appearance on the Supreme Court grant page is not
independent corroboration of the grant. Matches among the four publication
families likewise remain separately attributable occurrences rather than
additional sources for the same fact.

The Court's opinion notice distinguishes three version states. Website and
docket copies may be modified after publication; a `Final Copy` in the advance
sheets replaces prior versions; bound Georgia Reports contain the final and
official text. The adapter retains the raw notice and revision notes. The
2017-starting opinion pages and 2022-starting order/list pages therefore supply
partial official decision-publication coverage, not a comprehensive historical
Georgia Supreme Court opinion archive. The recent public docket, oral argument
calendar, case announcements, and later official-report versions remain useful
complements with different record grains.

## Orange County trial, publication, and request routes

Orange County is represented by complementary routes rather than one source:

| Source | Native record layer | Record identity |
|---|---|---|
| `us-fl-orange-clerk-my-eclerk` | Approximate 1990-present case/docket discovery and generally 2009-present documents through the interactive case portal | Canonical Clerk case record |
| `us-fl-orange-county-hearing-calendar` | Current/future case number, hearing date/time, location, caption, judge, and status | Shares the Clerk case identity for case-linked events |
| `us-fl-ninth-circuit-division-calendars` | Orange and Osceola daily, weekly, monthly, all-hearing, and available-hearing division views | Independent division schedule or hearing-slot record |
| `us-fl-orange-clerk-records-request` | Online, mail, and in-person search/copy requests using case, party, date of birth, document, and year selectors | Shares the Clerk case-record identity |
| `us-fl-ninth-circuit-court-reporters` | In-house transcript and audio requests for the published non-civil proceeding families across the circuit | Independent transcript or proceeding-audio record |
| `us-fl-orange-court-registry-balance` | Exact-case registry balance current as of the last business day | Independent dated financial snapshot linked by case number |
| `us-fl-orange-confidentiality-notices` | Case-number links published after judicial confidentiality determinations for not less than 30 days | Independent Clerk notice linked by case number |
| `us-fl-ninth-circuit-administrative-orders` | Text, order-number, and category search over active administrative orders, with status and direct PDFs | Independent court-administration document |
| `us-fl-ninth-circuit-appellate-opinions-archive` | Keyword-searchable, paginated local appellate opinion archive with direct PDFs | Independent historic circuit-appellate opinion |

The principal statewide and federal publication complements are also cataloged
separately:

| Source | Native record layer | Relationship |
|---|---|---|
| `us-fl-appellate-opinions-search` | Opinion-text, style, number, court, and release-date search across the Florida Supreme Court and all six DCAs | Primary statewide appellate-opinion index |
| `us-fl-sixth-dca-opinion-releases` | Sixth DCA recent-written, recent-PCA, and release-date archive views | A focused monitoring view over the same Sixth DCA opinion identity used by the statewide search |
| `us-fl-acis` | State appellate cases, parties, dockets, available filings, publications, and lower-tribunal pivots | Independent case/docket identity connected to opinions by court and appellate case number |
| `us-flmd-recent-opinions` | Middle District of Florida opinions from the previous 30 days, filterable by judge and division, with direct PDFs | Independent federal district opinion; Orange is in the Orlando Division |
| `us-ca11-published-opinions` and `us-ca11-unpublished-opinions` | Official Eleventh Circuit archives with appellate number, originating district docket, date, author, and direct PDF | Separate published and unpublished appellate-opinion identities |

The hearing adapter uses the official calendar's same-session anti-forgery
token and cookie. The returned HTML contains the complete result table;
DataTables pagination is client-side. A live probe parsed all 1,285 rows
reported for its selected day, so the adapter exposes caller-selected
`--limit` and `--offset` without inventing a source ceiling.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_orange_county_courts.py search \
  --case-number 2020-CT-001540-A-O \
  --output "$WORKDIR/orange-hearings.json"
uv run python tools/query_orange_county_courts.py search \
  --date 2026-07-29 --limit 100 \
  --output "$WORKDIR/orange-daily-hearings.json"
uv run python tools/query_orange_county_courts.py search \
  --first-name "EXAMPLE" --last-name "PERSON" \
  --output "$WORKDIR/orange-name-hearings.json"
uv run python tools/public_records_monitor.py run \
  us-fl-orange-county-hearing-calendar \
  --output "$WORKDIR/orange-calendar-monitor.json"

uv run python tools/public_records_actions.py plan \
  us-fl-orange-clerk-my-eclerk \
  --operation search_cases --selector "EXAMPLE PERSON" \
  --output "$WORKDIR/orange-case-search-action.json"
```

The cross-domain planner carries these catalog relationships into
`complementary_routes`. Clerk copy requests are marked `shared` with the
my eClerk case identity, and the Sixth DCA release archive is marked `shared`
with the statewide opinion identity. Division schedules, registry balances,
confidentiality notices, administrative orders, transcripts, recorded
instruments, district opinions, and Eleventh Circuit opinions are marked
`independent` while retaining their case, party, date, parcel, instrument, or
originating-docket pivots.

## Los Angeles Superior Court civil cases and tentative rulings

`query_los_angeles_court.py` combines two anonymous civil representations
without confusing their record grains. Exact-number Case Summary returns case
metadata, future hearings, parties, the filed-document index, past
proceedings, and register actions. Tentative Rulings exposes a changing
inventory of exact location/department/date selectors and full text for every
case occurrence in a selected publication.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_los_angeles_court.py case 24NNCV00427 \
  --output "$WORKDIR/la-civil-case.json"
uv run python tools/query_los_angeles_court.py selections \
  --output "$WORKDIR/la-ruling-selections.json"
uv run python tools/query_los_angeles_court.py rulings \
  "ALH,3,07/30/2026" --output "$WORKDIR/la-rulings.json"
uv run python tools/query_los_angeles_court.py rulings all \
  --output "$WORKDIR/la-all-current-rulings.json"
uv run python tools/query_los_angeles_court.py probe \
  --output "$WORKDIR/la-civil-probe.json"

# Shared exact-case views all use the complete Case Summary representation.
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

uv run python tools/public_records_monitor.py run \
  us-ca-los-angeles-superior-civil \
  --output "$WORKDIR/la-civil-monitor.json"
```

Case Summary is uncapped unless the caller selects a docket-entry limit; it
retains the court's statement that the page is not the official record.
Current ruling traversal is also exhaustive by default. The verified
inventory contained 84 exact selections; each traversal refreshes WebForms
state and returns a continuation cursor only when the caller chooses a
selection bound.

Alternative discovery and acquisition paths are first-class catalog sources:

- `us-ca-los-angeles-superior-civil-name-index` provides paid party-to-case
  discovery through a free contract probe, court-cart preparation, guest
  receipt recovery, and saved-result parsing.
- `us-ca-los-angeles-superior-civil-document-images` supplies the image
  delivery complement to the free filed-document metadata.
- The Archives and Records Center covers older or offline indexes/files;
  the divorce-judgment service supplies available certified judgment images.
- Trellis supplies adjacent party, attorney, judge, docket, document, and
  tentative-ruling discovery that can be checked against the court routes.
- Separate family-law, small-claims, and probate Case Summary sources preserve
  their own case families.
- The Superior Court Appellate Division tentative-ruling source, Second
  District case information, Judicial Branch opinions, and public notices
  extend ruling, appellate, and notice coverage without being represented as
  civil docket substitutes.

## Los Angeles Superior Court paid party-name index

`query_los_angeles_name_index.py` probes the official coverage, fee, search
form, and guest-receipt contracts without purchasing a search. `prepare`
submits a person or company query in one court session and returns the court
cart. `receipt --retrieve` reconnects a completed guest purchase using its
receipt number and the card's last four digits. `parse-results` processes a
saved purchased page.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

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

Each result occurrence retains the matched name, case type, filing date and
location, image count, and a duplicate ordinal. The ingester maps its case
number to the corresponding civil, family-law, small-claims, or probate Case
Summary identity and stores the name-index hit in `case_source_occurrence`.
This lets a later exact-case fetch enrich the same case without replacing
the purchased match evidence.

## Los Angeles Superior Court probate

`query_los_angeles_probate.py` uses three verified anonymous court routes. The
`case` command follows the Case Summary service's same-session tokenized form
and returns case metadata, parties, future hearings, filed-document index rows,
past proceedings, and register actions. `notes` follows the separate Probate
Notes form and its future/past view switch. `calendar` queries the direct
known-case calendar page.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_los_angeles_probate.py case 17STPB02676 \
  --output "$WORKDIR/la-probate-case.json"
uv run python tools/query_los_angeles_probate.py notes 26STPB00601 \
  --view all --output "$WORKDIR/la-probate-notes.json"
uv run python tools/query_los_angeles_probate.py calendar 26STPB00601 \
  --output "$WORKDIR/la-probate-calendar.json"
uv run python tools/query_los_angeles_probate.py probe \
  --output "$WORKDIR/la-probate-probe.json"

# The unified router exposes the same anonymous case-scoped routes.
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

Each command returns every source row by default. Optional `--limit` and
`--offset` apply to the command's repeated docket, note, or hearing items.
Because Case Summary exposes no native filing/register row IDs, the adapter
uses deterministic case-scoped hashes of displayed fields plus a duplicate
occurrence ordinal. It retains the court's statement that Case Summary is not
the official record. The unified router leaves repeated rows uncapped unless
the caller selects `--limit` or `--max-records`; its continuation cursor is
`la-probate:offset:N`.

The surrounding discovery and document routes stay distinct:

- The paid probate name index covers 1983-present and returns case number,
  case type, filing date/location, litigant, and available-image count.
- The guest/account document service exposes document IDs, titles, filing
  dates, and page counts before paid email delivery; probate previews are not
  available there.
- Clerk and Archives routes handle older name discovery, missing images,
  courthouse review, copies, and certification.
- Second District Appellate Case Information supplies trial-case
  cross-references, parties/counsel, briefing, actions, dispositions, and oral
  argument. Judicial Branch opinion indexes remain a separate publication
  source.
- Assessor AIN/APN records, Registrar-Recorder grantor/grantee/year indexes,
  and California Public Notices provide property, instrument, alias, and
  hearing pivots without being represented as probate docket substitutes.

Plan paid, archival, and recorder work through `public_records_actions.py`.
The cross-domain planner links the separate probate sources through their
shared case-record identity:

```bash
uv run python tools/public_records_actions.py plan \
  us-ca-los-angeles-superior-probate-name-index \
  --operation search_cases --selector "EXAMPLE PERSON" \
  --action-type paid_lookup \
  --output "$WORKDIR/la-probate-name-action.json"

uv run python tools/public_records_search_plan.py "EXAMPLE PERSON" \
  --address "100 MAIN ST, LOS ANGELES, CA" --jurisdiction 06037 \
  --output "$WORKDIR/la-property-probate-plan.json"
```

## California Judicial Branch current appellate opinions

`query_california_opinions.py` covers the two current Judicial Branch
publication feeds: published/citable as-filed slip opinions retained for 120
days and unpublished/non-citable opinions retained for 60 days. Searches use
the native court, case-number, title, page-size, and zero-based page fields.
Exact detail pages expose the source-listed PDF and DOCX formats.

The publication identifier and appellate case identity remain separate. For
example, modified opinion `B350634M` crosswalks to base case `B350634`; both
values remain available for document and case joins. Shared `search`, `case`,
and `documents` operations can project a sparse appellate case, one opinion
publication event, and the currently listed official documents. Discovery and
probe records remain source snapshots.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_california_opinions.py search \
  --collection both --case-number S287786 \
  --output "$WORKDIR/ca-opinions.json"
uv run python tools/query_california_opinions.py detail \
  https://courts.ca.gov/opinion/published/2026-07-30/s287786 \
  --output "$WORKDIR/ca-opinion-detail.json"
uv run python tools/query_state_courts.py documents S287786 \
  --source us-ca-judicial-branch-opinions --document-type published \
  --output "$WORKDIR/ca-opinion-documents.json"
uv run python tools/public_records_monitor.py run \
  us-ca-judicial-branch-opinions \
  --output "$WORKDIR/ca-opinions-monitor.json"
```

The opinion `citings` archive stores the original web address alongside the
court-hosted archived copy of material cited by the opinion. Those two
representations are one source, not independent corroboration. Appellate Case
Information supplies older opinion and case chronology lookups. The official
no-fee Official Reports service supplies corrected citable text and historical
published opinions from 1850 onward; that later text is complementary to, not
already included in, the current-feed adapter.

## California statewide directory, Santa Clara, and San Diego

`query_california_court_directory.py` preserves the Judicial Branch’s complete
58-county directory as a discovery snapshot. Shared search can filter county,
GEOID, appellate district, court, or a published service route; ingestion does
not create case rows.

Santa Clara remains four distinct components: current department-level
tentative-ruling PDFs, requested civil and criminal tab-delimited index
products, and the public case/calendar portal. The open ruling publication has
shared directory, document, and download routes and snapshot-only ingestion.
The product descriptions retain their request forms, fields, delivery, and
cost basis; the observed portal forms retain their reCAPTCHA state.

San Diego’s shared routes cover party/business search for one native case type
and exact case-number search. The direct adapter also exposes case-detail pages
and exhausts the separate static new-filing partitions. Those lists retain
five court days, and neither representation is treated as a docket or
case-file document source. The adapter keeps the court’s DA-number search,
registers of actions, pre-1974 indexes, clerk copy/inspection routes, omitted
traffic/minor-offense files, and Fourth District appellate search available as
separate alternatives.

```bash
uv run python tools/query_state_courts.py search "San Diego" \
  --source us-ca-superior-court-directory
uv run python tools/query_state_courts.py documents 1 \
  --source us-ca-santa-clara-tentative-rulings
uv run python tools/query_state_courts.py search "Example" \
  --source us-ca-san-diego-superior-court-index --case-type civil
uv run python tools/query_san_diego_court_index.py new-filings --case-type all
```

## Fresno Superior Court publication and acquisition sources

`query_fresno_superior_court.py` keeps seven official sources distinct instead
of treating the current e-Court landing as the county's entire record system.
The anonymous case-bearing sources are daily calendar PDFs, civil tentative
ruling PDFs, and the Probate Examiner Notes application. The same adapter also
describes the monthly case-index product and the court's archive, copy,
case-contact, administrative-record, elevated-access, and Fifth District
appellate routes.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Enumerate and parse every row in one current daily calendar.
uv run python tools/query_fresno_superior_court.py calendar-index \
  --output "$WORKDIR/fresno-calendar-index.json"
uv run python tools/query_fresno_superior_court.py calendar \
  --date 2026-07-30 --output "$WORKDIR/fresno-calendar.json"

# Enumerate and parse a department's current tentative rulings.
uv run python tools/query_fresno_superior_court.py rulings-index \
  --output "$WORKDIR/fresno-rulings-index.json"
uv run python tools/query_fresno_superior_court.py rulings \
  --department 501 --date 2026-07-30 \
  --output "$WORKDIR/fresno-rulings.json"

# Exact-case probate notes and the non-anonymous acquisition alternatives.
uv run python tools/query_fresno_superior_court.py probate-notes \
  --case-number 19CEPR00967 \
  --output "$WORKDIR/fresno-probate-notes.json"
uv run python tools/query_fresno_superior_court.py alternatives \
  --output "$WORKDIR/fresno-alternatives.json"
uv run python tools/query_fresno_superior_court.py probe \
  --output "$WORKDIR/fresno-family-probe.json"

# Shared calendar and note routes use the same source-specific selectors.
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

A live daily-calendar check parsed all 1,056 published hearing rows. The
tentative-ruling index exposed 20 official PDFs across departments 403, 501,
502, and 503, and the probate sentinel returned 52 notes. Calendar rows become
case-linked hearing occurrences in the normalized sidecar. Rulings retain
their tentative, continuance, or must-appear state and link back to the exact
PDF. Examiner notes retain the court's statement that they are not part of the
official case file.

The e-Court landing currently exposes home, FAQ, registration, and login
operations but no anonymous case-search form. That observation does not hide
the useful alternatives: monthly criminal/traffic, civil/small-claims, family,
and probate index reports are orderable as PDF or text; Archives publishes
view, copy, and certification services for holdings observed back to 1860;
and separate civil, criminal/traffic, administrative, and appellate routes
provide additional case and document pivots.

Each anonymously observable component has its own monitor:

```bash
uv run python tools/public_records_monitor.py run \
  us-ca-fresno-superior-court-public-records \
  us-ca-fresno-superior-court-ecourt-portal \
  us-ca-fresno-superior-court-daily-calendar \
  us-ca-fresno-superior-court-tentative-rulings \
  us-ca-fresno-superior-court-probate-examiner-notes \
  --output "$WORKDIR/fresno-monitors.json"
```

## Orange County Superior Court calendars, rulings, and substitutes

`query_orange_county_court.py` implements the anonymous Cases on Calendar
form and the separate current civil, family-law, and probate tentative-ruling
directories. It keeps the 50-row calendar transport page, the court-stated
six-week future window, an optional caller limit, and the bounded monitor
probe as different concepts. With no caller limit, all native result pages
are traversed.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Six native categories are available: civil, criminal, family, probate,
# small-claims, and traffic.
uv run python tools/query_orange_county_court.py calendar civil \
  --title "Kiani" --output "$WORKDIR/orange-calendar.json"

# Enumerate a current directory and preserve one exact ruling PDF plus text.
uv run python tools/query_orange_county_court.py ruling-index \
  --division civil --output "$WORKDIR/orange-civil-ruling-index.json"
uv run python tools/query_orange_county_court.py ruling civil C44 \
  --download "$WORKDIR/orange-c44.pdf" \
  --output "$WORKDIR/orange-c44.json"

# Shared routing and normalized hearing/ruling ingestion.
uv run python tools/query_state_courts.py search "Kiani" \
  --source us-ca-orange-superior-court-calendar --case-type civil --ingest \
  --output "$WORKDIR/orange-calendar-unified.json"
uv run python tools/query_state_courts.py calendar all \
  --source us-ca-orange-superior-court-civil-tentative-rulings \
  --output "$WORKDIR/orange-ruling-index-unified.json"
uv run python tools/query_state_courts.py documents C44 \
  --source us-ca-orange-superior-court-civil-tentative-rulings --ingest \
  --output "$WORKDIR/orange-c44-unified.json"
```

A live calendar date returned 388 civil hearings across eight native pages.
The current ruling directories exposed 33 civil PDFs, no current family-law
artifact links, and six probate PDFs. The zero-result family directory is
retained as its present source state. Ruling documents retain their tentative
status, exact PDF identity, full text, department, judicial officer, hearing
fields, and case-number candidates; case-bearing documents can project to the
normalized sidecar without turning the tentative publication into a final
order.

When those anonymous publications do not answer the question, use the
separately cataloged official substitutes: the free-account name search,
case-type detail and document portals, permanent filing index, $50 monthly or
legacy plain-text index products, probate notes, and clerk copy,
certification, older-record, and retained-file routes. Their source identities
stay distinct so an account, product order, or record request can be planned
without implying that the calendar or ruling directory has complete case
coverage.

```bash
uv run python tools/public_records_monitor.py run \
  us-ca-orange-superior-court-public-records \
  us-ca-orange-superior-court-calendar \
  us-ca-orange-superior-court-civil-tentative-rulings \
  us-ca-orange-superior-court-family-tentative-rulings \
  us-ca-orange-superior-court-probate-tentative-rulings \
  --output "$WORKDIR/orange-monitors.json"
```

## Riverside Superior Court calendars, rulings, and substitutes

`query_riverside_court.py` keeps Riverside's eCourtCalendars JSON and
department tentative-ruling PDFs as separate source components. Both official
hosts currently return 403 to direct HTTP clients, while the anonymous pages
work in an ordinary headed Chrome session. The adapter uses that public browser
flow and preserves the exact page, JSON, and PDF provenance.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Omit --limit to return every row in the selected four-business-day window.
uv run python tools/query_riverside_court.py calendar \
  --courthouse "Historic Court House" --department 8 \
  --area-of-law probate \
  --output "$WORKDIR/riverside-calendar.json"

# List every PDF linked by the current directory, then acquire one department.
uv run python tools/query_riverside_court.py ruling-index \
  --output "$WORKDIR/riverside-ruling-index.json"
uv run python tools/query_riverside_court.py ruling PS1 \
  --download "$WORKDIR/riverside-ps1.pdf" \
  --output "$WORKDIR/riverside-ps1.json"

# Shared routing can normalize case-bearing hearings and ruling documents.
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
```

The verified eCalendar exposed nine courthouses, 64 departments, 93
department/area combinations, and Civil, Criminal, Probate, and Traffic
calendars. Department 8 Probate returned 58 hearing rows for 53 cases across
four business days. Its visible 12-row paging is a client-side grid control;
the JSON response is the complete selected source window.

The ruling directory exposed 17 department PDFs. Paths on the same current
directory used different publication months, so directory membership,
artifact path dates, and extracted hearing dates remain separate observations.
A verified nine-page PS1 PDF contained seven matters. Only PDFs with extracted
case numbers project to cases and tentative-ruling docket entries; directory
rows and no-ruling artifacts remain source snapshots.

Ten official complements remain independently selectable: registered Public
Access for case-number records, registers, calendars, name discovery, and
eligible documents; its coverage and fee guide; monthly or quarterly Civil,
Family Law, and Probate name-index products; clerk-performed searches; record
copy and certification forms; Probate Notes; high-interest case documents;
transcript requests; the trial-court Appellate Division; and Fourth District
Division Two appellate case information. These routes add case history,
documents, older or hard-to-find cases, hearing text, and appellate context
without being treated as duplicate calendar or ruling records.

```bash
uv run python tools/public_records_monitor.py run \
  us-ca-riverside-superior-court-ecalendar \
  us-ca-riverside-superior-court-tentative-rulings \
  --output "$WORKDIR/riverside-monitors.json"
```

## Queensland eCourts civil files and complementary routes

`query_qld_ecourts.py` searches the official anonymous eCourts service for
Supreme and District Court civil files. Search hits include registry-qualified
case identity and party rows. Exact detail adds ACNs, representatives, events,
related-file rows, and the filing-document index.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Party/company discovery. With no --limit, traverse all native pages.
uv run python tools/query_qld_ecourts.py search \
  --party-name COSCOLLUELA \
  --output "$WORKDIR/qld-party-search.json"

# Resolve the complete source-native identity and fetch detail.
uv run python tools/query_qld_ecourts.py case 6819/11 \
  --court SUPRE --location BRISB \
  --output "$WORKDIR/qld-case.json"

# Shared routing and normalized sidecar projection.
uv run python tools/query_state_courts.py search COSCOLLUELA \
  --source au-qld-ecourts-civil --jurisdiction AU-QLD \
  --court-id qld-supreme-court --courthouse BRISB \
  --output "$WORKDIR/qld-unified-search.json"
uv run python tools/query_state_courts.py case 6819/11 \
  --source au-qld-ecourts-civil --jurisdiction AU-QLD \
  --court-id qld-supreme-court --courthouse BRISB --ingest \
  --output "$WORKDIR/qld-unified-case.json"

uv run python tools/query_qld_ecourts.py sources \
  --output "$WORKDIR/qld-source-routes.json"
uv run python tools/public_records_monitor.py run \
  au-qld-ecourts-civil \
  --output "$WORKDIR/qld-ecourts-monitor.json"
```

The source uses 20-row WebForms pages and reports at most 500 matches in one
search. The adapter partitions a capped query by court, originating registry,
proceeding category, and party role. If a fully partitioned query still hits
the ceiling, the result is `partial` with the unresolved partition instead of
being presented as complete.

Case identity is `court code + originating registry code + file number`;
`6819/11` by itself is not sufficient because the same number can occur in
another registry. The normalized court record retains
`SUPRE-BRISB-6819-2011` as its source-internal identity.

eCourts publishes document-list metadata but not the filing images. The
separate Queensland Courts search-and-copy workflow is cataloged for those
documents. Criminal Case Lookup, Daily Law Lists, Supreme Court Library
Queensland CaseLaw, Queensland Judgments, and Queensland State Archives are
also separate sources for criminal events, current schedules, judgment text,
and older holdings.

## San Mateo Superior Court MIDX and complementary routes

`query_san_mateo_midx.py` follows the court's anonymous MIDX forms in a
short-lived Chromium session. MIDX is a case and party index for appeals,
civil, criminal, family law, probate, and small claims. It returns case number,
party name, the source's native `Type` code, filing date, and the available
index-information link; it does not supply a caption, case type, status,
register of actions, or filing images.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Exact case-number index lookup
uv run python tools/query_san_mateo_midx.py case PRO116668-B \
  --output "$WORKDIR/san-mateo-case-index.json"

# Person and business discovery
uv run python tools/query_san_mateo_midx.py search \
  --first-name "FRANK" --last-name "CREER" \
  --output "$WORKDIR/san-mateo-person-index.json"
uv run python tools/query_san_mateo_midx.py search \
  --business-name "EXAMPLE HOLDINGS*" \
  --output "$WORKDIR/san-mateo-business-index.json"

# The source accepts at most five inclusive calendar days per date query
uv run python tools/query_san_mateo_midx.py search \
  --filed-from 2026-07-20 --filed-to 2026-07-24 \
  --output "$WORKDIR/san-mateo-filed-index.json"

uv run python tools/query_san_mateo_midx.py probe \
  --output "$WORKDIR/san-mateo-midx-probe.json"
```

MIDX paginates with opaque same-origin `lookup.php?data=...` URLs. The adapter
follows every page and returns all native index rows by default. `--limit`
and `--offset` are optional caller controls. No source total-result ceiling was
observed: a verified five-day query exposed 1,290 rows over 86 pages, with 15
rows on each full page. Confidential cases are absent from the index, and the
court directs pre-1993 criminal research to the clerk.

Use the surrounding routes for the fields MIDX does not publish:

- Odyssey supplies additional case metadata, register-of-actions rows, and
  available public documents through its interactive Smart Search.
- Daily branch hearing PDFs and short-retention tentative rulings contribute
  hearing, department, motion, outcome, and ruling text.
- Records Management provides file viewing, copies, and certification.
- First District appellate case information, Judicial Branch opinions, and
  oral-argument calendars provide appeal and published-decision pivots.
- Recorder grantor/grantee records, assessor maps and tax lookup, and
  California Public Notices provide instrument, parcel, alias, case-number,
  and hearing pivots.

An MIDX row is official index evidence that the court displayed a named party
for a case and filing date. Odyssey docket rows, ruling text, clerk copies,
appellate opinions, recorded instruments, assessment records, and notices
remain distinct evidence objects.

## Pima County Superior Court Agave records

`query_pima_courts.py` queries the official Agave PublicDocs application linked
by the Pima County Clerk of the Superior Court. It resolves every frame,
result, case, and PDF token inside a fresh session; emitted records retain the
normalized case number and displayed source fields, not ephemeral URLs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_pima_courts.py search "MALLETT" --limit 25 \
  --output "$WORKDIR/pima-name-search.json"
uv run python tools/query_pima_courts.py case C20256501 \
  --output "$WORKDIR/pima-case.json"
uv run python tools/query_pima_courts.py document C20256501 \
  "<PIMA_DOCKET_ENTRY_ID>" "$WORKDIR/pima-filing.pdf" \
  --output "$WORKDIR/pima-document.json"
uv run python tools/query_state_courts.py search "MALLETT" \
  --source us-az-pima-superior-agave --ingest \
  --output "$WORKDIR/pima-unified-search.json"
uv run python tools/public_records_monitor.py run \
  us-az-pima-superior-agave \
  --output "$WORKDIR/pima-monitor.json"
```

Case detail includes parties, a document/docket grid, available public PDFs,
and criminal charges/dispositions when present. Agave exposes no durable row
ID, so docket identities are deterministic case-scoped hashes of displayed
fields plus duplicate occurrence. Exact-number resolution is incomplete for
at least one verified criminal case; the direct `case` and `document` commands
accept `--last-name` and optional `--first-name` to resolve that case through
the party index.

Complementary Pima routes fill different gaps:

- Arizona eAccess adds statewide Superior Court discovery, richer event and
  hearing fields, purchasable documents, and electronic certification for its
  published coverage period.
- Arizona Public Access Case Lookup provides broader cross-county and
  lower-court discovery but not Superior Court documents.
- The Pima Superior Court calendar adds future hearing date, time, location,
  judge, attorney, charge, and courtroom filters.
- Clerk Public Records Services supplies omitted, older, courthouse-only, or
  certified records; ECR for Parties is limited to a party's own linked cases.
- Arizona appellate case and opinion systems provide appeal, lower-court case,
  attorney, decision, and citation pivots.

The local Agave source publishes no historical cutoff. A live result from 1981
is an observation, not a completeness claim.

## Ohio county trial-court party indexes

Four Central Ohio sources now expose different but complementary court-record
workflows. Full contracts, access states, alternative routes, and examples are
in [`docs/sources/ohio-county-trial-court-party-indexes.md`](../sources/ohio-county-trial-court-party-indexes.md).

### Franklin County Common Pleas CIO

`query_ohio_franklin_courts.py` searches CIO's ordered lower-bound party-name
index and operates the exact-case route. Name results preserve every physical
occurrence and label true prefix matches separately from lexical spillover.
Exhaustive mode can partition supplied filing dates and the all-court category;
an unresolved numeric boundary or response-buffer-cut terminal row remains
partial because the source publishes no party-index cursor. Exact case returns
summary, parties, schedule, every native `next-docket-key` page, and metadata
for public filing PDFs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_franklin_courts.py name WEXNER \
  --court civil --filed-from 2020-05-19 --filed-to 2020-05-19 \
  --exhaustive --output "$WORKDIR/franklin-party.json"
uv run python tools/query_state_courts.py search WEXNER \
  --source us-oh-franklin-common-pleas-cio --ingest \
  --output "$WORKDIR/franklin-shared-party.json"
uv run python tools/query_state_courts.py case 22CV3098 \
  --source us-oh-franklin-common-pleas-cio --ingest \
  --output "$WORKDIR/franklin-case.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-common-pleas-cio \
  --output "$WORKDIR/franklin-monitor.json"
```

The fixed monitor makes five requests: landing, disclaimer acceptance, narrow
party sentinel, exact case sentinel, and first docket continuation. Docket and
document identities remain distinct; full case retrieval exhausts the native
docket chain, and download reacquires session-scoped document coordinates.

### Franklin County Municipal Court

`query_ohio_franklin_municipal.py` provides anonymous person, company,
case-number, and ticket search plus exact case detail, parties, attorneys,
charges, dispositions, events, financials, receipts, and duplicate-preserving
docket rows. The explicit 250-result ceiling has no continuation, so a boundary
hit returns partial coverage. `summary-pdf` retrieves the generated case
summary; it is not an individual filed document.

```bash
uv run python tools/query_ohio_franklin_municipal.py person BURKHALTER ERIKA \
  --output "$WORKDIR/fcmc-party.json"
uv run python tools/query_ohio_franklin_municipal.py case "2022 CVF 020731" \
  --output "$WORKDIR/fcmc-case.json"
uv run python tools/query_state_courts.py download generated-case-summary \
  --case-number "2022 CVF 020731" --destination "$WORKDIR/fcmc-summary.pdf" \
  --source us-oh-franklin-municipal-court-records \
  --output "$WORKDIR/fcmc-summary.json"
```

### Delaware County Common Pleas CourtView

`query_ohio_delaware_common_pleas.py` uses a persistent headed browser session
after the user clears the visible challenge. Party/company search selects 100
rows and exhausts CourtView's native pages; the source also offers 25, 50, and
75. Exact case returns parties, attorneys, docket, events, financial/receipt
tables, and row-available filing PDFs. Each download reopens the case and
resolves the current Wicket action for the durable case/docket-derived document
identity.

```bash
uv run python tools/query_ohio_delaware_common_pleas.py warmup \
  --wait-seconds 120 --output "$WORKDIR/delaware-session.json"
uv run python tools/query_ohio_delaware_common_pleas.py search-party \
  --last-name SMITH --first-name JOHN \
  --output "$WORKDIR/delaware-party.json"
uv run python tools/query_ohio_delaware_common_pleas.py case <case-number> \
  --output "$WORKDIR/delaware-case.json"
```

Domestic Relations filing images are not public online; the portal also states
that Juvenile and Probate images have some limitations. Clerk policy/contact,
Delaware RealAuction, and Recorder PAX remain useful copy, selector, and
recorded-instrument complements.

### Licking County Common Pleas remote records

`query_ohio_licking_common_pleas.py` verifies the official landing and public
Tyler tenant/configuration shell, then exposes targeted-browser, bulk-request,
current/certified-record, and archive handoffs. The terminal transition
currently reaches AWS Human Verification with no anonymous JWT, so the source
contract does not claim post-login case endpoints. The county-advertised scope
and official alternatives remain searchable planning data rather than being
lost behind one interactive route.

```bash
uv run python tools/query_ohio_licking_common_pleas.py probe \
  --output "$WORKDIR/licking-probe.json"
uv run python tools/query_ohio_licking_common_pleas.py targeted-browser-handoff \
  --party-name SMITH \
  --output "$WORKDIR/licking-browser.json"
uv run python tools/query_ohio_licking_common_pleas.py bulk-request-handoff \
  --scope "party index and docket rows" --party-name SMITH \
  --output "$WORKDIR/licking-bulk.json"
```

The fixed monitor uses six requests for the county landing, Tyler tenant shell,
and four anonymous JSON components. Licking Sheriff foreclosure sources, Recorder PAX,
Auditor records, OGRIP parcels, Clerk requests, and Records and Archives can
supply separately attributable case selectors, sale events, instrument PDFs,
property context, or historical files when the terminal portal is not the best
available route.

## Franklin County Probate Court NetData

`query_ohio_franklin_probate.py` covers the Probate Court's anonymous case
name, exact opened-date, case-type/subtype, attorney, fiduciary, and exact
case-number indexes. Exact case retrieval follows the published type-specific
detail link; separate operations return the docket, fiduciary roster, and
fiduciary or attorney details.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_franklin_probate.py name "SMITH" \
  --output "$WORKDIR/franklin-probate-name.json"
uv run python tools/query_ohio_franklin_probate.py case 617503 \
  --output "$WORKDIR/franklin-probate-case.json"
uv run python tools/query_ohio_franklin_probate.py docket 617503 \
  --output "$WORKDIR/franklin-probate-docket.json"
uv run python tools/query_state_courts.py search "SMITH" \
  --source us-oh-franklin-probate-netdata --ingest \
  --output "$WORKDIR/franklin-probate-shared-search.json"
uv run python tools/query_state_courts.py search "ARTZ" \
  --source us-oh-franklin-probate-netdata --search-field fiduciary --ingest \
  --output "$WORKDIR/franklin-probate-shared-fiduciary.json"
uv run python tools/query_state_courts.py docket 617503 \
  --source us-oh-franklin-probate-netdata --ingest \
  --output "$WORKDIR/franklin-probate-shared-docket.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-probate-netdata \
  --output "$WORKDIR/franklin-probate-monitor.json"
```

The source's native index page contains 40 rows. Without `--limit`, the
adapter follows its forward keys to exhaustion; an explicit limit produces a
query-, page-, row-, and schema-bound cursor. The case number plus fixed-width
suffix is the case identity. Docket rows preserve wrapped physical rows under
one logical entry identity, and fiduciaries use their case-scoped number.

Ingestion projects case metadata, docket entries, fiduciary parties, and
attorneys explicitly linked on the fiduciary roster. Attorney indexes and
profiles without a case link remain source snapshots. Docket reference,
receipt, and cost values remain docket metadata, and no filing artifact is
created because the verified routes do not expose filing images. The fixed
seven-request monitor separates route, selector, schema, identity, and paging
contracts from rolling names, status, dates, amounts, and row counts. Common
Pleas CIO, the Recorder, Auditor/OGRIP parcel records, and the court's copy or
certification channels remain separately attributable complements.

## Supreme Court of Ohio public eCMS docket

`query_ohio_supreme_court.py` uses the official anonymous eCMS application for
Supreme Court case search, exact case detail, docket entries, parties and
attorney appearances, decision metadata, issues, recent filings, and public
filing or decision PDFs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_state_courts.py search Newsome \
  --source us-oh-supreme-court-public-docket \
  --output "$WORKDIR/ohio-supreme-search.json"
uv run python tools/query_state_courts.py search 2017-1682 \
  --source us-oh-supreme-court-public-docket \
  --search-field case-number \
  --output "$WORKDIR/ohio-supreme-number.json"
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

The shared router supports `search`, `case`, `docket`, `documents`, and
`download`. Search defaults to the native caption field; `--search-field`
selects another verified native selector, and ISO `--after`/`--before` values
map to the eCMS filing-date form. An explicit caller window is applied only
after the server's complete array is returned. The observed 1,000-row source
boundary stays `partial`, and source refinement text is not reported as an
empty result.

Search and detail share the published case number as identity. The eCMS
internal case locator and search-row ID remain raw source metadata. Exact
ingestion retains parties, source-published counsel appearances and
registration numbers, docket IDs, decision events, document identities,
prior-jurisdiction arrays, issues, and raw source sections without inferring
case relations or outcomes. Non-dispositive decision descriptions remain raw
metadata rather than generic dispositions. Rolling recent rows remain on the
direct adapter because they do not publish `DocketItems.ID`.

The fixed monitor makes five requests without downloading a PDF and keeps
route/action/schema/identity fingerprints separate from mutable result
counts, status, and recent filings. This source is Supreme Court coverage, not
Ohio trial-court coverage. Reporter of Decisions, Clerk's Journal, attorney
and judge directories, the trial-court directory, court statistics, and local
court systems remain separate official components.

## Ohio Reporter of Decisions publications

`query_ohio_reporter_decisions.py` covers the official opinion and case-
announcement index for the Supreme Court of Ohio, the twelve district courts
of appeals, the Court of Claims, and Reporter miscellaneous publications.
The shared router exposes publication search, exact WebCite detail, and the
official PDF representation.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

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

Search exhausts the source's native 200-row GridView pages before applying
an explicitly requested caller window. With no explicit limit, there is no
local result cap. The source's documented 1,000-result full-text boundary is
reported as partial after all five native pages are retained. Exact WebCite
detail remains a publication operation rather than a case lookup.

WebCite identifies the publication. The deciding-court case number is only an
optional join, and the PDF is a separate representation. Ingestion snapshots
every publication; it adds a sparse case shell only for an unambiguous single
case-number token. Case-less announcements and ambiguous or combined
`Case No.` cells stay snapshot-only. The joined publication event is keyed by
WebCite and does not infer an outcome. Reporter, eCMS, Clerk's Journal, and
district copies can be complementary official views of the same act and do
not become independent corroboration solely because the routes differ.

The fixed monitor makes three requests without downloading a PDF. Stable
route, request, identity, pagination, and validation contracts are kept
separate from parser schema and rolling source-year or sentinel values;
WebForms state and cookies are not retained.

## Connecticut Superior Court Civil/Family case lookup

`query_connecticut_civil_family.py` covers the official anonymous party-name,
exact-docket, child-history, notice, and linked filing routes. The source-local
`curl_cffi` transport is injectable and confined to this portal because the
repository's standard requests transport did not complete the host's TLS
handshake during verification.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_state_courts.py search EPSTEIN \
  --source us-ct-superior-court-civil-family-case-lookup \
  --output "$WORKDIR/ct-party-search.json"
uv run python tools/query_state_courts.py case FBT-CV-26-6159214-S \
  --source us-ct-superior-court-civil-family-case-lookup --ingest \
  --output "$WORKDIR/ct-case.json"
uv run python tools/query_state_courts.py download 32503295 \
  --source us-ct-superior-court-civil-family-case-lookup \
  --case-number FBT-CV-26-6159214-S --ingest \
  --destination "$WORKDIR/ct-complaint.pdf" \
  --output "$WORKDIR/ct-document.json"
uv run python tools/public_records_monitor.py run \
  us-ct-superior-court-civil-family-case-lookup \
  --output "$WORKDIR/ct-monitor.json"
```

The party portal displayed `1-50 of 50` without a pager. The adapter returns
that display as `partial` with `source_display_slice`; it does not describe the
statewide index as exhaustive. With an explicit limit, its query- and
snapshot-bound cursor only windows the same reacquired display and never
represents source continuation beyond row 50. Every name row remains an
`unresolved_same_name_candidate`.

Exact docket detail preserves publisher party numbers, roles, appearance
wording, `DocumentNo`, scheduled-event numbers, notice `eNID`/`PSID`, and
complete-tuple identities for children without publisher IDs. Filing links
remain docket metadata until PDF bytes are downloaded and validated. A
DocumentNo-only download is supported; supplying `--case-number` also verifies
the link and gives ingestion a durable case relationship. No case outcome is
inferred from docket text.

The official fee-based Civil/Family bulk feed is registered as a
same-publisher field-matched complement covering pending and disposed cases,
basic case data, important dates, parties and appearances, motions and
pleadings, and companion cases. It does not include electronic documents.
Superior Court clerk offices remain the human request and copy route. See
`docs/sources/connecticut-superior-civil-family.md` for the full contract.

## New Mexico Judiciary Case Lookup

`query_new_mexico_case_lookup.py` covers the official anonymous statewide
case-metadata application. It provides targeted party discovery on the first
source-native result page and one caller-selected exact case record.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_new_mexico_case_lookup.py search \
  "Epstein Jeffrey" \
  --output "$WORKDIR/nm-party-search.json"
uv run python tools/query_new_mexico_case_lookup.py case \
  D-101-CV-199602449 \
  --output "$WORKDIR/nm-case.json"
uv run python tools/query_state_courts.py case D-101-CV-199602449 \
  --source us-nm-judiciary-case-lookup --ingest \
  --output "$WORKDIR/nm-shared-case.json"
uv run python tools/public_records_monitor.py run \
  us-nm-judiciary-case-lookup \
  --output "$WORKDIR/nm-monitor.json"
```

Search results are party occurrences and may repeat a case for distinct
roles. Exact detail preserves the case summary, parties, counsel, complaint
and cause groups, published disposition fields, register continuation text,
current judge, and judge assignment history. The case number plus derived
court code is canonical identity; transient Tapestry component, session, and
CSRF values are not record IDs.

The source publishes metadata rather than filed documents. re:SearchNM,
judiciary public-records requests, and individual clerks are complementary
routes selected by the missing field or record. The source's individual-record
acquisition grain is modeled at this adapter, independently of technical
search paging or other tools. The fixed monitor uses the four-request exact
case lifecycle and keeps stable form, route, schema, and identity contracts
separate from rolling row counts and current case metadata.

Detailed coverage and identity notes:
`docs/sources/new-mexico-case-lookup.md`.

## Palm Beach County eCaseView and complementary routes

`query_palm_beach_courts.py` operates the Clerk's public guest eCaseView flow
inside a short-lived headed Playwright/Chrome session. The browser helper
returns public fields to Python for normalization and does not emit the
session's ASP.NET, F5, or reCAPTCHA state.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_palm_beach_courts.py runtime-check \
  --output "$WORKDIR/palm-beach-runtime.json"
uv run python tools/query_palm_beach_courts.py search "KRAFT" \
  --output "$WORKDIR/palm-beach-name-search.json"
uv run python tools/query_palm_beach_courts.py search \
  50-2019-MM-002346-AXXX-NB --search-scope case-number \
  --output "$WORKDIR/palm-beach-case-search.json"
uv run python tools/query_palm_beach_courts.py case \
  50-2019-MM-002346-AXXX-NB \
  --output "$WORKDIR/palm-beach-case.json"
uv run python tools/query_palm_beach_courts.py docket \
  50-2019-MM-002346-AXXX-NB --limit 100 \
  --output "$WORKDIR/palm-beach-docket.json"
uv run python tools/query_palm_beach_courts.py download \
  50-2019-MM-002346-AXXX-NB 5 "$WORKDIR/palm-beach-din-5.pdf" \
  --output "$WORKDIR/palm-beach-din-5.json"

uv run python tools/query_state_courts.py case \
  50-2019-MM-002346-AXXX-NB \
  --source us-fl-palm-beach-ecaseview --timeout 300 --ingest \
  --output "$WORKDIR/palm-beach-unified-case.json"
```

The full Florida UCN is the case identity; UCN plus docket index number (DIN)
is the durable docket/document identity. Case output includes the public case
summary, party roles, docket entries, fees, charges, court events, warrants,
and arrests. Each docket entry retains its own image state: public, View on
Request, request in process, or unavailable online. A live exact-case check
returned 234 docket rows, five party-role rows, two charges, and 18 court
events; a selected public DIN returned a validated PDF.

Broad portal searches expose at most 200 recent matches. The adapter reports
that source state as `partial`; it does not impose a second aggregate cap.
Caller `--limit` and cursors page across every row the portal returned.

Complementary Palm Beach routes are registered independently:

| Source ID | Contribution | Tradeoff |
|---|---|---|
| `us-fl-palm-beach-clerkcart` | Purchasable daily, weekly, and monthly public civil/criminal/traffic reports in PDF or Excel | Product-specific fields, periods, and fees |
| `us-fl-palm-beach-records-service` | Entire-case, docket-range, photocopy, certified, and exemplified copy requests | Request/payment workflow |
| `us-fl-acis` | Fourth DCA and statewide appellate cases, dockets, opinions, and available filings | Appellate rather than trial coverage |
| `us-fl-palm-beach-official-records` | Deeds, mortgages, judgments, liens, and uncertified recorded-document images since 1968 | Recorder evidence, not a court docket |

Render any non-adapter route as a selector-specific action:

```bash
uv run python tools/public_records_actions.py plan \
  us-fl-palm-beach-clerkcart --operation request_case_report \
  --selector 50-2019-MM-002346-AXXX-NB
uv run python tools/public_records_actions.py plan \
  us-fl-palm-beach-records-service --operation request_case_copy \
  --selector 50-2019-MM-002346-AXXX-NB
uv run python tools/public_records_actions.py plan \
  us-fl-palm-beach-official-records --operation search_instruments \
  --selector "ROBERT KRAFT"
```

The Clerk's traffic-provider FTP is another structured feed, but it is limited
to qualifying driver-safety-training providers. Fifteenth Circuit division
pages add judge-specific schedule notices. These sources can supply missing
event, appeal, bulk-data, copy, and property/instrument fields while retaining
their separate provenance.

## Broward recorded-instrument pivots to local cases

`us-fl-broward-official-records` is the County recorder index, not the local
court docket. Its party, parcel, instrument, book/page, and case-number fields
can identify a filing or judgment to pivot into the Broward Clerk case search.
The adapter's `routes` output keeps that Clerk route separate alongside the
Property Appraiser, tax collector, Florida DOR roll, and tax-deed information
and auction systems.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_broward_official_records.py detail 114957232 \
  --output "$WORKDIR/broward-instrument.json"
uv run python tools/query_broward_official_records.py routes \
  --output "$WORKDIR/broward-routes.json"
```

Use the exact recorded case number, party name, filing date, parcel ID, or
legal description returned by one source as a selector in the next. The
recorder's ten-day bulk release adds current instrument, party,
cross-reference, legal-description, parcel, and TIFF observations; the Search
& Copy service covers older records and copy or certification requests.

## Virgin Islands C-Track and legacy court files

`query_vicourts.py` queries the anonymous C-Track backend used by the Judicial
Branch of the Virgin Islands for its Supreme and Superior Courts. Court
selectors are resolved against the live directory at runtime: `--court`
accepts an external ID such as `1`, a current resource UUID, or a unique court
name. Legacy selectors such as `ST-19-PB-80` are normalized to
`ST-2019-PB-00080` before exact case resolution.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Directory; case-number, title, and party searches
uv run python tools/query_vicourts.py courts \
  --output "$WORKDIR/vicourts-courts.json"
uv run python tools/query_vicourts.py search ST-19-PB-80 \
  --field number --match-mode exact \
  --output "$WORKDIR/vicourts-case-search.json"
uv run python tools/query_vicourts.py search "Estate of Epstein" \
  --field title --match-mode contains \
  --output "$WORKDIR/vicourts-title-search.json"
uv run python tools/query_vicourts.py search "Epstein" \
  --field party --match-mode match \
  --output "$WORKDIR/vicourts-party-search.json"

# Exact case, docket, limited claim headers, and one docket entry's documents
uv run python tools/query_vicourts.py case ST-19-PB-80 \
  --output "$WORKDIR/vicourts-case.json"
uv run python tools/query_vicourts.py docket ST-19-PB-80 \
  --output "$WORKDIR/vicourts-docket.json"
uv run python tools/query_vicourts.py claims ST-19-PB-80 \
  --output "$WORKDIR/vicourts-claims.json"
uv run python tools/query_vicourts.py documents ST-19-PB-80 \
  "<DOCKET_ENTRY_UUID>" --output "$WORKDIR/vicourts-documents.json"

# The shared router can query and normalize the same case-scoped records
uv run python tools/query_state_courts.py claims ST-19-PB-80 \
  --source us-vi-c-track --ingest \
  --output "$WORKDIR/vicourts-claims-ingested.json"
uv run python tools/query_state_courts.py documents ST-19-PB-80 \
  --source us-vi-c-track --docket-entry-uuid "<DOCKET_ENTRY_UUID>" \
  --ingest --output "$WORKDIR/vicourts-documents-ingested.json"
uv run python tools/query_state_courts.py claims ST-2019-PB-00080 \
  --output "$WORKDIR/vicourts-local-claims.json"

# OCR criteria can be combined; publications use their own index
uv run python tools/query_vicourts.py document-search \
  --exact "quarterly accounting" --any "estate probate" \
  --all "executor report" --none "sample" \
  --output "$WORKDIR/vicourts-document-search.json"
uv run python tools/query_vicourts.py publications \
  --publication-number PB-2026-00032 \
  --output "$WORKDIR/vicourts-publications.json"
uv run python tools/query_vicourts.py publication 1 \
  "<PUBLICATION_UUID>" --output "$WORKDIR/vicourts-publication.json"

# UUID-based C-Track PDF and exact numeric legacy file retrieval
uv run python tools/query_vicourts.py download 1 \
  "<CASE_INSTANCE_UUID>" "<DOCUMENT_LINK_UUID>" \
  "$WORKDIR/vicourts-document.pdf" \
  --output "$WORKDIR/vicourts-document-download.json"
uv run python tools/query_vicourts.py legacy-file 16911884 \
  "$WORKDIR/vicourts-legacy-16911884.pdf" \
  --output "$WORKDIR/vicourts-legacy-16911884.json"

# Direct route-family probe and catalog monitor
uv run python tools/query_vicourts.py probe \
  --output "$WORKDIR/vicourts-probe.json"
uv run python tools/public_records_monitor.py run us-vi-c-track \
  --output "$WORKDIR/vicourts-monitor.json"
```

C-Track pagination is zero-based internally, accepts caller cursors, and is
bounded to the verified 500-row page maximum. Commands have no default
aggregate record ceiling. A caller `--limit` returns an `ok` page with
`next_cursor`; a reported `totalElements` of 10,000 is the source search-window
ceiling and returns `partial` with a `source_overflow` error so the query can be
partitioned.

Claim results are limited header stubs: type, date, and sequence were verified,
but creditor names and amounts were not. The sidecar stores each claim under
its source-native identity and keeps claimant, amount, currency, and status
nullable, so richer source responses can populate those fields without a
schema change. Separately, a secured docket row can report documents while the
document-access route returns zero rows; the adapter preserves that docket row
with an empty document list.

Native identities remain backend-specific:
`CTRACK_COURT:<uuid>`, `CTRACK_CASE:<uuid>`,
`CTRACK_DOCKET:<uuid>`, `CTRACK_CLAIM:<uuid-or-sequence>`,
`CTRACK_DOCUMENT:<uuid>`, `CTRACK_PUBLICATION:<uuid>`, and
`VICOURTS_ITEM:<itemId>`. The legacy `DisplayFile.aspx` backend performs exact
numeric `itemId` retrieval from a separate, curated 96-file publication
container. That container is not the live C-Track probate docket, which
exposes 452 entries for `ST-2019-PB-00080`. Records from the two backends may
be deduplicated only when downloaded PDF SHA-256 values match.

## Texas statewide appellate and complementary court routes

`query_texas_appellate.py` queries the Texas Judicial Branch TAMES portal for
the Supreme Court, Court of Criminal Appeals, and fifteen Courts of Appeals.
The adapter supports case style, exact or partial appellate case number,
originating trial-case number, and attorney search; native court, filing-date,
case-type, county, originating-court, and trial-court filters; exact case
detail; parties and attorneys; docket events; calendar settings; and public
PDFs.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Statewide discovery and an originating-trial-case pivot
uv run python tools/query_texas_appellate.py search "Tesla" --limit 25 \
  --output "$WORKDIR/texas-appellate-style.json"
uv run python tools/query_texas_appellate.py search D-1-GN-24-008508 \
  --scope trial-case-number --county Travis \
  --output "$WORKDIR/texas-appellate-trial-pivot.json"

# Exact case, source-native event view, and public document index
uv run python tools/query_texas_appellate.py case 03-25-00287-CV \
  --output "$WORKDIR/texas-appellate-case.json"
uv run python tools/query_texas_appellate.py docket 03-25-00287-CV \
  --output "$WORKDIR/texas-appellate-docket.json"
uv run python tools/query_texas_appellate.py documents 03-25-00287-CV \
  --output "$WORKDIR/texas-appellate-documents.json"

# Caller-selected public PDF
uv run python tools/query_texas_appellate.py download \
  03-25-00287-CV "<MEDIA_VERSION_ID>" \
  "$WORKDIR/texas-appellate-document.pdf" \
  --output "$WORKDIR/texas-appellate-download.json"

# Unified routing, normalized projection, and the three-part monitor
uv run python tools/query_state_courts.py search "Tesla" \
  --source us-tx-appellate-tames --court-id tx-appellate-coa03 \
  --after 2025-01-01 --limit 25 --ingest \
  --output "$WORKDIR/texas-appellate-unified.json"
uv run python tools/public_records_monitor.py run us-tx-appellate-tames \
  --output "$WORKDIR/texas-appellate-monitor.json"
```

TAMES reports a 1,000-result ceiling for broad searches. The adapter surfaces
that source condition as `partial`, retains a continuation cursor, and lets the
caller narrow the query; it does not impose a separate aggregate ceiling.
Single-result searches that redirect directly to case detail are normalized as
one successful result. The portal states that its case data and documents are
refreshed nightly.

An appellate case's originating trial case is not flattened into the appellate
court. Ingestion creates a searchable trial-case stub, attaches the trial judge
to that trial court, and records the trial-to-appellate `appealed_to`
relationship. Calendar settings become canonical case events, while the
source-native calendar rows and reporter field remain available in raw
provenance.

`query_texas_supreme_publications.py` implements the separate official Supreme
Court publication route. Annual pages enumerate each hand-down date from 2014
forward. A release page preserves its full `#oReportDiv` orders text as native
case occurrences, including the Supreme Court docket, section and action
headings, raw case text, disposition and participation text, and published
county/lower-appellate locator candidates. Generated CSS class names are not
used as the parsing contract.

```bash
# Source inventory, archive families, and exhaustive selected-year dates
uv run python tools/query_texas_supreme_publications.py source \
  --output "$WORKDIR/texas-supreme-source.json"
uv run python tools/query_texas_supreme_publications.py years \
  --output "$WORKDIR/texas-supreme-years-archives.json"
uv run python tools/query_texas_supreme_publications.py releases --year 2026 \
  --output "$WORKDIR/texas-supreme-2026-releases.json"

# One release, a scoped case/text search, and an exact official PDF
uv run python tools/query_texas_supreme_publications.py release 2026-05-29 \
  --output "$WORKDIR/texas-supreme-2026-05-29.json"
uv run python tools/query_texas_supreme_publications.py search "Huffman" \
  --year 2026 --output "$WORKDIR/texas-supreme-huffman.json"
uv run python tools/query_texas_supreme_publications.py download \
  "https://www.txcourts.gov/media/<MEDIA_ID>/<FILE>.pdf" \
  "$WORKDIR/texas-supreme-publication.pdf" \
  --output "$WORKDIR/texas-supreme-download.json"

# Shared date-scoped route, normalized publication shell, and monitor
uv run python tools/query_state_courts.py search "Huffman" \
  --source us-tx-supreme-orders-opinions \
  --after 2026-01-01 --before 2026-12-31 --ingest \
  --output "$WORKDIR/texas-supreme-unified.json"
uv run python tools/public_records_monitor.py run \
  us-tx-supreme-orders-opinions \
  --output "$WORKDIR/texas-supreme-monitor.json"
```

The landing-page inventory retains the May 2020 network-outage orders and
opinions, the pre-October-2014 HTML archive, and fiscal-year order/opinion
aggregates as explicitly typed records. On release pages, the print-order PDF,
editorial case-summary PDF, court opinion, per curiam writing, concurrence,
and dissent each keep their own source document identity. Omitted limits
exhaust the caller-selected annual/date page set; a caller limit yields a
query- and release-set-bound cursor.

Texas coverage is split into independent sources because each answers a
different investigative question:

| Source ID | Best use | Route |
|---|---|---|
| `us-tx-appellate-tames` | Appellate cases, parties, attorneys, chronology, public PDFs, and trial-case pivots | Implemented live adapter |
| `us-tx-appellate-released-orders-opinions` | Court/year/quarter release index, dispositions, judges, orders, and opinions | Public TAMES release pages |
| `us-tx-supreme-orders-opinions` | Supreme Court hand-down text, release occurrences, summaries, independent publication PDFs, outage files, and older archives | Implemented official publication-page adapter |
| `us-tx-researchtx` | Trial cases, filings, document text, hearings, exports, and selected document purchases | eFileTexas account action |
| `us-tx-travis-odyssey-courts` | Free Travis civil/family records from 2006 and criminal records from 2008 | Public Odyssey action |
| `us-tx-travis-criminal-docket-search` | Future settings by date, name, or case number and sorted docket PDFs | Public search/report route |
| `us-tx-travis-district-clerk-records-request` | Official, certified, authenticated, data, and subscription requests | District Clerk action |
| `us-tx-hays-district-court-portal` | Free civil/criminal name discovery with cause, type, filing, summary, bond, and disposition fields | Public Tyler action |
| `us-tx-hays-county-clerk-courts` | County-court criminal, civil, probate, guardianship, calendar, jail, and bond pivots | Public Odyssey action |
| `us-tx-hays-district-clerk-records-request` | Ten-year clerk name searches and electronic or certified copies | District Clerk action |
| `us-tx-oca-citations-notices` | Cause/name discovery and notice text, especially estates, property, tax, condemnation, and substitute service | Public OCA search |
| `us-tx-oca-vexatious-litigants` | Names, aliases, cause numbers, courts, counties, styles, and linked prefiling orders | Public HTML, Excel, and orders |
| `us-tx-oca-local-rules-standing-orders` | Court-specific rules, forms, standing orders, and procedural context | Public OCA document search |
| `us-tx-oca-court-activity` | Filed/disposed counts by court level, county/court, period, and case category from September 1992 | Aggregate analytics source |
| `us-tx-oca-statistical-supplements` | Annual judge and detailed court-activity files | Aggregate bulk source |

The release pages overlap TAMES documents, but overlap is retrieval redundancy,
not independent corroboration. OCA activity and statistical supplements are
aggregate sources and stay outside individual-case projection. The citations
site yields notice records and case pivots; it does not imply a complete
underlying docket.

When the statewide account portal or a local interactive portal is not the best
route, create a reproducible action against the matching source:

```bash
uv run python tools/public_records_actions.py plan us-tx-researchtx \
  --operation search_documents --selector '"Example Holdings LLC"' \
  --output "$WORKDIR/researchtx-document-search.json"
uv run python tools/public_records_actions.py plan \
  us-tx-travis-district-clerk-records-request \
  --operation request_authenticated_copy \
  --selector "<TRAVIS_CASE_NUMBER> filing description" \
  --output "$WORKDIR/travis-authenticated-copy.json"
uv run python tools/public_records_actions.py plan \
  us-tx-hays-district-clerk-records-request \
  --operation request_case_report --selector "<PARTY NAME>" \
  --output "$WORKDIR/hays-case-report.json"
```

## Bexar County historical and current court routes

Bexar court discovery is split across four catalog entries because the
records, capabilities, and custodians differ:

| Source ID | Custodian and coverage | Route |
|---|---|---|
| `us-tx-bexar-district-historical-cases` | District Clerk historical case-file index, OCR, detail, and page images | Active Kofile PublicSearch adapter |
| `us-tx-bexar-justice-portal` | District Clerk and County Clerk current public case metadata and hearings | Tyler interactive portal candidate |
| `us-tx-bexar-district-clerk-records-request` | Civil district and felony criminal data or copies | District Clerk request/copy action |
| `us-tx-bexar-county-clerk-records-request` | County-court-at-law, misdemeanor, and probate data or copies | County Clerk request/copy action |

The historical archive bootstraps an anonymous public session and uses the
Kofile Neumo WebSocket protocol. Its result set is offset-paginated. The
verified census returned 13,965 Historical Cases records through an observed
index date of 1919-09-17. A raw `1/1/1800` file date is an unknown-date
sentinel, not evidence that a case was filed in 1800 or that coverage begins
then.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Indexed names, case numbers, and other indexed text
uv run python tools/query_bexar_courts.py search "SMITH" --limit 50 \
  --output "$WORKDIR/bexar-historical-index.json"

# OCR phrase search, optionally bounded by the source file-date field
uv run python tools/query_bexar_courts.py search "jury verdict" --ocr \
  --date-from 1900-01-01 --date-to 1919-09-17 \
  --output "$WORKDIR/bexar-historical-ocr.json"

# Date-only census; omit QUERY
uv run python tools/query_bexar_courts.py search \
  --date-from 1919-01-01 --date-to 1919-12-31 \
  --output "$WORKDIR/bexar-historical-1919.json"

# Exact source detail and one caller-selected page image
uv run python tools/query_bexar_courts.py case "<DOC_ID>" \
  --output "$WORKDIR/bexar-historical-case.json"
uv run python tools/query_bexar_courts.py page "<DOC_ID>" 1 \
  "$WORKDIR/bexar-historical-page-1.png" \
  --output "$WORKDIR/bexar-historical-page-1.json"

uv run python tools/query_bexar_courts.py probe \
  --output "$WORKDIR/bexar-historical-probe.json"
```

`case` returns the source's historical case-file detail; it does not construct
a modern register of actions or synthesize a docket. `page` retrieves one
uncertified source page image and records its source URL and content metadata.

The current Tyler Justice Information Portal is a different discovery
surface. The official guide documents public case-summary and hearing search,
a 200-result display ceiling, and no registration requirement for public
access. A CAPTCHA was observed in the search workflow, and the verified public
route did not expose document images. Use its catalog entry as an interactive
action rather than treating it as equivalent to the historical machine
source.

For records or copies beyond those surfaces, preserve the responsible clerk:

```bash
uv run python tools/public_records_actions.py plan \
  us-tx-bexar-district-clerk-records-request \
  --operation request_case_copy --selector "<DISTRICT_CASE_NUMBER>" \
  --output "$WORKDIR/bexar-district-copy-plan.json"
uv run python tools/public_records_actions.py plan \
  us-tx-bexar-county-clerk-records-request \
  --operation request_court_data --selector "county-court-at-law cases" \
  --output "$WORKDIR/bexar-county-data-plan.json"
```

## Pennsylvania and Delaware court-source bundles

Pennsylvania and Delaware each use multiple source records because their public
docket systems, published-opinion archives, and filing-copy routes expose
different evidence.

| Source ID | Implemented role | Useful complement |
|---|---|---|
| `us-pa-ujs-public-dockets` | Trial and appellate case discovery, parties, scheduled events, official docket-sheet and Court Summary PDFs | `us-pa-appellate-opinions-postings` for published text; `us-pa-aopc-bulk` for compiled data |
| `us-pa-appellate-opinions-postings` | Supreme, Superior, and Commonwealth Court opinion/order metadata and PDFs | UJS for the underlying docket |
| `us-de-courtconnect` | Public civil party/company indexes, full case reports, docket rows, related cases, and judgments | `us-de-opinions-orders` for published text; clerk record access for other filings |
| `us-de-opinions-orders` | Published Delaware opinion/order metadata and direct PDFs | CourtConnect for civil docket chronology |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Pennsylvania: exact docket, official docket-sheet PDF, and published opinion
uv run python tools/query_pa_ujs.py case CP-51-CR-0007622-2022 \
  --output "$WORKDIR/pa-case.json"
uv run python tools/query_pa_ujs.py report CP-51-CR-0007622-2022 \
  "$WORKDIR/pa-docket.pdf" --kind docket_sheet \
  --output "$WORKDIR/pa-docket-receipt.json"
uv run python tools/query_pa_opinions.py docket "69 WAL 2026" \
  --court supreme --output "$WORKDIR/pa-opinion-postings.json"

# Delaware: civil case and judgment indexes, then the separate publication corpus
uv run python tools/query_delaware_courts.py cases "EXAMPLE HOLDINGS LLC" \
  --output "$WORKDIR/de-cases.json"
uv run python tools/query_delaware_courts.py judgments "EXAMPLE HOLDINGS LLC" \
  --output "$WORKDIR/de-judgments.json"
uv run python tools/query_delaware_opinions.py search \
  --case-number 4373-LM --year 2026 \
  --output "$WORKDIR/de-opinions.json"
uv run python tools/query_delaware_opinions.py download 398840 \
  "$WORKDIR/de-opinion.pdf" \
  --output "$WORKDIR/de-opinion-receipt.json"
```

The adapters follow each source's native result pages by default. Pennsylvania
UJS preserves the portal's 180-day filing-date search window and flags the
observed no-pager boundary rather than silently calling the result complete.
The public UJS search also excludes Courts of Common Pleas civil cases; use
the applicable prothonotary or compiled-data route for that gap.
Delaware CourtConnect follows its 20-row pages; the Delaware opinion archive
supports its published 25, 50, and 100-row page sizes. Caller-selected
`--limit` values are applied only when requested.

Published opinions and orders can provide searchable allegations, holdings,
counsel, dates, and lower-court identifiers even when filing images are not
remotely available. They remain publication evidence, not substitutes for the
underlying complaint, exhibit, or complete docket. The catalog keeps
Pennsylvania AOPC compiled-data requests, Delaware clerk record/certified-copy
requests, and Delaware's named commercial remote-record route available for
those gaps. Publication records use `PAOPINION:<source/court/opinion/posting>`
and `DEOPINION:<document-id>` references.

## Oregon case, document, calendar, and directory components

Oregon's official court surfaces answer different parts of a case-record
question. The catalog keeps the public appellate case API, free Circuit/Tax
case discovery, paid Register of Actions, calendar, document collection,
directory, bulk-product, and record-request routes independently selectable.

### Circuit and Tax Court Smart Search contract

`query_oregon_smart_search.py` represents the official rendered Smart Search
as source `us-or-ojd-smart-search`. The page covers all 36 Circuit Courts and
the Tax Court. Its form is assembled in the browser and posts to
`/portal/SmartSearch/SmartSearch/SmartSearch`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_oregon_smart_search.py sources \
  --output "$WORKDIR/oregon-smart-search-sources.json"
uv run python tools/query_oregon_smart_search.py probe \
  --output "$WORKDIR/oregon-smart-search-contract.json"
uv run python tools/query_oregon_smart_search.py options JudgmentType \
  --output "$WORKDIR/oregon-smart-search-judgment-types.json"
uv run python tools/query_oregon_smart_search.py prepare "EXAMPLE LLC" \
  --search-by BusinessName --location Multnomah --case-type Civil \
  --output "$WORKDIR/oregon-smart-search-business-handoff.json"
uv run python tools/query_oregon_smart_search.py prepare \
  --last-name Smith --first-name Jane --file-date-start 2025-01-01 \
  --file-date-end 2025-12-31 \
  --output "$WORKDIR/oregon-smart-search-name-handoff.json"
```

The rendered contract exposes case, judgment, and warrant components; 38
locations; 11 search modes; and the current case-status, judicial-officer,
judgment-type, warrant-type, and warrant-status option sets. The live anonymous
configuration reports reCAPTCHA at submission. `probe` records the form,
stable controls, source settings, selector counts, and schema fingerprint.
`options` returns one complete native option set.

`prepare` validates the selected form values and returns a
`public-records-result/1.0` envelope containing one
`interactive_court_search_handoff`. Its query fingerprint includes every
form-affecting input, and the record preserves native strings, checkbox state,
requested components, form action, and browser-prefill instructions. The
record sets `prepared_search_is_case_result` to `false`: it describes the
search to run in the rendered session and contains no returned case,
judgment, or warrant row.

### OJCIN products and statewide-data delivery

`query_oregon_ojcin_products.py` keeps the public product directory and five
acquisition components separately attributable:

| Source ID | System or route | Published scope |
|---|---|---|
| `us-or-ojd-statewide-court-data-products` | Public OJD product directory | Metadata and acquisition evidence for the five components below |
| `us-or-ojcin-oeci-subscription` | OECI subscription | Register of Actions, case information, and judgments for all 36 Circuit Courts and the Tax Court |
| `us-or-ojcin-acms-subscription` | ACMS subscription | Supreme Court and Court of Appeals case registers, judgments, and authorized documents |
| `us-or-ojcin-standard-report-package` | OJCIN standard report package | Criminal Judgment Index, Civil Judgment Index, and Case Index reports |
| `us-or-ojcin-bulk-data-transfer` | Approved bulk transfer | Monthly or one-time delivery whose scope is established by OJD approval and the transfer agreement |
| `us-or-osca-statewide-court-data-request` | OSCA public-record request | Existing statewide court data and administrative records held by OSCA |

```bash
uv run python tools/query_oregon_ojcin_products.py products \
  --output "$WORKDIR/oregon-court-data-products.json"
uv run python tools/query_oregon_ojcin_products.py search "judgment index" \
  --output "$WORKDIR/oregon-product-search.json"
uv run python tools/query_oregon_ojcin_products.py handoff \
  us-or-ojcin-bulk-data-transfer \
  --output "$WORKDIR/oregon-bulk-handoff.json"
uv run python tools/query_oregon_ojcin_products.py probe \
  --output "$WORKDIR/oregon-product-route-probe.json"
uv run python tools/query_oregon_ojcin_products.py inspect-delivery \
  us-or-ojcin-bulk-data-transfer /path/to/acquired-delivery \
  --delivery-version 2026-07 --provider-reference OJD-REFERENCE \
  --correction-state original \
  --specification-ref /path/to/delivery-specification.pdf \
  --output "$WORKDIR/oregon-delivery-receipt.json"
```

`products` and `search` use the shared public-record result envelope; their
records are product metadata, not case-search results. `handoff` and `probe`
use `oregon-ojcin-products/1.0`. A full probe checks 13 official landing,
signup, fee, order, terms, form, login, search-information, case-copy, and
OSCA request representations while retaining the component source IDs attached
to each route.

`inspect-delivery` creates an `oregon-ojcin-delivery-receipt/1.0` receipt for
a delivery already acquired through one of those components. It preserves the
product, delivery version, receipt-time basis, provider reference, correction
state, scope note, specification and case-document references, artifact-set
hash, file hashes and sizes, observed formats, and ZIP member inventory.
Format labels are observations; the receipt reports zero parsed records and
does not assign a row schema that the verified public materials do not
publish. This leaves a byte-level lineage anchor for a later parser tied to an
actual delivery and its accompanying specification.

The canonical identifiers make earlier collapsed catalog labels visible as
history:

| Earlier source ID | Canonical replacement history |
|---|---|
| `us-or-ojd-free-circuit-tax-record-search` | Same Smart Search surface, now `us-or-ojd-smart-search` |
| `us-or-ojcin` | Earlier umbrella spanning what is now the public directory plus the separately identified OECI and ACMS products |
| `us-or-ojcin-bulk-data` | Earlier combined entry now split into `us-or-ojcin-standard-report-package` and `us-or-ojcin-bulk-data-transfer` |
| `us-or-ojd-statewide-data-request` | Same request family, now attributed to `us-or-osca-statewide-court-data-request` |

`us-or-appellate-record-search`, the Circuit/Tax and appellate calendars,
Law Library collections, and `us-or-ojd-case-record-request` remain distinct
complements with their own record and acquisition roles.

### Law Library court-document collections

`query_oregon_court_documents.py` shares one CONTENTdm transport while
retaining seven source identities:

| Source ID | Collection | Native role |
|---|---|---|
| `us-or-law-library-supreme-opinions` | `p17027coll3` | Supreme Court opinions |
| `us-or-law-library-coa-opinions` | `p17027coll5` | Court of Appeals opinions |
| `us-or-law-library-tax-court-decisions` | `p17027coll6` | Tax Court decisions and orders |
| `us-or-law-library-supreme-briefs` | `p17027coll7` | Supreme Court filed briefs |
| `us-or-law-library-coa-briefs` | `p17027coll8` | Court of Appeals filed briefs |
| `us-or-law-library-coa-orders-interest` | `p17027coll17` | Selected appellate orders |
| `us-or-law-library-multnomah-presiding-orders` | `p17027coll15` | Multnomah presiding-judge orders |

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_oregon_court_documents.py sources \
  --output "$WORKDIR/oregon-court-document-sources.json"
uv run python tools/query_oregon_court_documents.py search A182332 \
  --source us-or-law-library-coa-opinions --field all \
  --output "$WORKDIR/oregon-coa-opinion-search.json"
uv run python tools/query_oregon_court_documents.py search A182332 \
  --source us-or-law-library-coa-briefs --field all \
  --output "$WORKDIR/oregon-coa-brief-search.json"
uv run python tools/query_oregon_court_documents.py item 42527 \
  --source us-or-law-library-coa-opinions \
  --output "$WORKDIR/oregon-coa-opinion.json"
uv run python tools/query_oregon_court_documents.py download 42527 \
  "$WORKDIR/A182332.pdf" \
  --source us-or-law-library-coa-opinions \
  --output "$WORKDIR/oregon-coa-download.json"
uv run python tools/query_oregon_court_documents.py probe --all \
  --output "$WORKDIR/oregon-court-document-probes.json"
```

The source supports one search term and one field per request. Continuation
cursors bind that selection and its sort to the collection, initial result
count, start offset, and overlap item. Short pages do not end a count-backed
search; reordered boundaries, repeated identities, count drift, and pages that
make no progress remain explicit. Item responses preserve structured metadata,
extracted text, compound pages, source-native download routes, and collection
provenance. Downloads are content hashed and cited as
`ORCOURT-DOC:<source-id>:<item-id>` and
`ORCOURT-ARTIFACT:<source-id>:<sha256>`.

Briefs add searchable filing substance even when the full Circuit/Tax register
is available only through OJCIN. They do not turn the collection into a
statewide trial docket. Likewise, selected orders and presiding-judge orders
add adjudicative or procedural text without implying complete case coverage.

### Appellate case and docket API

`query_oregon_appellate.py` queries the official anonymous Supreme Court and
Court of Appeals API while preserving the court and C-Track UUID namespaces.

```bash
uv run python tools/query_oregon_appellate.py courts \
  --output "$WORKDIR/oregon-appellate-courts.json"
uv run python tools/query_oregon_appellate.py search-party \
  "EXAMPLE ORGANIZATION" --court coa --limit 25 \
  --output "$WORKDIR/oregon-appellate-party.json"
uv run python tools/query_oregon_appellate.py search-case A182332 \
  --field number --match-mode exact --court coa \
  --output "$WORKDIR/oregon-appellate-search.json"
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

Search continuations bind the court, selectors, sort, schema, total, and
boundary identity. The API reports a 10,000-result search ceiling, which is
retained as completeness state. Exact case aggregation keeps parties and
attorneys, docket entries, hearings, judgments, case groups, and document
metadata as independently reported components. For the verified A182332
sentinel, the official judgments subresource currently returns HTTP 500 while
the other components remain available; the case therefore returns as partial
with the working records intact. Document metadata and file retrieval state
remain separate capabilities.

### Supreme Court and Court of Appeals calendar lists

`query_oregon_appellate_calendars.py` keeps the Supreme Court and Court of
Appeals publications as distinct source components. The historical
`/sclist` and `/coadocket` links now resolve through OJD error pages; the
adapter records that migration state and queries the current official
SharePoint lists instead.

```bash
uv run python tools/query_oregon_appellate_calendars.py search \
  --court coa --current \
  --output "$WORKDIR/oregon-coa-calendar.json"
uv run python tools/query_oregon_appellate_calendars.py search \
  --court supreme --case-number S072119 \
  --output "$WORKDIR/oregon-supreme-calendar-case.json"
uv run python tools/query_state_courts.py calendar S072119 \
  --source us-or-supreme-court-calendar --ingest \
  --output "$WORKDIR/oregon-supreme-calendar-unified.json"
uv run python tools/query_oregon_appellate_calendars.py probe --court coa \
  --output "$WORKDIR/oregon-coa-calendar-probe.json"
uv run python tools/query_oregon_appellate_calendars.py probe --court supreme \
  --output "$WORKDIR/oregon-supreme-calendar-probe.json"
```

The list client follows every source continuation before applying date, case,
text, event-type, current-only, or caller-selected page filters. This matters
for the Court of Appeals: the official view declares a 300-row limit while a
live complete traversal returned 321 rows. The adapter reports the view limit
and complete API traversal separately. Supreme Court entries preserve issues,
attorneys, justices, hearing identifiers, and directly published attachment
documents such as briefs. Monitoring hashes the stable page/list/view
contract; changing row, attachment, and date counts remain probe details.
Ingestion retains event type, time, judge, location, and status so the same
hearings remain queryable through the local calendar route.

### Circuit and Tax Court hearing calendar

`query_oregon_court_calendar.py` implements the official Tyler PublicAccess
session flow: load the location directory, select a location, load that
location's form and judicial-officer options, then submit one source-native
search mode.

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

The direct adapter also supports party, business, attorney-name,
attorney-bar-number, and judicial-officer searches. It groups hearing rows
under stable case identities and emits stable docket-event identities, so the
shared court ingester can retain multiple hearings for one case without
inventing separate cases.

The source form accepts current and forward dates within its 90-day window.
The OJD quick guide describes display of the first 400 results, but a live
statewide same-day query returned 550 rows and an explicit
too-many-matches-to-display alert. These are stored as separate facts: the
adapter preserves every returned row, marks explicit truncation as partial,
and supplies location, day, category, and judicial-officer partition hints.
It does not impose a 400-row local cap.

### State and local court directories

`query_oregon_court_directories.py` keeps four official OJD lists distinct:
state court locations and administrators, state judges, municipal and justice
courts, and municipal and justice judge assignments.

```bash
uv run python tools/query_oregon_court_directories.py sources \
  --output "$WORKDIR/oregon-directory-sources.json"
uv run python tools/query_oregon_court_directories.py search Deschutes \
  --source us-or-state-court-directory \
  --output "$WORKDIR/oregon-state-courts.json"
uv run python tools/query_oregon_court_directories.py list \
  --source us-or-state-judge-directory --view presiding-judges \
  --output "$WORKDIR/oregon-presiding-judges.json"
uv run python tools/query_oregon_court_directories.py discovery \
  --query Bend \
  --output "$WORKDIR/oregon-local-source-candidates.json"
uv run python tools/query_oregon_court_directories.py probe \
  --source us-or-local-court-registry \
  --output "$WORKDIR/oregon-local-court-probe.json"
```

The adapter reproduces the page's anonymous bootstrap followed by same-session
SharePoint SOAP calls. It retains the list and view identifiers, raw fields,
normalized court or official identity, publication timestamps, and complete
rowset state. Named views and raw live view GUIDs are both accepted, so newly
published views can be inspected before configuration changes.

The local-court registry currently yields official website candidates for
nearly every listed municipal or justice court. `discovery` emits those
candidates with their directory lineage for the separate local-source backlog;
it does not conflate a directory entry with case-level coverage. Court and
judge roster growth remains monitor detail, while the stable list, view, and
row-schema contract drives drift detection.

### Oregon Tyler Municipal Record Search tenants

`query_eugene_municipal_court.py` implements a shared Tyler host contract while
retaining eight separate courts, source IDs, jurisdictions, selector sets, and
access observations.

| Source ID | Court | Direct case / docket observation | Verified public selectors or useful alternatives |
|---|---|---|---|
| `us-or-eugene-municipal-record-search` | Eugene Municipal Court | public / public | name, citation, docket, police case, plate, VIN; City JustFOIA record-request complement |
| `us-or-hermiston-municipal-record-search` | Hermiston Municipal Court | public / public | name, citation, docket, plate; official court-records information |
| `us-or-linn-county-justice-record-search` | Linn County Justice Court | public / public | name, citation |
| `us-or-medford-municipal-record-search` | Medford Municipal Court | public / public | name, citation, docket, police case, plate, VIN |
| `us-or-springfield-municipal-record-search` | Springfield Municipal Court | public / public | name, citation, docket, police case |
| `us-or-clackamas-county-justice-record-search` | Clackamas County Justice Court | login required / not found | Justice Court record-request form, county request routing, and court information |
| `us-or-corvallis-municipal-record-search` | Corvallis Municipal Court | login required / login required | City request form, archives, court information, violation lookup, and recorder routing |
| `us-tribal-grand-ronde-record-search` | Confederated Tribes of Grand Ronde Tribal Court | login required / login required | Tribal Court request/rules/forms for court-record requesters; Tribal Records Center routes remain separately labeled for tribal members |

The OJD
[municipal and justice court registry](https://www.courts.oregon.gov/courts/Pages/other-courts.aspx)
is discovery evidence for the Oregon local-court links. Direct tenant probes
establish the component states in the table; a directory link alone does not
establish anonymous case or docket access. Grand Ronde is attributed to the
Tribal Court rather than treated as an Oregon municipal court.

```bash
uv run python tools/query_eugene_municipal_court.py search \
  --tenant medford --citation M100 \
  --output "$WORKDIR/medford-citation-search.json"
uv run python tools/query_eugene_municipal_court.py search \
  --tenant linn-county --last-name ANDERSON --partial --limit 25 \
  --output "$WORKDIR/linn-name-search.json"
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
uv run python tools/query_eugene_municipal_court.py discovery \
  --tenant grand-ronde \
  --output "$WORKDIR/grand-ronde-source-discovery.json"
uv run python tools/query_eugene_municipal_court.py probe \
  --tenant corvallis \
  --output "$WORKDIR/corvallis-source-probe.json"
uv run python tools/query_state_courts.py search E018359 \
  --source us-or-medford-municipal-record-search \
  --search-field citation --jurisdiction 41029 \
  --output "$WORKDIR/medford-unified.json"
uv run python tools/public_records_monitor.py run \
  us-or-medford-municipal-record-search \
  us-or-corvallis-municipal-record-search \
  us-tribal-grand-ronde-record-search \
  --output "$WORKDIR/oregon-tyler-monitors.json"
```

Each public tenant uses only the selectors observed on its own form. Name
search can also carry first name, date of birth, driver-license number,
Soundex, and partial-name options where the form exposes them. The adapter
preserves complete server-rendered snapshots and adds local continuation bound
to the tenant, selector, snapshot, and prior boundary. Case references carry
the tenant's source and court IDs plus citation/violation identity;
docket-session references keep the native date, calendar code, and room code.

Eugene's
[Municipal Court JustFOIA request form](https://eugeneor.justfoia.com/Forms/Launch/81b9da81-94d7-49b8-8750-3452f260414f)
is a distinct official request and file-delivery complement to the online case
index. Other tenants retain their own official alternatives with audience and
role metadata. `discovery` reports those components and links without treating
a request, archive, payment, or member-records route as another case-index
observation.

### Case discovery and acquisition routes

- `us-or-appellate-record-search` is the anonymous official Supreme Court and
  Court of Appeals API for cases, parties, attorneys, docket entries, events,
  outcomes, and document metadata. File availability is a separate field from
  metadata availability.
- `us-or-ojd-smart-search` is the rendered Tyler Smart Search contract and
  browser-ready handoff for Circuit and Tax Court case, judgment, and warrant
  selectors.
- `us-or-ojcin-oeci-subscription` and `us-or-ojcin-acms-subscription` retain
  the Circuit/Tax and appellate Register of Actions products.
- `us-or-ojcin-standard-report-package` and
  `us-or-ojcin-bulk-data-transfer` retain the index-report and approved
  delivery products as separate acquisition components.
- `us-or-circuit-tax-court-calendars` exposes hearing discovery by attorney,
  case, judge, party/business, location, and date. The source's 90-day window,
  the guide's 400-result statement, returned-row count, and explicit
  truncation alert remain separate completeness facts used for partitioning.
- `us-or-court-of-appeals-calendar` and
  `us-or-supreme-court-calendar` retain the two appellate list namespaces,
  follow list continuations independently of visible view limits, and expose
  directly attached Supreme Court briefs when the source publishes them.
- `us-or-ojd-case-record-request` covers case copies and audio, while
  `us-or-osca-statewide-court-data-request` covers statewide and
  administrative data held by OSCA.

The state-court, state-judge, municipal/justice-court, and local-judge
SharePoint lists are separate directory components. In addition to contacts,
terms, jurisdictions, and court-of-record status, the local court registry
publishes court websites. Those websites feed a renewable per-court discovery
queue for structured case search, calendars, registers, documents, requests,
bulk products, and recurring vendor families.

## Harris County District Clerk public datasets

The District Clerk publishes a separate civil/criminal dataset catalog for
bulk case metadata. The adapter inventories the complete live catalog and
selects downloads by the exact current catalog path, so similarly named
historical, current, and delta files remain distinct.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_harris_court_bulk.py list \
  --section Civil --family case_summary --published-after 2026-07-01 \
  --result-limit 25 \
  --output "$WORKDIR/harris-civil-case-summary-catalog.json"
uv run python tools/query_harris_court_bulk.py inspect \
  'Civil\2024-08-15 FIELD_CODES.xlsx' \
  --output "$WORKDIR/harris-field-codes-inspection.json"
uv run python tools/query_harris_court_bulk.py download \
  'Civil\2024-08-15 FIELD_CODES.xlsx' \
  --destination "$WORKDIR/harris-field-codes.xlsx" \
  --output "$WORKDIR/harris-field-codes-receipt.json"
uv run python tools/query_harris_court_bulk.py sentinel \
  --output "$WORKDIR/harris-court-bulk-sentinel.json"

uv run python tools/query_state_courts.py discovery Civil \
  --source us-tx-harris-district-clerk-public-datasets \
  --case-type case_summary --limit 25 \
  --output "$WORKDIR/harris-shared-discovery.json"
uv run python tools/query_state_courts.py documents \
  'Civil\2024-08-15 FIELD_CODES.xlsx' \
  --source us-tx-harris-district-clerk-public-datasets \
  --output "$WORKDIR/harris-shared-artifact-inspection.json"
```

Civil families include case summaries, parties, activities, settings, service,
and historical extracts. Criminal families include filings, future settings,
dispositions, and other published extracts. The source sometimes returns an
unhelpful MIME type, so inspection and download receipts validate the response
filename and file signature.

The shared court router exposes exactly `discovery`, `documents`, `download`,
and `probe`. Here `documents` inspects one exact bulk artifact; it does not
represent an individual filing image. The streaming ingester currently parses
header-bearing civil case-summary, party, and activity extracts plus criminal
filing and disposition extracts:

```bash
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

Each input row retains an occurrence identity derived from the artifact,
source row number, and raw row hash before case-level projection. A live
five-artifact validation on 2026-07-30 preserved 18,419 source-row
occurrences and projected 6,619 cases, 11,699 parties, 1,741 attorneys, 3,575
representations, 9,873 docket entries, and 5,961 case events, with zero
unresolved rows on that run. Those values are a rolling validation
observation, not fixed catalog totals. No filing-document artifacts were
created; the separately attributed District Clerk eDocs route supplies that
case-specific document complement.

## Formal feeds and source actions

The catalog also includes formal court-data programs in Maryland, Indiana,
Wisconsin, Minnesota, North Carolina, Arizona, Oregon, Washington, and Texas,
plus targeted public portals such as Maryland Case Search and DC Superior
Court eAccess. Their entries preserve the official program URL, advertised
capabilities, authentication or agreement route, fees, update model, and
record-policy metadata:

```bash
uv run python tools/public_records_catalog.py list --domain court --json
uv run python tools/public_records_catalog.py show us-pa-ujs-public-dockets --json
uv run python tools/public_records_catalog.py show us-de-courtconnect --json
uv run python tools/public_records_catalog.py show us-md-case-search --json
uv run python tools/public_records_catalog.py show us-in-iocs-bulk --json
uv run python tools/public_records_catalog.py show us-wi-wcca-public --json
uv run python tools/public_records_catalog.py show us-wi-wscca-public --json
uv run python tools/public_records_catalog.py show us-wi-court-opinions --json
uv run python tools/public_records_catalog.py show \
  us-wi-state-law-library-briefs --json
uv run python tools/public_records_catalog.py show us-wi-wcca-rest --json
```

Wisconsin is represented by distinct circuit-case, appellate-case,
publication, archive, and acquisition routes. WCCA public search and its
subscription REST product cover circuit-case metadata. The implemented WSCCA
adapter covers Supreme Court and Court of Appeals case search, exact case
detail, parties, counsel, dockets, source-linked public documents, and the
direct per-case RSS feed:

```bash
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
```

The directory adapter keeps six current publication components separate:
circuit offices, clerks, judges, judicial administrative districts, Court of
Appeals offices, and Supreme Court/state offices. Its shared route and
ingester retain directory results as source snapshots rather than cases.
County court links are discovery candidates for later capability review.

```bash
uv run python tools/query_wisconsin_court_directory.py county Dane \
  --output "$WORKDIR/wi-dane-courts.json"
uv run python tools/query_wisconsin_court_directory.py search Ashley \
  --component administrative-districts \
  --output "$WORKDIR/wi-court-personnel.json"
uv run python tools/query_wisconsin_court_directory.py discovery \
  --query Dane --output "$WORKDIR/wi-county-court-routes.json"
uv run python tools/query_state_courts.py search "Example" \
  --source us-wi-court-directory --jurisdiction 55025 \
  --search-field clerk --ingest \
  --output "$WORKDIR/wi-directory-snapshot.json"
```

The adapter also maps the official municipal-court PDF, alphabetical employee
listing, and county juror contacts. WCCA, WSCCA, and the opinion corpus remain
separate case and publication sources.

The separate publication adapter searches Supreme Court opinions and orders,
Court of Appeals opinions and summary dispositions, both full-text indexes,
both incremental release feeds, and official PDFs:

```bash
uv run python tools/query_wisconsin_opinions.py search \
  --collection appeals-opinions --case-number 2025AP000482 \
  --output "$WORKDIR/wi-appeals-opinions.json"
uv run python tools/query_wisconsin_opinions.py keyword \
  "Wisconsin Voter Alliance" --court supreme \
  --output "$WORKDIR/wi-supreme-fulltext.json"
uv run python tools/query_wisconsin_opinions.py feed --court appeals \
  --output "$WORKDIR/wi-appeals-feed.json"
uv run python tools/query_wisconsin_opinions.py routes \
  --case-number 2025AP000482 \
  --output "$WORKDIR/wi-appellate-routes.json"
```

Appellate identity uses the normalized appellate case number. A PDF can be
shared by consolidated cases, so the normalized store keeps a case-scoped
document occurrence and a shared native artifact identifier. The State Law
Library brief search and copy service, UW Law historical brief repository,
appellate clerk, and CourtListener remain separately attributable complements
for records or eras not covered by one live route.

`public_records_actions.py` turns any catalog route into a reproducible plan.
`enqueue` adds the same structured request to `human_actions`, deduplicated by
its action fingerprint.

```bash
uv run python tools/public_records_actions.py plan us-in-iocs-bulk \
  --operation obtain_feed --selector "civil case metadata" \
  --requested-field case_number --requested-field party_name \
  --output "$WORKDIR/indiana-feed-plan.json"
uv run python tools/public_records_actions.py enqueue us-az-eaccess \
  --operation fetch_document --selector "CV2026-000042" \
  --court-or-office "Maricopa County Superior Court" \
  --output "$WORKDIR/arizona-document-action.json"
uv run python tools/public_records_actions.py plan us-wi-wcca-public \
  --operation search_cases --selector "Example Person" --jurisdiction 55 \
  --output "$WORKDIR/wisconsin-circuit-search-plan.json"
uv run python tools/public_records_actions.py plan us-wi-wscca-public \
  --operation search_cases --selector "2025AP000699" --jurisdiction 55 \
  --output "$WORKDIR/wisconsin-appellate-search-plan.json"
uv run python tools/public_records_actions.py plan us-pa-ujs-public-dockets \
  --operation fetch_docket_sheet --selector "CP-00-CR-0000042-2026" \
  --output "$WORKDIR/pennsylvania-docket-plan.json"
uv run python tools/public_records_actions.py plan us-md-aoc-court-data \
  --operation request_court_data --selector "civil judgments" \
  --output "$WORKDIR/maryland-court-data-plan.json"
uv run python tools/public_records_actions.py list --status pending \
  --output "$WORKDIR/pending-public-record-actions.json"
```

This keeps source-specific acquisition facts in the catalog and action record,
while query adapters remain focused on search and normalization.

## Court sidecar ingestion

Every valid `public-records-result/1.0` envelope can be retained as an immutable
source snapshot. `ok` and `partial` envelopes may also project canonical case
records into courts, cases, parties, attorneys, representations, judicial
assignments, docket entries, events, documents, and restriction events.
Barrier and zero-result envelopes remain useful source observations even when
there are no case rows to project.

```bash
uv run python tools/ingest_state_court_records.py ingest \
  "$WORKDIR/court-result.json" \
  --output "$WORKDIR/court-ingest.json"
```

Re-ingesting the same envelope is idempotent. The summary reports its snapshot
ID, source status, projected row counts, artifact hash, and canonical
`STATECOURT:` references.

## Cross-domain planning and document evidence

Build a reproducible search plan when litigation may be connected to a person,
entity, address, parcel, lender, recorder instrument, or legal description:

```bash
uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
  --alias "Example Holdings" \
  --address "100 Main St, Albany, NY" \
  --jurisdiction 36 \
  --output "$WORKDIR/example-records-plan.json"
```

The plan inventories every cataloged property and court source and emits
dependency-aware query templates. It includes sources reached through APIs,
bulk files, accounts, formal feeds, requests, and physical offices; the source
entry carries the current route and capabilities. Catalog-declared complements
are also expanded into route groups that show what roles and capabilities each
additional source contributes, its coverage start/cadence and jurisdiction
fit, and whether it shares the primary record identity or requires a
cross-source pivot.

For court filings, retain the source bytes in
`public_records_artifacts.py`, add OCR or parsed-text representations, and
ingest field-level extraction through `public_records_extract.py`. Evidence
rows can point to an artifact hash, representation, page, region, and exact
quote. Deterministic checks cover dates, amounts, identifiers, quoted text, and
the extraction schema; model or rule provenance stays attached to the derived
representation.

After court parties and property/instrument parties are in their sidecars,
`public_records_entity_candidates.py generate` produces explainable candidates
against investigation entities and aliases. Review its retained name, address,
and identifier signals, then use `decide --action accept|reject|reopen|undo`
to record the resolution history.

## U.S. Tax Court DAWSON and complementary records

`query_tax_court.py` queries the anonymous public DAWSON API for case
discovery, case detail, docket entries, orders, opinions, current releases,
judges, trial sessions, public filing PDFs, and the court's printable docket
record.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_tax_court.py cases Hagee \
  --output "$WORKDIR/tax-court-cases.json"
uv run python tools/query_tax_court.py cases \
  --state CA --filed-after 2025-01-01 --case-type Deficiency \
  --output "$WORKDIR/tax-court-california-deficiency.json"
uv run python tools/query_tax_court.py case 455-22S \
  --output "$WORKDIR/tax-court-case.json"
uv run python tools/query_tax_court.py docket 455-22S \
  --output "$WORKDIR/tax-court-docket.json"

uv run python tools/query_tax_court.py orders --docket 455-22 \
  --output "$WORKDIR/tax-court-orders.json"
uv run python tools/query_tax_court.py opinions \
  --keyword '"innocent spouse"' --opinion-type memorandum \
  --output "$WORKDIR/tax-court-opinions.json"

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

uv run python tools/query_tax_court.py download 455-22 \
  "<DOCKET_ENTRY_ID>" "$WORKDIR/tax-court-filing.pdf" \
  --output "$WORKDIR/tax-court-filing.json"
uv run python tools/query_tax_court.py docket-pdf 455-22 \
  "$WORKDIR/tax-court-docket.pdf" \
  --output "$WORKDIR/tax-court-docket-pdf.json"
uv run python tools/query_tax_court.py probe \
  --output "$WORKDIR/tax-court-probe.json"
```

DAWSON case search returns up to 5,000 rows without native pagination;
`cases --limit` is an optional caller-side slice after that response. Order and
opinion searches also have a 5,000-row native ceiling, and the adapter requests
the full ceiling by default. `today-opinions` has a separate 200-row source
ceiling. Docket entries are zero-based pages `0` through `20`, at 1,000 rows
per page; omitting `--page` fetches every source-accessible page and reports
whether that covered the native total. Today's Orders uses one-based,
100-row pages; omitting `--page` fetches all source-reported pages. The
public-document service issues short-lived signed URLs, so `download` records
the stable public request URL and observed expiry metadata rather than treating
the signed URL as an identifier.

The source roles remain distinct:

- DAWSON case and docket metadata establish what the court indexed and when;
  a docket row or `isFileAttached` flag alone does not establish the contents
  or availability of a public PDF.
- A downloaded DAWSON order, opinion, filing, or printable docket is a primary
  court record. Allegations quoted from a party filing remain party
  allegations.
- `us-tax-court-reports` is the court's separate pamphlet/PDF archive for
  published opinions and citation pages.
- `us-tax-court-records-transcripts` is the clerk/reporter route for copies,
  certification, and transcripts not supplied by DAWSON.
- GovInfo's `USCOURTS` collection with court code `tc` and CourtListener add
  opinion text, citation, and historical-discovery routes. The same document
  mirrored across these hosts is retrieval redundancy, not independent
  corroboration.

## query_courtlistener.py — CourtListener/RECAP

Comprehensive US court research: docket search, party/attorney/firm lookup, opinion text, RECAP document search and download, citation graphs, judge career timelines, financial disclosures, investment holdings, travel reimbursements, and FJC Integrated Database queries. Recently rebuilt with 17 commands.

**Auth:** Requires `COURTLISTENER_TOKEN` in `.env`. Free accounts available at courtlistener.com.

### Search Commands

```bash
# Generic search with field operators (type: r=RECAP, o=opinions, p=people)
uv run python tools/query_courtlistener.py search "Jeffrey Epstein" --type r --limit 20
uv run python tools/query_courtlistener.py search --party "Ghislaine Maxwell" --court nysd
uv run python tools/query_courtlistener.py search --attorney "David Boies" --type r
uv run python tools/query_courtlistener.py search --firm "Kirkland" --after 2020-01-01
uv run python tools/query_courtlistener.py search "fraud" --docket-number "1:23-cv-01234"
uv run python tools/query_courtlistener.py search "Epstein" --semantic --highlight

# RECAP docket search (shortcut for type=r with case-specific output)
uv run python tools/query_courtlistener.py cases "Epstein" --court nysd
uv run python tools/query_courtlistener.py cases "Maxwell" --after 2019-01-01 --before 2023-01-01

# Party search (returns parties, attorneys, firms)
uv run python tools/query_courtlistener.py party "Ghislaine Maxwell" --limit 20
uv run python tools/query_courtlistener.py party "Apollo Global" --court nysd

# Opinion search (with optional semantic search)
uv run python tools/query_courtlistener.py opinions "Epstein" --court ca2
uv run python tools/query_courtlistener.py opinions "qualified immunity" --semantic
```

### Docket & Document Commands

```bash
# Docket detail by ID
uv run python tools/query_courtlistener.py docket 16066603

# RECAP document search (filings, motions, exhibits)
uv run python tools/query_courtlistener.py recap-search "motion to dismiss" --court nysd

# Download RECAP document PDF
uv run python tools/query_courtlistener.py download "https://storage.courtlistener.com/..." /tmp/doc.pdf
uv run python tools/query_courtlistener.py download "recap/..." /tmp/doc.pdf --extract-text

# Full opinion text by opinion ID or cluster ID
uv run python tools/query_courtlistener.py opinion 12345678 --lines 500
# Auto mode checks the cluster endpoint first because cluster/opinion numeric IDs
# overlap. For a known raw opinion API ID, add: --id-type opinion

# Opinion cluster details (citation count, precedential status)
uv run python tools/query_courtlistener.py cluster 98765
```

### Citation & Reference Commands

```bash
# Citation graph (what this opinion cites and what cites it)
uv run python tools/query_courtlistener.py citations 98765 --limit 50

# Resolve citation text to CourtListener cluster IDs
uv run python tools/query_courtlistener.py resolve-cite "521 U.S. 702"
```

### Judge Research Commands

```bash
# Search judges by name
uv run python tools/query_courtlistener.py judge "Preska" --limit 10

# Full career timeline (positions, education, political affiliations)
uv run python tools/query_courtlistener.py career "Loretta Preska"

# Financial disclosures
uv run python tools/query_courtlistener.py disclosures --person-id 1234
uv run python tools/query_courtlistener.py disclosures --person-id 1234 --year 2022

# Investment holdings search (by company/description)
uv run python tools/query_courtlistener.py investments "Apollo Global" --limit 20
uv run python tools/query_courtlistener.py investments "JPMorgan" --person-id 1234

# Travel reimbursements (by source organization)
uv run python tools/query_courtlistener.py reimbursements "Federalist Society" --limit 20
uv run python tools/query_courtlistener.py reimbursements "Heritage Foundation" --person-id 1234
```

### FJC Integrated Database

```bash
# Federal case metadata (plaintiff, defendant, nature of suit, disposition)
uv run python tools/query_courtlistener.py fjc --plaintiff "United States" --nos 470 --after 2020-01-01
uv run python tools/query_courtlistener.py fjc --defendant "Epstein" --limit 50
```

FJC searches use one bounded request attempt because this upstream endpoint can
be much slower than the other CourtListener APIs. A timeout exits nonzero with
a concise diagnostic; narrow the party prefix or add a date range before retrying.

### Known Quirks

- The `opinion` command tries the opinion ID first, then falls back to treating it as a cluster ID (fetches first sub-opinion from the cluster).
- `download --extract-text` prefers PyMuPDF and automatically falls back to
  Poppler `pdftotext`. It exits nonzero if neither extractor works and warns
  when the resulting text density indicates that the PDF likely needs OCR.
- The `search` command supports field operators: `party:`, `firm:`, `attorney:`, `assignedTo:`, `docketNumber:` -- these can be combined with free text.
- `--semantic` enables vector-based semantic search (slower but finds conceptual matches).
- Court codes use CourtListener format: `nysd` (S.D.N.Y.), `ca2` (2nd Circuit), `scotus`, etc.
- The `career` command chains multiple API calls (person, positions, education, affiliations) -- budget for 4+ requests per invocation.

## E.D. Virginia bankruptcy CourtListener/RECAP archive

`query_edva_bankruptcy.py` provides a court-specific lifecycle adapter for
E.D. Virginia bankruptcy records available through CourtListener and the RECAP
archive. An exact case lookup uses the court's docket number; docket-entry and
document-metadata reads use a positive CourtListener docket ID. The adapter
keeps archive coverage explicit: available RECAP documents and metadata-only
documents are distinct states, and a blocked or empty archive result is not an
official finding that the docket is empty or that the case is sealed.

```bash
# Direct archive reads and route inventory
uv run python tools/query_edva_bankruptcy.py sources \
  --output "$WORKDIR/edva-bankruptcy-sources.json"
uv run python tools/query_edva_bankruptcy.py case 05-39367 \
  --output "$WORKDIR/edva-bankruptcy-case.json"
uv run python tools/query_edva_bankruptcy.py entries 49921079 \
  --output "$WORKDIR/edva-bankruptcy-entries.json"
uv run python tools/query_edva_bankruptcy.py probe \
  --output "$WORKDIR/edva-bankruptcy-probe.json"

# Shared exact-case, entry/document-metadata, and discovery routes
uv run python tools/query_state_courts.py case 05-39367 \
  --source us-va-ed-bankruptcy-pacer-recap \
  --jurisdiction 51 --court-id us-bankr-edva \
  --output "$WORKDIR/edva-bankruptcy-shared-case.json"
uv run python tools/query_state_courts.py docket 49921079 \
  --source us-va-ed-bankruptcy-pacer-recap \
  --jurisdiction VA --court-id vaeb \
  --output "$WORKDIR/edva-bankruptcy-shared-docket.json"
uv run python tools/query_state_courts.py documents 49921079 \
  --source us-va-ed-bankruptcy-pacer-recap \
  --jurisdiction US-VA --court-id us-bankr-edva --ingest \
  --output "$WORKDIR/edva-bankruptcy-shared-documents.json"
uv run python tools/query_state_courts.py discovery \
  --source us-va-ed-bankruptcy-pacer-recap \
  --jurisdiction VA \
  --output "$WORKDIR/edva-bankruptcy-shared-sources.json"

# Lifecycle monitor: two docket sentinels, one entry page each, and the
# read-only RECAP Fetch OPTIONS contract
uv run python tools/public_records_monitor.py run \
  us-va-ed-bankruptcy-pacer-recap \
  --output "$WORKDIR/edva-bankruptcy-monitor.json"
```

The monitor performs five bounded requests using `GET` and `OPTIONS`: two
known docket identities, one entry page for each docket, and the RECAP Fetch
field contract. It does not create a fetch or prayer request and does not
retrieve a document. Direct `fetch-docket`, `fetch-document`, `fetch-status`,
and `pray` commands remain explicit adapter operations rather than shared or
monitor routes.

RECAP is a contributed public archive, not the official PACER docket. Official
PACER/CM/ECF access, the PACER Case Locator, an E.D. Virginia Clerk copy
request, courthouse public-access terminals, and transferred closed-case files
available through the court, a Federal Records Center, or the National
Archives answer overlapping questions through separate records and access
paths; they are not represented as equivalent copies of the RECAP dataset.

## DOJ Epstein court-record release corpus

`query_doj_court_records.py` indexes the case-grouped Court Records section of
DOJ's consolidated Epstein disclosures and follows each case page's native
pagination to its published PDFs. The publisher is DOJ; the named courts remain
the authorities for their underlying dockets. A DOJ case group is therefore a
released-document collection, not a claim that every docket entry is present.

```bash
# Direct release-corpus reads
uv run python tools/query_doj_court_records.py index \
  --query "United States v. Epstein" \
  --output "$WORKDIR/doj-court-case-groups.json"
uv run python tools/query_doj_court_records.py case \
  "https://www.justice.gov/epstein/doj-disclosures/court-records-united-states-v-epstein-no-119-cr-00490-sdny-2019" \
  --output "$WORKDIR/doj-court-documents.json"
uv run python tools/query_doj_court_records.py sources \
  --output "$WORKDIR/doj-court-routes.json"

# Shared corpus search and exact case-page document listing
uv run python tools/query_state_courts.py search \
  "United States v. Epstein" \
  --source us-doj-epstein-court-records \
  --output "$WORKDIR/doj-court-shared-search.json"
uv run python tools/query_state_courts.py documents \
  "https://www.justice.gov/epstein/doj-disclosures/court-records-united-states-v-epstein-no-119-cr-00490-sdny-2019" \
  --source us-doj-epstein-court-records \
  --output "$WORKDIR/doj-court-shared-documents.json"

# Three-request lifecycle probe: index, first case page, five PDF bytes
uv run python tools/public_records_monitor.py run \
  us-doj-epstein-court-records \
  --output "$WORKDIR/doj-court-monitor.json"
```

The shared operations are `search`, `documents`, `discovery`, and `probe`.
They deliberately do not expose `case` or `docket`, and these release rows are
not projected into the normalized case sidecar. Document identity uses the
published EFTA identifier when available and otherwise retains the canonical
case slug plus filename; the exact official PDF URL remains provenance.
Omitting `--limit` returns every current index match or exhausts native case
pagination. Omitted pacing is `0.0` seconds in both direct and shared DOJ
routes; an explicit caller-selected `--minimum-interval` on the shared route
is preserved. A limited document traversal returns a checksum-protected v2
cursor bound to the canonical case, current page, page fingerprint, and
offset.

`recover` checks a former indexed PDF against the current case listing and
accepts only an exact EFTA or filename match as a replacement. `download`
validates PDF bytes and records a SHA-256 receipt. PACER/CM/ECF, CourtListener
and RECAP, the clerk for the court named by a release, Wayback snapshots, and
the local EFTA/OCR corpus remain separately attributable routes with different
coverage and evidentiary roles. The three monitor reads keep stable source,
identity, schema, cursor, route, and request contracts separate from rolling
release counts, first-page shape, and PDF response metadata. An exact mapped
release document can be cited as `[DOJCOURT:EFTA02824136]`.

## New York OCA attorney registrations

`query_ny_attorneys.py` searches the Office of Court Administration's official
quarterly NY Open Data snapshot (`eqw2-r5nb`). It supports person and structured
field searches, whole organization-name searches, and exact lookup by the
source's stable `registration_number`. Anonymous access works directly; an
optional `NY_OPEN_DATA_APP_TOKEN` can be supplied through the environment.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Inspect coverage and the separately attributable complementary routes
uv run python tools/query_ny_attorneys.py sources \
  --output "$WORKDIR/ny-attorney-sources.json"

# Direct searches preserve a company value such as "ACME HOLDINGS, LLC"
# as one publisher organization field.
uv run python tools/query_ny_attorneys.py search "Example Attorney" \
  --output "$WORKDIR/ny-attorney-name.json"
uv run python tools/query_ny_attorneys.py search \
  --company "ACME HOLDINGS, LLC" \
  --output "$WORKDIR/ny-attorney-organization.json"
uv run python tools/query_ny_attorneys.py registration 2064509 \
  --output "$WORKDIR/ny-attorney-registration.json"

# The HONEST shared route exposes registration search, exact detail,
# discovery, and probe only.
uv run python tools/query_state_courts.py search "ACME HOLDINGS, LLC" \
  --source us-ny-oca-attorney-registrations \
  --jurisdiction NY --entity-kind organization \
  --output "$WORKDIR/ny-attorney-shared-search.json"
uv run python tools/query_state_courts.py detail 2064509 \
  --source us-ny-oca-attorney-registrations \
  --jurisdiction 36 \
  --output "$WORKDIR/ny-attorney-shared-detail.json"
uv run python tools/query_state_courts.py discovery \
  --source us-ny-oca-attorney-registrations \
  --jurisdiction US-NY \
  --output "$WORKDIR/ny-attorney-shared-discovery.json"
uv run python tools/query_state_courts.py probe \
  --source us-ny-oca-attorney-registrations \
  --jurisdiction "New York" \
  --output "$WORKDIR/ny-attorney-shared-probe.json"
```

Searches without `--limit` traverse all matching registrations. Limited
searches return a checksum-protected v2 cursor bound to the criteria, declared
schema, quarterly `rowsUpdatedAt`, matching total, and offset. A continuation
therefore remains tied to the same query snapshot.

The lifecycle monitor runs a five-request lifecycle probe: initial metadata,
sentinel count, exact sentinel query, final metadata, and the current statewide
count. Dataset identity, registration identity, declared and response schemas,
cursor semantics, and complementary-route identity form the stable contract.
The row total, `rowsUpdatedAt`, and sentinel contents remain rolling
observations.

```bash
uv run python tools/public_records_monitor.py run \
  us-ny-oca-attorney-registrations \
  --output "$WORKDIR/ny-attorney-monitor.json"
```

Registration rows are not cases, dockets, or filings and are not projected
into the normalized case store. Keep these OCA representations distinct:

- The open dataset is the scalable quarterly registration, status, admission,
  office, and organization snapshot.
- The interactive Attorney Directory is a current presentation that may show
  changes after the latest open-data refresh.
- 22 NYCRR 118.2 describes separately delivered written-request data,
  including name and geographic lists.
- Appellate Division pages publish discipline decisions, suspensions,
  reinstatements, and registration notices as separate records.
- NYSCEF publishes case appearances and filed documents under its own source
  identity.

## query_nyscef.py — New York State Courts Electronic Filing

NYSCEF exposes a server-rendered guest portal rather than a public search API.
`query_nyscef.py` reads its route from the central source catalog. The current
review returns a structured `human_required` result with the requested criteria
and official URLs. Route facts can be updated centrally, and the same commands
consume them without a second environment-variable switch.

Canonical official pages:

- Guest search: <https://iapps.courts.state.ny.us/nyscef/CaseSearch>
- Terms of Use: <https://iappscontent.courts.state.ny.us/NYSCEF/live/termsOfUse.htm>
- FAQ: <https://iappscontent.courts.state.ny.us/nyscef/live/faq.htm>
- Court-record help: <https://www.nycourts.gov/help/representing-yourself-court/getting-court-records-case-information>

```bash
# Search using the current catalog route
uv run python tools/query_nyscef.py search "Jeffrey Epstein" \
  --county "New York" --after 2019-01-01 \
  --output "$WORKDIR/nyscef-human-action.json"

# Case and document routes
uv run python tools/query_nyscef.py case 156728/2019 \
  --output "$WORKDIR/nyscef-case-action.json"
uv run python tools/query_nyscef.py documents OPAQUE_DOCKET_ID \
  --output "$WORKDIR/nyscef-documents-action.json"
```

### Access notes

- Inspect the current decision with
  `uv run python tools/public_records_catalog.py show us-ny-nyscef --json`.
- Public search works by HTML form POST -> redirect -> server-side result pages. No public JSON endpoint was confirmed during discovery.
- Search results link into `DocumentList?docketId=...` pages, `CaseDetails?docketId=...` pages, and `ViewDocument?docIndex=...` PDF endpoints.
- Many cases and filings remain unavailable to guests; NYSCEF shows those as restricted rows rather than returning case detail.

### Local filing-body extraction and search

`query_nyscef_fulltext.py` starts after acquisition. It accepts a
`query_nyscef.py` document-list manifest (or compatible supplied rows) and
the corresponding PDFs, normalizes case/document identities, extracts
page text, applies targeted OCR to weak pages, and incrementally indexes the
results in SQLite FTS5.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_nyscef_fulltext.py sources \
  --output "$WORKDIR/nyscef-fulltext-sources.json"
uv run python tools/query_nyscef_fulltext.py probe \
  --output "$WORKDIR/nyscef-fulltext-probe.json"
uv run python tools/query_nyscef_fulltext.py normalize \
  "$WORKDIR/nyscef-documents.json" \
  --output "$WORKDIR/nyscef-normalized.json"
uv run python tools/query_nyscef_fulltext.py index \
  "$WORKDIR/nyscef-documents.json" \
  --pdf-dir "$WORKDIR/filings" \
  --database "$WORKDIR/nyscef-fulltext.db" \
  --output "$WORKDIR/nyscef-index-result.json"
uv run python tools/query_nyscef_fulltext.py search \
  "$WORKDIR/nyscef-fulltext.db" '"EXAMPLE HOLDINGS LLC"' \
  --mode fts --mention-name "EXAMPLE HOLDINGS LLC" \
  --output "$WORKDIR/nyscef-fulltext-hits.json"
uv run python tools/query_nyscef_fulltext.py stats \
  "$WORKDIR/nyscef-fulltext.db" \
  --output "$WORKDIR/nyscef-fulltext-stats.json"
```

Case identities use the court and raw case number; document identities add
the NYSCEF document number or index; artifact versions use the PDF SHA-256.
Each page hit returns `<record-identity>:p<page-number>` evidence. A searched
name is labeled `listed_party`, `non_party_candidate`, or
`party_list_unavailable` from the manifest's party list, which makes large
filing sets easier to triage without treating every textual mention as a case
party.

## New York Law Reporting Bureau and public-notice complements

`query_ny_law_reports.py` discovers official New York Law Reporting Bureau
decisions from the Selected Trial and Other Courts and Commercial Division
RSS, current indexes, and monthly archive pages. It can retrieve one full HTML
opinion or search the opinion bodies discovered within one selected source
window.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Current source feeds and all advertised archive months
uv run python tools/query_ny_law_reports.py rss --collection all \
  --output "$WORKDIR/ny-law-reports-rss.json"
uv run python tools/query_ny_law_reports.py archives --collection all \
  --output "$WORKDIR/ny-law-reports-archives.json"

# Current or one source-native monthly index
uv run python tools/query_ny_law_reports.py index --collection other \
  --output "$WORKDIR/ny-law-reports-current.json"
uv run python tools/query_ny_law_reports.py index --collection commercial \
  --year 2026 --month 6 \
  --output "$WORKDIR/ny-commercial-june-2026.json"

# Exact official opinion and body search inside one selected window
uv run python tools/query_ny_law_reports.py opinion 2026_26113 \
  --output "$WORKDIR/ny-law-report-opinion.json"
uv run python tools/query_ny_law_reports.py search "fraudulent conveyance" \
  --collection commercial --year 2026 --month 6 --match-mode phrase \
  --output "$WORKDIR/ny-commercial-body-search.json"
uv run python tools/query_ny_law_reports.py sentinel \
  --output "$WORKDIR/ny-law-reports-sentinel.json"
```

The adapter returns every row from the selected RSS, current index, or monthly
archive page by default; `--limit` is optional and has no adapter-defined
maximum. The source partitions history as one index page per month rather than
numbered result pages. It preserves caption, court, decision date, citation,
judge, index number, official URL/evidence reference, body text, digest,
parties, counsel, and raw publication metadata. Linked PDFs are retained as
document routes but are counted separately from searchable HTML bodies.

Law Reporting Bureau opinion text is an official judicial publication. It can
identify parties, counsel, NYSCEF document references, arguments, procedural
history, rulings, and quoted filing language, but it is not the underlying
docket or a repository of every filed document. CourtListener adds broader
opinion, citation, docket, and RECAP discovery. NYSCEF and clerk-copy routes
remain the sources for docket entries and filed documents. Infrastructure
request #90 therefore has implemented official opinion-body coverage and
useful filing pivots, while general NYSCEF filing-body coverage remains
incomplete.

`query_ny_column.py` searches New York newspaper public notices published
through Column. Notices often expose party aliases, index numbers, property
descriptions, lien or foreclosure facts, hearing dates, filer identifiers, and
publication provenance that can seed a court or property search.

```bash
# Full-text search; all source-reported pages return by default
uv run python tools/query_ny_column.py search "EXAMPLE HOLDINGS LLC" \
  --output "$WORKDIR/ny-column-notices.json"

# Partition a broad search with repeatable source facets
uv run python tools/query_ny_column.py search "mortgage" \
  --start-date 2026-01-01 --end-date 2026-06-30 \
  --county "New York" --county "Kings" \
  --notice-type "Foreclosure Sale" \
  --newspaper "New York Law Journal" --filer "<FILER_ID>" \
  --output "$WORKDIR/ny-column-foreclosures.json"

uv run python tools/query_ny_column.py sentinel \
  --output "$WORKDIR/ny-column-sentinel.json"
```

Column uses one-indexed pages and displays at most 10,000 matches for a
partition. The adapter retrieves all source-reported pages by default;
`--limit` is optional. Date ranges and repeatable county, notice-type,
newspaper, and filer filters create narrower partitions when the displayed
ceiling is reached. Each result preserves full notice text, linked PDF,
notice/filer IDs, type, newspaper, publication date, county/state, source URL,
and raw metadata. A Column item is newspaper public-notice evidence and a
discovery pivot, not a court filing or complete docket.

## query_military_justice.py — Military Justice Appellate Courts

Unified scraper for the U.S. Court of Appeals for the Armed Forces (CAAF) and
the four service Courts of Criminal Appeals (ACCA, NMCCA, AFCCA, CGCCA). These
courts publish dockets and opinions on disparate static sites and are NOT in
CourtListener — Eddie Gallagher's 2019 court-martial, for example, has no
CourtListener record.

**Killer feature**: the `attorney` subcommand cross-searches all reachable
opinion PDFs for a civilian counsel name and returns every case where that
name appears with a context snippet.

### Subcommands

```bash
# Cross-court keyword search (uses cached indices)
uv run python tools/query_military_justice.py search "Bergdahl" --output /tmp/x.json
uv run python tools/query_military_justice.py search "Bergdahl" --courts CAAF,ACCA --output /tmp/x.json
uv run python tools/query_military_justice.py search "Edward Gallagher" --refresh --output /tmp/x.json

# CAAF October Term opinion index — single year or 'current'
uv run python tools/query_military_justice.py caaf-dockets 2024 --output /tmp/x.json
uv run python tools/query_military_justice.py caaf-dockets current --output /tmp/x.json

# CAAF opinion PDF — extracts counsel block, panel, decision date, disposition
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --output /tmp/x.json
uv run python tools/query_military_justice.py caaf-opinion 24-0156/AR --full-text --output /tmp/x.json

# Service-court searches
uv run python tools/query_military_justice.py acca-search "Burke"   --output /tmp/x.json
uv run python tools/query_military_justice.py afcca-search "Smith"  --output /tmp/x.json
uv run python tools/query_military_justice.py nmcca-search "Gallagher" --output /tmp/x.json
uv run python tools/query_military_justice.py cgcca-search "Mieres" --output /tmp/x.json

# Killer feature — find every reachable opinion where <NAME> is counsel
uv run python tools/query_military_justice.py attorney "Conway" --pdf-limit 200 --output /tmp/x.json
uv run python tools/query_military_justice.py attorney "Parlatore" --skip-refresh --output /tmp/x.json

# One-docket detail
uv run python tools/query_military_justice.py case-detail "24-0156/AR" --output /tmp/x.json
```

### Court Coverage

| Court | Site | Coverage | Notes |
|-------|------|----------|-------|
| **CAAF** | armfor.uscourts.gov | Full | Term pages parsed (2018-2026 verified); Daily Journal monthly pages parsed for docket actions; opinion PDFs extracted via `pypdf` |
| **AFCCA** | afcca.law.af.mil | Full | Public opinion index parsed; docket page has no attorney info |
| **ACCA** | jagcnet.army.mil/ACCALibrary | Full | OC/MO/SFA/SD opinion lists parsed; URLs return PDFs despite not ending in `.pdf` |
| **NMCCA** | jag.navy.mil/.../nmcca/opinions/ | Limited | Server-rendered POST search form (Sitecore). Tool fetches index page only. Cross-court `attorney` finds NMCCA-origin cases via CAAF appeal records. |
| **CGCCA** | uscg.mil/.../CGCCA-Opinions/ | Limited | 403 from non-browser User-Agents (Akamai/CDN). Use `--user-agent` override or query FindLaw mirror at caselaw.findlaw.com |

### Caching & Rate Limiting

- All HTTP responses cached in `datasets/military_justice_cache.db` (SQLite WAL).
- Three tables: `pages` (raw HTTP), `pdf_text` (extracted PDF text), `docket_index` (parsed metadata).
- Default rate limit is 1 req/sec per host; configurable via `--rate-limit 0.5`.
- `--no-cache` bypasses caching for fresh fetches.

### Counsel Extraction

Opinions usually have a "For Appellant" / "For Appellee" block listing both
military counsel ("Captain Anthony J. Scarpati") and civilian counsel
("Daniel Conway, Esq."). The PDF-text extractor parses these blocks
heuristically and exposes them in the `counsel` field of `caaf-opinion`,
`case-detail`, and `attorney` outputs. Civilian names typically appear without
rank prefixes; military counsel names start with rank words (Captain, Major,
Colonel, Commander, etc.).

### Known Limitations

- NMCCA's search form is POST-only; full search requires Playwright. Documented in `--help` and `nmcca-search` output.
- CGCCA's CDN blocks bare-UA HTTP requests with 403. Documented in `--help` and `cgcca-search` output.
- Counsel-extraction heuristics may miss names embedded in continuous prose; the `attorney` command falls back to a substring check before reporting a hit.

## query_hudoc.py — ECHR Case Database

Searches European Court of Human Rights judgments, decisions, and communications (1959-present). ~20,000 judgments and ~100,000 decisions.

```bash
# Full-text search
uv run python tools/query_hudoc.py search "Ron Soffer"
uv run python tools/query_hudoc.py search "Soffer, avocat" --limit 20

# Case detail by item ID
uv run python tools/query_hudoc.py case 001-99808

# Lookup by application number
uv run python tools/query_hudoc.py appno "34868/03"

# Filter by respondent state
uv run python tools/query_hudoc.py respondent ROU --limit 50

# Full case text (HTML-to-text conversion)
uv run python tools/query_hudoc.py text 001-99808
```

### Known Quirks

- Uses an undocumented REST API at `hudoc.echr.coe.int/app/query/results`.
- Respondent codes are ISO 3166-1 alpha-3 (e.g., `ROU` for Romania, `GBR` for UK, `TUR` for Turkey).
- Rate limiting is polite (0.5s between requests) with retry on 429.
- Results include fields: `itemid`, `docname`, `respondent`, `extractedappno`, `conclusion`, `kpdate`.
- The `text` command fetches the HTML body and converts to plain text. Useful for searching specific language in judgments (e.g., counsel names that appear in the body but not metadata).

## query_military_corrections.py — DoD BCMR/BCNR Reading Room

Crawls the Department of Defense Boards of Review Reading Room (hosted by the Air Force at `boards.law.af.mil`) which mirrors decisional documents for all four service correction boards: AFBCMR (Air Force, 1984-present), ABCMR (Army, 1997-present), BCNR (Navy/Marines, 1998-present), and CGBCMR (Coast Guard, organized by topic). Decisions are redacted PDFs; petitioner counsel is sometimes named on the face of the PDF and sometimes redacted. Counsel is never exposed in index metadata, so a full-text scan over downloaded PDFs is the only way to identify a specific firm.

**Cache:** `.cache/military_corrections.db` (SQLite, WAL mode, FTS5). PDFs at `.cache/military_corrections/<service>/<bucket>/<filename>.pdf`. Reset with `--reset-cache`.

```bash
# Refresh the index of available decisions (no PDFs yet)
uv run python tools/query_military_corrections.py crawl-index --service all --output /tmp/mc-index.json
uv run python tools/query_military_corrections.py crawl-index --service afbcmr --year-from 2020 --year-to 2024

# Download a year's decisions for one service (or one CG topic folder)
uv run python tools/query_military_corrections.py download --service afbcmr --year-from 2024 --year-to 2024
uv run python tools/query_military_corrections.py download --service cgbcmr --bucket "Officer Promotion and DOR"
uv run python tools/query_military_corrections.py download --service bcnr --bucket CY2024 --limit 100

# Extract text into local SQLite
uv run python tools/query_military_corrections.py index-text --service all
uv run python tools/query_military_corrections.py index-text --service bcnr --reindex

# Killer feature: find decisions where a specific counsel appears
uv run python tools/query_military_corrections.py attorney "Parlatore" --output /tmp/parlatore.json
uv run python tools/query_military_corrections.py attorney "Parlatore Law Group" --service bcnr

# Topic search across the indexed corpus (FTS5 phrase search)
uv run python tools/query_military_corrections.py keyword "promotion list" --output /tmp/promo.json
uv run python tools/query_military_corrections.py keyword "selection board"
uv run python tools/query_military_corrections.py keyword "fitness report"

# One-decision lookup (works on docket OR fragment of the PDF filename)
uv run python tools/query_military_corrections.py decision afbcmr BC-2024-00035
uv run python tools/query_military_corrections.py decision bcnr NR20240000001

# Cache state
uv run python tools/query_military_corrections.py stats
```

### Service IDs and structure

| ID | Board | Bucket kind | Earliest | PDF naming |
|----|-------|-------------|----------|------------|
| `afbcmr` | Air Force BCMR | calendar year (`CY1984`–`CY2024`) | 1984 | `BC-YYYY-NNNNN BCYYYYNNNNN.pdf` |
| `abcmr` | Army BCMR | calendar year (`CY1997`–`CY2024`) | 1997 | `ARYYYYNNNNNNN_Redacted.pdf` |
| `bcnr` | Navy/Marines BCNR | calendar year (`CY1998`–`CY2024`) | 1998 | `NRYYYYNNNNNNN_Redacted.pdf` |
| `cgbcmr` | Coast Guard BCMR | topic categories (e.g. "Officer Promotion and DOR") | by topic | `<docket> <category>_Redacted.pdf` |

The Coast Guard board uniquely organizes by *topic* rather than year, so `--year-from`/`--year-to` are ignored and you select with `--bucket "<Category>"`. Categories include `Officer Promotion and DOR`, `Officer Performance and OERs`, `Discharge and Reenlistment Codes`, `NJP and Court-Martial`, `Discrimination and Retaliation`, etc.

### Volume estimates (single year of decisions)

Roughly 685 AFBCMR / 4,250 ABCMR / 3,510 BCNR decisions per recent year, plus ~2,700 CGBCMR decisions across all topic categories combined. A full historical crawl is well into the hundreds of thousands of PDFs — use `--year-from/--year-to` or `--bucket` to scope, and the tool's incremental cache (`local_path IS NULL` filter) means subsequent `download` runs only fetch missing files.

### Known Quirks

- The Reading Room is plain HTML directory listings (no API). The tool fetches the index pages, parses anchor tags, and persists the catalog into SQLite *before* downloading PDFs, so you can crawl the metadata cheaply, then download lazily.
- Default rate limit is 2.0s between requests (0.5 req/sec). Configurable via the global `--delay N` flag, which must precede the subcommand.
- `attorney` and `keyword` use SQLite FTS5 phrase search with porter+unicode61 tokenization, falling back to `LIKE` if FTS returns no rows. Both return up to 3 ~180-char excerpts per match.
- The tool pulls a docket identifier from the PDF filename via service-specific regex; falls back to the bare filename stem if the pattern misses.
- The Navy/SECNAV BCNR site (`secnav.navy.mil/mra/bcnr`) blocks automated requests behind an F5/BIG-IP defender; the Air Force-hosted mirror is the canonical machine-readable copy.
- ARBA (`arba.army.pentagon.mil`) and the Coast Guard Legal page (`uscg.mil/Resources/Legal/...`) are unreachable from automated fetchers (timeouts / 403). Again, the AF-hosted mirror is the workaround.
- PDF text extraction uses PyMuPDF when available. CourtListener downloads also
  support Poppler `pdftotext` as a fallback. Some redacted PDFs are scanned
  images with no useful text layer — those rows show `text_chars=0` and won't
  appear in keyword/attorney searches. OCR is out of scope for this tool.
- Before using `ocrmypdf --skip-text` on a mixed court exhibit, inspect each
  page's extracted text. A tiny footer or court page number makes an otherwise
  image-only page count as text-bearing and can skip the scanned body. For a
  bounded affected excerpt, use `--force-ocr` and verify the replacement text
  against the rendered pages.

## Skills Using These Tools

| Skill | Tools Used |
|-------|-----------|
| `/analyze-case` | `query_courtlistener.py` (docket, recap-search, opinion, citations, party), `query_state_courts.py` (case/docket/documents), `public_records_actions.py` (catalog routes), `query_military_justice.py` (case-detail, caaf-opinion) |
| `/deep-investigate` (Agent C) | `query_courtlistener.py`, `query_state_courts.py`, `public_records_search_plan.py`, `public_records_actions.py`, `query_military_justice.py` |
| `/investigate-person` | `public_records_search_plan.py`, `query_state_courts.py`, `query_courtlistener.py`, `query_hudoc.py`, `query_military_justice.py`, `public_records_entity_candidates.py` |
| `/systemic-analysis` | `query_courtlistener.py` (fjc, investments, reimbursements) |
| `/investigate-person` (mil. counsel) | `query_military_corrections.py attorney "<NAME>"` to surface BCMR/BCNR petitions where a target appears as petitioner counsel |
| `/deep-investigate` (mil. service members) | `query_military_corrections.py keyword`, `decision` for promotion-list challenges, OER/EER corrections, separation appeals |

## Common Investigation Patterns

### Litigation history for a person/entity
1. `party "Entity Name"` -- find all cases
2. `docket <ID>` -- get case details for interesting hits
3. `recap-search "Entity Name" --court nysd` -- find specific filings
4. `download <URL> --extract-text` -- get document text

### New York state-court search
1. `public_records_search_plan.py "Entity Name" --jurisdiction 36` -- build the property/recorder/court plan
2. `query_state_courts.py sources --jurisdiction 36` -- inspect the current catalog routes and capabilities
3. `query_state_courts.py search "Entity Name"` -- search normalized retained observations
4. `query_nyscef.py search "Entity Name"` -- return the current NYSCEF route with the requested criteria
5. `query_ny_law_reports.py search "Entity Name" --feed` -- search official current opinion bodies and extract case/document pivots
6. `query_ny_column.py search "Entity Name"` -- search public-notice text for index numbers, property, filer, and hearing pivots
7. `public_records_actions.py plan us-ny-nyscef --operation fetch_document --selector "<CASE/DOCUMENT>"` -- render the concrete source action for the underlying filing

### Judicial conflict-of-interest check
1. `judge "Judge Name"` -- get person ID
2. `career "Judge Name"` -- positions, education, affiliations
3. `disclosures --person-id <ID>` -- financial disclosures
4. `investments "Company Name" --person-id <ID>` -- specific holdings
5. `reimbursements "Organization" --person-id <ID>` -- travel/gifts

### Military counsel / promotion-board practice mapping
1. `query_military_corrections.py crawl-index --service all` -- refresh the catalog
2. `query_military_corrections.py download --service bcnr --year-from 2018 --year-to 2024` -- pull recent Navy decisions (or a specific year/bucket of interest)
3. `query_military_corrections.py index-text --service all` -- extract text into FTS5
4. `query_military_corrections.py attorney "Parlatore"` -- find decisions where the firm appears as petitioner counsel
5. `query_military_corrections.py keyword "promotion list"` -- correlate counsel hits with promotion-list adjudications
6. `query_military_corrections.py decision <SVC> <DOCKET>` -- pull metadata + text excerpt for any hit

### Citation chain analysis
1. `opinions "topic" --court ca2` -- find relevant opinions
2. `cluster <ID>` -- get cluster details and sub-opinions
3. `citations <cluster_id>` -- see what it cites and what cites it
4. `resolve-cite "521 U.S. 702"` -- resolve a specific citation
