# New Mexico Judiciary Case Lookup

Source ID: `us-nm-judiciary-case-lookup`

The New Mexico Judiciary's anonymous Case Lookup publishes case metadata for
the Supreme Court, Court of Appeals, District Court, Magistrate Court,
Metropolitan Court, and parts of the municipal-court record. It does not
publish filed documents. The official public-access page points to
re:SearchNM for registered case-information and document access and to
judiciary public-records or individual-clerk channels for records outside the
web application's display.

## Verified public operations

The application uses Apache Tapestry 4 session forms. The adapter discovers
live form actions and links rather than constructing Tapestry component
locators.

- Targeted party discovery: disclaimer GET, acceptance POST, then one
  source-native name-search POST. The result records are party occurrences,
  so one case may appear more than once for different roles.
- Exact case: disclaimer GET, acceptance POST, dynamic case-number-search GET,
  then one exact-case POST. The response contains the full metadata record in
  one page.
- Authoritative empty: the exact route's published no-results response remains
  distinct from transport or schema failures.

The source describes public use at the grain of an individual electronic
court record. The verified adapter contract therefore exposes the first
native party-discovery page and one caller-selected exact case. Technical
search paging remains a separate source behavior, and no global tool or model
restriction is inferred from it.

## Commands

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_new_mexico_case_lookup.py source \
  --output "$WORKDIR/nm-source.json"

uv run python tools/query_new_mexico_case_lookup.py search \
  "Epstein Jeffrey" \
  --output "$WORKDIR/nm-party-search.json"

uv run python tools/query_new_mexico_case_lookup.py case \
  D-101-CV-199602449 \
  --output "$WORKDIR/nm-case.json"

uv run python tools/query_state_courts.py search "Epstein Jeffrey" \
  --source us-nm-judiciary-case-lookup \
  --output "$WORKDIR/nm-shared-search.json"

uv run python tools/query_state_courts.py case D-101-CV-199602449 \
  --source us-nm-judiciary-case-lookup --ingest \
  --output "$WORKDIR/nm-shared-case.json"

uv run python tools/public_records_monitor.py run \
  us-nm-judiciary-case-lookup \
  --output "$WORKDIR/nm-monitor.json"
```

Shared `case`, `docket`, and `claims` all retrieve the same exact case page;
the normalized projection selects the relevant child sections. Case Lookup
has no shared `documents` or `download` route because the application does
not publish those artifacts.

## Record and identity model

The exact response preserves:

- published full case number, caption, filing date, court, and current judge;
- parties, role codes and descriptions, party numbers, and counsel lines;
- complaint, cause-of-action, and source-published disposition fields;
- register-of-actions rows and their continuation text;
- complete judge-assignment history; and
- generic table groups alongside the specialized projections.

The full case number plus its court-type and location components determines
the canonical case and court identity. Tapestry session values, CSRF values,
and result links are transport state.

The source does not publish native IDs for party occurrences, complaint and
cause rows, register entries, or judge-history rows. Their adapter IDs are
derived from the complete published field tuple plus a duplicate ordinal only
among identical tuples. This keeps unrelated row insertions from changing
existing child identities. Ingestion validates those identities and validates
the court code against the case number.

Register text is retained as docket metadata. Descriptions such as a dismissal
or order are not converted into a case outcome unless the source publishes a
corresponding disposition field.

## Coverage and alternatives

The official description says District and Magistrate information is updated
daily. Some cases filed before statewide automation was completed in 1997 may
remain in separate court databases. Municipal coverage is limited to
specified historical domestic-violence and DWI convictions. Juvenile cases
and Family Violence Protection Act orders have source-published display
exclusions.

Field-matched complements:

| Missing field or record | Complement |
|---|---|
| Filed documents | [re:SearchNM](https://researchnm.tylerhost.net/) |
| Records absent from the public application | [Judiciary public-records request](https://www.nmcourts.gov/public-records-request/) |
| Older or court-held records | [Individual court directory](https://www.nmcourts.gov/find-a-court/) |
| Published appellate opinions | The relevant official appellate publication source |

These routes add fields or access paths. A Case Lookup row and a retrieved
copy of the same court record are not independent corroboration merely because
they came through different interfaces.

## Process learnings

- Submit browser-successful controls only. Tapestry's dynamic location select
  can exist without options; emitting a fabricated empty value changes the
  server response.
- Resolve direct links from the accepted session page. Tapestry component
  queries are ephemeral locators, not stable endpoints or record IDs.
- Separate discovery occurrences from exact records. A party hit is a useful
  case-number pivot; exact detail supplies the normalized parties, counsel,
  causes, register, and judge history.
- Keep representation and access roles explicit. Metadata search, registered
  document access, records requests, and clerk-held older records solve
  different gaps.
- Monitor stable route, form, schema, and identity contracts separately from
  mutable caption, judge, row counts, and latest register date.
