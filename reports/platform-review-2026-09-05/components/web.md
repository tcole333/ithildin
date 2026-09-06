# Web and publication boundary review

Reviewed the current shared working tree on 2026-09-05. No production source/content was edited, no site was deployed, and the full export/build pipeline was deliberately not run because it mutates authored content. Existing worktree modifications include citation code/tests/source URLs; findings below describe the current tree and are not attributed to a particular model generation.

## Highest-priority defects

### P1 — Network deduplication transfers verification and profile ownership between different claims

**Locations:** `pipeline/export_network.py:224-244` (especially 227-242); `web/src/components/NetworkPage.tsx:34-38`; `web/src/components/NetworkGraph.tsx:208-215` and `:482`.

The network exporter deduplicates on an unordered pair of endpoints, ignoring relationship type, evidence, date, and investigation. It retains the first edge's description/relationship/date, selects the strongest strength, ORs `verified`, and unions profile IDs. As a result, one verified relationship makes a completely different unverified relationship appear verified. The union also makes the first profile's description visible when filtering for the second profile. "Verified only" in the UI does not fix this, because it trusts the merged flag.

**Reproduced on a scratch SQLite DB**, using the actual `export_network()` function (no mocked implementation). Two rows:

- profile-a: A → B, `alleged_payment`, description "Unverified payment allegation", weak, unverified, 2020.
- profile-b: A → B, `co_attendance`, description "Verified conference attendance", strong, verified, 2021.

Output is one edge containing the **unverified payment allegation**, strength **strong**, **verified=true**, date **2020**, and **both profiles**. Fixture and executable assertion: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/probe-network-dedup.py.txt`.

**Fix:** preserve the underlying claim edges and their IDs/provenance; aggregate only the visual geometry, with the complete supporting claims shown on selection. If dedup is retained, identity must at least include relationship/provenance/profile and verification must remain attached to the retained claim. Regression must include same endpoints with different types and profiles, not just duplicate copies of one relationship.

### P1 — `--viz-only` deletes authored narrative

**Locations:** `pipeline/curate_dossier.py:474-515`, especially `:505-508`; misleading CLI contract at `:524`.

The flag is documented as "Only update viz_data, skip curation scaffold." The function constructs a fresh scaffold, and **only** merges preserved narrative fields when `not viz_only`. It then writes that new scaffold to `dossier['curation']` unconditionally. Thus updating a chart removes the lead, sections, system role, open questions, and other preserved narrative fields.

**Reproduced on a scratch JSON file** containing authored `lead` and `sections`. Calling `curate_dossier(..., viz_only=True)` left only `key_finding_ids`, `key_identifiers`, `section_suggestions`, and `curated_at`; the lead/sections were gone. Unrelated data builders were stubbed so this exercised only the curation mutation. Probe: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/probe-web-mutation.py.txt`. Papercut **#2719** recorded.

**Fix:** in viz-only mode leave the entire existing curation object untouched. Default curation should merge derived scaffold fields into existing curation rather than reconstructing it from a narrow allowlist. Test with arbitrary authored keys and nested sections, and verify byte-equivalent curation after viz-only.

### P1 — Publication does not reliably propagate retractions/corrections, and failed gates do not stop CI deploy

**Locations:** `web/src/lib/findingCatalog.ts:174-196`, `:287-302`; `web/src/lib/findingDetail.ts:104-120`; `web/src/pages/dossiers/[slug].astro:107-112`, `:140-143`; `.github/workflows/deploy.yml:26-55`, `:72-79`.

Per-article/per-dossier finding snapshots override the DB catalog (`mergeFindingCatalogs(loadDbFindingCatalog(), contentCatalog)`), and route-local snapshots override that merged catalog again. Stale summaries/statuses therefore win even in a local build with an up-to-date DB. In CI the DB is deliberately unavailable, so the committed snapshots are the only source. All dossier-quality, financial-quality and citation lint gates have `continue-on-error: true`; they may upload a failure report and still deploy.

