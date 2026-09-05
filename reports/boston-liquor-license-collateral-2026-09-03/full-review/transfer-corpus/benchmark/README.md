# Terra versus Sol: evidence-extraction pilot

**Keep Sol for lien-status judgments on this evidence.** In one blinded run per model on the same 13-case packet, Terra made three unsupported current-lien assertions; Sol had no scored errors. This is a deliberately selected pilot, not a general model ranking or an estimate of production accuracy.

The packet contains 12 Boston Licensing Board items and one Lyons ownership-disclaimer case. It includes ordinary grants, combined transfer/pledge applications, stock-only actions, an issuance condition, a nonclosed transaction, a pledge release and an ownership disclaimer. Both fresh agents used **high reasoning effort**, identical instructions and source text, and no browsing or additional research. Initial input reading and final artifact writing were the only allowed tools. Input, reference, rubric and raw responses were frozen and hashed.

| Result | GPT-5.6 Terra (response A) | GPT-5.6 Sol (response B) |
|---|---:|---:|
| Schema valid; cases answered | Yes; 13/13 | Yes; 13/13 |
| Event-action extraction errors | 0 | 0 |
| Critical unsupported current-lien claims | 3 | 0 |
| Partial condition omissions | 1 | 0 |
| Ownership-disclaimer case score | 100/100 | 100/100 |
| Raw weighted mean | 97.77/100 | 100/100 |
| Mean after predeclared critical-error cap | 88.08/100 | 100/100 |

In cases C06, C10 and C13, Terra set `current_license_lien_status` to `established` on evidence of a granted pledge application. Those records do not establish a current outstanding lien. Sol retained `not_established`. In C04, Terra preserved an issuance hold but omitted the neighborhood-process confirmation required to lift it. Both correctly handled the Lyons ownership disclaimer and the action categories.

Two blinded reviewers assessed source ambiguities without being told model identity. They corrected one answer-key omission: C06 explicitly pledges stock as well as the license, which both responses correctly extracted. Other documented semantic allowances were applied equally. Frozen reference answers were not overwritten; [errata.json](errata.json) records the adjudication.

These results support further testing of Terra for narrow transcription or action extraction, with independent validation. They do **not** support substituting it for unsupported-status judgments on this task, or establish equal performance on corporate identity, ownership chains, document retrieval, OCR, browser operation or causal analysis. No model setting for the wider project was changed.

Per-run token usage and comparable start-to-finish latency were not captured, so this is not a cost or speed comparison. Output byte counts are not token-usage measurements. A repeat trial on held-out records would be needed to estimate reliability; the present result is already sufficient to retain the more conservative workflow for current-lien conclusions.

See [blind scoring](scoring.md), [component scores](scores.json), [administration](administration.md), [run metadata](run-metadata.json), [Terra raw response](response-a.json) and [Sol raw response](response-b.json).
