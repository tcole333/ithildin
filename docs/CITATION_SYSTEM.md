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
| `[PROPERTY:source/jurisdiction/kind/id]` | `[PROPERTY:us-nc-onemap-parcels/37005/parcel/3013467134]` | Canonical property record; official source URL when registered |
| `[ACRIS:docid]` | `[ACRIS:2008012900966001]` | NYC property record |
| `[STATECOURT:source/court/case/kind]` | `[STATECOURT:us-ny-nyscef/ny-supreme/CV-2026-1/case]` | Canonical state/local-court record; official source URL when registered |
| `[CL:docket]` | `[CL:4608967]` | CourtListener docket |
| `[FEC:committee]` | `[FEC:C00431569]` | FEC committee page |
| `[FARA:num]` | `[FARA:6071]` | FARA registration |
| `[REG:XX:id]` | `[REG:FL:P950000272]` | State corporate registry |
| `[DS10]` | `[DS10]` | DS10 financial dataset page |
| `[DOCUMENTCLOUD:id]` | `[DOCUMENTCLOUD:24402693]` | DocumentCloud document |
| `[OffshoreAlert:slug]` | `[OffshoreAlert:DB-Consent-Order-NYDFS]` | OffshoreAlert article |
| `[MUCKROCK:id]` | `[MUCKROCK:78799/Docs.redacted.pdf]` | MuckRock FOIA request |
| `[LittleSis:id]` | `[LittleSis:101661]` | LittleSis entity profile |
| `[ICIJ:id]` | `[ICIJ:82004676]` | ICIJ Offshore Leaks node |
| `[USASPENDING:id]` | `[USASPENDING:W91WAW11F0017]` | USAspending award (contract/grant) |
| `[USASPENDING:RECIPIENT:uei]` | `[USASPENDING:RECIPIENT:RN99S3S7N977]` | USAspending recipient profile |
| `[MEDICARE:npi]` | `[MEDICARE:1003000126]` | Medicare provider spending |

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
| Core library | `web/src/lib/citations.ts` |
| Support span engine | `web/src/lib/supportSpans.ts` |
| Shared content pipeline | `web/src/lib/contentEvidencePipeline.ts` |
| Evidence mode UI logic | `web/src/lib/supportMode.ts` |
| Article page | `web/src/pages/articles/[slug].astro` |
| Dossier page | `web/src/pages/dossiers/[slug].astro` |
| Finding evidence | `web/src/lib/findingEvidence.ts` |
| Coverage report CLI | `web/scripts/report-support-coverage.mjs` |

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
cd web
npm run report:support-coverage
# or
npm run report:support-coverage:changed
# compare a revision to the current staged/unstaged/untracked worktree
npm run report:support-coverage:changed -- --base-ref HEAD --head-ref WORKTREE
# or compare two revisions
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

### Focused Citation Validation

Use `npm run check:citations:focused` while changing citation resolution or
rendering. It runs the citation unit and snapshot suites without making an
unrelated legacy corpus finding look like a regression in the focused change.

For content edits, run `npm run lint:citations:changed:strict`; it checks the
staged, unstaged, and untracked article/dossier files in the worktree. Use
`-- --base-ref <BASE> --head-ref <HEAD>` to check a commit range, or
`-- --base-ref HEAD --head-ref WORKTREE` to spell out worktree scope.

`npm run lint:citations` remains the full release gate. Do not create or update
a blanket baseline to hide existing errors; fix the affected content or use a
narrow, expiring entry in `src/data/citation-exceptions.json` when an exception
is independently justified.

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

### Architecture: Declarative Citation Registry

All 24 citation types are defined in a single `CITATION_REGISTRY` array in `web/src/lib/citations.ts`. Each entry is a `CitationTypeDef` that co-locates everything about a type:

```typescript
type CitationTypeDef = {
  id: string;              // Unique type identifier ("efta", "sec", "fec", etc.)
  tokenPattern: string;    // Regex pattern string for bracket token detection
  healthTier: HealthTier;  // tier1-4 or "label-only" for check-citation-health.mjs
  resolve(token: string, options: CitationOptions): Omit<CitationEntry, "number"> | null;
  extract(raw: string): CitationLink[];
  stripPattern?: RegExp | false;  // false = don't strip from remainder text
};
```

