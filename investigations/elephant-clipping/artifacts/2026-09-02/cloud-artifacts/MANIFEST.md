---
profile: elephant-clipping
lead_id: 93829
thread_id: 209
captured_utc: 2026-09-02
collector: agent:manual-cloud-artifacts
scope: unauthenticated-public-only
---

# Cloud-artifact preservation manifest

This directory preserves public, unauthenticated evidence recovered during the first investigation wave. No access request was made; no account was used; no Discord or Telegram community was joined; and no executable, APK, or private file was downloaded. Public passwords, transient signed URLs, cookies, CSRF values, API nonces, and unrelated opaque account identifiers are deliberately excluded from the sanitized metadata.

## Discovery chains

1. The public description of @ogserviuos video `S81meXbQ-OY` linked `https://cutt.ly/3tEwIxmA`, labeled as a TikTok MOD APK tutorial. On 2026-09-02 the short link returned HTTP 301 to the published Google Doc `2PACX-1vREv_tUVDbPJTNVhj7GMTduPdOz6Eo8Bz7CVzRELiMfmZgHJtPRuQRtvoL0hYsYsWwqcUfVJqZ82CWS`, titled **TikTok Mod Tutorial [ClipIt]**.
2. A Wayback snapshot of @ogserviuos dated 2024-09-17 labeled `https://cutt.ly/DeR8T6o0` as a “BONUS TikTok Page Analytics & Resources folder.” On 2026-09-02 it resolved to public Drive folder `1pzCgNcXE9TKL9O66FV8Qprz7ca9IHLup`, titled **Roadmanhut Screenshots**.
3. The current public description of @ogserviuos video `4xcM01EYbHs` directly linked public Drive file `1Kso6rVzFlc3w9j9wGDOfLyo_ess6O-m9` and public Google Doc `1oChEcgTy0f60w-tbG9EUH7GsuR8tPczwN30ljz9Px9A`. The file page identifies the file as `proxy tutorial all apps.mp4`, displays owner `Serviuos`, and exposes uploader email `biz@serviuos.com`. The adjacent Doc is titled **Proxy Setup Guide** and references MonsterLab infrastructure.
4. The same YouTube description linked the public vanity invite `https://discord.gg/clipit`. Discord's unauthenticated invite API identifies ClipIt guild `1238662138864599172`; top-level invite object `1440580416800034937`; rules channel `1539465398930514000`. The public Discovery page is `https://discord.com/servers/clipit-1238662138864599172`.

## Durable files

| File | SHA-256 | Purpose |
|---|---|---|
| `clipit-tiktok-mod-embedded-02.png` | `03a4e8c74fe0cadb96c56a8d0c451901dba9b8125dcd7a96f8216a8bf5d9637a` | Public embedded tutorial image |
| `clipit-tiktok-mod-embedded-03.png` | `a2eab5995fad7dc496f0ebd026b4f86175a8bd28ee60553d83acc6f6173ebe52` | Public embedded tutorial image |
| `discord-invite-clipit.json` | `2418376590f210d46e7cce3cdbee3d3d85d57b712668641c0abfaae3c6ece68d` | Public invite API response |
| `instagram-Dbnq4gyOiWL-og-title.txt` | `432e448c38ef1fa2432b02b1ce7d824ae617ffd29ac8407ac0ad359060cc7be8` | Exact public Instagram metadata text containing the 258-word brief |
| `instagram-Db3A92YSgyG-og-title.txt` | `3faefb1b5e9839d54fb8b44ec7cb777e54f1e6f7676745908a0052d4b9a749ad` | Exact public metadata text containing workflow residue |
| `public-metadata.json` | `4968d06905415e64672b834676488268e96827aa599fa19482d73df22a410aeb` | Sanitized identifiers, provenance, and video-comparison metrics |
| `public-document-notes.md` | `2cb1fb9bebcf2fe08c7f90c8c27f9d510906feade457619308880a45e1a1fe2d` | Inert public-document and payment-screen evidence notes |
| `roadmanhut-inventory.json` | `be5747a3a43a4cb6f2dfd1bce9d40a75be5e644de914c60d31ce0b69284db9cc` | Sixteen public file IDs, filenames, dates, displayed sizes, and content hashes |

## Public folder contents and displayed financial fields

