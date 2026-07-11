# Reid Weingarten public-client census

Status: lead #52365 completed research pass on 2026-07-09. Active profile: `softbank-caper`.

Machine-readable companion: [reid-weingarten-clients.csv](./reid-weingarten-clients.csv)

## Bottom line

This census contains 139 source-graded rows, not 139 claimed personal clients. The rows deliberately keep apart:

- 42 named subjects with a direct appearance, signed filing, primary judicial allocation, direct retained-counsel statement, or comparably strong record (`C1`);
- 24 additional named personal or institutional engagements reported by Weingarten's firm, Weingarten himself, or strong contemporaneous reporting, but for which this pass did not retrieve a signed appearance (`C2`);
- 1 additional unidentified personal client directly attributed by strong contemporaneous reporting (`C2-U`);
- 6 dockets where Weingarten's participation is confirmed but the public attorney roster does not resolve which co-defendant was his client (`C1-M`);
- 3 matters proving that he had a client while the client's identity remains sealed or unstated (`C1-U`);
- 34 Steptoe matters that cannot be attributed to Weingarten personally (`C3`);
- 10 Epstein-mediated prospective-client, referral, or consultation rows (`C4/C5` or `C5`);
- 4 probable or publicly rumored identities that remain unverified (`C6`);
- 4 specifically tested people/entities or explicit non-client records for which the evidence does not support a client relationship (`T0`); and
- 11 grouped false-positive/name-context rows, principally cases Weingarten prosecuted before private practice (`C7`).

The strongest SoftBank-relevant result is still negative but not dismissive: the January 2019 Rajeev Misra exchange is a genuine prospective-matter signal, and `DB` remains relevant even though its expansion is unresolved. The public record still does not establish that Misra retained Weingarten, that SoftBank retained him, that Ron Soffer was engaged, or that Alessandro Benedetti was a client. The comparator set demonstrates why the intake exchange must remain live: a similarly phrased Huawei question later became a documented Wanzhou Meng representation, while the Flynn, Barrack, and Mizrahi inquiries did not produce a public Weingarten appearance.

The broader Epstein-overlap result is affirmative and worth separating from the SoftBank question. The Wall Street Journal reports that Weingarten represented Edmond de Rothschild Group before transferring the client to Kathryn Ruemmler and that Epstein was seen as the account's gatekeeper. Released 2013-2014 meeting messages independently support the relationship sequence, although they do not themselves prove the retainer.

## Evidence rules

| Code | Meaning | Required showing |
|---|---|---|
| `C1` | Confirmed personal appearance or retention | Signed filing, court allocation, client/agency record, direct retained-counsel statement, or equivalent primary proof |
| `C1-M` | Confirmed matter-level appearance | Weingarten is in the defense roster, but a multi-party docket does not map him to a particular defendant |
| `C1-U` | Confirmed unidentified client | A primary record proves a client relationship but seals or omits the identity |
| `C2` | Authoritative personal representation | Weingarten/Steptoe biography or strong contemporaneous report personally attributes the client, without a retrieved appearance |
| `C2-U` | Authoritative unidentified representation | Strong contemporaneous reporting personally attributes a client relationship but does not disclose the client's identity |
| `C3` | Steptoe firm-level matter only | The firm is confirmed, but no source attributes the matter to Weingarten |
| `C4/C5` | Epstein-mediated prospective engagement | Weingarten discussed taking the matter with Epstein, but retention is unproven |
| `C5` | Epstein referral or consultation | Legal advice, referral, or possible co-counsel discussion without proof of client retention |
| `C6` | Publicly claimed or inferred, unverified | Identity or relationship is plausible but not established by a primary/authoritative source |
| `T0` | Tested or explicit non-client | The person/entity was specifically checked or expressly disclaimed and should not be promoted to client status |
| `C7` | Collision or non-client context | Prosecutor role, bibliographic citation, or other demonstrable false positive |

An absent docket appearance is a bounded negative, not proof that private counseling did not occur. Corporate investigations, congressional matters, internal reviews, and pre-charge advice often leave no public appearance.

## Confirmed personal appearances or retentions (`C1`)

The CSV supplies aliases, dates, role, tribunal, outcome, confidence, and a best source for every row. This table gives the readable core.

