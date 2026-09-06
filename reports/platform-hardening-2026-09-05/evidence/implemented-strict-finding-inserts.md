# Strict new finding insertion integration

Status: complete and verified, including the authorized El Peruano and Companies House producer integrations. All owned files are stable and ready for parent integration; no Git mutations performed.

## Behavior

- `tools/findings_tracker.py:add_finding_to_db` requires at least one valid evidence reference and a nonblank textual exact source quote for every reference, for every claim type. No draft exemption switch exists.
- It uses the existing evidence span validation and shared candidate validation. Confidence ceilings, requested-confidence tracking, event-date normalization, profile/thread validation and caller-owned transaction behavior remain intact.
- Complete provenance does not confer verification: new rows still have `verification_status=unverified`, null reviewer and review timestamp.
- Existing reads, audits and correction/evidence repair paths retain legacy compatibility. A dedicated synthetic historical incomplete row can be read, corrected, rejected at verification, repaired through evidence-add, and then verified.
- Invalid new writes leave no finding/evidence/entity rows and do not commit/roll back an enclosing caller transaction. Nontext quote values are rejected before inserts rather than relying on a later SQLite bind error.

## Owned core files

- tools/findings_tracker.py (strict insert and clarification of internal validation/verification docstrings only; preserve parent preexisting changes)
- tests/test_finding_mutation_invariants.py (new required-provenance negative matrix across all five claim types, four nontext-quote cases, separate verification status and legacy repair)
- tests/test_finding_evidence_crud.py (valid synthetic provenance in ordinary fixtures; explicit direct-SQL incomplete legacy state only for repair-specific tests; narrowed queries when metadata test adds a second record)
- tests/test_finding_relation_corrections.py (valid fixture and CLI provenance)
- tests/test_findings_provenance_papercuts.py (valid initial evidence and precise rejection assertion)
- tests/test_findings_read_commands.py (valid fixture provenance)
- tests/test_enforcement.py (valid provenance for cap and profile/thread tests)
- tests/test_papercut_regressions.py (valid provenance for lead-link and date/search tests)

## Validation

Changed-file Ruff passed. Final affected integration suite: **291 passed in 24.28s**. Log: `/tmp/osint-CUTDyZF1/strict-finding-inserts-final.txt`.

Command:

```sh
uv run pytest tests/test_finding_mutation_invariants.py tests/test_finding_evidence_crud.py tests/test_findings_provenance_papercuts.py tests/test_finding_relation_corrections.py tests/test_findings_read_commands.py tests/test_abstract_finding_targets.py tests/test_findings_tracker_evidence.py tests/test_enforcement.py tests/test_connection_evidence_atomicity.py tests/test_dispatcher.py tests/test_connection_evidence_workflow.py tests/test_core_schema_bootstrap.py tests/test_papercut_regressions.py tests/test_queue_lifecycle_hardening.py -q --offline --maxfail=10 -p no:cacheprovider --basetemp /tmp/osint-CUTDyZF1/pytest-strict-finding-inserts-final
```

Workflow agent independently inspected the strict insertion implementation and ran 49 mutation-invariant tests with explicitly pinned scratch profile/DB; its docs now describe strict inserts and separate legacy repair.

## Papercut and scope

No live DB changes and no Git edits. Logged and resolved isolated observation #1 in `/tmp/osint-CUTDyZF1/strict-finding-papercuts.db`. Root owns any canonical observation import/logging.

Exact prior reproduction: `add_finding_to_db(db, target_name="Fixture", summary="Unsupported claim", source_datasets=["courtlistener"], claim_type="inference")` inserted an unverified row with no evidence. The same gap affected paraphrase, synthesis, and user_provided. Supplying refs without source_quotes also created unquoted rows. Expected behavior is rejection for every new claim, without removing audited legacy repair paths.


## Final combined validation including producers

**320 passed in 22.19s** with the entire 291-test core suite plus:

- tests/test_ingest_elperuano_findings.py
- tests/test_uk_companies_house_findings.py
- tests/test_uk_companies_house_output.py

The final command uses the core command above plus those three paths and `--basetemp /tmp/osint-CUTDyZF1/pytest-strict-finding-producer-integration`.

