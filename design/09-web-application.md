# 09 — Web Application Design

## 1. Overview

The web application is the primary delivery mechanism for all understanding engine output. It transforms markdown content, structured data, and visual exports into a **browsable, searchable research tool** — an investigative wiki where entity mentions auto-link to dossier pages, network graphs are interactive, and investigation threads provide primary navigation.

This is not a blog or CMS. It is a **structured research interface** for navigating interconnected investigation output across 6 threads, hundreds of entities, and thousands of findings.

### Design Principles

1. **Content-first**: Markdown with YAML frontmatter is the source of truth. The web app renders it.
2. **Interlinked by default**: Every entity mention links to its dossier page. Every finding cites its sources.
3. **Thread-navigable**: Investigation threads (Epstein Core, Mega Group, Deutsche Bank, Israeli Intel, Apollo/Black, Gulf State) are the primary organizational structure.
4. **Searchable**: Full-text search across all content types with faceted filtering.
5. **Privacy-aware**: Designed for controlled access. Self-hostable, no third-party analytics.

## 2. Technology Choice

### Recommendation: Astro + Islands Architecture

**Astro** is the recommended framework because:

- **Static-first**: Generates static HTML for all content pages (dossiers, explainers, articles). Fast, cacheable, zero JS by default.
- **Islands architecture**: Interactive components (network graphs, timelines, search) load as isolated "islands" of JavaScript — only where needed.
- **Markdown-native**: Built-in support for markdown with YAML frontmatter. No rendering pipeline to build.
- **Content collections**: Type-safe content schemas map directly to our modality types.
- **Framework-agnostic islands**: D3.js graphs, React search component, vanilla timeline — each island uses whatever framework fits.

**Alternatives considered**:

| Framework | Pros | Cons |
|-----------|------|------|
| Next.js | Full SSR, API routes, React ecosystem | Heavier than needed, ships more JS, requires Node runtime |
| Eleventy | Simple, fast, markdown-native | No islands, poor interactive component story |
| SvelteKit | Good DX, small bundles | Smaller ecosystem for visualization libraries |
| Plain static (Hugo) | Fastest build | No interactive components without separate tooling |

### Why not a dynamic app?

The content changes when agents publish — not when users interact. A static site with interactive islands covers the use case without requiring a running application server. If real-time features are needed later (live investigation dashboard, collaborative annotations), add an API layer incrementally.

## 3. Content Structure

### 3.1 Route Map

```
/                               # Landing — investigation overview, recent updates
/entities/{slug}                # Wiki dossier pages (persons, orgs, entities)
/threads/{id}                   # Investigation thread overview
/threads/{id}/findings          # All findings for a thread
/explainers/{slug}              # Mechanism explainer articles
/analysis/{slug}                # Deep analytical articles
/graph                          # Interactive network visualization
/graph/{entity-slug}            # Ego network for specific entity
/timeline                       # Full investigation timeline
/timeline/{thread-id}           # Thread-specific timeline
/finances/{entity-slug}         # Financial flow diagrams
/search                         # Full-text search
```

### 3.2 Content Directory Structure

All content lives as markdown files in a `content/` directory mirroring the routes:

```
web/
├── src/
│   ├── content/
│   │   ├── entities/           # Wiki dossier markdown files
│   │   │   ├── jeffrey-epstein.md
│   │   │   ├── leon-black.md
│   │   │   ├── southern-trust-company.md
│   │   │   └── ...
│   │   ├── explainers/         # Mechanism explainer articles
│   │   │   ├── trust-layering.md
│   │   │   ├── compliance-gap-exploitation.md
│   │   │   └── ...
│   │   ├── analysis/           # Analytical articles
│   │   │   ├── apollo-stc-flows.md
│   │   │   ├── mega-group-structure.md
│   │   │   └── ...
│   │   └── threads/            # Thread overview pages
│   │       ├── 1-epstein-core.md
│   │       ├── 2-mega-group.md
│   │       └── ...
│   ├── components/
│   │   ├── NetworkGraph.tsx    # D3/Sigma island
│   │   ├── Timeline.tsx        # Timeline island
│   │   ├── FinancialFlow.tsx   # Sankey diagram island
│   │   ├── Search.tsx          # Search island
│   │   ├── EntityMention.astro # Inline entity link component
│   │   └── ThreadNav.astro     # Thread navigation sidebar
│   ├── layouts/
│   │   ├── BaseLayout.astro
│   │   ├── DossierLayout.astro
│   │   ├── ArticleLayout.astro
│   │   └── GraphLayout.astro
│   └── pages/
│       ├── index.astro
│       ├── search.astro
│       ├── graph/
│       │   ├── index.astro
│       │   └── [slug].astro
│       ├── timeline/
│       │   ├── index.astro
│       │   └── [id].astro
│       └── finances/
│           └── [slug].astro
├── public/
│   └── data/                   # Pre-built JSON for interactive components
│       ├── graph.json          # Full network graph data
│       ├── timeline.json       # Full event timeline
│       └── entities.json       # Entity index for search
└── astro.config.mjs
```

### 3.3 Content Schemas

Each content type has a defined schema (Astro content collections):

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const entities = defineCollection({
  type: 'content',
  schema: z.object({
    name: z.string(),
    entity_type: z.enum(['person', 'organization', 'entity', 'location']),
    aliases: z.array(z.string()).default([]),
    thread_ids: z.array(z.number()).default([]),
    status: z.enum(['active', 'draft', 'stale']).default('active'),
    finding_count: z.number().default(0),
    connection_count: z.number().default(0),
    last_updated: z.date(),
    summary: z.string(),  // One-line summary for search results
    key_relationships: z.array(z.object({
      entity: z.string(),
      slug: z.string(),
      type: z.string(),
      detail: z.string(),
    })).default([]),
  }),
});

const explainers = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    mechanism: z.string(),  // e.g., "trust-layering", "compliance-gap"
    thread_ids: z.array(z.number()).default([]),
    entities_mentioned: z.array(z.string()).default([]),
    published_at: z.date(),
    updated_at: z.date(),
    summary: z.string(),
    word_count: z.number(),
  }),
});

const analysis = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    lens: z.enum(['financial', 'geopolitical', 'legal', 'intelligence']),
    thread_ids: z.array(z.number()).default([]),
    entities_mentioned: z.array(z.string()).default([]),
    published_at: z.date(),
    updated_at: z.date(),
    summary: z.string(),
    word_count: z.number(),
    source_count: z.number(),  // Number of primary sources cited
  }),
});

const threads = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    thread_id: z.number(),
    description: z.string(),
    key_entities: z.array(z.string()),
    finding_count: z.number(),
    connection_count: z.number(),
    last_updated: z.date(),
  }),
});
```

## 4. Data Flow

### 4.1 Publishing Pipeline

```
                                          ┌──────────────────┐
                                          │   Web App Build   │
                                          │   (astro build)   │
                                          └────────┬─────────┘
                                                   │
                                          Reads markdown +
                                          JSON data files
                                                   │
┌──────────────┐    ┌──────────────┐    ┌──────────▼─────────┐    ┌──────────────┐
│  Queue System │───▶│ Understanding│───▶│  content/ directory │───▶│ Static HTML  │
│  (PostgreSQL) │    │   Agents     │    │  (markdown + JSON)  │    │ (dist/)      │
└──────────────┘    └──────────────┘    └────────────────────┘    └──────────────┘
                                                   │
                                          WebPublisher writes:
                                          - markdown files
                                          - graph.json
                                          - timeline.json
                                          - entity index
