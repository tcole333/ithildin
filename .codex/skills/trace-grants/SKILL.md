---
name: trace-grants
description: Tier 2 grant flow network analysis — map nonprofit funding chains, detect circular flows, identify shared officers, generate coordination hypotheses
---

# $trace-grants

**TIER 2: ANALYSIS AGENT** — This skill performs grant flow network analysis using the IRS 990 bulk database (22.7M grants, 5M filings). The data extraction (grant amounts, officer lists) is Tier 1 factual work, but the network analysis (circular flow detection, shared officer mapping, co-grantor clustering) is Tier 2 pattern recognition. Every hypothesis about coordination or dark money routing MUST include falsification criteria. See `research/INVESTIGATIVE_METHODOLOGY.md#framework-discipline`.

## Arguments

- `$trace-grants "Donors Trust"` — search by name, resolve to EIN
- `$trace-grants --ein 522166327` — direct EIN
- `$trace-grants --ein 522166327 --depth 3` — deeper trace (default: 2)
- `$trace-grants --ein 522166327 --min-amount 1000000` — only trace grants above threshold

### Context Loading
```bash
uv run python tools/investigation_context.py show
```

## Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Identify Starting Entity

If given a name, resolve to EIN:
```bash
uv run python tools/query_990.py search "ORGANIZATION NAME" --output $WORKDIR/search.json
```

Then pull comprehensive view:
```bash
uv run python tools/query_990.py lookup <EIN> --output $WORKDIR/lookup.json
```

Read the lookup output. Note: org type (501(c)(3) vs (c)(4)), revenue, assets, officers, top grants. **Record the starting entity immediately.**

### 2. Pull Financial Context

```bash
uv run python tools/query_990.py financials <EIN> --output $WORKDIR/financials.json
```

Review revenue and expense trends. Key context: is this organization growing? Is it spending more than it receives (drawing down assets)? What's the program expense ratio?

### 3. Extract Grant Flow Network

This is the core operation — build the directed grant flow graph:

```bash
uv run python tools/query_990.py flow <EIN> --depth 2 --min-amount 50000 --output $WORKDIR/flow.json
```

Read the flow JSON. Key fields:
- `nodes`: All organizations in the network with total_granted / total_received
- `edges`: Directed grant flows with amounts, counts, and years
- `circular_flows`: **Critical** — A↔B patterns where money flows in both directions
- `stats`: Node count, edge count, total flow volume

**Record findings for:**
- Every circular flow (`claim-type: synthesis`, confidence: `medium` — the tool derives this from two or more filing rows)
- Top 5 aggregate edges by amount (`claim-type: synthesis`, confidence: `medium`)
- Nodes that are both funders and recipients (`type: "both"`) as **candidate** pass-through entities (`claim-type: synthesis`, confidence: `medium`)

Preserve the primary evidence beneath each synthesis. For every load-bearing filing,
attach an exact Schedule I/Part VII source row or verbatim XML/PDF span that includes
the names, amount, year, and role used in the calculation. A tool label such as
"Schedule I grant records" is method metadata, not a `source_quote`. A single raw
filing row may be recorded separately as `direct_quote`/`confirmed` only when its
stored quote is verbatim and the summary makes no aggregate or network inference.

### 4. Detect Shared Officers

Extract the top 10 recipient EINs from the flow, then check for officer overlap:

```bash
uv run python tools/query_990.py shared-officers <EIN1> <EIN2> <EIN3> ... --output $WORKDIR/shared-officers.json
```

**Record findings for each person serving on 2+ organizations in the network.** These are the human bridges connecting otherwise "independent" nonprofits.

### 5. Check Co-Grantors

For each of the top 3-5 recipients, find who else funds them:

```bash
uv run python tools/query_990.py co-grantors "RECIPIENT NAME" --output $WORKDIR/cograntors-<N>.json
```

This reveals the **funding constellation** around each recipient. If the same set of funders appears for multiple recipients, treat it as a coordination hypothesis, not proof. Test alternative explanations such as shared program area, geography, grant cycle, intermediary advice, or independently similar donor criteria.

### 6. Red Flag Analysis

Run red-flag checks on the starting entity and its top 3 recipients:

```bash
uv run python tools/query_990.py red-flags <EIN> --output $WORKDIR/redflags-<ticker>.json
```

Red flags include: high compensation relative to revenue, low program expense ratio, insider transactions (Schedule L), missing governance policies (conflict of interest, whistleblower).

### 7. Cross-Reference Against Investigation

```bash
uv run python tools/query_990.py cross-ref --output $WORKDIR/cross-ref.json
```

Match all entities in the grant network against investigation.db. **This is where grant tracing connects to the broader investigation.** If a grant recipient is also a corporate entity, political donor, or litigation party in the investigation, that's a cross-domain connection.

### 8. Record Findings

**DB-first principle**: Record findings as you discover them, not at the end.

