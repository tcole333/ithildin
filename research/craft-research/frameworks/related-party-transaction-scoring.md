---
name: Related Party Transaction Scoring
slug: related-party-transaction-scoring
domain: financial-crime
source: "Gordon et al. (2004) 'RPTs and Corporate Governance'; Kohlbeck & Mayhew (2010); SMCI prototype analysis (2026) — Liang family entity network"
status: adopted
created: 2026-03-22
grounding_findings: [6870, 6872, 6879, 6884, 6887, 4159, 4196, 5054, 4372, 6278, 6281, 11517]
related_models: [fiduciary-inversion, compliance-theater, peripheral-collapse, manufactured-dependency]
detection_keywords:
  - ["related party", "controlled entity", "family member", "affiliated"]
  - ["below market", "above market", "non-arm's length", "sweetheart"]
  - ["officer loan", "insider purchase", "management company", "consulting agreement"]
  - ["Ablecom", "Compuware", "Aterra", "nominee", "controlled supplier"]
  - ["transfer pricing", "intercompany", "cost-plus", "at cost"]
minimum_trigger: "Related-party transactions >5% of revenue or >10% of COGS, especially when counterparty is family-controlled"
anti_pattern: "Many conglomerates have legitimate intercompany transactions; arms-length pricing validated by independent appraisal; RPTs that are fully disclosed with market-rate terms"
---

## Definition

Related Party Transaction (RPT) Scoring evaluates the risk profile of transactions between a company and its officers, directors, their family members, or entities they control. The framework scores RPTs on four dimensions: **materiality** (how large relative to total operations), **pricing opacity** (how transparent the terms are), **counterparty control** (how concentrated control is in the hands of insiders), and **oversight quality** (how robust the board and audit committee review process is).

RPTs are not inherently problematic — many legitimate business relationships involve related parties. The risk emerges when the transactions are material enough to distort financial results, conducted at non-market prices, controlled by insiders who benefit personally, and insufficiently overseen by independent governance. The combination of these factors creates a channel for value extraction from public shareholders to insiders.

In this investigation: SMCI represents the paradigmatic case. $650.7M in cost of sales (3.3% of COGS) flows through Ablecom ($321.9M) and Compuware ($328.3M), both controlled by CEO Charles Liang's brothers (F6870). Ablecom manufactured 95.4% of SMCI's chassis requirements — a near-total manufacturing dependency on a family-controlled entity (F6879). The CEO personally owes $16.8M to his brother's (Ablecom CEO's) spouse (F6872). The Liang family network spans 8 entities with cross-ownership: Liangs own ~10.5% of Ablecom, Ablecom owns ~15% of Compuware, Ablecom/Compuware own ~30% of Leadtek (F6884). One of SMCI's four unremediated material weaknesses is specifically the "failure to timely identify and disclose new related party transactions."

## Detection Markers

### Materiality Scoring
- **Critical** (score 4): RPTs >10% of revenue or >20% of COGS
- **High** (score 3): RPTs 5-10% of revenue or 10-20% of COGS
- **Moderate** (score 2): RPTs 1-5% of revenue or 5-10% of COGS
- **Low** (score 1): RPTs <1% of revenue or <5% of COGS

### Pricing Opacity Scoring
- **Opaque** (score 4): No pricing methodology disclosed, "market terms" asserted without validation
- **Vague** (score 3): General pricing methodology described but no independent verification
- **Partial** (score 2): Some terms disclosed, no independent fairness opinion
- **Transparent** (score 1): Full terms disclosed with independent appraisal or committee review

### Counterparty Control Scoring
- **Family-controlled** (score 4): CEO/officer family members control the counterparty (SMCI: brothers run Ablecom and Compuware)
- **Officer-controlled** (score 3): Officer or director directly controls or has significant influence
- **Cross-owned** (score 2): Partial ownership by insiders but independent management
- **Arm's length** (score 1): Genuinely independent counterparty with incidental board overlap

### Oversight Quality Scoring
- **Failed** (score 4): Material weakness related to RPT identification/disclosure (SMCI)
- **Weak** (score 3): Audit committee includes non-independent members or controlled company exemption applies
- **Standard** (score 2): Independent audit committee review disclosed but no independent fairness opinion
- **Strong** (score 1): Independent committee + independent pricing validation + explicit board approval documented

### Compound Score
Total = Materiality + Pricing Opacity + Counterparty Control + Oversight Quality (range: 4-16)
- **12-16**: Severe — triggers investigation lead (high priority)
- **8-11**: Elevated — triggers investigation lead (medium priority)
- **5-7**: Notable — record as finding, monitor
- **4**: Normal — note for completeness

SMCI scores approximately 13-14 (Critical materiality + Vague pricing + Family-controlled + Failed oversight).

## Boundary Conditions

- **Vertical integration**: Companies that own their supply chain (e.g., Apple manufacturing components) are NOT the same as RPTs with family entities. The distinction is whether the related party is owned by the *company* (consolidated subsidiary) or owned by *individuals* who also control the company
- **Controlled company exemption**: NASDAQ/NYSE allow "controlled companies" (>50% voting power held by one person/group) to opt out of governance requirements including independent audit committees. This is a governance *choice*, not a governance *failure*, but it eliminates the primary RPT oversight mechanism
- **De minimis transactions**: Small RPTs (CEO's son employed as engineer at market salary) are common and benign. The framework focuses on transactions material enough to affect financial results
- **Cultural considerations**: In many non-US business cultures, family business networks are the norm. The framework evaluates risk to *public shareholders*, not cultural appropriateness

## Limitations

This framework identifies structural risk factors but cannot determine whether specific transactions are abusive without examining the actual pricing terms, which are rarely fully disclosed. A score of 14 doesn't prove extraction — it proves the *conditions for extraction* exist. Proving actual harm requires either (a) demonstrating non-market pricing through comparable analysis, or (b) identifying specific transactions where insiders benefited at shareholder expense. This typically requires /analyze-filing depth analysis of footnotes combined with corporate registry cross-referencing via /trace-entity.

## Evaluation (2026-07-11)

Promoted candidate → adopted. Grounding now spans four independent clusters, which is what the compound-scoring design needs: the SMCI Liang-family network (F6870, F6872, F6879, F6884), the GD Culture / Pallas BVI acquisition (F4159, F4196, F5054 — a 233%-of-shares related-party purchase from shell-company sellers), disclosed-but-material RPTs at Oscar Health/Thrive (F4372) and CRML (F6278, F6281), plus the governance-adjacent variants: Karp's aircraft reimbursement doubling (F6887) and the undisclosed Neumann-Besmertnik relationship behind the Conductor acquisition (F11517 — an RPT that *escaped* S-1 disclosure, the failure mode the oversight-quality dimension exists to catch). The scoring rubric discriminated correctly across all four clusters in testing (SMCI severe; Oscar notable; CRML elevated). Detection keywords already live; model_detector now loads this lens.
