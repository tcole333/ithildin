---
name: analyze-case
description: Court case deep analysis — read full opinions, extract parties/allegations/amounts, trace related litigation
user_invocable: true
---

# /analyze-case

**TIER 1: DEPTH ANALYSIS** — This skill reads full court opinions and extracts structured intelligence from complex litigation. LLMs can process 10-50KB opinion texts, identify every named party and corporate entity, extract specific factual allegations and monetary figures, and cross-reference everything against the investigation database. Record every factual discovery separately. Do not assess the legal merits — extract facts, parties, and money.

## Arguments

- `/analyze-case "Palantir Technologies"` — search CourtListener for cases by party name
- `/analyze-case --docket-id 67890123` — analyze a specific docket
- `/analyze-case --court nysd` — filter by court (e.g., scotus, ca2, nysd, cacd)

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

### 1. Find the Case(s)

```bash
# Search by party name — RECAP dockets
uv run python tools/query_courtlistener.py cases "<PARTY_NAME>" --output $WORKDIR/cl-cases.json

# Or get specific docket
uv run python tools/query_courtlistener.py docket <DOCKET_ID> --output $WORKDIR/cl-docket.json

# Search opinions (full-text searchable)
uv run python tools/query_courtlistener.py search "<PARTY_NAME>" --type opinions --output $WORKDIR/cl-opinions.json
```

Review results. For each case:
- Nature of suit (fraud, securities, antitrust, RICO, contract, employment)
- Date filed / date terminated
- Court and judge
- Whether it's still active

Prioritize cases that are: (a) filed in the investigation's time window, (b) involve investigation-linked parties, (c) allege fraud, corruption, or regulatory violations.

### 2. Read Full Opinion Text

Use the `opinion` command to fetch full opinion text directly from the API:

```bash
# Fetch by opinion/cluster ID (from search results or docket clusters field)
uv run python tools/query_courtlistener.py opinion <OPINION_ID> --lines 1000
```

If no opinion ID is available, search for opinions by case name:
```bash
uv run python tools/query_courtlistener.py search "<CASE_NAME>" --type o --limit 5
```

**This is the core LLM advantage.** A court opinion may be 20-50 pages (100K+ chars). Read it fully and extract:

### 2b. Search and Download RECAP Documents

RECAP documents contain filed court documents (memoranda, transcripts, exhibits, motions) — often richer than the opinion alone. Search for them:

```bash
# Search for RECAP documents related to this case
uv run python tools/query_courtlistener.py recap-search "<CASE_NAME> <KEY_TERMS>" --court <COURT> --limit 20
```

For each valuable document found (memoranda, government proffers, exhibit lists, sentencing memos):

```bash
# Download the PDF and extract text
uv run python tools/query_courtlistener.py download "<DOWNLOAD_URL>" $WORKDIR/doc-<NUM>.pdf --extract-text
```

Then read the extracted text file (`$WORKDIR/doc-<NUM>.txt`) for analysis. **RECAP documents are free to download** — the PDFs are hosted on storage.courtlistener.com.

Priority documents to look for:
- Government memoranda (legal theories, enterprise descriptions, money laundering mechanics)
- Superseding indictments (full defendant list, charge details)
- Sentencing memoranda (financial details, cooperation agreements)
- Pretrial hearing transcripts (factual proffers)
- Exhibit lists (names every document and entity the government will introduce)

**DB-first principle**: Record findings from each document as you read it, not after reading all documents. If you run out of context mid-analysis, unrecorded observations are lost.

### 3. Extract Structured Information

Read the opinion text systematically. **Do not skim — process the entire document.**

#### Parties Extraction
- [ ] **Plaintiffs**: full legal names, individual or entity, role in the dispute
- [ ] **Defendants**: full legal names, individual or entity, role in the dispute
- [ ] **Intervenors / Amici**: who else cared enough to participate?
- [ ] **Witnesses mentioned**: named individuals referenced in factual findings
- [ ] **Corporate entities**: every LLC, trust, fund, corporation mentioned in the opinion
- [ ] **Government agencies**: regulatory bodies, prosecutors, agencies mentioned

