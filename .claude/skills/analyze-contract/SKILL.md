---
name: analyze-contract
description: Government contract forensics — subaward chains, obligation and modification timelines, vehicle tracking, partnership mapping
user-invocable: true
---

# /analyze-contract

**TIER 1: DEPTH ANALYSIS** — Trace the selected contracts through award actions, reported subcontracting, vehicle competition, and teaming relationships. Distinguish obligations, ceilings/options, and actual outlays. Preserve factual observations separately from inferences; investigate explanations for significant patterns without inferring intent from timing alone.

## Arguments

- `/analyze-contract "Palantir Technologies"` — search for awards by recipient name
- `/analyze-contract --award-id "W31P4Q20C0042"` — analyze a specific award
- `/analyze-contract --uei "ZE2JVFS8ML75"` — all awards for a specific entity (by UEI)

### Context Loading
Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the requested profile/database. Select applicable sources and checks from the question and award type; record unavailable or not-applicable routes.

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

Honor a supplied award identifier. For a recipient-wide request, enumerate its requested scope and select deeper reviews by relevance, value, agency, and dates, recording selection criteria. An award list's first page is not the recipient's complete portfolio: inspect pagination and retrieve remaining pages when required.

### 2. Get Award Detail

```bash
# Full award detail (USASpending)
uv run python tools/query_usaspending.py award <AWARD_ID> --output $WORKDIR/award-detail.json
```

Extract and record:
- Canonical `generated_unique_award_id`, plain PIID, recipient identity, and the requested identifier. A PIID can repeat across agencies or parent awards; use the resolved canonical ID for award-scoped analysis.
- Total obligation and base + exercised options
- Period of performance (start, end, current end)
- Awarding agency and sub-agency
- Contract description (full NAICS/PSC classification)
- Recipient name, UEI, address
- Parent award (if IDV/IDIQ)
- Subaward count and total subaward amount

### 3. Trace the Subcontractor Chain

Trace the reported subaward chain. Reporting thresholds, source coverage, and a prime's first-tier subawards limit what the dataset can establish; an empty result does not prove no subcontracting occurred.

```bash
# Enumerate reported subawards using the plain prime PIID
uv run python tools/query_usaspending.py subawards --award-id "<PRIME_PIID>" --all-pages --output "$WORKDIR/subawards.json"

# For each significant subcontractor, get their detail
uv run python tools/query_highergov.py subcontract --awardee-uei <SUB_UEI> --output $WORKDIR/sub-<slug>.json
```

For each subcontractor:
- [ ] Who are they? What's their business?
- [ ] What reported subaward amount is attributable to this prime, and how does its period/basis compare with the prime's obligations?
- [ ] Are they in the investigation's entity database?
- [ ] Do their officers overlap with other investigation targets?
- [ ] Does evidence of staffing, operations, or subcontracting warrant testing a pass-through hypothesis? A high amount alone does not establish it.

The tool checks exact PIID and supplied scope on each returned page. Verify the prime recipient and awarding agency against award detail before combining rows, especially for reused PIIDs. Inspect `status`, `errors`, `retrieval.complete`, and `pagination`. `--all-pages` has a default 50-page budget; use `--max-pages N` or resume at `pagination.next_page` into a separate artifact, preserving page provenance and avoiding overlapping rows. Missing pagination is partial coverage. Cross-reference every contractor in the analyzed scope and report any remaining pages.

Register each subcontractor:
```bash
uv run python tools/entity_tracker.py add-entity --name "<SUB_NAME>" --entity-type <TYPE> --source "USASpending:<AWARD_ID>"
```

### 4. Analyze Obligations and Modifications

```bash
# Action records selected by canonical award identity
uv run python tools/query_usaspending.py transactions --uei "<RECIPIENT_UEI>" --award-id "<GENERATED_UNIQUE_AWARD_ID>" --all-pages --output "$WORKDIR/transactions.json"

# Optional recipient-wide context; keep its broader scope explicit
uv run python tools/query_usaspending.py timeline "<NAME>" --output $WORKDIR/timeline.json
```

This command paginates the existing recipient transaction search and applies exact canonical award-ID selection locally. It requires a recipient name or UEI; the generated ID is not sent as an unverified server filter. `award_selection` reports matched, excluded, and unresolvable rows. `pagination.reported_total` describes the upstream recipient query, not the selected award. Inspect all request messages, filters, dates, and completion flags; affiliated recipient records may appear, and source date limits still apply. Do not treat unresolved row identities or an interrupted/capped retrieval as complete.

