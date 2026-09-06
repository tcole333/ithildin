---
name: landscape-scan
description: Map the actors and evidenced relationships in a new investigation area, then prioritize factual follow-up questions. Use for breadth-first discovery across multiple targets rather than a deep investigation of one selected target.
user-invocable: true
---

# /landscape-scan

Produce a preliminary actor/relationship map and identify which questions deserve
deeper research. Choose breadth and depth from the user's area and evidence, and
make the limits of this initial pass visible.

## 1. Set the scan question and context

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`.
Pin profile/database and create unique outputs:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
uv run python tools/findings_tracker.py search "<AREA_KEYWORDS>" --output "$WORKDIR/scan-findings.json"
uv run python tools/lead_tracker.py search "<AREA_KEYWORDS>" --output "$WORKDIR/scan-leads.json"
```

State the area, key factual questions, target types, relevant dates/jurisdictions,
and existing thread context. Build a candidate list from authoritative source
inventories, public context, and existing evidence. Verify remembered identities
and current roles. Ten to thirty targets and a few sources per target are planning
defaults; adapt them to the actual area and requested scope.

## 2. Search a bounded initial source set

Choose a few high-value sources per target that can answer the scan questions,
using the shared applicability checklist and current `docs/modules/` commands.
This is initial coverage, not a claim that all relevant sources are exhausted.

| Target/nexus | Initial source choices |
|---|---|
| Person | Relevant role/affiliation records, corporate officers, court field matching their role, political or nonprofit records where applicable |
| Company | Relevant registry, regulator filings, awards or financial statements |
| Nonprofit | Charity filings, 990 organization/officer records, a bounded grant-flow view |
| Government actor | Official role records and relevant disclosure/contract/lobbying records |
| New target or missing identity | Official pages and attributed published context, followed by primary records |

Use exact identifiers once known, unique `--output` artifacts, and the shared
reuse rules. Record source scope, limits, continuation, and outcome for each
target. Namesakes, unavailable sources, and truncated results remain visible.

Independent target groups may use native chat subagents under the execution
contract. Give each worker a source/target scope and unique report path; retain
parent work for identity resolution, coverage, and cross-target reconciliation.

Read the source context needed to support significant observations. Full
documents are available when necessary; for long documents retain the complete
artifact and record sections/chunks read plus continuation. A scan may explicitly
defer deeper reading rather than claim the document was fully assessed.

## 3. Record evidence and map relationships

Preserve meaningful observations, including institutional roles, financial
flows, structural connections, and useful ambient facts. Significance depends on
the question and baseline, not a universal dollar/finding quota. A zero-result
search is a bounded coverage observation; a negative finding needs the shared
authoritative-source, identity, scope, and quoted-evidence standard.

```bash
uv run python tools/findings_tracker.py add \
  --target "<TARGET>" --type background \
  --summary "What the source establishes within the scan scope" \
  --evidence "<EVIDENCE_REF>" --claim-type paraphrase \
  --source-quote "<EVIDENCE_REF>:exact supporting source text" \
  --sources <SOURCE_TOKEN> --confidence high
```

Use lower confidence when warranted. Inference/synthesis is at most medium;
source repetition is not independent corroboration. Resolve entities before
registering them with `entity_tracker.py` and preserve dated roles/addresses.

```bash
uv run python tools/findings_tracker.py connect \
  --person-a "<TARGET_A>" --person-b "<TARGET_B>" \
  --type employment --strength weak \
  --evidence "<EVIDENCE_REF>" \
  --source-quote "<EVIDENCE_REF>:exact text supporting the relationship"
```

Choose the actual relationship type from current CLI choices. Keep candidate
matches and unexplained co-occurrence distinct from established relationships.

## 4. Prioritize and finish

Test the leading selection assumption against contrary evidence or an ordinary
alternative before recommending deeper work. Prioritize the question's structural
importance, evidence availability, unresolved contradictions, and expected value
of the next check. Several mirrors or source appearances alone do not justify
escalation, and a low-volume authoritative record can be decisive.

Create a lead for each actionable deeper question, linking relevant evidence:

```bash
uv run python tools/lead_tracker.py add \
  --title "Investigate <TARGET> — <specific unresolved question>" \
  --category entity --priority medium --target "<TARGET>" \
  --source "agent:landscape-scan" --evidence "<EVIDENCE_REF>"
uv run python tools/lead_tracker.py tier <LEAD_ID> scan
```

Choose the actual category/priority and tag created leads `scan`. Recommend
`/deep-investigate` for independent deep source tracks, `/pursue-lead` for a focused
queued question, or the relevant specialist skill. The number promoted follows
the evidence, not a fixed quota.

Completion means the agreed candidate set is accounted for, the preliminary map
is evidence-linked, coverage limits are explicit, and unresolved questions have
a triage recommendation. Return targets/types, findings and relationships,
source outcomes, record IDs, artifact paths, and reasons for prioritization.
Workers use the assigned report path; preserve incomplete scope and continuation.
Checkpoint progress across interruptions/compaction and resume the original area.
