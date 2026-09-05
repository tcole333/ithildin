---
agent: agent-b
target: ClipIt / Monster Lab legal merchant and authenticated campaign payments
skill: deep-investigate
supporting_skill: trace-entity
profile: elephant-clipping
status: partial_identity_and_payments_unresolved
findings_added: [15428, 15432]
findings_count: 2
entities_registered: [7126]
connections_added: 0
leads_spawned: []
leads_worked: [94300, 94308, 94366]
lead_status: in_progress
direct_search_checks_logged: 18
child_report: b-child-checkout-crosscheck.md
papercuts: [2498, 2503, 2505]
---

# Merchant and finance — wave two

## Key Discoveries

The legal company behind ClipIt/Monster Lab and an authenticated campaign-payment chain remain unresolved. This pass adds a useful **disconfirmation**: a tempting historical Stripe merchant display is not a defensible identity bridge. It also identifies the exact fields of the platform's user-specific invoice view, without accessing any invoice.

### 1. The Kreator checkout link is earlier creator-course material, not a resolved ClipIt merchant

The [December 11, 2023 Creatorkarro course archive](https://web.archive.org/web/20231211115349id_/https://www.creatorkarro.com/course) contains the exact public payment link `https://buy.stripe.com/8wM6rnbnCeaYbAIaFZ`. This precedes the [April 2, 2024 Serviuos AI Profit archive](https://web.archive.org/web/20240402195723id_/https://www.serviuos.com/) carrying that link. The earlier course uses it on 33 curriculum anchors and 13 purchase/price anchors. The Serviuos page retains it on 18 curriculum anchors, while its prominent AI Profit purchase buttons use a different link. Both retain Creatorkarro footer identifiers. Counts are HTML anchors, including responsive duplicates, not unique visible buttons or customers.

The questioned link currently renders merchant display **Kreator**, product **Instagram Creator Course (The Full Bundle)**, and **297 US dollars**. The earlier creator course's full bundle had the same price. This exact-link/product/footer pattern is consistent with residual template or reused course material. It does not prove accident, exclude an affiliate/commercial arrangement, or identify the Stripe account's legal holder. Most importantly, it must not become a merchant/ownership edge between Kreator and ClipIt or Monster Lab.

The separate main AI Profit payment link `https://buy.stripe.com/6oE00c5yyb4raSA3ci` renders an error saying no valid payment methods are available. No merchant identity is visible in that state. No form was filled and no payment initiated.

Primary-source chain, counts and limitations: `b-serviuos-merchant-link-excerpts.md`; observed checkout state: `b-stripe-visible-observations.md`; independent bounded cross-check: `b-child-checkout-crosscheck.md`. Finding **15432**, synthesis / medium.

### 2. Public invoice code gives an evidence schema, not a payment record

The [current invoice-view client](https://monsterlab.io/_next/static/chunks/pages/dashboard/myAccount/invoices-1b6d9634d0d7b514.js), found through the current terms page's build manifest, maps a user-specific invoice collection into hosted invoice URL, amount paid, currency, description, status, finalized timestamp and paid timestamp. This is a useful checklist for authenticating a future voluntarily public invoice.

No user ID was substituted, no Firestore or authenticated data endpoint was called, and no invoice was recovered. The code cannot identify a merchant, buyer, campaign payer, clipper withdrawal recipient or settlement. The separate checkout client confirms invoice creation requires an authenticated user token; that path was not invoked. Finding **15428**, paraphrase / high, explicitly scoped to static client behavior.

### 3. New historical mentorship selectors, but body recovery remains incomplete

A corrected hostname-only domain archive search returned **61 rows / 17 distinct original URLs**, extending the prior root-only Serviuos history. New relevant paths are `/clipit-coaching` (redirect captures) and `/clipit-mentorship` (HTTP200 capture metadata in July, November and December 2025). The first mentorship-body retrieval returned HTTP429; the paired December command did not execute after that failure. These rows are real new selectors, not proof of page contents.

The newly fetched January 24, 2025 root body remains AI Profit, retains the two stable payment links, and supplies no visible legal name, address, company/VAT number or seller-specific legal link. Current Monster terms JavaScript is byte-identical to the wave-one captured terms: the unnamed Company problem is unchanged.

## Findings Added

| ID | Type / confidence | What changed |
|---|---|---|
| 15428 | paraphrase / high | Current public invoice-client fields and user-specific boundary; no actual invoice |
| 15432 | synthesis / medium | Exact earlier creator-course link provides counter-evidence to merchant attribution from the Serviuos page alone |

Both are stored under `elephant-clipping`, with quoted evidence and source provenance. Latest audits: `b-provenance-15428-final.json`, `b-provenance-15432-final.json`. Currency was checked after persistence. The invoice source quote was refined through the audited evidence-correction command into one contiguous exact client-code excerpt; the factual scope did not change. Editorial verification remains unverified.

## Connections / Entities

- Registered **7126, Kreator (Stripe merchant display)** as an unknown-type, unknown-status display identity, not a company or person.
- Added **no ownership, funding or corporate connection** to ClipIt, Monster Lab, Serviuos or any legal person.
- Reused the existing Monster Lab and `serviuos.com` target entities.
- The child found a separate creator-site professional/company description, but it is not an operation-identity bridge and was not merged or pursued through registries. A legal entity candidate is not established merely by sharing a course-page link.

## Negative Results

- Exact-domain EDGAR searches for `"monsterlab.io"` and `"serviuos.com"`: zero results returned in the queried EFTS index.
- Local SEC enforcement searches for Serviuos, MonsterLab and ClipIt: zero results. Database scope is 37,793 action rows, dated through **2026-07-29**, not a current September-wide regulator clearance.
- New exact-domain/company/invoice/business-ID searches produced no primary legal-company or authenticated transaction record. Automated reputation/security pages and OCR false positives were excluded.
- No named seller company, registration/VAT number, postal address or seller-specific legal terms in either rendered Stripe state.
- No actual campaign invoice, funded amount, approved payout, wallet release, bank receipt, withdrawal or ultimate payer was recovered.
- The zero returned by the initial `*.serviuos.com/* --subdomains` query is **invalid coverage**: its wildcard-path selector was incompatible with domain match. The corrected hostname query returned 61 rows. It is not counted as evidence of archive absence.

These are bounded source negatives and access states, not claims that an entity, invoice, payment or relationship never existed.

## Sources Checked

`OLD` means `/tmp/osint-E6iGgeNz`; `NEW` means `/tmp/osint-ldT6picn`. Prior-artifact reuse is deliberate; no same-day baseline rerun is claimed as new evidence.

| Source | Status | Command / scope | Artifact and result | Coverage limit |
|---|---|---|---|---|
| Investigation DB / search_log | Newly checked | `check_searched` exact queries; profile context; lead claims | NEW `b-source-log.py`; 18 direct checks logged; leads 94300/94308/94366 | Child checks separately logged; business-ID query accidentally repeated once despite prior zero, not counted as new coverage |
| Monster first-party legal notice | Prior reused + newly verified asset | Current `/terms`, linked manifest/terms JS | NEW `b-monster-current-terms.js`; byte-identical to OLD terms | Unnamed Company remains; no inferred intent from incomplete drafting |
| Monster privacy | Prior coverage reused | OLD current privacy HTML/JS | OLD `monster-current-privacy.*`; findings 15353/15365 | No new legal selector, so not re-fetched |
| Monster invoice / checkout clients | Newly checked | Read-only GET of two manifest-listed public JS assets | NEW `b-monster-invoices-public-chunk.js`, `b-monster-checkout-public-chunk.js` | Static schema only; no data API, session, auth or invoice access |
| Stripe public payment links | Newly checked rendered UI | Two stable `buy.stripe.com` links already published on archived Serviuos page | NEW `b-stripe-visible-observations.md` | One error; one Kreator display without legal identity; no checkout action |
| Serviuos archive root | Prior reused + new body | `query_wayback.py fetch https://www.serviuos.com/ --timestamp 20250124160655 --output ...` | NEW `b-serviuos-2025-fetch.json`; title AI Profit, same two payment links | Raw temporary JSON contains excluded session-link material; do not promote whole file |
| Serviuos full-domain archive | Newly checked | `query_wayback.py snapshots serviuos.com --subdomains --output ...` | NEW `b-serviuos-domain-index.json`; 61 rows / 17 originals | Archive index, not full body set; excludes unindexed pages |
| ClipIt mentorship archive | Inaccessible in this pass | `fetch https://www.serviuos.com/clipit-mentorship --timestamp 20250713202445` | HTTP 429; NEW index retains 2025 capture selectors | December paired request did not run; no bypass/retry loop |
| Creatorkarro earlier course | Newly checked by bounded child | Public replays 20231211115349 and 20240407190853; exact-link comparison | NEW `b-child-karro-course-2023-archive.json`, `b-child-karro-course-archive.json` | Same-site continuity, not independent verification of account ownership |
| Web exact selectors | Newly checked | Exact domain + company/LLC/invoice, exact connected-account ID, mentorship path | NEW `b-web-search-notes.md` | No relevant bridge; search engine incompleteness; automated ratings not adopted |
| EDGAR | Newly checked | `query_edgar.py search '"monsterlab.io"'` and `'"serviuos.com"'`, `--size 20 --output` | NEW `b-edgar-*-domain.json`; 0 / 0 | Exact domain mentions, not every possible undisclosed company |
| SEC enforcement | Newly checked | `query_sec_enforcement.py search Serviuos/MonsterLab/ClipIt --output`; stats | NEW `b-sec-enforcement-*.json`; zero each, corpus through 2026-07-29 | Not a legal clearance or all-regulator scan |
| Unified corporate registry / officers | Prior coverage reused | Alias/name/officer searches from first wave | OLD `serviuos-registry-*.json`; no supported match | No newly bridged company/officer; Florida homonyms remain excluded |
| Latvian official register / historical names / officers / members / beneficial owners | Prior coverage reused | Exact alias scans across five official datasets | OLD `serviuos-latvia-*`; zero supported alias rows | Different undisclosed legal name remains possible |
| Latvian official gazette | Prior coverage reused | Exact-name, inflection-disabled searches | OLD report-serviuos-clipit + logged sources | No new selector; not repeated |
| OpenCorporates | Prior coverage reused | Prior LV exact aliases including inactive | OLD `serviuos-opencorporates-*-lv.json` | No new paid call or broader homonym hunt |
| GLEIF | Prior coverage reused | Prior LV alias queries | OLD `serviuos-gleif-*-lv.json`; zero | Monster brand-only global matching cannot establish legal identity |
| OpenSanctions | Prior coverage reused | Prior LV local-data alias queries | OLD `serviuos-opensanctions-*-lv.json`; zero | Dataset/jurisdiction bounded, not universal sanctions clearance |
| UK Companies House | Inapplicable | No UK company number, address, incorporation or relevant UK footprint found | No query | Buyer-country dropdown is not merchant jurisdiction |
| Registry lateral officer / address / registered-agent / formation / UCC routes | Inapplicable pending identity | No bridged legal operator, officer or business address | No speculative UCC/property pivot | No residential pivot; mass-market privacy/registrar services are not operators |
| VIES / VAT | Prior limitation reused | Validation requires known VAT number | OLD report-serviuos-clipit; no reverse-name route | No VAT number recovered |
| Domain RDAP / CT / Shodan / URLScan | Prior coverage reused | Existing merchant-domain history | OLD `monster-rdap.json`, `monster-crtsh-timeline.json`, `monster-shodan-domain.json`, Serviuos RDAP/Wayback | Privacy service / hosting != operator; no active scans or paid refresh |
| FEC / Ohio campaign finance | Prior coverage reused | TP PAC Schedule B/IE, alias payees/employers; Ohio 2020–2026-09-02 | OLD `finance-fec-tp-pac-disbursements.json`, other `finance-fec-*`; report-finance-politics | No new payer selector; donations not commercial payments |
| IRS 990 / Turning Point vendor disclosures | Prior coverage reused | Full TPUSA/TPA FY ended 2024-06-30 returns, aliases, 1TEN comparison | OLD `finance-990-*.json` + original filing evidence | Returns predate campaigns; top-five contractors incomplete; no same-day refresh; lead 94364 untouched |
| LDA / FARA | Prior coverage reused | Exact clients/registrants/filings/lobbyists; fresh FARA 2026-09-02 | OLD `finance-lda-*`, `finance-fara-*`; no exact operation match | No new legal name; same query not repeated |
| USAspending / SAM | Prior coverage reused | Exact resolved names and alias collision filtering; SAM 2026-03-01 | OLD `finance-usaspending-*`, `finance-sam-*` | Snapshot lag and unresolved legal name; no operation transaction |
| ICIJ / LittleSis / state courts / indexed document corpora | Prior reuse / owner handoff | Prior ICIJ aliases negative; Track C owns new checks | OLD `serviuos-icij-*`; Track C report | No duplicate source scan; track-specific limits remain |
| CourtListener / RECAP merchant selectors | Newly checked by Track C owner | Exact monsterlab.io, serviuos.com and acct_1TCPzsEBSSLjbpgL | NEW `c-legal-report.md`, `c-legal-coverage.json`; zero for each selector, no legal bridge | Public RECAP search coverage, not all litigation or private exhibits |
| Kabasshouse / LMSBAND / Unified private/case corpora | Inapplicable | Profile has zero configured corpus tools; no case-specific predicate | No query | Avoid unrelated private/personal data collections |
| FDIC / FINRA / aviation / medical / property | Inapplicable | No regulated financial institution, broker, aviation, medical or public-property predicate | No query | No legal entity guessed merely to fill checklist |
| Campaign/share pages, Docs/Drive/tutorial links | Owner handoff | Track A exclusive source ownership | A reported Whop course experience unavailable; no payment/merchant bridge | Do not infer no public campaign exists; use A report |

Track C also surfaced a public CPT sponsor deck with PromoSocial hosting and Digital Social Hour branding. No new legal company identifier, authenticated payment or ClipIt bridge emerged, so this lane did not expand into those adjacent commercial names.

## Source Gaps

1. An identifiable, primary merchant record bridging the existing ClipIt Whop business/plan or Monster domain to a named legal person remains absent. A public invoice/receipt, processor exhibit, seller legal disclosure or tax identifier would be discriminating.
2. The new 2025 mentorship captures merit a later bounded archive retry that respects rate limits. Exact stable source: `https://www.serviuos.com/clipit-mentorship`; July13, November11 and December8 captures are in the index. Do not expand to guessed paths or private identifiers.
3. The invoice schema is user-specific. Do not substitute guessed IDs or use disclosed credentials; seek an owner-published/redacted invoice or official exhibit.
4. No public payment record supports treating article/dashboard budgets as funded, spent, earned or withdrawn. Current code semantics do not authenticate historical campaign values.

## Follow-Up Leads

- **94300 — in_progress:** merchant identity unresolved; new link-contamination control recorded. Prioritize the main AI Profit/ClipIt seller, not the retained creator-course link.
- **94308 — in_progress:** unnamed Monster/ClipIt Company unchanged. Terms and current billing clients yield no legal bridge.
- **94366 — in_progress:** actual campaign-level payment evidence missing. Invoice fields refine the authentication checklist, not its fulfillment.
- **94364 — not advanced:** no new filing, date, payee or specific financial selector justifies repeating the first-wave political-vendor checks.
- No new lead added merely to duplicate these questions; the new mentorship selectors were attached to 94300.

## Preservation and Hygiene

Safe selective artifacts for coordinator promotion: `b-stripe-visible-observations.md`, `b-serviuos-merchant-link-excerpts.md`, selected fields from the child's two sanitized creator-course JSONs, and the relevant small invoice-client excerpt. Do not promote the raw Serviuos root JSON, raw browser AX output, all checkout DOM, or the empty `b-web-search-batch2.json` as evidence. Raw captured root HTML contains session-bearing links that were neither used nor copied to these notes.

| Artifact | SHA256 of saved artifact |
|---|---|
| b-stripe-visible-observations.md | a771391d657c5dab58c2d3e88d2f1eac5cc5cee43e977bfde81db64d7e2fa57e |
| b-serviuos-merchant-link-excerpts.md | e23de9e2b8f299bc979f95a95aa20ef906ab58c6fe83bec6e1e19a2c6ed80c91 |
| b-serviuos-domain-index.json | 934092a18212b05dae5aa49553a05a3911d7c3b5f9bf874d096b0d794d5ec8a0 |
| b-monster-invoices-public-chunk.js | 7505519d88da5523ac136526f08c2bee74d3320d234ace71c00d44aa4ff1cade |
| b-child-karro-course-2023-archive.json | d106bb2f66ad6bb46b1d1d4e1400ea757922cb0e199e47e5bdafe331f741fc4b |
| b-child-karro-course-archive.json | 1eaf0d5b4d4bb7a144867b5e0f7c44f58825dd9c8a0548faeb7341fdc3003084 |

The child artifacts separately record source acquisition times, HTTP status, final archive URLs and original-response hashes. Browser observations are clearly labeled observational notes, not raw HTTP captures. Scripts are session-local research aids, not infrastructure changes; Ruff passed `b-source-log.py` and the child's extraction script.

## Learnings

- **Identity resolution:** Test a checkout-link bridge against the earlier source and the link's placement. Exact shared payment URLs can survive in curriculum/template fragments while genuine primary CTAs use a different merchant route.
- **Source quality:** A live hosted-checkout display is a current marketing label, not a civil/legal identity, historical account-ownership record, payment receipt or campaign-finance ledger.
- **Source quality:** A public invoice client can define authentication fields while exposing no invoices. Preserve schema separately from record values; do not use user-specific collection paths as an invitation to query them.
- **Archive method:** Domain matching takes a hostname. A wildcard path with `--subdomains` yielded an invalid zero until corrected to `serviuos.com`; papercut 2503 records the avoidable validation/documentation friction. The corrected 61-row index surfaced previously missed mentorship paths.
- **Friction:** Wayback HTTP 429 blocked a newly discovered mentorship body; papercut 2505 records the barrier without relabeling it zero. zsh/fnm sandbox startup noise recurred (2498, earlier 2437; child 2502); non-login bash allowed clean scoped work.
- **Process:** Reusing same-day registry and political-record negatives preserves the distinction between coverage and progress. A new source/selector is valuable; another identical search without one is not corroboration.
