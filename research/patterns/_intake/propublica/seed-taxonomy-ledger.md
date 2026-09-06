# Wave-1 Seed Taxonomy Ledger (provenance for retired-priors accounting)

The wave-1 extraction agents (reports 01–08) were seeded with per-cluster starting taxonomies as HYPOTHESES
("code against these, extend/split when the evidence demands — note new tags you coin"). Wave-2 agents
(reports 11–16) received no taxonomy. This ledger records the seed assignments, recovered verbatim from the
wave-1 agent prompts (prior session transcript, 2026-07-28), so the ontology's retired-priors and
seeded-vs-emergent claims are auditable without that transcript.

## Seeded FINDING TYPES (union: 26 distinct after normalizing name variants; 29 raw)

| Seeded tag | Seeded into clusters |
|---|---|
| access-brokerage | judicial-ethics |
| algorithmic-or-systematic-denial | tax-wealth, healthcare, criminal-justice, corporate-consumer, environment-labor-tech |
| anomalous-vendor | gov-spending |
| charity-mission-inversion | tax-wealth, dark-money, healthcare, gov-spending |
| concentrated-harm-hotspot | tax-wealth, environment-labor-tech |
| conduit-network | dark-money |
| dark-pattern/consumer-deception | corporate-consumer |
| disparate-impact-by-race-or-geography | criminal-justice, corporate-consumer, environment-labor-tech |
| donor-anonymization-technique | dark-money |
| due-process-bypass | criminal-justice |
| extraction-from-captive-population | tax-wealth, healthcare, criminal-justice, corporate-consumer, gov-spending, environment-labor-tech |
| fraud-enablement-by-design | tax-wealth, dark-money, healthcare, criminal-justice, corporate-consumer, gov-spending |
| influence-laundering-via-intermediaries | tax-wealth, judicial-ethics, dark-money |
| institutional-coverup/records-suppression (also bare "institutional-coverup") | tax-wealth, judicial-ethics, healthcare, criminal-justice, gov-spending, environment-labor-tech |
| platform-complicity-by-design | environment-labor-tech |
| policy-erosion-across-jurisdictions | environment-labor-tech |
| preferential-carve-out | tax-wealth, judicial-ethics, dark-money, gov-spending |
| recusal-failure | judicial-ethics |
| regulatory-capture (variants: /revolving-door, /lobbying-to-preserve-rents, bare) | tax-wealth, judicial-ethics, healthcare, corporate-consumer, environment-labor-tech |
| self-dealing/related-party | tax-wealth, judicial-ethics, healthcare, corporate-consumer, gov-spending |
| statistical-outlier-practitioner | tax-wealth, healthcare, criminal-justice |
| two-books-asymmetry | tax-wealth, judicial-ethics, dark-money, healthcare, corporate-consumer, gov-spending |
| undisclosed-benefit-to-official | tax-wealth, judicial-ethics, dark-money |
| undisclosed-financial-conflict | healthcare |
| warning-ignored-before-disaster | gov-spending |
| wealth-defense-technique | tax-wealth |

## Seeded DETECTION SIGNATURES (union: 19)

| Seeded tag | Seeded into clusters |
|---|---|
| beneficiary-reverse-engineering | tax-wealth, judicial-ethics, dark-money, gov-spending |
| cross-jurisdiction-comparison | environment-labor-tech |
| crowdsourced-case-aggregation | all 8 |
| denominator-construction | all 8 |
| disclosure-gap-triangulation | tax-wealth, judicial-ethics, dark-money, healthcare, criminal-justice, corporate-consumer, gov-spending (7 — not environment-labor-tech) |
| entity-age-vs-award-diff | gov-spending |
| grant-chain-tracing | dark-money |
| ground-truth-construction | criminal-justice |
| hotspot-mapping-from-model-data | tax-wealth, environment-labor-tech |
| internal-rulebook-acquisition | all 8 |
| litigation-discovery-mining | corporate-consumer |
| named-cohort-tracing | all 8 |
| outlier-in-microdata | all 8 |
| platform-experiment | environment-labor-tech |
| policy-shadow-measurement | tax-wealth, judicial-ethics, dark-money, healthcare, criminal-justice |
| silo-join-on-hard-identifier | all 8 |
| site-forensics | corporate-consumer |
| temporal-correlation | all 8 |
| two-books-diff | all 8 |

Notes: "seeded into N clusters" counts prompt occurrences after normalizing slash-variants; each cluster prompt
carried a subset tailored to the beat (the full per-prompt blocks are preserved in the prior session transcript
`~/.claude/projects/-Users-travcole-projects-osint-research/13891cf8-bfc3-45ac-b770-153ca90b346e.jsonl`, Agent
tool calls, "STARTING TAXONOMIES" sections). The "9 of 26 seeded finding types became single-cluster dialects"
claim in the ontology derives from diffing this ledger against `tally/finding-type-lines.txt`.
