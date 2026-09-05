---
status: partial
lead_id: 93829
lead_status: in_progress
profile: elephant-clipping
thread_id: 209
findings_ids: [15400, 15401, 15402, 15403, 15404, 15416, 15417, 15419]
findings_count: 8
entities:
  - {id: 7099, name: "Elephant clipping campaign"}
  - {id: 7032, name: "YouTube account @ogserviuos"}
  - {id: 7047, name: "ClipIt"}
  - {id: 7046, name: "Monster Lab"}
connections: []
leads_spawned:
  - {id: 94427, title: "Resolve and preserve remaining ClipIt public resource links and guide documents"}
  - {id: 94429, title: "Preserve and compare three additional synchronized political Instagram reels"}
collector: agent:manual-cloud-artifacts
completed_utc: 2026-09-02
---

# Public cloud-artifact recovery — wave 1

## Outcome

The bounded pass recovered new public operational artifacts rather than a campaign-source folder. The most important new identity result is a public Google Drive video page, directly linked by @ogserviuos, that names the uploader **Serviuos** and exposes **biz@serviuos.com**. Two first-party YouTube descriptions led to live public Google documents, a sixteen-file Drive folder, and the current ClipIt Discord guild. None of these artifacts mentions Elephant Clipping, Enclave & Key, Steve Wynn, Jules Katz, Benjamin Goodman, Jack O’Hara, the `US Politics Clipping` campaign, or the political campaign brief. They are nevertheless useful additions because they independently document ClipIt/Serviuos’s operational resource stack and provide stable identifiers for future attribution.

The campaign-specific recovery question is not resolved. Lead 93829 therefore remains `in_progress`; the remaining public-document work is separated into lead 94427.

## Discoveries

### 1. The full campaign brief and workflow residue survive in public Instagram metadata

Unauthenticated HTML for `@frontrawpolitics` reel `Dbnq4gyOiWL` preserves the complete 258-word campaign-goal text in `og:title`. The platform metadata labels the post Aug. 4, 2026 and exposes owner ID `48655803582` and media ID `3956319399114843531`. The durable exact-text capture is `instagram-Dbnq4gyOiWL-og-title.txt`, SHA-256 `432e448c38ef1fa2432b02b1ce7d824ae617ffd29ac8407ac0ad359060cc7be8` (finding 15400).

Unauthenticated metadata for `@_politicalhub` reel `Db3A92YSgyG` repeats the brief and then appends an apparent work instruction asking whether the video aligns with the campaign goal, requesting a yes/no explanation, and beginning a request for titles before the public field truncates. The platform labels the post Aug. 10, 2026 and exposes owner ID `42172798083` and media ID `3960638647573286022`. This is evidence that production-workflow text leaked into public post metadata; it does not establish which software generated it. The durable exact-text capture is `instagram-Db3A92YSgyG-og-title.txt`, SHA-256 `3faefb1b5e9839d54fb8b44ec7cb777e54f1e6f7676745908a0052d4b9a749ad` (finding 15401).

### 2. A first-party channel links a live ClipIt-branded published Google Doc

The public description of @ogserviuos video `S81meXbQ-OY` lists:

- ClipIt: `https://monsterlab.io/serviuos`
- Free Discord: `https://discord.gg/clipit`
- “TikTok MOD APK Tutorial”: `https://cutt.ly/3tEwIxmA`
- Proxy marketplace: `https://monsterlab.io`

On 2026-09-02, the short link returned HTTP 301 to:

`https://docs.google.com/document/d/e/2PACX-1vREv_tUVDbPJTNVhj7GMTduPdOz6Eo8Bz7CVzRELiMfmZgHJtPRuQRtvoL0hYsYsWwqcUfVJqZ82CWS/pub`

The published title is **TikTok Mod Tutorial [ClipIt]**. Its text directs readers to a public Telegram distribution channel, tells them to obtain a mod and plugin, and instructs them to set the plugin region to USA. Six embedded images were downloaded and hashed. No uploader/author name, email, Drive file ID, payment instruction, legal term, campaign ID, or political-campaign text is present. No APK was downloaded and no Telegram group was joined. Findings 15402 and 15403 preserve the first-party chain and the document’s direct text.