```bash
# Circular flow finding
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "<ORG_A>" \
  --summary "Circular grant flow: <ORG_A> sent USD <AMOUNT_A> to <ORG_B>, which sent USD <AMOUNT_B> back. Net flow: USD <NET_AMOUNT> toward <DIRECTION>" \
  --type financial \
  --evidence "990:<EIN_A>" "990:<EIN_B>" \
  --claim-type synthesis \
  --source-quote \
    "990:<EIN_A>:<exact Schedule I row or verbatim XML/PDF span showing A→B, amount, and year>" \
    "990:<EIN_B>:<exact Schedule I row or verbatim XML/PDF span showing B→A, amount, and year>" \
  --sources 990 \
  --confidence medium

# Aggregate grant flow finding
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "<FUNDER>" \
  --summary "Grant: <FUNDER> sent USD <AMOUNT> to <RECIPIENT> over <N> grants (<YEARS>)" \
  --type financial \
  --evidence "990:<FILER_EIN>" \
  --claim-type synthesis \
  --source-quote "990:<FILER_EIN>:<exact source-row serialization or verbatim span for every load-bearing grant, including recipient, amount, and year>" \
  --sources 990 \
  --confidence medium

# Shared officer finding (synthesis across filings)
PYTHONPATH=. uv run python tools/findings_tracker.py add \
  --target "<PERSON_NAME>" \
  --summary "<PERSON> serves as officer at <N> organizations in grant network: <ORG1>, <ORG2>, ..." \
  --type relationship \
  --evidence "990:<EIN1>" "990:<EIN2>" \
  --claim-type synthesis \
  --source-quote \
    "990:<EIN1>:<exact Part VII row or verbatim XML/PDF span naming the person, title, and year at ORG1>" \
    "990:<EIN2>:<exact Part VII row or verbatim XML/PDF span naming the person, title, and year at ORG2>" \
  --sources 990 \
  --confidence medium
```

Register entities:
```bash
PYTHONPATH=. uv run python tools/entity_tracker.py add-entity \
  --name "<ORG NAME>" --entity-type nonprofit --jurisdiction "<STATE>" \
  --source "990:<EIN>"
```

### 9. Spawn Follow-Up Leads

```bash
# Undiscovered entity in the network
PYTHONPATH=. uv run python tools/lead_tracker.py add \
  --title "Trace grants: <ORG> — received USD <AMOUNT> from <FUNDER>, unknown to investigation" \
  --category entity --priority medium \
  --target "<ORG NAME>" --source "agent:trace-grants" \
  --evidence "990:<FILER_EIN>"

# Person appearing across multiple orgs
PYTHONPATH=. uv run python tools/lead_tracker.py add \
  --title "Investigate <PERSON> — officer at <N> nonprofits in <NETWORK_NAME> grant network" \
  --category person --priority medium \
  --target "<PERSON>" --source "agent:trace-grants" \
  --evidence "990:<EIN1>,990:<EIN2>"
```

### 10. Output

```
## $trace-grants: <STARTING_ORG> (EIN: <EIN>)

### Entity Profile
- Type: 501(c)(3) / 501(c)(4)
- Revenue: $X (FY<YEAR>)
- Assets: $X
- Officers: N

### Grant Flow Network (depth <N>, min $<AMOUNT>)
- Nodes: N organizations
- Edges: N grant flows
- Total flow: $X
- Circular flows: N detected

### Top Outgoing Grants
| # | Recipient | EIN | Amount | Grants | Years |
|---|-----------|-----|--------|--------|-------|

### Top Incoming Grants (if applicable)
| # | Funder | EIN | Amount | Grants | Years |
|---|--------|-----|--------|--------|-------|

### Circular Flows
| Pair | A→B | B→A | Net Flow | Direction |
|------|-----|-----|----------|-----------|

### Shared Officers
| Person | Orgs | Titles |
|--------|------|--------|

### Co-Grantor Clusters
[For each top recipient: who else funds them?]

### Red Flags
[Financial ratio anomalies, governance gaps, insider transactions]

### Cross-References with Investigation
[Entities appearing in both grant network and investigation.db]

### Summary
- Findings recorded: N
- Leads created: N
- Entities registered: N
```

## Key Analytical Patterns

**Circular flows**: Reciprocal transfers can inflate both organizations' reported activity and may indicate regranting, pass-through behavior, fiscal sponsorship, returned funds, or coordinated funding. If A sends $60M to B and B sends $260M back, the net direction measures the net transfer in the observed rows; it does **not** establish control or make one entity the other's fundraising arm. Treat control as a hypothesis and test grant purposes, transaction timing, governance authority, agreements, and the best innocent explanation.

**Hub-and-spoke topology**: One central funder (Donors Trust) distributing to many recipients is a donor-advised fund pattern. The hub anonymizes the original donor.

**Pass-through entities**: Organizations with type "both" (large incoming AND outgoing grants) and low program expenses are candidate conduits, not proven pass-throughs. Alternatives include grantmaking foundations, fiscal sponsors, pooled funds, accounting differences, or a temporary campaign. Verify purpose descriptions, timing, governance, and retained assets before classifying the organization.

**501(c)(4) coverage is form-specific**: IRS TEOS and ProPublica include 501(c)(4) organizations that file Form 990 or 990-EZ, so query the organization before declaring an opacity gap. If only Form 990-N exists for a year, detailed finances and outgoing grants are unavailable for that year. If a full return exists, inspect it normally. Separately note that contributor identities are often not publicly disclosed for non-private-foundation filers and that recipient-EIN coverage can be incomplete. State the exact missing form, year, field, or identity rather than treating every 501(c)(4) as invisible.

**Shared officers as structural bridges**: A shared officer creates possible governance or information overlap, but does not by itself prove functional coordination. Verify that the records refer to the same person, that service periods overlap, and that the role carried relevant authority. Test alternatives such as a common professional director, accountant, legal adviser, affiliate structure, or non-overlapping tenure before advancing a coordination hypothesis.

## Stop Conditions

- Flow network extracted (all depths explored)
- Circular flows recorded as findings
- Shared officers checked across top recipients
- Co-grantors analyzed for top 3-5 recipients
- Red flags checked for starting entity + top recipients
- Cross-reference against investigation.db complete
- All findings recorded, leads spawned for undiscovered entities
