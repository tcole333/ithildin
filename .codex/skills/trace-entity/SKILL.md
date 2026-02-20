---
name: trace-entity
description: Follow corporate/financial entity through registrations, filings, and offshore records
---

# /trace-entity

Trace a corporate or financial entity through all available data sources to map ownership chains, financial flows, and jurisdictional connections.

## Arguments

- Required: entity name (e.g., `/trace-entity Liquid Funding Ltd`)

**Refer to `research/INVESTIGATIVE_METHODOLOGY.md` for the investigative mindset, especially the sections on deception patterns and incentive structures.**

## Investigative Context

Corporate entities in the Epstein network are not random bureaucratic structures. Every layer of corporate complexity is a layer of obfuscation. When tracing an entity, always ask:

- **What is this entity hiding?** A BVI shell company with a single director and no visible operations exists for one purpose: opacity. What flows through it?
- **Why this jurisdiction?** US Virgin Islands, British Virgin Islands, Bermuda, Cayman Islands, Delaware — each has specific advantages for specific types of concealment. The jurisdiction choice reveals the intent.
- **Who are the real beneficiaries?** Named officers are often nominees (lawyers, trust company employees). The beneficial owners are the intelligence. Follow the chain until you find a natural person.
- **When was it created relative to events?** An entity incorporated 2 weeks before a large transfer, then dissolved after — that's a single-purpose vehicle. Map entity lifecycle against known events.
- **What other entities share the same officers, addresses, or intermediaries?** Common addresses (457 Madison Ave, etc.) and common registered agents reveal entity clusters that operate as a single economic unit.

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths and report files throughout this session.

### 1. Check Existing Knowledge
```bash
uv run python tools/findings_tracker.py search "<ENTITY>" --output $WORKDIR/trace-findings.json
uv run python tools/lead_tracker.py search "<ENTITY>" --output $WORKDIR/trace-leads.json
ls research/entities/
```

### 2. ICIJ Offshore Leaks (Primary)
```bash
uv run python tools/query_icij.py search "<ENTITY>"
uv run python tools/query_icij.py officers "<ENTITY>"
uv run python tools/query_icij.py connections "<ENTITY>" --depth 2
```

If matches found, trace the full graph:
- Who are the officers/directors?
- What intermediary set it up?
- What jurisdiction?
- What other entities share the same officers?
- Which leak (Panama Papers, Paradise Papers, etc.) exposed it?

### 3. DOJ Records
```bash
uv run python tools/query_doj.py search "<ENTITY>" --limit 30 --output $WORKDIR/trace-doj.json
uv run python tools/duggan_search.py "<ENTITY>" -n 30 --output $WORKDIR/trace-duggan.json
```

Look for:
- Incorporation documents
- Financial transfers mentioning the entity
- Legal filings referencing it

### 4. LMSBAND / Unified DB
```bash
uv run python tools/query_lmsband.py search "<ENTITY>" --limit 20 --output $WORKDIR/trace-lmsband.json
uv run python tools/query_lmsband.py entities "<ENTITY>" --output $WORKDIR/trace-lmsband-ent.json
uv run python tools/query_unified.py docs "<ENTITY>" --limit 20 --output $WORKDIR/trace-unified-docs.json
uv run python tools/query_unified.py triples --target "<ENTITY>" --output $WORKDIR/trace-unified-triples.json
```

### 5. Entity Co-occurrence
```bash
uv run python tools/query_lmsband.py cooccurrence "<ENTITY>" --top 20 --output $WORKDIR/trace-lmsband-coocc.json
uv run python tools/query_unified.py cooccurrence "<ENTITY>" --top 20 --output $WORKDIR/trace-unified-coocc.json
```

