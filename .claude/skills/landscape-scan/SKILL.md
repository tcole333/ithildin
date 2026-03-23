---
name: landscape-scan
description: Tier 0 landscape scan — map 10-30 targets quickly with 2-3 sources each, producing leads and a relationship map
user_invocable: true
---

# /landscape-scan

**TIER 0: LANDSCAPE SCAN** — This is a terrain-mapping skill on the Research Plane. You are mapping a landscape quickly (2-3 sources per target), not investigating deeply. Record what you find, create leads for targets that warrant Tier 1 investigation. Don't theorize or apply analytical frameworks — map the terrain and move on.

Quickly scan 10-30 targets in a new investigation area using 2-3 structured sources per target. The primary output is **leads** and a **relationship map**, not exhaustive findings. But don't suppress findings that are significant — the constraint is source breadth (fewer sources per target), not finding count.

## Arguments

- Required: area description (e.g., `/landscape-scan DHS immigration enforcement contractors`)
- Optional context: `/landscape-scan DHS immigration enforcement contractors — focus on private prison companies, ICE contracts, and revolving door between DHS and contractors`

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```

## Architecture

You are a **single agent** scanning many targets quickly. Unlike `/deep-investigate` (4 parallel sub-agents per target), you cover breadth over depth.

**Key differences from deep-investigate:**
- **Multiple targets** (10-30) in one session, not one
- **Fewer sources per target** (2-3 vs all), but still requires `--sources` on every finding
- **Primary output is leads** — but don't suppress important findings
- **Relationship map** as a core deliverable
- **Triage recommendations** at the end: which targets to escalate

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Define the Area and Key Questions

Before searching, articulate:
- **What is this area?** (e.g., "private companies profiting from immigration enforcement")
- **What are the key questions?** (e.g., "who gets the contracts? who moves between government and contractors? what are the financial flows?")
- **What target types are we looking for?** (companies, people, government agencies, nonprofits)
- **Which investigation threads does this relate to?** (check active profile)

### 2. Identify Targets (10-30)

Use a combination of:
- **Your knowledge** of the area (you know the major players)
- **WebSearch** to discover actors you don't know about
- **Existing investigation data** (check findings, leads, entities for overlap)

```bash
# Check existing knowledge
uv run python tools/findings_tracker.py search "<AREA_KEYWORDS>" --output $WORKDIR/existing-findings.json
uv run python tools/lead_tracker.py search "<AREA_KEYWORDS>" --output $WORKDIR/existing-leads.json
```

Create a target list with type classification:

```
| # | Target | Type | Why Interesting |
|---|--------|------|----------------|
| 1 | GEO Group | corporation | Largest private prison company |
| 2 | CoreCivic | corporation | Second largest |
| 3 | Thomas Homan | person | Former acting ICE director |
| ... | ... | ... | ... |
```

### 3. Quick-Pass Each Target

For each target, run **2-3 type-appropriate structured sources** plus WebSearch. Choose sources based on target type:

**Person targets — pick 2-3:**
- WebSearch (always)
- FEC: `uv run python tools/query_fec.py donor "<NAME>" --limit 10 --output $WORKDIR/scan-<N>-fec.json`
- EDGAR: `uv run python tools/query_edgar.py search "<NAME>" --size 5 --output $WORKDIR/scan-<N>-edgar.json`
- CourtListener: `uv run python tools/query_courtlistener.py search "<NAME>" --limit 5 --output $WORKDIR/scan-<N>-cl.json`
- LittleSis: `uv run python tools/query_littlesis.py search "<NAME>" --output $WORKDIR/scan-<N>-ls.json`
- Registries: `uv run python tools/query_registry.py officers "<NAME>" --output $WORKDIR/scan-<N>-reg.json`

**Corporation targets — pick 2-3:**
- WebSearch (always)
- EDGAR: `uv run python tools/query_edgar.py search "<ENTITY>" --size 5 --output $WORKDIR/scan-<N>-edgar.json`
- USASpending: `uv run python tools/query_usaspending.py awards "<ENTITY>" --output $WORKDIR/scan-<N>-usaspend.json`
- Registries: `uv run python tools/query_registry.py search "<ENTITY>" --output $WORKDIR/scan-<N>-reg.json`
- SAM.gov: `uv run python tools/ingest_sam.py search "<ENTITY>" --output $WORKDIR/scan-<N>-sam.json`
- Lobbying: `uv run python tools/query_lobbying.py client "<ENTITY>" --output $WORKDIR/scan-<N>-lda.json`

**Nonprofit targets — pick 2-3:**
- WebSearch (always)
- 990s: `uv run python tools/query_990.py search "<ENTITY>" --output $WORKDIR/scan-<N>-990.json`
- 990 lookup: `uv run python tools/query_990.py lookup <EIN> --output $WORKDIR/scan-<N>-990-lookup.json`  (if EIN known)
- EDGAR (if large): `uv run python tools/query_edgar.py search "<ENTITY>" --size 5 --output $WORKDIR/scan-<N>-edgar.json`
- FEC (PAC affiliates): `uv run python tools/query_fec.py employer "<ENTITY>" --output $WORKDIR/scan-<N>-fec.json`

**Government actor targets — pick 2-3:**
- WebSearch (always)
- FEC: `uv run python tools/query_fec.py donor "<NAME>" --limit 10 --output $WORKDIR/scan-<N>-fec.json`
- Lobbying (post-government): `uv run python tools/query_lobbying.py lobbyist "<NAME>" --output $WORKDIR/scan-<N>-lda.json`
- FARA: `uv run python tools/query_fara.py search "<NAME>" --output $WORKDIR/scan-<N>-fara.json`
- LittleSis: `uv run python tools/query_littlesis.py search "<NAME>" --output $WORKDIR/scan-<N>-ls.json`

### 4. Record Findings for Significant Discoveries

Don't create a finding for every search result. Create findings for:
- **Surprising connections** (unexpected relationships between targets)
- **Large financial flows** (contracts > $10M, donations > $100K)
- **Structural insights** (who controls what, who connects whom)
- **Negative results from authoritative sources** (if a major entity has zero court cases, that's notable)

Every finding must have full provenance:
```bash
uv run python tools/findings_tracker.py add \
    --target "<TARGET>" \
    --type <TYPE> \
    --summary "What the evidence shows" \
    --evidence <REFS> \
    --claim-type paraphrase \
    --source-quote "<REF>:key text from source" \
    --sources <SOURCE_NAMES> \
    --confidence medium
