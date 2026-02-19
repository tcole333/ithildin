# Citation System Architecture

## Overview

The citation system provides consistent footnote-style source linking across articles and dossiers. It converts inline citation tokens into numbered superscript links with a generated Sources section.

Evidence Support Spans (V1) now run on top of that citation layer:
- Sentence-level support mapping from prose to explicit citation links
- Page-local bidirectional highlight mode in the UI
- Coverage metrics report for pre-publish visibility

## How It Works

### 1. Citation Tokens

Writers include citations as inline tokens in content:

| Token Pattern | Example | Resolves To |
|--------------|---------|-------------|
| `[EFTAxxxxxx]` | `[EFTA02576529]` | Jmail viewer for DOJ documents |
| `[Finding #N]` | `[Finding #42]` | Evidence sources for that finding |
| `[SEC:accession]` | `[SEC:0001193125-15-266790]` | SEC EDGAR filing |
| `[EDGAR:accession]` | `[EDGAR:0001193125-15-266790]` | SEC EDGAR filing (alias) |
| `[990:EIN]` | `[990:133095231]` | ProPublica Nonprofit Explorer |
| `[ACRIS:docid]` | `[ACRIS:2008012900966001]` | NYC property record |
| `[CL:docket]` | `[CL:4608967]` | CourtListener docket |
| `[FEC:committee]` | `[FEC:C00431569]` | FEC committee page |
| `[FARA:num]` | `[FARA:6071]` | FARA registration |
| `[REG:XX:id]` | `[REG:FL:P950000272]` | State corporate registry |
| `[DS10]` | `[DS10]` | DS10 financial dataset page |

### 2. Processing Pipeline

```
Content with tokens → applyCitations() → HTML with citation links
                              ↓
                    findingEvidenceMap (for Finding #N resolution)
                              ↓
                    renderFootnotes() → Sources section HTML
                              ↓
        annotateSupportSpans() → sentence wrappers + support graph + metrics
```

### 3. File Locations

| Component | Path |
|-----------|------|
| Core library | `site/web/src/lib/citations.ts` |
| Support span engine | `site/web/src/lib/supportSpans.ts` |
| Shared content pipeline | `site/web/src/lib/contentEvidencePipeline.ts` |
| Evidence mode UI logic | `site/web/src/lib/supportMode.ts` |
| Article page | `site/web/src/pages/articles/[slug].astro` |
| Dossier page | `site/web/src/pages/dossiers/[slug].astro` |
| Finding evidence | `site/web/src/lib/findingEvidence.ts` |
| Coverage report CLI | `site/web/scripts/report-support-coverage.mjs` |

## Article Pipeline Integration

Articles use citations in the **Phase 2: Draft** stage:

```mdx
Epstein received $158 million in advisory fees from Leon Black 
through Southern Trust Company[EFTA02576529][EFTA02576530].
```

The `applyCitations()` function in `[slug].astro`:
1. Parses the MDX content
2. Replaces tokens with `<sup class="citation"><a>...</a></sup>`
3. Renders footnotes at the bottom

## Dossier Integration (New)

Dossiers now use the same citation system:

### Before (No Citations)
```html
<p>Alessandro Benedetti operated as Epstein's neighbor on Avenue Foch 
(EFTA00925685).</p>
```

### After (With Citations)
```html
<p>Alessandro Benedetti operated as Epstein's neighbor on Avenue Foch
<sup class="citation"><a href="https://jmail.world/thread/EFTA00925685">1</a></sup>.</p>

<!-- At bottom of page -->
<section class="citation-block">
  <div class="section-label">Sources</div>
  <ol class="citation-list">
    <li id="fn-1"><a href="https://jmail.world/thread/EFTA00925685">EFTA00925685</a></li>
  </ol>
</section>
```

### Dossier-Specific Features

1. **Finding Evidence Map**: Built from the dossier's own `findings` array
   - `[Finding #6]` resolves to that finding's evidence sources
   - Multiple evidence sources render as sub-links in footnote

2. **Parenthetical Normalization**: Legacy `(EFTAxxxxx)` format is auto-converted to `[EFTAxxxxx]`
   - Pure parenthetical citation groups like `(Finding #42, EFTA02576529)` are normalized to `[Finding #42][EFTA02576529]`

3. **Shared Numbering**: Citations are deduplicated across lead + all sections

## Evidence Support Spans

### Attribution Rule

- Unit: sentence
- Only explicit inline citations in that sentence count as support
- No carryover from previous/next sentence
- `[Finding #N]` maps to both:
  - the finding node (`finding:N`)
  - each resolved underlying source node from that finding

### UI Behavior

