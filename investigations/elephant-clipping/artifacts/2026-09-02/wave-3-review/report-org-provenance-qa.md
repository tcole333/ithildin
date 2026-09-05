---
agent: fable_org_review
target: "Elephant Clipping wave 3 organizational and content provenance findings"
skill: review-article
status: completed
findings_added: 0
connections_added: 0
entities_registered: 0
leads_spawned: 0
---

# Organizational and content provenance QA — September 2, 2026

## Scope and method

This is a read-only evidence and skeptic review of a working research record, not publication clearance. The reviewer read the wave 3 plan and the complete review-article rubric. The profile guidance and investigative methodology were already read in full. Live database access used SQLite URI `mode=ro`; no source retrieval, form interaction, database update, new finding, or contact occurred. Exact new finding scope: **15450, 15451, 15455 and 15456**. Concurrent other-worker findings 15452–15454 and 15457–15458 were excluded. A fresh local diagnostic image was generated from the already retained MP4; no source artifact was edited.

## Key Discoveries

- **Finding 15450 is supported as an archived publisher offer.** The retained July 13, 2025 and December 8, 2025 bodies both contain the title `ClipIt 6 Week Mentorship`, the `CLIPTOCASH` heading, the exact Viral Vault and Elite Editor Rolodex wording, and the phrase `Weekly updates and on-demand breakdowns included.` The preserved July href points to `https://form.typeform.com/to/fNzBmGno`; December points to `https://form.typeform.com/to/IypbS1ux`. These establish two observed link destinations, not the exact intervening change date or continuous availability.
- **Finding 15451 is supported at the stated current-observation layer.** Independent parsing of the retained unauthenticated HTML found the public embedded form titles `ClipToCash 1on1` and `ClipIt 1on1 Coaching`. Both schemas contain the contiguous phrases `Working with me 1:1 is a 4-figure investment` and `I’m open to payment plans if needed.` Only the public commercial schema wording was checked; no respondent data was read and no form was submitted.
- **The chronology is correctly bounded.** The historical capture timestamps belong to the referring mentorship pages. The form titles and commercial wording were captured on September 2, 2026 and are not established as the 2025 content. The findings state that distinction explicitly. The collection timestamps in the sanitized notes are file-mtime-based retrieval records, not independent publication timestamps.
- **The economic and organizational limits are correct.** Neither finding claims a sale, revenue, enrollment count, exact price, delivered clip library, source-content ownership, campaign funding, named legal merchant, licensor/licensee hierarchy, or political source packet. Promotional wording is attributed to its publisher, not adopted as evidence of earnings or performance.
- **Finding 15455 is supported as sparse archive coverage.** Independent extraction of all five complete retained bodies reproduces the catalogue text and web-link inventories. The archive timestamps are January 16, May 19 and November 10, 2025, and February 8 and April 21, 2026. The catalogue contains ordinary CPT event highlights and sponsor announcements, with no cited campaign label, named uploader or cloud-file link in these pages. This cannot establish the absence of political material from other pages, intervening dates or non-public sources. The finding correctly says that it does not contradict the Atlantic attribution.
- **Finding 15456 advances a candidate, not attribution.** The complete retained tutorial MP4 hash, size, duration and codecs reproduce. The durable 26-frame visual sheet and 104-frame caption strip visibly support the quoted programme/caption observations. Independent decoding of the retained public YouTube response reproduces the candidate's title, channel, date and description phrase. The programme and thematic correspondence nominate DSH #721, but no source-episode segment was available for an exact audiovisual or transcript comparison. The finding properly remains synthesis at medium confidence and does not assert a CPT supply, licensing, payment, control or political-use relationship.
- **The novelty statement is appropriately narrow.** The reviewer independently read all 28 paragraphs in the saved Atlantic article element and verified its original HTML hash. They do not describe the four-figure coaching/payment-plan offer or Viral Vault/editor-list wording. Generic coaching was already in finding 15363. The offer details therefore extend this investigation and the saved article, not necessarily all prior public reporting.

## Findings Added

None. The live texts and all 17 evidence rows for these exact IDs were read:

| Finding | Profile / thread / lead | Claim type / confidence |
|---|---|---|
| 15450 | elephant-clipping / 206 / 94992 | paraphrase / high |
| 15451 | elephant-clipping / 206 / 94992 | paraphrase / high |
| 15455 | elephant-clipping / 207 / 94994 | paraphrase / high |
| 15456 | elephant-clipping / 209 / 94994 | synthesis / medium |

## Retained-source checks

| Checked object | Independent local check | Result |
|---|---|---|
| July archive JSON and decoded HTML | SHA-256 against minimized preservation; retained character count versus reported full count | Both hashes match; 190,967 of 190,967 characters retained |
| December archive JSON and decoded HTML | SHA-256 against minimized preservation; retained character count versus reported full count | Both hashes match; 194,799 of 194,799 characters retained |
| Both archived page bodies | All four stored offer quotations; weekly-update wording; title; actual Typeform hrefs | Exact matches |
| Wayback final replay URLs | Retained outputs and read-only inspection of `query_wayback.py` collection code | The collector stores `resp.url`, not merely the constructed request; final records retain 20250713202445 and 20251208104202 |
| Both current Typeform captures | SHA-256 against minimized preservation; independent public-schema decoding | Both hashes, titles and commercial quotations match |
| Legal-seller observation | Retained visible-text and legal-anchor cues | No named legal seller found in the reviewed page layer; this does not cover other documents or private contracting records |
| Five CPT archive captures | Wrapper and decoded HTML hashes; full-body length; visible-text reproduction; web href extraction; exact catalogue quotation | All checks match; 62, 72, 75, 75 and 75 retained web href rows respectively, including repeated navigation links |
| CPT archive index | Compare all five returned CDX rows with captured original/replay URLs and Agent B's query scope | All five returned captures represented; query used a content-hub prefix and digest collapse, not an inventory of every historical capture; all returned originals were the same content-hub page |
| Tutorial MP4 | SHA-256, byte length and `ffprobe` | `ec293cafebdee849d9e69c957c4d8c164140b5b71dba75d70345482ebd32c81c`; 128,113,981 bytes; 25.983333 seconds; H.264/AAC; 1080 × 1920 |
| Tutorial visuals and captions | Viewed durable `sample-captions.jpg` and `caption-strip-corrected.jpg`; independently decoded a full-duration 1 fps sheet | 26 populated visual frames and 104 populated caption samples; exact `super`, `yachts`, `some`, `billionaires`, `nosebleed`, `stakes`, `poker` and `games` observations confirmed |
| Candidate episode metadata | Independent decode of retained YouTube player response and source SHA-256 | Exact title `The Billionaire Table: My High-Stakes Poker Journey \| Sean Perry DSH #721`, video `4uYmzucv4WQ`, channel `UCe9PesyMmm3KWmIzsE4zkxA`, publish time `2024-09-14T05:00:08-07:00`, and quoted description phrase match |
| Exact-match acquisition failures | Read collector notes, caption-fetch code and finalized `media-access-observations.json`; checked caption and two audio-result files | All three result files are empty; the added record explicitly identifies the 200/0, 404/0 and 410/0 outcomes as collector transcriptions of tool stdout, not raw HTTP headers or an independent response capture |
| Agent A minimized manifest and report | Recomputed all five artifact hashes and final report hash | All match; report SHA-256 `12dcbaf309410808d866592f7ad40ee91e2b0a386159b2825af2352fb2408643` |
| Agent B durable manifest and final narrative | Recomputed the initial eight artifact hashes plus the finalized media-access record; read full report and final changes | All nine hashes match; report SHA-256 `df09e0499bfbec187c8d6fe2d973d8ae3c781c00096da473e2fffa524d0dbba2`; narrative retains sparse-archive, sampled-caption and unverified-candidate limitations |
| Saved article comparison | Read all 28 article paragraphs and verify original HTML SHA-256 | Comparison is supported only against this saved article, not universal novelty |

Sources checked locally: `/tmp/osint-v4NdHom5/a/serviuos-mentorship-july.json`, `serviuos-mentorship-december.json`, `typeform-july-application.html`, `typeform-application.html`, their minimized records in `a/reviewed/`, `/tmp/osint-v4NdHom5/report-agent-a.md`, the five `b/content-hub-YYYYMMDD.json` bodies, `b/wayback-content-hub.json`, `b/content-hub-reviewed.json`, `b/VIDPODCASTSERV1.mp4`, `b/episode-metadata.json`, `b/youtube-4uYmzucv4WQ.html`, the caption/audio-result files, the durable visual sheets under `investigations/elephant-clipping/artifacts/2026-09-02/provenance-wave-3/`, the saved Atlantic HTML, and the live database evidence rows. Raw session-bearing source files remain temporary. The reviewed source records have discovery URLs and hashes; the reviewer did not re-acquire them independently.

