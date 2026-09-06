---
agent: wave3_provenance
target: "Campaign-file provenance; CPT production; tutorial-source candidate"
skill: deep-investigate
additional_skill: pursue-lead
status: completed
findings_added: 2
connections_added: 0
entities_registered: 0
leads_spawned: 0
finding_ids: [15455, 15456]
lead_id: 94994
lead_disposition: in_progress
profile: elephant-clipping
papercut_ids: [2606, 2616, 2628]
---

# Agent B: source-packet attribution is still missing

## Key Discoveries

1. **The CPT content hub is recoverable in archives.** All five returned
   captures, January 2025 through April 2026, were fetched and inspected. They
   are conventional article/event-highlight catalogues. Their complete visible
   text and href inventories contain no campaign-specific cloud link or named
   uploader. This is explicitly sparse page-level coverage, not a contradiction
   of the Atlantic's uploader reporting. Finding **15455**.
2. **The tutorial candidate is more specific, but still unverified.** The full
   public `VIDPODCASTSERV1.mp4` was recovered: 25.983333 seconds, 128,113,981
   bytes. Programme graphics and sampled poker/yacht/billionaire captions led
   to primary YouTube video **4uYmzucv4WQ**, *The Billionaire Table: My High-Stakes
   Poker Journey | Sean Perry DSH #721*, primary publication metadata September
   14, 2024. The description includes “From playing poker on super yachts with
   billionaires”. No actual source-episode audio/transcript segment was obtained
   for comparison, so this is **a candidate, not an exact match**. Finding
   **15456**, synthesis/medium. No face-based identification was performed.

There is still no independently attributable political campaign file, no
Wynn-side public uploader bridge, and no CPT-to-ClipIt supply/payment edge. The
missing bridge is the actual campaign folder/file ID or a published referrer,
followed by readable source metadata tied to that specific political artifact.
An ordinary tutorial episode match would not by itself supply that bridge.

## Findings Added

| ID | Claim | Type / confidence | Thread |
|---|---|---|---|
| 15455 | Five sparse archived CPT content-hub pages expose an ordinary catalogue | Paraphrase / high | 207 |
| 15456 | Full public tutorial sample yields DSH #721 as a specific unverified candidate | Synthesis / medium | 209 |

Eleven evidence rows cover the five exact archive URLs, primary episode/viewer
URLs, inert preservation and caption strip. Same-source preservation
assessments are explicit. Evidence audits for each new finding report zero
issues. All task Python scripts passed targeted Ruff checks.

## Connections Added

Zero. No commissioning, licensing, control, payment or content-supply edge.

## Entities Registered

Zero. The episode title's guest is not registered as a campaign operative or
merged with a depicted person. Existing CPT/Enclave/Serviuos entities are reused.

## Artifact Classification

| Artifact | Classification | Limit |
|---|---|---|
| Atlantic saved HTML | Secondary reporting / provenance lead | No actual Drive/Docs href or file ID in the saved copy; prior article-media no-ID review reused |
| Five CPT content-hub captures | Ordinary public commercial-media catalogue | Five exact pages only, not every date or linked article |
| VIDPODCASTSERV1.mp4 | General training sample | One of fifteen files; no political packet inferred; remaining fourteen not downloaded |
| DSH #721 public metadata | Ordinary published media / source candidate | Exact source segment not compared |
| Existing hiring/profile records | Professional production context | Role descriptions do not authenticate an uploader or political commission |

## Negative Results

- No campaign folder ID exposed by the seed article's links. Prior article
  visual-media review is reused, not counted as a new independent check.
- No relevant campaign artifact in the retrieved first pages from four Bing
  selectors. All four returned off-domain or unrelated results despite query
  echoes; they do not represent successful strict operator execution.
- Brave's first selector explicitly said its operators were not applied. Its
  second returned 429/captcha; the remaining two queries were not issued.
  Irrelevant relaxed-query Drive folders were not opened or mined for people.
- Mojeek returned HTTP 403 and an automated-query notice on one exact company
  domain/cloud query. No bypass or second query.
- `celebritypokertour.org/*` Wayback request failed 503 after the initial sandbox
  DNS failure was retried with network permission. No archive zero asserted.
- Exact public CPT hiring-post Wayback scope returned zero captures. Existing
  live/indexed role evidence in 15373/15425 and earlier Enclave roster reviews
  were reused. The broader production hiring dates remain unresolved.
