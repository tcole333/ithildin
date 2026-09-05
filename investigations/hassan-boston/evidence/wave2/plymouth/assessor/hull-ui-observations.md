# Hull assessor UI observations — 2026-09-04

Read using the Town of Hull's linked Patriot Properties public field-card UI.
Town route: https://www.town.hull.ma.us/648/Assessed-Values---Hull-Field-Cards
redirects to https://hull.patriotproperties.com/default.asp .
The welcome page calls this Fiscal Year 2026. These are assessor observations,
not original recorded instruments or a title opinion.

## Parcel 25-084

Source: https://hull.patriotproperties.com/Summary.asp?AccountNumber=2694

| Source field | Exact displayed text |
|---|---|
| Location | 53 BEACH AVE |
| Property Account Number | 25-084 |
| Parcel ID | 25-084 |
| Old Parcel ID | BEA -DUN- |
| Owner | HASSAN HICHAM ALI |
| Business mailing address | 218 NEWBURY ST SU#3; BOSTON; MA; 02116 |
| Sale Date | 12/13/2001 |
| Legal Reference | 21123-41 |
| Sale Price | 1 |
| Grantor(Seller) | HASSAN ALI HICHAM-ABDUL RAHMAN |
| Year | 2026 |
| Total Value | 1,714,200 |

The linked Sales panel at https://hull.patriotproperties.com/g_sales.asp displayed
one row: `12/13/2001 | 1 | 21123-41 | HASSAN ALI HICHAM-ABDUL RAHMAN | 101`.
That Sales URL is session-dependent: open the parcel summary first. Preserve the
unusual grantor string; it cannot be expanded into two resolved people from this
table alone.

## Parcel 39-307

Source: https://hull.patriotproperties.com/Summary.asp?AccountNumber=4294

| Source field | Exact displayed text |
|---|---|
| Location | 121 NANTASKET AVE, Unit 307 |
| Property Account Number | 39-900 |
| Parcel ID | 39-307 |
| Owner | HASSAN HICHAM ALI |
| Business mailing address | 218 NEWBURY ST SU 3; BOSTON; MA; 02116 |
| Sale Date | 8/31/2017 |
| Legal Reference | 48873-284 |
| Sale Price | 1 |
| Grantor(Seller) | SULLIVAN GREGORY V TRS |
| Year | 2026 |
| Total Value | 419,800 |
| Legal Description | Unit #307 %Int 1.36 |

The linked Sales panel displayed one row:
`8/31/2017 | 1 | 48873-284 | SULLIVAN GREGORY V TRS | 102`.
The account number 39-900 is the condominium-level account label; preserve the
separate unit parcel ID 39-307. The MassGIS CAMA_ID 4294 matches the summary URL
parameter. The trustee's represented trust is not identified in this card.

## Capture limitation

These tables were transcribed from the live rendered UI. A separate stateless
HTTP archive attempt did not preserve the selected parcel context, so no Hull
HTML file is represented as an archived parcel card. The durable MassGIS archive
and exact matched source rows independently preserve the parcel IDs, owner
labels, sale dates, prices and book/page references; the UI adds the grantors.
