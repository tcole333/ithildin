# /brand testimonial gallery — full review of all 11 result PNGs

The `monsterlab.io/brand` page (also embedded on `/clipit`) publishes 11
testimonial screenshots at `monsterlab.io/results/result-{1,2,3,4,6,8,9,10,15,16,20}.png`
(all HTTP 200). The prior pass reviewed only ~3 (findings 15444, 15445). This
reviews all 11. These are **operator-published marketing testimonials**, i.e.
screenshots of Discord messages the operation chose to display — they are
unverified promotional CLAIMS, not authenticated payment records.

PII minimization: the individual testimonial authors' Discord display names and
avatars are incidental third-party data and are NOT recorded here. Only the
operation's own promoted handles, campaign labels, and displayed figures are kept.

## Recurring elements

- Every "EARNINGS WITH CLIPiT" card carries a QR to **`discord.gg/clipit`**.
- Operation handles thanked across the set: **@SERVIUOS** (known primary operator),
  **@Max** (frequent co-operator), plus **@VODEGE**, **@nakeeb**, and
  **@Clipit Payouts** (payout account/bot). @VODEGE / @nakeeb / @Clipit Payouts are
  new selectors not previously recorded.
- Two recurring campaign labels on the cards: **"Political"** and **"AL Clipping"**
  (several posters explicitly tie both to political clipping, e.g. "One week with
  Political", "First Month clipping fr political", "w clipit w political").
- Payout rail claimed: **USDC crypto**, delivered to a **"Binance account"** (spot)
  or **"Funding Wallet"** — consistent with the client's `crypto-payments`,
  `wallet`, `payoutSnapshots`, `transactions` backend and the NOWPayments
  `/api/billing/nowpayments/create-invoice` endpoint.

## Per-image contents (figures as displayed; timeframes Dec 2025 – Jan 2026)

| File | Type | Campaign label | Displayed amount(s) | Notes |
|---|---|---|---|---|
| result-1 | CLIPiT earnings card ×3 | AL Clipping | $1,367; $632; $414 | multi-week |
| result-2 | text + phone photo | (political) | — | "political help me pay"; payout→iPhone |
| result-3 | CLIPiT earnings card | AL Clipping | $6,003 | "First Month clipping fr political" |
| result-4 | CLIPiT earnings card | AL Clipping | $2,348 | thanks @SERVIUOS @Max |
| result-6 | text + laptop photo | — | — | "New MacBook. Thank you, ClipIt" |
| result-8 | Deposit Details | — | +4,294 USDC (Completed, Binance) | "clipping for TR"; thanks @SERVIUOS @VODEGE @Max @Clipit Payouts |
| result-9 | Payment Details | — | +766 USDC (Completed, Funding Wallet) | From/Time/Order ID blurred **by the poster**; thanks @SERVIUOS @nakeeb @Clipit Payouts |
| result-10 | Deposit Details | political | +705 USDC (Completed, Binance) | "Political Payout of December" (prior finding 15444) |
| result-15 | CLIPiT earnings card ×3 | Political / AL Clipping | $1,059 (Political); $1,043; $1,115 | "@SERVIUOS @Max political" |
| result-16 | CLIPiT earnings card | AL Clipping | $2,976 | thanks @SERVIUOS @Max |
| result-20 | CLIPiT earnings card | Political | $2,351 (Dec 14–21) | "One week with Political" (prior finding 15445) |

## Assessment

The gallery **corroborates the operation's own claim** that it pays clippers, in
USDC crypto, for political clipping campaigns branded "Political" and "AL Clipping",
and that @SERVIUOS/@Max (with @VODEGE/@nakeeb/@Clipit Payouts) run payouts through
`discord.gg/clipit`. It does **not** authenticate any transfer, payer, recipient,
counterparty, or ledger — screenshots are self-published marketing and trivially
fabricable. The redacted fields in result-9 (From/Time/Order ID) show the poster
themselves withheld the settlement identifiers. Max confidence: paraphrase/`high`
for "the operation publishes these claims"; the underlying payments remain
unverified. New leads: identify the "AL Clipping" campaign/client and resolve the
@VODEGE / @nakeeb / @Clipit Payouts handles.