For each name, immediately check:
```bash
uv run python tools/entity_tracker.py lookup --name "<NAME>"
uv run python tools/findings_tracker.py search "<NAME>" --output $WORKDIR/xref-<slug>.json
```

#### Factual Allegations
- [ ] **What happened**: specific acts described in the opinion's factual background
- [ ] **When**: every date mentioned in the factual narrative
- [ ] **Where**: jurisdictions, locations of events, meeting places
- [ ] **Who did what to whom**: the chain of actions
- [ ] **What documents are referenced**: contracts, emails, financial records cited by the court

#### Monetary Figures
- [ ] **Damages sought**: what plaintiffs claimed
- [ ] **Settlement amount**: if case settled, the terms
- [ ] **Fines / disgorgement**: regulatory penalties imposed
- [ ] **Transaction amounts**: specific financial transactions described in the facts
- [ ] **Attorney fees**: if awarded

#### Legal Theories and Outcomes
- [ ] **Causes of action**: fraud, breach of fiduciary duty, securities violations, RICO, etc.
- [ ] **Statutes cited**: specific laws invoked (Securities Act § 10(b), RICO 18 U.S.C. § 1962, etc.)
- [ ] **Outcome**: dismissed, settled, judgment for plaintiff/defendant, consent decree
- [ ] **Remedies**: injunctions, monitoring requirements, disgorgement, structural reforms

#### Related Proceedings
- [ ] **Other cases referenced**: citations to related litigation
- [ ] **Regulatory actions**: SEC enforcement, DOJ investigations, state AG proceedings
- [ ] **Administrative proceedings**: agency hearings, debarment actions
- [ ] **Criminal proceedings**: parallel criminal cases

### 4. Search for Related Cases

Once you know the parties, search for their other litigation:

```bash
# Other cases involving the same defendant
uv run python tools/query_courtlistener.py cases "<DEFENDANT>" --output $WORKDIR/cl-related-def.json

# Other cases involving the same plaintiff
uv run python tools/query_courtlistener.py cases "<PLAINTIFF>" --output $WORKDIR/cl-related-plt.json

# Opinions mentioning this case
uv run python tools/query_courtlistener.py search "<CASE_CITATION>" --type opinions --output $WORKDIR/cl-citing.json
```

Look for patterns:
- [ ] **Serial litigant**: same party sued repeatedly for similar conduct
- [ ] **Regulatory enforcement pattern**: multiple agencies pursuing the same entity
- [ ] **Related transactions**: other litigation arising from the same underlying deal or scheme
- [ ] **Coordinated cases**: parallel cases in multiple jurisdictions (MDL, class actions)

### 5. Judge Analysis (if relevant)

If the case involves a judge whose impartiality matters:

```bash
# Judge info
uv run python tools/query_courtlistener.py judge "<JUDGE_NAME>" --output $WORKDIR/cl-judge.json

# Financial disclosures (check for conflicts)
uv run python tools/query_courtlistener.py disclosures <JUDGE_ID> <YEAR> --output $WORKDIR/cl-disclosures.json
```

Cross-reference the judge's disclosed investments/positions against the parties in the case.

### 6. Cross-Reference Against Investigation

```bash
# Every party name → check entities and findings
uv run python tools/entity_tracker.py lookup --name "<PARTY>"
uv run python tools/findings_tracker.py search "<PARTY>" --output $WORKDIR/xref-<slug>.json

# Case timeline dates → compare against key_dates
uv run python -c "
import yaml
with open('investigations/<ACTIVE>/config.yaml') as f:
    dates = yaml.safe_load(f).get('key_dates', [])
for d in dates: print(d)
"

# Monetary figures → compare against known financial flows
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
db.row_factory = sqlite3.Row
rows = db.execute('SELECT * FROM findings WHERE finding_type=\"financial\" AND target_name LIKE ?', ('%<PARTY>%',)).fetchall()
for r in rows: print(f'#{r[\"id\"]} {r[\"summary\"][:100]}')
"
```

