---
name: investigate-person
description: Comprehensive investigation of a named individual across all sources
user_invocable: true
---

# /investigate-person

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Document what you find. Do not theorize, speculate, or apply analytical frameworks. If you notice a pattern, record the raw data — pattern recognition is for Layer 2 analysis agents. Record mundane facts (employer history, addresses, professional affiliations, board seats) even when they don't seem relevant. Record negative results from every source checked.

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

### Jurisdiction Trigger: United Kingdom

If the subject is UK-based, has UK company ties, uses a UK address, or appears as a UK officer/director/PSC, **Companies House is mandatory**. Do not close a UK person trace without checking:

```bash
uv run python tools/ingest_uk_companies_house.py officer-search "<NAME>" --output "$WORKDIR/inv-uk-officer-search.json"
uv run python tools/ingest_uk_companies_house.py search "<NAME>" --limit 20 --output "$WORKDIR/inv-uk-company-search.json"
```

For each relevant company returned, pull:

```bash
uv run python tools/ingest_uk_companies_house.py company <COMPANY_NUMBER> --output "$WORKDIR/inv-uk-company-<COMPANY_NUMBER>.json"
uv run python tools/ingest_uk_companies_house.py officers <COMPANY_NUMBER> --output "$WORKDIR/inv-uk-officers-<COMPANY_NUMBER>.json"
uv run python tools/ingest_uk_companies_house.py psc <COMPANY_NUMBER> --output "$WORKDIR/inv-uk-psc-<COMPANY_NUMBER>.json"
uv run python tools/ingest_uk_companies_house.py filings <COMPANY_NUMBER> --output "$WORKDIR/inv-uk-filings-<COMPANY_NUMBER>.json"
```

Record negative results if the API returns no officer/company matches.

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
uv run python tools/findings_tracker.py list --target "<NAME>" --output $WORKDIR/inv-findings.json

# Check for existing leads
uv run python tools/lead_tracker.py search "<NAME>" --output $WORKDIR/inv-leads.json

# Check if person has a research file
ls research/persons/
```

### 2. Search All Sources
Run `/search-all-sources <NAME>` to get comprehensive results across all datasets.

Additionally, search for known aliases, maiden names, alternate transliterations, and associated email addresses if known. Try both formal names ("Terje Rod-Larsen") and informal references ("Terje", "Rod-Larsen", "TRL").

### 3. Entity Co-occurrence Analysis
```bash
# Who appears alongside this person?
uv run python tools/query_lmsband.py cooccurrence "<NAME>" --top 30 --output $WORKDIR/inv-lmsband-coocc.json
uv run python tools/query_unified.py cooccurrence "<NAME>" --top 30 --output $WORKDIR/inv-unified-coocc.json

# What are the RDF triples involving this person?
uv run python tools/query_unified.py triples --actor "<NAME>" --limit 30 --output $WORKDIR/inv-unified-triples-actor.json
uv run python tools/query_unified.py triples --target "<NAME>" --limit 30 --output $WORKDIR/inv-unified-triples-target.json
```

### 3b. LittleSis Relationship Mapping
```bash
# Pre-mapped relationships with amounts, dates, categories
uv run python tools/query_littlesis.py search "<NAME>" --output $WORKDIR/inv-littlesis.json
# If found, get their entity ID and pull relationships:
uv run python tools/query_littlesis.py relationships <ID> --limit 50 --output $WORKDIR/inv-littlesis-rels.json
uv run python tools/query_littlesis.py relationships <ID> --category 5 --output $WORKDIR/inv-littlesis-donations.json  # Donations
uv run python tools/query_littlesis.py relationships <ID> --category 1 --output $WORKDIR/inv-littlesis-positions.json  # Positions
uv run python tools/query_littlesis.py connections <ID> --output $WORKDIR/inv-littlesis-connections.json
```

### 3c. SEC EDGAR Search
```bash
# Find the person's CIK (if they're a public company insider)
uv run python tools/query_edgar.py lookup "<NAME>" --output $WORKDIR/inv-edgar-lookup.json

# Mentions in SEC filings (proxy statements, 10-K, enforcement)
uv run python tools/query_edgar.py search "<NAME>" --size 20 --facets --output $WORKDIR/inv-edgar-search.json
uv run python tools/query_edgar.py search "<NAME>" "{primary_subject}" --size 10 --output $WORKDIR/inv-edgar-subject.json

# If CIK found — insider transactions reveal ownership positions
uv run python tools/query_edgar.py insider <CIK> --detail --limit 10 --output $WORKDIR/inv-edgar-insider.json

# Read specific filings that look relevant
uv run python tools/query_edgar.py read "<FILING_URL>" --lines 200
```

### 3d. Political, Property & Registration Records
```bash
# FEC donations (political influence mapping)
uv run python tools/query_fec.py donor "<NAME>" --limit 20 --output $WORKDIR/inv-fec-donor.json
uv run python tools/query_fec.py employer "<KNOWN_EMPLOYER>" --output $WORKDIR/inv-fec-employer.json

# Reproducible property -> recorder -> court plan
uv run python tools/public_records_search_plan.py "<NAME>" \
  --address "<KNOWN_ADDRESS>" \
  --output "$WORKDIR/inv-public-record-plan.json"

# Normalized property and state/local-court observations
uv run python tools/query_property.py owner "<NAME>" \
  --output "$WORKDIR/inv-property-owner.json"
uv run python tools/query_property.py address "<KNOWN_ADDRESS>" \
  --output "$WORKDIR/inv-property-address.json"
uv run python tools/query_state_courts.py search "<NAME>" \
  --output "$WORKDIR/inv-state-courts.json"

