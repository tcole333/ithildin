# Boston Licensing Board: 2022 reviewed archive

All **24 distinct 2022 URLs** in the retained official Voting Minutes index were acquired and reviewed: **302 PDF pages**, dated **January 6–December 15, 2022**. All first-page voting dates match their archive labels. This establishes coverage of those linked documents, not completeness of the Board's 2022 meeting calendar or the lifetime history of any license.

## Results

| Ledger | Count | Explicit outcomes |
|---|---:|---|
| License transfer applications | 101 | 90 granted; 7 deferred; 2 continued; 1 withdrawn; 1 rejected |
| License pledge applications | 43 | 40 granted; 3 deferred |
| Ownership/stock/structure applications | 51 | 51 granted |
| Other notices | 7 | 5 pledge releases acknowledged; 1 ownership-clarification correspondence acknowledged; 1 license cancellation |
| Proposed/unresolved applications | 0 | No undecided application placed in a decision ledger |
| Excluded keyword candidates | 11 | Storage stock, member-event text, new pouring permit, non-alcohol lodging transfer, ordinary officer/manager notices, and other unrelated contexts |

The 101 transfer decisions name **88 distinct valid printed LB identifiers**, with one additional decision containing only malformed `L-99088`. Repeated proceedings remain separate. A transfer and a pledge requested in the same item are separate events, not two completed sales.

Ownership records comprise **46 explicitly alcoholic-beverage items** and **5 Common Victualler items without alcohol stated**. One explicit entity conversion, **Badoinkas, LLC → Badoinkas, Incorporated**, is recorded separately from the license-transfer petition heard that same day. The five non-alcohol-unspecified items provide equity parties or share counts; none of the 46 alcohol ownership items identifies prior/new equity holders or percentages. Generic ownership changes establish no private-equity sponsor or change in ultimate control.

## Evidence handling

- `source-index.json` records exact observed and final URLs, retrieval time, HTTP status, PDF/text hashes, page counts, first-page date text, and text-QC findings.
- `documents/` preserves original PDFs, `pdftotext -layout` text and page JSON. OCR was unnecessary. October 26 page 15 was rendered and confirmed blank.
- `candidates.json` contains **189 reviewed candidates**. Full-document keyword auditing included transfer, pledge, stock/stockholder, ownership, owner, interest, share, equity, corporate structure/conversion, membership, sale, purchase, surrender and revocation wording, including the end-of-document Board notices. No keyword occurrence remained outside a candidate span.
- `events.json`, `ownership-interest-events.json`, `notices.json`, and their CSV counterparts preserve source quotes, page/item references, parties, raw and normalized identifiers, outcomes, and ambiguities. `proposed-events.json` and `unresolved-events.json` are empty. `excluded-candidates.json` retains the excluded contexts.
- Explicit dispositions supply `decision_bearing`; an Agenda title alone does not. Board grants do **not** establish ABCC approval, license issuance, closing, purchase price, loan balance, perfection, or a current lien. All completed-sale/current-lien confirmation flags remain false.
- One initial sandbox DNS attempt reached no HTTP endpoint; its failure records are retained in `sandbox-network-attempts.json`. The authorized public-network acquisition returned all 24 PDFs without HTTP-error retries.

## Material edge cases

- [January 27, page 12, item 23](https://www.boston.gov/sites/default/files/file/2022/01/Voting%20Minutes%20Jan%2027.docx.pdf): Pho Countryside II → GRNA SP of MA/Street Pizza is **withdrawn**. [April 28, page 9, item 22](https://www.boston.gov/sites/default/files/file/2022/04/Voting%20Minutes%204-28-22-2.docx.pdf) instead grants the Obvers/Café Sauvage transfer and explicitly adds a pledge to 468 Commonwealth Avenue LLC in the Board's decision sentence.
- [May 26, page 10, item 19](https://www.boston.gov/sites/default/files/file/2022/06/Voting%20Minutes%205-26-22.docx.pdf): the decision changes the proposed DBA to **Dynasty Hot Pot**, destination to **14A Hudson Street**, and closing hour to midnight, pending a revised application. The licensee legal name remains Dailongy Hot Pot, Inc.
- [June 8, page 7](https://www.boston.gov/sites/default/files/file/2022/06/Voting%20Minutes%206_8_22.docx%20%282%29.pdf): the second item is visibly labeled `14 Speakeasy...` without a period. It is kept separate from item 13; each has its own transfer, pledge, and grant condition.
- [July 14, page 6, item 11](https://www.boston.gov/sites/default/files/file/2022/07/Voting%20Minutes%20-%207-14-22_2.pdf): 669 Centre/Tonino requests a **stock-only** pledge to David Doyle. It is not a license-pledge event.
- [August 4, page 6](https://www.boston.gov/sites/default/files/file/2022/08/Voting%20Agenda%208-4-22.docx.pdf): item 11 requires completion of the community process before license issuance. Item 12 visibly reads **Granted**; the extracted text layer adds stray `rantedTransferManage` residue, retained in raw text and explicitly corrected by visual review.
- [August 25, page 21, item 1](https://www.boston.gov/sites/default/files/file/2022/08/Voting%20Minutes%208-25-22.docx.pdf): Bedford Dining/White Horse Tavern → Full Revolution is **rejected with prejudice**, following an earlier deferral.
- [August 25, page 9, item 20](https://www.boston.gov/sites/default/files/file/2022/08/Voting%20Minutes%208-25-22.docx.pdf): the Harker/Qiao Lin transfer grant requires notice of the corrected destination, **392–398 Cambridge Street**. [September 15, page 8, item 13](https://www.boston.gov/sites/default/files/file/2022/09/Voting%20Minutes%209-15-22.docx.pdf) repeats the transfer with only that destination address after `To:`; the transferee entity remains null in that later record.
- [September 15, page 4, item 11](https://www.boston.gov/sites/default/files/file/2022/09/Voting%20Minutes%209-15-22.docx.pdf): Bubor Cha-Cha's outcome is **License Canceled** after a notice describing an *alleged* unapproved beneficial-interest/management change. This is a cancellation record, not an approved transfer or an independent finding about the underlying allegation.
- [October 26, page 9, item 21](https://www.boston.gov/sites/default/files/file/2022/10/Voting%20Minutes%2010-26-22.pdf): Bombolotti → Umbria prints **L-99088**. That raw ID is retained; no normalized LB identifier is invented.
- Five acknowledged releases concern Mullins Way/Shore Leave, 30 Traveler/Bar Mezzana, 571 Tremont/Black Lamb, Sip Wine Bar and Kitchen, and South of Hixbridge/Alcove. Each names the releasing creditor; a release from one creditor does not exclude other or later pledges.

## Verification and scope

Source hashes, exact candidate-text containment, page bounds, date matches, canonical-ID format, explicit-decision gates, unique event IDs, and full candidate accounting passed. Seven targeted page renders resolved blank-page, text-layer, identifier, stock-collateral, cancellation, and item-boundary issues. Changed Python scripts pass Ruff.

Reproduction scripts operate only inside this year directory. `prepare.py` prepares candidates; `extract_reviewed.py` applies the reviewed extraction; `finalize.py` validates and exports the ledger. Do not rerun acquisition to refresh a historical capture inadvertently. Existing 2024–2026 canonical events, benchmark files, MA SOS portals, profile records, and external records requests were not modified or queried.
