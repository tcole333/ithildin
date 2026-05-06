---
name: trace-entity
description: Follow corporate/financial entity through registrations, filings, and offshore records
user_invocable: true
---

# /trace-entity

**LAYER 1: RESEARCH AGENT** — This is a fact-gathering skill. Document corporate structures, officers, filings, and jurisdictions. Do not theorize about the purpose of structures — record what exists and let Layer 2 analysis agents interpret patterns. Record negative results from every registry checked.

Trace a corporate or financial entity through all available data sources to map ownership chains, financial flows, and jurisdictional connections.

## Arguments

- Required: entity name (e.g., `/trace-entity Liquid Funding Ltd`)

**Refer to `research/INVESTIGATIVE_METHODOLOGY.md` for the investigative mindset, especially the sections on deception patterns and incentive structures.**

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

### Jurisdiction Trigger: United Kingdom

If the entity is UK-incorporated, has a UK company number, uses a UK registered office, or the search surface indicates a UK corporate footprint, **Companies House is mandatory**. Do not treat a UK trace as complete without checking:

```bash
python tools/ingest_uk_companies_house.py search "<ENTITY>" --output $WORKDIR/trace-uk-search.json
python tools/ingest_uk_companies_house.py company <COMPANY_NUMBER> --output $WORKDIR/trace-uk-company.json
python tools/ingest_uk_companies_house.py officers <COMPANY_NUMBER> --output $WORKDIR/trace-uk-officers.json
python tools/ingest_uk_companies_house.py psc <COMPANY_NUMBER> --output $WORKDIR/trace-uk-psc.json
python tools/ingest_uk_companies_house.py filings <COMPANY_NUMBER> --output $WORKDIR/trace-uk-filings.json
```

If officers or PSC names are ambiguous, run:
```bash
python tools/ingest_uk_companies_house.py officer-search "<PERSON_NAME>" --output $WORKDIR/trace-uk-officer-search.json
```

Record negative results explicitly if the API returns no match.

## Investigative Context

Corporate entities within an investigation network are rarely random bureaucratic structures. Every layer of corporate complexity is a layer of obfuscation. When tracing an entity, always ask:

- **What is this entity hiding?** A BVI shell company with a single director and no visible operations exists for one purpose: opacity. What flows through it?
- **Why this jurisdiction?** US Virgin Islands, British Virgin Islands, Bermuda, Cayman Islands, Delaware — each has specific advantages for specific types of concealment. The jurisdiction choice reveals the intent.
- **Who are the real beneficiaries?** Named officers are often nominees (lawyers, trust company employees). The beneficial owners are the intelligence. Follow the chain until you find a natural person.
- **When was it created relative to events?** An entity incorporated 2 weeks before a large transfer, then dissolved after — that's a single-purpose vehicle. Map entity lifecycle against known events.
- **What other entities share the same officers, addresses, or intermediaries?** Check known_addresses from the investigation profile. Common addresses and common registered agents reveal entity clusters that operate as a single economic unit.

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
python tools/findings_tracker.py search "<ENTITY>" --output $WORKDIR/trace-findings.json
python tools/lead_tracker.py search "<ENTITY>" --output $WORKDIR/trace-leads.json
ls research/entities/
```

### 2. ICIJ Offshore Leaks (Primary)
```bash
python tools/query_icij.py search "<ENTITY>"
python tools/query_icij.py officers "<ENTITY>"
python tools/query_icij.py connections "<ENTITY>" --depth 2
```

If matches found, trace the full graph:
- Who are the officers/directors?
- What intermediary set it up?
- What jurisdiction?
- What other entities share the same officers?
- Which leak (Panama Papers, Paradise Papers, etc.) exposed it?

### 3. DOJ Records
```bash
python tools/query_doj.py search "<ENTITY>" --limit 30 --output $WORKDIR/trace-doj.json
python tools/duggan_search.py "<ENTITY>" -n 30 --output $WORKDIR/trace-duggan.json
```

Look for:
- Incorporation documents
- Financial transfers mentioning the entity
- Legal filings referencing it

### 4. LMSBAND / Unified DB
```bash
python tools/query_lmsband.py search "<ENTITY>" --limit 20 --output $WORKDIR/trace-lmsband.json
python tools/query_lmsband.py entities "<ENTITY>" --output $WORKDIR/trace-lmsband-ent.json
python tools/query_unified.py docs "<ENTITY>" --limit 20 --output $WORKDIR/trace-unified-docs.json
python tools/query_unified.py triples --target "<ENTITY>" --output $WORKDIR/trace-unified-triples.json
```

### 5. Entity Co-occurrence
```bash
python tools/query_lmsband.py cooccurrence "<ENTITY>" --top 20 --output $WORKDIR/trace-lmsband-coocc.json
python tools/query_unified.py cooccurrence "<ENTITY>" --top 20 --output $WORKDIR/trace-unified-coocc.json
```

### 6. Corporate Registries & External APIs
```bash
# Unified corporate registry (FL, NY, more)
python tools/query_registry.py search "<ENTITY>" --output $WORKDIR/trace-registry.json
python tools/query_registry.py officers "<ENTITY>" --output $WORKDIR/trace-registry-officers.json
python tools/query_registry.py address "<KNOWN_ADDRESS>" --output $WORKDIR/trace-registry-addr.json
python tools/query_registry.py agent "<ENTITY>" --output $WORKDIR/trace-registry-agent.json
python tools/query_registry.py filings <registry_entity_id> --output $WORKDIR/trace-registry-filings.json

