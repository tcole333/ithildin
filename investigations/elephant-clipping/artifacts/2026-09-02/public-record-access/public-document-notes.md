# Public payout-gallery source notes

Profile: `elephant-clipping`. Access date: September 2, 2026. Collector: `agent:public_records_access`. No authentication, form submission, payment, group join, private API query, bucket listing, guessed selector, or access-control bypass occurred.

## Discovery and observation

The owner-published [brand page](https://monsterlab.io/brand), linked from the [ClipIt landing page](https://monsterlab.io/clipit), contains the heading **REAL PAYOUTS. REAL CREATORS.** and states: “Our creators post proof of earnings every payout cycle. Click any screenshot to expand.” This is the publisher's characterization, not an investigator's authentication of payment.

The HTML explicitly links eleven distinct PNG paths, duplicated for its scrolling gallery: `result-1.png`, `result-2.png`, `result-3.png`, `result-4.png`, `result-6.png`, `result-8.png`, `result-9.png`, `result-10.png`, `result-15.png`, `result-16.png`, and `result-20.png`, each under `https://monsterlab.io/results/`. No omitted numeric path was guessed or requested. Only **three of eleven** images were downloaded and visually reviewed. The other eight remain unreviewed.

The coordinator compared the existing wave-one `monster-current-brand.html` and `monster-current-serviuos.html` captures with this fresh page. All disclose the same eleven image paths. These are **newly downloaded/reviewed in this pass**, not established newly published images. Earlier path existence also does not prove that historical image bytes were identical.

### Political testimonial A — finding 15444

Source: https://monsterlab.io/results/result-10.png

The chat-style caption reads “Political Payout of December...Thanks @SERVIUOS”. The depicted deposit panel reads “Deposit Details”, “+705 USDC”, and “Completed”; its explanatory text names a Binance account. A chat-style timestamp displays January 13, 2026, 1:11 AM. The image exposes no transaction hash, wallet address, bank/account number, invoice identifier, originating funds, or exact campaign identifier.

This records what the operator publicly presents. It does not authenticate the chat, the depicted deposit interface, the payment, its origin, payer, recipient identity or commissioning chain. The displayed timestamp is not an independently verified posting, gallery-publication or settlement date. Incidental display name/avatar were not transcribed or registered as entities.

### Political testimonial B — finding 15445

Source: https://monsterlab.io/results/result-20.png

The chat-style caption reads “One week with Political @SERVIUOS @Max”. A ClipIt-branded card displays `Campaign: Political`, `Date Period: Dec 14th - Dec 21th`, and `Received Payment: $2,351`. A chat-style timestamp displays December 26, 2025, 10:15 PM. The card's date period has no explicit year.

The graphic is an owner-published earnings claim, not a processor/bank receipt or a campaign database record. It supplies no actual campaign slug/ID, wallet or transaction identifier, payer, payment-source provenance, or account-to-campaign mapping. Neither displayed chat time nor date period is an independently verified publication or settlement date. The incidental display name/avatar were not transcribed or registered as entities.

### General testimonial control

Source: https://monsterlab.io/results/result-1.png

This first gallery image is a collage of ClipIt earnings graphics with a thank-you caption. It is another self-published testimonial, not an independent processor record. It was reviewed only as a content-type control; no additional financial finding was made from its figures or ambiguous small campaign lettering.

## Acquisition and hashes

| Exact public URL | Access time UTC | Response | Bytes | SHA-256 |
|---|---|---|---:|---|
| https://monsterlab.io/clipit | 2026-09-02T18:36:44.260406Z | HTTP 200 HTML | 154345 | `69c41b86fe5939ae919fc97c4c5c7ae86231c48cd638020cb3831d5aacf16648` |
| https://monsterlab.io/brand | 2026-09-02T18:38:10.604043Z | HTTP 200 HTML | 113697 | `25b0de4e4bbcb699ca10829aa423c5802fc9485a2f3fb0b716611e7bcbd2b827` |
| https://monsterlab.io/dashboard | 2026-09-02T18:38:10.255782Z | HTTP 200 HTML, “Loading...” only | 23314 | `e615aec4f6a5da44196f29c09a33644f66867f7a21c2093f213b6897ed4a6de8` |
| https://monsterlab.io/results/result-1.png | 2026-09-02T18:38:55.499809Z | HTTP 200 image/png | 416068 | `ec071424b0e71b8528144a435e1b1e399285c3d1f4a5ba667076a94ce04c76ac` |
| https://monsterlab.io/results/result-10.png | 2026-09-02T18:39:19.739617Z | HTTP 200 image/png | 223771 | `e30442ac6c19cdefe52b489d3749cb6cf93860f435cacb49a20e99479a85f8c0` |
| https://monsterlab.io/results/result-20.png | 2026-09-02T18:39:19.940882Z | HTTP 200 image/png | 307342 | `f4aa6de11336f969f0a41481c327f5bbda88011dc3583a686712e00110bf7fc1` |

ClipIt-page and image timestamps are capture-file modification times; brand/dashboard timestamps were recorded immediately before the HTTP requests. Raw HTML and original PNGs remain only in `/tmp/osint-Fk3kmuKS/`. The minimized notes intentionally omit incidental testimonial usernames and avatars. No image was redacted or edited.

## Evidence limits

The marketing publisher controls selection and could alter testimonials. There is one provenance chain, not independent corroboration. The findings are high-confidence paraphrases about **publicly displayed content**, with the underlying payment assertions expressly unverified. Neither record establishes a Firebase data exposure: the actual image URLs are same-domain public website assets. No Firebase data access was tested.
