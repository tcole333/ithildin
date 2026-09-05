# Persistent UCC batch transport — development handoff

Implemented September 4, 2026. **Offline tested; new persistent session live parity is not verified.** The [historical denial](ucc-access-block.json) records Access Denied / Error 15 at 02:42:12 UTC. This development run made **zero live portal requests** and did not launch Chrome. A later normal navigation in the same in-app browser loaded the form without a new debtor query or document request; result and document access remain unverified.

The [current collection status](ucc-collection-status.json) is **paused pending supported bulk access**. The Secretary's [Terms of Use](https://www.sec.state.ma.us/divisions/terms.htm) prohibit automated and manual scraping; slower requests or a reachable form do not resolve that restriction. The planned live parity check and full-roster collection remain deferred pending a supported route. See [access options](access-options.md) and the [unsent inquiry](ucc-access-inquiry-draft.md).

The existing single-request UCC CLI remains available. Its browser helper now also accepts bounded JSONL sessions of 1–50 requests, default 20. One ordinary, isolated headed Chrome is owned by each session. Requests are serialized: Python sends the next only after the previous raw response has been fsynced, parsed by the shared parser, and checkpointed by the runner. Diagnostics use stderr; responses carry request IDs. Individual requests retain the 180-second helper deadline and 210-second outer deadline. EOF, signals and errors close only the owned helper/browser, with bounded fallback.

The form resets party roles and optional name/location/date inputs, checks the actual submitted values, and reuses New Search only within the same archive scope. Current/lapsed changes start from the corresponding previously verified public form URL. Navigation/postback spacing remains at least one second. Existing 25-row pagination, missing-link/replayed-page checks, count/criteria agreement and maximum 500 returned rows remain in place. A larger result set stays partial. Explicit access challenges, including Access Denied / Error 15, are not retried.

`boston_ucc_runner.py` merges saved CUA events before selecting requests, preserving earlier complete observations. It also recovers its own append-only events and raw per-query checkpoints after interruption. A search-log row alone does not certify evidence or completeness. The runner checks the canonical log key before a query; successful parsed results retain normal search logging. The existing `--sync-events` command remains unchanged.

Evidence order and output layout:

1. `raw/<canonical-key-hash>.json` — complete source HTML pages, observed submitted parameters, capture timestamp and correlated response.
2. `results/<canonical-key-hash>.json` — shared parser output and a hash/path reference to the raw checkpoint.
3. `events.jsonl` — one queue event per completed/partial holder observation; updates fsync and atomically replace the journal so interruption cannot leave a partial appended line.
4. Queue JSON and `progress.json` — resumable coverage checkpoints.
5. `needs-review.json` — deferred name/input review cases, never false blocked or no-hit records.

Both `query_input_requires_review` and nonempty `name_mode_review_reasons` trigger deferral. They remain separate fields: the former concerns the proposed form input, while the latter concerns organization-versus-person/partnership/trade-name ambiguity. The local bridge now displays the latter reasons and sorts those requests last. It was not restarted during this offline build. Existing completed organization queries keep their query-level completion and do not become certification of every name mode.

Read-only merge of the saved queue and CUA events at handoff:

- 1,444 holder groups.
- Current: 96 complete; 1,348 pending, comprising 1,315 organization requests and 33 name-mode reviews.
- Lapsed: all 1,444 pending.
- No new live batch results were imported.

Deferred implementation example, **only for a supported access arrangement that expressly permits this collection method**:

```bash
uv run python tools/boston_ucc_runner.py \
  --queue reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-queue.json \
  --output-dir reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-batch \
  --scope current --max-queries 20 --batch-size 20
```

The default event input is the queue's sibling `ucc-cua/events.jsonl`; `--events FILE` overrides it. `--scope lapsed` is a separate run. `--batch-size` controls browser lifetime, while `--max-queries` caps new query attempts. Saved evidence can still be recovered after the new-query budget is reached. `STOP` in the output directory, or `--stop-file FILE`, prevents a subsequent query after any in-flight result is checkpointed.

Validation completed:

- 67 Python offline tests passed across the UCC parser, persistent framing/checkpoint recovery, runner and bridge. The prior localhost integration test was deselected because this follow-up changed only local queue display logic.
- Standalone Node mock tests passed for state reset, same-scope form reuse, archive separation, individual-field clearing, single-attempt challenge rejection and owned-browser cleanup. These do not launch a browser.
- Ruff passed for changed Python files; Node syntax check passed.
- Local dependency-only `runtime-check` completed; this is not a live availability check.
- Raw test proofs and merged coverage summary are under `/tmp/osint-ucc-session-FsLYxqyS/`.

Papercut #2658 records the former per-query Chrome launch cost; the implementation is present but its live parity gate remains deferred pending supported access. Papercut #2661 (separate name-mode flags omitted from queue deferral/display) and #2662 (interrupted event append prevents checkpoint replay) are resolved with regression coverage. No investigation profile was switched and no unrelated findings were created.
