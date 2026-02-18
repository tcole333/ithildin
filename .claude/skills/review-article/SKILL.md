---
name: review-article
description: Fact-check and edit articles and dossiers before publishing
user_invocable: true
---

# /review-article

Review, fact-check, and prepare articles and dossiers for publication. Acts as an editor verifying every claim against investigation.db evidence, surfacing backlink candidates, and checking for unsourced assertions.

## Arguments

- Required: path or cluster ID (e.g., `/review-article apollo-money-pipeline` or `/review-article site/content/articles/apollo-money-pipeline.mdx`)
- Optional `--dossier <slug>`: review a dossier instead of an article
- Optional `--backlinks-only`: just surface backlink candidates without full review
- No arguments: list articles/dossiers available for review

## Process

### 1. Load the Content

For articles:
```bash
# Read the article
Read: site/content/articles/<cluster-id>.mdx
```

For dossiers:
```bash
# Read the dossier JSON
Read: site/content/dossiers/<slug>.json
```

### 1.5. Evidence Integrity Check

Before fact-checking, run the evidence audit to catch systemic issues:

```bash
uv run python scripts/evidence_audit.py report
```

Flag in the review output if:
- >10% of findings referenced by the article have missing `source_quote`
- Any `direct_quote`/`confirmed` finding cited in the article has a cross-check mismatch
- Any EFTA ID cited in the article appears in an unresolved duplicate cluster

These are not blocking for review (unlike write-article), but should be prominently flagged:
```
### Evidence Integrity Issues
- WARNING: N findings cited in article lack source_quote
- WARNING: EFTA02454291 cited for "8865 claim" but cross-check shows quote is from EFTA02452433
- WARNING: Findings #529, #541, #632 are unresolved duplicates citing same EFTA
```

### 2. Fact-Check: Verify Every Claim

For each factual assertion in the article/dossier:

#### 2a. Dollar Amounts
Every financial figure must trace to a source:
```bash
uv run python tools/findings_tracker.py search "$40M" --output /tmp/review-amounts.json
uv run python tools/parse_ds10_financials.py query --entity "Southern Trust" --output /tmp/review-ds10.json
```
- Check: Does the amount match the source exactly?
- Check: Is the date correct?
- Check: Are the parties named correctly?

#### 2b. EFTA References
Every `[EFTA...]` citation must exist and support the claim:
```bash
uv run python tools/query_doj.py efta EFTA02576529 --text --output /tmp/review-efta.json
```
- Check: Does the document actually say what the article claims?
- Check: Is the quote accurate (for direct_quote claims)?
- Check: Is the inference reasonable (for inference claims)?

#### 2c. Named Persons and Entities
Every person/entity mentioned must have investigation.db support:
```bash
uv run python tools/findings_tracker.py search "<PERSON>" --output /tmp/review-person.json
```
- Check: Do we have findings for this person?
- Check: Is their described role accurate?
- Check: Are connections between persons supported by evidence?

#### 2d. Dates and Timeline
Every date must be verifiable:
- Cross-reference against finding `date_of_event` fields
- Check for anachronisms (did the entity exist on that date?)
- Verify sequence (A happened before B)

#### 2e. Claim Types
Verify the article correctly labels:
- **Facts**: directly supported by primary evidence
- **Inferences**: the article says "suggests" or "appears to" (not stated as fact)
- **Context**: background knowledge (regulatory frameworks, industry norms)

#### 2f. Statutes, Rules, and Regulatory Citations (CRITICAL — high hallucination risk)

**This is the highest-risk category for factual error.** LLMs frequently hallucinate CFR section numbers, statute citations, regulatory thresholds, and legal frameworks. Every legal/regulatory claim in the article MUST be verified via web search against authoritative sources (irs.gov, ecfr.gov, law.cornell.edu, fincen.gov, congress.gov, justia.com).

For each regulatory claim, verify:

1. **CFR/USC citations**: Search for the exact section number. Common errors:
   - Wrong part number (e.g., 31 CFR 1020.230 vs correct 31 CFR 1010.230)
   - Outdated section numbers (regulations get renumbered)
   - Correct statute but wrong subsection
   ```bash
   # Use WebSearch to verify each citation
   WebSearch: "31 CFR 1010.230" beneficial ownership
   WebSearch: "Title 9 Chapter 25" Virgin Islands Code banking
   ```

