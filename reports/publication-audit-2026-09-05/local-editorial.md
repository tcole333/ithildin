# Local editorial inventory — 2026-09-05 Eastern time

Frozen content/database cutoff: **2026-09-06T01:11:55.470934+00:00**. This is a complete file/metadata/structural inventory of 519 dossier JSON files and 9 article MDX files. It is not a claim-by-claim semantic review, and it makes no assertion about which exact versions are live. The live-route audit supplies that comparison.

## What is actually written

| Material | Count | Meaning |
|---|---:|---|
| Dossier narrative in normal fields | 280 | Lead and substantive section prose present; completion is mechanical, not editorial approval |
| Dossier narrative partly in ignored fields | 1 | Kurt Olsen has four authored sections the renderer omits |
| Dossier narrative entirely in ignored section fields | 2 | Musk Entities and Ronald Lauder have authored section bodies but only the lead renders normally |
| Dossier lead and empty section stubs | 1 | Nan Morabia |
| Data-only dossier page | 235 | Findings/connections exist but no curated lead; these are research reference pages, not completed narrative dossiers |
| Full article draft present | 9 | Each has YAML frontmatter and 3,331–5,307 body words; existing route presence does not establish current editorial approval |

**283 dossiers have authored narratives; 284 have a curated lead.** The three schema mismatches omit 15 sections totaling approximately 4,311 words. No additional current article MDX draft was found outside content in the tracked file inventory or the research/reports/investigations scan. An Apollo article was deliberately deleted in commit `75b34daa5b67d4f52152b972177b5f03c0766460` on 2026-02-20; old screenshots and Git blobs should not count as a current undeployed finished article.

## Publication review debt

**No exact-content semantic PASS receipt exists.** `content/dossier-review-receipts.json` is absent. Historical database records contain 31 LLM reviews across 25 distinct slugs, but those rows have no content hashes and cannot approve today's content. No receipt was fabricated or persisted during this inventory.

Static checks across all 519 dossiers returned **219 FAIL, 53 NEEDS_FIXES, 12 PASS, 235 SKIP**. SKIP is the uncurated/data-only population. Static issues include 5,132 citation blocking occurrences and 18 structure blocking occurrences. PASS only establishes these automated checks.

The content snapshot validator found **32,445 issue occurrences**, including 10,134 missing source quotes, 8,162 nonverified finding records, 5,207 invalid source-dataset encodings, 2,664 evidence-type mismatches, 3,791 references to unpublishable findings, and 193 missing cited-finding references. These are repeated occurrences across exports and references, **not 32,445 distinct findings**. Only 116 unique exported finding IDs pass the portable evidence checks. The separate missing `finding-catalog.json` snapshot adds one release issue, explaining the earlier total of 32,446. No release artifact was generated.

The `release_ready: false` field in the inventories means the current whole-site release cannot pass. It does not mean that each page has an individually proved semantic failure. In particular, articles that cite documents directly can have zero Finding-ID snapshot issues while still requiring claim review.

| Article | Words | Unique Finding IDs | DB status of those IDs | Finding IDs with absent/incomplete quotes |
|---|---:|---:|---|---:|
| The $30.5 Billion Startup Rewriting Defense (`anduril-defense-unicorn`) | 4,896 | 64 | 51 unverified, 13 verified | 63 |
| The Corporate Shell Network (`corporate-shell-network`) | 3,547 | 23 | 22 unverified, 1 verified | 17 |
| The $20 Million Bag of Copper Dust (`crml-copper-powder-fraud`) | 4,801 | 62 | 62 unverified | 58 |
| DOGE: The Data Operation (`doge-data-operation`) | 5,307 | 60 | 60 unverified | 60 |
| Golden Dome's Black Box (`golden-dome-black-box`) | 5,224 | 61 | 50 unverified, 11 verified | 61 |
| The Gulf Intelligence Web (`gulf-intelligence-web`) | 4,579 | 0 | Uses direct-source citations | 0 |
| The Parallel Diplomatic Corps (`parallel-diplomatic-corps`) | 3,331 | 11 | 11 unverified | 2 |
| The SoftBank Caper (`softbank-caper`) | 4,611 | 0 | Uses direct-source citations | 0 |
| The Thiel Network: From Stanford Review to Pentagon (`thiel-network-architecture`) | 4,984 | 56 | 49 unverified, 7 verified | 56 |

