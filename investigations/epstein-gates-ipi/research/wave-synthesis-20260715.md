# Wave Synthesis — 2026-07-15

Orchestrated wave: six Codex (gpt-5.6-sol) tier-1 lead pursuits under staged
read-only review, plus Claude tier-2 analysis. This file records the wave's
**material results and the finding/connection IDs** so they can be folded into
`master.md` (which a parallel session was actively rewriting during the wave).
Every result below was reconciled against that parallel session's concurrent
writes; only net-new findings were imported.

**Method note.** Codex tier-1 agents were database-read-only and produced staged
`findings-<lead>.json` for review; the orchestrator imported 55 findings by hand
(8 medal + 47 net-new) after per-finding dedup against the parallel session.
Three direct-quote findings were downgraded to paraphrase where the quote could
not be span-verified against the local corpus. The connection graph went from 0
to 20 edges. Caveat on process: the Codex agents ran under `--sandbox
workspace-write` with the repo writable, so their read-only discipline was
prompt-enforced, not sandbox-enforced; future tier-1 runs should mount the repo
read-only with only the scratch workdir writable.

## Material results

### 1. Program continuity weakens the Epstein-dependency reading
Lead 68435 · findings 13452–13464

Gates made **new same-scope commitments to IPI after the original grant ended** —
approximately $1.9M across INV-009501, INV-016206, INV-043279, and INV-063562 —
and comparable peace-and-health and Afghanistan/Pakistan security work continued
through 2021. IPI paid Nasra Hassan $442,871 across 2019–2021. Rød-Larsen's
resignation was accepted **2020-10-29** (corrects the prior December framing). The
Nexus Centre brand was not located after 2019, but the program substance
persisted. The post-2018 contraction tracks COVID-19 and donor events, not
Epstein's 2019 exit. **Evidentiary weight:** affirmative evidence of independent
program value — cuts against the covert-routing hypothesis. `master.md` currently
lists this only as a hypothetical "test that would move the assessment" (its §
Tests…); the wave supplies the actual records.

### 2. IPI-as-platform supported; funder network mapped
Lead 68433 · findings 13443–13451 · connections 6457–6470

