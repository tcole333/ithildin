# Boston liquor-license transfer history: available records and next access steps

Checked September 4, 2026; proposed transaction cutoff September 3, 2026. This is an access audit and an **unsent** records-request scope. No agency was contacted, no request was submitted, and no fee was authorized.

The same official archive used for the 2024–2026 review also links material from **2020–2023**. The subsequent [archive extension](transfer-corpus/prior-2024/README.md) has now reviewed all 91 linked URLs: 89 unique PDFs, 906 pages, 319 transfer dispositions, 147 license-pledge dispositions and seven releases, with ownership actions and other notices separately recorded. The original index-access audit below is preserved as its own stage of work. This audit did **not** identify a verified machine-readable download of complete license transaction histories, completed transfer application packets, sale consideration, or closing records. The available active-license exports cannot establish lifetime transfer history.

## What is available

### Earlier voting material: 2020–2023

The retained [Boston Licensing Board information and members page](https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members) contains the following entries within its Voting Minutes section:

| Year | Dated list entries | Distinct linked URLs | Earliest–latest date label |
| --- | ---: | ---: | --- |
| 2023 | 21 | 21 | January 5–December 14 |
| 2022 | 24 | 24 | January 6–December 15 |
| 2021 | 25 | 26 | January 21–December 16 |
| 2020 | 19 | 20 | April 23–December 23 |
| **Total** | **89** | **91** | **April 23, 2020–December 14, 2023** |

There are 92 anchor occurrences because of repeated/split links. April 8, 2021 and September 10, 2020 each link two PDF variants. All 91 distinct URLs end in `.pdf`; their contents and file identities were not inspected during this initial access audit. The subsequent extension verified the two duplicate pairs and classified each item's disposition. The 2020–2021 links are labeled “Voting agenda” inside the Voting Minutes section; that title alone was not treated as decision evidence. These are **index counts**, not proof of 89 meetings with decisions or calendar-complete coverage. No pre-2020 archive/catalog link was found in the saved page; that does not establish that older records are unavailable.

Exact labels, URLs, title attributes and index anomalies are retained in [older-archive-index.json](history-access-evidence/older-archive-index.json), with [audit notes](history-access-evidence/older-archive-notes.md). The source snapshot is [archive-index.html](transfer-corpus/archive-index.html), captured September 4, 2026 at 02:01 UTC (September 3 Eastern); SHA-256 `13c41a6b49339b5290827a56632e76456f1eabc0d136fb55544945098802ac95`.

The existing 64-document corpus covers the linked 2024–2026 material through September 3, 2026. Its 307 transfer/pledge events and separate 146 ownership-interest decisions remain unchanged. This audit did not fetch the 91 older URLs or re-read the existing 64 documents.

### License lists: useful for matching, limited for history

Boston's [Commonly Requested Records page](https://www.boston.gov/departments/public-records/commonly-requested-records) explicitly describes the Licensing Board export as active-only. It excludes void, expired and closed licenses/establishments, and applications pending before the Board or ABCC. The separate Section 12 alcohol-license dataset is also described as active-only.

