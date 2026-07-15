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

## Complementary work from the parallel session (not this wave)

Independently landed on this profile during the wave and worth cross-linking:
the **Boris Nikolic information channel** (Epstein repackaging IPI Pakistan
reporting to Gates's science adviser; findings ~13375–13396), **Epstein-financed
personal benefits to Ruemmler** (~13382), and **Epstein marketing Ruemmler to
Thiel / Sunstein / Kerrey** (~13391), plus lead 68823 document-routing.

## Still pending

- **Claude tier-2 grant-network trace** (IPI 990 cross-reference) was still
  running at synthesis time; fold its funding-map output in on completion.
- Fold sections 1–6 above into `master.md` once the parallel session's rewrite
  settles (avoid an edit collision on the live file).
