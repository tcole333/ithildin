# Semantic audit: analysis and depth-analysis skills

Scope: full `.codex/skills/` and `.claude/skills/` texts for analyze-network, timeline-analysis, systemic-analysis, generate-hunches, analyze-case, analyze-filing, analyze-contract. Read the review rubric, research workflow contract, relevant methodology, and implementation paths cited below. All seven pairs match after runtime normalization (confirmed by diff and supplied snapshot). Primary skill citations below use the Codex tree; the corresponding Claude line is one greater throughout the cited body sections. No repository/database mutation, source research, or skill execution occurred. Verification is static source inspection, not a live endpoint claim.

## Verified defects

### A1 — P2: ad hoc cross-reference SQL ignores the selected database and profile

- `.codex/skills/analyze-case/SKILL.md:218-223` opens literal `investigation.db` and queries all financial findings matching a party, with no `profile_id` predicate. `.codex/skills/analyze-filing/SKILL.md:212-217` does the same for connections. Claude counterparts: 219-224 and 213-218.
- `tools/findings_tracker.py:41` resolves `ITHILDIN_DB_PATH`; `tools/findings_tracker.py:2053-2078` scopes normal finding search to the resolved profile, and `tools/findings_tracker.py:3192-3223` does so for connection lookup. The embedded SQL bypasses both mechanisms.
- Failure: with a pinned staged database or a party shared between investigations, these snippets pull unrelated/live data and present it as the current investigation's cross-reference. Pinning environment variables as required by the higher-priority contract does not fix a literal SQL connection and missing predicate.
- Small correction: use existing profile-aware tracker/export APIs and structured output. If direct SQL is truly needed, obtain both database and profile through the canonical resolver and open read-only. Do not duplicate database routing logic in skills.
- Verification: a fixture with the same party in two profiles plus an alternate `ITHILDIN_DB_PATH`; assert the skill's documented route returns only selected-profile rows from that database.

### A2 — P2: contract timeline step supplies aggregate award metadata as transaction history

- `.codex/skills/analyze-contract/SKILL.md:84-100` labels the step “Analyze Payment Timeline” and its first command “Transaction-level payment history,” but runs `query_usaspending.py award` again. Claude: 85-101.
- `tools/query_usaspending.py:560-599` fetches `/awards/{id}/` and reports aggregate obligation/options, performance dates, and subaward totals. It does not fetch a sequence of award actions. The adjacent `timeline "NAME"` command is recipient-wide period aggregation (`tools/query_usaspending.py:1082-1101`), not a selected award's transaction history.
- The repository already exposes `transactions` (`tools/query_usaspending.py:719-754`), with `Action Date`, `Transaction Amount`, and `Mod`. Its current parser has recipient/UEI, agency, date, page, and limit parameters but **no `--award-id`** (`tools/query_usaspending.py:1236-1261`). Do not recommend an invented flag.
- Failure: agent cannot support the requested cadence, gaps, modification patterns, or front-loading from the supplied artifacts, or uses recipient totals as though they belong to the selected award. The skill also repeatedly calls obligation actions “payments”; its own finding example at lines 199-206 is explicitly a federal-action obligation, which does not establish cash disbursement timing.
- Small correction: document a bounded existing transaction route, paginate, explicitly filter/verify target award identity, and preserve action records. Call this obligation/modification analysis; reserve payment claims for actual outlay/disbursement evidence. A dedicated tested award-scoped transaction operation would be a useful tool improvement if the existing recipient route is too broad.
- Verification: two awards for one recipient with different action dates; documented analysis must isolate the requested award, detect pagination, and never describe an obligation-only row as a paid amount.
- Related coverage caveat: lines 65-66 say “Get all subawards” but run the first default page (`tools/query_usaspending.py:1225-1232`: 20 rows, page 1). The shared contract already prohibits treating partial results as complete, so this is a reinforcing stale example, not a separate finding.

### A3 — P2: structured financial extraction silently switches to the latest 10-K

- `.codex/skills/analyze-filing/SKILL.md:149-158` fetches income, balance sheet, and cash flow with `sections <TICKER_OR_CIK>` and no form/index binding. Claude: 150-159.
- The same skill explicitly supports a supplied historical URL or requested form, and may choose a filing matching a key date (lines 34-38, 53).
- `tools/query_edgar.py:1818-1819` defaults sections to `--form 10-K --index 0`; `tools/query_edgar.py:1568-1570` forwards those values, and `tools/query_edgar.py:1429-1440` chooses that filing from `company.get_filings(form=form)`.
- Failure: a 2019 accession or 10-Q is read correctly, then ratios are computed from the latest 10-K and may be attributed to the selected filing. The command implementation can be correct while the skill binds it incorrectly.
- Small correction: resolve and verify the same form/accession for every structured statement; use current form/index selectors only with explicit accession verification. Consider an accession/URL selector for the tool rather than requiring agents to reconcile moving ordinal indexes.
- Verification: mocked filing catalog containing a historical 10-K, latest 10-K, and 10-Q; each skill invocation must retain the original accession through all three statements and resulting ratios.

