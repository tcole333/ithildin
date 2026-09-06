# Hingham and two Hull assessor pivots — 2026-09-04

Hingham's official ownership-history table links **HOUSSAM ALI HASSAN** to the
Pinecrest parcel in 2006, followed by **PINECREST ROAD LLC** in 2007. Two exact Hull
parcel records list **HASSAN HICHAM ALI** and match the Plymouth recorder track's
address/deed pivots. No findings were created; the Plymouth track owns persistence
and original-instrument review.

## Hingham: historical owner and vehicle bridge

Official source: https://gis.vgsi.com/Hinghamma/Parcel.aspx?pid=5521

The parcel is 4 PINECREST ROAD, Hingham; Mblu `116/ 0/ 47/ /`; account
`1311160000000470`; PID `5521`. MassGIS independently maps it to PROP_ID
`116_0_47`, LOC_ID `F_818612_2904282`, CAMA_ID `5521`.

| Assessor sale date | Exact owner label in history | Source sale price | Book/page | Instrument code |
|---|---|---:|---|---|
| 2006-04-24 | HOUSSAM ALI HASSAN | 1,300,000 | 32556/0341 | 04 |
| 2007-11-07 | PINECREST ROAD LLC | 1 | 35274/0054 | 1F |
| 2010-01-28 | AVENI STEVEN V & COUSINEAU-AVENI | 1,375,000 | 38184/0289 | 04 |
| 2025-05-01 | KOLLOFF SEAN C & CHRISTEN | 2,320,000 | 59910/341 | 00 |

Exact excerpt supporting the first two rows: `HOUSSAM ALI HASSAN | $1,300,000 |
32556/0341 | 04 | 04/24/2006`; `PINECREST ROAD LLC | $1 | 35274/0054 | 1F |
11/07/2007`. Full original HTML is `hingham-pinecrest-5521.html`; its history table
is extracted without interpretation in `hingham-pinecrest-history.json`.

Two contextual bridges make this more than an isolated name match. Boston's
already-captured FY2019/2021/2026 assessment of 204 W Springfield Street names
`C/O HOUSSAM HASSAN TS` with 4 Pinecrest Road as mailing address. The existing
corporate inventory independently records **PINECREST ROAD, LLC**, MA ID
`000963451`, with Houssam manager, signatory and real-property roles. These
bridges support the match. They do not establish the LLC's beneficial owners,
the nature of its $1 transfer, family relationships, or the original source of
the 2006 purchase money.

The history also contains `MBALE MICHAEL A &`, date `01/01/1900`, book/page
`0000/0000`, price `$0`. Treat this as a placeholder with unknown actual date;
it is omitted from dated events. The municipal card labels its valuation year
2026 and total assessed value 2,645,900. This is not a sale price or equity.

**Registry priority:** retrieve 32556/341 and 35274/54, then 38184/289. The 2006
deed and same-period mortgages can test the purchase and financing; the 2007
deed should resolve the individual-to-vehicle transfer. The assessor table
does not label the grantor for these rows, so event exports leave `from_party`
blank rather than infer it from row order.

## Hingham current-owner screen and limits

The published municipal MassGIS DBF has **8,886 nondeleted rows**, all carrying
`FY=2027`. Executed 92 spelling-register queries against OWNER1 and OWN_CO using
case/punctuation-insensitive unordered tokens; joined ALIHASSAN was split for
search only. No target match. Also executed 55 exact vehicle-name comparisons
from the corporate inventory after removing punctuation and spacing; no match.
No variants were registered as aliases. Query IDs and inputs are preserved in
`hingham-name-variant-queries.csv/json` and `hingham-vehicle-queries.json`.

A broader HASSAN substring check returned one unrelated GHASSAN first-name
fragment; HASAN returned none. The live official VGSI owner search for HASSAN
returned the same unrelated result. It was excluded, with no identity link.
These negatives apply only to the indexed snapshot/current-owner labels, not
to historical ownership, undisclosed interests, trusts named differently or
all possible vehicles. The historical Pinecrest match demonstrates why the
negative current-owner result cannot be generalized to past ownership.

## Hull: exact property pivots

The parent asked for an evidence-led extension to two addresses found in the
Plymouth recorder index. This subtask did not conduct other-county or recorder
searches, nor an all-owner Hull surname screen.

| Parcel | Assessed owner | Last-sale fields in both municipal card and MassGIS | Municipal grantor label |
|---|---|---|---|
| 53 BEACH AVE; parcel 25-084; CAMA 2694; LOC_ID F_826811_2928691 | HASSAN HICHAM ALI | 2001-12-13; price 1; book/page 21123/41 | HASSAN ALI HICHAM-ABDUL RAHMAN |
| 121 NANTASKET AVE unit 307; parcel 39-307; CAMA 4294; LOC_ID F_831863_2922911 | HASSAN HICHAM ALI | 2017-08-31; price 1; book/page 48873/284 | SULLIVAN GREGORY V TRS |

Official municipal cards:
https://hull.patriotproperties.com/Summary.asp?AccountNumber=2694 and
https://hull.patriotproperties.com/Summary.asp?AccountNumber=4294 .
Both use the Boston business mailing location 218 Newbury Street, suite 3,
providing a second context beyond the exact name. Unit 307 matches the recorder
track's 48873/284 reference. The unit card's property-account field is `39-900`
while its parcel ID is `39-307`; do not conflate the condominium-level account
with the unit. It describes `Unit #307 %Int 1.36`.

Each municipal Sales panel exposed only its single latest row. The 1993
11586/230 and 1984 5787/169 deeds reported by the parent therefore remain
recorder-track work; the assessor page does not supply their earlier chain.
For Beach Avenue, prioritize 21123/41. Preserve the unusual grantor spelling
literally until the original identifies parties. For Nantasket, inspect
48873/284 to identify the trust represented by Sullivan and the consideration
terms; the assessor's nominal price field does not disclose transaction value.

The municipal cards label assessment year 2026: total 1,714,200 for Beach and
419,800 for unit 307. Their owner labels are assessor observations as viewed,
not proof of present title or beneficial ownership.

## Source vintage and durable evidence

Source discovery used the existing repository MassGIS manifest/probe/download
adapter and the municipalities' own links to their assessor applications.
Both linked ZIP archives were probed before download and preserved here.
Hingham DBF last-update is 2026-07-30; Hull is 2026-07-15. **Both manifests
reported FY2024 while their downloaded archives and all actual rows report
FY2027.** Papercut #2699 records this mismatch. Use the actual row FY as the
published label, with an explicit as-retrieved date of 2026-09-04. Do not turn
the future fiscal label into a claim about ownership in 2027 or merge its
assessment values with the municipal FY2026 cards.

Official archive URLs are recorded in `hingham-manifest.json` and
`hull-manifest.json`. Schemas, transfer receipts, archive hashes, selected raw
rows and variant-query ledgers are preserved. `hull-ui-observations.md` is an
explicit live-UI transcription: its grantor fields were read visually, not
claimed as downloaded HTML. A stateless archive attempt lost parcel context
and is not used as evidence. `events.csv` contains source-labeled sale-reference
and assessment-observation events, not established title intervals.