Read all selected action records, sorting by action date for analysis. Preserve zero and negative obligations and modification identifiers:
- [ ] **Obligation cadence**: regular or irregular actions, accounting for reporting and fiscal cycles
- [ ] **Spikes/deobligations**: large positive or negative actions and their descriptions
- [ ] **Timing relative to key_dates**: temporal associations to test against ordinary procurement explanations
- [ ] **Early commitments**: disproportionate obligations early in performance, distinguishing funding from expenditure
- [ ] **Gaps**: no reported actions in the searched period; evaluate coverage before hypothesizing a pause
- [ ] **Modification pattern**: exercise of options, scope changes, corrections, or administrative actions

`Transaction Amount` is obligation-action data. It does not establish when cash was paid, services delivered, or an invoice settled. Use explicit outlay/disbursement evidence for payment claims. Aggregate award detail and recipient-wide timelines cannot substitute for selected-award action history.

Maintain `$WORKDIR/contract-progress.md` with canonical identities, source/page coverage, analysis completed, finding IDs, and next steps. Read long records directly or in manageable chunks without losing coverage. Resume from these artifacts after compaction or interruption. Independent subcontractor or vehicle analysis can use native chat subagents with unique outputs and pinned context; the parent reconciles identities, amounts, periods, and gaps before synthesis.

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
# Contract metadata (single quotes preserve literal currency text)
uv run python tools/findings_tracker.py add \
  --target "<CONTRACTOR>" \
  --summary '<AWARD_ID> records total obligations of $<AMOUNT> to <CONTRACTOR> for <DESCRIPTION>, period <START>-<END>' \
  --type financial \
  --evidence "USASpending:<AWARD_ID>" \
  --claim-type paraphrase \
  --source-quote 'USASpending:<AWARD_ID>:Total Obligation $X, Award Type Y, Agency Z' \
  --sources usaspending \
  --confidence high

# Subcontractor relationship
uv run python tools/findings_tracker.py connect \
  --person-a "<PRIME>" --person-b "<SUB>" \
  --type financial --strength strong \
  --evidence "USASpending:<AWARD_ID>" \
  --finding-id <FID>

# Obligation/timing observation interpreted as an inference
uv run python tools/findings_tracker.py add \
  --target "<CONTRACTOR>" \
  --summary 'Contract <AWARD_ID> shows $X obligation spike on <DATE>, coinciding with <KEY_DATE_EVENT>' \
  --type financial \
  --evidence "USASpending:<AWARD_ID>" \
  --claim-type inference \
  --source-quote 'USASpending:<AWARD_ID>:<verbatim action-record excerpt supporting the amount and date>' \
  --sources usaspending \
  --confidence medium
```

### 9. Create Follow-Up Leads

Create leads for unresolved, relevant questions with a concrete next step, after checking existing leads. New contractor names alone are not sufficient.

```bash
# Unknown subcontractor
uv run python tools/lead_tracker.py add \
  --title 'Trace <SUBCONTRACTOR> — reported subaward of $<AMOUNT> on <AWARD_ID>' \
  --category entity --priority medium \
  --target "<SUBCONTRACTOR>" --source "agent:analyze-contract"

# Officer of contracting entity
uv run python tools/lead_tracker.py add \
  --title 'Investigate <OFFICER> — <ROLE> at <CONTRACTOR>, $<TOTAL> in federal obligations' \
  --category person --priority medium \
  --target "<OFFICER>" --source "agent:analyze-contract"

# Related vehicle analysis
uv run python tools/lead_tracker.py add \
  --title 'Analyze vehicle <VEHICLE_KEY> — <N> contracts, $<TOTAL> obligated' \
  --category contract --priority medium \
  --target "<VEHICLE_NAME>" --source "agent:analyze-contract"
```

### Stop Conditions

- Requested awards are identified canonically; transaction and subaward coverage is complete for the declared scope, or outstanding pages/source limitations are explicit
- Obligation/modification timeline is analyzed with amount semantics and date bounds preserved
- Applicable vehicle, partnership, and registration checks are completed or documented as unavailable
- Contractor names within the analyzed scope are cross-referenced against the pinned investigation
- Findings, contradictions, coverage, artifact paths, and follow-up questions are reported. Continue useful authorized work through recoverable failures; if external access prevents completion, preserve progress and provide the exact next action rather than claiming complete coverage.
