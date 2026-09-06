---
name: review-dossiers
description: Automated checks + LLM editorial review for curated dossiers
---

# $review-dossiers

Run automated quality checks and LLM editorial review on curated dossiers. Reports issues and optionally auto-fixes deterministic problems. Results are tracked in `dossier_reviews` table in investigation.db.

## Arguments

- `--target "Name"` — review a single dossier
- `--batch` — review all curated dossiers
- `--batch N` — review top N (by finding count)
- `--fix` — auto-fix deterministic issues after review
- `--fix-only` — skip LLM review, just apply automated fixes
- No arguments — show summary metrics and review status

## Session Isolation

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
```

## Process

### Phase 1: Automated Checks

Run the deterministic check suite. Results are recorded to `dossier_reviews` table.

#### Single target:
```bash
uv run python scripts/review_dossier_checks.py check <slug> --output $WORKDIR/automated-<slug>.json
```

#### Batch:
```bash
uv run python scripts/review_dossier_checks.py batch --top N --output $WORKDIR/automated-results.json
```

#### No arguments (status overview):
```bash
uv run python scripts/review_dossier_checks.py summary
uv run python scripts/review_dossier_checks.py status
```

Read the JSON output. If `--fix-only` was specified, run fixes and stop:
```bash
uv run python scripts/review_dossier_checks.py fix <slug>
```

### Phase 2: LLM Editorial Review

With `--fix-only`, report that semantic review remains outstanding. Otherwise
review every selected dossier, including automated PASS results. Skip a semantic
re-review only when `validate-receipts --slug <slug>` passes for the exact current
content version. Automated PASS establishes structural checks, not claim support.

```bash
uv run python scripts/review_dossier_checks.py validate-receipts \
  --slug <slug> --output "$WORKDIR/prior-review-<slug>.json"
```

A missing/stale receipt means perform the review; do not convert an old database
verdict into a new receipt.

Read the dossier JSON:
```bash
Read: content/dossiers/<slug>.json
```

Read the automated check results from Phase 1 and copy their `content_sha256` into the semantic result. Review that exact dossier version and its cited evidence; changes invalidate the review.

**Review checklist** (what automated checks cannot evaluate):

1. **Claim-evidence alignment**: Read the actual finding and its source evidence for every material assertion. A valid or verified citation ID may still be unrelated to the prose. Preserve attribution for allegations and distinguish fact, inference, and synthesis; flag unsupported assertions as BLOCKING.

2. **Tone**: Encyclopedic and neutral throughout? Any editorializing or loaded language beyond the banned phrase list? Watch for:
   - Implying guilt or wrongdoing without evidence
   - Characterizations that serve narrative over accuracy
   - Status inflation ("most influential," "key operative")

3. **Lead quality**: Standalone — would a reader who only sees the lead understand the subject? Does it cover who/what, significance, and current status?

4. **Section-lead overlap**: Do sections repeat the lead rather than going deeper? Sections should add detail, not restate.

5. **Narrative coherence**: Do sections flow logically? Is the writing clear? Are transitions natural?

6. **AI tells**: Scan for these patterns:
   - Colon crutch: `[Statement]: [Explanation]`
   - "This reveals..." / "This indicates..." transitions
   - Stacked declaratives (3+ consecutive short S-V-O sentences)
   - Same subject starting 3+ consecutive sentences
   - Hand-holding (explaining why evidence matters right after showing it)
   - Filler transitions ("Importantly," "Notably," "Significantly")

7. **Open questions quality**: Are they specific, actionable, and evidence-gap-based? Not vague ("What else is there?") or leading ("Did X commit fraud?").

8. **system_role quality**: Neutral analytical language describing structural role or mechanism? No loaded terms ("operative," "dark money," "machine").

#### Output format

Write LLM findings to `$WORKDIR/review-<slug>.json`:

```json
{
  "slug": "<slug>",
  "content_sha256": "<hash from reviewed Phase 1 output>",
  "reviewer": "<reviewing agent or human>",
  "reviewed_at": "<actual ISO timestamp with timezone>",
  "verdict": "NEEDS_FIXES",
  "llm_issues": [
    {
      "severity": "SHOULD_FIX",
      "category": "claim_compliance",
      "detail": "Section 'Financial Flows': 'Epstein controlled Black's tax strategy' stated as fact but Finding #1234 is claim_type=inference",
      "location": "section:financial-flows"
    }
  ]
}
```

Categorize each issue as `BLOCKING`, `SHOULD_FIX`, or `SUGGESTION`. Verdict is
`FAIL` with any blocking issue, `NEEDS_FIXES` with any should-fix issue, otherwise
`PASS`; even a clean result explicitly includes `llm_issues: []`. Only the actual
reviewer supplies this judgment. A missing field is not an implicit pass.

#### Batch parallelism

For batch mode, launch review sub-agents in parallel (groups of 3-5):

```
Use `spawn_agent` with one bounded task per dossier group.
Prompt: "Review dossier <slug> for editorial quality. Read content/dossiers/<slug>.json and the automated check results at $WORKDIR/automated-<slug>.json. Apply the LLM review checklist [paste checklist]. Write results to $WORKDIR/review-<slug>.json. Do NOT modify the dossier — review only."
```

#### Persist completed reviews (single target or batch)

Read each reviewer's completed output. For each newly completed semantic review,
the parent serially persists the supplied reviews and receipts after checking
each reviewed hash. Reusing an existing valid receipt needs no new ingestion:

```bash
uv run python scripts/review_dossier_checks.py ingest-llm --dir "$WORKDIR"
uv run python scripts/review_dossier_checks.py receipt \
  --review-file "$WORKDIR/review-<slug>.json"
