---
agent: wave3_budget_tools
target: "Elephant Clipping budgets and Monster Lab tool deployment"
skill: deep-investigate
status: completed
findings_added: 3
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_ids: [94996, 94998]
profile: elephant-clipping
---

# Agent D — budget evidence and tool deployment

## Key Discoveries

1. **The reviewed auto-submit client collects already-published posts for campaign submission.** It says an account is polled for new posts, submits them to the selected campaign and collects only posts published after activation. This is a narrower functional result than a social-posting bot. It does not establish runtime behavior, account use or other product capabilities. Finding **15447**.
2. **A separate public video-generation module explicitly advertises Political Clip mode.** Its changelog uses display date `May 21` and internal ID `2026-05-21`, describing AI conversion of long podcasts/interviews into vertical clips with hooks and captions. The rendering code displays the date field, without the year. Adjacent entries describe editing, branding, a monthly render cap, and watchlist processing of X-profile videos into History. An August 27 entry claims role-based sharing of uploaded sources across a clipping team. These are publisher/client claims, not an independently verified launch, named-campaign deployment, source rights, agency relationship or social publication. Finding **15449**.
3. **One externally hosted pseudonymous payment testimonial supplies a narrow lead, not corroborated settlement.** BlackHatWorld original post #3 is attributed to `Steeky` and displays July 4, 2026. It explicitly calls monsterlab.io ClipIt, describes earlier use on Whop and claims timely prior payments, while disclaiming use of the newer site. No amount, date of payment, receipt or political campaign is specified. Later quotations of this post are the same witness, not independent evidence. Finding **15448**, medium confidence and inference type because source independence and underlying payment remain unverified.

The two owner-published political payout graphics already recorded as **15444–15445** remain testimonials only. They were read and reused, not re-fetched or duplicated. The earlier **15404** screenshot set is not authenticated transactions. **15446** already establishes that normal logged-out dashboard entry leads to login; it was not repeated. No public campaign ledger, funded balance, campaign-specific processor receipt or comparable eligible-view/rate series was recovered.

## Findings Added

| ID | Type / confidence | Source | Boundary |
|---|---|---|---|
| 15447 | Paraphrase / high | Published auto-submit shared client | Client-described collection/submission of posts, not social publishing or observed use |
| 15448 | Inference / medium | Reader/indexed original BHW post | Claimed prior Whop payments; unverified alias and independence; no amounts or receipts |
| 15449 | Paraphrase / high | Published video-generation client and changelog | Political-specific capability claim; release date self-reported, campaign deployment unknown |

All are profile scoped, thread 206, and linked to the assigned leads. Exact primary text and retrieval caveats were persisted before this report. These are additions to this investigation, not assertions of first public disclosure.

## Connections Added

None. A forum ownership assertion was not adopted. Tool names, product modes, shared data storage and generic testimonials do not establish a legal relationship or account controller.

## Entities Registered

None. The evidence concerns existing Monster Lab / ClipIt records. `Political Clip` is a feature label, not a newly established company or campaign. The forum alias has not been resolved to a natural person or accepted as a verified counterparty.

## Negative Results

- Four Bing pages echoed the requested payout/nonpayment queries but returned generic ClipIt/Monster homonyms. Three ClipIt queries returned essentially the same broad destinations. This is no usable on-target testimony from those pages, not a strict-index zero.
- Brave's first query returned HTTP 429; three remaining queries were not issued. Yahoo's one compact query returned HTTP 500 with no body. Neither is a zero-result search. Prior DuckDuckGo/Yandex challenge routes were not retried.
- The public web lookup rediscovered the already-recorded Whop political earning-rate claim (**15382**). That historical offer cannot supply a matched date/campaign/rate basis for the article's February and August budgets. No budget-exhaustion arithmetic or sample-based upper bound was calculated.
- The only indexed Trustpilot review surfaced was a generic personal-information allegation without a payment amount, campaign or receipt. Direct retrieval was 403 and the reader gave a cache miss. No allegation was promoted as fact or nonpayment evidence. Automated scam-score pages were excluded as payment evidence.
- Literal case-insensitive searches for four drafting-residue fragments from **15401** returned zero matches across **30 successful captures representing 29 distinct successful JavaScript bodies**. The checked collection contains 31 retained files: one prior 9-byte `Not Found` response is excluded from substantive coverage, and prior/fresh 1824 captures have identical bytes. No evidence was deleted. This does not exclude other assets, server-side prompts or unrelated clipper tools.
- The public Discord Discovery page presents general community marketing, not a channel hierarchy, role roster or political campaign record. The reused invite response exposes the previously known rules channel. The public guide's proxy-support channel plus that rules channel do not establish channel adjacency or campaign deployment. No group was joined.

## Sources Checked