# UCC Filings (secured transactions, liens, creditor relationships)
python tools/query_registry.py ucc-search "<ENTITY>" --output $WORKDIR/trace-ucc.json
python tools/query_registry.py ucc-party "<ENTITY>" --role debtor --output $WORKDIR/trace-ucc-debtor.json
python tools/query_registry.py ucc-party "<ENTITY>" --role secured --output $WORKDIR/trace-ucc-secured.json
python tools/query_registry.py ucc-collateral "aircraft" --output $WORKDIR/trace-ucc-collateral.json

# DEPRECATED (March 2026): OCCRP removed free tier in 2026. Tool returns 0 results without paid API key. Skip Aleph queries until access is restored.
# OCCRP Aleph (global corporate registries, leaks)
python tools/query_aleph.py search "<ENTITY>" --schema Company --output $WORKDIR/trace-aleph-company.json
python tools/query_aleph.py search "<ENTITY>" --schema Organization --output $WORKDIR/trace-aleph-org.json

# CourtListener (legal proceedings)
python tools/query_courtlistener.py search "<ENTITY>" --output $WORKDIR/trace-cl.json
python tools/query_courtlistener.py party "<ENTITY>" --output $WORKDIR/trace-cl-party.json

# IRS 990 (if nonprofit — comprehensive view with officers, financials, grants)
python tools/query_990.py lookup <EIN> --output $WORKDIR/trace-990-lookup.json   # if EIN known
python tools/query_990.py search "<ENTITY>" --output $WORKDIR/trace-990.json     # if searching by name
python tools/query_990.py officers <EIN> --output $WORKDIR/trace-990-officers.json
python tools/query_990.py financials <EIN> --output $WORKDIR/trace-990-financials.json

# UK Companies House (mandatory for UK entities/officers/addresses)
python tools/ingest_uk_companies_house.py search "<ENTITY>" --output $WORKDIR/trace-uk-search.json
python tools/ingest_uk_companies_house.py officer-search "<ENTITY>" --output $WORKDIR/trace-uk-officer-search.json
```

### 6b. External APIs & Web Research
```bash
# LittleSis (relationship/board mapping)
python tools/query_littlesis.py search "<ENTITY>" --output $WORKDIR/trace-littlesis.json
python tools/query_littlesis.py relationships <ID> --category 10 --output $WORKDIR/trace-littlesis-ownership.json

# SEC EDGAR (mentions in public filings + ownership disclosures)
python tools/query_edgar.py lookup "<ENTITY>" --output $WORKDIR/trace-edgar-lookup.json
python tools/query_edgar.py search "<ENTITY>" --size 10 --facets --output $WORKDIR/trace-edgar.json
python tools/query_edgar.py search "<ENTITY>" --forms "SC 13D" --output $WORKDIR/trace-edgar-13d.json
python tools/query_edgar.py filings <CIK> --form "DEF 14A" --output $WORKDIR/trace-edgar-proxy.json

# FAA Registry (if aircraft/aviation entity)
python tools/ingest_faa.py search "<ENTITY>" --output $WORKDIR/trace-faa.json

# Investigation reports (if populated)
python tools/query_investigations.py search "<ENTITY>" --limit 10 --output $WORKDIR/trace-investigations.json
```

```bash
# NYC property records (if NYC entity)
python tools/query_acris.py party "<ENTITY>" --output $WORKDIR/trace-acris.json
python tools/query_acris.py batch-entities   # Cross-ref all investigation entities

# FEC (donations from entity employees)
python tools/query_fec.py employer "<ENTITY>" --output $WORKDIR/trace-fec.json

# Lobbying (was entity a client or registrant?)
python tools/query_lobbying.py client "<ENTITY>" --output $WORKDIR/trace-lobbying-client.json
python tools/query_lobbying.py registrant "<ENTITY>" --output $WORKDIR/trace-lobbying-registrant.json

# FARA (foreign agent registration)
python tools/query_fara.py search "<ENTITY>" --output $WORKDIR/trace-fara.json

