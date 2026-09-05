# Lead 73899 — DC parcel and Recorder access index

Date checked: 2026-07-23  
Profile: `oversight-project`  
Thread: 180

## Official DC property source

DC GIS / Office of Tax and Revenue, `Owner Polygons (Common Ownership
Layer)`, layer 40:

`https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land_WebMercator/FeatureServer/40`

The layer description says that attribution comes from OTR's Public Extract
and that the layer is updated automatically. The exact query was limited to
the ten lead SSLs and returned ten records.

All ten returned records have `INSTNO=null`.

Saved response:
`/tmp/osint-zKUMylKN/dc-owner-layer40-parcels.json`; SHA-256
`808a71205ee0eaddfa80a9f3dae0942fea6ca0af277466c895c7c4474e8cefab`.

Dates below convert ArcGIS millisecond timestamps to the
`America/New_York` calendar date. `OTR sale price` and `OTR sale date` are
field labels from the tax extract; they are not treated as deed
consideration or execution dates.

| Group | SSL | Premise address | OTR owner name | OTR secondary name | OTR sale date | OTR sale price | OTR recordation date | OTR extract date | OTR `INSTNO` |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Schedule R | 0762-0038 | 225 Pennsylvania Ave SE | Clear Plains Holdings LLC | — | 2022-07-14 | $5,500,000 | — | 2026-06-15 | null |
| Schedule R | 0762-0818 | 209 Pennsylvania Ave SE | Pennsylvania Avenue Holdings LLC | — | 2022-02-02 | $6,000,000 | — | 2026-04-15 | null |
| Schedule R | 0762-0840 | 203 3rd St SE | 116 Holdings LLC | — | 2022-07-26 | $5,100,000 | — | 2026-03-20 | null |
| Schedule R | 0762-0844 | 229 Pennsylvania Ave SE | Clear Plains LLC | — | 2026-06-26 | $0 | 2025-10-07 | 2026-07-06 | null |
| Schedule R | 0762-0845 | 231 Pennsylvania Ave SE | 753 LLC | Clear Plain LLC | — | $0 | 2025-10-07 | 2026-06-23 | null |
| Schedule R | 0762-0846 | 203 Pennsylvania Ave SE | 753 LLC | Clear Plain LLC | — | $0 | 2025-10-07 | 2026-03-20 | null |
| Schedule R | 0762-0847 | 233 Pennsylvania Ave SE | 753 LLC | — | 2026-06-26 | $0 | 2025-10-07 | 2026-07-07 | null |
| CPI direct | 0788-0805 | 126 3rd St SE | Conservative Partnership Institute Inc | — | 2020-11-12 | $1,500,000 | — | 2026-03-20 | null |
| McAllister | 0790-0016 | 315 Pennsylvania Ave SE | McAllister Holdings LLC | — | 2026-02-02 | $795,000 | — | 2026-07-10 | null |
| McAllister | 0790-0017 | 313 Pennsylvania Ave SE | McAllister Holdings LLC | — | 2026-02-02 | $1,425,000 | — | 2026-07-10 | null |

`OWNNAME2=CLEAR PLAIN LLC` is an OTR secondary billing-owner field on
0762-0845 and 0762-0846. It is not a deed-party, manager, member, or control
finding.

## Recorder access boundary

Official DC Recorder page:
`https://otr.cfo.dc.gov/page/recorder-deeds`

Linked online search:
`https://washington.dc.publicsearch.us/`

The Recorder search landing page states:

> The District of Columbia Recorder of Deeds public search is available to
> registered users and subscribers.

It further says registration provides free search and image viewing, while a
document download costs $4.00 plus a $1.50 transaction surcharge. A monthly
subscription is $175.00. Saved landing page:
`/tmp/osint-zKUMylKN/dc-recorder-publicsearch-landing.html`; SHA-256
`dbb467b298e056293b8b31d8da9b253abc7aa526fe91f3f8ff496c530ba56bed`.

No account was created, no credentials were requested or used, and no
purchase was made. Consequently, the following Recorder-only fields remain
unresolved for every SSL:

- instrument number and recording date for the current acquisition deed;
- exact deed grantor/grantee and stated consideration;
- deed execution date, notary, return address, title company, and authorized
  signatory/capacity;
- every deed of trust, assignment, modification, release, or satisfaction;
- immediate prior deed and prior-owner chain;
- the actual instrument language, including whether `CLEAR PLAIN LLC`
  (singular) appears as a recorded party.

## Instrument retrieval index

For each SSL below, a permitted registered user should search the Recorder
index from August 1921 to present, preserve every result's instrument number,
recording date, document type, grantor, grantee, and image availability, then
review only the instruments needed for the acquisition and financing chain:

1. 0762-0038 — 225 Pennsylvania Ave SE
2. 0762-0818 — 209 Pennsylvania Ave SE
3. 0762-0840 — 203 3rd St SE
4. 0762-0844 — 229 Pennsylvania Ave SE
5. 0762-0845 — 231 Pennsylvania Ave SE
6. 0762-0846 — 203 Pennsylvania Ave SE
7. 0762-0847 — 233 Pennsylvania Ave SE
8. 0788-0805 — 126 3rd St SE
9. 0790-0016 — 315 Pennsylvania Ave SE
10. 0790-0017 — 313 Pennsylvania Ave SE

Do not infer ownership or control from the shared tax-mailing address. Do not
treat the OTR sale-price field as stated consideration. Signatories,
consideration, lender/trustee roles, and return addresses may be reported only
from the actual recorded instrument.
