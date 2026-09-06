---
profile: elephant-clipping
date: 2026-09-02
reviewer: agent:manual-artifact-hygiene
scope: wave-two-reviewed-preservation
finding_ids: [15424, 15425, 15426, 15427, 15428, 15429, 15430, 15431, 15432, 15433, 15434, 15435, 15436, 15437, 15438, 15439, 15440, 15441, 15442, 15443]
---

# Wave-two reviewed preservation

One bounded local evidence review. No new external queries, source contact or authenticated access. The five agent reports are immutable, byte-identical copies of their reviewed temporary originals. Evidence URLs and temporary provenance paths inside them are retained as originally authored; database references were not silently rewritten. Later audited corrections are recorded in the final review report, not retroactively inserted into these source reports.

## Durable files

| File | SHA-256 | Role / transformation |
|---|---|---|
| `report-agent-a.md` | `063219ba0c4233ce6f4f93d0cdefda73d438872f878d3c6fe06ff2412eb9e0fd` | Byte-identical reviewed copy |
| `report-agent-b.md` | `a5f3ad936fcd0213840b4479b69cd00705714e6065df9344049d4ae07d72b9e6` | Byte-identical reviewed copy |
| `report-agent-c.md` | `e7e145899ee187d22ac38eb8cfd041a4a6b8788a86bee570a984e80eac5b2cf1` | Byte-identical reviewed copy |
| `report-agent-e.md` | `95e2f8ea515f0d2f2c3bbaa88dce959eb690c6aebead511dff57a89619584f56` | Byte-identical reviewed copy |
| `report-bing-profile-check.md` | `cb958d5bc9f8e63a250d32bebe204ea6a4a55cd28862b466f0b1d9f2f0ffef4a` | Byte-identical reviewed copy |
| `f-ykpolitics-metadata.json` | `3edf0ef2440dbbf5206fd0df2089bc56b97f7a4e887382b39c31a20d38e405dd` | Byte-identical reviewed copy |
| `f-us_politicstoday-metadata.json` | `e28cad4bbc7200e4f9b672f56c7dafb5f1f424f7684cac500ead7dda866d6b48` | Byte-identical reviewed copy |
| `coordinator-ach-matrix.json` | `72e9a2600aa86dfc99424542fab13495a980fef3da88a82ffae0f5edc23075a2` | JSON content unchanged; one terminal newline added by apply_patch |
| `coordinator-ach-competition.json` | `2c7da1c02cbca0a986ad2b488bf7c890b7679fe52497211a96af7d3e93a23687` | JSON content unchanged; one terminal newline added by apply_patch |
| `e-search-coverage-minimized.json` | `59775ce66f53d41571f8770432157995c9d67c3bdcdafced1252dd6da9de350e` | Minimized query/status/hash fields; unrelated results and page prefixes omitted |
| `e-bing-candidate-excerpts.json` | `5c578addb8bc79ec35e152c6c8cac53ec8eaac1af6f8f10e0428746843c00058` | Two selected indexed candidate excerpts only; not primary confirmation |

## Original-to-durable mapping

