# H forward test: observed execution and choices

Worktree: `/Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905`.
Fixture workdir: `/private/tmp/osint-forward-h-ca8J0rzr`.

I read the current Codex orchestrate-investigation, dispatch, and init-investigation skills, their execution/research/Git contracts, and the profile template. I did not read an implementation report for H. I inspected CLI help and the status/context interfaces to build a minimal fixture and select commands. This is a fixture/planning exercise; no research, agents, headless jobs, production DB calls, or repository writes occurred.

## Actual status execution

Created `selected.db` and `ambient.db` solely inside the fresh fixture workdir. Selected has alpha and other-profile rows, a shared default named `shared-default`, and a legacy-shaped analysis_runs table with no status field. Ambient contains a same-profile decoy lead. All content is synthetic. I set the shell to alpha with the ambient DB, then used the explicit requested database:

```bash
export ITHILDIN_PROFILE=alpha
export ITHILDIN_DB_PATH=/tmp/osint-forward-h-ca8J0rzr/ambient.db
uv run python tools/investigation_status.py --profile alpha   --db /tmp/osint-forward-h-ca8J0rzr/selected.db   --output /tmp/osint-forward-h-ca8J0rzr/status.json
```

Command exit: 0. Actual full saved output:

```json
{
  "schema_version": "investigation-status/1",
  "status": "partial",
  "generated_at": "2026-09-06T01:57:27.821686+00:00",
  "profile_id": "alpha",
  "db_path": "/private/tmp/osint-forward-h-ca8J0rzr/selected.db",
  "recent_since": "2026-08-30T01:57:27.821686+00:00",
  "metrics": {
    "lead_count": {
      "available": true,
      "value": 3
    },
    "leads_by_status": {
      "available": true,
      "value": [
        {
          "status": "in_progress",
          "count": 1
        },
        {
          "status": "open",
          "count": 1
        },
        {
          "status": "pending_triage",
          "count": 1
        }
      ]
    },
    "findings_count": {
      "available": true,
      "value": 2
    },
    "findings_by_confidence": {
      "available": true,
      "value": [
        {
          "confidence": "high",
          "count": 1
        },
        {
          "confidence": "medium",
          "count": 1
        }
      ]
    },
    "recent_findings_count": {
      "available": true,
      "value": 1
    },
    "latest_finding_at": {
      "available": true,
      "value": "2026-09-04 01:57:15"
    },
    "analysis_runs_count": {
      "available": true,
      "value": 1
    },
    "analysis_runs_by_status": {
      "available": false,
      "reason": "missing columns in analysis_runs: status"
    },
    "latest_analysis_at": {
      "available": true,
      "value": "2026-09-02 01:57:15"
    }
  }
}
```

My status summary would be: alpha in the explicitly selected database has three leads (one open, one in progress, one pending triage), two findings, and one finding in the trailing seven-day window. One analysis run is recorded; its lifecycle status is unavailable because the schema lacks that field. The overall snapshot is partial. I cannot infer that research is stalled, that the analysis completed, or that any source category is covered from these counts. This snapshot does not provide global capacity/source-health metrics; I would not attribute the fixture's global maintenance request to alpha.

To plan ownership without invoking an initializer/reaper, I performed a direct SQLite `mode=ro` lookup restricted to `profile_id='alpha'`. Actual output:

```json
{
  "profile_id": "alpha",
  "db_path": "/private/tmp/osint-forward-h-ca8J0rzr/selected.db",
  "leads": [
    {
      "id": 1,
      "title": "Legal posture question",
      "status": "open"
    },
    {
      "id": 2,
      "title": "Selected filing question",
      "status": "in_progress"
    },
    {
      "id": 3,
      "title": "Corpus identity question",
      "status": "pending_triage"
    }
  ],
  "ownership_metadata_available": false,
  "interpretation": "Lead 2 is in_progress; no worker liveness/ownership can be inferred from this fixture. Reconcile before duplicating that question."
}
```

