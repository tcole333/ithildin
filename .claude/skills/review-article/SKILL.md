---
name: review-article
description: Adversarial verification agent for articles and dossiers
user_invocable: true
---

# /review-article

Adversarial verification agent that finds problems in articles and dossiers. Produces a structured verification report — the reviewer does NOT edit the article directly. The writer (Phase 4 of `/write-article`) applies fixes.

## Arguments

- Required: path or cluster ID (e.g., `/review-article apollo-money-pipeline` or `/review-article site/content/articles/apollo-money-pipeline.mdx`)
- Optional `--dossier <slug>`: review a dossier instead of an article
- Optional `--backlinks-only`: just surface backlink candidates without full review
- Optional `--workdir <path>`: write verification report to this directory (for `/write-article` integration)
- No arguments: list articles/dossiers available for review

## Output

The reviewer produces `$WORKDIR/verification-report.md` (or outputs directly if no workdir) with these sections:

```
### BLOCKING (must fix before publication)
### SHOULD FIX (significant quality issues)
### SUGGESTIONS (optional improvements)
### SOURCE DIVERSITY (citation analysis)
### AI TELL SCAN (language pattern detection)
### BACKLINK CANDIDATES
```

---

## Process

### 1. Load the Content

For articles:
```
Read: site/content/articles/<cluster-id>.mdx
```

For dossiers:
```
Read: site/content/dossiers/<slug>.json
```

### 2. Evidence Integrity Check

```bash
uv run python scripts/evidence_audit.py report
```

Flag in the verification report if:
- >10% of findings referenced by the article have missing `source_quote`
- Any `direct_quote`/`confirmed` finding cited in the article has a cross-check mismatch
- Any EFTA ID cited in the article appears in an unresolved duplicate cluster

These are **BLOCKING** for articles in the write-article pipeline, **SHOULD FIX** for standalone review.

### 3. Claims Skeleton

Before evaluating prose quality, generate a stripped-down claims list:

```
CLAIM: [factual assertion as stated in article]
SOURCE: [EFTA ID / web source / "contextual - unverified"]
TYPE: [corpus / contextual / inference]
STATUS: [verified / needs-softening / needs-source / unsupported]
```

The skeleton separates the argument from the writing. If the skeleton has logical gaps or unsupported leaps, the article needs revision regardless of how well it reads.

Also evaluate sentence-level explicit support:
- Evidence mode maps support sentence-by-sentence.
- A factual sentence is unsupported if it lacks explicit inline citation tokens in that same sentence, even if nearby sentences are cited.

### 4. Fact-Check Every Claim

#### 4a. Dollar Amounts
Every financial figure must trace to a source:
```bash
uv run python tools/findings_tracker.py search "$40M" --output $WORKDIR/verify-amounts.json
uv run python tools/parse_ds10_financials.py query --entity "Southern Trust" > $WORKDIR/verify-ds10.txt
```
- Does the amount match the source exactly?
- Is the date correct?
- Are the parties named correctly?

#### 4b. Citation References
Every inline citation must exist and support the claim:
```bash
uv run python tools/query_doj.py efta EFTA02576529 --text --output $WORKDIR/verify-efta.json
```
- Does the document actually say what the article claims?
- Is the quote accurate (for direct_quote claims)?
- Is the inference reasonable (for inference claims)?

Run support coverage metrics and include key outputs in the review:

```bash
cd /Users/travcole/projects/osint-research/site/web
npm run report:support-coverage:changed -- --base-ref HEAD~1 --head-ref HEAD
```

Capture:
- supported sentence %
- unsupported sentence count
- orphan citation keys
- source fanout anomalies (sources with unexpectedly broad dependency)

#### 4c. Named Persons and Entities
```bash
uv run python tools/findings_tracker.py search "<PERSON>" --output $WORKDIR/verify-person.json
```
- Do we have findings for this person?
- Is their described role accurate?
- Are connections between persons supported?

#### 4d. Dates and Timeline
- Cross-reference against finding `date_of_event` fields
- Check for anachronisms
- Verify sequence

#### 4e. Claim Type Accuracy
- **Facts**: directly supported by primary evidence
- **Inferences**: article uses "suggests" / "appears to" (not stated as fact)
- **Context**: background knowledge (regulatory frameworks, industry norms)

#### 4f. Statutes, Rules, and Regulatory Citations

**Highest hallucination risk category.** Every legal/regulatory claim must be verified via WebSearch:

1. **CFR/USC citations**: verify exact section number
2. **Dollar thresholds**: SAR amounts, CTR thresholds, reporting minimums
3. **IRS rates and forms**: Section 7520, AFR, form numbers
4. **State/territory law**: USVI Code sections, state corporate law
5. **Regulatory frameworks**: verify mechanisms work as described

Record every verification:
```
[LINE X] "31 CFR 1010.230" — VERIFIED via ecfr.gov
[LINE Y] "SAR threshold of $5,000" — VERIFIED via FinCEN guidance
[LINE Z] "Title 9, Chapter 25" — WRONG: correct section is [X]
```

Wrong citations are **BLOCKING**.

#### 4g. Contextual Claims

Identify every factual assertion NOT attributed to an EFTA document or finding:

1. Dollar amounts not from primary sources
2. Biographical claims about public figures
3. Superlatives ("largest," "most influential")
4. Regulatory/legal framework descriptions
5. Institutional descriptions

For each, choose: **CITE** (verify + add source), **SOFTEN** (downgrade precision), or **DELETE** (remove unverifiable color).

- Unverified contextual claims with specific dollar amounts → **BLOCKING**
- Unverified superlatives → **SHOULD FIX**
- Unverifiable color → **SUGGESTIONS**

### 5. Source Diversity Report

**NEW** — Analyze what types of evidence the article actually cites vs. what's available.

```bash
uv run python scripts/source_diversity.py site/content/articles/<cluster-id>.mdx
```

