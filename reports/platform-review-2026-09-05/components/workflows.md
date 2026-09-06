# Platform review: agent workflows, skills, and methodology

Read-only review of the current working tree, 2026-09-05. No production code, skills, dossiers, findings, leads, profiles, queues, or investigations were changed. Four papercut observations were logged as required by AGENTS.md: #2716, #2720, #2721, #2724.

## Scope and checks

- Applied `.codex/skills/audit-skills/SKILL.md` and its review rubric.
- Deterministic snapshot of all 36 project skill packages / 69 Claude and Codex variants: **0 errors, 51 warnings, 5 informational items**. This is a structural result, not evidence that commands or semantics all work.
- Semantically reviewed the shared methodology and representative research, analysis, and editorial contracts: pursue-lead, deep-investigate, generate-hunches, timeline-analysis, systemic-analysis, analyze-network, curate-dossier, review-dossiers, review-article. Inspected paired variants or parity output where relevant.
- Deep-investigate is already dirty; its current diff adds Massachusetts UCC commands, unrelated to these findings. Other reviewed core contracts and methodology were clean at inspection. Preserved all existing changes.
- Ran synthetic contract checks with scratch SQLite and patched in-memory dossier loads. No real dossier or research claim was used as a test subject.
- Ran `findings_tracker.py add --help`, `correct --help`, and two known-failing add examples that reject before database writes. Inspected current finding triggers read-only to rule out date normalization at the database layer.
- Independent reviewer adjudicated confidence/probability and false-positive closure concerns. Did not verify historical allegations or browse external sources; this review concerns instructional logic.

Artifacts:

- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/skill-snapshot.json`
- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/check-workflow-contracts.py.txt`
- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/workflow-repros.json`
- `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/workflow-adjudication.md`

## Prioritized findings

### [P1] WF-1: An automated dossier PASS suppresses the semantic review needed to catch unsupported assertions

**Evidence:** `/Users/travcole/projects/osint-research/.codex/skills/review-dossiers/SKILL.md:54` instructs LLM review only for dossiers that did not get a clean PASS. Line 63 immediately describes its editorial checklist as things automated checks cannot evaluate. The same condition is in the Claude variant at line 55. `/Users/travcole/projects/osint-research/scripts/review_dossier_checks.py:762` assigns PASS when pattern-based checks find no blocking/should-fix issues.

**Verified failure:** A fully synthetic dossier asserted a conviction and bribery while its sole verified finding merely documented a company formation. `run_checks()` returned **PASS, zero blocking issues, zero should-fix issues, zero suggestions**. This is expected of bounded regex/structure checks; the defect is treating that result as grounds to skip claim-evidence review. The skill consequently routes this dossier around the only review explicitly responsible for semantic alignment and insinuations of wrongdoing.

**Small remedy:** Run semantic review for every selected dossier unless that exact content version already has a valid semantic review. Keep automated checks as a separate stage. Persist the semantic result with the existing `ingest-llm` capability, so a user-facing combined PASS does not mean only an automated PASS. Do not try to solve claim support by adding more banned phrases.

**Verification:** Keep the synthetic unrelated-citation case. A forward test of the revised skill must select it for semantic review and flag both unsupported claims. Include a clean, supported dossier to ensure the review still finishes. Papercut #2720.

### [P2] WF-2: Search deduplication silently treats old or differently scoped searches as reusable coverage

**Evidence:** `/Users/travcole/projects/osint-research/.codex/skills/pursue-lead/SKILL.md:79` skips a source on any truthy `check_searched` result. `/Users/travcole/projects/osint-research/tools/lead_tracker.py:2292` matches only query text and source. The schema at `tools/lead_tracker.py:602` stores no filter/scope signature, corpus version, response status, or result artifact; it has a timestamp, but this workflow never checks it. Claude counterpart has the same instructions.

**Verified failure:** A scratch `search_log` row containing a zero-result search dated **2001-01-01** is returned as a usable prior result by the current helper. Following the skill skips the source even after later records could exist. Queries that differ by date range, jurisdiction, operation, or source snapshot cannot be distinguished unless an agent manually encodes them into query text.

**Small remedy:** First change the skill to inspect freshness, exact search scope, outcome, and availability of results before reuse. Then provide one narrow reusable-search helper that returns why reuse is or is not valid and keys on normalized request scope. Preserve search history as an audit record; it should not automatically mean a cache hit. Static corpus searches can reuse a matching corpus version; dynamic sources need an explicit freshness policy.

**Verification:** Cases for stale zero, changed filter, failed acquisition, missing result artifact, and a valid same-version hit. Papercut #2721.

### [P2] WF-3: The timeline skill bypasses the canonical date correction path

**Evidence:** `/Users/travcole/projects/osint-research/.codex/skills/timeline-analysis/SKILL.md:63` backfills using raw `UPDATE findings SET date_of_event`. The canonical `/Users/travcole/projects/osint-research/tools/findings_tracker.py:1598` updates `date_of_event`, `event_date_iso`, and `date_precision` atomically and records a correction at line 1583. `/Users/travcole/projects/osint-research/tools/event_timeline.py:479` requires non-null `event_date_iso`. Claude variant has the same raw UPDATE at line 67.

**Verified failure:** Executing the documented UPDATE against a scratch row changes the raw date to `2020-02-03` but leaves `event_date_iso` and `date_precision` NULL. The current live database has only FTS triggers on findings, not a normalization trigger. The result disappears from normalized timeline-window queries and has no correction trail.

**Small remedy:** Replace both raw SQL examples with the existing `findings_tracker.py correct <ID> --field date_of_event --value YYYY-MM-DD --reason ...` command. This needs no new subsystem.

**Verification:** `correct --help` confirms the interface. A bounded fixture should assert all three columns plus one correction row; no broad investigation rerun needed. Papercut #2716.

### [P2] WF-4: Three analysis skills provide finding-write examples rejected by the current CLI

**Evidence:**

- `/Users/travcole/projects/osint-research/.codex/skills/analyze-network/SKILL.md:122`
- `/Users/travcole/projects/osint-research/.codex/skills/timeline-analysis/SKILL.md:129`
- `/Users/travcole/projects/osint-research/.codex/skills/systemic-analysis/SKILL.md:132`

All omit mandatory `--sources` (required in `/Users/travcole/projects/osint-research/tools/findings_tracker.py:3393`). Timeline/network examples use quote keys different from the supplied evidence reference; systemic-analysis provides an unkeyed quote and combines multiple references into one quoted semicolon string. Paired Claude examples have the same issues.

**Verified failure:** Executing the timeline example with synthetic values exits **2: required --sources**. Adding `--sources analysis_run` still exits **2: Evidence metadata supplied for refs not present in evidence_ids: timeline analysis**. Both reject before a DB write.

**Why it escaped:** `/Users/travcole/projects/osint-research/scripts/validate_skills.py:470` gathers allowed flags and rejects unknown ones, but does not validate omitted required arguments or payload contracts. The whole-skill snapshot reported 0 errors.

**Small remedy:** Update these examples with separate canonical evidence references, source tokens, and `ref:quote` pairs tied to preserved supporting artifacts. Add parse/validation-only contract fixtures for representative tracker examples; do not execute production mutation commands from a documentation validator. Keep the validator's current scope clearly labeled.

**Verification:** Fixture values should parse and validate against a scratch store; omitted sources and mismatched refs should fail deliberately. Papercut #2724. Lower priority than the editorial bypass: this fails visibly and is recoverable, rather than silently blessing unsupported prose.

## Design improvements, distinct from demonstrated defects

### Confidence is not automatically a probability

`/Users/travcole/projects/osint-research/research/INVESTIGATIVE_METHODOLOGY.md:715` maps medium to “likely/probably,” and `/Users/travcole/projects/osint-research/.codex/skills/review-article/SKILL.md:263` enforces that mapping as a blocking standard. But medium is also a default and a claim-type/source ceiling (`tools/findings_tracker.py:550`, `:560`, `:937`), including for opaque provenance and synthesis. An administrative ceiling says how strongly evidence may be treated; it does not establish that a proposition is more likely than not. Similarly, a confirmed quote confirms that the quote exists, not every proposition attributed in it.

**Recommendation:** Preserve confidence caps, provenance rules, and the weakest-link constraint. Remove automatic probability entitlement from those tiers. Require a proposition-specific likelihood assessment when probabilistic language matters; otherwise use factual attribution and explicit uncertainty. This is a semantic design recommendation, not a claim that the cap implementation is broken. An independent reviewer agreed with this narrower P2 concern.

### Reduce instructions that steer hypotheses toward suspicion before measuring the alternative

There are useful counterweights: methodology lines 472–482 require evidence first, base rates, and opportunism/coordination separation; lines 699–709 require competing hypotheses and diagnostic evidence; pursue-lead line 291 requires disconfirmation. These prevent a fair review from calling the entire methodology confirmation-biased.

However, concrete examples still pull against those safeguards. `generate-hunches/SKILL.md:116` says absent legal connections are suspicious because lawyers leave fewer traces; lines 109–112 and 125 label donor overlap or simultaneous contract growth as coordinated. `research/INVESTIGATIVE_METHODOLOGY.md:179` treats different dataset volumes as suggesting filtering/compartmentalization. These can be useful research prompts, but the wording preselects an explanation for ordinary missingness or common exposure.

**Recommendation:** Replace categorical examples with a neutral observation, a plausible mundane explanation, a coverage/base-rate check, and one discriminating test. In particular, distinguish “no findings in our collection for six months” from “no activity occurred.” Keep the strong existing competing-hypothesis framework rather than adding more ritual layers.

### Make source coverage conditional and canonical

`research/INVESTIGATIVE_METHODOLOGY.md:259` says ANY entity/person must receive NY, FL, NM, U.S. campaign-finance, and NYC property searches. The platform is now general-purpose, and deep-investigate/pursue-lead separately maintain different mandatory matrices. This creates unnecessary U.S.-centric work for targets without the relevant jurisdiction/role and increases policy drift.

**Recommendation:** Maintain one compact source applicability table keyed by target type, jurisdiction, question, and available route. The planner should record “not applicable” with a reason where warranted. Preserve mandatory coverage for relevant sources. This is a targeted simplification; it does not require a new orchestration framework.

### Preserve runtime adapters while reducing duplicated workflow bodies

There are 33 paired skill packages. Ten are flagged for normalized differences, but inspected review-dossiers/dedup-leads differences are legitimate runtime adaptations (`Agent tool` versus `spawn_agent`, output retrieval conventions), not demonstrated bugs. Deep-investigate is 805 lines and repeats long worker templates and source policy also found elsewhere.

**Recommendation:** Gradually move shared source/evidence/report contracts into a canonical referenced resource and keep skill bodies focused on decisions and handoffs. If mirror maintenance remains costly, generate the two thin runtime adapters from one body. Do not bulk-normalize all variants or interpret every parity warning as a defect.

## Strengths and dismissed concerns

- Evidence independence, claim-type ceilings, bounded negative results, explicit report ownership, atomic lead claiming, disconfirmation, primary-source attribution, and public-source/no-contact boundaries are substantive foundations worth retaining.
- Deep-investigate now defines one persistence owner per source category, an expected report set, scoped negatives, and separate implementation ownership. These directly address real concurrency/evidence risks.
- Structural validation is useful and currently finds no errors; warnings are triage hints. Runtime variants and cache bytecode files are not 51 separate platform defects.
- Dismissed the broad claim that pivot leads cannot stop: pursue-lead lines 293–300 expressly permit completion on consistent negatives/diminishing returns, and methodology line 591 references those conditions. Methodology line 316 could still clarify that disproving a particular pivot closes that linkage even when unrelated concerns remain separate.
- Confidence caps themselves obey AGENTS.md and should stay. The problematic part is the downstream probability interpretation.
- Did not recommend replacing the platform, adding approval gates, or imposing a large new framework. The highest-value changes repair existing contracts and remove duplicated or contradictory instructions.
