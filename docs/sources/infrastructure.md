# Infrastructure Recon (Shodan, crt.sh, Wayback, URLScan)

Digital infrastructure investigation tools. Only relevant when the target has a known domain, IP, or digital footprint.

## Shodan

**Auth:** Paid API key (SHODAN_API_KEY) — 99 query credits
**Tool:** `tools/query_shodan.py`

```bash
uv run python tools/query_shodan.py domain "TARGET_DOMAIN" --output $WORKDIR/shodan-domain.json
uv run python tools/query_shodan.py search "ssl:TARGET_DOMAIN" --output $WORKDIR/shodan-ssl.json
uv run python tools/query_shodan.py host TARGET_IP --output $WORKDIR/shodan-host.json
uv run python tools/query_shodan.py search "org:TARGET_ORG" --output $WORKDIR/shodan-org.json
```

**Note:** `search` costs 1 query credit. `host` is free. `domain` uses DNS, not search credits.

## crt.sh (Certificate Transparency)

**Auth:** None
**Tool:** `tools/query_crtsh.py`

```bash
uv run python tools/query_crtsh.py search "TARGET_DOMAIN" --output $WORKDIR/crtsh-search.json
uv run python tools/query_crtsh.py subdomains "TARGET_DOMAIN" --output $WORKDIR/crtsh-subs.json
uv run python tools/query_crtsh.py timeline "TARGET_DOMAIN" --output $WORKDIR/crtsh-timeline.json
```

## Wayback Machine

**Auth:** None
**Tool:** `tools/query_wayback.py`

```bash
uv run python tools/query_wayback.py snapshots "TARGET_URL" --output $WORKDIR/wayback-snaps.json
uv run python tools/query_wayback.py timeline "TARGET_DOMAIN" --output $WORKDIR/wayback-timeline.json
uv run python tools/query_wayback.py first "TARGET_DOMAIN" --output $WORKDIR/wayback-first.json
uv run python tools/query_wayback.py diff "TARGET_URL" --output $WORKDIR/wayback-diff.json
```

## URLScan.io

**Auth:** Free for search; API key for submit
**Tool:** `tools/query_urlscan.py`

```bash
uv run python tools/query_urlscan.py search "domain:TARGET_DOMAIN" --output $WORKDIR/urlscan-search.json
uv run python tools/query_urlscan.py technologies "domain:TARGET_DOMAIN" --output $WORKDIR/urlscan-tech.json
```

## What To Look For

- **Subdomain enumeration**: Hidden services, staging environments, internal tools
- **SSL certificate history**: Organization names, email addresses in cert fields
- **Shared hosting**: Other domains on the same IP (virtual hosting reveals related entities)
- **Historical web content**: Removed pages, changed team/about pages, deleted press releases
- **Technology stack**: What software runs the target's infrastructure?
- **DNS records**: MX records reveal email providers, TXT records reveal service integrations

## Findings

- Infrastructure data: `claim_type=direct_quote` (technical records)
- Infrastructure analysis: `claim_type=inference`
- `--sources shodan crtsh wayback urlscan`
