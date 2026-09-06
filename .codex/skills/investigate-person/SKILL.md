---
name: investigate-person
description: Research a named person's identity, institutional roles, and evidenced relationships. Use for a person-centered factual investigation; retain an existing lead's scope, and use deep-investigate for independent parallel source tracks.
---

# $investigate-person

Resolve the person's identity, roles, and relationships that bear on the requested
question. Hypotheses guide collection and disconfirmation; persisted claims remain
bounded by what the evidence supports.

## 1. Establish identity and scope

Accept the person's name and any investigation, question, dates, or jurisdiction.
Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`; pin the
profile/database and inherit the parent lead, source plan, ownership, and report
path when delegated. Create one isolated workdir or use the assigned unique paths.

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
uv run python tools/findings_tracker.py list --target "<NAME>" --output "$WORKDIR/person-findings.json"
uv run python tools/lead_tracker.py search "<NAME>" --output "$WORKDIR/person-leads.json"
uv run python tools/entity_tracker.py lookup --name "<NAME>" --output "$WORKDIR/person-entities.json"
```

Establish full name, aliases/transliterations, public roles, relevant institutions,
jurisdictions, and dates from existing records and authoritative public sources.
Treat remembered biography as a search starting point and verify current roles.
Distinguish namesakes before joins; name matches alone do not establish identity.

Write the factual questions, testable expectations, and plausible alternatives in
the lead notes or research record. Use first-party biographies, government records,
and published reporting for context; reporting supplies attributed claims and
discovery routes rather than automatic primary corroboration.

## 2. Choose and search applicable sources

Build the shared coverage matrix before querying. Use the configured corpus only
where its scope can cover the person/period. Consult the matching `docs/modules/`
reference for current commands and access routes:

| Nexus | Questions to resolve |
|---|---|
| Corporate roles | Officer/director/trustee positions, entity identity, appointment dates, ownership; relevant jurisdiction registries |
| Nonprofit activity | Board roles, compensation, institutional affiliations, grant flows; applicable charity filings and 990 officer search |
| Securities/financial | Filing identity, insider holdings, compensation, related parties; relevant regulator and EDGAR for a U.S. filing nexus |
| Legal | Whether the person is a party, witness, lawyer, or merely mentioned; relevant courts and filings |
| Property/secured assets | Ownership history, recording parties, liens, aircraft; evidence-selected jurisdictions and registries |
| Political/public office | Relevant giving, lobbying, foreign representation, procurement, public institutional records |
| Relationships/offshore | Identity-resolved LittleSis, ICIJ, sanctions and other applicable records |
| Corpus communications | Actual correspondence, dates, participants, threads, financial requests, and context; distinguish mirrors and derived extraction |

Use `$search-all-sources` for a bounded discovery lookup if needed; it does not
replace this source plan. Reuse existing outputs with the shared result-reuse
check. After each source, record scope and outcome, including bounded negatives,
failures, and continuation. Independent source tracks may use native chat
subagents under the execution contract while the parent continues useful work.

For a UK corporate nexus, check Companies House officer/company records. Read the
UK section of `docs/modules/registries.md` for current routes:

```bash
uv run python tools/ingest_uk_companies_house.py officer-search "<NAME>" --output "$WORKDIR/uk-officer-search.json"
uv run python tools/ingest_uk_companies_house.py search "<NAME>" --limit 20 --output "$WORKDIR/uk-company-search.json"
```

For relevant identity-resolved companies, retrieve company, officers, PSC, and
filings records using distinct company-number paths. Ambiguous officer names need
dates/company context; unavailable access remains an explicit gap.

For property/court questions, use `public_records_search_plan.py` and follow its
capabilities. For ICIJ, search the official remote service, review candidates,
then pass an exact numeric node ID to `connections`; local Neo4j is needed only
for deeper traversal. For email or co-occurrence analysis, use the profile's
documented structured tools and validate derived names/relations against the source.

## 3. Read and persist the evidence

Retrieve complete source artifacts. Read the entire document when the question
requires it; for long records inspect sequential chunks or relevant sections and
track read coverage and continuation. Resolve qualifications, authorship, dates,
and quoted context before persisting claims. Partial retrieval/read scope remains
partial in the report.

Record findings with `findings_tracker.py add`: canonical evidence references,
exact `ref:quote` pairs for every reference, registered source tokens, and an
appropriate claim type/confidence. Primary direct quotations may be `confirmed`;
paraphrases are at most `high` and inferences/synthesis at most `medium`. Use the
inherited lead/thread IDs. Correct prior findings through the audited correction
API instead of silently replacing their text.

Register discovered institutions/entities and the person's roles with
`entity_tracker.py`, resolving before creation. Preserve observed role dates,
addresses, formation details, financial amounts, and useful ambient facts. Add
career arcs with `pillar_tracker.py arc` for registered institutions. Relationships
need their own quoted evidence, even when linked to a finding:

```bash
uv run python tools/findings_tracker.py connect \
  --person-a "<NAME>" --person-b "<CONNECTED_ENTITY>" \
  --type employment --strength medium \
  --evidence "<EVIDENCE_REF>" \
  --source-quote "<EVIDENCE_REF>:exact source text supporting the relationship"
```

For another relationship type, use the current `connect --help` choices. Keep
potential identity matches and uncorroborated suggestions as questions/candidates.

## 4. Reconcile and complete

Compare records across time and independent sources. Investigate discrepancies
and perform a disconfirmation check for the working explanation. Communication
gaps need corpus/release coverage and ordinary alternatives before interpretation;
intermediaries and co-occurrence do not by themselves establish coordination.

Follow actionable new names, financial counterparties, and institutional links
within the question's scope; queue deeper independent questions as related leads.
Complete once applicable source coverage resolves the factual question or
remaining uncertainty has a documented next action/access barrier. Record
diminishing-return and incomplete-source decisions explicitly.

When a durable person research file helps, update
`research/persons/<name-slug>.md` with identity, dated roles, evidence-linked
findings, relationships, source coverage, contradictions, and open questions.
Preserve existing authored work and follow `docs/GIT_WORKFLOW.md` for retention.

Return the answer, finding/entity/connection IDs, coverage outcomes, bounded
negatives, contradictions, and artifact paths. Workers write the parent-assigned
report (otherwise `$WORKDIR/report-investigate-<name-slug>.md`), including disposition
and continuation. Ingest learnings with `methodology_tracker.py ingest-report`.
Checkpoint progress across interruptions/compaction and resume the original
question; a completed source pass alone is not completion of the investigation.
