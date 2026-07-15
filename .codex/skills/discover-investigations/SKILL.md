---
name: discover-investigations
description: Corpus-wide editorial commissioning review that inventories all investigation profiles and configured corpora, surfaces and deduplicates major story candidates, audits their evidence and current novelty, and packages only the strongest as proposed dedicated investigations. Use when asked to scan the whole platform for big stories, article-scale leads, overlooked investigations, the next major investigation to launch, or scattered evidence that could sustain a long-form article. Do not use to research a known target, generate ordinary leads, or draft an article.
---

# $discover-investigations

Operate as an **Editorial Plane commissioning orchestrator**. Review the platform broadly, identify candidate mechanisms or systems, and decide which ones justify a dedicated investigation. Do not turn editorial judgments into research findings.

Read [references/candidate-rubric.md](references/candidate-rubric.md) before screening, scoring, or writing outputs.

## Arguments

- No arguments: review every profile and configured local corpus; return at most 5 launch candidates.
- `--profile SLUG`: constrain discovery to one profile while still checking cross-profile overlap.
- `--focus TEXT`: favor a public-interest domain without excluding counter-signals.
- `--top N`: set the finalist cap; never exceed 5.
- `--since YYYY-MM-DD`: emphasize evidence created or events occurring after the date while retaining older context.
- `--dry-run`: build the scope and coverage plan only; do not register an analysis run or write durable outputs.

## Non-Negotiable Boundaries

- Use `uv run python` for every Python command.
- Use public and lawfully available sources only. Do not contact subjects or third parties.
- Treat this skill as read-only discovery except for its analysis-run audit row, novelty search logs, and final report/manifest.
- Do not create or modify findings, connections, entities, hypotheses, tags, leads, profiles, story clusters, articles, or queue jobs.
- Do not run `auto_leads.py`, submit dispatcher jobs, or invoke `$init-investigation` during discovery.
- Do not promote a candidate automatically. Stop for an explicit user choice.
- Do not call a review “full corpus” unless every configured corpus received semantic review. If any source was index-only, unavailable, or excluded, use “platform-wide index review” and name the limitation.
- Count the same document mirrored or re-OCR'd by multiple tools once. Reporting is prior-art/context, not primary corroboration.
- Keep fact, inference, allegation, and unknown separate. Never make an inference load-bearing for the evidence gate.
- Permit a result of **no launch recommendation**. Do not lower the bar to fill a list.

## Workflow

### 0. Create an Isolated Run

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
DATE=$(date +%F)
uv run python tools/investigation_context.py show
```

Load the active profile for ambient context, but do not change it and do not let it silently scope an all-profile run.

For a normal run, register a platform-wide analysis run. Pass an empty profile ID so the snapshot is global rather than silently scoped to the active profile.

```bash
uv run python -c "
from tools.analysis_export import start_analysis_run
print(start_analysis_run('discover-investigations', profile_id=''))
"
```

Store the printed `RUN_ID`. If the run fails, call `fail_analysis_run(RUN_ID, reason)` before stopping.

### 1. Freeze the Review Universe

Export a reproducible database snapshot with evidence and profile fields:

```bash
uv run python .codex/skills/discover-investigations/scripts/export_snapshot.py \
  --db investigation.db \
  --repo-root . \
  --output "$WORKDIR/platform-snapshot.json"
