---
status: completed
profile: elephant-clipping
track: D
collector: agent:manual-wave2-distribution
source_skill: pursue-lead
lead_id: 94429
secondary_lead: 94355
thread_ids: [210, 212]
date: 2026-09-02
findings_created: [15435, 15436, 15437, 15438, 15439, 15443]
connections_created: [6792]
connections_refined: [6790, 6791]
followup_leads: [94829, 94495, 94355]
---

# Track D — shared edits, rebranding and controls

## Key discoveries

This wave moves beyond the account census to preserved creative-level evidence. It examined **nine additional Instagram MP4s plus two preserved baseline MP4s**, not a random sample or a full account inventory.

1. A third account, `@theusdebatearena`, carries the same 1,750-character caption and nearly identical mirrored Charlie Kirk edit as the baseline pair. Its audio decodes to exactly the same mono16kHz float32LE bytes as `@lonealphapolitics`. The three media-ID-derived generation times span117.644 seconds. **Finding15435.**
2. Two separate `@politics.ts`/`@politics.fx` pairs reuse exact long captions and matching edited source frames/headlines/subtitles but swap the account logo. The derived gaps are about80 minutes and2 hours, not near-simultaneous. **Finding15437.**
3. The Batch B exact-caption pair also has **identical decoded audio**, matching subtitle/flag overlays and different branding. Its derived gap is nearly5 days. This supplies evidence of edited-content reuse while preserving public copying as an alternative. **Finding15438.**
4. Two tax-topic candidates are useful counter-evidence: `@newzinsights` uses a different edit of the same encounter, while `@politi.cszone` shows a different exchange altogether. **Finding15436.**
5. A public YouTube control has an explicit February23,2026 publication date and depicts the same Kirk/student encounter in a different split-screen treatment. It is not the origin of the exact matched edit. **Finding15439.**

These observations distinguish **shared source**, **shared edited material**, **rebranding**, **timing**, and **actor attribution**. They do not identify a human controller, payer, funder, or a campaign enrollment record. The coordinator's three ACH rivals remain open: one controller; separate clippers with a common packet; independent reuse of prior public material.

## Persisted findings and graph changes

| Finding | Claim | Confidence |
|---|---|---|
|15435|Third account extends baseline caption/edit/audio match|Synthesis, medium|
|15436|Different-edit and different-exchange controls|Synthesis, medium|
|15437|Two politics.ts/fx logo-swapped edited-caption pairs|Synthesis, medium|
|15438|Batch B identical audio/caption, rebranded edit|Synthesis, medium|
|15439|Earlier public encounter control, not exact edit origin|Synthesis, medium|
|15443|Selected embed disclosure observability limits|Synthesis, medium|

Added connection6792 between the registered accounts `@theusdebatearena` and `@lonealphapolitics`, explicitly limited to content sharing. Refined existing candidate edges6790 and6791 through audited corrections and added durable comparison evidence; no duplicate edges were created. Added `15435 refines15323`. No civil identities or ownership entities were resolved. New finding target labels are automatically represented by the repository as unknown-type subject entities; they are analytic subjects, not newly discovered legal organizations.

Root independently corrected baseline finding15323's timestamp wording and withdrew its old APSNR magnitude after audio QA. Track D did not compete with those edits.

## Post inventory and volatile metrics

`t-ID` below means **MEDIA-ID-DERIVED generation time**, using the historical scheme; it is not explicit `published_at`. All11 embeds omit `taken_at_timestamp`. The exact formula, primary historical source and limitations are in `d-methods.md`.

