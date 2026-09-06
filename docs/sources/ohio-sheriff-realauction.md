# Ohio county sheriff-sale sources

Observed and live-probed on 2026-07-30. Franklin, Delaware, and Licking
Counties publish separate official county tenants of the same Realauction
application:

| County | Source ID | Official tenant |
|---|---|---|
| Franklin | `us-oh-franklin-sheriff-realauction` | `https://franklin.sheriffsaleauction.ohio.gov/` |
| Delaware | `us-oh-delaware-sheriff-realauction` | `https://delaware.sheriffsaleauction.ohio.gov/` |
| Licking | `us-oh-licking-sheriff-realauction` | `https://licking.sheriffsaleauction.ohio.gov/` |

The standalone adapter is `tools/query_ohio_sheriff_sales.py`. It exposes
`source`, `calendar`, `auctions`, and `probe` operations for each tenant.

## Verified public request sequence

The calendar and auction JSON are available without signing in, but the JSON
routes depend on the public ColdFusion session established by the tenant root.
The verified sequence is:

1. Bootstrap the session with `GET https://{county}.sheriffsaleauction.ohio.gov/`.
2. Fetch a month with
   `GET /index.cfm?zaction=USER&zmethod=CALENDAR&selCalDate=MM/01/YYYY`.
3. Select an auction date with
   `GET /index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=MM/DD/YYYY`.
4. Load a native status area and page with
   `GET /index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA={R|W|C}&PageDir=0&doR=1&bypassPage={page}&test=1`.
5. Overlay changing status and amount fields with
   `GET /index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={comma-separated-AIDs},`.

`R`, `W`, and `C` are the running, waiting, and closed/canceled areas. Waiting
and closed/canceled results use native 10-row pages. The status response
reports their page counts in `WM` and `CM`. `bypassPage=0` loads the first page;
later pages use their one-based page number.

The routes and compact HTML substitutions were verified against the tenant's
public `Splash.js`, `Calendar.js`, and `auction.js`. The `probe` command
exercises the root bootstrap, calendar, preview, listing, and status routes
against an auction sentinel. Its defaults are 2026-07-10 for Franklin,
2026-07-29 for Delaware, and 2026-07-30 for Licking; `--date` accepts another
known auction date.

## Records and identity

Calendar rows provide auction date, auction kind, source time label, active
count, and scheduled count. Public auction rows provide:

- RealAuction `AID`
- case status and case number
- parcel identifier or identifiers
- property address, city, and postal code
- appraised value, opening bid, and deposit requirement
- scheduled datetime or current disposition
- sold-to class, sold amount, and bid-history availability when reported

The canonical source identity is county tenant plus `AID`. Case number remains
a useful court join, but it is not the auction identity because a case can
produce more than one scheduled auction. Parcel identifiers are preserved as
both the source text and a parsed list.

Omitting `--limit` traverses every native page. A caller-supplied limit is
applied after complete traversal and returns a continuation bound to the query
selection and ordered `AID` membership. Auction status and amount fields are
mutable; continuation refreshes those fields and does not describe them as a
frozen content snapshot.

The 2026-07-10 Franklin sentinel verified a 23-row closed result across native
pages of 10, 10, and 3 rows. The adapter checks each page's ordered `rlist`,
status membership, duplicate AIDs, and source-reported page counts.

## Access observations and remaining gaps

Direct browser-shaped requests returned HTTP 200 across all three official
tenants on 2026-07-30. A generic crawler separately returned HTTP 403 for two
tenant roots. This is recorded as an observed client-response difference, not
as a statement about source policy. A root bootstrap is necessary before
calling the session-bound calendar or auction routes.

The public listing does not expose plaintiff, defendant, full legal
description, court docket entries or filings, recorded sheriff's deed, title
status, or the special notes shown in the registered `DETAILS&AID=` view.
Bidding and that separate detail view use an account; neither is needed to
collect the public listing fields.

A sale listing or reported winning bid is an auction observation. Court
confirmation and the recorded sheriff's deed remain the appropriate records
for establishing a completed title transfer.

## Licking County field-richer foreclosure archive

Licking County also maintains a distinct official archive at
`https://apps.lickingcounty.gov/sheriff/foreclosures/`. It has its own source
identity, `us-oh-licking-sheriff-foreclosure-archive`, and standalone adapter,
`tools/query_licking_foreclosure_archive.py`. Its operations are `source`,
`years`, `year`, `case`, and `probe`.

The verified anonymous JSON routes are:

- year inventory:
  `GET /sheriff/foreclosures/api/saleyears/`
- complete selected year:
  `GET /sheriff/foreclosures/api/foreclosures/?year={year}`
- rolling current portal view:
  `GET /sheriff/foreclosures/api/foreclosures/?year=0`
- exact case detail:
  `GET /sheriff/foreclosures/api/foreclosures/{caseNumber}`

The year inventory contained every year from 2000 through 2026. A complete
live enumeration returned 14,275 rows, all with the same 16-key schema and a
nonblank case number. No case number was duplicated within or across those
year arrays. The observed year counts are machine-readable in the adapter's
`source` result; they range from 182 records in 2000 to 1,334 in 2010, with 65
records in the still-changing 2026 year at the verification observation.

