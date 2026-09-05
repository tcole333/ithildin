# Corporate Registries

Tools for corporate entity search, officer lookup, and ownership tracing across 25+ jurisdictions.

**When to read this module:** When running /trace-entity, investigating corporate structures, or tracing shell companies.

## Tool Inventory

| Tool | Jurisdiction | Method | Auth | Data |
|------|-------------|--------|------|------|
| `query_registry.py` | All ingested | Local SQLite (registry.db) | None | Unified search across all ingested entities, officers, agents, UCC filings |
| `registry_address_index.py` | All ingested | Generated local FTS5 sidecar | None | Principal, mailing, officer, and agent address fragments |
| `ingest_florida.py` | FL | SFTP bulk (fixed-width) | Public creds | 3M+ entities, officers, agents, filings |
| `query_california.py` | CA | BizFile UI + official search response | Node Playwright + Chrome | Bounded keyword/entity-number search (Imperva WAF) |
| `ingest_california.py` | CA | Azure APIM REST API | CA_SOS_API_KEY (free) | Keyword search, entity detail, ingest to registry.db |
| `ingest_newyork.py` | NY | Socrata SODA API (data.ny.gov) | None | 4.1M active corps, 20M filings, 17M addresses |
| `query_texas.py` | TX | Comptroller data-search proxy | None | Franchise tax entities, officers, agents |
| `query_michigan.py` | MI | LARA portal API (Cloudflare WAF) | Node.js browser helper | Entities, officers via browser bypass |
| `query_newjersey.py` | NJ | HTML form scraping | None | Name/ID search only (no officers in free portal) |
| `query_massachusetts.py` | MA | ASP.NET WebForms (Imperva WAF) | Node.js browser helper | Entity, officers, agent, name changes |
| `query_massachusetts_ucc.py` | MA (UCC) | Public WebForms search | None; Node Playwright + installed Chrome | Organization/individual search, filing-number lookup; separate lapsed archive |
| `query_nevada.py` | NV | SilverFlume portal (Incapsula WAF) | Playwright/Chrome browser helper | Officers, agents, filing history, name history |
| `query_wyoming.py` | WY | WyoBiz ASP.NET (F5 WAF + CAPTCHA) | Node.js browser helper | Key crypto-LLC state; parties, agents, filings |
| `query_tennessee_corps.py` | TN | TNCaB portal (Cloudflare Turnstile) | Node.js browser helper | Officers, agents, filings, standing |
| `query_puertorico.py` | PR | REST API (rceapi.estado.pr.gov) | None | Act 60 entities; officers, agents, articles, filings |
| `ingest_newmexico.py` | NM | REST API (enterprise.sos.nm.gov) | None | Entity search/detail/history (Azure WAF, 3-5s delays) |
| `ingest_dc.py` | DC | ArcGIS FeatureServer + CorpOnline API | None | 492K entities; principals, directors, NAICS |
| `ingest_colorado.py` | CO | Socrata SODA API (data.colorado.gov) | None | 1.3M+ entities since 1864 |
| `ingest_maryland.py` | MD | Web scraping (egov.maryland.gov) | MCP Playwright + manual CAPTCHA | Officers, agent, addresses (reCAPTCHA v2) |
| `ingest_ohio.py` | OH | SOS Business Search API (Cloudflare) | cf_clearance cookie | Entity, agent, organizer search; filing history |
| `ingest_usvi.py` | USVI | Catalyst portal scraping | None | No officers without paid cert request |
| `ingest_panama.py` | PA | ICIJ + OCCRP Aleph + PANADATA | PANADATA optional ($0.50/lookup) | ~800K entities across 3 sources |
| `query_delaware.py` | DE | OpenCorporates API | OPENCORPORATES_API_KEY | Search, entity, filings, batch |
| `query_hongkong.py` | HK | OpenCorporates API (ICRIS) | OPENCORPORATES_API_KEY | Search, entity, filings, batch |
| `query_cyprus.py` | CY | OpenCorporates API | OPENCORPORATES_API_KEY | Offshore hub; search, entity, filings |
| `query_opencorporates.py` | 160+ | OpenCorporates API | OPENCORPORATES_API_KEY | Global search, officers, addresses, filings, statements |
| `query_france.py` | FR | SIRENE API (gouv.fr) | None | SIREN/SIRET, dirigeants, activity codes |
| `query_israel.py` | IL | data.gov.il CKAN API | None | 720K+ companies (Hebrew + English) |
| `query_zefix.py` | CH | SPARQL (lindas.admin.ch) | None | All Swiss companies, foundations, associations |
| `ingest_uk_companies_house.py` | UK | REST API | COMPANIES_HOUSE_API_KEY (free) | Officers, PSC, filings, officer-search |
| `ingest_ucc_florida.py` | FL (UCC) | SFTP bulk (fixed-width) | Public creds | Federal tax liens (~99% IRS); NOT commercial UCC |
| `ingest_ucc_newmexico.py` | NM (UCC) | REST API (enterprise.sos.nm.gov) | None | Debtor/secured party search, filing detail |

