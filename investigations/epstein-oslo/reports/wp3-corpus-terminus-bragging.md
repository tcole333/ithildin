# WP3 — Corpus terminus, retrospective silence, and the “Oslo Play”

## Summary

The earliest **parseably dated** released-corpus mention of Terje Rød-Larsen is **2010-05-04**: Epstein told staff to call “that guy from the UN,” then asked for his full name; a call was scheduled for May 5. The earliest preserved content routed from Epstein toward Rød-Larsen is **2010-09-28**, and the earliest preserved incoming content from Rød-Larsen’s office is **2010-09-29**. Mona Juul first appears contextually on **2011-03-22** and by full name on **2011-03-27**; the only direct Epstein↔Juul thread found contains three messages, all on **2018-04-21**. No ≤1999 communication was found, so update rule 2 does not fire; because the corpus is left-censored, the late termini do not themselves favor H3.

The bragging test used **1,986 canonical document IDs** with confirmed Epstein↔Rød-Larsen header pairs or explicit relays, spanning **2010-09-28 to 2019-03-18**. Twenty-two documents hit at least one pre-committed retrospective term; six referred to the 1993 channel, but all six were third-party op-eds, articles, or play reviews forwarded by Rød-Larsen or his office. **Zero documents contain an Epstein statement to Rød-Larsen claiming, implying, or reminiscing about an Epstein role in the 1992-93 channel.** This within-coverage silence fires update rule 5 and is a significant update toward H3.

The play verdict is narrower than “Epstein financed the production.” Primary evidence supports Epstein funding an IPI-hosted private performance/ticket buyout: he wrote that he had “anonymously bought out the entire Vivian Beaumont theatre,” and KPMG later found $150,000 from Gratitude America recorded by IPI as “Reimbursement of tickets to the Oslo Play,” plus a separate $100,000 contribution labeled “Oslo Play.” Official production credits name Lincoln Center Theater as producer and do not name Epstein. The evidence therefore supports **funding the May 5 special performance and associated IPI event**, not financing or producing the underlying theatrical production.

This report establishes chronology and describes records; correspondence, funding, or appearance in released files is not by itself evidence of criminal wrongdoing.

## Findings

### 1. Rød-Larsen terminus: planned contact in May 2010; preserved message traffic from September 2010

**Claim (T1; evidence dated 2010-05-04 onward):** the earliest parseably dated corpus hit introducing Rød-Larsen is May 4, 2010. Epstein initially described him rather than naming him—“lets call that guy from the un theja”—then asked staff, “Give me his full name.” Staff answered “Terje Roed-Larsen” and scheduled a call for the next afternoon. This is the earliest dated **any-mention** found and evidence of planned contact, but it does not prove that the call occurred. On May 5, Epstein asked Peter Mandelson whether he knew “Therje Roed-Larsen. --Oslo accord United nations envoy?” and described him as powerful on “both sides”; that is a third-party reference to Rød-Larsen’s Oslo credential, not a Rød-Larsen communication or a claim about Epstein’s own role. Citations: `EFTA01811962`, `EFTA01812397`.

The five earliest distinct preserved routed/dyadic items are:

| # | Internal date | Direction | EFTA/Bates ID | What is preserved | Short quote |
|---:|---|---|---|---|---|
| 1 | 2010-09-28 | Epstein → Rød-Larsen, via staff | `EFTA01811325` | Epstein’s instruction to forward an article; the delivered copy is not preserved | “forward to terje” |
| 2 | 2010-09-29 | Rød-Larsen office → Epstein, via assistants | `EFTA02418985` (mirror: `EFTA00755058`) | Sir Bani Yas agenda and participant list | “From Mr. Terje Rod-Larsen for Mr. Jeffrey Epstein” |
| 3 | 2010-10-01 | Rød-Larsen → Epstein, forwarded through staff on Oct. 4 | `EFTA02419319` | Mallorca hotel/property contact information | “Fw: Hotel in Mallorca” |
| 4 | 2010-10-10 | Rød-Larsen → Epstein, text relay | `EFTA02421192` | Castle/private-beach property offer | “would you be interested in a castle with a private beach” |
| 5 | 2010-10-10 | Epstein → Rød-Larsen, reply preserved in relay thread | `EFTA01979329` | One-word response to the castle offer | “always” |

