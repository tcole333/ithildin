# Public resource recovery — sanitized evidence, wave two

Collector: agent:manual-cloud-artifacts. Public, unauthenticated HTTP capture on 2026-09-02. These are source-content observations, not proof that any political account used the described tools. Raw viewer HTML remains workdir-only; credentials, dummy credential examples, executable scripts, signed media URLs, order/banking identifiers and incidental user identifiers are excluded here. No executable or APK was downloaded, no account was used, and no community was joined.

## Disclosed iPhone guide

Source: https://docs.google.com/document/d/e/2PACX-1vSyPi_ylZllIulu5BAzcf16CpaLdpiM1Wdfs1PoKXyb8geQbK3HHWabvpNAZpmbjuaysBU9AmZokwlG/pub

Discovery: linked by the public **Proxy Setup Guide**, itself linked from @ogserviuos video `4xcM01EYbHs`; wave-one finding 15417.

- Actual published document title: `Proxy Setup For iPhone`.
- HTTP 200 at 2026-09-02T16:30:22.900355Z; 162,130 bytes; raw SHA-256 `66a64ea8f7f28310c9e4a6188aa941a95fdff3e8b2e8b8398bd0b468d6c48109`.
- Raw workdir file: `/tmp/osint-ldT6picn/a-iphone-guide.html`.
- The `#contents` body contains 460 whitespace-delimited words, not merely a Google viewer shell. It describes Shadowrocket and refers to `p.monsterlab.io`. A warning discourages iPhone use for TikTok CRP because of possible location leakage, then gives this exact advice: `However, it is safe to use for ClipIt.` This is the publisher's advice, not this investigation's assurance.
- No author, uploader email or publication date was visible. No embedded images or outbound document links were present in the content body.

## Disclosed cloud-phone guide

Source: https://docs.google.com/document/d/e/2PACX-1vSiVolBLzZ94AvMcdlBPn7VBDwzAcLscsEcKPox95QKGbGH39GeO8AIIfAv8ndlCbYcbJP7a_0lAX0k/pub

Discovery: same first-party guide chain as above.

- Actual published document title: `Cloud Phone Guide`.
- HTTP 200 at 2026-09-02T16:30:24.952277Z; 185,311 bytes; raw SHA-256 `b93ebf9eda36d6922f45fb69b53973cb4b2d7a6a0afde37122191268aafb1c1e`.
- Raw workdir file: `/tmp/osint-ldT6picn/a-cloudphone-guide.html`.
- The `#contents` body contains 709 whitespace-delimited words, not merely a Google viewer shell. It describes virtual Android devices and geography presentation for social platforms. Exact content phrase: `platforms like TikTok, Instagram, and YouTube recognize you as being in the United States`.
- Public outbound links: `https://duoplus.saaslink.net/G5rvNw` (label `Cloud Phone Provider Link`) and `https://discord.com/channels/1238662138864599172/1306098059662458940` (label `proxy ticket`). The first is a disclosed service referral, not a verified merchant identity; the second discloses a channel in the already-resolved ClipIt guild. Neither a purchase nor community access was attempted.
- References `p.monsterlab.io`; no visible author, uploader email, publication date, or embedded image.

Both complete document bodies were checked case-insensitively for `Elephant`, `Enclave`, `Wynn`, `Jules`, `Goodman`, `O’Hara`, `US Politics`, and `campaign`; each returned zero. This does not rule out political use elsewhere. The iPhone guide mentions ClipIt once; the cloud-phone body does not name ClipIt, although its support-channel URL belongs to the same published guild. Detailed configuration steps and credential-shaped examples are not reproduced.

## Free course shortlink — shell, not recovered course

Source: https://cutt.ly/clipitcourse

Discovery: public descriptions of @ogserviuos videos including `9rnwUsUSCos`, `Qa1FoIMKFNY` and `wozS5wpIdPw` label it `Free Clipping Course`.

At 2026-09-02T16:30:25.620236Z the chain was HTTP 301 to `https://whop.com/clipit/free-clip-it-course-BGXr0jrsEJ6k37/app/`, then HTTP 307 to `https://whop.com/clipit/exp_BGXr0jrsEJ6k37/app/`, then HTTP 200. The page title is `ClipIt | Whop`, but visible page text says: `Experience not found, Redirecting to Forums experience in 5s.` No course lessons were recovered. HTTP 200 is not proof of content availability.

Raw file `/tmp/osint-ldT6picn/a-clipitcourse.html`; 985,989 bytes; SHA-256 `f4fe62e0ca4b73acc3e88674f35100a1d35141df2c27faaf9d526d4d1ffb0148`. No authenticated app session or automatic forum access was initiated.

## Editors' videos shortlink — unavailable folder

Source: https://cutt.ly/brPe8z72

Discovery: @ogserviuos video `Qa1FoIMKFNY` labels it `Videos My Editors Made`.

At 2026-09-02T16:30:26.677741Z the shortlink returned HTTP 301 to `https://drive.google.com/drive/folders/1OoBdneUe1FDg4x3U51R_NAekykBg6UoE?usp=sharing`; Google returned HTTP 404 and the exact message `The requested URL was not found on this server.` No folder title or content was recovered. This is current unavailability, not proof of deletion or concealment.

