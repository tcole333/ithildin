# Connecticut Superior Court Civil/Family case lookup

Verified 2026-07-31. The standalone adapter uses source ID
`us-ct-superior-court-civil-family-case-lookup`.

The [Connecticut Judicial Branch case-lookup directory](https://www.jud.ct.gov/jud2.htm)
links the official
[Civil/Family Case Look-up](https://civilinquiry.jud.ct.gov/).
The implemented route combines party-name discovery, exact docket detail,
published case notices and transfer history, scheduled events, and filing
PDFs linked by the court's `DocumentNo`.

## Commands

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_connecticut_civil_family.py search EPSTEIN \
  --match exact \
  --output "$WORKDIR/ct-party-search.json"

uv run python tools/query_connecticut_civil_family.py case \
  FBT-CV-26-6159214-S \
  --output "$WORKDIR/ct-case.json"

uv run python tools/query_connecticut_civil_family.py document 32503295 \
  --docket FBT-CV-26-6159214-S \
  --pdf-output "$WORKDIR/ct-complaint.pdf" \
  --output "$WORKDIR/ct-complaint.json"

uv run python tools/query_connecticut_civil_family.py probe \
  --output "$WORKDIR/ct-probe.json"

uv run python tools/query_connecticut_civil_family.py routes --json
```

`--docket` on `document` is optional. When supplied, the adapter first
verifies that the selected case detail links the requested `DocumentNo`.

## Verified acquisition contract

Party search is an ASP.NET WebForms lifecycle:

1. GET `PartySearch.aspx` in a new session.
2. Preserve the live WebForms state and option inventory.
3. POST the caller's last/first name, match mode, location, Civil/Family
   category, case type, and sort selection in the same session.
4. Parse one published party-occurrence result display.

The portal publishes `Starts With`, `Contains`, `Is Equal To`, and `Soundex`
last-name modes. Exact surname `EPSTEIN` displayed `1-50 of 50` with 50 rows
and no pager. The adapter preserves those 50 occurrences as the
source-reported display slice and returns `partial` with
`source_display_slice`; it does not claim that the display is a complete
name index. With no caller `--limit`, all rows supplied by the portal are
returned. A caller-selected limit can resume within that display using a
query- and snapshot-bound adapter cursor. Resuming reacquires the same
publisher display and validates its anchor before applying the next local
window; it never represents a publisher continuation beyond row 50.

Every name-search occurrence is an
`unresolved_same_name_candidate`. It is a docket-discovery pivot, not an
identity match. The verified sentinel row is:

- published party name `EPSTEIN JEFFREY`;
- docket `FBT-CV-26-6159214-S`;
- court location Bridgeport Judicial District; and
- publisher party number `D-01`.

That row is useful for monitoring the source contract. It does not by itself
identify the party as any particular person.

## Exact case detail

`LoadDocket.aspx` redirects to the exact public case-detail route. The
adapter normalizes both compact and variably hyphenated source values to the
full docket form, such as `FBT-CV-26-6159214-S`, and verifies that the returned
docket matches the request.

The normalized record preserves:

- caption, prefix/suffix, case type code and description;
- file, return, last-action, disposition, and source-update dates;
- court location, list fields, and property address when published;
- parties, publisher party numbers, categories, appearance status, counsel
  or self-represented appearance text, juris number, address text, and
  appearance file date;
- every row in `Motions / Pleadings / Documents / Case Status`, including
  entry number, file date, filed-by code, description, additional text,
  result, notes, arguable status, and linked filing;
- scheduled-event number, date, time, description, and status;
- case-transfer history; and
- published notices with preview and full-notice link.

History and notices are child pages of the selected case. The history route
requires the active case session and case-detail `Referer`; a context-free
request can return the portal home page instead.

## Durable identity

| Record | Durable identity |
|---|---|
| Case | Normalized full docket |
| Party | Docket plus publisher party number, such as `D-01` |
| Filing PDF | Docket plus publisher `DocumentNo` |
| Docket entry without a PDF | Docket plus publisher entry number |
| Scheduled event | Docket plus publisher event number from the `#` column |
| Notice | Docket plus publisher `eNID`; `PSID` is also preserved |
| Transfer event | Published from-docket, to-docket, and transfer date tuple |
| Attorney appearance without a publisher ID | Complete published appearance tuple plus an ordinal only among identical tuples |

For a docket row that publishes neither `DocumentNo` nor an entry number, the
adapter derives an identity from the complete published field tuple. This is
used only where no publisher child identifier exists.

## Shared lifecycle

The canonical source is available through the shared court router and court
sidecar:

```bash
uv run python tools/query_state_courts.py search EPSTEIN \
  --source us-ct-superior-court-civil-family-case-lookup \
  --output "$WORKDIR/ct-shared-search.json"

uv run python tools/query_state_courts.py case FBT-CV-26-6159214-S \
  --source us-ct-superior-court-civil-family-case-lookup --ingest \
  --output "$WORKDIR/ct-shared-case.json"

uv run python tools/query_state_courts.py download 32503295 \
  --source us-ct-superior-court-civil-family-case-lookup \
  --destination "$WORKDIR/ct-complaint.pdf" \
  --output "$WORKDIR/ct-shared-document.json"

uv run python tools/query_state_courts.py download 32503295 \
  --source us-ct-superior-court-civil-family-case-lookup \
  --case-number FBT-CV-26-6159214-S --ingest \
  --destination "$WORKDIR/ct-verified-complaint.pdf" \
  --output "$WORKDIR/ct-shared-verified-document.json"
```

Party-search occurrences remain snapshot-only and are not promoted to case or
person identity rows. Exact docket detail projects the case, published party
roles and numbers, attorney appearances, docket metadata, scheduled events,
transfer history, and notices. A filing link on case detail is metadata, not a
downloaded artifact. The ingester creates a `document_artifact` only after the
PDF bytes exist locally and the media type, PDF signature, byte length,
`DocumentNo`, and SHA-256 agree. A DocumentNo-only download remains useful as
a retained source snapshot; supplying `--case-number` also verifies membership
and supplies the durable case relationship needed for artifact projection.

The fixed five-request monitor checks the party form and 50-row display, exact
docket detail, history, notices, and one linked `DocumentNo` as metadata. It
does not download the PDF. Stable route, identity, and completeness hashes are
reported separately from mutable caption, date, and child-count observations.

The sentinel detail publishes case type `C40 - Contracts - Collections`, file
date `04/23/2026`, return date `05/12/2026`, its parties and appearance, and
summons, complaint, and return-of-service filings. Complaint
`DocumentNo=32503295` returned a 71,393-byte `application/pdf` response during
verification.

## Coverage complements

The interactive portal and the routes below serve different acquisition
roles:

| Route | Value | Relationship |
|---|---|---|
| Interactive party search | Fast name-to-docket discovery | Published display slice |
| Interactive case detail | Rich selected-case metadata and linked PDFs | Same court case |
| DocumentInquiry | Underlying filed PDF where linked | Artifact from the same case |
| [Official Civil/Family bulk data](https://www.jud.ct.gov/publicdata/BulkDataCivilFamilyCases.pdf) | Pending and disposed cases at comprehensive feed grain | Field-matched bulk complement |
| [Superior Court clerk offices](https://www.jud.ct.gov/directory/directory/clerk.htm) | Court-of-record research and copies | Human acquisition complement |

The Judicial Branch says its fee-based bulk Civil/Family data includes basic
case information, important case dates, party and appearance information,
motions, pleadings, and companion cases. Electronic documents are not part of
that feed. It is therefore the best official complement for comprehensive
case enumeration and field matching, while `DocumentInquiry` supplies
published filing artifacts for selected cases.

If the interactive portal is unavailable, the bulk feed can still cover the
structured case, party, appearance, motion, pleading, and companion fields.
Clerk offices can provide court-held records and copies. These are alternate
representations or delivery routes from the same Judicial Branch; they are
not independent corroboration merely because the access path differs.

## Transport finding

The repository's standard `requests` system-trust session reached the host
but failed its TLS handshake. The installed `curl-cffi`/libcurl transport
successfully completed the same official-host requests and maintained the
WebForms session. The adapter therefore uses a source-local, injectable
`curl-cffi` session, keeps an exact official-host check, validates HTML versus
PDF response media, and reports a classified dependency/transport failure if
that transport is unavailable.

## Process improvements from this source

- Probe the repository's real HTTP transport before building a parser. A
  browser or command-line success does not prove that the adapter's TLS stack
  will work.
- Separate a portal display count from dataset completeness. Here, `1-50 of
  50` describes the visible slice; the official bulk feed is the appropriate
  comprehensive complement.
- Inventory publisher child identifiers before defining normalized records.
  Party number, entry number, event number, `DocumentNo`, `eNID`, and `PSID`
  remove most positional or row-order identities.
- Test child routes inside the selected case session, including their
  `Referer` behavior, rather than treating every visible link as stateless.
- Model party-name search as discovery and exact docket detail as the durable
  record. This prevents same-name results from becoming accidental identity
  assertions.
- Record lineage by underlying record, not delivery URL. Search result,
  detail page, bulk row, and filing image can all describe the same court
  case without becoming independent evidence.
- Monitor stable route, form, column, media, and identifier contracts
  separately from mutable case captions, row counts, latest dates, and
  docket activity.

## Focused validation

```bash
uv run pytest -q tests/test_query_connecticut_civil_family.py \
  tests/test_connecticut_civil_family_shared_integration.py
uv run ruff check tools/query_connecticut_civil_family.py \
  tools/query_state_courts.py tools/ingest_state_court_records.py \
  tools/public_records_monitor.py \
  tests/test_query_connecticut_civil_family.py \
  tests/test_connecticut_civil_family_shared_integration.py
uv run python -m py_compile tools/query_connecticut_civil_family.py \
  tools/query_state_courts.py tools/ingest_state_court_records.py \
  tools/public_records_monitor.py
```