Local reproduction command:

```sh
ffmpeg -hide_banner -loglevel error -i /tmp/osint-v4NdHom5/b/VIDPODCASTSERV1.mp4 -vf 'fps=1,scale=180:-1,tile=4x7' -frames:v 1 /tmp/osint-v4NdHom5/qa-tutorial-1fps.jpg
```

The diagnostic output has SHA-256 `830a7cf503a6490122ff20a637b89343f5b16503dee61b204626632da7548e4a`. It supplies no new source and identifies no person from appearance.

## BLOCKING

None identified in findings 15450, 15451, 15455 and 15456 at their stated claim scope. This does not clear any future synthesis that turns an advertised library into a recovered campaign packet, an offered price into actual revenue, or the nominated DSH episode into a verified source/supplier relationship.

## SHOULD FIX

None outstanding in the four finding texts. Preserve both dates whenever summarizing the archive/form chain. The single normalized event date on finding 15450 represents the first of its two documented snapshots, not the date of every component claim. Finding 15455's September 2, 2026 event field is the review date; its actual archive dates remain in the detail and source references.

**Resolved handoff ambiguity:** the early temporary `b/sample-contact-sheet.jpg` contains four populated 1/7 fps diagnostic frames and padding. It was not the claimed 1 fps evidence or a durable/cited artifact. The collector identified the correct durable `sample-captions.jpg`; direct visual review shows 26 populated 1 fps frames plus four padding cells, matching the independent decode. No source or finding correction is necessary. Keep the authoritative artifact name and sampling command explicit in the handoff.

## Source diversity and skeptic disposition

The offer sources belong to one first-party promotional chain. The archived referring pages and the current application schemas are not independent corroboration of commercial performance. An archive corroborates what it retained at its capture time; it does not authenticate the truth of the promotion. The findings correctly retain that distinction. Two different form URLs with identical wording do not establish two separate products, operators, customer cohorts, or revenues. The five CPT snapshots are repeated observations of one site, not five independent sources. The tutorial and programme metadata are separately preserved sources for a candidate match, not evidence that CPT supplied or licensed the clip. Missing episode data remains an acquisition gap, not contradictory evidence.

**Final disposition:** all four findings and the substantive narratives in both finalized Agent A and Agent B reports are suitable for a carefully bounded working brief at their stated scope. There are **zero substantive blocking issues and zero outstanding should-fix issues** within this review. Agent B's status/section-heading normalization is complete. The finalized media-access record was read and its hash verified as `397c15dcee638053263ee08d808bd120d83a8bfa07975eec35c93de881dd084b`; its collector-transcription limitation is accurately stated. No overall wave or publication verdict is supplied.

Parent synthesis must retain these boundaries: the coaching offer is not actual revenue; the historical application links do not date current form content; five digest-collapsed archive results are not the complete site history; the training file is not a political packet; DSH #721 is a candidate rather than an authenticated source episode; and neither CPT production capacity nor a shared programme graphic establishes campaign commissioning, funding or control. Follow-up should target a publicly accessible exact source segment or a specifically attributable campaign artifact, not infer relationships from missing names in unrelated tutorial material.

## Learnings

- [Methodology] Archive-linked applications require separate dates for the historical href and the currently captured form schema; a stable destination URL does not authenticate its earlier content.
- [Source quality] Public coaching forms establish offered commercial wording, not completed sales, business revenue, delivered resources, or the legal identity of the seller.
- [Methodology] Verify that a replay collector records the final response URL and retains the complete body before treating a requested Wayback timestamp as the source timestamp.
- [Methodology] Name the authoritative contact sheet and sampling rate explicitly when a workdir also contains earlier diagnostic sheets with different frame rates and black padding.
- [Methodology] A public episode title and thematically matching description can nominate a candidate, but an exact source attribution still requires a matching audiovisual or transcript segment.
