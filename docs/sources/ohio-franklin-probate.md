# Franklin County Probate Court NetData case records

Verified 2026-07-31 against the official [Franklin County Probate Court General
Case Search](https://probate.franklincountyohio.gov/Record-Search/General-Case-Search)
and its public NetData host. The standalone source ID is
`us-oh-franklin-probate-netdata`; the adapter is
`tools/query_ohio_franklin_probate.py`.

This source covers Franklin County probate matters. It is separate from the
Franklin County Clerk of Courts CIO adapter for Common Pleas cases and from the
state judicial publication indexes.

## Commands

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Verified source contract without a network request
uv run python tools/query_ohio_franklin_probate.py source \
  --output "$WORKDIR/franklin-probate-source.json"

# Current official landing methods and operational notices
uv run python tools/query_ohio_franklin_probate.py landing \
  --output "$WORKDIR/franklin-probate-landing.json"

# Ordered source-native discovery indexes
uv run python tools/query_ohio_franklin_probate.py name "SMITH, JOHN" \
  --limit 80 --output "$WORKDIR/franklin-probate-name.json"
uv run python tools/query_ohio_franklin_probate.py opened 2026-07-30 \
  --output "$WORKDIR/franklin-probate-opened.json"
uv run python tools/query_ohio_franklin_probate.py type E --subtype 16 \
  --output "$WORKDIR/franklin-probate-estates.json"
uv run python tools/query_ohio_franklin_probate.py attorney "ARTZ, BRIAN" \
  --limit 40 --output "$WORKDIR/franklin-probate-attorneys.json"
uv run python tools/query_ohio_franklin_probate.py fiduciary "ARTZ, BRIAN" \
  --limit 40 --output "$WORKDIR/franklin-probate-fiduciaries-by-name.json"

# Exact case index row and case-type-specific detail
uv run python tools/query_ohio_franklin_probate.py number 617503 \
  --output "$WORKDIR/franklin-probate-number.json"
uv run python tools/query_ohio_franklin_probate.py case 617503 \
  --output "$WORKDIR/franklin-probate-case.json"

# Related case records
uv run python tools/query_ohio_franklin_probate.py docket 617503 \
  --output "$WORKDIR/franklin-probate-docket.json"
uv run python tools/query_ohio_franklin_probate.py fiduciaries 617503 \
  --output "$WORKDIR/franklin-probate-fiduciaries.json"
uv run python tools/query_ohio_franklin_probate.py fiduciary-detail 617503 02 \
  --output "$WORKDIR/franklin-probate-fiduciary-02.json"
uv run python tools/query_ohio_franklin_probate.py attorney-detail 617503 02 \
  --output "$WORKDIR/franklin-probate-attorney-02.json"
uv run python tools/query_ohio_franklin_probate.py attorney-profile 0002003 \
  --output "$WORKDIR/franklin-probate-attorney-profile.json"

# Seven-request live route/schema sentinel
uv run python tools/query_ohio_franklin_probate.py probe \
  --output "$WORKDIR/franklin-probate-probe.json"
```

`--suffix` accepts the source's optional one- or two-character case suffix on
case-scoped commands. `opened` accepts either ISO `YYYY-MM-DD` or the landing
page's `MM/DD/YYYY` spelling.

## Published search surface

The landing page exposes these public discovery modes:

| Command | NetData route | Published selector |
|---|---|---|
| `name` | `PBCNameInx.ndm/input` | case name |
| `opened` | `PBODateInx.ndm/input` | opening date as `YYYYMMDD` |
| `number` | `PBCNumbInx.ndm/input` | case number plus optional suffix |
| `type` | `PBCTypeInx.ndm/input` | type plus optional subtype |
| `attorney` | `PBAttyInx.ndm/input` | attorney name |
| `fiduciary` | `PBFidyInx.ndm/input` | fiduciary name |

The official type vocabulary is Estate (`E`), Civil (`C`), Trust (`T`), Adult
Guardianship (`GA`), Minor Guardianship (`GM`), Miscellaneous (`M`), and the
source-labeled “Sentinal Trusts” (`ST`). The adapter keeps that source spelling
in the published vocabulary and preserves returned type/subtype labels on each
row.

The name, attorney, fiduciary, date, and type routes are ordered browse indexes.
For example, an attorney name request can begin at the first lexicographic row
at or after the supplied key. The adapter therefore retains every returned
source row and its discovery operation; downstream matching can compare the
returned name rather than assuming that every row is an exact name match.
`number` additionally filters the valid returned page to the requested case
number and optional suffix.

## Native pagination and caller windows

NetData ordinarily publishes 40 rows with duplicated `Prev` and `Next` links at
the top and bottom. The links carry opaque forward (`stringf`) and backward
(`stringb`) keys whose grammar varies by index. The adapter deduplicates those
links and follows the exact forward URL. It does not reconstruct the next key
from a row.

With no `--limit`, discovery follows forward pages until NetData publishes no
next link. With an explicit `--limit`, retrieval stops at the requested caller
window and returns an opaque cursor. That cursor retains:

- source and operation;
- normalized query selectors;
- exact native page URL;
- row position within the native page;
- a fingerprint of that page's ordered source rows.

Resuming inside a page re-fetches and verifies that page before continuing. A
cursor issued exactly at a 40-row boundary also points to the completed page;
on resume it verifies that page and then follows its preserved forward link.
This avoids an implicit adapter cap while keeping deliberately bounded work
resumable. If a later page fails after earlier pages were collected, the result
is `partial`, retains those rows, and emits the same page-boundary continuation
so retrieval can resume without restarting the browse.

## Detail routes and fixed-width selectors

Exact-number rows link to a case-type-specific route:

| Native type | Detail route family |
|---|---|
| Estate | `PBCaseTypeE.ndm/ESTATE_DETAIL` |
| Civil | `PBCaseTypeC.ndm/CIVIL_DETAIL` |
| Trust | `PBCaseTypeT.ndm/TRUST_DETAIL` |
| Adult/minor guardianship | `PBCaseTypeG.ndm/GUARD_DETAIL` |
| Miscellaneous | `PBCaseTypeM.ndm/MISC_DETAIL` |
| Sentinal Trusts | `PBCaseTypeSTG.ndm/input` |

Case selectors contain a two-character suffix field. NetData represents each
blank character with a literal semicolon, so an unsuffixed case is
`617503;;`; suffix `A` is `617503A;`. Docket and case-fiduciary routes use that
selector directly.

Fiduciary and case-linked attorney detail add the two-digit fiduciary number:
`617503;;02`. NetData's fiduciary table currently emits links such as
`61750302`, which the detail service parses as case `617503` with suffix `02`
and reports as not on file. The fixed-width form was verified directly against
both detail services. Records retain the emitted `*_href_raw` and also expose a
corrected `*_detail_url`.

Semicolons have transport meaning to this legacy service. The adapter keeps
them literal; a request containing `%3B%3B` was observed to be parsed as source
data and returned `CASE IS NOT FOUND`.

## Records, identity, and source preservation

The adapter emits these record kinds:

| Record kind | Role | Source-native identity |
|---|---|---|
| `source_capabilities` | static verified route contract | source ID |
| `source_landing` | current landing methods/notices | landing URL |
| `probate_case_index` | name/number/date/type/fiduciary discovery row | case number + fixed-width suffix |
| `probate_attorney_index` | attorney-name discovery row | seven-digit attorney number |
| `probate_case` | case-type-specific detail | case number + fixed-width suffix |
| `probate_docket_entry` | logical docket entry | case selector + source position + source-row fingerprint |
| `probate_docket_summary` | source account summary row | same case-scoped occurrence identity |
| `probate_fiduciary` | fiduciary/attorney case row | case selector + two-digit fiduciary number |
| `probate_fiduciary_detail` | case fiduciary detail | same person selector |
| `probate_attorney_detail` | attorney attached to that fiduciary row | same person selector, plus published attorney number |
| `probate_attorney_profile` | attorney-number profile | seven-digit attorney number |
| `source_probe` | live sentinel result | source ID + sentinel case |

Index records keep `source_row`, the emitted HTTP href, the upgraded HTTPS URL,
native status code, opening/closing values, type/subtype text, and source page
position. Detail records keep the complete ordered label/value rows and a
label-keyed `fields` object. Convenience fields do not replace that raw
structure: `AKA`, bond amount, address, related case, date, and source “N/A” or
“Case is Open” strings remain available exactly as displayed.

The docket's line wrapping is structural. A primary row carries a date or code;
following blank-date/blank-code rows with the same source row color continue
that entry. The adapter joins those description/reference lines for search and
also retains every physical row in `source_rows`. The separately formatted
`DEPOSIT REMAINING` row stays a `probate_docket_summary`. Receipt and cost text
remain `*_raw`, including values such as `.00`.

The live sentinel case `617503` resolved to Estate / Ancillary Administration,
native status `03`, opened `01/04/2023`, and displayed `Case is Open` on
2026-07-31. Its live docket produced 164 logical records from 272 physical
source rows, including 74 wrapped entries and one deposit summary. The case
published three fiduciary rows; corrected selectors successfully returned both
fiduciary and linked-attorney detail.

## Probe and monitor contract

`probe` makes seven nominal requests:

1. official search landing;
2. exact-number sentinel index;
3. type-specific case detail;
4. docket;
5. fiduciary list;
6. first fiduciary detail;
7. linked attorney detail.

It does not traverse a broad browse index. Useful stable monitor dimensions are
landing method/form names, route paths, index headers, detail field labels,
docket/fiduciary headers, case-type route family, fixed-width selector behavior,
and the presence of wrapped docket rows. Current names, status codes, dates,
addresses, counts, amounts, and docket membership are rolling observations.
The source emits duplicated navigation links and legacy `http://` hrefs; the
adapter's normalized HTTPS URLs and unique forward link are stable transport
projections, while the original href remains provenance.

## Scope and complementary sources

The court says case-search records are current as of the previous day and notes
routine backup activity between 10 PM and 2 AM on weekdays plus random weekend
backup activity. A temporary availability failure in that window is distinct
from an empty validated index page.

The official landing's current edge configuration returned HTTP 403 to a
Chrome-shaped `requests` profile while returning the full public page to a
conventional curl HTTP profile; NetData accepted the same curl profile. The
adapter uses that single source-compatible profile. This is a useful source
review distinction: retry a directly verified standard transport profile
before classifying a public application route as unavailable.

The [Certified Records department](https://probate.franklincountyohio.gov/Departments/Certified-Records)
describes copy and certified-record channels for estates, guardianships, name
changes, marriage licenses, and other probate material. It says electronic
images exist for most filings after August 2, 1998. Those copy channels are the
official complement when the public index supplies metadata/docket rows but no
filing image. The department also identifies adoption, mental-illness, and
developmental-disability records as confidential; their absence from this
general index is not an empty public case finding.

Related platform sources can supply different evidence roles:

- `us-oh-franklin-common-pleas-cio` covers Franklin Common Pleas exact cases,
  docket chronology, and selected filing PDFs; it is not a probate substitute.
- `us-oh-reporter-of-decisions` finds published Ohio opinions and case
  announcements, including appellate treatment of a probate matter.
- `us-oh-supreme-court-public-docket` supplies the Supreme Court of Ohio eCMS
  docket for matters that reach that court.
- `us-oh-franklin-county-recorder-publicsearch` supplies recorded deeds,
  mortgages, releases, liens, and instrument images for property-related joins.
- Franklin Auditor and Ohio OGRIP parcel sources supply parcel, assessed-owner,
  transfer, address, and geometry observations.

These sources can recover valuable adjacent facts when a local record or image
is unavailable, while keeping court case, appellate publication, recorded
instrument, and parcel observations separately attributable.
