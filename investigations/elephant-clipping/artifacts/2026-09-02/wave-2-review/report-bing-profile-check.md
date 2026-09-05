---
agent: manual-bing-profile-check
target: "@ykpolitics and @us_politicstoday"
skill: "none — bounded manual verification"
status: completed_bounded
profile: elephant-clipping
lead_id: 94495
thread_id: 210
counts:
  candidates_checked: 2
  first_party_metadata_confirmed: 2
  public_timelines_verified: 0
  findings_added: 2
  connections_added: 0
  entities_added: 0
---

## Key Discoveries

Both Bing-discovered bio/code candidates are independently corroborated by publicly reachable first-party Instagram metadata. They are **not** two additionally verified public timelines: the browser surface was unavailable, and the static HTTP responses did not expose a current `is_private` value, hydrated DOM, or recent reel layer.

| Candidate / canonical URL | First-party display name | Literal bio shown in description metadata | Numeric profile-route ID | Metadata followers / following / posts | Capture completed UTC | State established |
|---|---|---|---|---|---|---|
| `https://www.instagram.com/ykpolitics/` | Political | `ML-T0UJ` | `46452494248` | 3 / 10 / 8 | `2026-09-02T16:50:39.755705Z` | Unauthenticated HTTP 200; exact canonical URL and profile metadata reachable. Current timeline privacy unknown. |
| `https://www.instagram.com/us_politicstoday/` | Us Politics Today | `ML-EC19` | `12005255780` | 22 / 15 / 32 | `2026-09-02T16:50:42.746810Z` | Unauthenticated HTTP 200; exact canonical URL and profile metadata reachable. Current timeline privacy unknown. |

The numeric IDs came from the public initial-route `page_logging.params.profile_id` data, not a private API. Metadata counts are access-time source representations and may be cached; they are not current hydrated counts or verified reach totals. No reel count was retrieved. The `posts` values above are profile-description metadata only.

Source E owns discovery. Its exact Bing query was `site:instagram.com "ML-" politics`, from `https://www.bing.com/search?q=site%3Ainstagram.com+%22ML-%22+politics`, acquired at `2026-09-02T16:47:27.231846Z` in `e-bing-q1.json`. `@ykpolitics` was rank 5 and `@us_politicstoday` rank 8. Bing showed 9 following for `@ykpolitics`; the later first-party response showed 10. The index's underlying snapshot date is unknown, so this difference is not presented as a measured follow event.

## Findings Added

- **#15441** — first-party public profile metadata confirms `@ykpolitics` and literal bio code `ML-T0UJ`.
- **#15442** — first-party public profile metadata confirms `@us_politicstoday` and literal bio code `ML-EC19`.

Both are `direct_quote` / `confirmed` only for the literal first-party metadata facts, scoped to profile `elephant-clipping`, lead `94495`, thread `210`. Both retain explicit privacy, count, enrollment, ownership, payer, and campaign-participation limits. They were read back after insertion to verify persisted source quotes and scope.

## Connections/Entities

None added. No ownership, political funding, payer, or Monster enrollment edge was created.

## Negative Results

- Exact handle searches in profile findings returned zero prior records before insertion (`f-existing-ykpolitics.json`, `f-existing-us-politicstoday.json`).
- Both numeric IDs returned zero matches in existing profile finding detail and global entity notes.
- A literal search for both handles and both numeric IDs across available prior-wave CSV/JSON/Markdown records in `/tmp/osint-E6iGgeNz` and the durable `investigations/elephant-clipping/artifacts/2026-09-02` tree returned no match. This checks available ID-bearing records, but cannot exclude a rename where an earlier sampled account's numeric ID was never preserved.
- No current private/public timeline state, live DOM count, or latest reel IDs were retrieved. These are untested fields, not negative evidence that posts or a public timeline do not exist.

## Sources Checked

| Source / command | Scope | Artifact | Result and coverage limit |
|---|---|---|---|
| Profile guidance and manual wave-two plan | Current scope, evidence rules, source ownership | `investigations/elephant-clipping/AGENTS.md`; `research-plan-wave-2.md` | Read and applied; active profile verified as `elephant-clipping`. |
| `check_searched(exact_profile_url, "official_website")` | The two exact URLs | Search-log preflight | Neither had a prior same-query/source row; both successful checks then logged with result count 1. |
| Source E's Bing output, reused | Exact query; ranks 5 and 8 only | `/tmp/osint-ldT6picn/e-bing-q1.json` | Discovery provenance retained; no additional engine searches performed here. |
| `cua.getBrowser({url: exact_profile_url})` | Attempted safe unauthenticated browser path | Tool result | No browser available. No login, challenge, or permission bypass attempted. |
| `curl -L --max-time 30 -A 'Mozilla/5.0' exact_profile_url` | Two public profile HTTP GETs | `f-ykpolitics-raw.html`; `f-us_politicstoday-raw.html` | HTTP 200; effective and canonical URLs unchanged. Raw HTML remains temporary. |
| `uv run python /tmp/osint-ldT6picn/f-extract-public-meta.py` | Allowlisted metadata and public profile-route IDs only | `f-ykpolitics-metadata.json`; `f-us_politicstoday-metadata.json` | Sanitized artifacts omit cookies, signed media URLs, session values, and unrelated JSON fields. |
| `uv run ruff check /tmp/osint-ldT6picn/f-extract-public-meta.py` | Extraction script | Tool result | Passed. |
| Findings search, numeric-ID SQL, and literal prior-ledger `rg` | Handle and rename-aware dedup | `f-existing-*.json`; prior-wave records | No existing handle or available-ID collision found. |

Raw-response SHA-256:

- `@ykpolitics`: `bf1f3520d4abd33dc809a8684fb1f0f81d9f7e12b979fbc9e616d221eaecf1d0`
- `@us_politicstoday`: `badfbd5a55882f3f77c01ac67dc40274940a9a4f2fd740372318efa2c37867dd`

## Source Gaps

The unavailable browser prevented confirmation of the current complete rendered bio, hydrated metrics, `is_private` state, and reel grid. Static description metadata independently corroborates the literal codes, but does not resolve those gaps. The public `ML-*` code does not itself prove Monster Lab enrollment, account ownership, a common operator, payment, or political sponsorship.

## Follow-Up Leads

No new lead was created. Lead #94495 received a note with both finding IDs, exact numeric IDs, dedup scope, and the metadata-only caveat. It remains open for the broader census owner; this bounded two-profile check does not close it. A future public-browser check may resolve privacy and grid fields when the surface is available, without login or bypass.

## Learnings

- Engine diversity produced two useful exact-profile selectors, but each still needed first-party verification. Search-result counts are not current profile metrics.
- Treat public metadata and a verified public timeline as different coverage states. An HTTP 200 profile response can confirm a literal bio code without establishing current privacy or exposing any reels.
- Numeric-ID dedup reduces rename-driven double counting; report the limit when earlier account records omitted numeric IDs.
- Papercut #2521 records repeated `fnm_multishells` permission noise in noninteractive shell commands. Papercut #2523 records raw-JSON exact-quote validation rejecting decoded strings containing escaped quotation marks. Neither was expanded into an unrelated fix during this bounded task.
