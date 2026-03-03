---
name: write-article
description: Generate a long-form investigative MDX article from a story cluster using a five-phase workflow (research dossier, structure, draft, verify, revise). Use for evidence-heavy article writing or major article rewrites.
user_invocable: true
---

# /write-article

Generate a deep-dive investigative article from a story cluster. Use this pipeline:

Phase 0 `research dossier` -> Phase 1 `structure` -> Phase 2 `draft` -> Phase 3 `verify` -> Phase 4 `revise`.

## Arguments

- Required: cluster ID (example: `/write-article <cluster-id>` — run `uv run python pipeline/story_clustering.py --list` for available clusters)
- Optional `--dry-run`: run only Phase 0 and stop after the dossier
- No arguments: list available clusters

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

## Non-Negotiable Defaults

- Use `uv run python` for every Python command.
- Create one isolated workspace per run:
  `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`.
- Use `--output $WORKDIR/<file>.json` for searches when supported.
- Keep context lean: read `report-*.md` files first, open raw JSON only for targeted verification.
- Prefer system explanation over event recitation (about 60/40).
- For contextual claims, use `cite`, `soften`, or `delete`.
- Use exact dates, exact figures, and inline citation tokens.
- Read `research/craft-principles.md` for full writing craft rules.

---

## Pipeline Overview

```
Phase 0: RESEARCH DOSSIER -> $WORKDIR/research-dossier.md
Phase 1: STRUCTURE        -> $WORKDIR/article-structure.md
Phase 2: DRAFT            -> content/articles/<cluster-id>.mdx
Phase 3: VERIFY           -> $WORKDIR/verification-report.md
Phase 4: REVISE           -> updated article + revision summary
```

---

## Phase 0: Research Dossier

Search across corpus + structured + legal/network sources. Use corpus tools from the investigation profile rather than assuming specific corpus databases.

### 0.1 Discover Cluster Context

No args:

```bash
uv run python pipeline/story_clustering.py --list
```

With a cluster:

```bash
uv run python pipeline/story_clustering.py --cluster <CLUSTER_ID>
```

Read `content/clusters.json`, locate the selected cluster, and capture:
- title
- targets
- `source_diversity`
- `unsearched_sources`

### 0.2 Evidence Integrity Gate

```bash
uv run python scripts/evidence_audit.py report
```

Block writing if any are true:
- >10% of **document-sourced** evidence rows have missing `source_quote`
- Any `direct_quote`/`confirmed` finding has a cross-check mismatch
- >5 unresolved duplicate clusters within the article's scope

Evidence category rules:
- **Document** (EFTA, DOJ, court filings, etc.): `source_quote` required — quote proves claim is in actual document
- **Structured** (FEC, IRS 990, ACRIS, FARA, LDA, SEC, etc.): `source_quote` optional — the evidence_ref itself is the verification. Quote can hold extracted values (e.g., `"amount: $650,000; recipient: IPI"`)
- **Web/Media** (URLs, GDELT, etc.): `source_quote` recommended but not blocking — URLs go dead, quote preserves context

### 0.3 Source Diversity Assessment

From `source_diversity`, explicitly note:
- dominant source type and percentage
- available source types
- underrepresented source types to prioritize in drafting

### 0.4 Parallel Research Tracks (A/B/C)

Run three tracks in parallel and write markdown reports:
- `$WORKDIR/report-corpus.md`
- `$WORKDIR/report-financial.md`
- `$WORKDIR/report-legal.md`

Track A: Corpus deep-dive
```
# Search all corpus tools from the investigation profile.
# For each corpus_tool in the profile, run:
uv run python tools/<corpus_tool>.py search "<QUERY>" --limit 20 --output "$WORKDIR/corpus-<tool-name>.json"

# For tools supporting sub-commands (emails, docs, entities, triples), run those too.
# Pull full text for key references found in search results.
```

