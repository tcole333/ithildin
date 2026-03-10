# Investigation Context

Agent orientation data — wave results, critical intelligence, registry findings. Not auto-loaded — read on demand. For full wave detail see `investigations/epstein/wave-results.md`.

## Analysis System
- **Pipeline**: gather -> store -> analyze/synthesize -> hypothesize -> gather more
- **Tools**: hypothesis_tracker.py, tag_manager.py, event_timeline.py (98 events 1985-2024), graph_tools.py, analysis_export.py
- **Thread population**: All 2,810+ findings classified into 7 threads (scripts/populate_threads.py). T1=2009 core, T2=114 Mega, T3=226 DB, T4=62 Israeli, T5=252 Apollo, T6=185 Gulf, T7=K&E
- **Graph stats**: 799 nodes, 1292 edges, 12 components, largest=769, avg degree=3.23, max degree=278 (Epstein). K&E=#3 degree (47), #5 betweenness (0.077), brokerage=0.967
- **Dispatcher integration**: 4 analysis skills have triggers in dispatch_config.json (cooldown 48-168h, threshold 30-50 new findings)

## Wave Summaries (detail in wave-results.md)
- **W1** (46 findings): Black, Gratitude, Weingarten, IPI, Enhanced Ed, Ruemmler
- **W2** (115): Summers, Bannon, Rod-Larsen, HDI, Thomas, Deripaska
- **W3** (80+): Starr defense, Goldman Triple, Wolff PR, Norwegian Network, Financial Vehicles, IPI
- **W4** (27+, 16 conn): Putin back-channel, Trump-Rybolovlev, Gulf, ProtonMail, Edwards-Schoen, Gates-Nikolic
- **W5** (81, 62 conn, 42 entities): Entity traces, Inner circle, Gulf/Russia, DB+Property, Carbyne/Gates, Addresses
- **W6** (130, 41 conn): ACRIS, FEC bundling, FARA non-compliance, 990 nonprofit, FL SunBiz, Shadow lobbying
- **W7** (271, 43 conn): SoftBank honey trap, Teodorani, K-1 schedule, Johnson/Zuckerman, YHS, Obsidian, Shell sweep
- **W8** (568, 213 conn): PTJ, Ghosn, de Rothschild, Al Thani, Rowan + many others
- **W9** (98, 58 conn): FOIA harvest, DocumentCloud, Southern Trust financial, Osborne, PTJ/Rowan/Harris, Gulf intel
- **W10** (78, 43 conn): Apollo all-3-founders IRS, Dechert report destroyed, zero-finding nodes filled, CBP lookout, Ruemmler multi-Gulf, Hedosophia, Broidy
- **W11** (~97, 48 conn): DS10 financial forensics (WE LLC $23.5M), Wexner trust architecture, 9E71st deed chain, 5-tier corporate architecture, Gratitude grants, Black-Clinton $750K, BBVI active
- **W12** (~43, 13 conn): Indyke PLLC ($250K/mo), $14.9M post-death to co-executors, Harlequin Dane, G&W since 1988, DB RM 82289 account roster, 1953 Trust renamed 2 days pre-death
- **K&E** (130, 115 conn): Thread 7. Filip DPA rules -> defense. Benczkowski letter weaponized. Boeing->Epstein path. NOT DB/JPM counsel. IS Apollo counsel. Foundation clean. Trump $125M.

## Critical Intelligence
Key patterns agents should know (query `findings_tracker.py search "TERM"` for detail):
- **Leon Black**: $40M to STC in 2013 alone, $158M+ total. All 3 Apollo founders engaged (EFTA02576529)
- **STC balance trajectory**: $0->$110M peak (Dec 2015)->IB consolidation (Dec 2019). EdR $25M unresolved
- **FARA non-compliance**: Systematic across 15+ intermediaries, 6 countries. Only Schoen registered
- **Shadow lobbying**: 5-layer structure outside LDA. IPI/HDI zero filings despite 33+ Congress members
- **FEC bundling**: USVI (Indyke+Groff->Plaskett), NM (->Richardson), Clinton (Maxwell+Kahn+Barrett+Dershowitz)
- **Ian Osborne**: Hedosophia founder, Epstein investor. Primary Thiel/SV intermediary
- **Brad Karp**: Paul Weiss chairman leaked privileged Ghosn/DOJ intel to Epstein (7 docs Nov-Jan 2019)
- **MCC records**: Hard drives replaced same night as death. Cameras corrupted. 3,385pp in DocumentCloud
- **CBP travel**: Complete 1988-2019 border history. Enhanced screening from late 2016. New passport 3/8/2019
- **Gulf three-tier**: Qatar (Al Thani/HBJ), Saudi (Alsabbagh/Alahmadi), UAE/Turkey (Sulayem/Tamince). Broidy/Nader opposing anti-Qatar op -- Ruemmler connected to both sides

## Key External Researchers
- **Thomas Volscho** (CUNY sociology, @ksumnole987 Substack): Best primary-source researcher. 3 posts (Dec 2025-Jan 2026). Original research: NYC Municipal Archives, Bear Stearns personnel file (DOJ Jan 30 2026), Fidelifacts check. Findings #2862-2876.
- **Key insight**: Entity names (Maple/Nautilus/Neptune/Cypress/Laurel) = Sea Gate Brooklyn streets NOT tree names
- **IAG**: Intercontinental Assets Group Inc (1981, DOS) = Epstein's FIRST company (not "J. Epstein & Co" 1988)
- Bear Stearns start: March 15, 1976. Resume fraud at both Dalton and Bear Stearns

## Registry Findings
- **Zorro Ranch LLC**: NM #2306629, formed 12/27/2002, agent resigned + revoked 08/12/2019 (5 weeks post-arrest)
- **San Rafael Ranch LLC**: NM active 07/28/2023 (successor entity at same address)
- **Panama**: 5 Epstein-named companies in 2008 registry (EPSTEIN HOLDING CORP 1983, EPSTEIN OVERSEAS INC 1996, EPSTEIN CORP 2004, AYER-EPSTEIN S.A. 2005, EPSTEIN GLOBAL CORPORATION 2005). Unconfirmed if connected to financier
- **NY 457 Madison**: Indyke entities (LYN AND JOJO LLC, E MANAGEMENT NEW YORK LLC, MAX HOTEL SERVICES CORP), M EPSTEIN FAMILY HOLDINGS LLC, 301 E 66TH STREET ASSOCIATES LP
- **FL (Wave 6)**: Ghislaine Corp (P95000027272, 1995-1998), Financial Strategy Group Inc (P93000087814, 1993-2000), Florida Science Foundation, 124 Parc Monceau LLC (Indyke, Paris)
- **FL Indyke addresses**: 30 Le Lac Rd Boca Raton 33496, 16065 Bristol Isle Way Delray Beach 33446

## Priority Sources (Not Yet Integrated)
| Source | Value | Status |
|--------|-------|--------|
| Giuffre v. Maxwell (SDNY 15-cv-7433) | Civil depositions | Not started |
| USVI v. JPMorgan (SDNY 1:22-cv-10904) | Financial evidence | Not started |
| DE corporate registry | Next state for /add-registry | Not started |
| CBP/FBI Vault PDFs | Download + ingest | Not started |
