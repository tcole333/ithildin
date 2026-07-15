# Candidate Gates, Rubric, and Output Contracts

Read this file before screening or scoring candidates and before writing the commissioning memo or manifest.

## Hard Gates

Fail closed. Do not use a high score to override a failed gate.

### G0 — Reproducible scope

- Freeze the database maxima/counts, profile list, content inventory, git state, and cutoff time.
- Account for every configured corpus in the coverage ledger.
- Describe index-only or unavailable sources accurately.

### G1 — Evidence-anchored longlist

- Require at least 3 concrete finding IDs or primary record IDs per raw candidate.
- Require a bounded public-interest question and a proposed mechanism.
- Filter unsupported hunches and isolated curiosities.

### G2 — Deduplication and scope home

- Compare profiles, threads, leads, hypotheses, articles, clusters, dossiers, reports, and prior manifests.
- Exclude work already commissioned.
- Mark an angle `merge` when it belongs inside an existing investigation rather than a new profile.

### G3 — Documentary integrity

- Require at least 2 independent primary-source families, or 1 uniquely decisive primary record plus 1 independent corroborative public record.
- Count mirrors, re-OCRs, and repeated reporting of one document once.
- Prevent disputed, retracted, contradicted, or superseded findings from carrying the core proposition.
- Resolve load-bearing identity, amount, date, and chain-of-custody conflicts.
- Allow inference to frame questions, never to satisfy the evidence floor.

### G4 — Apparent novelty

- Run targeted current searches using unique names, amounts, identifiers, phrases, counterparties, and mechanisms.
- Record exact queries, dates, and closest prior coverage.
- Separate already reported components from a potentially new assembled mechanism.
- Use “apparently unreported as of DATE” as a bounded negative-search conclusion.

### G5 — Dedicated-investigation scale

- Require a meaningful consequence involving public money, markets, governance, rights, safety, regulatory integrity, or a generalizable institutional mechanism.
- Require at least 3 distinct, falsifiable research workstreams.
- Require at least 3 specific next records with identifiable acquisition paths.
- Require at least 1 realistically obtainable decisive step.
- Treat a single lookup or missing document as an ordinary lead.

### G6 — Adversarial and legal safety

- State the best innocent explanation and strongest counter-evidence.
- State what is not established.
- Identify identity, causation, allegation, privacy, and defamation risks.
- Define evidence that would kill or materially narrow the investigation.
- Keep allegation-only candidates off the launch list unless a concrete corroboration path exists.
- Reject association-only, salacious-only, victim-identifying, or unresolved-identity premises.

### G7 — Independent judgment

- Obtain 2 independent scores.
- Ask a skeptic to adjudicate when totals differ by more than 10 points or a weighted dimension differs by more than 5 points.
- Permit no launch recommendation.

### G8 — Persistence without queue pollution

- Persist one Markdown memo and one JSON manifest.
- Complete the analysis run with all creation counts at zero.
- Stop for a human commissioning decision.

### G9 — Separate promotion

- Require explicit user selection.
- Dry-run `$init-investigation` before creating a profile.
- Create one YAML-backed profile, then its threads and seed leads.
- Never create candidate profiles or operational leads during discovery.

## 100-Point Rubric

Score only after G0–G7 pass.

| Dimension | Weight | Anchors |
|---|---:|---|
| Documentary strength | 25 | 0 none; 5 secondary allegation; 10 one primary; 15 several records from one family; 20 two independent primary families; 25 a primary chain establishes the core event/mechanism with identities, dates, and amounts resolved |
| Apparent novelty | 20 | 0 same story well covered; 5 reframing; 10 meaningful unassembled angle; 15 novel records or linkage; 20 apparently original core mechanism after exact searches |
| Public consequence | 20 | 0 curiosity; 5 limited private stakes; 10 institutional/local/market impact; 15 national, systemic, or substantial funds; 20 ongoing broad integrity or harm implications |
| Mechanism and dedicated scope | 15 | 0 factoid; 5 one ordinary lead; 10 coherent mechanism with 3+ workstreams; 15 cross-institution system capable of sustaining a profile and multiple outputs |
| Tractability | 10 | 0 decisive evidence unavailable; 3 mostly inaccessible; 5 mixed; 8 several public/FOIA/docket routes; 10 decisive records already obtainable |
| Timeliness | 10 | 0 no peg; 5 durable evergreen; 8 live filing/docket/decision; 10 immediate consequence |

Launch only when:

- total score is at least 80;
- readiness is at least 3;
- documentary strength is at least 18;
- apparent novelty is at least 12;
- public consequence is at least 12;
- mechanism and dedicated scope is at least 9;
- tractability is at least 5;
- every hard gate passes.

Use `watchlist` for scores of 70–79 or one named decisive missing record. Use `reject` below 70. Use `merge` regardless of score when an existing profile owns the scope.

## Readiness Scale

1. Speculative: identity, mechanism, or evidence base unresolved.
2. Signal: credible anchors exist, but several foundational facts remain open.
3. Investigation-ready: several obtainable records can test the proposition.
4. Near-draftable: one decisive check or record remains.
5. Draftable: the core documentary chain is already publication-capable.

Report legal/editorial risk separately as `low`, `medium`, `high`, or `extreme`; do not hide risk inside the score.

## Candidate Packet

Use this structure for every launch and watchlist candidate:

```markdown
### [Rank]. [Candidate title]

**Candidate ID:** stable-kebab-slug
**Working headline/question:** ...
**One-sentence thesis:** ...
**Source profiles:** ...
**Recommendation:** launch | watchlist | merge | reject
**Score / readiness / risk:** 00/100 | 1–5 | low–extreme

#### Why this deserves a dedicated investigation
[Mechanism, consequence, and why this is larger than one lead or an existing article angle.]

#### Established
- Finding # / canonical record ID / primary-source family — exact proposition.

#### Inference and what is not established
- Inference: ...
- Not established: ...

#### Best innocent explanation and counter-evidence
- ...

#### Novelty as of YYYY-MM-DD
- Exact queries: ...
- Closest coverage: ...
- Already reported components: ...
- Apparently new fact/linkage/mechanism: ...

#### Existing-work overlap
- Profile / thread / lead / hypothesis / cluster / article / report: ...
- Why launch separately or where to merge: ...

#### Proposed investigation
- Profile slug and primary subject: ...
- Threads (3–7): ...
- Key people/entities/identifiers: ...
- Key dates: ...
- Relevant corpus tools and structured sources: ...

#### Decisive next records and seed leads
1. Record or test — custodian/path — decisive question — access difficulty.

#### Kill criteria
- ...

#### Score breakdown
- Documentary strength: /25
- Apparent novelty: /20
- Public consequence: /20
- Mechanism and dedicated scope: /15
- Tractability: /10
- Timeliness: /10
```

## Markdown Memo Contract

Write sections in this order:

1. Title, date, run ID, cutoff, and truthful scope label
2. Scope snapshot and corpus coverage ledger
3. Method and hard-gate thresholds
4. Launch recommendations table (maximum 5)
5. Full launch candidate packets
6. Watchlist (maximum 5)
7. Merge recommendations
8. Filtered-out candidates with stable IDs and reasons
9. Coverage, source, and data-quality limitations
10. Promotion choices and explicit statement that no profile was created

## JSON Manifest Contract

Use this top-level shape:

```json
{
  "schema_version": 1,
  "run_id": 0,
  "generated_at": "ISO-8601",
  "scope_label": "full corpus | platform-wide index review | profile review",
  "scope_snapshot": {
    "profile_ids": [],
    "finding_count": 0,
    "finding_max_id": 0,
    "lead_count": 0,
    "lead_max_id": 0,
    "git_commit": "",
    "git_dirty": false,
    "content_inventory": {}
  },
  "coverage_ledger": [],
  "thresholds": {},
  "candidates": [],
  "watchlist": [],
  "merge": [],
  "filtered_out": [],
  "searches": [],
  "limitations": []
}
```

For every candidate object include:

- `candidate_id`, `candidate_fingerprint`, `title`, `working_headline`, `one_sentence_thesis`
- `source_profiles`, `existing_work_overlap`
- `public_interest`, `mechanism`, `why_dedicated`
- `established` with finding IDs, claim/verification state, canonical evidence refs, and source families
- `inferences`, `not_established`, `best_innocent_explanation`, `counter_evidence`
- `novelty` with as-of date, exact queries, closest coverage, and novelty class
- `proposed_profile_slug`, `proposed_threads`, `key_entities`, `key_dates`
- `next_records`, `seed_leads`, `kill_criteria`, `risks`
- `gate_results`, `score_breakdown`, `total_score`, `readiness_1_to_5`, `risk_level`
- `recommendation` as `launch`, `watchlist`, `merge`, or `reject`

Keep stable candidate IDs across later runs. Record prior IDs when merging or renaming a candidate.

When enough canonical information exists, also store a reproducible fingerprint derived from the sorted canonical evidence references, canonical target, and normalized investigation question. Do not use a title alone as identity.
