# Public-record catalog parse cache

The repeated parse was reproduced at `tools/seed_public_records_catalog.py::_load_config`, the shared read boundary used by bootstrap, source admission, and catalog auditing. The current tracked catalog has 47,222 lines and 578 sources.

## Change

- Added a four-entry LRU cache around YAML parsing only. The key includes the resolved requested path, exact file contents, and current parser callable.
- Every request still reads the file. Same-size edits with restored mtimes are detected, and removal or read failure cannot return stale cached data.
- Every request deep-copies the parsed value before existing validation and normalization. Nested edits by one caller cannot alter later results. Validation still runs on cache hits.
- Custom paths remain distinct. Replacing the parser in a test changes the cache key. YAML parse errors are not cached.
- No catalog database rows, acquisition decisions, access reviews, source registrations, or network results are cached. No endpoint requests, live database mutations, or Git operations were performed.

## Evidence

Three consecutive calls to `_load_config(DEFAULT_CONFIG_PATH)` in one process, timed with `time.perf_counter`:

| State | Cold load | Second load | Third load |
|---|---:|---:|---:|
| Before | 2.888 s | 1.563 s | 1.560 s |
| After | 1.345 s | 0.0238 s | 0.0233 s |

Warm loads were about 66 times faster in this local comparison. Cold-load timings vary with system activity; this change does not eliminate the first parse or promise an equivalent speedup for an entire suite. Tests that directly call `yaml.safe_load` bypass this boundary.

## Verification

- `uv run ruff check tools/seed_public_records_catalog.py tests/test_public_records_catalog_cache.py` — passed.
- `git diff --check -- tools/seed_public_records_catalog.py tests/test_public_records_catalog_cache.py` — passed.
- `uv run pytest tests/test_public_records_catalog_cache.py tests/test_seed_public_records_catalog.py -q -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-catalog-cache` — **66 passed in 138.68 seconds**.

The eight focused regressions check repeated-parse avoidance, nested caller isolation, same-size/same-mtime edits, custom paths, parser replacement, deletion, parse errors, validation on cache hits, and bounded eviction.

## Files

- `tools/seed_public_records_catalog.py`
- `tests/test_public_records_catalog_cache.py` (new)

## Papercut handoff

For the task owner's log: repeated reads of the large tracked catalog parsed the same YAML on every call (~1.56 seconds per warm read in one process). Reproduce with three `_load_config(DEFAULT_CONFIG_PATH)` calls timed with `perf_counter`; expected unchanged content to avoid redundant parse work while preserving fresh-file and isolated-caller behavior. No live log was written by this bounded subtask, per its explicit no-database-mutations scope.
