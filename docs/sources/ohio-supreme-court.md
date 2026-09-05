# Supreme Court of Ohio public records

Verified against the official Ohio Judicial System host on 2026-07-30.

## Implemented components

### Public eCMS docket

Source ID: `us-oh-supreme-court-public-docket`

Tool: `tools/query_ohio_supreme_court.py`

The public eCMS docket covers Supreme Court of Ohio cases filed on or after
January 1, 1985, and practice-of-law cases filed on or after January 1, 1989.
It is a Supreme Court docket, not a statewide index of cases filed in every
trial and intermediate appellate court.

```bash
uv run python tools/query_ohio_supreme_court.py source --json

uv run python tools/query_ohio_supreme_court.py search \
  --caption LaPilusa \
  --output /tmp/ohio-supreme-search.json

uv run python tools/query_ohio_supreme_court.py case 2017-1682 \
  --output /tmp/ohio-supreme-case.json

uv run python tools/query_ohio_supreme_court.py recent --days 5 \
  --output /tmp/ohio-supreme-recent.json

uv run python tools/query_ohio_supreme_court.py document \
  2017-1682 835936.pdf /tmp/835936.pdf \
  --output /tmp/ohio-supreme-document.json

uv run python tools/query_ohio_supreme_court.py probe \
  --output /tmp/ohio-supreme-probe.json
```

Omitting `--limit` returns every row supplied in the source response. An
explicit limit creates a caller-sized window only after that response has been
retrieved. Continuation cursors bind the selector set and ordered response
membership.

### Shared state-court lifecycle

The shared router exposes `search`, `case`, `docket`, `documents`, and
`download`. The positional search query maps to the eCMS caption field by
default. `--search-field` selects another verified native field, and shared
ISO filing dates are translated to the source form.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_state_courts.py search Newsome \
  --source us-oh-supreme-court-public-docket \
  --output "$WORKDIR/ohio-supreme-caption.json"

uv run python tools/query_state_courts.py search 2017-1682 \
  --source us-oh-supreme-court-public-docket \
  --search-field case-number \
  --after 2017-01-01 --before 2017-12-31 \
  --output "$WORKDIR/ohio-supreme-number.json"

uv run python tools/query_state_courts.py case 2017-1682 \
  --source us-oh-supreme-court-public-docket --ingest \
  --output "$WORKDIR/ohio-supreme-case.json"

uv run python tools/query_state_courts.py documents 2017-1682 \
  --source us-oh-supreme-court-public-docket \
  --output "$WORKDIR/ohio-supreme-documents.json"

uv run python tools/query_state_courts.py download 835936.pdf \
  --source us-oh-supreme-court-public-docket \
  --case-number 2017-1682 \
  --document-section DocketItems \
  --destination "$WORKDIR/835936.pdf" \
  --output "$WORKDIR/ohio-supreme-download.json"

uv run python tools/public_records_monitor.py run \
  us-oh-supreme-court-public-docket \
  --output "$WORKDIR/ohio-supreme-monitor.json"
```

An omitted shared limit does not inherit the router's local default. An
explicit `--limit` or `--max-records` creates a caller window after eCMS
returns its array. Exact `case`, `docket`, and `documents` operations all
retrieve the same source case response. A download requires the emitted
document name, case number, and explicit `DocketItems` or `DecisionItems`
section; the router does not guess the section. Rolling `recent` discovery
remains on the direct adapter because those rows do not publish
`DocketItems.ID`.

Normalized search and exact-case records converge on `CaseInfo.CaseNumber`.
`CaseInfo.ID` and the search-row `ID` remain source-specific raw metadata and
are not used as the shared case identity. Exact ingestion projects published
parties and attorney appearances, docket rows keyed by `DocketItems.ID`,
decision events, and documents keyed by case, section, and `DocumentName`.
Prior-jurisdiction, issue, decision, and complete source arrays remain in raw
provenance.

The monitor makes five nominal requests without fetching a PDF: the eCMS
landing page, the application bundle that supplies its request token, a
stable caption search, one exact historical case, and rolling one-day recent
filings. Route, action, schema, identity, and source-boundary fingerprints are
separate from rolling counts, case status, and recent membership. Session
cookies and the request token are not persisted.

### Verified route contract

The application starts an anonymous ASP.NET session at:

`https://www.supremecourt.ohio.gov/clerk/ecms/`

