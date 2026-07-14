# The April–July 2019 Banking Exit-Ramp — Document-Anchored Reconstruction

**Investigation:** Epstein · **Lead:** #57676 · **Date:** 2026-07-13
**Method:** 5 parallel institution-by-institution primary-corpus sweeps (kabasshouse 1.42M-doc OCR + FinCEN BSAR transcripts, lmsband parsed Fedwire advices, epstein_derived financial model), reconciled against held findings. Reporting treated as SECONDARY throughout.

---

## Executive summary

In the ~90 days before his July 6 2019 arrest — as Deutsche Bank finally pushed him out (accounts closed **July 9 2019**) — Jeffrey Epstein's money moved onto a new set of rails. We can now reconstruct that migration **institution by institution from primary documents**, and it is stronger than the press has reported:

1. **The withdrawn Fidelity SAR is in our primary corpus.** The FinCEN BSAR transcript DOJ published in Jan 2026 then blacked out (ICIJ kept the original) is **EFTA00100894** — with a **penny-exact** itemized ledger the reporting never published: $5,250,650.18 in, $4,870,496.41 out to Puerto Rico banks, two securities to Interactive Brokers, zeroed by 07/18/2019.
2. **The $5M that funded Fidelity is confirmed on both sides** — STC's Deutsche Bank account 44129244 shows the exact 04/17 $2M + 04/26 $3M wires to National Financial Services (Fidelity).
3. **Charles Schwab was an *attempted* $27.66M exfiltration to Morocco that FAILED** — not the ">$20M moved" the press reported. Two wires to a Marrakech real-estate broker via Bank Julius Baer Zurich, both signed by Kahn and Epstein, **both canceled; $0 remitted.**
4. **There were TWO Fidelity accounts** — the STC brokerage AND a Butterfly Trust account opened 8–10 May 2019 by sweeping the closing Deutsche Bank money-market.
5. **The $15M day-after-death wire is answered from a primary FBI document.** It went from an Epstein Deutsche Bank NY account into his **defunct** USVI bank Southern Country International; the FBI opened a §1032 asset-concealment probe (2020) and closed it (2024) without charges.
6. **The $13M USVI prosecutors litigated is the STC → Interactive Brokers wire** (Dec 23 2019), primary-confirmed from the Fedwire advice — and it is a **separate** transaction from the $15M.

---

## The reconstructed flow of funds

