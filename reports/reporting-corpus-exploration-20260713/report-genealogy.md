# Epstein Reporting Corpus — Scoop Genealogy & Dead Threads

Corpus: `datasets/epstein_reporting.db` (7,775 items). Reporting is SECONDARY; all below are recommendations for primary-doc work, not corroboration. "First reporter" = first appearance *in this corpus* by `published_at` (true first-print may predate our capture). Cross-refs are epstein-profile `investigation.db` findings. Agent: genealogy lens (Claude Fable 5 subagent). Temp work: /tmp/osint-V9bT2NYs/.

## KEY DISCOVERIES

1. **The two 2002-03 profiles (NY Mag #1801, Vanity Fair #1802) are the corpus's origin scoop and still its richest un-chased source.** Ward's VF piece laid out — with SEC/deposition sourcing — the Hoffenberg/Towers Ponzi apprenticeship, the Bear Stearns "Reg D"/St. Joe Minerals exit, a Citibank $20M default suit, the Pennwalt/Riddell/Emery-Pan Am schemes, and the Wexner power-of-attorney, 23 years before the "Epstein files." Ward herself (#1806, 2011) states the girls allegations were in hand in 2003 but "the story didn't really go there" — the corpus's own record of the most famous *cut* thread.
2. **"Belonged to intelligence" — the corpus's most consequential quote has its weakest sourcing.** The Acosta "I was told Epstein 'belonged to intelligence' and to leave it alone" line traces in-corpus only to a **2026 radaronline.com** rewrite (#2013) of Wolff's telling. No contemporaneous primary attribution anywhere in the reporting set.
3. **Southern Trust genealogy is invertible with primary docs we now hold.** Reporting only ever gestured at Southern Trust (first bare mention CBS #6563, Jan 2020; real detail not until 2025-26 Drop Site/Lutnick/ICIJ files). Our findings already hold the wire anatomy (#219, #1272, #1302, #1336, #565) — Deutsche Bank acct 44129244, FirstBank USVI, the Dec-2019 Interactive Brokers liquidation. The corpus never told the money story.
4. **The bank-onboarding timeline is a clean, underwritten scoop.** ICIJ #12 (Jun 2026) is the first item to assemble the full chain: JPMorgan to ~2013 → Deutsche Bank to 2019 → then **Fidelity AND Charles Schwab both opened accounts April 2019** (post-Miami-Herald, mid-renewed-scrutiny), routing millions to Banco Popular/FirstBank PR and Interactive Brokers weeks before arrest. Fidelity/Schwab/PR-bank onboarding near-zero in prior coverage.
5. **Ehud Barak/Carbyne(Reporty) intelligence-startup funding via Southern Trust was broken early** (Haaretz via Times of Israel #2223, 11 Jul 2019) then went quiet until 2025-26. Nobody married it to the Southern Trust wire records until Drop Site (2025). Carbyne pre-2024 count = 1.
6. **Multiple early "enabler-economics" threads died at the Palm Beach stage and were never revived with documents that now exist:** the $90K firearms-simulator PBPD donation (last 2008), "jack shacks"/PBPD-hats-on-dashboard (Daily Beast 2010), Ballet Florida $100K "for massages" (dead 2006), charity inflation (NBC #7191).
7. **Corpus lineage is shallow:** `item_relation` = 1,107 rows, ALL exact-hash `duplicates`, zero `follows_up`/`corrects`/`retracts`. Dead-thread detection must be term-frequency era-splitting (the method used), not stored lineage.

## EARLY-ERA FACT INVENTORY

Read in full: all ~37 JE-relevant pre-2015 English items. (~74 Dutch NRC items are Jacob/Brian/Julius/Mitch Epstein homonyms — art/Beatles/NYRB — confirmed noise; NBC "Today in history"/allergy items likewise.)

| # | Assertion | Source / date | Still-true vs findings | Pursue? |
|---|-----------|---------------|------------------------|---------|
| E1 | Runs "$15B for wealthy clients," flat ~0.5% fee, sole named client Wexner, takes only $1B+ accounts | NY Mag #1801 (2002-10-28) | Unverified then/now; Forbes #2164 (2010) debunks "billionaire" | Yes — founding myth vs traced flows |
| E2 | Calls "private banker at JPMorgan" every morning | NY Mag #1801 | Corroborated — JPM ran to ~2013 (ICIJ #12) | Context |
| E3 | Real mentor = **Hoffenberg/Towers** ($450M Ponzi); Epstein "executed all instructions"; intro by Douglas Leese OR John Mitchell | VF #1802 (2003-03) | Structurally corroborated; #2085/#2102 (Gold shielded Epstein from Towers prosecution). Hoffenberg d.2022 | **Yes** |
| E4 | Left Bear Stearns 1981 amid SEC St. Joe Minerals probe + "Reg D" ($20K loan to W. Eisenstein) | VF #1802 | Never charged; SEC testimony quoted verbatim | Yes — 1981 SEC file |
| E5 | **Citibank sued Epstein for $20M loan default (~2002)**; he claimed "fraudulent inducement" | VF #1802 | Not in findings | **Yes** — earliest bank litigation, predates DB/JPM ~18 yrs |
| E6 | Wexner gave Epstein **power of attorney/fiduciary over all trusts**; put him on Wexner Fdn board over Bella Wexner (1992); town house via trust $13.2M (1989) | VF #1802; NY Mag #1801 | STRONGLY corroborated — #486 (ACRIS PAT Abigail Wexner→Indyke), #484 | Context |
| E7 | 1988 net worth $20M ($7M securities, $1M cash, $11M other incl. Riddell); Wexner co-signed Riddell indemnity | VF #1802 (Municipal Arts Society lease filing) | Not in findings | Yes — early net-worth primary doc |
| E8 | Pennwalt/Riddell/Nederlander/Toboroff stock schemes; Dick Snyder (S&S) pulled in; money secretly from Hoffenberg | VF #1802 | Not in findings | Maybe |
| E9 | 1998 US Attorney sued Epstein for illegally subletting ex-Iranian-consul (State Dept) home, overcharging Ivan Fisher | VF #1802 | Corroborated adjacent — #2034 (1998 USA v. Epstein 96-cv-8307) | Context |
| E10 | Self-described "bounty hunter"; 1989 depo: 80% of time recovering stolen money; International Assets Group from Solo bldg | VF #1802 | Not in findings | Yes — undocumented era |
| E11 | **$1M wire to Brunel's offshore acct Sep 2004** as MC2 launched; MC2 85% Brunel/15% Jeff Fuller; offices NY/Miami/Tel Aviv | Daily Beast #1805 (2010-07-22) | Partial — Brunel #905/#3212 + active leads; specific wire not in findings | **Yes** — traffick-financing wire |
| E12 | Alfredo Rodriguez kept $2,000 cash always on hand; jailed LONGER than Epstein for trying to sell his "golden nugget" notebook | Daily Beast #1805/#2163 | Dormant; "black book" pre-24=11 | Yes — notebook vs flight logs |
| E13 | PBPD $90K (firearms simulator) + $100K equipment; PBPD hats for dashboards to dodge tickets; $100K Ballet Florida "for massages" | PBP #1817/#1821, DB #1805 | Dead post-2010; not in findings | **Yes** — police-capture economics |
| E14 | "Three 12-yr-old French girls as a birthday gift"; ~40 FBI victims back to 2001; MC2 girls E. Europe on jets | Daily Beast #2163 (2010) | Recruitment corroborated; "French birthday" single-thread civil-suit sourced | Verify — high-shock, thin |
| E15 | Marcinkova imported "at 14" as "Yugoslav sex slave"; jail visits (4x/13 days); Kellen 3x | PBP #1830, DB #1805 | Corroborated | Context |
| E16 | Roger Schank (AI, Trump U "chief learning officer") + Igor Zinoviev (MMA) among jail visitors | PBP #1830 | Dead (2008) | Low |
| E17 | Deferred/non-prosecution agreement sealed; feds drop federal probe as part of state plea | PBP #1832/#1834 | Fully corroborated (became Acosta scandal) | Context |
| E18 | Epstein moved to **triple** Little St. James residence (underground theater) fall 2007 *while* negotiating NPA | NBC #7257 (2019-07-30) | Not in findings | Yes — USVI DPNR permit file |

## DEAD THREADS

Method: pre-2024 vs ≥2024 FTS counts. Val = pursue-priority 1-3.

| Thread | Originating item(s) | Last seen | Why it died | Resurrection path (primary docs we now hold) | Val |
|--------|--------------------|-----------|-------------|----------------------------------------------|-----|
| "Belonged to intelligence" provenance | radaronline #2013 (2026) rewriting Wolff | 2026-06 | Never had documentary anchor | Trace every appearance; adjudicate vs held House Oversight Acosta/Barak transcripts | 3 |
| Citibank $20M default suit (~2002) | VF #1802 | 2003 | Pre-digital docket, buried under later banks | Pull NY/SDNY docket; earliest Epstein bank litigation | 3 |
| Fidelity + Schwab April-2019 onboarding | ICIJ #12 (2026); Schwab pre-24=0 | 2026-07 | Only surfaced via late-2026 DOJ SAR (later pulled) | Marry SAR to our wire map (#1272/#1336) — "who banked him in the final 90 days" | 3 |
| Charity inflation (Gratitude America/Enhanced Education/Florida Science Fdn) | NBC #7191 (2019); Enhanced Ed last 2019 | mostly pre-2024 | NBC did once, arrest/death buried it | Rebuild claimed-vs-true ledger via EINs/officers/FirstBank PR acct (#23/#29/#565) | 2 |
| PBPD capture economics ($90K simulator, dashboard hats, Ballet Florida) | PBP #1817/#1821; DB #1805 | 2010 | Small-dollar, pre-arrest, local | Reiter 9-hr civil depo + PBPD donation records | 2 |
| Island expansion during NPA negotiation | NBC #7257 (2019) | 2019 | One-off, overtaken by death | USVI DPNR 2007 Maguire Group permit file | 2 |
| Hoffenberg/Towers "govt was lazy, never deposed Epstein" | VF #1802 | Hoffenberg d.2022 | Source now dead; complex 1990s facts | SDNY/Illinois insurance-regulator files; #2085/#2102 spine | 2 |
| Rodriguez "golden nugget" notebook | DB #1805 (2010) | fading | Rodriguez died | Cross-read notebook names vs released flight logs + DOJ files | 2 |
| OSU/Abigail Wexner/Maria Farmer 1996 | NBC #7220 (2020) | REVIVING 2025-26 | Dormant 2020-24, now live again | #2868 (1996 FBI report EFTA00006107 in DOJ release) | 2 |
| FBI "beauty pageant" arrest (May 2007 USVI) | NBC #7408 (2020, DOJ-OPR) | 2020 | Buried in 347-pg report | OPR report is primary, in hand | 1 |
| Surveillance video "no longer exists"/wrong-tier | NBC #7463 (2020) | 2020 | Accepted clerical; Tartaglione case closed | BOP/MCC records + Tartaglione docket | 1 |
| Kirkland & Ellis conflict web (Barr/Rosen/Harris) | CBS #6632 (2019) | 2021 | Partisan-flavored, faded | FEC + firm-conflict mapping | 1 |

## SCOOP GENEALOGY

| Fact | First reporter / date | Attribution basis | Channel notes |
|------|-----------------------|-------------------|---------------|
| Wexner **power of attorney** | **NY Mag #1801 (2002-10)**; detailed VF #1802 (2003-03) | "source close to Wexner"; SEC/lease filings | Founding scoop; all later re-derive 2003 VF |
| **Hoffenberg/Towers** apprenticeship | **VF #1802 (2003-03)** | Grand-jury testimony, 1989 depo, SEC docs, named ex-execs | Ward's document work; unmatched 16 yrs until CBS #6615 (2019) |
| **Intelligence connection** | **radaronline #2013 (2026-06)** in-corpus | Wolff retelling of Acosta anecdote | WEAKEST channel of any major claim |
| **Staley/Epstein** | **Guardian #1334/#1335 + CBS #6560 + NBC #7442, all 2020-02-13** | UK FCA regulator probe | Simultaneous cluster off one regulatory event |
| **Deutsche Bank** $150M | flags NBC #7530 (2019-08); substance **Guardian #1295/CBS #6466/CNBC #7400, 2020-07-07** | NYDFS consent order | Consent-order-driven, syndicated same day (one source) |
| **JPMorgan retention to ~2013** | named early (NY Mag #1801, 2002); cutoff framing **ICIJ #12 (2026)**; litigation NBC #7121 (2023) | USVI v. JPMorgan; ICIJ SAR review | "~2013" is a 2023-26 litigation artifact |
| **Southern Trust** $200M/USVI tax vehicle | bare name CBS #6563 (2020-01); substance **Drop Site #41 (2025-11)+CBS #5817+Al Jazeera #2328 (2026-02)** | DOJ files, Barak email DB, WSJ proposal | Our findings beat corpus on wire detail by years |
| **Ehud Barak/Carbyne** | **Times of Israel #2223 (2019-07-11)** crediting **Haaretz** | Haaretz + Barak on-record confession | Cleanest early foreign-desk scoop |
| **Leon Black fees** ($158M→$170M, 2012-17) | **NBC #7399 (2021-01-26)** | Apollo-commissioned Dechert report | Company review as source; USVI later subpoenaed |
| **Interactive Brokers/Fidelity accounts** | **ICIJ #12 (2026-06-01)** | DOJ-released SAR (withdrawn) | We already had IB in #1272 |
| **$577M will 2 days pre-death** | CBS #6607/NBC #36 (2019-08-19) | Court-filed will (1953 Trust) | Probate filing, syndicated |
| **$350K witness-tampering wires** | NBC #7469 (2019-07-12) | SDNY detention memo | Prosecution-filing-driven |
| **Charity donations exaggerated** | NBC #7191 (2019-07-11, Strickler) | NBC's own 56-charity canvass | Rare non-document shoe-leather scoop |

**Who got there first, consistently:** (1) Vanity Fair/Vicky Ward (2003) — finance/Hoffenberg/Bear Stearns/Wexner POA; (2) Palm Beach Post/Larry Keller (2006-08) — the criminal-case spine, police-report sourced; (3) Miami Herald/Julie K. Brown (2018-11, items #45/#46/#77, metadata-only/[NO TEXT] here) — reactivated the saga; (4) NBC investigative/Tom Winter (2019-20) — jail-death, island permits, DOJ-OPR; (5) Times of Israel/Haaretz — the Barak/Carbyne channel; (6) ICIJ/Drop Site (2025-26) — DOJ-files-era bank/Southern Trust genealogy.

## SINGLE-OUTLET ORPHANS

1. **"Belonged to intelligence"** — radaronline #2013 only. Check: held House Acosta transcript; Wolff source tapes.
2. **Citibank $20M default suit** — VF #1802 only. Check: NY/SDNY docket ~2001-02.
3. **1988 net-worth statement $20M** — VF #1802 only (lease filing). Check: NY County case file.
4. **$1M Sep-2004 wire to Brunel offshore** — Daily Beast #1805 only. Check: released bank records; MC2 filings.
5. **"Three 12-yr-old French girls birthday gift"** — Daily Beast #2163 only (civil-complaint). Check: complaint + flight logs.
6. **Ballet Florida $100K "for massages"** — Daily Beast #1805 only. Check: Ballet Florida 990s.
7. **PBPD hats on dashboards** — Daily Beast #1805 (Rodriguez depo) only. Check: Rodriguez depo transcript.
8. **Cecile de Jongh (USVI First Lady) $300K+ Southern Trust severance** — NBC #7278 (2023) only. Check: USVI v. JPMorgan exhibits (strong, underused).
9. **Fidelity emptied via Banco Popular/FirstBank PR + Interactive Brokers days pre-arrest** — ICIJ #12 only. Check: withdrawn DOJ SAR; #1272/#1336.
10. **Marcinkova imported "at 14," family paid** — PBP #1830 only, never adjudicated. Check: complaint; visa records.
11. **Spacey/Tucker/Casey Wasserman/Ron Burkle on 2002 Africa 727** — VF #1802/NY Mag #1801. Check: flight logs (held).
12. **FBI "wanted to arrest at USVI beauty pageant May 2007"** — NBC #7408 only. Check: 347-pg OPR report (obtainable).

## STORY ANGLES (ranked)

1. **"The story already written in 2003"** — reconstruct VF #1802's finance-crime skeleton + Ward's own 2011 cut-thread admission (#1806) vs what 2024-26 DOJ files confirmed. Uniquely ours (early corpus text + modern findings).
2. **The final-90-days banking sprint (Apr-Jul 2019)** — Fidelity+Schwab onboarding during peak scrutiny → PR banks → Interactive Brokers days pre-arrest. ICIJ #12 + our wire map.
3. **Provenance audit of "belonged to intelligence"** — biggest claim, flimsiest chain; adjudicate with held House transcripts.
4. **Southern Trust/Carbyne/Barak intelligence-tech funding** — marry 2019 Haaretz scoop to wire records the corpus never connected.
5. **Charity inflation ledger** — comprehensive claimed-vs-actual rebuild (NBC did 56 once); we have EINs/officers/accounts.
6. **Police-capture economics of Palm Beach (2005-08)** — resurrectable via Reiter depo + PBPD records.
7. **OSU/Abigail Wexner/Maria Farmer 1996** — already reviving; #2868 (1996 FBI report EFTA00006107 in DOJ release) is the live anchor.

## DEAD ENDS

- **Dutch NRC pre-2015 (~74 items):** homonym noise (Jacob/Brian/Julius/Mitch Epstein, NYRB's Barbara/Jason Epstein) — not the financier. Excluded.
- **NBC "Today in history"/allergy/Golden Globes/impeachment items:** swept in by the queryly crawl, no Epstein content.
- **item_relation lineage:** all 1,107 rows exact-hash `duplicates`; no follows_up/corrects/retracts — can't drive detection.
- **Miami Herald "Perversion of Justice" core (#45/#46/#77, #57-#76):** metadata present but `content_text` empty/[NO TEXT] — index only, read from primary Herald archive.
- **WSJ #26 ("WSJ, Feb 26 2020"):** placeholder, no body.
- **Peter Listerman, Melanie Walker, Celina Dubin, Liquid Funding, D.B. Zwirn, Aviloop, Gary Roxburgh:** zero corpus hits — never in this reporting set (pursue via primary sources, not reporting).
- **Prince Andrew/Giuffre/Maxwell-trial:** saturated across every era; no scoop-genealogy value.
