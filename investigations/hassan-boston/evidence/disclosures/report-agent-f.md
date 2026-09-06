# Track F — wider disclosures: bounded first pass

Profile: `hassan-boston`. Research date: 2026-09-04 (UTC). No presumption of political ties or wrongdoing. Searches concern public business/financial records; identities were not joined on name alone.

## Results worth carrying forward

1. **Finding #15501 — Hicham Ali Hassan, Tannery employer in 1992 FEC record.** The official FEC Schedule A API identifies `HASSAN, HICHAM ALI`, Hull, Massachusetts, employer `TANNERY`, receipt date **1992-11-06**, amount **$500**, committee **C00174862**, sub-ID **3061920110003101283**, image **93020012770**. Exact multipart name plus business affiliation supports the match. Source: http://docquery.fec.gov/cgi-bin/fecimg/?93020012770. The name search returned ten API rows across 1992–2002; eight carried Tannery as employer. Some rows share image/date/amount and must not be summed as separate contributions. No lifetime total or influence claim is made. **High, paraphrase.** This is useful as an early dated employer/identity link, not evidence explaining property capital.

2. **Finding #15502 — Houssam Hassan, Developer/Owner, Silverstone Development in 2022 OCPF report.** Original Massachusetts OCPF report **841345** is Andrea Joy Campbell, CPF ID **15931**, July 1–31, 2022, filed August 2, 2022. Page **23** lists a **$300** credit-card receipt from **Hassan, Houssam** on **2022-07-18**, with occupation **Developer/Owner** and employer **Silverstone Development**. Page 24 continues the city. Name and address match official MA PEMBROKE TOWNHOUSE LLC **001037265** (corporate track). Corporate track subsequently verified **SILVERSTONE DEVELOPMENT LLC**, **262859738 / old 000980408**, organized **2008-06-19**, with Houssam Ali Hassan as resident agent, manager and signatory at the same address (**finding #15532, entity #7196**). Occupation/Owner remains a reported declaration; manager/signatory does not quantify equity. Source: https://api.ocpf.us/report/pdf/841345. Original PDF downloaded, text extracted, and page 23 visually verified. **High, paraphrase.** Incidental residential address omitted here and retained only in original evidence for disambiguation.

Entities: The Tannery **#7174**. Business-label row Silverstone Development **#7176** was created before corporate track supplied exact legal entity **#7196**; parent should reconcile these after review. Findings also auto-link their person targets **#7166** and **#7169**.

## Source-by-person coverage

`0` means zero rows for the stated query/snapshot, not a clean or complete record. `U` means unverified namesake candidate, not attributed. FEC is **MA-filtered** (except employer-filtered Tannery follow-up). Exact full names and reduced first/last names were checked in local sources and EDGAR; remote smaller sources used the reduced names listed in coverage artifacts.

| Source | Hicham/Sam | Zouhair | Abdul Rahman | Houssam | Talal | Tarek |
|---|---|---|---|---|---|---|
| EDGAR exact full-name + lookup | 0 full/Hicham; 1 Sam U | 0 | 0 full; 5 reduced-name U | 0 | 0 | 0 full; 2 reduced-name U |
| FEC donor | 10 Hicham rows; matched Tannery; Sam results are Samer | 0 | 0 | 0 | 0 | 30 professor rows U; full Tarek Ali Hassan 0 |
| IRS 990 officer | 0 Hicham; 2 Sam substring candidates U | 0 | 0 | 0 | 0 | 3 medical-name candidates U |
| Senate LDA lobbyist | 0 Hicham | 0 | 0 | 0 | 0 | 0 |
| FARA registrants/principals | 0 | 0 | 0 | 0 | 0 | 0 |
| FARA short forms, direct local audit | no matching surname | 0 | no matching surname | 0 | no matching surname | no matching surname |
| GLEIF | 0 Hicham | 0 | 1 address/name mismatch U | 0 | 1 Virginia company U | 1 address/name mismatch U |
| OpenSanctions local | 0 | 0 | 5 partial-name records excluded | 0 | 0 | 0 |
| FAA local active/deregistered | 0 | 0 | 0 | 0 | 0 | 0 |
| LittleSis | 0 Hicham | 0 | 0 | 0 | 0 | 0 |
| MA OCPF | not systematic | not systematic | not systematic | report 841345 verified | not systematic | not systematic |

### Scope, false matches and boundaries