UK Companies House read-only commands (`search`, `company`, `officers`, `psc`, `filings`, `officer-search`, `officer-appointments`, and `insolvency`) support `--output FILE` for structured JSON artifacts.
Company `search` uses the phrase-sensitive advanced name endpoint by default;
add `--broad` only when token-based discovery is intentional.

## Unified Interface: `query_registry.py`

Prefer this tool over jurisdiction-specific tools. Searches all previously ingested data in `registry.db`.

### Subcommands

```bash
# Entity search (FTS5 full-text search across all jurisdictions)
uv run python tools/query_registry.py search "Financial Trust" --jurisdiction fl --limit 20
uv run python tools/query_registry.py search "LSJE" --exact

# Entity detail (by registry.db internal ID)
uv run python tools/query_registry.py entity 42

# Officer search (cross-jurisdiction)
uv run python tools/query_registry.py officers "Darren Indyke" --limit 20

# Address search (principal, mailing, officer, and agent addresses)
uv run python tools/query_registry.py address "457 Madison" --limit 20

# Registered agent search
uv run python tools/query_registry.py agent "CT Corporation" --limit 20

# Filing history for an entity
uv run python tools/query_registry.py filings 42 --limit 50

# UCC filing search (debtors + secured parties)
uv run python tools/query_registry.py ucc-search "Epstein" --jurisdiction fl --role debtor
uv run python tools/query_registry.py ucc-filing 123
uv run python tools/query_registry.py ucc-collateral "aircraft"
uv run python tools/query_registry.py ucc-party "Wells Fargo" --role secured

# Stats and metadata
uv run python tools/query_registry.py stats
uv run python tools/query_registry.py jurisdictions
uv run python tools/query_registry.py ucc-stats
```

### Generated Address Index

The `address` subcommand uses the generated, contentless FTS5 trigram sidecar
`datasets/registry_address_search.db`. It searches principal, mailing, officer,
and agent addresses without adding tables or indexes to `registry.db`. Build it
after the registry is created or updated:

```bash
uv run python tools/registry_address_index.py build --output /tmp/address-index-build.json
uv run python tools/registry_address_index.py status
uv run python tools/registry_address_index.py validate --output /tmp/address-index-validation.json
```

The builder normalizes case, accents, punctuation, and `P.O.` spacing using a
versioned normalization contract. It streams into a same-directory temporary
file, checks the source fingerprint and SQLite/FTS integrity, then publishes the
complete file atomically. An existing sidecar is retained as `.bak` during a
rebuild and can be restored with `registry_address_index.py rollback`. Build,
publish, and rollback operations share an interprocess lifecycle lock; an
overlapping operation fails without mutating either published file.

Address queries keep the existing result buckets and alphabetical per-bucket
limits, with row ID as the deterministic tie-breaker for equal names. Selectors
must contain at least three normalized letters or digits.
Missing, stale, or invalid sidecars fail with rebuild instructions; the command
does not fall back to a full `registry.db` scan.

