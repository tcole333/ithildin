---
name: investigate-person
description: Comprehensive investigation of a named individual across all sources
user_invocable: true
---

# /investigate-person

Deep-dive investigation of a named individual across all available data sources.

## Arguments

- Required: person name (e.g., `/investigate-person Samantha Rose Stein`)

**Read `research/INVESTIGATIVE_METHODOLOGY.md` before your first investigation.** This skill encodes that methodology.

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

## Process

### Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths and report files throughout this session.

### 0. Know Your Subject Before You Search

**This is the most important step.** Before querying any database, use your training data:

- **Who is this person in the world?** Public biography, position, known affiliations. A Goldman Sachs General Counsel is different from an obscure PR consultant. The investigation approach changes based on the person's power, visibility, and incentive structure.
- **What's their known role in the network?** This may be a direct relationship to the primary_subject, or a connection through threads defined in the investigation profile. Published reporting, court filings, media coverage — what's the public narrative? Your job is to test whether the documentary evidence supports, contradicts, or complicates that narrative.
- **Form explicit hypotheses.** Write them down as a lead note:
  - "Hypothesis: the relationship was transactional — Subject A wanted institutional access, Subject B wanted social/political connections through the network"
  - "If correct, I'd expect to see: emails about introductions, invitations to social events, and potentially financial favors"
  - "If wrong, I'd expect to see: purely social/casual correspondence with no ask patterns"

**Simulate the person:**
- What did they want from the network? (access, legitimacy, information, money, political cover, protection)
- What could the network offer them? (money, connections, intelligence, introductions, discretion)
- What was their public position vs. their private behavior? The gap is where the story lives.
- What were they afraid of? What would exposure cost them specifically? (Career, marriage, freedom, political position)
- Where do they sit in the network topology? Hub node? Intermediary? Peripheral? Which threads do they connect?

**Check international context.** For Israeli connections, consider Hebrew-language media coverage. For Russian connections, understand *siloviki* vs. *oligarch* dynamics. For Gulf connections, map the Saudi-Qatari rivalry and MBS consolidation. For European connections, consider WEF/IPI/Nordic financial networks. Try native-language name forms and alternate transliterations in searches.

### 0b. Web Background Research

Before diving into investigation-specific databases, research the subject's public profile:

- WebSearch: `"<NAME>"` — basic biography, current position
- WebSearch: `"<NAME>" {primary_subject}` — known public reporting on connection (use primary_subject from the investigation profile)
- WebSearch: `"<NAME>" investigation lawsuit scandal` — legal/reputational issues
- WebSearch: `"<NAME>" site:littlesis.org` — pre-mapped relationships

If the person has a Wikipedia page, WebFetch it for structured biographical data.
If they have a corporate affiliation, WebFetch the company's SEC filings page.

Also check reference files for historical context:
- `research/RELATED_INVESTIGATIONS.md` — relevant historical precedents
- `research/OSINT_RESOURCES.md` — additional tools and techniques

Record notable web findings as lead notes before proceeding to dataset searches.

### 1. Check Existing Knowledge
```bash
# Check if we already have findings on this person
python tools/findings_tracker.py list --target "<NAME>" --output $WORKDIR/inv-findings.json

# Check for existing leads
python tools/lead_tracker.py search "<NAME>" --output $WORKDIR/inv-leads.json

# Check if person has a research file
ls research/persons/
```

### 2. Search All Sources
Run `/search-all-sources <NAME>` to get comprehensive results across all datasets.

Additionally, search for known aliases, maiden names, alternate transliterations, and associated email addresses if known. Try both formal names ("Terje Rod-Larsen") and informal references ("Terje", "Rod-Larsen", "TRL").

### 3. Entity Co-occurrence Analysis
```bash
# Who appears alongside this person?
python tools/query_lmsband.py cooccurrence "<NAME>" --top 30 --output $WORKDIR/inv-lmsband-coocc.json
python tools/query_unified.py cooccurrence "<NAME>" --top 30 --output $WORKDIR/inv-unified-coocc.json

# What are the RDF triples involving this person?
python tools/query_unified.py triples --actor "<NAME>" --limit 30 --output $WORKDIR/inv-unified-triples-actor.json
python tools/query_unified.py triples --target "<NAME>" --limit 30 --output $WORKDIR/inv-unified-triples-target.json
```

