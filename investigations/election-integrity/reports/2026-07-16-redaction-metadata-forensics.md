# Redaction & Metadata Forensics + Declassification-Authority Timing

**Date**: 2026-07-16 (follow-up forensic pass on the WH election-integrity release)
**Tools**: pdffonts, pdftotext, qpdf, pdfinfo/XMP, pdfimages, raw-byte strings. No exiftool available.
**Scope**: all 58 PDFs + the 4 zips' macOS artifacts.

## Bottom line
The **digital** redaction craft is actually sound — cleaner than typical government releases. The improper redactions are confined to the **scanned-image** domain (strikethrough-legible names), and the metadata is thoroughly **scrubbed** (no authors, usernames, or paths corpus-wide). The most analytically significant finding is timing: the declassification authority had just shifted away from the departed DNI (Gabbard) to CIA Director Ratcliffe and White House Counsel Warrington — a shift visible directly on the stamps.

## 1. Redaction integrity (tested, not assumed)
- **Text-under-black-box (cosmetic redaction)**: NEGATIVE. Font analysis separates the corpus into (a) scanned images with an Adobe `HiddenHorzOCR` layer (NICA, etc.) — redactions baked into the raster, and (b) born-digital text-layer docs (the Outlook-printed emails, the DHS one-pager, the NICM). For the born-digital docs, `pdftotext` extraction shows the redacted values (classification lines, names, the Alien-summary black bar) were **removed from the text layer**, not merely covered. No extractable text sits under any black box.
- **Annotation-based (deletable) redactions**: NEGATIVE across all 58 files — no `/Redact`, `/Square`, `/Highlight`, or `/FreeText` overlay annotations. Redactions are flattened vector fills or baked into images, i.e., the correct method.
- **Email header scaffolding**: on the born-digital emails, personal names are stripped but Outlook display-name suffixes survive (`… NSA USA GOV`, `@nsa`, one `DNI-` recipient). This leaks *routing structure* (multiple NSA recipients + a DNI recipient) but **no actual names**.
- **Improper redactions that DO exist** — all in scanned images:
  - The FBI Inspection Division "Strategic Review" handout (`Tasking_3_AlbanyBriefingHandout…`) leaves **senior officials named** where line staff are boxed: the interview roster (p.3) names Nikki Floris and Tonya Ugoretz (both "Unable to contact") while boxing ~33 other interviewees; the org chart (p.4) names all SES executives (Kohler, Floris, Benavides, Cohen, Fomby, Relford, Young, Byron, Hardiman, Gorham, Ugoretz) while boxing every subordinate. This is likely a deliberate release choice, not a failure — the box redactions themselves are opaque and sound.
  - **Two FBI line-analyst names remain legible through failed strikethroughs** in the handout's electronic-communications exhibits (a genuine QC failure). The names are non-public employees and are deliberately **not recorded** in this repo.

