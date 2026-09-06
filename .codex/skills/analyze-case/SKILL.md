---
name: analyze-case
description: Court case deep analysis — read full opinions, extract parties/allegations/amounts, trace related litigation
---

# $analyze-case

Analyze court records for attributed factual statements, parties, monetary figures, procedural posture, and related proceedings. Use reasoning to choose useful searches and distinguish allegations, assumed facts, findings of fact, and holdings. Persist discrete supported discoveries with their source locations; label interpretations and uncertainty.

## Arguments

- `$analyze-case "Palantir Technologies"` — search CourtListener for cases by party name
- `$analyze-case --docket-id 67890123` — analyze a specific docket
- `$analyze-case --court nysd` — filter by court (e.g., scotus, ca2, nysd, cacd)

### Context Loading
Before scoped work, read `docs/RESEARCH_WORKFLOW_CONTRACT.md`, pin the resolved profile/database, and load `investigation_context.py show` under that environment. Honor the requested docket, court, parties, and period.

Independent document or related-case reviews may use native subagents supervised in the current task. Inherit the configured model, pass pinned context and unique report paths, assign evidence ownership, collect every report, and reconcile procedural posture and contradictions before final synthesis.

## Process

### 0. Session Setup
```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

### 1. Find the Case(s)

```bash
# Search by party name
uv run python tools/query_courtlistener.py party "<PARTY_NAME>" --court <COURT> --output $WORKDIR/cl-party.json

# Search RECAP dockets
uv run python tools/query_courtlistener.py cases "<PARTY_NAME>" --court <COURT> --output $WORKDIR/cl-cases.json

# Or get specific docket by ID
uv run python tools/query_courtlistener.py docket <DOCKET_ID> --output $WORKDIR/cl-docket.json

# Search with field operators (combine multiple)
uv run python tools/query_courtlistener.py search --party "<PARTY>" --court <COURT> --output $WORKDIR/cl-search.json
uv run python tools/query_courtlistener.py search --attorney "<ATTORNEY>" --output $WORKDIR/cl-attorney.json
uv run python tools/query_courtlistener.py search --firm "<FIRM>" --output $WORKDIR/cl-firm.json

# Search opinions
uv run python tools/query_courtlistener.py search "<QUERY>" --type o --output $WORKDIR/cl-opinions.json
uv run python tools/query_courtlistener.py search "<QUERY>" --type o --semantic --output $WORKDIR/cl-semantic.json
```

Review results. For each case:
- Nature of suit (fraud, securities, antitrust, RICO, contract, employment)
- Date filed / date terminated
- Court and judge
- Whether it's still active

Prioritize cases that are: (a) filed in the investigation's time window, (b) involve investigation-linked parties, (c) allege fraud, corruption, or regulatory violations.

### 2. Read Full Opinion Text

Identify the ID type from the returned record. CourtListener's cluster and raw opinion ID spaces overlap, so use an explicit selector and preserve the complete response:

```bash
# Inventory the cluster and its sub_opinions (including separate opinions)
uv run python tools/query_courtlistener.py cluster <CLUSTER_ID> --output "$WORKDIR/cl-cluster-<CLUSTER_ID>.json"
# Fetch each relevant raw opinion ID from that inventory
uv run python tools/query_courtlistener.py opinion <RAW_OPINION_ID> --id-type opinion --output "$WORKDIR/cl-opinion-<RAW_OPINION_ID>.json"
# Or search when no cluster is identified yet
uv run python tools/query_courtlistener.py search "<CASE_NAME>" --type o --output "$WORKDIR/cl-opinions.json"
```

Read the saved opinion's complete text-bearing field (`plain_text` or the available HTML/XML field), preserving the raw artifact and document identity. Choose navigation or chunking suited to its size, and track document/section coverage so a terminal preview is never mistaken for the full opinion. Read the relevant opinions in full, including context necessary to interpret quotations and procedural posture; record missing or pending documents explicitly. Use `CourtListener:opinion/<CLUSTER_ID>` for the public opinion-page citation while retaining the raw opinion ID, source URL, and paragraph/page location. Use `CourtListener:docket/<DOCKET_ID>` for docket claims. A docket citation alone does not identify a quoted pleading or opinion; retain the exact document URL/ID and location.

### 2b. Search and Download RECAP Documents

RECAP documents contain filed court documents (memoranda, transcripts, exhibits, motions) — often richer than the opinion alone. Search for them:

```bash
# Search for RECAP documents related to this case
uv run python tools/query_courtlistener.py recap-search "<CASE_NAME> <KEY_TERMS>" --court <COURT> --limit 20 --output "$WORKDIR/cl-recap.json"
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

Once you know the parties, search for their other litigation and trace the citation graph:

```bash
# Other cases by same defendant (field operator)
uv run python tools/query_courtlistener.py party "<DEFENDANT>" --output $WORKDIR/cl-related-def.json

# Other cases by same plaintiff
uv run python tools/query_courtlistener.py party "<PLAINTIFF>" --output $WORKDIR/cl-related-plt.json

# Citation graph — what does this opinion cite and what cites it?
uv run python tools/query_courtlistener.py citations <CLUSTER_ID> --output $WORKDIR/cl-citations.json

# Resolve a specific citation to a cluster ID
uv run python tools/query_courtlistener.py resolve-cite "<CITATION_TEXT>" --output $WORKDIR/cl-resolve.json

# Get opinion cluster detail (panel composition, citation count)
uv run python tools/query_courtlistener.py cluster <CLUSTER_ID> --output $WORKDIR/cl-cluster.json

# Semantic search for conceptually related opinions
uv run python tools/query_courtlistener.py search "<LEGAL_THEORY>" --type o --semantic --output $WORKDIR/cl-related-opinions.json

# FJC database — search federal case metadata by defendant
uv run python tools/query_courtlistener.py fjc --defendant "<DEFENDANT>" --output $WORKDIR/cl-fjc.json
```

Look for patterns:
- [ ] **Serial litigant**: same party sued repeatedly for similar conduct
- [ ] **Regulatory enforcement pattern**: multiple agencies pursuing the same entity
- [ ] **Related transactions**: other litigation arising from the same underlying deal or scheme
- [ ] **Coordinated cases**: parallel cases in multiple jurisdictions (MDL, class actions)

### 5. Judge Analysis (if relevant)

If the case involves a judge whose impartiality matters:

```bash
# Full career timeline (positions, education, political affiliations, appointer)
uv run python tools/query_courtlistener.py career "<JUDGE_NAME>" --output $WORKDIR/cl-career.json

# Check investments for conflicts with case parties (1.9M records searchable)
uv run python tools/query_courtlistener.py investments "<COMPANY_NAME>" --output $WORKDIR/cl-investments.json

# Check travel reimbursements (who paid for judge's travel?)
uv run python tools/query_courtlistener.py reimbursements "<SOURCE>" --output $WORKDIR/cl-reimb.json

# Financial disclosures by person ID
uv run python tools/query_courtlistener.py disclosures --person-id <JUDGE_ID> --output $WORKDIR/cl-disclosures.json
```

**Investment conflict check**: For each party in the case, search judge investments:
- `investments "<PARTY_COMPANY>"` — does the judge hold stock in a party?
- `reimbursements "<PARTY>"` — did a party pay for judge travel/speaking?
- Check career positions for prior employment at firms representing parties

### 6. Cross-Reference Against Investigation

```bash
# Every party name → check entities and findings
uv run python tools/entity_tracker.py lookup --name "<PARTY>"
uv run python tools/findings_tracker.py search "<PARTY>" --output $WORKDIR/xref-<slug>.json

# Case timeline dates → compare against key_dates in the pinned context
uv run python tools/investigation_context.py show --json

# Monetary figures → compare against financial findings in the pinned context
uv run python tools/findings_tracker.py list --target "<PARTY>" --type financial --output "$WORKDIR/financial-xref-<slug>.json"
```

Tracker lists are bounded. If results reach the selected limit, expand the
lookup or use the profile-scoped `analysis_export.py findings-dump` artifact
and filter financial rows for the party. Record the searched scope before
concluding that a cross-reference is absent.

### 7. Record Findings

One finding per factual discovery from the opinion:

```bash
# Direct quote from court opinion (highest confidence)
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Attributed factual finding stated by the court>" \
  --detail "Raw opinion <RAW_OPINION_ID>; <DOCUMENT_URL>; <PAGE_OR_PARAGRAPH>; procedural posture <POSTURE>" \
  --type legal \
  --evidence "CourtListener:opinion/<CLUSTER_ID>" \
  --claim-type direct_quote \
  --source-quote "CourtListener:opinion/<CLUSTER_ID>:exact text from opinion" \
  --sources courtlistener \
  --confidence confirmed

# Paraphrased allegation
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Summary of allegation from complaint/opinion>" \
  --type legal \
  --evidence "<EXACT_DOCUMENT_URL>" \
  --claim-type paraphrase \
  --source-quote "<EXACT_DOCUMENT_URL>:relevant text preserving allegation attribution" \
  --sources courtlistener \
  --confidence high

# Cross-case inference
uv run python tools/findings_tracker.py add \
  --target "<PARTY>" \
  --summary "<Observation from comparing related cases>" \
  --type legal \
  --evidence "CourtListener:opinion/<CLUSTER_ID_1>" "CourtListener:opinion/<CLUSTER_ID_2>" \
  --claim-type inference \
  --source-quote "CourtListener:opinion/<CLUSTER_ID_1>:relevant text from first opinion" \
  --source-quote "CourtListener:opinion/<CLUSTER_ID_2>:relevant text from second opinion" \
  --sources courtlistener \
  --confidence medium
```

Register discovered entities and relationships:
```bash
uv run python tools/entity_tracker.py add-entity --name "<ENTITY>" --entity-type <TYPE> --source "CourtListener:docket/<DOCKET_ID>"
uv run python tools/findings_tracker.py connect --person-a "<PLAINTIFF>" --person-b "<DEFENDANT>" --type legal --description "Opposing parties in <CASE_NAME>" --finding-id <SUPPORTING_FINDING_ID>
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

## Completion report

Write `$WORKDIR/report-analyze-case.md` with the requested case scope, document identities and coverage, procedural posture, finding/entity/lead IDs, attributed allegations and established outcomes, contradictions, missing documents, and next useful steps. Preserve source artifacts and any resumable reading state. Report partial coverage explicitly; related-case discovery does not require recursively analyzing every case before completing the requested case.