### Stage 1 — Deutsche Bank drains the accounts (March–May 2019)
| Date | Amount | From → To | Ref | Source |
|---|---:|---|---|---|
| 03/07–03/29 | **$5,000,000** | Epstein **personal** DB Elite Checking → FirstBank PR ($4.44M) + Banco Popular ($560K) | EFTA01288288 | DB stmt (primary) |
| 03/18 | ~$2,160,000 | DB "2017 Caterpillar Trust" → **Morgan Stanley** "2013 Butterfly Trust" (a/c 622-126989, via Citibank) | EFTA01376935 | DB memo |
| 04/12 | $250,000 | FirstBank check → **Fidelity** STC acct Z40021776 | EFTA00100894 | Fidelity SAR |
| 04/17 | $2,000,000 | STC DB 44129244 → **Fidelity**/NFS | EFTA01288388 | DB stmt |
| 04/26 | $3,000,000 | STC DB 44129244 → **Fidelity**/NFS | EFTA01288388 | DB stmt |
| April | $2,000,000 | STC DB → **Charles Schwab** (via Citibank) | EFTA01288388 | DB stmt |
| April | $1,500,000 | STC DB → **Valar** Global Fund III (via SVB) | EFTA01288388 | DB stmt (corrob #566) |
| April | $4,200,000 | STC DB → Epstein personal DB 35269691 | EFTA01288388 | DB stmt |
| 04/26 | $800,000 | Epstein DB "NOW" → **Southern Country Int'l** @ FirstBank PR (template "JEE to Southern Country") | EFTA01375161 | DB wire |
| 05/03 | swept to $0 | STC DB checking 44129244 emptied | EFTA01372157 | DB stmt |
| 05/10 | $97,828.79 | Butterfly DB money-market 44130552 → **Fidelity**/NFS (2nd Fidelity acct) | EFTA01282009/041 | DB stmt |
| **07/09** | closed | **Butterfly Trust + Jeffrey Epstein DB accounts CLOSED** ("closed today"); others "since May" | EFTA01368889/01372545 | DB emails |
| | | *April STC-DB dispersal total: **$12,937,917*** | | |

### Stage 2 — The new institutions (April–July 2019)
**Fidelity — Account 1 (Southern Trust Company, acct Z40021776).** SAR EFTA00100894. Restricted 05/30; zeroed 07/18.
| Date | Amount | Direction | Counterparty |
|---|---:|---|---|
| 04/12 | $250,000 | IN | FirstBank check |
| 04/17 + 04/26 | $5,000,000 | IN | Deutsche Bank (STC) |
| 05/14 | $650.18 | IN | Pershing LLC |
| 06/11 | $866,905.25 | OUT | FirstBank PR (STC) |
| 06/11 | $1,500,000 | OUT | Banco Popular (Epstein) |
| 06/11 | $2,500,000 | OUT | FirstBank PR (Epstein) |
| 07/02 | $3,591.16 | OUT | FirstBank PR (STC) |
| 07/03 | 2 securities (~$380,153.77 residual) | OUT (ACAT) | **Interactive Brokers** |
| | **IN $5,250,650.18 / OUT $4,870,496.41 → $0** | | |

**Fidelity — Account 2 (Butterfly Trust).** Opened 8–10 May 2019 (email EFTA00495004; application EFTA00299834); funded $97,828.79 from closing DB acct. Trustees Kahn + Kellerhals.

**Charles Schwab — 3 accounts (STC / Southern Financial / Southern Country), opened Apr–May 2019.** SAR EFTA00151545–553 (BSA 31000150416250, filed 07/13/2019).
| Date | Amount | Status | Counterparty |
|---|---:|---|---|
| Apr–May | ~$5,160,000 + securities | IN | DB/FirstBank seed checks, $2M wire, Merrill/TD Ameritrade securities |
| 06/26 | €11,150,000 ($12,708,324) | **ATTEMPTED — retracted 06/27, reversed 07/10 (−$113,527 FX)** | Marc Leon (Kensington Morocco) / Bank Julius Baer Zurich |
| 07/04 | $14,950,000 | **ATTEMPTED — canceled 07/09** | Marc Leon / Bank Julius Baer Zurich |
| | **$27,658,324 attempted / $0 remitted** | | |

### Stage 3 — Death and the estate consolidation (Aug 2019 – Jan 2020)
| Date | Amount | From → To | Ref | Source |
|---|---:|---|---|---|
| **08/11** (day after death) | **$15,000,000** | Epstein **Deutsche Bank NY** → **Southern Country Int'l** (defunct bank) | EFTA00128637 | FBI FD-1057 (primary attestation) |
| Jul–Aug | ~$4,660,568 | Southern Country Int'l → HBRK payroll (TD Bank) | EFTA01596053/595984/596065 | TD stmts |
| 11/20 | $5,566,408.92 | **Indyke PLLC IOLA trust** → Southern Trust Company | EFTA01273155 | Fedwire (txn …869) |
| 11/20 | $4,657,830.34 | **Indyke PLLC IOLA trust** → Southern Country Int'l | EFTA01273122 | Fedwire (txn …883) |
| 12/12 | $9,238,007.10 | 7 HBRK subsidiary wires (LSJE/Zorro/NES/Neptune/Plan D/JEGE/Hyperion) → STC | (DS10) | Fedwire |
| 12/12 | $98,795.45 | Butterfly/Kahn → STC (via **JPMorgan Chase**, not Fidelity) | (DS10) | Fedwire (txn …330) |
| **12/23** | **$13,000,000** | **STC → Interactive Brokers** (Greenwich CT, via Citibank correspondent) | EFTA01273155 | Fedwire (txn …627) |
| 01/13 | $348,667.02 | STC → STC (via Banco Popular) residual | (DS10) | Fedwire (txn …594) |
| | *Estate consolidation total: **~$33M*** | | |

**Terminal resting places:** liquid estate → **Interactive Brokers** ($13M money-market, Greenwich CT — the sum USVI prosecutors litigated); **FirstBank PR** holds residual operating balances ("to Present Day," per the class action); **Banco Popular** holds Epstein a/c 196077567 receipts; the **defunct Southern Country International** absorbed the $15M + $4.66M into a shell whose book value stayed ~$499,759.

---

## The $15M answer

**Recipient: Southern Country International Ltd** — Epstein's defunct USVI International Banking Entity, banking at FirstBank Puerto Rico (ABA 221571473). **Originator:** an Epstein Deutsche Bank Trust Co. Americas NY account (345 Park Ave; RM Stewart Oldfield). **Verbatim** (FBI FD-1057, Case 196D-SJ-3262541, 04/29/2020, EFTA00128637): *"On the day after his suicide, a bank transfer in the amount of $15 million dollars was moved from an EPSTEIN account at the DEUTSCHE BANK in New York and arrived at SOUTHERN COUNTRY."* FBI theory: 18 U.S.C. §1032 asset concealment. Grand-jury subpoena 2020R00037-003 (04/07/2020, USA Gretchen Shappert D.V.I.); probe **closed 02/12/2024**, USAO declining. The channel was pre-established: the identical "JEE to Southern Country" DB→FirstBank-PR template moved $800K on 04/26/2019.

**Correction to the reporting:** the Miami Herald's "~$45M through Southern Country" is not substantiable as SCI-specific — primary docs show ~$20.5M SCI-labeled ($15.8M in + $4.66M out). The rest conflates sibling Southern Trust Company flows. The **$15M (into SCI, Aug 11) and the $13M (STC→Interactive Brokers, Dec 23) are DISTINCT** transactions — different entity, direction, and date.

---

## New findings written (epstein profile, all → lead #57676)

| # | Finding | Confidence |
|---|---|---|
| **#12451** | Fidelity STC SAR (the recovered withdrawn SAR): $5.25M in / $4.87M out / $0 | confirmed |
| **#12454** | Schwab SAR: $27.66M attempted Morocco wires, both canceled ($0 moved) | confirmed |
| **#12455** | $15M day-after-death DB → Southern Country (the answer) | high |
| **#12458** | SCI wire-fraud probe opened 2020 / closed 2024 undeclined | confirmed |
| **#12459** | SCI licensed 2014 / surrendered 12/31/2019 / never operated | confirmed |
| **#12460** | $5M DB→Fidelity funding confirmed both-sides (STC DB acct 44129244) | confirmed |
| **#12463** | DB closed Butterfly + JE accounts 07/09/2019 | confirmed |
| **#12464** | Butterfly Trust's 2nd Fidelity account (opened 5/8–10/2019) | high |
| **#12475** | $13M STC → Interactive Brokers Fedwire (answers the $13M) | high |
| **#12478** | Indyke IOLA trust: two Nov-20 wires ($5.57M STC + $4.66M SCI) | high |
| **#12479** | "JEE to Southern Country" $800K pre-death DB channel | confirmed |
| **#12480** | SCI charter references: Staley + Farkas / JPMorgan + First Bank | confirmed |

**Corrections applied:** #1498 (March PR total $5.0M not $4.38M), #1252 ($13M is not a DB flow), #1461 (broken evidence refs; facts re-verified in #12475/#12478; Dec-12 wire routed via JPMorgan not Fidelity). #12465 retracted for an evidence error and re-added as #12475.

---

## Story-readiness assessment

**Publishable from primary documents TODAY — yes, and it is stronger than what has run.** We hold the withdrawn Fidelity SAR itself (EFTA00100894), with a penny-exact transaction ledger no outlet has published; we confirm the $5M Deutsche Bank funding on the *sending* bank's own statement; we can show Charles Schwab was an *attempted and blocked* $27.66M exfiltration to Morocco (correcting the ">$20M moved" framing); we document a *second* Fidelity account nobody has reported; we answer the $15M day-after-death wire from a primary FBI record and the $13M from the Fedwire advice; and we date Deutsche Bank's final closure to July 9 2019 from its own internal emails. The spine of the story — *at peak public scrutiny, with DB heading for the exit, Epstein's people opened Fidelity and Schwab accounts in April 2019 and ran the money through Puerto Rico to Interactive Brokers, while the defunct Southern Country bank absorbed a $15M wire the day after his death* — rests entirely on primary documents.

**What still needs more than we hold:** (1) the two **Deutsche Bank SAR narratives** (BSA 31000152862375 / 31000155130250) exist only as index entries — the DB SAR *content* is not in-corpus; (2) the **underlying $15M bank/wire record** is attested by the FBI but the DB statement/wire confirmation itself is absent (recover from the DOJ SAR set or SDNY/D.V.I. Rule 6(e) production); (3) the two **securities** ACAT'd to Interactive Brokers are unnamed/unvalued; (4) any **false-statements** claim against Deutsche Bank's NYDFS consent order is NOT supported on our primary evidence — the consent-order text is not local, and the docs prove *late banking*, not a provable false statement (keep this framed as an AML-failure/timeline story, not a criminal-false-statement story). Note the withdrawn Fidelity SAR is no longer a blocking dependency: we already hold its full transcript.

**Recommended next acquisitions:** the two DB SAR transcripts and the Aug-2019 DB statement carrying the $15M debit (Rule 6(e) / DOJ SAR set); Interactive Brokers estate-account disposition (lead #1035); the Schwab Continuing Activity Report narrative (BSA 31000155725098, only p1 OCR'd).
