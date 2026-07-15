# Lead 60514 negative and boundary log

- FEC: no broad rerun. The prior 272-file SHA manifest passed and the identity-controlled ledger recomputed to 186 rows / $1,140,393.90 gross. This is a control, not a new finding.
- SEC search: a broad exact-phrase EDGAR query returned capped noise, so owner CIK `0001012998` and issuer CIK `0000923796` controlled the Forms 3/4/5 review. The insider `--detail` parser returned zero transactions for XSL-linked filings; raw ownership XML supplied the transactions (papercut #1040).
- SEC 13D/G: two returned documents were incidental historical references, not Zoley filer records.
- Florida UCC: zero exact-name filings.
- OpenCorporates: public API query stopped on an invalid configured token; no result was inferred from the access failure (papercut #1044).
- CourtListener: 46 RECAP search results, 21 party dockets, and 100 capped document hits. Most party hits were prisoner/detainee cases naming a senior GEO executive or recent habeas captions; they did not establish new entity roles or ownership. Existing litigation work already covered the major securities and detainee-labor cases, so no duplicative case findings were written.
- Government releases: zero exact results after retrying punctuation-safe `George Zoley` (papercut #1041).
- SEC enforcement: zero litigation, administrative, or AAER results after retrying punctuation-safe `George Zoley` (papercut #1042).
- LDA: zero lobbyist and zero contribution records. The zero-result lobbyist command did not create its requested output file (papercut #1043).
- FARA: zero registrants and zero foreign principals. The CLI misleadingly reported one result for two empty arrays (papercut #1045).
- IRS 990 person searches: zero exact person hits. Organization-first resolution by Foundation EIN `27-4034030` produced the 2023 president role. The `filings` command crashed formatting an integer form code (papercut #1046).
- LittleSis, OpenSanctions, GLEIF, and FAA: zero exact matches.
- ICIJ: 50 fuzzy reconciliation candidates, all `match:false`; none was identity-resolved to Zoley.
- DOJ/ICE/White House official-site checks: no additional exact personal event found. Congress supplied the one material official event.
- Property: one exact official Palm Beach County owner page. Residential street address and trust names are not repeated in the narrative/findings.
- No HigherGov API key, live SAM query, paid PACER, breach data, subject contact, `auto_leads.py`, or external contact was used.
- Findings CLI accepted unknown source labels while warning; #13044-#13049 were immediately normalized through audited corrections (papercut #1047).
- `entity_tracker add-role` ignored the second CEO tenure under a role-only unique key but printed success; the second tenure is preserved with a qualifier and papercut #1049.