| Account / exact post | t-ID, UTC | MP4 duration | Views in captured embed | Caption chars |
|---|---|---:|---:|---:|
|[theusdebatearena/Dcg245KTBBp](https://www.instagram.com/theusdebatearena/reel/Dcg245KTBBp/)|Aug26 18:29:03.725|51.106s|743|1,750|
|[_politicalhub/Dcg3GEFhIaG](https://www.instagram.com/_politicalhub/reel/Dcg3GEFhIaG/)|Aug26 18:30:51.620|51.245s|312|1,750|
|[lonealphapolitics/Dcg3HQQTea6](https://www.instagram.com/lonealphapolitics/reel/Dcg3HQQTea6/)|Aug26 18:31:01.369|51.106s|370|1,750|
|[newzinsights/Dchbt_aS0dF](https://www.instagram.com/newzinsights/reel/Dchbt_aS0dF/)|Aug26 23:50:53.069|61.415s|318|1,055|
|[politi.cszone/DcfbnTrMnBs](https://www.instagram.com/politi.cszone/reel/DcfbnTrMnBs/)|Aug26 05:11:29.455|51.524s|1,211|1,678|
|[politics.ts/Dcyh2RcyfT8](https://www.instagram.com/politics.ts/reel/Dcyh2RcyfT8/)|Sep2 15:11:31.986|24.171s|700|1,087|
|[politics.fx/DcyUDEkyN_1](https://www.instagram.com/politics.fx/reel/DcyUDEkyN_1/)|Sep2 13:10:56.802|24.147s|1,703|1,087|
|[politics.ts/Dcx9xisylQp](https://www.instagram.com/politics.ts/reel/Dcx9xisylQp/)|Sep2 09:56:18.866|49.898s|1,618|1,062|
|[politics.fx/Dcx0jZ1SnC8](https://www.instagram.com/politics.fx/reel/Dcx0jZ1SnC8/)|Sep2 08:35:44.451|49.829s|792|1,062|
|[dailypolitics2026/Dcics_thlwQ](https://www.instagram.com/dailypolitics2026/reel/Dcics_thlwQ/)|Aug27 09:18:43.636|24.124s|15,814|905|
|[truth.inpolitics/DcvOLk7xFni](https://www.instagram.com/truth.inpolitics/reel/DcvOLk7xFni/)|Sep1 08:21:57.456|24.124s|1,621|905|

Main three new embed response Date headers: Sep2 16:28:51–53Z. Six extension embeds:16:44:08–10Z. The two baseline counts are prior-wave preserved values, not refreshed snapshots; their embed response Date headers are14:57:48–49Z, distinct from the earlier primary-page/media capture chain. Sanitized JSON keeps each response header separately.

**No reach total is calculated.** The denominator is11 selected posts, with repeated creatives, overlapping audiences, different snapshot times and platform-defined views. Neither follower totals nor summed views estimate unique people reached, a complete campaign, or paid reach. This wave does not revise the wave-one27-profile/311-reel census.

## Comparison results

### Three-account Kirk package

Theus, politicalhub and lonealpha captions share SHA256:
`a35827e59c2769d91f171d6a2bedf8607199d9ed11ac04e540017c66637873d6`.

The caption includes the unusual phrase “leaving a high earner with only fifteen percent.” The three videos show the same mirrored interview treatment, crop/cuts, burned-in speech text and top headline. Full aligned SSIM for theus vs politicalhub is0.993816; the baseline pair was0.993332. These scores support the observed edit similarity and do not assign ownership.

Theus and lonealpha MP4 hashes differ, but both decode to816,251 identical mono16kHz float32LE samples (51.0156875 seconds), SHA256:
`6904c56827ca1d0252afedef6eb729bfa8dbf2f3b755406b3ab59416fb8a16f6`.

Theus is107.895 seconds before politicalhub under the media-ID derivation; lonealpha is9.749 seconds after politicalhub. This conditional ordering does not prove actual upload scheduling or establish which account first made the edit public.

### Repeated logo replacement across politics.ts/fx

Trump pair caption hash:
`6bc2aad12f0b29e9fecf24f84c9f01da6ba668cc2bb10b4ea49bd0d9851f0db3`.

Hawley/Bridges pair caption hash:
`8135654eef53ba2d99686aad72f3663611760da81c9581d61098c865d75dc1e0`.

For both, matching sampled video frames, headline wording and subtitle styling sit below different logos: a circular US flag on politics.ts and an eagle/Great-Seal-style graphic on politics.fx. The source-file hashes and decoded-audio hashes differ; this report does not call these byte-identical files. Full-frame SSIM after explicit360x640/SAR1/25fps normalization is0.930533 and0.689871. Those scores are layout/cadence sensitive; the repeatable textual and visual editing residues matter more than a threshold.

The fx→ts t-ID gaps are7,235.184 seconds and4,834.415 seconds. Thus two pairs show reusable content with account-specific branding, but do not demonstrate simultaneous posting. Public source events are much older: [Hawley's own page dates the hearing July12,2022](https://www.hawley.senate.gov/watch-far-left-berkeley-law-professor-melts-down-when-senator-hawley-asks-her-if-men-can-get/), and the [White House video page dates the congressional address March4,2025](https://www.whitehouse.gov/videos/president-trump-addresses-joint-session-of-congress-march-4-2025/). These date the source events, not the precise edited packages or their supplier.

### Batch B: same audio with changed visual card

The905-character caption hash remains:
`ebca3ab01fb8a503c5f1d9ae98eaa302aa24fa04938198ce7bf7dde36119f893`.

Both media decode to384,545 identical mono16kHz float32LE samples (24.0340625 seconds), SHA256:
`c9ec71e3e97932cb0bff9d5b59bbc41abcb6a8ad5d8ca0e46078334131ae22a8`.

Sampled Faulkner interview frames share the yellow speech captions and US-flag overlay. Dailypolitics uses a white card and baked-in `DAILY POLITICAL INSIGHT / daily_political_insight`; truth.inpolitics uses a black card and `DAILY POLITICS / Truth in politics Clips`. The headline changes singular “Number” to plural “Numbers.” Blue-check graphics are part of the image and **do not prove platform verification**.

The t-ID gap is428,593.820 seconds, or4 days23 hours3 minutes13.820 seconds. That large interval is compatible with copying an earlier public post. The branded selector `daily_political_insight` is unresolved; search returned no useful exact indexed profile, which does not establish nonexistence.

## Controls, contradictions and alternative explanations

- **Different edit, same encounter:** newzinsights is unmirrored, vertically split screen, uses colored subtitle emphasis, lasts61.415 seconds and has a different caption. Whole-clip audio alignment is weak because its selection/order differs; that does not disprove a shared raw source.
- **Different exchange:** politi.cszone shows another interlocutor and a different tax discussion. Full-frame SSIM0.668915 is not evidence of sameness: similar borders, speaker and backdrop can inflate a global score. The matching rule requires multiple distinctive features, not a popular speaker or broad topic.
- **Older public encounter:** [YouTube8yK0Oi7ituk](https://www.youtube.com/watch?v=8yK0Oi7ituk) has explicit publish/upload metadata February23,2026, channel `UC2rb3_pKU7nOfJocZcudkOg`, public author Belmar Division,39-second duration. Its disclosed thumbnail depicts the same encounter in an unmirrored split-screen treatment. Only metadata and the disclosed thumbnail were acquired; full-video or exact-edit identity is untested. It is evidence against assuming the underlying encounter was novel to these accounts, not evidence of a campaign link.
- **Index/live mismatch:** the earlier newzinsights discovery was prompted by indexed caption fragments. Its preserved live caption and media do not reproduce the baseline package. Search traces cannot substitute for current post preservation or establish caption edit history.
- **No attribution bridge:** an edited asset or caption can be copied, supplied to multiple clippers, or used across accounts by one controller. No current evidence resolves which mechanism explains these pairs. ML-code consistency from wave one remains contextual, not a public enrollment record.

## Audio QA and correction

The old approximately174dB APSNR statistic is excluded. The same pipeline returned173.52dB for unrelated997Hz sine audio against speech. Track D logged papercut2506 and immediately sent the counterexample to root; independent artifact-hygiene QA reproduced it and all five main PCM hashes.

Validated replacement: after trimming766 samples/47.875ms from politicalhub audio, its51.0156875-second overlap with lonealpha/theus has waveform Pearson0.9458160882. Independently aligned10ms RMS envelopes correlate0.9846651297. A one-second-shift control recovers1 second and correlation1.0; the unrelated sine is about0.00382. These are narrow similarity measurements, not attribution probabilities. Mono/resampling equality is not original stereo/file equality.

See `/tmp/osint-ldT6picn/report-audio-qa.md` and `h-audio-qa-results.json` for independent methods and brute-force validation. Exact Track D commands, version, negative control and caveats are durably in `d-methods.md`. The published findings here do not rely on APSNR magnitude.

## Disclosure and transparency limits

Finding15443 and a note on lead94355 record the observable boundary: the11 selected public embed field sets expose no explicit paid-partnership/sponsor/branded field. **Absent metadata is unobservable, not false.** This is not proof of no label, no creator payment or no platform ad purchase. CUA had no browser surface; rendered labels were not reviewed in this wave.

Meta's [2026 election-policy statement](https://about.fb.com/news/2026/02/meta-prepares-for-2026-us-midterms/), originally February19 and updated June1, describes authorization, payer disclaimers and library retention for political/social-issue/election **ads**. It is a current and pre-sampled-post policy source, not evidence the sampled posts were ads. The Ad Library root returned403 before any account-specific search; the Instagram branded-content Help page redirected to login/temporarily blocked. No “no ads found” conclusion is supported. The earlier organic-rule version gap in finding15357 remains.

## Sources checked and scoped negatives

| Source/method | Scope and result | Preserved output / limit |
|---|---|---|
|Instagram public HTTP embeds|9 exact new reel IDs, all200;2 preserved baselines reparsed|`d-public-post-metadata.json`, `d-baseline-public-post-metadata.json`, `d-extension-post-metadata.json`; no authenticated API|
|Public disclosed media URLs|9 new MP4s downloaded;11 total local comparisons|`media/`, hashes/probes in JSON; signed URLs excluded|
|Exact caption/headline web search|Kirk headline,15-percent fragment,Faulkner headline,Hawley headline|`d-upstream-search-1/2/3.json`; no useful earlier exact-package result, not proof of absence|
|Kirk85%/shirt/source search|One useful earlier YouTube encounter candidate|`d-upstream-search-2.json`, `d-youtube-control-metadata.json`; no full playback available|
|Official source-event pages|Hawley2022 hearing and WhiteHouse2025 address|`d-upstream-official-pages.json`; not exact-edit origin verification|
|Fox/Facebook source and baked handle search|No exact original Faulkner clip or useful daily_political_insight profile recovered|`d-upstream-search-4.json`; unrelated results excluded|
|Historical primary ID documentation|Instagram engineering presentation by MikeKrieger|`d-id-method-primary.json`; generation-time derivation only|
|Meta policy/help/library|Newsroom available;Help login/blocked;Library403|`d-meta-policy-observation.json`, `d-post-disclosure-observation.json`; no targeted ad-library search completed|
|Independent audio QA|Fresh decode, exact overlap-centered Pearson,controls|Root-owned `report-audio-qa.md`; account attribution remains our provenance responsibility|

Search logs were checked before queries and updated with bounded useful-result counts. Zero means no relevant exact result within the saved query response, not zero web results or universal absence. No Wayback replay for an exact earlier package was recovered this wave; archive expansion remains a follow-up, not an inferred negative.

## Artifacts and hygiene

Durable directory:
`investigations/elephant-clipping/artifacts/2026-09-02/distribution-wave-2/`

It contains sanitized metadata, file/PCM hashes, analysis scripts, comparison logs, contact sheets, the disclosed YouTube thumbnail, methods, and all11 analyzed Instagram MP4s under `media/` (about54MB total before final manifest). Raw Instagram/YouTube HTML and full headers remain temporary because they may contain signed media URLs/session material. Durable metadata explicitly excludes signed URLs. `d-manifest.json` lists durable file hashes.

The changed temporary Python analysis scripts pass `uv run ruff check`. Evidence audit found no new-lane issues; its two warnings concerned old15323 MP4 references missing quotes, sent to root without competing edits. Papercuts:2506 audio metric control failure;2518 unequal media dimensions/frame rates (addressed with explicit normalization);2520 no CUA browser;2522 schema-column assumption during read-only audit (no writes, then inspected live schema).

## Source gaps and follow-ups

- **94829, new:** earliest independently dated public copies of the four exact edited-caption packages, including uncoded controls and the baked `daily_political_insight` selector. Prior raw events and an earlier differently edited clip do not answer this.
- **94355, existing:** rendered disclosure, actual ad IDs/boost records and time-specific organic branded-content policy. Do not infer payments or violations from omitted fields.
- **94495, existing:** bounded broader ML-code census. Track E's two Bing candidates were independently handled by handle_triage_b, not duplicated here. Findings15441/15442 report first-party metadata confirmation for `@ykpolitics`/ML-T0UJ and `@us_politicstoday`/ML-EC19, but no hydrated timeline verification. Missing historical account IDs limit rename exclusion; root should preserve those distinctions.
- Ownership/funding/campaign attribution requires a public bridge from these exact accounts or creative versions to an operator, packet, campaign row or payment. Source originality is not actor attribution.
- More precise media timing would require explicit platform timestamps or documented ID-scheme validity. Keep current precision conditional.

Lead94429's assigned three-reel preservation/comparison question is completed, with the authorized three extension pairs also tested. No larger census or unauthenticated-access workaround was started.

## Exact additional metrics and media hashes

Views are in the inventory above. The following like/comment counts belong to the same respective embed snapshots; they are not endorsements by unique people or campaign reach.

| Post | Likes | Comments | Response Date, Sep2 UTC |
|---|---:|---:|---|
|Dcg245KTBBp|16|0|16:28:52|
|Dcg3GEFhIaG|2|0|14:57:48|
|Dcg3HQQTea6|15|1|14:57:49|
|Dchbt_aS0dF|6|0|16:28:53|
|DcfbnTrMnBs|16|0|16:28:51|
|Dcyh2RcyfT8|45|1|16:44:08|
|DcyUDEkyN_1|212|12|16:44:08|
|Dcx9xisylQp|44|0|16:44:09|
|Dcx0jZ1SnC8|53|7|16:44:09|
|Dcics_thlwQ|304|16|16:44:10|
|DcvOLk7xFni|63|0|16:44:10|

| Post | SHA-256 of exact MP4 bytes |
|---|---|
|Dcg245KTBBp|`42279c2ac288867b0725960767e45d94d85e894f01b37be78e78718340695e3b`|
|Dcg3GEFhIaG|`10305548ae619b14a675f7384308c8f85b0e138ded955550c8e39db59ded0f49`|
|Dcg3HQQTea6|`5c1219d036cde98766dd2dd8598c8d1ea8bff4d0d57c007e7039b49b4bf449d7`|
|Dchbt_aS0dF|`21a2bd75b33f227e82875ff48eb5552a6726d5344fc15bc3d40db6d6fd543cdf`|
|DcfbnTrMnBs|`b74e1a98817424e5f067b532ef2093d1f879e560678305ef766cbba23fdc56e1`|
|Dcyh2RcyfT8|`b249c0dcd9ef0cce6ed5c43ddc1505843cb75fe952d641292796196d0f0e8976`|
|DcyUDEkyN_1|`9deb33ae4fd1f9c092680ec73b94dd42c51fd0c8c0716511711de613e276580e`|
|Dcx9xisylQp|`fc3eb2bf8e31cbb0fd81f604e5a82b5efb8f73e54a2b224c799a25c9ec0547a6`|
|Dcx0jZ1SnC8|`1e36976f2d33e3001033b5622bd81e29d8d93b9ddca2fd2804b511a00b68e828`|
|Dcics_thlwQ|`1632de599817341b447547dfdb0b463c558b1e9098b2a7b23b684e71bbcc9576`|
|DcvOLk7xFni|`cfe00b53df877bdee5080eddabdb66dc390bc809f91ec2c3228193cac8c31113`|

| Post | Decoded mono16k f32 samples | SHA-256 of those decoded bytes |
|---|---:|---|
|Dcg245KTBBp|816,251|`6904c56827ca1d0252afedef6eb729bfa8dbf2f3b755406b3ab59416fb8a16f6`|
|Dcg3GEFhIaG|818,480|`6011c347e550613bf2a9b5fdbb0635f17c756c5ca325e2bbd810efe643d198a5`|
|Dcg3HQQTea6|816,251|`6904c56827ca1d0252afedef6eb729bfa8dbf2f3b755406b3ab59416fb8a16f6`|
|Dchbt_aS0dF|981,205|`86e042c4d7fb0614bbab1b3b2f57f5d34ca15fea09444bf12234bbe7aa6f49e7`|
|DcfbnTrMnBs|822,938|`c3d5cd12878ea580eb44c34a92020068a39c38fe65d1a8048fcd5aa448c241b5`|
|Dcyh2RcyfT8|385,288|`af65033baf90ab0b12c82c0671caaa2fbfab2a078308e2efe90d97a0d7b924ca`|
|DcyUDEkyN_1|384,545|`4d9928045ab90bcb3b386a43d5f4928734b99b72c4af7dbba84217ef49d6a0d3`|
|Dcx9xisylQp|796,932|`4e8a6b198da8ad4fac474c1280f3f4be09df549aaa71e65345f2c4b5d981d580`|
|Dcx0jZ1SnC8|795,445|`33f106ecd9d49db6f5c5cefebd70a7a236bc57f25c946ee9e847e1ae036fa22c`|
|Dcics_thlwQ|384,545|`c9ec71e3e97932cb0bff9d5b59bbc41abcb6a8ad5d8ca0e46078334131ae22a8`|
|DcvOLk7xFni|384,545|`c9ec71e3e97932cb0bff9d5b59bbc41abcb6a8ad5d8ca0e46078334131ae22a8`|

## Learnings

- A matching long caption plus repeatable crop/subtitle/logo residues is more discriminating than popular source footage. Preserve account-specific rebranding as evidence rather than treating every visual difference as a non-match.
- Known-different controls can invalidate an impressive metric. Preserve the failed statistic and correction trail, then use specified decoded-byte hashes and independently checked alignment.
- Keep source-file hashes, decoded PCM hashes, visual similarity, media-ID generation time and actor attribution in separate fields. Each supports a different claim.
- Global SSIM can be inflated by letterboxing or reduced by branding/frame cadence. Inspect controls and explicitly normalize dimensions/frame rates; do not use a universal match threshold.
- Long inter-post gaps are substantive counter-evidence to synchronization and keep copying of a prior public edit viable, even when caption/audio matches are exact.
- Public embeds can preserve strong media evidence while exposing no reliable disclosure state. Missing fields and access failures must remain unobservable, not negative factual claims.