The API's temporal views are materially different:

- `year=0` is the portal's rolling current subset. It is not listed in the
  year inventory and is not a complete current-year result.
- Selecting 2026 returns the complete current-year array at retrieval, but
  statuses, purchasers, prices, and membership can still change.
- Earlier selected years are historical archive slices and are expected to be
  substantially more stable, while still allowing later source corrections.

The archive returns its selected year as one JSON array and does not implement
server pagination. Omitting `--limit` returns the complete selected and
filtered array. An explicit limit is applied afterward; its cursor binds the
source, year and filters, ordered case-number membership, and boundary case.
Mutable content is refreshed on continuation.

The archive's native record identity is its exact case number, not a
RealAuction AID. Normalized fields include sale date, address, parcels,
appraisal, terms, sale type, required deposit, status, deed-as name, purchaser
contact/address, and purchase price. The source key
`RequiredDepositAmmount` is preserved in the raw record and normalized to the
correctly named deposit fields. `AdvertiseDate` was present but null across all
14,275 observed rows. Older records often omit modern parcel, sale-type, and
deposit fields, so those nulls are preserved rather than filled by inference.

Join the archive to RealAuction on case number, parcel identifier, and sale
date. Matching status or price values generally describe the same underlying
auction event; the match is useful cross-system consistency but is not
automatically independent proof of the outcome. Common Pleas filings, court
confirmation, and the recorded sheriff's deed remain distinct evidence.

Both adapters validate that a followed response resolves to the selected
official host before parsing it. This preserves source provenance if an
upstream route begins redirecting elsewhere.

## Official complements and alternatives

The adapter's `source` output keeps the complement inventory machine-readable.
The most useful observed routes are:

- **Delaware County Sheriff sale table**:
  `https://sheriff.co.delaware.oh.us/sheriff-sales/`. The public official HTML
  includes sale date, address, property description or recorder reference,
  case number, appraisal, deposit, purchaser, purchase price, and sale
  history.
- **Delaware County delinquent land-tax notice**:
  `https://auditor.co.delaware.oh.us/wp-content/uploads/sites/23/2018/11/delqadvertisinglist.pdf`.
  It provides parcel number, owner, legal description, and delinquent amount
  for upstream tax context.
- **Franklin County Clerk Case Information Online**:
  `https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/`, joined by case
  number for parties and docket events.
- **Franklin County property-tax search**:
  `https://treapropsearch.franklincountyohio.gov/`, joined by parcel for tax,
  assessment, and payment context.
- **Delaware County Clerk eServices**:
  `https://court.co.delaware.oh.us/eservices/home.page`, joined by case number.
- **Licking County Common Pleas records search**:
  `https://lickingcounty.gov/depts/clerk/records_search.htm`, which documents
  the current remote docket and pleading route.

These are complements rather than independent corroboration when they repeat
the same underlying auction record.

## Reusable process learnings

- Identify vendor families before building county-specific clients. Tenant
  configuration captures publisher, jurisdiction, schedule, official links,
  and fallback sources while the verified transport and parser stay shared.
- Inspect the public JavaScript before inferring request contracts. It exposed
  the date-session dependency, page selector, page-count fields, compact HTML
  substitutions, and dynamic status overlay.
- Treat an HTTP response as an access observation tied to the request method.
  The initial crawler response did not predict the direct public-session result.
- Select sentinels that exercise pagination and state diversity, not merely a
  landing page. Franklin's 23-row date verifies full traversal; the Delaware
  and Licking samples verify multi-parcel, cancellation, and sold-result
  fields.
- Triage alternatives by the missing field they replace. Court systems add
  parties and filings, property systems add tax/title context, and county sale
  archives add purchaser and historical outcome fields.
- Test the semantics of special selectors such as `year=0`. A default portal
  view may be a rolling subset even when a separate explicit-year request
  returns a complete archive slice.
- Audit identity across the full inventory before choosing a canonical key.
  The archive's 14,275 rows established case number as its native identity,
  while RealAuction continues to require tenant plus AID.

## Examples

```bash
.venv/bin/python tools/query_ohio_sheriff_sales.py source licking --json
.venv/bin/python tools/query_ohio_sheriff_sales.py calendar franklin \
  --month 2026-07 --json
.venv/bin/python tools/query_ohio_sheriff_sales.py auctions delaware \
  --date 2026-07-29 --output /tmp/delaware-sales.json
.venv/bin/python tools/query_ohio_sheriff_sales.py probe licking --json
.venv/bin/python tools/query_licking_foreclosure_archive.py years --json
.venv/bin/python tools/query_licking_foreclosure_archive.py year \
  --year 2026 --output /tmp/licking-foreclosure-archive-2026.json
.venv/bin/python tools/query_licking_foreclosure_archive.py case \
  --case-number 25CV01926 --json
.venv/bin/python tools/query_licking_foreclosure_archive.py probe --json
```
