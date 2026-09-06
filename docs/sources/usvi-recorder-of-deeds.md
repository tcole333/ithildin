# U.S. Virgin Islands Recorder of Deeds

Verified 2026-07-30 against the Recorder of Deeds CountyFusion guest portal
linked by the [Office of the Lieutenant Governor](https://ltg.gov.vi/departments/recorder-of-deeds/).

The standalone adapter is `tools/query_usvi_recorder.py`. It covers the
territorial recorder index, instrument detail, associated-document selectors,
and caller-selected public PNG pages.

```bash
# One indexed name; all native pages are retrieved
uv run python tools/query_usvi_recorder.py search "SMITH" \
  --district "ST THOMAS" --date-from 2025-01-01 \
  --output /tmp/usvi-smith.json

# Multiple names use the portal's native multiple-name form
uv run python tools/query_usvi_recorder.py search \
  --name "SMITH A DAVID" --name "LEDER GREGORY" \
  --output /tmp/usvi-names.json

# Legal-description components
uv run python tools/query_usvi_recorder.py search \
  --parcel "3-17" --estate "ESTATE THOMAS" --unit "12" \
  --district "ST THOMAS" --output /tmp/usvi-legal.json

# Document type codes are checked against the live source vocabulary
uv run python tools/query_usvi_recorder.py search \
  --document-type DEED --date-from 2026-01-01 \
  --output /tmp/usvi-deeds.json

# Exact detail requires all locators emitted by search
uv run python tools/query_usvi_recorder.py document 2026000625 \
  --district "ST THOMAS" --inst-id 903442 \
  --output /tmp/usvi-2026000625.json

# Fetch one source page as PNG
uv run python tools/query_usvi_recorder.py page 2026000625 1 \
  --district "ST THOMAS" --inst-id 903442 \
  /tmp/usvi-2026000625-page-1.png \
  --output /tmp/usvi-2026000625-page-1.json

# Live index/detail/image sentinel
uv run python tools/query_usvi_recorder.py probe --json
```

## Source contract

The public flow creates a per-session Struts token, logs in as an anonymous
public guest, and accepts the Recorder disclaimer. Search then uses the
portal's advanced forms.

| Native search | Main fields |
|---|---|
| Names | party role, one name, match mode, district, date range, document types |
| All Names (Multiple) | up to the ten rows exposed by the source, plus the name-search fields |
| Condo / Estate | name and party, parcel, quarter/condo, estate, building, unit, plot, land comment, district, date range, document types |
| Doc Type / Date | district, date range, document types |
| Document Number | document number or range, district |
| Book / Page | book, page or page range, district |

The source advertises native page sizes 10, 15, 20, 40, 60, 80, and 100.
The adapter defaults to 100 and follows the native `next` cursor until the
advertised count is reproduced. `--offset` and optional `--limit` are applied
after that traversal. There is no adapter default result cap.

The live pagination probe returned 157 name matches over 16 ten-row pages and
advanced from `startCursor=0` to `startCursor=10`. A broader query returned
3,553 results and 356 pages; the portal did not ask for refinement or expose a
search cutoff. The portal's separate 1,500-document print behavior is not
treated as a search limit. An exact synthetic miss returned all three
authoritative empty-result signals: `noResults=true`, count and page count
zero, and “No documents were found that match the specified criteria.”

Document-type filters use the live
`getInstrumentCategories.do?ordertypes=1&rootstring=All%20Document%20Types`
tree rather than a copied code list. Observed codes include `DEED`, `MTG`,
`TRST`, `ASN`, and the longer source taxonomy.

## Identity and session reacquisition

CountyFusion emits an opaque `instId`, instrument number, instrument type, and
district with each result. Canonical identity is:

```text
source + territorial GEOID 78 + district + instId
```

For example, the live sentinel's native identity is
`ST THOMAS:903442`. Instrument number and book/page remain useful lookup and
join fields, but do not replace that identity. This preserves distinct records
if the same instrument number appears in both district indexes.

Detail and image routes are session-scoped rather than independently
addressable. A clean retrieval therefore searches the exact instrument number
and district, verifies the returned district, `instId`, and instrument number,
then selects the matching row. No match, several exact matches, or a locator
mismatch is reported explicitly.

The detail route returns document type and description, district, document
number, recorded timestamp, book/page, instrument date, Party 1, Party 2, legal
descriptions, and a second form page for associated documents. Party 1 and
Party 2 are preserved as native labels and normalized to grantor and grantee.
Associated instruments are emitted only when the source supplies their
`instId`, number, and type.

The verified image route first selects the requested source page, reads the
source page count, and then retrieves PNG bytes from the same Recorder-linked
host.
The adapter validates the final host, media type, and PNG signature and records
the byte count and SHA-256 digest. A page is nested as a document artifact of
the same canonical instrument; it is not another instrument or a second
corroborating source. Its normalized rights label is
`official_host_reference_image_uncertified`, reflecting the Recorder's
statement that the hosted image is reference material rather than the official
record or a copy issued by the Recorder.

The sentinel is ST THOMAS `instId=903442`, instrument `2026000625`, a DEED
recorded 2026-02-05. The detail reported six image pages. The page-one response
observed during verification was a 1,526×1,978 PNG, 907,966 bytes, with SHA-256
`de7fafb8c6b441f45891d01917cc6b1d886cd849323c711b54fbfe89cda4b4f9`.
The probe reports whether the current digest matches that observation without
using a watermarked image digest as record identity.

## Evidence meaning and complements

The Recorder disclaimer says that historical data from the 1800s through 1999
is still a work in progress, online information is for reference, and only the
record or copies from the Recorder are official. The adapter carries those
source warnings with its results.

Two official-source complements cover different needs:

- [USVI PublicSearch](https://usvi.publicsearch.us/) is the Recorder's newer
  search surface. It exposes quick/advanced search, parties, OCR, document
  type/number, book/page, and subdivision/condo fields. It is useful as a
  distinct retrieval surface and migration cross-check, but it represents the
  same recorder authority and is not independent corroboration.
- [USVI Capture CAMA](https://usvi.capturecama.com/) supplies assessment,
  parcel, situs, and tax-oriented fields. Those observations can join recorder
  instruments through parcel and legal-description fields but do not replace
  the recorded instrument.

The shared property router exposes native search, exact detail, and one
explicitly selected page while retaining those source roles:

```bash
uv run python tools/query_property.py search SMITH \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" \
  --output /tmp/usvi-shared-search.json

uv run python tools/query_property.py instrument 2026000625 \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
  --ingest --output /tmp/usvi-shared-instrument.json

uv run python tools/query_property.py download 2026000625 \
  --source us-vi-recorder-of-deeds-countyfusion \
  --jurisdiction 78 --district "ST THOMAS" --inst-id 903442 \
  --page-number 1 --destination /tmp/usvi-page-1.png \
  --ingest --output /tmp/usvi-shared-page.json

uv run python tools/public_records_monitor.py run \
  us-vi-recorder-of-deeds-countyfusion \
  --output /tmp/usvi-recorder-monitor.json
```

The monitor uses a fixed 12-request exact-detail sentinel and does not retrieve
an image. Normalization projects only the recorded instrument, indexed parties,
legal text, and any explicitly retrieved nested page artifact; it does not
create a parcel, sale, title, or current-ownership assertion.
