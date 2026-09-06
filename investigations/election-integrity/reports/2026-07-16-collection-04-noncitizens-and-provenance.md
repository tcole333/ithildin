# WH Election Integrity Release (2026-07-16): Collection 4 Review + Cross-Cutting Provenance Sweep

Reviewer scope: (A) full document review of collection "4. Noncitizens on State Voter Rolls" (2 PDFs, 12pp); (B) provenance/anomaly sweep across all four collections (58 PDFs, 269pp).
Base path: `/Users/travcole/projects/osint-research/datasets/wh_election_integrity/`
Conventions: "document states" = text verbatim in the released file; "page claims" = text on the saved whitehouse.gov/election-integrity/ page (`provenance/election-integrity-page-20260716.html`). Quotes are exact, including typos, marked [sic] where load-bearing.

---

## A. Collection 4 — "Noncitizens on State Voter Rolls"

Zip: `Noncitizens-on-State-Voter-Rolls.zip` (565,400 bytes; server last-modified Thu, 16 Jul 2026 22:36:04 GMT — the LAST of the four uploads). Internal folder: `4. Noncitizens on State Voter Rolls/`. Two PDFs. **Neither document carries any declassification or release-approval stamp** (verified by stamp grep across all 58 OCR sidecars and by visual read). Nothing in this collection is a previously-classified record.

### A.1 Document 1: `Alien Voter Registration Summary.pdf_Redacted.pdf` (1 page)

File: `extracted/04-noncitizen-voter-rolls/Alien Voter Registration Summary.pdf_Redacted.pdf` (138,867 bytes; sha256 in `provenance/manifest.json`; no PDF producer/creator/date metadata — stripped or scanner-blank per `provenance/pdf_inventory.json`).

**Physical description (visual read of the PDF):**
- Letterhead: DHS seal + "Homeland Security" wordmark. No component (not USCIS, not CISA, not I&A), no address block.
- Header banner: "PREVENTING ALIEN VOTING".
- **No date on the document itself** (only an internal "As of June 22, 2026" statistic), **no author, no signature block, no POC, no classification or FOUO markings visible**.
- **One redaction**: a single black bar, bottom-center of the page below the final paragraph — position consistent with a footer marking or POC line. Unlabeled (no exemption code).
- Filename `…Summary.pdf_Redacted.pdf` is Adobe Acrobat's default redaction-tool output naming (Acrobat appends `_Redacted` to the source filename; the source already ended in `.pdf`, producing the double extension).
- A table titled "Proactive SAVE User States" with columns State / Deceased / Non-Citizen (transcribed below).
- Typo in the body: "10 have states processed" [sic] — present in the embedded text layer and the rendered page; the document was not carefully proofread.

**Operative passages (exact):**

1. Methodology track 1 (the 250,000 figure):
> "NATIONAL SECURITY INVESTIGATIONS: The Department of Homeland Security has initiated multiple investigations related to allegations of non-citizen voting and registration. Review of the first set of public voter files from states that have not utilized the SAVE system revealed:
> OVER 250,000 NON-CITIZENS ARE ILLEGALLY REGISTERED TO VOTE IN JUST THE FOUR STATES FOR WHICH PUBLIC DATA FILES HAVE BEEN REVIEWED."

2. The four states, notification, expansion, and the DOJ file channel:
> "State election officials in California, Pennsylvania, New Jersey and Nevada have been notified of this serious threat to national security and DHS stands ready to support their efforts to identify and remove ineligible registrants. The investigation is expanding to include multiple additional states. In addition, DHS will support the Department of Justice’s review of voter files obtained pursuant to their enforcement authority under the National Voter Registration Act of 1993 and the Help America Vote Act of 2002."

3. Methodology track 2 (the SAVE figures):
> "In the short time that the enhanced SAVE system has been available to states, 10 have states processed their full voter lists. As of June 22, 2026, a total of 25 different states processed more than 68 million registration records through the SAVE system. DHS has enabled those states to identify over 400,000 deceased registrants and over 28,000 non-citizens who illegally registered to vote."

4. The only "voted" language in the document (capability framing, no count):
> "Numerous proactive, conscientious state officials have successfully utilized free services offered by the Department of Homeland Security to assist election officials in identifying non-citizens who have registered and/or voted in their states."

5. The litigation paragraph:
> "Several other proactive state officials have also signed Memoranda of Agreement with USCIS to utilize the SAVE system and have processed portions of their state voter rolls. Unfortunately, due to the actions of the activist Judge Sparkle Sooknanan, many of the enhancements to this service of USCIS have been suspended pending appeal. As a result, US citizens are at risk of having their votes diluted by ineligible alien voters."

6. The closing (overtly political register):
> "UNAMBIGUOUS CONTRAST: There is an undeniable pattern emerging as DHS begins to unravel the horrific damage done by the open border policies of the Biden administration. States that have adopted alien-first policies instead of American-first policies have a disproportionate number of non-citizens on their voter rolls."

**"Proactive SAVE User States" table (transcribed from the rendered page):**

| State | Deceased | Non-Citizen |
|---|---|---|
| Georgia | 42,776 | 2,549 |
| Ohio | 59,774 | 769 |
| Tennessee | 37,850 | 1,009 |
| Texas | 111,573 | 2,296 |
| North Carolina | 34,622 | 1,599 |
| Idaho | 4,328 | 49 |
| Alabama | 33,165 | 465 |
| Missouri | 10,660 | 1,112 |
| Louisiana | 15,231 | 419 |
| Kansas | 10,197 | 449 |
| **Sum (10 listed states)** | **360,176** | **10,716** |

