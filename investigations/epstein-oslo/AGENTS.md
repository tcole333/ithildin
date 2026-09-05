# Epstein-Oslo Prehistory Investigation — Agent Context

Profile: `epstein-oslo`. The question: does any Epstein contact, funding, or
facilitation of the Oslo-channel network predate the documented post-2004
record — specifically around the Dec 1992 - Sept 1993 secret channel?

Read `research/hypotheses.md` before doing anything: it holds the three
pre-registered hypotheses (H1 channel role ~3%, H2 pre-2000 network contact
~15-20%, H3 null/reverse-acquisition remainder) and the PRE-COMMITTED update
rules. You report which rules your evidence triggers; you do not invent rules.
An all-null result is a publishable outcome, not a failure.

## Epistemic Ground Rules

**Source tiers:**

- **T1**: Court records, government archives, corporate registries, FAA/NARA
  records, the DOJ release documents themselves (with EFTA/Bates numbers),
  contemporaneous primary documents.
- **T2**: Contemporaneous quality journalism (DN, NRK, Bloomberg, AP, NYT),
  Waage's academic work, participant memoirs (Savir "The Process", Qurei,
  Beilin "Touching Peace", Corbin "The Norway Channel") — memoirs are T2 for
  what happened, T1 for what the author claims about themselves.
- **T3**: Advocacy-inflected outlets (Middle East Eye, Al Jazeera features).
  Leads only; every load-bearing claim requires independent T1/T2.
- **T4**: Unreliable narrators — Hoffenberg, Ben-Menashe, the single alleged
  2020 FBI doc claiming Epstein was "trained as a spy". Log verbatim with
  provenance; never load-bearing.

**Contamination ordering:** primary documents and memoirs before commentary.
Webb-tier synthesis last, if at all, and only to check for missed leads.

**Anti-retrofit guard:** the info environment currently runs "blackmailed
mediator brokered Oslo" as a frame. The 2010s evidence is damning and exerts
gravitational pull on the 1993 question. Date every claim: evidence OF
1992-93 vs evidence FROM the 2010s about nothing.

**Legal care:** Juul/Rod-Larsen are charged (Okokrim, Feb 2026), not
convicted, and deny. Jagland is charged. Appearing in files ≠ wrongdoing.
Maintain the distinction in every output; this may publish.

**Redundancy ≠ corroboration:** DOJ/LMSBAND/Unified/kabasshouse re-OCR the
same primary releases. A shared EFTA file_key across corpora is ONE source.

## Established Territory — cite, do not re-derive

The 2005-2019 relationship is documented under the `epstein` profile (110
findings mention Rod-Larsen/Juul) and `epstein-gates-ipi` (202 findings).
Reference finding IDs instead of re-deriving: #82 (2011 Gates pitch), #75
(2012 IPI Distinguished Fund launch, Epstein founding philanthropist), #105
($250K wire to Rod-Larsen's UNFCU account Dec 2015), #102/#127/#188-#193
(Drammensveien 42 purchase), #116 (Juul "forever grateful"), #143 (will: USD
10M to the couple's two children), #126/#242 (Okokrim charges), #77 (Mongolia
Advisory Board incl. Barak), #131 (IPI as access platform).

**Critical homonym:** finding #138 — "Oslo Play" was Epstein's OWN TERM for a
2018-era network operation involving Middle Eastern politicians through
IPI/Rod-Larsen. Corpus hits on "oslo play" must be classified: (a) the 2016-17
Broadway play thread, (b) Epstein's network-op term, (c) other.

As of 2026-07-17 launch, no finding in investigation.db places
Epstein↔Rod-Larsen contact before 2005 (pre-2005 string hits are name
collisions: Chris Larsen/Ripple, JUUL Labs, unrelated Epstein law firms).

