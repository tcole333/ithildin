---
name: review-article
description: Adversarial verification agent for investigative articles
---

# $review-article

Adversarial verification agent for investigative articles. Produces a structured verification report — the reviewer does NOT edit the article directly. The writer (Phase 4 of `$write-article`) applies fixes.

**For dossiers, use `$review-dossiers` instead.** Articles and dossiers have different editorial standards. Articles are investigative journalism — they can have a thesis, analytical voice, and narrative structure. Dossiers are encyclopedic reference material — neutral, Wikipedia-standard, no editorializing.

## Arguments

- Required: path or cluster ID (e.g., `$review-article golden-dome-black-box` or `$review-article content/articles/golden-dome-black-box.mdx`)
- Optional `--backlinks-only`: just surface backlink candidates without full review
- Optional `--workdir <path>`: write verification report to this directory (for `$write-article` integration)
- No arguments: list articles available for review

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

## Editorial Standards: Articles vs Dossiers

Articles are NOT dossiers. The review must apply the correct standard.

| Dimension | Article Standard | Dossier Standard (use $review-dossiers) |
|-----------|-----------------|----------------------------------------|
| **Voice** | Investigative journalism — analytical, can have thesis | Encyclopedic — neutral, no thesis |
| **Analytical claims** | Can state conclusions: "The system produces X" | Must attribute: "Analysis indicates..." |
| **Evaluative language** | Permitted when earned by evidence: "the most expensive defense program" | Banned: no superlatives, no characterizations |
| **Rhetorical devices** | Permitted: rhetorical questions, progressive revelation, counterintuitive hooks | Not permitted |
| **Banned phrases** | Narrow list (see below) | Broad list enforced by `review_dossier_checks.py` |
| **Analytical lenses** | Woven into prose — the article's job | Referenced in `applicable_models` field only |
| **Inference signposting** | Required for unsupported inferences. NOT required for conclusions that follow from presented evidence. | Required for ALL inferences regardless |

### Article Banned Phrases (narrower than dossier list)

These are banned in articles because they're lazy, not because they're opinionated:

- "raises questions" / "raises concerns" — say what the questions or concerns are
- "it is worth noting" / "it bears mentioning" / "notably" / "importantly" / "significantly" — filler transitions
- "shocking" / "explosive" / "bombshell" — sensationalist

These are **allowed** in articles (banned in dossiers):
- "apparatus" / "machine" — fine if descriptively accurate
- "operative" — depends on context; prefer specific role but not auto-banned
- "most significant" / "most consequential" — fine if supported by evidence
- "unprecedented" — fine if factually true (verify)
- "striking" / "extraordinary" / "remarkable" — fine if the evidence supports the characterization

### The Thesis Test

Articles have a thesis — a structural argument the evidence supports. The reviewer should evaluate whether the thesis is **supported**, not whether it exists. An article that says "the procurement system is designed to make its own accountability impossible" is making an argument. The question is: does the evidence in the article support that argument? Not: should the article avoid making arguments?

---

## Process

### 1. Load the Article

```
Read: content/articles/<cluster-id>.mdx
```

### 2. Evidence Integrity Check

```bash
uv run python scripts/evidence_audit.py report
```

Flag if:
- >10% of findings referenced by the article have missing `source_quote`
- Any `direct_quote`/`confirmed` finding cited in the article has a cross-check mismatch
- Any EFTA ID cited in the article appears in an unresolved duplicate cluster

These are **BLOCKING** when the article is in the `$write-article` pipeline, **SHOULD FIX** for standalone review.

### 3. Claims Skeleton

Generate a stripped-down claims list:

```
CLAIM: [factual assertion as stated in article]
SOURCE: [Finding #N / EFTA ID / web source / "contextual - unverified"]
TYPE: [primary-sourced / contextual / analytical-conclusion]
STATUS: [verified / needs-source / unsupported]
```

The skeleton separates the argument from the writing. If the skeleton has logical gaps or unsupported leaps, the article needs revision.

**Important distinction for articles**: Analytical conclusions that follow from presented evidence are NOT "unsupported." The article's thesis is an analytical conclusion. Flag it as unsupported only if the preceding evidence doesn't actually support it.

Also evaluate sentence-level explicit support:
- Every **factual** sentence (dates, amounts, names, events) must carry explicit inline citation tokens in that same sentence.
- **Analytical** sentences (conclusions, interpretations, system-level observations) do not require citations — they are supported by the evidence already presented. The question is whether the evidence is sufficient, not whether each analytical sentence has its own citation.

### 4. Fact-Check Every Claim

#### 4a. Finding ID Verification (CRITICAL)
Every `[Finding #N]` citation must actually exist and support the claim it's attached to. This is the highest-priority check — hallucinated finding IDs that reference unrelated cases are **BLOCKING**.

