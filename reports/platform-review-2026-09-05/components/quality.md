# Quality, CI, and runtime review

Scope: current working tree, plus a static comparison against HEAD. Read AGENTS.md and web/AGENTS.md. No production edits, endpoint calls, deployments, or live-data tests. The only intentional live DB writes were required papercut observations #2717, #2722, #2723. Test mutations used temp DBs or in-memory DBs. Existing dirty files were left intact.

## Prioritized findings

### 1. P1 — CI silently skips most of the existing pytest regression suite

Locations: `.github/workflows/tests.yml:22-26`, and nightly selector at line 39. Concrete omitted tests include `tests/test_enforcement.py:25`, `tests/test_finding_evidence_crud.py:425`, `tests/test_lead_tracker_fk_migration.py:89`, and `tests/test_auto_leads_profile_scope.py:50`.

PR CI runs unittest discovery, followed by pytest selecting only `integration and not live_data`. Unittest does not execute pytest functions or pytest classes without unittest.TestCase inheritance. The majority of pytest files have no integration marker. Nightly's `integration or live_data` selector also omits these tests. Therefore changes can regress confidence enforcement, evidence rollback, migration preservation, and profile scope despite a green test workflow.

Verification:
- Ran the four named files with pytest: **107 passed in 4.71s**.
- `unittest.defaultTestLoader.loadTestsFromName` counted **0 tests in each of all four modules**.
- Pytest collection with the CI marker expression: **107 deselected, no tests collected**.
- Conservative static inventory of the committed HEAD: **833 top-level offline pytest functions across 137 files** lack the integration marker. This excludes pytest classes and parameter expansion. Current contents of tracked file paths have 1,252 such functions; whole working tree has 4,212 across 428 files. The underlying defect clearly predates current uncommitted work.
- Existing integration scope itself works: **24 passed, 2 live_data deselected in 0.95s**.

Smallest repair: use pytest as the one runner for deterministic tests (pytest also runs unittest.TestCase cases), exclude explicit live/slow scopes only where needed, retain a separately opted-in live suite. Ensure network tests have explicit markers/gates and add a small CI collection check covering a known critical node. This is wiring existing meaningful tests into CI, not a request to create thousands of tests.

Evidence files: `quality-targeted-tests.txt`, `quality-ci-selection.txt`, `quality-integration-tests.txt`, `quality-test-inventory.json` in the sibling evidence directory. Required papercut: **#2717**.

### 2. P1 — Publication controls are advisory, and deployment proceeds independently of test results

Locations: `.github/workflows/deploy.yml:26-27`, `35-36`, `44-46`, `53-55`, `75-79`; `.github/workflows/tests.yml:3-7`; `scripts/review_dossier_checks.py:902-923`; `.gitignore:23-29`.

Financial quality, dossier review, full citation lint, and changed-file citation lint all explicitly continue on error. The workflow later publishes to production. Deployment and Python tests are separate workflows triggered by the same main push, with no success dependency in this repository. Thus a red quality gate or red Python test workflow does not stop this deployment workflow. Existing passing citation unit tests do not establish that the particular content being deployed passed the disabled content checks.

A clean checkout cannot run the DB-backed checks as intended: investigation.db and datasets are ignored. `check_publish_gate` opens/initializes a local review DB, then labels every curated dossier without a stored review as `never reviewed`. Financial gate opens a missing datasets DB path. Therefore simply deleting `continue-on-error` is insufficient; the validation inputs must first be made available in an appropriate form.

Verification: inspected workflow control flow and DB/default paths; no deployment or production gate invocation was performed. A safe fixture reproduction confirms the financial gate really returns nonzero on its blocking condition (see finding 3). No GitHub branch-protection settings were inspected, so do not assert what they are; the code-level workflow dependency is absent regardless.

