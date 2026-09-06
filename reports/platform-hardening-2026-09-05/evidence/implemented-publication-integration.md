# Publication integration fixes

Completed the bounded publication/export integration task. No Git operations,
production exports, live investigations, or publication-policy weakening.

## Diagnosis of the five reported failures

The canonical current publication gate is
`tools/findings_tracker.py::validate_connection_publication`, which validates
both the connection's quoted evidence and any upstream verified finding's full
provenance through `_validate_finding_candidate`. There is no
`pipeline/publication_policy.py` in the current tree.

- `tests/test_publication_exports.py::network_db` lacked `finding_evidence` and
  the upstream finding's claim_type/source_datasets/confidence fields. This was
  an incomplete fixture for the stricter gate, not grounds to permit evidence-
  free upstream findings. Added a synthetic quoted source and valid metadata.
- `tests/test_export_dossiers_verification_scope.py::dossier_db` gave its verified
  upstream finding `source_datasets=NULL`. Replacing this with an explicit valid
  synthetic source token restored connection 11. Its exclusion caused the four
  downstream connection-membership/timestamp/incremental/ego assertions to fail.
- The original assertions were preserved. No broad exception swallowing or
  validator bypass was added to make them pass.

## Actual implementation defect found and fixed

After correcting the fixtures, an expanded second-hop test demonstrated a real
curator bypass: public second-hop edges were selected solely by verified status,
and no requested investigation scope was applied. The test leaked three edges:
one lacking evidence, one with an unverified upstream finding, and one from an
unrelated investigation.

`pipeline/curate_dossier.py` now applies the same canonical connection publication
gate to public second-hop rows and filters by the requested profile. Its source
DB connection is read-only. Research mode keeps non-retracted draft edges, while
retaining the requested profile scope. Explicit all-profile public exports may
include other profiles, but all their public edges still pass evidence checks.

`pipeline/export_dossiers.py` now retains the requested `profile_id` in
`export_options` (null means explicit all profiles), and incremental reuse checks
the full export options. This prevents a same-membership export from silently
reusing a different second-hop scope. Older dossiers fall back to their recorded
contributing `profile_ids` during curation.

## Tests and verification

`uv run pytest -q tests/test_publication_exports.py tests/test_export_dossiers_verification_scope.py tests/test_curate_dossier_resolution.py`

**30 passed.** Added explicit revalidation cases for a verified upstream finding
with missing evidence, missing quote, missing source tokens, or excessive
confidence. The second-hop regression covers missing edge evidence, invalid
upstream verification, cross-profile leakage, research visibility, and explicit
all-profile behavior. Incremental regression checks a changed requested profile.

Ruff passes for all four changed files. Direct
`uv run python pipeline/curate_dossier.py --help` succeeds, checking the standalone
CLI import path after the shared validator import.

Changed files:

- `tests/test_publication_exports.py`
- `tests/test_export_dossiers_verification_scope.py`
- `pipeline/export_dossiers.py`
- `pipeline/curate_dossier.py`

Existing edits in both implementation files were preserved. Root retains
ownership of other frontend/release/integration work.

Papercut #2730 was logged on the reproduced graph bypass and resolved after the
focused tests and lint passed.