Its own JavaScript bundle supplies the current request token. Structured
operations use `POST /clerk/ecms/Ajax.ashx`:

| Action | Record role | Source identity |
|---|---|---|
| `CaseSearch` | Supreme Court case index | `CaseNumber`; the returned search-row `ID` is not an identity |
| `GetCaseDetails` | Exact case, prior jurisdiction, parties, counsel, docket entries, decisions, issues, document index | `CaseInfo.CaseNumber`, with `CaseInfo.ID` retained only as a source-internal locator |
| `GetRecentFilings` | Rolling filing discovery | Case number plus document locator; fetch exact case detail for `DocketItems.ID` |
| `GetCaseTypes` | Search vocabulary | Case-type ID and code |

The exact-case response publishes:

- case number, source-internal case locator, caption, filed date, status, and
  case type;
- prior jurisdiction, county, prior decision date, and lower-court numbers;
- parties, roles, pro-se flags, counsel names, attorney registration numbers,
  and counsel-of-record flags;
- docket entry ID, code, type, date, description, filing parties, and optional
  document name;
- decisions, release dates, disposition flags, published-opinion links, and
  optional decision documents;
- accepted case issues.

The stable identity domains stay separate:

- case: `CaseInfo.CaseNumber`; search and exact detail therefore share one
  canonical case reference;
- source-internal case locator: `CaseInfo.ID`, retained as metadata rather than
  incorporated into case identity;
- docket entry: `DocketItems.ID`;
- document: case number + `DocketItems` or `DecisionItems` + `DocumentName`;
- attorney: the attorney registration number carried on the appearance.

Public docket and decision documents resolve through
`/pdf_viewer/pdf_viewer.aspx`. The adapter verifies the final HTTPS host,
`application/pdf` media type, PDF signature, byte size, and SHA-256 before
writing a file.

### Source response semantics

The server returns a JSON array and the browser paginates that array locally;
there is no source page or next-token route to follow.

A broad live caption search for `State` returned exactly 1,000 rows. That is
treated as an observed source boundary: all returned rows are preserved and
the result is marked `partial`, with a structured suggestion to refine the
source-native selectors. It is not presented as a complete result set.

The source also returns the literal JSON string `"Too many results"` for some
unresolved selections, including observed exact-number misses. The adapter
reports `source_requires_refinement`; it does not convert that response into
`no_results`. An empty `CaseSearch` array is an authoritative empty search
result.

### Reporter of Decisions opinions and announcements

Source ID: `us-oh-reporter-of-decisions`

Tool: `tools/query_ohio_reporter_decisions.py`

The official Reporter of Decisions index publishes opinions and case
announcements from the Supreme Court of Ohio, all twelve district courts of
appeals, the Court of Claims, and a miscellaneous publication category. It
provides statewide publication discovery, but it is not a statewide case
docket or an index of every filing.

```bash
uv run python tools/query_ohio_reporter_decisions.py source --json

uv run python tools/query_ohio_reporter_decisions.py search \
  --source supreme --year 2026 \
  --output /tmp/ohio-reporter-2026.json

uv run python tools/query_ohio_reporter_decisions.py search \
  --source district-1 --case-number C-250425 \
  --output /tmp/ohio-first-district-opinion.json

uv run python tools/query_ohio_reporter_decisions.py publication \
  2018-Ohio-723 --output /tmp/ohio-publication.json

uv run python tools/query_ohio_reporter_decisions.py document \
  2018-Ohio-723 /tmp/2018-Ohio-723.pdf \
  --output /tmp/ohio-publication-document.json

uv run python tools/query_ohio_reporter_decisions.py probe \
  --output /tmp/ohio-reporter-probe.json
```

The WebForms search exposes full text, deciding source, decision-year range,
county, exact deciding-court case number, author, topics and issues, WebCite,
and print-citation fields. The official help page describes these native
semantics:

- spaces in full text are Boolean `AND`, `OR` is supported, and quotation
  marks select an exact phrase;
- case number is an exact match including punctuation;
- county applies to appellate-court opinions;
- WebCite identifies one posted decision and overrides every other filter;
- print citation is an exact Supreme Court opinion lookup and is overridden
  when WebCite is also supplied.

The adapter selects the source's 200-row page size and then follows every
ASP.NET GridView postback page. A live Supreme Court / 2026 query returned 399
rows as 200 plus 199, with 399 distinct WebCites. Omitting `--limit` returns
all collected native pages. An explicit limit is a caller window applied only
after that traversal; its continuation cursor binds both the selector set and
ordered WebCite membership.

Full-text completeness is a separate source property. The official help says
the search appliance returns the 1,000 most relevant full-text results. A live
all-source search for `court` over 1992-2026 returned exactly 1,000 distinct
WebCites over five native pages. The adapter preserves all 1,000 rows and
marks the result `partial` with
`documented_full_text_result_boundary`. A 1,000-row metadata-only query would
not be classified this way because the documented boundary is specific to
the full-text appliance. Once the page contract and selected filters validate,
a published zero-row count is an authoritative `no_results` response.

Reporter identity domains remain separate:

- publication: WebCite, such as `2026-Ohio-2912`;
- case: the optional deciding-court case number, such as `C-250425`;
- deciding source: the source code carried in the official PDF path;
- document representation: WebCite plus the linked official PDF.

This distinction covers case announcements, which have a WebCite and PDF but
often no case number. It also permits one case number to join to more than
one publication without collapsing those publications. The PDF operation
first resolves the WebCite through the index, then validates the final HTTPS
host, source-code path, WebCite, `application/pdf` media type, PDF signature,
byte size, and SHA-256 before writing.

An invalid reversed year range is not an empty search. The site displays a
year-range validation message while its row-count label may retain a prior
search's count. The adapter gives the visible validation state precedence and
returns `source_requires_refinement`.

### Reporter shared lifecycle

The shared router exposes publication `search`, exact WebCite `detail`, and
publication-PDF `download`. It intentionally does not expose Reporter rows as
the shared `case` route.

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

Shared search defaults to full text across all deciding sources.
`--search-field` also maps case number, author, topics and issues, or print
citation; `--court-id` selects a published deciding source. The router does
not approximate exact ISO dates with the source's year-only selectors.
Omitting a caller limit preserves the complete native traversal. An explicit
`--limit` or `--max-records` is applied only after every GridView page has
been collected.

Ingestion always snapshots the publication envelope. A publication with one
unambiguous source case-number token can additionally create a sparse case
join with a WebCite-keyed publication event and its PDF representation.
Case-less announcements and ambiguous or combined `Case No.` cells remain
snapshot-only, so a publication identity never becomes a fabricated case
identity. Download receipts are also snapshot-only. The source case number
is not stored as a source-internal identifier.

The monitor makes three nominal requests without fetching the PDF: one
landing request, a fresh exact-WebCite form request, and the exact-WebCite
submission. Stable routes, request shape, identity, pagination, and no-PDF
validation contracts are fingerprinted separately from parser schema and
rolling year vocabulary or sentinel metadata. WebForms state and session
cookies are not persisted.

## Related official components

These products share the Supreme Court of Ohio site but serve different
record roles. They should remain separate source components and join on
case number, citation, attorney registration number, court, or date as
appropriate.

