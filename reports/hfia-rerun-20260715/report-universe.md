# HFIA Post-Act Universe — 2026-07-15

Build timestamp: `2026-07-15T06:03:52+00:00`

## Methodology

The likely-foreign-private-issuer screening universe was reconstructed from SEC quarterly `form.idx` files for 2025-01-01 through 2026-07-15. An issuer enters the universe when a 6-K, 20-F, or 40-F (including amendments normalized to the root form) appears in that interval. This is the HFIA investigation's screening heuristic, not a legal conclusion about issuer status.

For every screened issuer, the builder read the issuer submissions JSON plus every overlapping submissions-history segment, selected Forms 3/4/5 and amendments filed from 2026-03-18 through 2026-07-15, and parsed the raw `ownershipDocument` XML. Amendments remain separate filings. Multi-owner XML filings are expanded to one `filings` row per reporting owner while `transactions` are stored once per accession.

## Endpoint probes

- Full-index probe: `https://www.sec.gov/Archives/edgar/full-index/2026/QTR1/form.idx` parsed 369,651 filing rows.
- Issuer-stream probe: `https://data.sec.gov/submissions/CIK0001611746.json` exposed SciSparc ownership filings in the issuer submissions stream.
- XML smoke test: `0001213900-26-030644` is the 2026-03-18 SciSparc Form 3 for Weiss Amitay; raw ownership XML parsed successfully from `https://www.sec.gov/Archives/edgar/data/1611746/000121390026030644/ownership.xml`. The accession prefix is `0001213900`.

## Row counts

- Likely-FPI issuers: **1,389**
- Issuers with at least one post-Act ownership filing: **865**
- Unique ownership accessions: **11,685**
- Filing-owner rows: **11,718**
- Reporting owners: **7,340**
- Parsed transaction rows: **9,515**
- Forms: 3=7,183, 3/A=239, 4=4,232, 4/A=61, 5=3
- Cross-issuer reporting-owner clusters: **241**
- Same-day multi-issuer synchronization batches: **726**
- Form 3 filing-owner rows more than 30 days after the Act with pre-Act FPI history: **839**
- Likely-FPI issuers with zero post-Act Section 16 filings: **524**
- Form 4 / financing-window matches: **1,221**
- SEC network requests: **11,910**; cache hits: **1,244**; retries: **0**

<!-- WEISS_GATE_AUDIT_START -->
## Weiss nine-issuer gate audit — resolved

The in-universe Amitay Weiss cluster contains **four issuer CIKs**, below the superseded eight-issuer gate. A separate live audit pulled all nine resolved issuer submissions JSON feeds with the required user agent and parsed every candidate post-Act ownership XML after validating its issuer CIK. The audit made 92 network requests with zero retries. **The four-issuer result is not a parser or coverage bug.**

