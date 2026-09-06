# Final publication-audit integrity review

Reviewed at 2026-09-06T01:36:50.277936+00:00.

**PASS — no material integrity error found in the bounded review.**

- Counts reconcile: nine current articles; 519 indexed dossier entries minus six redirects gives 513 distinct dossier content pages; 277 equal narratives plus Brad Karp and the citation-only Pesner difference gives 279 pages with narrative prose; 234 are data-only. Planned routes are explicitly separated from homepage HTTP-200 fallbacks.
- Local categories reconcile to 519 payloads: 283 authored narratives, one lead-only unfinished dossier, 235 data-only payloads. The report does not confuse alias payloads with new pages or completed drafts.
- All 23 artifact entries in the publication manifest exist and match recorded byte counts and SHA-256 values. All relative Markdown links in the two reviewed narrative reports resolve to existing files.
- All 13 JSON files in the publication audit plus commissioning companion parsed successfully (13 total). No truncated JSON detected.
- Checked all 32 established candidate anchors against the frozen database. Every ID exists; no anchor is marked retracted or disputed; every retained evidence reference/quotation matches the stored pair exactly. Aetna #10399 lacks a stored quote, but its packet explicitly identifies missing quotes and remains conditional; the candidate has three other quoted anchors. This is documented debt, not an undisclosed publication approval.
- Priority framing respects counter-evidence: GEO separates accounting periods and capacity/payment concepts; Curaleaf excludes laundering and statistical-significance overclaims; BIRD preserves waiver and investor-identity uncertainty; Gates–IPI acknowledges prior coverage and the Foundation review; CPI separates service sharing from control. Older Apollo, Deutsche Bank and Wexner directions are explicitly narrowed.
- Readiness is repeatedly distinguished from semantic PASS, current claim verification and the release gate. No new investigation is recommended or initialized. Source mirrors, proposition-specific independence, bounded novelty queries and non-frozen raw-corpus metadata are disclosed.

This review checks report integrity and consistency with retained evidence/inventories. It is not a new live-site crawl, exhaustive source audit, or semantic approval of the underlying content.

Reviewed artifact hashes:

- `reports/publication-audit-2026-09-05/README.md` — `825841ae2a9dfb72c93d46b3a0c17675534250ce87b5feebf918b8fc6479e14d`
- `reports/publication-audit-2026-09-05/manifest.json` — `ac2b527735d1d098010384174228186932766087c1953ec295cf0661ef22ab33`
- `reports/investigation-candidates/2026-09-05-run-155.md` — `5ec0c86b6e0f90fdb249a989715968ad13a2c3c3352f09e629cff348d4fba125`
- `reports/investigation-candidates/2026-09-05-run-155.json` — `e276f3284b95e41523e61fcbcf8afe7449de08a6beeea6ba0088921f900a865a`
