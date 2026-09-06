# Serviuos ClipIt Mentorship — Archive Recovery (sanitized)

Lane: infra-wave / archive-retry (agent-L3-archive). Lead #95057.
Recovery of the `serviuos.com/clipit-mentorship` body that a prior pass abandoned
on HTTP 429 (methodology note 2505) and whose live path failed TLS (note 2591).
**A single 30s back-off cleared the 429 and the body was recovered.** `id_` replay
mode used (no Wayback banner). Raw HTML is retained only in the ephemeral workdir;
per-session `csrf-token`/Turnstile nonces are deliberately EXCLUDED from durable
storage — only stable selectors and raw-body SHA-256 provenance hashes are kept here.

## Captures recovered (raw-body SHA-256 = provenance of fetched bytes)

| label | url | timestamp | http | decoded_bytes | raw_sha256 | replay_final_url |
|---|---|---|---|---|---|---|
| mentorship_20250713202445 | https://www.serviuos.com/clipit-mentorship | 20250713202445 | 200 | 191102 | `3c6525796fe57ef3bb213378cc8fc862e23ed72bcc71912ad60595bdbdb77fd1` | https://web.archive.org/web/20250713202445id_/https://www.serviuos.com/clipit-mentorship |
| mentorship_20250713210048 | https://www.serviuos.com/clipit-mentorship | 20250713210048 | 200 | 191093 | `457070989e0c109a4522fc4b85da7b6c62db2b68a3acea43a223314a2bd997bf` | https://web.archive.org/web/20250713210048id_/https://www.serviuos.com/clipit-mentorship |
| mentorship_20251111192707 | https://www.serviuos.com/clipit-mentorship | 20251111192707 | 200 | 194885 | `b29a7dc601ed3280edeb7fb07dcc2dd7444259ad6076bb9558d4150e75ff86e8` | https://web.archive.org/web/20251111192707id_/https://www.serviuos.com/clipit-mentorship |
| mentorship_20251208104202 | https://www.serviuos.com/clipit-mentorship | 20251208104202 | 200 | 194926 | `24098f7018a7143f63f37ac9364dd8272321421f7be80c70a343959fa98a5e01` | https://web.archive.org/web/20251208104202id_/https://www.serviuos.com/clipit-mentorship |
| coaching_20250713202445 | https://www.serviuos.com/clipit-coaching | 20250713202445 | 200 | 191102 | `3c6525796fe57ef3bb213378cc8fc862e23ed72bcc71912ad60595bdbdb77fd1` | https://web.archive.org/web/20250713202445id_/https://www.serviuos.com/clipit-mentorship |
| coaching_20250713210048 | https://www.serviuos.com/clipit-coaching | 20250713210048 | 200 | 191093 | `457070989e0c109a4522fc4b85da7b6c62db2b68a3acea43a223314a2bd997bf` | https://web.archive.org/web/20250713210048id_/https://www.serviuos.com/clipit-mentorship |

- `/clipit-coaching` at both July 13 timestamps returns **byte-identical** content
  to `/clipit-mentorship` (matching SHA-256; replay `final_url` resolves to
  `.../clipit-mentorship`): **`/clipit-coaching` 302-redirects into the mentorship
  funnel.** `/clipit-coaching1` (named in the tasking) is **absent** from both the
  Wayback domain index and Common Crawl — genuinely not-archived, not a hammered zero.
- Three distinct content versions: July 13 2025 (~191 KB), Nov 11 2025 (~195 KB),
  Dec 8 2025 (~195 KB). Content grew ~3.7 KB July→Nov.

## Owner / platform metadata (stable across July + Nov + Dec captures)

- **Meta/OG/Twitter description (verbatim):** `Matiss Tabuns' Team Workspace`
- **Platform:** ClickFunnels (`myclickfunnels.com`; `events.myclickfunnels.com`;
  `statics.myclickfunnels.com`). Workspace slug **`JnnKBy`**
  (every image path is `statics.myclickfunnels.com/workspace/JnnKBy/image/...`).
- **Title:** `ClipIt 6 Week Mentorship`. og:image workspace image id `474299`.
- Operator self-identification in the body copy (verbatim): `Hi, I'm Servious. I don’t consider myself a guru. I’m just a regular guy from a small town in Latvia.`
- Latvia earnings claim (verbatim): `yes $100k me the kid from Latvia made $100k`
- Program branding in copy: `ClipIt` / `CLIPTOCASH`. Marketing claims include
  "Visited Whop HQ in New York", clipping Mikki Mase, and "big name clients"
  (Conor McGregor, Michael Jackson — promotional claims, not verified relationships).

## Payment rail (ClickFunnels-native checkout)

- The application/checkout form POSTs to `https://www.serviuos.com/clipit-mentorship`
  (method POST) with ClickFunnels order params incl. `purchase[rebilly_token]`,
  `purchase[payment_method_nonce]`, `billing_address_attributes[...]`, `contact[...]`.
- Embedded **live gateway publishable key** (public client-side key; stable
  July→Dec): `pk_live_oSLT21YBfpfTp6TqUF5JCZX4vxMenFyjAAjUiso` — assigned to BOTH `data-rebilly-publishable-key`
  and `data-stripe-publishable-key`; `data-rebilly-organization-id` / `-website-id`
  are empty (ClickFunnels-managed gateway scaffold). This is a THIRD payment rail,
  distinct from the two `buy.stripe.com` links on the AI Profit root page
  (`8wM6rnbnCeaYbAIaFZ` Kreator, `6oE00c5yyb4raSA3ci` AI Profit).
- A publishable key identifies a payment-gateway integration; it is **not** a
  legal-merchant identity or proof any charge occurred.

## Identity caveat

"Matiss Tabuns' Team Workspace" is owner-configured ClickFunnels metadata. Per
profile discipline it is an **identifier requiring corroboration**, not a confirmed
civil identity — a team workspace's display name may name an owner who is not
necessarily the sole operator. It is, however, the operator's own infrastructure
metadata on the operator's own funnel (self-identified "Servious"), which is a much
stronger link than a bare name coincidence. Corroboration pathway: Latvian
registers (SIA / self-employed merchant), OpenCorporates LV, GLEIF, social/OSINT
on "Matiss Tabuns" and ClickFunnels workspace `JnnKBy`.
