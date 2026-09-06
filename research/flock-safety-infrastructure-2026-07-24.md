---
title: "Flock Safety: Passive Infrastructure Profile — Expanded Retrieval Follow-up"
date: 2026-07-24
status: expanded-follow-up
target: "Flock Group Inc. d/b/a Flock Safety"
seed_domain: flocksafety.com
method: passive-public-osint-and-unauthenticated-public-retrieval
---

# Flock Safety: Passive Infrastructure Profile

## Executive summary

This investigation began with stored-data OSINT and was extended with tightly
bounded, browser-equivalent retrieval. The follow-up issued unauthenticated
`GET` requests only to public root pages, assets those pages declared, and
source maps those assets explicitly named. It also queried crt.sh, Shodan's
stored index, Wayback CDX, public DNS/RDAP, and public GitHub. No scan was
submitted, no authentication was attempted, no credential-shaped value was
used, and no customer data, camera feed, hotlist content, or authenticated
product function was contacted. The sole request to the API namespace was
`GET https://api.flocksafety.com/`, which returned a 404 JSON response; no
discovered API route was requested.

The evidence supports a layered architecture:

- The current corporate site is a Webflow site delivered through Cloudflare. The apex resolves to Webflow's `198.202.211.1`; live response headers include `server: cloudflare` and `x-wf-region: us-east-1`.
- Flock's application namespace relies heavily on AWS. First-party policies name AWS, S3, IAM, KMS, and GovCloud. Passive DNS independently returned CloudFront, ELB, API Gateway, RDS/Aurora, and `us-gov-west-1` target names. Shodan also observed Flock-named certificates on Amazon networks.
- The public namespace reflects multiple managed services: Auth0, Google Workspace, Atlassian Statuspage, ReadMe, SafeBase, Salesforce, Cloudflare, and Webflow, among others.
- The returned DNS labels expose development, preview, internal, government-looking, product, and observability naming patterns. These names are useful architectural clues but do not prove that a service is live, reachable, correctly named, or currently used.
- The corporate site's delivery changed substantially over time: Cloudflare in 2020, Nexcess/nginx in 2021, Amazon S3/CloudFront in 2022, an AWS-addressed/Webflow-asset phase in 2023–2025, and Cloudflare-fronted Webflow delivery by December 2025.
- `https://www.flocksafety.com/sitemap.xml` is not RSS even though it is served as `application/rss+xml`. Its XML root is a standard Sitemap Protocol `<urlset>`. It contains 1,207 unique URLs, including numerous CMS test/copy paths.
- A repaired raw crt.sh export yielded per-name certificate chronology. The
  earliest returned validity starts were 2023-03-13 for
  `dev-dbproxy.gov.flocksafety.com`, 2023-03-20 for
  `prod-dbproxy.gov.flocksafety.com`, 2025-04-04 for
  `*.dev.federal.flocksafety.com`, and 2025-06-25 for one certificate
  containing both `federal.flocksafety.com` and
  `*.federal.flocksafety.com`. These are certificate metadata, not host
  first-seen or liveness dates.
- Public application bundles expose deployment nomenclature, backend URL
  strings, route templates, and feature-flag keys. They support claims about
  shipped client code only; they do not show that a feature was enabled, that
  a route was accessible, or that a named service was live.
- A broader Shodan SSL pivot added an Amazon-issued leaf whose SANs jointly
  cover `*.flocknova.com` and `*.flocksafety.com`, observed on three
  GovCloud-region AWS addresses. Its JARM/JA3S pattern matches a subset of
  commercial Flock-certificate observations but is extremely common across
  AWS ELBs, so it does not establish identical workloads or controls.
- Public GitHub produced useful leads but no independently validated endpoint.
  An apparently Flock-operated namespace contains a FedRAMP 20x submission
  repository. Separate third-party repositories contain Flock-branded URL and
  route strings; those prove only what their authors documented or
  implemented. No route or credential was tested.

This is a provider, naming, and public-client-code profile, not a vulnerability
assessment. No vulnerability conclusion is supported.

## Scope and attribution rules

Sources observed on 2026-07-24 UTC:

- Verisign and ARIN RDAP
- Google Public DNS
- crt.sh certificate transparency
- Shodan DNS, certificate, resolver, and stored host observations
- URLScan's existing public scan corpus
- Internet Archive interfaces
- Flock's public site, policies, developer documentation, status page, security center, sitemap, and robots file
- Public root-page headers and page-declared JavaScript/CSS/source maps
- Public GitHub code search and commit-pinned file retrieval

The following distinctions are essential:

- A DNS label proves that the label appeared in the returned DNS corpus, not that it was live or accurately described.
- A CNAME proves a configured provider target, not ownership of the provider or a distinct workload.
- A CT-returned certificate subject/SAN establishes naming in the returned
  certificate metadata. A stored Shodan TLS banner separately establishes
  certificate presentation at Shodan's observation timestamp. Neither proves
  that the named application was functional.
- A certificate `not_before` value is a validity start, not the time a CT log
  first observed it and not a host-liveness timestamp.
- A shared Cloudflare, Webflow, or CDN IP does not make the edge's ports or unrelated co-hosts Flock assets.
- A client bundle's hostname, route, or feature-flag string proves only that
  the string shipped in that artifact. It does not prove enablement,
  authorization, reachability, or current backend behavior.
- A CSP source expression authorizes a browser destination for that response;
  it does not prove a current request, active contract, data flow, or Flock
  ownership of the destination. Managed-service CSPs may reflect a provider's
  general platform allowlist.
- Shodan's Ashburn/Boardman geolocation describes provider IPs, not customer-data residency.
- Flock's claims about encryption, IAM, KMS, GovCloud, and data handling remain first-party claims unless independently validated.

No Flock-specific investigation profile exists in the repository. The active profile was unrelated, so no profile-scoped findings, leads, connections, or entities were created. Mandatory tooling-friction observations were logged globally as repository papercuts.

## Infrastructure map

| Layer | Observable surface | Provider or signal | Supported conclusion |
|---|---|---|---|
| Corporate site | `flocksafety.com`, `www.flocksafety.com` | Webflow address space; Cloudflare response edge | Current marketing site is Webflow-hosted and Cloudflare-delivered |
| Public application edge | `app`, `api`, `login`, and other public names | Cloudflare plus AWS-backed targets | Mixed CDN/application delivery; edge ports cannot be attributed as Flock services |
| Developer platform | `docs.flocksafety.com` | ReadMe/Cloudflare; documentation names `api.flocksafety.com` | Flock publishes an OAuth-based developer/API surface; no API calls were made |
| Identity | `login`, `device-login`, development variants | Five Auth0 tenant-edge CNAME rows; official status page names Auth0 user and machine authentication | Auth0 dependency has cross-source support; tenant configuration remains unknown |
| Status/support/trust | `status`, `help`, `trust`, `security` | Atlassian Statuspage, managed help tooling, AWS ELB, SafeBase | Public operational and security surfaces are largely managed services |
| Application hosting | CloudFront, ELB, API Gateway, RDS/Aurora target families | AWS, predominantly `us-east-1`; seven DNS rows named `us-gov-west-1` | Broad AWS reliance; DNS does not validate data contents, control effectiveness, or residency |
| Mail | Apex MX and SPF | Google Workspace; Google, Sendergen, Reply.io, Mandrill, Marketo, Amazon SES, and a first-party SPF include | Google-hosted mail and a broad authorized sending stack at observation time |
| Authoritative DNS | Four `awsdns` nameservers, DS record | Route 53 and DNSSEC | AWS-hosted authoritative DNS with signed delegation |
| Corporate web history | Existing public URLScan records | Cloudflare, Nexcess, AWS, Webflow | Multiple public-site hosting migrations are visible |

## Domain, DNS, and registration

Verisign RDAP returned:

- Registration: **2017-01-23T18:56:56Z**
- Registrar: **Name.com, Inc.**
- Status: `client transfer prohibited`
- Expiration: **2034-01-23T18:56:56Z**
- Nameservers: four AWS Route 53 `awsdns` hosts