| Original | Original SHA-256 | Durable copy |
|---|---|---|
| `/tmp/osint-ldT6picn/report-agent-a.md` | `063219ba0c4233ce6f4f93d0cdefda73d438872f878d3c6fe06ff2412eb9e0fd` | `report-agent-a.md` |
| `/tmp/osint-ldT6picn/report-agent-b.md` | `a5f3ad936fcd0213840b4479b69cd00705714e6065df9344049d4ae07d72b9e6` | `report-agent-b.md` |
| `/tmp/osint-ldT6picn/report-agent-c.md` | `e7e145899ee187d22ac38eb8cfd041a4a6b8788a86bee570a984e80eac5b2cf1` | `report-agent-c.md` |
| `/tmp/osint-ldT6picn/report-agent-e.md` | `95e2f8ea515f0d2f2c3bbaa88dce959eb690c6aebead511dff57a89619584f56` | `report-agent-e.md` |
| `/tmp/osint-ldT6picn/report-bing-profile-check.md` | `cb958d5bc9f8e63a250d32bebe204ea6a4a55cd28862b466f0b1d9f2f0ffef4a` | `report-bing-profile-check.md` |
| `/tmp/osint-ldT6picn/f-ykpolitics-metadata.json` | `3edf0ef2440dbbf5206fd0df2089bc56b97f7a4e887382b39c31a20d38e405dd` | `f-ykpolitics-metadata.json` |
| `/tmp/osint-ldT6picn/f-us_politicstoday-metadata.json` | `e28cad4bbc7200e4f9b672f56c7dafb5f1f424f7684cac500ead7dda866d6b48` | `f-us_politicstoday-metadata.json` |
| `/tmp/osint-ldT6picn/coordinator-ach-matrix.json` | `0e3df8850c9a0ce20e379532a72ff30af4ce88ae422d4bc6e14fd7a66c38c890` | `coordinator-ach-matrix.json` |
| `/tmp/osint-ldT6picn/coordinator-ach-competition.json` | `46cb7c0073a679bd649bd1f939643cd436ddfdca18893b7af7480812b4e5e3b8` | `coordinator-ach-competition.json` |
| `/tmp/osint-ldT6picn/e-bing-q1.json` | `31a725a583f4ad5325cb5088957d339763a7bce9d9c1ab6ab23791e9a85e1d8c` | `e-search-coverage-minimized.json` and `e-bing-candidate-excerpts.json` |
| `/tmp/osint-ldT6picn/e-bing-q2.json` | `b48ca0b5ab56cff3e718ac6603226e69a4f7930c0e70b0dd68f5dbeb6e748b58` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-bing-q3.json` | `b238eb757537a72845afedd42abf1ce439eb485b6c08a1308ec335afbe6d11ea` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-bing-q4.json` | `4b8382c409b800bea87894cd5e6155a20a0b2b0c27397f2f90b5d9272cf670d1` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-bing-q5.json` | `d163ed2de2c6daf7147ec4999a84073bdc5a1f29226ac6c4150320e983068bf5` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-q1.json` | `0a04253615a608cb703adcc41e5297d3ddb29e48658aec05fe63fe6d20118f9c` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-q2.json` | `4301d23bdd631ec44abf487761ae77ad4ba7a57128cabf7d68d04860fe24dbb9` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-q3.json` | `d3bd7a21c7789398ad522c0215555f63e94343fb6966827e67531baa788d1e7e` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-q4.json` | `6c787ba511ad317c17a89801f69c7dbc57056855a01d0c2f11fa6c2172e0f637` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-q5.json` | `90edc426eab848d0ea9c52412947fe594af28110f36130543fe0e273065983aa` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-duckduckgo-q3.json` | `0824002b89de1c80df5dd311961ad9215b27235701195c826117d0de43dc912b` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-yandex-q3.json` | `204d991dc6d06809ea68f1abe63a9696e090b23f051f1bd860889cf08e312dc9` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-bing-extra1.json` | `1951477e5e5b9a0f677c5b0e2adb6902b9d90d84c701670d4af0799b2b2fc776` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-bing-extra2.json` | `f75193354c73cd4e93af4e90f26632a8afe16fe08d75c76b0b3e3b3c7fab8403` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-extra1.json` | `cb0cb8064838881fead5542e4f51325e1c506a56994d9dcf4d81fb7824b06b3f` | `e-search-coverage-minimized.json` |
| `/tmp/osint-ldT6picn/e-brave-extra2.json` | `20d40d2209453d2aa73a27f52639b9a8f877c7c71d72bd45fcd14e3e321b11d3` | `e-search-coverage-minimized.json` |

## Minimization and limits

- F metadata preserves allowlisted public profile URLs, bio text, route-level account IDs, capture time, response status and raw-capture hashes. These are public identifiers and claims about served metadata, not credentials, legal identities, campaign enrollment or hydrated timeline verification. Raw profile HTML is not retained here.
- E preservation retains 16 issued-query records, access/challenge states, operator/rewrite notices and original/raw hashes. It preserves only the two useful Bing candidate excerpts; 119 distinct core-result destination strings and other irrelevant snippets are not mirrored. Eight unissued DuckDuckGo/Yandex matrix cells remain explicitly unqueried, with null—not zero—results. Successful status does not prove search operators were honored.
- The ACH exports contain 21 assessments over seven findings and three competing hypotheses. All seven findings are non-diagnostic. The displayed sort order is not a winner; all three hypotheses remain proposed. The export copies differ only by a terminal newline, where listed.
- No raw HTML, cookies, authorization values, signed media URLs, payment-session outputs, incidental order/bank fields, unrelated profile inventories, or incidental local-user paths were copied into this bundle. Safe stable public document/account IDs and business email mentions are not treated as secrets.
- Existing `../cloud-wave-2/` and `../distribution-wave-2/` bundles are not duplicated. Their reviewed manifests contain the underlying cloud excerpts and 11-video comparison package. Temporary-only B/C artifacts referenced by their reports remain available at their original paths; preservation here is not a promise that every raw source is durable.
- The final evidence audit had zero errors and only two intentionally missing source quotes for binary MP4 evidence in finding 15323. This is a structural audit, not universal quote/source authentication. Exact quotations in the scoped wave were separately checked against retained text/excerpts and relevant images, with corrections described in the review report.

## Related bundles

- Cloud preservation: `../cloud-wave-2/MANIFEST.md`.
- Distribution preservation: `../distribution-wave-2/d-manifest.json` (59 listed files, 11 MP4s; 56,844,547 total listed bytes at review).
- Review report: `/tmp/osint-ldT6picn/report-final-evidence-audit.md`.

