# Handoff: bounded ICIJ wave-2, then The Markup

Paste the "PROMPT TO HAND OFF" section below into a fresh session. Everything above it is context for
whoever is doing the pasting.

## Why this scope (decided 2026-07-29)

An access-substitution analysis (`research/patterns/_intake/access-substitution-analysis.md`) measured how
much of each outlet's method is reproducible without their private corpora:

| Outlet | Signatures | End-to-end public | Usable incl. verification half | Closed-platform-dependent |
|---|---:|---:|---:|---:|
| ICIJ | 36 | 50.0% | 69.4% | 0 |
| OCCRP | 31 | 22.6% | 64.5% | 1 |

ICIJ's public Offshore Leaks graph makes half its moves regenerable; OCCRP never publishes the decisive bank
ledgers, so its moves mostly reduce to a verification half. Aleph Pro gating turned out **not** to be the
binding constraint (1 of 67 signatures) — leaks are.

The ICIJ census (`_intake/icij/report-10-census.md`) found the famous 7-project canon is 14% of projects but
50.7% of project-path output, and that the non-canon portfolio is largely **open-records** work. Its largest
residual cluster (R4, offshore/tax leak families) is explicitly "methodologically closer to the existing
canon" — high volume, low marginal value. So this wave inverts the volume ranking: take the open-records
clusters, skip R4.

---

## PROMPT TO HAND OFF

You are continuing a multi-outlet investigative pattern-library project in the repo
`/Users/travcole/projects/osint-research`. Read `research/patterns/README.md` first — it defines the library,
the entry schema, the sampling-frame discipline, and the extension path. Then read
`research/patterns/_intake/access-substitution-analysis.md` (why this scope was chosen) and
`research/patterns/_intake/icij/report-10-census.md` §8 (the sampling frame for task 1).

**State already complete — do not redo any of it:**
- ProPublica: fully profiled and synthesized. `research/patterns/` holds README.md,
  propublica-ontology.md, detection-signatures.md (37 pattern cards), propublica-story-index.md (217 entries),
  adapter-gaps.md. Extraction layer in `_intake/propublica/` (reports 01–16 + tally/ + raw/).
- OCCRP: census + methodology + laundromat canon + 4 wave-2 clusters, in `_intake/occrp/`.
- ICIJ: census + methodology + offshore-leaks canon (33 entries), in `_intake/icij/`.
- Card validation: 3 cards executed against held data; memos in `research/patterns/_validation/`.

### TASK 1 — Bounded ICIJ wave-2 (3 clusters, ~18 projects)

Dispatch three parallel agents, one per cluster. Each writes ONE report into
`research/patterns/_intake/icij/`. **Skip cluster R4 (noncanonical offshore/tax leak families) deliberately** —
it re-derives mechanics already extracted from the canon. R3 (conflict/repression) is optional if capacity
allows; R1 (dirty money beyond FinCEN) is partly covered by the canon report already.

| Report file | Cluster | Seed projects (all at `https://www.icij.org/investigations/<slug>/`) |
|---|---|---|
| `report-12-extractives-environment.md` | Natural resources, extractives, environment (8 projects, 138 items) | fatal-extraction, deforestation-inc, looting-the-seas, looting-the-seas-ii, looting-seas-iii, waterbarons, coltan, global-climate-change-lobby |
| `report-15-aid-development-finance.md` | Aid, development finance, public contracting (5 projects, 111 items) | world-bank *(Evicted and Abandoned)*, divine-intervention, us-aid-latin-america, collateraldamage, windfalls-war |
| `report-17-lobbying-regulatory-capture.md` | Corporate lobbying and regulatory capture (5 projects, 102 items) | big-tobacco-smuggling, tobacco-underground, smoke-screen, uber-files, cancer-calculus |

Census-noted distinctive evidence per cluster — extract these carefully:
- **Extractives:** fisheries quota/subsidy records and DNA testing; stock-exchange filings, mining licenses,
  fatality reconciliation; environmental certification chains and timber-trade data; climate-lobby records;
  water-concession contracts.
- **Aid/development:** displacement and resettlement case databases; multilateral lender accountability files;
  PEPFAR grant conditions; military-aid and human-rights records; FOIA procurement data, campaign
  contributions, lobbying.
- **Lobbying/capture:** internal corporate documents; cross-jurisdiction lobbying campaigns; patent families;
  medicine pricing and court records; "ask forgiveness" market-entry strategies.

**Per-agent instructions (use verbatim, varying only cluster/seeds/file):**