### 3. A current @ogserviuos video exposes a public uploader email and proxy-resource stack

The current public description of @ogserviuos video `4xcM01EYbHs` links:

- `https://drive.google.com/file/d/1Kso6rVzFlc3w9j9wGDOfLyo_ess6O-m9/view`
- `https://docs.google.com/document/d/1oChEcgTy0f60w-tbG9EUH7GsuR8tPczwN30ljz9Px9A/pub`

The Drive page identifies the file as `proxy tutorial all apps.mp4`, MIME `video/mp4`, with reported size `360486220` bytes. Its unauthenticated serialized metadata includes display owner/uploader `Serviuos` and email `biz@serviuos.com`. The viewer HTML was captured at 2026-09-02T15:21:44Z and hashed as `8cf0657adb5674934fddd3017de08b4e06cda35ffa0193a0351f43a6904f7073`. The 360 MB media itself was not downloaded, and the raw page was not committed because it contains transient viewer nonces/API material. Stable fields are recorded in the sanitized manifest (finding 15416).

The adjacent public **Proxy Setup Guide** refers to proxy host `p.monsterlab.io`, displays the application username `aiprofit@monsterlab.io`, links download host `dl.monsterlab.io`, Wistia media ID `k8f4syvm0j`, and Discord direct-user ID `1245055580331180062` displayed as `@maxaiprofit`. It also discloses two further published Google-Doc IDs:

- iPhone guide: `2PACX-1vSyPi_ylZllIulu5BAzcf16CpaLdpiM1Wdfs1PoKXyb8geQbK3HHWabvpNAZpmbjuaysBU9AmZokwlG`
- cloud-phone guide: `2PACX-1vSiVolBLzZ94AvMcdlBPn7VBDwzAcLscsEcKPox95QKGbGH39GeO8AIIfAv8ndlCbYcbJP7a_0lAX0k`

Those two linked guides were not fetched after the wave stop; they are explicitly assigned to follow-up lead 94427. A public password and dummy proxy credential shown in the source were not duplicated into findings, manifests, or this report. The direct infrastructure disclosure is finding 15417.

### 4. An archived first-party resource link still opens a sixteen-file Drive folder

The Wayback snapshot of `https://www.youtube.com/@ogserviuos/` at `20240917211557` labels `https://cutt.ly/DeR8T6o0` as a “BONUS TikTok Page Analytics & Resources folder.” On 2026-09-02 it resolved to:

`https://drive.google.com/drive/folders/1pzCgNcXE9TKL9O66FV8Qprz7ca9IHLup?usp=sharing`

Public Drive metadata titles the folder **Roadmanhut Screenshots**, serializes creation at 2024-09-13T13:27:51Z and modification at 2024-09-14T17:29:31Z, and lists sixteen PNG files. Every downloaded image is 1080×2160 and visibly watermarked `@SERVIUOS`. Files `1.png`–`9.png` show TikTok video analytics; files `10.png`–`14.png` show creator rewards. `withdraw 1st.png` displays a £1,172.94 withdrawal, a masked bank suffix, and an order identifier. `withdraw received.png` displays `PIPO Europe Limited +1,172.94 GBP` on Aug. 30, 2024 and `PIPO Europe Limited +250.47 GBP` on Aug. 6, 2024. These are self-published screenshots, not independently authenticated transactions (finding 15404).

Key item IDs:

| Filename | Public Drive file ID | SHA-256 |
|---|---|---|
| `1.png` | `143NCbcazVJAHs1pD-3XxzGPwz8F11AtT` | `3dbf4db05b01b0e76d543cc425031819f7017bfaad207a1b7d778a43e97e7c0a` |
| `2.png` | `1doRj6RPeIVZk8vqfHefZfKqkv2p8GX35` | `9e8a3875776eb38917db8e366dd80303efd63aefdbc40381d3784d66baf64f5d` |
| `3.png` | `1uVdD6wZhlTA5kqphD3x_gBD59pdnVZIm` | `208c184948b6f4d7853c9d55c64afea653cf2aa92e1be4fcb2cdb70dbd418737` |
| `4.png` | `1_IyHS6e9lp6SGyFbWKFI9zBT93-aEGyJ` | `bc9e08a2528a2e948430d48d7241efd5f7a77b0bca3fc6a67337c0a9e88fbb4b` |
| `5.png` | `10g0GNDhSF-OEjG18ojfMxHetz4ogRkt-` | `41b6886c33d5cb74cd869c5b8e07bf89932bce6665dc0b4efb4e7a11e41ad927` |
| `6.png` | `13IWdwves9nAkfiAOrqH7ZiC9Z3kh2HNv` | `09cf439683e7371420a586b5516474c07de135db5ddcf4d4d6696b160ec1fa1c` |
| `7.png` | `1kgeovFHgz-oxv_8jUkS_c4fNWHlcCyvS` | `213c130441d4e13d69652b1bca5e871896fb928c8fcde0d2dbdc6112b5cbd7ba` |
| `8.png` | `1DefPngDL2UawLBzk3dRhYjvD1868rQq8` | `b5b627502a5492e46edb81daab8b58674b5c451125e9af93f92d23b8d4e5d41e` |
| `9.png` | `1p2IMt5OQpcGD9YLuWHMrYpzy3kt7bvnc` | `553c4a9515e1611c6ea51efb07aa8d582ab361a1697a8627b09987415ad2918b` |
| `10.png` | `1Gf3paadgBc1k08VjCad1_Osu9HRU6OsL` | `e83e99aee898e008537614dd76fad93ff27faca0e4b639e32237fbf7f6c10531` |
| `11.png` | `1Yz5EX-GZIvnRkgoVJl6aCvvv-GhIlbJP` | `6c3d9a9ee9d2f33e53c9718c29dd17a3cf02b7b410cd9f657c8683e0ca25be4c` |
| `12.png` | `1CWSkPvD6uWcMga1NF3hTb4zrXFbzWo2X` | `76b84b5bd85e4545db838aa85c558c922a77a8b625099cc41cef46ff4cf3c7d8` |
| `13.png` | `1OKj7EWJv_duYqgfulN2upoX7gpq9qa2n` | `81958c3ee1efd95f3395b6cf40728c9bf10fe16f913d12407f6d22248aa1d402` |
| `14.png` | `1KzIy83UuPPN9m0XX3Ltn17MEYPH8Nzk2` | `71b8922c1f32ed050058a44758b95b8ea9fda179f414d2bcfe8f8901df44026e` |
| `withdraw 1st.png` | `1jaE5-iIA7uOuOl6IncbFlLabrNDjRRp0` | `ad039b5803b6f3f8427b709dc588aa79aecda446bd00f247886df185d7bc4f53` |
| `withdraw received.png` | `1BI1nkOoXMyQpshw8_b5diryAIGjonzbO` | `2ca8fa127f23052453223125e6d87257258f1f59d2571ff9c990b7c95e28ca9d` |

### 5. ClipIt’s public Discord guild is independently identifiable

At 2026-09-02T14:53:39Z, the unauthenticated invite API for `https://discord.gg/clipit` returned:

- actual guild ID `1238662138864599172`
- top-level invite object ID `1440580416800034937`
- rules-channel ID `1539465398930514000`
- public profile counts of 39,157 members and 3,223 online
- guild tag `CLIP`, 55 boosts, tier 3
- description advertising paid clipping work with creators and brands

The official public Discovery page is `https://discord.com/servers/clipit-1238662138864599172` and labels the server as created May 11, 2024. No server was joined and no non-public message was accessed. Finding 15419 records the point-in-time public response. The top-level invite ID was initially mistaken in working notes for the guild ID; the JSON was re-read, corrected immediately, and only the corrected IDs were persisted.

### 6. Synchronized-post preservation assistance

For the distribution-network agent, two public Instagram media assets were preserved and compared:

| Reel | Owner ID | Media ID | Derived media-ID time | Asset ID | Video SHA-256 |
|---|---:|---:|---|---:|---|
| `_politicalhub/Dcg3GEFhIaG` | `42172798083` | `3972417180603287174` | 2026-08-26T18:30:51.620Z | `1371082288472414` | `10305548ae619b14a675f7384308c8f85b0e138ded955550c8e39db59ded0f49` |
| `lonealphapolitics/Dcg3HQQTea6` | `12643806887` | `3972417262388635322` | 2026-08-26T18:31:01.369Z | `2138893426981722` | `5c1219d036cde98766dd2dd8598c8d1ea8bff4d0d57c007e7039b49b4bf449d7` |

The timestamps are derived from Instagram media IDs, not explicit `taken_at` fields. They are 9.749 seconds apart. The encodes are not byte-identical, but aligned full-video SSIM is `0.993332` and aligned audio PSNR is `173.988 dB` per channel, supporting effectively the same audiovisual source. The distribution-network agent owns the coordinated-post finding (their finding 15323); this report owns only retrieval/preservation metadata.

## Artifacts preserved

Durable manifest: `investigations/elephant-clipping/artifacts/2026-09-02/cloud-artifacts/MANIFEST.md`

Durable captured artifacts and hashes:

| Artifact | SHA-256 |
|---|---|
| TikTok tutorial raw capture (workdir only; inert notes retained) | `cc76feb184d30cfae5af2283b41ccb8711a45fb98209fa0a62084a7e5e69b404` |
| `clipit-tiktok-mod-embedded-02.png` | `03a4e8c74fe0cadb96c56a8d0c451901dba9b8125dcd7a96f8216a8bf5d9637a` |
| `clipit-tiktok-mod-embedded-03.png` | `a2eab5995fad7dc496f0ebd026b4f86175a8bd28ee60553d83acc6f6173ebe52` |
| Proxy Setup Guide raw capture (workdir only; credential-shaped values excluded from the durable tree) | `1a3f92a890584f27b2d0ee125a43c50aa171b193982fb6590c25edb85c6e8cf1` |
| `discord-invite-clipit.json` | `2418376590f210d46e7cce3cdbee3d3d85d57b712668641c0abfaae3c6ece68d` |
| Roadmanhut withdrawal screenshot (workdir only) | `ad039b5803b6f3f8427b709dc588aa79aecda446bd00f247886df185d7bc4f53` |
| Roadmanhut received screenshot (workdir only) | `2ca8fa127f23052453223125e6d87257258f1f59d2571ff9c990b7c95e28ca9d` |
| `instagram-Dbnq4gyOiWL-og-title.txt` | `432e448c38ef1fa2432b02b1ce7d824ae617ffd29ac8407ac0ad359060cc7be8` |
| `instagram-Db3A92YSgyG-og-title.txt` | `3faefb1b5e9839d54fb8b44ec7cb777e54f1e6f7676745908a0052d4b9a749ad` |
| `public-metadata.json` | `4968d06905415e64672b834676488268e96827aa599fa19482d73df22a410aeb` |
| `public-document-notes.md` | `2cb1fb9bebcf2fe08c7f90c8c27f9d510906feade457619308880a45e1a1fe2d` |
| `roadmanhut-inventory.json` | `be5747a3a43a4cb6f2dfd1bce9d40a75be5e644de914c60d31ce0b69284db9cc` |

Raw Instagram pages, Drive viewer/folder pages, the two published Google-Doc HTML captures, and payment screenshots remain workdir-only because they contain transient signed URLs, cookies/CSRF values, nonces/API material, opaque Google principal identifiers, credential-shaped values, or incidental payment identifiers. Exact workdir paths and raw hashes are recorded in the durable manifest. Inert summaries and non-sensitive selectors are preserved in `public-document-notes.md` and `public-metadata.json`.

Atlantic media preserved in the workdir:

- `cloud-clippersSPOTSSmaller.gif`, SHA-256 `60f471c89da8bb2eb80755302f785dcdc24d5422759c88d809ad3eda6c7f17bf`
- `cloud-clippersSPOTS1_2.mp4`, SHA-256 `f232f1239f4db8fa7e2d4a0fcdb2e503624d89a2c8b5b14f93a6c684accdd038`
- `cloud-clippersSPOTS3.mp4`, SHA-256 `3c13c3fc88807b52cb005aad5104edbeef0a06de23f45e4acbf2710336da79bb`

All 332 frames were reviewed through extracted frames/contact sheets. They show editorially stylized example clips and generic phone/money imagery; no Drive/Docs/Discord URL, document ID, folder name, campaign code, or operational UI identifier is visible.

## Negative results and exact scope

All search families below were run on 2026-09-02 and logged in `search_log`.

- Exact searches for all four seed Instagram shortcodes (`Db3A92YSgyG`, `Dbnq4gyOiWL`, `DCBMjPmAoTi`, `DF_ZJ86v81H`) returned no independently indexed public source.
- Exact searches for `servtheclipper`, `clippersSPOTSSmaller`, `clippersSPOTS1_2`, and `clippersSPOTS3` returned no cloud-document identifiers or relevant public copies.
- Exact campaign-text searches using the distinctive opening sentence, the “serious, informative, and argument-driven” line, and `Goal of the Campaign` plus `social welfare advocacy`, combined with `site:drive.google.com`, `site:docs.google.com`, and `site:cdn.discordapp.com`, found no verified independent campaign document.
- `Jules Katz`, `Benjamin Goodman`, `Jack O Hara`, and `Enclave & Key` plus `site:drive.google.com` produced no relevant Drive item.
- Exact searches for Whop selectors `biz_MTuyZYomLpS6Hu`, `user_dWDlSFuNxFzH8`, `prod_vnUWCsIkdB0PT`, `biz_Obii9qxYQC2vk4`, and `clipitnew` produced no indexed cloud document.
- `site:drive.google.com` / `site:docs.google.com` searches for `ogserviuos` and `monsterlab.io` returned no indexed results. The artifacts in this report were found through first-party outbound links, demonstrating the index gap.
- `site:cdn.discordapp.com` searches for `clipit` and `monsterlab.io` returned no verified public CDN artifact.
- Exact `Elephant Clipping` searches on Notion, Dropbox, and OneDrive, plus `US Politics Clipping` on Notion, returned zero. `ClipIt` + `serviuos` on those platforms, `monsterlab.io` on Notion, and `ClipIt` on Google Forms likewise returned zero.
- Exact searches for the recovered Doc/folder/order/short-link IDs returned no independent indexed copies.
- Live and archived Whop page source for `whop.com/clipitnew/` contained no Drive, Docs, Forms, Discord-CDN, Dropbox, OneDrive, or Notion URL.
- Wayback reported zero captures for the ClipIt TikTok-mod published Doc and for `cutt.ly/3tEwIxmA`; the absence is archive coverage, not proof the pages did not exist earlier.

## Wayback/CDX coverage

Repository `query_wayback.py` commands wrote every result under `/tmp/osint-E6iGgeNz/cloud-wayback-*.json`.

| Target | Captures | First | Last |
|---|---:|---|---|
| ClipIt TikTok-mod published Doc | 0 | — | — |
| `https://cutt.ly/3tEwIxmA` | 0 | — | — |
| `https://www.youtube.com/@ogserviuos/` | 4 | 2024-05-22 | 2026-06-22 |
| `https://discord.gg/clipit` | 2 redirects | 2025-04-19 | 2026-07-12 |
| `https://whop.com/clipitnew/` | 2 | 2025-10-27 | 2026-01-13 |

The 2024 and 2026 YouTube snapshots and both Whop snapshots were fetched and searched for cloud/referrer URLs. The 2024 YouTube snapshot was the source of the live Roadmanhut folder. Its sibling short links currently resolve as follows: `PeREOoML` → Vsub with `linkId=lp_382606`, `sourceId=serviuos`, `tenantId=vsub`; `MeREPfia` → public Discord invite `aiprofit`; `reREAwlP` → `aiprofitmarketplace.com` (DNS resolution failed after the redirect); `eeREOPJx` → 404.