- Toggle: **Evidence Mode** (default off)
- When on:
  - supported sentences receive subtle support tint
  - unsupported sentences receive muted warning tint
- Interactions:
  - click sentence: highlight supporting citations/sources and related dependent spans
  - click citation/source: highlight all spans that depend on that evidence
- Scope: current page only (article or dossier page being viewed)

### Data Attributes (HTML Contract)

Citations now emit stable attributes used by support mode and tests:
- Superscript links:
  - `data-citation-number`
  - `data-citation-key`
- Footnote primary links:
  - `data-citation-number`
  - `data-citation-key`
- Footnote source links/spans:
  - `data-source-key`
  - `data-parent-citation-key`

### Coverage Metrics CLI

Run:

```bash
cd site/web
npm run report:support-coverage
# or
npm run report:support-coverage:changed -- --base-ref <BASE> --head-ref <HEAD>
```

Output is JSON (stdout only), non-blocking by design in V1:
- `total_sentences`
- `supported_sentences`
- `unsupported_sentences`
- `supported_sentence_pct`
- `orphan_citations_count`
- `orphan_citations`
- `source_fanout` (source node key → dependent span count)

## Usage in Skills

### write-article SKILL.md

Phase 2 (Draft) specifies:
```
### Citation format

Use the structured citation tokens that render as linked footnotes:
- `[EFTA02576529]` — DOJ corpus document
- `[SEC:0001193125-15-266790]` — SEC EDGAR filing
- `[990:133095231]` — IRS 990 via ProPublica
...
```

### curate-dossier SKILL.md

Updated to include:
```markdown
### 5. Citation Format

Dossier content uses the same citation system as articles. Use these inline tokens:

| Token Pattern | Example | Renders As |
|--------------|---------|------------|
| `[EFTAxxxxxx]` | `[EFTA02576529]` | Linked superscript to Jmail viewer |
...

**Citation rules:**
- Place citation immediately after the claim it supports
- Multiple sources: `[EFTA02576529][EFTA02576530]`
- The page auto-generates a Sources footnote section
```

## Technical Implementation

### citations.ts

```typescript
// Main functions
export function applyCitations(markdown: string, options?: CitationOptions): {
  markdown: string;  // HTML with citation links
  entries: CitationEntry[];
}

export function renderFootnotes(entries: CitationEntry[]): string;
export function extractEvidenceLinks(raw: string): CitationLink[];
```

### CitationEntry Type

```typescript
type CitationEntry = {
  key: string;       // Unique identifier
  label: string;     // Display text
  number: number;    // Footnote number
  url?: string;      // External link
  sources?: CitationLink[];  // For Finding #N resolution
};
```

### Dossier Page Implementation

```astro
---
import { applyCitations, renderFootnotes } from '../../lib/citations';

// Build finding evidence map from dossier data
const findingEvidenceMap = buildDossierFindingEvidenceMap(dossier);

// Process lead
const { html: leadHtml, entries: leadCitations } = 
  applyCitations(curation.lead, { findingEvidenceMap });

// Process sections with shared numbering
const processedSections = sections.map(section => {
  const result = applyCitations(section.content, { findingEvidenceMap });
  return { ...section, processedContent: result.html };
});

// Render shared footnotes
const footnotesHtml = renderFootnotes(allCitations);
---
```

## Migration Notes

### Existing Dossiers

Existing dossiers with parenthetical citations `(EFTAxxxxx)` are automatically normalized:

```typescript
// In citations.ts
function normalizeCitationPatterns(text: string): string {
  // Converts (EFTAxxxxxx) -> [EFTAxxxxxx]
  return text.replace(/(?<!\[)\((EFTA\d{6,})\)/g, '[$1]');
}
```

### Future Dossier Updates

When re-curating dossiers, use bracket format `[EFTAxxxxx]` instead of parentheses for consistency.

## Quality Checklist

For both articles and dossiers:

- [ ] Every factual claim has an inline citation
- [ ] Claims are sentence-local supported (no implicit citation carryover)
- [ ] Citations use correct token format
- [ ] Finding citations (`[Finding #N]`) reference actual findings
- [ ] Sources footnote section appears at bottom
- [ ] Citation links resolve correctly
- [ ] Evidence Mode renders both supported and unsupported spans
- [ ] Support coverage report is reviewed before publish

## Styling

Citations use these CSS classes:

```css
.citation          /* The <sup> wrapper */
.citation-index    /* Number in footnote list */
.citation-entry    /* Link in footnote list */
.citation-block    /* Sources section container */
.citation-list     /* <ol> of sources */
.citation-sources  /* Sub-sources for Finding #N */
```