| Resolved issuer | In FPI screen | Any post-Act Section 16 | Weiss post-Act | Per-issuer evidence |
|---|---:|---:|---:|---|
| SciSparc Ltd. (`0001611746`) | yes | 19 | 2 | [Weiss filing(s) confirmed: `0001213900-26-030644`, `0001213900-26-077342`](https://data.sec.gov/submissions/CIK0001611746.json) |
| N2OFF, Inc. / Save Foods, Inc. (`0001789192`) | no | 2 | 0 | [2 issuer Section 16 filings, none by Weiss: `0000897069-26-000730`, `0000897069-26-000736`](https://data.sec.gov/submissions/CIK0001789192.json) |
| Nexera Technologies Ltd / Jeffs' Brands Ltd (`0001885408`) | yes | 18 | 2 | [Weiss filing(s) confirmed: `0001213900-26-031244`, `0001213900-26-053307`](https://data.sec.gov/submissions/CIK0001885408.json) |
| Maris Tech Ltd. (`0001872964`) | yes | 11 | 1 | [Weiss filing(s) confirmed: `0001213900-26-030812`](https://data.sec.gov/submissions/CIK0001872964.json) |
| ParaZero Technologies Ltd. (`0001916241`) | yes | 10 | 1 | [Weiss filing(s) confirmed: `0001213900-26-029463`](https://data.sec.gov/submissions/CIK0001916241.json) |
| Viewbix Inc. (`0000797542`) | no | 6 | 1 | [Weiss filing(s) confirmed: `0001493152-26-014649`](https://data.sec.gov/submissions/CIK0000797542.json) |
| Clearmind Medicine Inc. (`0001892500`) | yes | 5 | 0 | [5 issuer Section 16 filings, none by Weiss: `0001475597-26-000079`, `0001475597-26-000080`, `0001475597-26-000082`, `0001475597-26-000091`, `0001475597-26-000092`](https://data.sec.gov/submissions/CIK0001892500.json) |
| Gix Internet Ltd. (`0001782265`) | no | 0 | 0 | [No post-Act Form 3/4/5 or amendment for this issuer in the live submissions feed](https://data.sec.gov/submissions/CIK0001782265.json) |
| Rail Vision Ltd. (`0001743905`) | yes | 12 | 0 | [12 issuer Section 16 filings, none by Weiss: `0001493152-26-010723`, `0001493152-26-010724`, `0001493152-26-010725`, `0001493152-26-010726`, `0001493152-26-010727`, `0001493152-26-010728`, `0001493152-26-010729`, `0001493152-26-010730`, `0001493152-26-010731`, `0001493152-26-010732`, `0001493152-26-010733`, `0001493152-26-026872`](https://data.sec.gov/submissions/CIK0001743905.json) |

**What the gap means.** Viewbix supplies the fifth observed post-Act Weiss issuer, but it does not enter the defined likely-FPI universe because no qualifying 6-K/20-F/40-F appears in the screening window. N2OFF, Clearmind Medicine, and Rail Vision each have post-Act Section 16 filings by other reporting owners but none by Weiss. Gix Internet has no post-Act Section 16 filing at all in its live issuer feed and is also outside the likely-FPI screen. These are genuine EDGAR filing states, not parser omissions; the absence of a Weiss filing alone does not distinguish a role change, the absence of a reportable event, or noncompliance. Gix and the three no-Weiss issuers require direct role/appointment and issuer-status evidence before any compliance conclusion.

`never_filers.csv` retains its 524 original in-universe zero-filer rows and appends nine rows with `record_type=weiss_gate_audit`. Those typed rows preserve the per-issuer submissions URL, complete matching accession list, Weiss accession list, FPI-scope flag, and XML issuer-CIK validation result without misrepresenting the audit exceptions as ordinary universe never-filers.
<!-- WEISS_GATE_AUDIT_END -->

## Top 20 cross-issuer clusters

### 1. HRT FINANCIAL LP — 17 issuers

CIK `0001475597`; roles: 10% Owner; Form 3/4/5 counts: 30/72/0. Chairman flag: 0; director flag: 0.
Issuers: Meiwu Technology Co Ltd [0001787803]; Lion Group Holding Ltd [0001806524]; Vision Marine Technologies Inc. [0001813783]; Ridgetech Inc. [0001856084]; Clearmind Medicine Inc. [0001892500]; Hub Cyber Security Ltd. [0001905660]; GMEX Robotics Corp [0001928581]; WORK Medical Technology Group LTD [0001929783]; Rubico Inc. [0001943421]; CL Workshop Group Ltd [0001948294]; Decent Holding Inc. [0001958133]; Linkers Industries Ltd [0001972074]; NewGenIvf Group Ltd [0001981662]; YY Group Holding Ltd. [0001985337]; INLIF Ltd [0001991592]; 707 Cayman Holdings Ltd. [0002018222]; Fitness Champs Holdings Ltd [0002023796]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 2. Yang Conor Chia-hung — 5 issuers

CIK `0002121924`; roles: CHIEF FINANCIAL OFFICER; Director; Form 3/4/5 counts: 5/0/0. Chairman flag: 0; director flag: 1.
Issuers: iQIYI, Inc. [0001722608]; UP Fintech Holding Ltd [0001756699]; EHang Holdings Ltd [0001759783]; NovaBridge Biosciences [0001778016]; Smart Share Global Ltd [0001834253]. The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation.

### 3. Adler Oz — 4 issuers

CIK `0001973096`; roles: CEO and CFO; Director; Form 3/4/5 counts: 6/1/0. Chairman flag: 0; director flag: 1.
Issuers: SciSparc Ltd. [0001611746]; Rail Vision Ltd. [0001743905]; Nexera Technologies Ltd [0001885408]; Polyrizon Ltd. [0001893645]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 4. BLIDNER JEFFREY M — 4 issuers

CIK `0001245162`; roles: Director; Form 3/4/5 counts: 4/1/0. Chairman flag: 0; director flag: 1.
Issuers: Brookfield Infrastructure Partners L.P. [0001406234]; Brookfield Renewable Partners L.P. [0001533232]; Brookfield Property Partners L.P. [0001545772]; Brookfield Business Corp [0001654795]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 5. Pittas Aristeidis J — 4 issuers

CIK `0002121849`; roles: Chief Executive Officer; Director; Form 3/4/5 counts: 4/0/0. Chairman flag: 0; director flag: 1.
Issuers: EUROSEAS LTD. [0001341170]; Pyxis Tankers Inc. [0001640043]; EuroDry Ltd. [0001731388]; Euroholdings Ltd. [0002032779]. The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation.

### 6. Weiss Amitay — 4 issuers

CIK `0001826620`; roles: Director; Form 3/4/5 counts: 6/0/0. Chairman flag: 0; director flag: 1.
Issuers: SciSparc Ltd. [0001611746]; Maris Tech Ltd. [0001872964]; Nexera Technologies Ltd [0001885408]; ParaZero Technologies Ltd. [0001916241]. The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation.

### 7. Elsztain Alejandro Gustavo — 3 issuers

CIK `0002119764`; roles: Director; Form 3/4/5 counts: 3/5/0. Chairman flag: 0; director flag: 1.
Issuers: IRSA INVESTMENTS & REPRESENTATIONS INC [0000933267]; CRESUD INC [0001034957]; BrasilAgro - Brazilian Agricultural Real Estate Co [0001499849]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 8. Shao Sean — 3 issuers

CIK `0001432657`; roles: Director; Form 3/4/5 counts: 2/4/0. Chairman flag: 0; director flag: 1.
Issuers: UTSTARCOM HOLDINGS CORP. [0001030471]; VNET Group, Inc. [0001508475]; Luckin Coffee Inc. [0001767582]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 9. ELSZTAIN EDUARDO S — 3 issuers

CIK `0001037182`; roles: 10% Owner; Director; Form 3/4/5 counts: 3/3/0. Chairman flag: 0; director flag: 1.
Issuers: IRSA INVESTMENTS & REPRESENTATIONS INC [0000933267]; CRESUD INC [0001034957]; BrasilAgro - Brazilian Agricultural Real Estate Co [0001499849]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 10. Lai Jimmy Y. — 3 issuers

CIK `0001975788`; roles: Director; Form 3/4/5 counts: 2/3/0. Chairman flag: 0; director flag: 1.
Issuers: 51Talk Online Education Group [0001659494]; FinVolution Group [0001691445]; Youdao, Inc. [0001781753]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 11. Falk Dan Michael — 3 issuers

CIK `0001966097`; roles: Director; Form 3/4/5 counts: 3/2/0. Chairman flag: 0; director flag: 1.
Issuers: NICE Ltd. [0001003935]; Evogene Ltd. [0001574565]; Innoviz Technologies Ltd. [0001835654]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 12. Panagiotidis Petros Panagiotis — 3 issuers

CIK `0002118775`; roles: Chief Executive Officer; Director; See Remarks; Form 3/4/5 counts: 3/2/0. Chairman flag: 0; director flag: 1.
Issuers: Castor Maritime Inc. [0001720161]; TORO CORP. [0001941131]; Robin Energy Ltd. [0002039060]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 13. Vafias Harry — 3 issuers

CIK `0001328921`; roles: CEO and President; CEO, President & CFO; Director; Form 3/4/5 counts: 3/2/0. Chairman flag: 0; director flag: 1.
Issuers: StealthGas Inc. [0001328919]; Imperial Petroleum Inc./Marshall Islands [0001876581]; C3is Inc. [0001951067]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 14. Zheng Yeeli Hua — 3 issuers

CIK `0002123010`; roles: Director; Form 3/4/5 counts: 3/2/0. Chairman flag: 0; director flag: 1.
Issuers: Bitfufu Inc. [0001921158]; MaxsMaking Inc. [0002008007]; Youlife Group Inc. [0002028177]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 15. Gaivironsky Matias Ivan — 3 issuers

CIK `0002120697`; roles: CFO; Chief Financial Officer; Director; Form 3/4/5 counts: 4/1/0. Chairman flag: 0; director flag: 1.
Issuers: IRSA INVESTMENTS & REPRESENTATIONS INC [0000933267]; CRESUD INC [0001034957]; BrasilAgro - Brazilian Agricultural Real Estate Co [0001499849]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 16. Karmiri Stefania — 3 issuers

CIK `0002122338`; roles: Corporate Secretary; Form 3/4/5 counts: 3/1/0. Chairman flag: 0; director flag: 0.
Issuers: EUROSEAS LTD. [0001341170]; EuroDry Ltd. [0001731388]; Euroholdings Ltd. [0002032779]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 17. Revach Moshe — 3 issuers

CIK `0001973293`; roles: Director; Form 3/4/5 counts: 5/1/0. Chairman flag: 0; director flag: 1.
Issuers: SciSparc Ltd. [0001611746]; Nexera Technologies Ltd [0001885408]; ParaZero Technologies Ltd. [0001916241]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 18. Zang Saul — 3 issuers

CIK `0001836939`; roles: Director; Form 3/4/5 counts: 3/1/0. Chairman flag: 0; director flag: 1.
Issuers: IRSA INVESTMENTS & REPRESENTATIONS INC [0000933267]; CRESUD INC [0001034957]; BrasilAgro - Brazilian Agricultural Real Estate Co [0001499849]. This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint.

### 19. Baudo Giampietro — 3 issuers

CIK `0002125501`; roles: Chief Executive Officer; Form 3/4/5 counts: 3/0/0. Chairman flag: 0; director flag: 0.
Issuers: AMTD IDEA GROUP [0001769731]; AMTD Digital Inc. [0001809691]; Generation Essentials Group [0002053456]. The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation.

### 20. Bevilacqua Flavia Vanesa — 3 issuers

CIK `0002131749`; roles: not specified; Form 3/4/5 counts: 3/0/0. Chairman flag: 0; director flag: 0.
Issuers: GAS TRANSPORTER OF THE SOUTH INC [0000931427]; EDENOR [0001395213]; Pampa Energy Inc. [0001469395]. The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation.

## Late-filer and never-filer patterns

Late Form 3 rows are concentrated among these filing-agent prefixes: 0001213900 (225), 0001493152 (125), 0001104659 (72), 0001193125 (68), 0000905148 (39). This is a timing screen only: the Act date is used as a common reference point, and the issuer's pre-Act 20-F/6-K history is only a proxy that the disclosed director/officer population already existed.

Of 524 zero-filer issuers, 176 had F-1/F-3/424B activity in 2025-2026. Leading reported countries/territories are British Columbia, Canada (83), Ontario, Canada (69), China (39), Cayman Islands (34), Unknown (32). `never_filers.csv` ranks financing intensity, because EDGAR submissions do not supply market capitalization; the `small_cap_proxy` field must not be read as measured market cap.

## Ten highest-value escalation candidates

1. **UBS AG** (AMUB, BDCX, BDCZ, CEFD, HDLB, IFED, IWDL, IWFL, IWML, MLPB, MLPR, MTUL, MVRL, PFFL, QULL, SCDL, SMHB, UCIB, USML), CIK `0001114446` — score 92907. 18578 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
2. **BARCLAYS BANK PLC** (ATMP, BWVTF, DJP, GBUG, GRN, JJETF, TAPR, VXX, VXZ), CIK `0000312070` — score 66295. 13254 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
3. **BANK OF MONTREAL /CAN/** (BMO, FNGD, AIQD, AIQU, BERZ, BNKD, BNKU, BULZ, CARD, CARU, DULL, FLYD, FLYU, FNGO, FNGS, FNGU, GDXD, GDXU, JETD, JETU, NRGD, NRGU, OILD, OILU, SHNY, WTID, WTIU), CIK `0000927971` — score 33906. 6777 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
4. **ROYAL BANK OF CANADA** (RY, RYLBF), CIK `0001000275` — score 26330. 5261 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
5. **BANK OF NOVA SCOTIA** (BNS), CIK `0000009631` — score 23960. 4787 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
6. **TORONTO DOMINION BANK** (TD, TDBCP), CIK `0000947263` — score 23331. 4662 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
7. **CANADIAN IMPERIAL BANK OF COMMERCE /CAN/** (CM, CNDIF), CIK `0001045520` — score 5791. 1154 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
8. **DEUTSCHE BANK AKTIENGESELLSCHAFT** (DB, ADZCF, DEENF, DGP, DGZ, DZZ, OLOXF), CIK `0001159508` — score 3810. 757 2025-26 financing/resale filing(s); zero Section 16 filings despite likely-FPI evidence.
9. **TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD** (TSM), CIK `0001046179` — score 685. 135 post-Act Form 4 filing(s); 1 cross-issuer insider(s); 3 ownership amendment(s).
10. **SOPHiA GENETICS SA** (SOPH), CIK `0001840706` — score 605. 115 Form 4/financing-window match(es); 99 post-Act Form 4 filing(s); 11 2025-26 financing/resale filing(s); 9 ownership amendment(s).

The ranking operationalizes the profile doctrine: financing-window Form 4 matches receive the most weight, followed by repeated post-Act changes, cross-issuer insiders, resale/registration activity, and amendments. It is a commissioning screen, not an allegation or finding of misconduct.

## Data-quality caveats

- `6-K`/`20-F`/`40-F` history is a likely-FPI heuristic. Publication candidates require direct status confirmation.
- SEC full indexes for the current quarter ordinarily run through the previous business day. The builder applies an inclusive end-date filter but cannot include filings absent from the downloaded index at run time.
- Submission history is deduplicated by accession across recent and overlapping historical JSON segments.
- The filing table's natural key is `(accession, owner_cik)` because a single ownership document can identify more than one reporting owner. Unique accession counts are reported separately.
- Form 3 holdings are not transactions and therefore are not inserted into `transactions`; Form 4/5 non-derivative and derivative transaction rows are included.
- Country is taken from the SEC submission business/mailing address (or incorporation code fallback), so it is not a normalized legal domicile field.
- An accession's first ten digits are a useful filing-agent/cohort fingerprint but do not by themselves identify counsel, a service provider, or coordinated conduct.
- Form 3 'late' status here means more than 30 days after 2026-03-18, not a legal timeliness determination. Appointment dates and individual statutory deadlines were not independently established.
- Financing-intensity ranking is not a substitute for market capitalization. Small-cap status should be added from a dated market-data source before publication.
- Names are preserved as filed. Owner CIK is the cluster key; spelling variants without a common CIK are not automatically merged.

## Index manifest

- 2025-QTR1: 340,030 rows, 6,898 qualifying form rows, 53,045,137 bytes — `https://www.sec.gov/Archives/edgar/full-index/2025/QTR1/form.idx`
- 2025-QTR2: 331,631 rows, 7,963 qualifying form rows, 51,734,892 bytes — `https://www.sec.gov/Archives/edgar/full-index/2025/QTR2/form.idx`
- 2025-QTR3: 287,254 rows, 7,047 qualifying form rows, 44,812,085 bytes — `https://www.sec.gov/Archives/edgar/full-index/2025/QTR3/form.idx`
- 2025-QTR4: 276,226 rows, 7,282 qualifying form rows, 43,091,716 bytes — `https://www.sec.gov/Archives/edgar/full-index/2025/QTR4/form.idx`
- 2026-QTR1: 369,651 rows, 7,426 qualifying form rows, 57,666,013 bytes — `https://www.sec.gov/Archives/edgar/full-index/2026/QTR1/form.idx`
- 2026-QTR2: 352,588 rows, 8,247 qualifying form rows, 55,004,184 bytes — `https://www.sec.gov/Archives/edgar/full-index/2026/QTR2/form.idx`
- 2026-QTR3: 39,769 rows, 885 qualifying form rows, 6,204,420 bytes — `https://www.sec.gov/Archives/edgar/full-index/2026/QTR3/form.idx`
