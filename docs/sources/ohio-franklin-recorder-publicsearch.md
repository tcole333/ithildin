# Franklin County Recorder PublicSearch

Verified 2026-07-31 against the anonymous Cloud Search portal linked by the
[Franklin County Recorder](https://www.franklincountyohio.gov/Agency-Directory/Recorder/Real-Estate/Public-Records-Search).
The shared standalone adapter is `tools/query_govos_recorders.py`; the source
identity is `us-oh-franklin-county-recorder-publicsearch`.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_govos_recorders.py search \
  --source us-oh-franklin-county-recorder-publicsearch \
  202607290091301 --output "$WORKDIR/franklin-recorder-search.json"

uv run python tools/query_govos_recorders.py document \
  --source us-oh-franklin-county-recorder-publicsearch \
  323279115 --output "$WORKDIR/franklin-recorder-detail.json"

uv run python tools/query_govos_recorders.py page \
  --source us-oh-franklin-county-recorder-publicsearch \
  323279115 1 "$WORKDIR/franklin-recorder-page-1.png" \
  --output "$WORKDIR/franklin-recorder-page-1.json"

uv run python tools/query_govos_recorders.py probe \
  --source us-oh-franklin-county-recorder-publicsearch \
  --output "$WORKDIR/franklin-recorder-probe.json"
```

## Verified transport

The Recorder's official information page links both the current Cloud Search
portal and a legacy CountyFusion portal. It says that neither requires
registration and that all Recorder records are available in both systems. The
Cloud Search route shares the GovOS/Kofile Neumo protocol already used by the
platform's other `publicsearch.us` tenants:

1. `GET https://franklin.oh.publicsearch.us/` hydrates the anonymous tenant
   configuration and issues the paired session cookies.
2. `wss://franklin.oh.publicsearch.us/ws` accepts versioned search and exact
   document-detail messages for department `RP`.
3. Exact detail supplies session-signed page URLs; the adapter refreshes detail
   in the same anonymous session before fetching a caller-selected PNG page.

The 2026-07-31 bootstrap reported tenant `39049`, one `RP` department, a
source-advertised recorded-date range from `16000101` through `20260730`, and a
certified-through date of `2026-07-29`. A one-day search for 2026-07-29
reported 592 rows and returned a native next offset after a three-row request,
confirming the existing source-native offset contract. Searching exact
instrument `202607290091301` returned one row.

## Identity, paging, and artifacts

The reusable adapter keeps Franklin's county source identity distinct from the
other GovOS tenants. Canonical instrument identity uses the department-qualified
native document ID (`RP:<doc_id>`). The Recorder's instrument number, `rsId`,
recording date, document type, parties, legal descriptions, parcel text, and
marginal references remain source fields and join candidates.

Search uses native offsets and reports the publisher's total. With no
`--limit`, the adapter follows every native offset; a caller-selected limit
returns that slice and a continuation bound to source, department, search
criteria, OCR/date mode, workspace, publisher total, and protocol response
type. Resume it with `--cursor`. Both modes retain the source, department,
search mode, query, and date range. Quick search covers indexed
party names, subdivisions, document types, and document numbers. Advanced
search supports recorded-date ranges and optional full-text OCR search.

Search-index and exact-detail responses are retained as separate raw
occurrences for the same department-qualified document identity. The
normalized instrument prefers document detail over the sparser index and uses
retrieval time within the same representation, preserving known instrument,
party, and artifact fields when later source rows omit them.

Exact detail may expose multiple parties, legal descriptions, marginal
references, return-address text, an image ID, and page count. A fetched page is
a PNG representation nested under its recorded instrument, not another
instrument observation. Session tokens and signed URLs are transport values;
the persistent locator is the official detail URL plus department and native
document ID.

The live probe sentinel is instrument `202607290091301`, document ID
`323279115`. Exact detail reported `rsId=12176651`, document type `EA`, two
parties, image ID `305782565`, and six pages. Page one was a 38,393-byte PNG
with SHA-256
`2e7e562081d4fd72b0728d7996c2a098c45a8f9fdbdc8ae1cc05872727c7c228`.
The probe downloads that single page, not the complete six-page instrument.

## Evidence roles and complements

The Recorder states that its real-estate records include deeds, mortgages,
releases, liens, assignments, plats, leases, and partnerships. The index and
page image therefore add recorded-instrument and party evidence that the
existing Ohio parcel and assessment sources do not publish.

- `us-oh-franklin-county-auditor-property` supplies assessment-owner,
  valuation, parcel-detail, and transfer observations.
- `us-oh-ogrip-statewide-parcels` supplies standardized parcel identifiers,
  address observations, land use, area, geometry, and the local CAMA route.
- `us-oh-franklin-sheriff-realauction` supplies auction lifecycle observations
  and foreclosure case/parcel selectors.
- `us-oh-franklin-common-pleas-cio` supplies exact case metadata, parties,
  docket chronology, and selected public court filings.
- The Recorder-linked legacy CountyFusion portal is another access surface for
  the same Recorder corpus; it is useful for retrieval continuity rather than
  independent corroboration of a Cloud Search row.

Instrument parties describe how the Recorder indexed a filing. Parcel joins,
ownership conclusions, transfer conclusions, and case relationships can be
evaluated against the separately attributable Auditor, OGRIP, Sheriff, and
Clerk sources using exact published identifiers and dates.
