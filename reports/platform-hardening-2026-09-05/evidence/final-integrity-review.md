# Final publication and release correctness review

Reviewed the new finding snapshot, candidate export, static finding catalog, release runner, deployment wiring, and the nested citation/source consumers. Initial review was read-only; the task owner subsequently authorized the confirmed fixes below. No production content, canonical investigation database, Git history, or deployed site was changed by this review. Local synthetic probes and tests were used.

## Confirmed defects and disposition

| Defect | Reproduction / impact | Fix and verification |
|---|---|---|
| Candidate output can recursively copy itself | `build_candidate(source / 'candidate', source_content=source, ...)` creates the destination inside the input before `copytree`. The bounded probe recorded `candidate/content/candidate/content` recursion after four calls. | `pipeline/build_all.py:44` rejects equal, ancestor, or descendant overlap with both content inputs using resolved paths before creating output. Dedicated tests exercise both inputs, symlink aliases, preserved bytes, and a valid fresh sibling. |
| Release artifact output can corrupt its own input | `stage_artifact(content, build, build / 'release')` recursively copies its output; `content / 'release'` changes reviewed content after the runner's final comparison. | `scripts/validate_release.py:36` rejects all input/output ancestry overlap before writing. Dedicated tests assert unchanged content/build bytes and no child directory creation. |
| Artifact root symlinks bypass descendant-only checks | Replacing `artifact/site` with a symlink to external matching bytes was accepted by `verify_artifact`. | `scripts/validate_release.py:22,54` now rejects symlinked content/build/site/artifact roots and receipt files. Validation inspects the original content path before resolving it. Malformed receipt top-level shapes also produce controlled validation failures. |
| Optional live DB audit ignores current source confidence policy | Identical exported/snapshot fields with `courtlistener` sources and `high` confidence passed an optional DB audit even when the actual DB row had `dehashed` sources. Its current source cap is `medium`. | Routed to `finding_insert_integration`; that owner added current-row policy validation before normalization. Independent reproduction now fails with `confidence_exceeds_cap`, `scope=database`, and finding ID. Snapshot schema-1 fingerprint remains unchanged. |
| Release lint and built checks use different publication roots | With `ITHILDIN_CONTENT_DIR` set, lint scanned the default corpus (3,580 issues in the probe), while the build checker unconditionally opened two fixed Epstein routes and demanded finding #596. | `web/scripts/lint-citations.mjs` selects the same root. `test-citation-build.mjs` derives all expected article/dossier pages and their citations from the selected input, requires emitted footnotes/source pages/bootstrap, and retains original raw NYDFS/dead VI regressions in synthetic tests. Alternate-root Git changed-file lint now fails explicitly. |
| Source routes import another corpus | `sourceCatalog.ts` hardcoded both default content directories. A selected-root probe loaded 9,929 default source records and unrelated occurrences. These source pages are emitted by Astro independently of article/dossier route selection. | `web/src/lib/sourceCatalog.ts:116,176` uses shared `contentRoot()`. Actual-loader synthetic regression requires selected article and dossier source records and zero unrelated occurrences. Manual source URL/registry metadata remains unchanged. |
| Citation-only findings have no generated source pages | The stronger build check exposed a missing source route linked from Boris Nikolic's dossier. Finding 13236 is among five `citation_findings`; the dossier has zero ordinary `findings`. Source catalog scanned only ordinary findings. | `web/src/lib/sourceCatalog.ts:210` scans both finding arrays. A synthetic citation-only finding now produces its source record and linked finding occurrence. The task owner rebuilt 10,612 pages; the regenerated citation-only source routes passed the stronger checker. |

## Changed paths owned by this review

- `pipeline/build_all.py`
- `scripts/validate_release.py` (also adds the owner's required `--require-critical-tests` pytest flag)
- `tests/test_build_output_boundaries.py`
- `web/src/lib/sourceCatalog.ts`
- `web/scripts/test-source-catalog-selection.mjs`
- `web/scripts/lint-citations.mjs`
- `web/scripts/test-citation-build.mjs`
- `web/scripts/test-publication-checks.mjs`
- `web/package.json` (wires both new JS regressions into `test:frontend`)

Snapshot source changes were made by the separately assigned finding insertion agent, not this review. No commits were made here; the root task owns the coordinated commits.

## Validation

- `uv run pytest --offline -q tests/test_build_output_boundaries.py tests/test_release_validation.py tests/test_publication_exports.py`: **95 passed**.
- Ruff passes for both changed Python implementation files and the new boundary test.
- `node scripts/test-source-catalog-selection.mjs`: selected article/dossier isolation and citation-only evidence checks pass.
- `node scripts/test-publication-checks.mjs`: **19 actual-CLI synthetic gate checks pass**.
- Changed-path `git diff --check` passes.
- Independent recheck of the original DB source-cap drift probe confirms rejection with a database-scoped diagnostic.

## Reproduction artifacts

- `/tmp/osint-CUTDyZF1/final-integrity-probes/snapshot_probe.py` and its isolated metadata content/DB.
- `/tmp/osint-CUTDyZF1/final-integrity-probes/nested_stage_probe.py`; copying was interrupted after four calls to prevent runaway writes.
- `/tmp/osint-CUTDyZF1/final-integrity-probes/source_catalog_probe.mjs` and isolated source-content tree.
- `/tmp/osint-CUTDyZF1/implemented-release-artifact-review.md` contains the delegated gate review, command details, and additional artifact probes.
- `/tmp/osint-CUTDyZF1/release-artifact-review/probes-wzus_ruz` contains selected-lint, fixed-route, nesting, and symlink probes.

## Limits and remaining content review

No full Python suite, full production build, or deployment was run by this reviewer; the root task owns those final checks. The root task completed a fresh 10,612-page build and frontend tests. The new built checker now honors explicit dossier redirects by requiring their declared meta-refresh target and emitted destination, with four dedicated regressions. It then exposed real authored-link debt: the Steven Pesner dossier contains 11 unique literal uppercase `/sources/EFTA...` paths whose canonical generated source routes have lowercase hashed IDs. This is persisted content, not a selected-root or rendering defect; the failure remains intact. Details are in `/tmp/osint-CUTDyZF1/release-artifact-review/missing-built-source-links.json`. Missing semantic review receipts, missing authoritative snapshots, retracted claims, invalid historic evidence, and confidence violations remain real publication/content debt and must not be waived by these code fixes. The snapshot's optional DB audit is explicit; static builds do not silently consult the current DB.

No material deployment-order bypass was confirmed: local and CI deployment consume the validated staged site and verify its receipt before upload. A local hash receipt detects changes; it is not an authenticated signature against a trusted user intentionally rewriting both the receipt and payload. This review did not test hostile concurrent filesystem replacement during a build.