### A4 — P2: cross-case finding example supplies invalid evidence/quote mapping

- `.codex/skills/analyze-case/SKILL.md:254-263` puts two references inside one semicolon-delimited `--evidence` argument and supplies a single separately keyed quote. Claude: 255-264.
- `tools/findings_tracker.py:3430` uses `nargs='+'`; it does not split semicolon strings. `tools/findings_tracker.py:856-885` matches each quote against an explicitly supplied evidence reference; `tools/findings_tracker.py:1034-1059` rejects quote metadata for a key absent from `evidence_ids` and requires a quote for each ref.
- Failure after substituting real IDs: `--evidence "CourtListener:101;CourtListener:202" --source-quote "CourtListener:101:excerpt"` creates one compound evidence key, and the quote parser falls back to `CourtListener`, producing a mismatched key. The documented cross-case write fails validation. This is not the intentionally generic placeholder syntax itself; the separator/arity is wrong.
- Small correction: provide two individually quoted evidence arguments and two matching ref:quote arguments, following the current analysis-skill examples. Preserve both original source references.
- Verification: parse the documented example with synthetic IDs; assert two references and one matching quote per reference, then validate against a disposable database fixture.

### A5 — P2: the formation-date hunch scan requests a field absent from its export

- `.codex/skills/generate-hunches/SKILL.md:49,65,71-73` exports `entity-network` then says to scan those entities for `formation_dates`. Claude: 50,66,72-74.
- `tools/analysis_export.py:586-592` and `tools/analysis_export.py:612-614` explicitly select entity id/name/type/jurisdiction/status/EIN/address/source/notes; neither scoped nor all-profile output includes formation date. The actual schema field is `date_formed` (`tools/lead_tracker.py:1219`), not `formation_dates`.
- Failure: a populated `entities.date_formed` is invisible to the prescribed scan, leading to needless reconstruction from prose or a false empty formation-clustering result.
- Small correction: expose documented `date_formed` through the existing export, update the skill's field name, and retain source/date precision limitations. Do not invent exact formation dates from vague notes.
- Verification: entity-network export fixture with a populated `date_formed`, asserting the field survives profile-scoped and all-profile paths; forward-test a small formation cluster.

## Optional improvements and design decisions

These are material opportunities for the parent's current-guidance comparison, not additional proven defects. Several concern lower-level language already moderated by binding shared instructions.

1. **Replace numerical novelty gates with evidence-sensitive triage.** `generate-hunches:130-134` rejects directly connected actors and requires three independent findings/entities. Its report explicitly permits “only 2 data points” as a rejection reason (line 210). A surprising new funding mechanism between already-connected parties, or two highly diagnostic primary records, can merit investigation. Treat thresholds as starting heuristics with an override justified by diagnosticity, novelty, and a cheap discriminating test. Keep the independence check and falsifiable lead requirement. Evaluate against fixtures containing an ordinary three-way overlap and an important two-record discovery.

2. **Remove prewritten causal interpretations of graph statistics.** `analyze-network:89-95,108-111` says neighbors “don't know each other,” a node “controls information flow,” and low-clustering nodes “are brokers.” The graph is a collection of heterogeneous recorded relations (`tools/graph_tools.py:146-184`), and structural-hole score is merely one minus observed neighbor density (`tools/graph_tools.py:426-439`). Likewise `systemic-analysis:113` says three shared attributes “indicate systemic behavior, not coincidence,” despite its own base-rate instruction at line 8. The shared contract and methodology already require alternative explanations and collection-gap checks, so I did not classify these as permission to assert causation. Replace the categorical language with observed-graph statements and questions to test; preserve the computations and confidence ceilings. Include an ordinary high-degree professional-service provider in the eval.

3. **Make temporal thresholds and scan menus explicit defaults.** `timeline-analysis:72-100` fixes 3 findings/14 days, 10 findings/30-day silence, and simultaneous weekly activity across 2 targets. `analyze-network:55-79` requires a large fixed metric bundle; `generate-hunches:65-124` mandates twelve scans, some making external calls. These may be useful reproducible baselines, but cadence, collection density, graph size, and factual question should decide relevance and sensitivity. Record selected thresholds and skipped scans; allow a valid “no actionable pattern” result. Keep full coverage of sources actually applicable under the shared contract.

