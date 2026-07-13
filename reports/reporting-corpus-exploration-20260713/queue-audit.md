# Read-only queue audit

## Corpus facts that materially affect ranking

I inspected `docs/modules/reporting.md` Phase 4, the live schema, and the
`add-claim` / `import-claims` implementations without opening the database for
write access.

- Live counts: 7,775 items; 6,763 items have non-empty current full text; 11
  claims across seven items; 1,107 `item_relation` rows, all of them
  `duplicates` relations.
- 5,822 `scope_class='direct'` items have at least 1,200 characters of current
  text. A full-name/transliteration relevance gate reduces that to about 4,757.
- `independence_group` is populated for every item but is **not normally a
  story/rewrite cluster**. There are 251 distinct groups: 238 `outlet:*` groups
  covering 7,661 items and only 13 `content:*` exact-content groups covering 114
  items. Treating every independence group as a cluster would incorrectly
  select only one story from an entire outlet.
- The duplicate detector overwrites the `outlet:*` value with `content:<hash>`
  for exact duplicates. Thus the one column currently conflates source
  independence and exact story duplication. Publisher/domain must remain part
  of the ranking record.
- Exact normalized titles identify 231 duplicate-title items. Only exact body
  copies have relations; rewrites, translations, and syndications are otherwise
  unrecorded (`syndicates`, `rewrites`, and `translates` currently have zero
  rows).
- Volume is sharply skewed: 1,868 items are dated 2025, 3,135 are dated 2026 or
  later, and 742 are undated. The 2026+ bucket alone is 40% of the corpus.
- The full-name-gated substantive pool has only 32 pre-2015 items and 29 from
  2015-2018. These are mostly the genuinely valuable early New York Magazine,
  Vanity Fair, Palm Beach Post, Daily Beast, and early Andrew coverage, so an
  era floor is more appropriate than a modest era bonus.
- `scope_class='direct'` is not a sufficient relevance filter. Pre-2000 NRC
  results include Brian Epstein, Mitch Epstein, and unrelated artists. Require
  `Jeffrey Epstein`, `Ghislaine Maxwell`, or a language-specific full-name
  transliteration in title/body before applying an early-era bonus.
- Long text is not necessarily substantive. AP captures around 78,000
  characters begin with roughly 35,000 characters of menu/navigation before
  the headline. NBC also contains long program transcripts in which the case
  may be a small segment. Saturate the length bonus, locate an article window
  around the headline/byline where possible, and penalize low subject density.
- Outlet concentration is severe: NBC News has 1,444 items, CBS 1,064, and The
  Guardian 1,036. These three publishers are 46% of the entire corpus. A raw
  score will not produce topical or source diversity.
- Source type is also uneven: 2,794 `broadcast`, 1,506 `unknown`, 3,075
  `secondary_quality`, and only 37 `wire_service`. Publisher source type is a
  useful prior, not a verdict. AP/Reuters may be the original within an exact
  syndicated group even though wire copy should receive a lower extraction
  priority overall.
- Historical discovery methods (`import:early_reporting`,
  `import:palm_beach_post_archive`, and the released-reporting seed) are a
  strong curation signal. Conversely, the Miami Herald series is mostly
  metadata-only and must not pass a full-text queue merely because the series is
  important.
- Author-level conflicts must override publisher scoring. Item 1801 would rank
  highly on age/length/outlet, but the Epstein profile flags Landon Thomas Jr.;
  tag it for lineage/context review instead of granting it an ordinary
  investigative-outlet bonus.

The importer is idempotent only within an item: its unique fingerprint is
`(item_id, normalized claim_text)`. It will happily import the same assertion
from twelve rewrites. This makes queue-level story clustering essential.

## Tested SQL prefilter and coarse score

The following shape ran successfully against the live database. It deliberately
uses `content:*` as an exact duplicate key but treats each `outlet:*` item as its
own story candidate. The production script should export the top 600-800 coarse
candidates, then apply the Python features and quotas below.

