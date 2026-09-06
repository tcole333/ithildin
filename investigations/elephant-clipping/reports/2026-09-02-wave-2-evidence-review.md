---
status: completed
profile: elephant-clipping
skill: deep-investigate
reviewer: agent:manual-artifact-hygiene
agent: manual-artifact-hygiene
target: elephant-clipping-wave-two-evidence
date: 2026-09-02
findings_added: []
scope: final-wave-local-evidence-review
---

# Final-wave evidence and artifact review

## Key Discoveries

One bounded local pass completed. No new source queries, source contact, child agents, investigation claims, or direct database edits by this reviewer. The final profile evidence audit has **zero errors**, two intentional binary-quote warnings, and no dangling local evidence references. The reviewed durable artifacts pass all 73 listed file-hash checks; no JSON/YAML parse failures or credential/session-bearing HTML candidates were found in the three scoped bundles.

The separate structured-handoff validator reports eight schema/Learnings-format issues in five original reports. Those reports were deliberately preserved unchanged, not silently reformatted. This is not a claim that every source across the whole profile has been independently authenticated.

## Inspected scope

- Read completed temporary reports A, B, C, D, E and F (`report-bing-profile-check.md`), the profile instructions, and the applicable deep-investigate review instructions. D's final capture-time correction and completed manifest were included.
- Read all 20 new findings **15424–15443**, the root's corrected **15323**, their **73 evidence rows**, and connections **6790–6792** with attached evidence. All eight synthesis findings in the 20-record wave remain medium; ten paraphrases remain high; the two direct-quote/confirmed findings are narrowly limited to first-party served profile metadata, not ownership or campaign membership. Baseline 15323 remains synthesis/medium.
- Re-ran the repository evidence audit across the full profile: **128 findings / 340 evidence rows; 78 automated span matches, zero mismatches, 260 unchecked and two missing quotes**. An unchecked URL is not independently validated by that structural audit.
- Verified **59 distribution files** against D's JSON manifest, including all **11 MP4s**, total **56,844,547 bytes**; **three cloud-wave-2 files** against its manifest; and **11 newly preserved review files** against the new manifest. All 73 hashes and listed sizes agree. No existing D/cloud evidence was duplicated.
- Inspected the three bundles' textual JSON/Markdown/code/log material for raw HTML, credential literals, cookie/authorization values, signed/session media URL indicators and incidental Windows user paths. Public account IDs, media IDs, document IDs, ordinary business-contact emails and stable public payment links are not credentials. No unsafe candidate remained in this scoped scan. No raw payment-session output or incidental bank/order fields were copied into the review bundle.

## Quote verification and audited corrections

All 71 nonempty scoped evidence quotes were located in the retained local evidence/excerpts or checked visually; two MP4 rows remain intentionally unquoted. Breakdown: **24 exact local-text matches, 44 retained-excerpt matches, one whitespace-normalized match and two manually checked image quotes**. Retained excerpts include collector-authored same-source notes, not independent corroboration or a new live retrieval. The CPT content-hub quote in 15425 joins adjacent display lines with normalized whitespace; its cached/index rendering and live-access limitation remain explicit.

Targeted primary checks included raw retained YouTube descriptions for the two A shortlink quotes; O'Hara's retained credit and public-post extracts; literal invoice-client code; both F profile-description fields; D's caption/method JSON; and the historical engineering-PDF extraction. The YouTube control thumbnail visibly says `sales tax so`; the public tutorial thumbnail visibly says `Poker`; the rendered CPT deck shows `Digital Social Hour` and the quoted sponsor-service text. The recording-preview watermark is represented by A's retained same-source observation and was not recopied into durable storage because its raw preview includes incidental local-user data.

Three issues were proposed to root, repaired by root through the audited tracker, and verified in the persisted export:

| Record | Repair | Correction IDs |
|---|---|---|
|15435, historical ID-method evidence|Removed a noncontiguous concatenation of two source lines. The source quote is now the single exact `result := (now_millis - our_epoch) << 23;` line; the separate epoch declaration and historical-method limitation are in the assessment.|11898–11899|
|6790, four older URL assessments|Labeled the original “media equality untested” observations as initial wave-one scope and pointed to the completed 15437 comparison. Does not imply file-byte identity or common ownership.|11900–11903|
|15443, Ad Library access evidence|Changed `403 Forbidden` to the preserved exact punctuation `(403) Forbidden`. It remains a fetch failure before any account-specific ad search, not a negative ad result.|11904|