2. **Dollar thresholds**: SAR amounts, CTR thresholds, reporting minimums
   - BSA SAR threshold: $5,000 (verify against FinCEN guidance)
   - CTR threshold: $10,000 (verify — Congress has proposed changes)
   - Beneficial ownership: 25% equity threshold (verify current CDD Rule)

3. **IRS rates and forms**:
   - Section 7520 rate: verify it's the correct rate for the described purpose
   - Applicable Federal Rate (AFR): verify the specific rate matches the month/year claimed (use PBGC historical tables at pbgc.gov/employers-practitioners/interest-rates/historical-applicable-mid-term)
   - Form numbers (709, 1041, 990, etc.): verify each form is used for the described purpose
   - EIN formats and attribution: verify the EIN belongs to the correct entity

4. **State/territory law**:
   - USVI Code sections: verify against justia.com/codes/virgin-islands/
   - State corporate law claims: verify formation requirements, annual report obligations
   - Trust law claims: verify self-settled spendthrift trust availability by jurisdiction

5. **Regulatory frameworks described in prose**:
   - Even hedged claims ("requires banks to...," "the framework provides...") must be accurate
   - Verify that described regulatory mechanisms actually work the way the article says
   - Check that regulatory bodies named actually have the described jurisdiction

**For EVERY statutory/regulatory citation found in the article, record the verification result:**
```
[LINE X] "31 CFR 1010.230" — VERIFIED via ecfr.gov (beneficial ownership requirements)
[LINE Y] "Section 7520 rate" — VERIFIED via IRS (GRAT hurdle rate)
[LINE Z] "SAR threshold of $5,000" — VERIFIED via FinCEN guidance
[LINE W] "Title 9, Chapter 25" — VERIFIED via Justia (USVI International Banking Center Regulatory Act)
```

**If ANY citation cannot be verified or appears incorrect, flag it immediately with [WRONG CITE] and provide the correct citation.**

### 3. Surface Backlink Candidates

This is a critical step for making the site navigable. Scan the content and identify:

#### 3a. Person/Entity → Dossier Links
For every person or entity name mentioned in the article:
```bash
# Check if they have a dossier
ls site/content/dossiers/ | grep -i "<slugified-name>"
```
If a dossier exists, the name should be hyperlinked: `[Leon Black](/dossiers/leon-black)`

#### 3b. Article → Article Cross-References
Check if the article references topics covered by other articles:
```bash
# Read clusters.json for all cluster topics
Read: site/content/clusters.json
```
If an article mentions "Deutsche Bank transactions" and there's a `deutsche-bank-plumbing` article, suggest a cross-link.

#### 3c. Evidence → Source Links
For EFTA references, generate links to the DOJ document viewer (if available) or note the reference for the evidence index.

#### 3d. Entity → External Registry Links
For corporate entities, check if we have registry data:
```bash
uv run python tools/query_registry.py search "<ENTITY>" --output /tmp/review-registry.json
```
If found, suggest linking to the registry page or noting the filing number.

#### 3e. Dossier → Article Links
When reviewing a dossier, check which articles reference this target:
```bash
# Search article content for the target name
Grep: pattern="<TARGET_NAME>" path="site/content/articles/"
```
Add to the dossier's `related_articles` field.

### 4. Generate Backlinks Report

Output a structured list of all backlink candidates:

```markdown
### Backlink Candidates

#### Dossier Links (insert into article text)
| Text in Article | Link Target | Confidence |
|-----------------|-------------|------------|
| "Leon Black" | /dossiers/leon-black | high |
| "Southern Trust Company" | /dossiers/southern-trust-company | high |
| "Brad Karp" | /dossiers/brad-karp | medium (dossier sparse) |

#### Cross-Article Links
| Reference | Target Article | Suggested Anchor Text |
|-----------|---------------|----------------------|
| "Deutsche Bank processed 579 transactions" | /articles/deutsche-bank-plumbing | "Deutsche Bank's compliance theater" |
| "USVI trust structure" | /articles/usvi-operations | "the USVI trust industry" |

#### External References
| Entity | Registry | Filing Number |
|--------|----------|---------------|
| Southern Trust Company | USVI | ... |
| Maple Inc USVI | USVI | ... |
```

