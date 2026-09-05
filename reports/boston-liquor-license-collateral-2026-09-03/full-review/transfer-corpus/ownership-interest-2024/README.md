# 2024 ownership-interest ledger

Reviewed all 23 supplied 2024 Board decision documents, including all 60 keyword candidate items. The ledger contains 55 source occurrences: 53 granted ownership/corporate-structure application dispositions and two separately labeled ownership/management notices. Five inventory/storage references are excluded in `candidates.json`.

Of the 53 dispositions, 41 concern stated alcohol licenses and 12 concern Common Victualler licenses with no alcohol stated. The two notices concern CV7AL categories. Use `license_scope` and `event_subtype` to keep these populations separate.

The ownership actions overlap within items: 30 ownership-interest changes, 28 stock-interest changes, five corporate-structure changes, and one ownership-of-licensed-business change. Three of the corporate-structure items explicitly identify corporation-to-LLC conversions (Marriott Hotel Services at Long Wharf and Copley, plus Courtyard Management). The before/after corporate names are separate entity fields, not owner parties. Caffe Nero's Ltd-to-Inc names are also separate entity fields; that source labels it ownership of the licensed business, without establishing a legal conversion.

No alcohol-license disposition identifies owner parties or equity percentages. Ten nonalcohol CV items explicitly report percentage ownership before and after: Ula Cafe, Cobblestones, Monumental Market, Lucky Cafe, four Boston Pie locations, Boston Soup Dumplings, and West Garden. Jade Naga independently names an ownership recipient without giving a percentage. A manager/officer title is never used to infer shareholding. All percentages transcribed here have an explicit percent sign in their source; a bare number of shares is not converted into a percentage.

Repeated source occurrences remain separate and carry notes: RBSBW/Roche Bros has two overlapping items for each of two license numbers on October 31; Night Shift Lovejoy repeats the same stated LB number across four pouring-license categories on November 21; Boston Pie repeats the same stated ownership percentages across four licensed locations. Marriott's common entity conversion appears for two licenses. Golden Goose's generic stock-interest applications recur in February and June. These are not counts of distinct underlying equity transactions.

The August 22 notices are not grants of equity changes: M.Y.N./Dublin Pub must update its license to reflect current ownership/management; Causeway Union will have a further hearing for ownership/management participation. Both have empty owner arrays.

Files:

- `events.json`: 55 source occurrences with full item text, outcome, actions, page references and structured parties/entity fields.
- `candidates.json`: all 60 reviewed keyword candidates and exclusion reasons.
- `coverage.json`: all 23 documents, per-document counts, keyword coverage and visual-check pages.
- `extract.py`: local reviewed-corpus extraction helper; not an unreviewed general parser.

Validation confirmed unique event IDs, exact item text within source text, valid PDF page bounds, faithful normalized ownership quotes, explicit percent signs, and empty owner arrays on notices. Five rendered pages were visually inspected to verify conversions, percentage clauses, source entity names, and outcome placement. Python lint passed. No frozen transfer/pledge events or benchmark artifacts were changed.
