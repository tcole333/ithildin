---
agent: uploader_provenance
target: "Jules Katz; Benjamin Goodman; Jack O'Hara — uploader/content-supply attribution"
skill: investigate-person
additional_skill: pdf
status: completed_bounded_pass
lead_id: 93835
lead_disposition: blocked
profile: elephant-clipping
date: 2026-09-02
findings_added: 4
finding_ids: [15424, 15425, 15431, 15434]
connections_added: 0
entities_registered: 0
leads_spawned: 0
descendants_completed: [uploader_legal]
papercut_ids: [2497, 2519]
descendant_papercut_ids: [2499, 2501, 2504, 2507]
descendant_learning_ids: [2509, 2510, 2511, 2512, 2513, 2514, 2515]
---

# Track C: public production evidence, not uploader authentication

## Outcome

This pass found an exact dated public video credit linked from O'Hara's professional profile, a more detailed CPT/podcast production self-description, a 2023 Enclave event association, and a public CPT sponsor deck advertising interview assets for sponsors' social channels. It did **not** authenticate any of the three reported Google uploaders, any personal-versus-corporate account transition, political commissioning, or campaign payment. Lead #93835 is blocked at those missing primary artifacts, not completed or rejected.

The strongest cross-track candidate is narrower than authorship: a blue circular-arrow/clock-hand logo in Track A's public tutorial sample is consistent with the Digital Social Hour branding on the CPT deck. Both agents visually compared the graphics; no face identification was attempted. This is a medium-confidence partial-brand comparison, not an exact episode match, uploader attribution, client relationship, or proof that CPT supplied the sample. Public podcast reuse remains an alternative. Root owns any cross-lane synthesis finding.

## Key Discoveries

### 1. O'Hara: exact public content credit

