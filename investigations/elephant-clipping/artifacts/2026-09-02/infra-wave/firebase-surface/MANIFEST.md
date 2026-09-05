# MANIFEST — Firebase / client-surface infra wave (Lane 1)

Investigation: elephant-clipping. Agent: agent-L1-firebase. Lead: #95053.
Skill: investigate-infra. Captured: 2026-09-02 (UTC). Target: monsterlab.io /
Firebase project monsterlab-3496 (build id oT3om4jzC9FhrymKHBqql).

All artifacts are derived from public, unauthenticated first-party assets or
from unauthenticated access-posture probes. SANITIZED: no session tokens, FIDs,
signed/expiring URLs, cookies, bearer tokens, or third-party PII are stored. The
Firebase apiKey/appId/measurementId are recorded because they are public client config.

## Provenance of probe/raw files
- raw/_buildManifest.js — GET https://monsterlab.io/_next/static/oT3om4jzC9FhrymKHBqql/_buildManifest.js (200)
- raw/webconfig-endpoint-response.json — GET firebase.googleapis.com/v1alpha/projects/-/apps/<appId>/webConfig (200; public appId+apiKey only)
- raw/api-endpoints.txt, raw/firestore-collections.txt — grep-derived inventories over 240 public JS chunks
- raw/probe-firestore-campaigns-*.json — GET firestore.googleapis.com/v1/projects/monsterlab-3496/databases/(default)/documents/socialMediaCampaigns?pageSize=1 (403)
- raw/probe-storage-firebasestorage-o-*.json — GET firebasestorage.googleapis.com/v0/b/monsterlab-3496.appspot.com/o/results%2Fresult-1.png[?alt=media] (403)
- raw/probe-storage-gcs-object.xml — GET storage.googleapis.com/monsterlab-3496.appspot.com/results/result-1.png (403)
- raw/probe-api-campaigns-public-bare.txt — GET https://monsterlab.io/api/campaigns/public/ (308)
- raw/probe-api-billing-products.json — GET https://monsterlab.io/api/billing/products (401, unauthenticated)

## SHA-256
```
c8f849f9a216cd994d615e17f68f2f91567f925f2eb6ad5a7d305680faad4ece  brand-gallery-review.md
b749552f53440c825896768c793bc22e43adf4b4d7bb370f9eaa5b8fb401e984  client-surface-schema.md
6ab2006277342a081535c099a0b66ef08a838f8cbc8425cd60b4fd5127ca3b87  firebase-webconfig.json
90550294e70578effe1cb063e9c9ba88e44500c42d07dbe065a74e3e4d595a1f  firestore-storage-probes.md
a911e5415a7ff08a62a133eaaee9985bd836cef82e53afc98f1d35c4f2ac986d  raw/_buildManifest.js
8908aef87bbcfb575d8c3b0010d6849aa7e9e416ff1a78afd4b5c60ed93084ca  raw/api-endpoints.txt
90245c3b31307e553fdd01f53482bb7b0c0088654154d77d3369d3a283e46e32  raw/firestore-collections.txt
7ec5bc51fc593d8932d40207a7cee8e934141178e7781cde5bcb591684d64235  raw/probe-api-billing-products.json
7c040f8633b8823d72ed63da9b3b2dfe9846e912c66a64c9433ec9c4815d76c2  raw/probe-api-campaigns-public-bare.txt
f29760abff154be99cd0bfa76989f2b3a0b004461bd110330ec354431a44f537  raw/probe-firestore-campaigns-no-key.json
f29760abff154be99cd0bfa76989f2b3a0b004461bd110330ec354431a44f537  raw/probe-firestore-campaigns-with-key.json
8cb089d6475d64276d4e54aa50c0296082f88546c0ae4b44797bde6ac541a35e  raw/probe-storage-firebasestorage-o-altmedia.json
8cb089d6475d64276d4e54aa50c0296082f88546c0ae4b44797bde6ac541a35e  raw/probe-storage-firebasestorage-o-metadata.json
509ecad0e23c632a1214d951dc46568617d42a0a3459149f4adccf6d3e9328df  raw/probe-storage-gcs-object.xml
fee0a688d8554ba6bcbf9cede3d7bcc63bc396237c1a4f98611c8c4bd378d93c  raw/webconfig-endpoint-response.json
529c0fa06498b9d09ed8c782f795be6ec437f085f12704d091a7a10372f97ee3  route-data-payloads.md
```