The retained [Licensing Board Licenses dataset](https://data.boston.gov/dataset/licensing-board-licenses) download has 3,610 rows, 3,593 distinct license numbers and Active status throughout. It contains identifiers, issuance/expiry dates, license classifications, names, comments and premises/contact fields. It has no dedicated transaction table, transferor/transferee pair, consideration field or closing-status field. `historicallicensenum` is an identifier column, not a transaction ledger; `issued` should not be treated as a sale date. See the existing [source manifest](../source-manifest.json) and [CSV](source-licenses.csv). The dataset landing page could not be reopened through the web tool during this audit; these details use retained provenance, independently supported by the City's current active-only description.

The official [ABCC records-access instructions](https://www.mass.gov/info-details/submit-a-public-records-request-to-the-alcoholic-beverages-control-commission) describe an active state/retail licensee search and a Download Results Excel option in Accela. That is a second active-license export, not a verified full-history download. The official indexed page text was available; direct page opening failed. No Accela or Secretary of the Commonwealth portal was queried.

### Transfer packets: the forms identify where financial terms may be recorded

Boston's [forms and applications page](https://www.boston.gov/departments/licensing-board/common-licensing-board-forms-and-applications) lists license transfers, stock changes, pledges and amendments, and directs alcohol petitions through an online submission form. No browsable repository of completed packets was identified on that page.

The previously retained [ABCC transfer application, November 2024 version](https://www.mass.gov/doc/application-for-a-transfer-of-license-retail-112024/download) is a blank form, not a transaction. Its checklist requests purchase-and-sale and financing material. PDF page 7 (printed page 5), section 10, asks for real-estate and business-assets purchase prices, other costs, funding contributions and loans; section 11 addresses pledges and supporting documents. There is no dedicated license-only price field. A signed purchase agreement and any allocation schedule are therefore needed to distinguish license consideration from a bundled business, inventory or property price. See the retained [sales evidence report](../follow-up/evidence/sales/report-license-sales.md).

The packet requirements show which records to seek. They do not establish that every submitted packet remains held, is published, includes an allocated license price, or proves that a transaction closed.

## Concrete existing-records request scope — draft only

The City's [public-records page](https://www.boston.gov/departments/public-records) now directs requests to **JustFOIA**, replacing GovQA. The verified linked destination is the [Boston public-records request form](https://boston.justfoia.com/publicportal/home/newrequest). A separate [ABCC public-records route](https://www.mass.gov/public-records-requests-to-the-abcc) can address state-held approval/application records. Start with the register and its coverage; select packets after availability and any cost estimate are known.

### Stage 1: existing transaction register and its coverage

Suggested scope for Boston:

> Please provide existing electronic records that record the history of Boston alcoholic-beverage licenses and associated applications or transactions, from the earliest retained date through September 3, 2026, including inactive, expired, cancelled, void and transferred-out licenses as well as current licenses. This includes any existing transaction register, event/audit history, report or export recording license transfers, stock or membership/beneficial-interest changes, entity conversions, pledges and pledge releases.
>
> Where maintained, requested fields are the Boston license number and prior/historical numbers, ABCC identifier, application/transaction and parent-record identifiers, transaction type, filing/hearing/decision/approval/issuance dates, disposition and status, prior and subsequent legal licensees and DBAs, premises addresses, transferor/transferee names, pledge recipient and release information, recorded consideration, and attachment/document identifiers. Please also provide existing field definitions, identifier crosswalks, date-range or migration documentation, and retention/archive inventories sufficient to explain what historical records the export covers.
>
> Please provide an existing export or report in its available electronic format; this request does not ask the office to create a new analysis or determine whether loans remain outstanding. If another office holds part of the requested records, please identify that office. Please provide any required cost estimate before undertaking chargeable work.

For ABCC, adapt the scope to its existing Boston retail-license application and amendment records and identifiers. Its published instructions ask targeted requesters to identify the licensee's corporate name, DBA and address. If a bulk historical register is not an available existing record, use those identifiers and a defined date range to select application files rather than assume a complete export exists.

### Stage 2: selected existing application packets and subsequent records

An optional [307-row packet selector](boston-records-packet-event-selector.csv) copies the canonical event IDs, printed/normalized license IDs, decision dates, exact action/outcome fields, parties, source URL, page and item number. It preserves repeat decisions, combined transfer/pledge rows, releases and revocation notices. Four rows from two combined items lack printed license IDs; these remain identifiable by date, item and parties. Source-page links point to voting evidence, not to application attachments. The selector is **not a paid-copy order** and does not imply 307 distinct applications. See its [manifest](history-access-evidence/packet-selector-manifest.json).

That selector remains a preserved 2024–2026 artifact. The subsequent [combined 780-action ledger](review-board-events-combined.json) adds the reviewed 2020–2023 window with source-window, document, page and party provenance. Use it for older packet candidates; neither ledger identifies 780 completed sales or distinct application packets. Ownership-interest actions and supplemental court notices remain separate.

Suggested packet scope, after the register identifies the relevant application IDs:

> For selected application/transaction IDs, please provide existing transfer or ownership-change applications and amendments; financial/source-of-funds pages; signed purchase-and-sale agreements and any schedules allocating consideration to the license; financing, promissory-note, pledge or security documents; amendments or releases; Board decisions; ABCC approvals; issued-license records; and subsequent records held by your office that document closing, withdrawal, cancellation or revocation. A shared packet need only be produced once, with its associated application IDs identified if already recorded.

For a bounded pilot, the selector includes the June 26, 2024 LB99458 transfer and pledge involving Russian Benevolent Society and Keryan & Co, Inc.; it also permits pairing earlier approvals with later nonclosing notices, such as LB99671 (September 26, 2024 approval and April 17, 2025 notice) and LB99070 (August 28, 2025 approval and March 5, 2026 notice). These chronologies illustrate why the final status must be checked rather than assumed from approval. A separate ownership-interest selector may be drawn from the [ownership-interest ledger](transfer-corpus/ownership-interest-events.json) if corporate-interest changes are part of the request; those events are not included in the 307-row transfer/pledge selector.

### Stage 3: older archive and remaining date gaps

Request existing voting decisions/minutes and transaction docket/register records before the earliest publicly linked date, plus any retained records for identified gaps after that date. Ask for the existing archive inventory, record-series/retention description and migration/transfer documentation if held. This makes the request concrete without asking the office to certify an invented start date or assemble new findings. The 2020–2023 URLs have now been downloaded and checked in the separate extension; use its manifest to avoid requesting duplicate public documents.

## What a completed review could claim

“Every current roster license was matched against the retained event corpus” describes roster coverage. It does not establish lifetime history: predecessor licensees, inactive records, older periods and missing decisions remain separate coverage questions. Likewise, a Board grant establishes the stated approval, not payment, a completed sale or a current loan balance. A stock/member-interest change can affect ownership without transferring the license, and those words alone do not identify a private-equity sponsor or a change in control.

The public archive extension is complete for its retained links. The next access question is whether Boston or ABCC holds an export of historical transactions. Packet evidence can then resolve price allocations, buyer/seller identities and post-approval outcomes for selected events. The bounded access findings and failures are retained in [access-observations.json](history-access-evidence/access-observations.json) and [search-audit.json](history-access-evidence/search-audit.json). The request scopes above remain unsent.
