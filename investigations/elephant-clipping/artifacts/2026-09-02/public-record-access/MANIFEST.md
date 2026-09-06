# Public-record availability evidence

Profile: `elephant-clipping`. Collected and reviewed September 2, 2026.

This bounded follow-up distinguishes operator-published marketing from actual
campaign and payment records. It does not establish a Firebase data exposure.
The parent independently viewed the three sampled images and reviewed findings
15444–15445, including their attribution, quoted evidence, currency, date limits,
lead ownership and confidence. These remain working investigative findings, not
human publication clearance or authenticated financial transactions.

## Preserved files

| File | SHA-256 |
|---|---|
| `report-public-records-access.md` | `26e280cee92f5d3031d3e108a307a4a416321cd0babc1770655434e3b169477e` |
| `public-document-notes.md` | `6b8a20cf590940682700a85308063356e1922232004ca9d136d3db67a1f6faf8` |
| `report-browser-public-access.md` | `65bf825a889d8b99e16f4324049bb260eddb14f2bee21b27e4b58f76ebc6c0e5` |
| `browser-public-access-notes.md` | `a1184792a341c7c53700d21c5071eee817db69c0553cc3071d96df2de37a84c4` |
| `browser-public-login-snapshot.md` | `45ef02f8f04e32da8bee88d4fd4030f3e0826cce4ae50a6045919f76914707d5` |
| `report-bucket-metadata-check.md` | `43d74491a77e355d8dc900ac396af65ae71bd96571d58c290586bb43ad239759` |
| `bucket-observation.json` | `281bb68f106d19347df6a5c5fef940a34d4922573490712783d5e9345710d23f` |
| `bucket-response.json` | `a2458c584e4dda8577575ffd4601654604e16493c7acfab017ea375884eab70b` |
| `bucket-provider-docs.md` | `ff269437591154a5dc87005fcdac1b268ca1b68d6dec5f51cc26ce34905041bc` |

The two reports and two notes files are byte-identical to the reviewed originals
under `/tmp/osint-Fk3kmuKS/`. The preserved login snapshot has one added terminal
newline (1,697 bytes versus the source's 1,696); comparison verified no other byte
difference. Its original SHA-256 is
`a1da55f8fa0e911bf7e6e1e6d37407f1f9037fb090ea1b3c5cc1030d2b7896a0`.
Original images, raw page HTML and raw search-result pages
remain temporary. Incidental testimonial names and avatars were not transcribed
or made into entity records. No credentials, signed URLs, account identifiers or
private records are included in this handoff.

## Coordinator checks

- The earlier brand and Serviuos HTML and freshly captured brand HTML all name
  the same eleven `/results/` PNG paths. No new path was added in that comparison.
  The three sampled images are newly reviewed, not established newly published;
  historical image bytes were not available for comparison.
- A local scan of 920 retained HTML/HTM/JS/JSON/TXT files found no concrete
  absolute Monster campaign/share URL or literal known-form Firebase/GCS object
  URL for the disclosed bucket. Three campaign matches were wildcard-query
  bookkeeping artifacts. This is neither 920 independent sources nor coverage
  of all relative, dynamically constructed or encoded URLs. The local-only
  audit script passed Ruff.
- The orphan older empty share-CDX artifact lacks corroborating successful
  acquisition metadata. It is not a verified zero. The separately documented
  Wayback 429 and URLScan 403 remain errors, not negative search results.
- The post-pass local cross-reference scan created zero automatic leads.
- Five explicitly tagged Learnings were ingested as observations 2592–2596.
- The normal browser entry reached the rendered login form; finding 15446's
  exact source quotation matches the preserved snapshot. This does not test
  Firebase object permissions or every share route. Passive request metadata
  distinguishes automatic installation/analytics traffic from record access;
  the response-body gap after tool context loss remains explicit. Four browser
  Learnings were ingested as observations 2599–2602.

## Direct metadata check

The four bucket-check artifacts were reviewed separately against the complete
small service error and provider documentation. They are byte-identical copies
of the worker artifacts. One anonymous request on the exact disclosed name
returned HTTP 401 for `storage.buckets.get`, including the service's explicit
nonexistence ambiguity. No object listing, file retrieval, IAM/ACL query,
Firestore query or authentication was attempted. This is not a Firebase rules
audit or a conclusion about individual file readability. No new exposure finding
was added. Its single Learnings observation is 2603.
