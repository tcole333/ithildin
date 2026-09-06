---
name: review-article
user-invocable: true
description: Verify an investigative article's claims, citations, legal context, reasoning and editorial quality. Use for article fact-checking or review; use review-dossiers for encyclopedic dossier pages.
---

# /review-article

Review the requested current article and produce an actionable verification report. Default to review-only; if the user also authorized fixes, apply them and review affected claims on final bytes. A writer invoking this skill may use an independent chat-native reviewer, inheriting the configured model. Never fabricate an independent review or delegate to an unattended job by default.

## Inputs and setup

- An article path or cluster ID selects the target.
- With no target, list available `content/articles/*.mdx`.
- `--backlinks-only` narrows the task to link candidates and broken-link checks.
- `--workdir DIR` supplies the parent-owned report location; otherwise create `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)`.

Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and pin the selected profile/database. Work in the current checkout. Read the article in full, then retrieve source context as needed. Record article path/hash, evidence artifacts, verified claims and remaining work in WORKDIR so long reviews resume without losing progress. A valid prior artifact can be reused only for the content/source version it actually covers.

## Evidence and claims

Run these commands on the actual target, replacing the example path:

```bash
uv run python scripts/evidence_audit.py report \
  --article "content/articles/<cluster-id>.mdx" \
  --output "$WORKDIR/evidence-audit.json"
npm --silent --prefix web run report:support-coverage -- \
  --file "content/articles/<cluster-id>.mdx" > "$WORKDIR/support-coverage.json"
```

The audit reads the pinned DB/profile, performs text checks and reports unknowns explicitly. Supply `--source-texts "$WORKDIR/source-texts.json"` for a JSON map from exact evidence refs to UTF-8 artifact paths (relative paths resolve beside the manifest). An EFTA OCR corpus may be supplied explicitly with `--documents-db`. No primary text available means unknown, not pass. Inspect missing/out-of-profile finding IDs, unmapped citations, quote mismatches, missing quotes and integrity issues. A mismatch needs source/OCR inspection; do not automatically “fix” evidence to match the article. Overlap candidates are not adjudicated duplicates.

Confirm the coverage result contains the requested article and current hash, including an unchanged article. If any target is missing, verification is incomplete. A structural support percentage is not semantic claim validation.

Build a claims inventory with assertion, citation/finding ID, claim type, source artifact, result and limitation. For every material assertion:
- Open the cited finding and actual source, not merely a similarly named search result. Verify identity, amount, date, role and the precise proposition. Use `uv run python tools/findings_tracker.py show <ID> --output "$WORKDIR/finding-<ID>.json"`.
- Read sufficient surrounding source context for qualifications and attribution, expanding to the complete document where needed. Keep quoted text and exact evidence identifiers.
- Verify every quoted passage and load-bearing financial figure; do not let a ten-citation sample stand in for full material-claim coverage.
- Verify legal/regulatory claims against current official sources and the rules applicable at the event date. Check recodifications, reporting thresholds, jurisdiction and the described mechanism.
- For contextual facts, cite, qualify or remove. Specific amounts and allegations need actual supporting evidence.
- Preserve allegation/charge/conviction language and distinguish authenticity of a document from truth of its contents.
- Distinguish independent provenance chains from mirrors or repeated reporting. A missing record is evidence only within a justified collection scope.

Every factual sentence needs explicit sentence-local citation support. Analytical conclusions may rely on evidence developed in preceding sections; test whether the conclusion follows, rather than mechanically demanding a token on every analytical sentence.

## Skeptic and epistemic review

Articles can have a thesis and an analytical voice. Test whether the thesis is supported and intelligible; do not apply dossiers' prohibition on editorial argument.

Block unsupported causal claims, scope overreach, unsupported certainty, wrong identities/citations, or material allegations without evidence. Distinguish an observed outcome from inferred intent: evidence that a structure produces a result does not establish that someone designed it for that purpose. Consider the strongest alternative explanation and counter-evidence.

For a claim resting on one provenance chain or an opposition-research, PR or litigation artifact, apply the methodology's MOM/POP/MOSES/EVE checks. Verify authenticity-versus-truth language and preserve caveats. Provenance-opaque aggregator material carries at most medium evidentiary weight.

Apply `research/INVESTIGATIVE_METHODOLOGY.md`'s estimative-language standard. Confidence is an evidence-quality ceiling, not a probability. Likelihood language needs a proposition-specific rationale considering alternatives, independence and material uncertainty. The conclusion may not outrun its weakest necessary evidence link. Do not invent a numeric probability to compensate for weak sourcing.

Check each subject's role and each institution's status at the relevant time. Weight factual errors by their effect on the argument; a material temporal error is blocking regardless of its stylistic category.

## Editorial and presentation review

Evaluate whether a reader can follow the mechanism, evidence and stakes; whether structure follows the evidence; and whether secondary detail overwhelms central claims. Citation diversity helps only when it supplies useful independent evidence. Suggest relevant omitted evidence; do not impose a source-type quota.

Use `research/craft-principles.md` as optional craft guidance. Prefer concrete, restrained language over sensationalism, filler and formulaic transitions. Evaluate patterns in context; a colon, short sentence or repeated subject is not itself a defect. Character counts, length, confidence-framing paragraphs and opening-hook formulas are defaults, not publication conditions. Communicate uncertainty where readers need it without forcing a template.

Check visualization JSON paths and data against the article. Suggest visuals when they clarify chronology, flows, networks or ownership. Link existing dossiers on first mention and relevant related articles; verify every proposed internal target exists. Check current analytical models only where the evidence warrants their use.

## Report and completion

Write `$WORKDIR/verification-report.md` with:
- Exact article path/hash and scope, including any limited review mode.
- Material claims checked, source artifacts, unresolved checks and unavailable sources.
- `BLOCKING`: unsupported material claims, wrong evidence, causal/legal/identity errors or unresolved load-bearing verification.
- `SHOULD FIX`: significant clarity or accuracy issues that do not invalidate the core claim.
- `SUGGESTIONS`: optional craft, source, visualization and linking improvements.
- Each issue's location, evidence, practical impact and proportionate correction.
- Completed structural checks and their target hashes; distinguish them from semantic review.
- Summary verdict: `needs-revision`, `verification-incomplete` or `reviewed`. Use `reviewed` only when material claims were actually checked and no blocking issue remains.

If changes are authorized, apply relevant fixes, verify new/changed claims and rerun checks affected by those changes. Reuse unchanged evidence work and valid content-bound reviews; do not force an unrelated full rewrite. Do not call a changed artifact reviewed using an earlier hash. Publication still follows the repository's release validator and existing user authorization.