The public API functions (`applyCitations`, `extractEvidenceLinks`, `resolveCitationToken`) loop the registry instead of maintaining separate if/else chains. `CITE_TOKEN_PATTERNS` is derived from the registry automatically.

### Adding a New Citation Type

To add a new citation type (e.g., `[HUDOC:001-234567]`), add **one object** to `CITATION_REGISTRY` in `web/src/lib/citations.ts`:

```typescript
// In CITATION_REGISTRY array:
{
  id: "hudoc",
  tokenPattern: "HUDOC:\\d{3}-\\d{6}",
  healthTier: "tier1",
  resolve(token) {
    const match = token.match(/HUDOC:(\d{3}-\d{6})/i);
    if (!match) return null;
    const caseId = match[1];
    return {
      key: `hudoc:${caseId}`,
      label: `HUDOC ${caseId}`,
      url: `https://hudoc.echr.coe.int/eng?i=${caseId}`,
    };
  },
  extract(raw) {
    return (raw.match(/HUDOC:\d{3}-\d{6}/gi) || []).map(ref => {
      const caseId = ref.replace(/HUDOC:/i, "");
      const url = `https://hudoc.echr.coe.int/eng?i=${caseId}`;
      return { key: url, label: `HUDOC:${caseId}`, url };
    });
  },
},
```

That's it. No other files need to change for the citation engine to recognize the new type.

### Public-record source landing URLs

`PROPERTY:` and `STATECOURT:` tokens carry a canonical source ID as their
first path segment. `web/src/data/source-urls.json` can register that source's
official landing URL using:

```json
{
  "PROPERTY_SOURCE:us-nc-onemap-parcels": "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1",
  "STATECOURT_SOURCE:us-ny-nyscef": "https://iapps.courts.state.ny.us/nyscef/CaseSearch"
}
```

The rendered citation keeps the complete canonical record label and links to
the registered source page. It does not synthesize a parcel, case, or document
deep link from source-native identifiers. An unregistered source ID remains a
record-only citation.

### Generic URL Override (`source-urls.json`)

For one-off citation keys that don't fit a structured pattern (e.g., a specific report URL, a news article), add a key → URL mapping to `web/src/data/source-urls.json`:

```json
{
  "KPMG:IPI_Forensic_Review_p12": "https://example.com/kpmg-ipi-report.pdf"
}
```

The override is consulted as the **last resort** in both `resolveCitationToken()` and `extractEvidenceLinks()` — after all registry patterns have been tried. This means structured patterns always take priority.

**Checklist after adding a type:**
1. Add a unit test in `web/scripts/test-citations.mjs` (both `applyCitations` and `extractEvidenceLinks`)
2. Run `npm run test:citations && npm run test:citations:snapshots`
3. Update the token pattern table in this document (below) and in relevant skills
4. If the URL builder is complex, extract it as a standalone function above the registry

### extract() key convention

The `extract` method returns `CitationLink[]` where `key` is `url || label` (matching the deduplication behavior of `extractEvidenceLinks`). For types with URLs, `key` is the URL. For label-only types (KPMG), `key` is the label string.

### Public API

```typescript
export function applyCitations(markdown: string, options?: CitationOptions, state?: CitationState): {
  markdown: string;
  entries: CitationEntry[];
}

export function renderFootnotes(entries: CitationEntry[]): string;
export function extractEvidenceLinks(raw: string): CitationLink[];
export function splitCitationGroup(group: string): string[];
export function createCitationState(): CitationState;
export function getCitationHealthTier(citationKey: string): HealthTier | "skip";
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

### File Locations

| Component | Path |
|-----------|------|
| Core library + registry | `web/src/lib/citations.ts` |
| Unit tests (48) | `web/scripts/test-citations.mjs` |
| Snapshot regression | `web/scripts/test-citation-snapshots.mjs` |
| Link health checker | `web/scripts/check-citation-health.mjs` |
| Lint | `web/scripts/lint-citations.mjs` |
| Support span engine | `web/src/lib/supportSpans.ts` |
| Shared content pipeline | `web/src/lib/contentEvidencePipeline.ts` |
| Evidence mode UI logic | `web/src/lib/supportMode.ts` |
| Coverage report CLI | `web/scripts/report-support-coverage.mjs` |

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

Existing dossiers with parenthetical citations `(EFTAxxxxx)` are automatically normalized to bracket format by `normalizeCitationPatterns()`.

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