All explicitly named Finding IDs in the nine article bodies exist in the frozen database. This is an identity/existence check, not proof that they support the attached claims. Gulf Intelligence Web and SoftBank Caper cite primary documents/URLs directly and contain no Finding-ID citations; their zeroes are not missing-citation findings. Citation-format counts are recorded separately in JSON and do not measure independent source families.

The 12 static PASS dossiers are: Boris Nikolic, Brad Karp, Carlos Ghosn, Ian Osborne, Immigration Enforcement Industry, Leon Black, Michael Wolff, Mortimer Zuckerman, Paul Weiss, Rajeev Misra, Robert Kraft, SoftBank Group. They are a manageable queue for actual exact-version semantic review, rather than permission to bypass it.

## Concrete content defects

1. **Unrendered authored prose.** Musk Entities uses `prose` for five sections (1,937 words); Ronald Lauder uses `body` for six (1,474 words); Kurt Olsen uses `prose` for four (900 words). `web/src/lib/contentEvidencePipeline.ts:161` reads only `section.content`. `scripts/review_dossier_checks.py:376` checks that the section array exists but its per-section loop at line 395 does not reject empty/missing content. These fields need deliberate normalization and claim review; a schema check should prevent recurrence.
2. **Nan Morabia is unfinished.** Seven sections exist only as empty body stubs. Its long lead is not a completed dossier. The current static check does not flag the empty section bodies.
3. **Exports are mostly old.** 490 dossiers have May 2026 `generated_at`, 11 June, 9 July, 4 March, and 5 lack this field. Those dates describe exported data, not trustworthy last-edit dates of authored prose. Research added since those exports will not automatically appear in local or live dossiers.

## Article backlog and duplicate scope

| Cluster | Inventory status | Main cluster finding IDs | Split export finding IDs |
|---|---|---:|---:|
| The Apollo Money Pipeline (`apollo-money-pipeline`) | planned_visible_on_article_index | 1,000 | 604 |
| Wexner Trust Architecture (`wexner-trust-architecture`) | planned_visible_on_article_index | 533 | 356 |
| Deutsche Bank Plumbing (`deutsche-bank-plumbing`) | planned_visible_on_article_index | 1,084 | 694 |
| The Gulf Intelligence Web (`gulf-intelligence-web`) | article_exists | 448 | 0 |
| Shadow Lobbying Empire (`shadow-lobbying-empire`) | backend_cluster_only | 1,113 | 375 |
| The Corporate Shell Network (`corporate-shell-network`) | article_exists | 2,980 | 1,002 |
| The Legal Shield (`legal-shield`) | planned_visible_on_article_index | 1,290 | 498 |
| Science & Tech Interface (`science-tech-interface`) | planned_visible_on_article_index | 1,641 | 462 |
| The Norwegian Connection (`norwegian-connection`) | backend_cluster_only | 264 | 224 |
| Inner Circle Operations (`inner-circle-operations`) | planned_visible_on_article_index | 801 | 662 |
| USVI Operations (`usvi-operations`) | planned_visible_on_article_index | 595 | 509 |
| The Thiel Network (`thiel-network-architecture`) | article_exists | 998 | 0 |
| Anduril: Rewriting Defense (`anduril-defense-unicorn`) | article_exists | 648 | 0 |
| The Political Influence Machine (`political-influence-machine`) | backend_cluster_only | 1,802 | 532 |
| Golden Dome's Black Box (`golden-dome-black-box`) | article_exists | 2,159 | 0 |
| DOGE: The Data Operation (`doge-data-operation`) | article_exists | 1,535 | 0 |
| The SoftBank Caper (`softbank-caper`) | article_exists | 928 | 928 |
| The Parallel Diplomatic Corps (`parallel-diplomatic-corps`) | article_exists | 2,892 | 0 |

