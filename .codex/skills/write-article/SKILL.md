---
name: write-article
description: Write or substantially revise an evidence-heavy investigative MDX article from a story cluster. Use for drafting or major rewrites; use review-article for review without rewriting and curate-dossier for encyclopedic reference pages.
---

# $write-article

Produce an article whose argument is supported by primary evidence and whose structure helps the reader understand the mechanism.

## Inputs and setup

- A cluster ID selects the evidence base. With no target, list clusters using `uv run python pipeline/story_clustering.py --list`.
- A requested rewrite may start from an existing article path and its linked cluster.
- `--dry-run` produces the research dossier and proposed structure only.

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the requested profile/database before scoped work. Use the current worktree root, `uv run python`, and one isolated directory:

`WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`

Use chat-native subagents when independent research or review helps. Inherit the configured model; give each worker the pinned context, bounded question, source ownership, unique report path, and mutation policy. The parent stays engaged, collects every expected artifact or explicit failure, reconciles contradictions, and owns article edits. Do not launch unattended jobs to carry out an interactive article request.

Keep a short progress note in WORKDIR with the selected article, context, artifacts, completed checks and remaining work. Resume from those artifacts after compaction; continue until the requested draft/revision is complete or a concrete dependency prevents further work.

## 1. Assemble the evidence and argument

For a cluster:

`uv run python pipeline/story_clustering.py --cluster <CLUSTER_ID>`

Read its entry in `content/clusters.json` selectively. Identify the central question, strongest findings, source independence, counter-evidence, missing records and any existing article. Use the source-applicability checklist and module docs in the research contract to plan relevant research. Reuse complete, current result artifacts through the shared reuse workflow. A corpus miss or unavailable source is a coverage gap, not proof that an event did not happen.

For substantial gaps, delegate independent questions (for example corpus records, financial mechanism or legal context) with unique `report-*.md` outputs. Track searched/reused/partial/unavailable/not-applicable coverage and collect the source records needed to verify material claims. Read enough of each original document to understand qualifications, allegations and surrounding context; do not rely on a clipped search excerpt for a load-bearing conclusion.

Write `research-dossier.md` and `article-structure.md` in WORKDIR:
- Central question and supported thesis; strongest alternative explanation.
- Material findings with IDs, exact evidence refs/quotes, relevant dates and source artifacts.
- Source independence, contradictions, unresolved identity/provenance issues and bounded gaps.
- Proposed sections: claim, supporting evidence, explanatory purpose and useful visualizations.

Choose length, cast and structure for the evidence and audience. The craft guidance in `research/craft-principles.md` offers defaults and examples, not quotas or mandatory rhetorical patterns. An opening scene, transaction chain, timeline or explanatory hook may work; surprise is not a requirement. Do not add sources, characters or sections merely to hit a count.

## 2. Draft

Write `content/articles/<cluster-id>.mdx`. Explain how the mechanism works and why it matters. Keep fact, allegation, inference and speculation distinguishable; article analysis may draw supported conclusions without becoming a dossier. Do not infer intent from an outcome, independence from source-type counts, or inactivity from collection gaps.

Preserve exact dates/figures where the claim depends on them; otherwise use justified precision without overstating the source. Cite, qualify or remove contextual claims. Mark unresolved draft claims with `<!-- VERIFY: claim and needed evidence -->` until reviewed.

Use the citation system in `docs/CITATION_SYSTEM.md` and the current registry in `web/src/lib/citations.ts`. Examples: `[Finding #42]`, `[EFTA02576529]`, `[SEC:0001193125-15-266790]`, or a source-linked Markdown citation for contextual material. Every factual sentence needs its own explicit citation; an adjacent sentence's citation does not establish its support. A citation ID alone is not proof that the source supports the claim.

Frontmatter:

```yaml
---
title: "[TITLE]"
subtitle: "[SUBTITLE]"
cluster: <cluster-id>
targets: "[comma-separated targets]"
date: "[YYYY-MM-DD]"
status: draft
word_count: 0
---
```

Replace the word count with the actual count. Do not add an Evidence Index (automatically generated) or an Editor's Note. Link an existing dossier on the subject's first mention and related articles where useful.

When a visualization improves understanding, create its source JSON under `content/{timelines,financials,ego,structures}/`, provide the corresponding runtime asset under `web/public/content/`, and check that the embedded data agrees with the text. Use current analytical models from `content/models/` only when supported, retaining boundary conditions and counter-evidence.

## 3. Verify the requested current content

Run a scoped evidence report on the current article:

```bash
uv run python scripts/evidence_audit.py report \
  --article "content/articles/<cluster-id>.mdx" \
  --output "$WORKDIR/evidence-audit.json"
npm --silent --prefix web run report:support-coverage -- \
  --file "content/articles/<cluster-id>.mdx" > "$WORKDIR/support-coverage.json"
```

The audit honors the pinned database/profile. Add `--source-texts "$WORKDIR/source-texts.json"` when primary text artifacts are available. That JSON maps exact evidence references to UTF-8 file paths, optionally `{"REF": {"path": "record.txt"}}`; relative paths resolve beside the JSON. For a local EFTA OCR corpus, pass its actual path with `--documents-db`. No corpus path is assumed.

Inspect audit `status`, `checks_complete`, quote mismatches, missing/out-of-profile findings and unmapped citations. Unavailable source text is `unknown`; obtain/read the source or document the unresolved check. A full normalized quote match only proves textual presence. Assess the actual claim, allegation attribution, source independence and reliability yourself. Source-overlap candidates are not adjudicated duplicates and do not block an unrelated article.

Confirm the coverage result includes the requested path and current content hash. This explicit mode works for new, modified and unchanged articles. Coverage is structural instrumentation, not semantic verification.

Use `$review-article` for the final draft, preferably with an independent chat-native reviewer on substantial articles. Give the reviewer the exact article and evidence artifact paths, not a desired verdict. It returns `verification-report.md` to WORKDIR. If independent review is unavailable, say so and perform the substantive checks; do not invent another reviewer.

## 4. Revise and finish

Resolve unsupported material assertions, wrong citations/amounts, source mismatches, causal overreach and legal errors. Consider quality suggestions using editorial judgment; no mandatory rewrite for harmless sentence patterns. Verify changed claims and rerun affected checks on final bytes. Reuse unchanged valid evidence work, but never call a changed article reviewed solely because an earlier draft passed.

Run `npm --prefix web run build` from the owned checkout and inspect its exit status/output. Do not pipe away failure status. Follow the shared publication validation path for any separately authorized release.

Return the article path, actual word/citation counts, thesis, completed verification, final content version, and any unresolved evidence or access limitation. Distinguish draft completion from publication readiness. Do not publish as part of an article-writing request unless publication was authorized.