Track B: Financial/corporate/property
```
uv run python tools/query_edgar.py search "<TARGET>" --size 20 --output "$WORKDIR/fin-edgar.json"
uv run python tools/query_990.py search "<TARGET>" --output "$WORKDIR/fin-990.json"
uv run python tools/query_acris.py party "<TARGET>" --output "$WORKDIR/fin-acris.json"
uv run python tools/parse_ds10_financials.py query --entity "<TARGET>" > "$WORKDIR/fin-ds10.txt"
uv run python tools/query_fec.py donor "<TARGET>" --limit 20 --output "$WORKDIR/fin-fec-donor.json"
uv run python tools/query_fec.py employer "<TARGET>" --limit 20 --output "$WORKDIR/fin-fec-employer.json"
uv run python tools/query_registry.py search "<TARGET>" --output "$WORKDIR/fin-registry.json"
uv run python tools/query_gleif.py search "<TARGET>" --limit 10 --output "$WORKDIR/fin-gleif.json"
uv run python tools/ingest_faa.py --json search "<TARGET>" --limit 20 > "$WORKDIR/fin-faa.json"
```

Track C: Legal/court/network
```
uv run python tools/query_courtlistener.py search "<TARGET>" --limit 20 --output "$WORKDIR/legal-cl.json"
uv run python tools/query_fara.py search "<TARGET>" --limit 20 --output "$WORKDIR/legal-fara.json"
uv run python tools/query_lobbying.py client "<TARGET>" --limit 20 --output "$WORKDIR/legal-lda-client.json"
uv run python tools/query_lobbying.py registrant "<TARGET>" --limit 20 --output "$WORKDIR/legal-lda-registrant.json"
uv run python tools/query_littlesis.py search "<TARGET>" --output "$WORKDIR/legal-littlesis.json"
uv run python tools/query_aleph.py search "<TARGET>" --schema Person --output "$WORKDIR/legal-aleph-person.json"
uv run python tools/query_aleph.py search "<TARGET>" --schema Company --output "$WORKDIR/legal-aleph-company.json"
uv run python tools/query_icij.py search "<TARGET>" --output "$WORKDIR/legal-icij.json"  # optional; requires Neo4j
uv run python tools/query_opensanctions.py search "<TARGET>" --limit 20 --output "$WORKDIR/legal-sanctions.json"
uv run python tools/query_gdelt.py articles "<TARGET>" --limit 20 --timespan 3m --output "$WORKDIR/legal-gdelt.json"

# Also perform web search for recent legal/news outcomes when contextual claims depend on it.
```

For each track report, include:
- sources searched
- top findings with citation IDs
- negative results
- candidate leads for corroboration

### 0.5 Synthesize Dossier

Wait for all track reports, then write `$WORKDIR/research-dossier.md`:

```markdown
# Research Dossier: [CLUSTER TITLE]

## Evidence Inventory
| Source Type | Count | Key Items |
|-------------|-------|-----------|
| DOJ corpus  | 280   | [key document IDs and descriptions] |
| SEC EDGAR   | 12    | 10-K disclosures, Form D filings |
| IRS 990     | 8     | Gratitude America grants |
| ACRIS       | 15    | Property transfers |
| CourtListener | 6   | USVI v. JPMorgan docket |
| FEC         | 4     | Bundled contributions |
| Registry    | 22    | FL/NY/USVI shell entities |
| Other       | 18    | LittleSis, FARA, LDA |
| **Total**   | **365** | |

## Source Diversity
- Dominant source: EFTA (76.7%)
- Source types used: 8
- Diversity floor met: [yes/no] (need 3+ types if 4+ available)

## Top 50-80 Findings (ranked for explanatory value)
[Findings selected for mechanism-revealing quality, not just relevance]

## Multi-Source Corroboration Chains
[Where the same claim is supported by 2+ independent source types]

## Gaps / Negative Results
[What was searched but not found — absence is evidence]

## Suggested Narrative Entry Points
[Most surprising findings that could open the article]
```

If `--dry-run`, output the dossier to the user and stop.

---

## Phase 1: Structure

Use the dossier (not raw cluster JSON) to design the argument.

### 1.1. Find the Structural Hook

Choose one counterintuitive system-level finding as the opening.

