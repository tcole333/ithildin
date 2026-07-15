# GEO donor identity ambiguity and negative log — lead 59035

## Identity exclusions

The row-level matrix preserves every candidate record. The following counts are excluded or unresolved and are not added to personal totals:

- Paul Laird: 1662 of 1772 candidate rows excluded/unresolved.
- Jack Brewer: 1088 of 1106 candidate rows excluded/unresolved.
- Daniel Ragsdale: 216 of 316 candidate rows excluded/unresolved.
- Donald Houston: 74 of 99 candidate rows excluded/unresolved.
- Christopher D. Ryan: 31 of 159 candidate rows excluded/unresolved.
- Richard K. Long: 7 of 10 candidate rows excluded/unresolved.
- Brian R. Evans: 3 of 28 candidate rows excluded/unresolved.

Paul Laird's Los Angeles `GEO GROUP / PROFESSOR` and Redondo Beach `GEO / PROFESSIONAL` records remain unresolved because geography and occupation conflict with the SEC-documented GEO operations career; exact employer text alone was not accepted.

## Refund-resolution negatives

- The corrected official Schedule B by-recipient pass returned 57 aggregate candidate rows. Most were organizations containing the searched name or unrelated common-name persons. Transaction-level Florida/amount tests returned zero for the ambiguous Jack Brewer, generic Daniel Ragsdale, and generic Donald Houston hits.
- A $2,200 Schedule B refund from DLJCC PAC to George C. Zoley is identity-confirmed by full name and Boca Raton address, but targeted official Schedule A searches for that committee/name returned zero. It is preserved and not subtracted.
- Earlier ad hoc files used an invalid Schedule B route and encountered HTTP 429 responses. They were overwritten by corrected `/v1/schedules/schedule_b/by_recipient/` cycle results and are excluded from every conclusion.

## State-record boundary

The official Florida campaign-finance portal returned a Cloudflare challenge, and the advertised in-app browser backend had no available browser session. The archived challenge page documents access failure. No Florida person-level zero or state total is asserted.
