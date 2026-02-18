---
name: write-article
description: Generate a patio11-style investigative article from a story cluster
user_invocable: true
---

# /write-article

Generate a deep-dive investigative article in Patrick McKenzie's "Bits about Money" style from a story cluster. Uses Task tool subagents to fill research gaps.

## Arguments

- Required: cluster ID (e.g., `/write-article apollo-money-pipeline`)
- Optional `--dry-run`: show cluster data and proposed outline without generating
- No arguments: list available clusters

## Writing Style

Articles emulate the approach of Patrick McKenzie ("patio11"), Matt Levine, and Byrne Hobart — writers who make complex financial/legal systems legible to intelligent non-specialists. The goal is not to report *what happened* but to teach the reader *how the system works* using a specific case as the vehicle.

### The Core Principle: Teach the System Through the Story

The reader should come away understanding not just "Epstein had shell companies" but "how USVI trust companies work, why that jurisdiction exists, what a Grantor Retained Annuity Trust actually does, and where the regulatory architecture breaks down." The specific facts are the evidence; the system explanation is the article. Aim for 60-70% "how the system works" and 30-40% "what happened in this case."

### The Three-Part Explanation Architecture

Every mechanism explanation in the article must follow this structure:

1. **Conceptual frame** — What is this thing? What problem does it solve? What role does it play?
2. **Specific evidence** — A particular instance from the investigation with exact dates, amounts, parties, and EFTA references.
3. **Analysis connecting them** — Why does this instance illuminate the mechanism? What does it reveal?

A section with (1) without (2) is a Wikipedia article. A section with (2) without (1) is a document dump. Both without (3) is journalism. All three together is explanation.

### Perspective Internalization

Don't describe systems from outside. Put the reader *inside* the system.

Bad: "The Bank Secrecy Act requires banks to file Suspicious Activity Reports."
Good: "You're a compliance officer at Deutsche Bank's Jacksonville branch. A wire transfer for $4.4 million arrives from a client flagged in your system. Your BSA obligations are clear: file an SAR within 30 days. But your relationship manager has already approved the transaction..."

Write from the compliance desk, the trust administrator's office, the shell company registrar's window. The reader should experience the system's pressures, not read about them.

### Infrastructure Reveal / Waterfall

Peel back layers. Show the invisible automatic mechanisms: the compliance cascade (transaction → SAR → FinCEN → FBI → DOJ, with falloff rates at each stage), the liability waterfall (who bears responsibility when a trust company fails CDD?), the regulatory chain (which agency has jurisdiction, and where does it break?). The gap between the top and bottom of the waterfall IS the story.

### Evolutionary Explanation

Don't just say "here's how it works." Explain WHY it works this way:

1. How it works today
2. Why that seems weird or counterintuitive
3. The historical/structural reason it evolved this way
4. What would happen if you tried to change it
5. Now you understand why it persists

### How to Think About Structure

**Structure follows explanatory logic, not chronology and not a predetermined template.** Don't start at the beginning. Don't impose a rigid section outline before understanding the evidence. Start wherever the best entry point is — the most counterintuitive fact, the moment where the system becomes visible, the detail that makes a reader stop and think. Work outward from there.

Ask yourself: *What is the one thing in this evidence that would most surprise an intelligent person who works in finance/law/compliance?* Lead with that. Then ask: *What does the reader need to understand before the next surprising thing lands?* That's your structure.

### The Dual-Spine Technique

Every article needs two spines working simultaneously:

- **Holding spine**: What the reader holds onto — a timeline, a person's story, a transaction chain. Provides forward momentum.
- **Depth spine**: What provides understanding — system explanation, regulatory framework analysis. Provides meaning.

Neither alone works. A piece that's all holding spine is a chronology. A piece that's all depth spine is a textbook. The art is in the weaving.

### Progressive Revelation

**Control when the reader learns what.** Build understanding layer by layer so each new fact recontextualizes what came before. The reader should have the "oh" moment because you sequenced the information correctly, not because you told them to be surprised.

