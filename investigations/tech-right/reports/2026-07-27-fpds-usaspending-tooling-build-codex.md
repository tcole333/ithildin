# codex-R Wave 3 report — FPDS ATOM + USAspending transaction keywords

## CONFIRMED — built

- Added `tools/query_fpds.py` with:
  - `piid <PIID>` exact-PIID search and `search <query>` raw-query search.
  - `--from-file`, `--max-pages` (default 10), `--output`, and `--json`.
  - Structured extraction of action identifiers, dates, action and total
    values, vendor/UEI, NAICS/PSC, description, and the FPDS workflow fields
    `createdBy`, `lastModifiedBy`, and `approvedBy` (plus their timestamps).
  - ATOM `rel=next` paging, one-second inter-page delay, a repeated-link guard,
    retry/backoff for 5xx and timeout failures, and explicit rejection of HTML
    block pages.
  - Namespace handling that uses an explicit Atom/FPDS namespace map while
    matching FPDS field local names, so `ns1`/`ns2` prefix changes do not affect
    extraction.
- Extended `tools/query_usaspending.py` additively with
  `transactions-keyword <keyword>`:
  - `--start`, `--end`, `--naics`, `--psc`, `--agency`, `--limit`,
    `--all-pages`, `--from-file`, `--output`, and `--json`.
  - Contract-only transaction search (`A/B/C/D`) sorted by action date
    ascending.
  - `page_metadata.hasNext` pagination with a 50-page safety cap.
  - Exact-dollar console rendering with Action Date, Award ID, Recipient,
    Amount, Mod, and a 120-character transaction description.
- Added offline coverage in `tests/test_query_fpds.py` and
  `tests/test_query_usaspending.py`.
- Copied both orchestrator responses to `tests/fixtures/`. SHA-256 comparison
  confirmed that each test fixture is byte-for-byte identical to its source in
  `/tmp/osint-FRmkNLeM/fixtures/`.

## CONFIRMED — fixture results

- FPDS fixture `fpds_atom_70CDCR26FR0000014.xml` parses as two actions:
  modification `0` and `P00001`.
- The base action has `createdBy == lastModifiedBy == approvedBy ==
  JABYAD7012`, action obligation `$348,000.00`, and signed date `2025-12-16`.
- `P00001` has a `$0.00` action obligation, `createdBy=JBOUDREAUX7012`, and
  `lastModifiedBy=approvedBy=SWRAY7012`.
- USAspending fixture `usaspending_txn_skiptracing.json` renders and exports all
  82 transactions. The offline console check includes
  `70CDCR24FR0000006 / P00011 / $7,372,680.00` on `2025-10-09`.

## CONFIRMED — offline validation

Commands run:

```bash
python3 -m py_compile tools/query_fpds.py tools/query_usaspending.py \
  tests/test_query_fpds.py tests/test_query_usaspending.py

.venv/bin/python -m pytest -q \
  tests/test_query_fpds.py \
  tests/test_query_usaspending.py \
  tests/test_query_usaspending_subawards.py
# 12 passed in 0.15s

.venv/bin/ruff check \
  tools/query_fpds.py tests/test_query_fpds.py tests/test_query_usaspending.py
# All checks passed

python3 tools/query_fpds.py piid 70CDCR26FR0000014 \
  --from-file tests/fixtures/fpds_atom_70CDCR26FR0000014.xml \
  --output /tmp/fpds-offline.json

python3 tools/query_usaspending.py transactions-keyword "skip tracing" \
  --from-file tests/fixtures/usaspending_txn_skiptracing.json \
  --output /tmp/usaspending-transactions-offline.json
```

The whole pre-existing `tools/query_usaspending.py` is not currently
Ruff-clean: Ruff reports seven unchanged legacy findings (`F401`, `E701`,
`F841`, and `F541`) outside this additive change. Running Ruff with those four
pre-existing rule codes ignored reports no other findings. I did not reformat
or alter legacy code because the assignment explicitly required an additive
change only.

## Live verification commands for the orchestrator

```bash
uv run python tools/query_fpds.py piid 70CDCR26FR0000014 \
  --max-pages 3 --output /tmp/codex-r-live-fpds-piid.json

uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64' \
  --max-pages 2 --output /tmp/codex-r-live-fpds-uei.json

uv run python tools/query_usaspending.py transactions-keyword "skip tracing" \
  --start 2015-10-01 --end 2026-07-27 --all-pages \
  --output /tmp/codex-r-live-usaspending-skip.json

uv run python tools/query_usaspending.py transactions-keyword \
  "safety verification" --start 2026-01-01 --end 2026-07-27 \
  --naics 561611 --psc R799 \
  --agency "Department of Homeland Security" --all-pages \
  --output /tmp/codex-r-live-usaspending-filtered.json
```

## UNCONFIRMED — API-shape assumptions for live verification

1. The saved FPDS response confirms the entry structure and field names but is
   a single page. A live multi-page result must confirm that the feed's
   `rel=next` URL is present and directly reusable through the last page.
2. The verified FPDS probe URL used `FEEDNAME=PUBLIC`,
   `templateName=1.5.3`, `q=<query>`, and implicit/default `start=0`; the tool
   sends explicit `start=0`. Confirm that FPDS accepts this equivalent form.
3. The USAspending fixture confirms the unfiltered keyword/date/contract
   payload and camel-case `page_metadata.hasNext`. It does not exercise a
   second live page; confirm that incrementing the top-level `page` field is
   sufficient on paginated results.
4. The optional NAICS shape follows the existing repository form
   `[{"naics_code": CODE, "is_primary": true}]`. The PSC shape is the analogous
   `[{"psc_code": CODE}]`. Neither optional-filter shape is covered by the
   saved response, so the fourth live command must confirm both.
5. `--agency` follows the file's existing top-tier awarding-agency shape:
   `[{"type": "awarding", "tier": "toptier", "name": NAME}]`. It therefore
   expects a top-tier name such as `Department of Homeland Security`, not a
   subtier name such as `U.S. Immigration and Customs Enforcement`.
6. The tool defaults to `limit=100`, matching the saved successful request.
   Confirm that USAspending continues to accept 100 results per page when the
   optional NAICS/PSC/agency filters are combined.

## NEEDS MANUAL OPENCORPORATES

None. This code-only infrastructure assignment required no corporate-registry
lookups.
