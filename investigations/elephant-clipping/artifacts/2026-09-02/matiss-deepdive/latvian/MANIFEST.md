# Matiss Tabuns — Latvian primary-records deep dive (Lane A)

Investigation: elephant-clipping | Thread 208 (Latvian & Norwegian Vendor Chain) | Lead #95397
Retrieved 2026-09-02. Public/unauthenticated primary open data only.

## Key result
Matiss Tabuns (Latvian: **Tabūns Matīss**, personal-code prefix 081003 → born 8 Oct 2003) is the
**sole board member, sole shareholder (2,800 shares / €2,800 paid-up capital) and sole beneficial owner
of SIA "Avalanche Consulting"** (regcode **50203352961**), an **active** Talsi SIA registered **2021-10-13**
at **Andreja Pumpura iela 9-22, LV-3201 Talsi** — the exact address given for the Wyoming CLIPIT LLC
organizer. EU VAT **LV50203352961** is valid (EC VIES). VID records the company's declared primary
activity as **NACE 63.99/63.92 "information service activities"** (an online-content line consistent with
clipping) and a taxpayer rating of **"B"** ("obligations fulfilment needs to be improved", 2026-08-12).

He therefore DOES hold a Latvian registered business, but it is a generic pre-existing information-services
SIA (2021), not an entity named for ClipIt — and ClipIt itself was placed in a **separate Wyoming LLC** (2025).
Structural read: a deliberate choice of a US privacy-jurisdiction vehicle over an available domestic entity.

Findings: **15481** (confirmed — identity/company facts), **15483** (medium — WY↔LV identity linkage),
**15485** (confirmed — annual accounts FY2022-2025), **15486** (medium — structural conclusion),
**15491** (confirmed — VID rating/NACE/taxes-paid).

## Method
Full-table CSV exports of LR Uzņēmumu reģistrs (CKAN org `ur`, resources last-modified 2026-09-01) scanned
diacritic-insensitively for the `Tabun` surname token, the full name (both orders), and the address
`Andreja Pumpura iela 9-22` + `Talsi`. Tables: core register (incl. IK/IU sole-traders as subjects),
officers, members, beneficial owners, stockholders, name history, equity, area-of-activity, liquidations,
insolvency, suspensions, lobbyists, political parties, and annual-report financials. Corroborated by
EC VIES and VID (State Revenue Service) open data; and, non-independently, by the Lursoft public profile
(a UR reseller). Latvijas Vēstnesis gazette full-text search was JS-gated (recorded unavailable, not a true
zero — UR + VIES already provide the primary registration facts it would restate). Third-party same-name
persons' masked identifiers are NOT retained here (incidental-PII minimisation).

## Files (SHA-256)
```
0583d2576a606b464fa1de8bb1c7e91c72956c1de6bcce5dd32c63f20815b42d  avalanche-consulting-record.json
2a4c5fab42de1c5de23fa024c836fca768330840267f9d17a54afa2bf3d6cd53  ur-open-data-provenance.json
ea7a47bdb2ca754cc973b94ff1073833dbbdfe66158960842f1aed944196c006  avalanche-financials-FY2022-2025.csv
b64e1f5c3226b6abcc3ca3e821daeb05b4bd880216e56647eb35756c2e6d15ab  vies-LV50203352961.json
0379f6e096ce13938352ceea60327fccab6a1587a77b313ccd5d8fa4dedaf37c  vid-taxpayer-avalanche.json
```

- `avalanche-consulting-record.json` — resolved company + principal + linkage + financials + VID + conclusion.
- `ur-open-data-provenance.json` — every dataset searched, row counts, per-table result, resource URLs; corroborating (VIES/VID/Lursoft) and challenged (Vēstnesis) sources.
- `avalanche-financials-FY2022-2025.csv` — company-level annual accounts (turnover/result/equity/assets), 4 years.
- `vies-LV50203352961.json` — raw EC VIES response confirming VAT validity, name and address.
- `vid-taxpayer-avalanche.json` — VID taxpayer rating + NACE + VID-administered taxes paid (2022-2024).
