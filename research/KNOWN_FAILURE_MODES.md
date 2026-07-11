# Known Analytical Failure Modes

This catalog preserves institutional memory for `/review-methodology` and reviewer training. These are documented failures from the platform's own work, not hypothetical examples. Each entry names the bias that contributed to the error and the discipline reviewers should use to prevent a recurrence.

## The Hallucinated Estate Release (July 2026)

**Incident:** An agent claimed that a "June 2025 estate document release" existed. The real page was the November 2025 release the platform already held.

**Bias:** Expectation-driven confabulation (vividness + availability) — an expected, readily imagined release was recalled as an observed one.

**Corrective discipline:** Verify release pages against the primary source before ingesting them. A claimed new corpus requires a URL, publication date, and document-count check.

**Reviewer question:** "Did anyone actually fetch the page this release supposedly came from?"

## The Bates-Adjacency Misattribution (June 2026)

**Incident:** Epstein's redacted 2013–14 emissary was initially attributed to Gulsum Osmanova because her documents sat Bates-adjacent in the corpus. The emissary was later identified as Yulia Stepanova.

**Bias:** Proximity-as-association (contiguity heuristic) — neighboring records were treated as substantively linked.

**Corrective discipline:** Corpus adjacency is a lead, never evidence of linkage. Attribution requires a content-level match.

**Reviewer question:** "Is this connection substantive, or just neighboring pages?"

## The Name-Collision PEP False Positive (June 2026)

**Incident:** Stepanova's husband was matched to a politically exposed "Oleg Stepanov." It was the wrong person with a common name.

**Bias:** Base-rate neglect on name frequency — a name match was overweighted without considering how many people share it.

**Corrective discipline:** Identity resolution requires at least two non-name attributes, such as date of birth, address, employer, or documented relationship, before asserting a match. Check name frequency for common names.

**Reviewer question:** "How many people share this name, and what besides the name ties this one to the claim?"

## The Duplicate-Documentation Incident (June 2026)

**Incident:** An agent re-documented Ehud Barak inside the softbank-caper profile, creating 10 duplicate findings—later retracted—of facts already established in the epstein profile.

**Bias:** Anchoring on own-profile completeness (context blindness) — the current profile was treated as the full universe of prior work.

**Corrective discipline:** Entities are shared across investigations. Query cross-profile findings before dispatching documentation work; cite existing findings instead of re-deriving them.

**Reviewer question:** "Did we check what the other profiles already hold on this entity?"

## The Single-Source Memo Overreach (#9134, July 2026)

**Incident:** A legacy finding asserted a Waitt-brokered Gates–FBI arrangement from one memo's paraphrase. It was disputed after sworn testimony from both principals contradicted it.

**Bias:** Single-source anchoring + paraphrase drift — one derivative account became the narrative anchor and gained certainty through retelling.

**Corrective discipline:** Sworn primary testimony outranks memo paraphrase. The `paraphrase` claim type caps at `high`, and contradiction by two sworn sources triggers the dispute workflow.

**Reviewer question:** "What claim-type is the chain's weakest link, and does anything sworn contradict it?"

## Using This Catalog

`/review-methodology` maps new corrections and retractions from the `corrections` table to these entries. Review all `correction_type` values—`factual_error`, `source_mismatch`, `hallucination`, `outdated`, `refinement`, `merge`, and `retraction`—and disputed or retracted findings. When no existing failure mode fits, propose a new catalog entry with the same incident, bias, corrective-discipline, and reviewer-question structure.
