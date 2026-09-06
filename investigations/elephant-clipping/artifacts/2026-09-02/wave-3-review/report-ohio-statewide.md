---
agent: wave3_budget_tools
target: "Ohio statewide expenditure navigation helper"
skill: search-all-sources
status: completed
findings_added: 0
connections_added: 0
entities_registered: 0
leads_spawned: 0
profile: elephant-clipping
---

# Ohio statewide expenditure helper — navigation handoff

## Key Discoveries

The correct statewide expenditure form is available through ordinary public navigation. This helper completed **source routing and handoff only**, not the six-name search. Primary agent `wave3_payments` accepted the route and is responsible for executing, preserving, reconciling and persisting results. This helper submitted **no name queries**, entered no dates and never clicked Run Report.

The official [campaign-finance entry](https://www.ohiosos.gov/elections/campaign-finance) links its Simple Search, Advanced Search and File Transfer choices to the [data portal](https://data.ohiosos.gov/portal/campaign-finance). In native Firefox, the portal's Expenditures link opens the published sessionless route `https://www6.ohiosos.gov/ords/f?p=CFDISCLOSURE:3:::NO:RP,3::`, which renders the Expenditure Search form at `https://www6.ohiosos.gov/ords/f?p=CFDISCLOSURE:3:::NO:3::`.

The official entry describes statewide candidate, PAC, state-party and legislative-caucus report coverage. Prior results from `boefilesearch.ohiosos.gov` are local BOE-file records and do not substitute for this source. No source-level result reconciliation is made in this helper report.

## Findings Added

None. Primary payment agent owns persistence. No finding, entity, connection, lead or lead-status changes were made.

## Connections Added

None.

## Entities Registered

None.

## Negative Results

**No substantive negative name-search results.** None of the requested stems were submitted by this helper, and no result count, table or pagination was reached. A JavaScript shell and HTTP 403 are access outcomes, not zero-result searches. The site is not globally unavailable: its portal and form rendered in native Firefox.

## Sources Checked

| Source / action | Effective scope and outcome |
|---|---|
| Existing search_log | Read prior local BOE rows separately; requested stems had no matching `oh_statewide_expenditures_ui` record at helper check. |
| Official campaign-finance page, web reader | Retained actual reader output; three search/file-transfer labels share the data-portal destination. |
| Data portal, web reader | JavaScript shell only. |
| Official entry → data portal → Expenditures, native Firefox | Form successfully rendered. Navigation was ordinary public clicking, not an inferred or probed endpoint. |
| Form defaults / bounded dropdown inspection | Initially Candidate Committees, Active and 15 rows per page; name/date fields blank. Dropdown options not exposed in native accessibility output. Keyboard inspection changed dependent fields to PAC Name while popup label remained Candidate Committees, so effective selection was left unresolved. |
| One GET of the published form URL | HTTP 403; preserved response bytes. No retry, authentication or bypass. |
| Transfer to payment agent | Verified route and defaults sent; no duplicate helper queries after transfer. Primary agent has separate browser controls and will provide its own observed filters/results. |

## Requested Versus Effective Filters

Requested payee stems were `B WYNN SPORTS`, `BG CONTROL`, `NEVER FOLD`, `BW COUNTERPUNCH`, `1776 CASTLE` and `BWRP`, optionally `ENCLAVE`, for expenditure dates 01/01/2024–09/02/2026. Intended scope included relevant statewide entity categories and all committee statuses. **These filters were not applied by the helper.** Exact versus contains matching was not tested, and no query outcome is attributed to these names here.

The form provides a Payee-Non-Individual/Committee field, Start Date and End Date fields. Its initial Candidate Committees / Active defaults are narrower than requested coverage. Primary agent must preserve actual entity-type choices and status, not inherit the defaults silently.

## Source Gaps Identified

The form describes searchable coverage from 2020 onward, with both audited and unaudited data that can change through audits and committee updates. Searches exceeding 10,000 records need narrower criteria; a public file-transfer route is offered for large datasets. These are source-published limitations, not independently assessed completeness. Amendment handling, payer coverage, match semantics, pagination and all six name outcomes remain the primary agent's tests.

Native Firefox could render the form but did not expose dropdown options; its screenshot call was unavailable, and the selected label appeared stale after keyboard navigation. This is a tool-specific scope-verification limit, not proof the source lacks the options. Open papercut **2630** records the reproduction. No repository fix was attempted.

## Follow-Up Leads Created

None. The existing payment lane continues the original bounded scope; this handoff is not a new investigative lead.

## Preservation

Artifacts are in `/tmp/osint-v4NdHom5/c-ohio-helper/`:

- `reader-entry-response.json`: actual retained web-reader response, captured 2026-09-02 19:37:51 UTC; SHA-256 `5c90aa0d5440a8aee802b71da5f60635b9051f56fa317ffad173ee4f0d9506c0`.
- `form-ax-selected.json`: exact selected-line JSON returned by native accessibility capture at 2026-09-02T19:43:00.928Z; unrelated tabs and incidental browser state omitted. It preserves the contradictory popup/dependent-field state without resolving it.
- `navigation-scope.json`: explicitly labeled analyst navigation/scope notes, including requested/unapplied filters and handoff. The intervening portal's AX output was observed but not separately saved verbatim; this note is not represented as a source capture.
- `statewide-form.html`: the direct HTTP 403 response, 1,253,633 bytes; SHA-256 `2ac49dd52c84f74f98585f15569f3ad52f3f34387282b4117b9e47acc2fdb7ea`. Its file mtime is retained as the timing basis, not invented as an exact request timestamp. Raw barrier response is temporary and not needed for substantive name findings.

Final artifact hashes are recorded in the adjacent manifest. Primary agent and root receive this report for source-level reconciliation; it should not be counted as an additional six-name coverage pass.

## Learnings

- [Methodology] Official navigation distinguishes statewide campaign-finance records from Ohio's separate local BOE-file search; similar state branding is not source equivalence.
- [Source quality] A rendered report form can be available even when a reader receives an app shell and an ordinary HTTP client receives 403; preserve each surface outcome separately.
- [Friction] Native select accessibility may retain a stale label after changing dependent fields; do not assert effective query scope without a reliable control or result readback.
- [Process gap] Transferring a verified route to one primary query owner avoids duplicate name passes and keeps source-level coverage reconciliation coherent.
