# Critical deterministic collection guard

Implemented the bounded Q1 closeout after the completion audit identified that the ledger promised a collection guard but CI only relied on ordinary discovery. No full suite, network calls, database writes, or Git mutations were performed.

## Changed paths

- `tests/conftest.py`: adds explicit `--require-critical-tests`. `pytest_collection_finish` checks the final selected node IDs, after all path/marker/keyword deselection. Four stable representative tests cover confidence enforcement, last-evidence deletion, metadata-preserving FK migration, and profile propagation, using the same four modules omitted by the original CI selector. A missing node raises a usage error naming exactly what was omitted. Renaming/removing a sentinel requires an explicit list update. Existing offline/live behavior is unchanged.
- `tests/test_critical_test_collection.py`: five actual pytest subprocess collection regressions. The current `not live_data` selector retains all required nodes; the former `integration and not live_data` expression, a narrowed file list, and a keyword exclusion fail the guard; focused local collection without the flag remains supported. All subprocesses use an explicit temporary DB path, assert it is never created, and execute no test bodies.
- `.github/workflows/tests.yml`: passes the guard flag on the actual deterministic pytest run, preserving the parent's restored push-main trigger and Node 22 setup.

The parent was informed to add the same flag to its owned `scripts/validate_release.py` pytest command for consistent release validation. This subtask did not edit that file.

## Verification

```bash
uv run ruff check tests/conftest.py tests/test_critical_test_collection.py
uv run python -m pytest tests/test_critical_test_collection.py tests/test_offline_network_policy.py --offline -q -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-critical-collection
git diff --check -- tests/conftest.py tests/test_critical_test_collection.py .github/workflows/tests.yml
```

**14 passed in 1.41 seconds**; Ruff and changed-path whitespace check passed. Log: `/tmp/osint-CUTDyZF1/critical-collection-tests.txt`.

The parent froze the full-suite source before these three small edits. The new code path is opt-in; the running frozen suite remains valid for its recorded source, and these focused tests establish the post-freeze guard changes. The audit's Q1 state can become implemented once the parent's full deterministic suite passes and these paths are integrated. This completes the collection-control portion of existing review papercut #2717; it is not a separate undiscovered production issue.