- **EDGAR:** Full multipart names returned no CIK/public-company/registered-entity matches. Exact reduced-name searches found `Sam Hassan` in a CytoDyn S-3 selling-holder table (2016, accession **0001193125-16-725771**). The filing excerpt lacks contextual identifiers tying the holder to Hicham; **unresolved and unlinked**, not ruled out. `Tarek Hassan` appeared in two Aviceda Therapeutics Form D filings (2024/2025); this points to a medical-company namesake context and was not joined. Abdul Rahman variants occur in fund proxy-voting lists of different full names, including **Yassen Abdul Rahman Hassan Al-Jefry** and **Abdulrahman Hassan Y. Bakheet**. No investment or director finding was created for these candidates.
- **FEC:** Broad Tarek Hassan MA results identify occupations Professor and employers BU/Boston University/University of Chicago, rather than Concepts; excluded pending independent identity evidence. `Sam Hassan` returned **Samer Hassan**, Mass General employer. Tannery-employer follow-up isolates eight Hicham rows. Duplicate source image/date/amount records preserved without summing.
- **990:** The tool uses substring matching: Sam Hassan also matches **Hossam Hassan**, and Tarek Hassan also matches **Tarek Hassanein MD**. A Sam Hassan trustee row for Muslim American Society of New York lacks Boston/Tannery context; not attributed. Tarek rows concern Retina World Congress and medical affiliations; not attributed. **No claim about religious affiliation or charitable activity** was made from these namesake candidates.
- **GLEIF:** Search is broad and can match address text. Abdul result concerns a differently named person in a Dubai address. Tarek result joins a different Tarek business name with “Hassan Bin Ali Street.” Talal result is **EPI Holding LLC**, LEI **254900DAV7OOMVWRPK46**, Virginia registration **S1199225**, C/O Talal Hassan. No Boston or known-business context was established; kept as unlinked candidate.
- **OpenSanctions:** Five reduced Abdul-name hits have materially different full names and Iraqi/Nigerian contexts; no target has been linked to any listing. Snapshot last seen dates are February 2026; this is not current certification.
- **FAA:** Zero name-token matches in the locally ingested February 2026 active and deregistered database. Aircraft under unknown corporate vehicles remain outside this person-name screen.
- **FARA:** CLI searches registrants and foreign principals only, despite broader documented wording. I separately checked all **44,613** short-form rows via bounded read-only name queries. First-name hits had different surnames and were excluded. Local bulk files date September 2, 2026.
- Local DB filesystem dates: FAA and OpenSanctions February 2026; IRS990 March 2026, queried row tax years include 2023/2024. Exact file timestamps/sizes are in `coverage.json`; these are snapshot metadata, not claims of complete underlying coverage.

## Follow-up leads

- **#95838** — Identify the legal vehicle/ownership behind Houssam’s Silverstone Development disclosure. Corporate track’s later #15532 answers legal-vehicle identity; remaining question is ownership/capital/property linkage. Parent should annotate/refine or complete the lead to prevent duplicating Track B.
- **#95840** — Verify **2018 Zappos investment** terms and Concepts recipient vehicle. Hypebeast quotes Tarek Hassan, CEO of Concepts International, about a Zappos relationship and reports investment. This is a useful capital-origin lead, **not a verified investment amount, equity percentage, sale, or property-funding link**. Article: https://hypebeast.com/2018/8/concepts-amazon-zappos-partnership-investment-streetwear-industry. EDGAR phrases “Concepts International” and “The Tannery” produce many unrelated issuers; “Silverstone Development” returns Alterra Healthcare subsidiary-list records, not an established connection. Do not traverse them as target affiliates without legal-entity context.

## Persistence, access and learnings

Durable evidence: `investigations/hassan-boston/evidence/disclosures/`. Key files: `coverage.json`, `persisted-ids.json`, `fec-hicham-1.json`, `fec-tannery.json`, `ocpf-841345.pdf`, `ocpf-841345.txt`, `ocpf-page-23.png`, per-source JSONs/manifests, `fara-shortforms.json`, and four EDGAR candidate excerpts. Scoped search-log records added; substantive findings #15501/#15502 were reread to verify profile, amounts, claim type, confidence and evidence linkage.

Initial sandbox network DNS failures were resolved with approved bounded public-source network access; final remote checks succeeded. No source outage was converted into a zero. OCPF full donor coverage, historical IRS completeness, identity resolution of remaining Sam/Talal candidates, and unknown-vehicle aircraft coverage remain explicit research gaps.

**Important artifact distinction:** Initial `edgar-<person>-1.json` experiments double-quoted names already auto-quoted by the tool, producing separate-word intersections. They are superseded by **`edgar-exact-*`** files and must not be interpreted as person matches. Tool CLI expects plain multiword name arguments and adds phrase quotes itself.

Papercuts logged: **#2670** FARA documented short-form coverage missing from search; **#2672** bundled Poppler emits excessive Fontconfig/cache errors. The PDF render ultimately completed and was visually verified, so this did not block findings. No tool build or unrelated refactor performed. No contact, purchase or headless dispatcher.


## Supplement — spelling variants (2026-09-04)

Completed 84 additional scoped searches of 14 candidate spellings across IRS990, FAA, OpenSanctions, FARA registrants/principals, FARA short forms and MA-filtered FEC. No additional subject identity link or substantive finding; all nonzero candidates remain unlinked. Full methods, counts, exclusions and snapshot limitations: `evidence/disclosures/variants-2026-09-04/report-variant-disclosures.md`; actual-query CSV: `variant-query-manifest.csv` in the same directory. These spellings are search-only, not accepted aliases.