## Sources and commands

- Direct public HTTP capture with `curl -L`, response headers, access times, and SHA-256 hashes.
- Instagram canonical/OG metadata and public embed source; tokenized signed CDN URLs were used only for lawful media capture and then excluded from durable metadata.
- Discord unauthenticated invite API and official Discovery page.
- Google published-Doc HTML, Drive folder HTML, Drive viewer HTML, and direct public Drive downloads.
- YouTube current watch pages for twelve videos on canonical channel `UCtnBA-3CRpSSg4uPwRtqoOw`, plus two archived channel snapshots.
- `uv run python tools/query_wayback.py {timeline,snapshots,fetch}` with `--output /tmp/osint-E6iGgeNz/cloud-*.json`.
- Web exact-string/site-restricted searches, each checked against and then written to `search_log`.
- `ffprobe` for codec/duration metadata; `ffmpeg` SSIM and audio PSNR for the synchronized pair; frame extraction/contact sheets for Atlantic media.
- `shasum -a 256` for all preserved artifacts.

## Contradictions and cautions

- The Discord invite JSON’s top-level `id` is an invite object ID, not the guild ID. The correct guild ID is nested as `guild.id` / `guild_id`: `1238662138864599172`. The mistaken working interpretation was corrected before persistence.
- Instagram media-ID times are derived using the platform’s snowflake-style ID relationship. They are not direct `taken_at` values and are labeled as derived everywhere.
- The Roadmanhut financial screens are self-published and watermarked. They support statements about what is displayed and its first-party-linked provenance, not independent proof of payment or ownership of the receiving account.
- The recovered operational resources predate or are broader than the 2026 political campaign. They establish infrastructure and public identity selectors but do not by themselves tie the tutorial, Drive folder, or 2024 earnings to Elephant Clipping or Enclave & Key.
- The Atlantic alone was treated as secondary intake, not corroboration. The new findings rely on first-party/public platform evidence and archive captures.

## Source gaps

- No campaign-specific Google Drive folder, source-video folder, payment sheet, contractor roster, Discord message, or campaign document was recovered.
- The published Google Docs do not expose an author/uploader display name. Uploader identity was recovered only from the linked Drive video page.
- No non-public Discord content was accessed; message-level campaign searches remain out of scope without a public index/archive.
- Search engines incompletely index Drive/Docs and CDN URLs. Exact negative results are bounded to the query families above.
- The large public proxy video was not downloaded; its viewer metadata and hash were preserved instead.
- Three newly surfaced political Instagram reels were not captured after the wave stop; they are lead 94429.

## Follow-up leads

- **94427 — Resolve and preserve remaining ClipIt public resource links and guide documents.** Resolve current first-party short links `cutt.ly/clipitcourse`, `cutt.ly/brPe8z72`, and `cutt.ly/mrg0EboV`; preserve the two disclosed published guide IDs; perform bounded exact-ID/referrer/Wayback searches. Public unauthenticated access only; no executable/APK download and no credential reproduction.
- **94429 — Preserve and compare three additional synchronized political Instagram reels.** Capture sanitized metadata and media for `Dcg245KTBBp`, `Dchbt_aS0dF`, and `DcfbnTrMnBs`; compare timing/hashes/SSIM/audio against the Dcg3 pair.

## Learnings

- Archived first-party descriptions were more productive than search-engine indexing: a 2024 YouTube snapshot yielded a still-live Drive folder that exact Drive searches missed.
- Current YouTube descriptions exposed stable Drive/Doc IDs and an uploader email absent from the public channel profile and Whop page.
- Volatile platform pages should be captured immediately, then reduced to sanitized durable metadata so signed URLs and session material are not propagated.
- Exact quotes and source-chain labels are essential here: a public artifact can establish what ClipIt/Serviuos published without authenticating the earnings, proving legal ownership, or tying the resource to the political campaign.