The query route counts FTS candidates independently for each bucket. At 10,000
or fewer candidates it materializes matching row IDs and sorts the joined base
rows. Above 10,000 it walks the existing alphabetical base-name index and uses
a correlated FTS `rowid + MATCH` constraint for membership, stopping at the
requested limit. Both routes return the same strict global alphabetical top-N;
the adaptive route never tests raw address columns with `LIKE` or another scan.

## When to Use State-Specific Tools

Use jurisdiction-specific tools when you need to:
1. **Ingest new data** into registry.db (`ingest-entity`, `ingest-batch`, `ingest-search`)
2. **Access live/fresh data** not yet in registry.db
3. **Use jurisdiction-specific features** (e.g., PR articles of incorporation, NY address datasets, NV stock info)

### Common Patterns Across State Tools

Most state tools share these subcommands:
```bash
search "QUERY"                 # Search by entity name
entity <ID>                    # Get entity detail
ingest <ID>                    # Ingest single entity into registry.db
ingest-search "QUERY"         # Search + ingest all results
ingest-batch "QUERY"          # Same as ingest-search (naming varies)
```

## Auth Requirements Summary

| Requirement | Tools |
|------------|-------|
| **None** | query_registry, query_texas, query_newjersey, query_puertorico, ingest_newyork, ingest_colorado, ingest_newmexico, ingest_dc, query_france, query_israel, query_zefix |
| **Free API key** | ingest_california (CA_SOS_API_KEY; approval may be delayed), ingest_uk_companies_house (COMPANIES_HOUSE_API_KEY) |
| **Paid API key** | query_opencorporates, query_delaware, query_hongkong, query_cyprus (OPENCORPORATES_API_KEY — basic 500/mo, 200/day) |
| **Node.js browser helper** | query_california, query_michigan, query_massachusetts, query_nevada, query_wyoming, query_tennessee_corps |
| **MCP Playwright** | ingest_maryland (CAPTCHA) |
| **Manual CAPTCHA** | ingest_maryland (reCAPTCHA v2 on first search), ingest_ohio (cf_clearance cookie) |