### 3b. LittleSis Relationship Mapping
```bash
# Pre-mapped relationships with amounts, dates, categories
python tools/query_littlesis.py search "<NAME>" --output $WORKDIR/inv-littlesis.json
# If found, get their entity ID and pull relationships:
python tools/query_littlesis.py relationships <ID> --limit 50 --output $WORKDIR/inv-littlesis-rels.json
python tools/query_littlesis.py relationships <ID> --category 5 --output $WORKDIR/inv-littlesis-donations.json  # Donations
python tools/query_littlesis.py relationships <ID> --category 1 --output $WORKDIR/inv-littlesis-positions.json  # Positions
python tools/query_littlesis.py connections <ID> --output $WORKDIR/inv-littlesis-connections.json
```

### 3c. SEC EDGAR Search
```bash
# Find the person's CIK (if they're a public company insider)
python tools/query_edgar.py lookup "<NAME>" --output $WORKDIR/inv-edgar-lookup.json

# Mentions in SEC filings (proxy statements, 10-K, enforcement)
python tools/query_edgar.py search "<NAME>" --size 20 --facets --output $WORKDIR/inv-edgar-search.json
python tools/query_edgar.py search "<NAME>" "{primary_subject}" --size 10 --output $WORKDIR/inv-edgar-subject.json

# If CIK found — insider transactions reveal ownership positions
python tools/query_edgar.py insider <CIK> --detail --limit 10 --output $WORKDIR/inv-edgar-insider.json

# Read specific filings that look relevant
python tools/query_edgar.py read "<FILING_URL>" --lines 200
```

### 3d. Political, Property & Registration Records
```bash
# FEC donations (political influence mapping)
python tools/query_fec.py donor "<NAME>" --limit 20 --output $WORKDIR/inv-fec-donor.json
python tools/query_fec.py employer "<KNOWN_EMPLOYER>" --output $WORKDIR/inv-fec-employer.json

# NYC ACRIS property records (if NYC connection)
python tools/query_acris.py party "<NAME>" --output $WORKDIR/inv-acris.json

# Federal lobbying disclosures
python tools/query_lobbying.py lobbyist "<NAME>" --output $WORKDIR/inv-lobbying.json

# FARA foreign agent registrations (if foreign connections)
python tools/query_fara.py search "<NAME>" --output $WORKDIR/inv-fara.json

# Federal contracts & grants (companies they lead or are associated with)
python tools/query_usaspending.py awards "<KNOWN_COMPANY>" --output $WORKDIR/inv-usaspending.json
python tools/query_usaspending.py awards "<KNOWN_COMPANY>" --grants --output $WORKDIR/inv-usaspending-grants.json

# SAM.gov exclusions (debarment/suspension check)
python tools/query_sam.py exclusions "<NAME>" --output $WORKDIR/inv-sam-exclusions.json

# SAM.gov Bulk (local SQLite — 874K entities, 167K exclusions, no API limit)
python tools/ingest_sam.py search "<NAME>" --output $WORKDIR/inv-sam-bulk.json
```

### 4. ICIJ Offshore Cross-Reference
If Neo4j is running:
```bash
python tools/query_icij.py search "<NAME>"
python tools/query_icij.py search "<KNOWN_ENTITY>"  # If associated companies known
```

### 5. Email Analysis (if applicable)
```bash
# Check HF parquet for email correspondence
python -c "
import pandas as pd
df = pd.read_parquet('datasets/emails.parquet')  # Use investigation-specific email corpus if available
mask = df.apply(lambda r: '<NAME>'.lower() in str(r).lower(), axis=1)
hits = df[mask]
print(f'Found {len(hits)} emails')
for _, row in hits.head(20).iterrows():
    print(f\"  {row.get('date','?')} | {row.get('from','?')} -> {row.get('to','?')}\")
    print(f\"    Subject: {row.get('subject','?')}\")
"
```

