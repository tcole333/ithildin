# OSINT & Infrastructure Recon

Tools for passive infrastructure reconnaissance: certificate transparency, web archiving, internet-connected device search, URL scanning, username enumeration, and aircraft registry.

**When to read this module:** When running /investigate-infra, mapping digital infrastructure, tracking domain ownership changes, or identifying exposed services.

## Tool Inventory

| Tool | Source | Auth | Rate Limit | Data |
|------|--------|------|------------|------|
| `query_crtsh.py` | crt.sh (Sectigo CT aggregator) | None | None enforced (be polite, 1 req/sec) | Certificate issuance, subdomains, issuer patterns |
| `query_wayback.py` | Internet Archive CDX API | None | None enforced (be polite, 1 req/sec) | Historical snapshots, content diffs, first-seen dates |
| `query_shodan.py` | Shodan API (api.shodan.io) | SHODAN_API_KEY (paid) | 1 req/sec (free), higher on paid | IP details, open ports, DNS, SSL certs, org search |
| `query_urlscan.py` | URLScan.io API | URLSCAN_API_KEY (optional) | 60 req/min (search), 2 req/min (submit) | Tech stacks, linked domains, HTTP transactions, scripts |
| `query_maigret.py` | Maigret CLI (local) | None (requires `maigret` package) | N/A (local execution) | Username matches across 2500+ sites |
| `ingest_faa.py` | FAA ReleasableAircraft bulk data | None | N/A (bulk download) | Aircraft registration, ownership, N-numbers, addresses |

## Subcommands and Examples

### `query_crtsh.py` — Certificate Transparency

Discovers certificates issued for a domain or organization. Essential for finding subdomains, tracking infrastructure changes, and identifying related domains.

```bash
# Search by domain (exact match)
uv run python tools/query_crtsh.py search example.com

# Include subdomains (wildcard search)
uv run python tools/query_crtsh.py search example.com --subdomains

# Search by organization name (O= field in certificate)
uv run python tools/query_crtsh.py search "Organization Name" --org

# Exclude expired certificates
uv run python tools/query_crtsh.py search example.com --exclude-expired

# Enumerate unique subdomains from SAN fields
uv run python tools/query_crtsh.py subdomains example.com

# Certificate issuance timeline (spot patterns, gaps)
uv run python tools/query_crtsh.py timeline example.com

# Get specific certificate detail
uv run python tools/query_crtsh.py cert 12345678
```

### `query_wayback.py` — Wayback Machine CDX

Queries the Internet Archive's CDX index for historical web snapshots. Essential for timeline reconstruction, detecting removed content, and proving what a site said at a specific date.

```bash
# List all captured snapshots
uv run python tools/query_wayback.py snapshots example.com

# Filter by date range
uv run python tools/query_wayback.py snapshots example.com --from 2019 --to 2020

# Include subdomains
uv run python tools/query_wayback.py snapshots "*.example.com" --subdomains

# Filter by MIME type (e.g., only PDFs)
uv run python tools/query_wayback.py snapshots example.com --mimetype application/pdf

# Snapshot frequency timeline (when was the site most active?)
uv run python tools/query_wayback.py timeline example.com

# First-ever capture of a URL
uv run python tools/query_wayback.py first example.com

# Compare two snapshots (detect content changes)
uv run python tools/query_wayback.py diff example.com --from 20190101 --to 20200101

# Fetch a specific snapshot's content
uv run python tools/query_wayback.py fetch example.com --timestamp 20190715
```

### `query_shodan.py` — Shodan Internet Device Search

Searches internet-connected devices by IP, domain, organization, or service banner. Reveals hosting providers, exposed services, and organizational infrastructure.

```bash
# Full host detail (ports, services, banners, location)
uv run python tools/query_shodan.py host 198.202.211.1

# Search by SSL certificate, org, port, etc.
uv run python tools/query_shodan.py search "ssl:leadingthefuture.com"
uv run python tools/query_shodan.py search "org:\"Webflow\" port:443" --limit 50

# DNS records for a domain
uv run python tools/query_shodan.py domain leadingthefuture.com

# Resolve hostnames to IPs
uv run python tools/query_shodan.py dns-resolve google.com,example.com

# Reverse DNS lookup
uv run python tools/query_shodan.py reverse-dns 8.8.8.8,8.8.4.4

# SSL certificate details
uv run python tools/query_shodan.py ssl-cert leadingthefuture.com

# Check API credit balance
uv run python tools/query_shodan.py info
```

### `query_urlscan.py` — URLScan.io Passive Analysis

Searches past web scans to discover technology stacks, linked domains, and page behavior without touching the target.

```bash
# Search by domain, IP, page title, server, etc.
uv run python tools/query_urlscan.py search domain:example.com
uv run python tools/query_urlscan.py search ip:198.202.211.1
uv run python tools/query_urlscan.py search "page.title:Leading The Future"
uv run python tools/query_urlscan.py search "server:cloudflare AND domain:example.com"

# Get full scan result (HTTP transactions, DOM, screenshots)
uv run python tools/query_urlscan.py result <scan-uuid>

# Extract detected technologies (frameworks, analytics, CDNs)
uv run python tools/query_urlscan.py technologies <scan-uuid>

# Extract all outbound links from a scanned page
uv run python tools/query_urlscan.py links <scan-uuid>
```

### `query_maigret.py` — Username Enumeration