| Source | Command / scope | Outcome |
|---|---|---|
| Existing records | Tracker provenance, read-only finding details, lead notes, search_log, wave-two brief/manifests | Reused 15340, 15382, 15401, 15404, 15427 and 15444–15446; did not repeat known dashboard barrier |
| Bing public HTML | `collect-searches.py`: `"ClipIt" "Serviuos" payout`; `"Monster Lab" clipping payment review`; `"ClipIt" "Political" "paid"`; `"ClipIt" "unpaid"` | Four HTTP 200 pages, 10 extracted results each, off-target/broad queries; strict execution unknown |
| Brave public HTML | First same query only | HTTP 429; stopped, three unissued |
| Yahoo public HTML | One same exact ClipIt / Serviuos payout query | HTTP 500; stopped |
| Public web reader/search | Four-query batched discovery; BHW thread open, original-post permalink; Trustpilot open | BHW original post text available in reader/index; direct BHW 403; permalink cache miss; Trustpilot reader cache miss |
| Published static clients | `fetch-public.py`, nine explicit asset URLs across reused/current manifests | Seven HTTP 200 assets, two superseded content-generation filenames 404; no hidden-route guessing or runtime calls |
| Exact residue review | `preserve.py`: four fragments; 31 retained files, 30 successful captures, 29 distinct successful JS bodies | Zero literal matches in successful captures; one error artifact excluded |
| Discord public Discovery/invite | Explicit known Discovery URL; reused invite JSON | General public marketing and known rules channel only; no public channel map |

Initial Bing/Brave curl attempts failed local DNS resolution. A single approved-network retry reached the services, with the outcomes above. Those local failures are preserved separately, not counted as source negatives. HTTP status, capture time, hashes, requested/echoed query and effective-query uncertainty are in `d/public-evidence.json`.

## Source Gaps Identified

- **Money:** configured campaign budget, deposited funding, approved rewards, wallet release and external payout are still distinct and not reconciled. Genuine partly used funds remain a live explanation. Testimonials neither prove full-scale spend nor fictitious budgets.
- **Political software use:** the public `Political Clip` label is now documented, but no named campaign settings, production job, exact output provenance, enrolled account or source delivery chain is public in this sample. Caption residue does not identify its tool.
- **Chronology:** the changelog's self-reported date is not an independent first-publication date. Public archived first appearance of the exact route/client or dated tutorial can test it without invoking a private interface.
- **Public testimony:** the useful forum statement is third-party-hosted, but its author is not established independent of the business; no receipt or named political payment was linked.

## Follow-Up Leads Created

None; existing leads are sufficient and remain **in_progress**.

- **94996:** seek independently published original receipts or named campaign-specific rate/view/payment statements with comparable dates. Do not infer the missing money from showcase totals or generic complaint scores.
- **94998:** extend to publicly archived first appearances, dated owner tutorials and examples of `Political Clip` mode, then compare exact published outputs with campaign-specific instructions. Preserve the distinction between a feature claim and actual named-campaign use. Reuse this lead rather than creating a duplicate.

## Preservation and Review

### Comparison with the attached article

The complete 16,127-character text extracted from the attachment's article element was read and compared. The story already describes Gemini/ChatGPT idea generation, already-posted clips submitted for payment review, proxy guidance, repeated brief captions and unverified automated reach updates. **Generic AI assistance and the publish-then-submit workflow are not new details.** The saved article does not describe the named `Political Clip` client mode, its changelog dating, the particular auto-submit client's after-activation condition, or integrated watchlist-to-History clipping/source-sharing functionality. Those are specific additions relative to this saved version, not established worldwide novelties or proof of campaign deployment. Reproducible literal checks and source hashes are in `d/article-comparison.json`.

Manifest: `/tmp/osint-v4NdHom5/d/MANIFEST.md`. Inert bundle: `/tmp/osint-v4NdHom5/d/public-evidence.json`, SHA-256 `f7cc79d2eb4510179c3e3574d6ea32b57010ed96b700b29b79706bfceceed5d9`.

The actual BHW reader response is `/tmp/osint-v4NdHom5/d/bhw-reader-response.json`; it includes acquisition request/time and was sent to the parent and independent reviewer. Direct-response failure and indexed-reader availability are not conflated. Raw HTML, scripts, irrelevant search results and the full forum rendering are temporary; the inert bundle preserves relevant quotes, offsets, scope and hashes. The parent owns durable-copy review, final audit, learning ingestion and the single post-wave auto-lead scan.

## Learnings

- [Methodology] Auto-submit can mean polling already-published social content for reward submission; generation, source sharing, submission and social publication must be tested separately.
- [Source quality] A dated changelog entry has at least three dates: its internal ID, the date text the client displays and the independently observed publication time; this record establishes only the first two claims plus current availability.
- [Source quality] A pseudonymous post on another host is not automatically independent payment corroboration, and quoted repetitions of that post are still one provenance chain.
- [Methodology] Public dependency manifests can safely resolve stale static filenames; an earlier 404 is not a missing feature when a current explicitly linked asset is available.
- [Friction] Papercut 2607 records this agent's use of a rejected legacy `web` source token; the unsaved record was retried with canonical `web_search`, exact source URL and retrieval limitations, and the papercut was resolved after readback without changing repository code.
