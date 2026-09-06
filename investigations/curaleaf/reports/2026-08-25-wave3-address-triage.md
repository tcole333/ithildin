# Wave 3 address-lead triage audit

- Profile: `curaleaf`
- Scope: pending leads `#91393` through `#91400` only
- Mode: scheduling-only triage; no source investigation and no new findings
- Result: 8 processed, 0 promoted, 8 dead-ended, 9 lead relations recorded
- Scheduler assignment for every processed row: priority `low`, depth tier `scan`, recommended skill `/pursue-lead`

| Lead | Address target | Decision | Consolidated into | Thread |
|---|---|---|---|---|
| #91393 | 20 Vassilissis Freiderikis | Dead-end: generic corporate-services address; spelling duplicate #91400 | #90976 Ionics/Vassiliades exit-cascade deep dive | 200 |
| #91394 | 767 Third Avenue | Dead-end: non-key commercial-building address; no distinct OCO hypothesis | #90409 Omega/OCO-Cetus facility deep dive | 199 |
| #91395 | 1736 S. Las Vegas Blvd. | Dead-end: Naturex II ownership/TOI work already covered | #91104 Nevada TOI and Cetus-Blokh-Muraviev deep dive | 202 |
| #91396 | 15374 Dickens St. | Dead-end: New Apothecary/Nova ownership work already covered | #91301 Nova/New Apothecary records deep dive | 202 |
| #91397 | 6455 Dean Martin Drive | Dead-end: LVNC ownership/TOI work already covered | #91104 Nevada TOI and Cetus-Blokh-Muraviev deep dive | 202 |
| #91398 | 1201 N. Larrabee St. | Dead-end: residential, non-key address; no distinct hypothesis | #91301 Nova/New Apothecary records deep dive | 202 |
| #91399 | 9120 W. Post Rd. | Dead-end: Naturex/BBMC ownership work already covered | #91104 Nevada TOI and Cetus-Blokh-Muraviev deep dive | 202 |
| #91400 | 20 Vasilissis Freiderikis | Dead-end: exact address/spelling duplicate of #91393 | #90976; duplicate relation to #91393 | 200 |

## Audit basis

None of the eight targets is a profile `known_address`. The potentially meaningful address questions are already represented by open, higher-depth leads: #90976 (Ionics/Vassiliades), #90409 (Omega/OCO), #91104 (Naturex II/LVNC/Naturex-BBMC), and #91301 (Nova/New Apothecary). Existing coverage was also substantial for Naturex II (9 findings) and LVNC (7 findings). The two El Greco House rows are spelling variants of the same address.

Each processed lead received a concise `triage_rationale`, `stop_reason`, `triaged_by`, `triaged_at`, completion timestamp, and audit note. Consolidation notes were added to the four surviving higher-depth leads. Relations recorded: eight `related` links from the surviving leads to the address rows, plus one `duplicate` link from #91393 to #91400.
