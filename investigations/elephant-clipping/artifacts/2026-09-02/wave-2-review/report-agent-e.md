---
agent: cross_engine_discovery
track: E
target: Elephant Clipping cross-engine public discovery
profile: elephant-clipping
skill: search-all-sources
status: completed
date: 2026-09-02
counts:
  named_engines_attempted: 4
  named_engines_with_readable_serps: 2
  shared_query_serps_retrieved: 10
  shared_query_challenge_responses: 2
  shared_combinations_not_issued_after_challenge: 8
  supplementary_serps_retrieved: 4
  new_coded_profile_candidates: 2
  new_profiles_primary_metadata_verified_by_helper: 2
  findings_added_by_track_e: 0
  connections_added_by_track_e: 0
  new_leads_added_by_track_e: 0
  existing_lead_notes_added: 1
  searches_logged: 16
---

# Track E — actual named-engine comparison

## Key Discoveries

Actual public Bing results exposed two Instagram profile candidates absent from
the launch-wave 27-account sample: `ykpolitics` and `us_politicstoday`. Their
indexed snippets contain `ML-T0UJ` and `ML-EC19`, respectively. Both were routed
immediately to the distribution owner; the coordinator then assigned helper
`handle_triage_b` to verify the live profiles. Its direct unauthenticated
Instagram HTTP metadata independently confirmed both code/profile pairs, with
HTTP 200 and exact canonical URLs. This verifies public profile metadata, not
Monster Lab enrollment, human ownership, or campaign membership. The helper did
not verify a hydrated DOM, private-status field, or visible reels.

Bing and Brave each returned genuine, query-specific result pages for all five
shared requests. These were HTTP GETs to their named public interfaces, with the
requested query echoed in the page title and search field. No generic web-search
backend is represented as Bing, Brave, DuckDuckGo, or Yandex.

Query acceptance was not the same as strict query execution. Brave explicitly
removed operators for three of the shared queries and changed `Serviuos` to
`servicios` for another. Bing returned unrelated or off-domain results for four
queries despite the requested text in its title/search box. Consequently, these
pages do not establish exact-query absences from either index.

DuckDuckGo and Yandex presented human challenges. No challenge was answered,
bypassed, or retried through an alternate route. Their remaining four queries
each were not issued; neither engine has successful result coverage here.

## Shared Query Set

| Key | Exact requested query |
|---|---|
| Q1 | `site:instagram.com "ML-" politics` |
| Q2 | `"leaving a high earner with only fifteen percent"` |
| Q3 | `"Elephant Clipping"` |
| Q4 | `"Serviuos" site:drive.google.com` |
| Q5 | `"ClipIt" site:docs.google.com` |

## Sources Checked

All times below are September 2, 2026 UTC. Counts mean extracted primary organic
result blocks on the first returned page, not estimated index totals, all
sitelinks, relevant records, or independent sources. The `e-<engine>-qN.json`
files contain destination URLs, titles, snippets, requested query, echoed query,
interface, acquisition time, HTTP status, and raw temporary capture SHA-256.