| Official component | Public role and observed shape | Relationship to eCMS |
|---|---|---|
| [Clerk's Journal](https://www.supremecourt.ohio.gov/Clerk/Journal/) | Electronic journal of Supreme Court orders beginning in January 2007; search by case number, caption, or year/month; linked order images and docket links | Order/journal publication; may represent the same order listed in eCMS |
| [Oral Argument Calendar](https://www.supremecourt.ohio.gov/opinions-cases/oral-arguments/oral-argument-calendar/) | Current and historical argument dates, case numbers, captions, county, time allocation, docket links, a calendar PDF, and Ohio Channel video links | Schedule and audiovisual layer joined by case number |
| [Attorney Directory](https://www.supremecourt.ohio.gov/AttorneySearch/) | Public attorney registration search and detail | Registration/status source; an eCMS counsel row is appearance evidence |
| [Judge Directory](https://www.supremecourt.ohio.gov/JudgeSearch/site/index.html) | Sitting appellate and trial judges, court, county, term end, and mailing address; client-side Excel export | Court-personnel directory, not case assignment evidence |
| [Ohio Court of Appeals directory](https://www.supremecourt.ohio.gov/courts/judicial-system/ohio-court-of-appeals/) | Twelve appellate districts, county coverage, judges, contacts, district websites, online-opinion links, local rules, and selected weekly dockets | Routing inventory for district-specific dockets and opinions |
| [Ohio trial-court directory](https://www.supremecourt.ohio.gov/courts/judicial-system/ohio-trial-courts/) | County/court directory, local rules, local court sites, and a statewide ArcGIS court map | Routing layer for county and municipal case systems |
| [State court-statistics dashboards](https://www.supremecourt.ohio.gov/courts/services-to-courts/court-services/dashboards/) | Aggregate appellate and trial caseload, disposition, timeliness, and performance dashboards | Aggregate operations data; the Supreme Court states that it does not collect individual local cases for these dashboards |
| [eStats public report](https://www.supremecourt.ohio.gov/estatspublic/) | Public rendering of submitted judicial caseload reports | Aggregate judge/month reporting, not a case index |

### Attorney registration alternative

The attorney portal is password protected, but the public Attorney Directory
is a field-matched official alternative for registration data. Its live
application bundle identifies anonymous `Ajax.ashx` actions for:

- `SearchAttorney`;
- `GetAttyInfo`;
- `GetAttyDiscipline`;
- `GetAttyLanguage`;
- `LoadSearchOptions`.

Search fields include registration number, first/middle/last name, address,
city, state, county, ZIP, and languages. This makes the directory the right
future source for registration status and public directory fields; the eCMS
attorney number should be used as the join key.

### Judge and court-directory alternative

The Judge Directory application exposes anonymous JSON collections at:

- `/JudgeSearch/api/judges`;
- `/JudgeSearch/api/counties`;
- `/JudgeSearch/api/courtmastertypes`;
- `/JudgeSearch/api/courtentitytypes`.

The browser filters the returned judge collection and creates the Excel file
client-side. Observed fields include county, court type, court name, judge
name, term-end date, mailing address, administrative-judge status, appellate
district, and subject-matter entity types.

This is a useful structured alternative when a court website's staff page is
hard to parse. It should not be used to infer that a judge handled a
particular case; the case docket or assignment entry supplies that fact.

## Source-selection lessons

- A shared host and publisher do not make docket entries, filed PDFs,
  published opinions, journal orders, schedules, registration records,
  directories, and aggregate statistics interchangeable.
- Search completeness has to be determined from the source response contract,
  not the page controls. eCMS paginates one JSON response in the browser; the
  Reporter uses server-side WebForms postbacks that must all be followed.
- A source-native maximum page size is a transport setting, not a result cap.
  Query-specific boundaries still need separate evidence: the Reporter can
  exhaust five 200-row pages while remaining incomplete because its
  full-text appliance selects only the 1,000 most relevant matches.
- Validation state outranks stale result chrome. The Reporter can leave an old
  row-count label visible after rejecting a reversed year range.
- Result links can carry attribution absent from visible columns. The
  Reporter's PDF path source code distinguishes Supreme Court, appellate
  district, Court of Claims, and miscellaneous publications even in an
  all-source query.
- A blocked or gated primary interface should be decomposed by field role.
  The public attorney directory replaces the password-protected portal for
  public registration fields; public dashboards replace eStats submission
  access for aggregate statistics; district opinion links replace no
  statewide local-opinion index, but do not replace local dockets.
- Alternative representations of the same filing or order add access and
  fields, but they are not independent corroboration.
