# TASE / E.D.B. valuation retrieval — result

## Bottom line
The E.D.B. Hebrew valuation is NOT on the AutoMax TASE/MAYA feed and structurally cannot be. The signed author remains unidentified from any primary source. But the search surfaced a material contradiction between the two merger parties' regulator filings.

## (1) Why the Hebrew original is not on TASE
- **The E.D.B. valuation was SciSparc's document, not AutoMax's.** It exists publicly only as the English translation in SciSparc's SEC F-4/A ("ANNEX E — TRANSLATION OF VALUATION REPORT OF E.D.B."), which names no individual — only "a representative of E.D.B." AutoMax valued at $44.8M, presented 2024-03-31.
- **SciSparc was delisted from TASE on 2018-08-07** (NASDAQ-only since), so it has no MAYA feed and never filed the E.D.B. valuation on TASE. E.D.B. was engaged by SciSparc's board (CEO Oz Adler).
- **AutoMax (the only TASE-listed party, issuer 2280) explicitly disclaimed obtaining any valuation.** Merger-vote convocation section 3.14.6: the audit committee and board "did not receive any document or work regarding a valuation [of SciSparc]... and did not base the transaction value on any methodology such as DCF or the net-asset-value method." Only external work cited: BDO Israel's consulting division (a financial analysis of SciSparc, not a valuation) and Asiag/Aviad Cohen (2024 IAS-36 impairment valuations). Never E.D.B.
- Full sweep of AutoMax's MAYA feed (136 immediate reports, 2024-01-01 → 2026-07-15): no valuation report, zero E.D.B. markers (א.ד.ב / E.D.B / ebrik10 / 052-3817124 / Bareket / Mevasseret / בריק / אלדד).

## (2) The Eldad Brik hypothesis — neither confirmed nor refuted
The signed Hebrew source is not on TASE; the SEC translation names no author; the E.D.B. registry record (co. 514752195) lists no officer. Brik remains an unconfirmed single-source (breach-data) lead. Remaining confirmation paths are SEC-side (a signed exhibit version in SciSparc's EDGAR filings, or SEC comment-letter correspondence) or the paid Israeli registry nesach — NOT TASE.

## (3) The two secondary valuations are NOT E.D.B.
- Shor (P1727609-01): author Sagi Ben Shalosh, CPA (שגיא בן שלוש רו"ח).
- Endymed (P1629461-02): author Yuval Zilberstein, CPA (רו"ח יובל זילברשטיין).
Repeat-player hypothesis not supported by these two.

## (4) Cohort context (incidental, confirmed)
Amitay Weiss chaired both AutoMax and SciSparc; Kinneret Tzedef (cohort member) appointed AutoMax external director 2025-07-28; SciSparc holds ~4.82% of AutoMax plus stakes in Clearmind and Jeff's Brands. None of this touches E.D.B.

## TASE docs retrieved (issuer 2280; mayafiles.tase.co.il/rpdf/<A>-<A+999>/P<RptCode>-<NN>.pdf)
- P1587015-00 — 11.04.2024 merger announcement (no annex)
- P1596279-00 — 02.06.2024 court petition to convene
- P1609957-00 — 08.08.2024 court approval to convene
- P1681252-00/-01, P1681250-00/-01 — 23.07.2025 merger-vote convocations (no valuation annex)
- P1687175-00/-01, P1687173-00/-01 — 21.08.2025 amended convocations per ISA request (no valuation)
- P1654609-00 — 27.03.2025 2024 annual report (valuations by Asiag/Aviad Cohen)
- P1673057-00/-01/-02 — 23.06.2025 routine convocation

## MAYA mechanics (for future runs)
mayaapi.tase.co.il is behind Incapsula (parametrized fetches blocked). Drive the SPA: set date filter via JS (input placeholder מתאריך) + click סינון, read /he/reports/<RptCode> hrefs from div.feed-item-report cards. RptCode = P-docId, so any report's PDF is directly curl-able from mayafiles.tase.co.il once you have the RptCode. Full transcript: tase-automax-edb-valuation-transcript.txt.
