# 2024 Boston Board transfer and pledge extraction

Reviewed all 23 published 2024 decision documents supplied in `../source-index.json` (292 PDF pages). A full-document keyword pass produced 100 candidate items; each candidate item was read. A second pass confirmed that every source line mentioning transfer or pledge was contained in the candidate material. Seven pages were rendered and visually inspected to check the most consequential outcome associations and source anomalies. This is coverage of the supplied published archive, not a representation that all 2024 Board meetings are published there.

`events.json` contains 124 evidence events, each with full source item text, original URL, document and archive date, actual PDF page numbers, parties, outcome, and any ambiguity notes:

- 80 transfer-application decisions: 77 granted, 2 deferred, 1 rescheduled.
- 1 acknowledged notice of transfer revocation / voided purchase-and-sale agreement.
- 41 pledge-application decisions: 40 granted and 1 deferred.
- 2 acknowledged releases of prior pledges/security interests.

The transfer applications cover 77 unique license-and-party chains: Pho on Thayer to Nowon Seaport, PQT to VJ Partners, and Laura's Place to The Pearl each appear on two meeting dates. Do not treat repeated approvals as additional license sales. Six items use the phrase “transfer the licensed business” by the named alcohol-license holder; they are included with a wording note, distinct from stock-interest or manager changes. The source dates match all 23 archive dates. Two transfer/pledge items omit a Boston LB identifier: The Family Restaurant Partners to Reggie Rondo (January 4 item 23), and H and M Restaurant to VFW Parkway Restaurant Operator (February 8 item 7). Their IDs remain null.

Important evidence limits and events:

- Board grants are approvals, not proof that a sale closed, a loan funded, or a loan remains outstanding. The reviewed items do not establish sale prices or license-only allocations.
- Mirage Charcoal Kabob to LZZ was granted March 28 (LB-99643). June 6 Old/New Business item 5 explicitly reports that the purchase-and-sale agreement was voided at both parties' request and acknowledges their mutual intent to revoke the transfer. The latter source spells the seller “Kebab” and gives a different ZIP code; exact source wording is retained.
- February 1 items 13–14 grant sequential transfers of LB-98957: Bedford Dining to 116 Brighton License, then 116 Brighton License to Jongro BBQ Market Allston. The second application includes a pledge back to 116 Brighton License.
- October 17 item 22 grants DK Associates to Crazy Tiger (LB-99305), but explicitly withholds license issuance until successful community process. Neighboring Grand Bouchon to Chang Dao (item 21) is rescheduled, not granted.
- December 12 item 23 defers KBG to Flik and its accompanying BP TRS Services pledge. Item 22 separately grants Immersive Art Space Boston to Mai Izakaya.
- August 1 new-pledge item 8 says “CAMI 1974 Corporation”; same-document release item 1 says “Cami 1975 Corporation.” Both specify LB-99655 and Melodias at 1045 Saratoga Street. Names are preserved rather than silently corrected.
- Four keyword candidates were excluded as prospective transfer references or unrelated nonalcohol approval, with full text and reasons in `excluded-items.json`.

`coverage.json` accounts for every supplied 2024 document, including March 7 with no events, and records visual checks. `extract_candidates.py` and `build_events.py` reproduce these artifacts for this reviewed corpus; they are review helpers, not a general-purpose unreviewed legal-record parser. Python lint passed. Validation confirmed all 124 item texts occur exactly in source text, IDs are unique, pages are bounded by source page count, source dates agree, and required outcome/party fields are populated. The raw source item remains the authoritative evidence for any structured-field interpretation.
