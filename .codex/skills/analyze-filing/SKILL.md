---
name: analyze-filing
description: Deep SEC filing analysis — read full 10-K/proxy/13D text, extract related-party transactions, officers, subsidiaries, risk disclosures
---

# $analyze-filing

**TIER 1: DEPTH ANALYSIS** — Read the selected SEC disclosure package, extract material facts, and cross-reference its people, entities, and transactions. Keep disclosed facts separate from analytical interpretations. Explain significant patterns when the evidence warrants it, with explicit alternatives and inference confidence ceilings.

## Arguments

- `$analyze-filing "Palantir Technologies"` — look up CIK, list recent filings, analyze most relevant
- `$analyze-filing --cik 1321655` — go directly to CIK
- `$analyze-filing --url "https://sec.gov/..."` — read a specific filing URL
- `$analyze-filing --form "DEF 14A"` — filter to proxy statements (default: 10-K)

### Context Loading
Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the requested profile/database before scoped work. Preserve that context throughout the task and any supervised subagent work.

```bash
uv run python tools/investigation_context.py show
```

## Process

### 0. Session Setup
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Identify the Filing

Resolve the invocation before selecting a filing:

- If `--url` was supplied, use that exact document URL and skip company lookup
  and form selection. Record the accession and document filename when the URL
  exposes them.
- Otherwise resolve the target to a CIK. Use the requested `--form` value; only
  default to `10-K` when the invocation omitted it.

```bash
# Look up CIK
uv run python tools/query_edgar.py lookup "<COMPANY_OR_PERSON>" --output "$WORKDIR/edgar-lookup.json"

# Get company metadata and recent filings
uv run python tools/query_edgar.py company <CIK> --output $WORKDIR/edgar-company.json

# List the requested form type (substitute 10-K only when --form was omitted)
uv run python tools/query_edgar.py filings <CIK> \
  --form "<REQUESTED_FORM_OR_10-K>" \
  --output $WORKDIR/edgar-filings.json
```

Honor a supplied filing. Otherwise select the filing relevant to the question and dates, defaulting to the latest only when no historical scope is requested. Record CIK, accession, form, filing date, primary-document URL, and reporting period in the workdir. Use that stable accession for every later extraction; an ordinal filing index can move.

### 2. Read the Full Filing

Acquire the complete extracted text through the tool's structured-output path;
`--lines` only controls terminal previews and is not a full-read mechanism.

```bash
uv run python tools/query_edgar.py read "<FILING_URL>" \
  --output "$WORKDIR/filing-full.json"
jq '{url, retrieval, characters, line_count}' "$WORKDIR/filing-full.json"
jq -r '.text' "$WORKDIR/filing-full.json" > "$WORKDIR/filing-full.txt"
```

Read the complete filing directly when it fits the runtime's available context. For larger filings, use sequential chunks sized for the available tool output and context; 2,000 lines below is an adjustable example. Read every chunk and record covered ranges against `line_count`:

```bash
split -l 2000 -d -a 4 "$WORKDIR/filing-full.txt" "$WORKDIR/filing-chunk-"
ls "$WORKDIR"/filing-chunk-*
```

Use repeatable `read --find TERM --context N` calls only to revisit targeted
passages; they do not replace the sequential full-text pass.

Maintain `$WORKDIR/filing-progress.md` with the selected identities, coverage ranges, unresolved references, persisted finding IDs, and next step. Resume from these artifacts after compaction or interruption. Continue the requested analysis while useful authorized work remains; context pressure is a reason to checkpoint and resume. Independent exhibit or cross-reference work can run in native chat subagents with explicit ownership; the parent reconciles the complete package before reporting.

#### Cover the accession package

The primary document is not necessarily the complete disclosure package. Use
the accession from `edgar-filings.json` to inspect the official SEC accession
directory (remove dashes from the accession number):

```text
https://www.sec.gov/Archives/edgar/data/<CIK>/<ACCESSION_NO_DASH>/
```

Record that directory URL in the coverage notes, inspect its document table,
and inventory:

- the primary form;
- separately filed exhibits needed by the checklist (including Exhibit 21 and
  material contracts); and
- any proxy or other filing incorporated by reference.

Fetch each load-bearing document through the same complete-text path and keep a
separate artifact so its URL, accession, and filename remain auditable:

```bash
uv run python tools/query_edgar.py read "<SEC_EXHIBIT_OR_INCORPORATED_DOCUMENT_URL>" \
  --output "$WORKDIR/filing-<document-label>.json"
```

Read every required artifact sequentially. If the primary form incorporates a
later DEF 14A that has not yet been filed, mark Part III coverage as pending and
do not claim complete filing analysis. If a referenced document is unavailable,
record the exact missing document and affected checklist items.

### 3. Extract by Filing Type