Log: `/tmp/osint-CUTDyZF1/strict-finding-producer-integration.txt`. Ruff passed across all 12 owned Python source/test paths. The tracker add help/example now also state the required quoted-evidence contract.

### Producer handoff and exact papercut reproductions

# Finding producer integration

Owned changes:

- `tools/ingest_elperuano.py`
- `tools/ingest_uk_companies_house.py`
- `tests/test_ingest_elperuano_findings.py`
- `tests/test_uk_companies_house_findings.py`

## El Peruano

The producer now uses the actual supporting URL as its evidence reference: the landing page for a verbatim sumilla excerpt, or the visor API for a verbatim full-text excerpt. Document display numbers remain in the summary and saved metadata rather than masquerading as separate evidence. Each quote is passed as the tracker CLI's required `reference:quote` argument, preserving URL colons, text colons, and newlines.

Blank excerpts and overrides absent from both fetched texts fail before tracker invocation. Finding failures return a nonzero ingestion exit with a clear error after the fetched JSON has been saved. Paths outside the repository work with the documented `--output` flag; reporting that path no longer raises `relative_to` errors.

## UK Companies House

Generated case summaries are classified as `paraphrase` with `high` confidence. The quoted text is the actual API case `type` string, with `cases[index].type` as its locator. A fetched company name receives separate evidence at its actual company-profile API endpoint and a `company_name` locator. The full parsed case is retained in the detail as JSON, explicitly labeled serialization rather than a verbatim response excerpt. Cases lacking a nonblank string type fail instead of fabricating a quotation.

The public Companies House display page remains linked in the detail. No historical stored findings were changed.

## Verification

`uv run python -m pytest tests/test_ingest_elperuano_findings.py tests/test_uk_companies_house_findings.py tests/test_uk_companies_house_output.py --offline -q -p no:cacheprovider`

Result: **29 passed in 0.88s** (8 El Peruano, 6 new Companies House, 15 existing output regressions).

`uv run ruff check tools/ingest_elperuano.py tools/ingest_uk_companies_house.py tests/test_ingest_elperuano_findings.py tests/test_uk_companies_house_findings.py`

Result: all checks passed. `git diff --check` passed for the owned paths.

Tests invoke the ingestion CLI entry point with synthetic fetch results. In addition to parser/capture regressions, one El Peruano test routes the produced command through the actual tracker CLI, actual canonical validation, and actual finding/evidence insertion into an isolated temporary database. One UK test routes the producer through `add_finding_to_db` on the full isolated schema. Both assert persisted source references/quotes, claim type, confidence, profile, and unverified status. Other tests capture finding requests to inspect detailed record context. All network fetches are synthetic. No live API calls, live database writes, or Git mutations occurred.

## Exact papercut reproduction for parent logging

No live database was opened for logging, per delegated scope. The parent may log/resolve the following concrete reproductions with the verification above:

1. **El Peruano finding ingestion emits malformed quote metadata.** Before this patch `_create_finding()` produced `--evidence 001-2026-DE https://busquedas.elperuano.pe/dispositivo/NL/2493140-1 --source-quote 'Aprueban el convenio: cooperación técnica'`. `_parse_source_quote_args` either rejected a quote with no colon or treated the words before its colon as an unknown evidence reference; neither of the two actual arguments received valid quotation metadata. Expected: one actual supporting source reference with its exact mapped quote. Regression: `test_cli_maps_verbatim_sumilla_to_its_source_and_preserves_output`.
2. **El Peruano --output outside the repo crashes after writing its document.** `cmd_ingest()` used `path.relative_to(REPO_ROOT)` unconditionally when printing an absolute `/tmp/osint-.../document.json` output path. Expected: report the path and continue to requested finding creation. Covered by the same regression and all failure-preservation tests.
3. **UK insolvency producer labels generated prose as a confirmed quotation.** Given a parsed case `{"number":1,"type":"creditors-voluntary-liquidation"}`, it emitted `claim_type='direct_quote'`, `confidence='confirmed'`, and quote `Insolvency case #1, type: creditors-voluntary-liquidation`, which was generated by an f-string rather than present in the source. Expected: paraphrase/high, actual source field quotations, field locators, and traceable retained record context. Regression: `test_insolvency_summary_is_paraphrase_with_exact_values_and_labeled_record`.

No changes outside the four owned source/test files and this isolated handoff were made.
