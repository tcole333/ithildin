# Monster Lab / ClipIt client surface schema (public JS bundle)

Derived entirely from **public, unauthenticated** first-party assets served by
`monsterlab.io` (Next.js `_buildManifest.js` + 240 static JS chunks, ~8.95 MB,
all HTTP 200). Retrieved 2026-09-02. Build id `oT3om4jzC9FhrymKHBqql`.
No authentication, cookies, or tokens were used; nothing here is user-scoped
data — these are route/endpoint/collection **names** compiled into the public client.

## 1. Route map (from `_buildManifest.js`)

The public build manifest declares the full page-route table. Notable clusters
beyond the public marketing/auth pages (`/clipit`, `/brand`, `/login`,
`/signup`, `/forgot-password`, `/terms`, `/privacy`, `/blocked`):

- **Public campaign viewers:** `/campaign/[slug]`, `/c/[slug]` (both thin shells
  rendering a shared viewer component), `/share/campaign/[token]`, `/r/[code]`,
  `/u/[token]`, `/qr`.
- **Operator "control room"** `/dashboard/controlRoom/*`: `users`, `cr-wallet`,
  `credit-balance`, `crypto-payments`, `devices`, `discounts`, `proxies`,
  `registrations`, `social-media-monitoring`, `welcome-credits`, `onboarding`,
  `manage/products[/[productId]]`, `manage/subscriptions`, `manage/news`,
  `manage/billingIntervals`, `apps`.
- **Operator `cr-*` panels** under `/dashboard/`: `cr-antifraud`, `cr-audits`,
  `cr-auto-submit`, `cr-campaign-closure`, `cr-clipping-partners`, `cr-clips`,
  `cr-compliance`, `cr-discord-dm`, `cr-display-factor`, `cr-feedback`,
  `cr-grants`, `cr-impersonations`, `cr-ip-clusters`, `cr-knowledgebase`,
  `cr-mentorship`, `cr-merge`, `cr-monitored-accounts`, `cr-payouts`,
  `cr-polling`, `cr-rate-limits`, `cr-secure-folder`, `cr-site-mode`,
  `cr-tax-forms`.
- **Clipper-facing campaign machinery** `/dashboard/social-media-monitoring/*`
  (CampaignOffers, SubmissionsList/Table/Filters, URLSubmissionForm,
  TopClipsTab, UserLeaderboardTab, AnalyticsDashboard, appeal/edit/metrics modals).
- **Proxy / anti-detection toolbox** `/dashboard/myToolbox/*`: `checkProxy`,
  `formatProxy`, `pingIP`, `portScan`, `webrtcLeakTest`, `whatsMyIP` (+ Map),
  `rok`; plus `/dashboard/myStuff/{apps,devices,proxies,tasks}`.
- **Accounting ledger** `/books/*`: `ap`, `balance-sheet`, `close`,
  `due-to-owner`, `entry`, `expenses`, `exports`, `needs-review`, `pnl`,
  `reconciliation`, `settings`, `trial-balance`, `analytics`.
- **Money movement:** `/dashboard/wallet`, `/dashboard/checkout`,
  `/dashboard/stripe-return`, `/dashboard/shop`, `/dashboard/myAccount/invoices`,
  `/dashboard/myAccount/subscriptions[/browse|/manage]`.
- Other: `/dashboard/phone-ops`, `/dashboard/viral-collage`,
  `/dashboard/contentGeneration[/video]`, `/dashboard/mentor[ship]`,
  `/dashboard/api/{docs,keys,limits,usage}`, `/setup-mfa`, `/verify-email`,
  `/complete-profile`, `/reset-password`.

## 2. `/api/*` endpoint groups (250 distinct endpoints, 38 groups)

`account, admin, audit, auth, billing, brands, campaigns, chatbot, chutes,
clips, collaboration, devices, docs, feedback, keys, limits, mfa, news, oauth2,
passkeys, preview, projects, proxy, remotion, share, social-media, storage-url,
stripe, task-definitions, tasks, tax, toolbox, usage, users, validate,
version-control, waitlist, wallet`

Investigation-relevant server endpoints observed (names only): `admin/grants/clipit`,
`admin/antifraud/clusters`, `admin/rate-limits/cluster-payouts`,
`admin/impersonation/users`, `admin/crypto-payments/config`, `admin/tax-forms/queue`,
`billing/nowpayments/create-invoice` (NOWPayments crypto processor),
`billing/subscription/checkout|provision`, `campaigns/public/{slug}`,
`campaigns/apply`, `campaigns/track-click`, `share/campaign`, `brands/leads`,
`brands/apply`, `social-media/campaigns`, `clips/submit`, `wallet`, `tax`,
`storage-url?path=`. Full list: `api-endpoints.txt`.

## 3. Cloud Firestore collections (27 top-level names compiled into the client)

`appConfig, apps, bulkOperationJobs, bulkRefreshJobs, clipFeedback, discordBots,
discordBroadcasts, impersonationLogs, mentorshipCollections, mentorshipEnrollments,
mentorshipPayoutRuns, payoutAlerts, payoutCsvJobs, payoutSnapshots, payout_requests,
proxyPool, referralLinks, refresh, settings, socialMediaCampaigns, system_configs,
transactions, urlSubmissions, userPreferences, users, videoRuns, viralCollages`

Payment/campaign-relevant: **`socialMediaCampaigns`** (campaign objects),
**`payoutSnapshots`**, **`payout_requests`**, **`payoutAlerts`**, **`transactions`**,
**`urlSubmissions`** (submitted clips), **`videoRuns`**, `referralLinks`,
`impersonationLogs`, `discordBots`/`discordBroadcasts`, `proxyPool`.

## 4. Storage access pattern

Cloud Storage objects are **server-mediated**: the client obtains a download URL
via `GET /api/storage-url?path={encoded-path}` (path is a server-supplied
parameter) rather than referencing raw Storage object URLs. The only raw Storage
URL template in the client is the generic SDK form
`firebasestorage.googleapis.com/v0/b/${bucket}/o/...`. **No hard-coded public
Storage object path** is referenced anywhere in the client (no guessable,
already-public object names to reproduce).

## 5. What the client reads UNAUTHENTICATED vs AUTHENTICATED

- **Boot (`_app`):** the only Firestore read at startup is `users/{uid}` — gated
  on `onAuthStateChanged` (i.e., only after a user authenticates). No fixed-path,
  non-user-scoped config document is read anonymously at boot. (`appConfig` string
  matches in `_app` belong to the Firebase **Installations** SDK internals, not a
  Firestore read.)
- **Public pages:** `/brand` -> `POST /api/brands/apply`; `/clipit` -> auth flows
  (`/api/auth/register|sync`, `/api/oauth2/authorize`, `/api/auth/discord/callback`);
  `/campaign/[slug]` & `/c/[slug]` -> `GET /api/campaigns/public/{slug}` (+ POST
  `track-click`, `apply`); `/share/campaign/[token]` -> `/api/share/campaign`.
  The only unauthenticated **GET** of substance is the **slug-parameterized**
  `/api/campaigns/public/{slug}`. No unauthenticated non-parameterized data GET is
  exposed by a public page at load.
- **Everything under `/dashboard/*`** reads Firestore/`/api` only after auth.
