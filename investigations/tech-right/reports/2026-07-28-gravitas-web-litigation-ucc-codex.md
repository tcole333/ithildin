# Gravitas Professional Services LLC / Adam Visnic

## VERDICT — NO (no accessible sign found)

**CONFIRMED — Verdict.** I found no affirmative public evidence of firm-level distress, closure, litigation, or financing pressure that explains why ICE did not extend Gravitas's delivery order. The accessible evidence points the other way: the website was live in every sampled capture; its federal/skip-tracing marketing stayed in place; Visnic's professional page was edited one day after the order expired; a Tampa contact location was added after May; Google Maps currently labels the Cincinnati listing open; and the federal award record still contains only the original action. **BLOCKED — Important limit.** Ohio's official UCC search was behind a Cloudflare security/maintenance page, its alternate API required a bearer token, and the Warren recorder search invokes reCAPTCHA. I therefore cannot determine whether Gravitas filed a financing statement, factored receivables, or has a recorder-indexed lien. The verdict means **no sign found in the accessible sources**, not proof that no undisclosed business or government-side issue existed.

**CONFIRMED — Retrieval scope.** All retrievals below were made on **2026-07-28**. Files are saved under `/tmp/osint-FRmkNLeM/work-T/`.

## 1. Website timeline and infrastructure

