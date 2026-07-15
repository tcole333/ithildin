# Multilingual Epstein-Reporting Intelligence Sweep

Corpus: `datasets/epstein_reporting.db` (read-only). Agent: multilingual lens (Claude Fable 5 subagent). Cross-referenced against `investigation.db` via **direct `findings_fts` MATCH** — critical methodology note: the active profile is `richard-merkin`, so `findings_tracker.py search` returned FALSE NEGATIVES on epstein-profile findings. Every absence claim below was re-verified against the profile-agnostic `findings_fts` index and `person_resolution.py`.

**Big picture:** The English corpus already holds the marquee facts (Barak/Carbyne, Ruemmler, Southern Trust/EdR, Norwegian probes, Prusakova, Seckel, Kellerhals, Joi Ito, Marrakech palace). Non-English reporting adds two things: (a) **national-jurisdiction actions** — prosecutors/parliaments/regulators moving in France, Norway, Poland, UK, Austria, USVI; and (b) a layer of **local named actors** (recruiters, models, victims, bankers, doctors) confirmed in the primary DOJ docs via `person_resolution` but never written up as findings. Richest veins: **French** (original Le Monde/Libération/Franceinfo reporting) and **German-Austrian** (Der Spiegel/Standard, Die Presse).

## KEY DISCOVERIES