Use the filing-type checklist to guide a thorough pass, recording material disclosures and explicit not-applicable items. For a user-requested narrow question, define its document coverage and affected checklist items; do not present that scoped answer as an exhaustive filing review.

#### 10-K / 10-Q Extraction Checklist

- [ ] **Officers and directors** (Part III or incorporated proxy reference)
  - Full names, titles, ages, start dates
  - Other board seats and affiliations mentioned
  - Register each via `entity_tracker.py add-role`

- [ ] **Subsidiaries** (Exhibit 21 or Item 1)
  - Entity name, jurisdiction of incorporation, ownership percentage
  - Register each via `entity_tracker.py add-entity`

- [ ] **Related-party transactions** (footnotes, typically Note 12-20)
  - Who is the related party? What is the relationship?
  - Dollar amounts, terms, dates
  - This is where the buried intelligence lives — read every footnote

- [ ] **Risk factors mentioning litigation or investigations** (Item 1A)
  - Named proceedings, regulatory agencies, potential exposure
  - Status of pending matters, estimated losses

- [ ] **Material contracts** (Item 1, or Exhibit index)
  - Counterparties, terms, dollar values
  - Government contracts, licensing agreements, joint ventures

- [ ] **Segment revenue** (footnotes)
  - Revenue by business segment and geography
  - Which segments are growing/declining

- [ ] **Off-balance-sheet arrangements / VIEs** (footnotes)
  - Variable interest entities, special purpose vehicles
  - Consolidation decisions and their rationale

- [ ] **Subsequent events** (final footnote)
  - Material events after the filing period

- [ ] **Financial statements** (structured extraction via edgartools)
  - Pull structured data for ratio analysis:
    ```bash
    uv run python tools/query_edgar.py sections <CIK> --accession "<SELECTED_ACCESSION>" --section income_statement --output "$WORKDIR/income.json"
    uv run python tools/query_edgar.py sections <CIK> --accession "<SELECTED_ACCESSION>" --section balance_sheet --output "$WORKDIR/balance.json"
    uv run python tools/query_edgar.py sections <CIK> --accession "<SELECTED_ACCESSION>" --section cashflow_statement --output "$WORKDIR/cashflow.json"
    ```
  - An exact `sections --url "<SELECTED_SEC_ARCHIVES_URL>"` can replace CIK/accession selection. It selects that accession's structured filing, even when the URL names an exhibit; continue reading the exact exhibit separately. The tool rejects accession, CIK, or explicit form mismatches and never substitutes the latest 10-K.
  - Inspect each output's `accession`, `form`, `filing_date`, `statement_type`, and `periods` before ratio analysis. A full-text fallback is not structured financial data. Missing statements or unavailable XBRL are coverage gaps; extract from the selected text where possible and retain units, consolidated scope, and comparable periods.
  - Run ratio analysis:
    ```bash
    uv run python tools/financial_ratios.py analyze $WORKDIR/income.json $WORKDIR/balance.json --cashflow $WORKDIR/cashflow.json --output $WORKDIR/ratios.json
    ```
  - Review ratios for anomalies: margin compression, earnings/cash divergence, high accruals, pass-through indicators
  - Record each anomaly as a separate finding with `--type financial`
  - Screening examples include gross margin below 5%, operating cash flow negative while net income is positive, accruals above 10%, and receivables outgrowing revenue. Interpret these against sector, accounting policies, periods, and peers; they do not establish pass-through activity or misconduct.

- [ ] **Accounting policy changes** (footnotes, typically Note 1-2)
  - Revenue recognition methodology
  - Depreciation/amortization methods and useful life assumptions
  - Changes in estimates or policies (and when they occurred)
  - Compare to prior year filing if available — policy changes coinciding with earnings pressure are significant

- [ ] **Auditor information** (filing signature page / Exhibit 99)
  - Which firm? How long have they been auditor?
  - Any going concern qualifications?
  - Any audit disagreements or scope limitations?
  - Auditor change during investigation-relevant period is a red flag

#### DEF 14A (Proxy Statement) Extraction Checklist

- [ ] **Board of directors** — full list with employer affiliations, committee memberships
- [ ] **Executive compensation** — Summary Compensation Table, stock option grants, pension values
- [ ] **Related-party transactions** — mandatory SEC disclosure section
- [ ] **Shareholder proposals** — who submitted, what they asked, how the vote went
- [ ] **Change-of-control provisions** — golden parachutes, acceleration of equity vesting
- [ ] **Director independence** — who qualifies, who doesn't, and why (conflicts disclosed)

#### SC 13D / 13G (Beneficial Ownership) Extraction Checklist

- [ ] **Identity of filer and associates** — who is acquiring, and who are they coordinating with?
- [ ] **Source and amount of funds** — where did the money come from?
- [ ] **Purpose of transaction** — activist intent? Passive investment? Merger plans?
- [ ] **Plans for changes** — board seats sought, proposed transactions, structural changes
- [ ] **Contracts and understandings** — joint filing agreements, voting arrangements