```

**Steps**:

1. Agent completes a job (e.g., `wiki_dossier_update` for Leon Black)
2. Editor agent reviews and approves
3. `WebPublisher` writes markdown to `content/entities/leon-black.md`
4. `WebPublisher` updates `public/data/entities.json` (search index)
5. Build trigger runs `astro build` → generates static HTML
6. Deploy to hosting (or serve locally)

### 4.2 Incremental Updates

Not every publish requires a full rebuild. Astro supports incremental builds, but even full rebuilds are fast (<30s for hundreds of pages). The publish flow:

```python
class WebPublisher:
    def publish(self, content_path: str, modality: str, metadata: dict):
        """Write content and trigger rebuild."""

        # 1. Write markdown to content directory
        output = self.get_output_path(modality, metadata)
        content = self.read_and_interlink(content_path)
        self.write_content(output, content)

        # 2. Update data files for interactive components
        if self.should_update_graph(modality):
            self.rebuild_graph_json()
        if self.should_update_timeline(modality):
            self.rebuild_timeline_json()

        # 3. Update search index
        self.update_entity_index(metadata)

        # 4. Record in published_content table
        self.record_publication(output, modality, metadata)

        # 5. Trigger rebuild (debounced — max once per 5 minutes)
        self.trigger_rebuild()
```

### 4.3 Data Export for Interactive Components

Interactive components consume pre-built JSON files (not database queries at runtime):

**`public/data/graph.json`** — Network graph:
```json
{
  "nodes": [
    { "id": "jeffrey-epstein", "label": "Jeffrey Epstein", "type": "person",
      "degree": 262, "threads": [1], "url": "/entities/jeffrey-epstein" },
    { "id": "leon-black", "label": "Leon Black", "type": "person",
      "degree": 15, "threads": [5], "url": "/entities/leon-black" }
  ],
  "edges": [
    { "source": "jeffrey-epstein", "target": "leon-black",
      "type": "financial", "strength": "strong", "label": "$158M+ via STC" }
  ]
}
```

**`public/data/timeline.json`** — Events:
```json
{
  "events": [
    { "date": "2019-07-06", "title": "Epstein arrested",
      "category": "legal", "threads": [1],
      "entities": ["jeffrey-epstein"], "detail": "Arrested at Teterboro Airport..." }
  ]
}
```

**`public/data/entities.json`** — Search index:
```json
[
  { "slug": "jeffrey-epstein", "name": "Jeffrey Epstein",
    "type": "person", "summary": "Financier and convicted sex offender...",
    "aliases": ["JE", "Jeffrey E. Epstein"],
    "threads": [1], "finding_count": 262 }
]
```

These JSON files are rebuilt by `analysis_export.py` (existing tool) with a web-compatible output format.

## 5. Search

### 5.1 Client-Side Search (Phase 1)

For initial deployment, use client-side search via **Pagefind** (Astro-native):

- Zero-config integration with Astro
- Builds a search index at build time
- Searches entirely in the browser (no server needed)
- Supports faceted filtering by content type, thread, entity type
- Index size scales well (< 1MB for thousands of pages)

```astro
---
// src/pages/search.astro
import BaseLayout from '../layouts/BaseLayout.astro';
---
<BaseLayout title="Search">
  <div id="search"></div>
  <link href="/_pagefind/pagefind-ui.css" rel="stylesheet" />
  <script>
    import { PagefindUI } from '/_pagefind/pagefind-ui.js';
    new PagefindUI({
      element: '#search',
      showSubResults: true,
      showImages: false,
    });
  </script>