```bash
uv run python tools/findings_tracker.py search "<CLAIM_TEXT>" --output $WORKDIR/verify-finding.json
```

Spot-check at least 10 finding citations:
- Does Finding #N exist in the database?
- Does the finding's summary/detail match what the article claims?
- Is the finding about the right person/entity?

Wrong finding IDs → **BLOCKING**.

#### 4b. Dollar Amounts
Every financial figure must trace to a source:
```bash
uv run python tools/findings_tracker.py search "$40M" --output $WORKDIR/verify-amounts.json
```
- Does the amount match the source exactly?
- Is the date correct?
- Are the parties named correctly?

Wrong amounts → **BLOCKING**.

#### 4c. Citation References (EFTA, SEC, etc.)
Every inline citation must exist and support the claim:
- Does the document actually say what the article claims?
- Is the quote accurate (for direct_quote claims)?

Run support coverage metrics:
```bash
cd /Users/travcole/projects/osint-research/web
npm run report:support-coverage:changed -- --base-ref HEAD~1 --head-ref HEAD
```

Capture: supported sentence %, unsupported sentence count, orphan citation keys.

#### 4d. Named Persons and Entities
```bash
uv run python tools/findings_tracker.py search "<PERSON>" --output $WORKDIR/verify-person.json
```
- Is their described role accurate?
- Are connections between persons supported?

#### 4e. Dates and Timeline
- Cross-reference against finding `date_of_event` fields
- Check for anachronisms
- Verify sequence

Temporal errors → **SHOULD FIX**.

#### 4f. Statutes, Rules, and Regulatory Citations

**Highest hallucination risk category.** Every legal/regulatory claim must be verified via WebSearch:

1. **CFR/USC citations**: verify exact section number (watch for recodifications)
2. **Dollar thresholds**: SAR amounts, CTR thresholds, reporting minimums
3. **State/territory law**: USVI Code sections, state corporate law
4. **Regulatory frameworks**: verify mechanisms work as described

Wrong statutory citations → **BLOCKING**.

#### 4g. Contextual Claims

Identify every factual assertion NOT attributed to a finding or document:

For each, choose: **CITE** (verify + add source), **SOFTEN** (downgrade precision), or **DELETE** (remove unverifiable color).

- Unverified contextual claims with specific dollar amounts → **BLOCKING**
- Unverified factual claims → **SHOULD FIX**
- Unverifiable color/context → **SUGGESTIONS**

### 5. Source Diversity Report

```bash
uv run python scripts/source_diversity.py content/articles/<cluster-id>.mdx
```

Report:
- Citation count by source type
- Percentage breakdown
- Flag if >80% from a single source type
- Available but uncited evidence from investigation.db
- Specific suggestions for strengthening with additional source types

Source diversity issues are **SUGGESTIONS** unless the article makes claims that an available source could directly support → then **SHOULD FIX**.

### 6. Narrative Quality Evaluation

#### Structure Assessment
- Does the opening hook genuinely surprise?
- Is there a clear dual-spine (holding + depth)?
- Does structure follow from evidence or was a template imposed?
- Could you summarize the structural argument in one sentence?

#### Mechanism Clarity
- Does the article explain HOW the system works, not just WHAT happened?
- Is the evolutionary explanation present?
- Would a reader with no prior knowledge follow the argument?

#### Progressive Revelation
- Information sequenced so each fact recontextualizes what came before?
- Counterfactual woven throughout ("what should have happened")?

#### Evidence Integration
- Documents narrated as plot points?
- Evidence budget applied (30-50 findings, not 200)?
- Missing documents noted as evidence?

#### Character Management
- 3-5 principals clearly identified?
- Supporting characters not overwhelming?
- Everyone else by role?

Structural problems → **SHOULD FIX**. Minor style issues → **SUGGESTIONS**.

### 7. Skeptic Pass (Adversarial Review)

The skeptic pass checks that the article's argument is honest, not that it avoids having one.

- **Unsupported causal claims**: asserting cause without evidence for the causal link (not just correlation) → **BLOCKING**
- **Scope creep**: extending claims beyond what the presented evidence supports → **BLOCKING**
- **Implied intent without evidence**: "they designed the system to..." when the evidence shows the outcome but not the intent → **SHOULD FIX** (reframe as structural observation: "the system produces..." rather than "they designed the system to...")
- **Dramatic escalation**: narrative arc that amplifies beyond evidence gradient → **SHOULD FIX**
- **Status inflation**: describing influence in terms that serve narrative over accuracy → **SHOULD FIX**

#### Planted-Source / Deception Check

For every claim resting on a single provenance chain or on an opposition-research, PR, or litigation artifact, verify that: (a) the article's language separates document authenticity from content truth; (b) the underlying finding or the article's caveats reflect a MOM/POP/MOSES/EVE pass; and (c) provenance-opaque aggregator material carries no more than `medium` weight. Any mismatch is a **BLOCKING** edit.

