# Compass suite: DC CorpOnline filing boundary, 2021–2025

Date checked: 2026-07-23  
Lead: 73883  
Profile: oversight-project  
Global thread: 180

## Result

The free phase recovered a historical screenshot record for Compass
Professional Inc, but not the underlying authenticated filing images.

An archived Accountable.US PDF reproduces two DC government screens:

- a trade-name result for `Compass Professional Services` showing
  `Registration Date: 3/26/2021`, `Trade Name Status: Expired`, and `Trade Name
  Expiration Date: 9/01/2023`;
- a January 2024 `Beneficial Owners` view for `Compass Professional Inc` in
  which the visible `Type` for every row is `Governor`;
- a separate `Two-Year Report` image captioned `07/25/22`, which repeats the
  five names and addresses.

The source PDF links the old official entity page as:

`https://corponline.dcra.dc.gov/BizEntity.aspx/ViewEntityData?entityId=4296585`

The value `4296585` is preserved only as a **legacy CorpOnline entity ID**. It
is not labeled or treated as the entity's DC `FILE_NUMBER`.

## Exact historical screenshot fields

The reproduced entity table is headed `Beneficial Owners`, with columns
`Type`, `Business Contact Name`, and `Address`:

| Type | Business Contact Name | Address |
|---|---|---|
| Governor | Corrigan, Ed | 300 Independence Ave SE, Washington, DC 20003 |
| Governor | Vought, Russ | 300 Independence Ave SE, Washington, DC 20003 |
| Governor | Denton, Wesley | 300 Independence Ave SE, Washington, DC 20003 |
| Governor | McMahon, Sean | 300 Independence Ave SE, Washington, DC 20003 |
| Governor | Holland, James | 300 Independence Ave SE, Washington, DC 20003 |

The embedded report caption reads:

> Compass Professional Inc. Two-Year Report, Washington D.C. Department of
> Consumer & Regulatory Affairs, 07/25/22

The screenshot does **not** display a file number, document or tracking number,
signer, title beyond `Governor`, ownership percentage, distributional interest,
or the legal/control branch that caused a person to be reportable.

DC's current FAQ says the BRA-25 updates beneficial-owner information and that
DC reporting covers either an ownership interest exceeding 10 percent **or**
control of financial/operational decisions or day-to-day operations. Therefore
the screenshot's `Governor` rows cannot be converted into equity ownership
claims.

## Current public DC metadata

The current official DLCP ArcGIS layer returned zero records for each bounded
name query:

| Operational suite entry | Query | Result |
|---|---|---|
| Compass Professional Inc | `Compass Professional` | 0 |
| Compass Legal Group Inc / Compass Legal Services Inc | `Compass Legal` | 0 |
| Compass Property Management Inc | `Compass Property Management` | 0 |
| Compass Direct LLC | `Compass Direct` | 0 |
| Conservative Partnership Campus, Inc. | `Conservative Partnership Campus` | 0 |

An address search for `300 INDEPENDENCE` returned only two unrelated revoked
legacy records: Anderson Tuell LLP (`P27023`) and Dinino Associates LLC
(`L17560`). Neither is one of the scoped entities.

The public detail endpoint now expects the `GLOBALID` UUID from the current
layer. Submitting legacy numeric ID `4296585` returned HTTP 400: `The value
'4296585' is not valid.` The old official URL had only two observed Wayback
captures, both 302 redirects, so no entity page or filing image was recovered.

These are current-dataset negatives, not proof that the five operational suite
entries were never registered in DC. They also do not disconfirm the historical
screenshots. The agency said the December 2025 CorpOnline upgrade would
transfer filing histories and keep previously filed online documents
available, but the current public open-data record does not expose a migrated
UUID for these names.

## What is established and what remains open

Established at bounded confidence:

- the reproduced 2022 report and January 2024 entity view display the same five
  `Governor` rows for Compass Professional Inc;
- the historical trade-name screen displays the 2021 registration and 2023
  expiration dates above;
- the old official entity link used legacy identifier `4296585`;
- current free official name/address metadata does not surface the scoped
  entities.

Not established:

- any governor's equity percentage or beneficial ownership as an equity holder;
- Compass Professional's DC file number or migrated UUID;
- the 2023–2025 governor/beneficial-owner roster or address history;
- DC filing dates/numbers, governors, officers, or beneficial-owner fields for
  the other suite entries;
- common ownership or control across entities merely because names share an
  address.

Human action 102 holds the authenticated remainder. It requests the 2021–2025
registration, BRA-25/Two-Year, trade-name, amendment/correction, name-change,
status, and registered-agent filings for the exact scoped names, with every
field preserved exactly as labeled. No login, account creation, payment,
submission, or CAPTCHA bypass was attempted.

## Evidence trail

- Archived source PDF:
  <https://web.archive.org/web/20241110231224id_/https://accountable.us/wp-content/uploads/2024/09/2024-03-18-Executive-Office-of-the-President_Russ-Vought.pdf>
- Preserved rendered pages:
  `compass-professional-accountable-page-31.png` (SHA-256
  `f75165890898cb56474a93ba99512bc12d403c0cea775dc9a9c8e01ede8f0360`) and
  `compass-professional-accountable-page-32.png` (SHA-256
  `ab777d53e9a7b36e46fdd64f17296a35e8cb9cff46e90757d0488f86cfc0e8a0`)
- Consolidated public-query export:
  `dc-compass-suite-public-metadata-2026-07-23.json`
- Official ArcGIS layer:
  <https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Business_Licensing_and_Grants_WebMercator/FeatureServer/0>
- Official DC FAQ:
  <https://dlcp.dc.gov/page/corporations-division-business-registration-faqs>
- Official system-upgrade notice:
  <https://dlcp.dc.gov/blog/corponline-system-upgrade-%E2%80%93-what-you-need-know>
- Findings 14374 and 14375; human action 102.