The listed 10 states account for 360,176 of the claimed "over 400,000" deceased and 10,716 of the claimed "over 28,000" non-citizens; the remainder is implicitly attributed to the other 15 of the "25 different states," unitemized.

**What the methodology section does and does not say:**
- Matched against what: **not stated** for the 250,000 figure. The document says only "Review of the first set of public voter files" — it never names the reference database (USCIS/SAVE records? CBP entry data? visa records?), the match keys (name/DOB/address?), the match-confidence standard, or any de-duplication step. Note that the *public* voter files of CA/PA/NJ/NV generally do not include SSN or full DOB in all fields, which makes any citizenship match on them identifier-poor by construction. The 28,000 figure, by contrast, is attributed to states running their own rolls through the (enhanced) SAVE system under MOAs with USCIS.
- States covered vs excluded: covered by track 1 = California, Pennsylvania, New Jersey, Nevada ("the FOUR STATES FOR WHICH PUBLIC DATA FILES HAVE BEEN REVIEWED"); covered by track 2 = 25 states that processed records through SAVE, of which 10 processed full lists (the table). Excluded = everyone else; the document says the investigation "is expanding to include multiple additional states." **The document never says any state refused anything** (see A.3).
- False-positive risk / naturalization: **entirely unaddressed**. Zero occurrences of "naturaliz*" in the entire 58-document corpus (grep across `text/*/`). No error rate, no "possible match" vs "confirmed" distinction, no handling of naturalization dates, no mention of the known history of such matches collapsing (TX 2019, FL 2012, VA). The document does not acknowledge that history in any form.
- Timeframe: the only date anchor is "As of June 22, 2026" for the SAVE statistics. No date for the four-state review, no registration-date window.
- "Registered" meaning: present tense — "ARE ILLEGALLY REGISTERED TO VOTE" — implying current registrants, but the document never distinguishes active vs inactive status or says when the registrations were made.
- Voting claim: **the document does not claim the 250,000 (or 278,000) voted.** The only voted-language is the "registered and/or voted" capability sentence about SAVE-using states (quote 4), which carries no number.
- Authorship: no individual or office is identified. Language register ("activist Judge," "horrific damage done by the open border policies of the Biden administration," "alien-first policies instead of American-first policies") is campaign/political rather than career-agency fact-sheet style. Characterization: a DHS-branded, unsigned, undated one-page political summary with one redaction; not a declassified record and bearing no release stamp.

