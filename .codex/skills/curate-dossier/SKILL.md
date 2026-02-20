---
name: curate-dossier
description: Generate narrative wiki-style dossier curation with sectioned prose and contextual visualizations
---

# /curate-dossier

Generate encyclopedic wiki-style narrative for dossier entries. Produces a `lead` (standalone summary) and data-driven `sections` (topical prose with embedded visualizations).

## Arguments

- Required: target name (e.g., `/curate-dossier "Leon Black"`)
- Optional `--batch N`: curate N dossiers with the most findings that lack narratives
- Optional `--refresh`: regenerate narratives even if they already exist
- Optional `--dry-run`: show section suggestions without generating
- No arguments: list dossiers that need curation

## Session Isolation

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
```

## Process

### 1. Run Automated Pipeline

```bash
uv run python pipeline/curate_dossier.py --target "TARGET_NAME"
```

This populates `key_finding_ids`, `key_identifiers`, `section_suggestions`, and `viz_data`.

### 2. Load Data

Read the dossier JSON:
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
uv run python tools/findings_tracker.py search --target "TARGET_NAME" --output $WORKDIR/findings.json
uv run python tools/lead_tracker.py search --query "TARGET_NAME" --output $WORKDIR/leads.json
```

### 4. Generate Narrative

Write these fields into the dossier JSON's `curation` object:

#### `lead` (HTML, 2-3 paragraphs)

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

#### `system_role` (plain text, 1-2 sentences)

What this entity reveals about how the network operates. The "lens onto the machine" principle.

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

2. **Sections are topical, not categorical** — "Key Relationships" not "Relationship Findings." "Financial Architecture" not "Financial Findings." The section title should describe what the reader will learn, not what database type the data came from.

3. **Content is prose, not lists** — weave findings into narrative paragraphs. Don't list findings as bullet points. A reader should be able to read the section as a coherent essay.

4. **Link to other dossiers** — when naming people or entities that have their own dossiers, use `<a href="/dossiers/SLUG">Name</a>`. This is what makes it a wiki — you navigate by following links.

5. **Use citation tokens for all evidence** — citations render as linked footnotes. Use the citation format below.

6. **`viz` field** — set to `"ego_network"`, `"timeline"`, or `null`. The page embeds the visualization after the section prose. Only set viz on the section where it contextually supports understanding. The `section_suggestions` already recommend which sections get which viz.

7. **Adapt to the subject type:**
   - **People**: relationships, financial activity, corporate roles, legal proceedings
   - **Entities** (corporations, foundations, trusts): purpose/function, key officers, financial flows, regulatory history
   - **Events**: participants, sequence, consequences
   - The automated suggestions handle this — they only suggest sections when data exists

8. **Don't repeat the lead** — sections go deeper on specific topics. The lead is the summary; sections are the detail.

#### `open_questions` (array of strings)

3-5 specific, actionable investigative questions. Based on evidence gaps, not speculation.

#### `applicable_models` (array of strings)

Check `content/models/` for which analytical models apply. Use model IDs.

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

If you run this from shell, avoid `uv run python -c "..."` for large HTML strings. Dollar amounts like `$250,000` will be shell-expanded and corrupted.

### 7. Quality Checks

Before writing:
- [ ] Lead is standalone — makes sense without reading sections
- [ ] Every section has prose paragraphs, not bullet lists
- [ ] People/entities mentioned link to their dossiers where they exist (`<a href="/dossiers/SLUG">Name</a>`)
- [ ] **Every factual claim has an inline citation** — `[EFTAxxxxxx]`, `[Finding #N]`, etc.
- [ ] No confidence inflation — inferences not stated as confirmed facts
- [ ] Sections match what the data supports — don't force sections with thin evidence
- [ ] Viz assignments are contextual — ego_network with relationships, timeline with chronological content
- [ ] Tone is encyclopedic reference throughout — not narrative journalism, not data dump

## Batch Mode

When `--batch N`:
1. Read `content/dossiers/_index.json`
2. Sort by total_findings descending
3. Filter to those without `curation.lead`
4. Process top N

## Output

Updates dossier JSON in place. Prints summary of sections generated.