Searches for a username across 2500+ sites. Results are INFERENCE ONLY -- a matching username does NOT confirm identity.

```bash
# Search top 50 sites (default)
uv run python tools/query_maigret.py search "targetuser"

# Search top N sites
uv run python tools/query_maigret.py search "targetuser" --top 30

# Output to file
uv run python tools/query_maigret.py search "targetuser" --output results.json
```

### `ingest_faa.py` — FAA Aircraft Registry

Downloads and searches the FAA's bulk aircraft registration data. Covers all US-registered aircraft with owner details.

```bash
# First-time setup: download and ingest
uv run python tools/ingest_faa.py download
uv run python tools/ingest_faa.py ingest

# Search by owner name or entity
uv run python tools/ingest_faa.py search "JEGE"
uv run python tools/ingest_faa.py search "Epstein"

# Lookup by N-number (tail number)
uv run python tools/ingest_faa.py n-number N212JE

# Search by registrant address
uv run python tools/ingest_faa.py address "457 Madison"

# Database stats
uv run python tools/ingest_faa.py stats
```

## Auth Requirements

| Tool | Variable | How to Get | Cost |
|------|----------|-----------|------|
| `query_crtsh.py` | None | Free, no auth | Free |
| `query_wayback.py` | None | Free, no auth | Free |
| `query_shodan.py` | `SHODAN_API_KEY` | [shodan.io](https://shodan.io/) | Paid ($49 one-time for basic; 99 query credits). `search` requires paid plan. `host`, `dns-resolve`, `reverse-dns` work on free. |
| `query_urlscan.py` | `URLSCAN_API_KEY` | [urlscan.io](https://urlscan.io/) | Free tier for searching public scans. API key needed for submission and higher rate limits. |
| `query_maigret.py` | None | Install: `uv add maigret` | Free (open source tool) |
| `ingest_faa.py` | None | Free bulk download | Free (~60MB ZIP, refreshed daily) |

## Known Quirks

- **query_crtsh.py**: crt.sh frequently overloaded -- returns non-JSON HTML when under load. Retry after a few minutes. Deduplicates by serial_number. Large domains (e.g., google.com) may return thousands of results and timeout.
- **query_wayback.py**: CDX API returns JSON with first row as headers, rest as data (tool handles this). The `--collapse` flag deduplicates by digest to reduce noise. Heavy queries on popular URLs may timeout at 60s.
- **query_shodan.py**: `search` subcommand costs query credits (paid plan only, HTTP 402 on free). `host` lookups are free but rate-limited to 1/sec. Uses Shodan query syntax: `ssl:`, `org:`, `port:`, `asn:`, `country:`, etc. Empty/invalid key returns HTTP 401.
- **query_urlscan.py**: Only searches PUBLIC scans. Private/unlisted scans not visible. The `search` subcommand uses Elasticsearch query syntax: `domain:`, `ip:`, `page.title:`, `server:`, etc. The `--after` flag enables cursor-based pagination.
- **query_maigret.py**: Results are INFERENCE confidence only. A matching username does NOT confirm identity -- many people share usernames. Timeout is 120 seconds. Requires the `maigret` package to be installed (`uv add maigret`). Returns structured JSON with site name, URL, and match status.
- **ingest_faa.py**: Requires two-step setup (`download` then `ingest`). Bulk ZIP is ~60MB, refreshed daily by FAA. Data stored locally in `datasets/faa_registry.db`. Includes both active and deregistered aircraft (MASTER + DEREG files). Registrant type codes: 1=Individual, 2=Partnership, 3=Corporation, 7=LLC.

## Skills That Use These Tools

| Skill | How It Uses Infra Tools |
|-------|------------------------|
| `/investigate-infra` | Primary consumer. Runs crt.sh subdomain enumeration, Wayback timeline, Shodan host lookup, and URLScan tech stack analysis in sequence. |
| `/deep-investigate` | Agent D handles infrastructure recon. Uses crt.sh for cert history, Wayback for timeline gaps, Shodan for IP attribution. |
| `/trace-entity` | Checks domain registrations and certificate history to link entities to web infrastructure. |

## Investigation Patterns

### Domain Attribution
1. Start with `query_crtsh.py subdomains target.com` to enumerate all subdomains
2. Use `query_shodan.py domain target.com` for DNS records and IP resolution
3. Check `query_shodan.py host <IP>` for each resolved IP to find co-hosted domains
4. Cross-reference with `query_urlscan.py search domain:target.com` for technology stack

### Timeline Reconstruction
1. Use `query_wayback.py first target.com` to find when site first appeared
2. Run `query_wayback.py timeline target.com` to see capture frequency over time
3. Use `query_wayback.py diff` to detect content changes around key dates
4. Cross-reference with `query_crtsh.py timeline target.com` for cert issuance patterns

### Removed Content Recovery
1. Use `query_wayback.py snapshots target.com/removed-page` to find captures
2. Fetch specific snapshot: `query_wayback.py fetch target.com/page --timestamp 20190715`
3. Compare before/after: `query_wayback.py diff target.com/page --from 20190101 --to 20200101`

### Aircraft Ownership Tracing
1. Search by name: `ingest_faa.py search "Entity Name"`
2. Lookup specific tail number: `ingest_faa.py n-number N212JE`
3. Search by address to find co-located registrations: `ingest_faa.py address "457 Madison"`
4. Cross-reference owner entities with corporate registry data