**Internal rate inconsistency worth flagging (document's own numbers):** the four-state public-file review implies roughly 250,000 non-citizens among ~40M registrants in CA/PA/NJ/NV (~0.6%), while the SAVE track implies 28,000 among 68M records processed (~0.04%). The document's two methodologies differ by a factor of ~15 in flag rate. Either non-SAVE states are dramatically worse, or the unexplained public-file matching method flags at a far looser standard than SAVE status verification. The document offers no reconciliation; it instead attributes the contrast to "alien-first policies" (quote 6).

### A.2 Document 2: `Voter Registration Database Threats - FINAL.pdf` (11 pages)

File: `extracted/04-noncitizen-voter-rolls/Voter Registration Database Threats - FINAL.pdf` (496,082 bytes).

**Provenance-critical metadata** (`provenance/pdf_inventory.json`): Producer/Creator "Microsoft® Word for Microsoft 365"; **created Wed Jun 24 13:41:52 2026 EDT; modified Mon Jul 13 17:55:00 2026 EDT**. This is a **newly written document** — drafted in Word ~3 weeks before publication, finalized 3 days before — not a declassified record. It carries no declass/release stamp. Filename suffix "- FINAL" is a working-draft convention, consistent with the also-new `CISA Election Report - FINAL.pdf` and `WHTF ... Statement FINAL.pdf`.

**Physical description:** cover page with a dark U.S.-map graphic, **both the DHS seal and CISA seal**, title "Recognizing and Addressing Threats to Statewide Voter Registration Databases," dateline "July, 2026". No author, no signature, no component office named anywhere. Ten numbered pages + cover. References page with 14 footnotes.

**Self-description (exact):**
> "This product provides an unclassified overview of the threats to statewide voter registration databases from both foreign and domestic actors. It relies on reporting from the intelligence community, law enforcement, and state election officials. This report is intended to inform state and local election officials of the associated threats and the need to implement recommended mitigating controls."

**Tie-in to the release (exact, opening line of the executive summary):**
> "Recently declassified records revealed that China breached multiple state voter registration systems prior to the 2020 election."

**Headline claim exceeding the established public record (exact):**
> "Hackers have attempted to breach voter registration systems in all 50 states, with confirmed successes in at least 20 states."

The "all 50 states" targeting claim matches the 2019 Senate Intelligence Committee findings (which the doc cites at fn 6), but "**confirmed successes in at least 20 states**" has no public-record precedent (2016-cycle confirmed intrusions were Illinois plus a small number of others; SSCI vol. 1 described access in "a small number of states"). The sentence's footnote 1 resolves to the **Mueller report** PDF (`https://www.justice.gov/archives/sco/file/1080281/dl?inline`), which does not support a 20-state confirmed-success count. The same Mueller URL is reused for footnotes 1, 2, 4, and 5. The doc separately includes: "In January 2017, WH officials reported that the federal assessment was that networks in at least seven states were compromised" (fn 7 = the NBC "U.S. intel: Russia compromised seven states" story, which DHS publicly disputed at the time; the doc does not note the dispute).

**Content map:** history of VRDB incidents 2016-2023 (Russia 2016 items from Mueller/SSCI; Riverside County CA party-affiliation changes; Illinois/Arizona 2016; Kennesaw State 2017; Iran 2020 via CISA AA20-304a; PRC scanning 2022; a 2023 New Hampshire vendor anecdote — "The software had been configured to connect to servers in Russia, and a programmer had hard-coded the Ukrainian national anthem into the database"); exploitation scenarios (mass absentee-ballot requests, registration alteration/deletion — "Data obtained in a breach from 2021, for example, could be used to request a ballot for an election in 2028 because the data does not get stale."); CISA-style hygiene checklists (MFA, DMARC, DDoS, ransomware, backups); a "DATA BREACHES GENERALLY" section citing Equifax 2017 (unnamed, "a credit reporting firm... 143 million"), the Feb 10 2020 DOJ PLA indictment with the William Barr quote, an April 2024 background-check-firm breach ("2.9 billion records containing PII of 170 million individuals... offered for $3.5 million" — matches National Public Data), a June 2025 insurer breach ("22.65 million individuals" — matches the Aflac disclosure), and "A report from the University of Oxford" ranking Russia and China first and third for cybercrime threat (the World Cybercrime Index). All 14 references are public/unclassified sources (Mueller report, SSCI, CISA advisories, DHS memo, DoD CSA, media stories).

**Fit-to-collection anomaly:** this document contains **nothing about noncitizens** — no noncitizen registration content at all. It is a voter-registration-database cybersecurity overview placed in the "Noncitizens on State Voter Rolls" collection, presumably because the DHS one-pager alone would have made a 1-page collection. Its natural home is collection 1 or 2 (its subject matter is the China/VRDB-breach story).

### A.3 Page claims vs. document contents

Page pillar 4 (exact, rendered text):
> "According to a D.H.S. review of state voter rolls and public records, they identified approximately 278,000 non-citizens who are registered to vote in federal elections. Since Democrat states refused to share their voter files, the real number is actually much higher—yet even this limited analysis found more than a quarter of a million foreigners illegally registered to vote."

And the page's summary paragraph:
> "…hundreds of thousands of non-citizens and dead people are listed and active on the voter rolls—and yet, we still have elections with no Voter I.D., no Proof of Citizenship, and tens of millions of ballots floating aimlessly through the mail."

Findings:
1. **The 278,000 is arithmetically the sum of two methodologically different buckets in the DHS one-pager: "OVER 250,000" (four-state public-file review, method undescribed) + "over 28,000" (SAVE status checks run by 25 states on their own rolls).** 250,000 + 28,000 = 278,000. The page merges them into a single "D.H.S. review of state voter rolls and public records" — collapsing a state-initiated SAVE verification stream into a DHS "review," and treating an unexplained matching exercise and an immigration-status verification system as one analysis.
2. **"Democrat states refused to share their voter files" is documented nowhere in the release.** Zero grep hits for "refus*" across all 58 OCR sidecars. The DHS document says the opposite dynamic for the four states: their **public** voter files were obtained and reviewed precisely because they "have not utilized the SAVE system," and those four (CA, PA, NJ, NV) are the Democrat-leaning states. The only file-access mechanism mentioned is prospective: DOJ obtaining files under NVRA/HAVA enforcement authority. If any refusal occurred (e.g., in response to 2025-2026 DOJ voter-file demand letters), it is exogenous to this release.
3. **"registered to vote in federal elections"** (page) — the document says "registered to vote" on state rolls; it never uses "federal elections" for the 250k/28k figures.
4. **"the real number is actually much higher"** (page) — no such extrapolation appears in the document; the document says only that the investigation "is expanding."
5. **Neither page nor documents claim these people voted.** The page stops at "registered"; the document's only "voted" is the un-numbered capability sentence. The page's "listed and active on the voter rolls" adds "active," which the document does not say; and its "hundreds of thousands" merges the 400,000-deceased figure with the noncitizen figures.
6. The page describes collection 1 as "previously-classified U.S. Intelligence Community Assessments and other reports" and the release as declassified intelligence — **collection 4 contains no declassified or previously-classified material at all** (one unsigned DHS one-pager; one June/July 2026 Word document).

### A.4 Named entities (collection 4)

- Department of Homeland Security (letterhead, both docs); USCIS (SAVE MOAs); CISA (seal on doc 2; toolkit URL `www.cisa.gov/cybersecurity-toolkit-and-resources-protect-elections`); Department of Justice (NVRA/HAVA review role; 2020 PLA indictment).
- **Judge Sparkle Sooknanan** (called "the activist Judge"; U.S. District Judge, D.D.C.) — enjoined "many of the enhancements" to the SAVE service, "suspended pending appeal."
- States: California, Pennsylvania, New Jersey, Nevada (four-state review); Georgia, Ohio, Tennessee, Texas, North Carolina, Idaho, Alabama, Missouri, Louisiana, Kansas (SAVE table).
- Statutes: National Voter Registration Act of 1993; Help America Vote Act of 2002.
- Attorney General William Barr (quoted in doc 2 re: 2020 PLA indictment); China's People's Liberation Army; Kennesaw State University; Riverside County (CA) District Attorney; University of Oxford (cybercrime index); unnamed: Equifax ("a credit reporting firm"), National Public Data ("a background check firm"), Aflac ("One of the largest supplemental insurance providers"), IRGC ("Iranian Republic Guard Corp" [sic]).

### A.5 Verification leads

1. **Reconstruct the 250k methodology against the TX-2019 failure template.** Texas SOS's Jan 2019 advisory flagged ~95,000 registrants as possible noncitizens (~58,000 "voted") by matching DMV records lacking naturalization updates; within weeks ~25,000+ were confirmed naturalized citizens, the list collapsed, litigation settled, the SOS resigned. FL 2012 (180,000 → 2,600 → ~85) and VA's "Alien Invasion" reports failed the same way. The DHS one-pager reproduces the precondition (status snapshot without naturalization-date reconciliation) and does not name its reference database. FOIA/press-query DHS for: reference DB, match keys, match-confidence tiers, naturalization-date handling for the four-state review.
2. **Identify the Sooknanan case and what "enhancements" were enjoined.** Pull D.D.C. dockets (CourtListener) for 2025-2026 orders by Judge Sparkle Sooknanan against USCIS/DHS re: the SAVE system (plausibly the SSN-based bulk-matching expansion announced by USCIS in 2025). The injunction's scope defines which of the two DHS tracks (bulk matching vs. per-record status checks) produced which number, and the opinion likely contains the government's own description of the methodology the one-pager omits.
3. **Test the four-state notification claim.** Public-records requests to the CA, PA, NJ, NV secretaries of state / election directors for the DHS notification correspondence (the document says they "have been notified"). Whether DHS transmitted record-level lists, counts only, or a letter — and the states' technical responses — directly tests the 250,000.
4. **Denominator sanity check + the 15x internal rate gap.** ~40M registrants across CA/PA/NJ/NV → 250k ≈ 0.6% flagged, vs. SAVE-processed 28k/68M ≈ 0.04%. Also compare the table's per-state rates (e.g., TX 2,296 noncitizens over ~18M registrants ≈ 0.013%) with academic/litigation baselines (Brennan Center audits; GA's 2022 citizenship audit found ~1,600 non-verified over 20 years, nearly all never voted). The two orders-of-magnitude spread inside one document is the single strongest methodological tell.
5. **Trace whether "refused" refers to the 2025-2026 DOJ voter-file demand campaign.** DOJ (Civil Rights Division) sent voter-file requests/demands to numerous states in 2025-2026 under NVRA/HAVA; several Democratic-led states publicly declined full statewide-file production. If the page's "refused" sentence imports that dispute, the page is attributing a DOJ-vs-states conflict to the DHS review — checkable against DOJ press releases (`datasets/government_releases.db` per repo tooling) and state AG statements.
6. (Bonus, doc 2) **"Confirmed successes in at least 20 states"** — press ODNI/CISA for the basis; no public source supports 20 confirmed VRDB breaches, and the cited source (Mueller report) does not contain it.