| Client | Matter | Best public proof |
|---|---|---|
| William Facteau | Acclarent medical-device prosecution | [Federal docket](https://www.courtlistener.com/docket/4511866/united-states-v-facteau/) |
| David Rainey | Deepwater Horizon obstruction/false-statement case | [Opinion allocating Weingarten to Rainey](https://www.courtlistener.com/opinion/8725426/united-states-v-rainey/) |
| Bernard Ebbers | WorldCom prosecution and appeal | [Second Circuit opinion](https://www.courtlistener.com/opinion/795254/united-states-v-bernard-j-ebbers/) |
| Richard Causey | Enron prosecution | [Court opinion](https://www.courtlistener.com/opinion/2573062/united-states-v-causey/) |
| Anthony Cuti | Duane Reade accounting-fraud prosecution | [Federal docket](https://www.courtlistener.com/docket/6067624/united-states-v-cuti/) plus Steptoe bio |
| James Treacy | Monster.com options-backdating case | [Second Circuit opinion](https://www.courtlistener.com/opinion/206316/united-states-v-treacy/) |
| Elizabeth Monrad | General Re/AIG finite-reinsurance case | [Signed judgment naming Weingarten](https://www.justice.gov/sites/default/files/criminal-fraud/legacy/2015/05/22/04-14-09elizabeth-monrad-judgment.pdf) |
| A. Michael Espy | Independent Counsel prosecution | [District-court opinion](https://www.courtlistener.com/opinion/2516283/united-states-v-espy/) |
| Ronald Carey | Teamsters election/perjury matters | [District-court opinion](https://www.courtlistener.com/opinion/2482998/united-states-v-carey/) |
| Pauline Kanchanalak | DNC fundraising prosecution | [D.C. Circuit opinion](https://www.courtlistener.com/opinion/184993/united-states-v-kanchanalak/) |
| Yah Lin “Charlie” Trie | DNC fundraising matters | [D.C. Circuit amicus appearance](https://www.courtlistener.com/opinion/184864/united-states-v-hsia-maria/) plus Steptoe bio |
| Lauren Stevens | GSK/FDA-response prosecution | [Court opinion](https://www.courtlistener.com/opinion/2476495/united-states-v-stevens/) |
| John Rowland | Connecticut campaign-consulting prosecution | [Federal docket](https://www.courtlistener.com/docket/4199281/united-states-v-rowland/) |
| Jesse Jackson Jr. | Campaign-funds prosecution | [Official Senate questionnaire identifying counsel](https://www.judiciary.senate.gov/imo/media/doc/Graves%20%28DC%29%20SJC%20Questionnaire%20%28public%29.pdf) |
| Anthony Chiasson | Level Global insider-trading prosecution | [Federal docket](https://www.courtlistener.com/docket/4350184/united-states-v-newman/) and Steptoe profile |
| Volkswagen AG | Diesel-emissions criminal investigation and plea | [Steptoe statement personally attributing representation](https://www.steptoe.com/en/news-publications/law360-again-names-reid-weingarten-an-mvp-in-white-collar.html) and Liang dockets |
| Fethullah Gülen | Civil claims and extradition/public-response work | [Federal docket](https://www.courtlistener.com/docket/4528372/ates-v-gulen/) and released client-team emails |
| Jeffrey Epstein | 2019 SDNY prosecution and appeal | [Signed appellate stipulation](https://www.justice.gov/multimedia/Court%20Records/United%20States%20v.%20Epstein%2C%20No.%2019-2221%20%282d%20Cir.%202019%29/19-2221_Documents.pdf) |
| Wanzhou Meng | Huawei CFO prosecution | [Federal docket](https://www.courtlistener.com/docket/14539830/united-states-v-huawei-technologies-co-ltd/) and 2021 appearance |
| Steve Wynn | DOJ FARA civil action | [D.C. Circuit docket](https://www.courtlistener.com/docket/66714163/attorney-general-of-the-united-states-v-stephen-wynn/) |
| Ali Sadr Hashemi Nejad | Iran-sanctions prosecution | [Federal docket](https://www.courtlistener.com/docket/6360274/united-states-v-nejad/) |
| Mike Lynch | Autonomy/HP fraud prosecution | [Signed defense motion](https://northerndistrictpracticeprogram.org/wp-content/uploads/2025/05/US-v.-Lynch-Motion-to-Exclude-Expert-Yelland.pdf) |
| Alain Kaloyeros | Buffalo Billion prosecution and appeals | [Second Circuit record](https://www.govinfo.gov/content/pkg/USCOURTS-ca2-18-02990/pdf/USCOURTS-ca2-18-02990-3.pdf) |
| Rick Renzi | Federal public-corruption prosecution | [Ninth Circuit opinion](https://www.courtlistener.com/opinion/219551/united-states-v-renzi/) |
| Terrance Wilson | ADM lysine price-fixing prosecution | [Seventh Circuit opinion](https://www.courtlistener.com/opinion/769183/united-states-of-america-plaintiff-appelleecross-appellant-v-michael-d/) |
| David Kay | American Rice FCPA prosecution | [Fifth Circuit opinion](https://www.courtlistener.com/opinion/52834/united-states-v-kay/) |
| Franklin Brown | Rite Aid accounting-fraud prosecution | [Court opinion](https://www.courtlistener.com/opinion/2573137/united-states-v-brown/) |
| Eugene Bennett | Virginia murder prosecution | [Contemporaneous report quoting Weingarten accepting representation](https://www.washingtonpost.com/archive/local/1997/02/05/major-case-high-profile-legal-team/3413970b-a2bc-4513-ac0d-57b953517a77/) |
| Harvey Weinig | Executive-clemency petition | [Congressional report](https://www.govinfo.gov/content/pkg/CRPT-107hrpt454/pdf/CRPT-107hrpt454-vol1.pdf) says Weinig hired Weingarten and spouse Alice Morey retained him; [Washington Post](https://www.washingtonpost.com/archive/politics/2001/03/03/humanitarianism-cited-in-clemency-for-lawyer/466c7336-7fdf-4295-97f4-6d8c33b5b332/) calls him Weinig's attorney |
| Bernard Berlow | Federal criminal matter | [Single-defendant docket](https://www.courtlistener.com/docket/8344563/united-states-v-berlow/) |
| Charles Busse | Federal criminal matter | [Single-defendant docket](https://www.courtlistener.com/docket/21226448/united-states-v-busse/) |
| Samuel Burstyn | Federal criminal matter | [Single-defendant docket](https://www.courtlistener.com/docket/20866919/united-states-v-burstyn/) |
| Brian Block | American Realty Capital Properties accounting case | [Single-defendant criminal docket](https://www.courtlistener.com/docket/4610216/united-states-v-block/) |
| Cargill, Inc. | High-fructose-corn-syrup antitrust appeal | [Seventh Circuit opinion](https://www.courtlistener.com/opinion/747776/dellwood-farms-inc-v-cargill-inc/) |
| Project Life, Inc. | Disability-access litigation | [District-court opinion](https://www.courtlistener.com/opinion/2409977/project-life-inc-v-glendening/) |
| U.S. Department of Commerce | Judicial Watch FOIA litigation | [District-court opinion](https://www.courtlistener.com/opinion/8746728/judicial-watch-inc-v-united-states-department-of-commerce/) |
| Ivan Glasenberg | Swiss, British, and Dutch Glencore investigations | [2025 English High Court judgment, ¶255](https://www.judiciary.uk/wp-content/uploads/2025/08/Disclosure-Judgment-for-Hand-Down-28082025.pdf) |
| Richard Ireland | Pennsylvania pay-to-play prosecution | `HOUSE_OVERSIGHT_023102` and [Steptoe account](https://www.steptoe.com/en/news-publications/law360-again-names-reid-weingarten-an-mvp-in-white-collar.html) |
| Nicole Daedone | OneTaste forced-labor conspiracy prosecution | [Federal docket](https://www.courtlistener.com/docket/67480223/united-states-v-cherwitz/) and [Reuters report](https://www.yahoo.com/news/founder-us-orgasmic-meditation-group-161542412.html) allocating Weingarten to Daedone |
| Michael A. Brown | D.C. bribery prosecution | [Single-defendant federal docket](https://www.courtlistener.com/docket/4212042/united-states-v-brown/) and [Washington Post lead-attorney attribution](https://www.washingtonpost.com/opinions/2024/01/26/evans-brown-dc-politics-council/) |
| Parthasarathy Sudarshan | Illegal export of controlled electronic components to Indian government entities | Two single-defendant federal dockets, [1:08-cr-00037](https://www.courtlistener.com/docket/4209123/united-states-v-sudarshan/) and [1:07-cr-00051](https://www.courtlistener.com/docket/4206761/united-states-v-sudarshan/), list Weingarten; [contemporaneous reporting](https://timesofindia.indiatimes.com/indian-origin-man-jailed-for-illegal-technology-export/articleshow/3138751.cms) calls him Sudarshan's lead attorney |
| Richard Marshall Hirschfeld | Pending E.D. Va. indictments, German witness-travel negotiations, and presidential-pardon submission | A [Clinton Presidential Library/NARA file](https://nara-media.s3.amazonaws.com/presidential-libraries/clinton/foia/2006/2006-1704-F-Seg-1-PDF/2006-1704-F-Pardons-PDF/Box_47/42-t-7422579-20061704F-047-003-2016.pdf) contains Weingarten's February 24, 2000 Steptoe letter stating “We jointly represent Richard Hirschfeld”; a January 9, 2001 transmittal separately calls Weingarten counsel to the pardon petitioner |

Two boundary notes matter. First, Epstein is confirmed for the 2019 case and subsequent estate-privilege response; that does not establish that Weingarten negotiated Epstein's 2007–2008 non-prosecution agreement. Second, the Commerce opinion really does list private Steptoe counsel “for Defendant,” but the unusual government-client allocation should be checked against the underlying docket before relying on it for a more specific proposition.

## Authoritative personal representations without a retrieved appearance (`C2`)

| Client | Publicly described matter | Best source and limitation |
|---|---|---|
| Mark Belnick | Tyco criminal/civil matters | [Steptoe/Law360 profile](https://www.steptoe.com/en/news-publications/law360-names-reid-weingarten-a-trial-ace.html); federal sweep mainly returned related civil litigation |
| Gordon Herman | Neteller prosecution | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); no signed appearance retrieved |
| Douglas Jemal | Washington bribery prosecution | [Steptoe publication calling Weingarten lead defense attorney](https://www.steptoe.com/a/web/1708/2778.pdf) |
| Lamar Owens | Naval Academy court-martial | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html) and Weingarten interview; military appearance not retrieved |
| Erick Brown | Washington, DC detective matter | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); caption/date withheld |
| Republic of Kazakhstan | Grand-jury/investigations work | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); an opinion names an unidentified “Republic” but does not identify Kazakhstan |
| Ronald “Ron” Brown | Commerce/independent-counsel matters | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); do not confuse with Franklin Brown |
| Joshua “Josh” Steiner | Whitewater testimony and related Treasury inquiries | [March 1994 Washington Post report](https://www.washingtonpost.com/archive/politics/1994/03/09/when-scandal-rocks-capital-lawyers-are-ready-to-roll/fd5ec004-cff7-4b6e-8157-68644f0ab7fa/) says Steiner was turning to Weingarten; later reporting directly calls Weingarten his lawyer |
| Bud Shuster | House/transportation-related investigation | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); matter caption withheld |
| John Rosales | Henry Cisneros-related investigation | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); matter caption withheld |
| William Brady | Credit Suisse First Boston matter | [Steptoe bio](https://www.steptoe.com/en/lawyers/reid-weingarten.html); matter caption withheld |
| Cary Maultasch | Drexel/junk-bond investigation | [Steptoe Trailblazer profile](https://www.steptoe.com/en/news-publications/national-law-journal-names-reid-weingarten-a-trailblazer-in-white-collar.html) |
| Lloyd Blankfein | Goldman Sachs financial-crisis investigations | [Contemporaneous retention report](https://www.theguardian.com/business/2011/aug/23/lloyd-blankfein-banking); advisory work would not necessarily create an appearance |
| Roman Polanski | Los Angeles fugitive/extradition matter | [Steptoe/Am Law profile](https://www.steptoe.com/en/news-publications/am-law-litigation-daily-profiles-reid-weingarten.html) |
| Jane Harman | Unidentified matter | [Steptoe Trailblazer profile](https://www.steptoe.com/en/news-publications/national-law-journal-names-reid-weingarten-a-trailblazer-in-white-collar.html); no matter named |
| Abbe Lowell | DOJ pardon/bribery inquiry | [Contemporaneous report identifying Lowell's attorney](https://www.yahoo.com/news/u-justice-department-probed-kushner-033507365.html) |
| Pilot Flying J | Internal investigation after federal raid | [Contemporaneous report of the company hiring Weingarten](https://cs.observer-reporter.com/news/2013/may/01/tenn-governors-former-boss-to-oversee-pilot-probe/) |
| U.S. Senate Foreign Relations Committee panel | October Surprise inquiry | [Contemporaneous report of his appointment as special counsel](https://www.washingtonpost.com/archive/national/1991/12/17/senators-name-special-counsel-for-october-surprise-inquiry/14acc70f-78ab-4204-b3a3-de0d2ec6a3e1/); institutional legal engagement, not a private defense client |
| Peter J. Visclosky | PMA Group/earmark investigation and House Ethics response | [Washington Post](https://www.washingtonpost.com/politics/visclosky-aide-offered-earmarks-for-campaign-donation-convicted-lobbyist-said/2014/09/18/7ab7cc6a-3f3f-11e4-b0ea-8141703bbf6f_story.html) identifies Visclosky's attorneys as Weingarten and Brian Heberlig |
| Edith O'Brien | MF Global collapse investigations and immunity discussions | [Fox Business](https://www.foxbusiness.com/features/exclusive-senior-mf-global-executive-said-corzine-knew-about-misuse-of-funds) directly identifies Weingarten as O'Brien's attorney; this does not by itself allocate the later CFTC civil case to him |
| Gaynelle Griffin Jones | Internal Justice Department probe concerning her handling of Houston investigations | [Houston Press](https://www.houstonpress.com/news/the-insider-6571478) reported contemporaneously that Jones hired Weingarten to defend her interests; the public outcome of the internal probe was not found |
| Edmond de Rothschild Group | U.S. regulatory matter later transferred to Kathryn Ruemmler | A [Wall Street Journal report](https://www.tovima.com/wsj/when-the-fbi-arrested-epstein-he-called-kathryn-ruemmler) says Weingarten had represented the Swiss bank before transferring it to Ruemmler; released 2013-2014 meeting emails corroborate the Weingarten/Rothschild/Epstein relationship sequence but do not independently prove the retainer |
| Robert F. Smith | DOJ/IRS offshore-tax investigation | A [Bloomberg investigation syndicated in full](https://www.wealthmanagement.com/high-net-worth/how-billionaire-robert-smith-avoided-indictment-in-a-multimillion-dollar-tax-case) says Smith retained Kenneth Wainstein and Weingarten was prepared to try the case if Smith were indicted; the 2020 non-prosecution agreement explains the absence of a court appearance |
| Jacob H. Rivers | Bolar Pharmaceutical/generic-drug investigation and indictment | The [Washington Post](https://www.washingtonpost.com/archive/politics/1991/10/11/four-indicted-in-generic-drug-probe/3986e311-b2b0-42a2-b0b8-777e860d1c21/) contemporaneously called Weingarten an attorney for Rivers and quoted him contesting the charges; no signed appearance was retrieved |

The present Steptoe biography names 22 people/entities in its “Recent” and “Select Prior” lists. Wayback captures from 2018, 2019, 2021, and 2025 carry the same roster. That stability is useful for authentication, but it also shows that the page is a selected and partly stale marketing list, not a chronological client register.

## Confirmed matter, unresolved client allocation (`C1-M`)

| Docket/matter | Publicly named possible clients | What is known |
|---|---|---|
| U.S. v. Jaffe Group | Morris Douglas Jaffe Jr.; Jaffe Group, Inc. | Two linked 1992 dockets list Weingarten; exact entity/person allocation should be confirmed from filings |
| U.S. v. USPlabs | USPlabs; Geissler; Doyle; Hebert; Miles; S.K. Laboratories; Patel; Willson | [Opinion](https://www.courtlistener.com/opinion/7332474/united-states-v-united-statesplabs-llc/) lists Weingarten in the collective defense roster |
| SEC v. Kelly | John Michael Kelly; Joseph Ripp; Steven Rindner; Mark Wovsaniker | [Opinion](https://www.courtlistener.com/opinion/2151290/securities-exchange-commission-v-kelly/) gives a collective defense roster only |
| Montgomery v. eTreppid | eTreppid; Warren Trepp; other defendants | [Opinion](https://www.courtlistener.com/opinion/1651048/montgomery-v-etreppid-technologies-llc/) lists Weingarten among counsel for defendants |
| U.S. v. Marlinga | Carl Marlinga; James Barcia; Dennis Johnston; Ralph Roberts | CourtListener attorney hit is matter-level; allocation was not resolved |
| U.S. v. Bravo-Fernandez | Juan Bravo-Fernandez; Hector Martinez-Maldonado; other defendants | CourtListener attorney hit is matter-level; allocation was not resolved |

These are relevant, not discarded. They are held at matter level so a later PACER filing or archived appearance can resolve the client without having to rediscover the case.

## Firm-level matters not attributable to Weingarten (`C3`)

| Client/matter | Basis | Why it is not a personal-client claim |
|---|---|---|
| Huawei Technologies corporate prosecutions | Legal 500 and court records | Weingarten's personal appearance is established for Meng; that cannot be silently extended to Huawei corporate |
| Gilbert Chagoury DPA | DOJ DPA identifies Steptoe's Stewart Baker | A separate 2017 email shows Chagoury wanted Weingarten, but final personal allocation is unresolved |
| Hytera Communications | Legal 500 firm work highlight | No personal lawyer attribution |
| Freeport-McMoRan | Legal 500 firm work highlight | No personal lawyer attribution |
| Eight former FTX executives | Legal 500 firm work highlight | Identities withheld and no personal lawyer attribution |
| Control Components | 2019 GIR firm profile | Firm-level matter |
| Barrick Gold | 2019 GIR firm profile | Firm-level matter |
| Linde Group | 2019 GIR firm profile | Firm-level matter |
| Tidewater Marine International | 2016 GIR firm profile | The [profile](https://globalinvestigationsreview.com/survey/foreign-corrupt-practices-act/washington-dc-s-fcpa-bar/article/steptoe-johnson) says Steptoe advised the company on an FCPA internal investigation; it does not allocate the matter to Weingarten |
| Hercules Offshore | 2016 GIR firm profile | The same profile says Steptoe advised the company on an FCPA internal investigation; it does not allocate the matter to Weingarten |
| National Bank of Moldova | 2019 GIR firm profile | Steptoe conducted an international fraud investigation after three banks collapsed; its March 2018 report was delivered to prosecutors, but the profile makes no personal allocation |
| Western Union | 2019 GIR firm profile | The firm represented Western Union in an FTC/state anti-fraud-program investigation and 2017 settlement; no personal allocation |
| Serco | 2019 GIR firm profile | The firm helped Serco agree a £19.2 million UK SFO DPA in July 2019; no personal allocation |
| ExxonMobil; GlaxoSmithKline; Amazon; Monsanto; Nissan; Rockwell Collins; Cameron International; Duke Energy; American Electric Power | 2019 GIR explicit “Clients” roster | The profile lists each as a Steptoe client but does not disclose the matter or allocate the work to Weingarten; Lauren Stevens's personal representation cannot be silently extended to GSK corporate |
| Andrew McCabe | Current Steptoe practice-page highlight | The firm says it obtained a DOJ declination after a two-year investigation; the page does not allocate the engagement to Weingarten |
| MingQing Xiao | Current Steptoe practice-page highlight | The firm says it obtained acquittals on grant-fraud and false-statement charges, with probation on tax counts; the page does not allocate the engagement to Weingarten |
| Patrick Fabian | Facteau/Fabian case publicity | The available release pairs Weingarten and Fabian's co-counsel Frank Libby; it does not clearly allocate Fabian to Weingarten |
| Edward Sullivan | 2013 Steptoe/Law360 profile | `U.S. v. Sullivan` captions also contain Ebbers; no personal Sullivan allocation was established |
| University of Michigan | Initial Robert Anderson misconduct investigation | The [commissioning institution's final report](https://regents.umich.edu/files/meetings/01-01/WH_Anderson_Report.pdf) says the University hired Steptoe in February 2020 and replaced it in March, citing the firm's prior representation of prominent clients accused of sexual misconduct; no source attributes this engagement personally to Weingarten |
| Ofer Paz | Africa Sting FCPA prosecution | A [primary joint defense filing](https://www.nacdl.org/getattachment/47e0ca1f-da47-4915-b619-27995ceb2d5f/defense-mtn-for-evidentiary-hearing-12-7-10.pdf) allocates Paz to Brian Heberlig of Steptoe, not Weingarten; the [firm profile](https://www.steptoe.com/a/web/3844/2013WC.pdf) is therefore retained only at firm level |
| EagleClaw Midstream | Current Legal 500 key client | Listed for the [Steptoe practice](https://www.legal500.com/rankings/ranking/c-united-states/dispute-resolution/corporate-investigations-and-white-collar-criminal-defense/52535-steptoe-llp); matter and personal lawyer allocation not disclosed |
| Ernst & Young | Current Legal 500 key client | Listed for the Steptoe practice; matter and personal lawyer allocation not disclosed |
| Sean Dunn (“Sandwich Guy”) | Federal criminal-defense matter | Listed for the Steptoe practice; public materials attribute the defense to other Steptoe team members, not Weingarten |
| Michael Roeffler | Current Legal 500 key client | Listed for the Steptoe practice; matter and personal lawyer allocation not disclosed |
| Jordan Willing | Current Legal 500 key client | Listed for the Steptoe practice; matter and personal lawyer allocation not disclosed |
| Gianluca Sabbioni | Current Legal 500 key client | Listed for the Steptoe practice; matter and personal lawyer allocation not disclosed |

## Epstein-mediated intake, referral, and consultation

| Subject | Date | Exact status | Downstream result |
|---|---:|---|---|
| Donald Trump / White House | 2017-05-22 | Ashley Parker told Weingarten he was a finalist for outside counsel; Weingarten asked Epstein, “Do I have the choice? And if so, your view?” | No retention found; Marc Kasowitz was selected |
| Michael Flynn | 2017-02-16 | Weingarten had to decide whether to “take flynn” | Public Flynn docket does not list Weingarten/Steptoe |
| Tom Barrack | 2017-05-30 | “maybe I should rep your buddy here” | No checked public appearance |
| Gilbert Chagoury | 2017-07-26 | “wants me to rep him” | Later Steptoe firm role, through Stewart Baker; personal role unresolved |
| Mizrahi-Tefahot Bank | 2018-08-22 | “mizrahi bank wants to hire me” | DPA names Manatt and Gibson Dunn lawyers |
| Wanzhou Meng | 2018-12-26 | “should I take the huawei cfo?” | Positive control: Weingarten appeared in 2021 |
| Rajeev Misra | 2019-01-25 | Asked Epstein for “special jeffrey insights” | No public retention found |
| Ron Soffer | 2019-01-26 | Considered as possible lawyer on “Softbank caper”; Weingarten sought a “book” on him | No engagement found; Soffer was a possible lawyer, not client |
| Arif Naqvi | 2019-06-17 | “Do I want to rep arif naqvi” | No downstream public retention found |
| Stephen Bannon | 2018 | Legal advice and meetings in released messages | Consultation signal only; no engagement proof |
| Leon Black (probable subject) | 2015-07-26 | Epstein suggested “add Levander or Weingarten? relationship to law enf paramount” | Referral suggestion only; the quoted primary email does not name Black or show contact/retention |
| Jared Kushner | 2017-06-23 | Bloomberg reporter: “I'm told on good authority that Jared wants you as his atty” | Third-party rumor; no direct confirmation |

The House, Unified, LMSBAND, and DOJ copies of the same email are one source event, not multiple corroborating sources.

## Specifically tested SoftBank-caper names

| Name | Result |
|---|---|
| Rajeev Misra | Relevant prospective-client signal; outcome unresolved, not irrelevant |
| SoftBank / SoftBank Vision Fund | No Weingarten retention found. Epstein's compressed January 26 message says Brad Karp represented SoftBank, not Misra |
| `DB` | Ambiguous but relevant. It may refer to Deutsche Bank, David Boies, or something else; ambiguity lowers specificity, not investigative relevance |
| Alessandro Benedetti | Weingarten knew the name and called him Epstein's Avenue Foch neighbor; no client/prospective-client evidence found |
| Ron Soffer | Possible co-counsel considered by Weingarten, not a client; no evidence that Soffer was engaged |
| Piyasena Perera | Later shared NYSBA faculty roster with Soffer; no representation, meeting, or campaign-work inference is supported |
| Huawei/Meng | Intake-to-retention positive control |
| Chagoury | Intake-to-later-firm-role mixed control |
| Mizrahi Bank | Intake with a public downstream counsel list that excludes Weingarten/Steptoe |
| Michael Flynn | Intake with no public Weingarten appearance |
| Tom Barrack | Suggestion of representation with no public Weingarten appearance |
| Arif Naqvi | Intake with no public Weingarten appearance found |
| Bruce Deifik | Probable identity of the unnamed “NJ client developer” who bought Revel/Trump's casino; retained only as `C6` inference |

One additional `C6` row preserves, rather than adopts, a recurring public claim about Eric Holder. Breitbart called Weingarten Holder's former personal attorney and attributed that statement to a 2008 New York Times article. Accessible authoritative coverage confirms that the two were close friends, co-founded the See Forever Foundation, and that Weingarten helped prepare Holder for his attorney-general confirmation; it does not identify a personal legal matter. Holder therefore remains an unverified claimed client, not a confirmed representation.

## Unidentified clients and deliberately unresolved matters

Primary records establish three client relationships without a usable identity; strong contemporaneous reporting establishes one more unidentified client; and one primary message supplies an explicit non-client boundary:

- `EFTA00396977` (2013-01-24): Weingarten's assistant said he was in London “with my client.”
- `unified:5033`: Weingarten explicitly wrote “Not my new guy...not repping him.” This is a `T0` affirmative non-client boundary, not an unidentified client.
- [In re Grand Jury Proceedings](https://www.courtlistener.com/opinion/769504/in-re-grand-jury-proceedings-united-states-of-america-v-john-doe/): Weingarten was on the brief for a sealed John Doe appellant.
- [In re Grand Jury Subpoena](https://www.courtlistener.com/opinion/2360075/in-re-grand-jury-subpoena-dated-august-9-2000/): Weingarten represented an unidentified “Republic.” The Steptoe bio separately names Kazakhstan, but the opinion itself does not permit that identification.
- [Washington Post, August 12, 1991](https://www.washingtonpost.com/archive/business/1991/08/12/bcci-scandal-a-windfall-for-attorneys-unlike-any-other/4a6d8c14-6b22-4c95-810f-35836f3e5729/): Weingarten represented an unidentified partner at Clifford & Warnke during the BCCI/First American inquiry. This must not be converted into Clark Clifford, Robert Altman, or another named partner without additional evidence.

The current/archived Steptoe biography also lists 11 high-profile investigations without naming the client:

1. Whitewater
2. Columbia HCA
3. Archer Daniels Midland
4. Drexel
5. Salomon Brothers
6. III Wind
7. BCCI
8. G.E./Israel
9. FDA/generic drug and tobacco
10. House Bank
11. Democratic National Convention fundraising

Three can be connected to named clients with other evidence: ADM to Terrance Wilson, Drexel to Cary Maultasch, and DNC fundraising to Trie/Kanchanalak. The others remain matter-only entries; no client should be guessed from the investigation title.

## False positives and role collisions (`C7`)

The opinion search returned many 1976–1989 cases because Weingarten was a government lawyer. Those defendants are not clients. The excluded groups include:

- Pennsylvania criminal defendants from 1976–1978, where he appeared as a deputy district attorney;
- John Jenrette, George Hansen, William Borders, Walter Nixon, Paul “Bud” Holmes, and Carrol Lynn, where he represented the United States;
- Richard Secord, whom Weingarten prosecuted as part of the Iran-Contra Independent Counsel team;
- Alcee Hastings-related grand-jury litigation, where he represented the United States;
- `U.S. v. Zhang Jian Zhong`, where the opinion merely mentions Weingarten as an information source; and
- `Grimes v. District of Columbia`, where the opinion cites an article coauthored by Weingarten.

Mark Whitacre is not promoted to client: one version of an ADM opinion groups Weingarten with Whitacre, while another version and the appellate opinion allocate him to Terrance Wilson. The conflicting metadata is preserved as `C6`, not erased.

## Source coverage ledger

| Source family | Scope | Result |
|---|---|---|
| Steptoe current bio | Full representative-matters section | 22 named people/entities and 11 unnamed investigation classes |
| Wayback | Bio captures from 2018, 2019, 2021, 2025 | Same roster across captures; no historical names recovered from the page itself |
| Steptoe news/archive/sitemap | Client wins, profiles, awards | Added Maultasch, Harman, Volkswagen, Ali Sadr, Kaloyeros, Mike Lynch, Ireland and matter detail |
| CourtListener exact attorney search | `Reid Weingarten` and `Reid H. Weingarten`, plus the Sudarshan name pivot | 86 result rows, 85 unique dockets, 60 unique captions; many BP and ARCP linked cases |
| CourtListener opinion search | Both exact name forms | 106 result rows, 102 unique clusters; 61 dated 1992 or later before removing citations/collisions |
| DOJ, NARA, and other government records | DOJ releases, signed judgments, DPAs, Senate questionnaire, congressional clemency report, Clinton Presidential Library pardon file | Primary confirmation and counsel allocation for several clients, including Hirschfeld |
| England and Wales Judiciary | 2025 Glencore disclosure judgment | Added Ivan Glasenberg; court quotes Weingarten attending 2023-2024 law-enforcement interviews |
| Contemporaneous news archives | Washington Post, Reuters, Bloomberg, Fox Business, Houston Press and other bounded exact-name searches | Added personal allocations including Sudarshan, O'Brien, Griffin Jones, Steiner, Visclosky, Michael A. Brown, Robert F. Smith, Jacob H. Rivers, and the anonymous BCCI client; retained the Holder claim only as unverified |
| Unified released-email index | 439 Weingarten-linked rows | Intake denominator, direct client references, unidentified clients, and explicit non-client wording |
| LMSBAND | First 500 Weingarten results | Mostly redundant released communications; added unidentified London-client record |
| DOJ Epstein corpus | 18 exact-name results in queried set | 2019 Epstein counsel record and Leon Black-probable referral document |
| House Oversight corpus | 469 path hits before deduplication | Authoritative released copies of intake and client-reference messages |
| FARA | Exact Weingarten search | No registrant/foreign-principal record; this does not exclude legal representation |
| LDA | Exact lobbyist search | No Weingarten lobbyist filing found in bounded query |
| SEC EDGAR | Exact name forms | One VEREIT/ARCP exhibit with service-list email; not a new client allocation |
| FEC | Exact/name-variant search | Three exact individual-contribution records; no client information |
| LittleSis / nonprofit officers / ACRIS | Exact-name search | No new client relationship |
| Legal 500, Chambers, GIR, Steptoe practice page | Current and historical work highlights | Added explicitly bounded firm-level matters and rosters; no practice-level listing was converted into a personal Weingarten client |

## Limits and next records

No public census can be literally complete. Conflict checks, matter-opening records, engagement letters, invoices, pre-charge counseling, internal investigations, and many state/military dockets are confidential or poorly indexed. The proper claim is therefore: exhaustive across the named public sources and query families above, with every ambiguous hit retained at the strongest class the evidence supports.

The highest-yield next records are:

1. underlying PACER/state docket entries for the six `C1-M` matters, to resolve co-defendant allocation;
2. archived state and military appearances for the Steptoe-bio-only clients, especially Lamar Owens, Douglas Jemal, Mark Belnick, Gordon Herman, and Erick Brown;
3. the identity of the January 2013 London client and the unnamed NJ/Revel client;
4. a broader commercial-news archive search for the six still-unmapped Steptoe investigation categories; and
5. any lawful public matter-opening, fee, conflict, or privilege-log record that could resolve Misra, SoftBank, Soffer, Naqvi, Flynn, Barrack, Chagoury, Mizrahi, and Black.

Those gaps should be investigated as unresolved possibilities, not converted into claims of either retention or non-retention.