# NYC ACRIS recorder records when the plan identifies a NYC connection
uv run python tools/query_acris.py party "<NAME>" --output $WORKDIR/inv-acris.json

# Federal lobbying disclosures
uv run python tools/query_lobbying.py lobbyist "<NAME>" --output $WORKDIR/inv-lobbying.json

# FARA foreign agent registrations (if foreign connections)
uv run python tools/query_fara.py search "<NAME>" --output $WORKDIR/inv-fara.json

# Federal contracts & grants (companies they lead or are associated with)
uv run python tools/query_usaspending.py awards "<KNOWN_COMPANY>" --output $WORKDIR/inv-usaspending.json
uv run python tools/query_usaspending.py awards "<KNOWN_COMPANY>" --grants --output $WORKDIR/inv-usaspending-grants.json

# SAM.gov exclusions (debarment/suspension check)
uv run python tools/query_sam.py exclusions "<NAME>" --output $WORKDIR/inv-sam-exclusions.json

# SAM.gov Bulk (local SQLite — 874K entities, 167K exclusions, no API limit)
uv run python tools/ingest_sam.py search "<NAME>" --output $WORKDIR/inv-sam-bulk.json

# UK Companies House (mandatory for UK-linked subjects)
uv run python tools/ingest_uk_companies_house.py officer-search "<NAME>" --output "$WORKDIR/inv-uk-officer-search.json"
uv run python tools/ingest_uk_companies_house.py search "<NAME>" --limit 20 --output "$WORKDIR/inv-uk-company-search.json"
```

Follow the public-record plan's source capabilities with the matching direct
adapter for addresses, parcels, instruments, cases, docket entries, and
documents. For an account, formal feed, request, paid product, or physical
office route, render the concrete work with `public_records_actions.py plan`,
passing the source ID, operation, and selector from the plan. Preserve route
and barrier states in source coverage rather than recording them as zero hits.

### Nonprofit Board Positions (990)

Check if the person serves on nonprofit boards — this reveals institutional affiliations not visible in corporate registries:

```bash
uv run python tools/query_990.py officer-search "<NAME>" --output $WORKDIR/inv-990-officers.json
```

If found on 2+ nonprofits, run a quick grant flow check for each:
```bash
uv run python tools/query_990.py flow <EIN> --depth 1 --min-amount 100000 --output $WORKDIR/inv-990-flow-<EIN>.json
```

Record each nonprofit board position as a finding with `--type relationship --sources 990`.

### 4. ICIJ Offshore Cross-Reference

Use the official ICIJ remote service. Review reconciliation candidates, then
use an exact numeric node ID for entity details or first-hop traversal:

```bash
uv run python tools/query_icij.py search "<NAME>" --output "$WORKDIR/inv-icij-person.json"
uv run python tools/query_icij.py search "<KNOWN_ENTITY>" --type Entity \
  --output "$WORKDIR/inv-icij-entity.json"
uv run python tools/query_icij.py connections <EXACT_NODE_ID> \
  --output "$WORKDIR/inv-icij-connections.json"
```

### 5. Email Analysis (if applicable)
```bash
# Check HF parquet for email correspondence
uv run python -c "
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
uv run python tools/findings_tracker.py add \
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
uv run python tools/findings_tracker.py connect \
    --person-a "<NAME>" --person-b "<CONNECTED_PERSON>" \
    --type <RELATIONSHIP> --strength <LEVEL> \
    --evidence <EFTA_IDS>
```

### 6b. Register Entities, Roles & Relations

**CRITICAL**: When you discover entities (companies, trusts, foundations, law firms) or person-entity relationships during investigation, register them in the structured entity tables — not just in findings text.

```bash
# Resolve before creating; add-entity performs near-duplicate matching too.
uv run python tools/entity_tracker.py lookup \
    --name "Entity Name" \
    --output "$WORKDIR/inv-entity-lookup.json"

# Register only if lookup did not resolve the entity.
uv run python tools/entity_tracker.py add-entity \
    --name "Entity Name" \
    --entity-type unknown \
    --jurisdiction "jurisdiction" \
    --status active \
    --source "SOURCE_REF" \
    --notes "Why this entity matters"
# Allowed entity types: person, llc, inc, ltd, corporation, pllc, trust,
# foundation, nonprofit, partnership, fund, association, government, pac,
# agency, joint_venture, shell, unknown.

# Register the person's role at the resolved entity ID.
uv run python tools/entity_tracker.py add-role \
    --entity-id <ENTITY_ID> \
    --person-name "Person Name" \
    --role "director" \
    --date-start "2010-01" \
    --date-end "2019-07" \
    --source "EFTA02XXXXXX"

# Register an observed entity address.
uv run python tools/entity_tracker.py add-address \
    --entity-id <ENTITY_ID> \
    --address "123 Main St, City, ST 00000" \
    --address-type registered \
    --date-observed "2019" \
    --source "SOURCE_REF"

# Register an entity-to-entity relationship. Single quotes preserve currency in zsh.
uv run python tools/entity_tracker.py add-relation \
    --entity-a-id <ENTITY_A_ID> \
    --entity-b-id <ENTITY_B_ID> \
    --relation-type funds \
    --description 'Entity A donated $10M to Entity B via shell LLC' \
    --source "SOURCE_REF"

# Generate explainable links from retained property/instrument/court-party rows.
uv run python tools/public_records_entity_candidates.py generate \
    --output "$WORKDIR/inv-public-record-candidates.json"
uv run python tools/public_records_entity_candidates.py list --status open \
    --name "<NAME>" \
    --output "$WORKDIR/inv-public-record-candidates-for-person.json"
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
## Sources Checked
| Source | Tool Command | Results | Findings Created |
|--------|-------------|---------|-----------------|
| [source] | [tool command used] | [count] | [count] |
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
