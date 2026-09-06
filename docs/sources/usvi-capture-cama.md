# USVI Capture CAMA assessor and property-tax portal

## Source boundary

- Source ID: `us-vi-property-tax-capture-cama`
- Authority: USVI Office of the Lieutenant Governor, Office of the Tax
  Assessor
- Official authority page:
  <https://ltg.gov.vi/departments/office-of-tax-assesment/>
- Primary search:
  <https://propertytax.vi.gov/CAMA/CAPortal/Custom/CZ_RealPropertySearch54.aspx>
- Platform family: E-Ring/Capture CAMA Citizen Access Portal
- Observed: 2026-07-30

The authority page links `https://usvi.capturecama.com/`. That hostname and
`propertytax.vi.gov` expose the same USVI Capture tenant. The former is useful
as a failover route, but the two hostnames are duplicate representations rather
than independent corroboration.

This source publishes assessment-roll and property-tax observations. Owner
labels, mailing addresses, assessed values, balances, sales labels, tax
statements, and payment rows do not by themselves establish current recorded
title.

## Verified live contract

The anonymous search is an ASP.NET WebForms form with these native selectors:

| Role | Form control |
|---|---|
| Owner | `NameSearchText` |
| Formatted parcel | `ParcelSearchText` |
| Property address | `AddressSearchText` |
| Legal description | `LegalSearchText` |
| Tax year | `TaxYear` |
| Page size | `RecordsDDL` (`10`, `50`, `200`) |

The result grid is `GridView1`. It publishes total-result text, formatted
parcel number, tax year, internal `ParcelId`, owner and mailing labels,
property and legal addresses, land/improvement/total/assessed values,
exemption, current-year and total balances, class, municipality, and millage
code.

Native pagination uses WebForms postbacks on `GridView1` with
`Page$First`, `Page$Prev`, `Page$Next`, and `Page$Last`. An end-to-end browser
probe advanced a `SMITH` owner search from rows 1–200 to rows 201–400 of 986
published 2026 results using:

```text
__EVENTTARGET=GridView1
__EVENTARGUMENT=Page$Next
__LASTFOCUS=
RecordsDDL=200
TaxYear=2026
```

The view state, event validation, search controls, and other hidden form
values came from the immediately preceding page. The adapter follows `Next`
until it disappears, verifies that each page advances, and checks the fetched
unique-row count against the published total. A caller `--limit` is applied
only after that traversal.

A bounded legal-description search for `ST JAMES` returned four 2026
observations covering published Great St. James and Little St. James parcels.
An exact parcel search for `1-09801-0101-00` demonstrated that the internal
locator is tax-year specific:

| Tax year | `ParcelId` |
|---|---:|
| 2026 | `1614772` |
| 2025 | `1582141` |
| 2024 | `1485057` |

The durable observation identity is therefore:

```text
formatted parcel number + tax year
```

`ParcelId` is retained separately as the source locator needed to open that
year's detail record.

## Detail and child records

The parcel detail shell publishes a navigation component and a valuation
component. Navigation provides the owner/mailing/location/legal summary and
routes for:

- valuation and tax history;
- land;
- buildings;
- assessment-layer sales;
- photographs;
- maps; and
- the printable property record card.

The valuation component publishes three distinct child collections:

- tax statements/invoices, keyed under the parent parcel observation by tax
  year and statement number;
- annual valuation rows, keyed by valuation year; and
- payment transactions, keyed by the published transaction ID.

Bill print views and payment receipts have their own document identity domains.
Their selectors are discovered from the corresponding statement or payment
row. Live checks found that tax bills, receipts, and property cards resolve to
printable HTML (`Receipt` or `PRC Print` pages), not PDFs. Downloads validate
the final official hostname, HTML media type, document title signature, byte
length, and SHA-256 digest. Session GUIDs are acquired from the live search and
retained only for the same search/detail/download transaction; they are not
part of persisted child identity.

## CLI

```bash
# Show source capabilities
uv run python tools/query_usvi_property_tax.py source --json

# Exhaust all native result pages
uv run python tools/query_usvi_property_tax.py search legal "ST JAMES" \
  --tax-year 2026 --output /tmp/usvi-st-james.json

# Apply an explicit caller window after native exhaustion
uv run python tools/query_usvi_property_tax.py search owner SMITH \
  --tax-year 2026 --limit 50 --output /tmp/usvi-smith.json

# Exact parcel detail, including valuation/tax, land, building, and sales text
uv run python tools/query_usvi_property_tax.py parcel 1-09801-0101-00 \
  --tax-year 2026 --output /tmp/usvi-parcel.json

# Printable bill and receipt HTML
uv run python tools/query_usvi_property_tax.py artifact 1-09801-0101-00 \
  --tax-year 2026 --kind bill --statement 24457395 \
  --destination /tmp/usvi-bill.html --output /tmp/usvi-bill-metadata.json

uv run python tools/query_usvi_property_tax.py artifact 1-09801-0101-00 \
  --tax-year 2026 --kind receipt --transaction-id 1786629 \
  --destination /tmp/usvi-receipt.html \
  --output /tmp/usvi-receipt-metadata.json

# Shared routing, projection, and drift monitoring
uv run python tools/query_property.py parcel 1-09801-0101-00 \
  --source us-vi-property-tax-capture-cama --tax-year 2026 \
  --ingest --output /tmp/usvi-shared-parcel.json
uv run python tools/query_property.py download 1-09801-0101-00 \
  --source us-vi-property-tax-capture-cama --tax-year 2026 \
  --artifact-kind bill --statement 24457395 \
  --destination /tmp/usvi-shared-bill.html --ingest \
  --output /tmp/usvi-shared-bill.json
uv run python tools/public_records_monitor.py run \
  us-vi-property-tax-capture-cama \
  --output /tmp/usvi-cama-monitor.json
```

Omitting `--tax-year` uses the portal's currently selected native year.
Omitting `--limit` returns the complete traversed result set.
Artifact destinations are not replaced unless `--overwrite` is explicit.

Shared normalization creates parcel snapshots keyed by formatted parcel and
tax year. The published owner label becomes a dated `assessment_roll`
assertion tied to that source version; it is not a recorded-title or beneficial
ownership conclusion. Valuation rows become assessments, and statement,
balance, and payment rows become tax events. Payer names, assessor sales,
land/building text, and selectors for artifacts that were not downloaded stay
in the raw observation. A printable view becomes a `document_artifact` only
after the HTML has actually been retrieved and hashed.

The fixed monitor uses the exact parcel/year search, detail shell, navigation,
and valuation component in five requests. It does not retrieve photographs,
maps, property cards, bills, or receipts. Stable route, paging, identity, and
nested source-column contracts are hashed separately from rolling owner,
value, balance, locator, statement-count, and payment-count observations.

## Official field-matched complements

When a CAMA representation is absent or a different evidence domain is
required, the closest official complements are:

- the Office of the Tax Collector for tax status, tax-clearance certificates,
  delinquency lists, and payment-plan records; and
- the Recorder of Deeds for recorded instruments, grantor/grantee indexing,
  recording dates, and instrument-level legal descriptions.

Those sources answer different questions. Matching a parcel, party, address,
or legal description across them is a join, not an identity collapse.
