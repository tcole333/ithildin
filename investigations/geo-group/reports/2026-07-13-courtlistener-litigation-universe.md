# GEO Group CourtListener litigation universe

**Lead:** #59487  
**Profile/thread:** `geo-group` / 113  
**As of:** 2026-07-13  
**Scope:** discovery and classification, not merits analysis

## Result

The bounded search universe contained 75 name rows: all 60 guarantor-subsidiary names in GEO's fiscal-2025 SEC Exhibit 22, the parent, primary-supported current/legacy legal-name variants from the 14-UEI DHS map, and the former Wackenhut Corrections parent name supported by the same SEC issuer CIK and the 2003 proposed name-change filing.

After canonicalizing court and docket number, merging division prefixes and judge suffixes, and linking opinion clusters, the inventory contains 1,494 exact-party-supported dockets. Of those, 1,489 are classified as identity-confirmed GEO/current-or-legacy-subsidiary dockets and five remain unresolved same-name-party dockets. This is a docket count, not a count of unique disputes, adjudicated violations, plaintiffs, facilities, or adverse outcomes: appeals, transfers, consolidated matters, and related district proceedings remain separate when their court/docket identifiers differ.

The broader candidate layer contains 4,597 canonical docket/opinion records. It is not a GEO case count. It includes 196 quoted-text/opinion-reference-only records and 2,907 false-positive query hits, chiefly from generic subsidiary names and free-text search behavior. Those rows are retained with explicit flags so future agents can audit exclusions instead of silently losing search coverage.

CourtListener's termination field is populated for 1,312 of the 1,489 identity-confirmed dockets; 177 lack a termination date and are labeled `active` in the machine artifacts only as shorthand for “unterminated in the API.” That label is not a verified current-status finding. Seventeen identity-confirmed canonical dockets link to at least one opinion-search or docket-detail cluster, while 1,087 expose at least one returned RECAP-document identifier or `more_docs` indicator. The inventory links 652 distinct opinion clusters across all identity and reference layers.

## Identity-confirmed category counts

| Category | Dockets |
|---|---:|
| Civil rights | 801 |
| Other / not safely classifiable from metadata | 369 |
| Detention conditions | 148 |
| Employment | 89 |
| Labor / wage / TVPA | 37 |
| Medical / death | 25 |
| Contract / procurement / False Claims | 15 |
| Securities / investor | 5 |
| Antitrust | 0 |
| **Total** | **1,489** |

These categories are metadata-level routing labels based on captions, nature-of-suit/cause fields, and limited search snippets. They do not state what a complaint alleged, what a court held, or whether GEO prevailed.

## Highest-value case files

