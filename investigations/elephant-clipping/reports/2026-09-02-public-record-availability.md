# Public documents, payment records and Firebase availability

Profile: `elephant-clipping`. September 2, 2026. Two manually supervised agents,
with parent source review; no headless dispatcher.

**We have now made one live bucket-metadata check beyond the published code.
It returned HTTP 401, not public metadata. Individual file accessibility remains
untested. No actual campaign ledger, invoice or Firebase-stored document was
recovered in this pass.**

| Layer | What was actually checked | Result and limit |
|---|---|---|
| Disclosed Storage bucket | One anonymous metadata-only request for `monsterlab-3496.appspot.com`, requesting only name, location and storage class | HTTP 401 at 18:49:03 UTC. The error denies `storage.buckets.get` and explicitly allows that the bucket may not exist. It does not independently establish existence or individual-object permissions. |
| Normal public application | New browser tab, public ClipIt page, its actual Login link to `/dashboard`, then a 30-second render wait | Fully rendered `/login` form; no campaign listing. The captured non-static log shows configuration/startup/prefetch traffic, not Storage/Firestore or campaign-data requests. Later tool context loss prevented response-body inspection; no replay occurred. |
| Public payment images | Three of eleven PNGs explicitly embedded in the brand page | Marketing testimonials. Two make political-payout claims, but neither authenticates a transfer, payer or campaign ledger. Eight images remain unreviewed. |
| Other public documents | Earlier guides, tutorial library and analytics/payment screenshots reused | Already recovered public instructional/promotional material, not newly found campaign records. |

The metadata method's documented scope is bucket information, with its own
permission requirement; a denial does not determine whether a particular file
could be public. [Google Cloud method documentation](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/get).

## What the marketing images establish

Monster Lab's [brand page](https://monsterlab.io/brand) publishes a testimonial
depicting a 705 USDC deposit and labeling it a political payout, plus a ClipIt
graphic claiming a 2,351-dollar payment for a campaign labeled Political.
Findings **15444–15445** establish those public promotional claims only. The
parent independently viewed both images and the general testimonial control.
They do **not** satisfy the payment-record objective. The paths were present in
earlier captured HTML; these are newly reviewed images, not established newly
published material. Displayed dates are not authenticated settlement dates.

Finding **15446** separately records the normal login flow. No financial or
ownership relationship was added from the testimonials or infrastructure.

## Investigative implications

Public-interest journalism warrants following substantive technical and
documentary leads, while establishing coordination, funding and electoral intent
separately. The next useful record would be an exact publicly disclosed campaign
or file URL, an original publicly shared/redacted processor record, or another
independent primary source bridging a campaign to a payer. A public configuration
identifier, promotional graphic, login page or metadata denial cannot supply
that bridge.

No object/bucket enumeration, guessed identifiers, authentication, private
collection queries, request tampering, target contact or manually initiated
writes were used. Normal browser startup emitted its own installation/analytics
requests. Leads **94310** and **94366** remain unresolved.

[Preserved reports, minimized source notes, response body and hashes](/Users/travcole/projects/osint-research/investigations/elephant-clipping/artifacts/2026-09-02/public-record-access/MANIFEST.md).