</BaseLayout>
```

### 5.2 Server-Side Search (Phase 2, if needed)

If search volume or complexity outgrows client-side:

- PostgreSQL `tsvector` search against the `published_content` table (already defined in `07-infra-integration.md`)
- API endpoint via lightweight server (Astro SSR mode or standalone)
- Facets: modality, thread, entity type, date range
- Ranking: freshness + finding count + connection density

## 6. Entity Interlinking

The core feature distinguishing this from a static site: **every entity mention in any content type automatically links to its dossier page**.

### 6.1 Interlinking Pipeline

The `DossierInterlinker` (defined in `04-content-pipeline.md`) runs at publish time:

1. Maintain a mapping of `entity_name → slug` from the entities content collection
2. For each piece of content being published, scan the body text
3. Replace entity name mentions with markdown links: `[Leon Black](/entities/leon-black)`
4. Handle aliases (e.g., "Black" in context → same link, but only when unambiguous)
5. Avoid double-linking (don't link inside headings, existing links, or code blocks)

### 6.2 Disambiguation

Entity names can be ambiguous ("Black" could be Leon Black or a color). Rules:

- **Full name match**: Always link. "Leon Black" → `[Leon Black](/entities/leon-black)`
- **Surname-only match**: Link only if the full name appeared earlier in the same document
- **Acronym match**: Link only if explicitly defined earlier (e.g., "Southern Trust Company (STC)")
- **Common words**: Never link entity names that are common English words unless the full name matches

### 6.3 Backlinks

Each dossier page displays a "Mentioned in" section showing all content that links to it:

```astro
---
// In DossierLayout.astro
const backlinks = await getBacklinks(entity.slug);
---
<section class="backlinks">
  <h2>Mentioned In</h2>
  <ul>
    {backlinks.map(link => (
      <li>
        <a href={link.url}>{link.title}</a>
        <span class="badge">{link.modality}</span>
      </li>
    ))}
  </ul>
</section>
```

## 7. Interactive Visualizations

### 7.1 Network Graph

**Library**: Sigma.js (WebGL-based, handles 1000+ nodes smoothly)

**Features**:
- Full network view at `/graph` with zoom, pan, search
- Entity ego networks at `/graph/{slug}` (1-2 hop neighborhood)
- Color-coded by thread (6 thread colors)
- Node size proportional to degree centrality
- Edge thickness proportional to connection strength
- Click node → navigate to dossier page
- Filter by thread, entity type, connection type
- Highlight bridges and structural holes (from `graph_tools.py` output)

```typescript
// src/components/NetworkGraph.tsx
import { SigmaContainer, useLoadGraph } from '@react-sigma/core';
import graphData from '/data/graph.json';

