# Track D — deeds, mortgages and liens

Profile: `hassan-boston`. Research date: September 4, 2026. Workdir: `/tmp/osint-deeds-wol9xee9`. Durable evidence directory: `/Users/travcole/projects/osint-research/investigations/hassan-boston/evidence/deeds-finance`.

## Principal results

Six findings are persisted, with exact registry locators and reviewed-page metadata:

| Finding | Instrument | Result and review boundary |
|---|---|---|
| 15578 | Suffolk 17988/312, January 15, 1993 | First page names Hicham Ali Hassan, **Abdul Rahman Ali Hassan**, and Zouhair Ali Hassan as trustees of 400 Boylston Street Realty Trust, buying from Boylston Boston Corporation. Typed $1 million is crossed out and replaced by handwritten **$1,725,000**. Identified parcels include 392/394 and 396–398 Boylston. This directly resolves the ABDUL R index spelling for this deed. Other pages and source of consideration remain unread. |
| 15539 | Suffolk 19679/1, April 3, 1995 | Original first page names Hicham and Zouhair as trustees of 376 Boylston Street Realty Trust securing **$1 million** to Berkshire Life Insurance Company on 372–378 Boylston. Index links a **2001 release at 27659/170**, not yet read. This proves historical secured borrowing, not current debt or original equity capital. |
| 15572 | Suffolk 21956/120, December 2, 1997 | Original first page: Institutional Asset LLC conveys Brimmer by foreclosure deed to Zouhair as trustee of Eighteen Brimmer Street Realty Trust for **$325,000**, expressly subject to a 1994 mortgage and taxes/liens. Purchase price alone understates or may differ from total acquisition economics. |
| 15569 | Suffolk 56617/279, August 17, 2016 | Original first page: Hicham, acting as Brimmer trust trustee, conveys to Hassan Residential Properties LLC for **less than $100**. Prior title is the 1997 foreclosure. Index displays 100.00; the image says less than $100. |
| 15570 | Suffolk 56617/267, August 17, 2016 | Original first page: Hicham as trustee conveys both 216 and 218 Newbury to 216-218 Newbury Street Realty LLC for **less than $100**. Trust dated May 24, 1996, at 20592/119; prior deed dated June 5, 1996, at 20630/164. |
| 15573 | Suffolk 72957/242–243, July 1, 2026 | Both pages read: **$405,000 attachment**, docket 2184CV00205-BLS1, requested by Tivoli Audio against the LLC's real estate at 216–218 Newbury. Approved June 29, issued June 30, sheriff attached July 1 at 10:40 a.m. Legal track linked the underlying opinions. Do not add this amount to court awards or describe it as Hicham's personal debt. No subsequent satisfaction/release search completed. |

All six are paraphrases at `high` confidence. The original 1995 mortgage page is saved locally; remaining original scans were visually read and have exact excerpts, page numbers, and observed image URLs preserved. No unreviewed index entry was promoted into a claim of current ownership, debt or wrongdoing.

Finding 15578 is linked through the tracker helper to entities **7166 Hicham**, **7167 Zouhair**, and **7168 Abdul Rahman**, with trustee roles verified in the resulting junction rows. The other findings auto-linked their named targets. Audited corrections update 15569 after reading the 1997 deed and attach page metadata to all reviewed sources.

## Deliverables

- `instrument-ledger.csv`: 32 selected instruments and finance/title pivots. Explicitly distinguishes original-page review from index-only observations. Includes the six people; most individual index hits still require identity and capacity review.
- `search-coverage.json`: 13 exact source/query coverage records, including successful zero results and partial result-page review.
- `scan-observations.md`: readable original-image excerpts, interpretation boundaries, and acquisition gaps.
- `citation-map.json`: canonical reference → official Suffolk search portal. Viewer links are session-bound; use Recorded Land → Book Search with the reference's book/page.
- `source-image-locators.json`: exact observed encrypted image URLs for reproducibility while valid.
- `suffolk-19679-1-mortgage-page1.jpg`, source asset manifest, local UCC search outputs, and findings receipts.
- `index-selected-transcription.txt`: selected manually retained index strings; the later reviewed 1993 result supersedes its index-only identity limitation.

## Six-person coverage and name variants

Suffolk Recorded Land searched both party directions, December 13, 1972–September 4, 2026. Counts are **index occurrences, not unique instruments or owned properties**.

