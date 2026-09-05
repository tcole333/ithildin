---
profile: elephant-clipping
collector: agent:wave3_provenance
lead_ids: [94994, 94826]
finding_ids: [15455, 15456]
capture_date: 2026-09-02
scope: public-unauthenticated-only
---

# Campaign-file provenance: wave three preservation

The public source-packet/uploader bridge remains unresolved. This bundle
preserves five sparse CPT content-hub captures and a general-training video
sample, not the political campaign folders described by the Atlantic.

| File | SHA-256 | Role |
|---|---|---|
| `VIDPODCASTSERV1.mp4` | `ec293cafebdee849d9e69c957c4d8c164140b5b71dba75d70345482ebd32c81c` | Original public 128,113,981-byte training MP4; 25.983333 seconds |
| `caption-strip-corrected.jpg` | `af9f10ed8246796e55088790d7a5bdccdf67e20bb1233d49114a1db7daeb0f5f` | Four-per-second caption crops; row-major chronological order |
| `sample-captions.jpg` | `a1cc0d2e58c4e05f37b456c2a8998b7962037335e99e15fee879c0fdd353feeb` | One-per-second visual frames; black final tiles are padding |
| `content-hub-reviewed.json` | `432852ae01ea0e94b69d92965982d42fbe6847ddb61b3f30f95687fa83df26cd` | Inert text, hrefs, archive times, retrieval times and source hashes for all five captures |
| `episode-metadata.json` | `72086b23a9db38b0d6bc3d49e669b81d18109b5550550735150387c28df7c797` | Selected primary YouTube metadata for candidate episode 4uYmzucv4WQ |
| `reviewed-notes.md` | `cf7fcc624748b4ed2c8d21cb38e1c8284773415b6d52b0227a59e8de588dd1c1` | Classification, exact short quotations and limits |
| `sample-download-metadata.json` | `55142f4292acb3d0414fbfa37204d9a2265cdc34e549f9f882ac833d5155eaa8` | Stable public download provenance, time, status and hash |
| `search-coverage-reviewed.json` | `72b75ca33ee94890328302b70949dc3b22faff7989f45a72401f9a66ad7054b3` | Allowlisted Bing, Brave and Mojeek coverage metadata only; no result payloads; effective queries unknown |
| `media-access-observations.json` | `397c15dcee638053263ee08d808bd120d83a8bfa07975eec35c93de881dd084b` | Collector transcription of caption/audio status stdout, plus empty-file hashes and times; not raw HTTP headers |

Source chains and sparse snapshot timestamps are in `reviewed-notes.md` and the
JSON records. Collector-authored files preserve the same underlying sources;
they are not independent corroboration. Captions are sampled visual words,
not a validated complete transcript. The September 2024 episode is a specific
candidate selected by programme/text clues, not an exact source match or
person identification from a face. No supply, licensing, ownership, payment or
political-use relationship is established.

The caption/audio status record was transcribed from tool stdout from this
same research turn. Raw HTTP headers were not retained and no requests were
repeated to create the record. The three empty result files are retained in
the temporary work directory; their hashes and times cannot independently
establish the reported HTTP statuses.

Search-record minimization correction (papercut 2628): the original
26,374-byte record remains byte-identically recoverable at
`/tmp/osint-v4NdHom5/b/search-coverage-reviewed.pre-minimization.json`, SHA-256
`d1eba42cc64d7d542fe71f1e8b6061d0e748a163f26d4498242c304e1c4b152c`.
The durable 6,209-byte derivative removes the entire `results` payload,
`title`, `visible_page_prefix`, and redundant `artifact`, `interface`, and
`search_url` fields. It retains only engine, requested/displayed query,
effective-query uncertainty, execution state, timestamp/status/raw hash,
counts, relaxation/barrier notices, and scope. Original result titles,
snippets and destination URLs remain temporary only; acquisition evidence
was not deleted. A strict key-allowlist check and count/status invariants
validated all seven records. No finding cites the removed result payloads.

The public MP4 download followed the viewer-disclosed link and ordinary
file-size virus-scan warning form. It used no account, access request or
permission change. No script or executable was downloaded. Raw Google,
YouTube, SERP, iVoox and archive-wrapper HTML stays under
`/tmp/osint-v4NdHom5/b`; public form UUIDs, transient caption URLs, scripts,
payment configuration and unrelated incidental details are not preserved here.

Reproduction commands:

```bash
ffmpeg -i VIDPODCASTSERV1.mp4 -vf 'fps=1,scale=270:-1,tile=6x5' -frames:v 1 sample-captions.jpg
ffmpeg -i VIDPODCASTSERV1.mp4 -vf 'fps=4,crop=1080:160:0:900,scale=540:80,tile=4x26' -frames:v 1 caption-strip-corrected.jpg
```

The temporary `/tmp/osint-v4NdHom5/b/sample-contact-sheet.jpg` is a separate,
intentional early diagnostic generated with `fps=1/7,scale=360:-1,tile=4x4`:
four populated samples and twelve padding tiles. It was not promoted or cited
as the one-per-second review. The durable `sample-captions.jpg` instead has
26 populated one-per-second frames and four padding tiles. The durable
`caption-strip-corrected.jpg` has 104 populated quarter-second caption crops.

The initial incorrect crop and its unhelpful OCR were excluded from this
bundle. The corrected visual strip, not OCR alone, supports the caption
observations. Findings 15455 and 15456 each passed the repository evidence audit
with zero reported issues; this does not independently authenticate source
claims or resolve the missing source episode.