| Engine/interface | Query | Time UTC | HTTP / blocks | Observed result and limit | Sanitized artifact |
|---|---|---:|---:|---|---|
| Bing public `/search` | Q1 | 16:47:27.231846 | 200 / 10 | Six baseline profile URLs; two new coded-bio candidates; one unrelated `ml__politics` reel and one weak non-coded profile result | `e-bing-q1.json` |
| Bing public `/search` | Q2 | 16:47:27.494746 | 200 / 10 | Definitions/uses of “leaving”; no requested caption exposed | `e-bing-q2.json` |
| Bing public `/search` | Q3 | 16:44:06.743209 | 200 / 10 | Animal/elephant pages, no operation-specific result | `e-bing-q3.json` |
| Bing public `/search` | Q4 | 16:47:27.735825 | 200 / 10 | Unrelated City-Data locality pages, outside requested Drive domain | `e-bing-q4.json` |
| Bing public `/search` | Q5 | 16:47:27.968840 | 200 / 10 | Other ClipIt/Klipit products; outside requested Docs domain | `e-bing-q5.json` |
| Brave public `/search` | Q1 | 16:47:27.288911 | 200 / 19 | Says operators were not applied because too few matches; unrelated ML/politics matches, no new coded bio exposed | `e-brave-q1.json` |
| Brave public `/search` | Q2 | 16:47:27.934926 | 200 / 20 | Same operator-removal notice; financial/high-earner pages, not the caption | `e-brave-q2.json` |
| Brave public `/search` | Q3 | 16:44:32.247387 | 200 / 3 | Atlantic seed, Shutterstock false positive, Jingletree apparent republication | `e-brave-q3.json` |
| Brave public `/search` | Q4 | 16:47:28.814575 | 200 / 11 | Explicit “Showing results for servicios”; unrelated Drive documents | `e-brave-q4.json` |
| Brave public `/search` | Q5 | 16:47:29.456768 | 200 / 16 | Operator-removal notice; unrelated clip/construction/software/resource documents | `e-brave-q5.json` |
| DuckDuckGo public `/` then owner-linked `/html/` | Q3 | 16:45:26.289731 | 202 / unavailable | Initial page linked ordinary non-JS search; that page required duck-image human challenge; stopped | `e-duckduckgo-q3.json` |
| Yandex public `/search/` | Q3 | 16:44:35.050728 | 200 / unavailable | “Are you not a robot?” SmartCaptcha; stopped | `e-yandex-q3.json` |

Probe times use the capture file's modification timestamp; subsequently
collected query times were recorded immediately before the request. No
second-page pagination, sign-in, proxy rotation, user-agent rotation, or paid
service was used. Ordinary cURL followed HTTP redirects and imposed a 20-second
timeout and 3 MB per-response bound.

The four original `web.run OPEN` attempts to the explicit Q3 search URLs all
returned renderer “not safe to open (non-retryable error)”; they yielded no engine
results and are not counted as engine coverage. An initial sandboxed Bing cURL
attempt failed DNS. The same bounded public GET succeeded after normal sandbox
network approval. This is a transport change, not an access-control bypass.

### Comparison and deduplication

The ten shared-query SERPs contain 119 distinct extracted destination URL
strings: 50 from Bing and 69 from Brave, with no literal URL overlap between the
two engines in this sample. This is a measure of the retrieved lists, not 119
relevant or independent records. At least one Brave Docs object appears in two
different views; these are one underlying document. Baseline Instagram profile
`/reels/` paths were deduplicated to the handle before novelty testing.

The only two high-priority account additions were Bing Q1 ranks 5 and 8.
Searches of the lead title/description/target fields found neither handle before
routing. The helper remains responsible for primary-source facts. A page
appearing in several engines would still be one source, and multiple reposts of
the Atlantic seed do not corroborate its underlying claims.

### Bounded supplementary queries

Before the coordinator's final no-expansion instruction, two additional queries
were started per accessible engine using the supplied CPT/poker context. They
are separate from the five-query comparison and no further queries followed.

| Engine | Query | Time UTC | HTTP / blocks | Result | Artifact |
|---|---|---:|---:|---|---|
| Bing | `"ClipIt" "Digital Social Hour"` | 16:48:47.198574 | 200 / 10 | Same ClipIt/Klipit homonyms as Q5; no conjunction established | `e-bing-extra1.json` |
| Bing | `"Serviuos" "Poker"` | 16:48:47.580210 | 200 / 7 | Unrelated commercial-property listings | `e-bing-extra2.json` |
| Brave | `"ClipIt" "Digital Social Hour"` | 16:48:47.152028 | 200 / 20 | Operators not applied; separate ClipIt homonyms and DSH sources | `e-brave-extra1.json` |
| Brave | `"Serviuos" "Poker"` | 16:48:48.086954 | 200 / 20 | Operators not applied; general poker pages | `e-brave-extra2.json` |

