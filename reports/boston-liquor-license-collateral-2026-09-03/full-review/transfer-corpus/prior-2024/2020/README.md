# Boston Licensing Board: indexed 2020 materials

This directory contains the 20 exact 2020 PDF URLs observed in the retained official archive inventory, downloaded once per URL in the successful network run. The two September 10 URLs have identical SHA-256 hashes: they share one stored PDF and one extraction, with both URLs retained in `source-index.json` and source-event provenance. The corpus therefore has **19 distinct PDFs and 97 pages**, spanning archive labels **April 23–December 23, 2020**.

All document voting-heading dates match their archive dates. The documents are titled *Voting Agenda* or *Voting Hearing Agenda*, but contain explicit individual dispositions. Neither the title nor an application narrative alone was treated as a completed Board decision.

| Ledger | Records | Breakdown |
| --- | ---: | --- |
| `events.json` | 44 | 28 license transfers: 24 granted, 4 deferred; 16 license pledges: 14 granted, 2 deferred |
| `ownership-interest-events.json` | 26 | All explicitly granted: 24 alcohol-license items and 2 Common Victualler items without alcohol stated |
| `notices.json` | 6 | Two closure/intended-transfer notices; ownership inquiry, information hearing, conditional revocation directive, and new-license ownership clarification |
| `unresolved-events.json` | 1 | Asmabanu Enterprises stock-transfer item visibly prints “Grated”; no grant normalization made |
| `proposed-events.json` | 0 | No otherwise in-scope application lacked a printed disposition; the ambiguous printed disposition is separated above |
| `excluded-candidates.json` | 8 | Storage/stock language, nonalcohol lodging-house transfers, ordinary alcohol sale/service, and unrelated floor-plan items |

`candidates.json` retains 75 raw candidate blocks. `reviewed-candidates.json` contains 76 reviewed blocks after visually separating the unnumbered Pushcart Café item from the preceding Alfa Wines item on May 28. The Pushcart→Dolce transfer is explicitly deferred; Alfa Wines→Newa and its pledge are granted. `coverage.json` records per-document counts and broad keyword coverage. `documents/` retains the original PDFs, Poppler layout text, and page JSON.

The source manifests include hashes, sizes, retrieval metadata, text-quality checks, and exact raw/archive link occurrences. Five sparse pages were visually checked: two are blank, two contain only a footer, and the final December 23 page contains a grant continuing an unrelated Hojoko extension item. No OCR was needed. The May 28 unnumbered item and December 3 “Grated” wording were also visually checked, with images retained. Full item quotes, page spans, normalized and raw LB identifiers, explicit dispositions, and known parties are preserved. The broad scan also checked unnumbered text and corporate/ownership/share/stock/conversion and transfer/pledge/revocation/release language; no matched line remains outside a reviewed candidate.

Ownership records use `event_type: ownership_interest`, `event_subtype: ownership_application_disposition`, explicit `actions`, and `equity_change_completion_verified: false`. Combined “issuance/transfer” wording is preserved without asserting that both actions independently occurred. Unknown owners remain empty. Ogawa Coffee explicitly names Yoshinori Uda as recipient of 100% of stock; its outgoing manager/officer is not inferred to be the prior stockholder. Asmabanu explicitly names a shareholder proposed for removal, but its ambiguous disposition stays outside the decision ledger. No alcohol ownership application identifies its equity parties or percentages, and no explicit legal-entity conversion was found.

Repeated source occurrences remain separate. Atlas appears deferred in July and granted in August; the August item states no LB number, which is left null. Del Frisco’s repeats ownership-change applications for two licenses on December 3; the text does not establish whether these represent separate underlying equity transactions. The Churrascaria directive threatens later revocation if documentation is inadequate; it does not establish that the condition occurred or that revocation ultimately took effect. License-type changes accompanying actual transfers are retained in full item text but are not classified as legal-entity conversions.

These are **source-disposition counts, not distinct completed transaction counts**. Board approval does not prove closing, a current lien, a loan balance, ownership control, or financial sponsorship. The saved index is not proof of meeting completeness; no January–March materials were linked and no missing-meeting audit was undertaken. Frozen 2024–2026 and benchmark files were not edited.

`collect.py` refuses to run if the final manifest exists, preventing accidental repeat requests. Initial sandbox DNS failures occurred before HTTP and are retained in `sandbox-dns-attempts.json`; the approved network run had no HTTP errors or retry loop. `prepare.py`, `review.py`, and `finalize.py` preserve the candidate scan, reviewed field extraction, and provenance/coverage checks. Run Python with `uv run python` from the repository root. All four scripts passed targeted Ruff checks.
