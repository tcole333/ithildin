**Review evidence index**

These files preserve the diagnostics used for the 5 September platform review. Production source and authored content were not modified. The SQLite fixtures themselves are intentionally omitted; the diagnostic scripts construct their own synthetic records. The publication audit used the existing database in read-only mode.

| Evidence | What it demonstrates |
|---|---|
| `data-model-output.txt`, `repro-data-model.py.txt` | Stale verification, confirmed inference after correction, stale subject links, alias identity conflict. |
| `data-migrations-output.txt`, `repro-data-migrations.py.txt` | Historical migration loses provenance/disables foreign keys; normal fresh initialization lacks required tables. |
| `orchestration-results.json`, `repro-orchestration.py.txt` | Lost imported evidence, incomplete bundle acceptance, concurrent replay, heartbeat replacement, trigger locking, late completion. |
| `worker-semantics-results.json`, `repro-worker-semantics.py.txt` | Distinct cross-profile lead treated as duplicate; all failed source commands still complete research. |
| `sources-repro-output.txt`, `sources-repro.py.txt` | Registry re-import identity loss, repeated agents, failed search classified as no match, query-scope collision. |
| `profile-switch-repro.json`, `profile-switch-repro.py.txt` | Same process silently changes write profile after another task changes the global default; explicit profile remains stable. |
| `probe-network-dedup.py.txt`, `probe-web-mutation.py.txt` | Scratch reproductions of verification transfer and visualization-only narrative deletion. |
| `web-state-output.txt`, `audit-web-state.py.txt` | Read-only snapshot of local publication drift; not a live-site audit. |
| `quality-targeted-tests.txt`, `quality-ci-selection.txt`, `quality-integration-tests.txt`, `quality-test-inventory.json` | Existing tests pass locally but are omitted by configured CI selection. |
| `financial-gate.json`, `quality-*-help.txt` | Obsolete financial default path and undeclared CLI dependencies. |
| `web-citations.log`, `web-snapshots.log`, `web-support.log`, `web-types.log`, `web-curator-cli.log` | Passing focused tests, seven TS diagnostics, unsupported pipeline argument. |
| `workflow-repros.json`, `check-workflow-contracts.py.txt` | Unsupported synthetic claims pass structural review, old searches are treated as reusable, date backfill leaves normalized fields empty. |
| `skill-snapshot.json`, `workflow-adjudication.md` | Structural skill audit and independent adjudication of methodological recommendations. |
| `code-inventory.json`, `source-metrics.py.txt` | Size/concentration measurements and source contract duplication. |

The `.py.txt` files are unchanged diagnostic script snapshots, not installed regression tests. Some contain their original absolute scratch directory (`/tmp/osint-SXYkyRSJ`) and fixture setup assumes a clean directory. Before replay, copy the desired script into a fresh work directory, update scratch paths, and inspect the setup; run from the repository root with `PYTHONPATH="$PWD" uv run python "$WORKDIR/script.py"`. The source and profile probes use temporary/in-memory fixtures; do not point any mutation probe at production databases. This note describes replay requirements, not an approval requirement.

Expected outputs currently demonstrate defects. Remediation should translate the relevant cases into maintained tests asserting the corrected behavior, rather than adding these one-off scripts verbatim to the test suite.

The parent independently replayed the source and core-data probes and repeated the publication audit. Other component results were reviewed against their scripts and code paths. All local counts can change as the shared working tree and database evolve. `../manifest.json` records retained artifact hashes and the reviewed HEAD; the review explicitly includes uncommitted work.
