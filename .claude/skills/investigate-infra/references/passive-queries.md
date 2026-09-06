# Passive query examples

Consult the corresponding section of `docs/modules/osint-infra.md` and current
`--help` for filters, pagination, and access requirements. Run only operations
selected by the source plan. Substitute verified identifiers and distinct output
paths for each query. These query existing public observations.

## Domain, DNS, and certificate questions

```bash
uv run python tools/query_shodan.py info
uv run python tools/query_shodan.py domain "<DOMAIN>" --history --output "$WORKDIR/domain-dns.json"
uv run python tools/query_crtsh.py search "<DOMAIN>" --subdomains --output "$WORKDIR/domain-certificates.json"
uv run python tools/query_crtsh.py timeline "<DOMAIN>" --output "$WORKDIR/certificate-timeline.json"
uv run python tools/query_crtsh.py cert <CERT_ID> --output "$WORKDIR/certificate-detail.json"
```

Use observation timestamps and certificate IDs/SANs. A common issuer or wildcard
alone does not establish organizational identity or enumerate every service.

## Existing host observations

```bash
uv run python tools/query_shodan.py host "<IP>" --output "$WORKDIR/host.json"
uv run python tools/query_shodan.py ssl-cert "<DOMAIN>" --output "$WORKDIR/certificate-hosts.json"
uv run python tools/query_shodan.py reverse-dns "<IP1>,<IP2>" --output "$WORKDIR/reverse-dns.json"
uv run python tools/query_shodan.py dns-resolve "<DOMAIN1>,<DOMAIN2>" --output "$WORKDIR/dns-resolve.json"
uv run python tools/query_shodan.py search 'org:"<ORG>"' --count-only --facets "port,country" --output "$WORKDIR/org-count.json"
```

A count/facet query can size a relevant pivot before retrieval. Preserve the
difference between source-observed hosts and the organization's actual inventory.
Queries using favicon/ASN/certificate-organization selectors should first establish
why those selectors discriminate the target from shared infrastructure.

## Historical web content

```bash
uv run python tools/query_wayback.py first "<DOMAIN>" --output "$WORKDIR/first-capture.json"
uv run python tools/query_wayback.py snapshots "<DOMAIN>" --from <START_YEAR> --to <END_YEAR> --output "$WORKDIR/snapshots.json"
uv run python tools/query_wayback.py fetch "<URL>" --timestamp <TIMESTAMP> --output "$WORKDIR/archived-page.json"
```

Use the relevant period. Compare actual archived content rather than inferring
service changes from capture frequency alone. Keep the requested and returned
snapshot timestamps distinct.

## Existing URLScan records

```bash
uv run python tools/query_urlscan.py search "domain:<DOMAIN>" --output "$WORKDIR/urlscan-search.json"
uv run python tools/query_urlscan.py result "<UUID>" --output "$WORKDIR/urlscan-result.json"
uv run python tools/query_urlscan.py technologies "<UUID>" --output "$WORKDIR/urlscan-technologies.json"
uv run python tools/query_urlscan.py links "<UUID>" --output "$WORKDIR/urlscan-links.json"
```

Inspect existing HTTP transactions for actual response headers and observed
requests at scan time. Technology detections and configured allowlists have
different evidentiary strength. Preserve result caps, missing transactions, and
unavailable records; do not submit new active scans as part of this passive skill.