The root's earlier correction of 15323 was also checked: **11890–11891** withdraw the approximately 174 dB APSNR magnitude as identity evidence, attach independently reviewed replacement computation, retain the SSIM/caption evidence, and preserve the **media-ID-derived** 9.749-second wording. The detailed independent local control review remains in `report-audio-qa.md`; this final pass did not edit that finding. Connections 6791 and 6792 explicitly limit their meaning to shared/rebranded content, not a payer/controller.

As one additional local replication check, fresh FFmpeg decoding of the two durable Batch B MP4s (first audio stream, mono 16 kHz float32-LE) returned the same SHA-256 for each: `c9ec71e3e97932cb0bff9d5b59bbc41abcb6a8ad5d8ca0e46078334131ae22a8`, matching 15438/D's comparison. Equality of this decoded representation is not proof of original-file/stereo equality or attribution.

## Reviewed preservation

Created `investigations/elephant-clipping/artifacts/2026-09-02/wave-2-review/MANIFEST.md` with original-to-durable mappings, original and destination hashes, transformations and exclusions.

- A/B/C/E/F reports: five **byte-identical**, immutable reviewed copies.
- F metadata: two byte-identical allowlisted public-profile captures for `ykpolitics` and `us_politicstoday`. Raw HTML was not copied.
- E: a minimized coverage file for **16 issued requests** and a separate file containing only the two useful Bing candidate excerpts. Eight unissued DuckDuckGo/Yandex cells remain explicitly unqueried, not zero. Operator suppression and the `servicios` rewrite notice are preserved; unrelated destination inventories and session-bearing raw HTML are excluded.
- ACH: two safe exports. JSON content is unchanged; `apply_patch` adds only a terminal newline, and both original and durable hashes are disclosed. There are **21 assessments / seven findings / three hypotheses**, all seven findings non-diagnostic. No ordering is treated as a winning explanation.

No database evidence references were rewritten to these copies. The existing cloud/distribution bundle manifests are linked rather than duplicated.

## Remaining limitations and warnings

1. The only evidence-audit warnings are the original two binary MP4 refs on 15323. No invented textual quote was assigned to binary media. They exist at their retained temporary paths; matching media copies are also present in D's manifest.
2. Some B/C raw material, the independent QA report/script, and original acquisition outputs remain temporary. The manifest does not claim that every primary raw source is durable. Raw viewer HTML, payment-session material and the incidental-user-path recording preview remain deliberately outside the durable review bundle.
3. `validate_report.py` finds eight handoff-format issues: A lacks `findings_added`/`skill`; E lacks `findings_added`/`Findings Added`; A/B/E/F have untagged Learnings entries; C uses `[Process]` instead of `[Process gap]`. All copied frontmatter parses as YAML. Root owns separately normalized ingestion copies; originals were not altered. This review did not re-run article/brief review or duplicate root's synthesis.
4. No browser-rendered privacy state, ad label, account-specific Ad Library search, owner identity, campaign enrollment, payment attribution, historic rename exclusion or earliest exact-edit origin was established by this hygiene pass. Search failures and omitted embed fields are not negative substantive evidence.
5. The credential-pattern scan and excerpt matching are bounded checks, not a forensic guarantee over every byte of every original acquisition. Preserved media were hashed; no full new frame-by-frame review was performed.

The handoff-schema friction was reported to root but not separately logged by this reviewer. Exact reproduction: `uv run python tools/validate_report.py investigations/elephant-clipping/artifacts/2026-09-02/wave-2-review`. The final audit report itself passes `uv run python tools/validate_report.py /tmp/osint-ldT6picn/report-final-evidence-audit.md`.

## Findings Added

None. The coordinator made only the audited corrections listed above.

## Learnings

- [Source quality] A quote assembled from two true but noncontiguous source lines still needs an ellipsis or separate contextual assessment; exact code quotations deserve the same span discipline as prose.
- [Methodology] Structural evidence-audit success must be reported with its unchecked denominator. It does not turn inaccessible URLs or same-source preservation notes into independent verification.
- [Process gap] Preserve agent reports as immutable source records and normalize separate ingestion copies when the required handoff schema or Learnings syntax differs; disclose any byte-level newline normalization in manifests.
- [Methodology] Search coverage can be preserved without mirroring irrelevant result inventories: keep query/access/operator status, useful candidate excerpts and hashes, and retain unqueried/challenged cells as null rather than false negatives.
