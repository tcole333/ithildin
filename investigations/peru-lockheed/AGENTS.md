# Peru × Lockheed Martin — Investigation Addendum

Case-specific instructions for agents working this profile. Loaded in addition to the project AGENTS.md.

## Verify-First Posture

Treat **every named person, date, contract value, and aircraft variant** as unverified until corroborated against primary sources. The skill seeded this profile from training-knowledge approximations and explicitly flagged dates with "verify" annotations. Do not promote any seeded date to `confirmed` without primary-source corroboration.

Specifically:
- The exact date Boluarte left office and Jerí assumed the presidency was placeholder-dated `2025-10-01`. Confirm against Congreso.gob.pe vote records or official gazette (El Peruano).
- The Lockheed Martin selection date `2026-01-01` is a placeholder. Confirm against MINDEF press releases, DSCA notifications, or LMT 8-K disclosures.
- The aircraft variant (assumed F-16 Block 70/72) is **inferred** from Lockheed's current export catalogue. The actual platform could be C-130, S-70 Black Hawk, missile systems, or a multi-platform package. Establish before assuming.

## Primary-Source Hierarchy (Peru)

Use in this order:

1. **El Peruano** (official gazette) — laws, resolutions, presidential decrees, supreme decrees
2. **Congreso.gob.pe** — vote records, hearing transcripts, plenary actas
3. **Ministerio de Defensa (mindef.gob.pe)** — procurement notices, ministerial resolutions
4. **OSCE / SEACE** — public procurement portal (some defense items exempt; check what is and is not posted)
5. **Fiscalía de la Nación** — formal accusations, dispositions
6. **Contraloría General de la República** — audit reports
7. **Sunarp / SUNAT** — registry/tax data on Peruvian entities
8. **El Comercio / La República / Gestión** — establishment press, verify against above
9. **Ojo Público / IDL Reporteros / Convoca** — investigative outlets — generally reliable; still verify

Do **not** treat Wikipedia or social media as evidence. Use them to surface leads, not to support findings.

## Primary-Source Hierarchy (US side of the sale)

1. **DSCA Major Arms Sales** notifications (dsca.mil) — AECA §36(b) Congressional notifications
2. **State Department DDTC** — ITAR licensing
3. **Federal Register** — required publication of certain transfers
4. **SEC EDGAR** — Lockheed Martin 10-K, 10-Q, 8-K, proxy
5. **House LDA / Senate LDA** — lobbying disclosures
6. **FARA eFile** — foreign agent registrations relevant to Peru
7. **FEC** — campaign contributions from LMT PAC and executives
8. **USASpending / HigherGov** — federal contract baselines (LMT domestic) for context

## Known Patterns to Watch For

- **Strategic-rationale pivot**: a technical evaluation that ranks one bidder first, then a "strategic" or "interoperability" rationale flips selection to another, often correlates with intermediary payments. Document the technical ranking before the political decision.
- **FMS vs DCS routing**: the choice between Foreign Military Sale and Direct Commercial Sale changes who holds the contract risk and what disclosures are public. FMS = DSCA + Congressional notification (more transparent); DCS = ITAR license but less Congressional visibility.
- **Offset agreements as corruption vector**: defense offsets routed through shell entities are a known mechanism. Trace any local-content / industrial-cooperation commitments to the actual Peruvian recipient entities.
- **Rotation-of-ministers as accountability gap**: Boluarte cycled defense ministers rapidly. The minister who *signed* may differ from the minister who *decided*. Both matter.
- **Lava Jato playbook**: Odebrecht established a template — payments via offshore structures (often Panama, BVI), Brazilian banks, intermediary "agentes" — that Peruvian elites know how to operate. Default to assuming any major contract has an intermediary chain unless proven otherwise.

## Confidence Discipline

Per project AGENTS.md, never set `confirmed` for inference or synthesis. For this case specifically:
- The **existence** of a Lockheed Martin sale to Peru: confirmable via DSCA notification or LMT public disclosure
- The **price** quoted in DSCA notifications is an *estimate*, not the contract value — flag this distinction
- **Officials' motivations** are always inference; max `medium`
- **Intermediary involvement** requires documentary evidence (FARA, banking records, court filings) — speculation is not a finding

## Language

Many primary sources are in Spanish. Use them — do not wait for English translations of decrees, resolutions, or actas. Acta de sesión and resolución suprema are the operative documents.

## Out of Scope

- Targeting any subject's personal life beyond what touches the procurement
- Speculation about US intelligence community activity beyond what is in declassified or court records
- Predictions about ongoing court cases beyond charged conduct

## Suggested Skill Sequence

1. `$deep-investigate "Lockheed Martin Peru sale"` — get the procurement ground truth
2. `$investigate-person "Dina Boluarte"` — political-side context
3. `$investigate-person "José Jerí"` — successor government
4. `$analyze-filing` for Lockheed Martin recent 10-Ks
5. `$timeline-analysis` once 20+ findings are in DB
6. `$analyze-network` once entity graph is populated