**Current-tree evidence, read-only DB audit:** 8,561 dossier finding/citation-finding instances representing 8,175 unique finding IDs. There are 321 status differences versus DB and 1,339 summary differences. Of the status differences, **37 instances are retracted in DB but still present as unverified in dossiers**, and **160 say verified in dossiers but unverified in DB**. Example: finding 10490 in `content/dossiers/richard-merkin.json` is unverified in the file and retracted in DB. These are current working-tree facts, not a claim about a deployed remote site. Counts can change as concurrent investigation work continues. Audit script: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/audit-web-state.py.txt`.

`export_dossiers.py` has a useful verified-only export predicate and materializes verified citation findings. The weakness is that running the exporter/sync check is not one deterministic, mandatory release operation. Re-exporting is also insufficient to make an old narrative claim correct merely because its citation record disappears: a retraction needs to invalidate or mark the dependent prose.

**Fix:** produce a versioned publication snapshot with one authoritative finding record per ID, retain finding revision/status metadata, and validate every referenced ID and dependent prose before publication. Make correctness failures blocking; grandfather existing editorial debt with narrow, explicit exceptions instead of bypassing entire gate categories. Treat DB-free builds as consuming a reviewed artifact, and local DB-backed preview as an explicitly different mode, rather than silently combining them. No need to ship a live DB to the static site.

### P1/P2 — The network export has a looser evidence boundary than dossiers

**Locations:** `pipeline/export_network.py:91-131`, `:134-174`, `:177-204`, versus `pipeline/export_dossiers.py:121-131`; `web/src/components/NetworkGraph.tsx:155`.

Dossier exports are verified-only by default. The public network exporter includes every connection whose status is not retracted, collapsing all other statuses (including disputed) to a boolean `verified=false`. It also marks all `entity_roles` and `entity_relations` edges `verified=true` without selecting/checking evidence or verification state. Users see all these edges by default because `verifiedOnly` starts false.

The current `content/network.json` contains **7,070 edges, of which 4,547 have verified=false** and 2,484 have no profile IDs. The frontend intentionally includes unscoped structural edges in every investigation filter, so even an unrelated investigation can show substantial global material. A shared canonical entity table is sensible; it does not establish that every global role belongs in each investigation or that a recorded role has passed evidence review.

**Fix:** define one explicit publication policy shared by all projections. Preserve original verification statuses and claim provenance; only label an edge verified from actual verification evidence. For investigation views include structural edges connected to the selected profile's scoped graph, or label a deliberate global overlay separately. UI defaults must match the intended public/research audience. This is less urgent than the concrete verification transfer above but compounds it.

## Build and contract defects

### P2 — Full export pipeline has broken CLI wiring and cannot report trustworthy success

**Locations:** `pipeline/build_all.py:17`, `:28`, `:40-44`; `pipeline/curate_dossier.py:520-527`, `:550-567`; `pipeline/export_dossiers.py:744-758`.

The parent reviewer identified the wrong subprocess cwd (`PIPELINE_DIR.parent.parent`, one directory above the repo). I independently confirmed another unconditional failure: build_all passes `curate_dossier.py --all --all-profiles`, but the curator parser has no `--all-profiles`. Running that exact child command exited 2 before mutation. Captured output: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/web-curator-cli.log`.

The full pipeline continues after failed prerequisites and writes outputs in place, so it can leave a mixed-generation publication tree before reporting failure. Separately, the curator catches every per-dossier exception, prints it, then finishes with exit code 0; the orchestrator cannot reliably detect failed curation. A profile-scoped bulk dossier export replaces the shared `_index.json` with only that profile (only `--target` uses merging), while older dossier JSON routes remain. This makes source routes, index, and search results capable of disagreeing.

**Fix:** correct CLI contract/cwd, propagate failures, and stage all generated output in one temporary release directory before validating and atomically swapping it into place. Keep authored curation separate from regenerable projections. Add a small orchestrator contract test that inspects actual child `--help`/arguments and failure propagation without exporting real content. Decide whether indexes are global or profile-specific and encode that choice in paths/types.

### P2 — Local deploy and CI deploy build different artifacts

**Locations:** `web/package.json:7`, `:25-26`; `.github/workflows/deploy.yml:69-79`; `pipeline/export_search_index.py:11-12`, `:82-108`; `pipeline/export_preview_index.py:12-13`.

CI refreshes search and preview indexes before building, but `npm run build`, `npm run deploy` and `npm run deploy:preview` do not. Conversely local deploy runs `test:citations:build`, while CI deploy omits it. Current checked-in search index is missing **12 article/dossier IDs** present as source files (including article `softbank-caper`) and retains 2 removed dossier IDs (which may be served by redirects). This is a proven local-artifact mismatch, **not a claim that CI also leaves these indexes stale**.

**Fix:** one build/release entry point that regenerates all browser projections, validates them, builds, and checks the generated artifact; both CI and manual deploy should invoke it. Build tools must accept explicit input/output roots to support safe staging and reproducibility. Validate every search href against generated routes.

### P2 — Strict TypeScript is configured but not enforced

