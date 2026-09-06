# Franklin County Auditor bulk data

Source ID: `us-oh-franklin-county-auditor-bulk`

Adapter: `tools/query_ohio_franklin_auditor_bulk.py`

Official sources:

- Data landing: <https://auditor.franklincountyohio.gov/Auditor/FTP>
- Anonymous file directory: <https://apps.franklincountyauditor.com/>

The Franklin County Auditor publishes assessment, tax-accounting, conveyance,
parcel CSV, and GIS extracts as files in an anonymous IIS directory tree. The
data landing explains the releases; the file host provides the machine-usable
directory and artifact contract. The landing and file hosts can behave
differently at the transport layer, so source health is based on the official
file directory while retaining the landing URL as provenance.

## Published families

| Family | Source organization | Useful contents |
|---|---|---|
| `appraisal` | `Outside_User_Files/<year>/<date> Appraisal/` | Parcel, land, building, dwelling, improvement, permit, and three assessor-sale workbooks, plus Excel and tab-delimited archives |
| `tax-accounting` | `Outside_User_Files/<year>/<date> Tax Accounting/` | Parcel, payment, rental contact, special assessment, tax detail/distribution, transfer, and value workbooks, plus archives |
| `daily-conveyances` | `Daily_Conveyances/` | Daily and consolidated conveyance workbooks |
| `gis-shapefiles` | `GIS_Shapefiles/CurrentExtracts/` and year/month archives | Parcel polygons, FileGDB, boundaries, appraisal neighborhoods, and other county GIS layers |
| `parcel-csv` | `Parcel_CSV/<year>/<month>/Parcel.csv` | Wide parcel, assessment, owner-observation, address, value, transfer, and building fields |

`current` means the newest release exposed by that family's own source
organization. It is not forced into a common calendar model. In particular,
the parcel CSV tree currently ends at path period `2025-07`, while its
`Parcel.csv` file has a later file-modification timestamp. The adapter records
the path period and modification timestamp separately and leaves
`release_date` unset when the publisher supplies only a month directory.

## Operations

```bash
WORKDIR=$(mktemp -d /tmp/osint-franklin-auditor-XXXXXXXX)

uv run python tools/query_ohio_franklin_auditor_bulk.py source --json
uv run python tools/query_ohio_franklin_auditor_bulk.py families --json

uv run python tools/query_ohio_franklin_auditor_bulk.py releases appraisal \
  --output "$WORKDIR/franklin-appraisal-releases.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py releases parcel-csv \
  --year 2025 --output "$WORKDIR/franklin-parcel-releases.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py releases gis-shapefiles \
  --all-releases --output "$WORKDIR/franklin-gis-releases.json"

uv run python tools/query_ohio_franklin_auditor_bulk.py artifacts tax-accounting \
  --release current --output "$WORKDIR/franklin-tax-artifacts.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py artifact-probe \
  daily-conveyances DailyConveyances_20260723.xlsx --sample-bytes 64 \
  --output "$WORKDIR/franklin-daily-probe.json"

uv run python tools/query_ohio_franklin_auditor_bulk.py download tax-accounting \
  Payment2025.xlsx --release current \
  --destination "$WORKDIR/Payment2025.xlsx" \
  --output "$WORKDIR/franklin-payment-download.json"

uv run python tools/query_ohio_franklin_auditor_bulk.py inspect-local \
  "$WORKDIR/Payment2025.xlsx" --record-family payment \
  --output "$WORKDIR/franklin-payment-schema.json"
uv run python tools/query_ohio_franklin_auditor_bulk.py rows \
  "$WORKDIR/Payment2025.xlsx" --record-family payment \
  --release-id tax-accounting-2026-07-15 --release-date 2026-07-15 \
  --source-url https://apps.franklincountyauditor.com/Outside_User_Files/2026/2026-07-15%20Tax%20Accounting/Payment2025.xlsx \
  --parcel 010-000001-00 --output "$WORKDIR/franklin-payment-rows.json"

uv run python tools/query_ohio_franklin_auditor_bulk.py probe --sample-bytes 64
```

Release and artifact listings accept optional `--limit` and continuation
cursor arguments. Row extraction streams an explicit local workbook or text
artifact. With no `--limit`, it scans all matching rows; a caller-selected
limit returns a continuation cursor bound to the file hash and query criteria.
ZIP parsing uses an explicit member name so archive membership remains part of
row provenance; XLSX rows include both the outer member and inner worksheet in
their occurrence identity. Downloads use the shared resumable bulk-transfer
path and write to the caller's selected destination. `--max-download-bytes`
is an optional caller-selected ceiling. Shared local-row calls can pass the
download record's exact URL with `--artifact-source-url`.

## Identity and evidence grain

- A release ID combines the family with the publisher's directory date,
  filename date/range, or archive path period.
- An artifact ID is derived from its official relative path. Directory size
  and modification time describe the listed version; probes add ETag,
  Last-Modified, byte-range support, and a bounded signature; completed
  downloads add the full SHA-256 digest.
