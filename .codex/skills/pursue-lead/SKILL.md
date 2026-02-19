---
name: pursue-lead
description: Pick up an open lead from investigation.db and investigate it to completion
---

# /pursue-lead

Claim and investigate the next highest-priority open lead. Operates fully autonomously.

## Arguments

- Optional lead ID: `/pursue-lead 42` to pursue a specific lead
- No arguments: automatically picks the highest-priority open lead

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths and report files throughout this session. This prevents parallel `/pursue-lead` instances from overwriting each other's files.

### 1. Select Lead
If no specific ID given:
```bash
uv run python tools/lead_tracker.py next
```
Then claim it:
```bash
uv run python tools/lead_tracker.py claim <ID>
```

### 2. Classify Investigation Type
Read the lead's description and category to determine the right approach:

- **person** → Run `/investigate-person` workflow
- **entity** → Run `/trace-entity` workflow
- **financial** → Focus on DOJ Vol 11, LMSBAND financial records, ICIJ offshore data
- **document** → Focus on locating and analyzing specific documents
- **digital** → Focus on email accounts, usernames, digital footprint
- **connection** → Focus on tracing relationship between two known entities

### 3. Check Search Log
Before querying any source, check if the query was already run:
```python
# In your search workflow, check:
from tools.lead_tracker import check_searched
prior = check_searched("rod-larsen", "doj_vol11")
if prior:
    # Skip this source, already searched
```

### 4. Execute Searches
Run queries against relevant sources. For each search:
1. Query the source
2. Log the search: `uv run python tools/lead_tracker.py` (use log_search function)
3. Record notable results as notes on the lead
4. If a definitive finding is discovered, create a finding in findings_tracker

### 4b. Web Context Research (when relevant)

For person/entity leads, supplement dataset searches with web research:
- WebSearch for background on newly discovered names or entities
- WebFetch key reference pages (Wikipedia, corporate websites, government records)
- Check `research/RELATED_INVESTIGATIONS.md` for relevant historical parallels
- Check `research/OSINT_RESOURCES.md` for specialized tools that might help

Additional API tools (use `--output` to keep context lean):
```bash
# LittleSis (relationship/board mapping)
uv run uv run python tools/query_littlesis.py search "<TARGET>" --output $WORKDIR/lead-littlesis.json

# SEC EDGAR (mentions in public filings)
uv run uv run python tools/query_edgar.py search "<TARGET>" --size 10 --output $WORKDIR/lead-edgar.json

# Investigation reports (if populated)
uv run uv run python tools/query_investigations.py search "<TARGET>" --limit 10 --output $WORKDIR/lead-investigations.json
```

This is especially important when:
- A lead involves a person not well-covered in Epstein datasets
- A lead involves an international entity or jurisdiction
- A lead connects to broader patterns (banking fraud, intelligence ops, etc.)

### 5. Record Findings
For each confirmed discovery (all provenance fields required by hooks):
```bash
uv run python tools/findings_tracker.py add \
    --target "<TARGET_NAME>" \
    --summary "One-line summary of what the evidence shows" \
    --type communication \
    --evidence EFTA02XXXXXX \
    --claim-type paraphrase \
    --source-quote "EFTA02XXXXXX:exact text from source supporting this claim" \
    --sources doj_vol11 lmsband \
    --confidence high \
    --date "2017-03-15" \
    --lead-id <LEAD_ID>
```

**Claim types** (hooks enforce this):
- `direct_quote` — verbatim from source (can be `confirmed`)
- `paraphrase` — agent summary of source (max `high`)
- `inference` — agent conclusion from evidence (max `medium`)
- `synthesis` — combined multiple sources (max `medium`)

