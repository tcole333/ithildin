---
name: review-dossiers
user-invocable: true
description: Run structural checks and evidence-based editorial review for curated dossiers, optionally applying deterministic fixes. Use for dossier quality/release review; use review-article for investigative articles.
---

# /review-dossiers

Review the actual final dossier content. Automated checks validate structure and citation plumbing; a semantic review must establish claim support. Exact-content review receipts remain required for publication.

## Inputs and context

- `--target "Name"`: resolve one dossier using `content/dossiers/_index.json` and the actual file.
- `--batch`: all curated dossiers; `--batch N`: top N by finding count. This is a selection convenience, not a measure of importance.
- `--fix`: apply authorized deterministic fixes before semantic review.
- `--fix-only`: apply deterministic fixes and structural checks; report semantic review outstanding.
- No arguments: report `summary` and `status` from `scripts/review_dossier_checks.py`.

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin profile/database before scoped work. Create `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`. Use the current checkout and preserve unrelated edits. Keep selected slugs, artifact paths, completed content hashes and remaining work in a progress note; continue from that state through long batches/compaction.

The checker records results in the selected investigation DB. Use `--no-record` on `check`/`batch` when a read-only audit was requested. Do not infer authorization to fix from a review-only request.

## 1. Prepare final content and automated packets

If `--fix` or `--fix-only` was requested, apply the bounded deterministic fixes to each selected dossier first:

```bash
uv run python scripts/review_dossier_checks.py fix <slug>
```

This inserts exact-name crosslinks and corrects prohibited title phrases. Inspect the diff. It does not establish claim support. Apply any other already-authorized corrections before reviewing final bytes where practical.

Then check the selected content:

```bash
uv run python scripts/review_dossier_checks.py check <slug> \
  --output "$WORKDIR/automated-<slug>.json"
uv run python scripts/review_dossier_checks.py batch --top N \
  --output "$WORKDIR/automated-results.json" --packet-dir "$WORKDIR"
```

Choose single or batch, not both. Omit `--top N` to review all curated dossiers. Batch writes one aggregate result plus an actual `automated-<slug>.json` file per dossier, with `content_sha256`. Verify every selected slug has a packet. If `--fix-only`, report the fixes/checks and outstanding semantic review, then finish.

## 2. Semantic review

Review every selected dossier, including structural PASS results, unless a current receipt validates:

```bash
uv run python scripts/review_dossier_checks.py validate-receipts \
  --slug <slug> --output "$WORKDIR/prior-review-<slug>.json"
```

A missing/stale receipt requires review. Do not turn a historical DB verdict into a new receipt. Review the exact version hashed by the automated packet; concurrent changes require a new packet and review of the affected content.

Start with narrative fields, the automated packet, cited findings and relationship context. Retrieve underlying primary evidence for every material assertion, expanding to full documents/dossier context when needed. Avoid loading unrelated machine metadata simply because it shares a JSON file.

Evaluate:
- **Claim support:** actual source supports the precise assertion, identity, date, amount and relationship. A valid citation can be unrelated. Unsupported material claims are BLOCKING.
- **Attribution:** distinguish fact, inference, synthesis and allegation; preserve charge/conviction language, provenance and confidence ceilings. Do not infer intent or guilt from association.
- **Neutrality and significance:** reference prose is encyclopedic. Avoid loaded characterizations, status inflation and prominence based merely on finding count.
- **Clarity:** standalone lead, topical sections adding detail, coherent explanations and accurate source framing. Evaluate language in context, not by a quota of short sentences or repeated subjects.
- **Open questions:** specific, testable evidence gaps rather than leading accusations.
- **System role:** explain the structural mechanism neutrally, without internal investigation-process jargon.
- **Rendering and links:** current citation tokens, existing crosslinks, valid visualization data and claims consistent with the rendered content.

For a substantial batch, use independent chat-native subagents with disjoint dossier groups. Inherit the configured runtime model. Give each reviewer pinned context, the actual per-slug packet path, dossier path, this checklist, output schema and unique `review-<slug>.json` path. Review workers do not edit shared dossiers; the parent collects every output or explicit failure, handles authorized revisions, and persists results serially. Stay engaged with user steering; no unattended/headless job is needed.

Write each actual review:

```json
{
  "slug": "<slug>",
  "content_sha256": "<SHA-256 of raw dossier bytes, matching the automated packet's content_sha256>",
  "reviewer": "<actual reviewing agent or human>",
  "reviewed_at": "<actual ISO timestamp with timezone>",
  "verdict": "NEEDS_FIXES",
  "llm_issues": [
    {
      "severity": "SHOULD_FIX",
      "category": "clarity",
      "detail": "A concrete issue, its evidence and proportionate correction.",
      "location": "section:background"
    }
  ]
}
```

Verdict is `FAIL` for any BLOCKING issue, `NEEDS_FIXES` for any SHOULD_FIX, otherwise `PASS`. Suggestions use `SUGGESTION` severity. A clean review explicitly includes `llm_issues: []`. Only the actual reviewer supplies the judgment; absent fields are not implicit PASS.

## 3. Revisions, persistence and report

If fixes beyond deterministic preparation are authorized, apply them and review affected claims on the changed version before recording a final receipt. Reuse unchanged evidence work, but never attach an earlier content hash to changed prose. Do not repeatedly review unchanged valid content merely to complete another pass.

The parent checks each completed output and current hash, then persists supplied reviews and receipts serially:

```bash
uv run python scripts/review_dossier_checks.py ingest-llm --dir "$WORKDIR"
uv run python scripts/review_dossier_checks.py receipt \
  --review-file "$WORKDIR/review-<slug>.json"
```

Run ingestion once after collecting the completed batch; write one receipt per actual review. If the user requested a read-only report, leave results in WORKDIR and report that durable review tracking was not updated. Do not manufacture receipts for missing reviews.

Receipts live in `content/dossier-review-receipts.json`. Preserve exact-content binding and the independent static blockers: the release validator checks current bytes without the private DB. `uv run python scripts/review_dossier_checks.py gate` requires current semantic PASS receipts for all curated dossiers. A scoped review is not proof that the platform-wide gate passes.

Write `$WORKDIR/review-report.md`: selected/reviewed/reused/incomplete dossiers; final hashes; automated versus semantic results; actionable issues with evidence; changes made; unresolved checks and publication limitations. Include before/after effects for fixes. Do not equate coverage percentages or link counts with factual support, and do not claim publication readiness from an automated PASS.