4. **Scope ACH effort to the methodological trigger.** Four analysis skills prescribe a complete competing set and matrix for every pattern or observation (`analyze-network:149-176`, `systemic-analysis:157-184`, `timeline-analysis:151-178`, `generate-hunches:140-164`). The methodology says ACH is mandatory for coordination/intent theories and live rivals (`research/INVESTIGATIVE_METHODOLOGY.md:665-675`). A deterministic shared-board observation need not always trigger a full speculative competition. Offer a cheap observation/lead path, escalating to ACH under that trigger. Preserve falsification, explicit alternatives, and rival scoring for actual explanatory claims.

5. **Make source planning a menu rather than duplicating old universal lists.** `systemic-analysis:70-99` says to query five services for each group member; `:274` gives LittleSis blanket priority. The shared research contract already owns source applicability and prevents a universal minimum. Align the body with that contract, including jurisdiction and role relevance, while keeping useful source-specific commands as examples. Do not report this as a missing source-applicability safeguard: the safeguard already exists.

6. **Modernize CourtListener document acquisition and typed citations.** `analyze-case:64-70` uses an ambiguous “opinion/cluster ID” and terminal preview capped at 1,000 lines. The tool supports `--id-type` because raw opinion and cluster IDs overlap (`query_courtlistener.py:381-404,925-934`), and `--output` preserves full raw response before terminal truncation (`:421-451`). Adapt the already-good full-artifact/chunked-coverage approach in analyze-filing. Preserve the returned cluster/opinion identities and all relevant sub-opinions. Also replace bare `CourtListener:<DOCKET_ID>` examples at lines 237-250 with typed document identities: the citation renderer deliberately refuses bare refs (`web/src/lib/citations.ts:276-281`) and supports typed docket/opinion tokens (`:1980-1986,2033-2037`). This is a concrete usability improvement; I have not claimed every current finding fails persistence, or that the higher-level full-read instruction allows truncation.

7. **Reduce repeated prose, retain domain checklists.** These skills are 222-318 lines, all below the rubric's rough 500-line ceiling; line count alone does not justify splitting. The end sections praising LLM capability and contrasting it with human skimming (`analyze-case:308-317`, `analyze-filing:306-315`, `analyze-contract:241-250`) can be removed without losing procedure. Stable CLI recipes can move to directly linked command references or deterministic wrappers. Retain the genuinely useful court extraction categories, accession-package inventory, and claim/evidence requirements.

8. **Consider a tool-level analysis-run CLI.** Four skills repeat embedded `python -c` start/complete calls, manually transcribe run IDs/counts, and independently define report schemas. A small start/complete command with structured output and required artifact paths could eliminate transcription and quoting overhead. This is an optional ergonomic change, not evidence that the existing Python APIs fail.

## Strengths to preserve

- Analysis skills already pin profile/database through the shared contract, use unique workdirs and explicit report paths, and distinguish synthesized findings from primary facts.
- Exact canonical evidence/quote pairs and medium ceilings for analysis are explicit. Updated analysis examples correctly reject an analysis-run label as sole evidence (`analyze-network:134-137` and counterparts).
- analyze-filing's full saved text, sequential coverage tracking, accession-package inventory, and incorporated-document pending states are strong task-specific instructions (`:55-107,294-304`). Broadly reducing “read the entire document” to a search/snippet-only workflow would weaken this depth-analysis skill.
- analyze-case separates quoted court text, paraphrased allegation, and cross-case inference with appropriate ceilings (`:231-263`). The shared methodology further distinguishes authenticity from truth and mandates attribution (`research/INVESTIGATIVE_METHODOLOGY.md:688-698,713-729`). Preserve those safeguards.
- Hunches explicitly test collection coverage/base rates, check past hypotheses, and require falsification plus concrete next searches. These controls address known investigative failure modes and should not be removed simply because models improved.
- No accidental substantive Claude/Codex drift in this scope. Shared-policy consolidation can build on the existing contract rather than invent another umbrella document.

## Dismissed suspicions / no-action notes

- Context-loading blocks in the three depth skills only show `investigation_context.py show`; I did **not** report missing pinning as a defect because AGENTS.md already requires the workflow contract before source planning. The literal SQL bypass remains a separate concrete defect.
- Unquoted `--assessment consistent|inconsistent|...`, angle-bracket fields, and N/M placeholders are visibly templated choices, so I did not claim an intended verbatim CLI execution failure.
- I did not flag `entity-by-uei --output`, HigherGov vehicle/partnership flags, finding category `case`/`contract`, or analysis `pattern-type` values: inspected parsers support them.
- Semicolon evidence in A4 is distinct from placeholder notation: replacing all placeholder values still leaves invalid argument structure.
- No universal six-agent requirement applies within these single-agent scoped skills; adding parallelism is not itself a recommendation.
- No source counts were treated as corroboration counts in this audit; the root report should distinguish three contexts from three independent provenance chains.
- Source writes and follow-up lead creation are authorized by these investigative skill workflows. I did not recommend blanket confirmation gates.