Bad: "Shockingly, the compliance committee approved continuing the relationship."
Good: [Spend 400 words explaining what the ARRC is, what triggers a review, what the normal outcome looks like for a high-risk client.] "The ARRC reviewed the relationship in January 2015. They were, per internal minutes, 'comfortable with things continuing.'"

The reader does the math themselves. That's more powerful than any adjective.

### Voice and Register

- **Conversational expertise.** Like a knowledgeable friend explaining something over drinks. Not academic, not breathless journalism. Dry humor earned through specificity.
- **Understated tone.** Let the details do the work. Never use "shocking," "explosive," "bombshell," or "stunning." If the facts aren't striking on their own, you haven't presented them well.
- **Parenthetical asides that show understanding**: "(Deutsche Bank, which at this point had its own $7.2 billion money-laundering settlement to worry about, chose not to worry about this.)" These earn trust with the reader — they show you know more than you're saying.
- **Explain the normal before showing the abnormal.** Before showing how a GRAT was abused, explain what a GRAT is and why it's a legitimate estate planning tool. The contrast does the work.

### The Counterfactual

Every article should have a "what should have happened" thread — not as a separate section bolted on at the end, but woven throughout. When you describe a wire transfer, explain what BSA compliance should have flagged. When you describe an entity formation, explain what CDD should have required. Show the gap between design and reality at each step, not just in a summary.

### Specificity as Evidence of Understanding

- **Exact figures.** "$56,542,688.38" not "over $56 million." The precision proves you've read the source document.
- **Exact dates.** "November 22, 2011" not "late 2011."
- **Form numbers, account numbers, entity IDs.** These are not decoration — they let the reader verify, and they demonstrate primary-source access.
- **Cite evidence inline** using `[EFTA02576529]` or `[DS10]` or `[ACRIS 2008012900966001]`. No naked claims.

### Earning the Length

Every paragraph must either advance the reader's understanding or provide evidence. No filler. No "it is important to note that." No "as previously mentioned." If a paragraph doesn't teach something new, delete it. 3,000-8,000 words — but only if every word earns its place.

### Honesty About Uncertainty

Distinguish clearly between documented fact, reasonable inference, and open question. Treat gaps as interesting rather than embarrassing. "We do not know the balances in the Valartis accounts" is more honest and more interesting than omitting the accounts entirely. The "What We Don't Know" should be one of the most compelling sections.

## Process

### 1. Load Cluster Data

```bash
# List available clusters
uv run python site/pipeline/story_clustering.py --list

# Export single cluster
uv run python site/pipeline/story_clustering.py --cluster <CLUSTER_ID>
```

Then read the cluster JSON:
```
Read: site/content/clusters.json
```

Extract the cluster's findings, connections, evidence, and stats.

### 1.5. Evidence Integrity Pre-Flight

**CRITICAL: Run the evidence audit before writing.** This catches misattributions, missing quotes, and duplicate findings before they enter the article.

```bash
uv run python scripts/evidence_audit.py report
```

**Block article writing if ANY of these conditions are true:**
- >10% of cluster findings have missing `source_quote`
- Any `direct_quote`/`confirmed` finding has a cross-check mismatch (quote not found in cited EFTA)
- >5 unresolved duplicate clusters within the article's scope

If blocked, inform the user:
```
ARTICLE BLOCKED: Evidence integrity issues detected.
- [X] missing source_quote on N/M findings (>10% threshold)
- [X] N cross-check mismatches on direct_quote/confirmed findings
- [X] N unresolved duplicate clusters

Run these to fix:
  uv run python scripts/efta_backfill_quotes.py          # Backfill missing quotes
  uv run python tools/finding_dedup.py scan               # Review duplicates
  uv run python scripts/evidence_audit.py cross-check     # Verify quote attributions
```