The current Track C owner received these DSH candidate destinations from the
Brave supplementary page: [Digital Social Hour](https://www.digitalsocialhour.com/),
[its Simplecast page](https://digital-social-hour.simplecast.com/),
[YouTube @DigitalSocialHour](https://www.youtube.com/@DigitalSocialHour),
[YouTube @DigitalSocialHourClips](https://www.youtube.com/@DigitalSocialHourClips),
and a [HappyScribe transcript index](https://podcasts.happyscribe.com/digital-social-hour).
These are scope-limited source suggestions for the existing CPT/seanmikekelly
question. The returned page did not establish a ClipIt/DSH relationship. No
identity, legal-company, financial, or campaign finding was added from them.

## Novel URLs and Primary-Check Ownership

| Destination | Search discovery / quotation | Novelty / current outcome | Owner |
|---|---|---|---|
| [@ykpolitics](https://www.instagram.com/ykpolitics/) | Bing Q1 rank 5; title “Political (@ykpolitics)”; snippet contains `ML-T0UJ` | Outside baseline 27; unauthenticated Instagram metadata independently confirms code, 16:50:39.755705 UTC, HTTP 200, exact canonical URL | Track D / coordinator's `handle_triage_b` helper; lead 94495 |
| [@us_politicstoday](https://www.instagram.com/us_politicstoday/) | Bing Q1 rank 8; title “Us Politics Today (@us_politicstoday)”; snippet contains `ML-EC19` | Outside baseline 27; unauthenticated Instagram metadata independently confirms code, 16:50:42.746810 UTC, HTTP 200, exact canonical URL | Track D / coordinator's `handle_triage_b` helper; lead 94495 |
| [Jingletree apparent seed republication](https://jingletree.com/inside-a-conservative-operation-to-hijack-your-social-media-feed-261971.html) | Brave Q3 rank 3; same article headline and same sampled snippet as Atlantic rank 1 | Newly returned URL, not independent underlying evidence; no primary-check commission warranted | Coordinator informed; not promoted |
| DSH public identity/transcript destinations above | Brave supplemental query, operators explicitly not applied | Useful only as candidate source locations for existing CPT question; no connection established | Track C `uploader_provenance`; owner notified |

Weak political-looking URLs `uspoliticslive` and `politics.gg` were not promoted
as coded-account candidates: the retrieved snippets did not expose an ML code or
an operation-specific bridge. The unrelated `ml__politics` reel is also excluded.
Cloud owner A was told that the two cloud queries produced no on-target artifact;
no irrelevant Drive/Docs documents were opened or copied into the evidence set.

## Findings Added (IDs)

None by Track E. Source ownership was respected: engine discovery did not
duplicate primary findings belonging to the account, cloud, merchant, or uploader
researchers. Exact search-trace candidate text was persisted as lead 94495 note
**12348** and read back from the database. See `e-routing-persistence.json`.

The tracker contains 16 search rows/history events from this track: 14 retrieved
SERPs and two challenge outcomes. Challenge `result_count` values are **NULL**,
not zero. `search_log` has no profile column; the existing lead and this report
carry `elephant-clipping` scope. The eight never-issued combinations are not
misrepresented as completed searches.

## Connections / Entities

None added by Track E. A public code-shaped snippet is not a public
account-to-platform enrollment record, a human-owner match, or evidence of a
funder. No funds, employment, commissioning, or payment conclusion follows from
these search results.

## Negative Results

- No requested exact caption or on-target campaign/cloud/merchant artifact was
  exposed in the retrieved first-page primary blocks.
- Most rare-name and exact-phrase requests were demonstrably rewritten, had
  operators removed, or returned results inconsistent with their filters. These
  are limitations of the observed results, not proof of absence from the index.
- DuckDuckGo and Yandex were unavailable behind challenges. No true zero-result
  page was retrieved from either.
- The supplementary CPT/poker terms did not expose a ClipIt/Serviuos-to-CPT or
  DSH connection. Same-page loose matches are not a relationship.

## Source Gaps

- Four of five intended queries remain unissued for each challenged engine.
- Brave's stricter “Search instead for” option was not followed during this
  bounded pass; its automatic spelling replacement is documented, not accepted
  as equivalent coverage.
- Bing's off-domain and unrelated responses could not discriminate non-indexing
  from ignored filters, query relaxation, or another result-serving behavior.
- Direct profile verification belongs to the helper, not to SERP snippet
  preservation. Search follower/post counts can be stale: Bing reported 9
  following for `ykpolitics`; direct metadata reported 10. The helper did not
  validate hydrated DOM, private-status, or reel visibility.

## Follow-Up Leads

Lead 94495 carries both newly discovered accounts. The helper completed the
direct metadata/code comparison; the distribution owner can determine whether a
bounded post comparison is useful. If added to the account census, mark the
verification layer as unauthenticated metadata and leave reel counts unknown.
Do not infer campaign membership or enrollment from the codes alone.

No new legal-company, financial, public cloud, or uploader lead was created:
the retrieved evidence did not support a nonduplicative commission in those
lanes. DSH source suggestions were handed to the existing uploader-provenance
owner without asserting the hinted connection.

## Learnings

- Named-engine attribution requires a real named-engine result page. An
  unspecified search backend and a failed renderer `OPEN` are not substitutes.
- Record the engine's spelling/operator notices as part of query provenance.
  Brave explicitly changed `Serviuos` to `servicios`; exact quotes alone did not
  prevent query relaxation. A matching page title is insufficient evidence that
  the strict query ran.
- Different indexes can add useful candidates: Bing exposed two new
  code-bearing profile snippets missed by the sample, while Brave's campaign
  name query mostly rediscovered the seed. Count relevant novelty, not raw
  result volume or cross-index repetitions.
- A challenged engine is unavailable, not empty. Stop without bypass; leave
  remaining query combinations unissued and store NULL result counts.
- Indexed profile snippets can lag live metadata even within a short comparison
  window; retain engine and primary observations separately instead of silently
  replacing the search evidence.
- Native browser discovery was already reported unavailable/hung by the prior
  worker. No CUA/native call was repeated here. Papercut **2517** records that
  existing discovery failure. Previously logged zsh/fnm startup friction was
  reused; clean non-login Bash avoided an unrelated startup side effect.

## Artifact and Execution Hygiene

All track outputs are under `/tmp/osint-ldT6picn/e-*`. Raw result-page HTML stays
temporary and must not be copied into a durable bundle: search click/session
parameters can be embedded in it. Sanitized JSON stores decoded destination
URLs, not Bing click URLs; incidental tracking parameters were removed while
public content selectors such as YouTube `v` and `list` were retained. Challenge
tokens/images and renderer session material are not included in this report.

The one-off `e-public-search-collector.py` was created only after direct probes
verified the public interfaces. It uses cURL with fixed bounds, stops on
unavailability, writes inert extraction artifacts, and logs actual attempts.
`--reparse-saved` only re-extracts existing local captures; it performs no network
request or search-log write. Both this collector and `e-register-routing.py`
passed `uv run ruff check`. No repository infrastructure, browser installation,
credential, login, target document, or external account was modified.

Validation read back all 16 exact query/source rows and matched each result
count to its sanitized artifact, including NULL for the two challenges. The
search-log IDs are 13450–13465. A targeted hygiene check found no Bing click
tracking, signed-download signature, access-token, or cookie-header strings in
the 16 sanitized query artifacts. Raw HTML was deliberately excluded from this
hygiene claim.