```

Receipts live in `content/dossier-review-receipts.json`; add one only for a
completed actual review, including its issues. The release validator rechecks
current bytes and automated blockers without using the private database.

### Phase 3: Compile Report

Merge automated + LLM results into a summary report. Print to console:

```markdown
# Dossier Review Report

## Summary
| Dossier | Auto Verdict | LLM Issues | Blocking | Should Fix | Coverage | Links |
|---------|-------------|------------|----------|------------|----------|-------|

## Issues by Dossier

### <name> — NEEDS_FIXES
**Automated:**
- [SHOULD_FIX] Missing crosslink: Glenn Dubin in "Key Relationships"
- [SHOULD_FIX] Banned phrase "raises questions" in lead

**Editorial:**
- [SHOULD_FIX] Section "Financial Flows" states inference as fact
- [SUGGESTION] Lead could mention jurisdiction

## Aggregate Metrics
- Total reviewed: N
- PASS: N | NEEDS_FIXES: N | FAIL: N
- Avg citation coverage: N%
- Avg outbound links: N
```

Also write the full report to `$WORKDIR/review-report.md`.

### Phase 4: Fix (if `--fix`)

For each dossier with fixable issues:

```bash
uv run python scripts/review_dossier_checks.py fix <slug>
```

This handles:
- Inserting missing cross-links (first mention per section, exact name matches only)
- Removing banned phrases from section titles

After fixing, re-run automated checks to confirm improvement:

```bash
uv run python scripts/review_dossier_checks.py check <slug> --output $WORKDIR/post-fix-<slug>.json
```

Print before/after comparison for each fixed dossier. Content changes invalidate previous semantic receipts; repeat semantic review on the changed version before claiming publication readiness.

## Automated Check Reference

These checks run deterministically in `scripts/review_dossier_checks.py`:

| # | Check | Severity | Auto-fixable |
|---|-------|----------|-------------|
| 1 | **Cross-link completeness** — names in text that have dossiers but aren't linked | SHOULD_FIX | Yes |
| 2 | **Banned phrase scan** — regex against editorial standards list | BLOCKING (titles/system_role), SHOULD_FIX (body) | Partial |
| 3 | **Structure validation** — has lead, has sections, no `<ul>`/`<ol>`, valid viz values | BLOCKING if missing lead/sections | No |
| 4 | **Citation coverage** — heuristic inline-ID coverage | SHOULD_FIX if <50%, SUGGESTION if <80%; not proof of support | No |
| 5 | **Claim type compliance** — inference/synthesis cited without attribution language | SHOULD_FIX | No |
| 6 | **Outbound link count** — flag if <5 cross-links | SUGGESTION | No |

## DB Tracking

All check/batch runs automatically record results to `dossier_reviews` table in investigation.db.

```bash
# View review status
uv run python scripts/review_dossier_checks.py status

# Publish gate (exits non-zero if any FAIL)
uv run python scripts/review_dossier_checks.py gate
```

The gate requires an exact-content semantic PASS receipt for every curated dossier and reruns static automated blockers. Missing, unbound, or stale reviews are outstanding review work; they do not acquire a PASS from an automated result or historical database row.

## Context Management

- Dossier JSONs are typically 50-200KB — read in full for review
- Use `--output` on all check commands to keep results in WORKDIR
- For batch LLM review, sub-agents read files from WORKDIR — read their output files instead of retrieving full transcripts
- Read cited findings and underlying source evidence selectively for claim support; automated citation checks cannot establish that support