### 1.2. Build Argument Skeleton

For each proposed section, list:
- The claim(s) it makes
- The evidence supporting those claims (with source types)
- The explanatory function (what does the reader learn here?)

### 1.3. Apply Evidence Budget

Target: 30-50 findings cited in a 5,000-word article. Selection criteria:
- Does this reveal a *mechanism*, not just an event?
- Does it connect to another investigation thread?
- Is it primary-sourced?
- Is it specific (exact date/amount/entity)?

**Source diversity floor**: If the cluster has evidence from 4+ source types, the article must cite at least 3 types. Don't let EFTA crowd out SEC filings, 990 data, or ACRIS records when they provide independent corroboration.

### 1.4. Cast Characters

- **3-5 principals** who appear throughout
- **8-12 supporting characters** who appear in specific sections
- **Everyone else** referenced by role, not fully characterized
- Character ceiling: 7-12 named characters max

### 1.5. Map Dual Spine + Visualization Opportunities

- **Holding spine**: timeline, person, transaction chain
- **Depth spine**: system explanation, regulatory framework
- **Visualizations**: where would TimelineChart, SankeyDiagram, EgoNetwork, CorporateStructure, or TransactionTable genuinely help?

Output: `$WORKDIR/article-structure.md`

---

## Phase 2: Draft

Writing priorities:
- **Lead with surprise.** The counterintuitive finding from Phase 1 is your opening.
- **Weave the counterfactual throughout.** "What should have happened" at each step, not bolted on at the end.
- **Use documents as plot points.** Paraphrase context, then quote the devastating line.
- **Note missing documents.** Absence is evidence.
- **Establish stakes before mechanism.** Tell the reader what happens when the system fails BEFORE explaining how it works.
- **Mark uncertainties inline** with `<!-- VERIFY: claim -->` HTML comments for Phase 3 to check.

### Citation format

Use the structured citation tokens that render as linked footnotes:
- `[EFTA02576529]` — DOJ corpus document
- `[SEC:0001193125-15-266790]` — SEC EDGAR filing
- `[990:133095231]` — IRS 990 via ProPublica
- `[ACRIS:2008012900966001]` — NYC ACRIS property record
- `[CL:4608967]` — CourtListener docket
- `[FEC:C00431569]` — FEC committee
- `[FARA:6071]` — FARA registration
- `[REG:FL:P950000272]` — State corporate registry
- `[DS10]` — DS10 financial dataset
- `[text](url)` — Markdown link for contextual claims

Evidence-support mapping now runs at sentence granularity in the web UI:
- Every factual sentence must carry explicit inline citation tokens in that same sentence.
- Do not rely on citations in adjacent sentences; support mode will mark those claims unsupported.

### Article format

Write `content/articles/<cluster-id>.mdx` with YAML frontmatter:

```mdx
---
title: "[TITLE]"
subtitle: "[SUBTITLE]"
cluster: <cluster-id>
targets: "[comma-separated targets]"
date: "[YYYY-MM-DD]"
status: draft
word_count: ~XXXX
---

[Article body — structure driven by evidence, not template]
```

Do not include:
- Evidence Index section (auto-generated from citations)
- Editor's Note section

### Create visualization data files

When you encounter a section where a visualization genuinely helps, create the JSON data file during writing:
- `content/{timelines,financials,ego,structures}/` for source data
- Copy to `web/public/content/` for runtime fetch
- Embed: `<div data-viz="TimelineChart" data-src="/content/timelines/cluster-name.json" data-height="420" data-group-by="entity"></div>`

### Analytical model callouts

When evidence exemplifies an analytical model, insert a callout block:
```mdx
> **Manufactured Dependency** — Creating conditions for problems, then selling the solution. [Full analysis →](/models/manufactured-dependency)
>
> Evidence: [CITATION_ID] — [Specific evidence from corpus supporting this model application]
```

Available models: manufactured-dependency, bridge-tax, private-order, narrative-shield, jurisdictional-arbitrage, parallel-financial-system, enabler-gradient, complexity-as-credential.

### Save and build

