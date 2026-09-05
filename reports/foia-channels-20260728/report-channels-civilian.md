# FOIA / Records-Request Channel Verification — Civilian Agencies (as of 2026-07-28)

Read-only verification of submission channels. Nothing was submitted. All checks performed 2026-07-28.

---

## 1. CIA FOIA

**Portal status — the 2026-07-15 report is confirmed: `foia.cia.gov` is dead at the DNS level.**
- `dig foia.cia.gov` returns no A or CNAME record; fetch fails with `ENOTFOUND` (checked 2026-07-28). The Wayback Machine availability API returns **zero snapshots** for `foia.cia.gov`.
- CIA's own FOIA regulation, 32 C.F.R. § 1900.03, still cites the dead URL `https://www.foia.cia.gov/foia_request/form` for online filing — the reg text is stale (https://www.law.cornell.edu/cfr/text/32/1900.03).

**Current electronic submission** lives on the CIA Electronic Reading Room, which is up and still branded "CIA FOIA (foia.cia.gov)":
- Site: https://www.cia.gov/readingroom/ — confirmed live via Wayback captures of 2026-07-18 and 2026-07-27; page nav includes "Submit Request" -> `https://www.cia.gov/readingroom/foia_request`.
- FOIA.gov's agency dataset lists CIA's submission web form as `https://www.cia.gov/readingroom/node/256459` (api.foia.gov agency_components record for CIA).
- Caveat: cia.gov aggressively bot-blocks non-browser clients (403s to fetchers; 302 self-redirect loops to curl). Verify the form in a real browser; automated probing is unreliable.

**FOIA.gov National FOIA Portal:** FOIA.gov's live dataset (api.foia.gov) now carries CIA with `portal_submission_format: "email"` — i.e., the portal is configured to transmit portal-created requests to CIA by email. This is a change from March 2023, when the National Security Archive audit flagged CIA as one of the agencies you could NOT reach through FOIA.gov (https://nsarchive.gwu.edu/foia-audit/2023-03-09/key-agencies-missing-central-freedom-information-act-portal). Recommend starting (not submitting) a request at foia.gov to confirm the UI actually offers CIA before relying on it.

**Mailing address (confirmed in both FOIA.gov dataset and 32 C.F.R. § 1900.03):**
> Information and Privacy Coordinator, Central Intelligence Agency, Washington, DC 20505

**Fax:** 703-613-3007 (listed in FOIA.gov dataset and § 1900.03). **FOIA Requester Service Center:** 703-613-1287 (no collect calls). Status page: `https://www.cia.gov/readingroom/request/status`.

**Processing (FY2025 data via FOIA.gov):** simple track median 12 days; complex track median 173 days / average 347.6 days / max 3,069 days; expedited average 516.5 days. Assume multi-year for anything non-trivial.

