# Ohio county trial-court party indexes

Verified 2026-08-03 against the official Franklin, Delaware, and Licking County
routes. These integrations deliberately keep party-index occurrences, durable
case identities, docket entries, filing artifacts, and copy/request workflows
as related but distinct records.

## Coverage at a glance

| Source | Discovery and access | Case and document depth | Exhaustion evidence |
|---|---|---|---|
| [Franklin Common Pleas CIO](https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/) | Anonymous lower-bound party-name window after the session disclaimer | Exact case, parties, schedule, exhaustive next-key docket, public filing PDFs | Empty state or later nonmatching lexical spillover; matching native-row or response-buffer boundaries remain explicit partial states |
| [Franklin Municipal Court](https://www.fcmcclerk.com/case/search/) | Anonymous person, company, case-number, and ticket search with a CSRF session | Detailed case sections, parties, attorneys, charges, dispositions, events, financials, receipts, docket, and a generated summary PDF | The source stops at 250 occurrences and publishes no continuation; a ceiling hit is partial |
| [Delaware Common Pleas CourtView](https://court.co.delaware.oh.us/eservices/home.page) | Persistent headed browser session after the user clears the visible challenge | Exact case, parties, attorneys, docket, events, financial/receipt tables, and docket-linked PDFs where published | Default search selects 100 rows and follows every native page; bounded output uses a query-bound offset cursor over that exhaustive result set |
| [Licking Common Pleas remote records](https://lickingcounty.gov/depts/clerk/records_search.htm) | Verified county landing and anonymous Tyler tenant/configuration shell; targeted transition currently reaches AWS Human Verification | County advertises General and Domestic Relations dockets/pleadings and Fifth District matters; structured browser, bulk, copy, and archive handoffs are implemented | No terminal result-set or post-login paging contract is claimed from the verified public state |

This distinction matters to agent triage. “Rows returned” can mean a complete
prefix, a source-capped slice, an exhausted native page chain, or merely a
verified handoff. The source result carries the corresponding coverage state so
later model analysis can use the records without guessing what was omitted.

## Franklin County Common Pleas CIO

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_franklin_courts.py name WEXNER \
  --court civil --filed-from 2020-05-19 --filed-to 2020-05-19 \
  --exhaustive --output "$WORKDIR/cio-party.json"
uv run python tools/query_ohio_franklin_courts.py case 22CV3098 \
  --output "$WORKDIR/cio-case.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-common-pleas-cio \
  --output "$WORKDIR/cio-monitor.json"
```

The name route emits every physical row as a `case_index_occurrence`. CIO
starts at the requested lexical key, so later nonmatching names are useful
spillover evidence rather than false matches. `matched_query` labels the rows
whose normalized displayed name actually begins with the requested prefix.
Exact duplicates remain separate occurrences.

The portal has row-count choices but no party-index continuation. Exhaustive
mode can partition a supplied filing-date range and then a one-day all-court
window by native court category. It reports any unresolved same-day/category
boundary. It also distinguishes a malformed terminal row caused by the
response-byte buffer from a clean numeric row boundary. See the
[Franklin-specific lifecycle](ohio-franklin-common-pleas.md) for exact-case,
docket, document identity, and recorder/auction joins.

The monitor uses exactly five requests: landing, disclaimer acceptance, narrow
party sentinel, exact case sentinel, and first docket continuation.

## Franklin County Municipal Court

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_franklin_municipal.py person BURKHALTER ERIKA \
  --output "$WORKDIR/fcmc-person.json"
uv run python tools/query_ohio_franklin_municipal.py company "L BRANDS" \
  --output "$WORKDIR/fcmc-company.json"
uv run python tools/query_ohio_franklin_municipal.py case "2022 CVF 020731" \
  --output "$WORKDIR/fcmc-case.json"
uv run python tools/query_ohio_franklin_municipal.py summary-pdf \
  "2022 CVF 020731" "$WORKDIR/fcmc-summary.pdf" \
  --output "$WORKDIR/fcmc-summary.json"
uv run python tools/public_records_monitor.py run \
  us-oh-franklin-municipal-court-records \
  --output "$WORKDIR/fcmc-monitor.json"
```

Search rows have case-party occurrence grain. A query fingerprint plus response
ordinal preserves duplicates without promoting the randomized encrypted case
handle into record identity. Exact detail reacquires a current handle and uses
the court plus normalized displayed case number as the stable case identity.

The results page states a 250-row maximum and exposes no next page or cursor.
The adapter therefore returns `partial` when that boundary is reached, even if
the caller also supplied a year filter. It does not present a capped shard as a
complete name index.

Exact detail conditionally includes civil or criminal fields, parties,
attorneys, charges, dispositions, events, financial summary, receipts, and
ordered duplicate-preserving docket rows. `case/view/pdf` produces a case
summary from the current view. It is explicitly a generated summary, not an
individual filed pleading or order, and its digest is a rolling observation
rather than a stable monitor invariant.

Useful same-court complements include the Clerk's [public-records
policy](https://www.fcmcclerk.com/documents/clerk/FCMC_Clerk_Public_Records_Policy.pdf),
[retention schedule](https://www.fcmcclerk.com/documents/clerk/FCMC_Clerk_Retention_Schedule.pdf),
[daily arraignment reports](https://www.fcmcclerk.com/reports/daily-arraignment),
[monthly eviction CSVs](https://www.fcmcclerk.com/reports/evictions), and
[civil drop list](https://www.fcmcclerk.com/reports/drop-list). Those routes can
supply filing-copy, retention, calendar, charge, address, disposition, or bulk
context that the 250-row search boundary does not.

## Delaware County Common Pleas CourtView

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

# Open or restore the persistent headed session. Complete the visible
# challenge in that browser if the portal presents it.
uv run python tools/query_ohio_delaware_common_pleas.py warmup \
  --wait-seconds 120 --output "$WORKDIR/delaware-session.json"

uv run python tools/query_ohio_delaware_common_pleas.py search-party \
  --last-name SMITH --first-name JOHN \
  --output "$WORKDIR/delaware-party.json"
uv run python tools/query_ohio_delaware_common_pleas.py case <case-number> \
  --output "$WORKDIR/delaware-case.json"
uv run python tools/query_ohio_delaware_common_pleas.py documents <case-number> \
  --output "$WORKDIR/delaware-documents.json"
uv run python tools/query_ohio_delaware_common_pleas.py document \
  <case-number> <dktdoc-id> \
  --document-output "$WORKDIR/delaware-filing.pdf" \
  --output "$WORKDIR/delaware-filing.json"
```

CourtView uses Apache Wicket actions whose path suffixes, anti-cache values,
and session state change as the page is rendered. The browser helper resolves
those current actions from the page. Durable records use the displayed case
number, physical party/docket occurrences, and a derived `dktdoc-*` identity
based on the case and docket occurrence—not a saved Wicket URL.

The source offers 25, 50, 75, and 100 rows per page. The default workflow
selects 100 and follows every native next-page action, checking the source-
reported total against rendered occurrences. An explicit caller limit slices
that collected result and returns an offset cursor bound to the exact query.

Exact case detail preserves parties and attorneys, docket, scheduled or
completed events, and the source's financial and receipt tables. A docket row
records either `link_present` or `not_listed`. Download reopens the exact case,
finds the current row action for the derived document identity, and validates
the returned PDF and digest.

The official portal states that Domestic Relations filing images are not
viewable online to the general public and that Juvenile and Probate case images
have some limitations. The [search
guide](https://co.delaware.oh.us/wp-content/uploads/2019/06/eFiling-Searching-Public-Portal.pdf),
[public-records policy](https://clerkofcourts.co.delaware.oh.us/wp-content/uploads/sites/9/2022/07/Delaware-County-Common-Pleas-Court-Public-Records-Policy-June-2022.pdf),
and [Clerk contact route](https://co.delaware.oh.us/contactus-copy/) cover
remotely unavailable or certified records. Delaware RealAuction can supply a
foreclosure case selector, while Recorder PAX provides independently
attributable recorded-instrument identities and PDFs.

The monitor is a browser contract probe rather than a fixed HTTP request count:
session restoration, challenge state, Wicket Ajax page-size selection, and Name
tab rendering change the network-step count. It fingerprints the rendered POST
form, person/company/date fields, option sets, page-size choices, and published
CourtView version; a renewed challenge is an access observation.

## Licking County Common Pleas remote records

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/query_ohio_licking_common_pleas.py source \
  --output "$WORKDIR/licking-source.json"
uv run python tools/query_ohio_licking_common_pleas.py probe \
  --output "$WORKDIR/licking-probe.json"
uv run python tools/query_ohio_licking_common_pleas.py targeted-browser-handoff \
  --party-name SMITH \
  --output "$WORKDIR/licking-browser-action.json"
uv run python tools/query_ohio_licking_common_pleas.py bulk-request-handoff \
  --scope "party index and docket rows" --party-name SMITH \
  --output "$WORKDIR/licking-bulk-action.json"
uv run python tools/query_ohio_licking_common_pleas.py record-request-handoff \
  <case-number> --copy-type certified \
  --output "$WORKDIR/licking-copy-action.json"
uv run python tools/query_ohio_licking_common_pleas.py archives-handoff \
  --party-name SMITH --year 1990 \
  --output "$WORKDIR/licking-archives-action.json"
```

The official county landing says remote data covers Common Pleas General and
Domestic Relations case dockets and pleadings plus Fifth District Court of
Appeals matters, with updates ordinarily about every 15 minutes. It excludes
domestic-violence civil protection orders and criminal protection orders from
that remote scope.

The fixed six-request probe checks the county landing, the Tyler tenant shell
needed to establish the portal session, and four anonymous JSON components:
application configuration, auth claims, subscription configuration, and the
Licking tenant definition. The observed tenant is
county ID 1 with external source “Licking County”; anonymous JWT and user
profile values were null. Targeted navigation reached AWS Human Verification.
The adapter records that access state and creates a browser handoff; it does not
assert unverified post-login case endpoints. A 403 from a Tyler route is
reported as `human_required/interactive_verification_required`, not as an
authoritative empty result or generic source outage. Tyler's public maximum-export
configuration is not treated as a search or page ceiling.

When the terminal route cannot answer the immediate question, the agent can
continue with field-specific official substitutes:

- the Clerk's landing supplies bulk distribution and current/certified record
  contacts (Civil/Criminal 740-670-5791; Domestic Relations 740-670-5392);
- [Records and Archives clerk holdings](https://lickingcounty.gov/depts/records_n_archives/list_of_holdings_by_department/clerk_of_courts.htm)
  describe many historical series extending from the 1810s through 1992 or
  1994;
- the Sheriff foreclosure archive and RealAuction add case number, parcel,
  purchaser, price, and auction lifecycle observations;
- Recorder PAX can resolve an exact instrument and PDF, while Auditor and OGRIP
  sources add parcel, owner, value, address, transfer, and geometry context.

These alternatives are not relabeled as the missing docket or pleading. They
remain independently attributable records that can keep an investigation
moving and often provide a selector for a later court or Clerk request.

## Reusable test and triage pattern

For each new court party index, fixture and live-sentinel coverage should answer
four separate questions:

1. What is one physical result occurrence, and are exact duplicates retained?
2. How does the source signal a match versus ordered spillover or another
   nonmatch?
3. What proves exhaustion: spillover, an explicit empty state, a native last
   page, or nothing beyond a ceiling?
4. Can the transport truncate a row or page independently of the advertised
   row count?

That pattern caught materially different behaviors across three nearby courts:
CIO's lexical and byte-buffer boundaries, Municipal Court's hard 250 ceiling,
and CourtView's native multi-page traversal. Licking adds a fourth useful state:
a verified source and official alternatives even when terminal record execution
currently needs a human browser step.