```sql
WITH raw AS (
  SELECT i.id,i.title,i.published_at,i.language,i.discovery_method,
         i.independence_group,p.name AS publisher,p.domain,p.source_type,
         v.content_text,length(trim(v.content_text)) AS chars,
         lower(coalesce(i.title,'')||char(10)||coalesce(v.content_text,'')) AS txt
  FROM reporting_item i
  JOIN item_version v ON v.id=i.current_version_id
  LEFT JOIN publisher p ON p.id=i.publisher_id
  WHERE i.scope_class='direct'
    AND length(trim(v.content_text)) >= 1200
    AND NOT EXISTS (
      SELECT 1 FROM reporting_claim c WHERE c.item_id=i.id
    )
), eligible AS (
  SELECT *,
    CASE WHEN independence_group LIKE 'content:%' THEN independence_group
         ELSE printf('item:%d',id) END AS exact_cluster,
    CASE WHEN substr(published_at,1,4) GLOB '[12][0-9][0-9][0-9]'
         THEN CAST(substr(published_at,1,4) AS INTEGER) END AS pub_year
  FROM raw
  WHERE txt LIKE '%jeffrey epstein%' OR txt LIKE '%ghislaine maxwell%'
     OR txt LIKE '%جيفري إبستين%' OR txt LIKE '%джеффри эпштейн%'
     OR txt LIKE '%ג''פרי אפשטיין%'
), scored AS (
  SELECT *,
    CASE WHEN chars>=20000 THEN 16 WHEN chars>=10000 THEN 14
         WHEN chars>=6000 THEN 11 WHEN chars>=3500 THEN 8
         WHEN chars>=2000 THEN 5 ELSE 2 END
    + min(28,
        5*(txt LIKE '%according to court records%')
      + 5*(txt LIKE '%court filing%' OR txt LIKE '%court record%'
                                      OR txt LIKE '%court document%')
      + 5*(txt LIKE '%released email%' OR txt LIKE '%released document%'
                                       OR txt LIKE '%released record%')
      + 5*(txt LIKE '%emails show%' OR txt LIKE '%documents show%'
                                  OR txt LIKE '%records show%'
                                  OR txt LIKE '%emails reveal%'
                                  OR txt LIKE '%documents reveal%')
      + 4*(txt LIKE '%obtained by%' OR txt LIKE '%reviewed by%')
      + 3*(txt LIKE '%deposition%') + 3*(txt LIKE '%subpoena%')
      + 2*(txt LIKE '%affidavit%' OR txt LIKE '%exhibit%'
                                 OR txt LIKE '%testimony%'))
    + CASE source_type
        WHEN 'secondary_quality' THEN 7 WHEN 'trade_press' THEN 5
        WHEN 'academic' THEN 5 WHEN 'broadcast' THEN 1
        WHEN 'unknown' THEN -2 WHEN 'wire_service' THEN -10
        WHEN 'secondary_compromised' THEN -8
        WHEN 'secondary_blog' THEN -6 ELSE 0 END
    + CASE WHEN source_type='secondary_quality' AND domain IN (
        'miamiherald.com','palmbeachpost.com','nymag.com','vanityfair.com',
        'thedailybeast.com','theguardian.com','bbc.com','bbc.co.uk',
        'lemonde.fr','spiegel.de','elpais.com','sueddeutsche.de','nrc.nl',
        'oglobo.globo.com','liberation.fr','propublica.org')
      THEN 5 ELSE 0 END
    + CASE WHEN pub_year<2015 THEN 14 WHEN pub_year<2019 THEN 10
           WHEN pub_year=2019 THEN 4 WHEN pub_year BETWEEN 2020 AND 2024 THEN 2
           WHEN pub_year=2025 THEN -3 WHEN pub_year>=2026 THEN -8 ELSE -5 END
    + CASE WHEN discovery_method IN (
        'import:early_reporting','import:palm_beach_post_archive',
        'file:historical_released_reporting',
        'import:historical_released_reporting') THEN 6 ELSE 0 END
    + min(12,
        4*(txt LIKE '%reporters reviewed%' OR txt LIKE '%reporter reviewed%'
                                           OR txt LIKE '%our review%')
      + 4*(txt LIKE '%reporters obtained%' OR txt LIKE '%reporter obtained%'
                                           OR txt LIKE '%interviewed by%')
      + 2*(txt LIKE '%exclusive%' OR txt LIKE '%investigation%'))
    + CASE WHEN lower(title) LIKE '%jeffrey epstein%'
                 OR lower(title) LIKE '%ghislaine maxwell%' THEN 3 ELSE 0 END
    - CASE WHEN chars>20000
                AND txt NOT LIKE '%jeffrey epstein%jeffrey epstein%'
                AND txt NOT LIKE '%ghislaine maxwell%ghislaine maxwell%'
           THEN 8 ELSE 0 END AS coarse_score
  FROM eligible
), leaders AS (
  SELECT *, row_number() OVER (
    PARTITION BY exact_cluster
    ORDER BY
      CASE WHEN exact_cluster LIKE 'content:%'
                 AND domain IN ('apnews.com','reuters.com') THEN 0
           WHEN source_type='secondary_quality' THEN 1
           WHEN source_type='broadcast' THEN 2 ELSE 3 END,
      coarse_score DESC,(published_at IS NULL),published_at,id
  ) AS exact_rank
  FROM scored
)
SELECT * FROM leaders
WHERE exact_rank=1
ORDER BY coarse_score DESC,id
LIMIT 800;
```