- A parsed row is one physical occurrence identified by release ID, artifact
  SHA-256, archive member and worksheet when applicable, and physical row
  number.
- Normalized sale identity is separate from that occurrence. Appraisal Sales
  use parcel plus `INSTRUNO`; daily conveyances use parcel plus
  `CONVEYNUMBER`. When the publisher omits the business number, parcel, sale
  date, instrument, sale type, amount, and available parties form a
  conservative deterministic fallback.
  Repeated rows across releases remain separate observations but update one
  business `sale_event` on a cross-roll parcel anchor. Source release period
  ranks before retrieval time, so a historical artifact fetched later cannot
  regress a newer projection; annual parcel snapshots remain separate.
- Raw headers, raw cell values, duplicate-header occurrences, and the complete
  source field map are retained beside the small parsed projection.
- Parcel identifiers are join candidates scoped to county GEOID `39049`.
- Franklin projections remain on Franklin-owned annual parcel shells or the
  cross-roll sale-event anchor. OGRIP keeps its own same-lineage parcel
  representation, so loading it before or after a bulk release cannot move or
  duplicate Franklin facts; normalized parcel aliases remain available for
  explicit joins.
- These files and the interactive Franklin Auditor property source share the
  same county authority. Agreement between them is source redundancy, not
  independent corroboration.

The implemented official `Sales Information` ArcGIS complement,
`us-oh-franklin-county-auditor-sales-gis`, adds structured recent
grantor/grantee, conveyance, validity, parcel, address, structure, and point
fields. Its observed date range is source-managed and does not make it a
replacement for the longer monthly release history. Layer 0 is the canonical
feature layer; layers 1–4 are renderer aliases. See the [Sales GIS source
contract](ohio-franklin-auditor-sales-gis.md) for its query, identity,
projection, and monitoring semantics.

The adapter keeps each component's assertions at its native grain. A payment
row is not a parcel-title row; an assessor sale or daily conveyance row is not
silently promoted to a Recorder instrument; owner strings are preserved as
publisher observations rather than resolved ownership conclusions.

## Parsed row contracts

The streaming parser currently exposes `parcel`, `value`, `payment`,
`transfer`, `sales`, and `daily-conveyance` row families. Each output includes:

- release and artifact provenance, SHA-256, file size, source URL, worksheet or
  ZIP member, header row, physical row, raw headers/values, and source fields;
- parsed parcel ID, event date, amount, owner and prior-owner strings,
  instrument, tax year, and bill type when the source component provides them;
- raw and normalized parcel join candidates; and
- a deterministic row-occurrence reference.

Live schema verification on 2026-07-31 covered representative workbooks:

- `DailyConveyances_20260723.xlsx` (36,542 bytes; SHA-256
  `2cf8bc4dd0f4142efc45ec2a629b06c681c5688ff79baaefcaa75a1ccbf9e346`)
  has a title row followed by 17 fields including conveyance number, parcel,
  sale date/price, current and prior owner strings, situs, and instrument type.
- `Payment2025.xlsx` (1,854,494 bytes; SHA-256
  `4eade2e78c4e278fd8c794fcf773aaaa21f4ed14afdf8263460b85eec03d458a`)
  has `Parcel Id`, `EffectiveDate`, `TaxYear`, `BillType`, and `Amount`. Its rows
  show that the filename year and row tax year are separate source facts.
- `Sales010.xlsx` uses the 21-column appraisal-sales contract beginning with
  `PARCEL ID`, `MAP ROUTING`, `SALEDT`, `NOPAR`, `INSTRUMENT`, `INSTRUNO`,
  `VALID`, `SALETYPE`, and `PRICE`, followed by adjusted-price and conditional-
  sale fields. `SALEDT` includes pre-2000 XLSX datetimes. `VALID` includes
  `0 - VALID`, adverse codes such as `99 - RMS INVALID`, and blanks.

Dated positive-price appraisal Sales rows can project to `sale_event` while
retaining the raw `VALID` value in `qualification_code`; an adverse or blank
code is not represented as qualified or arm's-length. Rows without a parsed
date or positive price remain observations. Daily-conveyance rows use
`ISEXEMPT=NON-EXEMPT` as their projection signal; `SALETYPE` describes asset
scope (`LAND AND BUILDING`, `LAND ONLY`, or `BUILDING ONLY`) and is not used as
a validity flag.

Other row families use family-specific header contracts and can be inspected
before a full scan. Unknown headers return `source_changed` with the selected
family and header-scan context rather than being silently remapped.

## Health monitoring

`probe` performs a bounded live check:

1. verifies the official IIS listing identity and required top-level family
   directories;
2. resolves the current release for all five families using their native
   naming patterns; and
3. metadata/range-probes one current daily workbook using the requested sample
   byte count without downloading a large artifact.

Monitoring should treat directory title/host, required family paths, naming
contracts, and artifact signature behavior as structural state. Current
release IDs, artifact sizes, modification times, and ETags are rolling release
state. A release update should therefore remain distinguishable from source
schema or transport drift.
