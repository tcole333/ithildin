---
profile: elephant-clipping
collector: agent:manual-cloud-artifacts
lead_ids: [94427, 94310]
thread_id: 209
capture_date: 2026-09-02
scope: unauthenticated-public-only
findings_ids: [15426, 15427, 15429, 15430, 15433]
---

# Public cloud-resource preservation — wave two

The directory contains only inert, sanitized preservation material. Nine raw HTML captures and two public thumbnails remain under `/tmp/osint-ldT6picn/`. No raw Google/Whop viewer HTML, executable scripts, credential-shaped examples, signed media URL, order/banking identifier, or incidental local user path is copied here. No executable/APK or full video was downloaded; no account, access request or community membership was used. Exact source URLs, access times, HTTP status chains, sizes and raw SHA-256 hashes are in `public-metadata.json`.

## Durable files

| File | SHA-256 | Role |
|---|---|---|
| `public-document-notes.md` | `87e707d632a9a806e0e8e71487350dc6ed1c46de3454d174fc21642a8a2952b2` | Safe exact excerpts, content/shell distinctions, provenance, sample limits |
| `challenge-library-inventory.json` | `c66d68afeae7cba8f2a24e21bf7ea76cf8849f227584f7cfc8f6aba49f524152` | Fifteen public file IDs and exact displayed filename/date/size rows |
| `public-metadata.json` | `26c7eb45b5d48795f6c6e52e1719b0b18c0bca69214b6d50d572ea66a332290f` | Stable URLs, timestamps, redirect chains, raw/thumbnail hashes and workdir paths |

These collector-authored files preserve the same primary sources; they are not independent corroboration. Each linked finding has exact source quotes, and note/inventory evidence is explicitly assessed as same-source preservation.

## Discovery chain and availability

1. Previously recovered @ogserviuos video `4xcM01EYbHs` → public **Proxy Setup Guide** `1oChEcgTy0f60w-tbG9EUH7GsuR8tPczwN30ljz9Px9A` → two disclosed published Docs:
   - **Proxy Setup For iPhone**: `2PACX-1vSyPi_ylZllIulu5BAzcf16CpaLdpiM1Wdfs1PoKXyb8geQbK3HHWabvpNAZpmbjuaysBU9AmZokwlG`, HTTP 200, actual 460-word body.
   - **Cloud Phone Guide**: `2PACX-1vSiVolBLzZ94AvMcdlBPn7VBDwzAcLscsEcKPox95QKGbGH39GeO8AIIfAv8ndlCbYcbJP7a_0lAX0k`, HTTP 200, actual 709-word body.
2. First-party YouTube descriptions → `https://cutt.ly/clipitcourse` → Whop experience `exp_BGXr0jrsEJ6k37`. HTTP 200 returned an **Experience not found** shell, not course lessons.
3. Video `Qa1FoIMKFNY`, label **Videos My Editors Made** → `https://cutt.ly/brPe8z72` → Drive folder `1OoBdneUe1FDg4x3U51R_NAekykBg6UoE`, HTTP 404. No contents recovered.
4. Video `wozS5wpIdPw`, challenge-resource description → `https://cutt.ly/mrg0EboV` → live folder **10 Clipping Videos (24hr challenge)** `1gkKBLN5aLI2GDohDTCKxk8BU-JaKf9qV` → two public subfolders: `1NA6J-fflQ1vHNfsZnF-Fsi3UjxcYpNdL` and `1KL61dbJi6cCqc8qmGI92ihUrZ7hmKo2X` → ten edited MP4 entries plus five editing recordings.

The folder rows display modification dates in March/April 2025. Those are not publication or authorship dates. Two sampled file viewers display **Serviuos** / **biz@serviuos.com**, which identifies the business persona, not a legal person. The sampled edited preview shows a podcast/microphone shot captioned **Poker**; the recording preview shows Premiere/Bandicam. Only two previews were reviewed; no conclusion about every frame or all fifteen files is warranted.

## Search and archive audit

- Nine exact document/shortlink/folder/experience/filename queries returned empty unified-web results. Three title/referrer queries returned no relevant copy (the broad library-title query produced unrelated results). `a-web-exact-initial.json`, `a-web-exact-shortlinks.json`, `a-web-exact-new-selectors.json`, and `a-web-title-referrers.json` preserve the tool outputs.
- Six exact Wayback timelines returned `total_snapshots: 0`: both guide URLs, the three named shortlinks, and unavailable folder `1OoBdneUe1FDg4x3U51R_NAekykBg6UoE`. Each output is `/tmp/osint-ldT6picn/a-wayback-<name>.json`. The live challenge-folder timeline timed out after 55 seconds; no zero is asserted.
- Seven exact URLScan searches (`page.url:"<known URL>"`, limit 100) returned zero public scan records: both guides, three shortlinks, unavailable folder and live challenge folder. Outputs `/tmp/osint-ldT6picn/a-urlscan-<name>.json`.
- New campaign-share web search returned generic MonsterLab root/ClipIt pages, not a campaign row. Twelve preserved YouTube descriptions contain no concrete MonsterLab `/campaign/`, `/c/` or `/share/` URL.
- New Wayback `/share/campaign/*` lookup failed HTTP 429; campaign-focused URLScan search failed HTTP 403. No service key was configured for URLScan. Neither failure is a negative search. Exact commands are preserved in `/tmp/osint-ldT6picn/a-campaign-history-errors.json`, SHA-256 `390645d66baebb7a451362bc7bb088ad4908465f73f5201d9fd02024ca242b46`.
- Reused same-day wave-one: `/campaign/*` and `/c/*` CDX negatives; broad-domain CDX inventory; single public URLScan `/clipit?ref=serviuos` result; public route/client schema; twelve YouTube description captures; archived channel descriptions; article-media review; exact political-brief/cloud queries. Reuse prevents meaningless repeated negatives.

Repository commands used `--output /tmp/osint-ldT6picn/a-*.json`; direct HTTP captures are indexed in `public-metadata.json`. `a-history-coverage.json` is the task-run log; its Wayback `count: null` fields reflect an initial parser expecting a different count key, while the underlying outputs correctly say `total_snapshots: 0` and are the authority. Papercuts 2508 (bounded history timeout) and 2516 (misleading URLScan search-403 message) were logged, not silently worked around.

## Unresolved scope

No campaign-specific public row, owner-generated campaign-share token, political source-video folder, ledger, account-to-campaign mapping or authenticated payout was recovered. The guides document general commercial tooling, not account-specific deployment. Both leads remain `in_progress`; access-limited content and broader recovery are not marked solved. Cross-lane comparison of partial show branding in one thumbnail is left to coordinator verification and does not establish funding or source delivery.