These are document-internal dates verified against the underlying OCR/text, not release dates. The September 28 item proves an outbound routing instruction, not delivery. The September 29 item is the first preserved content from Rød-Larsen’s office to Epstein. No candidate with a true pre-2010 internal date survived review; apparent 2000/2002 values were parser artifacts caused by truncated 2011/2017 header text.

### 2. Juul terminus: contextual mention in March 2011; only three direct messages in April 2018

**Claim (T1; evidence dated 2011-03-22 onward):** the earliest contextual Juul mention is Epstein’s March 22, 2011 message to Rød-Larsen asking whether “you, mona and the kids” wanted a day trip to Epstein’s island; Rød-Larsen replied, “Will be our great pleasure!” (`EFTA01778859`). The earliest full-name occurrence is a March 27 travel-administration email listing passport details for “Mona Juul” (`EFTA02319920`). That administrative record is an any-mention, not Juul↔Epstein correspondence.

Only one distinct direct Epstein↔Juul thread was found. It contains three messages—not five—so all preserved direct items are reported rather than padding the table with duplicates or third-party forwards:

| # | Internal time/date | Direction | EFTA/Bates ID | Short quote |
|---:|---|---|---|---|
| 1 | 2018-04-21 12:05 UTC | Epstein → Juul | `EFTA02461584` (embedded duplicate in `EFTA02462103`; OCR mirror `EFTA00826783`) | “Mona. If you would like more info on current hospital / surgery plans…” |
| 2 | 2018-04-21 12:16 UTC | Juul → Epstein | `EFTA02462103` (OCR mirror `EFTA00826783`) | “Forever grateful for all you are doing for him (and us).” |
| 3 | 2018-04-21 12:27:55 UTC | Epstein → Juul | `EFTA02462192` (OCR mirror `EFTA00826791`) | “Friendship is my North star… the recommendation is to do surgery in wash.” |

Seven candidate rows collapse to these three message events because forwarded-thread copies and separate OCR corpora repeat the same messages. `EFTA02667734` (Rød-Larsen forwarding Juul contact information) and `EFTA01027124` (a 2019 message from Edward Rod Larsen to his parents with Epstein blind-copied) were excluded because they are not Juul↔Epstein messages.

### 3. Bragging test: 1,986 confirmed correspondence documents, no Epstein claim of an Oslo-channel role

**Slice construction.** I first built a 2,322-ID high-recall candidate envelope using `Terje`, `Rod/Rød/Roed-Larsen`, Epstein sender identifiers, quoted-thread forms, and explicit relay phrases. I then required either (a) a From/To header pair in either direction anywhere in the document or (b) an explicit relay such as “text/message from Terje,” “send/forward to Terje,” or “From Mr. Terje Rod-Larsen for Mr. Jeffrey Epstein.” This produced **1,986 canonical document IDs**:

| Corpus layer | Candidate records with Terje/Rod-Larsen terms | Confirmed header/relay IDs | Notes |
|---|---:|---:|---|
| Kabass House | 9,651 | 1,983 | Primary working layer; richest OCR and metadata |
| LMSBAND | 4,128 | 100 | Mostly mirrors of Kabass EFTA documents; OCR header loss reduces exact classification |
| Unified documents | 67 | 11 | Ten/eleven mirrored documents depending orthographic tokenization |
| Unified parsed emails | 15 | 0 | No exact Terje header pair after excluding the Edward Rod Larsen homonym; raw-document layer preserves the dyad |
| House Oversight 20k | 62 | 4 | Some IDs overlap Kabass/Unified |
| FBI files | 0 | 0 | No Rød-Larsen/Juul name hits |
| **Canonical union** | — | **1,986** | Shared EFTA IDs counted once |

