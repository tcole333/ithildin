---
name: trace-entity
description: Follow corporate/financial entity through registrations, filings, and offshore records
user_invocable: true
---

# /trace-entity

**LAYER 1: RESEARCH AGENT** — You MUST read and follow `docs/sources/_preamble.md` before starting. It defines evidence standards, entity registration, and report format.

Trace a corporate or financial entity through all available data sources to map ownership chains, financial flows, and jurisdictional connections.

## Arguments

- Required: entity name (e.g., `/trace-entity Liquid Funding Ltd`)

**Refer to `research/INVESTIGATIVE_METHODOLOGY.md` for deception patterns and incentive structures.**

### Context Loading
```bash
uv run python tools/investigation_context.py show
```

## Investigative Context

Corporate entities within an investigation network are rarely random. Every layer of complexity is a layer of obfuscation. Always ask:

- **What is this entity hiding?** A BVI shell with a single director exists for opacity.
- **Why this jurisdiction?** USVI, BVI, Bermuda, Cayman, Delaware — each has specific advantages.
- **Who are the real beneficiaries?** Named officers are often nominees. Follow until you find a natural person.
- **When was it created relative to events?** Incorporated 2 weeks before a large transfer = single-purpose vehicle.
- **What other entities share officers, addresses, or intermediaries?** Check `known_addresses` from the profile.

## Process

### 0. Session Setup
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Check Existing Knowledge
```bash
uv run python tools/findings_tracker.py search "<ENTITY>" --output $WORKDIR/trace-findings.json
uv run python tools/lead_tracker.py search "<ENTITY>" --output $WORKDIR/trace-leads.json
uv run python tools/entity_tracker.py lookup --name "<ENTITY>"
```

### 2. Source Module Protocol

Read and execute the relevant source modules:

**Primary sources for entity tracing:**
- `docs/sources/aleph-icij.md` — Offshore leaks, ICIJ graph
- `docs/sources/corpus.md` — Investigation corpus
- `docs/sources/registry.md` — Corporate registries (unified + per-state), UCC filings
- `docs/sources/edgar.md` — SEC filings, ownership disclosures
- `docs/sources/usaspending.md` — Federal contracts, SAM, HigherGov
- `docs/sources/courtlistener.md` — Legal proceedings
- `docs/sources/gleif-ds10.md` — LEI hierarchy, financial records
- `docs/sources/990.md` — If nonprofit
- `docs/sources/lobbying.md` — If lobbying client/registrant
- `docs/sources/sanctions.md` — PEP/sanctions check
- `docs/sources/littlesis.md` — Relationship/board mapping
- `docs/sources/acris-ucc-property.md` — Property records, UCC liens
- `docs/sources/offshorealert.md` — Offshore court cases, regulatory actions (if offshore jurisdiction)

**Also search:**
```bash
# Co-occurrence in corpus
uv run python tools/query_lmsband.py cooccurrence "<ENTITY>" --top 20 --output $WORKDIR/trace-coocc.json

# Web research
# WebSearch: "<ENTITY>" site:opencorporates.com
# WebSearch: "<ENTITY>" "beneficial owner" OR "registered agent"
```

### 3. Record Findings

See `docs/sources/_preamble.md` for evidence standards and entity registration commands.

Register ALL entities/roles/addresses/relations with `entity_tracker.py` as you discover them.

### 4. Exhaustive Lateral Exploration

When tracing an entity, perform exhaustive lateral checks:

1. **Registered address** — search for all other entities at that address
2. **Each officer** — search for all other entities they serve as officer
3. **Registered agent** — search for all other entities using that agent (filter mass-market agents like CT Corp, CSC, NRAI)
4. **Formation date** — search for entities formed the same week by the same agent/officer
5. **Document ALL lateral findings** — they may surface connections later

### 5. Analyze the Structure

- **Standalone or cluster?** Map entities sharing addresses, officers, or intermediaries.
- **Money trail**: Even partial financial data is valuable.
- **Timeline sense**: Entity created 2005, first transaction 2012, dissolved 2019 — gaps tell a story.
- **Who benefits from opacity?** Most motivated to hide = most important lead.

### 6. Spawn Follow-Up Leads

Create leads for:
- Newly discovered officers/directors
- Related entities in the ownership chain
- Financial flows needing tracing
- Jurisdictions needing further research
- Entities sharing officers or addresses
- Anomalies: stated purpose doesn't match activity

### Report File (when running as sub-agent)

Write to `$WORKDIR/report-trace-<entity-slug>.md` using the format in `docs/sources/_preamble.md`.
