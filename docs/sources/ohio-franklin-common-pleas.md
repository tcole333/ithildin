# Franklin County Common Pleas CIO

Verified 2026-08-03 against the official Franklin County Clerk of Courts Case
Information Online portal. The adapter covers party-name discovery, exact case
detail, complete native docket traversal, and public filing copies. The wider
Central Ohio comparison is in
[`ohio-county-trial-court-party-indexes.md`](ohio-county-trial-court-party-indexes.md).

Official portal:
`https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/`

## Commands

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Party occurrences from CIO's ordered name index
uv run python tools/query_ohio_franklin_courts.py name WEXNER \
  --court civil --filed-from 2020-05-19 --filed-to 2020-05-19 \
  --exhaustive --output "$WORKDIR/franklin-party.json"

# Exact case and every native docket continuation
uv run python tools/query_ohio_franklin_courts.py case 22CV3098 \
  --output "$WORKDIR/franklin-case.json"

# Download by the document identity emitted by `case`
uv run python tools/query_ohio_franklin_courts.py document \
  22CV3098 franklin:document:<id> "$WORKDIR/franklin-filing.pdf" \
  --output "$WORKDIR/franklin-download.json"

# Shared lifecycle
uv run python tools/query_state_courts.py search WEXNER \
  --source us-oh-franklin-common-pleas-cio --ingest \
  --output "$WORKDIR/franklin-shared-search.json"
uv run python tools/query_state_courts.py case 22CV3098 \
  --source us-oh-franklin-common-pleas-cio --ingest \
  --output "$WORKDIR/franklin-shared-case.json"
uv run python tools/query_state_courts.py documents 22CV3098 \
  --source us-oh-franklin-common-pleas-cio \
  --output "$WORKDIR/franklin-documents.json"

# Fixed five-request party/case/docket contract monitor
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-common-pleas-cio \
  --output "$WORKDIR/franklin-monitor.json"
```

## Party-index semantics

CIO's name search is an ordered lower-bound index window, not an exact-match
result set. Each physical response row is emitted as a
`case_index_occurrence`, including duplicates and later nonmatching spillover.
`matched_query` says whether the normalized displayed name begins with the
requested prefix; it does not change the row's source identity.

The portal publishes row-count choices from 25 through 350 but no continuation
cursor for the party index. A window is complete when the source returns an
authoritative empty state or the ordered response reaches nonmatching
spillover. When matching rows reach the boundary, `--exhaustive` can bisect a
supplied filing-date range and, for one-day all-court windows, split by Appeals,
Civil, Criminal, and Domestic categories. If a same-day court window still ends
inside the prefix, it remains partial. An incomplete terminal HTML row is a
separate response-buffer boundary and also remains partial; neither state is
turned into a synthetic cursor.

CIO publishes no durable party-result row ID. The captured occurrence identity
therefore combines a fingerprint of the exact native query window with the
response ordinal. The court plus normalized case number remains the durable
case join.

## Exact case, docket, and filing copies

A public session begins with the portal's dynamic disclaimer action. Exact case
lookup returns the case summary, parties, schedule, first docket page, and
page-local document coordinates. The adapter follows `next-docket-key` through
`POST /CaseInformationOnline/docket` until the source returns an empty key; it
does not infer completeness from the first page size.

CIO does not expose a durable docket-entry ID. Docket identities use the case,
displayed entry fields, detail fields, and a duplicate occurrence number. A
filing has a separate case-scoped identity. When several docket entries share a
fiche/frame/pages locator, every source link is retained while normalized
storage uses one deterministic primary link. Disclaimer values, session IDs,
native next keys, click coordinates, and document coordinates remain
reacquired transport locators.

Downloaded artifacts are accepted only after the response remains on the
official CIO host and has PDF media type and signature. CIO describes online
material as a copy rather than the official court file; official or certified
copies use the Clerk's separate public-record request channel.

## Monitor and complementary evidence

The fixed probe makes five requests: landing, disclaimer acceptance, a narrow
WEXNER/Civil/2020-05-19 party window, exact case `22CV3098`, and its first known
docket continuation. The route paths, request fields, party result columns,
lower-bound spillover behavior, case/docket identities, and pagination contract
are stable checks. Match counts, status, judge, schedule and docket counts,
dates, and document counts are rolling observations.

Franklin Municipal and Probate provide separate court domains. RealAuction can
supply foreclosure case selectors; the Recorder establishes recorded-
instrument identities and page images; Auditor and OGRIP sources add parcel,
assessment, sale, address, and geometry observations. A court confirmation
order can corroborate an auction, while a recorded deed is the stronger source
for the recorder-side title event.