- DSH #721's disclosed YouTube auto-caption request returned 200/zero bytes;
  the Podchaser-linked ART19 audio route returned 404 and the iVoox page's public
  listen link returned 410. This is unavailable comparison material, not proof
  captions/audio never existed or the candidate is wrong.

## Sources Checked

All new local outputs are under `/tmp/osint-v4NdHom5/b` unless noted.

| Source | Exact scope / command family | Outcome / artifact |
|---|---|---|
| Profile, lead and evidence baseline | `investigation_context show`; lead 94994/94826; findings 15373,15425,15433/15440; wave-two brief and lane manifests | Read and reused; 94994 claimed after root clarification note |
| Seed article | BeautifulSoup anchors and uploader/Drive paragraphs in user-supplied HTML | No actual file href; no new allegation finding |
| Bing public HTML | `"celebritypokertour.org" site:drive.google.com`; `"enclaveandkey.com" site:drive.google.com`; `"Elephant Clipping" "Google Drive"`; `"US Politics Clipping" "drive.google.com"` | Four pages, 10 parsed destinations each, all off-target; `serp-public/e-bing-q*.json` |
| Brave public HTML | First two identical selectors above | First 13 parsed destinations with explicit relaxation; second 429/captcha; last two unissued; `serp-public/e-brave-q*.json` |
| Mojeek public HTML | `"celebritypokertour.org" "drive.google.com"` | 403 automated-query barrier; `mojeek-domain.html`; reviewed coverage JSON |
| Unified web | Company-domain cloud variants; exact campaign plus folder/Drive; Jack O'Hara three-podcast/production wording; CPT clipping | No relevant new file/job bridge. Normalized scopes logged; production results saved in `web-production-search.json` |
| Wayback content hub | `query_wayback.py snapshots 'www.cptnews.com/content-hub*' --collapse digest --limit 100 --output ...`; fetch all five returned timestamps | Five retrieved pages; `content-hub-*.json`; sanitized `content-hub-reviewed.json` |
| Wayback former company domain | `query_wayback.py snapshots 'celebritypokertour.org/*' --collapse digest --limit 300 --output ...` | 503; not zero |
| Wayback exact CPT hiring post | `https://www.linkedin.com/posts/jack-o-hara-7b35a9157_hiring-activity-7283644659178913792-1eX3`, digest collapse, limit 100 | Zero captures; `wayback-jack-job.json`; prior indexed/live text reused |
| Public Drive download | Viewer-disclosed `drive.usercontent.google.com/uc?id=1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE&export=download`, then ordinary public size-warning form | Full MP4, metadata and hashes preserved; no login or access request |
| Video sampling | `ffprobe`; ffmpeg one-per-second full frames and four-per-second caption crops | `sample-captions.jpg`, `caption-strip-corrected.jpg`; visual review, no face identification |
| Programme/text search | DSH with nosebleed, poker/apps, super/billionaires; then exact episode-title/ID and transcript variants | Specific episode candidate; `web-tutorial-caption-search.json`, `web-episode-candidate.json`, related web JSONs |
| Primary YouTube | Exact watch page `4uYmzucv4WQ`; disclosed auto-caption URL | Metadata retrieved; captions empty 200; `episode-metadata.json`, raw HTML temporary |
| Public audio links | ART19 episode `0cf375f1-f195-481d-829a-13ae4138abef.mp3`; iVoox episode `133890665` → disclosed `/listen_mn_133890665_1.mp3` | 404/410; no audio comparison |
| Disconfirmation-oriented check | Try ordinary public DSH episode reuse as explanation for tutorial logo | Earlier public episode candidate found; exact match not established and no commissioned-supply inference |

The search log records new search scopes and failures. Initial sandbox DNS
failures are separate from the single network-permitted retry. The discovered
exact public clip remains general training, so missing Wynn names in it cannot
disconfirm article-described uploaders in different folders.

## Source Gaps Identified

1. **Actual political source artifact:** still no public campaign folder/file ID
   or archived referrer for the reported political packets. A public reporter
   supplement, retained campaign share URL, or company-published artifact would
   be useful; none recovered here. Do not contact subjects or request access.
2. **Exact tutorial episode:** episode 4uYmzucv4WQ is a much narrower candidate;
   a publicly accessible transcript/audio/video segment could test it. Existing
   lead 94826 now contains the candidate and failed route details.