Google Public DNS returned the same nameservers, authenticated answers, and a DNSSEC DS record. The apex A answer was `198.202.211.1`, which ARIN assigns within a Webflow netblock. The apex MX set was Google's standard five-host mail set. The apex CAA query returned no CAA answer at that instant; that says nothing about subdomain CAA records.

Shodan's history-enabled domain query returned a bounded set of **565 DNS rows across 330 labels**:

| Record type | Returned rows |
|---|---:|
| A | 198 |
| CNAME | 319 |
| TXT | 38 |
| MX | 5 |
| NS | 4 |
| SOA | 1 |

The 198 A rows covered only 13 labels and 198 rotating values. That pattern is consistent with load balancing or elastic address rotation; it is not evidence of 198 stable Flock-owned servers.

Selected CNAME target families:

| Target family | Rows |
|---|---:|
| Cloudflare custom-hostname targets | 126 |
| AWS CloudFront | 91 |
| AWS ELB | 18 |
| AWS RDS/Aurora | 6 |
| AWS API Gateway | 3 |
| Auth0 tenant edges | 5 |
| Webflow | 2 |
| Atlassian Statuspage | 2 |
| ReadMe | 1 |
| SafeBase | 1 |
| Salesforce Siteforce | 1 |

These are row counts, not workload counts.

## Certificate timeline

The successful crt.sh timeline query returned **1,350 tool-deduplicated CT records** after the repository tool's serial-number deduplication:

- Earliest returned certificate validity start: **2017-03-06**, about 42 days after registration
- Latest returned certificate validity start: **2026-07-23**
- Let's Encrypt: **1,012 (75.0%)**
- Google Trust Services: **169 (12.5%)**
- Amazon: **96 (7.1%)**
- Cloudflare: **44 (3.3%)**
- Sectigo: **27 (2.0%)**
- COMODO: **2 (0.1%)**

The returned record count grew from four in 2017 and 21 in 2018 to 232 in 2024 and 292 in 2025. The partial 2026 count was 207 through July 23. Renewal automation and short-lived certificates inflate these counts; they are not counts of unique hosts or a canonical count of globally unique certificates. X.509 serial uniqueness is scoped to an issuer, while the repository tool deduplicates on serial number alone.

A Shodan certificate preflight counted 40 observations for the token query `ssl.cert.subject.CN:flocksafety.com`. Retrieving the bounded result used one query credit and returned all 40 rows on port 443, grouped into five fingerprints, all on Amazon networks. Certificate subjects included:

- `*.flocksafety.com`
- `*.video-api.flocksafety.com`
- `*.dev-video-api.flocksafety.com`
- `demo-fly.flocksafety.com`

Those subjects demonstrate naming and certificate presentation at Shodan's timestamps. They do not establish application liveness or function. The strongest reviewed host association was `external-bw.flocksafety.com`, where point-in-time DNS, a Shodan hostname, an AWS ELB marker, and a Flock wildcard certificate converged.

## Exact naming observations

Shodan's returned labels contained substantial environment and deployment nomenclature. Selected examples are reproduced because they are analytically useful:

| Exact hostname | Strongest passive evidence | Bounded interpretation |
|---|---|---|
| `prod-dbproxy.gov.flocksafety.com` | Passive DNS pointed to an AWS ELB name in `us-gov-west-1`; three URLScan submissions had no page metadata. | Naming and a regional AWS target only; not proof of a live database proxy, public reachability, customer data, or GovCloud data residency. |
| `device-login.flocksafety.com` | Passive DNS pointed to an Auth0 tenant edge; URLScan tasks commonly ended at the corporate root. | Supports an Auth0 association, not tenant configuration or a functioning device-login application. |
| `internal.support.flocksafety.com` | Passive DNS pointed to Atlassian SaaS; URLScan ended at an AtlassianEdge service-desk login. | A public login surface is not evidence of exposed internal content. |
| `hotlist.flocksafety.com` and `sftp.hotlist-importer.flocksafety.com` | The first was a Cloudflare CNAME with URLScan login redirects; the SFTP-named label had a passive A record. | The SFTP name alone does not establish an SFTP listener, port, liveness, or accessibility. |
| `vms.flocksafety.com` and `vms-api.flocksafety.com` | Passive DNS naming aligns with Flock's official public VMS component label; a sampled `vms` URLScan task ended at login. | Does not establish an unauthenticated API, the complete VMS architecture, or current liveness. |
| `scim.flocksafety.com` | Passive DNS plus seven URLScan records; observations ended at `/app/` or `/app/setup` with HTTP 200 responses from 2022–2026. | “SCIM” suggests identity provisioning only lexically; no tenant, customer, configuration, or data was inspected. |
| `dev-springbank12-pr-351.flocksafety.com` | Passive DNS pointed to CloudFront; one URLScan task recorded an HTTP 200 response in 2025. | One PR-preview naming example, not proof of current liveness or what `springbank12` denotes. |
| `cad-ingestion.flocksafety.com` and `camera-management.flocksafety.com` | Both were Cloudflare custom-hostname CNAMEs; their names align with public product/API categories. | The alignment is synthesis; the labels do not prove function, implementation, exposure, or data flow. |

### Identity and access

- `login`
- `device-login`
- `dev-login`
- `dev-device-login`
- `dev-integrations-auth`
- `integrations-auth`
- `scim`
- `dev-wix-answers-login`

### Product- and workflow-looking labels

- `camera-management`
- `dev-camera-management`
- `dev-cad-events`
- `hotlist`
- `dev-hotlist`
- `dev-hotlist-new`
- `dev-map-data`
- `search`
- `search-api`
- `dev-search-api`
- `sharing`
- `vms`
- `dev-vms`
- `dev-vms-api`
- `video-demo`
- `dev-video-demo`
- `dev-devices`

### Infrastructure and observability

- `dev-alertmanager`
- `dev-prometheus`
- `dev-linkerd-internal`
- `dev-exporter-internal`
- `dev-tunnel-proxy1`
- `dev-tunnel-proxy1-internal`
- `dev-gha-token-dispenser`
- `dev-dbproxy.gov`
- `prod-dbproxy.gov`
- `internal.support`

### Government-looking labels

- `external.gov`
- `dev-external.gov`
- `dev-external-flt.gov`
- `dev-cabo-gov`
- `dev-campari-gov`
- `dev-redbull-search-gov`
- `dev-water-gov`
- `dev-linkerd-internal-gov`

### Preview and service naming

The label set includes long runs of PR-numbered names such as `dev-monaco-pr-*`, `dev-strawberry-soju-pr-*`, and `dev-springbank12-pr-*`. Existing public URLScan records independently included examples such as:

- `dev-monaco-pr-333.flocksafety.com`
- `dev-strawberry-soju-pr-2349.flocksafety.com`
- `dev-springbank12-pr-457.flocksafety.com`
- `dev-search-component-lib-pr-392.flocksafety.com`
- `dev-jose-cuervo-pr-816.flocksafety.com`

The namespace also uses a conspicuous beverage/cocktail theme:

- `apple-pie-moonshine`
- `champagne`
- `dev-cognac-api`
- `dev-gimlet-internal`
- `prod-gimlet-write`
- `dev-hurricane-internal`
- `dev-kraken-internal`
- `dev-martini`
- `dev-negroni`
- `dev-sangria-api`
- `prod-moonshine-write`
- `dev-strawberry-soju-pr-*`
- `dev-tanqueray-internal`
- `dev-titos-internal`

These strings establish a naming convention visible in passive DNS/URLScan data. They do not prove the service behind a name, its environment, its exposure, or its present state. None was probed.

## TXT-record vendor footprint

Google Public DNS returned 37 apex TXT answers. Omitting verification-token values, the records named:

**Adobe, Airtable, Amazon Business, Anthropic, Apple, Atlassian, Autodesk, Cursor, DocuSign, Drift, Fastly, Google, HackerOne, Microsoft, Northpass, OneTrust, OpenAI, Parallels, Qase, Sage Intacct, Salesforce/Pardot, Segment, Stripe, Tailscale, Uber, Wiz, and Zapier**, plus Mailgun-style verification.

Verification records can be stale or survive a trial or terminated integration. They support domain-verification history, not active production use or a current data flow.