## 2. Metadata (new detail beyond the first pass)
- **Scrubbed corpus-wide**: zero `/Author`, zero usernames, zero `/Users/` or `C:\Users\` paths, zero full agency email addresses in raw bytes across all 58 files. `dc:creator` and `xmpMM:subject` are empty even on the born-digital 2026 docs. Whoever prepared the release was careful with digital metadata — in contrast to the sloppy image strikethroughs.
- **Born-digital 2026 docs — XMP timeline**:
  - `Voter Registration Database Threats – FINAL` (DHS/CISA): MS Word for M365; **created 2026-06-24 13:41:52, modified 2026-07-13 17:55:00**.
  - `CISA Election Report – FINAL`: Acrobat PDFMaker 26 for Word; **created 2026-07-13 18:14:12, modified 2026-07-16 12:14:24** (release day). → both born-digital products share a **July 13 finalization session**, with the CIA-adjacent items assembled July 14 (`CIA Wire Memo` created 7/14 13:53; `CIA Venezuela note` 7/14 14:00:59).
  - DocumentIDs/InstanceIDs present (uuid) but carry no PII.
  - Shared **Joanna MT** typeface across the two DHS docs = a common template/author fingerprint.
- **FBI Albany IIR**: Producer `iText 2.1.7 by 1T3XT`, Title "FBI Albany IIR Provided to Chairman Grassley", **ModDate 2025-07-01** — confirms it is the recycled 2025 Senate Judiciary production, not a 2026 declassification.
- **macOS artifacts**: only 2 of 4 collections carry a `.DS_Store` (Michigan @ 12:21, Noncitizens @ 18:26 on release day) — both are empty `Bud1`/`DSDB` stubs (no folder-name or username leak), but their timestamps corroborate the two-phase build (midday assembly + ~18:26 evening rebuild) already seen in the quarantine xattrs.

## 3. Declassification-authority timing (the Gabbard/Ratcliffe throughline)
Tulsi Gabbard resigned as DNI — announced ~2026-05-22, effective **late June 2026** (June 19 per Wikipedia; end-of-June per CNN), citing her husband's cancer, after months of reported friction and being sidelined in favor of CIA Director John Ratcliffe. Map that onto the release's stamps:

| Declassifying authority | Date | Which documents |
|---|---|---|
| **DNI Gabbard** | 16 Mar 2026 | Only the Jan-2020 NICM — an *earlier* tranche, while she was still DNI |
| **CIA Director Ratcliffe** | 1 Jul 2026 | The CIA Venezuela note (authored 29 Jun, "not coordinated within the IC") |
| **President Trump** | 3 Jul 2026 | NICA, Oct-2020 NICM, several emails |
| **WH Counsel Warrington** | 10 Jul 2026 | CIA WIRe, key emails, **all FBI files** |

The NIC products in this release (NICMs, NICA, the ICA emails) are **ODNI-owned** — the DNI is normally their declassification authority. But every July-window declassification routed **around ODNI**: through the President directly, the CIA Director, and White House Counsel. The acting DNI appears nowhere as a declassifying authority.

**Succession (verified)**: Gabbard resigned May 22, 2026; **Bill Pulte** (FHFA director, no IC background) was named acting DNI to bipartisan backlash that contributed to the failure of the Section 702 reauthorization push; **Jay Clayton** (ex-SEC chair, SDNY US Attorney) was nominated as permanent DNI June 11, with Pulte remaining acting until confirmation. Clayton's Senate confirmation hearing — where he was questioned about election integrity — was **July 15, 2026, one day before this release**. Sources: [NPR](https://www.npr.org/2026/06/11/nx-s1-5855365/trump-director-of-national-intelligence-jay-clayton-bill-pulte-fisa-702), [NBC](https://www.nbcnews.com/politics/white-house/trump-nominates-jay-clayton-director-national-intelligence-rcna349673), [CBS](https://www.cbsnews.com/news/jay-clayton-trumps-dni-nominee-senate-confirmation-hearing/). In other words, the intelligence-declassification lever had just passed from Gabbard (ODNI) to Ratcliffe (CIA) + the White House, and the release's most sensational new document — the Venezuela "vote-totals-altered-undetectably" note — was authored the week Gabbard departed and declassified by her rival two days later (1 July), amid Ratcliffe's broader early-July declassification push. This is consistent with the rushed, Counsel-driven assembly fingerprint (template placeholders on the page, July-13/14/16 born-digital timestamps, careful metadata scrubbing but sloppy image strikethroughs).

**Sources**: [CNN](https://www.cnn.com/2026/05/22/politics/tulsi-gabbard-resigns), [NBC](https://www.nbcnews.com/politics/white-house/tulsi-gabbard-resign-director-national-intelligence-sources-say-rcna264273), [Wikipedia](https://en.wikipedia.org/wiki/Tulsi_Gabbard), [NBC on Gabbard-vs-CIA declassification](https://www.nbcnews.com/politics/politics-news/tulsi-gabbard-declassified-documents-objections-cia-sources-say-rcna223548).
