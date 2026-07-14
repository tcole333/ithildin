# Lead #62587: ISAP V item 42 and skip-tracing acquisition record

**Research date:** 2026-07-14  
**Profile / thread:** `geo-group` / 109, Electronic Monitoring & ISAP  
**Target instruments:** ISAP V IDIQ `70CDCR25D00000062`; task `70CDCR25FR0000127`; modifications P00002–P00004; solicitation `70CDCR25R00000018`  
**Evidence layer:** federal award actions, preserved public pre-award solicitation extraction, SEC-filed company statements, and bounded official-corpus searches

## Disposition

The signed P00002–P00004 packages and the post-award Attachment 4 pricing schedule item 42 were **not recovered**. The public record establishes the actions and their labels, but it does not disclose item 42's unit, quantity, unit price, eligible case population, deliverables, data flow, invoice basis, suppliers, or acquisition rationale.

The exact-quote evidence matrix is [2026-07-14-lead-62587-isap-v-skiptrace-evidence-matrix.csv](2026-07-14-lead-62587-isap-v-skiptrace-evidence-matrix.csv). The hashed archive manifest is [2026-07-14-lead-62587-isap-v-skiptrace-source-manifest.json](2026-07-14-lead-62587-isap-v-skiptrace-source-manifest.json). Both are deterministically rebuilt by `scripts/build_geo_isap_v_skiptrace_lead.py`.

## What the federal award record establishes

USAspending currently returns five actions on task `70CDCR25FR0000127`:

| Action date | Modification | Action type | Action obligation | Public description boundary |
|---|---|---|---:|---|
| 2025-09-30 | base | delivery order | $21,966,324.91 | ISAP V technology and case management |
| 2025-09-30 | P00001 | funding-only action | $16,103.09 | additional ISAP V funding |
| 2025-10-30 | P00002 | funding-only action | $690,000.00 | adds funding for skip-tracing services |
| 2025-12-17 | P00003 | funding-only action | $9,660,000.00 | names Attachment 4 pricing schedule item 42 skip-tracing services |
| 2026-01-27 | P00004 | funding-only action | $76,011,425.00 | repeats the item-42 label |

P00002–P00004 sum to **$86,361,425**, or **79.7105%** of the task's current **$108,343,853** obligations. P00003 and P00004—the actions that expressly identify item 42—sum to **$85,671,425**. These are federal action obligations, not invoices, payments, outlays, unit prices, recognized revenue, or the IDIQ ceiling.

The current award snapshot separately reports **$94,747,700.79 in account outlays**. That award-level total is not allocated publicly among the five actions and cannot be converted into item-42 payments or GEO revenue. The same snapshot reports `subaward_count = 0` and no structured subaward amount. That is a structured-data boundary—not proof that BI used no subcontractor, supplier, reseller, data broker, or contractor-to-contractor arrangement.

The task names **B.I. Incorporated** (UEI `PKK6L9KLMYR5`) as recipient and **The GEO Group, Inc.** as parent recipient. The local SAM entity extract independently maps that UEI to B.I. Incorporated and CAGE `3CUH9`. It does not turn the GEO parent into the legal task-order awardee.

## What the public pre-award schedule does—and does not—show

A preserved extraction from the public August 15, 2025 SAM Attachment 4 pricing workbook enumerates operational-support items through **“39. J-site Case Coordination Meeting.”** Its schedule note states that quantities are estimates for evaluation and that the Government is not obligated to order them.

This wave did not recover the original XLSX bytes. The archive therefore labels the extraction accurately: it is a preserved local representation from a prior mirror of the public SAM attachment, with file metadata retained and all expiring or credential-bearing URLs excluded. It is adequate to document the public pre-award item-39 boundary, but it is not the missing post-award schedule.

The comparison supports only this narrow conclusion: P00003 and P00004 refer to a later or otherwise different item 42 than the 39 numbered operational-support items visible in the preserved pre-award extraction. It does not reveal whether items 40 and 41 were added, when item 42 was negotiated, or whether item 42 was a new scope, an option, a pilot, a surge, a pricing-only change, or another contractual mechanism.

## New SEC timing and contract-identity evidence

GEO's SEC-filed February 12, 2026 results release separates three corporate descriptions:

1. the September 30, 2025 two-year ISAP award for electronic monitoring, case management, and supervision;
2. an “initial Skip Tracing pilot contract” implemented during fourth-quarter 2025; and
3. a new two-year skip-tracing contract awarded in December 2025, with GEO describing a transition from the pilot to the new contract.

GEO's May 6, 2026 SEC-filed first-quarter release adds that the company began service under the new two-year skip-tracing contract in **March 2026** and described that contract as worth up to **$60 million in revenues per year**.