### 6. Corporate Registries & External APIs
```bash
# Unified corporate registry (FL, NY, more)
uv run python tools/query_registry.py search "<ENTITY>" --output $WORKDIR/trace-registry.json
uv run python tools/query_registry.py officers "<ENTITY>" --output $WORKDIR/trace-registry-officers.json
uv run python tools/query_registry.py address "<KNOWN_ADDRESS>" --output $WORKDIR/trace-registry-addr.json
uv run python tools/query_registry.py agent "<ENTITY>" --output $WORKDIR/trace-registry-agent.json
uv run python tools/query_registry.py filings <registry_entity_id> --output $WORKDIR/trace-registry-filings.json

# UCC Filings (secured transactions, liens, creditor relationships)
uv run python tools/query_registry.py ucc-search "<ENTITY>" --output $WORKDIR/trace-ucc.json
uv run python tools/query_registry.py ucc-party "<ENTITY>" --role debtor --output $WORKDIR/trace-ucc-debtor.json
uv run python tools/query_registry.py ucc-party "<ENTITY>" --role secured --output $WORKDIR/trace-ucc-secured.json
uv run python tools/query_registry.py ucc-collateral "aircraft" --output $WORKDIR/trace-ucc-collateral.json

# OCCRP Aleph (global corporate registries, leaks)
uv run python tools/query_aleph.py search "<ENTITY>" --schema Company --output $WORKDIR/trace-aleph-company.json
uv run python tools/query_aleph.py search "<ENTITY>" --schema Organization --output $WORKDIR/trace-aleph-org.json

# CourtListener (legal proceedings)
uv run python tools/query_courtlistener.py search "<ENTITY>" --output $WORKDIR/trace-cl.json
uv run python tools/query_courtlistener.py party "<ENTITY>" --output $WORKDIR/trace-cl-party.json

# ProPublica 990 (if nonprofit)
uv run python tools/query_990.py search "<ENTITY>" --output $WORKDIR/trace-990.json
```

### 6b. External APIs & Web Research
```bash
# LittleSis (relationship/board mapping)
uv run python tools/query_littlesis.py search "<ENTITY>" --output $WORKDIR/trace-littlesis.json
uv run python tools/query_littlesis.py relationships <ID> --category 10 --output $WORKDIR/trace-littlesis-ownership.json

# SEC EDGAR (mentions in public filings + ownership disclosures)
uv run python tools/query_edgar.py lookup "<ENTITY>" --output $WORKDIR/trace-edgar-lookup.json
uv run python tools/query_edgar.py search "<ENTITY>" --size 10 --facets --output $WORKDIR/trace-edgar.json
uv run python tools/query_edgar.py search "<ENTITY>" --forms "SC 13D" --output $WORKDIR/trace-edgar-13d.json
uv run python tools/query_edgar.py filings <CIK> --form "DEF 14A" --output $WORKDIR/trace-edgar-proxy.json

# FAA Registry (if aircraft/aviation entity)
uv run python tools/ingest_faa.py search "<ENTITY>" --output $WORKDIR/trace-faa.json

# Investigation reports (if populated)
uv run python tools/query_investigations.py search "<ENTITY>" --limit 10 --output $WORKDIR/trace-investigations.json
```

```bash
# NYC property records (if NYC entity)
uv run python tools/query_acris.py party "<ENTITY>" --output $WORKDIR/trace-acris.json
uv run python tools/query_acris.py batch-entities   # Cross-ref all investigation entities

# FEC (donations from entity employees)
uv run python tools/query_fec.py employer "<ENTITY>" --output $WORKDIR/trace-fec.json

# Lobbying (was entity a client or registrant?)
uv run python tools/query_lobbying.py client "<ENTITY>" --output $WORKDIR/trace-lobbying-client.json
uv run python tools/query_lobbying.py registrant "<ENTITY>" --output $WORKDIR/trace-lobbying-registrant.json

# FARA (foreign agent registration)
uv run python tools/query_fara.py search "<ENTITY>" --output $WORKDIR/trace-fara.json
```

Web research:
- WebSearch: `"<ENTITY>" site:opencorporates.com`
- WebSearch: `"<ENTITY>" "beneficial owner" OR "registered agent"`
- Check `research/RELATED_INVESTIGATIONS.md` for relevant historical parallels
- Check `research/OSINT_RESOURCES.md` for specialized registry tools

### 7. Record Findings
For each entity discovered in the ownership chain (provenance fields required):
```bash
uv run python tools/findings_tracker.py add \
    --target "<ENTITY>" \
    --type financial \
    --summary "What the evidence shows" \
    --evidence <IDS> \
    --claim-type <direct_quote|paraphrase|inference> \
    --source-quote "<ID>:exact text from source" \
    --confidence <LEVEL>
```

Record ownership/corporate connections:
```bash
uv run python tools/findings_tracker.py connect \
    --person-a "<ENTITY>" --person-b "<OWNER/OFFICER>" \
    --type corporate --strength strong \
    --evidence <IDS>
```

### 7b. Register Entities, Roles & Relations in DB

**CRITICAL**: Every entity in the ownership chain, every officer/director, every address, and every entity-to-entity relationship MUST be registered in the structured entity tables. The research file is for narrative; the DB is for cross-referencing.