The Drive folder lists sixteen PNG files, each modified September 14, 2024. All downloaded images are 1080×2160 PNGs and visibly carry a diagonal `@SERVIUOS` watermark. Files `1.png` through `9.png` show TikTok video analytics; `10.png` through `14.png` show creator-reward details. The two workdir-only withdrawal images display a £1,172.94 withdrawal and a matching `PIPO Europe Limited +1,172.94 GBP` entry, along with a separate `PIPO Europe Limited +250.47 GBP` entry. These are self-published screenshots; preservation confirms what the images display, not the authenticity of the underlying transactions. A masked bank suffix and order identifier remain visible in the source image but are not repeated here or duplicated in the durable tree.

## Sanitization and workdir-only captures

- Raw Instagram and embed HTML stays only in `/tmp/osint-E6iGgeNz/` because it contains transient signed media URLs, cookies, or CSRF material. `public-metadata.json` and the two exact `og:title` text files preserve the stable evidence.
- Raw TikTok tutorial HTML stays only at `/tmp/osint-E6iGgeNz/cloud-doc-tiktok-mod.html` because it contains executable Google scripts, CSP nonces, and opaque image-resource URLs. Its raw SHA-256 is `cc76feb184d30cfae5af2283b41ccb8711a45fb98209fa0a62084a7e5e69b404`; inert evidence notes are preserved in `public-document-notes.md`.
- The raw Drive folder page stays only at `/tmp/osint-E6iGgeNz/cloud-drive-1pzCgNcXE9TKL9O66FV8Qprz7ca9IHLup.html` (SHA-256 `f5a323a5996392f4c15db621677ac2ecd5a4d83d4b924384204acb7d068cca2f`) because it includes transient nonces, API keys, and opaque Google principal IDs.
- The raw Drive video page stays only at `/tmp/osint-E6iGgeNz/cloud-drive-file-1Kso6rVz.html` (SHA-256 `8cf0657adb5674934fddd3017de08b4e06cda35ffa0193a0351f43a6904f7073`) for the same reason. The advertised 360,486,220-byte video was not downloaded; its public stable metadata is preserved in `public-metadata.json`.
- The raw Proxy Setup Guide stays only in `/tmp/osint-E6iGgeNz/` because the published page contains a public password and credential-shaped examples that should not be propagated. Its source URL, stable document ID, non-sensitive selectors, and raw SHA-256 `1a3f92a890584f27b2d0ee125a43c50aa171b193982fb6590c25edb85c6e8cf1` are preserved in `public-metadata.json` and this manifest.
- The full sixteen-file public folder capture remains in `/tmp/osint-E6iGgeNz/cloud-drive-roadmanhut/`; every content hash is recorded in `roadmanhut-inventory.json`. Payment images are not duplicated in the durable tree because they contain incidental payment/order and masked-bank fields; `public-document-notes.md` preserves their relevant content and hashes.
- The two synchronized public Instagram media captures remain workdir-only: `Dcg3GEFhIaG` SHA-256 `10305548ae619b14a675f7384308c8f85b0e138ded955550c8e39db59ded0f49`; `Dcg3HQQTea6` SHA-256 `5c1219d036cde98766dd2dd8598c8d1ea8bff4d0d57c007e7039b49b4bf449d7`. Signed CDN URLs are intentionally omitted.

## Atlantic media preservation

The article-hosted media were downloaded and reviewed frame-by-frame in the workdir. No public cloud URL, document ID, Discord identifier, folder name, or operational UI label was visible.

- `cloud-clippersSPOTSSmaller.gif`: SHA-256 `60f471c89da8bb2eb80755302f785dcdc24d5422759c88d809ad3eda6c7f17bf`
- `cloud-clippersSPOTS1_2.mp4`: SHA-256 `f232f1239f4db8fa7e2d4a0fcdb2e503624d89a2c8b5b14f93a6c684accdd038`
- `cloud-clippersSPOTS3.mp4`: SHA-256 `3c13c3fc88807b52cb005aad5104edbeef0a06de23f45e4acbf2710336da79bb`

## Archive coverage

Wayback CDX returned zero captures for the ClipIt TikTok-mod Doc and its `3tEwIxmA` short link; four captures for `@ogserviuos` (2024-05-22 through 2026-06-22); two redirect captures for `discord.gg/clipit` (2025-04-19 and 2026-07-12); and two captures for `whop.com/clipitnew/` (2025-10-27 and 2026-01-13). Snapshot-list and fetch JSON files remain in the workdir under the `cloud-wayback-*` prefix.