## Public corporate-site history

The fully paginated URLScan query `domain:flocksafety.com` returned **651 existing public records** in seven pages, spanning 2019-11-25 through 2026-07-23. Representative root observations:

| Observation | Delivery | Supporting details |
|---|---|---|
| 2020-10-01 | Cloudflare | AS13335; Cloudflare certificate and server |
| 2021-10-03 | Nexcess/nginx | WordPress, Unbounce, and Yoast detected |
| 2022-06-03 | Amazon S3/CloudFront | AS16509; Amazon certificate |
| 2023-11-23 | AWS-addressed | Webflow asset dependencies; Marketo and Google tags |
| 2025-12-08 | AWS-addressed | Last representative pre-Cloudflare root observation in the retrieved set |
| 2025-12-20 | Cloudflare/Webflow | First representative root observation using `198.202.211.1` |
| 2026-07-17 | Cloudflare/Webflow | 234 requests, 39 apex domains, 50 IPs, and 24 detected technologies |

The intervals bound third-party observations, not exact migration dates.

The latest representative root scan showed a large marketing dependency surface:

- Delivery/assets: Cloudflare, Webflow assets, Amazon S3/CloudFront, cdnjs, jsDelivr, Unpkg, Jetboost, Slater
- Analytics/experimentation/monitoring: Google Analytics/Tag Manager, Hotjar, VWO, Cloudflare Browser Insights, Microsoft Clarity, HockeyStack, Sentry
- Advertising/intent/sales/chat: DoubleClick, Microsoft Advertising, Mountain, Nextdoor Ads, Reddit Ads, StackAdapt, Qualified, Warmly, ZoomInfo, Intentsify
- Consent: OneTrust

These were page-load observations, not ownership claims.

## Sitemap and robots

At **2026-07-24T02:02:32Z**, `https://www.flocksafety.com/sitemap.xml` returned:

- HTTP 200
- `Content-Type: application/rss+xml; charset=utf-8`
- `server: cloudflare`
- `x-wf-region: us-east-1`
- a Webflow-style surrogate key
- a Cloudflare cache hit

The body is not RSS. It is well-formed XML rooted at:

```xml
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
```

An RSS document would use an `<rss>` root with channel/item elements. The RSS presentation is therefore an HTTP MIME-type mismatch.

The sitemap contains **1,207 unique URLs**:

| First path segment | URLs |
|---|---:|
| `/blog` | 809, including the index |
| `/webinar` | 95 |
| `/ebooks` | 60 |
| `/customers` | 40 |
| `/thank-you` | 18 |
| `/industries` | 18 |
| `/legal` | 17 |
| `/products` | 12, including the index |
| `/video` | 11 |
| `/events` | 10 |
| `/abm` | 10 |

All 1,207 URLs use `https://www.flocksafety.com`; none has a query string. The document contains no `lastmod`, `changefreq`, `priority`, or `xhtml:link` elements.

The sitemap exposes multiple CMS/test/copy paths, including:

- `/book-a-demo-test`
- `/book-a-demo-paid-copy`
- `/email-exclusions-test`
- `/form-test`
- `/book-a-demo-form-test`
- `/privacy-ethics-copy`
- `/book-a-demo-short-form-test`
- `/webinar/this-is-a-test`
- `/webinar/webinar-test-evens-page-copy-2` through other numbered copies
- `/events/test-event`
- `/events/test-third-party-events-copy-*`

Inclusion proves only that the public Webflow sitemap generator emitted these paths.

`robots.txt` explicitly advertises this sitemap and disallows:

- `/blog-audiences/`
- `/use-case-filters/`
- `/g0lnomhfn3mgNjgyMWNjOWVjYzk2NmI3ZjI1MmIzNzJl/`
- `/nvhc9u4gxsagNjgyMWNjOWVjYzk2NmI3ZjI1MmIzNzJl/`

The opaque paths were not fetched.
None of the four disallowed path families appeared in the captured sitemap.

The shared suffix `NjgyMWNjOWVjYzk2NmI3ZjI1MmIzNzJl` base64-decodes to
`6821cc9ecc966b7f252b372e`, the same identifier present in the live Webflow
surrogate-key response header. This links the generated robots paths to the
Webflow site identifier at the naming level; it does not establish the paths'
purpose.

## Follow-up Task 1: certificate chronology and federal milestones

### Per-identity method

A fresh crt.sh JSON export retrieved at **2026-07-24T02:57–02:58Z**
contained 2,456 rows and 1,350 distinct serial strings. A conservative parser
inspected `common_name` and newline-delimited `name_value`, normalized case,
trailing dots, and IDNA, retained wildcard names as patterns rather than
expanding them, and selected the minimum returned certificate `not_before` for
each identity.

The bounded response produced 79 in-scope identities: 69 exact names and 10
wildcard patterns. Twelve identities/patterns used
`.gov.flocksafety.com` or an explicit `federal` label. They were supported by
11 distinct serial strings because one certificate contained both
`federal.flocksafety.com` and `*.federal.flocksafety.com`.

The timestamps below are reproduced exactly as crt.sh returned them; the raw
strings contain no explicit timezone offset. They are certificate validity
starts, not CT observation times, issuance times, DNS first-seen dates, or host
liveness.

| Rank | Identity | Kind | Earliest returned `not_before` | Supporting crt.sh row ID | Supported conclusion | Explicit limits |
|---:|---|---|---|---:|---|---|
| 1 | `dev-dbproxy.gov.flocksafety.com` | exact | `2023-03-13T13:54:59` | 8911284186 | The returned certificate metadata names this exact identity and has this validity start. | It does not show when the name became public, DNS, a listening service, database exposure, a customer, or continuous operation. |
| 2 | `blahtest1.gov.flocksafety.com` | exact | `2023-03-14T16:55:09` | 8917655869 | Returned metadata names a test-labeled identity in the same Flock-controlled namespace and gives this validity start. | `.gov.flocksafety.com` is beneath Flock's commercial `.com`; it is not a U.S. government `.gov` domain. |
| 3 | `prodblahtest1.gov.flocksafety.com` | exact | `2023-03-14T17:40:21` | 8917795114 | Same bounded certificate-name and validity-start observation. | The lexical `prod` string does not prove production use. |
| 4 | `newblahtest1.le.gov.flocksafety.com` | exact | `2023-03-17T18:52:13` | 8934588475 | Same bounded certificate-name and validity-start observation. | The name does not identify an agency or function. |
| 5 | `newblahtest2.gov.flocksafety.com` | exact | `2023-03-17T19:11:18` | 8934632230 | Same bounded certificate-name and validity-start observation. | No liveness conclusion. |
| 6 | `newblahtest3.gov.flocksafety.com` | exact | `2023-03-17T19:35:50` | 8934750821 | Same bounded certificate-name and validity-start observation. | No liveness conclusion. |
| 7 | `blahtest3.gov.flocksafety.com` | exact | `2023-03-20T14:55:29` | 8956812285 | Same bounded certificate-name and validity-start observation. | No liveness conclusion. |
| 8 | `blahtest4.gov.flocksafety.com` | exact | `2023-03-20T16:23:04` | 8957218410 | Same bounded certificate-name and validity-start observation. | No liveness conclusion. |
| 9 | `prod-dbproxy.gov.flocksafety.com` | exact | `2023-03-20T17:14:36` | 8957426847 | The returned certificate metadata names this exact identity and has this validity start. | It does not show when the name became public or establish a live database proxy, public reachability, or GovCloud data residency. |
| 10 | `*.dev.federal.flocksafety.com` | wildcard pattern | `2025-04-04T00:00:00` | 17633278617 | Returned certificate metadata contains this wildcard pattern and validity start. | It proves no particular covered hostname existed. |
| 11 | `*.federal.flocksafety.com` | wildcard pattern | `2025-06-25T00:00:00` | 19250725105 | One returned Amazon certificate contains this wildcard pattern and validity start. | It proves no particular covered hostname existed. |
| 12 | `federal.flocksafety.com` | exact | `2025-06-25T00:00:00` | 19250725105 | The same certificate contains this base name and validity start. | This is one certificate event supplying two identities, not two hosts or workloads. |