```bash
# Check if entity exists
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('SELECT id, name, entity_type FROM entities WHERE name LIKE ?', ('%ENTITY_NAME%',)).fetchall()
for r in rows: print(r)
"

# Register new entity
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entities (name, entity_type, jurisdiction, ein, status, source, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
    ('Entity Name', 'type', 'jurisdiction', 'ein_if_known', 'active', 'source_ref', 'notes'))
db.commit()
print('Entity ID:', db.execute('SELECT last_insert_rowid()').fetchone()[0])
"
# entity_type: llc, trust, foundation, law_firm, bank, shell_company, nonprofit, corporation, investment_fund, government
# jurisdiction: ny, fl, nm, usvi, bvi, de, uk, cayman, bermuda, panama, etc.

# Register officers/directors
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_roles (entity_id, person_name, role, date_start, date_end, source) VALUES (?, ?, ?, ?, ?, ?)',
    (ENTITY_ID, 'Person Name', 'director', '2010-01', '2019-07', 'EFTA02XXXXXX'))
db.commit()
"

# Register addresses
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_addresses (entity_id, address, address_type, date_observed, source) VALUES (?, ?, ?, ?, ?)',
    (ENTITY_ID, 'Address', 'registered', '2019', 'source'))
db.commit()
"

# Register entity-to-entity relationships (ownership chains, funding flows)
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_relations (entity_a_id, entity_b_id, relation_type, description, source) VALUES (?, ?, ?, ?, ?)',
    (PARENT_ID, CHILD_ID, 'owns', 'Parent holds 100% of subsidiary', 'source'))
db.commit()
"
# relation_type: owns, controls, funds, shares_officer, subsidiary, successor, shares_address, client_of, banks_with
```

**For every entity in the ownership chain:**
1. Register the entity itself (name, type, jurisdiction, status)
2. Register all known officers/directors with roles and date ranges
3. Register all known addresses (registered agent, mailing, physical)
4. Register parent/child relationships between entities
5. Register funding flows between entities
6. Register shared-officer relationships when the same person appears at multiple entities

### 8. Create Entity Research File
Create `research/entities/<entity-slug>.md`:
```markdown
# <Entity Name>

## Registration
- Jurisdiction:
- Date incorporated:
- Status:
- ICIJ Source: (Panama Papers / Paradise Papers / etc.)

## Officers & Directors
| Name | Role | Period |
|------|------|--------|

## Ownership Chain
(upstream: who owns this entity)
(downstream: what does this entity own)

## Financial Activity
- Known accounts
- Transfer records
- Asset holdings

## Connection to Epstein Network
- How it links back to Epstein or associates

## Source Coverage
- [x] ICIJ — node_id XXXXX
- [x] DOJ Vol 11 — X hits
- [ ] SEC EDGAR — not searched
```

### 9. Analyze the Structure

Before spawning follow-ups, step back and assess the overall corporate architecture:

- **Is this a standalone entity or part of a cluster?** Epstein used dozens of entities (NES LLC, Maple Inc, Financial Trust Company, Liquid Funding, LSJE LLC, etc.). Map which entities share addresses, officers, or intermediaries to identify the cluster.
- **What's the money trail?** Even partial financial data (a wire amount, a bank name, a transaction date) is valuable. Financial flows between entities reveal the real purpose behind the corporate structure.
- **Does the timeline make sense?** Entity created in 2005, first transaction in 2012, dissolved in 2019 — the gaps tell a story.
- **Who benefits from the opacity?** The person most motivated to hide their connection to this entity is often the most important lead.

### 10. Spawn Follow-Up Leads
Create leads for:
- Newly discovered officers/directors who need investigation
- Related entities in the ownership chain
- Financial flows that need tracing (amounts, dates, counterparties)
- Jurisdictions that need further research
- **Entities that share officers or addresses** with this one — the cluster analysis
- **Anomalies**: entities whose stated purpose doesn't match their activity

## Context Management

### Output Discipline
- **Use `--output $WORKDIR/...` on ALL search commands** (already shown in examples above)
- **Do NOT `cat` or `Read` full document text** — extract relevant quotes only
- **Record findings as you go**, not in a batch at the end

### Report File (when running as sub-agent)
If spawned by another skill or a wave orchestrator, write a completion report:

```markdown
# Entity Trace Report: <Entity Name>
## Status: completed | partial | blocked
## Findings Added: [count] (IDs: ...)
## Connections Added: [count]
## Entities Registered: [count]
## Ownership Chain
- [parent] → [entity] → [subsidiaries]
## Key Discoveries
- [1-2 sentence summary per finding]
## Gaps / Follow-up Needed
- [Jurisdictions not searched, officers not investigated]
## Leads Spawned: [count] (IDs: ...)
```

Write to `$WORKDIR/report-trace-<entity-slug>.md`.