**For each finding, note its narrative potential:**
- Is this an **infrastructure reveal**? (Shows an invisible mechanism — the SAR waterfall, the liability chain, the compliance cascade)
- Is this a **counterintuitive fact**? (Contradicts what most people would assume — "the compliance committee approved continuing")
- Is this a **missing document**? (What should exist but doesn't — absent SARs, email gaps, missing filings)
- Is this a **concrete-first anchor**? (A specific, vivid instance that would make a good entry point for explaining a broader pattern)

**When completing a lead**, identify the single most article-worthy finding — the one that would make a reader stop and think. Note it in the lead completion summary. This seeds future `/write-article` work.

If the finding reveals a relationship:
```bash
uv run python tools/findings_tracker.py connect \
    --person-a "<PERSON_A>" --person-b "<PERSON_B>" \
    --type financial --strength strong \
    --evidence EFTA02XXXXXX \
    --finding-id <FINDING_ID>
```

### 5b. Register Entities, Roles & Relations

**CRITICAL**: When you discover any new entity (LLC, trust, foundation, law firm, bank, shell company), person role, or entity relationship, register it in the structured entity tables. Findings narratives are not enough — the entity tables power cross-referencing and network analysis.

```bash
# 1. Check if entity already exists
uv run uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('SELECT id, name, entity_type FROM entities WHERE name LIKE ?', ('%ENTITY_NAME%',)).fetchall()
for r in rows: print(r)
"

# 2. If not found, register it
uv run uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entities (name, entity_type, jurisdiction, status, source, notes) VALUES (?, ?, ?, ?, ?, ?)',
    ('Entity Name', 'type', 'jurisdiction', 'active', 'source_ref', 'notes'))
db.commit()
print('Entity ID:', db.execute('SELECT last_insert_rowid()').fetchone()[0])
"
# entity_type: llc, trust, foundation, law_firm, bank, shell_company, nonprofit, corporation, investment_fund, government
# jurisdiction: ny, fl, nm, usvi, bvi, de, uk, etc.

# 3. Register person roles at entity
uv run uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_roles (entity_id, person_name, role, date_start, date_end, source) VALUES (?, ?, ?, ?, ?, ?)',
    (ENTITY_ID, 'Person Name', 'role', '2010-01', '2019-07', 'EFTA02XXXXXX'))
db.commit()
"
# role: officer, director, trustee, secretary, vp, president, registered_agent, partner, counsel, beneficiary, signatory

# 4. Register entity addresses
uv run uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_addresses (entity_id, address, address_type, date_observed, source) VALUES (?, ?, ?, ?, ?)',
    (ENTITY_ID, '457 Madison Ave, New York, NY 10022', 'registered', '2019', 'ny_sos'))
db.commit()
"

# 5. Register entity-to-entity relationships
uv run uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_relations (entity_a_id, entity_b_id, relation_type, description, source) VALUES (?, ?, ?, ?, ?)',
    (ENTITY_A_ID, ENTITY_B_ID, 'funds', 'Enhanced Education donated $150K to IPI', 'EFTA02XXXXXX'))
db.commit()
"
# relation_type: owns, controls, funds, shares_officer, subsidiary, successor, shares_address, client_of, banks_with
```

**When to register:**
- Every LLC, trust, foundation, or corporate entity mentioned in findings
- Every person-role relationship (director, officer, trustee, counsel, etc.)
- Every known address for an entity
- Every entity-to-entity relationship (funding, ownership, shared officers)
- Law firms and banks that appear as institutional actors (not just mentioned in passing)

### 5b. Record Career Arcs

When employment history is discovered during investigation, record career arcs:

```bash
uv run uv run python tools/pillar_tracker.py arc \
    --person "<NAME>" --pillar "<INSTITUTION>" \
    --role "<ROLE>" --seniority <junior|mid|senior|leadership|founder> \
    --start "<YEAR>" --end "<YEAR>" \
    --source "<EVIDENCE_REF>"
```

Check registered pillars: `uv run uv run python tools/pillar_tracker.py list --type banking` (or legal, government, etc.)

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

### 7. Complete the Lead
```bash
uv run python tools/lead_tracker.py complete <ID> --findings "Summary of what was found and what remains unknown"
```

If the lead is a dead end:
```bash
uv run python tools/lead_tracker.py dead-end <ID> "Explanation of why"
```

If blocked (e.g., Neo4j not running, API down):
```bash
uv run python tools/lead_tracker.py block <ID> "Neo4j not available for ICIJ cross-reference"
```

## Investigative Mindset

**Read `research/INVESTIGATIVE_METHODOLOGY.md` if you haven't already.** You are an investigator, not a search engine.

### Before Touching Any Tool

1. **Form hypotheses first.** Read the lead's description and your training data knowledge. What do you expect to find? What would confirm this lead? What would refute it? Write your hypotheses as a note on the lead.

2. **Simulate the person.** If this lead involves a person, ask: What role does this target play in the investigation thread? What are their incentives? What would confirmation look like? What was their public position vs. private behavior? The gap is where the story lives.

3. **Check the timeline.** What else was happening in the world when this event occurred? A Dec 2016 email about a Russian ambassador means something very different than a Dec 2014 one.

4. **Think about what's missing.** If you find 5 emails between two people in 2017 but zero in 2018-2019, the gap may be more significant than the emails. Did they move to ProtonMail? Did the relationship end? Did they start using intermediaries?

### During Investigation

- **Follow the incentive structure.** Money flows reveal truth that words obscure. When you find a financial transaction, ask: what service could possibly justify this amount?
- **Look for the "both sides" pattern.** Epstein maintained relationships with opposing parties simultaneously. Map contradictions — they reveal his actual strategy.
- **Try alternate search terms.** Transliterations, maiden names, entity abbreviations, coded language. A search for "craft purchase" finds what "boat" or "yacht" misses.
- **Analyze tone and context**, not just frequency. 10 formal emails may reveal less than 3 intimate ones with financial requests.

### When Recording Findings

- **Distinguish fact from inference.** "Email shows wire transfer of $18M" is a fact. "This was payment for diplomatic access" is an inference. Label them differently.
- **Note what you didn't find.** "Searched 5 sources for Churkin-Epstein financial links, found none" is itself a finding.
- **End with new hypotheses.** Every completed lead should spawn questions, not just answers.

### Thread Awareness

- **Do NOT close a lead because you didn't find direct Epstein connections.** Follow the thread — if the target connects to other interesting actors or reveals network infrastructure, that's valuable. A Mega Group lead is about the Mega Group, not about Epstein.
- If the lead has a `thread_id`, assign new findings to the same thread with `--thread-id N`.
- If you discover something relevant to a different thread, create a new lead in that thread.

## Operational Principles

- **Be thorough**: Search at least 3-4 local sources before completing
- **Cite evidence**: Always include EFTA IDs, file paths, or source references
- **Don't duplicate**: Check search_log before querying, check existing findings before creating
- **Prefer EFTA IDs** as canonical evidence references when available
- **Create follow-ups generously**: If something looks interesting, create a lead for it
- **Document dead ends**: A dead end is still valuable — it prevents re-investigation
- **Be curious and proactive about infrastructure**: As you investigate, look for data sources we don't have tools for. If you find a government database, corporate registry, or public dataset that would help the investigation, create an infrastructure request via `uv run uv run python tools/infra_tracker.py add --title "..." --type new_source --description "..." --source-name "..." --priority medium --discovered-by "agent:pursue-lead"`. If the source has a free API and you can build the tool quickly, do it — probe the endpoint first, confirm it works, then write the tool and update CLAUDE.md.
- **Extend existing tools when gaps appear**: If a query tool doesn't cover a jurisdiction you need, or a search tool misses a variant you tried manually, create an infra request with `--type tool_improvement`. Small enhancements compound across all future investigations.

## Context Management

This skill is designed to work as a **standalone command in its own CC instance**. For wave execution, run multiple CC instances each running `/pursue-lead`:

```
Terminal 1: claude → /pursue-lead
Terminal 2: claude → /pursue-lead
Terminal 3: claude → /pursue-lead
```

All instances write to shared `investigation.db` (WAL mode handles concurrent writes).

### Output Discipline
- **Use `--output $WORKDIR/...` on ALL search commands** to keep context lean
- **Do NOT `cat` or `Read` full document text** — extract relevant quotes only
- **Record findings as you go**, not in a batch at the end

### Tool Bug Reporting
If you encounter bugs in CLI tools (crashes, incorrect output, missing features), submit them to the infra queue:
`uv run uv run python tools/infra_tracker.py add --title "Bug: <description>" --type tool_improvement --priority high --description "<details including the error traceback>"`

### Report File (when running as sub-agent)
If spawned by another skill (e.g., wave orchestrator), write a report at completion:

```bash
# Write to $WORKDIR/report-lead-<LEAD_ID>.md
```

Report format:
```markdown
# Lead #<ID> Report: <title>
## Status: completed | blocked | dead_end
## Findings Added: [count] (IDs: ...)
## Connections Added: [count]
## Entities Registered: [count]
## Key Discoveries
- [1-2 sentence summary per finding]
## Gaps / Follow-up Needed
- [items that couldn't be resolved]
## Leads Spawned: [count] (IDs: ...)
```