export default function NetworkGraph({ entitySlug }: { entitySlug?: string }) {
  const loadGraph = useLoadGraph();

  useEffect(() => {
    const graph = new Graph();
    const data = entitySlug
      ? filterEgoNetwork(graphData, entitySlug, 2)  // 2-hop neighborhood
      : graphData;

    data.nodes.forEach(n => graph.addNode(n.id, {
      label: n.label,
      size: Math.log(n.degree + 1) * 3,
      color: THREAD_COLORS[n.threads[0]] || '#888',
      url: n.url,
    }));
    data.edges.forEach(e => graph.addEdge(e.source, e.target, {
      label: e.label,
      size: STRENGTH_MAP[e.strength],
    }));
    loadGraph(graph);
  }, [entitySlug]);

  return (
    <SigmaContainer style={{ height: '80vh' }}>
      {/* Controls: zoom, search, filter */}
    </SigmaContainer>
  );
}
```

### 7.2 Timeline

**Library**: Timeline.js or custom D3 timeline

**Features**:
- Scrollable timeline from 1985–2024
- Events color-coded by category (legal, financial, political, etc.)
- Filter by thread, entity, category
- Click event → expand detail panel with linked findings
- Zoom levels: decade → year → month
- Highlight temporal clusters (from `event_timeline.py` analysis)

### 7.3 Financial Flow Diagrams

**Library**: D3.js Sankey diagrams

**Features**:
- Entity-specific flow diagrams at `/finances/{slug}`
- Source → intermediary → destination flow visualization
- Amounts labeled on edges
- Time-series capability (animate flows over years)
- Click node → navigate to entity dossier
- Pre-built from `DS10 Financial` and findings data

## 8. Page Layouts

### 8.1 Dossier Page

```
┌─────────────────────────────────────────────────────┐
│  [Thread Nav]  │  Leon Black                        │
│                │  ════════════                       │
│  Threads:      │  Type: Person                      │
│  · Core        │  Threads: Apollo/Black Financial    │
│  · Mega Group  │  Status: Active investigation      │
│  · Deutsche    │  Last updated: 2026-02-15          │
│  · Israeli     │  Findings: 47 │ Connections: 23    │
│  · Apollo ◄    │                                    │
│  · Gulf State  │  Summary                           │
│                │  ─────────                         │
│  Content:      │  [1-2 paragraph summary]           │
│  · Entities    │                                    │
│  · Explainers  │  Key Relationships                 │
│  · Analysis    │  ──────────────────                │
│  · Graph       │  · Jeffrey Epstein (financial)     │
│  · Timeline    │  · STC (ownership)                 │
│                │  · Apollo Global (position)         │
│  Search: [  ]  │                                    │
│                │  [Body content — findings,          │
│                │   evidence, analysis organized      │
│                │   by topic with source citations]   │
│                │                                    │
│                │  Financial Flow                     │
│                │  ──────────────                    │
│                │  [Embedded Sankey diagram]          │
│                │                                    │
│                │  Mentioned In                       │
│                │  ────────────                      │
│                │  · "Apollo-STC Flows" (analysis)    │
│                │  · "Trust Layering" (explainer)     │
│                │                                    │
│                │  Sources                            │
│                │  ───────                           │
│                │  · EFTA02576529 (DOJ Vol 11)        │
│                │  · Dechert Report (redacted)        │
└─────────────────────────────────────────────────────┘
```

### 8.2 Thread Overview

```
┌─────────────────────────────────────────────────────┐
│  Thread 5: Apollo / Leon Black Financial             │
│  ═══════════════════════════════════════             │
│                                                      │
│  252 findings │ 89 connections │ 34 entities          │
│                                                      │
│  Description                                         │
│  ───────────                                        │
│  [Thread description — scope, key questions,         │
│   status of investigation]                           │
│                                                      │
│  Key Entities                    Network Fragment     │
│  ─────────────                  ─────────────────    │
│  · Leon Black                   [Sigma.js mini-graph │
│  · Marc Rowan                    showing thread      │
│  · Josh Harris                   entities only]      │
│  · Southern Trust Company                            │
│  · Apollo Global                                     │
│                                                      │
│  Recent Findings                                     │
│  ───────────────                                    │
│  · [Last 10 findings for this thread]                │
│                                                      │
│  Related Content                                     │
│  ───────────────                                    │
│  · "Apollo-STC Flows" (analysis)                     │
│  · "Trust Layering" (explainer)                      │
└─────────────────────────────────────────────────────┘
```

## 9. Authentication & Access Control

### 9.1 Access Model

This is **not a public website**. It contains sensitive investigation findings with specific sourcing requirements. Access tiers:

| Level | Access | Implementation |
|-------|--------|---------------|
| **Private** (default) | Single researcher or small team | No auth needed — serve on localhost or VPN |
| **Shared team** | Invited collaborators | Basic auth (htpasswd) or Cloudflare Access |
| **Semi-public** | Verified researchers | OAuth (GitHub/Google) with allowlist |
| **Public** | Open access | Requires editorial review of all content first |

### 9.2 Recommendation

Start with **private** (localhost + Tailscale for remote access). Add authentication only when sharing externally. Never deploy publicly without a full editorial review pass — findings contain unverified content and inferences that could be defamatory if published without context.

### 9.3 Content Sensitivity

All content includes `verification_status` in frontmatter. The web app should:

- Display verification badges (verified / unverified / disputed)
- Show confidence levels on findings
- Clearly label inferences vs. direct quotes
- Include source citations for every claim

## 10. Deployment

### 10.1 Local Development

```bash
cd web/
npm install
npm run dev          # Astro dev server at localhost:4321
```

### 10.2 Build & Preview

```bash
npm run build        # Generates static site in dist/
npm run preview      # Serve built site locally
```

### 10.3 Production Hosting

**Option A: Self-hosted (recommended for privacy)**

```bash
# Simple static file server
cd web/dist && python -m http.server 8080

# Or with Caddy (auto-HTTPS, reverse proxy)
caddy file-server --root web/dist --listen :8080