#### 8-K (Material Events) Extraction Checklist

- [ ] **Event type** — officer departure, acquisition, bankruptcy, restatement, contract award
- [ ] **Financial impact** — dollar figures, timeline
- [ ] **Named persons and entities** — who is involved?
- [ ] **Effective dates and conditions** — when does this take effect?

### 4. Cross-Reference Against Investigation

For every person and entity name extracted from the filing:

```bash
# Check if already in our database
uv run python tools/entity_tracker.py lookup --name "<NAME>"

# Check for existing findings
uv run python tools/findings_tracker.py search "<NAME>" --output $WORKDIR/xref-<slug>.json

# Check connections using the pinned database/profile
uv run python tools/findings_tracker.py connections "<NAME>" --output "$WORKDIR/connections-<slug>.json"
```

Flag names that appear in the investigation profile's `key_persons` or `known_addresses`.

### 5. Insider Transaction Analysis (if person-related)

```bash
uv run python tools/query_edgar.py insider <CIK> --detail --output $WORKDIR/insider-detail.json
```

Read the parsed XML data. Map:
- **Who** is trading (Director, Officer, 10%+ Owner)
- **What** they're trading (shares, options, grants)
- **When** relative to key_dates in the investigation
- **Pattern**: consistent selling before bad news? Buying before announcements?

### 6. Record Findings

Persist supported findings and resolved entities as coherent extraction units finish; keep an evidence ledger for work still being reconciled. Check existing records before adding duplicates. Preserve quoted passages and source artifacts beyond the temporary workdir when they support persisted findings, following `docs/GIT_WORKFLOW.md`.

One finding per discrete factual discovery. **Do not batch into one mega-finding.**

```bash
# Direct quote from filing text
uv run python tools/findings_tracker.py add \
  --target "<COMPANY>" \
  --summary "<One-line factual summary>" \
  --type <identity|financial|relationship|legal> \
  --evidence "SEC:CIK<NUM>:<ACCESSION>" \
  --claim-type direct_quote \
  --source-quote "SEC:CIK<NUM>:<ACCESSION>:exact text from filing" \
  --sources edgar \
  --confidence confirmed

# Paraphrased disclosure
uv run python tools/findings_tracker.py add \
  --target "<COMPANY>" \
  --summary "<Summary of disclosed information>" \
  --type financial \
  --evidence "SEC:CIK<NUM>:<ACCESSION>" \
  --claim-type paraphrase \
  --source-quote "SEC:CIK<NUM>:<ACCESSION>:relevant text from filing" \
  --sources edgar \
  --confidence high
```

Register discovered entities and officers:
```bash
uv run python tools/entity_tracker.py add-entity --name "<SUBSIDIARY>" --entity-type llc --jurisdiction "<STATE>" --source "SEC:CIK<NUM>"
uv run python tools/entity_tracker.py add-role --entity-id <ID> --person-name "<OFFICER>" --role "<TITLE>" --source "SEC:CIK<NUM>"
```

### 7. Create Follow-Up Leads

Create leads for unresolved, relevant questions with a concrete next step. A newly mentioned name alone does not require a new investigation.

```bash
# New person discovered in filing
uv run python tools/lead_tracker.py add \
  --title "Investigate <PERSON> — officer of <COMPANY>, related-party transaction disclosed" \
  --category person --priority medium \
  --target "<PERSON>" --source "agent:analyze-filing" \
  --evidence "SEC:CIK<NUM>:<ACCESSION>"

# Subsidiary worth tracing
uv run python tools/lead_tracker.py add \
  --title "Trace <SUBSIDIARY> — subsidiary in <JURISDICTION>, <OWNERSHIP>% owned" \
  --category entity --priority medium \
  --target "<SUBSIDIARY>" --source "agent:analyze-filing"

# Referenced litigation
uv run python tools/lead_tracker.py add \
  --title "Analyze case: <CASE_NAME> — disclosed in <COMPANY> 10-K risk factors" \
  --category case --priority medium \
  --target "<CASE_NAME>" --source "agent:analyze-filing"
```

### 8. Stop Conditions

- The requested question is answered with recorded scope, or all applicable checklist items are covered for a full filing review
- All discovered names cross-referenced against investigation DB
- Insider transactions analyzed (if person-related investigation)
- The requested form or exact requested URL was honored
- The accession index was inventoried; the primary form, load-bearing exhibits,
  and incorporated documents were saved and read through their recorded
  `line_count`, or each unavailable/pending document was explicitly recorded
- Structured statements and ratios retain the selected accession and reporting periods
- The final report identifies findings, contradictions, source/document coverage, artifacts, and remaining work. Continue through recoverable failures; when an external dependency prevents completion, report partial coverage and an exact resumption step. Do not claim complete package coverage while required incorporated documents remain pending.