For targeted checks on specific cluster findings, query the cluster's finding IDs and check their evidence:
```bash
uv run python -c "
import sqlite3, json
db = sqlite3.connect('investigation.db')
db.row_factory = sqlite3.Row
# Get finding IDs for cluster
findings = db.execute('''
    SELECT f.id, f.claim_type, f.confidence,
           COUNT(CASE WHEN fe.source_quote IS NULL OR fe.source_quote = '' THEN 1 END) as missing_quotes,
           COUNT(fe.evidence_ref) as total_evidence
    FROM findings f
    LEFT JOIN finding_evidence fe ON f.id = fe.finding_id
    WHERE f.target_name LIKE '%<TARGET>%'
    GROUP BY f.id
''').fetchall()
missing = sum(1 for f in findings if f['missing_quotes'] > 0)
total = len(findings)
print(f'Missing quotes: {missing}/{total} ({100*missing/total:.0f}%)')
"
```

### 2. Assess Coverage

Before writing, evaluate what you have:
- How many findings? (Need 20+ for a substantive article)
- How many unique targets?
- What date range do the findings cover?
- What types of evidence: direct quotes, financial records, corporate filings, court documents?
- What's the strongest evidence chain?
- **What's missing?** Identify 3-5 gaps that would make the article stronger.

If the cluster has fewer than 10 findings, warn the user and suggest running `/deep-investigate` on key targets first.

### 3. Fill Research Gaps (Parallel Subagents)

For each identified gap, spawn a research subagent. Launch up to 3 in parallel:

```
Task tool (subagent_type: "general-purpose", run_in_background: true)
```

**Research agent prompt template:**
```
You are a research assistant for an investigative article about [CLUSTER TOPIC].

RESEARCH QUESTION: [specific gap to fill]

CONTEXT: [what the article already knows]

Search these sources and report what you find:
1. uv run python tools/query_doj.py search "[QUERY]" --limit 20 --output /tmp/write-research-1.json
2. uv run python tools/duggan_search.py "[QUERY]" --output /tmp/write-research-2.json
3. uv run python tools/query_lmsband.py search "[QUERY]" --limit 15 --output /tmp/write-research-3.json
4. [additional source-specific queries based on the gap type]

For any documents found, read full text: uv run python tools/query_doj.py efta EFTA_ID --text

FINAL STEP: Write your findings to /tmp/write-research-[GAP_NAME].md in this format:
# Research: [QUESTION]
## Found
- [key facts with EFTA references]
## Not Found
- [what you looked for but didn't find]
## Suggested Text
- [1-2 paragraphs the writing agent can incorporate]
```

### 3.5. Wait for Research — Then Synthesize

**CRITICAL: Do NOT begin writing until all research subagents have completed and you have read their reports.**

Writing before research is finished produces articles where the structure is predetermined and evidence is backfilled to fit. The result reads like a Wikipedia article with better citations. The evidence must drive the structure, not the other way around.