| Person / search | Observed coverage |
|---|---|
| Hicham: `HASSAN / HICHAM` | 35 rows, all read. `HACH` prefix: zero-hit dialog. |
| Abdul Rahman: `HASSAN / ABD` | 26 rows, all read. ABDUL R appears in 17328/343 foreclosure and 17329/1 mortgage (March 3, 1992), plus 17988/312 deed (January 15, 1993). Last deed's original image confirms full Abdul Rahman Ali Hassan. Other Abdelghany and Abdirahman rows were not assigned to him. Mortgage first image explicitly unavailable, so the two 1992 instruments retain their identity gap. |
| Zouhair: `HASSAN / Z` | 75 rows; first 50 read. Exact displays include `HASSAN ZOUHAIR` and `HASSAN ZOUHAIR A` with spaces. Initial rows for Ziad excluded. Original mortgage and foreclosure establish trustee roles. |
| Houssam: `HASSAN / HO` | 65 rows; first 50 read. `HU` prefix: zero-hit dialog. Includes multiple deeds, mortgages and releases at South End properties. Some mortgages index him as **grantee**, potentially indicating lending rather than borrowing; capacities require originals. |
| Talal: `HASSAN / TAL` | 2 rows, both read: 72170/29 unit deed and 72170/34 homestead, December 3, 2025. Person match remains unresolved; precise unit need not enter the public report. |
| Tarek: `HASSAN / TAR` | 24 rows, all read, including TAREK, TAREK A, TAREK ALI. Business property matches include Lexington, Havre, Marlborough and Meridian vehicles supplied by corporate track. 2016 tax lien has a near-date release candidate, not a current-liability finding. |

Middlesex South Recorded Land: HASSAN/HICHAM query returned a zero-hit dialog. No variants, entity names, or Registered Land searched there. Cambridge nexus needs a parcel-driven follow-up, not a claim of no property.

Local `query_registry.py ucc-search` for Hassan, all jurisdictions and MA, returned zero; the local UCC dataset contains only Florida (99,434 filings), so MA is a coverage gap. Successful public Massachusetts UCC current Article 9 debtor searches for HASSAN/HICHAM and 216-218 NEWBURY STREET REALTY LLC returned zero. **Lapsed archive, other individuals/vehicles, secured-party roles and separate liens database remain unsearched.** No known state filing number was obtained for a filing-detail lookup. This is bounded first-wave coverage, not a lien clearance.

## Exact next-record queue

1. Finish 1993 deed 17988/312 pages 2–3 and contemporaneous 400 Boylston trust declaration referenced as recorded herewith. Identify the acquisition mortgage, settlement funding, beneficial schedule and any partners. This is now the earliest reviewed multi-person acquisition.
2. **Lead 96187:** Brimmer foreclosure 21956/120 remaining pages; trust 21956/113; senior mortgage **19143/176 dated June 15, 1994**; foreclosing mortgage **21879/264 dated October 3, 1997**; Chapter 11 **97-10296-JNF**, Cameron Hall/Alexander Randall 5th, trustee Janet E. Bostwick. Quantify assumptions and sale consideration without guessing cash origin.
3. Berkshire release **27659/170 (2001)** and original acquisition **19678/333 (1995)**; mortgage 19679/1 remaining pages. Follow any replacement financing.
4. Newbury acquisition **20630/164**, mortgage **20630/170**, financing statement **20630/196** (June 1996), trust **20592/119**; full 2016 deed **56617/267** and certificate **56617/269**.
5. Remaining 2016 transfers **56617/263** (419 Boylston), **56617/271** (376 Boylston), **56448/317** (384–390 Boylston) and **56448/321** (392–394 Boylston). Read grantees, capacities, consideration and certificate references.
6. Attachment **72957/242** is reviewed; legal follow-up **96192** reconciles docket, execution, payment and release. Historical liens include Brimmer **25267/67**, **33269/285**, **33486/4**, plus reference-only **32601/291**, **38443/248–249**; 419 Boylston **41799/224, /226, /285, /287**, **42126/208**, and complaints **42275/98, /107, /114**. Check releases before liability assertions.
7. **Lead 96189:** the 1993 deed now resolves Abdul's full name; the two 1992 instruments still need full identity and financing review. Mortgage **17329/1 page 1** reports image unavailable; try other pages or another official representation later.
8. Review Houssam mortgagee candidates **46991/183** and **58093/179**, with release candidates **48231/216** and **58465/84**, to test whether some capital circulated as lending. Complete the unread 25 Zouhair and 15 Houssam index rows before calling their searches exhaustive.

## Learnings and operational limits

- Suffolk returns a zero-hit modal while retaining the previous search table. Read the modal, dismiss it, and verify the actual query before treating old rows as new results. No false zeros or stale rows were counted here.
- Clicking an image opens/reuses a separate viewer tab even though the parent page can appear unchanged. Read the browser tab inventory.
- Index consideration can differ materially from original language: both 2016 deed images say less than $100. A foreclosure price can also exclude assumed senior encumbrances.
- Name occurrence rows duplicate instruments across parties; preserve roles and do not count rows as holdings.
- Papercut **2669** records the local UCC CLI Chrome launch failure. CUA public lookup succeeded. Papercut **2684** records `ucc-stats --output` printing statistics without creating the requested file; a clearly labeled stdout observation was preserved.
- A single browser asset download took 524 seconds; later image reads preserve locators/excerpts instead of claiming downloaded files. The parent knows this limit.
- Audited correction writes briefly failed because root's auto-lead dry run held the database writer; after root released it, the corrections succeeded. Root owns logging that friction.

No subject contact, paid orders, records requests, bulk portal crawl, or headless dispatcher was used.
