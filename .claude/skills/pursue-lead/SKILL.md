---
name: pursue-lead
description: Pick up an open lead from investigation.db and investigate it to completion
user_invocable: true
---

# /pursue-lead

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Document what you find. Do not theorize, speculate, or apply analytical frameworks. If you notice a pattern, record the raw data — pattern recognition is for Layer 2 analysis agents. Record mundane facts (officer names, addresses, formation dates, filing numbers) even when they don't seem interesting. Record negative results from every source checked.

Claim and investigate the next highest-priority open lead. Operates fully autonomously.

## Arguments

- Optional lead ID: `/pursue-lead 42` to pursue a specific lead
- No arguments: automatically picks the highest-priority open lead

### Context Loading
Before scoped work, read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the
resolved task profile with `ITHILDIN_PROFILE`. Preserve/pass the selected
`ITHILDIN_DB_PATH` to workers. Load `investigation_context.py show` under that
environment for corpus tools, dates, threads, people, and jurisdictions; use
those values throughout this skill. Do not change the shared active profile.

### Ambient Documentation
**Document everything, not just what's relevant to your current hypothesis.**
When you encounter information during investigation — officer names, addresses,
corporate relationships, financial figures, dates, professional affiliations —
record it even if it doesn't obviously connect to the current lead. Use
`entity_tracker.py` to register entities, roles, and addresses. Use
`findings_tracker.py` with `--type background` for contextual facts that don't
directly answer the current question but are worth preserving. These ambient
findings compound across investigations and surface connections later.

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths and report files throughout this session. This prevents parallel `/pursue-lead` instances from overwriting each other's files.

### 1. Select Lead
If no specific ID given, use `claim-next` to atomically select and claim in one step (prevents race conditions with parallel agents):
```bash
uv run python tools/lead_tracker.py claim-next
```
To filter by category or thread:
```bash
uv run python tools/lead_tracker.py claim-next --category person --thread-id 1
```
If a specific lead ID was given, claim it directly and then load its details:
```bash
uv run python tools/lead_tracker.py claim <ID>
uv run python tools/lead_tracker.py show <ID>
```

### 2. Classify Investigation Type
Read the lead's description and category to determine the right approach:

- **person** → Run `/investigate-person` workflow
- **entity** → Run `/trace-entity` workflow
- **financial** → Focus on investigation corpus financial records, ICIJ offshore data
- **document** → Focus on locating and analyzing specific documents
- **digital** → Focus on email accounts, usernames, digital footprint
- **connection** → Focus on tracing relationship between two known entities

### 3. Check Prior Work and Result Reuse

Follow `docs/RESEARCH_WORKFLOW_CONTRACT.md#reuse-a-result-not-a-historical-log-entry`.
Historical `check_searched` rows describe work already done. Skip a new query only
when `search_reuse.py check` returns `reusable: true` for the actual operation,
filters, limit, freshness/source version, successful outcome, and intact artifact.
Inspect the reused results and record their scope in the lead report.

### 4. Build the Applicable Source Plan

Use the canonical applicability checklist in `docs/RESEARCH_WORKFLOW_CONTRACT.md`.
For each source record the question, jurisdiction/date scope, relevance reason,
and planned outcome. Check every applicable required source, including sources
likely to return zero. Record `not_applicable` for an irrelevant source with a
specific reason; an unavailable relevant source remains a coverage gap.

### 4b. Execute Searches
When the source plan selects property or litigation records, build the
capability-driven public-record plan before choosing a jurisdiction-specific
route:

```bash
uv run python tools/public_records_search_plan.py "<TARGET>" \
  --output "$WORKDIR/lead-public-record-plan.json"
uv run python tools/query_property.py owner "<TARGET>" \
  --output "$WORKDIR/lead-property.json"
uv run python tools/query_state_courts.py search "<TARGET>" \
  --output "$WORKDIR/lead-state-courts.json"
```

Use the plan's source IDs and operations with the unified routers for direct
adapters. When the catalog describes an account, request, purchase, formal
feed, or physical-office route, render the concrete work with
`public_records_actions.py plan`. Treat local-cache misses and acquisition
states as coverage information rather than source-authoritative zero results.

Run queries against relevant sources. For each search:
1. Query the source
2. Log the search with the current function signature:
   ```python
   from tools.lead_tracker import log_search
   log_search("<query text>", "<source>", result_count)
   ```
   Pass `session_id=` only when it is the integer ID of an existing `sessions`
   row; a lead ID is not a session ID. Use `lead_tracker.py note <LEAD_ID> ...`
   when the search also needs a lead-specific audit note.
