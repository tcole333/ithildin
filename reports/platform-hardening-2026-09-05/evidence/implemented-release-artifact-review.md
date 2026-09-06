# Release artifact boundary review and selected-content gate fix

Owned source changes (no commits made):

- `web/scripts/lint-citations.mjs`
- `web/scripts/test-citation-build.mjs`
- `web/scripts/test-publication-checks.mjs` (new)

The parent owns package.json wiring for `node scripts/test-publication-checks.mjs` in `test:frontend`.

## Confirmed defects fixed

1. Citation lint ignored `ITHILDIN_CONTENT_DIR` and scanned the checkout's articles/dossiers even when the release runner built a separate selected publication. The selected finding catalog was already loaded, producing a mixed-root check. A probe containing only `release-probe-selected-only.mdx` instead returned 3,580 issues from checkout content and omitted the selected file. Lint now reads the selected root. Git changed-file filtering explicitly rejects alternate roots because Git cannot describe those paths; full selected-publication lint remains available.
2. Built citation checks required two fixed production routes (`corporate-shell-network` and `southern-financial-llc`) and finding #596 regardless of selected content. A different valid publication failed with ENOENT. The checker now enumerates selected article and dossier routes and requires all their generated pages. It checks ordinary cited findings against emitted anchors, footnote targets, source-record destinations, and required evidence bootstrap features. The former NYDFS raw-token and VI dead-anchor regressions remain covered by arbitrary-slug synthetic fixtures. Missing selected input or missing build index fails explicitly.

## Verification

- `cd web && node scripts/test-publication-checks.mjs`: **19 checks pass**. Exercises the actual CLI scripts against isolated synthetic input and built trees: alternate slugs, missing content/build/page, removed citation, raw NYDFS token, dead VI anchor, missing footnote/source/bootstrap, malformed bootstrap, selected-root lint failure/success and incompatible changed-file mode. Intentional dossier redirects are checked against their selected metadata and built targets, including old JSON whose prose no longer renders, aliases without JSON, missing targets, and wrong targets.
- `node --check` passes for all three owned scripts.
- `git diff --check` passes for owned paths.
- Test output: `/tmp/osint-CUTDyZF1/release-artifact-review/publication-check-tests.txt`.
- No full Python suite or production build was run in this review.

## Final build check and authored-link debt

After the parent fixed sourceCatalog's selected root and citation_findings handling and completed a fresh 10,612-page build, the Boris Nikolic missing source-page defect no longer appears. The checker honors intentional dossier redirects from `_redirects.json` (including `hdi`) by verifying the exact built meta-refresh target and target-page existence rather than requiring obsolete old prose anchors.

The final standalone check now fails on `/sources/EFTA02450801` in `dossiers/steven-pesner`. Source JSON contains literal uppercase EFTA hrefs; the canonical built page is `/sources/efta02450801-h94gpy`. An independent read-only scan found **11 unique missing source paths, all confined to steven-pesner**, each from an authored literal uppercase EFTA href. This is existing authored-link debt, not a root-selection or redirect false positive. No publication content was changed and no check was weakened to excuse dead targets.

Outputs:
- `/tmp/osint-CUTDyZF1/release-artifact-review/build-check-current.txt`
- `/tmp/osint-CUTDyZF1/release-artifact-review/missing-built-source-links.json`

## Additional confirmed artifact path defects handed to parent

`stage_artifact` in `scripts/validate_release.py` checked equality of output/input roots but not ancestry:

- `stage_artifact(content, build, content / 'release')` succeeds and mutates publication content after the release runner's unchanged-content check.
- `stage_artifact(content, build, build / 'release')` recursively copies its own destination. A bounded isolated probe with recursion limit 100 raises `RecursionError`; ordinary execution continues copying nested `release/site` paths until a filesystem/recursion limit is hit.
- `verify_artifact` accepts an artifact whose `site` directory is replaced by a symlink to external matching files; `file_manifest` checks descendants but misses the root symlink.

Probes and diagnostic outputs are retained under `/tmp/osint-CUTDyZF1/release-artifact-review/probes-wzus_ruz`. These source fixes are explicitly outside my current ownership and were routed to the parent.

No material deployment ordering bypass was found in `.github/workflows/deploy.yml` or `web/scripts/deploy-validated.mjs`: both consume the staged site and run receipt verification before upload, and CI deployment depends on validation. An editable local hash receipt is an integrity check, not an authenticated signature; this review did not treat a trusted user's intentional replacement of both payload and receipt as a defect.