Chosen next actions: review the pending triage question if execution is requested; resolve the factual scope of the open legal question; and reconcile the in-progress financial question's existing owner/artifacts before duplicating it. The fixture has no ownership notes or real worker IDs. I did not change any lead state or claim that an in-progress database label proves worker liveness.

## Supervision plan selected from the skills

Keep work in this chat. If the user later requests actual research, use native spawn/message/wait/follow-up tools for the independent legal, financial, and corpus questions once each factual target and source applicability are resolved. Omit model/reasoning overrides so the current chat's settings are inherited. Do not invoke dispatcher launch, claude -p, codex exec, queue jobs, or a new user-owned chat. If native tools are unavailable, proceed sequentially under the same owner.

The retained `assignments.json` defines three proposed mandates:

| Owner scope | Factual question | Source boundary |
|---|---|---|
| legal | What allegations and rulings are documented in the agreed alpha-related case, and what remains unresolved? | Relevant court system and primary filings/opinions after docket, party, jurisdiction, and date resolution |
| financial | What amount, transaction type, period, and counterparties are documented in the selected alpha-related financial record? | Applicable regulator/filing or award records, bound to the selected accession/award |
| corpus | Which independent records in alpha's configured corpus address the agreed question, and what do they establish? | Configured corpus and exact version; mirrors stay within one provenance chain |

Each would receive `ITHILDIN_PROFILE=alpha`, `ITHILDIN_DB_PATH=/private/tmp/osint-forward-h-ca8J0rzr/selected.db`, a unique report path (`report-legal.md`, `report-financial.md`, or `report-corpus.md`), artifact-only proposal authority initially, and explicit report requirements. Those requirements cover canonical references, exact quotes, source tokens, claim/confidence distinction, source applicability/outcomes, complete material reading coverage, ordinary alternatives, contradictions, bounded negative results, and unfinished scope. In this exercise all worker IDs remain null and execution states remain `not_started`.

While workers run in an authorized real investigation, I would perform useful parent work: resolve target/record identities, check source coverage, inspect retained evidence, and prepare an integration table. I would coordinate before querying a worker-owned source. I would read every report or identify its missing scope, verify load-bearing quotations and provenance, reconcile contradictions, and only then persist authorized findings through tracker APIs. Completion depends on answered questions and applicable coverage, not worker counts or elapsed time. No dispatcher receipt is expected for native workers.

## Interruption and continuation observed

I saved `checkpoint-before-interruption.json` after the status snapshot and the legal/financial mandate plans. It retained objective, selected context, constraints, completed work, expected report paths, null worker IDs, write policy, user steering, unknowns, and remaining tasks. The corpus mandate was still pending planning.

I then simulated an interruption and explicitly read that checkpoint in a separate tool call. On continuation I reopened the retained status artifact, checked its profile/database against the checkpoint, examined each expected report path, and confirmed that no worker or report had been created. I treated missing reports as `not started; no research outcome exists`, rather than negative search results or failures. I finished the corpus mandate, retained the original status output, added beta preparation to the plan, and wrote `checkpoint-after-continuation.json`. A subsequent read-only lead review added the need to reconcile financial lead #2 before starting overlapping work. No step replayed a seed, source query, or status mutation.

This is a simulated interruption between planning steps, not a claim to have tested a host crash or recovered real running agents.

## Beta plan and exact seed commands

Prepared `beta-config-proposal.yaml` under the fixture workdir only. It uses the user-provided label beta as a provisional subject, records that subject-specific identity/scope are unresolved, and has one organizing thread for initial questions. No real key persons, dates, pillars, or corpus tools are invented. The actual repository profile must be reviewed and installed without overwriting an existing beta config before the following commands are runnable. No seeds were executed and no seed counts or database thread IDs are claimed.

Saved command artifact (passed `/bin/bash -n`):

