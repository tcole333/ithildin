# MANIFEST — Elephant Clipping infra wave, Lane 5 (Discord + monsterlab subdomains)

- Generated (UTC): 2026-09-02T19:20:16.943419+00:00
- Agent: agent-L5-discord | Lead: #95061 (advances hunch #94998) | source_skill: investigate-infra
- Method: unauthenticated, passive only. Discord public invite/widget/discovery APIs; single HTTP HEAD/GET of subdomain roots; single openssl s_client TLS cert read; already-indexed Shodan host data; ARIN RDAP; crt.sh CT logs. Honest research UA (`Ithildin-OSINT-Research/1.0`), no browser spoofing.
- Out of scope / NOT done: no server join, no message/channel reads, no authenticated Discord API, no port scanning/vuln probing/brute force, no path enumeration, no bot-check solving.
- Sanitization: transient Cloudflare cookies (`_cfuvid`) and rotating CF telemetry (Report-To/NEL/CF-RAY/x-vercel-id/etag) removed from stored headers; Discord boilerplate CSP (static public Sentry DSN) dropped from Discord-surface headers. Target CSPs on books/relay retained as substantive infrastructure evidence.

| SHA-256 | Bytes | File | Description |
|---------|-------|------|-------------|
| `5649764d89f6853678c9238b4564e0eb985b71911136a85a2c6f56b1537a4845` | 2703 | `books-monsterlab-head.headers.json` | Sanitized HEAD headers for https://books.monsterlab.io/ (200, Server: Vercel). CSP RETAINED - documents Stripe/Google Pay/Firebase/hCaptcha/ipify integration surface. |
| `c0e5a35a738b0f902b97e94410f9202a1878220b58ae720018de1abc3b7d1d8d` | 4190 | `cert-books.monsterlab.io.pem` | Leaf TLS certificate presented by books.monsterlab.io (single openssl handshake). CN=books.monsterlab.io, Let's Encrypt YR2, valid 2026-07-13..2026-10-11, SAN single-domain. |
| `3a5f06a598bf6f923c6afc0e925fa5101350580c97959e019f2ead3c8f81ae8e` | 3947 | `cert-relay.monsterlab.io.pem` | Leaf TLS certificate presented by relay.monsterlab.io (single openssl handshake). CN=relay.monsterlab.io, Let's Encrypt YE1, valid 2026-07-24..2026-10-22, SAN single-domain. |
| `ffa332f412127a369dac969a2cfb4f0cf74589b41b7ab8883808b6aa4779b0f7` | 213 | `crtsh-monsterlab-subdomains.json` | crt.sh CT-log subdomain enumeration for monsterlab.io: api, books, apex, relay, www (138 certs). |
| `0845c7ecc1716868056b889131cc0ef07162eaeaf2ecc22c9ab5564a5ef558dc` | 30942 | `crtsh-monsterlab-timeline.json` | crt.sh certificate issuance timeline for monsterlab.io: 76 certs, first 2017-03-20, steady since 2023-03; issuer mix. |
| `d52f0acf1f5e586dde5e5ed04b8c366d85a98456ce83d201d001cc60c9dbdc36` | 3328 | `discord-discovery.extracted.json` | Extracted schema.org ld+json + OpenGraph meta from the public discovery page (200). SPA shell; exposes name/id/description/splash/category + SubscribeAction count only. |
| `5b94dc1fcedf5687fa37bb649ccf9b1bcc5282e46b460fb03fa02c93be76effb` | 1144 | `discord-discovery.headers.json` | Sanitized response headers for the discovery page GET (200). |
| `4fedea4d283702e9ad684b0a32b8c0a364dfc787286594382a85fe92837dcb29` | 1185 | `discord-invite-clipit.headers.json` | Sanitized response headers for the invite API GET (200). |
| `976fc8bf9fd04f761885ef0c28d9e247e2264ac84362ff337d94138338d93aa6` | 5709 | `discord-invite-clipit.json` | Full unauthenticated Discord invite object for vanity `clipit` (v10 invites API, with_counts+with_expiration). Public guild metadata: 41 features, profile traits, tag, permanent invite, counts at capture, creator-name description. No tokens. |
| `63247f4f28ec2b8ca8a050cfaf7dd4ca58bf37361d6b48b6873f6bc23d540205` | 408 | `discord-snowflake-decode.json` | Deterministic Discord-snowflake decode of guild/invite/rules/proxy-support IDs to UTC creation timestamps. |
| `a541491db7f030559a82f142a49f33e0e7b697fb268717d82a37078db56b0628` | 1049 | `discord-widget.headers.json` | Sanitized response headers for the widget.json GET (403). |
| `b6304e7b1b4ba8f216d49cece9f5bacf4380239ffa8b80c30cded61db98dae1c` | 93 | `discord-widget.json` | guild widget.json result: HTTP 403 + body {"message":"Widget Disabled","code":50004}. Public widget is DISABLED by the owner. |
| `7ef1c8ce66730aacca1f6ea93d539a55c8e6460410cf82c6b2e2b59e3d735f51` | 15483 | `rdap-98.142.250.50.json` | ARIN RDAP record for 98.142.250.50: 98.142.250.0/24 assignment, registrant masked (Private Customer) via Internet Utilities NA LLC. |
| `257902aeb8de52c3231c55c0c94f91dfeb68aa3063687055faf548dcbeff3918` | 724 | `relay-monsterlab-head.headers.json` | Sanitized HEAD headers for https://relay.monsterlab.io/ (404 JSON, Via: 1.1 Caddy). |
| `ecc885bf14fbba335ca544c8ddc16689edf879fea4234b7e7c2e8d5985fdd1cc` | 243 | `relay-monsterlab-root-get.json` | GET of relay public root: Fastify default not-found JSON. Root only; no path enumeration. |
| `4536f824d77d18e40aad7004f1155e841f22fc09999782a1370a0ccf165328b0` | 9060 | `shodan-98.142.250.50.raw.json` | Raw Shodan host record for 98.142.250.50 (already-indexed passive data; Shodan performed the scan, not this agent). |
| `b01eec5bd62d1d989546a79b734c35f6ee87dcde8a661c0cce0349253d1723d4` | 1407 | `shodan-98.142.250.50.summary.json` | Trimmed Shodan summary: org LINVEO LLC / AS62564, Dallas US, rDNS 50.250.142.98.tx1.linveo.com, ports 22/80/443, per-service banners. |
