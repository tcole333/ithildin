# org:We care 4 u LLC
**Stats**: 8 findings, 2 connections, 0 entities
**Dossier**: /dossiers/orgwe-care-4-u-llc

## Key Findings
- **[pattern/high]** wecare4llc.com contact page lists HADEF's Suite 225 address instead of We Care 4 U's Suite 224 — reveals website was built by cloning HADEF's template (2026-03-27) (Finding #8131)
- **[connection/high]** Phone (612) 800-4888 is shared between We Care 4 U LLC's DHS license record, MN.gov provider listings, wecare4llc.com, and hadef.org — confirming operator identity across entities (2026-03-27) (Finding #8133)
- **[infrastructure/high]** We Care 4 U LLC uses two emails: operational inbox info@wecare4llc.com and personal/alternative Gmail Wecarehomescare@gmail.com (2026-03-27) (Finding #8134)
- **[infrastructure/high]** wecare4ullc.com (typo variant) had a GoDaddy cert Jan 2024–Jan 2025, now NXDOMAIN — likely registered as placeholder then abandoned in favor of wecare4llc.com (2025-01-16) (Finding #8136)
- **[infrastructure/high]** wecare4llc.com had a burst of 7 subdomain cert issuances in August 2024 (app, admin, backend, dev, staging, demo, ftp) — indicating a healthcare application platform build-out prior to DHS license activation (2024-08-08) (Finding #8135)
- **[infrastructure/high]** We Care 4 U LLC operates wecare4llc.com, launched July 2023 with first cert from ZeroSSL; hosted on Hostinger (AS47583, IP 147.79.79.118) (2023-07-29) (Finding #8130)
- **[pattern/medium]** wecare4llc.com and hadef.org share identical WordPress stack including theme (ekko), cache hash (qiyc4fz1), and hosting org — consistent with single administrator or shared web developer (2026-03-27) (Finding #8132)
- **[infrastructure/medium]** HADEF maintains active @hadeforg social accounts on three platforms; We Care 4 U claims @wecare4u but all social links are dead/redirect to homepage (2026-03-27) (Finding #8137)

## Top Connections
- **org:Horn of Africa Development and Education Foundation** [corporate/strong]: wecare4llc.com and hadef.org share: identical WordPress theme (ekko), identical WP Fastest Cache hash (qiyc4fz1), same phone (612-800-4888), same hosting provider and Shodan org (Brander Group Inc./Hostinger AS47583), and identical page structure. The wecare4llc.com contact page incorrectly lists HADEF's Suite 225 address, confirming the LLC site was built by cloning HADEF's template.
- **org:Brander Group Inc.** [corporate/medium]: Both wecare4llc.com and hadef.org are attributed to 'Brander Group Inc.' in Shodan host data on Hostinger (AS47583). The shared attribution suggests both sites were built or managed by the same web developer entity. This developer is the likely bridge between We Care 4 U LLC and HADEF's digital infrastructure.