The confirmed slice runs from `EFTA01811325` (2010-09-28) to `EFTA02636787` (2019-03-18). It is a document-ID count, not a count of unique human-authored messages: forwarded chains, office newsletters, duplicate sends, and separate EFTA copies remain distinct released documents. The broader 2,322-ID envelope caught May 2010 introduction material and some third-party Epstein messages about Rød-Larsen; those were useful for the any-mention terminus but were not treated as dyadic correspondence.

**Quantitative result.** Within the 1,986-document confirmed slice, 22 documents hit at least one retrospective term. Six refer to the 1993 channel:

- `EFTA00675787` and `EFTA00675835` — Rød-Larsen/office forwards of the September 2013 “In Praise of the Oslo Accords” twentieth-anniversary op-ed (near-duplicate sends).
- `EFTA00666265`, `EFTA00682502`, and `EFTA00824006` — Rød-Larsen forwards of July 2016 reviews/background about J.T. Rogers’s play.
- `EFTA01024171` — Rød-Larsen’s September 6, 2018 forward of a 25th-anniversary article, “Why Netanyahu Keeps Oslo Alive.”

All six historical references are third-party content. **Zero are Epstein statements to Rød-Larsen about the 1992-93 channel; zero claim or imply that Epstein had a role; zero use relationship-origin language to place their acquaintance in or before 1993.** The remaining 16 term-hit documents concern unrelated Pakistan/Afghanistan back channels, generic “old friend” language, science and finance references to twenty years, or contemporary Middle East coverage.

This is not simply a failure of Epstein to mention Oslo anywhere. Outside the dyad, he marketed Rød-Larsen’s credential to others: the May 2010 Mandelson message (`EFTA01812397`), a 2014 message to Kathy Ruemmler asking about Samantha Power’s view of Rød-Larsen “(oslo accords)” (`EFTA02589823`), and a 2015 proposal to Noam Chomsky describing Rød-Larsen as “oslo accords” and “a very close friend” (`EFTA00845776`, mirror `EFTA02487523`). Those control examples make the absence of self-credit **with Rød-Larsen himself** more probative, while still not proving that no earlier contact occurred.

### 4. Retrospection-term review

“Relevant” below means a confirmed Epstein↔Rød-Larsen document in which the hit actually refers to the 1992-93 channel. Full-corpus totals are deduplicated by canonical EFTA/House/Bates ID across the five local corpus families; the corpus vector gives raw records in **K/L/Ud/Ue/H/F** order (Kabass, LMSBAND, Unified documents, Unified emails, House 20k, FBI). Mirrors are redundancy, not corroboration.