### 6. Record Findings
For each notable discovery (all provenance fields required by hooks):
```bash
python tools/findings_tracker.py add \
    --target "<NAME>" \
    --summary "What the evidence shows — one line" \
    --type <TYPE> \
    --evidence <EFTA_IDS> \
    --claim-type <direct_quote|paraphrase|inference|synthesis> \
    --source-quote "<EFTA_ID>:exact text from source supporting this claim" \
    --sources <DATASETS> \
    --confidence <LEVEL> \
    --date "<DATE>"
```

**Claim type determines max confidence**: `direct_quote` can be `confirmed`, `paraphrase` max `high`, `inference`/`synthesis` max `medium`.

Record connections to known network:
```bash
python tools/findings_tracker.py connect \
    --person-a "<NAME>" --person-b "<CONNECTED_PERSON>" \
    --type <RELATIONSHIP> --strength <LEVEL> \
    --evidence <EFTA_IDS>
```

### 6b. Register Entities, Roles & Relations

**CRITICAL**: When you discover entities (companies, trusts, foundations, law firms) or person-entity relationships during investigation, register them in the structured entity tables — not just in findings text.

```bash
# Check if entity exists
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('SELECT id, name, entity_type FROM entities WHERE name LIKE ?', ('%ENTITY_NAME%',)).fetchall()
for r in rows: print(r)
"

# Register new entity (if not found)
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entities (name, entity_type, jurisdiction, status, source, notes) VALUES (?, ?, ?, ?, ?, ?)',
    ('Entity Name', 'type', 'jurisdiction', 'active', 'source_ref', 'notes'))
db.commit()
print('Entity ID:', db.execute('SELECT last_insert_rowid()').fetchone()[0])
"
# entity_type: llc, trust, foundation, law_firm, bank, shell_company, nonprofit, corporation, investment_fund, government
# jurisdiction: ny, fl, nm, usvi, bvi, de, uk, etc.

# Register person's role at entity
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_roles (entity_id, person_name, role, date_start, date_end, source) VALUES (?, ?, ?, ?, ?, ?)',
    (ENTITY_ID, 'Person Name', 'role', '2010-01', '2019-07', 'EFTA02XXXXXX'))
db.commit()
"
# role: officer, director, trustee, secretary, vp, president, registered_agent, partner, counsel, beneficiary, signatory

# Register entity address
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_addresses (entity_id, address, address_type, date_observed, source) VALUES (?, ?, ?, ?, ?)',
    (ENTITY_ID, '123 Main St, City, ST 00000', 'registered', '2019', 'state_sos'))
db.commit()
"

# Register entity-to-entity relationship
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.execute('INSERT INTO entity_relations (entity_a_id, entity_b_id, relation_type, description, source) VALUES (?, ?, ?, ?, ?)',
    (ENTITY_A_ID, ENTITY_B_ID, 'funds', 'Entity A donated $10M to Entity B via shell LLC', 'SOURCE_REF'))
db.commit()
"
# relation_type: owns, controls, funds, shares_officer, subsidiary, successor, shares_address, client_of, banks_with
```

**Register these as you find them:**
- Every entity the person is connected to (employer, board seat, trust, foundation, shell company)
- The person's specific role at each entity (director, trustee, counsel, etc.) with date range
- Every entity address discovered (registered, mailing, physical)
- Entity-to-entity relationships (funding flows, ownership, shared officers)
- Law firms, banks, and institutional actors (not just passing mentions)

### 6c. Record Career Arcs

When you discover employment history (past or present positions at institutions), record them in the pillar system:

```bash
# Record each institutional affiliation discovered
uv run python tools/pillar_tracker.py arc \
    --person "<NAME>" --pillar "<INSTITUTION>" \
    --role "<ROLE>" --seniority <junior|mid|senior|leadership|founder> \
    --start "<YEAR>" --end "<YEAR>" \
    --exit-type <voluntary|fired|collapse|retirement|government_appointment|indictment|unknown> \
    --source "<EVIDENCE_REF>"
```

