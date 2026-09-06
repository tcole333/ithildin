# Implemented workflow hardening

Implementation is complete in the shared working tree. No Git operations, live
investigations, or production semantic review/receipt fabrication were performed.
Existing dirty changes were preserved. Required papercuts #2716, #2720, #2721,
and #2724 are now addressed with the implemented changes and test evidence.

## Changes

- `tools/search_reuse.py`: separate reusable-result metadata keyed with the
  existing `canonical_search_key`. A matching legacy log row never skips a query.
  Reuse requires a complete successful result, identical source/operation/query/
  filters/limit, matching immutable corpus version or explicit freshness policy,
  and an unchanged recoverable artifact. Failed/partial/unavailable latest
  attempts invalidate reuse. Uses `ITHILDIN_DB_PATH`; creates only its companion
  `search_reuse` table on explicit recording. Existing lead_tracker/search_log
  code was not edited.
- `scripts/review_dossier_checks.py`: semantic reviews require exact raw-file
  SHA256, reviewer identity, actual timezone-bearing review time, explicit verdict,
  and an explicit issues list agreeing with that verdict. Legacy DB reviews stay
  unbound. New `receipt` command stores a supplied actual review, including failed
  reviews; no automatic PASS is created. Existing `ingest-llm` records these fields
  and rejects malformed/stale input before DB mutation. `llm-status` distinguishes
  current hashes from old reviews.
- Portable `validate-receipts` and existing `gate` require current semantic PASS
  receipts and rerun automated blockers using the exported dossier's own finding
  evidence, without a database. Missing/stale/unbound review is outstanding review
  debt. Enumerates curated files even if missing from the index. Respects
  `ITHILDIN_CONTENT_DIR`; default receipt file is
  `content/dossier-review-receipts.json` under the selected content root.
- `docs/RESEARCH_WORKFLOW_CONTRACT.md`: canonical profile/database pinning, source
  applicability, query reuse and evidence/worker-report handoffs. Replaces the
  duplicated universal U.S. source matrices with jurisdiction/question relevance
  and explicit not_applicable/unavailable/partial outcomes.
- Both `.codex/skills` and `.claude/skills` mirrors updated for nine skills:
  `pursue-lead`, `deep-investigate`, `analyze-network`, `timeline-analysis`,
  `systemic-analysis`, `generate-hunches`, `curate-dossier`, `review-dossiers`,
  `review-article`. Runtime-specific delegation syntax preserved. Codex writes
  succeeded via apply_patch without a permission escalation.
- `review-dossiers` now reviews every selected dossier after automated PASS,
  skipping only a valid current semantic receipt; reviewer reads actual evidence.
  Fix-only reports outstanding semantic review; edited content needs re-review.
- Timeline backfill uses existing canonical `findings_tracker.py correct`.
  Three analysis finding examples now provide required sources and individual
  evidence/reference-quote pairs, with instructions to preserve underlying
  evidence and computed artifacts.
- Methodology and hunch examples distinguish coverage gaps from inactivity,
  overlap from coordination, and hypothesis testing from suspicion. The existing
  confidence caps and disconfirmation requirements stay intact; tiers no longer
  automatically authorize probability language. Removed universal source-count
  advice and clarified closure of a disproved pivot independently of unrelated
  questions.

## Verification

`uv run pytest -q tests/test_search_reuse.py tests/test_dossier_review_receipts.py tests/test_review_dossier_checks.py tests/test_analysis_skill_commands.py`

**39 passed**. Fixtures cover unrelated citations yielding an automated PASS
without a semantic pass, stale receipt invalidation, semantic failure, embedded
unverified evidence, malformed review fields, old unbound DB records, duplicate
receipts, unindexed curated content, clean-checkout CLI content-root isolation,
stale zero/changed search scope/source version, partial/error outcomes, artifact
loss/tampering, and six documented command parse/payload contracts with writes
intercepted.

Ruff passes for all five changed/new Python files:

- `tools/search_reuse.py`
- `scripts/review_dossier_checks.py`
- `tests/test_search_reuse.py`
- `tests/test_dossier_review_receipts.py`
- `tests/test_analysis_skill_commands.py`

Selected skill snapshot: **9 packages / 18 variants, 0 errors, 4 warnings**
(existing long deep-investigate bodies and deliberate runtime drift).
Full repo skill validator: **69 markdown files, 0 errors, 16 legacy warnings**
for bare Python examples in add-registry, which was outside this subtask.
Artifacts: `/tmp/osint-CUTDyZF1/workflow-skill-snapshot.json` and
`/tmp/osint-CUTDyZF1/workflow-validator.txt`.

A fresh read-only forward test at `/tmp/osint-CUTDyZF1/forward-workflows.md`
confirmed semantic review after automated PASS, search reuse requirements, and
Peru-relevant source selection. Follow-up doc corrections removed the old minimum
source count and unbounded-negative wording, scoped diminishing returns to
completed applicable coverage, replaced mandatory new hypotheses with actionable
factual follow-ups, and made receipt persistence explicitly cover single-target
as well as batch review. The reviewer did not rerun those final prose corrections;
they add no commands or code paths.

## Integration handoff to root

Quality worker was informed to invoke:

```bash
uv run python scripts/review_dossier_checks.py validate-receipts \
  --receipt-file content/dossier-review-receipts.json --json
```

Set `ITHILDIN_CONTENT_DIR` to the exact content tree to be built. Validator exits
1 for missing/stale/failed reviews or static blockers. No production receipt file
was created, so existing dossiers correctly remain outstanding review work until
actual semantic review happens. Do not generate baseline PASS receipts from old
DB verdicts to make release checks pass.

Root owns the new contract pointer in AGENTS.md/CLAUDE.md and the env-aware profile
resolution implementation. Source worker retains canonical_search_key and query
logging integration; helper calls are explicit workflow actions after output
inspection, not automatic inference from arbitrary adapter response JSON.

Receipt-file updates must be serialized by the parent (documented in the skill).
The validator proves artifact identity and receipt structure, not the truth of an
LLM's judgment; semantic review must actually be performed. Changes to any dossier
bytes, including embedded evidence, invalidate its receipt.