Those company statements provide useful contract-identity and timing anchors, but they do not identify the pilot's PIID. The federal sequence makes the ISAP V funding actions an obvious record request, not a proven mapping: P00002 occurred in October 2025; P00003 in December; P00004 in January 2026; and the separate two-year vehicle began its first BI task in December 2025. Without the signed scopes and item-42 schedule, this report does not assign the corporate “pilot” label to any one action.

The company figure “up to $60 million in revenues per year” is also not comparable to an action obligation or current outlay. It is a company-described potential revenue rate, not an ICE obligation, invoice, payment, or recognized-revenue ledger.

## Evidence implications for later synthesis

For hypotheses #347 and #350, the SEC statements document that GEO itself described a pilot-to-new-contract transition and separately discussed ISAP. That is evidence of distinct contractual identities and phases. It does **not** resolve whether the pilot was item 42, whether item-42 cases overlapped the later vehicle's cases, or whether BI provided integration or common data services across the two channels. The missing schedule and scopes remain the decisive records.

For hypotheses #348 and #349, the SEC record supplies two public operational anchors: a pilot during fourth-quarter 2025 and service under the new two-year contract beginning in March 2026. No controlling PTA, PIA/PIA-update decision, SORN compatibility determination, ATO, data-flow approval, or risk acceptance was recovered here. The new dates sharpen the approval-versus-deployment comparison but do not decide it.

These are source-level implications only. No Tier 1 finding in this wave scores or resolves the competing hypotheses.

## Public-record stopping point

The following checks did not recover the signed packages:

- exact PIID/modification and item-42 searches across indexed official pages;
- exact PIID search in GovInfo, which returned zero results;
- review of the preserved public ISAP V opportunity-document metadata and pre-award pricing extraction;
- fresh USAspending task, IDIQ, and transaction calls;
- local SAM entity and exclusion pivots;
- SEC filing and exhibit searches for the PIID, pilot, ISAP V, and skip-tracing terms.

Two live SAM wrapper calls ended without stdout, stderr, or the requested output file. A direct follow-up returned HTTP 429. This is preserved as papercut **#979** without any credential material. The failure limits the live SAM pass; it does not change the substantive document boundary because the indexed opportunity package and exact-web searches likewise did not surface a post-award modification package. No HigherGov API call was made during this wave.

CourtListener was not queried for this lead because no materially related protest, contract claim, or disclosure action was identified from the PIID and item-42 record. CourtListener's absence here is not a claim that no related litigation exists.

## Precise agency-held records request

Human action **#67** requests a narrowed ICE FOIA production from the Office of Acquisition Management / Detention Compliance and Removals, with program records from ERO Alternatives to Detention / Removal Management:

1. the signed base task order `70CDCR25FR0000127` and complete P00002, P00003, and P00004 packages, including SF-30s, continuation pages, funding documents, and incorporated attachments;
2. every version of task Attachment 4 and pricing schedule items 40–42, including unit descriptions, quantities, rates, periods, ceilings, and version history;
3. the item-42 SOW, acquisition plan, market research, independent government cost estimate, approvals, scope analysis, and any competition, exception, fair-opportunity, or determination-and-findings record;
4. the document identifying the Q4 2025 pilot PIID, scope, start/end dates, results, and transition relationship to the December 2025 two-year vehicle;
5. COR records defining case eligibility, source systems and fields, assignment and cross-channel duplicate-control procedures, deliverables, acceptance, invoices, credits, deductions, and action/service-period outlays;
6. releasable subcontracting plans, supplier schedules, software/data-license records, and contractor-to-contractor arrangements associated with item 42; and
7. privacy and security approvals tied to the pilot, item 42, and new vehicle, including PTA/PIA/SORN/ATO decisions and dated production or first-case-transfer approvals.

PII can be redacted while retaining aggregate counts, unit descriptions, data dictionaries, approval dates, and acquisition-decision records.

## Reproducibility and limits

- Verified findings: **#12467** (exact skip-action sum and current-obligation share), **#12941** (pre-award item-39 / post-award item-42 boundary), **#12942** (GEO's Q4 2025 pilot statement), and **#12943** (GEO's March 2026 new-contract service-start statement).
- Retracted and replaced: **#12468**, because its prior source quote was not present verbatim in the preserved package; #12941 supplies the bounded, verbatim replacement.
- No Tier 1 hypothesis evaluation was added. Root/Tier 2 review can score the new evidence after independent QA.
- Source archive: `investigations/geo-group/sources/2026-07-14-lead-62587/`
- Evidence matrix: 12 rows, each with an exact quote or structured-field representation and a source SHA-256.
- Manifest: 14 archived source artifacts, generated-output hash, calculations, and boundary statements.
- Rebuild: `uv run python scripts/build_geo_isap_v_skiptrace_lead.py`

The archive preserves the original USAspending JSON and SEC HTML alongside normalized text. Multiple mirrors of a federal award record are not treated as corroboration. Company filings are primary evidence of what GEO stated, not independent proof of the agency's acquisition rationale or internal records.