### 5. Check for Unsourced Assertions

Flag any statement that:
- States a fact without an EFTA reference or finding ID
- Makes a causal claim without evidence ("because", "this caused", "as a result of")
- Names a specific person in a negative context without supporting evidence
- Uses media-sourced claims without primary source verification

For each flag:
```
[LINE X] "Black paid Epstein $40M" — NEEDS: EFTA reference for this specific amount
[LINE Y] "This suggests criminal intent" — TONE: too strong for inference claim
[LINE Z] "According to the New York Times" — VERIFY: do we have the primary source?
```

### 5a. Contextual Claims Verification (CRITICAL — high hallucination risk for added context)

Articles contain two types of claims: **corpus claims** (from EFTA documents, cited inline) and **contextual claims** (added by the writer from general knowledge). Contextual claims are the highest-risk category because they bypass the EFTA verification pipeline.

**Identify every contextual claim in the article** — any factual assertion NOT attributed to an EFTA document or finding. Common categories:

1. **Dollar amounts not from primary sources**: sovereign wealth fund AUM, corporate revenue, deal sizes, penalty amounts
2. **Biographical claims about public figures**: job titles, career timelines, when someone was hired/fired
3. **Superlatives and status claims**: "largest," "most influential," "first," "youngest"
4. **Temporal status claims**: "at the time the most..." — verify the claim holds for the specific date
5. **Regulatory/legal framework descriptions**: how FARA works, SAR thresholds, corporate law requirements
6. **Institutional descriptions**: what an organization does, how large it is, who it reports to

**For each contextual claim, the reviewer must choose one of three outcomes:**
- **CITE**: verify via web search and add a source (even parenthetically). Use authoritative sources: government sites (.gov), regulatory bodies, court filings, SEC filings.
- **SOFTEN**: downgrade the precision to match what can be verified. "$800 billion" → "hundreds of billions"; "the most influential" → "among the most influential"; "the largest" → "one of the largest"
- **DELETE**: if the claim adds color but not substance and can't be verified, remove it.

```
[LINE X] "$800 billion AUM" — SOFTEN: use "hundreds of billions" (exact figure varies by year and source)
[LINE Y] "most influential strategist outside government" — DELETE: unverifiable superlative
[LINE Z] "$150 million NYDFS penalty" — CITE: verified via NYDFS consent order July 2020
[LINE W] "FARA was enacted in 1938" — CITE: verified via DOJ FARA FAQ page
```

### 5aa. Claims Skeleton (Pre-Review Verification)

Before evaluating prose quality, generate a **claims skeleton** — a stripped-down list of every factual claim in the article with its evidence. This separates the argument from the writing, making logical gaps and unsupported claims visible.

Format:
```
CLAIM: [factual assertion as stated in article]
SOURCE: [EFTA ID / web source / "contextual - unverified"]
TYPE: [corpus / contextual / inference]
STATUS: [verified / needs-softening / needs-source / unsupported]
```

If the claims skeleton doesn't hold up — if the argument has logical gaps, unsupported leaps, or claims that only work because the prose is compelling — the pretty version needs revision regardless of how well it reads.

The skeleton also serves as a **diff-aware provenance check**: after any editing pass, generate a new skeleton from the edited text and compare it to the pre-edit version. Any new claims that appeared during editing (not present in the original EFTA-sourced draft) must pass the cite/soften/delete test before publication.

### 5b. Model Cross-Reference Check

Verify that articles reference applicable analytical models where evidence warrants:

```bash
# Run model detector on article text
uv run python tools/model_detector.py detect --text "<first 2000 chars of article body>"
```

For each detected model (medium/high confidence):
- Check if the article already references it via callout block or `/models/` link
- If not, flag as a suggestion: `[MODEL] Consider referencing {model title} — {reason}`
- Check that existing model callouts have supporting evidence cited