**LEFT-CENSORING WARNING (floors measured 2026-07-17):** the released corpus
cannot see the early 1990s, so the absence above is NOT affirmative evidence
for H3 and must never be cited as such. Measured floors: unified email layer
begins 2008-07 (density only from 2011, peak 2016-17); kabasshouse
financial_transactions begin 1999 (dense from 2001); parseably dated 1991-95
kabasshouse documents number only ~50 of 1.42M — and are overwhelmingly
Pilot's Flight Log / Logbook pages (DOJ-OGR-00015799 through -00015952,
IMAGES006 dataset; plus the Maxwell-trial flight log in USAvJE_FOIA), i.e.
exactly WP1's raw material. A LATE corpus terminus is uninformative; only an
EARLY terminus updates (rule 2). The instruments that can see pre-2000:
flight logs (1991+), the black book (mid-90s-2004), the few dated-90s
artifacts, and external archives (FAFO/ECF/registries/press).

## Evidence Discipline

Claim types and max confidence (hard caps):
- `direct_quote` → can be `confirmed` (if primary source)
- `paraphrase` → max `high`
- `inference` / `synthesis` → max `medium`

Canonical references: EFTA IDs for DOJ-corpus docs (e.g. `EFTA02336502`);
`SOURCE:ID` for others (e.g. `LMSBAND:12345`,
`MUCKROCK:<request>:<file>:p<page>`); URLs for web sources.

## Agent Operating Rules (Codex tier-1)

- **Database: READ-ONLY.** Allowed: query/search/doc/entity/emails/docs/
  triples/cooccurrence/financials/curated/flights/stats subcommands; sqlite3
  SELECT. Forbidden: ANY add/claim/complete/correct/verify/dispute/retract/
  set/ingest/download/crawl-index subcommand; sqlite3 writes; git commands;
  `tools/investigation_context.py set`. You stage findings as JSON for
  orchestrator review — you do not write to investigation.db.
- **File writes:** ONLY your assigned deliverable paths under
  `investigations/epstein-oslo/reports/` plus /tmp scratch. Use
  `--output /tmp/...` for tool JSON output.
- **Invocation:** `uv run python tools/<tool>.py ...` from the repo root.
- **Tool syntax:** `docs/modules/corpora.md` is authoritative. Quirks:
  query_unified.py has NO `search` subcommand (use `emails`/`docs`);
  DocumentCloud anonymous cap is 500 calls/day/IP (creds in .env lift it).
- **Web:** passive collection only. Do not contact any person, do not intrude
  into or actively scan non-public systems, do not file FOIA/registry requests.
  Already-published leaked/public datasets are in scope to analyze. Polite curl
  with a descriptive User-Agent; archive.org/Wayback for dead URLs.
- **Null results are deliverables.** Report every search term × corpus × hit
  count. "Searched X for Y, 0 hits" is evidence; silence about coverage is
  not.
- **Language:** use Norwegian/Hebrew/Arabic/French search terms where the
  source is native; translate quotes and keep the original alongside.

## Deliverable Format

Each work package writes exactly two files (plus any explicitly assigned
extras):

1. `investigations/epstein-oslo/reports/wpN-<slug>.md`:
   - `## Summary` — lead with the answer, 5-10 lines
   - `## Findings` — each: claim, tier, date-of-evidence, citation
   - `## Nulls & Coverage` — terms × corpora × hit-count table
   - `## Update-Rule Triggers` — quote any pre-committed rule that fired, or "none"
   - `## Proposed Leads` — for orchestrator consideration
   - `## Sources Consulted`
2. `investigations/epstein-oslo/reports/staged/wpN-findings.json` — array
   (possibly empty) of staged findings:
   ```json
   [{"target_name": "...", "summary": "...", "detail": "...",
     "claim_type": "direct_quote|paraphrase|inference|synthesis",
     "confidence": "confirmed|high|medium|low",
     "source_datasets": ["kabasshouse"], "date_of_event": "YYYY-MM-DD or YYYY",
     "source_quote": "verbatim quote or null", "evidence_refs": ["EFTA...", "https://..."],
     "tier": "T1|T2|T3|T4", "thread_id": 170}]
   ```
   Respect the confidence caps. Findings that merely restate established
   territory (see above) do not belong in staged output.