Report should include:
- Citation count by source type (EFTA, SEC, 990, ACRIS, CL, FEC, FARA, REG, etc.)
- Percentage breakdown
- Flag if >80% of citations are from a single source type
- Available but uncited evidence from investigation.db (findings for the cluster's targets that use non-EFTA sources)
- Specific suggestions: "Finding #1234 (SEC Form D filing for STC) could strengthen the entity formation section"

Source diversity issues are **SUGGESTIONS** unless the article makes claims that a specific non-EFTA source could directly support — then **SHOULD FIX**.

### 6. Narrative Quality Evaluation

#### Structure Assessment
- Does the opening hook genuinely surprise?
- Is there a clear dual-spine?
- Does structure follow from evidence or was a template imposed?
- Could you summarize the structural argument in one sentence?

#### Mechanism Clarity
- Does the article explain HOW the system works, not just WHAT happened?
- Is the evolutionary explanation present?
- Uses Three-Part Architecture?
- Would a reader with no prior knowledge follow the money?

#### Progressive Revelation
- Information sequenced so each fact recontextualizes what came before?
- "Oh" moments created by sequencing?
- Counterfactual woven throughout?

#### Evidence Integration
- Documents narrated as plot points?
- Evidence budget applied (30-50 findings, not 200)?
- Missing documents noted as evidence?

#### Character Management
- 3-5 principals clearly identified?
- Supporting characters not overwhelming?
- Everyone else by role?

#### Perspective
- Reader placed INSIDE the system?
- "Why it works this way" explained?
- Stakes established before mechanism?

Structural problems are **SHOULD FIX**. Minor style issues are **SUGGESTIONS**.

### 7. Skeptic Pass (Adversarial Review)

Check for claims that look factual but are interpretive:

- **Interpretations presented as facts**: absence of hedging + causal verbs
- **Scope creep**: extending claims beyond evidence boundaries
- **Implied intent**: ascribing motive without documentary evidence
- **Dramatic escalation**: narrative arc not supported by evidence gradient
- **Status inflation**: describing influence in terms that serve narrative over accuracy

Interpretations-as-facts → **BLOCKING**. Status inflation → **SHOULD FIX**.

### 8. Epistemic Consistency Check

- **Observation language** for direct document evidence
- **Inference language** for conclusions drawn from evidence
- **Speculation language** for hypotheses

Flag paragraphs that:
- Use observation language for an inference (inflating confidence) → **BLOCKING**
- Use speculation language for documented facts → **SHOULD FIX**
- Contain interpretive claims with no signpost → **SHOULD FIX**

Verify the article includes a **confidence framing paragraph** before the first evidentiary section. Missing → **SHOULD FIX**.

### 9. Temporal Accuracy Check

For each named person:
- Role accurate for the date in the article?
- Time boundaries clear for multiple roles?
- Status descriptors date-appropriate?

For each institution/entity:
- Described as it existed at the time?
- Dissolved entities flagged?
- Banking/professional relationships bounded?

For relationship arcs:
- Phases distinguished?
- Post-arrest knowledge separated from pre-arrest narrative?

Temporal errors → **SHOULD FIX**.

### 10. AI Tell Detection

- No colon crutch: `[Statement]: [Explanation]`
- No "This is..." / "This reveals..." transitions
- No stacked declaratives (3+ consecutive short S-V-O)
- No repetitive subject starts (same subject 3x)
- No hand-holding (explaining why evidence matters after showing it)
- Syntactic variance present throughout
- Confidence framing paragraph present

AI tells → **SHOULD FIX**.

### 11. Visualization Assessment

Check existing visualizations:
- Valid `data-src` pointing to existing JSON?
- Data matches article claims?
- Placed at natural orientation points?

Identify opportunities:
- 10+ dated events across 3+ actors → suggest TimelineChart
- Financial flows with amounts → suggest SankeyDiagram / TransactionTable
- Complex relationship network → suggest EgoNetwork
- Corporate ownership chains → suggest CorporateStructure

Visualization issues → **SUGGESTIONS**.

### 12. Model Cross-Reference

```bash
uv run python tools/model_detector.py detect --text "<article excerpt>"
```

Check if applicable analytical models are referenced. Missing model references → **SUGGESTIONS**.

### 13. Surface Backlink Candidates

#### Person/Entity → Dossier Links
```bash
ls site/content/dossiers/ | grep -i "<name>"
```
Every person with a dossier should be linked: `[Leon Black](/dossiers/leon-black)`

#### Article → Article Cross-References
Check if the article references topics covered by other articles.

#### Entity → External Registry Links
```bash
uv run python tools/query_registry.py search "<ENTITY>" --output $WORKDIR/verify-registry.json
```

#### Dossier → Article Links (when reviewing dossiers)
```bash
Grep: pattern="<TARGET_NAME>" path="site/content/articles/"
```

### 14. Compile Verification Report

Write `$WORKDIR/verification-report.md`:

```markdown
# Verification Report: [TITLE]

## BLOCKING (must fix before publication)
- [LINE X] "Black paid Epstein $40M" — NEEDS: EFTA reference for specific amount
- [LINE Y] "31 CFR 1020.230" — WRONG CITE: correct is 31 CFR 1010.230
- [LINE Z] "positioned himself as an intelligence asset" — inference presented as fact

## SHOULD FIX (significant quality issues)
- [LINE X] "most influential strategist" — status inflation; verify or downgrade
- [LINE Y] Missing confidence framing paragraph
- [LINE Z] "Ruemmler, White House Counsel" — TEMPORAL: she left role in 2014

## SUGGESTIONS (optional improvements)
- [LINE X] Finding #1234 (SEC Form D) could strengthen entity formation section
- [SECTION "The Three Tiers"] TimelineChart would help track 30+ events
- Consider referencing jurisdictional-arbitrage model

## SOURCE DIVERSITY
| Source Type | Citations | % |
|-------------|-----------|---|
| EFTA        | 28        | 82% |
| SEC         | 2         | 6%  |
| ACRIS       | 1         | 3%  |
| FEC         | 1         | 3%  |
| Contextual  | 2         | 6%  |

Available but uncited: 8 IRS 990 findings, 15 ACRIS records, 6 CourtListener dockets

## AI TELL SCAN
- [LINE X] Colon crutch: "The pitch: Carbyne wanted to..."
- [LINE Y] Stacked declaratives (lines 45-47)
- Overall syntactic variance: acceptable / needs work

## BACKLINK CANDIDATES
### Dossier Links
| Text | Target | Confidence |
|------|--------|------------|
| "Leon Black" | /dossiers/leon-black | high |

### Cross-Article Links
| Reference | Target Article | Anchor Text |
|-----------|---------------|-------------|
| "Deutsche Bank transactions" | /articles/deutsche-bank-plumbing | "Deutsche Bank's compliance theater" |

## Summary
- **Claims verified**: XX/YY
- **Blocking issues**: X
- **Should-fix issues**: X
- **Suggestions**: X
- **Status**: needs-revision | ready-for-publication
```

---

## Reviewing Dossiers

When reviewing a dossier (`--dossier` flag):

1. **Completeness**: Compare finding count against dossier JSON
```bash
uv run python tools/findings_tracker.py search "<TARGET>" --output $WORKDIR/verify-dossier.json
```
2. **Connection accuracy**: Are all connections properly attributed?
3. **Timeline integrity**: Events in chronological order?
4. **Entity roles**: Corporate positions and dates accurate?
5. **Related articles**: Which published articles reference this target?
6. **Backlinks**: Which connected persons have dossier pages?

---

## Context Management

- Read articles/dossiers in full (small compared to investigation data)
- Use `--output` on all verification searches
- Don't dump full EFTA documents — extract only the relevant quote
- Backlink candidate generation: scan content + check dossier index
