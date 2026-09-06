# Cross-investigation MuckRock document sweep

**Research date:** 2026-07-15  
**Profiles reviewed:** 28 database profile rows; 25 configured investigations plus the template  
**New targeted searches:** 76 across 23 configured investigations  
**Fresh prior coverage incorporated:** `epstein` and `epstein-gates-ipi`  
**Primary result:** five new, visually reviewed findings imported to `geo-group`

## Result

The repaired MuckRock client is operational. Its focused test set passed (`13 passed, 2 deselected`), and a live search, request-detail retrieval, file download, ZIP extraction, PDF text extraction/OCR, and page rendering all succeeded.

The sweep reviewed every configured investigation against the database's current open-document needs. At sweep start, the database contained 12,383 leads, 13,383 findings, 5,265 entities, and 6,000 logged source searches. The database changed concurrently during the run; its closing counts should therefore be treated as a later snapshot, not as changes attributable solely to this sweep.

The inventory isolated 1,544 actionable leads whose text indicated a document, records, filing, correspondence, contract, inspection, or other source gap. A capped cross-profile ranking of 229 candidates supplied distinctive names, identifiers, organizations, and document classes for the queries. Database-only profile rows `crml`, `new`, and `test` had no corresponding investigation configuration and were inventoried but not treated as live search targets; the `_template` profile was also excluded from searching.

Of the 76 new MuckRock queries, 68 returned no matches. Eight result files were nonempty, representing seven terms because `GEO Group` was fetched both at the normal page limit and in full. Four non-GEO terms were lexical false positives: `Rain AI`, `ISAP V`, `Andrew Tate`, and `Three Rivers`. The genuinely useful clusters were `GEO Group`, `BI Incorporated`, and `immigration detention`.

This is a useful negative result for the other profiles. Distinctive searches covering Allbirds, Sam Altman/Hydrazine/Oklo, Brad Karp/Paul Weiss, Kenny Chesney, the Coscoluella/Grand Wilshire/Towers Financial cluster, the DFJ/Drokova cluster, Feeding Our Future, Joshua Fink/Enso, John Hagee/CUFI, HFIA/3i/BGIN/Liberty Strategic Capital/Tether, the manosphere targets, Ezra and Richard Merkin, Mike Johnson, NGINX/Rambler, Tim Parlatore, Peru-Lockheed, Supermicro, SoftBank principals, tech-right targets, and Paolo Zampolli produced no relevant MuckRock releases in this pass. Exact queries and counts are preserved in `search_log` and `search_history` under source `muckrock`.

## New primary-source findings

### 1. ISAP III specified minute-level on-demand GPS updates

The 998-page ICE production in MuckRock request 20166 contains contract `HSCEDM-14-D-00004`. Its tracking specification permits a `Locate Now` mode with automatic location updates in real time or at least once per minute. In normal mode, it requires coordinate storage at least every three minutes and upload at least every four hours. This establishes the monitoring requirement; it does **not** establish a Palantir or other analytics-platform integration.

- Database finding: `13438` (verified, high-confidence paraphrase)
- Evidence: `MUCKROCK:20166:2015-ICFO-90401:p626`
- Local release: `datasets/muckrock/20166/releases/2015-ICFO-90401.pdf`

### 2. GEO Care Family Case Management guaranteed minimum

MuckRock request 73576 contains GEO Care task-order modification `P00001` to `HSCEDM-16-J-00044` under base contract `HSCEDM-15-D-00008`. It funded Family Case Management Services in the Washington, DC/Baltimore region through December 20, 2016. The pricing page adds a `$21,127.74` Option Year 1 guaranteed-minimum line for heads of household.

- Database finding: `13439` (verified, high-confidence paraphrase)
- Evidence: `MUCKROCK:73576:2019-ICFO-39460:p184` and `p187`
- Local release: `datasets/muckrock/73576/releases/9-14-21 MR73576/2019-ICFO-39460.pdf`

The same production identifies separate Family Case Management Program base/task-order pairs for Los Angeles, New York, Miami, and Chicago. Those identifiers are document leads, not yet separate findings.

### 3. Northwest Detention Center: 2009 TB-control and safety citations

Washington inspection `313393175` recorded four serious and two general violations at GEO's Northwest Detention Center, with `$10,000` in total penalties. The largest item was a `$4,000` citation concerning a missing documented tuberculosis-control program; the citation listed 164 custodial workers as exposed.