The SQL score is intentionally coarse. In Python, score the actual article
window and produce rationale tags with these weights:

| Signal | Weight / cap |
|---|---:|
| Usable prose length (1,200 to 20,000+, saturating) | 2 to 16 |
| Strong document-grounding phrase families | +5 each, cap +20 |
| Formal-record words (`deposition`, `subpoena`, `affidavit`, etc.) | +2/+3 each, total document cap +28 |
| Outlet says its reporters obtained/reviewed/analyzed records or interviewed sources | +4 each, cap +8 |
| `exclusive`, `investigation`, `our review` | +2 each, cap +4 |
| Publisher prior | quality +7; broadcast +1; unknown -2; wire -10; compromised -8; blog -6 |
| Curated investigative outlet | +5, suppressed when author/outlet conflict applies |
| Curated historical ingestion method | +6 |
| Era | pre-2015 +14; 2015-18 +10; 2019 +4; 2020-24 +2; 2025 -3; 2026+ -8; undated -5 |
| Strongest topical signal (title hit counts 3x body hit) | cap +8 |
| Full subject name in title | +3 |
| Low subject density / headline-body mismatch | -8 to -15 |
| Nav/paywall/related-link boilerplate dominates capture | -12 or reject |
| Non-leader exact/title/near-duplicate | reject from first-wave queue |

Use language-specific document dictionaries rather than giving English items an
implicit advantage. At minimum include French (`documents judiciaires`,
`courriels`, `assignation`, `déposition`, `selon`), Spanish (`documentos
judiciales`, `correos`, `citación`, `declaración`, `según`), German
(`Gerichtsakten`, `Unterlagen`, `Vorladung`, `Aussage`, `laut`), Portuguese
(`documentos judiciais`, `depoimento`, `intimação`, `segundo`), and Dutch
(`rechtbankstukken`, `dagvaarding`, `volgens`). A generic `selon`/`según` match
must count less than a specific record phrase.

For boilerplate, derive `analysis_text` by locating a normalized headline/byline
inside the capture and scoring a bounded window around it. Also compute subject
mentions per 10,000 characters, prose-word count, repeated-line ratio, and a
navigation-marker ratio (`Menu`, `SECTIONS`, `Newsletters`, `Sign in`,
`Subscribe`, `Privacy policy`, `All rights reserved`). Never let raw character
count alone elevate an AP shell or broad television transcript.

For unrecorded rewrites, normalize titles with NFKC/casefold/punctuation removal
and remove update/live-blog boilerplate. Cluster exact normalized titles first,
then title token-Jaccard >=0.82 within a seven-day window; optionally require a
shared dominant topic or body-shingle similarity. Select one leader per
provisional story cluster, preferring a publisher-native original/byline, then
the earliest timestamp, then source quality. Keep translations in the same
lineage cluster but retain one translation when it adds a genuinely local source
or angle; it is not independent corroboration.

Suggested rationale tags are `longform`, `court-records`, `released-emails`,
`outlet-obtained`, `investigative-publisher`, `historical-curated`,
`era:pre2015`, `topic:<name>`, `language:<code>`, `exact-dup-leader`,
`near-dup-leader`, `source-conflict`, `wire-penalty`, and
`headline-body-risk`.

## Quota-aware selection for 200 items

