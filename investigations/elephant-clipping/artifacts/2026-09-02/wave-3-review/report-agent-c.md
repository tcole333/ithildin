---
agent: wave3-payments
target: "Blake Wynn corporate entities — six-LLC political-payment trail"
skill: deep-investigate
status: completed
findings_added: 0
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 95000
thread_id: 207
profile: elephant-clipping
scope: main-pass plus reconciled Ohio statewide addendum
---

# Agent C — six-LLC payment trail, main pass

## Key Discoveries

No entity-resolved payment to a target emerged. The main pass expanded the prior single-committee federal search to all-committee Schedule B recipient searches, and actually queried public Nevada, Ohio local, Arizona beta and IRS Form 8872 transaction interfaces. This is a coverage result, not evidence that no payments occurred or that advertised budgets were fictitious.

The important scope correction is Ohio: **BOe-file's all-county local committee search is not the separate statewide candidate/PAC system.** The latter's current official route is [Ohio Campaign Finance Data Portal](https://data.ohiosos.gov/portal/campaign-finance), linked by the [Secretary of State campaign-finance page](https://www.ohiosos.gov/elections/campaign-finance). The [official BOe-file launch notice](https://www.ohiosos.gov/office/media-center/categories/press-releases/2021-01-08) describes local candidates/committees filing with county boards. All statewide target searches were unissued at main-pass close. A manually dispatched helper then located the form and handed it back to Agent C, who ran 18 name/category scopes; see the reconciled addendum below. No target rows displayed, but the source provided no explicit zero count. Lead 95000 remains **in_progress**, not closed because this pass ended.

Florida did not yield any valid target search: the form returned `Invalid Date Range Entered` for three materially different configurations. That is an access/validation outcome, not a zero. Only B WYNN SPORTS was attempted there. Arizona's functioning beta interface carries a data/visual-defect warning; the main host failed DNS and the documented API directory probe returned HTTP 403. These constraints remain explicit despite completed beta queries.

## Findings Added

None. Ordinary no-result searches were stored in search_log rather than converted to absence findings. There is no new financial edge or campaign-purpose finding to review.

## Connections Added

None. Neither shared Blake Wynn roles, entity names nor a shared surname establishes a political-payment connection or kinship.

## Entities Registered

None; reused the existing entity/registry resolution in F15364 and the prior Enclave/Wynn report. Canonical set:

| Entity | Entity ID | Nevada entity number | Formation date | Selector used in state/IRS main pass |
|---|---:|---|---|---|
| B WYNN SPORTS LLC | 7044 | E0456082018-2 | 2018-09-28 | B WYNN SPORTS |
| BG Control LLC | 7052 | E41497012024-7 | 2024-06-27 | BG CONTROL |
| NEVER FOLD LLC | 7053 | E47162252025-4 | 2025-03-05 | NEVER FOLD |
| BW Counterpunch LLC | 7054 | E50176732025-9 | 2025-07-08 | BW COUNTERPUNCH |
| 1776 Castle LLC | 7055 | E53268132025-8 | 2025-11-21 | 1776 CASTLE |
| BWRP, LLC | 7056 | E57779492026-9 | 2026-05-31 | BWRP |

B WYNN SPORTS is the entity behind the documented Enclave & Key DBA and Celebrity Poker Tour mark/brand. The other five are lateral Wynn-role entities, not established subsidiaries or proven operators of Enclave's campaigns. Registry/mark address identifiers were available for resolving a plausible hit; no target-like candidate survived even name/geography/purpose triage. Dates before formation would require predecessor/misidentification analysis, not automatic attribution.

## Negative Results

Dates below mean **expenditure/transaction date 2024-01-01 through 2026-09-02**, not filing date. `0` means completed observed selector result only. It does not mean all spelling variants, all payments, every filing system or every reporting period is comprehensively exhausted.

| Recipient selector | FEC Schedule B | NV payee | OH local BOe | AZ beta expense + IE | IRS electronic 8872 | Florida | OH statewide |
|---|---|---|---|---|---|---|---|
| B WYNN SPORTS | Broad request 504; WYNN SPORTS and B WYNN SPORTS LLC each 0 in 2024 and 2026 two-year periods | 0 | 0 | 0 | 0 | Validation error, 3 attempts | E × 3; addendum |
| BG CONTROL | 0 | 0 | 0 | 0 | 0 | Unissued | E × 3; addendum |
| NEVER FOLD | 0 | 0 | 0 | 0 | 0 | Unissued | E × 3; addendum |
| BW COUNTERPUNCH | 0 | 0 | 0 | 0 | 0 | Unissued | E × 3; addendum |
| 1776 CASTLE | 0 | 0 | 0 | 0 | 0 | Unissued | E × 3; addendum |
| BWRP | 0 | 0 | 0 | 0 | 0 | Unissued | E × 3; addendum |
| ENCLAVE | 3 distinct venue/resort records, excluded | 0 | 0 | 0 | 0 | Unissued | Unissued |
| CELEBRITY POKER TOUR | 0 | 0 | 0 | 0 | 0 | Unissued | Unissued |

`E` means a completed empty displayed result section, without a source-provided count, table or explicit no-results message; it is not the same evidence as an explicit zero. Three scopes per name cover Candidate Committees, PAC/PCE Committees and Political Parties/LCF. Optional statewide brands remain unissued.

FEC additionally returned 0 for **ENCLAVE & KEY** and **ENCLAVE AND KEY**. Other main-pass portals used the broader ENCLAVE stem, not separate exact punctuation/wording versions. Arizona first ran expense-only queries for the six legal stems plus ENCLAVE (seven zeroes), then expanded to Expense + Independent Expenditure for all eight table selectors (eight zeroes). CPT was not separately issued in the earlier expense-only scope; it was covered in the broader combined scope. This is bounded variant/stem searching, not a claim of exhaustive fuzzy matching.

Positive functionality controls: Arizona's same expense-only/date filters with AMAZON returned **2,259 candidate entries**, first 10 displayed; IRS's same recipient/date fields with AMAZON returned **133 items**, first 10 of 14 pages. These controls were not fully paginated, identity-resolved or summed; they show the workflows can return records. Arizona's displayed transaction-name cells were blank, reinforcing the beta-quality limit. NV/OH did not receive separate positive controls this pass.

## Sources Checked (commands/scope/outcomes)

### 1. FEC — all-committee recipient searches

Used the configured public FEC provider and existing `tools.query_fec._fetch`, not a web-search substitute. The current CLI's `disbursements` command requires a committee, so a bounded one-off caller invoked the already-supported public `/schedules/schedule_b/` endpoint without a committee selector. This was logged as infra **325**, not shipped as an integration.

```bash
PYTHONPATH="$PWD" uv run python /tmp/osint-v4NdHom5/c/fec-sweep.py --output /tmp/osint-v4NdHom5/c/fec-sweep-live.json
PYTHONPATH="$PWD" uv run python /tmp/osint-v4NdHom5/c/fec-sweep.py --output /tmp/osint-v4NdHom5/c/fec-wynn-2024.json --name 'WYNN SPORTS' --name 'B WYNN SPORTS LLC' --cycle 2024
PYTHONPATH="$PWD" uv run python /tmp/osint-v4NdHom5/c/fec-sweep.py --output /tmp/osint-v4NdHom5/c/fec-wynn-2026.json --name 'WYNN SPORTS' --name 'B WYNN SPORTS LLC' --cycle 2026
```

Parameters in each saved query: recipient_name, min_date `2024-01-01`, max_date `2026-09-02`, sort `-disbursement_date`, per_page 100, max_pages 20. Wynn retries explicitly supplied `two_year_transaction_period=2024` or `2026`. Those are two-year transaction periods, not an assumption about the recipient's formation/election. No amount/state/committee restriction. Initial sandbox DNS failures are preserved as errors, not source searches. Live broad B WYNN SPORTS returned HTTP 504; the four successful cycle-bounded variants are separate scopes, not retroactive conversion of that failure to a zero.

**13 successful scopes:** 12 zero-response scopes plus ENCLAVE's three records; one live 504. Every successful response reported `is_count_exact: true` and `last_indexes: null`; zero responses reported count 0/pages 0, ENCLAVE count 3/pages 1. No pagination limit bound. `is_count_exact` concerns the count, **not exact-name matching**. Recipient-name selector normalization/fuzzy behavior was not independently established; both precise phrases and broad stems were tried.

All ENCLAVE rows were excluded as non-target name collisions:

| Reported payee | Reporting committee | Date / amount | Reported purpose | Resolution / source pointer |
|---|---|---|---|---|
| ENCLAVE EVENT CENTER, Oklahoma City, OK | Oklahoma Leadership Council, C00167213 | 2026-04-10 / $1,500 | FACILITY RENTAL | Different named event venue, not Enclave & Key. Transaction SB21B.1133683; [FEC image reference](https://docquery.fec.gov/cgi-bin/fecimg/?202605209870139987). |
| OCEAN ENCLAVE RESORT, Myrtle Beach, SC | Fry for Congress, C00786657 | 2024-11-07 / $246.47 | LODGING EXPENSE | Resort/travel, not target agency. Transaction B3755BBB17EC745ED8CA; [FEC image reference](https://docquery.fec.gov/cgi-bin/fecimg/?202412059730912416). |
| OCEAN ENCLAVE RESORT, Myrtle Beach, SC | Fry for Congress, C00786657 | 2024-11-07 / $499.51 | LODGING EXPENSE | Same exclusion; distinct transaction BFAD1F499CCAD4763857, same filing-image pointer. |

These are API-reported rows, not independently reaudited original reports. The image links are supplied for audit; they were not fetched because no row plausibly matched a target. Returned amendment indicator `A`/description `ADD`, memo fields and file/sub/transaction IDs are retained. No explicit latest/amendment or memo exclusion was added. Thus no political-payment total is asserted and amounts are not added. Any future plausible match must be reconciled against amendments, memo entries, reimbursements and duplicate filings before quantification or campaign attribution.

### 2. Nevada — official expense/payee UI

[Official search](https://www.nvsos.gov/SoSCandidateServices/AnonymousAccess/CEFDSearchUU/Search.aspx): selected `Search Type: Expenditure Search`; each stem in `Expense Payee`; dates `1/1/2024`–`9/2/2026`; payer, amount and type unrestricted/default. Eight completed rendered responses said `No expenses found for these search values.` No result pagination. The source advertises expense records from 2006 and electronic filings from 2012; this is a search of its filed/indexed records, not a completeness statement about reportable or indirect payments. Search text normalization was not independently verified.

### 3. Ohio — local BOe portal only

[BOe-file public search](https://boefilesearch.ohiosos.gov/ords/f?p=BOEFDISCLOSURE:1::::::): Simple Search field `P1_SEARCH` each stem; `P1_FROM_DT_input=01/01/2024`, `P1_TO_DT_input=09/02/2026`; category EXPENDITURES; county ALL. Eight completed responses: `No results found. Please try another search.` The source covers 2020 onward, audited and unaudited records, and warns data can change. It requires narrowing above 10,000 rows; no cap bound here. Simple Search is described as broad; payee-only/exact/fuzzy semantics were not established. Statewide candidate/PAC source outcomes were collected subsequently and are separated in the addendum.

### 4. Arizona — official beta UI, bounded source quality

[Beta Advanced Search](https://spotlightv2.arizona.vote//Reporting/AdvancedSearch): `ContributorName` each stem, Expense checked, Income unchecked, all election cycles, dates `2024-01-01`–`2026-09-02`, other filters unrestricted. Seven expense-only scopes and eight scopes with Independent Expenditure additionally checked returned both `No data found, try updating your filter options` and `Showing 0 to 0 of 0 entries`. The autocomplete's no-results label was never counted as the transaction result; the completed table was read. Default 10/page; no continuation for zeroes.

[Public API documentation](https://spotlightv2.arizona.vote//Reporting/Api) describes keyless GET JSON, `/api/transactions/search` name/date/type filters, pagination and date-vs-cycle precedence. A direct `/api` directory request returned 403; no target API query was issued. [SeeTheMoney](https://SeeTheMoney.arizona.vote) failed browser DNS. No bypass/repeated challenge probing. Existing infra **205** updated with observations; no new adapter built. Beta defects/current-primary completeness remain barriers to treating the UI result as statewide exhaustive.

### 5. IRS — electronic Form 8872 recipient/date search

[Form 8872 advanced search](https://forms.irs.gov/app/pod/advancedSearch/Adv8872Search): selected `Recipient’s name` and `Date of expenditure`, entered each name and `01/01/2024`–`09/02/2026`, submitted and read completed results. Eight responses said `...no results found`. No form-type restriction: initial/amended/final were not separately filtered. A future hit must therefore be reconciled at form and transaction level.

[IRS name-search guidance](https://www.irs.gov/charities-non-profits/political-organizations/political-organizations-disclosures-search-tips-exact-and-partial-string-searching) describes exact ordered words/phrases within a name, not typo/fuzzy matching; an inserted middle component can matter. No wildcards were used. [Search scope guidance](https://www.irs.gov/charities-non-profits/political-organizations/tips-for-successful-searching-of-political-organization-disclosures) limits this to electronic submissions. The selected expenditure-date field exists from December 2002, comfortably before our requested window. This is neither every political organization nor every kind of political payment; absence here does not establish no payment.

### 6. Florida — attempted but no valid target result

[Official expenditure form](https://dos.elections.myflorida.com/campaign-finance/expenditures/) submits to `/cgi-bin/expend.exe`. Payee name B WYNN SPORTS; matching option **containing**, max 500 rows. Three attempts: (1) All elections with dates `01/01/2024`–`09/02/2026`; (2) All elections with both dates empty; (3) 2026 election with dates empty. Each returned `Invalid Date Range Entered`. Stopped after these materially different attempts. Other five legal names and all DBA/mark selectors unissued, not zero. Infra **326** requests supported public form/export diagnosis.

### 7. Prior coverage reused, not silently repeated

Read prior F15394/lead94364 and search_log. F15394's TP PAC C00814152 scope (684 Schedule B rows, 2025-01-01–2026-09-02) is not all-committee coverage. Its prior Ohio operation-name queries did not cover this six-LLC set and were not treated as a substitute. Prior TPUSA/TPA 990 coverage ends with fiscal period **2024-06-30**, predating the campaigns. No later filing was newly identified this pass; no same-day re-download. Top-five contractor disclosure cannot establish that other payments were absent. FARA/LDA/procurement/registry background was not repeated without a new selector.

## Source Gaps Identified

1. **Ohio statewide limits:** the subsequently completed 18 target scopes had empty displayed result sections but no explicit source count; optional DBA/brand and separate Electioneering Communications, Transition Funds and State Retirement Board menus remain unissued. This is distinct from the local portal and from a source-reported zero.
2. **Florida validation:** infra 326; exact failed configurations and unissued names preserved.
3. **Arizona current-primary/API:** added evidence to prior infra 205; beta query outcomes do not cure current-source completeness or blank transaction-name cells.
4. **FEC CLI:** infra 325; research used existing fetch helper, leaving normal tool support for all-committee recipient searches unresolved.
5. **Matching/reporting:** no exhaustive typo/fuzzy alias guarantee; no intermediary/subcontractor or unitemized expenditure coverage; filing lag, source revisions and 990 period limits remain. No reporting model was established that would make a complete negative probative of fictitious budgets.

## Follow-Up Leads Created

None, to avoid duplicate work. Lead 95000 remains in_progress and owned by Agent C; root controls any next-wave assignment. Source-specific infrastructure records: **325**, **326**, and updated **205**. Papercuts **2605** (FEC CLI restriction), **2609** (in-app export capability mismatch), **2610** (subagent tab visibility option) remain open. Report-format papercut **2629** was fixed and validated; browser-ID input issue **2631** was dismissed as a corrected invocation, not a repository defect. Helper papercut **2630** concerns native select accessibility. No unsafe workaround or repository integration patch.

## Evidence and persistence

- [Minimized lane manifest](/tmp/osint-v4NdHom5/c/manifest.json) supplies SHA-256/byte lengths and provenance for the minimized FEC response fields, UI observations, scripts and log receipt.
- [UI observations](/tmp/osint-v4NdHom5/c/ui-observations.json) are **analyst transcriptions of observed rendered public pages**, not raw HTML archives. Observation window 19:08–19:34 UTC September 2; individual UI-query timestamps were not captured. This limitation is explicit because in-app HTML export was unavailable. Session-bearing URLs and incidental data were removed.
- [FEC minimized output](/tmp/osint-v4NdHom5/c/fec-minimized.json) retains exact submitted filters, source timestamps, source counts, cursor exhaustion and relevant off-target rows without unrelated committee/person fields. Temporary original response files remain available for local audit but are not designated durable exports.
- [Search log receipt](/tmp/osint-v4NdHom5/c/search-log-receipt.json): 46 UI scopes (39 completed target scopes, 2 first-page positive controls, 5 barrier attempts). FEC independently logged successful/error scopes. No unissued query is logged as an executed zero.
- Both one-off scripts passed `uv run ruff check`. No findings/hypotheses/root docs changed by this agent; status/notes, search logs and infrastructure observations only. Parent ingests nonduplicate Learnings; this agent has not separately ingested them.

## Learnings

- [Methodology] An all-county local filing search does not establish coverage of a separate statewide campaign-finance system; identify the filer population before labeling a state's coverage complete.
- [Source quality] Positive controls distinguish a functioning zero-result query from a broken workflow, but a beta interface's blank payee cells and warning still limit source completeness and resolution.
- [Process gap] Search evidence must retain errors, unissued selectors, matching semantics, report/date scope, cursor exhaustion and amendment flags separately; an exact result count is not exact-name matching or proof of absent payments.

## Ohio statewide addendum — reconciled September 2, 2026

Helper [navigation report](/tmp/osint-v4NdHom5/report-ohio-statewide.md), SHA-256 `3a941748595bdc539bd51471e51c9706215c32fd5bd5122a19b559acf005dff8`, was read and reconciled. Its [manifest](/tmp/osint-v4NdHom5/c-ohio-helper/MANIFEST.md) distinguishes the retained official-entry reader output, selected final-form AX lines and analyst navigation notes. The intermediate portal AX was observed but not separately retained; the direct form GET's HTTP 403 is temporary barrier evidence, not substantive coverage. The helper submitted **no names or dates and no Run Report actions**. Thus it is not a second payment sweep or corroborating negative.

The helper followed the official portal's Expenditures link to [the published statewide form](https://www6.ohiosos.gov/ords/f?p=CFDISCLOSURE:3:::NO:RP,3::). Agent C opened that route in the existing in-app browser and executed all actual query scopes from 19:42–19:48 UTC. The browser exposed three entity types; there was no all-types option. Status was changed from default **Active** to **-All-** and read back. Payee-Non-Individual/Committee was used, not payer or individual name. Dates were entered before every query because Back cleared them. Report type, year, payer/PAC name, geography, purpose and amounts were unrestricted. Requested dates were 01/01/2024–09/02/2026; target result headings did not echo filters, so no independent backend date-filter audit is claimed.

| Payee stem | Candidate Committees | PAC & PCE Committees | Political Parties/LCF |
|---|---|---|---|
| B WYNN SPORTS | Empty displayed section; no count | Empty displayed section; no count | Empty displayed section; no count |
| BG CONTROL | Same | Same | Same |
| NEVER FOLD | Same | Same | Same |
| BW COUNTERPUNCH | Same | Same | Same |
| 1776 CASTLE | Same | Same | Same |
| BWRP | Same | Same | Same |

All **18** submissions rendered the appropriate results heading and expenditure-region heading but no table, rows, explicit no-results text, count or pagination. These outcomes are stored with `source_count: null` and `rows_displayed: 0`, not numeric negative counts in search_log. No payment was displayed; the source's hidden/backend completeness is not established.

One Candidate-committee **AMAZON** control, with input dates and All status read back, returned a real table and `row(s) 1 - 15 of 804`. Despite the form requesting 100 rows per page, 15 were displayed; remaining pages were not acquired. Visible payee variants AMAZON, AMAZON.COM and AMAZON INC establish some partial-name behavior, not exhaustive substring/typo normalization. The control confirms this UI can produce records, but PAC/PCE and Party categories did not receive separate controls. No control amounts or incidental addresses are retained in the minimized addendum, and no control total is asserted.

The source says its searchable records start in 2020, include audited and unaudited data, and may change. A 10,000-record narrowing rule is advertised; no target pagination existed to exhaust. No amendment/latest-version filter was applied and report type was unrestricted; any future hit still requires amendment/memo/duplicate and entity-purpose review. Optional statewide DBA/brand queries and the separate special-filing menus were not issued, per the bounded handoff instruction.

Addendum artifacts: [observations](/tmp/osint-v4NdHom5/c/ohio-statewide-observations.json) and [19-scope log receipt](/tmp/osint-v4NdHom5/c/ohio-statewide-search-log.json) (18 targets plus one first-page control). The lane manifest includes their hashes. Main-pass 46 UI log scopes and 13 successful FEC scopes remain unchanged; the 19 addendum scopes are not merged into a misleading zero count. **No finding, entity, connection or monetary edge was added.** Lead 95000 remains unresolved/in_progress, with source-specific Florida/Arizona limits and remaining bounded selectors available for a future commission.