---

## B. Cross-cutting provenance and anomaly findings (whole release)

### B.1 PDF metadata patterns (`provenance/pdf_inventory.json`)

- **50 of 58 PDFs carry no producer, no creator, and no creation/modification dates** — consistent with scan-and-redact pipeline output that strips or never writes XMP/Info. The exceptions are the tells:
- **Documents authored or assembled in 2026 (metadata-dated):**
  - `01/.../CISA Election Report - FINAL.pdf` — Producer "Adobe PDF Library 26.1.187", Creator "Acrobat PDFMaker 26 for Word", **created Mon Jul 13 18:14:12 2026, modified Thu Jul 16 12:14:24 2026 EDT** — a Word-authored 2026 report (CISA "ELECTION REPORT" branding, footer "As of July 13, 2026"), modified at 12:14 PM on publication day (see B.5: the modification is an Adobe Acrobat re-save on the publishing Mac). Content confirms 2026 authorship: "The intent of this report is to draw from CISA's assessments in the 2019-2025 timeframe", "concluded in 2025", and footnote 3: "Dominion Voting Systems Democracy Suite Preliminary Vulnerability Assessment, **Mojave Research for the ODNI, September 25, 2025**" (a previously unknown third-party Dominion assessment commissioned by ODNI — its own verification lead).
  - `04/.../Voter Registration Database Threats - FINAL.pdf` — Word 365, created Jun 24 2026, modified Jul 13 2026 (Section A.2).
  - `01/.../CIA Note - Venezuela Machines Intel Memo_29JUNE2026_DECLASS_REDACTED.pdf` — created Tue Jul 14 14:00:59 2026 (redaction-export date). The memo itself is **content-dated 29 June 2026** and stamped "Deciassified [sic, OCR] by D/CIA Ratcliffe on 1 July 2026" plus "APPROVED FOR PUBLIC RELEASE BY COUNSEL TO THE PRESIDENT WARRINGTON on 10 July 2026" — i.e., a CIA note written ~17 days before publication and declassified 2 days after it was written. Precisely characterized: current-intelligence product created for/near this release, not a legacy 2020 record (the page presents it as documents showing "the CIA obtained reporting of a specific plot by the Maduro regime").
  - `01+02/.../CIA Wire Memo Summer 2020 DECLASS(_)REDACTED.pdf` — created Jul 14 13:53:48, modified 13:55:23 2026 (both collection copies byte-identical; only scanned-legacy doc with a creation timestamp = its redaction export).
