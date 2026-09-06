# serviuos.com live-path TLS characterization (route-around outcome)

The prior pass's live `serviuos.com/clipit-mentorship` fetch failed TLS validation
(note 2591) and was abandoned. Re-probed here to characterize (no `-k`/validation
bypass; the archive was the substantive route-around and succeeded).

- `curl -sSI https://www.serviuos.com/clipit-mentorship` ->
  `curl: (60) SSL: no alternative certificate subject name matches target host name
  'www.serviuos.com'`
- `curl -sSI https://serviuos.com/clipit-mentorship` (apex) -> same error for
  `'serviuos.com'`.
- Certificate actually served (both www and apex), via `openssl s_client`:
  - subject: `C=US, ST=California, L=San Francisco, O=Netlify, Inc, CN=*.netlify.app`
  - issuer:  `C=US, O=DigiCert Inc, CN=DigiCert Global G2 TLS RSA SHA256 2020 CA1`
  - SAN: `DNS:*.netlify.app, DNS:netlify.app`

**Interpretation:** serviuos.com now resolves to Netlify's edge, but no
custom-domain TLS certificate is provisioned for serviuos.com there, so Netlify
serves its default `*.netlify.app` certificate whose SAN does not cover the host.
This is a **real current-state condition, not a transient failure** — the site
migrated off ClickFunnels (which hosted the archived mentorship funnel) and the
custom-domain binding is currently broken/incomplete. The Wayback/Common Crawl
archive was the correct and successful route-around.