**CONFIRMED — 2025-10-14 and 2025-11-19.** The homepage was live and described the firm as serving “Private investigators serving public and private clients.” Its structured metadata said the page had last been modified on 2025-07-22. There was no homepage reference to government agencies, skip tracing, SAM.gov, ICE, or DHS in these captures. Sources: [2025-10-14 10:35:29 UTC capture](https://web.archive.org/web/20251014103529id_/https://www.gravitasinv.com/) (saved `wayback-20251014103529.html`) and [2025-11-19 07:55:24 UTC capture](https://web.archive.org/web/20251119075524id_/https://www.gravitasinv.com/) (saved `wayback-20251119075524.html`).

**CONFIRMED — 2026-01-17.** The homepage remained live with the same public/private-client positioning; its metadata showed a 2025-12-05 modification date. Source: [2026-01-17 16:44:55 UTC capture](https://web.archive.org/web/20260117164455id_/https://www.gravitasinv.com/) (saved `wayback-20260117164455.html`).

**CONFIRMED — 2026-02-12.** A homepage revision dated 2026-02-06 changed the positioning to “Private investigators serving insurers, attorneys, employers, and government agencies nationwide,” displayed “Skip Trace,” and added the footer identifier `SAM.gov UEI #EJB9AHGV8BD1`. Source: [2026-02-12 01:08:24 UTC capture](https://web.archive.org/web/20260212010824id_/https://www.gravitasinv.com/) (saved `wayback-20260212010824.html`).

**CONFIRMED — Contract-expiry and post-expiry captures.** The 2026-03-15, 2026-04-15, and 2026-05-17 homepage captures retained the government-agency, skip-trace, and SAM.gov language. Nothing in those captures announces closure, suspension, layoffs, or an end to federal work. Sources: [2026-03-15 11:37:43 UTC](https://web.archive.org/web/20260315113743id_/https://www.gravitasinv.com/) (saved `wayback-20260315113743.html`), [2026-04-15 22:01:11 UTC](https://web.archive.org/web/20260415220111id_/https://www.gravitasinv.com/) (saved `wayback-20260415220111.html`), and [2026-05-17 04:14:17 UTC](https://web.archive.org/web/20260517041417id_/https://www.gravitasinv.com/) (saved `wayback-20260517041417.html`).

**CONFIRMED — ICE/DHS language was not removed.** Visnic's professional page already listed ICE and DHS in the 2025-11-19 capture. The 2026-04-15 capture reported a page modification on **2026-03-16**, one day after the order expired, and still listed both agencies. The live page reports another modification on **2026-04-22** and continues to list ICE and DHS. Sources: [2025-11-19 capture](https://web.archive.org/web/20251119064532id_/https://www.gravitasinv.com/about-us/adam-visnic/) (saved `wayback-adam-20251119.html`), [2026-04-15 capture](https://web.archive.org/web/20260415220059id_/https://www.gravitasinv.com/about-us/adam-visnic/) (saved `wayback-adam-20260415.html`), and [live Visnic page](https://www.gravitasinv.com/about-us/adam-visnic/) (saved `current-adam-visnic.html`).

**CONFIRMED — Additional post-expiry edits.** The live homepage reports a **2026-06-16** modification and adds a direct SAM.gov logo/link that was absent in the sampled February-May homepages. The contact page also reports a 2026-06-16 modification and now lists a Tampa location; Tampa was absent from the 2026-05-16 capture. Sources: [live homepage](https://www.gravitasinv.com/) (saved `current-root.html` and `wp-page-554.json`), [2026-05-16 contact capture](https://web.archive.org/web/20260516172624id_/https://www.gravitasinv.com/contact-info/) (saved `wayback-contact-20260516.html`), and [live contact page](https://www.gravitasinv.com/contact-info/) (saved `current-contact.html`).

**CONFIRMED — No captured website shutdown or platform abandonment.** The enumerated Wayback record contains root captures throughout the relevant period, and every sampled page returned substantive WordPress content. Sampled archived responses from October 2025 through May 2026 identify Apache and WordPress/Enfold assets; the live response is also Apache/WordPress. **UNCONFIRMED — Inter-capture availability.** A brief outage between snapshots cannot be ruled out, but no prolonged abandonment is visible. Sources: [Wayback CDX enumeration](https://web.archive.org/cdx/search/cdx?url=gravitasinv.com%2A&output=json&filter=statuscode%3A200&filter=mimetype%3Atext%2Fhtml&collapse=digest) (saved `wayback-cdx.json` and `wayback-root-window.json`) and the capture files above.

**CONFIRMED — Current domain and certificate maintenance.** On 2026-07-28 the domain resolved to `173.236.243.27`, used DreamHost name servers and registrar, and had an expiry date of 2027-01-17. Certificate Transparency shows uninterrupted Let's Encrypt certificates, including certificates issued 2026-03-08, 2026-05-02, and 2026-06-27; the last expires 2026-09-25. CT names were limited to `gravitasinv.com` and `www.gravitasinv.com`, with no sibling hostnames found. Sources: DNS and WHOIS lookups (saved `dns-current.txt` and `whois-gravitasinv.com.txt`) and [crt.sh identity query](https://crt.sh/?Identity=%25.gravitasinv.com&output=json) (saved `crtsh-identity.json`).

**UNCONFIRMED — Historical hosting provider.** The current DNS and registration point to DreamHost, while archived and current HTTP responses consistently say Apache. That is insufficient to prove the underlying hosting provider never changed; no relevant historical DNS series was available. It does establish that no platform or server-family change is visible in the sampled pages.

**CONFIRMED — urlscan coverage was sparse.** The public urlscan search returned one scan, for the contact page on 2024-04-16, and `has_more:false`; it supplied no later independent snapshots. Source: [urlscan public search](https://urlscan.io/api/v1/search/?q=domain%3Agravitasinv.com) (saved `urlscan-search.json`).

## 2. Litigation

**CONFIRMED — Warren County Common Pleas: zero.** A broad surname/name search for `VISNIC` and a broad organization search for `GRAVITAS`, across all court types, causes, divisions, statutes, Plaintiff/Defendant/Judge/Attorney roles, and aliases, each returned **Cases Found: 0**. The clerk says its case histories cover May 1991 forward, with captions from 1980-May 1991. Sources: [Warren County case inquiry](https://clerkofcourts.warrencountyohio.gov/CommonPleasDiv/CaseInquiry/Index) and [Benchmark search](https://clerkofcourt.co.warren.oh.us/BenchmarkCP/CourtCase.aspx/CaseSearch) (saved `warren-commonpleas-inquiry.html`, `warren-results-visnic.html`, and `warren-results-gravitas.html`).

**CONFIRMED — Lebanon Municipal Court: zero.** Broad searches for `VISNIC` and `GRAVITAS` each returned **0 Matches Found**. Source: [Lebanon Municipal Court CaseLook](https://caselook.lebanonohio.gov/search/8321) (saved `lebanon-results-visnic-broad.html` and `lebanon-results-gravitas-broad.html`).

**CONFIRMED — Twelfth District published opinions: zero.** The Supreme Court of Ohio Reporter of Decisions search, limited to Twelfth District, Warren County, 1992-2026, returned **0 rows** for `Gravitas` and **0 rows** for `Visnic`. The Twelfth District states that county common-pleas clerks maintain appellate case files; the Warren broad search above also returned zero and included all court types, including notices of appeal. Sources: [Twelfth District clerk explanation](https://12thdca.com/clerks.html) (saved `twelfth-clerks.html`) and [Ohio Reporter of Decisions search](https://www.supremecourt.ohio.gov/rod/docs/?source=12) (saved `ohio-rod-gravitas.html` and `ohio-rod-visnic.html`).

**CONFIRMED — Federal public/RECAP coverage: no target case found.** Exact-party CourtListener searches returned zero for the firm and Visnic. Southern District of Ohio bankruptcy searches returned zero for both. A Southern District keyword search produced two unrelated cases, but neither party list contained Gravitas or Visnic; they were excluded as text-search false positives. Sources: [CourtListener search API](https://www.courtlistener.com/api/rest/v3/search/) (saved `courtlistener-party-firm.json`, `courtlistener-party-visnic.json`, `courtlistener-ohsb-firm.json`, `courtlistener-ohsb-visnic.json`, `courtlistener-ohsd-firm.json`, and `courtlistener-ohsd-visnic.json`).

**CONFIRMED — Litigation conclusion within accessible coverage.** No accessible county, municipal, published appellate, federal, or bankruptcy result showed collections, contract disputes, judgments, liens, employment claims, eviction, or bankruptcy involving the target names.

## 3. UCC and financing

**BLOCKED — Ohio UCC result cannot be determined.** The production Ohio Secretary of State UCC portal returned HTTP 403 with a Cloudflare security page titled “Ohio Secretary of State's Office Website Maintenance.” The alternate public-facing API returned HTTP 401 with `WWW-Authenticate: Bearer`. Complying with the no-login/no-CAPTCHA rule, I did not attempt the security challenge, acquire a token, or use the test system as evidence. Sources: [Ohio UCC search](https://ucc.ohiosos.gov/search) (saved `ohio-ucc-search.html` and `ohio-ucc-headers.txt`) and alternate API response (saved `uccapi-search-gravitas-headers.txt` and `uccapi-search-gravitas.json`).

**BLOCKED — Warren County recorder.** The recorder says its AVA site permits name searches of recorded land documents, but the current client invokes reCAPTCHA v3 for searches. No challenge was attempted. Sources: [Warren Recorder public-record instructions](https://recorder.warrencountyohio.gov/Info/SearchInfo/Index) and [AVA](https://ohwarren.fidlar.com/OHWarren/AvaWeb/) (saved `warren-recorder-info.html`, `fidlar-home.html`, `fidlar-appConfig.json`, and `fidlar-main.js`).

**UNCONFIRMED — Financing-pressure comparison.** There is no defensible positive or negative UCC answer from this run. Gravitas cannot be placed in, or contrasted with, the peer factoring cluster on the evidence obtained.

## 4. Business footprint, signs of life, and 1985 King Avenue

**CONFIRMED — Current Google business listing.** Google's public map-search response identified “Gravitas Investigations” as a private investigator at 525 Vine Street #523, Cincinnati, linked to `gravitasinv.com`, and displayed **Open · Closes 9 PM** for Tuesday 2026-07-28. This confirms what the listing displayed, not independently verified staffing or office occupancy. Source: [Google map-search query](https://www.google.com/search?tbm=map&hl=en&gl=us&q=Gravitas+Investigations+Kings+Mills+OH) (saved `google-tbm-map-firm.txt`).

**CONFIRMED — Public LinkedIn company page remains live.** The guest-visible page returned HTTP 200, displayed 579 followers, described work for insurance carriers, attorneys, employers, and public agencies, and encoded a company size of four employees. Its latest guest-visible post was dated 2025-12-17, so LinkedIn supplied no dated post-expiry activity. Source: [Gravitas Investigations on LinkedIn](https://www.linkedin.com/company/gravitasinvestigations/) (saved `linkedin-company-correct.html`).

**CONFIRMED — Stronger post-expiry signs came from the firm's own site.** The 2026-03-16 and 2026-04-22 Visnic-page modifications, the 2026-06-16 homepage/contact modifications, the newly displayed Tampa location, and continued ICE/DHS/SAM.gov/skip-trace marketing are inconsistent with a website abandoned because the firm had closed. **UNCONFIRMED — Operational inference.** These are marketing and technical signals; they do not prove revenue, headcount, solvency, or that every listed office is staffed.

**CONFIRMED — 1985 King Avenue is a postal facility/multi-address building.** The firm's current contact page displays `1985 King Avenue, #321, Kings Mills, OH 45034`. Google's exact base-address map response identifies `1985 King Ave Rd` as a building and lists **United States Postal Service — Post office** at the same address and coordinates; it also lists several unrelated businesses using numbered suites/units there. Sources: [firm contact page](https://www.gravitasinv.com/contact-info/) (saved `current-contact.html`) and [Google exact-address map query](https://www.google.com/search?tbm=map&hl=en&gl=us&q=1985+King+Avenue+Kings+Mills+OH+45034) (saved `google-tbm-map-address-base.txt` and `google-tbm-map-address.txt`).

**UNCONFIRMED — Mailbox inference.** Because the base address is a post office and the known mailing address is P.O. Box 321, `#321` is very likely a street-address representation of that postal box rather than a conventional occupied office. The public records obtained do not independently prove the box assignment, so this remains an explicit inference.

**CONFIRMED — Other footprint checks.** BBB's public search returned zero results for “Gravitas Investigations” near Kings Mills. Google's news RSS searches for the firm and Visnic found four items each over the prior year; post-March items concerned the ICE contracting program, not closure, litigation, layoffs, bankruptcy, or financial distress. Sources: [BBB search](https://www.bbb.org/search?find_country=USA&find_text=Gravitas%20Investigations&find_loc=Kings%20Mills%2C%20OH) (saved `bbb-search.html`), [Google News firm query](https://news.google.com/rss/search?q=%22Gravitas+Investigations%22+when%3A1y&hl=en-US&gl=US&ceid=US%3Aen) (saved `google-news-gravitas.xml`), and [Google News Visnic query](https://news.google.com/rss/search?q=%22Adam+Visnic%22+when%3A1y&hl=en-US&gl=US&ceid=US%3Aen) (saved `google-news-adam.xml`).

**UNCONFIRMED — Hiring.** No careers page appeared in the firm's current 25-page sitemap, and the guest-visible LinkedIn company page did not expose a firm-specific vacancy. Indeed could not be checked because it returned a Cloudflare challenge. Absence from these limited surfaces is not evidence of layoffs or a hiring freeze.

## 5. Current FPDS / USAspending state

**CONFIRMED — FPDS unchanged.** The 2026-07-28 FPDS feed contains exactly one entry for `70CDCR26FR0000016`: transaction 0, modification 0, signed 2025-12-16, completion 2026-03-15, and obligation $427,500. Its last-modified timestamp remains 2026-01-22. There is no de-obligation, closeout, termination, or extension modification. Source: [FPDS public Atom feed](https://www.fpds.gov/ezsearch/FEEDS/ATOM?FEEDNAME=PUBLIC&templateName=1.5.3&q=PIID%3A%2270CDCR26FR0000016%22&start=0) (saved `gravitas-fpds-raw.xml` and parsed `gravitas-fpds.json`).

**CONFIRMED — USAspending outlay unchanged.** The award-detail API reports total obligation **$427,500.00** and total account outlay **$130,769.84**, or **30.6%**, leaving **$296,730.16 obligated but not reflected as account outlay**. The period still ends 2026-03-15, its last-modified date is 2026-01-22, and subaward count is zero. Source: [USAspending award-detail API](https://api.usaspending.gov/api/v2/awards/CONT_AWD_70CDCR26FR0000016_7012_70CDCR26D00000018_7012/) (saved `usaspending-award-detail-raw.json` and `usaspending-award-detail.json`).

**UNCONFIRMED — Closeout inference.** The unchanged federal records provide no public administrative explanation for the non-extension. They also do not prove that closeout or invoice processing is complete, because account outlay and contract-action feeds can lag internal government activity.

## 6. CHECKED AND EMPTY

- **CONFIRMED — Empty:** Warren County Common Pleas broad searches for `VISNIC` and `GRAVITAS` — zero cases.
- **CONFIRMED — Empty:** Lebanon Municipal Court broad searches for both names — zero matches.
- **CONFIRMED — Empty:** Twelfth District/Warren published-opinion searches, 1992-2026 — zero rows for both names.
- **CONFIRMED — Empty:** CourtListener exact-party searches for the firm and Visnic — zero; Southern District of Ohio bankruptcy searches — zero.
- **CONFIRMED — Empty:** CourtListener Southern District keyword hits were reviewed and excluded as unrelated false positives.
- **CONFIRMED — Empty:** BBB exact local search — zero listings.
- **CONFIRMED — Empty:** crt.sh sibling-name search — only the apex and `www` names.
- **CONFIRMED — Empty:** urlscan — no scan after 2024-04-16.
- **CONFIRMED — Empty:** Current site sitemap — no careers page.
- **CONFIRMED — Empty:** Accessible post-March news results — contract reporting only; no distress/closure report.
- **CONFIRMED — Empty:** FPDS — no action after modification 0; USAspending — no changed end date and no subaward.

## 7. BLOCKED ITEMS FOR FOLLOW-UP

- **BLOCKED — Ohio UCC:** Cloudflare security/maintenance page; alternate API required bearer authentication. No CAPTCHA or login was attempted.
- **BLOCKED — Warren recorder lien/index search:** AVA invokes reCAPTCHA v3 for search. No challenge was attempted.
- **BLOCKED — Mason Municipal Court:** the public search action required Google reCAPTCHA. No challenge was attempted. Saved `mason-search-2.html`.
- **BLOCKED — Franklin County eAccess:** the public docket is JavaScript-only; terminal browser startup was denied by the sandbox and no connected in-app browser was available. Saved `franklin-eaccess.html`.
- **BLOCKED — PACER-only federal material:** PACER requires an account/login. CourtListener/RECAP was checked instead; sealed and non-RECAP matters remain outside this run.
- **BLOCKED — Yelp:** HTTP 403/DataDome challenge. Saved `yelp-search.html`.
- **BLOCKED — Indeed:** HTTP 403/Cloudflare challenge. Saved `indeed-gravitas.html`.
- **BLOCKED — Adam Visnic LinkedIn profile detail:** the public company page was accessible, but the individual guest page did not expose substantive profile content after redirect. No login was attempted. Saved `linkedin-adam.html`.