After reading all research reports:
1. **Identify the single most surprising or counterintuitive finding.** This is your lead candidate.
2. **Identify the strongest evidence chain.** This is your core section.
3. **Identify what reframes conventional understanding.** This is your thesis.
4. **Map the Eight-Beat Envelope** (Keefe's structural technique):
   - Opening scene (the hook), first transition, first turning point, development body, second turning point, complication (what doesn't fit), climax (moment of maximum clarity), ending. You don't need all eight in every piece, but know where they are before you start writing.
5. **Cast the characters:**
   - **3-5 principals** who appear throughout — the reader knows their names, roles, and motivations
   - **8-12 supporting characters** who appear in specific sections, introduced with role context
   - **Everyone else** referenced but not characterized — "a Deutsche Bank relationship manager," not a fully named and backstoried individual
   - Character ceiling: 7-12 named characters max before readers lose track
6. **Apply the evidence budget:** You have 200+ findings — you cannot use them all. Selection criteria:
   - Does this reveal a *mechanism* (how something works), not just an event?
   - Does it connect to another investigation thread?
   - Does it contradict the public narrative?
   - Is it primary-sourced (EFTA documents, court filings)?
   - Is it specific ($23.5M on March 14, 2014 > "millions over several years")?
   - Target: 30-50 findings cited in a 5,000-word article. You're selecting the best 25%, not summarizing 100%.
7. **Sketch an outline driven by these findings** — not by a template. Every article's structure should be different because every evidence base is different.
8. **Note what's missing.** Gaps are interesting — they become the "What We Don't Know" section.

### 4. Write the Article

**Structure is argument.** The opening evidence determines the entire architecture. Don't start with the template below — start with the finding that would most surprise an intelligent person in finance/law/compliance. Work outward from there.

Key writing principles for this step:
- **Lead with surprise.** The counterintuitive finding is your opening. Not "Epstein was bad" — something structural that makes the reader stop.
- **Weave the counterfactual throughout.** "What should have happened" is not a separate section bolted on at the end — it's a running thread. When you describe a wire transfer, explain what BSA compliance should have flagged. When you describe an entity formation, explain what CDD should have required. Show the gap at each step.
- **Use documents as plot points.** Paraphrase the context, then quote the devastating line. "The ARRC met in January 2015. They had Epstein's full file before them. Their determination: they were 'comfortable with things continuing.' [EFTA02576529]"
- **Note missing documents.** Absence of expected records is itself evidence. What SARs should exist but don't? What emails are missing from the timeline?
- **Establish stakes before mechanism.** Tell the reader what happens when the system fails BEFORE explaining how the system works. This creates urgency through technical exposition.

Generate the article as MDX with YAML frontmatter. The template below is a starting scaffold, not a mandatory outline — every article's structure should be different because every evidence base is different:

```mdx
---
title: "The Apollo Money Pipeline"
subtitle: "How $158M+ flowed from three billionaires to a convicted sex offender"
cluster: apollo-money-pipeline
targets: "Leon Black, Marc Rowan, Joshua Harris, Southern Trust Company"
date: "2026-02-14"
status: draft
word_count: ~5000
---

## Opening Hook
[Most surprising/counterintuitive fact — 1-2 paragraphs]

## Background Context
[What the reader needs to know — 2-3 paragraphs]

## The Mechanism
[Core explainer — how the money/structure/scheme actually worked]
[Use Three-Part Architecture: (1) conceptual frame, (2) specific evidence, (3) analysis]
[This is the longest section — 1000-2000 words]

## The Timeline
[Chronological reconstruction with exact dates and amounts]

## What Should Have Happened
[Regulatory/compliance framework that should have caught this]
[NOTE: This section is the fallback. Ideally the counterfactual is woven throughout.]

## The Wider Pattern
[Connect to systemic issues — trust industry, compliance theater, etc.]
[Use Evolutionary Explanation: why does the system work this way?]

## What We Don't Know
[Honest about gaps — what questions remain unanswered]
[Include missing documents: what records should exist but don't?]

```

**DO NOT include an Evidence Index section.** The `citations.ts` system auto-generates a "Sources" section with numbered footnotes and jmail.world links from the inline `[EFTA...]` citations. A manual evidence index would duplicate this.

**DO NOT include an Editor's Note in the article file.** Instead, after saving the article, output your structural reasoning directly to the user in the report (step 8). This includes: what finding drove the lead, the core thesis, structural choices, and what evidence would make the article stronger. This reasoning is for the user's review, not for publication.

### 5. Evidence Audit

After writing, verify every factual claim:

1. **Every dollar amount** must have an EFTA reference or DS10 transaction ID
2. **Every date** must be sourced
3. **Every quote** must be a direct_quote finding with source_quote
4. **Every named person** must appear in investigation.db findings
5. **Inferences** must be clearly labeled as such ("The timing suggests..." not "This proves...")
6. **No claims without evidence.** If you can't cite it, flag it with `[NEEDS SOURCE]`

### 6. Save the Article

Write the MDX file:
```bash
# Save to content/articles/
```
File path: `site/content/articles/<cluster-id>.mdx`

### 7. Rebuild Site

```bash
cd /Users/travcole/projects/osint-research/site/web && npx astro build 2>&1 | tail -5
```

### 8. Report

Output to the user:
```
## Article Generated: [TITLE]

- **Words**: X,XXX
- **Evidence citations**: XX EFTA references
- **Findings used**: XX of YY cluster findings
- **Research gaps filled**: X subagent queries
- **Status**: draft (run /review-article to fact-check)
- **Path**: site/content/articles/<cluster-id>.mdx

### Flagged Items
- [Any [NEEDS SOURCE] items]
- [Any inferences that need human review]
```

## Cluster Reference

| ID | Title | Findings | Key Angle |
|----|-------|----------|-----------|
| apollo-money-pipeline | The Apollo Money Pipeline | 430 | How do you move $40M to a felon through legitimate banking? |
| wexner-trust-architecture | Wexner Trust Architecture | 220 | A masterclass in using trusts to obscure beneficial ownership |
| deutsche-bank-plumbing | Deutsche Bank Plumbing | 383 | What 579 transactions and $304M tell us about compliance theater |
| gulf-intelligence-web | The Gulf Intelligence Web | 137 | The geopolitics of a financier's Rolodex |
| shadow-lobbying-empire | Shadow Lobbying Empire | 232 | How to lobby Congress without technically lobbying Congress |
| corporate-shell-network | The Corporate Shell Network | 610 | The corporate structure diagram that takes a full wall |
| legal-shield | The Legal Shield | 262 | When your lawyers are also your intelligence service |
| science-tech-interface | Science & Tech Interface | 250 | Philanthropy as a social technology |
| norwegian-connection | The Norwegian Connection | 180 | An ex-diplomat, a defense minister, and a registered sex offender |
| inner-circle-operations | Inner Circle Operations | 473 | The org chart of a criminal enterprise that filed its taxes |
| usvi-operations | USVI Operations | 353 | Why the US Virgin Islands is the Delaware of the Caribbean |
| political-influence-machine | The Political Influence Machine | 292 | Campaign finance as relationship management |

## Context Management

- Read cluster JSON selectively — don't dump 400 findings into context at once
- Group findings by type and read the most evidence-rich ones first
- Research subagents write to `/tmp/write-research-*.md` — read reports, not TaskOutput
- Keep article under 8,000 words — if it's longer, split into two articles
- Use `--output` on all search commands in research subagents

## Analytical Model Callouts

When an article discusses evidence that exemplifies one of the 8 analytical models, insert a **callout block**:

```mdx
> **Manufactured Dependency** — Creating conditions for problems, then selling the solution, compounding leverage silently. [Full analysis →](/models/manufactured-dependency)
>
> Evidence: [EFTA02576529] — Epstein introduced Black to the extortionist years before the "rescue."
```

Use this format when:
- A finding directly illustrates a model mechanism
- The reader would benefit from understanding the broader pattern
- The model provides explanatory context beyond the specific facts

Available models: manufactured-dependency, bridge-tax, private-order, narrative-shield, jurisdictional-arbitrage, parallel-financial-system, enabler-gradient, complexity-as-credential.

Run `uv run python tools/model_detector.py detect --text "[article excerpt]"` to identify applicable models.

## Craft Reference

For the full set of writing, explanation, and narrative principles, see `research/craft-principles.md`. These principles derive from studying McKenzie, Levine, Hobart, McPhee, Keefe, Caro, and others. Key sections:
- **Explanation Architecture** (Three-Part Structure, Perspective Internalization, Infrastructure Reveal, Evolutionary Explanation)
- **Narrative Structure** (Eight-Beat Envelope, Dual-Spine, Character-Web, Evidence Budget, Progressive Revelation)
- **Anti-Patterns** (language, structural, precision, and analytical failure modes to avoid)

## Quality Bar

An article is ready for `/review-article` when:
1. Every factual claim has an evidence citation
2. No `[NEEDS SOURCE]` flags remain
3. The mechanism is explained (a reader with no prior knowledge could follow the money)
4. Tone is dry and understated (no "shocking" or "explosive")
5. The "What We Don't Know" section is honest about gaps
6. Word count is 3,000-8,000
7. The structure was driven by the evidence, not imposed before research completed
8. Applicable analytical models are referenced via callout blocks where evidence warrants
9. No Evidence Index or Editor's Note in the article (citations auto-generate Sources; structural reasoning goes in the user report)