```bash
#!/usr/bin/env bash
# PROPOSED ONLY — not executed in the forward test.
# Prerequisite: install reviewed investigations/beta/config.yaml without
# overwriting an existing profile. Keep source/provenance notes alongside it.
# Shell may remain ITHILDIN_PROFILE=alpha. No shared-default 'set' is used.
set -euo pipefail
cd /Users/travcole/projects/osint-research/.claude/worktrees/skill-modernization-20260905
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/investigation_context.py show --json
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/lead_tracker.py thread seed
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/event_timeline.py seed
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/pillar_tracker.py seed
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/lead_tracker.py stats
uv run python tools/investigation_context.py run --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python tools/investigation_status.py --profile beta --db /private/tmp/osint-forward-h-ca8J0rzr/selected.db --output /private/tmp/osint-forward-h-ca8J0rzr/beta-status-after-seed.json
# Read actual returned thread IDs; do not use the profile-local id as a DB id.
# On resume, inspect existing beta leads before adding any distinct initial question.

```

I also executed a harmless environment probe through the same wrapper, with the shell still pinned to alpha/ambient.db:

```bash
uv run python tools/investigation_context.py run --profile beta   --db /tmp/osint-forward-h-ca8J0rzr/selected.db -- uv run python -c   'import json, os; print(json.dumps({"child_profile": os.environ["ITHILDIN_PROFILE"], "child_database": os.environ["ITHILDIN_DB_PATH"]}))'
```

Actual stdout: `{"child_profile": "beta", "child_database": "/private/tmp/osint-forward-h-ca8J0rzr/selected.db"}`.
The following shell print remained `parent_profile=alpha` and `parent_database=/tmp/osint-forward-h-ca8J0rzr/ambient.db`. This proves environment routing for that child, not successful beta creation or seed execution.

## Errors, limits, and ambiguities observed

- No invoked command failed. The status snapshot deliberately reported a missing analysis status column as unavailable; that is a real coverage limitation, not an exception or a zero.
- The fixture supplies queue records but no alpha YAML/case guidance, exact question contents, jurisdiction, dates, or configured corpus. The plan remains conditional on resolving those inputs; I did not silently choose U.S. sources or claim a corpus exists.
- The init skill directs the reader to inspect `investigation_context.py list`, but also says dry-run creates no database rows. Source inspection showed `list_profiles()` opens/reconciles the catalog and commits. I skipped that command in this read-only exercise rather than treating its name as proof of no mutations. A more explicit dry-run-safe inventory route would remove that ambiguity.
- Beta configuration lives in the repository filesystem while its seed rows belong to the selected database. There is no shown CLI switch for a fixture-only profile directory. I therefore saved a proposal outside the repository and marked installation as an unexecuted prerequisite; the environment probe does not validate that prerequisite.
- The analysis snapshot offers no lifecycle metadata for native workers. Checkpoints and real native tool status would supply it in an actual run.

## Fixture integrity and retained artifacts

Both selected and ambient database bytes stayed unchanged after all status/context/read-only inspection operations. Shared defaults stayed `shared-default`; beta has zero rows, consistent with unexecuted planning:

```json
{
  "selected.db": {
    "sha256_before": "bfe925f703ce8245c1e93adb35a1071e3ad4f35283bf35e9d7bb520f29a5a338",
    "sha256_after": "bfe925f703ce8245c1e93adb35a1071e3ad4f35283bf35e9d7bb520f29a5a338",
    "shared_default": "shared-default",
    "beta_rows": 0,
    "unchanged": true
  },
  "ambient.db": {
    "sha256_before": "48298d94d0bd9f41a80cdc3c0285b85d9faba24f2f5ad1116a7a16c0788c6ec5",
    "sha256_after": "48298d94d0bd9f41a80cdc3c0285b85d9faba24f2f5ad1116a7a16c0788c6ec5",
    "shared_default": "shared-default",
    "beta_rows": 0,
    "unchanged": true
  }
}
```

Retained in the fixture workdir: both synthetic databases, their before snapshots, `status.json`, `lead-context.json`, `assignments.json`, both interruption checkpoints, `beta-config-proposal.yaml`, `beta-seed-commands.sh`, and `fixture-integrity.json`.
