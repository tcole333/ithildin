---
name: curate-dossier
description: Generate narrative wiki-style dossier curation with sectioned prose and contextual visualizations
---

# $curate-dossier

Generate encyclopedic wiki-style narrative for dossier entries. Produces a `lead` (standalone summary) and data-driven `sections` (topical prose with embedded visualizations).

## Arguments

- Required: target name (e.g., `$curate-dossier "Person Name"`)
- Optional `--batch N`: curate N dossiers with the most findings that lack narratives
- Optional `--refresh`: regenerate narratives even if they already exist
- Optional `--dry-run`: show section suggestions without generating
- No arguments: list dossiers that need curation

## Context and session isolation

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
```

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the requested profile/database. Work in the current checkout. For batch curation, use chat-native subagents only for disjoint dossier files and inherit the configured model; the parent collects outputs, reviews changes and owns persistence. Keep selected slugs, artifacts, final hashes and remaining work in WORKDIR so the task can resume through compaction.

## Process

### 1. Run Automated Pipeline

```bash
uv run python pipeline/curate_dossier.py --target "TARGET_NAME"
```

This populates `key_finding_ids`, `key_identifiers`, `section_suggestions`, and `viz_data`. For `--dry-run`, copy the selected dossier into `$WORKDIR/dossiers/` first, pass `--dossier-dir "$WORKDIR/dossiers"`, and return those temporary suggestions without editing the source dossier.

### 2. Load Data

Read the current narrative and relevant findings/relationships from the dossier JSON. Expand to full context when needed; unrelated machine metadata need not occupy the review context:
```bash
Read: content/dossiers/<slug>.json
```

Key fields to use:
- `curation.section_suggestions`: what sections the data supports, with finding_ids and guidance per section
- `curation.key_finding_ids`: the most significant findings
- `findings`: full finding data including evidence
- `connections`: relationships with evidence
- `entities`: corporate roles and jurisdictions

### 3. Research Context

```bash
uv run python tools/findings_tracker.py search "TARGET_NAME" --output $WORKDIR/findings.json
uv run python tools/lead_tracker.py search "TARGET_NAME" --output $WORKDIR/leads.json
```

### 4. Generate Narrative

Write these fields into the dossier JSON's `curation` object:

#### `lead` (HTML; usually 2-3 paragraphs, adapted to the subject)

The Wikipedia-style lead section. Must be:
- **Standalone** — a reader who only reads the lead understands the subject
- **Encyclopedic tone** — neutral, authoritative, information-dense
- **Specific** — names, amounts, dates, jurisdictions. Not "a major financial firm" but "Apollo Global Management"
- **Every claim has inline citations** — use citation tokens (see Citation Format below)
- Format as `<p>` tags since rendered via `set:html`

Structure:
1. Who/what this is and why it matters to the investigation
2. The most significant facts (financial, legal, structural)
3. Current status and unresolved questions

The lead should work for people, entities, AND events — adapt the structure to what the subject is.

#### `system_role` (plain text; usually 1-2 sentences)

What this subject reveals about how power, money, or institutions operate. Use neutral, analytical language — no loaded terms ("operative," "dark money," "machine"). Describe the structural role or mechanism, not a judgment.

#### `sections` (array of objects)

Each section has:
```json
{
  "id": "key-relationships",
  "title": "Key Relationships",
  "content": "<p>HTML prose...</p>",
  "viz": "ego_network"
}
```

**Section generation rules:**

1. **Use `section_suggestions` as your starting point** — the automated pipeline analyzed the data and suggested sections with relevant finding_ids and guidance. Follow the suggestions but you can rename titles, merge sections, or skip ones with insufficient data.

2. **Sections are topical, not categorical** — "Key Relationships" not "Relationship Findings." "Financial Architecture" not "Financial Findings." Section titles should be neutral and descriptive (what the reader will learn), not editorial or analytical ("The Integrated Machine," "The Pipeline").

3. **Content is prose, not lists** — weave findings into narrative paragraphs. Don't list findings as bullet points. A reader should be able to read the section as a coherent essay.

4. **Link to other dossiers (MANDATORY)** — when naming people or entities that have their own dossiers, use `<a href="/dossiers/SLUG">Name</a>`. This is what makes it a wiki. To find existing dossier slugs, check `content/dossiers/_index.json`. Every named person or organization that appears in the index MUST be linked on first mention in each section. This is a hard requirement — dossiers without cross-links fail review.

5. **Use citation tokens for all evidence** — citations render as linked footnotes. Use the citation format below.

6. **`viz` field** — set to `"ego_network"`, `"timeline"`, or `null`. The page embeds the visualization after the section prose. Only set viz on the section where it contextually supports understanding. The `section_suggestions` already recommend which sections get which viz.

7. **Adapt to the subject type:**
   - **People**: relationships, financial activity, corporate roles, legal proceedings
   - **Entities** (corporations, foundations, trusts): purpose/function, key officers, financial flows, regulatory history
   - **Events**: participants, sequence, consequences
   - The automated suggestions handle this — they only suggest sections when data exists

8. **Don't repeat the lead** — sections go deeper on specific topics. The lead is the summary; sections are the detail.

9. **Section order and length reflect importance, not evidence volume** — put the most structurally significant section first. A section with 3 high-confidence findings about a key relationship should come before (and may be longer than) a section with 20 findings about routine corporate filings. Ask: "What would a journalist, analyst, or researcher most need to understand about this subject?"

#### `open_questions` (array of strings)

Specific, actionable investigative questions based on evidence gaps, not speculation. Include only questions supported by actual gaps; there is no quota.

#### `applicable_models` (array of strings)

Check `content/models/` for which analytical models apply. Use model IDs.

### Editorial Standards

Dossiers are reference material, not investigative journalism. Apply Wikipedia's core content policies.

#### Importance vs. Evidence Density (CRITICAL)

Finding count does NOT equal importance. The investigation may have deeply researched a minor corporate registration (producing 30 findings) while a structurally significant relationship has only 2 findings. **Do not let research depth distort the narrative.**

- **Weight sections by actual significance, not finding count.** A section about someone's role on a key board may deserve more prominence than a section about a corporate filing we happened to investigate thoroughly.
- **Don't lead with whatever has the most evidence.** Lead with what matters most to understanding this subject's role. A reader should come away understanding why this person/entity matters, not just which aspects we documented most.
- **Don't inflate minor details.** If we have extensive evidence about a routine corporate address change, that doesn't make it a key section. Mention it where relevant and move on.
- **Use domain judgment.** You understand power structures, finance, and institutions. Use that understanding to assess what's genuinely significant — don't defer to the data's shape.

#### Neutral Point of View (CRITICAL)

**Banned phrases** — do NOT use any of the following:
- "raises questions" / "raises concerns"
- "striking" / "extraordinary" / "remarkable" / "unprecedented" (unless quoting a source)
- "most significant" / "most consequential" / "most important"
- "dark money" (unless quoting a specific source that uses the term — attribute it)
- "machine" / "apparatus" / "operative" in section titles or system_role

**Qualification is appropriate when evidence is uncertain.** Do not replace a cautious, supported statement with a stronger assertion merely to avoid a phrase.

**Instead**: State documented facts and let the reader draw conclusions. If a characterization is relevant, attribute it: "Campaign finance watchdogs described the arrangement as 'dark money' [Finding #N]."

**Section titles must be neutral and descriptive**: "Grant Distribution Network" not "The Dark Money Pipeline." "Personnel Transitions" not "The Revolving Door Machine."

#### Claim Type Rules

- `direct_quote` / `confirmed` → state the documented fact with citation; a quote establishes what was said, and allegations retain attribution
- `paraphrase` / `high` confidence → state as fact with citation
- `inference` / `medium` confidence → attribute: "Analysis of [source] indicates..."
- `synthesis` → attribute: "Cross-reference of [N] findings shows..." — NEVER state synthesis as confirmed fact
- Hypotheses → "Hypothesis #N proposes..." (never state as fact)

**Synthesis sections**: If a section primarily synthesizes multiple findings into a structural conclusion, the prose must use attribution language throughout. Not "FAIR functions as a pass-through" but "Grant flow analysis indicates FAIR distributed funds from CPI to state-level organizations [Finding #N][Finding #M]."

#### Evidence Quality

- **Primary records** (government filings, court documents, registries): state what the record establishes; attribute allegations and self-reported claims
- **Moderate** (USASpending, FEC, API data): cite with source: "Federal spending records show..."
- **Weak** (web search, news paraphrases): cite with publication: "According to [outlet]..."

### 5. Citation Format

Dossier content uses the same citation system as articles. Use these inline tokens:

| Token Pattern | Example | Renders As |
|--------------|---------|------------|
| `[EFTAxxxxxx]` | `[EFTA02576529]` | Linked superscript to Jmail viewer |
| `[Finding #N]` | `[Finding #42]` | Linked to finding's evidence sources |
| `[SEC:accession]` | `[SEC:0001193125-15-266790]` | SEC EDGAR filing link |
| `[EDGAR:accession]` | `[EDGAR:0001193125-15-266790]` | SEC EDGAR filing link (alias) |
| `[990:EIN]` | `[990:133095231]` | ProPublica 990 link |
| `[ACRIS:docid]` | `[ACRIS:2008012900966001]` | NYC property record |
| `[CL:docket]` | `[CL:4608967]` | CourtListener docket |
| `[FEC:committee]` | `[FEC:C00431569]` | FEC committee link |
| `[FARA:num]` | `[FARA:6071]` | FARA registration |
| `[REG:XX:id]` | `[REG:FL:P950000272]` | State registry link |

**Citation rules:**
- Place citation immediately after the claim it supports
- Multiple sources: `[EFTA02576529][EFTA02576530]` or `[Finding #6][Finding #7]`
- The page auto-generates a Sources footnote section from all citations
- Finding citations resolve to their evidence sources (e.g., `[Finding #6]` → EFTA links)
- Use bracket tokens only. Do **not** use parenthetical formats like `(Finding #6, EFTA02576529)`.
- Support spans are sentence-level: every factual sentence should include explicit citation tokens in that same sentence.

### 6. Write JSON

Read current dossier, merge narrative fields into `curation`, write back:

```python
import json
from pathlib import Path

path = Path(f"content/dossiers/{slug}.json")
dossier = json.loads(path.read_text())

dossier["curation"]["lead"] = lead_html
dossier["curation"]["system_role"] = system_role
dossier["curation"]["sections"] = sections
dossier["curation"]["open_questions"] = open_questions
dossier["curation"]["applicable_models"] = applicable_models

path.write_text(json.dumps(dossier, indent=2, default=str))
```

If you run this from shell, avoid `python -c "..."` for large HTML strings. Dollar amounts like `$250,000` will be shell-expanded and corrupted.

### 7. Quality Checks

Before writing, verify ALL of the following:

**Cross-linking (HARD REQUIREMENT):**
- [ ] Read `content/dossiers/_index.json` to get the list of existing dossier slugs
- [ ] Every person/entity mentioned in the text that has a dossier slug is linked with `<a href="/dossiers/SLUG">Name</a>` on first mention per section
- [ ] Link relevant existing dossiers; do not add names or links merely to hit a count

**Citations:**
- [ ] Every factual claim has an inline citation in the same sentence
- [ ] Sentence-local support: no factual sentence depends on citations in neighboring sentences
- [ ] No orphan citations (citation tokens that don't correspond to actual findings/sources)

**Tone (HARD REQUIREMENT):**
- [ ] Grep your output for banned phrases: "raises questions," "striking," "extraordinary," "remarkable," "unprecedented," "most significant," "most consequential," "dark money" (unattributed), "machine," "apparatus" (in titles)
- [ ] Synthesis/inference claims are attributed ("Analysis indicates...") not stated as fact
- [ ] Section titles are neutral and descriptive, not editorial
- [ ] `system_role` uses no loaded terms

**Structure:**
- [ ] Lead is standalone — makes sense without reading sections
- [ ] Every section has prose paragraphs, not bullet lists
- [ ] Sections don't repeat the lead
- [ ] Sections match what the data supports — don't force sections with thin evidence
- [ ] Viz assignments are contextual — ego_network with relationships, timeline with chronological content

## Batch Mode

When `--batch N`:
1. Read `content/dossiers/_index.json`
2. Sort by total_findings descending
3. Filter to those without `curation.lead`
4. Process top N

## Output

Updates dossier JSON in place. Prints summary of sections generated.

After writing, run support-coverage metrics:

```bash
npm --silent --prefix web run report:support-coverage -- --file "content/dossiers/<slug>.json" > "$WORKDIR/support-coverage.json"
```

Confirm the result contains the requested file and current content hash. Inspect unsupported sentences, orphan citations, and source fanout; these structural metrics do not establish semantic support. Run the dossier review workflow on final content before claiming publication readiness; preserve exact-content receipts and the shared release gate.
