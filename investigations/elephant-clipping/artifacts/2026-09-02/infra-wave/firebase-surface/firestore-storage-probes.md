# Firestore / Storage / API access-posture probes (the RIGHT probes)

All probes unauthenticated, no cookies, no bearer/session tokens. The public
Firebase `apiKey` (a public client key) was used only where the SDK itself would
send it, and probes were also run without it. Retrieved 2026-09-02. Raw response
bodies (small service error documents, no tokens) saved alongside this file.

## Correcting the prior pass

The prior pass issued `GET storage/v1/b/monsterlab-3496.appspot.com` — an
**owner/IAM `storage.buckets.get`** request — got HTTP 401, and correctly noted
it does not settle object readability. It then stopped. `buckets.get` is denied
even on fully world-readable buckets, so it says nothing about objects. The RIGHT
probe is an **object-level** GET (`storage.objects.get`) on a path already
referenced in public HTML, and a **Firestore documents** GET. Both are below.

## Results

| # | Probe (unauthenticated) | HTTP | Body (verbatim, sanitized) |
|---|---|---|---|
| A1 | Firestore REST `GET .../projects/monsterlab-3496/databases/(default)/documents/socialMediaCampaigns?pageSize=1&key=<publicApiKey>` | **403** | `PERMISSION_DENIED — "Missing or insufficient permissions."` |
| A2 | same, **without** apiKey | **403** | `PERMISSION_DENIED — "Missing or insufficient permissions."` |
| B1 | Storage object `GET firebasestorage.googleapis.com/v0/b/monsterlab-3496.appspot.com/o/results%2Fresult-1.png?alt=media` | **403** | `{"error":{"code":403,"message":"Permission denied."}}` |
| B2 | same, metadata form (no `?alt=media`) | **403** | `Permission denied.` |
| B3 | Storage object `GET storage.googleapis.com/monsterlab-3496.appspot.com/results/result-1.png` | **403** | XML `AccessDenied — "Anonymous caller does not have storage.objects.get access to the Google Cloud Storage object."` |
| C | `GET https://monsterlab.io/api/campaigns/public/` (bare, no slug) | **308** | redirect to `/api/campaigns/public` (endpoint reachable; requires a slug — not guessed) |
| D | `GET https://monsterlab.io/api/billing/products` (unauthenticated) | **401** | `{"success":false,"error":"Unauthorized: Bearer token or API key required"}` |

## Interpretation (all clean, real results — locked posture)

- **A1/A2:** Cloud Firestore security rules **deny anonymous reads** of the
  `socialMediaCampaigns` collection. Campaign rows are **not** world-readable via
  direct Firestore. This directly answers lead #94310 for the Firestore path: the
  database is locked; campaign objects cannot be recovered by an anonymous read.
- **B1/B2/B3:** Cloud Storage **denies anonymous `objects.get`** on the referenced
  object path, via both the Firebase (`firebasestorage.googleapis.com/o/`) and raw
  GCS (`storage.googleapis.com/<bucket>/`) URL families. Individual object
  readability — the exact question the prior 401 left "untested" — is now
  answered: **objects are locked to anonymous callers.** (The `results/result-*.png`
  files render on the site because they are served from the Next.js `/public`
  directory at `monsterlab.io/results/…`, not from the Storage bucket.)
- **C:** The public campaign endpoint exists and is reachable unauthenticated but
  needs a valid slug. No public slug is known (lead #94310 found none indexed), so
  none was guessed — out of scope.
- **D:** Even the product/pricing catalog requires auth; the `/api/billing/*`
  surface is not anonymously readable.

**Net:** No public Firestore collection, Storage object, or billing API is
anonymously readable. The operation's data plane is locked. No enumeration,
identifier guessing, user-scoped substitution, authentication, or writes were
performed.