Do not merely sort and take 200. Start from the 600-800 scored leaders and use a
greedy deficit bonus while respecting publisher/story caps. Recommended era
targets, which exactly total 200, are:

- pre-2015: 24
- 2015-2018: 16
- 2019: 40
- 2020-2024: 55
- 2025: 35
- 2026+: 25
- undated/manual-date-triage: 5

Recommended non-overlapping primary-topic targets are 32 banks/trusts/USVI, 24
Wexner/Black, 28 Maxwell, 30 political/intelligence, 24 science/philanthropy, 22
properties, and 24 staff/operations (184), followed by the 16 best remaining
cross-topic or unclassified candidates. Assign the primary topic using
title-weighted hits, but retain every matching topic as a rationale tag.

Cross-cutting constraints:

- at least 24 non-English items across at least five languages; no more than ten
  from one non-English language;
- no more than 18 items from one publisher, 50 broadcast items total, or ten
  wire-service items total;
- at least 25 publishers;
- one item per exact/near story cluster in the first pass;
- exclude the seven already-claimed items from bootstrap extraction, then run a
  separate completeness review later.

One workable selector is: at each step choose the remaining item maximizing
`score + 10*era_deficit + 9*topic_deficit + 5*language_deficit -
2*publisher_already_selected`, while rejecting anything that exceeds a hard
cap. Re-run the final 200 through a deterministic swap pass until every feasible
floor is satisfied. Use `score DESC, published_at, item_id` for stable ties.

## Twenty diverse candidate IDs

These are high-signal candidates for the parent queue/pilot review, not claims
and not endorsements of every assertion in the articles.

| Item | Date | Outlet | Primary lane | Why prioritize |
|---:|---|---|---|---|
| 2177 | 2018-03-28 | The Daily Beast | political/network | Long historical synthesis with unusually dense record language |
| 1821 | 2006-08-14 | Palm Beach Post | properties/operations | Early local reporting; long and source-rich |
| 1802 | 2003-03-01 | Vanity Fair | Wexner/business | Foundational pre-criminal-case profile; useful for later contradiction/lineage |
| 2163 | 2010-07-20 | The Daily Beast | justice/operations | Early post-release investigation grounded in legal history |
| 1818 | 2006-07-29 | Palm Beach Post | staff/legal tactics | Early local account citing police/prosecutorial records |
| 7409 | 2020-07-31 | NBC News | Maxwell | Explicitly grounded in unsealed correspondence |
| 1282 | 2020-07-31 | The Guardian | Maxwell | Document-grounded allegations; good cross-outlet lineage comparison |
| 6341 | 2023-07-26 | CBS News | banks/USVI | Specific lawsuit, named executives, and $190 million amount |
| 7278 | 2023-08-19 | NBC News | JPMorgan/network | Narrow, testable referral claim from litigation records |
| 39 | 2025-12-10 | Drop Site News | Wexner/philanthropy | Long original email-based reporting despite recent-era penalty |
| 1514 | 2015-02-01 | The Guardian | philanthropy | Early charity response and institutional ties |
| 7191 | 2019-07-11 | NBC News | philanthropy | Testable claims about exaggerated charitable giving |
| 7471 | 2019-07-12 | NBC News | science/Harvard | Faculty contact after conviction; institutionally specific |
| 6602 | 2019-08-22 | CBS News | science/MIT | Researcher resignations and institutional response |
| 7257 | 2019-07-30 | NBC News | properties | Island expansion tied temporally to the Florida deal |
| 7225 | 2019-10-08 | NBC News | staff/enablers | Named operational actors and roles |
| 405 | 2026-02-19 | The Guardian | political/operations | Long investigative piece based on released records; warrants a recent-era slot |
| 4063 | 2019-08-13 | Libération | French network | Original French-network reporting; multilingual/local-angle value |
| 3780 | 2024-01-04 | El Confidencial | released documents | Spanish longform explanation of unsealed records |
| 4031 | 2019-10-04 | Franceinfo | Brunel/staff network | Detailed French operational-network account |

Item 1801 (the 2002 New York Magazine profile) is also structurally important,
but it should carry an explicit `source-conflict:landon-thomas` penalty and be
handled as narrative-lineage evidence, not ordinary corroboration.