Save to `content/articles/<cluster-id>.mdx`, then:
```bash
cd /Users/travcole/projects/osint-research/web && npx astro build 2>&1 | tail -5
```

---

## Phase 3: Verify

Run `/review-article <cluster-id> --workdir $WORKDIR`. The reviewer writes `$WORKDIR/verification-report.md` with:

- **BLOCKING** (must fix before publication)
- **SHOULD FIX** (significant quality issues)
- **SUGGESTIONS** (optional improvements)
- **SOURCE DIVERSITY** (citation type breakdown, available but uncited evidence)
- **AI TELL SCAN** (language pattern detection)

The reviewer does NOT edit the article directly — it reports problems for Phase 4 to fix.

Then run support-coverage metrics for the draft:

```bash
cd /Users/travcole/projects/osint-research/web
npm run report:support-coverage:changed -- --base-ref HEAD~1 --head-ref HEAD
```

Review:
- supported sentence %
- unsupported sentence count
- orphan citations
- source fanout

---

## Phase 4: Revise

Read the verification report and apply fixes.

### 4.1. Apply BLOCKING fixes
- Wrong citations, unsourced claims, regulatory errors
- These are non-negotiable

### 4.2. Evaluate SHOULD FIX items
- Epistemic issues, temporal accuracy, style problems
- Apply unless there's a deliberate reason not to

### 4.3. Consider SUGGESTIONS
- Source diversity improvements, model callouts, visualization opportunities
- Apply if they improve the article without disrupting its architecture

### 4.4. Backlinks pass
- Link named persons/entities to their dossier pages: `[Person Name](/dossiers/person-slug)`
- Cross-reference other articles where relevant
- Link external registry entries

### 4.5. Diff-aware claims check
- For any text added or changed during revision, verify claims against cite/soften/delete test
- Don't introduce new unsourced assertions while fixing old ones

### 4.6. Final build and report

```bash
cd /Users/travcole/projects/osint-research/web && npx astro build 2>&1 | tail -5
```

Output to the user:
```
## Article Complete: [TITLE]

- **Words**: X,XXX
- **Evidence citations**: XX total (XX EFTA, XX SEC, XX 990, ...)
- **Source types cited**: X
- **Findings used**: XX of YY cluster findings
- **Research agents**: 3 (corpus, financial, legal)
- **Verification**: [X blocking / Y should-fix / Z suggestions]
- **Status**: reviewed
- **Path**: content/articles/<cluster-id>.mdx

### Structural Notes
- [What finding drove the lead]
- [Core thesis]
- [Key structural choices]
- [What evidence would make it stronger]

### Remaining Items
- [Any unresolved verification items]
- [Any inferences flagged for human review]
```

---

## Cluster Reference

Load available clusters dynamically:

```bash
uv run python pipeline/story_clustering.py --list
```

This returns all active story clusters with their IDs, titles, key angles, and readiness metrics. Use the output rather than a hardcoded table, as clusters evolve with the investigation.

## Readiness Criteria

Checked in Phase 3 (`/review-article`):

1. Every corpus claim has an evidence citation
2. Every contextual claim is cited, softened, or flagged
3. No `[NEEDS SOURCE]` flags remain
4. Mechanism explained (reader with no prior knowledge could follow the money)
5. Tone is dry and understated
6. Epistemic signposting distinguishes observation/inference/speculation
7. Confidence framing paragraph before first major evidentiary section
8. "What We Don't Know" section is honest about gaps
9. Word count 3,000-8,000
10. Structure driven by evidence, not template
11. Analytical models referenced where evidence warrants
12. No Evidence Index or Editor's Note in article
13. No colon crutch, "This is..." transitions, or stacked declaratives
14. Visualizations present where genuinely helpful
15. Relationship/role claims temporally accurate

## Context Management

- Read cluster JSON selectively — don't dump 400 findings into context
- Group findings by type; read evidence-rich ones first
- Parallel research tracks write to `$WORKDIR/report-*.md` — read reports first
- Keep article under 8,000 words — split into two if longer
- Use `--output` on search commands whenever supported
