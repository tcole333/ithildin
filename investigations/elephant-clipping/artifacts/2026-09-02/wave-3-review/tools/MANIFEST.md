# Wave-three budget and tool evidence

Profile: `elephant-clipping`. Collector: `wave3_budget_tools`. Findings: **15447–15449**. Public unauthenticated access only. No account, group join, contact, purchase, private endpoint, ID guessing, generation job, posting action or access-control bypass was used.

## Inert preservation

- `public-evidence.json` — allowlisted capture metadata and SHA-256 values; exact client excerpts with character offsets; a minimized reader-source excerpt; engine acquisition and query-execution caveats; corrected residue inventory of 31 retained files, 30 successful captures and 29 distinct successful JavaScript bodies. One 9-byte `Not Found` error artifact is retained but excluded from substantive coverage. SHA-256: `f7cc79d2eb4510179c3e3574d6ea32b57010ed96b700b29b79706bfceceed5d9`.
- `article-comparison.json` — source hashes, reproducible literal checks and contextual comparison with the complete user-supplied article text; specific feature details are absent from that saved version, while generic AI assistance and publish-then-submit payment workflow were already covered.
- `bhw-reader-response.json` — actual web-reader tool response and acquisition request/time, retained temporarily for independent review. It is not a direct HTTP page capture. Direct GET returned 403; the disclosed exact-post permalink returned a reader cache miss. Use the minimized excerpt in `public-evidence.json` for durable publication.
- `findings.json` and `finding-1.json` through `finding-3.json` — authored finding payloads and tracker receipts, respectively. The database is the authority.
- `collect-searches.py`, `fetch-public.py`, `persist-findings.py`, `preserve.py` — bounded collection/preservation scripts. All pass targeted Ruff checks. Do not rerun merely to regenerate a report: some scripts log searches or persist records.

## Public source chains

The same-day prior `/clipit` page disclosed its build manifest, which referenced shared auto-submit asset `1824-444bfb31f106dbaf.js`. A fresh GET returned the same published asset. Lane A's newer public `/terms` page separately links current build manifest `/_next/static/oT3om4jzC9FhrymKHBqql/_buildManifest.js`; this also references the auto-submit asset and current content-generation route/dependencies. Lane A retains `a/monster-terms-current.html` and `a/monster-build-manifest.js` under the common wave workdir.

The current video route wrapper calls module `82315`; shared asset `2315-13f181a882d3b3ad.js` defines that module. The text-generation wrapper calls `93530`; `1149-dea35cbdcb488261.js` defines it. Both were read as inert text. No client code was executed. Earlier content-generation filenames from the prior build returned 404; only the filenames explicitly disclosed by the fresh public manifest were then fetched.

| Evidence | Captured UTC | HTTP | SHA-256 |
|---|---|---|---|
| [Auto-submit client](https://monsterlab.io/_next/static/chunks/1824-444bfb31f106dbaf.js) | 2026-09-02 19:11:40.781242 | 200 | `b6d7cbaf1fa35a2c1ff5390cce4fe9c8ef93b148a486d0eed0908ae6e1a65fa7` |
| [Video-generation client](https://monsterlab.io/_next/static/chunks/2315-13f181a882d3b3ad.js) | 2026-09-02 19:14:42.808182 | 200 | `98a5622ff6441a0bb9a0ec3bd54978cf79dde942668380b87ec6e6c16a74987e` |
| [Text-generation client](https://monsterlab.io/_next/static/chunks/1149-dea35cbdcb488261.js) | 2026-09-02 19:14:42.436567 | 200 | `ae2586bcfc3e58729b0349a23a5c7a9bf54b384089edfcd86beef5cac435f1a9` |

## Limits and minimization

Raw source bytes stay temporary. Durable review should retain inert excerpts/metadata, not generic framework code, raw session-bearing pages, the full forum page, unrelated forum users, or irrelevant search-result destinations. No payment identifier was obtained. The forum alias is unverified and its claimed payments lack amounts, campaign names and receipts. Software release dates are publisher claims: the relevant entry's displayed date is `May 21`, while the internal ID is `2026-05-21`.

The reviewed code distinguishes generation, shared source storage, reward submission and social publication. A general `Political Clip` feature name is not an observed Elephant campaign, client commission, account-enrollment record or political payout. The exact drafting residue was absent only from the 30 successful selected captures representing 29 distinct JavaScript bodies, not from all public assets or server-side prompts. The remaining retained error file supplies no substantive JavaScript coverage.
