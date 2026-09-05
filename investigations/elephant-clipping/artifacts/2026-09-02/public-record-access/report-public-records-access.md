---
agent: public_records_access
target: Monster Lab / ClipIt public documents, campaign records and payments
skill: pursue-lead
supporting_skill: search-all-sources
profile: elephant-clipping
status: completed_bounded_pass_leads_unresolved
findings_added: 2
finding_ids: [15444, 15445]
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 94310
related_lead_id: 94366
---

# Public-record availability check

## Key Discoveries

**The newly reviewed images are marketing testimonials, not exposed backend records or authenticated payment documents. This check recovered no actual campaign database record or payment ledger.**

The current [brand page](https://monsterlab.io/brand) explicitly embeds eleven payout-gallery PNGs. Three were downloaded and visually reviewed. One [image](https://monsterlab.io/results/result-10.png) labels a depicted **705 USDC** deposit as a “Political Payout of December”; another [image](https://monsterlab.io/results/result-20.png) presents a ClipIt card labeled **Political** with **$2,351** “Received Payment.” These are self-published testimonial claims, not independently authenticated payments, payer identities or a campaign ledger. The publisher could select or alter such screenshots. Their chat-style timestamps are not verified publication or settlement dates.

The same eleven paths were already in earlier retained HTML, as the coordinator independently checked. The images are **newly reviewed, not established newly published**. There is no preserved earlier image-byte comparison. Eight images remain unreviewed. The minimized exact source notes, response metadata and hashes are in `public-document-notes.md`; original PNGs and raw HTML remain in the temporary workdir only.

## Findings Added

| ID | Claim type / confidence | Scope |
|---|---|---|
| 15444 | paraphrase / high | Operator's public gallery presents a political-payout caption beside a 705 USDC completed-deposit depiction |
| 15445 | paraphrase / high | Operator's public gallery presents a ClipIt Political earnings card claiming $2,351 received |

Confidence describes the directly observed public content, not whether the depicted payment occurred. Both findings explicitly preserve that distinction, disclose single-source promotional provenance, omit incidental recipient display names, and link to lead 94366 / thread 206. Search checks found no existing finding for either exact caption. No entity or financial relationship was added.

## Fresh Sources Checked

| Source / exact scope | Result | Limit |
|---|---|---|
| `https://monsterlab.io/clipit` | HTTP 200 marketing/sign-up page; links only to brand, dashboard, privacy and terms | No campaign selector or record in returned HTML |
| `https://monsterlab.io/brand` | HTTP 200 brand intake/marketing page plus eleven explicitly embedded payout-gallery images | No form submitted; images are testimonials, not records from a queried database |
| `https://monsterlab.io/dashboard`, linked as Login | HTTP 200 HTML with “Loading...” | No browser rendering or authenticated request; neither anonymous dashboard availability nor denial established |
| Three gallery images `result-1`, `result-10`, `result-20` | All HTTP 200 actual PNGs; two political claims, one general testimonial control | Three of eleven sampled, not full-gallery review; no private IDs or omitted numeric paths guessed |
| `https://www.serviuos.com/clipit-mentorship`, exact previously public archived path | TLS certificate hostname mismatch; no HTTP response | No certificate-validation bypass; not a 404 or zero-content finding |
| Unified web: `"monsterlab-3496.appspot.com"`, `"monsterlab.io" "receipt"`, `"monsterlab.io" "campaign" "share"` | Empty results for all three new queries | Bounded index negatives, not resource nonexistence |
| Bing: exact bucket and domain+campaign+share queries | Two HTTP 200 result pages, ten extracted results each, all off-target | Requested query echoed, but returned content does not establish strict-query execution |
| Brave: same two queries | Two HTTP 200 result pages, twenty extracted results each | Both explicitly said “search operators were not applied”; generic Monster root appeared, no object/campaign/receipt selector |

The four alternate-engine pages yielded **60 extracted result entries**, not 60 relevant or independent records. No exact owner-published Firebase object URL or concrete campaign/share selector emerged. Result metadata and sanitized destination records are `public-bing-1.json`, `public-bing-2.json`, `public-brave-1.json`, and `public-brave-2.json`; raw SERP HTML stays temporary. Acquisition reused the earlier bounded SERP parser. The new one-off acquisition script `public-availability-check.py` passed Ruff and used normal anonymous GETs only.

## Prior Coverage Reused

- Previously recovered Docs guides, fifteen-file tutorial library, historical analytics/reward images and two TikTok/PIPO payment screenshots were not rediscovered or counted as new. Their wave-one/two manifests remain the source of scope and provenance.
- Existing Firebase configuration and invoice-client schema were not queried as data. Configuration is not a public-record authorization or an exposure finding.
- Earlier `/campaign/*` and `/c/*` Wayback negatives, campaign-focused URLScan HTTP 403 and `/share/campaign/*` Wayback HTTP 429 were not retried. The orphan older `[]` share-CDX file lacks a corroborating success log and is not treated as a successful zero.
- No new legal/payer selector warranted repeating FEC, Ohio campaign-finance, IRS 990, corporate-registry, EDGAR, LDA/FARA or government-award searches from earlier waves.
- The coordinator's separate retained-file audit found no concrete absolute Monster campaign/share URL or known-form Firebase object URL. Its scope was literal URL matching over 920 saved files, not 920 independent sources or all possible encodings.

## Disconfirmation and Negative Results

The explicit counter-test was that normal public entry points might expose only marketing rather than records. The fresh ClipIt and brand pages support that narrower description; the dashboard's returned HTML is only a loading shell, so it cannot support a login-denial conclusion. The three screenshot controls provide publisher claims only. No ledger, actual invoice, campaign row, account-to-campaign mapping, settlement authentication, payer or originating funds was recovered.

Firebase Storage/Firestore permissions remain **untested**. No bucket listing, private collection read, hidden endpoint reconstruction, credential, session, login, token, account, purchase, community join, contact, scan submission or write was used. No attempt was made to infer or guess campaign slugs or image paths absent from the public HTML.

## Lead Status and Follow-up

Leads **94310** and **94366** remain `in_progress`; notes were appended to both. The bounded availability check is complete, not the broader campaign/payment questions. The first worthwhile next source is a genuinely public campaign-specific link, voluntarily public original transaction/processor statement, or another primary record corroborating these testimonials. The eight remaining publisher gallery images are an unreviewed coverage gap, not an expectation that they contain bank records.

## Preservation and Hygiene

Promote only this report and `public-document-notes.md` to durable storage, with their hashes. Keep original PNGs, raw target HTML and raw SERPs in the workdir. Do not propagate incidental testimonial names/avatars or infer civilian identities. No such entity records were created. No sensitive account, wallet, invoice or transaction identifier was exposed in the three reviewed images.

Searches and availability checks were logged; one initial sandbox DNS failure was resolved by the normal network approval route, without changing endpoint. Papercuts **2590** (sandbox DNS) and **2591** (public-host TLS mismatch) were logged. Root owns final evidence review, preservation and Learnings ingestion.

## Learnings

- [Methodology] Ordinary owner-published marketing galleries can contain campaign-labelled testimonials even when search indexes and campaign route templates yield no records; distinguish newly reviewed assets from newly published material.
- [Source quality] A screenshot combining a political-payout caption with a deposit or earnings card proves what the operator publishes, not that the payment happened, who funded it or which campaign it belongs to.
- [Source quality] HTTP 200 dashboard HTML containing only Loading... establishes a shell response, not public data access or a login denial; actual database permissions remain untested.
- [Process gap] Requested search operators and result-page acquisition need separate coverage labels because Bing can echo exact requests while returning unrelated content and Brave can explicitly drop operators.
- [Friction] Restricted-shell DNS failed once and a current archived-hostname follow-up failed TLS validation; normal network approval resolved the former, while the latter remained unavailable without bypass.
