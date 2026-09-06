# MANIFEST — infra-wave / archive-retry (agent-L3-archive, 2026-09-02)

Lead #95057. Sanitized durable artifacts from the corrective archive-retry lane.
Excluded from durable storage: raw archived HTML bodies (they carry per-session
`csrf-token` and Cloudflare Turnstile nonces); only stable selectors, verbatim
legal/marketing prose, CDX index rows, and raw-body SHA-256 provenance are kept.
`pk_live_...` and google-api-key values are public client-side keys, retained
deliberately as selectors.

## SHA-256 of durable artifacts

| file | sha256 |
|---|---|
| commoncrawl-index-serviuos-monsterlab.json | `af7de580beb22f28e0240c1dfa54b8ab43b84268bcf186c856aab689bc4f9de6` |
| fetch-provenance.json | `0e444ef52c660c4984dd06fbd8d91cbbab33eb700ef00ce4b02faa308e73fa9c` |
| live-tls-characterization.md | `4e4baae6a95db89fa9ee9e3323839334444198709fab055a620e6e4a29728afa` |
| monsterlab-domain-index-uncollapsed.json | `61f58b8856123d6255ab38154b339b754da8486383a51b47cf4a62d355e5721c` |
| monsterlab-legal-terms-privacy.md | `ff02da5888a3207d70c537bc7e091eb7f54a1ff45ef237ee395b32ccfbdd92a1` |
| serviuos-clipit-mentorship-recovery.md | `8f87b57ca27be8dad9e68b411d83c681b30d98d1a5f03c17dea2ca7797403965` |
| serviuos-domain-index.json | `934092a18212b05dae5aa49553a05a3911d7c3b5f9bf874d096b0d794d5ec8a0` |

## Raw-body provenance (fetched bytes; bodies not stored durably)

See `fetch-provenance.json` for the SHA-256 of each fetched raw body (Wayback `id_`
replay), keyed by capture URL + timestamp + HTTP status.
