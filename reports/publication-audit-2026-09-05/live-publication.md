# Live publication inventory — September 5, 2026 (America/New_York)

The live site and frozen local content contain the same nine article slugs and the same 519 advertised dossier slugs. Six dossier entries redirect to other entries, so the site serves **513 distinct dossier content pages**. There are no entirely new article or dossier routes in the frozen local content that are absent live. This is a content inventory, not a release-readiness judgment.

The [live article index](https://ithildin.app/articles/) lists nine published articles and seven planned subjects; the [live dossier index](https://ithildin.app/dossiers/) advertises 519 entries. Direct route GETs ran **2026-09-06 01:18:20–01:19:25 UTC** (September 5, 9:18–9:19 p.m. Eastern), against frozen content captured at **2026-09-06T01:11:55.470934+00:00**, commit `53acdf3eae8fe6a2e8a8ad406c30c1a2e3ade54b`. All **596** route probes completed without transport failures: 528 advertised/local routes, 61 additional alias routes, and seven planned-cluster probes.

## What is live

| Published article | Comparable prose words | Local/live wording |
|---|---:|---|
| [The $30.5 Billion Startup Rewriting Defense](https://ithildin.app/articles/anduril-defense-unicorn/) | 4,661 | Same |
| [The Corporate Shell Network](https://ithildin.app/articles/corporate-shell-network/) | 3,383 | Same |
| [The $20 Million Bag of Copper Dust](https://ithildin.app/articles/crml-copper-powder-fraud/) | 4,581 | Same |
| [DOGE: The Data Operation](https://ithildin.app/articles/doge-data-operation/) | 5,088 | Same |
| [Golden Dome's Black Box](https://ithildin.app/articles/golden-dome-black-box/) | 4,987 | Same |
| [The Gulf Intelligence Web](https://ithildin.app/articles/gulf-intelligence-web/) | 4,499 | Same |
| [The Parallel Diplomatic Corps](https://ithildin.app/articles/parallel-diplomatic-corps/) | 3,218 | Same |
| [The SoftBank Caper](https://ithildin.app/articles/softbank-caper/) | 4,562 | Same |
| [The Thiel Network: From Stanford Review to Pentagon](https://ithildin.app/articles/thiel-network-architecture/) | 4,804 | Same |

Of the 513 distinct dossier pages, **279 contain authored narrative prose** and **234 expose findings/data without authored narrative prose**. Of the narrative pages, 277 match exactly under the documented normalization, one has a substantive local prose addition, and one differs only in citation presentation. All nine article titles and 513 dossier titles match. All 513 dossier section-heading lists and system-role subtitles match; 511 string-valued open-question lists match, while two have the rendering defect below.

## Local changes that are not live

- **[Brad Karp](https://ithildin.app/dossiers/brad-karp/):** the local dossier adds the July 22, 2014 exchange in which Epstein attributed his initial Ruemmler connection to Karp, with the explicit limit that it does not establish the underlying introduction or Karp's knowledge. Frozen local data includes **finding #13338**, which is absent from the live All Findings cards. The other 512 dossier summary/detail multisets match. The local and live counts for Karp are 85 and 84 findings respectively. Whether the addition is editorially approved is outside this comparison.
- **[Steven Pesner](https://ithildin.app/dossiers/steven-pesner/):** strictly normalized text differs because the live page still prints EFTA document IDs inline where the local pipeline emits citation markers. Removing that explicitly recorded source-label pattern yields identical wording. This is a citation-presentation delta, not a new narrative.

There are **no complete local-only MDX articles** and **no new local-only dossier content routes** in the frozen publication directory. This does not inventory drafts in research/report folders or newer database findings; those require the separate editorial and database review.

## Index aliases and visible defects

These six advertised dossier entries are aliases, counted again in the live total:

| Indexed alias | Canonical destination |
|---|---|
| `elizabeth-ross-johnson` | `elizabeth-ross-johnson-trust` |
| `hdi` | `humpty-dumpty-institute` |
| `honeycomb-partners` | `honeycomb-asset-management-lp` |
| `ipi` | `international-peace-institute` |
| `jeffrey-schantz` | `jeffrey-a-schantz` |
| `world-liberty-financial-inc` | `world-liberty-financial` |

All 67 known alias rules resolve successfully. Their static redirect pages use HTTP 200 plus HTML meta refresh, with normal HTTP 308 trailing-slash redirects around them; the inventory preserves every hop instead of calling them independent content pages. Each of the six indexed aliases also has a local dossier JSON file whose own payload is shadowed by its redirect rule; five contain authored prose. Those six payloads were not compared to their canonical destinations and should be reconciled as aliases, rather than counted as six new publication opportunities.

The planned headings are:

- The Apollo Money Pipeline
- Wexner Trust Architecture
- Deutsche Bank Plumbing
- The Legal Shield
- Science & Tech Interface
- Inner Circle Operations
- USVI Operations

Their seven locally mapped cluster article URLs each return **HTTP 200 with the Overview homepage**, not an article. They remain planned. A simple HTTP-success check would falsely report them published.

The [Kirkland & Ellis Foundation](https://ithildin.app/dossiers/kirkland-ellis-foundation/) and [Raafat Alsabbagh](https://ithildin.app/dossiers/raafat-alsabbagh/) sidebars each visibly show five **`[object Object]`** entries under Open Questions. Both local JSON files hold question objects although the page renders a string list. Their question content is not displayed to readers.

## Comparison and limits

Local prose was rendered with the production content pipeline from frozen source, with explicit empty evidence maps and no database reads. Article body and dossier lead/section prose were compared to live HTML. Normalization decodes Cloudflare's public email-obfuscation attributes as the browser does, removes generated citation superscripts/reference blocks, scripts, and visualization placeholders, preserves authored link text and inline adjacency, and applies Unicode NFKC plus whitespace collapse. Case and punctuation remain significant. Email obfuscation accounted for many initial apparent changes and is not treated as an editorial difference.

Finding comparison covers sorted multisets of rendered summary/detail text, retaining duplicate multiplicity. It does **not** certify matching evidence, confidence, verification status, dates, profile ownership, IDs, source URLs, or order. Prose equality does not establish source accuracy, editorial approval, or deployment readiness. Citation target integrity, visualizations, browser interactions, stats, key identifiers, connections, entity roles, timelines, and unindexed unknown routes remain unverified. Exact deployed Git identity must come from deployment records; it is not inferred from body-text equality.

`publication-inventory.json` is the complete 596-route record, including timestamps, HTTP/meta-refresh hops, response hashes, local-file hashes, normalized prose hashes, finding comparison, and comparison limits. `publication-inventory.csv` is the flat review table. Compressed raw HTML and small prose diffs remain only under `/tmp/osint-SUw5NK21/live/`; they should not be mistaken for reviewed publication artifacts. All source/content/database/Git operations in this audit were read-only.