- **The iText 2.1.7 file** is `02-china-voter-data/FBI_ALBANY_IIR_PROVIDED_TO_CHAIRMAN GRASSLEY .pdf` (note trailing space in filename), Producer "iText 2.1.7 by 1T3XT", **modified Tue Jul 1 10:32:23 2025 EDT — a full year before this release**. iText 2.1.7 (2009 vintage) is the engine embedded in government FOIA/e-discovery redaction suites. The page images carry Bates numbers **FBI-SJC-IIR-000001 through -000006** ("SJC" = Senate Judiciary Committee) — this exact PDF is the FBI Albany IIR production made for Chairman Grassley in mid-2025 (matching Grassley's July 2025 public release of the Albany IIR), recycled into this collection unmodified. It is the only document in the release that predates the July 2026 processing wave. Content note: the IIR itself states "INFORMATION REPORT, NOT FINALLY EVALUATED INTELLIGENCE", sources it to "collaborative source with indirect access whose reporting has been corroborated for less than one year" via a sub-source citing "unidentified PRC government officials", and warns "Receiving agencies are requested not to take action based on this raw reporting" — caveats not reflected in the page's framing of the China pillar.
- Filename sloppiness cluster (manual handling): `NICM_VulnerabilitiesInUS2020ElectionInfrastructure_15JAN2020_DECLASS_REDACTEDed.pdf` ("REDACTEDed"), two filenames with a space before `.pdf`, `PRC Analsyis` [sic], `Orginal Muskego` [sic] (page spells it "Muskeegon"; the actual city is Muskegon).

### B.2 Upload sequence, HTTP layer, and page state

**Zip last-modified (from `provenance/*.headers.txt`), all Thu 16 Jul 2026, GMT → EDT:**

| Upload order | Zip | last-modified GMT | EDT | Page display position |
|---|---|---|---|---|
| 1 | Chinas-Acquisition-...-Voter-Data.zip | 22:15:26 | 6:15:26 PM | #2 |
| 2 | Michigan-Voter-Registration-Investigation.zip | 22:19:09 | 6:19:09 PM | #3 |
| 3 | Vulnerabilities-in-Electronic-Voting-....zip | 22:26:48 | 6:26:48 PM | #1 |
| 4 | Noncitizens-on-State-Voter-Rolls.zip | 22:36:04 | 6:36:04 PM | #4 |

21-minute upload window on publication evening; upload order (2,3,1,4) differs from display order. Combined with zip-internal folder mtimes (B.5): the China and Michigan zips were built ~12:21-12:26 PM and uploaded ~6 hours later; the Vulnerabilities and Noncitizens zips were (re)built at 6:26 PM **mid-upload-session** — Vulnerabilities was uploaded within ~60 seconds of being zipped; Noncitizens (the smallest collection) went up last, 10 minutes after its re-zip. Hosting: nginx, `x-rq: jfk1`, `x-cache: HIT`, `cache-control: max-age=31536000`, short-hex etags (`e21aeaefbbdc5b63` etc.), served from WordPress paths `wp-content/uploads/2026/07/`. Our capture ran 02:32 GMT Jul 17 = 10:32 PM EDT Jul 16, ~4h post-upload. The page's own pillar-1 text says "**Tonight**, we are releasing all of these findings" — confirming same-evening publication.

**Rush-publication indicators in the page** (`election-integrity-page-20260716.html`) — precise rendering status:
- **Rendered (user-visible):** every document card reads "`ZIP · —`" — an em-dash where the template's size/page-count metadata belongs (the in-source example shows the intended format). Also rendered: each section is labeled with a literal "§" (`<span class="num">§</span>`) and the literal word "Pillar" — template section markers never replaced with numbers/titles.
- **Source-only (inside HTML comments, not rendered):** per-pillar scaffold "To add more documents, copy this row and edit:" with the placeholder card "Your document title / Short description. / PDF · 12 pp"; and in the video section "To embed a YouTube video, replace the empty <div class="aspect"></div> contents below with:" — where the instruction comment already contains the very video ID that is live below it. These are leftover developer scaffolding visible to anyone viewing source.
- **"From the President" section:** heading "President Trump Address", live YouTube embed `https://www.youtube.com/embed/iIlqG0untYM`, iframe title "A statement from the President on election integrity".
- **Mailing-list framing:** "Get the next update." / "New findings, new filings, and next steps in the effort to secure our elections — delivered to your inbox as they land." — an explicit promise of further releases (consistent with the WHTF statement's "first disclosure" language, B.3). The form POSTs to Mailchimp: `whitehouse.us10.list-manage.com/subscribe/post?u=255057cc391ca0facb169b81c&id=004f59aa22&f_id=0024c6e5f0`. The sitewide footer form uses `wdg.us10.list-manage.com` with the **same account (u=255057cc391ca0facb169b81c) and same list (id=004f59aa22)**, different f_id — i.e., the "election integrity updates" signup feeds the general WH newsletter list; "wdg" is the Mailchimp domain alias of the site's web vendor (consistent with WDG, the DC WordPress agency).
- Page-level claim inconsistencies: pillar 2 says China acquired "**220 million** U.S. voter files"; the WHTF statement in collection 2 says "**more than 200 million** voter records"; the zip's own headline document is titled "**200M** Voter Records Compromised". Pillar 3 spells the city "Muskeegon" while the FBI filename says "Muskego" (actual: Muskegon). Section ids: `voting-systems`, `foreign-data`, `registration-fraud`, `noncitizen-rolls`.

### B.3 OCR-corpus tells: stamps, authorities, banners, anachronisms

**Release-stamp taxonomy** (grep of first stamp line across all 58 sidecars in `text/*/`; complete mapping verified):

| Stamp (exact) | Applied to |
|---|---|
| "DECLASSIFIED BY PRESIDENT TRUMP on 3 July 2026" | IC analytic products & IC emails: NICA 19AUG2020 (both copies), NICM 16OCT2020, EMAIL "Everyone's favorite topic" 23DEC2021 (both copies), EMAIL_NSA.MassagedPDB 20NOV/23NOV2020, EMAIL "RE Please coord by COB 9.1" 03SEP2020 |
| "DECLASSIFIED BY COUNSEL TO THE PRESIDENT WARRINGTON ON 10 July 2026" | CIA Wire Memo Summer 2020 (both copies), EMAIL_ICA.CommentsReMinorityView 30DEC2020, EMAIL "RE For IC coord" 7OCT2020, 200M Voter Records, 18 States Memo, Note - Sensitive PRC Reporting, Summary PARTs 1-3, US Voter Registration for 6 States |
| "APPROVED FOR PUBLIC RELEASE BY COUNSEL TO THE PRESIDENT WARRINGTON on 10 July 2026" | All 25 Michigan FBI files, the Albany briefing handout (Tasking_3), and the CIA Venezuela note (which additionally bears "Declassified by D/CIA Ratcliffe on 1 July 2026") |
| No stamp of any kind | Both collection-4 documents, CISA Election Report - FINAL, WHTF statement, FBI Albany IIR (2025 SJC production), plus thin-OCR scans where stamps exist visually but OCR missed them (PDB 25JUN2020, PRC series, NICM 15JAN2020, Michigan `0000001`) |

Reading: a three-step chain — D/CIA (Jul 1) → President (Jul 3) → WH Counsel Warrington (Jul 10, acting both as declassifier and public-release approver), matching the WHTF statement's description that the task force advises the President "through the Counsel to the President." Two nonstandard features worth noting factually: (i) "DECLASSIFIED BY COUNSEL TO THE PRESIDENT" is not a conventional authority line (declassification under EO 13526 runs through the President and original classification authorities; no EO citation, case number, or declass office appears anywhere); (ii) the original "Classified By: / Derived From: / Declassify On:" blocks visible in several docs are blank or redacted in OCR (e.g., `01/.../NICA...txt` line 58, `01/.../EMAIL_Everyone's favorite topic...txt` lines 15-17).

**Filename convention → processing pipeline mapping:** `DECLASS_REDACTED`/`DECLASS REDACTED` = IC docs with red declass stamps (Trump or Warrington); `- clean - declass marked_Redacted` = the China PRC series — Adobe Acrobat redaction output (`_Redacted`) + "declass marked", and these are the docs carrying the SENSITIVE GOVERNMENT AGENCY banner overlay (below); `RELEASE MARKED` = FBI investigative files (Michigan + Albany handout) stamped "APPROVED FOR PUBLIC RELEASE" — these were never classified (their readable banners are UNCLASSIFIED//FOUO variants), so they are release-marked rather than declassified; `.pdf_Redacted.pdf` = one-off Acrobat redaction (the DHS one-pager); `- FINAL` = newly authored 2026 Word/CISA/WHTF documents. At least three distinct upstream pipelines feed the release: an IC declass/redact line, a WH-counsel release-marking line for FBI files, and a recycled 2025 congressional production (iText/Bates).

**Classification banners: physically overwritten.** Visual reads of `02/.../200M Voter Records Compromised...pdf` (pp.1-2) and `02/.../18 States Memo...pdf` (p.1) show the original header/footer banner areas covered by black boxes bearing red text "**SENSITIVE GOVERNMENT AGENCY**", with red Warrington declass stamps above/below, and paragraph-level portion marks redacted. Consequence: **no TOP SECRET/SECRET/SI/NOFORN banner text survives anywhere in the release** (grep for NOFORN, //SI, ORCON, HCS, FISA, REL TO across all sidecars = zero hits); the only readable banners corpus-wide are UNCLASSIFIED//FOUO variants on the FBI Michigan files (OCR-garbled as "FOvO", "FO8O", "EQUO", etc.). The originating agency name and the prior classification level of the marquee China documents are therefore unverifiable from the release itself.

**Anachronism scan (2025/2026 dates inside purportedly 2020-2023 documents):** after excluding the declass/release stamps themselves, **no 2025 or 2026 date appears in the body text of any document dated 2020-2023**. All in-body 2025/2026 dates sit in the six documents that are genuinely 2025/2026 artifacts (CISA report, VRDB Threats, Alien Summary, WHTF statement, Venezuela note, FBI Albany IIR's 2025 file-metadata). Caveat: five documents remain effectively image-only after OCR (`0000001`, `PRC Analsyis...`, `PRC Target 2024...`, `PRC US Voter Data 7 States...`, `Tasking_3 AlbanyBriefingHandout`), so body-text screening is incomplete for those.

**Content-vs-title tension (flag, not a finding of fabrication):** the visible (unredacted) text of "200M Voter Records Compromised" describes a PRC-possessed list of leaked datasets "primarily dated from between 2009 and 2018" with "97 entries that were explicitly identified as originating from U.S. […] entities" and "several characterized as voter registration records" — the "200M" of the WH-assigned filename does not appear in any unredacted passage of the doc's first two pages; the figure is carried by the WHTF statement ("more than 200 million") and the page ("220 million"). Most of the document is redacted, so the number may sit under the boxes — but as released, the title asserts more than the visible text shows.

**WHTF file:** `02/.../WHTF Government Transparency - States Statement FINAL.pdf` = **White House Task Force "Government Transparency"** letterhead + circular seal ("WHITE HOUSE TASK FORCE · GOVERNMENT TRANSPARENCY"), dated July 13, 2026. Document states: created May 2026 "within the White House Executive Office of the President for the purpose of advising him, through the Counsel to the President, on documents that should be declassified and/or released"; "Today the Government Transparency Task Force announces the **first disclosure** of U.S. Intelligence Community records that were declassified last week under the direction of President Trump"; claims voter rolls "from at least 18 states (not all identified by name)" were compromised by the PRC and lists **16** jurisdictions by name (AK, AR, CO, CT, DC, FL, GA, IA, KS, MD, MI, NY, NC, OH, OK, RI — DC being a non-state). "First disclosure" + the page's mailing-list copy = an announced series.

### B.4 Cross-collection duplicates (byte-identical, sha256 from `provenance/manifest.json`)

| sha256 (prefix) | Collection 01 filename | Collection 02 filename | Size |
|---|---|---|---|
| `1be94e7fa86a…` | CIA Wire Memo Summer 2020 DECLASS REDACTED.pdf | CIA Wire Memo Summer 2020 DECLASS_REDACTED.pdf | 522,629 |
| `6e22be494ee8…` | NICA_ Foreign Threats to 2020 US election_19AUG2020 - DECLASS_REDACTED.pdf | NICA Foreign Threats To 2020 US Election_19AUG2020 DECLASS_REDACTED.pdf | 1,857,619 |
| `efa073c1baba…` | EMAIL_Everyone's favorite topic_23DEC2021_DECLASS_REDACTED.pdf | EMAIL_Everyone's favorite topic 23DEC2021 - DECLASS_REDACTED.pdf | 196,369 |

58 zip entries → 55 unique files. Implications: (i) the collections are **thematic marketing buckets assembled by manually copying from a common document pool** — each copy was independently (and inconsistently) renamed (underscores vs. spaces vs. dashes), which is hand-work, not scripted export; (ii) page/document totals double-count 11 pages; (iii) the same document is offered under two editorial framings (the NICA supports both the "machines vulnerable" pillar and the "China data" pillar). The "Everyone's favorite topic" email (an ODNI National Intelligence Officer for Cyber complaining that a post-2020 report re-attributed to "the Chinese military" activity the IC had declined to attribute in 2020 — "That's a weird coincidence, and one we should highlight for oversight") is the connective document the curators evidently considered probative for both narratives.

### B.5 macOS assembly artifacts — the strongest provenance chain in the release

The four zips are Finder-made ("Compress" → `__MACOSX/._*` AppleDouble sidecars for every entry, UTF-8 entry names with curly apostrophe; the `ΓÇÖ` in our manifest and `???` in unzip listings are cp437-decode artifacts of our tools, not the source). The AppleDouble files preserve **`com.apple.quarantine` extended attributes**, which record the application that placed each file on the staging Mac and a Unix timestamp. Decoded (all 2026-07-16 EDT):

- **Chrome, in four sequential clusters matching display order** — 12:02:35 (collection 1 folder + files), 12:02:57 (collection 2), 12:03:05 (collection 3), 12:03:13 (collection 4). The quarantine attribute sits on the **collection folders themselves** as well as the files: the four pre-assembled, pre-named folders (including their internal file mtimes of Jul 12-15, the redaction-batch window: Michigan batch Jul 15 11:09-11:32, China "declass marked" batch Jul 15 12:29-12:30, etc.) were **downloaded via Chrome as archives and expanded** on the publishing Mac in a 38-second span around 12:02-12:03 PM — i.e., four sequential link-clicks from a browser source (webmail/file-share). The documents were curated elsewhere; this Mac only packaged and published.
- **AdobeAcrobat @ 12:14:24** — `CISA Election Report - FINAL.pdf` only. Matches the PDF's internal modified timestamp (Thu Jul 16 12:14:24) to the second, and its AppleDouble carries FinderInfo type/creator `PDF CARO` (classic Acrobat signature): the CISA report was **opened and re-saved in Adobe Acrobat on the publishing Mac 11 minutes after download**, on publication day. What changed in that save is not recoverable from the release.
- **Mattermost @ 12:25:47** — `WHTF Government Transparency - States Statement FINAL.pdf` only. The task-force statement was **received via Mattermost** (self-hosted team-chat platform — an operational detail about the publishing team's internal tooling), `com.apple.lastuseddate#PS` shows it was opened at 12:26:19, and the China folder (its destination) was zipped that same minute (folder mtime 12:26). It was the last-arriving document.
- `com.apple.lastuseddate#PS` on `NICM_VulnerabilitiesInUS2020ElectionInfrastructure...pdf` = **18:08:01** — someone re-opened this document at 6:08 PM, between the midday packaging and the evening upload of its (re-zipped 18:26) collection.
- **.DS_Store**: present inside the Michigan zip (mtime 12:21) and Noncitizens zip (mtime 18:26) only. Both parsed: fresh Finder view-state stubs (Bud1/DSDB allocator; the Michigan one holds a single `dscl` bool record). **No usernames, no home-directory paths, no window-bookmark blobs** — no operator identity leaks. The quarantine UUIDs (e.g., `774B0A10-E952-4C24-AA35-34E99A1E8D8C` on the Alien Summary) index the downloader's local QuarantineEventsV2 database and are not resolvable to URLs from outside.

### B.6 Assembly timeline synthesis (all times EDT, Jul 2026; each point evidenced above)

| When | Event | Evidence |
|---|---|---|
| Jul 1 2025 | FBI Albany IIR produced for Senate Judiciary (Grassley) | iText 2.1.7 modified date; FBI-SJC-IIR Bates |
| Jun 24 | "Voter Registration Database Threats" drafted in Word | PDF created date |
| Jul 1 | D/CIA Ratcliffe declassifies the Jun 29 Venezuela note | in-document stamp |
| Jul 3 | Presidential declass wave (IC analytic docs) | "DECLASSIFIED BY PRESIDENT TRUMP" stamps |
| Jul 10 | WH Counsel Warrington declass + public-release wave | Warrington stamps |
| Jul 12-15 | Redaction/export batches (file mtimes inside zips; CIA Wire Memo re-export Jul 14 13:53) | zip entry mtimes, pdf metadata |
| Jul 13 | WHTF statement dated; CISA report exported from Word (18:14) | doc dateline; pdf created |
| Jul 16 12:02:35-12:03:13 | Four pre-built collection folders downloaded via Chrome onto publishing Mac, display order | quarantine xattrs |
| 12:14:24 | CISA report re-saved in Adobe Acrobat | quarantine + pdf modified |
| 12:21-12:26 | Michigan, then China folders zipped; WHTF statement arrives via Mattermost 12:25:47 and is included | folder/.DS_Store mtimes, quarantine |
| 18:08 | NICM 15JAN2020 re-opened (final review) | lastuseddate xattr |
| 18:15:26 / 18:19:09 | China, Michigan zips uploaded | HTTP last-modified |
| 18:26 | Vulnerabilities + Noncitizens folders re-zipped mid-session | folder mtimes; Vulnerabilities uploaded 18:26:48 |
| 18:36:04 | Noncitizens zip uploaded (last) | HTTP last-modified |
| Evening | Page live ("Tonight, we are releasing…"); template metadata ("ZIP · —", "§ Pillar") never filled | page text |
| 22:32 | Our capture | header `date:` |

### B.7 Consolidated anomaly list (one line each, with pointer)

1. Two of the release's 58 documents are 2026 Word-authored products presented inside a "declassified records" release; a third (CIA Venezuela note) was written 29 Jun 2026 and declassified 2 days later (B.1).
2. The collection titled "Noncitizens on State Voter Rolls" contains zero declassified records and one document with zero noncitizen content (A.2).
3. Page's 278,000 = sum of two incommensurable buckets (250k unexplained public-file match + 28k SAVE checks); "Democrat states refused" appears nowhere in the release; the 250k came from Democrat-led states' public files (A.3).
4. Declassification authority lines are nonstandard ("DECLASSIFIED BY COUNSEL TO THE PRESIDENT"); no EO 13526 citation anywhere; original classification blocks blank/redacted (B.3).
5. Original classification banners are physically overlaid with red "SENSITIVE GOVERNMENT AGENCY" boxes — prior classification level and originating agency of the marquee China docs are unverifiable from the release (B.3).
6. Release figures for the same claim: 200M (zip/doc title), "more than 200 million" (WHTF), 220 million (page pillar 2) (B.2/B.3).
7. Three byte-identical documents cross-filed between collections 1 and 2 with inconsistent manual renames; 58 entries = 55 unique files (B.4).
8. FBI Albany IIR is a recycled July 2025 Senate Judiciary production (iText 2.1.7, FBI-SJC Bates), the only pre-2026 processing artifact; the IIR's own "not finally evaluated / do not act on this" caveats are absent from the page framing (B.1).
9. Quarantine xattrs reconstruct the publishing workflow: folders arrived via Chrome 12:02-12:03 PM on publication day; CISA report re-saved in Acrobat 12:14; WHTF statement delivered via Mattermost 12:25; two zips re-made mid-upload at 6:26 PM (B.5/B.6).
10. Rendered template residue ("ZIP · —", literal "§"/"Pillar" markers) + commented scaffolding ("Your document title", "PDF · 12 pp", "contents below with:") mark a rushed, hand-edited single-page build; the "next update" mailing list feeds the general WH Mailchimp list (u=255057cc391ca0facb169b81c, id=004f59aa22) (B.2).
11. No 2025/2026 anachronisms found inside any 2020-2023-dated document body (OCR-limited for 5 image-only files) — the release's internal dating is consistent; the newness sits in the 2026-authored additions, not in doctored legacy text (B.3).