**Third-party requests about living private individuals (Glomar practice):**
- CIA states on its FOIA site that it will neither confirm nor deny the existence of records on ~10 subjects, including "specific confidential or covert relationships," names/titles/salaries of CIA personnel, and budget/expenditure data (per NARA OGIS, "NCND/Glomar," FOIA Ombuds Observer 2024-01: https://www.archives.gov/ogis/resources/foia-ombuds-observer/2024-01).
- A request about a living private individual will ordinarily draw a Glomar response grounded in FOIA (b)(1)/(b)(3) (CIA Act/National Security Act) plus privacy exemptions. Per OGIS, the showings that avoid or overcome it: (1) a **privacy waiver** signed by the subject; (2) **proof of death** ("such as an obituary or death certificate"); (3) **documented official acknowledgment** by the agency of the same records ("not public speculation or a leak"); or (4) a **public-interest showing** that disclosure "would shed light on agency operations."

**SUBMIT VIA:** Online form on the Electronic Reading Room — https://www.cia.gov/readingroom/node/256459 (nav: Submit Request) — or mail to Information and Privacy Coordinator, Central Intelligence Agency, Washington, DC 20505; fax 703-613-3007. FOIA.gov portal submission (relayed to CIA by email) now appears enabled — confirm in the FOIA.gov UI first. Do NOT use foia.cia.gov (dead hostname).

---

## 2. Department of State FOIA

**foia.state.gov is current** and is State's FOIA hub. New requests go through the **Public Access Link (PAL)**: https://pal.foia.state.gov/app/Home.aspx — register/sign in to submit, track status, and download responsive records. FOIA.gov's dataset lists State with `portal_submission_format: "api"`, so requests created on FOIA.gov flow into State's system as well; State's listed submission page is `foia.state.gov/Request/Submit.aspx`.

**Referencing the existing pending case F-2025-18993:**
- PAL account: status of requests submitted through PAL is visible after sign-in (status link on the PAL home page).
- FOIA Requester Service Center (for status of any case, including F-2025-18993): **phone (202) 261-8484**, **email FOIAStatus@state.gov** — put the case number in the subject line.
- Mail: U.S. Department of State, Information Access Programs Directorate (A/SKS/IAP), 2201 C Street NW, Washington, DC 20520.
- Do not resubmit the request — a new submission gets a new case number; reference the existing F-number in all correspondence.

**SUBMIT VIA:** New requests — https://pal.foia.state.gov (or via FOIA.gov). Status of pending case F-2025-18993 — FOIAStatus@state.gov / (202) 261-8484, citing the case number.

---

## 3. NARA / Donald J. Trump Presidential Library (Presidential Records Act)

**The 5-year PRA window is confirmed open.** "The Trump Presidential Library will accept FOIA requests for records of the 45th Presidential Administration (January 2017 - January 2021) starting January 20, 2026 at 12:00am Eastern Standard Time (EST)" (https://www.trumplibrary.gov/research/submit-foia-request; also FAQ). American Oversight and Freedom of the Press Foundation filed on day one (https://americanoversight.org/american-oversight-seeks-trump-1-0-records-on-first-day-they-become-publicly-available-under-law/; https://freedom.press/the-classifieds/you-can-now-foia-trumps-first-term-records/).

**Submission channels (all NARA, College Park — not the private Miami facility):**
- Online form: https://www.trumplibrary.gov/research/submit-foia-request (attachments up to 5 MB/file)
- Email: **trump.library@nara.gov**
- Mail: Donald J. Trump Presidential Library, c/o FOIA Coordinator, 8601 Adelphi Rd, Room 1900, College Park, MD 20740
- Special requirement: one topic per request ("Requests must be submitted one at a time. We suggest sending FOIA requests in separate emails with your name in the subject line.")

**P1-P6 restrictions — primary-source confirmation that the 12-year categories, including P2 and P5, are in effect and being applied.** NARA's first Trump 45 intent-to-release notice, **PA 2026-099 (July 23, 2026)**, signed by Kathleen Dillon McClure, Director, Archival Operations Division, to White House Counsel David Warrington (https://www.archives.gov/files/foia/pra-notifications/pdf/trump45/rn-pldjt-2026-099.pdf), states the first processed tranche (5,798 pages, 2,934 photographs, 1,045 assets) "has been reviewed for the six PRA Presidential restrictive categories, **including confidential communications requesting or submitting advice (P5) and material related to appointments to federal office (P2)**," and that as a result "503 pages, 241 photographs, and 501 assets in whole and 893 pages and 189 assets in part have been restricted." Release of the non-privileged remainder: 60 working days from the notice = **October 19, 2026**, unless the former or incumbent President takes a one-time 30-working-day extension or asserts constitutionally based privilege (44 U.S.C. § 2208). Note: no separate public instrument in which Trump designated the categories was located; the operative evidence is NARA's review/withholding language and the actual restrictions applied. (Contrast: Obama lifted P2/P5 for his records, per American Oversight.) Trump 45 now appears on NARA's PRA notifications page (https://www.archives.gov/foia/pra-notifications) — only this single letter so far, i.e., processing is in its first tranche.

**Processing caveats:**
- Requests processed in order received; "The FOIA process takes time" (trumplibrary.gov FAQ). FPF reported one of its requests was "36th in line, with an estimated completion date of November" as of ~Feb-Mar 2026 (https://freedom.press/the-classifieds/the-trump-librarys-dm-double-standard/). FPF warns Bush-library precedent suggests some requests could take up to 12 years.
- Quality-control risk: on Feb 17, 2026 the library told the Washington Post it had "no records" of Trump Twitter DMs while the same day confirming to FPF that it holds them — draft requests with multiple phrasings ("sent to or from" vs "related to").
- Institutional risk: **DOJ OLC opinion of April 2, 2026** (52 pp., AAG T. Elliot Gaiser) concludes the PRA is unconstitutional and Trump "need not further comply" (ABC News: https://abcnews.com/US/doj-rejecting-decades-law-trump-presidential-records/story?id=131668575). Its direct target is current-term compliance, and the July 23, 2026 notice shows NARA is still processing first-term FOIA requests under the PRA — but it clouds the regime. Also: NARA budget cuts and archivist-independence concerns (American Oversight; FPF).

**SUBMIT VIA:** Online form at trumplibrary.gov/research/submit-foia-request, or trump.library@nara.gov, or mail c/o FOIA Coordinator, 8601 Adelphi Rd, Room 1900, College Park, MD 20740. One topic per request.

---

## 4. GAO records requests (not FOIA)

**Confirmed: GAO is not subject to FOIA** ("The Government Accountability Office (GAO) is not subject to the Freedom of Information Act (5 USC 552)") but discloses in the spirit of it under **4 C.F.R. Part 81**. Current page: https://www.gao.gov/foia-requests.
- **Channel:** email **RecordsRequest@gao.gov**, directed to the Chief Quality Officer (processed by GAO's Audit Policy and Quality Assurance office). Regulation address: Chief Quality Officer, U.S. GAO, 441 G Street NW, Washington, DC 20548 (4 C.F.R. § 81.4, https://www.law.cornell.edu/cfr/text/4/81.4). GAO OIG records: OIGRecordsRequest@gao.gov.
- Acknowledge/honor within 20 days; expedited processing on compelling need; fees per 4 C.F.R. § 81.7; appeal denials within 60 days to the Comptroller General.
- Not released: records originating outside GAO, ongoing-work records, and congressional-request work product unless the congressional requester authorizes release (§§ 81.5-81.6).

**Bid-protest file materials:**
- **While pending: nothing.** "We do not release documents while a protest is pending" (GAO bid protest FAQ, https://www.gao.gov/legal/bid-protests/faqs). Filings live in EPDS (Electronic Protest Docketing System, mandatory since May 1, 2018) — accessible to parties, not the public.
- **Procurement Law Control Group (PLCG)** = the docketing/intake unit within the Office of General Counsel; protests are addressed to "General Counsel ... Attention: Procurement Law Control Group" (4 C.F.R. § 21.1(b)); recorded filing-information line (202) 512-4788 (GAO-09-471SP, Bid Protests at GAO: A Descriptive Guide, https://www.gao.gov/assets/gao-09-471sp.pdf). Practical route for protest-file copies: Part 81 request to RecordsRequest@gao.gov after the protest closes, referencing the B-number; PLCG for docket/status questions.
- **After decision:** "After a protest is decided, you may request access to information, including redacted protests" (FAQ). By rule, "GAO will not withhold material submitted by a protester from any party outside the government after issuing a decision on the protest, in accordance with GAO's rules at 4 CFR part 81," and the protester must file a **redacted copy of the protest within 1 day** of filing (4 C.F.R. § 21.1(g)) — so a releasable redacted protest letter exists in the file from day one.
- **Protective-order material:** only outside counsel/consultants admitted under the PO ever see it; "the confidentiality of protected material is maintained in perpetuity." Decisions containing protected information issue first to parties, then a **redacted public version** posts, typically within 2-3 weeks (4 C.F.R. § 21.12).
- **Dismissed protests without published decisions:** dismissals need not produce a published merits decision, but the (redacted) protest letter and the dismissal notice are in GAO's file and are obtainable by Part 81 request after closure. **Agency report:** due 30 days after GAO's notice of the protest (4 C.F.R. § 21.3(c)); agencies seeking dismissal file "as soon as practicable" *before* the report — so if a protest was dismissed ~2-4 weeks after filing, the agency report was almost certainly never filed and **no agency report exists to request** (the underlying agency documents would have to be sought from the procuring agency under its own FOIA).

**SUBMIT VIA:** RecordsRequest@gao.gov (Chief Quality Officer; cite the protest B-number for bid-protest files). Docket/status questions: PLCG, (202) 512-4788.

---

## 5. Office of Government Ethics (OGE)

**FOIA channel** (per OGE's "Submitting a FOIA Request," https://www.oge.gov/web/oge.nsf/Resources/Submitting+a+FOIA+Request):
- Email **usoge@oge.gov** with subject line indicating "Freedom of Information Act request," or mail: OGE FOIA Officer, Office of Government Ethics, **Suite 750, 250 E Street SW, Washington, DC 20024** (note: OGE moved from 1201 New York Ave NW — use the 250 E Street SW address). Phone (202) 482-9300. FOIA.gov submission also referenced; status tracker at extapps2.oge.gov.
- Fees: commercial (search+review+$0.15/page); educational/news media (first 100 pages free); all others (first 2 hours search + 100 pages free); filing deemed agreement to pay up to $25 unless stated.

**OGE Form 201 (the non-FOIA route for public financial disclosure reports, OGE Form 278e/278-T and other ethics documents)** — per the current OGE Form 201 (OMB 3209-0002, exp. 5/31/26; instructions quoted from the form):
- **(a) Officials whose documents OGE holds:** requests to OGE cover only ~1,000 of ~26,000 public filers — individuals who are "(1) Presidentially appointed and Senate-confirmed; (2) a Presidential or Vice Presidential candidate; (3) a senior official at the White House; (4) a Designated Agency Ethics Official" (plus certificates of divestiture for anyone). **Use OGE's online 201 system whenever possible**; otherwise email the PDF form to **201forms@oge.gov** or mail: U.S. Office of Government Ethics, 250 E Street SW, **Suite 710**, Washington, DC 20024-3249. OGE currently cannot fulfill PDF-form requests lacking a requester email. President/VP and Level I/II filers' reports are posted on oge.gov without a 201. 278e/278-T become available 30 days after filing.
- **(b) Agency-level senior officials (e.g., an ICE Senior Advisor, non-PAS):** OGE does **not** hold these. "If you are looking for the ethics documents of an individual who is NOT [in the four categories above], **you must submit a request to the agency that employs the individual**" — i.e., the DHS/ICE ethics office (DAEO), using OGE Form 201 or the agency's own intake ("Agencies may use other systems or forms to accept requests").
- Caveat: a **Modified OGE Form 201** is in OMB clearance (Federal Register, Sept 9, 2025: https://www.federalregister.gov/documents/2025/09/09/2025-17233/; public-inspection follow-up Feb/Mar 2026) — check oge.gov for the newest form version before mailing.

**18 U.S.C. § 208(d)(1) — confirmed:** "Upon request, a copy of any determination granting an exemption under subsection (b)(1) or (b)(3) shall be made available to the public" by the granting agency, per the procedures of 5 U.S.C. § 13107; FOIA-exempt material may be withheld, and for (b)(3) waivers the financial-interest detail is limited to what the individual's disclosure report contains (https://www.law.cornell.edu/uscode/text/18/208). The OGE Form 201 itself lists "18 U.S.C. § 208(b)(1) & (b)(3) waivers" as a requestable document category, citing § 208(d)(1) — so an individual conflict-of-interest waiver for an agency employee is requestable from the employing agency (and via OGE's 201 system for the officials OGE covers).

**SUBMIT VIA:** FOIA — usoge@oge.gov (or mail OGE FOIA Officer, Suite 750, 250 E Street SW, Washington, DC 20024). Financial disclosures — OGE online Form 201 system / 201forms@oge.gov for PAS/White House/DAEO filers; the employing agency's ethics office (DHS/ICE) for agency-level officials such as an ICE Senior Advisor.

---

## 6. DOJ Civil Division FOIA

Verified from the live page https://www.justice.gov/civil/foia (fetched 2026-07-28; justice.gov 403s generic fetchers — use a browser UA):
- "All FOIA requests for Civil Division records should be submitted **via the Civil Division's page on FOIA.gov**. For those without internet access, we do accept FOIA requests via the mail."
- Mail: **Civil Division, Office of Records and Information, Room 8400, 1100 L Street NW, Washington, DC 20530**. Email listed on the page: **civil.routing.foia@usdoj.gov**. Division Records and Information Counsel: Brian Flannigan. FOIA Public Liaison: Stephanie Logan, (202) 514-2319 (also the FOIA Requester Service Number).
- Litigation-records requirement (verbatim tip on the page): identify which DOJ component is handling the case before filing — "If FOIA requesters provide a case name, case citation, and court name when submitting a request to the Civil Division," misdirected requests can be re-routed to the proper component. US Attorney's Offices (via EOUSA) handle much general civil litigation — check the docket for which office appeared.
- FOIA Library on the same page houses frequently requested Civil Division records.

**SUBMIT VIA:** The Civil Division component page on https://www.foia.gov (include case name, citation, and court); mail fallback: Civil Division, Office of Records and Information, Room 8400, 1100 L Street NW, Washington, DC 20530.

---

### Cross-cutting notes
- FOIA.gov consolidation is accelerating: DHS and CBP stopped accepting mail/email/fax requests entirely effective Jan 22, 2026 (FOIA.gov or agency portals only) — expect other agencies to follow; the portal channels above are the durable ones.
- Sources verified 2026-07-28 via live fetches, the api.foia.gov dataset, Wayback captures (cia.gov/readingroom 2026-07-18 and 2026-07-27), eCFR/Cornell regulation text, and NARA primary documents (PA 2026-099 letter).