3. Record notable results as notes on the lead
4. If a definitive finding is discovered, create a finding in findings_tracker

### 4c. Web Context Research (when relevant)

For person/entity leads, supplement dataset searches with web research:
- WebSearch for background on newly discovered names or entities
- WebFetch key reference pages (Wikipedia, corporate websites, government records)
- Check `research/RELATED_INVESTIGATIONS.md` for relevant historical parallels
- Check `research/OSINT_RESOURCES.md` for specialized tools that might help

Additional API tools (use `--output` to keep context lean):
```bash
# LittleSis (relationship/board mapping)
uv run python tools/query_littlesis.py search "<TARGET>" --output $WORKDIR/lead-littlesis.json

# SEC EDGAR (mentions in public filings)
uv run python tools/query_edgar.py search "<TARGET>" --size 10 --output $WORKDIR/lead-edgar.json

# Investigation reports (if populated)
uv run python tools/query_investigations.py search "<TARGET>" --limit 10 --output $WORKDIR/lead-investigations.json
```

This is especially important when:
- A lead involves a person not well-covered in the investigation corpus
- A lead involves an international entity or jurisdiction
- A lead connects to broader patterns (banking fraud, intelligence ops, etc.)

### 5. Record Findings
For each confirmed discovery (all provenance fields required by hooks):
```bash
uv run python tools/findings_tracker.py add \
    --target "<TARGET_NAME>" \
    --summary "One-line summary of what the evidence shows" \
    --type communication \
    --evidence <EVIDENCE_REF> \
    --claim-type paraphrase \
    --source-quote "<EVIDENCE_REF>:exact text from source supporting this claim" \
    --sources <SOURCE_NAMES> \
    --confidence high \
    --date "2017-03-15" \
    --lead-id <LEAD_ID>
```

**Claim types** (hooks enforce this):
- `direct_quote` — verbatim from source (can be `confirmed`)
- `paraphrase` — agent summary of source (max `high`)
- `inference` — agent conclusion from evidence (max `medium`)
- `synthesis` — combined multiple sources (max `medium`)

**When completing a lead**, summarize: (1) what factual questions the lead asked, (2) what the evidence showed, (3) what was NOT found despite checking (negative results), (4) what new factual questions were raised.

If the finding reveals a relationship:
```bash
uv run python tools/findings_tracker.py connect \
    --person-a "<PERSON_A>" --person-b "<PERSON_B>" \
    --type financial --strength strong \
    --evidence <EVIDENCE_REF> \
    --finding-id <FINDING_ID>
```

### 5b. Register Entities, Roles & Relations

**CRITICAL**: Register entities in structured tables as you discover them. Use `tools/entity_tracker.py` instead of inline SQL snippets.

```bash
# 1) Lookup existing entities
uv run python tools/entity_tracker.py lookup --name "Entity Name"

# 2) Create entity if missing
uv run python tools/entity_tracker.py add-entity   --name "Entity Name"   --entity-type llc   --jurisdiction ny   --status active   --source "EFTA02XXXXXX"   --notes "Context"

# 3) Record person role
uv run python tools/entity_tracker.py add-role   --entity-id <ENTITY_ID>   --person-name "Person Name"   --role "director"   --date-start "2010-01"   --date-end "2019-07"   --source "EFTA02XXXXXX"

# 4) Record address
uv run python tools/entity_tracker.py add-address   --entity-id <ENTITY_ID>   --address "123 Main St, City, ST 00000"   --address-type registered   --date-observed "2019"   --source "ny_sos"

# 5) Record entity relation
uv run python tools/entity_tracker.py add-relation   --entity-a-id <ENTITY_A_ID>   --entity-b-id <ENTITY_B_ID>   --relation-type funds   --description "Enhanced Education donated $150K to IPI"   --source "EFTA02XXXXXX"
```

Use allowed entity types: `person, llc, inc, ltd, corporation, pllc, trust, foundation, nonprofit, partnership, fund, association, government, pac, agency, joint_venture, shell, unknown`.

### 5c. Record Career Arcs

When employment history is discovered during investigation, record career arcs:

```bash
uv run python tools/pillar_tracker.py arc \
    --person "<NAME>" --pillar "<INSTITUTION>" \
    --role "<ROLE>" --seniority <junior|mid|senior|leadership|founder> \
    --start "<YEAR>" --end "<YEAR>" \
    --source "<EVIDENCE_REF>"
```

Check registered pillars: `uv run python tools/pillar_tracker.py list --type banking` (or legal, government, etc.)