**Not a problem in articles:**
- Having a thesis or structural argument — that's the article's job
- Drawing analytical conclusions from presented evidence — that's investigative journalism
- Using evaluative language backed by evidence — "the most expensive defense program" is fine if the evidence supports it
- Deploying analytical lenses — articles should apply frameworks

### 8. Epistemic Consistency Check

Three tiers still apply, but the article standard is different from the dossier standard:

- **Assertion language** for facts AND for analytical conclusions supported by the article's evidence
- **Inference language** for claims that go beyond what the evidence directly shows
- **Speculation language** for hypotheses and open questions

Flag:
- Claims stated as fact that have NO evidentiary support in the article → **BLOCKING**
- Claims stated as fact where the evidence is thin (1 source, indirect) → **SHOULD FIX**
- Missing confidence framing paragraph (brief statement of sources and epistemological stance before first evidentiary section) → **SHOULD FIX**

**Not a problem**: An article that presents evidence and then draws a conclusion using assertion language. "The Golden Dome procurement structure produces a specific set of conditions" is an earned conclusion if the preceding sections document those conditions.

### 9. Temporal Accuracy Check

For each named person:
- Role accurate for the date in the article?
- Time boundaries clear for multiple roles?

For each institution/entity:
- Described as it existed at the time?
- Status descriptors date-appropriate?

Temporal errors → **SHOULD FIX**.

### 10. AI Tell Detection

These are writing quality issues that apply to all content:

- No colon crutch: `[Statement]: [Explanation]`
- No "This is..." / "This reveals..." transitions
- No stacked declaratives (3+ consecutive short S-V-O)
- No repetitive subject starts (same subject 3x)
- No hand-holding (explaining why evidence matters after showing it)
- Syntactic variance present throughout

AI tells → **SHOULD FIX**.

### 11. Visualization Assessment

Check existing visualizations:
- Valid `data-src` pointing to existing JSON?
- Data matches article claims?

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

Check if applicable analytical models (Tier 1) or lenses (Tier 2) are referenced where evidence warrants. Missing model references → **SUGGESTIONS**.

Tier 1 models get callout blocks. Tier 2 lenses get woven into analytical prose. Full lens definitions in `research/craft-research/frameworks/`.

### 13. Surface Backlink Candidates

#### Person/Entity → Dossier Links
```bash
ls content/dossiers/ | grep -i "<name>"
```
Every person/entity with a dossier should be linked on first mention: `[Person Name](/dossiers/person-slug)`

**Also verify that linked dossier files actually exist.** Broken links to nonexistent dossiers → **SHOULD FIX**.

#### Article → Article Cross-References
Check if the article references topics covered by other articles.

### 14. Compile Verification Report

Write `$WORKDIR/verification-report.md`:

```markdown
# Verification Report: [TITLE]

## BLOCKING (must fix before publication)
- [LINE X] Wrong finding citation: Finding #NNNN is about [WRONG TOPIC], not [ARTICLE CLAIM]
- [LINE Y] "31 CFR 1020.230" — WRONG CITE: correct is 31 CFR 1010.230
- [LINE Z] Causal claim without evidence for causation

## SHOULD FIX (significant quality issues)
- [LINE X] Temporal error: Palantir deal was August 2025, not July
- [LINE Y] Missing confidence framing paragraph
- [LINE Z] Implied intent — reframe as structural observation

## SUGGESTIONS (optional improvements)
- [LINE X] Finding #1234 (SEC Form D) could strengthen this section
- [SECTION "The Three Tiers"] TimelineChart would help track 30+ events
- Consider referencing infrastructure-lock-in lens

## SOURCE DIVERSITY
| Source Type | Citations | % |
|-------------|-----------|---|

Available but uncited: [specific findings with non-dominant source types]

## AI TELL SCAN
- [LINE X] Colon crutch
- [LINE Y] Stacked declaratives (lines 45-47)
- Overall syntactic variance: acceptable / needs work

## BACKLINK CANDIDATES
### Dossier Links
| Text | Target | Confidence |
|------|--------|------------|

### Broken Dossier Links (linked but file doesn't exist)
| Text | Target | Status |
|------|--------|--------|

### Cross-Article Links
| Reference | Target Article | Anchor Text |
|-----------|---------------|-------------|

## Summary
- **Finding citations verified**: XX/YY correct
- **Blocking issues**: X
- **Should-fix issues**: X
- **Suggestions**: X
- **Status**: needs-revision | ready-for-publication
```

---

## Context Management

- Read articles in full (small compared to investigation data)
- Use `--output` on all verification searches
- Don't dump full EFTA documents — extract only the relevant quote
- Backlink candidate generation: scan content + check dossier index
- Spot-check at least 10 finding citations against the actual database — this catches the most critical errors
