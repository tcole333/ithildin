# Epstein local artifact metadata audit — 2026-07-29

## Scope and method

This is a full metadata inventory of supported files currently present under
`datasets/epstein-archive/data`, plus the five local top-level EFTA PDFs. The
scanner read the source artifacts without modifying them and stored exact
SHA-256 hashes, locations, and format-aware observations in the regenerable
`datasets/epstein_derived.db` sidecar.

The audit covered 27,724 file locations representing 14,702 unique byte-level
artifacts and produced 564,545 metadata observations. Supported material
included EML and mail sidecars, PDF, CSV, RTF, JSON, JPEG, PNG, and WebP files.
ExifTool was not installed, so the media pass captured container properties but
not the broadest possible EXIF/IPTC/XMP/device metadata.

Metadata dates were kept in separate provenance layers:

- `source_native`: email/application metadata
- `production_lineage`: mailbox sidecars and production-system fields
- `release_container`: PDF/release-wrapper metadata
- `container_embedded`: media/container tags needing interpretation
- `acquisition`: local filesystem and scan observations

No metadata observation in this report is promoted as a factual finding about
an underlying event.

## Results worth following up

### 1. The Yahoo tree is an exact two-path mirror

The `jeeproject_yahoo` tree contains 26,020 EML locations but only 13,010 unique
files. The root contains 13,010 messages and the nested
`jeeproject@yahoo.com tranche 1` directory contains exact byte-for-byte copies
of the same 13,010 messages.

**Operational consequence:** searches and frequency counts must deduplicate by
SHA-256 or message identity. Counting paths doubles this collection and creates
false corroboration.

### 2. The Yahoo collection extends well past the 2019 reference date

Header dates on the 13,010 unique Yahoo messages range from 2007-09-20 through
2021-12-07. Of those, 5,618 have a header date after 2019-07-06.

**Inference, not fact:** this appears to be a mailbox/archive collection whose
scope extends beyond Epstein's lifetime, not a closed historical set bounded by
his death. The account ownership, acquisition history, and inclusion criteria
should be verified before treating all messages as Epstein-origin material.
Post-2019 dates are not by themselves suspicious.

### 3. Barak sidecars preserve useful production lineage but not full messages

The Barak directory contains 925 `.eml.meta` sidecars and seven `.eml` files.
None of the sidecars has a same-basename EML companion. The sidecars contain
mailbox path, sender, optional subject, message date, change date, flags,
internal IDs, size, and a blob digest. The audit hashes—but does not retain—the
sidecar's metadata text.

The 925 sidecars contain 917 distinct blob-digest values; eight digest values
appear twice. If the producing system's digest semantics can be confirmed,
those pairs are strong candidates for logical-message deduplication even though
the sidecar files themselves differ.

Mailbox placement across all sidecars:

| Folder | Sidecars |
|---|---:|
| `/Inbox/` | 493 |
| `/Sent/` | 423 |
| `/Sent Messages/` | 9 |

The source-message dates span 2013-01-08 through 2016-03-19. All recorded
`change_date` values fall between 2016-03-22 10:49:34Z and
2016-03-23 07:59:42Z.

**Inference, not fact:** the narrow change-date window is consistent with a
bulk mailbox export, index, or production operation. It should be treated as
lineage timing, not communication timing. A useful next step is to seek the
corresponding blobs/load files and test whether `blob_digest` or internal IDs
provide a crosswalk.

### 4. PDF metadata mostly describes later release and conversion history

Several PDF fingerprints are useful for clustering release workflows:

- `EPSTEIN FLIGHT LOGS UNREDACTED.pdf` identifies Numbers as creator, macOS
  Quartz as producer, title `JE Flight Logs CSV`, and a 2020-12-16 creation
  timestamp.
- `Evidence List.pdf` identifies the Department of Justice as author, includes
  `Evidence List; Epstein Files Phase 1` keywords, and carries 2025-02-27
  creation/modification timestamps.
- `Gieuffre vs Maxwell Exhibit D.pdf` identifies Nicole Simmons as author,
  Microsoft Word 2010 as creator, and Acrobat/iText production tooling.
- `Jeffrey Epstein's Black Book.pdf` carries author `mep`, title/creator
  `EXHIBITS_STM_UNDISPUTED_FACTS.PDF`, and Acrobat Paper Capture production.
- `jeffery_epstein_records_4_2.pdf` identifies US CBP as author.
- `EFTA01091533.pdf` identifies Firefox and macOS 26 Quartz and carries a
  2026-02-14 timestamp, indicating that this local PDF is a later
  browser/print-style container rather than an original contemporaneous file.
- Six transcript PDFs in `text/lvoocaudiop1` carry sequential creation times on
  2026-01-12, consistent with one batch generation session.

These are release/container observations. They may help identify common
production batches, but they do not date the underlying evidence.

### 5. Structural validation and exact duplicate artifacts

Four top-level EFTA PDFs (`EFTA00190141`, `EFTA00198118`, `EFTA00300480`, and
`EFTA01322916`) parse successfully but produce a qpdf `expected endobj`
warning. That is a recoverable structural warning, not a failed or unreadable
PDF. `Email 1.pdf` and `jeffery_epstein_records_4_2.pdf` also parse
successfully with recoverable linearization/hint-table warnings. The other 17
scanned PDFs pass qpdf validation without warnings.

Other exact duplicates include:

- `Gieuffre vs Maxwell Exhibit 1.pdf` and `exhibit-1.pdf`
- three Barak EML duplicate pairs
- mirrored thumbnail paths for two estate images
- six 15-byte CSV table extracts, plus one repeated substantive CSV table

The CSV duplicates indicate extraction/layout artifacts and should not be
treated as distinct records.

## What the audit did not establish

- It did not authenticate who created or controlled any email account.
- It did not establish that a PDF author/creator field is truthful.
- It did not infer event dates from release, conversion, or filesystem dates.
- It did not parse image EXIF/IPTC/XMP comprehensively because ExifTool is not
  installed.
- It did not promote metadata-derived claims into `investigation.db`.

## Recommended next passes

1. Obtain or locate Barak mailbox blobs/load files and build a crosswalk using
   `blob_digest`, internal IDs, message size, sender, subject, and source date.
2. Install/enable ExifTool only if a deeper image/device-location review is
   justified, then rescan the 693 JPEG/PNG/WebP locations.
3. Analyze the 26 unique messages with attachments by attachment hash and
   filename, linking duplicates back to message IDs without extracting private
   body content.
4. Treat the Yahoo mirror as one logical collection in all downstream corpus
   metrics.

## Reproduction

```bash
uv run python tools/epstein_metadata.py stats --output /tmp/metadata-stats.json
uv run python tools/epstein_metadata.py report \
  --reference-date 2019-07-06 --output /tmp/metadata-report.json
uv run python tools/epstein_metadata.py show EFTA01091533 \
  --output /tmp/metadata-efta01091533.json
```