- Database finding: `13440` (verified, high-confidence paraphrase)
- Evidence: `MUCKROCK:19138:Inspection-313393175:p6` and `p14`
- Local release: `datasets/muckrock/19138/Inspection_313393175_Enforcement_Case_File.pdf`

### 4. Northwest Detention Center: 2014 sharps and bloodborne-pathogen citations

Washington inspection `316977552` recorded three serious violations and `$7,350` in penalties. The first item listed 200 exposed workers and cited the employer for failing to recognize occupational exposure among employees handling trash bags containing sharp objects. The other items addressed bloodborne-pathogen training and regulated-waste handling.

- Database finding: `13441` (verified, high-confidence paraphrase)
- Evidence: `MUCKROCK:19138:Inspection-316977552:p7` and `p8`
- Local release: `datasets/muckrock/19138/Inspection_316977552_Enforcement_Case_Information.pdf`

### 5. GEO's municipal payment arrangement with Basile, Louisiana

An August 10, 2015 agreement concerning the South Louisiana Correctional Center provided for 25 cents per inmate-day paid to the Town of Basile, a `$24,610.25` retroactive payment, `$75,766` for sewer improvements and repairs, and annual Evangeline Parish School Board scholarships of `$1,000` for each average 100 inmates detained during the year. The response letter includes checks matching the two one-time amounts.

- Database finding: `13442` (verified, high-confidence paraphrase)
- Evidence: `MUCKROCK:68087:Mutual-Cooperation-Agreement:p5`
- Local release: `datasets/muckrock/68087/5-30-19_corres._to_MuckRock_News.pdf`

## Requests acquired or refreshed

The sweep requested downloads for MuckRock requests `2947`, `3204`, `3220`, `12437`, `12557`, `12657`, `12659`, `12827`, `12968`, `19129`, `19134`, `19138`, `19837`, `20166`, `22193`, `36135`, `38021`, `68087`, `72901`, `73576`, `193740`, and `195903`. Twenty-one yielded a local package; request `193740` had no downloadable file.

The most substantial newly extracted productions are:

| Request | Material | Triage result |
|---|---|---|
| `20166` | 998-page ICE/BI Incorporated ISAP III contract production | New GPS-monitoring finding imported |
| `73576` | 435-page ICE/GEO Care and BI contract production | New Family Case Management finding imported; four additional metro contract pairs identified |
| `22193` | 126-page LaSalle/ICE/GEO contract production | Relevant, but overlaps the existing LaSalle contract record |
| `12827` | 24-page ICE/GEO New Jersey contract production | Relevant contract material; no separate novel finding imported in this pass |
| `19138` | Multiple Washington safety-enforcement files | Two new findings imported; no-violation complaint files kept as counterevidence |
| `68087` | Basile response, checks, agreement, and resolution | New local-payment finding imported |
| `38021` | Texas detention sexual-abuse investigation records, including a spreadsheet | Potential follow-up; not yet row-by-row reviewed |
| `72901` | 191-page Stewart healthcare production | Downloaded but encrypted; common request/password variants did not unlock it |
| `195903` | Homan/GEO/Fisher correspondence request | Current release contains only a DOCX administrative communication, not the requested correspondence |

MuckRock requests `150052` and `25844`, already downloaded immediately before this sweep, remain useful to the Epstein profiles and are represented by findings `13372`–`13374` and `13388`–`13393`.

## Controls and limitations

- A MuckRock request description is a lead, not evidence that responsive records exist or that an allegation is true.
- Search terms are not phrase-exact. Token matches generated large false-positive sets for several short or ambiguous names.
- A request marked `done` may contain no released files; request `193740` is one example.
- Multiple files or mirrored requests containing the same agency production are redundancy, not corroboration.
- Only the five findings above received full quote-level and visual page review in this pass. Other downloaded packages remain triaged leads unless separately cited.
- The Stewart production in request `72901` is public but password-protected. Its contents were not used as evidence.

## Database imports

Findings `13438`–`13442` were added to the `geo-group` profile with exact source quotes and canonical MuckRock references, then marked verified by `codex-primary-source-audit`. They use `paraphrase` claim type and `high` confidence; none is presented as a confirmed inference or synthesis.
