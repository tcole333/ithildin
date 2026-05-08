# The Real World (Andrew Tate)
**Stats**: 11 findings, 4 connections, 0 entities
**Dossier**: /dossiers/the-real-world-andrew-tate

## Key Findings
- **[digital/confirmed]** therealworld.com is owned by MTV/Viacom (Paramount), not Andrew Tate; HTTP 301 redirects to www.mtv.com/series/all-content; Tate's platform runs on jointherealworld.com (2026-03-28) (Finding #8256)
- **[digital/confirmed]** TRW content library hosted on Hetzner dedicated server (91.98.19.94) in Dubai, UAE — operationally consistent with Tate's UAE base (2026-03-28) (Finding #8257)
- **[digital/confirmed]** Live Radom Pay checkout (pay.radom.com/checkout/{uuid}) confirmed redirecting to Telegram after payment — consistent with TRW's crypto-then-community onboarding flow (2025-12-10) (Finding #8261)
- **[digital/confirmed]** TRW affiliate TikTok clip tool (cliptok.jointherealworld.com) runs on trw-afm.online, hosted on Hetzner Germany (128.140.103.112), registered via Porkbun (2025-08-10) (Finding #8258)
- **[digital/confirmed]** TRW checkout stack confirmed: Next.js/Vercel frontend, NMI card processing, Kount/Equifax fraud detection (ssl.kaptcha.com), 3DS Integrator for 3D Secure, HotJar analytics, internal ingest.therealworld.ag telemetry (2023-12-21) (Finding #8254)
- **[digital/confirmed]** nmi.therealworld.ag subdomain on Vercel confirms NMI payment gateway integration at DNS level; checkout also loads Kount (ssl.kaptcha.com) and 3DS Integrator (cdn.3dsintegrator.com) (2023-01-04) (Finding #8251)
- **[digital/confirmed]** The Real World internal infrastructure runs on therealworld.ag (Antigua TLD), launched 2023-01-01; 30+ service subdomains mapped including api, rpc2 (AWS ELB), sentry, unleash, nmi relay (2023-01-01) (Finding #8252)
- **[digital/confirmed]** jointherealworld.com domain secured via first SSL cert April 2019 — 4 years before TRW public launch — indicating early brand pre-positioning (2019-04-14) (Finding #8255)

## Top Connections
- **NMI (Network Merchants Inc.)** [corporate/strong]: Andrew Tate's The Real World uses NMI (Network Merchants Inc.) as its card payment processor after mainstream processors dropped the account. This relationship is confirmed via change.org petition update referencing NMI by name as the payment facilitator for Tate's merchandise and subscription store.
- **Radom Pay** [corporate/strong]: The Real World uses Radom Pay as its cryptocurrency subscription processor, confirmed via multiple source references identifying Radom Pay as the crypto payment rail for Hustler's University and The Real World alongside NMI for card payments.
- **New Era Learning LLC** [financial/strong]: NMI (Network Merchants Inc.) connects The Real World branded platform and New Era Learning LLC (operator) in its payment gateway role — neither entity has a direct documented edge to the other in the graph, only through NMI and Radom Pay
- **Radom Pay** [corporate/medium]: Radom Pay uses HotJar (site ID 6433214) for user behavior analytics on their pay.radom.com checkout page. The TRW checkout (checkout.jointherealworld.com) also loads HotJar. Both platforms use the same analytics vendor for checkout funnel analysis, though their specific HotJar site IDs may differ.
