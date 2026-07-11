---
name: investigate-infra
description: Passive digital infrastructure investigation — domains, IPs, certificates, DNS, hosting patterns
---

# $investigate-infra

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Document infrastructure observations (certificates, DNS, hosting) as facts. Do not theorize about intent — record what exists and let Layer 2 analysis agents interpret patterns.

Passive infrastructure reconnaissance of a domain, IP address, organization, or person's digital footprint. Map hosting, certificates, DNS topology, vendor stacks, and deployment patterns using only publicly observable signals.

Inspired by the [vmfunc/Persona investigation](https://vmfunc.re/blog/persona) methodology — every misconfigured header, every certificate SAN, every DNS wildcard is a breadcrumb.

## Arguments

- Required: target (domain, IP, org name, or person name)
- Examples:
  - `$investigate-infra leadingthefuture.com`
  - `$investigate-infra 198.202.211.1`
  - `$investigate-infra org:"Example Trust Company"`
  - `$investigate-infra "Person Name" — map digital footprint of known domains`

## The Unseeing Discipline

Before executing any search, internalize this:

**You are not looking at websites. You are looking at machines.** A domain is an abstraction over DNS records. A website is an abstraction over HTTP responses from a process on a server at an IP address. A "company" online is an abstraction over certificates, hosting accounts, deployment pipelines, and vendor relationships.

Strip the abstractions. At every step ask:

1. **What is this system really made of?** A website is IPs, ports, certificates, headers, DNS records, deployment configs. Those are the atoms — the "website" is the comfortable fiction.
2. **What's leaking that wasn't meant to be visible?** CSP headers expose vendor stacks. Certificate SANs reveal internal service names. Server headers identify infrastructure. Source maps expose codebases. Kubernetes pod names in headers reveal deployment architecture.
3. **What's conspicuously absent?** A domain with no MX records never receives email — so how do they communicate? A host with no HTTPS in 2026 is either negligent or deliberate. An org with one visible domain probably has more — where are they?
4. **What would I see if I dropped one abstraction level?** Don't look at the webpage — look at the HTTP response. Don't look at the domain — look at the certificate. Don't look at the certificate — look at who issued it and what else they issued for the same entity.
5. **What connects to what through channels the surface doesn't show?** Two "separate" organizations sharing an IP range, a certificate authority, a CDN configuration, or a Google Analytics ID are revealing a relationship their marketing websites would never admit.

This is defamiliarization applied to infrastructure. The educated eye sees "a website." The unseeing eye sees a certificate issued 3 days before the entity was publicly announced, served from a Google Cloud instance in a region inconsistent with the stated business location, with a CSP header that whitelists an analytics endpoint belonging to a different company entirely.

**Negative results are primary intelligence.** The absence of expected infrastructure is often more revealing than its presence. A billion-dollar fund with a single-page Squarespace site. A "technology company" with no GitHub presence. A domain registered in 2015 that first resolves in 2019. These gaps are evidence.

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Identify Entry Points

Determine what you're starting with and what you need to discover:

| Starting with | First moves |
|---|---|
| **Domain** | DNS records, WHOIS, certificate transparency, Shodan |
| **IP address** | Shodan host lookup, reverse DNS, certificate search |
| **Organization name** | Shodan org search, web search for domains, then pivot |
| **Person name** | Search investigation DB for known domains/emails, web search, then pivot to discovered infrastructure |

```bash
# Check what we already know
uv run python tools/findings_tracker.py search "<TARGET>" --output $WORKDIR/existing-findings.json
uv run python tools/lead_tracker.py search "<TARGET>" --output $WORKDIR/existing-leads.json
```

### 2. Domain Intelligence

If you have a domain (or discover one):

```bash
# DNS topology — subdomains, record types, historical changes
uv run python tools/query_shodan.py domain <DOMAIN> --history --output $WORKDIR/dns-domain.json

# Certificate Transparency — every cert ever issued for this domain
uv run python tools/query_crtsh.py search <DOMAIN> --output $WORKDIR/ct-certs.json
uv run python tools/query_crtsh.py search <DOMAIN> --subdomains --output $WORKDIR/ct-subdomain-certs.json
uv run python tools/query_crtsh.py subdomains <DOMAIN> --output $WORKDIR/ct-subdomains.json
uv run python tools/query_crtsh.py timeline <DOMAIN> --output $WORKDIR/ct-timeline.json
```

**What to extract from CT logs:**
- **Timeline**: When was the first certificate issued? (This often predates public launch)
- **Subdomain enumeration**: Certificate SANs reveal internal service names (e.g., `api-internal.`, `staging.`, `admin.`, `watchlistdb.`)
- **Certificate rotation frequency**: 90-day Let's Encrypt = automated; annual = manual; irregular = interesting
- **Issuer changes**: Switching from Let's Encrypt to DigiCert suggests compliance requirements
- **Wildcard vs. specific**: Wildcard certs hide the subdomain landscape; specific certs enumerate it

```bash
# Historical web snapshots — when did the site first appear? What changed?
uv run python tools/query_wayback.py first <DOMAIN> --output $WORKDIR/wayback-first.json
uv run python tools/query_wayback.py timeline <DOMAIN> --monthly --output $WORKDIR/wayback-timeline.json
uv run python tools/query_wayback.py snapshots <DOMAIN> --from 2019 --to 2020 --output $WORKDIR/wayback-snapshots.json

# Content version diffing — how many unique versions of the page existed?
uv run python tools/query_wayback.py diff <DOMAIN> --from 20190101 --to 20200101 --output $WORKDIR/wayback-diff.json

# Fetch a specific archived page (use to check removed team pages, old About pages, etc.)
uv run python tools/query_wayback.py fetch <DOMAIN>/about --timestamp 20190715 --output $WORKDIR/wayback-fetch.json
```

**What to extract from Wayback:**
- **First capture date** vs. domain registration date — gap reveals pre-operational setup
- **Capture gaps** — periods with no snapshots may indicate the site was down or hidden
- **Content changes over time** — removed team members, altered About pages, disappeared press releases
- **robots.txt history** — what pages were hidden from crawlers, and when did that change?
- **Subdomains captured** — use `--subdomains` to find URLs archived under `*.domain.com`

```bash
# Passive web scans — tech stack, linked domains, HTTP transactions
uv run python tools/query_urlscan.py search "domain:<DOMAIN>" --output $WORKDIR/urlscan-search.json
# If scans found, get full details:
uv run python tools/query_urlscan.py result <UUID> --output $WORKDIR/urlscan-result.json
uv run python tools/query_urlscan.py technologies <UUID> --output $WORKDIR/urlscan-tech.json
uv run python tools/query_urlscan.py links <UUID> --output $WORKDIR/urlscan-links.json
```

**What to extract from URLScan:**
- **Technology stack**: Wappalyzer detection of frameworks, CMSes, analytics, CDNs
- **All domains contacted**: Every external resource loaded — reveals vendor relationships
- **IP addresses**: Which IPs were contacted during page load?
- **Certificates**: TLS certs observed during the scan
- **Screenshots**: Visual snapshot at scan time (available at screenshot URL)

```bash
# WHOIS — registration dates, registrant, nameservers
# Use WebSearch or direct WHOIS lookup
```
Note: Many WHOIS records are redacted (GDPR). When they are, the registrar, nameservers, creation/expiry dates, and DNS hosting provider still leak organizational information.

### 3. IP & Hosting Intelligence

```bash
# Host details — ports, services, banners, certificates, vulnerabilities
uv run python tools/query_shodan.py host <IP> --output $WORKDIR/host-detail.json

# Search for other hosts in the same org or network range
uv run python tools/query_shodan.py search "org:\"<ORG_NAME>\"" --output $WORKDIR/org-hosts.json

# SSL certificate search — find all hosts presenting certs for this domain
uv run python tools/query_shodan.py ssl-cert <DOMAIN> --output $WORKDIR/ssl-hosts.json

# Reverse DNS — what domains point to this IP?
uv run python tools/query_shodan.py reverse-dns <IP1>,<IP2> --output $WORKDIR/reverse-dns.json

# Resolve discovered domains
uv run python tools/query_shodan.py dns-resolve <DOMAIN1>,<DOMAIN2> --output $WORKDIR/dns-resolve.json
```

**What to extract from Shodan host data:**
- **Ports & services**: What's running? SSH on a non-standard port? RDP exposed? Database ports open?
- **Server headers**: `via: 1.1 google` = GCP. `server: cloudflare` = proxied. `x-powered-by: Express` = Node.js
- **SSL certificate details**: Subject CN, issuer, SANs, expiry. Cross-reference with CT logs.
- **ASN & ISP**: Cloud provider, hosting company, or self-hosted? The choice reveals budget and sophistication.
- **Geolocation**: Does the hosting location match the stated business location?
- **Vulnerabilities**: Known CVEs. Not for exploitation — for characterizing the organization's security posture.
- **Historical data**: Shodan retains snapshots. Infrastructure changes over time reveal migrations, expansions, and pivots.

### 4. HTTP Header & Response Analysis

For discovered web services, use WebFetch to inspect responses. Extract:

**Content-Security-Policy (CSP):**
The CSP header is an unintentional vendor manifest. Every allowed domain is a technology relationship:
- `*.google-analytics.com` — Google Analytics
- `*.sentry.io` — Sentry error tracking
- `*.intercom.io` — Intercom customer chat
- `*.stripe.com` — Stripe payments
- `*.chainalysis.com` — blockchain analytics (Persona/KYC use case)
- `api.openai.com` — OpenAI API integration
- Any internal domains whitelisted in CSP are especially valuable — they reveal the org's other services

**Other revealing headers:**
- `X-Powered-By` — framework/runtime
- `Server` — web server software
- `X-Request-Id` / `X-Trace-Id` — tracing infrastructure (Datadog, Jaeger)
- `X-Envoy-*` — Istio/Envoy service mesh (Kubernetes deployment)
- `X-Cloud-Trace-Context` — Google Cloud
- `X-Amzn-*` — AWS
- `Via` — proxy chain (CDN, load balancer)
- `Set-Cookie` domain attributes — reveals domain scope

### 5. Lateral Discovery (Pivoting)

This is where the investigation becomes non-linear. Every finding opens new search vectors:

**IP pivot**: Found an IP → Shodan host → discover other domains on same IP → investigate those domains
**Certificate pivot**: Found a cert SAN → discover internal service names → search for those subdomains
**Org pivot**: Found the hosting org → search Shodan for all their hosts → discover infrastructure scope
**Registrant pivot**: Found a registrant name/email → WHOIS search for other domains they registered
**Nameserver pivot**: Found nameservers → what other domains use the same nameservers?
**Analytics pivot**: Found a Google Analytics ID (UA-XXXXXX or G-XXXXXXX) → search for other sites sharing that ID (shared ownership signal)
**Favicon pivot**: Hash the favicon → search Shodan for `http.favicon.hash:<HASH>` to find related sites

```bash
# Example: find all hosts with the same favicon
uv run python tools/query_shodan.py search "http.favicon.hash:<HASH>" --output $WORKDIR/favicon-matches.json

# Example: find all hosts in the same ASN
uv run python tools/query_shodan.py search "asn:AS<NUMBER>" --limit 50 --output $WORKDIR/asn-hosts.json

# Example: find other hosts with matching SSL org
uv run python tools/query_shodan.py search "ssl.cert.subject.O:\"<ORG>\"" --output $WORKDIR/ssl-org.json
```

### 6. Infrastructure Timeline Reconstruction

Map when infrastructure appeared, changed, and disappeared:

- **Certificate issuance dates** from crt.sh (often pre-date public announcement by weeks/months)
- **Domain creation dates** from WHOIS
- **First appearance on Shodan** (when did the host first become visible?)
- **DNS record changes** from `--history` flag
- **Wayback Machine** snapshots (via WebFetch: `https://web.archive.org/web/<YEAR>*/<DOMAIN>`)

Cross-reference infrastructure timeline against:
```bash
# Investigation event timeline
uv run python tools/event_timeline.py list --output $WORKDIR/event-timeline.json

# Known entity lifecycle dates
uv run python tools/entity_tracker.py lookup --name "<ENTITY>"
```

**What to look for:**
- Infrastructure provisioned before a company was publicly announced = pre-operational setup
- Domains registered in bursts = planned infrastructure buildout
- Certificates that stop renewing = abandoned or migrated services
- IP address changes correlating with external events (arrests, investigations, lawsuits)

### 7. Cross-Reference with Investigation DB

Connect infrastructure findings to the broader investigation:

```bash
# Search for discovered domains/IPs/orgs in document corpus
uv run python tools/ingest_kabasshouse.py search "<DISCOVERED_DOMAIN>" --limit 20 --json > $WORKDIR/corpus-domain.json
uv run python tools/query_unified.py emails "<DISCOVERED_DOMAIN>" --limit 20 --output $WORKDIR/unified-domain-emails.json

# Check corporate registries for hosting companies / registrants
uv run python tools/query_registry.py search "<HOSTING_COMPANY>" --output $WORKDIR/registry-hosting.json

# Check if discovered IPs appear in any existing findings
uv run python tools/findings_tracker.py search "<IP_ADDRESS>" --output $WORKDIR/findings-ip.json
```

### 8. Record Findings

Infrastructure findings are first-class intelligence:

```bash
# Record infrastructure mapping
uv run python tools/findings_tracker.py add \
    --target "<TARGET>" \
    --type digital \
    --summary "Infrastructure: <DOMAIN> resolves to <IP> on <PROVIDER>, cert issued <DATE>, CSP reveals <VENDORS>" \
    --evidence "<SHODAN_URL_OR_CERT_HASH>" \
    --claim-type direct_quote \
    --source-quote "Shodan:host <IP> shows port 443 with CN=<DOMAIN>, org=<ORG>" \
    --confidence confirmed

# Record infrastructure connections
uv run python tools/findings_tracker.py connect \
    --person-a "<ENTITY_A>" --person-b "<ENTITY_B>" \
    --type digital --strength medium \
    --description "Shared IP <IP>, same SSL cert covering both domains" \
    --evidence "<CERT_HASH>"

# Register entities for hosting companies, registrars, etc. if relevant
uv run python tools/entity_tracker.py add-entity \
    --name "<HOSTING_PROVIDER>" \
    --entity-type unknown \
    --jurisdiction us \
    --source "shodan" \
    --notes "Hosting provider for <TARGET>"
```

### 9. Infrastructure Map

Produce a structured map of what was found:

```
## Infrastructure Map: <TARGET>

### Domains
| Domain | Registrar | Created | Nameservers | Notes |
|--------|-----------|---------|-------------|-------|

### DNS Records
| Domain | Type | Value | First Seen | Last Seen |
|--------|------|-------|------------|-----------|

### Hosts
| IP | Provider | ASN | Location | Ports | Services |
|----|----------|-----|----------|-------|----------|

### Certificates
| CN | SANs | Issuer | Issued | Expires | Hosts |
|----|------|--------|--------|---------|-------|

### Vendor Stack (from CSP/headers)
| Vendor | Service Type | Evidence |
|--------|-------------|----------|

### Shared Infrastructure
| Signal | Entity A | Entity B | Evidence |
|--------|----------|----------|----------|

### Timeline
| Date | Event | Source |
|------|-------|--------|
```

### 10. Spawn Follow-Up Leads

Create leads for:
- **Unexplained infrastructure**: Domains/IPs that don't match stated business purpose
- **Shared infrastructure signals**: Two entities sharing hosting/certs/analytics that shouldn't be connected
- **Historical infrastructure**: Abandoned domains or IPs that may reveal prior operations
- **Internal service names**: Subdomains discovered via CT logs that suggest undisclosed capabilities
- **Associated persons**: WHOIS registrants, DNS admin contacts, or SSL cert organization fields that name individuals
- **Vendor relationships**: Unusual technology partners revealed by CSP headers (e.g., surveillance tech, blockchain analytics, intelligence platform integrations)

```bash
uv run python tools/lead_tracker.py add \
    --title "<LEAD_TITLE>" \
    --priority <PRIORITY> \
    --category digital \
    --description "<DESCRIPTION>" \
    --source "investigate-infra"
```

## Shodan Query Cheatsheet

Paid plan has 99 query credits. Use them wisely — check `info` first.

```bash
# Organization search
uv run python tools/query_shodan.py search "org:\"<NAME>\""

# SSL certificate search
uv run python tools/query_shodan.py search "ssl:\"<DOMAIN>\""
uv run python tools/query_shodan.py search "ssl.cert.subject.O:\"<ORG>\""
uv run python tools/query_shodan.py search "ssl.cert.subject.CN:\"<CN>\""

# HTTP content/header search
uv run python tools/query_shodan.py search "http.title:\"<TITLE>\""
uv run python tools/query_shodan.py search "http.html:\"<STRING>\""
uv run python tools/query_shodan.py search "http.favicon.hash:<HASH>"

# Technology-specific
uv run python tools/query_shodan.py search "product:\"<PRODUCT>\" org:\"<ORG>\""
uv run python tools/query_shodan.py search "port:<PORT> org:\"<ORG>\""

# Network range
uv run python tools/query_shodan.py search "net:<CIDR>"
uv run python tools/query_shodan.py search "asn:AS<NUMBER>"

# Count-only (saves credits)
uv run python tools/query_shodan.py search "org:\"<NAME>\"" --count-only --facets "port,country"
```

## crt.sh Cheatsheet

```bash
uv run python tools/query_crtsh.py search <DOMAIN>              # All certs for domain
uv run python tools/query_crtsh.py search <DOMAIN> --subdomains # Subdomain certs (wildcard)
uv run python tools/query_crtsh.py search "Org Name" --org      # Certs by organization name
uv run python tools/query_crtsh.py subdomains <DOMAIN>          # Unique subdomain list
uv run python tools/query_crtsh.py timeline <DOMAIN>            # Issuance timeline + issuer stats
uv run python tools/query_crtsh.py cert <ID>                    # Specific cert by crt.sh ID
```

## Wayback Machine Cheatsheet

```bash
uv run python tools/query_wayback.py first <DOMAIN>                              # First known capture
uv run python tools/query_wayback.py timeline <DOMAIN> --monthly                 # Capture frequency
uv run python tools/query_wayback.py snapshots <DOMAIN> --from 2019 --to 2020   # Filtered snapshots
uv run python tools/query_wayback.py snapshots "*.<DOMAIN>" --subdomains         # All subdomains
uv run python tools/query_wayback.py diff <DOMAIN> --from 20190101 --to 20200101 # Unique content versions
uv run python tools/query_wayback.py fetch <URL> --timestamp 20190715            # Retrieve archived page
```

## URLScan.io Cheatsheet

```bash
uv run python tools/query_urlscan.py search "domain:<DOMAIN>"                    # Domain scans
uv run python tools/query_urlscan.py search "ip:<IP>"                            # IP scans
uv run python tools/query_urlscan.py search "page.title:<TITLE>"                 # Title search
uv run python tools/query_urlscan.py search "server:cloudflare AND domain:<D>"   # Combined filters
uv run python tools/query_urlscan.py result <UUID>                               # Full scan details
uv run python tools/query_urlscan.py technologies <UUID>                         # Detected tech stack
uv run python tools/query_urlscan.py links <UUID>                                # All contacted domains/IPs
```

## Context Management

- **Use `--output $WORKDIR/...` on ALL Shodan queries**
- **WebFetch results can be large** — ask targeted questions in the prompt
- **Record findings incrementally** as you pivot, not in a batch at the end
- **Credit awareness**: Run `uv run python tools/query_shodan.py info` early to check remaining Shodan credits

## Report File (when running as sub-agent)

Write to `$WORKDIR/report-infra-<target-slug>.md`:

```markdown
---
agent: investigate-infra
target: "<TARGET>"
status: completed
findings_added: [count]
connections_added: [count]
leads_spawned: [count]
shodan_credits_used: [count]
---
# Infrastructure Investigation: <TARGET>

## Entry Point
[What we started with and why]

## Infrastructure Map
[Structured map from step 9]

## Key Discoveries
- [Most significant infrastructure findings]

## Unseeing Moments
- [What became visible only after dropping an abstraction]
- [What was conspicuously absent]
- [What two "separate" things turned out to be connected]

## Negative Results
- [Expected infrastructure that wasn't found]

## Follow-Up Leads
- Lead #X: [description]

## Learnings
- [Friction] tool/source issues
- [Surprise] unexpected findings
- [Methodology] investigative approach insights
```