Available models: manufactured-dependency, bridge-tax, private-order, narrative-shield, jurisdictional-arbitrage, parallel-financial-system, enabler-gradient, complexity-as-credential.

### 5c. Narrative Quality Evaluation

Beyond mechanical fact-checking, evaluate whether the article actually WORKS as a piece of explanatory writing. See `research/craft-principles.md` for the full principles.

#### Structure Assessment
- [ ] Does the opening hook genuinely surprise? (Not just "Epstein was bad" — something counterintuitive about the system)
- [ ] Is there a clear dual-spine? (What's the holding spine — timeline, person, transaction chain? What's the depth spine — system explanation, regulatory framework?)
- [ ] Does structure follow from evidence, or was a template imposed? (Every article's structure should be different because every evidence base is different)
- [ ] Could you summarize the structural argument in one sentence?

#### Mechanism Clarity
- [ ] Does the article explain HOW the system works, not just WHAT happened?
- [ ] Is the evolutionary explanation present? (Not just "here are shell companies" but "here's why USVI trust law exists and what makes it attractive for this purpose")
- [ ] Uses Three-Part Architecture: conceptual frame + specific evidence + analysis connecting them?
- [ ] Would a reader with no prior knowledge be able to follow the money?

#### Progressive Revelation
- [ ] Is information sequenced so each fact recontextualizes what came before?
- [ ] Are there "oh" moments created by sequencing, not by telling the reader to be surprised?
- [ ] Does the counterfactual ("what should have happened") appear throughout, not just in one bolted-on section?

#### Evidence Integration
- [ ] Are documents narrated as plot points (paraphrase context, then quote the devastating line)?
- [ ] Is the evidence budget applied? (Not all 200+ findings dumped — the best 30-50 selected for structural fit)
- [ ] Are missing documents noted as evidence? (What SARs should exist but don't? What emails disappear from the timeline?)

#### Character Management
- [ ] Are principals (3-5) clearly identified and consistently present throughout?
- [ ] Are supporting characters (8-12 max) introduced with role context, not overwhelming?
- [ ] Is everyone else referenced by role rather than fully characterized?

#### Perspective
- [ ] Does the article put the reader INSIDE the system (compliance desk, shell company registrar, trust administrator)?
- [ ] Is the "why it works this way" explained, not just the "how"?
- [ ] Are stakes established BEFORE the mechanism is explained?

### 5d. Skeptic Pass (Adversarial Review)

Review the article specifically for claims that look factual but are actually interpretive. The goal is to catch "interpretations dressed as facts" — the category most likely to survive normal fact-checking because they feel true.

Check for:
- **Interpretations presented as facts**: absence of hedging language + presence of causal verbs ("caused," "proves," "reveals," "demonstrates"). These verbs should be reserved for claims directly supported by documents.
- **Scope creep**: extending claims beyond the temporal or geographic boundaries of evidence. If the emails cover 2016-2019, don't generalize about "a decades-long pattern."
- **Implied intent**: ascribing motive without documentary evidence. "Epstein positioned himself as..." implies strategic intent. "The correspondence shows Epstein feeding intelligence to..." describes observable behavior.
- **Dramatic escalation**: claims that build to a climax not supported by the evidence gradient. If the evidence shows routine correspondence, don't narrate it as an escalating intelligence operation.
- **Status inflation**: describing someone's role or influence in terms that serve the narrative rather than accuracy. Check every description of a person's status against the specific date in the article.

For each finding:
```
[LINE X] "positioned himself as an intelligence asset" — SKEPTIC: implies strategic intent; change to "the correspondence shows him feeding intelligence to"
[LINE Y] "the most influential strategist" — SKEPTIC: status inflation; verify for specific date or downgrade
[LINE Z] "the kind of intelligence that hedge funds pay millions for" — SKEPTIC: inflates value of a public press release
```

### 5e. Epistemic Consistency Check

Verify the article uses consistent epistemic signposting:
- **Observation language** ("In the email chain…", "The CC line shows…") for direct document evidence
- **Inference language** ("The correspondence suggests…", "The simplest explanation is…") for conclusions drawn from evidence
- **Speculation language** ("One possible explanation is…", "We cannot determine from this corpus…") for hypotheses

Flag any paragraph that:
- Uses observation language for an inference (inflating confidence)
- Uses speculation language for something directly documented (deflating confidence)
- Contains an interpretive claim with no epistemic signpost at all
- Uses "reveals" or "demonstrates" for an inference rather than a documented fact

Also verify the article includes a **confidence framing paragraph** before the first major evidentiary section.

### 5f. Temporal Accuracy Check

Verify that all relationship claims, role descriptions, and institutional affiliations are accurately time-bounded. This is a high-risk category — articles covering decade-spanning networks can easily treat past relationships as current or flatten relationship evolution.

**For each named person, check:**
- [ ] Is their described role accurate for the date in the article? (e.g., "White House Counsel" only during their actual tenure)
- [ ] If multiple roles are mentioned, are the time boundaries clear? ("then-White House Counsel, now general counsel of Goldman Sachs")
- [ ] Are status descriptors date-appropriate? (Don't call someone "chairman" after they've stepped down)

**For each institution/entity, check:**
- [ ] Is the entity described as it existed at the time? (Not retroactively applying later developments)
- [ ] Are dissolved entities flagged as dissolved? (Corporate registrations expire; trusts terminate)
- [ ] Are banking/professional relationships bounded? ("served as Epstein's bank from 2013 to 2019" not "Epstein's bank")

**For relationship arcs, check:**
- [ ] Does the article distinguish phases? (Early social contact vs. later operational use)
- [ ] Is post-arrest knowledge separated from pre-arrest narrative? (The article shouldn't read as if everyone knew in 2016 what became public in 2019)
- [ ] Are "at the time" qualifiers present where needed?

**For legal outcomes, check:**
- [ ] Indictments, guilty pleas, acquittals, and pardons all have correct dates
- [ ] Pending vs. resolved matters are accurately distinguished
- [ ] "Convicted" is not used for someone who was acquitted or whose case is pending

Flag temporal errors as:
```
[LINE X] "Ruemmler, White House Counsel" — TEMPORAL: she left that role in 2014; this event is 2018. Use "former White House Counsel"
[LINE Y] "Barrack, chairman of Colony Capital" — TEMPORAL: verify he still held this title in 2021 when indicted
[LINE Z] "Deutsche Bank, Epstein's bank" — TEMPORAL: relationship ended Dec 2018; frame as past tense after that date
```

### 5g. Visualization Assessment

Evaluate whether the article would benefit from interactive visualizations, and check any existing ones.

**Check existing visualizations:**
- [ ] Does each `data-viz` marker have a valid `data-src` pointing to an existing JSON file?
- [ ] Does the data match the article's claims? (Dates, names, amounts should be consistent)
- [ ] Is the visualization placed at a natural point in the article where the reader needs orientation?
- [ ] Does surrounding prose provide enough context that the article works without JS?

**Identify visualization opportunities:**
- [ ] Does the article have 10+ dated events across 3+ actors? → Suggest TimelineChart
- [ ] Does it describe financial flows with specific amounts between parties? → Suggest TransactionTable or SankeyDiagram
- [ ] Does it introduce a complex network of relationships? → Suggest EgoNetwork
- [ ] Does it describe corporate structures or ownership chains? → Suggest CorporateStructure

**Flag opportunities:**
```
[SECTION "The Three Tiers"] — VIZ: TimelineChart would help readers track 30+ events across 7 actors
[SECTION "The Mechanism"] — VIZ: SankeyDiagram for money flows; data available in DS10 records
[NO VIZ NEEDED] — Article has simple linear structure; prose handles it well
```

Available components: TimelineChart, TransactionTable, EgoNetwork, SankeyDiagram, CorporateStructure.
Data format specs in `site/web/src/components/*.tsx`.

### 6. Style Review

Check the article against the patio11 style guide:
- [ ] Opens with a hook (surprising/counterintuitive fact)
- [ ] Explains mechanisms, not just events
- [ ] Uses exact figures (not "millions" or "many")
- [ ] Tone is dry and understated (no "shocking", "explosive", "bombshell")
- [ ] Cites evidence inline
- [ ] Has "What We Don't Know" section
- [ ] Long-form (3,000-8,000 words)
- [ ] No editorializing or moral judgments (let facts speak)
- [ ] Applicable analytical models referenced via callout blocks
- [ ] No chronological-only structure when thematic would be clearer
- [ ] No exhibit-list evidence dumps — everything narrated into the story
- [ ] Calibrated precision (exact figures when known, honest ranges when uncertain)
- [ ] Infrastructure revealed, not just described (the waterfall, the cascade, the gap)
- [ ] Relationship and role claims are temporally accurate (time-bounded to when they were true)
- [ ] Visualizations present where they help and absent where they'd be decorative

#### AI Tell Detection
- [ ] No colon crutch: `[Statement]: [Explanation]` pattern used sparingly, not as default exposition structure
- [ ] No "This is..." / "This reveals..." / "What X reveals is..." transitions — integrate conclusions into descriptions
- [ ] No stacked declaratives: three or more consecutive short S-V-O sentences
- [ ] No repetitive subject starts: same subject beginning three consecutive sentences
- [ ] No hand-holding: don't explain why evidence matters after presenting it — let the reader do the math
- [ ] Syntactic variance: subordinating conjunctions, participial phrases, and varied sentence lengths present throughout
- [ ] Confidence framing paragraph present before first major evidentiary section

### 7. Apply Fixes

If the user approves, apply the backlinks and fixes directly:

For MDX articles:
```
Edit: site/content/articles/<cluster-id>.mdx
- Replace plain names with dossier links
- Add cross-article references
- Fix any factual errors found
- Add [NEEDS SOURCE] flags for unsourced claims
- Update frontmatter status from "draft" to "reviewed"
```

For dossier JSONs — update the `related_articles` field:
```python
uv run python -c "
import json
from pathlib import Path
p = Path('site/content/dossiers/<slug>.json')
data = json.loads(p.read_text())
data['related_articles'] = ['apollo-money-pipeline', 'deutsche-bank-plumbing']
p.write_text(json.dumps(data, indent=2, default=str))
"
```

### 8. Report

```markdown
## Review: [TITLE]

### Fact-Check Results
- **Claims verified**: XX/YY
- **Unsourced assertions**: X (flagged with [NEEDS SOURCE])
- **Incorrect facts**: X (corrected)
- **Inference misclassified as fact**: X (softened)
- **Statute/regulatory citations verified**: X/Y (list any corrections)

### Backlinks Applied
- **Dossier links**: XX inserted
- **Cross-article links**: XX inserted
- **External references**: XX noted

### Style Notes
- [Any style issues found and fixed]

### Remaining Issues
- [Items that need human review]
- [EFTA references that couldn't be verified (document not found)]

### Status: reviewed | needs-revision | approved
```

## Reviewing Dossiers

When reviewing a dossier (`--dossier` flag):

1. **Completeness check**: Does the dossier include all findings for this target?
```bash
uv run python tools/findings_tracker.py search "<TARGET>" --output /tmp/review-dossier-findings.json
```
Compare finding count against dossier JSON.

2. **Connection accuracy**: Are all connections properly attributed?
3. **Timeline integrity**: Are events in chronological order?
4. **Entity roles**: Are corporate positions and dates accurate?
5. **Related articles**: Which published articles reference this target?
6. **Backlinks to other dossiers**: Which connected persons have their own dossier pages?

## Batch Review

To review all articles at once:
```bash
ls site/content/articles/*.mdx
```
For each, run the fact-check and backlinks process. Output a summary table:

```
| Article | Claims | Verified | Flagged | Backlinks | Status |
|---------|--------|----------|---------|-----------|--------|
| apollo-money-pipeline | 47 | 43 | 4 | 28 | reviewed |
| deutsche-bank-plumbing | 38 | 35 | 3 | 22 | needs-revision |
```

## Context Management

- Read articles/dossiers in full (they're small compared to investigation data)
- Use `--output` on all verification searches
- Don't dump full EFTA documents — extract only the relevant quote
- Backlink candidate generation can be done quickly by scanning content + checking dossier index