The public [O'Hara professional profile](https://www.linkedin.com/in/jack-o-hara-7b35a9157) includes a first-person wrestling/media appearance and the public [shortlink ga_59JCi](https://lnkd.in/ga_59JCi). Its logged-out landing identifies [YouTube video QFNVAo4Tqzs](https://www.youtube.com/watch?v=QFNVAo4Tqzs), titled *1 WWE Hater vs 10 WWE Superfans (feat. Maven Huffman)*. The publicly retrieved video metadata identifies the CLASH channel (`UCE8Iv52JJl_OpW-4yv95TXg`), publication timestamp `2025-09-19T09:00:48-07:00`, and a description credit naming Jack O'Hara with the public handle `jackoharatv`.

Finding **#15424**, paraphrase/high, preserves the exact chain. This identifies a conventional public media credit, not ownership of the channel or an editing/production job that the video does not specify. Track D received the video ID and found no overlap in its sampled Charlie Kirk or congressional/gender-policy material. The exact video was retrievable directly even though the search index did not return it.

Reviewed artifact: `c-reviewed-jack-video.json`. Raw public YouTube HTML SHA-256: `26fe32421841ee89fcf6f09a6c1fbeea1d5661872f84b739f7a6ace9d9439270`. Acquisition timestamp recorded from download mtime: `2026-09-02T16:32:21Z`. Reviewed output excludes signed media URLs, cookies, platform nonces and unrelated credits.

### 2. O'Hara: the professional production remit is broader than poker clips

The public search-index rendering of the same profile describes producing shows for Paulo Costa and the Chrisley family after a July 25 CPT event, with an August 30 Invitational VIII still forthcoming. Other visible activity recruits an in-office team for three weekly podcasts, thumbnails/graphics and daily social posts, plus short/longform and livestream editing across YouTube, Instagram, TikTok and X.

Finding **#15425**, paraphrase/high, records only that self-description. It does not give the undated activity an exact timestamp. CPT's indexed first-party event listing places the cited event sequence in 2025, but the live content-hub page returned 404. Its detail was audited and corrected to make that cached/live distinction explicit. No new exact job title or political work is inferred from these duties.

### 3. O'Hara's public Enclave association predates the CPT joining post

A directly accessible [LinkedIn activity7091891452812685313](https://www.linkedin.com/posts/jack-o-hara-7b35a9157_what-an-amazing-experience-at-allegiant-stadium-activity-7091891452812685313-WhWI) has public structured `datePublished` of `2023-07-31T21:24:43.304Z`. In an Allegiant Stadium/Manchester United event post, O'Hara thanks Blake Wynn and Enclave & Key for having him.

Finding **#15434**, paraphrase/high, is an earlier dated **association**, not an earlier employment start. It does not contradict his January 2025 CPT joining announcement. The source says nothing about payment, production assignments or political material. Selected metadata and quote: `c-reviewed-jack-2023-post.json`; raw-page SHA-256 `ceeb0b403340e1e4e1ae6da42c31a27efdb170575acc12d30874c812e20c2f20`.

### 4. CPT publicly advertises sponsor-social interview assets

The 27-page [Celebrity Poker Tour Overview 2025 PDF](https://promosocial.com/wp-content/uploads/2025/01/Celebrity-Poker-Tour-Overview-2025.pdf) has a page26 Digital Social Hour integration offering, including: “HOST INTERVIEWS WITH TALENT TO POST TO YOUR SOCIAL MEDIA”. Page27 names Blake Wynn as CEO/founder and uses an Enclave business contact. Neither all-page extracted text nor visually checked pages26–27 names Katz, Goodman or O'Hara.

Finding **#15431**, paraphrase/high, preserves this background/control artifact. The page26 and page27 quotations are now separate page-specific evidence rows, corrected through the audit interface; they are not independent sources. The deck's public hosting at PromoSocial establishes where this copy was retrieved, not a contractual affiliation. No delivered service or political campaign role is inferred.

PDF SHA-256: `f723c847f76835d450d1c2f308530c525ba1e988eb14b7cd46401b22fc5f53f3`; 14,392,832 bytes; observed `2026-09-02T16:33:42Z` from download mtime. Editable metadata identifies Author Brock Prince, Creator Canva, Producer PassportPDF, creation `2025-01-12T20:27:38Z`, modification `2025-01-12T20:27:01Z`. These metadata fields do not prove authorship or original public-posting date. The PDF skill prompted both full-text extraction and visual verification; the latter exposed the useful explicit branding.

Reviewed artifact: `c-reviewed-cpt-deck.json`. Visual checks: `c-cpt-overview-integration.png` and `c-cpt-overview-contact.png`. The named commercial contact and Digital Social Hour branding were sent to Track B; no new corporate ID/legal name emerged.

### 5. Cross-lane programme-brand candidate, not a person bridge

Track A's public ClipIt-linked *10 Clipping Videos (24hr challenge)* sample `VIDPODCASTSERV1.mp4`, Drive file `1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE`, has a thumbnail at `/tmp/osint-ldT6picn/a-thumbnail-edited.jpg`. Its background shows a blue open-circle/lower-right arrow, white clock-hand arrows and obscured adjacent text. CPT deck page26 displays the same distinctive shape with the full Digital Social Hour title. A and C independently inspected these graphics and judged them consistent, at medium confidence because the sample title/brand text is only partial.

The sample's caption “Poker” is not the attribution evidence; the graphic comparison is. The deck also displays `seanmikekelly` on interview examples, but that handle was **not** independently read in the sample. No person in either image was identified by appearance. The comparison does not establish a shared client, contractual content-supply chain, or one of the three uploaders. Keep independent public reuse and authorized client supply as unresolved alternatives until an exact episode, credit or file record discriminates them.

## Role Resolution and Prior Knowledge Reused

| Person | Primary public support | Remaining boundary |
|---|---|---|
| Jules Katz | Existing #15375: public professional profile lists Celebrity Poker Tour | No independently visible exact title or employment dates; the article's chief-of-staff description remains reported, not newly verified |
| Benjamin Goodman | Existing #15374: public professional profile lists Enclave & Key | No independently visible exact title/dates; VP Operations appears in commercial directories, which are not primary corroboration |
| Jack O'Hara | Existing #15373: January2025 public CPT Head of Media/Studio Production joining announcement; new dated media credit and earlier event association | Professional identity/role support does not authenticate a Google uploader, file authorship or political client |

Current commercial directory listings put Veronica Childs in the chief-of-staff role. This may reflect turnover, stale data or a different scope; it does not disprove the article's historical claim. The prior sampled Enclave About archives did not list these three; that page-level absence is not an employment negative. No common-name profile in politics, finance, music, property or unrelated production was merged into the investigation.

The Clark County/USPTO baseline remains unchanged: Enclave & Key is a DBA of B WYNN SPORTS LLC, and CPT is a same-LLC brand/mark, not a separately established subsidiary. Track B owns corporate/finance persistence. No new organizational role was registered from a video credit, event invitation, fuzzy candidate or promotional deck.

The Atlantic is secondary reporting. This pass does not upgrade its uploader assertions to primary facts or treat unchallenged statements as admissions. Previously recorded denials/responses remain intact, including Enclave's description of routine/lawful work, Wynn's assertion of inaccuracies, and Turning Point's reported lack of familiarity. No outreach occurred.

## Findings Added

Four: **15424, 15425, 15431, 15434**. All are `paraphrase`, confidence `high`; none is marked confirmed. Provenance exports: `c-provenance-{15424,15425,15431,15434}.json`. #15425 detail and #15431 page quotations were refined through audited tracker commands. Findings reference lead93835 and profile elephant-clipping.

Zero new connections, entities, organizational roles, career arcs or leads. No merchant/funding edge. No dedicated biography files were warranted. Descendant `uploader_legal` completed with zero findings/connections/entities/leads; its entire report was read and its coverage is merged below. There is no uncollected descendant work.

## Negative Results

- No independently attributable Google Docs artifact for any of the three names. Prior same-day exact Google Drive name negatives were reused; new uploader-specific variants and known public professional-selector searches found no named uploader/file bridge. This is an indexed-public visibility result, not proof that files never existed.
- No exact dated primary Katz/Goodman title history. Their exact LinkedIn Wayback scopes returned empty snapshot lists; O'Hara's archive call failed503 and is unavailable, not zero.
- No exact political-production match from bounded O'Hara/Candace, Charlie Kirk, Benny Johnson, Tulsi or Steve Wynn library searches. Ordinary OShow/wrestling sources were not turned into political evidence.
- No attributable court/public-corpus bridge. Katz/O'Hara professional-context RECAP queries returned0/0. Goodman's broad query returned five old bankruptcy service/creditor lists; requiring exact company phrases returned0/0. Bulk unrelated address lists were not downloaded for biography collection.
- Exact merchant selectors `monsterlab.io`, `serviuos.com` and `acct_1TCPzsEBSSLjbpgL` each returned0/0 RECAP results. The result was sent to Track B; no further court expansion.
- LittleSis returned zero entities for each full name. ICIJ returned only fuzzy candidates, all `match:false`, none professionally attributable. No node/relationship traversal or identity merge followed.
- No relevant publicly indexed DocumentCloud/MuckRock artifact. No authoritative Nevada local docket/recorder negative can be claimed: the catalog/sidecar lacks the requested covered scope.

## Sources Checked

Artifact names are relative to `/tmp/osint-ldT6picn/`. `c-search-ledger.json` contains 24 newly logged normalized scope rows, including acquisition and archive failures. Those scope summaries are explicitly not represented as verbatim original query strings. `c-legal-coverage.json` has descendant exact supplemental scopes and hashes for30 JSON artifacts. Repeated sources across web queries are redundancy, not corroboration.

| Source / coverage state | Tool or scope | Output artifact(s) | Result / limits |
|---|---|---|---|
| Existing DB and intake / reused | Lead93835, findings15373–15375, prior Enclave report and archive review | `c-prior-{jules,ben,jack}.json`, prior workdir report | Role baseline reused; no duplicate role findings |
| Public professional web / newly checked | Three names with Enclave/CPT, titles, dates and professional portfolio selectors | `c-web-role-search-{1,2,3,4,5}.json`, `c-web-last-role-check.json` | Primary profiles plus commercial discovery pointers; no Katz/Goodman title/date resolution |
| Public production websites / newly checked | O'Hara handle, OShow, sports-publisher/podcast pages, CPT shows | `c-web-professional-sites.json`, `c-web-professional-sites-2.json`, `c-web-production-search-1.json`, `c-web-jack-handle.json` | Conventional public work/control artifacts; podcast directory locale is not a UK tie |
| Google public index / new and reused | Exact three names on docs.google.com; uploader-specific Google/Drive variants; prior exact Drive negatives reused | `c-web-docs-search.json`, `c-web-uploader-identity-search.json`, `c-web-social-roles.json` | No attributable named uploader; relaxed-query unrelated results excluded |
| Political/source-library index / newly checked | O'Hara with reported political subjects and exact public professional selectors | `c-web-political-producers-1.json`, `c-web-source-library-check.json` | No exact political asset; latter found the2023 professional event post |
| Enclave/CPT first-party pages / mixed | Public about/home/content-hub opens | `c-web-firstparty-open.json`, `c-web-cpt-pages.json`, `c-enclave-about.html`, `c-cpt-about.html`, `c-cpt-home.html` | Enclave curl gave Wix shell, web403; CPT current about lists founders; old .org host gives lander script; content-hub404. None is a no-employment result |
| Public LinkedIn posts / retrieved | Exact joining activity and2023 activity7091891452812685313 | `c-web-cpt-pages.json`, `c-reviewed-jack-2023-post.json` | Direct public posts useful despite profile429/redirect limits |
| Public YouTube/shortlink / retrieved | `ga_59JCi` → `QFNVAo4Tqzs`, public watch and oEmbed | `c-reviewed-jack-video.json`, `c-jack-content-link.html`, `c-jack-youtube.html`, `c-jack-youtube-oembed.json` | Exact public named credit; no campaign match. `c-web-jack-artifacts.json` retains web-fetch failures preceding successful direct acquisition |
| CPT sponsor PDF / retrieved | Public URL, `pdfinfo`, `pdftotext`, pages26–27 rendered and visually checked | `c-reviewed-cpt-deck.json`, `c-cpt-overview-2025.pdf`, `.txt`, two page PNGs |27-page public marketing artifact; metadata editable; hosting is not affiliation |
| Wayback / mixed | `query_wayback.py snapshots` for exact profile wildcard scopes | `c-wayback-jules.json`, `c-wayback-benjamin.json`; failure recorded in ledger | Two empty lists; Jack503/no file. Reused prior Enclave snapshots rather than rerunning |
| CourtListener RECAP / newly checked | `query_courtlistener.py recap-search` exact person + professional context, limit20 | `c-legal-recap-{katz,goodman,goodman-refined,ohara}.json` |0/0 except broad Goodman5/5 bulk lists; exact refinement0/0 |
| CourtListener merchant selectors / newly checked | Exact public domain/account phrases, limit20 | `c-legal-recap-{monsterlab,serviuos,account}.json` | Each0/0; not merchant clearance; prior exact B Wynn/Enclave legal negatives reused |
| LittleSis / newly checked | `query_littlesis.py search NAME --output FILE` | `c-legal-littlesis-{katz,goodman,ohara}.json` | Each zero; selective public network database |
| ICIJ / newly checked | `query_icij.py search NAME`, all types then Officer-only | `c-legal-icij-{katz,goodman,ohara}.json` and `-officer.json` |25 fuzzy candidates per request, no accepted match; bounded reconciliation is not exhaustive absence |
| Nevada court catalog/sidecar / unavailable | `query_state_courts.py sources/search --jurisdiction 32` | `c-legal-state-sources-nv.json`, `c-legal-state-katz.json`, Goodman/O'Hara `-serial.json` | No cataloged Nevada coverage; final local_scope_not_covered, not zero dockets. Serial rechecks resolved misleading lock state |
| Recorder/court planner / planned only | `public_records_search_plan.py NAME --related-entity 'Enclave & Key' --related-entity 'Celebrity Poker Tour' --jurisdiction 32` | `c-legal-plan-{katz,goodman,ohara}.json` | Catalog-wide/national routes, no recorder query templates; no residential selector supplied |
| DocumentCloud/MuckRock / indexed web only | Exact names and three merchant selectors on public collection hosts | `c-legal-web-corpora-1.json`, `c-legal-web-corpora-nv-2.json`, `c-legal-web-refinement-4.json` | No relevant indexed document; not an authenticated corpus sweep |
| Official Nevada/Clark and ICIJ indexed web / checked | Professionally constrained names; merchant phrases on ICIJ domain | `c-legal-web-nv-icij-3.json` and related corpus/refinement files | No relevant match; unrelated parcel map not followed and incidental PII sanitized |
| Cross-track tutorial thumbnail / delegated acquisition, C visual review | Exact A file1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE, explicit-logo comparison only | A's `a-thumbnail-edited.jpg`; C's deck p26 PNG | Partial DSH brand consistency, medium; no exact source episode or person identity |
| Finance/corporate/government sources / delegated or inapplicable | Registry, SEC, FEC,990,LDA,FARA,UCC, sanctions/LEI | Track B/prior wave | No new legal selector; avoid duplicate corporate persistence |
| Configured profile/private corpus / inapplicable | Profile corpus_tools:0; no target-authenticated content | Active profile and launch mandate | No unrelated Epstein/private/breach-personal corpus searches |
| UK Companies House / not triggered | No attributable UK professional/company selector | Scope assessment | A podcast site's UK locale was not treated as the person's jurisdiction |

## Source Gaps and Followups

1. A public Google source file with attributable creator/uploader metadata, exact source filename, dated export or a public work credit tied to a supplied artifact would permit reopening #93835. A display name or company job alone is insufficient.
2. Exact primary title/start/end dates for Katz and Goodman remain unverified. Directory disagreement should not be resolved by selecting the most convenient title; a dated company announcement or public professional history is needed.
3. The Digital Social Hour candidate can be tested with a readable programme/episode title, caption transcript, or exact public video identifier from the tutorial sample. Do not identify faces or infer a client chain from the logo alone. A owns the sample retrieval; D owns political distribution comparisons.
4. Court/recorder coverage is incomplete. A new relevant contract, party name or docket would justify a precise public query; repeating broad common-name searches would not solve the uploader question.
5. Retain ordinary public reuse, authorized client production and political commissioning as distinct explanations. These professional controls do not establish which applies to the political clipping folders. Reported denials remain preserved.

No new followup lead was created because these are unresolved portions of93835 and cross-track work already assigned. No contact, login, membership request, checkout/payment, access request, private-ID enumeration, active scan or credential use against targets occurred. Authorized read-only public OSINT API queries were used by the legal descendant.

## Learnings

- [Methodology] A public profile-to-shortlink-to-video chain can authenticate an exact conventional media credit even when search indexes miss the video; it still does not authenticate a similarly named Google uploader or a political job.
- [Source quality] Distinguish page-specific absence, acquisition failure and actual zero query results. Here a CPT content-hub404, LinkedIn profile429, Wayback503 and missing Nevada catalog coverage all required different labels from no-match searches.
- [Methodology] Rendering a sponsor deck exposed a programme logo unavailable from the extracted text alone. Matching explicit graphics is a useful content-source candidate, but an obscured partial logo cannot establish a person, client, contract or exact episode.
- [Source quality] A dated thank-you post proves an earlier public association, not an employment start. Editable PDF Author/CreationDate metadata and a hosting path similarly require narrower claims than authorship or partnership.
- [Friction] Papercut2497 logged the repeated fnm startup permissions issue; bash without login avoided further noise. Papercut2519 logs lead_tracker show labeling a successfully saved blocked lead as results unavailable. No infrastructure changes were made.
- [Process] Legal-child learnings2509–2515 were already ingested from c-legal-report.md. The child report is fully collected; do not re-ingest those same paragraphs. Root can ingest this report's distinct learnings once.