# Federal contracts & grants (USAspending — no auth)
python tools/query_usaspending.py awards "<ENTITY>" --output $WORKDIR/trace-usaspending-contracts.json
python tools/query_usaspending.py awards "<ENTITY>" --grants --output $WORKDIR/trace-usaspending-grants.json
python tools/query_usaspending.py subawards "<ENTITY>" --output $WORKDIR/trace-usaspending-subs.json
python tools/query_usaspending.py timeline "<ENTITY>" --group fiscal_year --output $WORKDIR/trace-usaspending-timeline.json

# SAM.gov API (entity registration, exclusions — requires SAM_API_KEY)
python tools/query_sam.py entity "<ENTITY>" --output $WORKDIR/trace-sam-entity.json
python tools/query_sam.py exclusions "<ENTITY>" --output $WORKDIR/trace-sam-exclusions.json

# SAM.gov Bulk (874K entities, 167K exclusions — local SQLite, no API limit)
python tools/ingest_sam.py entity "<ENTITY>" --output $WORKDIR/trace-sam-bulk-entity.json
python tools/ingest_sam.py exclusion "<ENTITY>" --output $WORKDIR/trace-sam-bulk-excl.json
```

Web research:
- WebSearch: `"<ENTITY>" site:opencorporates.com`
- WebSearch: `"<ENTITY>" "beneficial owner" OR "registered agent"`
- Check `research/RELATED_INVESTIGATIONS.md` for relevant historical parallels
- Check `research/OSINT_RESOURCES.md` for specialized registry tools

### 7. Record Findings
For each entity discovered in the ownership chain (provenance fields required):
```bash
python tools/findings_tracker.py add \
    --target "<ENTITY>" \
    --type financial \
    --summary "What the evidence shows" \
    --evidence <IDS> \
    --claim-type <direct_quote|paraphrase|inference> \
    --source-quote "<ID>:exact text from source" \
    --sources <SOURCE_NAMES> \
    --confidence <LEVEL>
```

Record ownership/corporate connections:
```bash
python tools/findings_tracker.py connect \
    --person-a "<ENTITY>" --person-b "<OWNER/OFFICER>" \
    --type corporate --strength strong \
    --evidence <IDS>
```

### 7b. Register Entities, Roles & Relations in DB

**CRITICAL**: Register all discovered entities/roles/addresses/relations with `tools/entity_tracker.py`.

```bash
# Lookup first
uv run python tools/entity_tracker.py lookup --name "Entity Name"

# Add entity if missing
uv run python tools/entity_tracker.py add-entity   --name "Entity Name"   --entity-type ltd   --jurisdiction bvi   --status active   --source "source_ref"   --notes "ownership chain node"

# Add officers/directors
uv run python tools/entity_tracker.py add-role   --entity-id <ENTITY_ID>   --person-name "Person Name"   --role "director"   --date-start "2010-01"   --date-end "2019-07"   --source "EFTA02XXXXXX"

# Add addresses
uv run python tools/entity_tracker.py add-address   --entity-id <ENTITY_ID>   --address "Address"   --address-type registered   --date-observed "2019"   --source "source"

# Add entity-to-entity relationships
uv run python tools/entity_tracker.py add-relation   --entity-a-id <PARENT_ID>   --entity-b-id <CHILD_ID>   --relation-type owns   --description "Parent holds 100% of subsidiary"   --source "source"

# Inspect consolidated entity view
uv run python tools/entity_tracker.py show <ENTITY_ID>
```

Use allowed entity types: `person, llc, inc, ltd, corporation, pllc, trust, foundation, nonprofit, partnership, fund, association, government, pac, agency, joint_venture, shell, unknown`.

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

## Connection to Investigation Network
- How it links back to the primary subject or known associates

## Source Coverage
- [x] ICIJ — node_id XXXXX
- [x] DOJ Vol 11 — X hits
- [ ] SEC EDGAR — not searched
```

### 9. Analyze the Structure

Before spawning follow-ups, step back and assess the overall corporate architecture:

- **Is this a standalone entity or part of a cluster?** Investigation subjects often use dozens of entities. Map which entities share addresses, officers, or intermediaries to identify the cluster. Cross-reference known_addresses and key_persons from the investigation profile.
- **What's the money trail?** Even partial financial data (a wire amount, a bank name, a transaction date) is valuable. Financial flows between entities reveal the real purpose behind the corporate structure.
- **Does the timeline make sense?** Entity created in 2005, first transaction in 2012, dissolved in 2019 — the gaps tell a story.
- **Who benefits from the opacity?** The person most motivated to hide their connection to this entity is often the most important lead.

### 9b. Exhaustive Lateral Exploration

When tracing an entity, perform exhaustive lateral checks:
1. **Registered address** -- search for all other entities at that address
2. **Each officer** -- search for all other entities they serve as officer
3. **Registered agent** -- search for all other entities using that agent (filter mass-market agents like CT Corporation, CSC, NRAI)
4. **Formation date** -- search for entities formed the same week by the same agent/officer
5. **Document ALL lateral findings**, even if most seem unrelated -- they may surface connections later

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