| Docket | Court / dates | Routing basis | Available-document indicators | Follow-up |
|---|---|---|---:|---|
| `Menocal v. The GEO Group`, 1:14-cv-02887 (#4196461) | D. Colo.; filed 2014-10-22; no API termination date | Labor/TVPA, class-scale record, ICE party, appellate history | 2 clusters / 8 RECAP IDs | Existing full-document lead #59489 |
| `State of Washington v. The GEO Group`, 3:17-cv-05806 (#6167009) | W.D. Wash.; 2017-10-09–2021-11-03 | Government plaintiff and detainee-work/labor classification | 7 clusters / 6 RECAP IDs | Existing full-document lead #59489 |
| `Nwauzor v. The GEO Group`, 3:17-cv-05769 (#6159152) | W.D. Wash.; 2017-09-26–2021-11-02 | Labor/TVPA, related government litigation and appellate chain | 10 clusters / 3 RECAP IDs | Existing full-document lead #59489 |
| `The GEO Group v. Newsom`, 2:24-cv-02924 (#69303316) | E.D. Cal.; 2024-10-22–2025-06-10 | State-statute challenge relevant to detention operations | 2 clusters / 3 RECAP IDs | Related to active state-law track |
| `Mendez v. ICE`, 3:23-cv-00829 (#66846016) | N.D. Cal.; 2023-02-23–2023-05-01 | ICE/GEO party overlap and detention/civil-rights routing | 0 clusters / 3 RECAP IDs | Existing full-document lead #59489 |
| `The GEO Group v. Inslee`, 3:23-cv-05626 (#67606656) | W.D. Wash.; filed 2023-07-13; no API termination date | Active state-statute challenge; related Ninth Circuit docket | 2 clusters / 6 RECAP IDs | New lead #59856 |
| `United States ex rel. Roycroft v. GEO`, 17-3521 (#6086896) | Sixth Cir.; filed 2017-05-18; no API termination date | CourtListener NOS 3375, False Claims Act; origin chain unresolved | 0 clusters / 2 RECAP IDs | New lead #59854 |
| `State of New Jersey v. The GEO Group`, 2:25-cv-12007 (#70610911) | D.N.J.; filed 2025-06-23; no API termination date | Government plaintiff and direct 2025 DHS/ICE relevance | 0 clusters / 3 RECAP IDs | New lead #59858 |
| `Raul Novoa v. The GEO Group`, 5:17-cv-02514 (#6244853) | C.D. Cal.; 2017-12-19–2022-03-31 | Labor/TVPA/class routing | 0 clusters / 5 RECAP IDs | Existing full-document lead #59489 |
| `Hartel v. The GEO Group`, 9:20-cv-81063 (#17329078) | S.D. Fla.; 2020-07-07–2023-11-17 | Securities Exchange Act / investor case | 0 clusters / 8 RECAP IDs | New lead #59852 |

No allegation or merits finding was created from these captions. The new leads require full complaints, opinions, dispositive orders, settlements and related proceedings before factual claims are promoted.

## Search and deduplication controls

- Every Exhibit 22 name received party, quoted RECAP/case and opinion search treatment. Punctuation-only equivalents that compile to the same normalized intent share a query group and are labeled as such; genuinely distinct former/legacy names were searched separately.
- The parent's unsharded party searches reached the 500-result cap. They were superseded by date-sharded party-field searches for both leading-article and no-article parent variants. All party shards were below 500 and their returned `dateFiled` values were checked against the requested bounds.
- The original parent quoted-case shards were invalid because the client did not transmit the verified CourtListener date parameters. Those files were discarded after the client fix (papercut #851). Repaired shards returned 10, 200, 355, 521 across annual 2015–2019 shards, 397, and 483 rows for the six periods; no repaired annual shard reached 500.
- Dockets are keyed first by canonical court plus normalized docket number. This merges forms such as `1:14-cv-02887` and `Civil Action No. 14-cv-02887-JLK`. Distinct appellate and district dockets remain separate. Opinion results are joined by cluster ID and canonical docket key.
- `exact_party_supported`, `quoted_text_only`, `opinion_reference_only`, `identity_confirmed_geo_case`, `false_positive`, and `identity_status` are separate columns in both artifacts. Caption position supplies only an explicitly labeled inferred party role.
- Generic SEC names such as `Community Alternatives`, `Correctional Properties, LLC`, and `SECON, Inc.` are not resolved to GEO merely because CourtListener returned the same spelling. Five exact-party dockets remain in the unresolved same-name bucket.

## Negative alias and source coverage

Forty-four alias rows produced zero exact-party-supported dockets, including many holding/property entities and the exact current names GEO Care Services, LLC, GEO CPM, Inc., GEO Management Services, Inc., and GEO Reentry of Alaska Inc. These are bounded CourtListener search negatives, not proof that the entities were never parties: captions can use parent, facility, trade, predecessor, misspelled or abbreviated names.

FJC Integrated Database coverage failed at the source level. Fourteen exact-name sentinel searches timed out without files; a broad `GEO` starts-with search returned Georgia-prefixed defendants rather than a usable company universe. Papercut #844 records the failure. The remaining aliases were not misreported as zero-result FJC searches. Consequently the artifacts leave structured monetary-demand, amount-received and judgment fields null unless later recovered from a docket document; CourtListener search metadata alone did not provide those fields.

## Durable artifacts

- `investigations/geo-group/reports/2026-07-13-courtlistener-litigation-universe.csv`
- `investigations/geo-group/reports/2026-07-13-courtlistener-litigation-universe.json`
- `investigations/geo-group/reports/2026-07-13-courtlistener-litigation-universe.md`

Primary alias sources were GEO's 2025 SEC Exhibit 22, the normalized 14-UEI DHS map, the active profile, and GEO's SEC 2003 Wackenhut name-change filing. Case metadata and documents are CourtListener/RECAP records. Search discovery was not used as evidence that a pleaded allegation was true.

Audit writes: verified synthesis findings #12617–#12618; new case-analysis leads #59852, #59854, #59856 and #59858. Existing full-document lead #59489 covers the principal detention/labor/medical case family and prevented duplicative commissioning here.