# Or Docker
docker build -t osint-web .
docker run -p 8080:80 osint-web
```

**Option B: Tailscale Funnel (share with team)**

```bash
# Serve to specific Tailscale users
tailscale serve --bg 8080
```

**Option C: Cloud hosting (if semi-public)**

- Cloudflare Pages (free, fast, Access for auth)
- Vercel (free tier, serverless functions for search API)
- Netlify (free tier, form handling)

All three support deploy-on-push from a git repository.

### 10.4 Automated Publishing

The build integrates with the understanding engine pipeline:

```bash
#!/bin/bash
# scripts/publish_web.sh — called by WebPublisher after content updates

cd web/
npm run build

# Optional: deploy to hosting
# npx wrangler pages deploy dist/  # Cloudflare
# vercel --prod                     # Vercel
```

Debounced by the `WebPublisher` — max one rebuild per 5 minutes even if multiple pieces of content are published.

## 11. Performance Considerations

### 11.1 Build Performance

- **Hundreds of pages**: Astro builds in <30 seconds
- **Thousands of pages**: May need incremental builds or content chunking
- **Interactive data**: JSON files for graph/timeline should be <5MB (current graph: 670 nodes, 1065 edges ≈ 200KB)

### 11.2 Runtime Performance

- **Static HTML**: Zero server load for content pages
- **Client-side search**: Pagefind index <1MB, instant results
- **Network graph**: Sigma.js handles 1000+ nodes in WebGL. For full graph (670 nodes), performance is excellent. For 5000+ nodes, implement progressive loading.
- **Timeline**: Virtualized rendering for 100+ events

### 11.3 Graph Data Budget

The network graph JSON should stay under 2MB for smooth client-side rendering:

| Nodes | Edges | Approx JSON Size | Performance |
|-------|-------|-------------------|-------------|
| 670 | 1,065 | ~200KB | Excellent |
| 2,000 | 5,000 | ~800KB | Good |
| 5,000 | 15,000 | ~2.5MB | Needs progressive loading |

If the graph grows beyond 5,000 nodes, switch to server-rendered subgraphs with on-demand expansion.

## 12. Integration with Existing Infrastructure

### 12.1 Data Sources

The web app reads from two sources:

1. **Content directory** (`web/src/content/`): Markdown files written by `WebPublisher`
2. **Data directory** (`web/public/data/`): JSON files exported by `analysis_export.py`

It does **not** query PostgreSQL or investigation.db at build time. All data flows through the content/data files. This decouples the web app from the investigation infrastructure.

### 12.2 Existing Tool Integration

| Existing Tool | Web App Usage |
|---------------|---------------|
| `analysis_export.py connections-graph` | Generates `graph.json` |
| `analysis_export.py timeline-export` | Generates `timeline.json` |
| `analysis_export.py entity-network` | Generates per-entity ego network data |
| `analysis_export.py coverage-matrix` | Generates investigation coverage data for dashboard |
| `findings_tracker.py` | Source data for dossier content |
| `graph_tools.py` | Computes centrality/bridges for graph styling |

### 12.3 Content Generation Trigger

When the understanding engine publishes content:

```
Agent completes job
    → Editor reviews + approves
    → WebPublisher.publish()
        → Writes markdown to content/
        → Updates data JSON files
        → Triggers web build (debounced)
        → Records in published_content table
```

## 13. Future Extensions

These are **not in scope for initial implementation** but inform architectural decisions:

- **Collaborative annotations**: Users can annotate findings (requires auth + database)
- **Live investigation dashboard**: Real-time queue status, agent activity (requires SSR or WebSocket)
- **Export to PDF/EPUB**: Generate downloadable reports from content collections
- **API access**: REST/GraphQL API for programmatic access to published content
- **Diff view**: Show what changed between dossier versions
- **Citation graph**: Visualize which findings cite which sources

---

**See also**:
- `04-content-pipeline.md` — Understanding engine that produces web app content
- `07-infra-integration.md` §2.3 — Web application database schema
- `08-implementation-phases.md` Phase 4 (web scaffold) and Phase 7 (full frontend)