California BizFile uses a short-lived headed Chrome process and a dedicated
local profile to retain Imperva clearance. Check the runtime first, then issue a
bounded keyword or normalized entity-number search:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/query_california.py runtime-check --output "$WORKDIR/ca-runtime.json"
uv run python tools/query_california.py probe --output "$WORKDIR/ca-probe.json"
uv run python tools/query_california.py search "APPLE" --limit 25 --output "$WORKDIR/ca-search.json"
uv run python tools/query_california.py search C0726332 --by-number --limit 5 --output "$WORKDIR/ca-number.json"
```

The helper requires Node.js, `playwright` or `playwright-core`, and installed
Google Chrome. It launches one bounded operation per process and closes Chrome
afterward; it does not attach to an MCP/Codex browser or start a daemon. Headless
mode is not supported by the verified path because Imperva returns 403. Advanced
filters, entity detail, history, and ingestion currently fail explicitly until
their new-runtime flows are live-verified. Interactive search is not a substitute
for the weekly statewide bulk importer tracked by infrastructure request #130.
Do not block California research on a pending developer-key application: use
this keyless bounded search for individual entities. For repeatable bulk work,
log into BizFile and order `BE Bulk Order - Weekly Data & Images` (free); a
`BE Bulk Order Master Unload of Data` costs $100 and is needed for a complete
baseline before weekly deltas can keep it current.

Nevada SilverFlume uses session-backed entity and history pages behind
Incapsula. Verify the local runtime before searching, and warm the persistent
browser session if the portal presents a challenge:

```bash
uv run python tools/query_nevada.py runtime-check
uv run python tools/query_nevada.py warmup
uv run python tools/query_nevada.py probe --output /tmp/nv-probe.json
uv run python tools/query_nevada.py search "APOLLO" --limit 25 --output /tmp/nv-search.json
uv run python tools/query_nevada.py entity E0125332010-5 --output /tmp/nv-entity.json
```

The helper requires Node.js, the `playwright` or `playwright-core` package, and
Google Chrome by default. `runtime-check` reports actionable installation errors
without opening a browser. Set `NV_BROWSER_CHANNEL=chromium` only after installing
the Playwright browser with `npx playwright install chromium`.

## Known Quirks

- **query_california.py**: Imperva can remount/detach the Angular search DOM. The helper retries that condition twice and otherwise returns actionable challenge guidance. Search is capped at 500 and defaults to 25; detail/history/ingest are not yet supported by the new runtime.
- **ingest_florida.py**: Fixed-width COBOL-era format (1440 chars/record). SFTP creds are public: `Public / PubAccess1845!`
- **ingest_newyork.py**: Three separate Socrata datasets. Officer names are in the filings dataset, not the main entity dataset.
- **query_newjersey.py**: Free portal exposes only 5 fields (name, ID, city, type, date). No officers/agents. Paid portal has more but requires account.
- **ingest_usvi.py**: Officers/directors are NOT available without paying for a certificate request. Only basic entity info is public.
- **ingest_panama.py**: Combines 3 sources (ICIJ ~200K, OCCRP ~600K, PANADATA live). Direct registry scraping impossible (Blazor WebSocket).
- **query_opencorporates.py**: Basic tier has 500 calls/month, 200/day max. Use `account-status` to check remaining credits.
- **ingest_ucc_florida.py**: Despite the name, this is federal lien data (IRS), NOT commercial UCC Article 9. Commercial UCC is at floridaucc.com (separate system).
- **ingest_ohio.py**: Requires manually obtaining a cf_clearance cookie from Chrome DevTools. Cookie expires frequently.
- **ingest_newmexico.py / ingest_ucc_newmexico.py**: Azure WAF requires 3-5 second delays between requests.
- **query_wyoming.py**: Requires `warmup` subcommand before first search to establish session through F5 WAF.

## Skills That Use These Tools

| Skill | How It Uses Registries |
|-------|----------------------|
| `/trace-entity` | Primary consumer. Searches unified registry, then fans out to jurisdiction-specific tools for live data and ingest. |
| `/deep-investigate` | Agent B traces corporate structures. Uses query_registry for known entities, state tools for new ingests. |
| `/landscape-scan` | Broad entity search across multiple jurisdictions to map organizational footprints. |

## Investigation Patterns

### Shell Company Tracing
1. Start with `query_registry.py search "Entity Name"` to check all ingested jurisdictions
2. Use `officers` to find who controls the entity
3. Search those officer names back through `officers` to find other entities they control
4. Use `agent` to find shared registered agents (common shell pattern: same agent across dozens of entities)
5. Use `address` to find entities sharing a principal address

### Cross-Jurisdiction Mapping
1. Search unified registry to see where an entity is registered
2. For each jurisdiction hit, use the state-specific tool to get live data and ingest it
3. Check `query_opencorporates.py` for jurisdictions not yet ingested locally
4. Use `query_opencorporates.py officers "Person Name"` for global officer search

### Offshore Structure Identification
1. Check USVI (`ingest_usvi.py`) for VI-registered entities
2. Search Panama (`ingest_panama.py`) across ICIJ and OCCRP datasets
3. Check Cyprus (`query_cyprus.py`) for Russian-linked structures
4. Check Hong Kong (`query_hongkong.py`) for Asia-Pacific structures
5. Use UK Companies House (`ingest_uk_companies_house.py`) PSC endpoint for persons of significant control

### UCC/Lien Research
1. Search unified UCC: `query_registry.py ucc-search "Entity" --role debtor`
2. Check collateral descriptions: `ucc-collateral "aircraft"` or `"all assets"`
3. For Florida: note that `ingest_ucc_florida.py` covers federal liens (IRS), NOT commercial UCC
4. For New Mexico: `ingest_ucc_newmexico.py` covers both debtor and secured party search
5. For Massachusetts: use `query_massachusetts_ucc.py` for live public UCC records; follow the search controls below.

### Massachusetts UCC: `query_massachusetts_ucc.py`

**Bulk-access status, reviewed September 4, 2026:** the Secretary's
[Terms of Use](https://www.sec.state.ma.us/divisions/terms.htm) permit individual
business-record searches but prohibit scraping/crawling by automated or manual
means. The Boston full-roster portal run is paused pending a supported
bulk route. [950 CMR 140.11](https://www.sec.state.ma.us/divisions/corporations/pdf-html/950_CMR_140.htm)
publishes an index extract and image service, with data layout available on
request. Ask `corpinfo@sec.state.ma.us` for baseline/history coverage, current
price, minimum order and applicable terms before ordering. The published
weekly price does not establish that one week includes a historical baseline.

Corporate bulk records are a separate published program under
[950 CMR 113.15](https://www.sec.state.ma.us/divisions/corporations/download/950113.pdf#page=7).
Confirm its entity-type coverage and historical role fields separately; do not
assume a UCC order includes corporate data. Officers, directors, managers and
agents are reported roles, not a complete equity-ownership table. The Boston
[access review](../../reports/boston-liquor-license-collateral-2026-09-03/full-review/corporate-records-access-options.md)
and [combined unsent inquiry](../../reports/boston-liquor-license-collateral-2026-09-03/full-review/massachusetts-bulk-data-inquiry-draft.md)
preserve the verified routes and unresolved product questions.

The [Secretary of the Commonwealth's public UCC search](https://corp.sec.state.ma.us/corpweb/UCCSearch/UCCSearch.aspx)
supports organization and individual names, filing numbers, and a separate
lapsed-record archive. The default database is the current database, which can
retain filings for one year after lapse; preserve reported status and dates
without treating current-database membership as active lien status.
It uses Node Playwright with installed Chrome in a temporary, visible browser
session and needs no account. `runtime-check` checks local dependencies without
opening Chrome or contacting the portal. `source_report.py` reports that result
as `configured`; run `probe` to check whether the live public form is available.
An HTTP 200 response alone is insufficient: ordinary HTTP
requests can receive an Imperva challenge instead of the search form.

```bash
uv run python tools/query_massachusetts_ucc.py runtime-check --output "$WORKDIR/ma-ucc-runtime.json"
uv run python tools/query_massachusetts_ucc.py probe --output "$WORKDIR/ma-ucc-probe.json"
uv run python tools/query_massachusetts_ucc.py search-org "HARVARD" --limit 25 --output "$WORKDIR/ma-ucc-org.json"
uv run python tools/query_massachusetts_ucc.py search-individual "SMITH" --first "JOHN" --output "$WORKDIR/ma-ucc-person.json"
uv run python tools/query_massachusetts_ucc.py search-org "BANK" --role secured --search-type begins --output "$WORKDIR/ma-ucc-secured.json"
uv run python tools/query_massachusetts_ucc.py search-org "HARVARD" --lapsed --output "$WORKDIR/ma-ucc-lapsed.json"
uv run python tools/query_massachusetts_ucc.py filing "<FILING_NUMBER>" --output "$WORKDIR/ma-ucc-filing.json"
```

Search controls:

- `--search-type begins` is the default. `article9` uses the portal's Article 9
  name search; `exact` is available for organizations only.
- `--role debtor` is the default; `secured` and `assignee` require `begins`.
- `search-individual` takes the last name separately from optional `--first`,
  `--middle`, and `--suffix` fields.
- `--city`, `--state`, and `--since YYYY-MM-DD` narrow the search. `--limit`
  accepts 1–500 returned occurrence rows and defaults to 25. Use uppercase
  two-letter state codes. Multiple occurrences can
  refer to one filing; do not treat the row count as a unique-filing count.
- `--lapsed` selects a separate archive. Run it separately when historical
  coverage matters; an empty current search does not establish archive absence.

For a prepared Boston holder queue, `boston_ucc_runner.py --queue QUEUE.json
--output-dir CAPTURE_DIR --scope current --max-queries 20 --batch-size 20`
reuses one owned, isolated Chrome for a bounded serial batch. `--scope lapsed`
is separate. It merges the queue's sibling `ucc-cua/events.jsonl` by default
(override with `--events`), skips completed scopes, and defers both invalid
inputs and nonempty `name_mode_review_reasons` to `needs-review.json`. The
existing input flag and organization-query completions retain their original
meaning; they do not certify all possible individual/partnership name modes.
Raw HTML responses, parsed results, append-only events, and queue progress are
checkpointed before the next request. Resume recovers saved evidence without
requerying it; `STOP` in the output directory stops before another request.
The browser is recycled after 1–50 requests (`--batch-size`, default 20), with
at least one second between navigations and no retry of an access challenge.
The new persistent session path has offline regression coverage only. Its live
three-query parity check was canceled after Access Denied / Error 15 on
September 4, 2026. One later navigation in the same in-app browser reached the
search form, without testing result or document access. Full-roster portal
batches remain paused because of the published bulk-collection restriction;
a slower rate or different browser does not establish permission. The saved
runner is an implementation artifact, not an approved public-portal bulk route.

`filing` takes a 12-digit filing number and also accepts `--lapsed`. Name inputs
follow the source's limits: organization 175 characters, individual last name 35,
first/middle/suffix 25 each, and city 35. The CLI rejects longer values before
opening the browser.

All commands support `--output FILE`. This version provides live lookup without
ingesting into `registry.db`; local `query_registry.py ucc-search --jurisdiction ma`
therefore does not replace a live search. Store findings with
`--sources massachusetts_ucc` and evidence references `MA-UCC:<filing-number>`.
The citation opens the official public search page. Preserve the source-returned
history/detail URLs in the JSON evidence; those URLs cannot be derived reliably
from the filing number alone.

Filing-number lookup returns the available UCC1/UCC3 history sections, named
party/address blocks, collateral text where published, and source-linked PDF
viewer URLs. Use the `filing` command to retrieve a known filing rather than
constructing a history URL from its number.

The portal's paid certified UCC11 search and its separate liens database remain
complementary routes when a certified result or non-UCC lien coverage is needed.
The public UCC adapter does not submit paid requests or query that liens database.

`boston_ucc_filing_review.py build` is an **offline** companion for a Boston
license-holder inventory. Supply `--queue`, `--observations`, `--samples`, and
`--output`. It validates saved CUA index captures with the existing bridge parser,
groups original filing numbers while retaining party occurrences and namesakes,
and keeps history review, original PDFs, and amendment PDFs separate. Optional
`--tool-index HOLDER_ID=FILE` and `--tool-history FILE` import existing MA query
tool JSON; a captured history does not certify analyst review. Explicit
`--decisions FILE` records require evidence and a note, including for false-positive
rejections. No network or investigation database writes occur. Rebuild to include
new captures; malformed records and unresolved original numbers remain explicit.
See the generated filing queue's limitations for formation-jurisdiction, alias,
individual-mode, and current-versus-lapsed coverage gaps. No loan count is inferred.

## Database Schema

Ingest-capable state tools use a shared `registry.db` with unified tables:
- `registry_entities` — one row per corporate entity (name, type, status, addresses, EIN)
- `registry_officers` — officers/directors/managers with addresses and dates
- `registry_agents` — registered agents with address history
- `registry_filings` — filing/event history (annual reports, amendments, dissolutions)
- `registry_name_history` — tracks name changes over time
- `ucc_filings` / `ucc_debtors` / `ucc_secured_parties` / `ucc_collateral` — UCC/lien data

FTS5 full-text search indexes cover entity, officer, and agent names. Address
fragments are served by the generated trigram sidecar described above.
