---
name: analyze-contract
description: Government contract forensics — subaward chains, payment timelines, vehicle tracking, partnership mapping
---

# $analyze-contract

**TIER 1: DEPTH ANALYSIS** — This skill traces government contracts through their full lifecycle: prime awards, subcontractor chains, payment timelines, vehicle competition, and teaming partnerships. LLMs can process hundreds of transaction records, cross-reference every contractor name against the investigation, and detect payment anomalies that humans miss in tabular data. Record every factual discovery separately. Do not theorize about procurement intent — record the money flows and flag patterns.

## Arguments

- `$analyze-contract "Palantir Technologies"` — search for awards by recipient name
- `$analyze-contract --award-id "W31P4Q20C0042"` — analyze a specific award
- `$analyze-contract --uei "ZE2JVFS8ML75"` — all awards for a specific entity (by UEI)

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

### 1. Identify the Contract(s)

```bash
# Search by recipient name (USASpending)
uv run python tools/query_usaspending.py awards "<NAME>" --output $WORKDIR/usa-awards.json

# Search by recipient (HigherGov — richer detail)
uv run python tools/query_highergov.py contract --awardee-uei <UEI> --output $WORKDIR/hg-contracts.json

# If you have a parent award / vehicle key
uv run python tools/query_highergov.py contract --parent-award <PARENT_ID> --all-pages --output $WORKDIR/hg-vehicle-contracts.json
```

Select the most significant awards by: dollar value, relevance to investigation threads, awarding agency, and recency.

### 2. Get Award Detail

```bash
# Full award detail (USASpending)
uv run python tools/query_usaspending.py award <AWARD_ID> --output $WORKDIR/award-detail.json
```

Extract and record:
- Total obligation and base + exercised options
- Period of performance (start, end, current end)
- Awarding agency and sub-agency
- Contract description (full NAICS/PSC classification)
- Recipient name, UEI, address
- Parent award (if IDV/IDIQ)
- Subaward count and total subaward amount

### 3. Trace the Subcontractor Chain

This is the core forensic capability — follow the money through the supply chain.

```bash
# Get all subawards under this prime
uv run python tools/query_usaspending.py subawards --award-id <AWARD_ID> --output $WORKDIR/subawards.json

# For each significant subcontractor, get their detail
uv run python tools/query_highergov.py subcontract --awardee-uei <SUB_UEI> --output $WORKDIR/sub-<slug>.json
```

For each subcontractor:
- [ ] Who are they? What's their business?
- [ ] How much are they receiving relative to the prime?
- [ ] Are they in the investigation's entity database?
- [ ] Do their officers overlap with other investigation targets?
- [ ] Are they a pass-through (receiving large sums, minimal apparent capability)?

Register each subcontractor:
```bash
uv run python tools/entity_tracker.py add-entity --name "<SUB_NAME>" --entity-type <TYPE> --source "USASpending:<AWARD_ID>"
```

### 4. Analyze Payment Timeline

```bash
# Transaction-level payment history
uv run python tools/query_usaspending.py award <AWARD_ID> --output $WORKDIR/transactions.json

# Spending trends over time
uv run python tools/query_usaspending.py timeline "<NAME>" --output $WORKDIR/timeline.json
```

Read the transaction data and map:
- [ ] **Payment cadence**: regular monthly/quarterly, or irregular?
- [ ] **Spikes**: unusually large single obligations — what triggered them?
- [ ] **Timing relative to key_dates**: payments clustering before elections, contract modifications after personnel changes
- [ ] **Front-loading**: disproportionate payments early in the period of performance
- [ ] **Gaps**: periods with zero activity — contract paused? Performance issues?
- [ ] **Modification pattern**: frequent contract mods suggesting scope creep or requirements changes

Cross-reference transaction dates against investigation `key_dates`:
```bash
uv run python -c "
import yaml
with open('investigations/<ACTIVE>/config.yaml') as f:
    dates = yaml.safe_load(f).get('key_dates', [])
for d in dates:
    print(f'{d}')
"
```

### 5. Vehicle and Partnership Analysis (HigherGov)

This reveals the competitive landscape and corporate relationships.

```bash
# What vehicle is this contract on?
uv run python tools/query_highergov.py idv --award-id <PARENT_AWARD> --output $WORKDIR/hg-idv.json

# All contracts under this vehicle
uv run python tools/query_highergov.py contract --vehicle-key <VEHICLE_KEY> --all-pages --output $WORKDIR/hg-vehicle-all.json

# Who does this contractor team with?
uv run python tools/query_highergov.py partnership --awardee-key <AWARDEE_KEY> --output $WORKDIR/hg-partnerships.json

# Vehicle metadata
uv run python tools/query_highergov.py vehicle --vehicle-key <VEHICLE_KEY> --output $WORKDIR/hg-vehicle-meta.json
```

