# Ohio statewide navigation helper — evidence manifest

Finalized 2026-09-02 UTC. Navigation support only; zero name queries submitted by this helper. Primary query/results owner: `wave3_payments`. No findings or lead state modified. Report validator passes and all three JSON files parse.

| Artifact | SHA-256 | Preservation note |
|---|---|---|
| `../report-ohio-statewide.md` | `3a941748595bdc539bd51471e51c9706215c32fd5bd5122a19b559acf005dff8` | Validated helper handoff report; does not contain payment agent's later query results |
| `reader-entry-response.json` | `5c90aa0d5440a8aee802b71da5f60635b9051f56fa317ffad173ee4f0d9506c0` | Actual reader output, 2026-09-02 19:37:51 UTC; official entry and portal app shell |
| `form-ax-selected.json` | `ad189ada8797f2a2c030c3002bdb935334b2c839b812b65780eb50ff976400d9` | Actual selected accessibility lines, 2026-09-02T19:43:00.928Z; form fields and limitations, unrelated browser state omitted |
| `navigation-scope.json` | `de4b88c13c88e72a3033b10b745630cf9ccb93ffe5e037b5c94e6781de7c1426` | Authored notes explicitly distinguished from source captures; requested filters were not applied |
| `statewide-form.html` | `2ac49dd52c84f74f98585f15569f3ad52f3f34387282b4117b9e47acc2fdb7ea` | One ordinary HTTP GET returned 403; 1,253,633 bytes; file mtime 2026-09-02T19:41:16Z is timing proxy, not exact request timestamp; temporary barrier body, not substantive evidence |

Source chain: official campaign-finance entry → public data portal → published Expenditures link → rendered Expenditure Search form. The middle portal accessibility output was observed, not separately saved verbatim; the analyst notes do not claim to be that capture. No session-bearing links, incidental user tabs, authentication data or private routes are preserved in the sanitized JSON artifacts.

Native control limitation is open papercut 2630. Do not label the reader shell, direct 403 or zero submitted helper queries as zero matching statewide expenditures. Refer to the primary payment agent's final source-level addendum for actual query results and coverage boundaries.
