# Unit G implementation

Owned worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`.

Completed changes:

- Updated both runtime variants of `analyze-network`, `timeline-analysis`, `systemic-analysis`, `generate-hunches`, `analyze-case`, and `discover-frameworks`.
- `analyze-case` now uses the profile-aware financial tracker view instead of hardcoded SQLite. Bounded list coverage is explicit. Cross-case examples supply two distinct typed opinion references and a matching quote for each. The direct opinion example retains raw opinion identity, document URL, location, and procedural posture; the connection example points to its supporting finding. CourtListener retrieval distinguishes cluster/raw opinion IDs, saves complete artifacts, inventories separate opinions, tracks reading coverage, and uses the cluster ID for the citation graph. Preserved the full relevant-opinion reading requirement and allegation/holding distinctions. Removed capability-marketing prose and added a resumable completion report.
- `analysis_export.py` includes `date_formed` in both scoped and all-profile entity exports. Hunch scanning consumes that actual field. Partial dates and nulls are preserved rather than invented or normalized to false exact dates.
- Numerical novelty, shared-attribute, temporal, group-size, and framework-promotion rules now serve as explained starting points. Important two-record discoveries and new mechanisms among already-connected parties remain eligible; routine larger overlaps are not automatically significant.
- Graph interpretation now describes recorded edges, coverage, dates, and semantics. Missing edges do not establish social separation or information control. Source and metric lists are selectable menus with recorded coverage.
- ACH remains required for coordination/intent and live rival explanations, with falsification, competing evidence, and concrete research leads. Descriptive measurements no longer require invented explanatory competitions. Canonical evidence/quotes and synthesis confidence ceilings remain intact.
- Framework discovery verifies origins against original/official scholarly or practitioner sources, considers counterexamples, and adopts based on diagnostic value and boundary tests. Keyword gaps, article mentions, and elapsed time no longer serve as automatic evidence of applicability or promotion. Review-only intent remains read-only absent existing apply authorization.
- Native supervised delegation is explicit where independent source, case, or framework reviews help, with model inheritance, pinned context, unique reports, ownership, collection, and reconciliation. No named model generations added. Scope/coverage and resumable partial/no-action outcomes were strengthened across the packages.

Files to stage for this unit:

- `.claude/skills/{analyze-network,timeline-analysis,systemic-analysis,generate-hunches,analyze-case,discover-frameworks}/SKILL.md`
- `.codex/skills/{analyze-network,timeline-analysis,systemic-analysis,generate-hunches,analyze-case,discover-frameworks}/SKILL.md`
- `tools/analysis_export.py`
- `tests/test_analysis_skill_modernization.py` (new; eight parameterized fixture cases)

Validation performed, with the assigned `UV_PROJECT_ENVIRONMENT`, `UV_NO_SYNC=1`, `UV_CACHE_DIR`, bash `login:false`, and explicit worktree cwd:

1. `uv run python -m pytest tests/test_analysis_skill_modernization.py tests/test_analysis_skill_commands.py tests/test_analysis_export_connections.py tests/test_analysis_export_timeline.py tests/test_analysis_cli_papercuts.py tests/test_profile_analysis_papercuts.py -q` — **23 passed**.
2. `uv run python -m pytest tests/test_core_schema_bootstrap.py tests/test_analysis_skill_modernization.py -q` — **14 passed** (six overlap with the first run; **31 distinct tests** total).
3. `uv run ruff check tools/analysis_export.py tests/test_analysis_skill_modernization.py` — **passed**.
4. `git diff --check` scoped to the owned files — **passed**.
5. At unit C's request, added an analogous both-runtime selected-database/profile fixture for the documented `analyze-filing` connections command. Final `uv run python -m pytest tests/test_analysis_skill_modernization.py -q` — **8 passed**; ruff passed again. These add two distinct tests, bringing the distinct validated total to **33**.

The new fixture tests execute the documented case financial cross-reference and filing connections lookup against a selected database/profile with matching foreign-profile and decoy-database rows; only selected facts/connections survive. Both runtimes' documented cross-case command is parsed through the actual tracker CLI while intercepting persistence and validating evidence payloads. Entity-network fixtures cover a related endpoint, foreign-profile entity, exact/month/year dates, and a null date in both export modes. Existing bootstrap coverage verifies the added export field against fresh full-schema databases.

Mechanical lint cleanup: the owned `analysis_export.py` already had four unused imports and seven placeholder-free f-strings. Removed those without changing behavior so changed-file lint passes. No new CLI or export routing implementation was duplicated.

Boundaries and remaining integration work:

- No commits, production database writes, source queries, headless operations, new agents, or edits to another unit's owned paths.
- Left shared metadata normalization, root policy/methodology reconciliation, global skill validation/parity, and independent agent forward tests to the parent. No performance gains across actual Claude/Codex runs are claimed.
- Left `analyze-filing`, `analyze-contract`, EDGAR, and USAspending work entirely to unit C.
- Formation date exposes the existing raw schema field; it does not introduce a new entity date precision system. CourtListener acquisition uses the existing complete-output route and explicit IDs rather than adding another downloader.
- The scoped analysis-run Python APIs remain as existing recipes; the optional start/complete CLI redesign was not necessary for these correctness fixes.
