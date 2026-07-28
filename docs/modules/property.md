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
| `query_nc_property.py` | North Carolina OneMap parcel search | Official ArcGIS query service | Structured projection through generic ingestion |
| `query_cook_property.py` | Cook County historical parcel lookup | Official Socrata dataset | Structured projection through generic ingestion |
| `query_md_property.py` | Maryland statewide address and parcel lookup | Official Socrata dataset | Structured projection through generic ingestion |
| `query_fl_dor_property.py` | Florida DOR assessment-roll and GIS release discovery/transfer | Official bulk directories | Download destination selected by caller |
| `query_massgis_property.py` | MassGIS municipal release discovery/transfer | Official ArcGIS manifest and bulk archives | Download/extraction destination selected by caller |
| `query_harris_property.py` | Harris Central Appraisal District release discovery/transfer | Official JSON manifests and bulk ZIPs | Download destination selected by caller |
| `query_acris.py` | NYC recorder index and instrument records | Official Socrata datasets | Structured projection for document-shaped envelopes |
| `query_la_property.py` | East Baton Rouge assessment, parcel, and tax-default records | Official Socrata datasets | No |
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

## Initialize and inspect the control plane

```bash
uv run python tools/seed_public_records_catalog.py --json
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
uv run python tools/public_records_census.py stats --json
uv run python tools/public_records_census.py list --domain property --state FL \
  --output "$WORKDIR/fl-property-census.json"
uv run python tools/public_records_census.py claim --domain court --state WI \
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
`coverage_status`, and recorded gaps.

Priority remains three-dimensional: benefit from current investigative demand,
feasibility from the best cataloged capability path, and risk from uncertainty
or operational friction. The tool stores and explains those dimensions
separately rather than hiding them in a blended score.

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

These families preserve source-native fields and schema fingerprints while
leaving jurisdiction-specific normalization to the adapter. A caller-selected
result or transfer ceiling remains explicit in the query; otherwise the family
follows source pagination and the cataloged source facts.
There is no platform-wide `maximum_records_per_run` compatibility setting:
caller limits and endpoint page-size mechanics remain separate and visible.

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
```

ACRIS covers the Bronx, Brooklyn, Manhattan, and Queens, not Staten Island.
Recorder parties, assessor owners, and possible beneficial owners are stored as
different assertions. Cook County's Parcel Universe contains historical parcel,
classification, centroid, and district fields but no owner-name or street-
address columns. The Maryland dataset intentionally omits current-owner names;
the adapter keeps `owner_visibility.state=withheld_by_source` while retaining
its parcel, situs, assessment, deed, sale, and historical-grantor fields.

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

Miami-Dade Official Records commercial data services and Harris County Clerk
real-property products are also cataloged as recorder candidates. They are
source/action routes rather than implemented query adapters. Their entries
capture grantor/grantee or instrument search, images, bulk index/feed
capabilities, product cadence, account/fee facts, and stable source keys.

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
dry-run, or transfer it.

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
```

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

Harris Central Appraisal District publishes tax-year manifests for assessment,
ownership, improvement, deed, personal-property, and hearing extracts.
`query_harris_property.py` represents each published archive without requiring
a full download:

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
```

The catalog preserves the tax-year certification state, source update date,
artifact sizes, codebook, and probe fingerprints.

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
projection exists. Current projections cover NC OneMap, Cook County Parcel
Universe, Maryland assessments, and direct document-shaped ACRIS envelopes.
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
template carries only that source's matched jurisdictions.

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
for status, artifact, or schema changes.

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