3. **Production timing:** direct dated hiring updates beyond the original
   January 2025 joining post are still lacking; relative LinkedIn activity ages
   are not exact dates and the exact job archive query had no captures.
4. **Engine execution:** query echo is not evidence of strict execution. Brave
   explicitly relaxed operators, Bing was off-target, and Mojeek/Brave hit
   barriers. No index-wide cloud-document absence conclusion is justified.

No new integration was built. Papercut 2606 logs the reused one-off collector's
failure to distinguish unavailable prior searches from completed coverage;
the temporary retry wrapper makes the distinction explicitly. No permanent
tool change or separate infrastructure request was warranted in this pass.

## Follow-Up Leads Created

Zero duplicates. Added the candidate and limitations to existing **94826**.
**94994 remains in progress**, with a completion note for this bounded pass;
the source-packet question is unresolved. Parent may consolidate its future
routing with blocked uploader lead 93835, but no false/negative attribution
disposition was applied.

## Preservation and Verification

Durable lane bundle:
`investigations/elephant-clipping/artifacts/2026-09-02/provenance-wave-3/MANIFEST.md`.
It includes the original public training MP4, two sampled visual derivatives,
selected episode metadata, all five archive text/href inventories, allowlisted
search-coverage metadata and exact notes. Raw script/session-bearing pages and
form UUIDs stay temporary. Source hashes and retrieval times are preserved;
all durable hashes were checked after copying. No acquisition evidence was
deleted.

Final artifact QA identified overbroad SERP preservation (papercut 2628).
The original 26,374-byte `search-coverage-reviewed.json` remains recoverable at
`/tmp/osint-v4NdHom5/b/search-coverage-reviewed.pre-minimization.json`, verified
byte-identical before replacement and SHA-256
`d1eba42cc64d7d542fe71f1e8b6061d0e748a163f26d4498242c304e1c4b152c`.
The durable 6,209-byte derivative now contains only seven allowlisted coverage
records. Removed fields are `results` (including all result titles, snippets
and destination URLs), `title`, `visible_page_prefix`, and redundant `artifact`,
`interface`, `search_url`. Requested/displayed queries, unknown effective-query
state, times/statuses/raw hashes, counts, notices and scope remain. All seven
rows passed exact-key allowlist, count and status checks. Findings 15455/15456
do not cite this file or its removed payloads, so their evidence was unchanged.

Sampling filenames are deliberately distinguished: temporary
`b/sample-contact-sheet.jpg` is an early four-frame diagnostic at one frame per
seven seconds, with twelve padding tiles, and was never cited or promoted.
Durable `sample-captions.jpg` has 26 populated one-per-second frames and four
padding tiles. Durable `caption-strip-corrected.jpg` has 104 populated
quarter-second caption crops. Blank tiles were not counted as reviewed frames.

`media-access-observations.json` records the caption/audio HTTP outcomes as a
collector transcription of tool stdout from this research turn, alongside the
three empty files' hashes and modification times. It is not a retained raw
HTTP-header log or an independent response capture. No requests were repeated
to create that record. The status claims retain this preservation limitation.

Papercut 2616 records the report validator's exact-heading requirement. The
heading and bounded-pass status were corrected; lead 94994 itself remains in
progress because the campaign-file provenance question is unresolved.

## Learnings

- [Methodology] A live content-hub 404 can be complemented by sparse archives, but each recovered capture must be inspected and the gaps between captures must remain explicit.
- [Source quality] Public query echo does not prove search operators were honored; unrelated Bing results, Brave's explicit relaxation, and 403/429 barriers are different coverage states.
- [Methodology] A training-file logo and distinctive captions can nominate a concrete earlier public episode without identifying anyone by face; an exact segment comparison is still required before declaring the source match.
- [Source quality] A public auto-caption URL returning empty HTTP 200 and podcast audio links returning 404/410 limit acquisition, not the historical existence or truth of the material.
- [Methodology] Empty or nonsensical OCR can result from a wrong crop; visually inspect corrected frames before treating extracted text as evidence.
- [Friction] Papercut 2606 records that the reused temporary SERP collector skipped explicit retries after unavailable transport attempts because any prior search-log row counted as completed coverage.
- [Friction] Papercut 2628 records overbroad durable SERP preservation. The corrected positive-allowlist derivative excludes unrelated result payloads while the byte-identical acquisition record remains recoverable temporarily; validate the actual durable file, not only its label.

Root owns the single nonduplicate post-wave learning import and auto-lead scan.