Documented multi-patron platform with the funder network now in the graph:
Mongolia-funded Summers advisory board ($100K honorarium, wire instructions via
Epstein's assistant), Norwegian MFA/Norad framework funding, Carnegie direct
project grants, Bahrain host/donor, and $650K of Epstein-linked donations
(Enhanced Education, Gratitude America — KPMG). The Summers "What is IPI?" pattern
(meaningful counterparty ≠ formal payer) recurs. General operating support is
treated as fungible; no cross-patron funding is inferred.

### 3. Gates-DAF-as-Ruemmler-onboarding hunch weakened
Lead 68821 · findings 13472–13479

Supports an **attempted placement, not a completed onboarding**. Karp-mediated
recruitment predates the June 2014 pitch; Epstein's "on board" claim is
contradicted by his own "considering using" wording and by the Foundation staying
with Morgan Lewis; no Ruemmler DAF work product or Gates/Latham
engagement/matter/invoice was located; the DAF continued without her once EdR work
began. The two "Ruemmler polio" corpus hits are **duplicate copies of one
social-invitation thread** and are debunked as evidence of DAF work — this
corrects the note in `master.md` describing them as an "unrelated December 2014
donor-advised-fund exchange."

### 4. Edmond de Rothschild fee residuals narrowed
Lead 68468 · findings 13466–13471

Two underlying commitments — $10M (EdR Suisse) and $15M (Ariane/Benjamin) —
reconcile to the $24,999,980 received; the **$20 shortfall** is an inferred
deduction of unproved cause. **No EdR board minute or Yves Aeschlimann approval**
was located for the private Southern Trust fee. The $45.245M combined NPA penalty
is confirmed. Latham and Pillsbury billing remain unrecovered; "kathy plus
pillsbury around 10" stays an Epstein estimate, not a paid figure.

### 5. Ruemmler CIA medal — inference, not fact; FOIA drafted
Lead 68444 · findings 13424–13433, 13465 · human action logged

The **Agency Seal Medal** is the strongest formal identification but is
unconfirmed absent a certificate, citation, or award register. Base-rate
comparators (Burns 2014, Lieberman 2012, Lindsay 2016) show the award covers
varied service. No medal-specific evidence supports a vaccination-policy basis.
Exact CIA FOIA request language is drafted (in `report-68444.md`, workdir) and
logged as a pending `human_actions` row.

### 6. Asymmetric role-packaging holds across chains
Lead 68825 · findings 13480–13489

The introduction→offer→contract→payment pattern recurs across Gates-IPI,
Summers-Mongolia, Puri-Hoffman, Ruemmler-EdR, and the Rød-Larsen fee. Net-new: a
May 2013 **Stern-Farkas China introduction chain** and a **failed/non-monetized
introduction base rate** to guard against survivorship bias in the pattern claim.

### 7. Tier-2 grant-network trace refutes the conduit and Greentree flags
Claude tier-2 · findings 13521, 13524, 13526, 13527, 13528 · connections 6483,
6484 · leads 70054, 70056

IPI's own EIN (**03-0213226**, 501(c)(3), NTEE Q400) confirms it makes **zero
outgoing grants** — a pure operating recipient, **not a pass-through or conduit**;
that removes circular-flow and re-granting from the table. Two red-flag refutations:
the **Greentree Foundation** $122,915 "contractor" line is an IPI→Greentree
*venue/vendor* payment (modeled as `supplies`, connection 6483), the opposite of a
circular grant. (This section originally reported the Epstein inflows as
"donor-side-invisible" — that finding, 13524, was **wrong and has been superseded**
by wave-2 lead 70056; see §W2 below. Gratitude America's 990-PFs *do* report IPI;
the apparent absence was a local-index coverage gap.) Revenue **peaked in
2014** ($11.87M, the Gates-launch year) with expenses exceeding revenue most
years. The donor-concentration note resolves toward **state money, not Gates**: in
2016 a single foreign government supplied ~62% (~$5.24M, >4× Gates that year).
Checked-and-not-found: no circular flows, no pass-through behavior, no shared
officers between funders and IPI. Open threads: Rød-Larsen's 2012–2019 Part VII
compensation (lead 70054, needs 990 PDFs), the FAFO Institute's overlap with
Norway's funding and Rød-Larsen's Norwegian network, and deconfliction of a second
"International Peace Institute" EIN (42-1311908) seen in the FTS index.

## §W2 — Wave 2 (grant reconciliation, consultant channel, Rød-Larsen entanglement)

A second orchestrated wave recovered four stale critical leads the crashed
session had locked, and pursued them plus the two tier-2 follow-ons. Five Codex
tier-1 agents + one Claude tier-2 network agent; ~40 net-new findings imported.

- **The controlling grant documents are confirmed absent, not merely unlocated
  (lead 68417, findings 13658–13664).** After 215 corpus queries the $2.5M→$5.5M
  amendment, the January 31 2014 approved narrative/milestones/budget, and all four
  required progress/final reports are absent from the released corpus — and the
  recovered OPP1096058 execution package is a *blank budget-narrative template* that
  references but does not contain the Jan-31 exhibits. Corpus search is exhausted; a
  `physical_records` request to Gates/IPI for the native grant-management files is
  the only remaining path (logged as a human action).

- **The consultant channel is Mark Shaw / STATT — security-adjacent, not
  intelligence (lead 68419, findings 13679–13685; connections 6489–6491).** Mark
  Shaw is fully identified (STATT Consulting director, Hong Kong co. 1474694; ten
  years at UNODC; now executive director of the Global Initiative Against
  Transnational Organized Crime). STATT is a **government-facing research and
  strategic-communications consultancy** with documented UK Foreign Office and
  Australian border-security (anti-people-smuggling) contracts — the best match for
  the $16,408 Nigeria/Somalia consultant line. Discipline held: intelligence-agency
  status and tasking were **explicitly not established**, and the Sahan/STATT
  conflation was refuted. No invoice-level payee exists in the corpus.

- **Gates-specific restricted-fund actuals are not recoverable from public records
  (lead 68421, findings 13716–13719).** IPI's org-wide restricted roll-forward
  reconciles exactly ($4.398M open + $12.132M recognized − $13.485M released −
  $95K other = $2.951M close) but is not a Gates subledger; no annual release is
  attributable to Gates, and the audits/990s never name Gates or polio. Attributing
  any IPI expense to Gates money would violate the fungibility discipline. The two
  $256,968 grants are INV-009501 (2019) and INV-016206 (2020).

- **The Epstein donor vehicles are named, and finding 13524 was corrected (lead
  70056, findings 13703–13712; connection 6492).** KPMG's $650K came from exactly
  two Epstein-controlled vehicles: **Enhanced Education** (= J. Epstein Virgin
  Islands Foundation, EIN 66-0585379) $125K in 2011, and **Gratitude America Ltd**
  (EIN 66-0789697) $525K across 2017–2019. Epstein directly ordered the payments
  ("rich, please send 150k to ipi. from gratitude"). Primary 990-PFs (SHA-256
  verified) show Gratitude *did* report IPI ($375K/2017, $150K/2019) — **superseding
  the trace-trace finding 13524**, whose negative was a local-index gap. C.O.U.Q.,
  Financial Trust, and the other 56 KPMG-scope entities are excluded as payors.

- **Rød-Larsen's salary was not Gates-driven, but a personal-benefit layer is new
  (lead 70054, findings 13720–13727).** Full 2012–2019 Form 990 compensation ledger
  (SHA-256 verified): $514K–$598K/yr, with **no upward break** at the Gates grants
  (comp fell 14% in the peak 2014 year; Gates-pay↔comp correlation −0.695). The
  major discovery is an Epstein→Rød-Larsen personal-benefit layer **outside IPI's
  books and outside KPMG's ledger scope**: a **$130,000 personal loan** (2013), an
  **Oslo apartment bought at "less than half its value"** with a contested NOK 4M
  Epstein contribution, plus monogrammed shoes, children's computers, 2018 Apple
  Watches ("Gift from Jeffrey Epstein"), a home-health invoice paid "from jee
  personal," and Paris/NYC/island hospitality. All held under strict money-status
  discipline. This materially strengthens the allocation-and-access broker model:
  Epstein personally financially entangled the IPI President.

- **Network structure (Claude tier-2, findings 13602–13603; connections
  6487–6488; leads 70553, 70555).** The 22-edge graph was three disconnected
  components until the two missing IPI-official edges (Rød-Larsen↔IPI,
  Pfanzelter↔IPI) were added. Secondary bridges (Epstein excluded per config):
  **Rød-Larsen, Ruemmler, Southern Trust** — all articulation points. Top
  under-documented structural nodes: Pfanzelter (lead 70553), the Ariane↔EdR hole
  (lead 70555). It also surfaced a real `graph_tools` profile-scope bug (flagged as
  a platform task) that inflated the graph 22→97 edges.

## Complementary work from the parallel session (not this wave)

Independently landed on this profile during the wave and worth cross-linking:
the **Boris Nikolic information channel** (Epstein repackaging IPI Pakistan
reporting to Gates's science adviser; findings ~13375–13396), **Epstein-financed
personal benefits to Ruemmler** (~13382), and **Epstein marketing Ruemmler to
Thiel / Sunstein / Kerrey** (~13391), plus lead 68823 document-routing.

## Still pending

- Fold sections 1–7 and §W2 above into `master.md` once the parallel session's
  rewrite settles (avoid an edit collision on the live file). Note the loan /
  half-price-apartment / donor-vehicle material is substantive enough to warrant
  its own master.md subsections.
- Open leads worth a wave 3: **68823** document-routing hunch (8 findings already
  attached from the crashed session, never completed), **68431** Norwegian/public-
  funder accounting (not yet pursued), **70553** Pfanzelter (0 findings, a bridge),
  **70555** Ariane↔EdR edge, plus the FAFO Institute Norwegian-network overlap and
  the second "International Peace Institute" EIN (42-1311908) deconfliction.
- Records-access (human): the Gates/IPI grant-management files for OPP1096058 /
  OPP1100586 (logged), and the CIA FOIA for the Ruemmler medal (logged wave 1).

*Note: `tools/query_990.py cross-ref` hangs indefinitely — it stalled and killed
the first tier-2 agent, and left 3-day zombie processes (since reaped). Use
bounded `query_990` subcommands wrapped in `timeout` instead.*