**Locations:** `web/tsconfig.json:2`; no check script in `web/package.json`; `.github/workflows/deploy.yml:57-79`.

`./node_modules/.bin/tsc --noEmit --pretty false` currently reports **7 diagnostics**: `citations.ts:223` and `:3114`, `findingCatalog.ts:99`, and four nullability errors in `supportMode.ts:76`, `:104`, `:121`, `:123`. Detailed output: `/Users/travcole/projects/osint-research/reports/platform-review-2026-09-05/evidence/web-types.log`. The citation suite still passes 621 tests; transpilation/build is not a substitute for checking the declared contract. Plain tsc does not check `.astro` templates, so this is a lower bound on unchecked boundaries. Papercut **#2715** recorded.

**Fix:** establish a reproducible `check` command covering Astro/TS, make it pass, and put it in the same release entry point. Introduce shared runtime schemas at the JSON boundary, rather than scattered `JSON.parse(...) as any` and separate handwritten interfaces in exporters/pages/components. Avoid a whole-app type refactor before fixing the publication defects.

## Focused maintainability and UX improvements

- **Delete an unused identical component:** `web/src/components/EgoNetworkV2.tsx` is byte-for-byte identical to the 749-line `EgoNetwork.tsx` and has no imports anywhere under web/src. This is safe consolidation with a route/build check. `CorporateStructureV2.tsx` and the original share large amounts of code, but V2 is used by `viz-demo` only; choose one production implementation or put the experiment outside the shipped route tree rather than maintaining parallel 1,000-line files.
- **Centralize content metadata:** article frontmatter is parsed ad hoc in `articles/[slug].astro:40-51`, `articles/index.astro:22-34`, `sourceCatalog.ts:38-46`, `export_search_index.py:96-108`, and `export_preview_index.py:76-86`. These are incompatible miniature YAML parsers. Search/preview derive article slug from `cluster`, while routes use the file stem; no mismatch is present in current articles, but changing cluster metadata can create broken search URLs. One schema-aware content loader should own title, route slug, publication status, and metadata.
- **Make first-load search recoverable:** `searchEngine.ts:22-43` caches a rejected initialization Promise permanently and does not check HTTP status. `SearchModal.tsx:29-39` awaits it without catch/finally, leaving loading true on failure. Query calculation depends only on `[query]` (`:72-82`), so text entered while the index loads will not be searched on index completion until the user edits again. Use explicit ready/error state, clear failed Promise, rerun on readiness, and add modal/focus semantics. These are source-path findings; no browser test was run here.
- **Lazy-load visualization families:** `vizHydrator.ts:18-31` statically imports five visualization components and their D3 dependencies; every article includes the hydrator script even if no marker exists (`articles/[slug].astro:166-169`). Dynamic imports selected by `data-viz` and parallel/lazy fetches are a straightforward performance improvement. No bundle-byte estimate or device-performance claim was measured.
- **Tooltip text trust boundary:** `NetworkGraph.tsx:482` interpolates relationship, strength and description into `.html()` without escaping. These fields originate in exported research records. Escape textual fields or build text nodes. Exploitability depends on who can author/import those values; this was code inspection only, not a security audit or exploit reproduction.

## Strengths to preserve

- Astro static generation suits a public read-mostly evidence site and avoids unnecessary backend operations.
- A single citation registry, explicit source records, common evidence pipeline, and centralized script-JSON escaping are useful architectural decisions. The repository has substantial citation regression coverage rather than relying only on screenshots.
- Verified-only dossier export predicates, cross-dossier citation materialization, alias redirects, and evidence details are already present; use these as the basis for a consistent publication boundary instead of rewriting the whole app.
- Financial workbench tests exercise a real user flow; existing support-span tests cover adjacency/orphan behavior and a feature flag permits staged rollout.

## Validation performed and limits

- `npm run test:citations`: **621 passed, 0 failed**.
- `npm run test:citations:snapshots`: passed.
- `npm run test:support-spans`: 4 checks passed.
- TypeScript check: 7 diagnostics, as above.
- Scratch probes: actual network exporter verification/profile corruption; curator viz-only narrative deletion; unsupported build-all curator option.
- Read-only SQLite/content audit: status/summary drift, network status/profile counts, search route drift, exact V2 duplication.

No production export, live site verification, browser E2E, remote source lookup, deployment, full build, or broad security/dependency audit was performed. The current DB and tree are actively changing, so aggregate counts are a snapshot. Nothing here justifies a wholesale rewrite: first fix claim identity/verification, prevent data loss, and make one reviewable publication artifact; then consolidate metadata/loading/types and remove dead UI code.