```

Export complementary derived views:

```bash
uv run python tools/analysis_export.py entity-network --all-profiles --output "$WORKDIR/entities.json"
uv run python tools/analysis_export.py connections-graph --all-profiles --output "$WORKDIR/connections.json"
uv run python tools/analysis_export.py timeline-export --all-profiles --output "$WORKDIR/timeline.json"
uv run python tools/analysis_export.py coverage-matrix --all-profiles --top 500 --output "$WORKDIR/coverage.json"
uv run python tools/tag_manager.py list-values --output "$WORKDIR/tags.json"
uv run python pipeline/story_clustering.py --list
uv run python tools/investigation_context.py list
uv run python tools/source_report.py
```

Do not dump the full snapshot into model context. Query it with `jq` or small read-only `uv run python` selectors and create per-track packets. Keep a reviewer packet to roughly 25–50 documents and at most 100,000 characters; give oversized documents their own packet.

Inventory existing editorial work and prior candidate reviews with `rg --files` across:

- `content/articles/`
- `content/dossiers/`
- `content/clusters.json`
- `reports/`
- `research/`
- `investigations/*/config.yaml`

Record snapshot counts, max IDs, profile IDs, git commit/dirty state, article/dossier/report inventories, and the exact cutoff time. Later-arriving evidence belongs to a later run.

### 2. Build a Corpus Coverage Ledger

Read every investigation config and union its `corpus_tools`. For each configured corpus, record:

| Corpus | Profiles | Health | Review level | Queries/slices | Result | Limitation |
|---|---|---|---|---|---|---|

Record each local sidecar's path, size, modification time, row count, and high-water mark where available. If a sidecar changes after the cutoff, keep the original bound or flag the run as non-frozen; do not mix moving records into a supposedly reproducible snapshot.

Use exactly one review level:

- `semantic`: relevant record text was searched or reviewed in batches.
- `index`: metadata, entity, frequency, or coverage indexes were reviewed, but not all text.
- `unavailable`: the source failed or required access not present.
- `excluded`: outside the stated scope, with a concrete reason.

For very large corpora, review the full index and stratified/high-signal slices first. Open full primary records only for finalists. Never imply that millions of raw pages were read serially.

Within each large corpus, account separately for curated/structured records, high-value document forms (agreements, invoices, wires, statements, court records, KYC/compliance, trusts, and reports), coverage gaps, and a sample of null/unknown classifications. Treat rank-limited search results with no count or cursor as `index`, not exhaustive coverage.

Treat source families correctly:

- Use government, court, registry, regulatory, and original document records as primary evidence.
- Use `epstein_reporting.db`, media corpora, and web reporting to locate prior art or context, not to corroborate the allegations they repeat.
- Preserve charge/allegation/conviction language from government releases and court records.

### 3. Run Discovery Wave in Parallel

Use available subagents as independent, read-only discovery tracks. Give each the frozen snapshot path plus only its relevant slices and raw indexes, the same candidate schema from the rubric, and a unique `$WORKDIR/report-discovery-*.md` output. Do not leak one track's candidates to the others before they finish.

Assign these tracks:

1. **Evidence reservoir** — scan strong findings, unresolved high-priority leads, hypotheses, prior reports, dossiers, and unfinished story clusters for mechanisms that have not been commissioned.
2. **Cross-profile structure** — scan shared entities, institutional bridges, financial flows, repeated counterparties, timeline clusters, and conflicts across profiles.
3. **Raw-corpus coverage gaps** — scan configured corpus indexes for high-volume or high-specificity people, entities, transactions, and document classes with little findings coverage.

Require each track to:

- Return 5–15 raw candidates, not a ranked top list.
- Anchor each candidate to at least 3 concrete finding IDs or primary record IDs.
- State the mechanism and public consequence, not merely a notable person or odd fact.
- Identify the existing profile, article, cluster, report, or lead that may already own the scope.
- Separate established facts, inferences, allegations, and missing records.
- Record filtered signals and reasons so later runs do not rediscover them.
- Write only inside `$WORKDIR`; make no database or repository changes.

### 4. Merge, Deduplicate, and Apply Hard Gates

Merge candidates by underlying event/mechanism, not headline wording. Check exact names, aliases, amounts, document IDs, counterparties, and proposed scope against:

- existing profiles and threads;
- active/completed/dead-end leads;
- hypotheses and competition groups;
- story clusters, articles, dossiers, research memos, and prior candidate manifests.

Apply Gates G0–G3 from the rubric. Cap the merged longlist at 20. Exclude candidates that are:

- one ordinary lookup or missing document;
- already commissioned under an existing profile;
- merely an article angle inside an existing well-scoped investigation;
- supported only by a secondary allegation or unresolved identity match;
- sensational but unable to explain a consequential mechanism.

Route excluded candidates to `merge`, `watchlist`, or `reject`; do not create operational leads.

### 5. Stress-Test Finalists in Parallel

Take no more than 8 provisional finalists into a second independent wave. Assign three read-only audits across the same finalist set:

1. **Evidence audit**
   - Open load-bearing findings and primary records.
   - Verify identities, dates, amounts, quotes, claim types, verification state, and source-family independence.
   - Use canonical crosswalks and `independence_group` values where a derived corpus provides them.
   - Check finding relations for disputed, retracted, contradicted, or superseded evidence.
   - Downgrade or reject any candidate whose core claim does not survive.

2. **Novelty and prior-art audit**
   - Check `check_searched(query, source)` before repeating repository searches.
   - Search current reporting with exact combinations of name, amount, identifier, unusual phrase, counterparty, and mechanism.
   - Log new searches without inventing a session ID.
   - Distinguish a new fact, a new linkage, a new assembled mechanism, a follow-up, and a well-covered story.
   - Say “apparently unreported as of DATE,” never “unreported.”

3. **Skeptic and commissioning audit**
   - State the best innocent explanation and strongest counter-evidence.
   - Identify defamation, privacy, identity-resolution, allegation-laundering, and causal-overreach risks.
   - Test whether the scope supports at least 3 falsifiable workstreams and 3 specific next records.
   - Identify kill criteria and the cheapest decisive test.
   - Reject association-only, salacious-only, victim-identifying, or unresolved-identity premises.

Require each auditor to write a separate `$WORKDIR/report-audit-*.md`. Reconcile disagreements from the artifacts, not agent confidence.

### 6. Score Only Candidates That Pass Every Gate

Apply Gates G4–G7 and the 100-point rubric. Use two independent scores. Ask the skeptic to adjudicate if totals differ by more than 10 points or any weighted dimension differs by more than 5 points.

Classify each candidate:

- `launch`: all gates pass, total at least 80, dimension floors pass, readiness at least 3.
- `watchlist`: total 70–79 or one named decisive record remains missing.
- `merge`: the work belongs in an existing profile, cluster, or article.
- `reject`: below threshold, duplicate, unsafe, or not tractable.

Return at most 5 `launch` candidates and 5 `watchlist` candidates.

### 7. Persist the Commissioning Memo and Manifest

Create both files:

```text
reports/investigation-candidates/YYYY-MM-DD-run-RUN_ID.md
reports/investigation-candidates/YYYY-MM-DD-run-RUN_ID.json
```

Create the directory if needed, then use `apply_patch` for both durable files. Keep all intermediate artifacts in `$WORKDIR`.

Use the exact memo and manifest contracts in the rubric. Include:

- scope snapshot and coverage ledger;
- ranked launch table and watchlist;
- complete candidate packets;
- closest existing work and novelty searches;
- filtered-out candidates with stable IDs and reasons;
- unresolved limitations and data-quality exclusions;
- proposed profile slug, 3–7 threads, and 5–10 seed leads for each launch candidate;
- the explicit statement that no investigation was initialized.

Do not create an empty launch section containing weak substitutes. Say that no candidate passed.

Complete the analysis run with zero created research objects and paths to both artifacts in `notes`:

```bash
uv run python -c "
import json
from tools.analysis_export import complete_analysis_run
complete_analysis_run(
    RUN_ID,
    findings_created=0,
    hypotheses_created=0,
    leads_created=0,
    tags_created=0,
    report_path='reports/investigation-candidates/YYYY-MM-DD-run-RUN_ID.md',
    notes=json.dumps({
        'manifest': 'reports/investigation-candidates/YYYY-MM-DD-run-RUN_ID.json',
        'scope': 'all_profiles',
        'snapshot_cutoff': 'ISO-8601 timestamp'
    }, sort_keys=True)
)
"
```

### 8. Return and Stop

Report the review scope, launch count, top candidate, report paths, and material coverage gaps. Ask the user which candidate—if any—to promote. Do not initialize it in the same run.

## Promotion Is a Separate Task

Only an explicit user selection authorizes promotion. On that later task:

1. Re-open the selected candidate packet and verify that its decisive facts have not changed.
2. Run `$init-investigation "<candidate>" --dry-run` first.
3. Show the proposed profile slug, scope, threads, key people, corpus tools, dates, pillars, and seed leads.
4. After confirmation, create one profile through `$init-investigation`; never create a database-only profile.
5. Seed 5–10 operational leads inside the new profile and update the candidate manifest with the promoted profile and timestamp.

## Handoffs

- Use `$generate-hunches` when the task is theory-building inside an existing investigation.
- Use `$landscape-scan` when the area is known but its actors need quick mapping.
- Use `$deep-investigate` or `$pursue-lead` after a target or operational lead is selected.
- Use `$init-investigation` only after a candidate is commissioned.
- Use `$write-article` only after evidence is organized into a story cluster.
