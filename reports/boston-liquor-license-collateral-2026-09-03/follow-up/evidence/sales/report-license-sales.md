# Liquor-license transfers: prices and completion evidence

Checked September 3, 2026. This was a bounded search of official Boston and Massachusetts sources, focused on the existing Jana / Keryan transfer and on public availability of transaction documents. It did not establish a Boston license sale price or consummated closing. It should not be described as a search proving that such records do not exist.

## Strongest result: the transfer file contains the relevant financial records

The current [ABCC Application for a Transfer of License — Retail (11/2024)](https://www.mass.gov/doc/application-for-a-transfer-of-license-retail-112024/download) is a 14-page PDF. It was downloaded and its relevant pages visually inspected in the in-app browser.

- PDF page 1 requires a purchase-and-sales agreement and supporting financial records for financing or loans, including pledge documentation where applicable.
- PDF page 7, printed page 5, section 10 collects real-estate purchase price, business-assets purchase price, other transaction costs, and total cost. It separately collects contributors and contribution amounts, lender names, financing amounts and financing type, with signed financing documentation. It also requests a narrative explaining funding sources.
- On the same page, section 11 asks whether a pledge is requested, the collateral category (license, stock, inventory), and the recipient; signed pledge documentation is requested.
- There is **no dedicated license-only sale-price field** on this page. A purchase-and-sales agreement or allocation schedule is needed to distinguish the license consideration from the price of the business, inventory, property, or bundled assets.

The form is saved as `transfer-application.pdf`; extracted text is `transfer-application.txt`. Page 1 and page 7 were visually checked. This is a blank form, not a completed transaction application.

## What ordinary public pages provide

[Boston's application guidance](https://search.boston.gov/departments/licensing-board/apply-alcoholic-beverages-retail-license) says open-market purchases of transferable licenses require local Board and ABCC approval. Boston reviews the transfer application but does not participate in the private license market. This is consistent with distinguishing a transfer approval from evidence of payment or closing.

The [Boston meeting-materials page](https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members) provides voting minutes and hearing videos. It links the June 26, 2024 transactional hearing relevant to Keryan / Jana to [Boston City TV's recording](https://www.youtube.com/watch?v=bKm4ufl_1t4). The recording opened in the in-app browser, and the player reported subtitles/closed captions unavailable. It was not reviewed in full, so no sale-price claim is derived from it.

The [Boston forms page](https://www.boston.gov/departments/licensing-board/common-licensing-board-forms-and-applications) links a submission form for alcohol petitions. No publicly browsable completed application/attachment archive was identified on the inspected pages. This is an observed source-coverage gap, not a conclusion about legal disclosure availability or all possible portals.

## Specific acquisition route, not submitted

The [ABCC public-records page](https://www.mass.gov/info-details/submit-a-public-records-request-to-the-alcoholic-beverages-control-commission) provides a route for obtaining license files. It asks for the licensee's corporate name, DBA and address, and identifies a separate route to search active retail licenses through Accela. It also allows requests for hearing audio or transcripts using the licensee name and hearing date. The site describes possible copying/search costs; no request or payment was made.

For a targeted later request, the concrete records would be:

> The transfer application and financial-disclosure pages for Boston license LB-99458, transferred from Russian Benevolent Society, Inc. to Keryan & Co, Inc., doing business as Jana Grill & Bar, 14–20 Linden Street, Allston, with Boston Board action on June 26, 2024; the purchase-and-sale agreement and any license-price allocation, promissory note, pledge/security agreement, amendments, ABCC approval, and any closing confirmation or issued-license record held in that transaction file. Please provide existing electronic records with exempt personal identifiers redacted.

This is proposed request scope only. No third party was contacted.

## Search scope and exclusions

Official-domain web searches covered purchase price, consideration, sale agreements, the Keryan / Russian Benevolent names, and public application access. Queries were checked and logged in `search_log` as `web_official`, without inventing result counts for search-engine output. No findings/leads were added to the unrelated active investigation.

Search results included historical ABCC decisions for Lucioso's Pub in Plymouth and Championes in Everett that discuss business-assets purchase amounts or conflicting contracts. These are outside Boston, do not supply a clean license-only price, and were not relied on as completed-sale examples. A Boston City Council transcript discussing a license's possible market value was also excluded: a valuation mentioned in testimony is not a verified closing price.

For the parent review, use the independently extracted granted-transfer events as concrete ownership-change candidates. Keep separate columns for local approval, state approval/issuance evidence, stated consideration, actual payment/closing evidence, and any lien or pledge. A current roster matching a transferee is useful later-status evidence, but does not establish the amount paid.

## Operational note

The in-app browser successfully displayed the ABCC form and official hearing. Creating a second tab with a browser ID and `visible:false` returned an unsupported-visibility error in this subagent; omitting the visibility option worked. Logged as papercut #2654. No tool implementation was changed.
