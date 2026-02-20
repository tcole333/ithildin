# Test Fixtures

This directory holds deterministic integration-test fixtures derived from real local project data.

## Goals

- Keep integration tests realistic by grounding fixtures in real data.
- Keep CI deterministic and fast by trimming fixtures to minimal datasets.
- Track provenance for every fixture update in `manifest.json`.

## Files

- `manifest.json`: provenance + generation metadata.
- `data/check_sync_investigation.db`: trimmed DB for `check_dossier_evidence_sync` tests.
- `data/dossiers/check-sync.json`: dossier fixture paired with the DB above.
- `data/financial_ds10.db`: trimmed DS10 fixture DB with one promoted transaction derived from real data.
- `data/financial_inv.db`: minimal investigation fixture DB with quality schema for financial-quality CLI tests.

## Regeneration

Run from repository root:

```bash
uv run python scripts/build_test_fixtures.py
```

Optional overrides:

```bash
uv run python scripts/build_test_fixtures.py \
  --inv-db /path/to/investigation.db \
  --ds10-db /path/to/lmsband_epstein_files.db \
  --dossier-dir /path/to/content/dossiers \
  --output-dir tests/fixtures/data \
  --manifest tests/fixtures/manifest.json
```

## Rules

- Do not hand-edit fixture `.db` files.
- Regenerate via `scripts/build_test_fixtures.py` and commit both fixture data and `manifest.json`.
- Keep fixture payloads small and deterministic.