1. **France — PNF corruption case + Rothschild-bank raid over diplomat Fabrice Aidan** (Le Monde #90/#4028, fr). PNF raided Banque Edmond de Rothschild's Paris HQ 24 Mar 2026, investigating Aidan for bribery of a foreign public official. Aidan appears 200+x in Epstein correspondence (person_resolution #25010, 134 mentions); our findings have 1 incidental FTS hit. A live state action, essentially untracked.

2. **The 62-name "victim census" Excel seized at 22 avenue Foch** (Franceinfo #4028, fr). CD-ROM "Confidentiel – Tableau complet," Excel last-saved 13 Jun 2007, lists 62 women tagged "o"(over-18)/"u"(underaged) with explicit act columns including one headed **"contact sexuel (2246(3))"** — the US federal statutory definition, implying it was built for his US defense. Named victim Haley Robson confirmed she'd never seen it. DOJ requested a copy via MLAT Jan 2021. Absent from findings.

3. **Norway — five simultaneous elite probes + an Epstein heir's suicide** (VG/Aftenposten/Expressen #2236, sv). New beyond our holdings: Epstein bequeathed **$10M to the Rød-Larsen/Juul twins**; son **Edward Juul Rød-Larsen (25) died by suicide** (Apr 2026); the Palace admitted Crown Princess **Mette-Marit's email account (broadpark.no) was deleted and unrecoverable**, password leaked in the 2012 Dropbox breach. We track the probes/bequest/Mette-Marit but NOT the death or the email forensics.

4. **Ivory Coast — Nina Keita brokered a state surveillance-system purchase + presidential Boeing 727** (Le Monde #1542, Al Jazeera #1810, ar). Keita (Ouattara's niece, now #2 at state oil-fund manager **Gestoci**) introduced Epstein to Ouattara, brokered the 2014 Israeli surveillance system + Boeing 727 for the presidency, and presented women. Arabic coverage adds **Karim Wade** (Senegal) and **Kagame** (Rwanda) outreach. ZERO findings on Keita/Gestoci/Ouattara/Kagame/Wade — the clearest structural gap.

5. **Barak/Carbyne export back-channel + Axon $625M exit** (Al Jazeera Arabic #1810, ar). Ties Ariane de Rothschild's $25M Southern Trust contract + Reporty→Carbyne (Barak chairman) + **Axon's Nov 2025 $625M Carbyne acquisition**, framed as an Israeli cyber-surveillance export channel evading the DECA/Pegasus licensing regime. Components tracked individually; the Axon exit + export-evasion synthesis is new.

6. **Austria — dense financial node** (Der Spiegel/Standard #1738/#1744, Die Presse #4465, de). €2,750 via **UniCredit Bank Austria** to a Wiener Wohnen-linked GmbH (ordered by Indyke); **13.7M-rouble transfer via Raiffeisen Bank Intl Vienna to Moscow** (2015, ref. Bella Klein); paid Vienna tuition for a victim; funded the Vienna think-tank IPI; **secret undeclared 5-hr Vienna trip Mar 2019**; 2018 Bannon-Epstein emails re meeting Chancellor **Kurz** (denied; Standard retracted an overstated version — framing caution).

7. **Denmark/Netherlands national model-agency nodes** (Avisen.dk #2402, Nieuwsuur #2567, NRC #4907). Danish house **Scoop Models** (founder Bente Lundquist) + Latvian **Lana Zakocela**; Dutch **Yfke Sturm** ("you owe me two girls") + **Sylvia Geersen**, 10 Dutch women, confirmed Epstein co-financed **MC2 Model Management**. Absent from findings.

8. **Tunisia — $15M Tunisair aircraft purchase attempt + 2009 Tunis pageant infiltration** (Independent Arabia #5323, ar). USVI shell "involved in transporting victims" offered $15M for a Tunisair jet demanding logo removal + total secrecy. Tunisia in 366 emails. Zero findings.

9. **Poland — govt inter-ministerial team + TVN24's custom "JEDD" AI reconstructing the Warsaw route** (TVN24 #2291/#1773, pl). Poland officially confirmed trafficking activity on its soil; women flew from **Warsaw Chopin 2014-2019** on Epstein's schedule (via Groff). Local figure: **Wojciech Fibak** (denies).

10. **UK — Gordon Brown's police-probe campaign + Essex Police Stansted inquiry** (Independent Arabia #5210/#5324, Die Presse #4436). Brown's 5-page letters to six forces allege girls flown via **Stansted** (~90 UK flights, 15 post-2008) and **RAF Marham** use (Dec 2000 Gulfstream→Sandringham); Met **royal-protection officers helped secure a 2010 Epstein dinner** with Andrew. "Stansted" = 0 findings.

## PER-LANGUAGE INVENTORY

- **French (478):** richest, original reporting. Full French judicial track (Lang laundering, Aidan corruption, avenue-Foch Excel). Untracked actors: **Daniel Siad** (recruiter, 3 identities), **Gérald Marie**, **Olivier Colom**, **Frédéric Chaslin**, **Simon Ghraichy**, **Nicolas Princen**, **Axel Dumas** (Hermès), **Steve Tisch**; doctor network **Eva Dubin/Jess Ting/Steven Victor/Peter Attia**; BNP Paribas account 2008-18; Accor/Bazin (Grizzly short).
- **German (380):** Austria complex; **Sal. Oppenheim** (Epstein eyed buying it 2009), Deutsche Bank, UBS-kept-Maxwell; academics **Martin Nowak**/**Karl Sigmund**; FIS/IOC's **Johan Eliasch**; Karl-Erivan Haub disappearance link (speculative); Slovakia's **Fico**.
- **Arabic (442):** Tunisia, Africa three-layer analysis, DP World/bin Sulayem, the Barak/Carbyne/Axon piece. Heavy UK-royal syndication otherwise.
- **Russian (357, Kommersant compromised):** regional-Russia color — **"Miss Tolyatti" Anastasia B.**, **Shtorm Models Krasnodar**, Sochi/Rostov mention-counts; Georgian **Elena Kantaria** + **Kakha Bendukidze**; Romanian painter **Ion Nicola**. FRAMING ARTIFACTS: Dmitriev "SPIEF replaces Davos," Zakharova/Lavrov "monsters are in the West," Iran-ambassador "Epstein cult sacrifice."
- **Portuguese (482):** Brazil victims **Marina Lacerda**; BBC Brasil's Brazil/Ecuador route — **Gláucia Fekete**, **Aline Weber**, **Models New Generation** pageant; elite-schools piece names **Joscha Bach**.
- **Spanish (410):** **Barcelona** as Siad's base (View Management, Uno Models); La Nación — **Epstein negotiated a helicopter sale to the Argentine government**; **Summers resigned from Banco Santander's advisory board**; Al Fayed French probe.
- **Dutch (278):** Sturm/Geersen/MC2 recruiting.
- **Scandinavian (da/sv/nb):** Scoop/Zakocela; **King Frederik** named twice (via Osborne, attendance unconfirmed); **Princess Sofia** admits 2 meetings; Swedish UNHCR chair **Joanna Rubinstein** resigned; **Nadia Marcinko** re-scrutiny.
- **Italian (87):** Al Seckel (Isabel Maxwell's partner, reputation "cleaner," found dead) — mostly derivative.
- **Hungarian (Telex):** genuine local desk — Budapest visits, Király utca apartment, **Barabási Albert-László**, Epstein-Bannon-**Orbán** emails ("Europe terrified of Orbán," misspelled "Orbahn").
- **Greek/Korean/Japanese/Turkish:** Southern Country Intl (in.gr, tracked); Philippine SEO (Yonhap, tracked); Joi Ito (President Online, tracked); Ben Black/DFC (Anadolu, partial).

## NEW ENTITIES (absent from `entities`/`findings`; verified via `person_resolution`)

HIGH: **Nina Keita** (person #1122) | **Daniel Siad** | **Gérald Marie** | **Fabrice Aidan** (person #25010). MEDIUM: Gestoci, Karim Wade, Marina Lacerda, Gláucia Fekete/Aline Weber, Joscha Bach, Yfke Sturm/Sylvia Geersen, Lana Zakocela, Joanna Rubinstein, Benny Shabtai (person #9312), Steve Tisch, Jess Ting/Steven Victor, Barabási Albert-László. LOW: Elena Kantaria (#23311), Kakha Bendukidze, Ion Nicola, Scoop Models/Lundquist, View Management/Uno Models/MC2, Eva Dichand, Beatrice Coyle.

**Already tracked — do NOT recreate:** Ian Osborne (#587), Boris Nikolic (#4404), Glenn/Eva Dubin, Kathryn Ruemmler (#3722), Carbyne (#223), Melanie Walker, Al Seckel, Erika Kellerhals, Joi Ito, Maria Prusakova, Bella Klein, Indyke, Kahn, Sultan bin Sulayem (#3513), Brunel (#3496).

## JURISDICTIONAL LEADS

France PNF (Lang laundering, Aidan corruption, EdR raid, IMA searches); Norway Økokrim (Jagland/Juul/Rød-Larsen, immunity-lift, parliamentary commission — heir death + deleted email untracked); UK Essex Police Stansted + Brown's RAF-Marham/Met-officer campaign; Poland inter-ministerial team; Austria (Vorarlberg/Montafon email, passport, ÖAW/Nowak); USVI AG subpoenas to **Bank Leumi** + 6 US banks; Argentina helicopter-sale; Council of Europe/ECHR (Karim Wade case-routing).

## NEW CONNECTIONS (non-English only)

Epstein↔Ouattara (via Keita) + Ivory Coast govt↔Israeli vendor; Carbyne↔Axon ($625M); Southern Trust↔EdR↔Carbyne triangle; Bazin(Accor)↔Epstein (weak, 2nd-hand via Chaslin — flag unverified); Siad↔Marie↔Brunel Barcelona/Paris triangle; Summers↔Banco Santander; Ben Black↔ESWW; Epstein↔King Frederik (unconfirmed); Epstein↔Princess Sofia (confirmed); Bannon↔Orbán; Bendukidze↔Epstein.

## STORY ANGLES (ranked)

1. **African surveillance-tech-for-access channel** (Keita/Ouattara + Israeli systems + Wade/Kagame) — entirely unbuilt; verify via Keita's primary emails (person #1122).
2. **France's live criminal cases as a corroboration engine** — avenue-Foch §2246 Excel + Aidan's 200+ corpus mentions are checkable now.
3. **National model-agency franchise map** (Scoop/DK, Sturm-MC2/NL, View-Uno/Barcelona, Ecuador pageant).
4. **Barak/Carbyne→Axon $625M exit + export-evasion frame** — acquisition is public/SEC-checkable; treat intel framing as hypothesis.
5. **Austria financial node** — UniCredit/Raiffeisen transfers with dates+ordering party; Kurz angle needs caution (Standard retraction).
6. **Norwegian heir's suicide** — Norwegian-press-only, sensitive, don't overreach.

## DEAD ENDS (pure syndication, no local content)

Indonesian (ANTARA — mostly mis-scoped domestic news), Finnish (Yle — Maxwell wire), Czech (Novinky — agency + one off-topic item), Romanian (Digi24 — agency; its only local actor came via Russian press), Hindi (AajTak — wire), Chinese (UDN — wire). **DW Arabic/Russian** = translations of DW's own German copy (count as one source with German). **Kommersant "Zarubezhnye SMI"** column = explicit digest of other outlets, state-aligned framing — never independent.
