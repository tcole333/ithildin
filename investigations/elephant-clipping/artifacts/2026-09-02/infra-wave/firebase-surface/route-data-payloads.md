# `_next/data/*.json` route-data payloads (the abandoned login.json inspection, completed)

The prior pass (methodology note 2603) abandoned inspection of the `login.json`
response body after a browser tool lost its request index ("Request #55 not
found"). That was a transient tool failure, not a boundary. This resolves it by
reproducing the client's own unauthenticated GETs directly.

Build id `oT3om4jzC9FhrymKHBqql`. All requests unauthenticated, no cookies.

| Route-data URL | HTTP | Body |
|---|---|---|
| `/_next/data/<bid>/login.json` | 200 | SSR HTML shell (server serves the page HTML for this SSR route). `__NEXT_DATA__` -> `props.pageProps = {}`, `runtimeConfig = null`, `query = {}`, `page = "/login"`. |
| `/_next/data/<bid>/forgot-password.json` | 200 | SSR HTML shell, same empty-props shape. |
| `/_next/data/<bid>/signup.json` | 200 | `{"pageProps":{},"__N_SSP":true}` (31 bytes). |

Adding the Next.js client header `x-nextjs-data: 1` returns the same content.

## Result

**The route-data payloads carry no configuration, credentials, campaign data, or
personal data — they are empty server-rendered shells.** The Firebase config is
NOT injected via `__NEXT_DATA__`/`runtimeConfig`; it lives only in the client JS
bundle (see `firebase-webconfig.json`). This closes the prior pass's open item:
inspecting `login.json` yields no sensitive material.

Full extracted `__NEXT_DATA__` (login) top-level keys: `props, page, query,
buildId, nextExport, autoExport, isFallback, scriptLoader`. No `firebase`,
`apiKey`, `appspot`, `projectId`, `storageBucket`, `campaign`, `monster`, or
`clipit` substrings anywhere in the blob.