### 6. Spawn Follow-Up Leads
When investigation reveals new threads worth pursuing:
```bash
uv run python tools/lead_tracker.py add \
    --title "Investigate Samantha Stein ProtonMail communications" \
    --category person \
    --priority high \
    --source "agent:pursue-lead" \
    --target "Samantha Rose Stein" \
    --evidence EFTA02731082 \
    --related <PARENT_LEAD_ID>
```

Agents should freely create follow-up leads at whatever priority they judge appropriate.

**Depth-analysis leads**: When you find a specific SEC filing, federal contract, or court case worth detailed analysis, spawn a lead with the appropriate category so depth-analysis skills can pick it up:

```bash
# SEC filing worth reading in full
uv run python tools/lead_tracker.py add --title "Analyze <COMPANY> 10-K — related-party transactions" \
  --category filing --priority medium --target "<COMPANY>" --source "agent:pursue-lead"

# Government contract worth tracing
uv run python tools/lead_tracker.py add --title "Analyze $<AMT> <AGENCY> contract to <COMPANY>" \
  --category contract --priority medium --target "<COMPANY>" --source "agent:pursue-lead"

# Court case worth deep reading
uv run python tools/lead_tracker.py add --title "Analyze <CASE_NAME> — <ALLEGATION_TYPE>" \
  --category case --priority medium --target "<PARTY>" --source "agent:pursue-lead"
```

These route to `/analyze-filing`, `/analyze-contract`, and `/analyze-case` which read the full source documents — something discovery agents shouldn't spend time on.

### 7. Check Stop Conditions

**Disconfirmation Sweep (required before completion):** Run at least one search designed explicitly to refute the working hypothesis, not merely to complete source coverage. Record the query and result through the existing evidence/negative-results mechanism. A negative disconfirmation search is itself reportable evidence and must not be omitted because it found nothing.

Stop investigating and move to completion when ANY of these is true:

- **Applicable source plan complete**: You've checked the required sources and answered the factual question to its evidence standard, or recorded the remaining bounded uncertainty. Count independent evidence, not mirrors of one document.
- **Mandatory sources exhausted with consistent negatives**: You've checked all mandatory sources and found nothing. Record negative results and complete.
- **Diminishing returns after applicable coverage**: Required source coverage is complete and further query variations yield no new entities, connections, or documents. Unsearched relevant sources remain explicit gaps; an access barrier follows the blocking path below.
- **Hard access barrier**: The next useful step requires infrastructure we don't have (e.g., a registry tool, a paid database, FOIA). Create an infra request and block the lead.

Do NOT stop because you "found enough" — stop because sources are exhausted or returns are diminishing. But also do NOT rabbit-hole into speculative searches when mandatory sources are done.

### 8. Complete the Lead
```bash
uv run python tools/lead_tracker.py complete <ID> --findings "Summary of what was found and what remains unknown"
```

If the lead is a dead end:
```bash
uv run python tools/lead_tracker.py dead-end <ID> "Explanation of why"
```

If blocked by a hard access barrier after exhausting public alternatives:
```bash
uv run python tools/lead_tracker.py block <ID> "Required primary record is behind unavailable authenticated or paid access"
```

Do not block solely because local ICIJ Neo4j is unavailable. Run the official
remote ICIJ search and first-hop workflow first; missing local Neo4j limits only
depth greater than one and should be recorded as a narrower coverage gap.

## Investigative Mindset

**Read `research/INVESTIGATIVE_METHODOLOGY.md` if you haven't already.** You are an investigator, not a search engine.

### Before Touching Any Tool

1. **Form hypotheses first.** Read the lead's description and your training data knowledge. What do you expect to find? What would confirm this lead? What would refute it? Write your hypotheses as a note on the lead.

2. **Simulate the person.** If this lead involves a person, ask: What role does this target play in the investigation thread? What are their incentives? What would confirmation look like? What was their public position vs. private behavior? The gap is where the story lives.

3. **Check the timeline.** What else was happening in the world when this event occurred? A Dec 2016 email about a Russian ambassador means something very different than a Dec 2014 one.

4. **Think about what's missing.** If you find 5 emails between two people in 2017 but zero in 2018-2019, the gap may be more significant than the emails. Did they move to ProtonMail? Did the relationship end? Did they start using intermediaries?

### During Investigation

- **Follow the incentive structure.** Money flows reveal truth that words obscure. When you find a financial transaction, ask: what service could possibly justify this amount?
- **Look for the "both sides" pattern.** Investigation subjects often maintain relationships with opposing parties simultaneously. Map contradictions — they reveal the subject's actual strategy.
- **Try alternate search terms.** Transliterations, maiden names, entity abbreviations, coded language. A search for "craft purchase" finds what "boat" or "yacht" misses.
- **Analyze tone and context**, not just frequency. 10 formal emails may reveal less than 3 intimate ones with financial requests.