Smallest repair: create one release validation path shared by PR and deploy; run static-content checks directly against committed content and bind any offline review/quality export to the content revision/hash being published. Make failures block publishing after baselining existing debt, particularly new/changed content. Run deployment only after the validation job succeeds. Existing old content problems can be explicitly baselined instead of making every new failure advisory forever.

### 3. P2 — Financial parity validation always checks a removed default directory

Locations: `scripts/financial_quality.py:18`, `969-981`; masked by the test override at `tests/test_financial_quality_math.py:157`.

EXPORT_JSON_PATH is still `PROJECT_ROOT / site / content / financials / ds10-flows.json`, while the canonical checked-in file is `content/financials/ds10-flows.json` and site/ no longer exists. The repository's `scripts/check-path-contract.mjs` even forbids tracked files in site/. Consequently the real default `gate --with-math` reports a critical missing-export error regardless of whether the canonical export is sound. Unit tests override the path, and integration gate tests omit --with-math, so they miss this boundary.

Verification: copied committed clean financial fixture DBs under `quality-gate-repro/` and ran `gate --scope publish --strict --with-math --json --inv-db TEMP_INV --ds10-db TEMP_DS10`. It returned **exit 2**, `MATH004_EXPORT_TOTAL_PARITY`, `math_checks_passed: false`; code inspection identifies the nonexistent-path branch. Output: `quality-gate-repro/financial-gate.json`. No production DBs were used.

Smallest repair: change default to canonical content/financials; add an explicit --export-json path so temporary CLI integration tests can exercise the complete gate, plus one default-path contract assertion. Required papercut: **#2723**.

### 4. P2 — Supported CLIs cannot start from the declared runtime

Locations: `tools/offshorealert_search.py:29`, `scripts/backfill_ds09_text_entities.py:25`, dependency list `pyproject.toml:6-23`; documented OffshoreAlert commands at `docs/TOOL_REFERENCE.md:7863`.

The first CLI unconditionally imports cloudscraper and the second imports fitz/PyMuPDF. Neither is declared in pyproject.toml/uv.lock, and neither is available in the current project uv runtime. Both fail before argparse, including --help. That turns a documented command into a runtime repair task for each fresh agent/environment.

Verification: both --help commands reproduced ModuleNotFoundError; no endpoints contacted. Output: `quality-offshore-help.txt`, `quality-backfill-help.txt`.

Smallest repair: declare dependencies in the runtime or small documented optional groups (e.g. document extraction/source-specific tooling), with a clear startup message for unavailable optional capabilities. Add a bounded offline smoke check for advertised CLI startup using each supported dependency group. Do not force every large optional toolkit into every invocation solely to solve two imports. Required papercut: **#2722**.

## Additional improvement, lower priority

Web validation is primarily triggered after main receives a push, not in a PR workflow. `.github/workflows/deploy.yml:3-5` is push-only; `web/package.json` exposes support-span, changed-content, build-citation, and Playwright tests, but CI invokes only citation unit/snapshot tests. Prefer a small PR web validation job exercising the existing focused unit checks and build, and a small deterministic browser smoke path. This is secondary to repairing the omitted Python suite and publication controls; no browser regressions were claimed or tested in this review.

## What is already sound / simplification direction

- There is substantial useful regression coverage: evidence/correction rollback, migration preservation of indexes/triggers/sequences/FTS, profile propagation, and CLI DB override tests assert behavior at meaningful boundaries.
- Copied small SQLite fixtures and tmp_path-based CLI integration tests provide fast deterministic validation without the huge private/live corpora. The current integration subset completes in roughly one second here.
- uv.lock and npm's lockfile already exist. The Python/JS ecosystems do not need replacement or a new build framework.
- The best simplification is one authoritative validation command/workflow, one Python test runner, and explicit deterministic/live boundaries. Preserve good tests; remove duplicated orchestration and disabled promises. No blanket lint cleanup, coverage percentage target, or wholesale dependency reorganization is justified by this review alone.
