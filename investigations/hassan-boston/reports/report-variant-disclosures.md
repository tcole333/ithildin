# Track F supplementary spelling-variant screen — 2026-09-04

A bounded supplement completed **84 source/query combinations** for **14 search-only spellings** across six scopes: local IRS 990 officers, local FAA, local OpenSanctions, local FARA registrants/principals, separate local FARA short forms, and official FEC donor search filtered to Massachusetts. No spelling was promoted to an alias; no new subject finding, entity, or connection was created.

Queries: **Hachim Hassan; Hisham Hassan; Hesham Hassan; Zuhair Hassan; Zouheir Hassan; Abdulrahman Hassan; Abdelrahman Hassan; Abdel Rahman Hassan; Abdur Rahman Hassan; Hossam Hassan; Hussam Hassan; Husam Hassan; Tarik Hassan; Tariq Hassan.** Talal had no requested additional variant in this supplement and retains original Track F coverage.

| Scope | Result |
|---|---|
| FAA active/deregistered local | Zero returned for all 14 spellings |
| FARA registrants/foreign principals | Zero returned for all 14 spellings |
| FARA short-form names | Zero returned for all 14 first-name-variant + Hassan filters |
| IRS990 officer names | Hossam Hassan: one 2023 Masjid Al-Shuhada vice-president row; Tariq Hassan: four 2023/2024 rows at Education for Employment and Petco Love. Other 12 spellings zero. None has a Boston/Tannery/Concepts/Silverstone identity bridge. |
| FEC Schedule A, state MA, no cycle restriction, first 30 | Tariq Hassan: 30 returned candidate rows (query cap reached), with Elevate Services Inc / VP Procurement Services or Vice President and retired employment fields in New Bedford/Randolph. Other 13 spellings zero. No retail/development context; unlinked. The 30 rows are not a lifetime count and are not summed. |
| OpenSanctions, local phrase search, cap 20 | Abdulrahman 3; Abdelrahman 2; Abdel Rahman 2; Tariq 1; other 10 variants zero. These are raw matching rows, with overlap across spelling queries. Inspected contexts concern different full names, an Egyptian actor born 1992, Sudanese banker, Palestinian politician, earlier Iraqi/Nigerian namesakes and an Iraqi full-name mismatch. No attribution to an investigation subject; presence in the multi-topic corpus is not itself sanctions status. |

Local snapshot limits remain: FAA and OpenSanctions February 2026; IRS990 DB March 2026, with the returned tax years 2023/2024; FARA bulk September 2, 2026. FEC was queried live on2026-09-04. All searches succeeded; no access failure was recorded as zero. Local IRS was executed as one bounded batch of the same substring conditions used by officer-search, returning five rows below the 500-row batch cap. This avoids rescanning the large officers table 14 times. FARA short forms were checked directly because the CLI excludes that table (existing papercut #2670).

These are scoped negatives and unlinked candidates, not certifications that the subjects lack registrations, giving or affiliations. No religious affiliation, political identity, income or wealth claim is inferred from name matches. Any later candidate needs an independent business-context bridge.

**Evidence and query ledger:** `investigations/hassan-boston/evidence/disclosures/variants-2026-09-04/`. `variant-query-manifest.csv` contains subject, candidate spelling, actual query, source, filters, snapshot, result-row count, disposition and durable artifact. Raw per-query JSONs and the IRS SQL/parameters are preserved. Scoped `search_log` entries were written for every query. This manifest was sent to the identities agent for incorporation into `name-variants.csv`.