### When Recording Findings

- **Distinguish fact from inference.** "Email shows wire transfer of $18M" is a fact. "This was payment for diplomatic access" is an inference. Label them differently.
- **Scope negative results.** Record searched queries, dates, filters, and coverage in the report/search log. Create a negative finding only when the bounded-negative evidence standard is met.
- **Record remaining factual questions.** Queue actionable follow-ups when evidence leaves a useful next step; a completed answer need not generate another lead.

### Thread Awareness

- **Do NOT close a lead because you didn't find direct {primary_subject} connections.** Follow the thread — if the target connects to other interesting actors or reveals network infrastructure, that's valuable. A thread-specific lead is about that thread's subject, not solely about the primary subject.
- If the lead has a `thread_id`, assign new findings to the same thread with `--thread-id N`.
- If you discover something relevant to a different thread, create a new lead in that thread.

## Operational Principles

- **Complete applicable coverage**: Follow the shared source plan and stop conditions; a universal source count does not establish coverage
- **Cite evidence**: Always include EFTA IDs, file paths, or source references
- **Reuse deliberately**: Inspect prior search history and use the shared reuse check; search existing findings before creating new ones
- **Prefer EFTA IDs** as canonical evidence references when available
- **Create follow-ups generously**: If something looks interesting, create a lead for it
- **Document dead ends**: A dead end is still valuable — it prevents re-investigation
- **Be curious and proactive about infrastructure**: As you investigate, look for data sources we don't have tools for. If you find a government database, corporate registry, or public dataset that would help the investigation, probe only enough to verify the public endpoint and create an infrastructure request via `uv run python tools/infra_tracker.py add --title "..." --type new_source --description "..." --source-name "..." --priority medium --discovered-by "agent:pursue-lead"`. Do not implement the integration during research; `/build-infra` owns the claimed build, tests, documentation, citation support, source-health update, and completion.
- **Extend existing tools when gaps appear**: If a query tool doesn't cover a jurisdiction you need, or a search tool misses a variant you tried manually, create an infra request with `--type tool_improvement`. Small enhancements compound across all future investigations.

## Context Management

This skill can be run directly or dispatched as a subagent from an orchestrating session. Multiple `/pursue-lead` subagents can run in parallel — the DB claim mechanism (`claim-next`) prevents double-claiming. All subagents write to shared `investigation.db` (WAL mode handles concurrent writes).

### Output Discipline
- **Use `--output $WORKDIR/...` on ALL search commands** to keep context lean
- **Do NOT `cat` or `Read` full document text** — extract relevant quotes only
- **Record findings as you go**, not in a batch at the end
- **DB-first, report-second**: Every factual discovery must be recorded to `findings_tracker.py add` and every entity to `entity_tracker.py` as you find them. The report file (if writing one for a parent orchestrator) is a summary of what you already persisted. The database is permanent; tmp files are ephemeral.

### Tool Bug Reporting
If you encounter bugs in CLI tools (crashes, incorrect output, missing features), submit them to the infra queue:
`uv run python tools/infra_tracker.py add --title "Bug: <description>" --type tool_improvement --priority high --description "<details including the error traceback>"`

### Report File (when running as sub-agent)
If spawned by another skill (e.g., wave orchestrator), write a report at completion:

```bash
# Write to $WORKDIR/report-lead-<LEAD_ID>.md
```

Report format:
```markdown
---
agent: pursue-lead
target: "<TARGET>"
skill: pursue-lead
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
lead_id: <ID>
---
# Lead #<ID> Report: <title>
## Key Discoveries
- [1-2 sentence summary per finding]
## Findings Added
[count] findings (IDs: ...)
## Connections Added
[count] connections
## Entities Registered
[count] entities
## Negative Results
- [Sources searched with zero results]
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
## Gaps / Follow-up Needed
- [items that couldn't be resolved]
## Leads Spawned
[count] leads (IDs: ...)
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes
```

After writing the report, ingest learnings into the methodology tracker:
```bash
uv run python tools/methodology_tracker.py ingest-report "$WORKDIR/report-lead-<LEAD_ID>.md" --skill pursue-lead --lead-id <LEAD_ID>
```

During investigation, record tool friction or process issues inline as they occur:
```bash
uv run python tools/methodology_tracker.py add --category friction \
    --description "query_doj.py FTS5 times out for common words" \
    --skill pursue-lead --lead-id <LEAD_ID>
```