The requested `external.gov.flocksafety.com`,
`dev-external.gov.flocksafety.com`, and
`dev-external-flt.gov.flocksafety.com` names did **not** appear as exact
identities in this crt.sh response. Nor did the cocktail/service names ending
`-gov`. The prior passive-DNS result associated the three `external` names
with rotating A answers only in June–July 2026 and the `-gov` names with CNAME
rows last seen 2026-07-22. Those later `last_seen` values cannot be substituted
for historical CT or DNS first-seen dates. No returned wildcard pattern exactly
covers the multi-label `external.gov` names.

### Comparison with Flock's retrospective federal timeline

Flock's current article, retrieved **2026-07-24T02:59:33Z**, retrospectively
lists federal-client pilot intervals beginning with the FBI on 2021-07-21 and
continuing through CBP in 2025. It also says that in January 2026 Flock
introduced a single “Federal Sharing” toggle in Admin Settings. A separate
first-party post retrieved **2026-07-24T02:59:48Z** says on its 2025-08-25
publication date that all ongoing federal pilots had been paused “as of last
week.”

| Exact temporal comparison | Source | Supported conclusion | Explicit limits |
|---|---|---|---|
| The March 2023 `.gov.flocksafety.com` validity starts follow the earliest pilot start Flock now gives, 2021-07-21, and fall during several retrospectively stated pilot intervals. | [Flock, “Does Flock Share Data With ICE?”](https://www.flocksafety.com/blog/does-flock-share-data-with-ice), live HTML retrieved 2026-07-24T02:59:33Z | These validity starts do not predate the earliest pilot date stated retrospectively on Flock's current page. | The current corporate page is not an independent record and does not establish when any pilot was first publicly announced. No certificate is tied to a named pilot. |
| Every ranked `.gov`/`federal` validity start precedes the January 2026 Federal Sharing-toggle statement. | Same source | The returned certificate-name/validity-start metadata predates the page's stated one-toggle control. | This does not mean that the control, feature, sharing behavior, or a corresponding host existed on the certificate validity dates. |
| `*.dev.federal.flocksafety.com` falls during Flock's stated NCIS and HSI intervals; the June 2025 federal certificate falls during its stated CBP interval. | Same source | The date ranges overlap. | Temporal overlap alone supplies no functional or customer attribution. |
| An apparently Flock-operated GitHub namespace records a FedRAMP 20x repository root commit on 2025-06-13 and a commit titled “Promote internal to Public” on 2025-08-27. | [Repository](https://github.com/flocksafety/flock-core-fedramp20x) and saved commit API records, retrieved 2026-07-24T03:02:46Z–03:02:56Z | The June 25 federal certificate validity start is 12 calendar days after the repository's root-commit timestamp. | A commit timestamp is not the operational pilot start, public-visibility date, authorization date, or proof of a relationship to the certificate. GitHub displayed no Verified badge in the reviewed evidence. |

**Disposition:** no requested hostname can responsibly be flagged as live
before any cited operational milestone. The certificate validity dates do not
predate the pilot starts stated retrospectively on Flock's current page. The
evidence establishes certificate naming and later passive-DNS observations,
not host liveness, and it does not reveal when the pilot starts were first
publicly disclosed.

## Follow-up Task 2: application-edge headers and CSP

Eleven public roots were fetched with unauthenticated `GET` requests during
**2026-07-24T02:57:58Z–02:58:01Z**.

| Requested root | Response chain | Salient exact headers | Supported conclusion | Explicit limits |
|---|---|---|---|---|
| `www` | 200 | `server: cloudflare`; CSP `frame-ancestors 'self'`; `X-Frame-Options: SAMEORIGIN` | The observed marketing response used Cloudflare and a minimal frame-ancestor policy. | This policy does not constrain script, image, or connection origins. |
| `app` | 200 | `server: cloudflare`; CloudFront `Via`; HSTS 30 days; `X-Frame-Options: DENY`; no CSP | The root response traversed Cloudflare and CloudFront. | No-CSP is point-in-time header absence, not a vulnerability conclusion or origin identification. |
| `api` | 404 JSON | `server: cloudflare`; HSTS 30 days; no CSP or CORS header | The bare public root returned a JSON 404. | No API route was requested; the result says nothing about authenticated endpoints. |
| `login` | 302 → 301 → 200 | Redirected to apex then `www`; final marketing CSP | The sampled root did not present a login UI and resolved to marketing content. | No authentication attempt occurred; alternate login paths were not tested. |
| `docs` | 200 | `server: cloudflare`; one-year HSTS; `X-Frame-Options: Deny`; permissions policy disables camera, microphone, geolocation, and payment; no CSP | The public documentation root exposed this header set. | Headers do not identify the origin or every docs route. |
| `admin` | 302 → 200 | Redirected to `users`; final Cloudflare plus CloudFront `Via`; `X-Frame-Options: DENY`; no CSP | `admin` and `users` converged on one public application shell. | This does not show common backend authorization or data. |
| `users` | 200 | Cloudflare plus CloudFront `Via`; HSTS 30 days; `X-Frame-Options: DENY`; no CSP | Same observed application-edge class. | Same point-in-time limitation. |
| `status` | 200 | `server: AtlassianEdge`; CloudFront `Via`; `Access-Control-Allow-Origin: *`; `Report-To` CloudFront endpoint; NEL 1% failure fraction | Atlassian Statuspage supplied the public status response and network-error reporting configuration. | Wildcard CORS on public status HTML is not evidence that a product API permits cross-origin access. |
| `help` | 301 → 200 | Redirected to `/s/`; CSP only `upgrade-insecure-requests` | The public help root used a minimal upgrade policy. | No broader allowlist can be inferred. |
| `trust` | 301 → 301 → 200 | Initial `server: awselb/2.0`; then Cloudflare marketing response | An AWS load-balancer redirect led to the marketing trust page. | The first hop does not establish a distinct Flock-owned workload. |
| `security` | 200 | Cloudflare; `Via: 1.1 google`; SafeBase CSP with `strict-dynamic`, `frame-ancestors 'none'`, `object-src 'none'`, and a redacted Sentry `report-uri` | The SafeBase-powered security center returned the only broad CSP in the sample. | The policy may reflect SafeBase's general platform; it is not the application or marketing CSP. |

No sampled root returned `Content-Security-Policy-Report-Only` or
`Reporting-Endpoints`. Only `status` returned `Report-To` and `NEL`;
`security` used legacy CSP `report-uri`.

After normalizing schemes, wildcard prefixes, paths, and ports, the
`security` CSP contained **122 unique host tokens**. The comparison baseline,
the latest prior public URLScan marketing-root load on 2026-07-17, contacted
58 hostnames across 39 apex domains:

| CSP/marketing comparison | Exact count |
|---|---:|
| Exact hostname overlap | 6 |
| CSP hosts suffix-matching a marketing apex | 14 |
| Shared apex-domain families | 9 |
| CSP hosts without a marketing-apex match | 108 |
| Marketing apex domains without a CSP match | 30 |

The six exact host overlaps were `cdn.cookielaw.org`,
`fonts.googleapis.com`, `fonts.gstatic.com`, `stats.g.doubleclick.net`,
`www.google.com`, and `www.googletagmanager.com`. Shared families were
Cookielaw, DoubleClick, Google Analytics/Google/Google APIs/Tag Manager/Gstatic,
OneTrust, and Sentry.

Marketing-only apexes included Webflow/Cloudflare/CDN delivery; Hotjar, VWO,
Microsoft Clarity, HockeyStack; Microsoft, Mountain, Nextdoor, Reddit, and
StackAdapt advertising; Qualified, Warmly, Intentsify, and ZoomInfo; and
Jetboost, jsDelivr, Slater, and Unpkg. The SafeBase CSP additionally allowed
families such as Mixpanel, Segment, Amplitude, Chameleon, Intercom, Split,
Explo, Statsig, Clearbit, Flatfile, HubSpot, Facebook, PayPal, Cookiebot,
Liveblocks, Ketch, Transcend, Datadog, TrustArc, Dropbox, SecurityScorecard,
Drata, Livestorm, Svix, Stripe, and Productboard.

This establishes that the SafeBase CSP's permitted destination set was broader
and materially different from the observed marketing-page dependency graph. A
CSP token is permission, not evidence of a request, contract, enabled
integration, or data flow. Apex TXT verification records were excluded from
this comparison because they indicate historical verification, not current
use.

<details>
<summary>Full normalized 122-host SafeBase CSP inventory</summary>

```text
adservice.google.com
analytics.google.com
analytics.nationwide.com
api-js.mixpanel.com
api-sr-us.amplitude.com
api-sr.amplitude.com
api.cr-relay.com
api.liveblocks.io
api.segment.io
api.statsig.com
api.us.flatfile.io
api.x.flatfile.com
api2.amplitude.com
app.livestorm.co
app.safebase.io
app.svix.com
auth.safebase.io
autocomplete.clearbit.com
browser-intake-datadoghq.com
calendly.com
cdn.amplitude.com
cdn.auth0.com
cdn.brandfetch.io
cdn.cookielaw.org
cdn.cr-relay.com
cdn.mxpnl.com
cdn.safebase.io
cdn.segment.com
celebrus-prod2.nationwide.com
chameleon.io
collect.analyze.ly
connect.facebook.net
consent.trustarc.com
cookiebot.com
cookies-data.onetrust.io
dratacdn.com
dropbox.com
dropboxstatic.com
embed.explo.co
embedded.tray.io
explo.co
fast.wistia.net
flatfile.com
flatfile.io
fonts.googleapis.com
fonts.gstatic.com
forms.hsforms.com
google-analytics.com
googleusercontent.com
hs-scripts.com
hscollectedforms.net
hsforms.com
hsforms.net
hubapi.com
hubspot.com
ingest.sentry.io
intercom-attachments-1.com
intercom-attachments-2.com
intercom-attachments-3.com
intercom-attachments-4.com
intercom-attachments-5.com
intercom-attachments-6.com
intercom-attachments-7.com
intercom-attachments-8.com
intercom-attachments-9.com
intercom-messenger.com
intercom-sheets.com
intercom.help
intercom.io
intercomcdn.com
js.hs-analytics.net
js.hs-banner.com
js.hs-scripts.com
js.hsadspixel.net
js.hscollectedforms.net
js.hsleadflows.net
js.hubspotfeedback.com
js.intercomcdn.com
js.stripe.com
ketchcdn.com
logo.clearbit.com
messenger-apps.intercom.io
nexus-websocket-a.intercom.io
nexus-websocket-b.intercom.io
o410058.ingest.sentry.io
onetrust.com
p.adsymptotic.com
p.typekit.net
pagead2.googlesyndication.com
platform.flatfile.com
platform.securityscorecard.io
player.vimeo.com
portal.productboard.com
px.ads.linkedin.com
px4.ads.linkedin.com
s.gravatar.com
safebase.io
split.io
sr-client-cfg.amplitude.com
static.hsappstatic.net
static.intercomassets.com
stats.g.doubleclick.net
statuspage.io
stigg.io
storage.googleapis.com
transcend-cdn.com
transcend.io
uploads.intercomcdn.com
uploads.intercomusercontent.com
use.typekit.net
usemessages.com
wp.com
www.facebook.com
www.google.ca
www.google.com
www.google.ie
www.googletagmanager.com
www.gstatic.com
www.intercom-reporting.com
www.loom.com
www.paypal.com
www.youtube.com
```

</details>

## Follow-up Task 3: public bundles, source maps, and Wayback

The 11 root bodies contained 977 page-to-asset references resolving to **527
unique JavaScript/CSS URLs**. Between 2026-07-24T02:58Z and 03:01Z, 526 returned
200 and one obsolete `html5shim.googlecode.com` reference returned 404. No
request errored or reached the 20 MiB cap; 40,917,640 bytes were saved. Of the
successful assets, 416 finished on `app.flocksafety.com` or
`users.flocksafety.com`; endpoint and flag extraction was restricted to those
first-party assets.

The map parser accepted only actual line-start JS/CSS `sourceMappingURL`
declarations. It found 48 external references and no inline map:

| Declaring asset family | Exact map references | Result | Supported conclusion | Explicit limits |
|---|---:|---|---|---|
| SafeBase security assets | 41 | 41 × 404 | The downloaded SafeBase assets declared maps that were unavailable at retrieval. | Point-in-time 404s do not prove the maps never existed. |
| Atlassian Statuspage CDN | 4 | 4 × 200, valid JSON with `sourcesContent` | Four third-party Statuspage maps were publicly retrievable. | They describe Atlassian-delivered code, not Flock application source. |
| Wistia | 2 | 1 × 403; 1 × 404 | The declared maps were not retrieved. | No absence claim. |
| Lenis on marketing pages | 1 | 1 × 200, valid JSON with `sourcesContent` | One third-party library map was public. | It is upstream Lenis code. |

All five reachable maps were third-party Lenis/Atlassian assets. No downloaded
`app`, `users`, or `docs` bundle contained a live map declaration, and no map
filename was guessed.

One app-shell script reference was literally `/src/bootstrap.tsx`. Its exact
GET returned the HTML SPA shell rather than TypeScript source. That is a
fallback-routing observable, not a source-code disclosure.

### Shipped client configuration

The `app` root's public `FlockOS` bootstrap emitted
`login.flocksafety.com`, audience `com.flocksafety.hunch-punch`,
`wss://websockets.flocksafety.com/` with audience
`com.flocksafety.whiskey-sour`, and SSO redirect
`https://dev-users.flocksafety.com/`, plus a redacted Auth0 public client ID.
These are current browser-configuration observables. The websocket and redirect
targets were not requested; the strings do not prove resolution, liveness,
production use, or unauthenticated access.

One directly referenced app bundle contained six exact microfrontend manifest
URLs:

- `https://hotlist.flocksafety.com/public/mfe/mf-manifest.json`
- `https://nightshift.flocksafety.com/public/mfe/mf-manifest.json`
- `https://patrol.flocksafety.com/public/mfe/mf-manifest.json`
- `https://search-2.flocksafety.com/public/mfe/mf-manifest.json`
- `https://sharing.flocksafety.com/public/mfe/mf-manifest.json`
- `https://vms.flocksafety.com/public/mfe/mf-manifest.json`

None was fetched. Their presence establishes shipped configuration, not an
enabled module, reachable manifest, or distinct workload.

The shared `users`/`admin` main bundle was 13,318,288 bytes at retrieval
(SHA-256
`e89e3c06668920c013729cf1504ab6d4a2f94b063f6d22875adadcedc0ce9161`
before redaction). Its public configuration labeled the app `coke`,
`env: prod`, and `environment: production`; used request prefix `coke-`; named
`https://crown.flocksafety.com/` as an API base; and listed first-party
LaunchDarkly proxy names plus `apple-pie-moonshine`, `hit-diagnosis-api`,
`analytics`, `planner`, `transparency`, and `grog` service URLs.

Lexical extraction found 76 distinct API-style route templates in that bundle.
Representative exact strings include:

- `/api/v1/organization/${e}/user/csv`
- `/api/v1/organizations/${e}/integrations/${t}/${n}/export`
- `/v1/authorized-access-lists`
- `/v1/authorized-access-lists/${e.authorizedAccessListId}/entries`
- `/v1/integrations/forcemetrics/oauth/auth-url`
- `/v1/map/token`
- `/v1/organization/${e}/lprPolicy`
- `v1/organizations/${e.organizationId}/data-requests/preservation`

No route was called. Static code can retain disabled, dead, vendor-library, or
role-gated paths and does not establish current server behavior.

The same bundle contained 30 feature-flag keys:

`showBillingBanner`, `showFusus`, `showLowes`, `showOrgEnableDisable`,
`showOrgActivateDeactivate`, `showUserLevelAuth`, `showThinkLp`,
`showFreeformSearch`, `showEnableHotlistCamerasButton`, `showOrgFormV2`,
`showAutoPermissionProvisioning`, `showFlockBusinessNetwork`,
`showNightshiftPermission`, `showDeviceManagement`, `showOrgFormV2Release`,
`shouldShowImportShapeFile`, `showDataPreservation`, `showNovaPermissions`,
`showDeterrencePage`, `shouldValidateOri`,
`showOwnTransparencyReportPage`, `showSharedNetworksPage`,
`showManageFreeTrials`, `showBulkSelectUserActions`,
`showExternalOffenseTypeManagement`, `flockPhoenix`,
`showFinAiPermissions`, `canUseMicrofrontend`,
`showUnauthorizedVehicleAlerts`, and `showDataAndPrivacy`.

The names prove only that the keys were compiled into the live client. They do
not reveal values, rollout, entitlement, or server-side state. No LaunchDarkly
URL was contacted. The artifact's production labels coexist with an embedded
Datadog RUM block labeled `service: dev-coke` and `environment: dev`; that exact
configuration mismatch does not prove the served application is a development
deployment.

### Exact Wayback outcome

Five representative exact content-hashed bundle URLs without first-party live
maps were submitted to Wayback CDX at **2026-07-24T03:04–03:05Z**:

| Bundle family | Exact CDX result | Supported conclusion | Explicit limits |
|---|---|---|---|
| Marketing Webflow | 200 with `[]` | No capture was exposed for that exact hashed URL. | Alternate filenames or captures are not excluded. |
| App main | 403 `AdministrativeAccessControlException: Blocked Site Error` | Archive retrieval was blocked. | No archive-absence claim is possible. |
| Docs ReadMe main | 200 with `[]` | No capture was exposed for that exact hashed URL. | Same exact-URL limit. |
| Users main | Same 403 administrative block | Archive retrieval was blocked. | No archive-absence claim is possible. |
| SafeBase page bundle | One 2026-07-23 capture; replay 200 | The replay was byte-identical to the live 7,235-byte asset. | It supplied no older variant and says nothing about other bundles. |

Thus Wayback was checked, but the administrative block prevents a defensible
historical result for the two first-party application bundles.

## Follow-up Task 4: Shodan/Censys and edge fingerprints

The follow-up began and ended with 92 Shodan query credits and 100 scan credits.
No scan was submitted and the observed balance did not change.

| Exact stored-data query, 2026-07-24T02:58–03:07Z | Result | Supported conclusion | Explicit limits |
|---|---:|---|---|
| `ssl:"flocksafety.com"` | 43/43 retrieved | Broader SAN/token search added three rows missed by the earlier subject-CN query. | Rows are indexed service observations, not live unique hosts. |
| `ssl.cert.subject.O:"Flock"` | 0 | No exact subject-organization match in this index snapshot. | Organization fields may be absent or different; zero is query-bounded. |
| `hostname:flocksafety.com` | 30/30 retrieved | Shodan stored hostname-level Flock observations. | Counts are service observations; provider aliases are not workloads. |
| `hostname:gov.flocksafety.com` | 0 | No exact bounded hostname match. | It is not a wildcard-subdomain absence test. |
| `ssl:"gov.flocksafety.com"` | 0 | No exact bounded SSL token match. | Same index/query limitation. |
| `http.html:"flocksafety.com"` | 0 | No exact HTML-token result. | Shodan may not render or retain relevant content. |
| `http.title:"Flock Safety"` | 299; adding `hostname:flocksafety.com` or `ssl:"flocksafety.com"` reduced it to 0 | The broad title count is unattributed. | It must not be reported as 299 Flock hosts. |
| `http.favicon.hash:-149422220` | 0 | No indexed banner matched the marketing-site favicon hash. | Different icons/encodings, unrendered pages, and unindexed virtual hosts remain possible. |
| `ssl:"flocknova.com"` | 10/10 retrieved | Shodan stored ten certificate observations, all on AWS GovCloud-region PTR names. | Ten observations are not necessarily ten workloads. |

Three of the 43 SSL rows presented one Amazon-issued leaf with subject
`*.flocknova.com`, SANs `*.flocknova.com` and `*.flocksafety.com`, fingerprint
`c6d8a28e4879ecc480c5c99cb97397a03b34e7847c15f0b41b907e7e0f728df1`,
valid from 2026-06-16, and observed on three AWS PTR names ending
`us-gov-west-1.compute.amazonaws.com` between 2026-07-16 and 2026-07-20.
This is strong certificate-deployment association between the namespaces, not
legal-domain ownership, application liveness, or proof that every host using
either name belongs to Flock.

The ten `flocknova.com` observations split across two leaves: seven on a
`*.flocknova.com`-only certificate valid from 2026-01-27 and three on the mixed
leaf. All ten used the same Shodan JA3S. Verisign RDAP, retrieved
2026-07-24T03:09–03:10Z, says `flocknova.com` was registered 2025-02-26 through
GoDaddy and delegated to four Route 53 nameservers, but supplied no registrant.
Flock's first-party page, observed live on 2026-07-24, displays a publication
date of 2025-02-13 and calls Flock Nova its data-intelligence platform. No
offline snapshot of that page was retained in the fingerprint artifact
directory. The live branding observation and mixed SAN together support the
association; the RDAP record alone does not prove ownership.

The three mixed-SAN GovCloud observations and 20 commercial
`*.flocksafety.com` observations shared JARM
`29d29d00029d29d00041d41d00041dcb3f8752a2d70d1dbf446fc46ab5df96`,
JA3S `2009b2385b34539627d76cfaf1db72a2`, and `awselb/2.0`. However,
count-only pivots returned 2,395,652 observations for that JARM and 282,935 for
the JA3S. A stored observation at one current `.gov` DNS address also showed an
unrelated certificate with the same JARM.

**Supported conclusion:** the government-region and commercial observations
share a coarse AWS ELB edge class. **Explicit limit:** the fingerprints cannot
establish identical code, backend, tenant, configuration, controls, deployment
pipeline, ownership, or data residency.

No Censys query was completed. The repository had no Censys wrapper or
configured credentials, and an unauthenticated request to the public search
surface received a Cloudflare 403 challenge. This is a coverage gap, not a zero
result.

## Follow-up Task 5: public GitHub code search

Searches ran through a read-only GitHub connector on 2026-07-24. Result counts
are bounded by the connector index and `topn` cap; full-hostname strings were
supplied, but exact-phrase semantics are not guaranteed. Pinned positive-file
derivatives retain commit and Git blob SHAs while redacting secret-shaped
values.

| Exact observable | Source and timestamp | Supported conclusion | Explicit limits |
|---|---|---|---|
| The apparently Flock-operated `flocksafety` namespace displayed nine public repositories. `flock-core-fedramp20x` describes itself as “Flock Safety's FedRAMP 20x Phase One Pilot Submission”; saved metadata records a root commit on 2025-06-13 and a “Promote internal to Public” commit on 2025-08-27. | [`flocksafety` organization](https://github.com/flocksafety), [repository](https://github.com/flocksafety/flock-core-fedramp20x), commit-pinned API data retrieved 2026-07-24T03:02:46Z–03:02:56Z | A public Flock-branded FedRAMP submission artifact exists. | The organization page displayed branding and a Flock-domain link but no GitHub Verified badge. Commit text does not prove visibility or operational launch dates. |
| Organization-scoped searches for `flocksafety.com`, `api.flocksafety.com`, `external.gov`, `dbproxy`, `Federal Sharing`, and `Auth0` returned only the FedRAMP README hit for the apex query. | Read-only connector, `org=flocksafety`, `topn=100`, rerun and retained 2026-07-24T03:21Z | No searched endpoint or distinctive label appeared in that bounded public-code index. | Deleted, private, history-only, lagging, or unindexed content is outside the result; zero is not absence. |
| At commit `f5a4a75`, third-party repository `erhhung/ncric-alprs` described an ALPRS stack, a staging database for an NCRIC organization holding “Flock raw data,” and a “Flapper” integration. Its docs name `https://api.flocksafety.com/api-docs/` plus `POST /v1/auth/userpass`, `POST /v1/query`, `POST /v2/images`, and `GET /v1/cameras`; config names `https://api.flocksafety.com/api` with environment-substituted credentials. | [README](https://github.com/erhhung/ncric-alprs/blob/f5a4a7538caeb687fb77e73df12cf48e57dff8a9/README.md), [API notes](https://github.com/erhhung/ncric-alprs/blob/f5a4a7538caeb687fb77e73df12cf48e57dff8a9/docs/flock_api.md), [config](https://github.com/erhhung/ncric-alprs/blob/f5a4a7538caeb687fb77e73df12cf48e57dff8a9/flapper/config/flapper.yaml), pinned retrieval 2026-07-24 | This is evidence of the repository author's claimed integration design and URL/route strings. | The repository is not Flock-owned; same-repository files are one lineage, not independent corroboration. The design may be stale, customized, inaccurate, or nonfunctional. No route was called. |
| The same repository's dev/prod example files contain one populated Flock-account email and three populated Auth0 client IDs; paired password/client-secret fields are empty. | [Production example](https://github.com/erhhung/ncric-alprs/blob/f5a4a7538caeb687fb77e73df12cf48e57dff8a9/config/prod.tfvars.example#L160-L175) and dev example, pinned retrieval 2026-07-24 | The examples expose populated, potentially operational identifiers and an expected authentication shape, but no populated secret was found in the reviewed fields. | Client IDs are normally public identifiers. This was not a repository-history-wide secret scan; values were redacted and never tested. |
| Community repository `QuyDu/Xavier` sets `https://api.flocksafety.com/v2` and appends `/plate-reads`. | [Pinned file](https://github.com/QuyDu/Xavier/blob/4871f1c72cf003a5f81c489ba3d189b4abab8da9/webapp/app/services/flock_lpr.py), retrieved 2026-07-24 | This records another author's claimed integration design. | No demonstrated Flock affiliation or route validity; the code may be example, speculative, or generated. |
| Generated `api-search/scopes` and `api-search/security` files describe bearer/client-credentials OAuth and plate-read/hotlist scopes while citing one `api-evangelist/flock-safety` OpenAPI lineage. | [Scopes](https://github.com/api-search/scopes/blob/e6a5eecc91e7a6920dd35926a40e2ad092371b45/_scopes/flock-safety/flock-safety-scopes.md) and [security](https://github.com/api-search/security/blob/f9552206f9c0a1f2b7a9dc46dac2952f4204bed5/_security/flock-safety/flock-safety-authentication.md), retrieved 2026-07-24 | The generated files preserve a tertiary claim about an API design. | The cited upstream returned 404 at observation; both files share one lineage and may be stale. No token endpoint was requested. |
| Searches using `prod-dbproxy.gov.flocksafety.com`, `scim.flocksafety.com`, and `device-login.flocksafety.com` returned only two bulk subdomain-list repositories; `sftp.hotlist-importer.flocksafety.com`, `external.gov.flocksafety.com`, and `dev-external-flt.gov.flocksafety.com` full-hostname queries returned zero. | Selected retained search ledger, 2026-07-24T03:21Z | GitHub added no independent functional evidence for those labels in this bounded pass. | Bulk lists may copy CT/passive DNS and are redundancy, not corroboration; zero is index-bounded. |

## Potential disclosure items

Nothing in this section was validated, exchanged, submitted, replayed, or used.
Most items are deliberately browser-visible public identifiers rather than
authentication secrets; they are retained because the user requested
conservative disclosure triage.

| Source/location | Class | Redacted observable | Assessment and handling |
|---|---|---|---|
| App shell | Auth0 public client ID | `[REDACTED sha256:4c2bf6d593088aa7 len:32]` | Public OAuth identifier, not a bearer secret; unused. |
| Users bundle | Messaging app ID | `[REDACTED sha256:63888f0059567efc len:8]` | Client configuration; sensitivity not tested. |
| Users bundle | Session-replay organization ID | `[REDACTED sha256:7c06b6bd28904d65 len:36]` | Client configuration; unused. |
| Users bundle | LaunchDarkly client ID | `[REDACTED sha256:585c2ce61fa4a761 len:24]` | Client-side identifier; no LaunchDarkly request made. |
| Users bundle | reCAPTCHA site key | `[REDACTED sha256:494fb23b553f5174 len:40]` | Public site key; unused. |
| Users bundle | Segment write key | `[REDACTED sha256:4401aef301f0e76b len:32]` | Browser telemetry key; unused. |
| Users bundle | MUI X client license | `[REDACTED sha256:85fdfc0a74f62e38 len:100]` | Embedded client license; unused. |
| Users bundle | Auth0 public client ID | `[REDACTED sha256:a18e123fcef72e55 len:32]` | Public OAuth identifier; unused. |
| Users bundle | Datadog RUM app ID / public client token | `[REDACTED sha256:4f5c77509954a154 len:36]`; `[REDACTED sha256:f083f4e3506f38a0 len:35]` | Public browser telemetry identifiers; unused. |
| Security CSP | Sentry reporting key | `[REDACTED sha256:76b40c7d20f7d11b len:32]` | Browser-reporting DSN component on SafeBase page; unused. |
| SafeBase client configuration | Split, Segment, Flatfile, Datadog, Sentry, Amplitude, MUI X, FullStory, Auth0, Stigg, and Brandfetch public/client-side identifiers | Twelve values retained only as redacted SHA-256-prefix/length fingerprints in `bundle-observables.json` | Third-party `NEXT_PUBLIC_*` configuration; provider-level attribution only. None was used. |
| Third-party GitHub example | Three Auth0 client IDs | `[REDACTED CLIENT ID]` | Paired client-secret fields were empty; client IDs are not credentials by themselves. |
| Third-party GitHub example | Flock integration-account email | `[REDACTED EMAIL]` | Password field was empty; identifier may merit disclosure review but is not a credential. |
| Flock public pages | Cloudflare visitor cookie | `_cfuvid=[REDACTED]` | Automatically set, redacted in saved headers, never replayed. |
| Censys 403 response | Cloudflare challenge cookie | `[REDACTED-UNUSED-TRANSIENT-CLOUDFLARE-CHALLENGE-COOKIE]` | Transient third-party challenge material; never replayed. |
| Public root/assets | Rotating cookies, challenge values, CSP nonces, and tracing identifiers | `[REDACTED rotating values]` | Ephemeral browser material; redacted and not treated as credentials. |

Two lexical “private key” hits were audited against adjacent bundle text. Each
was only the literal 27-character `BEGIN PRIVATE KEY` header marker inside
parsing-library code; neither had adjacent encoded data or an ending marker.
They are false positives and are excluded from the disclosure list.

A bounded lexical scan found no candidate AWS access key, JWT, GitHub token,
Slack token, Stripe secret, Google API key, or actual private-key payload. That
is not a guarantee that no other sensitive value exists.

## Bounded negative results and limitations

- crt.sh wildcard/SAN-detail requests intermittently timed out or returned
  404/502. A later base-domain raw JSON export succeeded and supported the
  per-identity chronology above. Failed endpoints still do not support absence
  claims.
- Internet Archive calendar endpoints returned administrative blocks for
  sampled site URLs. Exact CDX bundle lookups later returned empty arrays for
  two representative URLs, an identical current SafeBase capture for one, and
  administrative 403s for the app/users bundles. This does not establish who
  requested blocking or that no alternate captures exist.
- Shodan returned `vulns:null` on five reviewed host resources. That means Shodan supplied no vulnerability list in those records, not that the endpoints are vulnerability-free.
- The URLScan full-result JSON endpoint required login. Existing public HTML result pages supplied the representative technology and dependency evidence.
- The follow-up ran the requested SSL, subject-organization, hostname, title,
  HTML, favicon, JARM, and JA3S pivots. It did not run a broad organization,
  ASN, CIDR, or cloud-range enumeration because shared-provider results would
  be weakly attributable and potentially expansive.
- Censys coverage remains incomplete: no repository wrapper or configured
  credentials were available, and an unauthenticated request to the public
  search surface returned a Cloudflare 403 challenge.
- The first pass used one Shodan query credit. During the follow-up, the
  displayed balance remained 92 query and 100 scan credits from start to
  finish; no scan was submitted.

## Follow-up leads

1. Obtain authorized Censys Platform access or add a repository wrapper, then
   reproduce the bounded certificate/hostname pivots without treating shared
   cloud addresses as Flock assets.
2. Establish passive CT and authoritative-DNS monitoring for new names, issuer
   changes, and durable provider migrations.
3. Compare exact PR-preview naming and certificate validity dates with
   contemporaneous public release records, without resolving or probing the
   preview hosts.
4. Track sitemap diffs and public bundle hashes to identify newly shipped legal,
   product, route, or feature-name changes while preserving the same retrieval
   boundary.
5. Corroborate AWS/GovCloud architecture through procurement records, security
   documentation, FedRAMP materials, and first-party technical disclosures
   rather than endpoint inference.
6. Consider responsible disclosure for the redacted account identifier and
   client-side configuration inventory only after human review; do not test any
   value.
7. Create a dedicated Flock Safety investigation profile before writing
   findings or leads to `investigation.db`.

The sitemap exposes several first-party pages suitable for the next document
review: `/blog/flock-safety-cybersecurity-how-we-protect-customer-community-data`,
`/blog/flock-security-testing-bishop-fox-privacy`,
`/blog/response-to-compiled-security-research-on-flock-safety-devices`,
`/blog/understanding-flocks-testing-and-development-program`,
`/blog/update-on-limited-condor-device-configuration-issue`, and
`/blog/has-flock-been-hacked`.

## Reproducibility

Primary repository commands used:

```bash
uv run python tools/query_shodan.py domain flocksafety.com --history --output <file>
uv run python tools/query_shodan.py search 'ssl.cert.subject.CN:flocksafety.com' --count-only --facets org,port --output <file>
uv run python tools/query_shodan.py ssl-cert flocksafety.com --output <file>
uv run python tools/query_crtsh.py timeline flocksafety.com --output <file>
uv run python tools/query_crtsh.py search www.flocksafety.com --output <file>
uv run python tools/query_urlscan.py search 'domain:flocksafety.com' --limit 100 --output <file>
```

Follow-up representative commands:

```bash
curl --location --max-time 90 \
  'https://crt.sh/?q=flocksafety.com&output=json' \
  --output /tmp/osint-l7qLKAAV/ct-federal/crt-raw-flocksafety.json

uv run python tools/query_shodan.py search 'ssl:"flocksafety.com"' \
  --page 1 --limit 100 \
  --output /tmp/osint-l7qLKAAV/fingerprint-pivots/search-ssl-domain-p1.json

uv run python tools/query_shodan.py search 'ssl:"flocknova.com"' \
  --page 1 --limit 100 \
  --output /tmp/osint-l7qLKAAV/fingerprint-pivots/search-ssl-flocknova-p1.json

uv run python tools/query_shodan.py search \
  'http.favicon.hash:-149422220' --count-only \
  --output /tmp/osint-l7qLKAAV/fingerprint-pivots/count-favicon-hash.json

curl --location --max-redirs 10 --max-time 60 \
  --dump-header /tmp/osint-l7qLKAAV/headers-bundles/live/HOST.headers \
  --output /tmp/osint-l7qLKAAV/headers-bundles/live/HOST.body \
  https://HOST.flocksafety.com/
```

Bundle decision rules and local parsers:

1. An asset URL had to appear in returned HTML as a script, stylesheet, or
   preload reference.
2. A map URL had to resolve from an actual `sourceMappingURL` declaration.
3. Wayback queries used exact live bundle URLs; no guessed or wildcard paths.
4. Secret-shaped values were redacted and never used.

An adversarial audit found one SPA-fallback copy of the app shell that the
first sanitizer pass had missed. It was redacted before this report was
finalized, saved-body hashes were added to `asset-fetch-results.json`, and targeted
scans found no remaining raw auth-bootstrap base64, Cloudflare challenge
object, or keyed users-configuration value. Repeated sanitizer runs produced
zero new changes; the aggregate SHA-256 over the settled evidence files
(excluding the sanitizer script) was
`32424a5ab9bc629777eb329c9c8cd61ed4e72ee2cc6cea5c1891434bf697eba7`
on both checks. The sanitization log is a useful transformation ledger but not
a complete chain for every duplicate/root-body rewrite, so it should not be
treated as exhaustive provenance.

First-pass artifacts were retained under `/tmp/osint-WRuYkZKn/`. Key reports:

- `/tmp/osint-WRuYkZKn/report-official.md`
- `/tmp/osint-WRuYkZKn/report-ct-dns.md`
- `/tmp/osint-WRuYkZKn/report-shodan.md`
- `/tmp/osint-WRuYkZKn/report-web-history.md`
- `/tmp/osint-WRuYkZKn/review-initial.md`
- `/tmp/osint-WRuYkZKn/review-final.md`

Follow-up session artifacts were retained under `/tmp/osint-l7qLKAAV/`.
Those paths are ephemeral unless separately archived:

- `/tmp/osint-l7qLKAAV/report-ct-federal.md`
- `/tmp/osint-l7qLKAAV/report-headers-bundles.md`
- `/tmp/osint-l7qLKAAV/report-fingerprint-pivots.md`
- `/tmp/osint-l7qLKAAV/report-github.md`
- `/tmp/osint-l7qLKAAV/github-pinned-evidence.json`
- `/tmp/osint-l7qLKAAV/github-search-ledger.json` — selected bounded queries,
  not the complete underlying search session
- `/tmp/osint-l7qLKAAV/review-stage1.md`
- `/tmp/osint-l7qLKAAV/review-stage2.md`

Captured sitemap/robots SHA-256 values:

- `sitemap.xml`: `d78af828c1dc2c7189c37c4e2354b1fe8a6aec7fa19a4454c861c3a3d784aea2`
- `robots.txt`: `10e2d90bded23f99ea7d35e63d7e7143da594dd7ffc87b0fc8efc88919efca82`

Selected follow-up artifact SHA-256 values:

- `crt-raw-flocksafety.json`: `178f3f953e14b193152ab94ed1814c3a2503207911e067d0fb53bc61ad504664`
- `ct-first-seen.json`: `a5e1cb7ff4790c9ee71a5d294ec7ff0b1a69f58055f165787853ada86269fc4f`
- `asset-fetch-results.json`: `6b5e27db14c39fd041e1865b2764b94c96a3ce9b0ee8921ab1d147309b95085c`
- `bundle-observables.json`: `bee498af1143f33b9eeb70f989ef0c67eb2a45e13e2336be7736b700b0fc6ae5`
- `source-map-fetch-results.json`: `b4296cd2a25a6f1871afd67f8cc0923637eedd2db33cbb96daff7f67976676c0`
- `csp-marketing-diff.json`: `f4b121eee566db08c3b0b416cdbd1e4de6000b32fcfdb6dc7e756fd20b0a6757`
- `search-ssl-domain-p1.json`: `dbcb776f370e4f4fa71905c8a4a4acd62da51591d899584a8255959d585a9489`
- `search-ssl-flocknova-p1.json`: `441babfcad4ffab785c8fdb87c57fe91d82a03e447639d467220689aafa2555a`
- `github-pinned-evidence.json`: `fa4ac5ca57ad230775cac8eeb01b88ada48eb0c4c16ef122cd008244f64b075c`
- `github-search-ledger.json`: `43e22f104624ec421b241ef248af33ec786ed10892529bc49be2a4e71d671e9d`

## First-party references

- https://www.flocksafety.com/
- https://www.flocksafety.com/legal/privacy-policy
- https://www.flocksafety.com/legal/flock-evidence-policy
- https://www.flocksafety.com/legal/lpr-policy
- https://www.flocksafety.com/legal/api-integration-terms
- https://docs.flocksafety.com/
- https://docs.flocksafety.com/developer-hub/reference/post_oauth-token
- https://status.flocksafety.com/
- https://security.flocksafety.com/
- https://www.flocksafety.com/sitemap.xml
- https://www.flocksafety.com/robots.txt
- https://www.flocksafety.com/blog/does-flock-share-data-with-ice
- https://www.flocksafety.com/blog/ensuring-local-compliance
- https://www.flocksafety.com/blog/flock-nova-smarter-investigations-faster-case-resolutions
- https://github.com/flocksafety/flock-core-fedramp20x