Raw file `/tmp/osint-ldT6picn/a-brPe8z72.html`; 1,652 bytes; SHA-256 `eb58241d29dc08fe669038efb667d83a00954db66850cbcc72b90439467efe13`.

## 24-hour challenge shortlink — live public tutorial library

Source: https://cutt.ly/mrg0EboV

Discovery: the public description of @ogserviuos video `wozS5wpIdPw` says the link provides the ten videos from its challenge and screen recordings of how they were edited. The description contains ordinary Whop Content Rewards/clipping context, not the political campaign brief.

At 2026-09-02T16:30:27.043798Z the link returned HTTP 301 to `https://drive.google.com/drive/folders/1gkKBLN5aLI2GDohDTCKxk8BU-JaKf9qV?usp=sharing`; the folder returned HTTP 200, title `10 Clipping Videos (24hr challenge) - Google Drive`.

- Raw file `/tmp/osint-ldT6picn/a-mrg0EboV.html`; 308,094 bytes; SHA-256 `2f798fbc02c5386c02310324f29df28f844fe00ba6f044ae71d5fc7c55af20c5`.
- The real public listing contains two subfolders (each displayed as modified Apr 20, 2025): `10 Videos` (`1NA6J-fflQ1vHNfsZnF-Fsi3UjxcYpNdL`) and `How I Edited Them (full recording)` (`1KL61dbJi6cCqc8qmGI92ihUrZ7hmKo2X`).
- Their public listings returned HTTP 200 at 2026-09-02T16:32:18.135638Z and 2026-09-02T16:32:18.716837Z respectively. The first lists ten MP4s named `VIDPODCASTSERV1.mp4` through `VIDPODCASTSERV10.mp4`, modified March 9–10, 2025. The second lists five MP4s named `1.mp4` through `5.mp4`, modified March 9, 2025.
- Raw files `/tmp/osint-ldT6picn/a-ten-videos.html` (391,792 bytes; SHA-256 `82c500ac8f7ee64e97b10c857d67055641cca098de47c4c38942c85c6904e999`) and `/tmp/osint-ldT6picn/a-editing-recordings.html` (340,260 bytes; SHA-256 `3720a0a20a1d9e5ee6f9814638b53ab9e24f5757eb73cea5f4f9961527f12d7c`).

The sanitized item inventory preserves each public file ID, displayed filename, size and modification date. The listings, not the full videos, have been recovered; filenames alone cannot establish their subjects or campaign use. Drive modification dates are not publication or authorship dates. No political campaign row, ledger, account-to-campaign mapping, or authenticated payout is established by these tutorial surfaces.

## Bounded sample viewer metadata and previews

Two of the fifteen listed files were sampled through public viewer pages and thumbnails, without downloading full videos or identifying people from faces:

1. `https://drive.google.com/file/d/1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE/view`: title `VIDPODCASTSERV1.mp4`; serialized `docs-doddn` value `Serviuos` and business email `biz@serviuos.com`. HTTP 200 at 2026-09-02T16:36:07.464214Z; raw file `/tmp/osint-ldT6picn/a-sample-edited-video.html`; 76,749 bytes; SHA-256 `e0c0951d8bbeaa9502156213385b7509ca1f19e62c33691715bdf711faebf63c`.
2. `https://drive.google.com/file/d/16fF8nXrPg82zOznE7riJ5nJwhacKv5XU/view`: title `1.mp4`; same display value `Serviuos` and business email `biz@serviuos.com`. HTTP 200 at 2026-09-02T16:36:07.810718Z; raw file `/tmp/osint-ldT6picn/a-sample-recording.html`; 76,858 bytes; SHA-256 `cfa8db703616660567e682e6e076f0c5fbacd4e2e1d4b355b8f1c1a62170e0de`.

Public preview source for sample 1: `https://drive.google.com/thumbnail?id=1GKwLAdk3qXsyDs9UVfEHwO5aKmM7IFcE&sz=w1000`; HTTP 200 image/jpeg, captured 2026-09-02T16:39:01.011595Z. Workdir `/tmp/osint-ldT6picn/a-thumbnail-edited.jpg`; 215,784 bytes; SHA-256 `98b77b9846133d77c52e64c95ec99fc7b46cb094347d6bfa0dceb9aaf006a3ce`. It shows a vertical microphone/podcast shot with the caption `Poker`. No political campaign title or brief is visible in this preview.

Public preview source for sample 2: `https://drive.google.com/thumbnail?id=16fF8nXrPg82zOznE7riJ5nJwhacKv5XU&sz=w1000`; HTTP 200 image/jpeg, captured 2026-09-02T16:39:01.835350Z. Workdir `/tmp/osint-ldT6picn/a-thumbnail-recording.jpg`; 86,540 bytes; SHA-256 `b9343b92aa68c7f5ebd39206841ec49b6886bb7c5d6a01cae6cd246dfec29950`. It shows `Adobe Premiere Pro 2025`, `BANDICAM`, and project label `VideoRawf_1`; no political campaign identifier or brief is visible. The image includes an incidental local user path, which is neither transcribed nor duplicated in the durable tree.

These two previews are consistent with a podcast-clipping/editing tutorial sample. They do not identify the subjects, prove commercial sponsorship, rule out political material elsewhere in the fifteen-file collection, or authenticate the content of unreviewed video frames. The uploader metadata corroborates the public Serviuos business persona, not a civil or legal identity.