Analyze:
- [ ] **Vehicle competition**: who else holds contracts on this vehicle? Market concentration?
- [ ] **Teaming patterns**: which contractors repeatedly partner? Do any investigation targets appear as teaming partners?
- [ ] **Incumbent advantage**: how long has this contractor held this work? Multiple re-competes won?
- [ ] **Vehicle scope**: what does the IDIQ/BPA cover? Is the work consistent with the vehicle's intended scope?

### 6. SAM.gov Cross-Reference

```bash
# Registration details
uv run python tools/query_sam.py entity --uei <UEI> --output $WORKDIR/sam-entity.json

# Debarment/suspension check
uv run python tools/query_sam.py exclusions "<NAME>" --output $WORKDIR/sam-exclusions.json

# Local bulk data (faster, more fields)
uv run python tools/ingest_sam.py entity-by-uei <UEI> --output $WORKDIR/sam-bulk.json
```

Check:
- [ ] Small business certifications (8(a), HUBZone, SDVOSB) — legitimate or shell?
- [ ] NAICS codes — does the contractor's registered expertise match the contract work?
- [ ] Registration dates — entity created just before contract award?
- [ ] Exclusions — any debarment or suspension history?
- [ ] Physical address — co-located with other investigation entities?

### 7. Cross-Reference Against Investigation

```bash
# Check every contractor name against entities
uv run python tools/entity_tracker.py lookup --name "<CONTRACTOR>"

# Check for existing findings
uv run python tools/findings_tracker.py search "<CONTRACTOR>" --output $WORKDIR/xref.json

# Geographic analysis — where was the work performed?
uv run python tools/query_usaspending.py geography "<NAME>" --output $WORKDIR/geography.json
```

Flag:
- Contractors that appear in the investigation's entity database
- Contractors co-located with investigation addresses (known_addresses from profile)
- Contracts awarded by agencies where investigation targets hold positions
- Subcontractors whose officers overlap with prime contractor officers (self-dealing)

### 8. Record Findings

One finding per discrete discovery:

```bash
# Contract metadata
uv run python tools/findings_tracker.py add \
  --target "<CONTRACTOR>" \
  --summary "<AGENCY> awarded $<AMOUNT> contract (<AWARD_ID>) to <CONTRACTOR> for <DESCRIPTION>, period <START>-<END>" \
  --type financial \
  --evidence "USASpending:<AWARD_ID>" \
  --claim-type paraphrase \
  --source-quote "USASpending:<AWARD_ID>:Total Obligation $X, Award Type Y, Agency Z" \
  --sources usaspending \
  --confidence high

# Subcontractor relationship
uv run python tools/findings_tracker.py connect \
  --person-a "<PRIME>" --person-b "<SUB>" \
  --type financial --strength strong \
  --evidence "USASpending:<AWARD_ID>" \
  --finding-id <FID>

# Payment anomaly (inference)
uv run python tools/findings_tracker.py add \
  --target "<CONTRACTOR>" \
  --summary "Contract <AWARD_ID> shows $X obligation spike on <DATE>, coinciding with <KEY_DATE_EVENT>" \
  --type financial \
  --evidence "USASpending:<AWARD_ID>" \
  --claim-type inference \
  --source-quote "USASpending:<AWARD_ID>:Federal Action Obligation $X on <DATE>" \
  --sources usaspending \
  --confidence medium
```

### 9. Spawn Follow-Up Leads

```bash
# Unknown subcontractor
uv run python tools/lead_tracker.py add \
  --title "Trace <SUBCONTRACTOR> — received $<AMOUNT> as sub on <AWARD_ID>" \
  --category entity --priority medium \
  --target "<SUBCONTRACTOR>" --source "agent:analyze-contract"

# Officer of contracting entity
uv run python tools/lead_tracker.py add \
  --title "Investigate <OFFICER> — <ROLE> at <CONTRACTOR>, $<TOTAL> in federal contracts" \
  --category person --priority medium \
  --target "<OFFICER>" --source "agent:analyze-contract"

# Related vehicle analysis
uv run python tools/lead_tracker.py add \
  --title "Analyze vehicle <VEHICLE_KEY> — <N> contracts, $<TOTAL> obligated" \
  --category contract --priority medium \
  --target "<VEHICLE_NAME>" --source "agent:analyze-contract"
```

### Stop Conditions

- All subawards enumerated and cross-referenced
- Payment timeline analyzed for anomalies
- Vehicle/partnership data checked (if HigherGov available)
- SAM.gov registration verified
- All contractor names cross-referenced against investigation DB

## What Makes This Skill Valuable

A human analyst looking at a contract sees: recipient, amount, agency. They rarely trace subcontractor chains, analyze payment timing patterns across hundreds of transactions, or cross-reference every contractor name against an investigation database of thousands of entities.

An LLM agent processes the **full transaction history** and **complete subcontractor tree**, then cross-references every name. This surfaces:
- Shell subcontractors receiving disproportionate pass-through payments
- Payment spikes coinciding with political events or personnel changes
- Contractors who team together across multiple vehicles (hidden relationships)
- Entities created shortly before contract award (suspicious timing)
- Geographic patterns (all work performed at an investigation-linked address)