| Pre-committed term | Full-corpus canonical hits | Raw corpus vector K/L/Ud/Ue/H/F | Confirmed dyad hits | 1993-channel relevant | Earliest full-corpus hit and classification |
|---|---:|---|---:|---:|---|
| Fafo | 8 | 5/4/4/0/3/0 | 1 | 1 | 2011-07-14, `EFTA02691515`: FAFO polling newsletter; not relationship history |
| Sarpsborg | 0 | 0/0/0/0/0/0 | 0 | 0 | Null |
| Borregaard | 2 | 1/0/2/0/2/0 | 0 | 0 | 2014-12-09, `HOUSE_OVERSIGHT_023133`: scholarly book proof describing the January 1993 meeting |
| Holmenkollen | 0 | 0/0/0/0/0/0 | 0 | 0 | Null |
| Holst | 11 | 7/1/5/0/5/0 | 0 | 0 | 2013-01-24, `EFTA02318974`: “Holst & Lee” retail homonym; Johan Jørgen Holst appears later in book/play material |
| Abu Ala | 17 | 4/1/11/0/16/0 | 1 | 1 | 2014-12-09, `HOUSE_OVERSIGHT_023133`: retrospective scholarly account |
| Qurei | 8 | 6/4/3/0/3/0 | 2 | 1 | 2012-06-11, `EFTA02720608`: contemporary politics; the other dyad hit is play background |
| Hirschfeld | 21 | 16/8/9/0/10/0 | 1 | 1 | 2013-01-05, `EFTA00398368`: Al Hirschfeld Theatre homonym; later channel material is relevant |
| Pundak | 9 | 6/3/4/0/6/0 | 1 | 1 | 2014-04-13, `EFTA00662852`: article on Oslo negotiator Ron Pundak |
| Beilin | 42 | 15/9/21/0/30/0 | 3 | 2 | 2012-03-05, `EFTA02406470`: Peres/current-politics article; two dyad hits are play history |
| Savir | 16 | 10/8/9/0/8/0 | 3 | 3 | 2014-12-09, `HOUSE_OVERSIGHT_023133`: retrospective scholarly account |
| Oslo near 1993 | 72 | 56/35/23/0/25/0 | 4 | 4 | 2011-05-23, `EFTA01777704`: article recounting the 1993 accords; no Epstein-role claim |
| Oslo accord(s) | 153 | 125/79/33/0/36/0 | 7 | 6 | 2010-05-05, `EFTA01812397`: Epstein asks Mandelson about Rød-Larsen’s credential; third-party, no self-credit |
| Oslo agreement | 25 | 14/10/7/0/16/0 | 1 | 1 | 2012-03-13, `EFTA00930905`: general Oslo implementation/radio-frequency article |
| declaration of principles | 20 | 8/2/14/0/16/0 | 0 | 0 | 2011-07-03, `EFTA02690105`: general newsletter/background; not dyadic retrospection |
| back channel | 85 | 67/40/15/0/26/0 | 4 | 1 | 2009-12-07, `EFTA00743195`: Dubai business back-channel reference; unrelated |
| backchannel | 15 | 13/2/3/0/4/0 | 0 | 0 | 2007-09-21, `DOJ-OGR-00023117`: legal-defense memo; unrelated |
| since we met | 103 | 103/63/0/0/0/0 | 0 | 0 | 2004-03-29, `EFTA02332698`: generic relationship language involving others |
| old friend | 770 | 715/344/74/11/92/0 | 4 | 0 | 2002-08-24, `EFTA02332293`: Nicholas Winton letter; dyad hits are generic and undated as to origin |
| when we first | 292 | 288/157/8/2/7/0 | 0 | 0 | 2004-04-05, `EFTA00579077`: unrelated financial plea |
| known you since | 1 | 1/0/0/0/0/0 | 0 | 0 | 2010-09-30, `EFTA02421045`: Bob Berlin says he had known Epstein since 1980; unrelated |
| 20 years | slice-only | not run as a full-corpus relevance measure | 5 | 0 | 2010-09-28, `EFTA01811325`: forwarded currency article (“past 20 years”) |
| twenty years | slice-only | not run as a full-corpus relevance measure | 1 | 0 | 2013-02-21, `EFTA02723181`: neuroscience article (“twenty years at Caltech”) |

**Added variants (labeled additions):** `Abu Alaa` (1 canonical full-corpus hit), `Ahmed Qurei` (7), `Ahmed Qurie` (1), `Yair Hirschfeld` (8), `Ron Pundak` (9), `Yossi Beilin` (39), `Uri Savir` (11), singular `Oslo Accord` (147), `Oslo peace process` (15), and `twentieth anniversary` (5). These additions produced no Epstein self-credit or earlier relationship-origin statement. `J.T. Rogers` and `J T Rogers` return the same FTS token set and were not summed.

### 5. “Oslo Play” homonym and financing test

The play-thread searches produced the following full-corpus canonical counts and confirmed Rød-Larsen-slice counts:

| Term | Full-corpus canonical hits | Raw corpus vector K/L/Ud/Ue/H/F | Confirmed Rød-Larsen slice | Slice classification |
|---|---:|---|---:|---|
| Bartlett Sher | 5 | 5/5/0/0/0/0 | 4 | 2016 reviews/invitations for the play |
| J.T. Rogers / J T Rogers | 14 (same set) | 13/8/2/0/2/0 | 7 | Playwright references; do not double-count spelling variants |
| Lincoln Center | 697 | 653/324/59/5/57/0 | 8 | Mostly unrelated full-corpus venue hits; slice hits concern the production/event |
| Vivian Beaumont | 54 | 54/23/1/0/0/0 | 1 | `EFTA00681198`, May 5 invitation |
| broadway | 5,707 | 5,283/2,719/205/24/148/320 | 12 | Mostly unrelated full-corpus theater/venue text; slice hits reviewed |
| Oslo play | 23 | 22/11/2/0/2/0 | 1 | Slice hit `EFTA00681198` is the Broadway event |

Every exact `Oslo play` hit was classified as required:

- **(a) J.T. Rogers/Lincoln Center/Broadway play — 16 canonical IDs:** `EFTA00508273`, `EFTA00515333`, `EFTA00516327`, `EFTA00658355`, `EFTA00681198`, `EFTA00786686`, `EFTA00822914`, `EFTA00822919`, `EFTA00822930`, `EFTA01615352`, `EFTA01783789`, `EFTA02363150`, `EFTA02455940`, `EFTA02456457`, `HOUSE_OVERSIGHT_027406`, `HOUSE_OVERSIGHT_027414`.
- **(b) Epstein’s network-operation usage — 7 canonical IDs:** `EFTA00644393`, `EFTA01048625`, `EFTA02352563`, `EFTA02389476`, `EFTA02651487`, `EFTA02651539`, `EFTA02652208`. These reduce to two discussion chains: Epstein offering Tom Pritzker access to “middle east pols” around the play, and coordination with Khalid Jabor for May 5. The phrase uses the performance as a network-convening opportunity, consistent with established finding #138.
- **(c) Other — 0.**

The production/event evidence separates four propositions:

1. **Ordinary ticket purchases are documented.** In July 2016 Epstein’s assistant asked Rød-Larsen for three tickets and said Epstein was “happy to pay” (`EFTA02047288`). In June 2017 four house seats for Eva Dubin cost $588 and were charged to Epstein’s Black Amex (`EFTA02215790`, `EFTA02213959`). In September 2017 staff again said, “We will pay for them of course!” (`EFTA02223201`).
2. **A special May 5, 2017 performance is documented.** Rød-Larsen forwarded Epstein an invitation stating that IPI and Lincoln Center Theater would present “an exclusive performance of OSLO” at the Vivian Beaumont, followed by a discussion with Bartlett Sher, J.T. Rogers, and Rød-Larsen (`EFTA00681198`). Epstein’s calendar calls it “Terje’s Opening of Oslo” and records four seats (`EFTA00450519`).
3. **Epstein claimed a full-theater buyout, and an independent ledger review materially corroborates a ticket/event payment.** In a contemporaneous May 5 email preserved later in the chain, Epstein wrote: “Tonight I anonymously bought out the entire vivian beaumont theatre in order that a majority U. N diplomats could be see OSLO” (`EFTA02344821`; duplicate chain `EFTA02644632`). KPMG’s review of IPI’s general ledger, bank/supporting records, and non-public Schedule B found a May 8, 2017 $150,000 Gratitude America donation recorded as “Reimbursement of tickets to the Oslo Play” and a November 1 $100,000 donation recorded as “Contribution from Gatitude [sic] America, LTD Oslo Play.” KPMG also stated that it found no donor instructions restricting these contributions. [KPMG forensic review, pp. 7-8](https://www.ipinst.org/wp-content/uploads/2020/12/IPI-KPMG-Forensic-Review-12-18-2020.pdf).
4. **Production financing is not established.** The official/industry production records credit Lincoln Center Theater as producer, not Epstein. [Playbill production credits](https://playbill.com/production/oslo-vivian-beaumont-theater-2016-2017), [IBDB production record](https://www.ibdb.com/broadway-production/oslo-509322). LCT’s official announcement describes LCT moving its own production to the Beaumont. [LCT announcement](https://media.lct.org/filer_public/52/21/5221b67f-be29-4e47-9755-ab8bb56b451b/oslo_beaumont_press_announcement.pdf). An archived LCT page for the original Newhouse production names the Doris Duke Charitable Foundation, Edgerton Foundation, Laura Pels International Foundation for Theater, NEA, and Laurents/Hatcher Foundation as supporters; it does not name Epstein. [Archived LCT page, captured 2017-05-09](https://web.archive.org/web/20170509032706/http://www.lct.org/shows/Oslo/). The May 2017 archived Broadway and support pages likewise contain no Epstein name, but that null cannot exclude anonymous support. The public LCT Form 990 contains no Epstein string, while donor Schedule B is not public. [LCT Form 990, FYE 2017](https://media.lct.org/filer_public/14/87/14879d05-51f4-448b-98da-708f8208f40d/lincoln_center_theater_federal_form_990_fye_6-30-17_public_disclosure.pdf).

**Verdict:** primary records support Epstein-linked funding of the May 5 ticket buyout/private performance and an additional play-labeled contribution to IPI—$250,000 in IPI ledger descriptions—plus ordinary ticket purchases. They do **not** show Epstein as a producer or production financier. The T3 formulation that Epstein “financed the play” is therefore supportable only if rewritten as “Epstein funded an IPI-hosted special performance and related play-labeled costs/contributions.”

## Nulls & Coverage

### Person-name coverage for the terminus search

Raw FTS records are shown; the same EFTA document can appear in multiple corpora and Kabass can contain multiple page/document representations.

| Name query | Kabass | LMSBAND | Unified docs | Unified emails | House 20k | FBI |
|---|---:|---:|---:|---:|---:|---:|
| `Terje` | 9,259 | 3,861 | 61 | 10 | 58 | 0 |
| `Rod Larsen` | 3,473 | 1,677 | 26 | 7 | 21 | 0 |
| `Mona Juul` | 37 | 17 | 3 | 0 | 4 | 0 |

The terminus review combined metadata dates, strict four-digit-year parsing of top/forwarded `Date:` and `Sent:` headers, and underlying-document reads. It also searched orthographic variants `Rød`, `Rod`, and `Roed`. No name-bearing document with a valid pre-May-2010 internal header date was found. This null is not evidence against pre-2000 contact because the released email corpus cannot see that period well.

### Financial-table nulls

Kabass `financial_transactions` contains 49,770 rows. Merchant/payee searches returned zero rows for `Lincoln Center`, `Lincoln Center Theater`, `Vivian Beaumont`, and `LCT`. `OSLO` returned three unrelated records: a 2003 Czech-bank merchant string and two extractions of the same 2013 Nordea Oslo loan transfer. The absence is explained in part by the actual payment route: KPMG located the play-related money in IPI’s ledger as donations from Gratitude America, not as a direct Epstein credit-card merchant payment to LCT.

### Coverage limitations

- The confirmed correspondence slice prioritizes specificity. The 2,322-ID high-recall envelope was also searched so that redacted headers and relays would not silently disappear; retrospective candidates were then reviewed against the underlying documents.
- OCR can omit or reorder headers. Unified’s parsed email layer is sparse for this dyad, so raw documents carry most of the evidence.
- Attachments and office newsletters are not all parsed into discrete messages. Counts are document IDs, not unique conversational turns.
- Shared EFTA IDs across Kabass, LMSBAND, Unified, and House are one source. Counts across corpus columns must not be added as corroboration.
- The corpus is left-censored before 2008 and extremely thin in the 1990s. The late terminus is a lower bound on released documentation, not a proven first meeting.
- Archived LCT donor pages are incomplete, and anonymous support would not appear by name. Official credits and KPMG’s IPI-ledger evidence answer different questions: production credit versus funding of a private performance.
- The quick web check did not locate a standalone public LCT 2016-17 annual report/donor roster. The official 2017 Form 990, official show pages/press release, Playbill/IBDB credits, and 2017 Wayback captures were used instead; none names Epstein as producer or production supporter, but those public-name nulls cannot exclude anonymous support.

## Update-Rule Triggers

- **Rule 2 — not triggered.** “Earliest dated Epstein↔Rod-Larsen (or Juul) communication in released corpus ≤1999 → major update H2.” The earliest preserved Rød-Larsen routed/dyadic content is in September 2010; Juul direct messages begin in April 2018. Under the censoring guard, these late dates cause **no H3 update**.
- **Rule 5 — triggered.** “Sustained silence about Oslo across the full Epstein↔Terje corpus → significant update toward H3.” In 1,986 confirmed correspondence document IDs spanning 2010-2019, 22 hit retrospective terms, six contained third-party material about the 1993 channel, and **zero** contained Epstein credit-taking or reminiscence about an Epstein role. This is a significant update toward H3 within the corpus’s actual coverage.
- **Rule 6 — not assessed here.** Retirement requires the combined WP1-WP5 results.

## Proposed Leads

1. Obtain or locate the IPI invoice/ticket manifest and LCT settlement for the May 5, 2017 event. This would determine whether $150,000 purchased all seats, included reception/event costs, or reimbursed a broader package.
2. Resolve the November 1, 2017 $100,000 “Oslo Play” ledger description against IPI’s supporting documents. KPMG says no donor restriction was found, so the label alone does not establish production financing.
3. Search released Gratitude America bank/check records and IPI board/finance correspondence for the May and November payments. The local Kabass merchant table does not capture this route.
4. Preserve the May 4-5, 2010 call-scheduling sequence as a candidate first-introduction lead for external IPI calendars/visitor logs; the corpus does not prove the scheduled call took place.

## Sources Consulted

- `datasets/kabasshouse_epstein.db` via `tools/ingest_kabasshouse.py search`, `doc`, and `financials`, plus read-only SQLite `SELECT` queries.
- `datasets/unified_epstein.db` via `tools/query_unified.py emails/docs` and read-only SQLite header/date queries.
- `datasets/lmsband_epstein_files.db`, `datasets/epstein_files_20k.db`, and `datasets/epstein_fbi_files.db` via their local FTS tables/read-only queries.
- Underlying documents cited above, especially `EFTA01811962`, `EFTA01812397`, `EFTA01811325`, `EFTA02418985`, `EFTA02419319`, `EFTA02421192`, `EFTA01979329`, `EFTA01778859`, `EFTA02319920`, `EFTA02461584`, `EFTA02462103`, `EFTA02462192`, `EFTA00675787`, `EFTA00675835`, `EFTA00666265`, `EFTA00682502`, `EFTA00824006`, `EFTA01024171`, `EFTA00681198`, `EFTA00450519`, `EFTA02344821`, `EFTA02047288`, `EFTA02215790`, and `EFTA02213959`.
- [KPMG forensic review of IPI transactions](https://www.ipinst.org/wp-content/uploads/2020/12/IPI-KPMG-Forensic-Review-12-18-2020.pdf).
- [Lincoln Center Theater official production announcement](https://media.lct.org/filer_public/52/21/5221b67f-be29-4e47-9755-ab8bb56b451b/oslo_beaumont_press_announcement.pdf), [2017 Form 990](https://media.lct.org/filer_public/14/87/14879d05-51f4-448b-98da-708f8208f40d/lincoln_center_theater_federal_form_990_fye_6-30-17_public_disclosure.pdf), and [archived Oslo page](https://web.archive.org/web/20170509032706/http://www.lct.org/shows/Oslo/).
- [Playbill production record](https://playbill.com/production/oslo-vivian-beaumont-theater-2016-2017) and [IBDB production record](https://www.ibdb.com/broadway-production/oslo-509322).
