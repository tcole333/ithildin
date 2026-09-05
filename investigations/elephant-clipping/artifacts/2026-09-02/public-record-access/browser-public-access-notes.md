# Rendered public-entry observation

Collector: `agent:public_records_access`; profile `elephant-clipping`; date September 2, 2026; finding **15446**; lead **94310**.

## Navigation and visible state

A supported browser tool created a **new dedicated tab** at `https://monsterlab.io/clipit`. The initial tab list otherwise contained only an `about:blank` tab. The public page visibly presented a **Login** link whose published URL was `/dashboard`; no authenticated account state appeared.

The investigator clicked that actual navigation link, not a sign-in button or form. The resulting page URL was `https://monsterlab.io/login`. A single 30-second render wait ended at 18:45:44 UTC. The rendered accessibility snapshot showed:

- “Welcome Back”
- “Login to your account and continue the motion”
- Empty email/password fields
- LOGIN, sign-in provider controls, and a REGISTER HERE link

No campaign listing or authenticated account was visible. No field was filled and no sign-in, account creation, payment or private request was attempted. This establishes a login surface for the **normal dashboard entry path**, not a comprehensive access-control audit or absence of other deliberately public share pages. The earlier HTTP-only `Loading...` response was insufficient on its own; the rendered observation resolves that specific gap.

## Sanitized page-made request list

The browser's non-static network list contained the following eleven entries after navigation and waiting. Query strings, keys, request bodies, cookies and session material are omitted. HTTP status is from the tool's network list, not from a separate replay.

| Count | Method | Origin and path class | Status |
|---:|---|---|---:|
| 3 | POST | `monsterlab.io/cdn-cgi/rum` | 204 |
| 2 | GET | `firebase.googleapis.com/v1alpha/projects/-/apps/[public-app-id]/webConfig` | 200 |
| 1 | POST | `firebaseinstallations.googleapis.com/v1/projects/monsterlab-3496/installations` | 200 |
| 2 | POST | `www.google-analytics.com/g/collect` | 204 |
| 1 | GET | `monsterlab.io/_next/data/[public-build-id]/login.json` | 200 |
| 1 | GET | `monsterlab.io/_next/data/[public-build-id]/forgot-password.json` | 200 |
| 1 | GET | `monsterlab.io/_next/data/[public-build-id]/signup.json` | 200 |

The source list reported **68 static requests omitted**. The non-static list contains no visible Firestore, Storage or campaign-data endpoint. That is bounded navigation coverage, not proof that no such endpoint exists or is accessible elsewhere. The three route-data requests are page startup/prefetch observations, not retrieved account records. No request was crafted or replayed. Normal page loading itself emitted analytics/RUM and Firebase Installations requests; the investigator did not submit those manually or use their returned session material.

An attempt to inspect only the response body of the already-listed `login.json` request failed: the tool said **“Request #55 not found. Use browser_network_requests to see available indexes.”** and reported the page as `about:blank`. Root confirmed it had not operated the browser. The unexplained context/index loss is a **tool/session limitation**, not a site redirect or access denial. No retry, request replay, body inference or further navigation followed. Firebase configuration, installation and analytics response bodies were not inspected.

## Preservation

Raw non-static request log: `/tmp/osint-Fk3kmuKS/browser-public-network-raw.txt`. Keep temporary only because URLs may contain query/session material. Rendered public login snapshot: `/tmp/osint-Fk3kmuKS/browser-public-login-snapshot.md`. It contains empty placeholders, not entered user data. Initial automatic tool snapshots remain in the browser's `.playwright-mcp` directory.

| Capture | Recorded time UTC (file modification) | Bytes | SHA-256 |
|---|---|---:|---|
| Public login snapshot | 2026-09-02T18:45:44.104086Z | 1696 | `a1da55f8fa0e911bf7e6e1e6d37407f1f9037fb090ea1b3c5cc1030d2b7896a0` |
| Temporary raw network list | 2026-09-02T18:45:44.110884Z | 2273 | `1a615c2fd2e3f22621d44223a03dd850c36dd915a5e78d2083b82e127db3e380` |

The first report and its notes were not changed during this follow-up. This file and the separate browser report are minimized preservation artifacts; no actual campaign or payment record was acquired.