Record arcs at: law firms, banks, government agencies, accounting firms, intelligence agencies, academic institutions, media organizations. The pillar must already be registered — check with `uv run python tools/pillar_tracker.py list`.

### 7. Create/Update Person Research File
If the person warrants a dedicated file (10+ findings, active investigation):

Create `research/persons/<name-slug>.md` with:
```markdown
# <Person Name>

## Identity
- Full name, aliases
- Known email addresses
- Known affiliations

## Email Corpus Summary
- Total emails: X (date range)
- Key correspondents
- Key threads

## Key Findings
(List findings with EFTA citations)

## Financial Connections
(If any financial links discovered)

## Network Connections
(Who they connect to across investigation threads)

## Source Coverage
- [x] DugganUSA — X hits
- [x] DOJ Vol 11 — X hits
- [x] LMSBAND — X hits
- [ ] ICIJ — not yet searched
- etc.

## Open Leads
(Links to related open leads)
```

### 8. Analyze What's Missing

Before spawning follow-ups, explicitly consider:

- **Communication gaps**: If emails span 2016-2017 but nothing in 2018-2019, why? ProtonMail migration? Relationship ended? Intermediaries?
- **The "both sides" pattern**: Who else was the primary subject communicating with who has an adversarial relationship to this person? Map the contradictions.
- **Coded language**: Flag any euphemisms or unusual phrasing for deeper analysis. "Craft purchase," "cognitive intervention," "training program" — always question jargon that doesn't fit the context.
- **Intermediary patterns**: If communications go through known gatekeepers or intermediaries (assistants, lawyers, fixers listed in key_persons) instead of directly, ask why this relationship needed a cutout.
- **Timeline context**: Map key events in this person's life against their communication pattern with the primary subject. Promotions, legal troubles, elections, divorces — correlate external events with contact frequency/tone changes.

### 9. Spawn Follow-Up Leads
Create leads for:
- Unexplored connections to new persons discovered in co-occurrence analysis
- Financial trails that need tracing (new entity names, account references, wire amounts)
- Entities associated with this person that haven't been traced through ICIJ
- Sources not yet searched (note in the person's research file)
- **New hypotheses generated by the investigation** — a lead should represent a question, not just a task
- Contradictions or anomalies that need resolution

## Context Management

### Output Discipline
- **Use `--output $WORKDIR/...` on ALL search commands** (already shown in examples above)
- **Do NOT `cat` or `Read` full document text** — extract relevant quotes only
- **Record findings as you go**, not in a batch at the end

### Report File (when running as sub-agent)
If spawned by `/deep-investigate` or a wave orchestrator, write a completion report:

```markdown
---
agent: investigate-person
target: "<Person Name>"
skill: investigate-person
status: completed
findings_added: [count]
connections_added: [count]
entities_registered: [count]
leads_spawned: [count]
---
# Investigation Report: <Person Name>
## Key Discoveries
- [1-2 sentence summary per finding]
## Findings Added
[count] findings (IDs: ...)
## Connections Added
[count] connections
## Entities Registered
[count] entities
## Network Map
- [Key relationships discovered]
## Negative Results
- [Sources searched with zero results]
## Gaps / Follow-up Needed
- [Sources not searched, hypotheses not tested]
## Leads Spawned
[count] leads (IDs: ...)
## Learnings
- [Friction] any tool/source issues encountered
- [Surprise] unexpected findings worth noting
- [Methodology] investigative approach insights
- [Process gap] missing infrastructure
- [Source quality] data source reliability notes
```

Write to `$WORKDIR/report-investigate-<name-slug>.md`.

After writing the report, ingest learnings into the methodology tracker:
```bash
uv run python tools/methodology_tracker.py ingest-report "$WORKDIR/report-investigate-<name-slug>.md" --skill investigate-person
```

During investigation, record tool friction or process issues inline as they occur:
```bash
uv run python tools/methodology_tracker.py add --category friction \
    --description "query_doj.py FTS5 times out for common words" \
    --skill investigate-person --target "<NAME>"
```
