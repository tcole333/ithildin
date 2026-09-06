# codex-U report — USPTO trademark search

## Built

- Added `tools/query_trademarks.py`, an unauthenticated wrapper for
  `POST https://tmsearch.uspto.gov/prod-v1-0-0/tmsearch`.
- Added `mark`, `owner`, `serial`, and `goods` subcommands. `mark` defaults to
  exact `match_phrase` matching on `WM`; the USPTO site's broad boosted
  OR-style query is opt-in with `--loose`, and `--include-pseudo` adds an exact
  phrase match on `PM`.
- Added common `--limit`, `--all-pages` (20-page cap), `--live-only` /
  `--dead-only`, `--class`, `--output`, `--json`, and `--from-file` options.
- Preserved every `ownerFullText` entry in parsed and console output, including
  both `(REGISTRANT)` and `(LAST LISTED OWNER)` blocks. Console output also
  includes wordmark, serial, LIVE/DEAD status, filed date, registration number,
  international classes, and truncated goods-and-services text.
- Added one-request-per-second pagination, timeout and 5xx retry/backoff, and a
  clear blocked-response error when HTML is returned instead of JSON.
- Added `tests/test_query_trademarks.py` plus byte-for-byte copies of all three
  supplied fixtures under `tests/fixtures/`.
- Additively documented the tool in `docs/TOOL_REFERENCE.md` and
  `docs/modules/patents.md`, including the distinction between the `patents`
  and `trademarks` registers and source tokens.

No network request was made, and no database was opened, imported, queried, or
modified.

## Offline validation

All validation used the saved `uspto_tm_*.json` fixtures.

- `python3 -m py_compile tools/query_trademarks.py tests/test_query_trademarks.py`
  — passed.
- `.venv/bin/ruff check tools/query_trademarks.py tests/test_query_trademarks.py`
  — passed with no findings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider --basetemp=/tmp/osint-FRmkNLeM/codex-U-pytest tests/test_query_trademarks.py`
  — 7 passed.
- Exercised console parsing for the two-hit wordmark fixture and confirmed that
  both owner-chain lines are printed for serial `85877492`.
- Exercised owner parsing with `--live-only --class 042 --json`; the saved
  nine-hit response filtered cleanly to serials `85877492` and `86255449`.
- Exercised the zero-hit fixture; it printed `0 results.` and exited 0.
- SHA-1 checks confirmed all three test fixture copies exactly match the
  orchestrator-supplied originals.

## Orchestrator live verification

Run these six commands from the repository root:

```bash
WORKDIR=$(mktemp -d /tmp/osint-tm-live-XXXXXXXX)
uv run python tools/query_trademarks.py mark "HC STANDARD" --limit 25 --output "$WORKDIR/mark-exact.json"
uv run python tools/query_trademarks.py mark "HC STANDARD" --loose --limit 5 --output "$WORKDIR/mark-loose.json"
uv run python tools/query_trademarks.py owner "Global Emergency Resources" --limit 2 --all-pages --output "$WORKDIR/owner.json"
uv run python tools/query_trademarks.py serial 85877492 --output "$WORKDIR/serial.json"
uv run python tools/query_trademarks.py goods "asset tracking" --live-only --class 042 --limit 10 --output "$WORKDIR/goods.json"
```

Expected high-value checks: the exact mark query should reproduce the two
`HC STANDARD` records; serial `85877492` should expose both the registrant and
last-listed owner; the owner query should page without duplicate or skipped
records; and the goods query should return only live class `IC 042` records.

## API-shape assumptions to confirm live

1. The endpoint continues to accept unauthenticated JSON POSTs containing raw
   Elasticsearch DSL and a browser-like User-Agent.
2. `WM`, `PM`, `ownerFullText`, and `goodsAndServices` remain searchable with
   the documented `match_phrase` / `match` clauses.
3. Exact serial lookup accepts a `term` query against `id`, whose stored value
   is the trademark serial number.
4. Status filtering accepts a boolean `term` on `alive`, and class filtering
   accepts `match_phrase` on `internationalClass` using values such as
   `IC 042`.
5. Paging continues to use `size` plus `from`, with total hits reported as the
   integer `hits.totalValue`.
6. Records remain under `hits.hits[].source` (not `_source`), and the requested
   source-field names retain the casing documented in the captured contract.