```

### 5. Create Leads for Targets Warranting Further Investigation

For every target that shows enough signal to warrant deeper investigation:
```bash
uv run python tools/lead_tracker.py add \
    --title "Investigate <TARGET> — <reason>" \
    --category <person|entity|financial> \
    --priority <high|medium|low> \
    --source "agent:landscape-scan" \
    --target "<TARGET>"
```

Tag leads with their investigation tier:
```bash
uv run python tools/lead_tracker.py tier <LEAD_ID> scan
```

### 6. Map Preliminary Relationships

Record connections discovered during scanning:
```bash
uv run python tools/findings_tracker.py connect \
    --person-a "<TARGET_A>" --person-b "<TARGET_B>" \
    --type <TYPE> --strength <weak|medium> \
    --evidence <REFS>
```

Register entities and roles as you find them:
```bash
uv run python tools/entity_tracker.py add-entity --name "<ENTITY>" --entity-type <TYPE> --jurisdiction <JUR> --source "<SOURCE>"
uv run python tools/entity_tracker.py add-role --entity-id <ID> --person-name "<NAME>" --role "<ROLE>" --source "<SOURCE>"
```

### 7. Triage and Recommend

After scanning all targets, create a triage summary:

**Escalation criteria** (promote to Tier 1 standard investigation):
- Target appears in 3+ sources during scan
- Target has connections to 2+ known actors
- Target holds a structural role (registered agent, compliance officer, fund administrator, government-to-private revolving door)
- Significant financial flows discovered

**Recommend:**
- **2-4 targets for deep dives** (`/deep-investigate`) — highest structural importance
- **5-10 targets for standard investigation** (`/pursue-lead`) — strong signal, need full source coverage
- **Remaining targets** — stay as open leads for later, or close as low-priority

### 8. Present Summary

Format:
```
## /landscape-scan <AREA> — Results

### Area Overview
[2-3 sentences describing what was found]

### Targets Scanned: <N>
| # | Target | Type | Sources Checked | Key Finding | Recommendation |
|---|--------|------|----------------|-------------|----------------|
| 1 | GEO Group | corp | edgar, usaspend, web | $2.3B in ICE contracts | Deep dive |
| 2 | CoreCivic | corp | edgar, usaspend, web | Renamed from CCA 2016 | Standard |
| ... | ... | ... | ... | ... | ... |

### Relationship Map
[Key relationships discovered — who connects to whom]

### Sources Checked
| Source | Queries Run | Total Results | Findings Created |
|--------|------------|---------------|-----------------|
| WebSearch | 15 | n/a | 3 |
| EDGAR | 8 | 42 | 2 |
| USASpending | 6 | 18 | 4 |
| ... | ... | ... | ... |

### Escalation Recommendations
**Deep Dive** (2-4 targets):
- <TARGET>: <reason> → Lead #X

**Standard Investigation** (5-10 targets):
- <TARGET>: <reason> → Lead #X

### Key Questions for Further Investigation
1. [Question that emerged from the scan]
2. [Pattern that needs deeper analysis]

### Findings Created: <N>
### Leads Created: <N>
### Connections Mapped: <N>
```

## Context Management

- **Use `--output $WORKDIR/...` on ALL search commands**
- **Record findings as you go**, not in a batch at the end
- **Don't read full JSON files** unless you need specific details — the summary output is enough for landscape scanning
- **Aim for < 50 tool calls** — you're scanning, not investigating
- This skill runs as a single agent in one CC instance

## Notes

- This is Tier 0 — the lightest touch. The goal is breadth, not depth.
- Every finding still needs full provenance (`--sources`, `--evidence`, `--claim-type`, `--source-quote`)
- The hook will block findings without `--sources` — this is intentional
- Tag all created leads with `tier scan` so they can be tracked
- The value of a landscape scan is the **map**, not the individual findings — who's connected to whom, what the structure looks like, where the money flows