The 18-cluster backend catalog covers eight existing articles and ten unwritten plans. The ninth article, CRML Copper Powder, has no matching seed cluster. Seven plans are displayed by the article index: Apollo Money Pipeline, Wexner Trust Architecture, Deutsche Bank Plumbing, Legal Shield, Science & Tech Interface, Inner Circle Operations, and USVI Operations.

**The three backend-only unwritten clusters are wholly subsumed by Finding-ID membership in Parallel Diplomatic Corps:** Norwegian Connection (264/264), Shadow Lobbying Empire (1,113/1,113), and Political Influence Machine (1,802/1,802). That does not prove the published prose covers every fact, but it is strong reason to develop a specific new mechanism or update the existing article before commissioning three overlapping narratives. Science & Tech also overlaps 61.9% of Thiel Network's IDs. Anduril overlaps 82.1% of its IDs with Golden Dome.

Where split `cluster-*.json` exports exist, they usually contain smaller subsets than `clusters.json`; SoftBank is the sole identical set. For example Apollo is 604 versus 1,000 findings, Legal Shield 498 versus 1,290, Science & Tech 462 versus 1,641. An absent split file is recorded as zero in the table, not an empty investigation. Cluster keyword membership is a broad retrieval pool and **not an evidence-ready article score**. The selector in `pipeline/story_clustering.py` and hard-coded planned list in `web/src/pages/articles/index.astro` are separate catalogs.

## Authored research outside website content

A separate metadata scan indexed 769 Markdown/MDX documents under `research/`, `reports/`, and `investigations/` with path, heading, word count, SHA-256 and observation time. This scan is outside the frozen content backup; concurrent research additions may postdate the content cutoff. It is not a semantic completion review of all 769 files.

| Artifact | Classification | Publication implication |
|---|---|---|
| `investigations/elephant-clipping/reports/2026-09-02-matiss-tabuns-dossier.md` | Substantive internal consolidated research dossier | Not a site JSON dossier. It explicitly leaves the civil-identity/persona bridge circumstantial; needs public-interest framing, incidental personal-data minimization, neutral prose and full claim review before adaptation |
| `investigations/epstein-oslo/reports/wp10-witness-dossiers.md` | Interview-preparation packet | Not public dossiers or a finished article; clearly says no outreach authorized and retires its original Epstein/1992–93 hypothesis |
| `reports/epstein-draft-candidates-20260714/review.md` | Source-document draft detection queue | “Draft” means archival draft emails, not draft articles. Not 2,094 unpublished stories |
| Three `reports/boston-liquor-license-collateral-2026-09-03/full-review/*-inquiry-draft.md` files | Agency inquiry drafts | Correspondence preparations, not articles; no sending is authorized here |
| `reports/top-10-newsworthy-candidates-20260711.md` | Earlier commissioning shortlist | Historical readiness/novelty judgments require fresh verification; use to avoid redundant commissioning, not as current publishing approval |

## Reproducibility and boundaries

- `inventory.json` / `inventory.csv`: every dossier and article, provenance hashes, writing state, finding/citation counts, database citation status, structural results, publication issue totals and review-record status.
- `dossier-static-checks.json`: exact automated findings; not semantic verdicts.
- `clusters.json` / `clusters.csv` and `cluster-overlap.json`: backend/planned/current article reconciliation and overlap.
- `unrendered-prose.json`: each affected section and word count.
- `research-document-index.json` / `.csv`: outside-content metadata scan with separate observation time.
- `publication-issues.json`: full 7.5 MB diagnostics; keep as local audit evidence rather than committing an oversized repeated-error dump. Per-page and aggregate counts are already in the compact inventory.
- `inventory.py` and `supplement.py`: reproduction scripts. Pure `run_checks(..., static_only=True)` avoids the check CLI's review-table writes. SQLite was opened with `mode=ro` against the frozen backup. No database, content, receipts, profile settings or Git state was changed.

Assumptions: dossier routes derive from JSON filenames; narrative bodies render from `curation.lead` and `curation.sections[].content`; article routes/metadata use `pipeline.article_metadata.load_article`; findings link through `finding_evidence.finding_id`; historical `dossier_llm_reviews` contains issue counts and timestamps, with neither a verdict nor a content hash. Citation-source-format counts are mechanical and may undercount compound tokens, so they are not evidence-independence assessments.