> Review ICIJ's <CLUSTER> reporting and extract a structured evidence ontology — what they found, what
> evidence/sources they used, and the precise analytic move that surfaced each finding. Web research +
> analysis only; do NOT write to any database. Write the report to `research/patterns/_intake/icij/<FILE>`
> and nothing else outside that directory. If the Write tool is blocked for report files, write via Bash
> heredoc (`cat > FILE <<'EOF' … EOF`).
>
> Calibrate depth and schema against `research/patterns/_intake/propublica/report-05-criminal-justice.md`.
> Seed ONLY from the census-identified project URLs given; fetch each project page, then its stories. Cover
> 8–12 stories/projects. FREE-FORM tagging — invent tags describing what you observe, define each on first
> use; do NOT import a predefined taxonomy. Verify attribution (ICIJ-coordinated project vs member-outlet
> story published under the project banner) and name lead outlets.
>
> Per story:
> ```
> ### <Title> (<year>) — <one-line what it revealed>
> - **URL**:
> - **Partner/awards**:
> - **What they found** (2–4 concrete bullets — names, amounts, scale):
> - **Finding type(s)**: free-form, defined on first use
> - **Evidence & sources**: typed list; each labeled with what it is and how it was obtained
> - **INPUT DEPENDENCY** (REQUIRED): classify the decisive evidence as (a) open-record-runnable — obtainable
>   today by an outside investigator; (b) re-anchoring — discovery needed a leak/insider but VERIFICATION ran
>   on public records (state exactly which half is public and reusable); (c) leak-dependent — inert without
>   non-public material; (d) closed-platform-dependent. For (c)/(d), name the nearest public substitute and
>   what it loses.
> - **Detection signature**: the precise analytic move (join/diff/gap/reconstruction), named by you, described
>   as "X joined/compared to Y on key Z revealed W". Most important field.
> - **Corroboration structure**:
> - **Methodology notes**: cite ICIJ's own methodology/"how we did it" page (URL); else [inferred] + basis
> - **Generalization**: where else this pattern appears; what a generic detector looks for
> ```
>
> End with "## Cluster Synthesis": (1) evidence-source types with frequency; (2) detection signatures with
> frequency (your own tags); (3) **input-dependency profile — counts in each class a/b/c/d**; (4) 3–5 named
> transferable pattern candidates with mechanics, minimum data, and recognition cues in ANY domain; (5) which
> patterns this platform could run today vs what is missing. Platform holdings: 20+ corporate registries incl.
> UK Companies House, OpenCorporates, GLEIF, OpenSanctions, ICIJ Offshore Leaks DB, local OpenAleph,
> property/deed tools, CourtListener/RECAP, USASpending/FPDS, USPTO, FAA registry, 990 stack, Etherscan/Solscan.
>
> Quality bars: URL citation for every claim; quoted methodology vs [inferred]; one-line official impact per
> story where applicable. Final response: 5-line summary including the input-dependency counts.

### TASK 2 — The Markup (census first, then clusters)

The substitution analysis recommends The Markup as the next outlet: an organization built around published
data, code, and measurement should yield more end-to-end runnable cards per unit of effort than any
leak-centered outlet. Note The Markup merged with CalMatters (2024) — resolve the current site structure and
archive location before enumerating, and state an explicit attribution rule for pre/post-merger work.

1. **Census agent first.** Mirror `research/patterns/_intake/propublica/report-10-census.md` — enumerate from
   The Markup's own site/sitemap structure, not from memory: series/investigations index, article counts by
   year, their published datasets and GitHub repos (they open-source unusually heavily — treat the code
   repos as a first-class corpus), awards, bottom-up clusters, a coverage-diff against any "famous work"
   frame, ranked second-wave recommendations with seed URLs, and a sampling-frame-biases section. Write to
   `research/patterns/_intake/markup/report-10-census.md`, raw pulls to `_intake/markup/raw/`.
2. **Then** spawn cluster extractions from that census's §8, same per-story schema as Task 1 (including
   INPUT DEPENDENCY).

### Operating constraints (all tasks)

- **No investigation.db writes.** No leads, findings, connections, or infra_tracker enqueues. Read-only
  SELECTs are fine; note that `investigation.db` is WAL — use `PRAGMA query_only=ON`, since `sqlite3
  -readonly` cannot open it. Never run `investigation_context.py set` (other sessions may hold a different
  profile).
- **No commits.** Leave everything uncommitted for review.
- Use `uv run python` for all repo tools. Any repo query tool returning bulk results must pass
  `--output <file>` — a pre-tool hook blocks it otherwise, and the hook also trips on prompt text mentioning
  `tools/query_*` with bulk subcommand words, so include the `--output` convention in agent prompts.
- Session isolation: `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` for scratch files.
- Codex agents are the preferred workers here (independent second system). Verified headless pattern:
  ```
  codex exec --cd /Users/travcole/projects/osint-research --sandbox workspace-write \
    -c 'sandbox_workspace_write.network_access=true' - <<'EOF' > out.md 2> err.log
  <prompt>
  EOF
  ```
  Network is DISABLED by default in workspace-write — the `network_access=true` line is required for any
  web research. Check the stderr banner ~15s in to confirm model/sandbox. Add extra writable roots with
  `-c 'sandbox_workspace_write.writable_roots=["<dir>"]'` if writing outside the repo.

### After both tasks — the integration pass (do not start until profiling is done)

One cross-outlet pass producing: a merged finding-type and evidence-source ontology with frequencies
re-derived over the combined corpus; a unified `detection-signatures.md` card layer with per-outlet exemplars
and per-card input-dependency; a re-ranked `adapter-gaps.md` weighted by observed usage across all outlets;
and candidate promotions into `research/craft-research/analytical-models.md` as Tier-2 lenses via
`/discover-frameworks`. Integration was deliberately deferred until all outlets were profiled so the
US-records-shaped ProPublica frame would not get baked in early.

**Card-schema discipline to preserve** (added after live validation — see `research/patterns/_validation/`):
cards whose result is a computed statistic carry *Pre-registration* (parameters fixed before computing),
*Coverage statement* (fraction of the denominator resolvable), and *Control* (null population; report lift,
never raw rates); any card may carry *Preconditions* (credential/CAPTCHA/coverage gates). Numeric parameters
carry their derivation, and dollar literals are written shell-safe — under zsh a pasted `$20,833` loses its
digits.