### 7. Record Findings

One finding per factual discovery from the opinion:

```bash
# Direct quote from court opinion (highest confidence)
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Factual finding stated by the court>" \
  --type legal \
  --evidence "CourtListener:<DOCKET_ID>" \
  --claim-type direct_quote \
  --source-quote "CourtListener:<DOCKET_ID>:exact text from opinion" \
  --sources courtlistener \
  --confidence confirmed

# Paraphrased allegation
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Summary of allegation from complaint/opinion>" \
  --type legal \
  --evidence "CourtListener:<DOCKET_ID>" \
  --claim-type paraphrase \
  --source-quote "CourtListener:<DOCKET_ID>:relevant text" \
  --sources courtlistener \
  --confidence high

# Cross-case inference
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Observation from comparing related cases>" \
  --type legal \
  --evidence "CourtListener:<DOCKET_ID_1>;CourtListener:<DOCKET_ID_2>" \
  --claim-type inference \
  --source-quote "CourtListener:<ID>:relevant text" \
  --sources courtlistener \
  --confidence medium
```

Register discovered entities and relationships:
```bash
uv run python tools/entity_tracker.py add-entity --name "<ENTITY>" --entity-type <TYPE> --source "CourtListener:<DOCKET_ID>"
uv run python tools/findings_tracker.py connect --person-a "<PLAINTIFF>" --person-b "<DEFENDANT>" --type legal --strength strong --evidence "CourtListener:<DOCKET_ID>"
```

### 8. Spawn Follow-Up Leads

```bash
# New party discovered
uv run python tools/lead_tracker.py add \
  --title "Investigate <PARTY> — named in <CASE_NAME>, alleged <ALLEGATION>" \
  --category person --priority medium \
  --target "<PARTY>" --source "agent:analyze-case"

# Related case worth analyzing
uv run python tools/lead_tracker.py add \
  --title "Analyze case: <RELATED_CASE_NAME> — related to <ORIGINAL_CASE>" \
  --category case --priority medium \
  --target "<RELATED_CASE>" --source "agent:analyze-case"

# Referenced regulatory proceeding
uv run python tools/lead_tracker.py add \
  --title "Investigate <AGENCY> proceeding against <PARTY> — referenced in court opinion" \
  --category legal --priority medium \
  --target "<PARTY>" --source "agent:analyze-case"

# Judge conflict of interest
uv run python tools/lead_tracker.py add \
  --title "Judge <NAME> financial conflict — disclosed investments overlap with <PARTY>" \
  --category person --priority high \
  --target "<JUDGE_NAME>" --source "agent:analyze-case"
```

### Stop Conditions

- All relevant opinions read in full (not just snippets)
- All parties cross-referenced against investigation DB
- Related cases searched and cataloged
- Judge analysis completed (if relevant)
- Timeline of case events recorded

## What Makes This Skill Valuable

A human reading a court opinion focuses on the holding — did the plaintiff win? An investigation agent reads the **factual background section**, which is where the court lays out exactly what happened: who met whom, what was said, what money moved, what documents exist. Judges are required to be specific about facts. These factual findings are often the most reliable narrative of events available anywhere — more detailed than news reports, more specific than regulatory filings.

An LLM agent reads the **entire opinion**, extracts **every named party and entity**, maps **every date and dollar amount**, and cross-references everything against the investigation. This surfaces:
- Corporate entities mentioned in passing that connect to other investigation threads
- Specific dates and transaction amounts that corroborate or contradict other evidence
- Witnesses and third parties who may have relevant information
- Related regulatory proceedings the court references
- Judges with financial conflicts of interest disclosed in their own filings
