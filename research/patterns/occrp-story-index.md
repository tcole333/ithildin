# OCCRP Story Index — Per-Story Evidence Base

The coded corpus behind the OCCRP pattern library’s frequency claims. Distilled from the full extraction reports in
`_intake/occrp/` (reports 01, 09, 11, 13, 14, and 16), which retain per-claim citations; this index compresses
each story or methodology unit to its evidence skeleton. Report-10 is the excluded sampling frame.

**Entry fields** — URL; Partner/awards; Found (core finding); Types (source-report finding tags, exact spelling);
Evidence (typed sources with acquisition mode); Systems (specific named record systems, conservatively derived);
Signature (coined detection move and mechanics); Method (cited methodology URL vs `[inferred]`); Impact (official
consequences); Dependency (INPUT DEPENDENCY class plus a short reason). Report-01 dependencies are joined
one-for-one from the OCCRP signature table in `_intake/access-substitution-analysis.md` and marked
`[access-substitution]`; unmatched report-09 method/tool units remain `unassessed`.

---

## Laundromat / banking-leak canon (report-01)

### The Proxy Platform (2011) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/the-proxy-platform); [main investigation](https://www.occrp.org/en/project/the-proxy-platform/the-proxy-platform).
- Partner/awards: OCCRP coordinated reporters from Novaya Gazeta, Re:Baltica/TV3 Latvia, Kyiv Post, CINS, CIN Bosnia and Herzegovina, and other member centers (project team). OCCRP lists the project as a 2013 Daniel Pearl Award finalist (awards).
- Found: Bank records for Tormex, Sirena, and Nomirex showed thousands of transactions among phantom companies with no genuine offices, employees, or tax activity but recurring counterparties and proxy directors (main investigation). Tormex alone moved roughly **$680 million in 15 months**; the platform touched actors tied to the Magnitsky fraud, Asian organized crime, Moldovan business interests, and entities in the Wachovia/Sinaloa money-laundering case (main investigation).
- Types: shell-network convergence; pass-through laundering
- Evidence: Leaked/obtained bank transaction records for Tormex, Sirena, and Nomirex (bank records obtained by reporters from confidential sources) (main investigation); UK, New Zealand, Latvian, Moldovan, Panamanian, and other company-registration records (public or registry-request records assembled cross-border) (main investigation); Moldovan litigation and law-enforcement records plus interviews and site checks (public/request-gated records and reporter verification) (opening investigation)
- Systems: Tormex/Sirena/Nomirex bank ledgers; UK/New Zealand/Latvian/Moldovan/Panamanian company registries; Moldovan court and law-enforcement records
- Signature: proxy-bank ledger → company/role registry join: Bank-ledger counterparties for Tormex, Sirena, and Nomirex joined to corporate registries on company name, registration number, address, director, and formation agent revealed a dense group of high-throughput shells with shared infrastructure rather than three unrelated firms (main investigation).
- Method: https://www.occrp.org/en/project/the-proxy-platform
- Impact: Russia’s central-bank chair later said one organized group accounted for over half of Russia’s $49 billion in questionable 2012 outflows; OCCRP linked that description to the network it had profiled (OCCRP impact report).
- Dependency: (b) [access-substitution] — public registries cannot regenerate bank ledger.

### A bad-tire lawsuit opened the platform (2011) — laundromat-canon
- URL: [“Opening the Door: Proxy Platform Revealed”](https://www.occrp.org/en/project/the-proxy-platform/opening-the-door-proxy-platform-revealed).
- Partner/awards: OCCRP and RISE Moldova supplied the court-to-company reporting inside the wider OCCRP consortium; award attribution remains at project level (project team; awards).
- Found: A Moldovan dispute over a **$437,176** defective-tire transaction identified Tormex and exposed payment and ownership links to Sirena and Nomirex. The dispute’s apparently ordinary commercial paperwork provided names, counterparties, and accounts that could be pivoted into registries and bank records.
- Types: litigation-seed expansion
- Evidence: Moldovan civil-court pleadings, exhibits, and decisions (public/request-gated judicial records); Bank records and cross-border company files reached from names and accounts in the case (privileged bank data plus public/request-gated registries)
- Systems: Moldovan civil-court files; cross-border company registries; Tormex/Sirena/Nomirex bank records
- Signature: small lawsuit seed → global shell/payment-network expansion: Court exhibits joined to bank ledgers and registries on company name, account, director, and address revealed that a one-off commercial plaintiff/defendant sat inside a repeated multi-company payment platform.
- Method: [inferred]
- Impact: the project-level network was later identified by Russia’s central-bank chair as a major organized questionable-flow channel (impact report).
- Dependency: (b) [access-substitution] — case expands publicly; payments remain private.

### Magnitsky proceeds met a dormant UK company (2011) — laundromat-canon
- URL: [“Following the Magnitsky Money”](https://www.occrp.org/en/project/the-proxy-platform/following-the-magnitsky-money).
- Partner/awards: Novaya Gazeta and OCCRP reporting within the Proxy Platform consortium; project was a 2013 Daniel Pearl Award finalist (project team; awards).
- Found: Bunicon and Elenast received about **$52 million** from Krainiy Sever in a short February 2008 window tied to the **$230 million** Russian tax fraud exposed by Sergei Magnitsky. Nomirex appeared in the flow even though its UK filings portrayed it as inactive, exposing a gap between legal-form status and financial behavior.
- Types: proceeds re-entry; registry-status mismatch
- Evidence: Bank-transfer records mapping the Magnitsky-related flow (privileged bank records); UK Companies House filings and Russian case material (open-public/request-gated registry and judicial records)
- Systems: Magnitsky-related bank-transfer records; UK Companies House; Russian case records
- Signature: Magnitsky proceeds → dormant UK company flow chain: A known-proceeds transaction chain joined to UK registry status on company name and date revealed that a company represented as inactive was receiving or transmitting crime-linked funds.
- Method: [inferred]
- Impact: the broader platform was publicly linked by Russia’s central-bank chair to a dominant questionable-flow group (impact report).
- Dependency: (c) [access-substitution] — transfer chain is the decisive signal.

### The Russian Laundromat (2014/2017) — laundromat-canon
- URL: [2014 project](https://www.occrp.org/en/project/the-russian-laundromat); [2017 bank-record expansion](https://www.occrp.org/en/project/the-russian-laundromat-exposed); [2017 findings](https://www.occrp.org/en/project/the-russian-laundromat-exposed/the-russian-laundromat-exposed).
- Partner/awards: OCCRP and Novaya Gazeta led the initial work; RISE Moldova, the Guardian, Süddeutsche Zeitung, and many national partners participated in the 2017 expansion through OCCRP’s secure collaboration. The investigation was shortlisted in European Press Prize categories when OCCRP received a special award (award report).
- Found: From 2010 to early 2014, fake loan guarantees and more than 50 Moldovan court orders involving over 20 judges gave a lawful-looking basis for moving Russian funds through Moldindconbank and Latvia’s Trasta Komercbanka (2014 investigation). The 2017 reconstruction found **$20.8 billion**, 21 core shell companies, **26,746 payments**, and beneficiaries in **96 countries**; the underlying datasets contained roughly 75,000 transfers (2017 findings; ).
- Types: judicial legitimation; legal-pretext laundering
- Evidence: Two confidential bank datasets from Moldindconbank and Trasta Komercbanka, plus PDFs and records from multiple sources (privileged bank records); Moldovan court orders, loan/guarantee instruments, invoices, and criminal-investigation records (open-public/request-gated judicial and law-enforcement material) (2014 investigation); National and international registries, sanctions lists, and bank KYC records (open-public/request-gated sources plus privileged compliance files) (banks story)
- Systems: Moldindconbank ledger; Trasta Komercbanka ledger; Moldovan court files; national corporate registries; sanctions lists; bank KYC files
- Signature: Moldovan judgments/guarantees → executing bank transfers: Moldovan judgments and guarantees joined to bank transfers on debtor, creditor, guarantor, account, amount, and date revealed a repeated machine in which Russian companies “defaulted,” Moldovan courts validated debt, and banks routed the resulting payments abroad (2014 investigation; ).
- Method: https://www.occrp.org/en/project/the-russian-laundromat-exposed/about-the-project
- Impact: agencies in the UK, Switzerland, Moldova, and elsewhere announced inquiries; Moldova investigated judges and bank officials, while Trasta’s license had been withdrawn for anti-money-laundering failures (world response).
- Dependency: (b) [access-substitution] — public case cluster lacks transfer join.

### Moldovan courts manufactured the payment key (2014) — laundromat-canon
- URL: [“The Russian Laundromat”](https://www.occrp.org/en/project/the-russian-laundromat/the-russian-laundromat).
- Partner/awards: OCCRP, Novaya Gazeta, and RISE Moldova supplied the central court and bank reconstruction; awards are recorded at project level (award report).
- Found: More than **20 judges in 15 Moldovan courts** issued over 50 orders validating supposed debts backed by Moldovan guarantors (2014 investigation). The mechanism involved more than 90 Russian companies and 19 Russian banks, converting nominal defaults into orders payable through Moldindconbank (2014 investigation).
- Types: institutionalized pretext repetition
- Evidence: Moldovan court orders and case files (open-public/request-gated judicial records) (2014 investigation); Guarantee agreements and loan documents (court exhibits and confidential/source-provided records) (2014 investigation); Bank transfers implementing the orders (privileged bank records)
- Systems: Moldovan court files; guarantee/loan instruments; Moldindconbank and Trasta Komercbanka transfers
- Signature: repeated court templates/shared actors → enforcement/outward-payment pattern: Court cases compared across court, judge, debtor, creditor, guarantor, amount, and filing date revealed repeated structures; joining those cases to bank execution records showed that judgments were the common authorization layer for outward transfers (2014 investigation).
- Method: [inferred]
- Impact: Moldovan authorities investigated 16 judges and sent 14 cases to court, while bank officials also faced investigation or prosecution (world response).
- Dependency: (a) [access-substitution] — court-template cluster runs on public files.

### The 2017 bank leak exposed the destination layer (2017) — laundromat-canon
- URL: [“The Russian Laundromat Exposed”](https://www.occrp.org/en/project/the-russian-laundromat-exposed/the-russian-laundromat-exposed); [project methodology](https://www.occrp.org/en/project/the-russian-laundromat-exposed/about-the-project).
- Partner/awards: OCCRP and Novaya Gazeta coordinated a secure cross-border workspace with RISE Moldova, the Guardian, Süddeutsche Zeitung, and national partners who investigated local recipients.
- Found: Twenty-one core shells made **26,746 payments** into 96 countries, including payments to major companies and Russian state contractors (2017 findings). Repeated and apparently copied invoices supplied supposed commercial explanations for transfers from the same small shell core (2017 findings).
- Types: beneficiary fan-out; document-template anomaly
- Evidence: Moldindconbank and Trasta Komercbanka transaction exports plus source PDFs (privileged bank data); Payment invoices and bank documentation (privileged/source-provided transactional records) (2017 findings); Sanctions lists and national corporate registries researched by local partners (open-public/request-gated reference data)
- Systems: Moldindconbank ledger; Trasta Komercbanka ledger; payment invoices; sanctions lists; national corporate registries
- Signature: normalize two bank datasets → beneficiary map and invoice-text clusters: Two bank datasets normalized into one transfer schema and joined on sender/recipient account, company, amount, currency, and date revealed the 21-shell fan-out; invoice texts clustered by repeated wording and commodity descriptions exposed copied commercial pretexts (2017 findings).
- Method: https://www.occrp.org/en/project/the-russian-laundromat-exposed/about-the-project
- Impact: regulators and investigators in multiple recipient jurisdictions opened reviews after publication (world response).
- Dependency: (c) [access-substitution] — private ledgers supply union and recurrence.

### The Azerbaijani Laundromat (2017) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/the-azerbaijani-laundromat); [how the system worked](https://www.occrp.org/en/project/the-azerbaijani-laundromat/what-is-a-laundromat); [raw-data note](https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-raw-data).
- Partner/awards: Berlingske obtained the banking data and shared it with OCCRP, which organized reporting with the Guardian, Süddeutsche Zeitung, Le Monde, Czech Center for Investigative Journalism, Bulgarian Investigative Journalism Center, and other partners; the work also sat within the OCCRP/Transparency International Global Anti-Corruption Consortium.
- Found: Nearly 17,000 payments moved about **$2.9 billion** through four UK-registered companies’ accounts at Danske Bank’s Estonian branch between 2012 and 2014 (raw-data note). The system mixed state-linked inputs, including funds tied to the International Bank of Azerbaijan and ministries, with payments benefiting officials, politicians, a journalist, luxury purchases, and other recipients.
- Types: state-origin layering; influence laundering
- Evidence: Leaked Danske Estonia payment ledger covering four UK companies (privileged bank data obtained by Berlingske and shared with OCCRP) (raw-data note); UK Companies House, Azerbaijani corporate/state records, and other national registries (open-public/request-gated records); Parliamentary, lobbying, property, and asset records plus interviews (open-public/request-gated records and reporter verification) (influence story)
- Systems: Danske Bank Estonia payment ledger; UK Companies House; Azerbaijani corporate/state records; lobbying and parliamentary records
- Signature: four-company Azerbaijani ledger → registry and influence joins: The four-company bank ledger joined to UK registrations and source/recipient identities on account, company, and date revealed coordinated pass-through shells; recipient payments then joined to political roles, lobbying disclosures, votes, trips, and statements surfaced influence threads (how it worked; influence story).
- Method: https://www.occrp.org/en/project/the-azerbaijani-laundromat
- Impact: a Council of Europe inquiry cited the reporting and found code violations and corruption-facilitation concerns; UK authorities later seized £5.6 million from an Azerbaijani lawmaker linked to the system (Council report coverage; UK seizure).
- Dependency: (a) [access-substitution] — published ledger supports registry/influence joins.

### Same-day matching flows exposed coordinated shells (2017) — laundromat-canon
- URL: [“What Is a Laundromat?”](https://www.occrp.org/en/project/the-azerbaijani-laundromat/what-is-a-laundromat); [raw-data note](https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-raw-data).
- Partner/awards: Berlingske supplied the data; OCCRP analysts Amy Guy, Friedrich Lindenberg, and Lion Summerbell supported the shared database used by the reporting consortium (raw-data note).
- Found: Hundreds of thousands of dollars could enter and leave an account on the same day, leaving balances near zero (how it worked). The same amount was sometimes sent to the same recipient from different core companies on the same day, indicating coordination across nominal entities (how it worked).
- Types: velocity pairing
- Evidence: Nearly 17,000 incoming and outgoing bank payments for the four core UK companies (privileged bank ledger) (raw-data note); UK company registrations for the nominal account holders (open-public/request-gated registry records)
- Systems: Azerbaijani Laundromat payment database; UK Companies House
- Signature: same-day matched pass-through flows among coordinated shells: Incoming transfers self-joined to outgoing transfers on core account, calendar date, near-equal amount/currency, and recipient revealed repeated same-day pass-through pairs and synchronized behavior across four UK shells (how it worked).
- Method: https://www.occrp.org/en/project/the-azerbaijani-laundromat/what-is-a-laundromat
- Impact: Danske and authorities faced sustained scrutiny, and the Council of Europe examined recipients and lobbying conduct linked to the ledger (Council report coverage).
- Dependency: (a) [access-substitution] — published rows support velocity testing.

### Laundromat payments aligned with reputation lobbying (2017) — laundromat-canon
- URL: [“The Influence Machine”](https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-influence-machine); [U.S. lobbying story](https://www.occrp.org/en/project/the-azerbaijani-laundromat/us-lobbying-firm-launders-azerbaijans-reputation-and-gets-laundromat-cash).
- Partner/awards: OCCRP worked with European partners on the Council of Europe thread and with U.S.-focused reporters on lobbying disclosures, under the wider Berlingske/OCCRP consortium.
- Found: Former German parliamentarian Eduard Lintner received roughly **$1.1 million** while running election-observation and other pro-Azerbaijan activities (influence story). Four Laundromat transfers to Renaissance Associates closely tracked quarterly payments to U.S. lobbying firm Bob Lawrence & Associates; the firm reported about **$1.533 million** in income from 2012–2015, close to Renaissance’s receipts (U.S. lobbying story).
- Types: payment-policy alignment
- Evidence: Leaked bank transfers to Lintner and Renaissance Associates (privileged bank data) (influence story; U.S. lobbying story); Council of Europe records, election-observation material, and public statements (open-public institutional records) (influence story); U.S. lobbying/FARA disclosures and corporate records (open-public/request-gated filings) (U.S. lobbying story)
- Systems: Azerbaijani Laundromat payment database; Council of Europe records; U.S. FARA filings; U.S. lobbying disclosures
- Signature: laundromat payments → lobbying/reputation actions timeline: Laundromat deposits joined to lobbying invoices/disclosures and public-action dates on recipient, amount, quarter, client, and issue revealed that opaque upstream payments closely funded identifiable downstream reputation work (U.S. lobbying story; influence story).
- Method: [inferred]
- Impact: the Council of Europe’s independent investigation cited the reporting and found ethics violations and corruption-facilitation concerns among assembly members (Council report coverage).
- Dependency: (a) [access-substitution] — published payments align with public actions.

### The Troika Laundromat (2019) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/the-troika-laundromat); [main investigation](https://www.occrp.org/en/project/the-troika-laundromat/vast-offshore-network-moved-billions-with-help-from-major-russian-bank); [data methodology](https://www.occrp.org/en/project/the-troika-laundromat/about-the-data).
- Partner/awards: OCCRP and Lithuania’s 15min obtained the data and coordinated **23 media organizations**, including national partners using local registries and reporting expertise (collaboration note). OCCRP lists Troika among its Sigma and IJ4EU-recognized work (awards).
- Found: A core of 75–76 offshore companies received about **$4.6 billion**, sent **$4.8 billion**, and circulated roughly **$8.8 billion** internally from 2006 to early 2013. Emails, contracts, formation records, and payments showed Troika Dialog personnel and an Irish formation network building and operating shells that paid expenses, hid assets, and shifted value for Russian elites (main investigation; ).
- Types: operator-attributed shell system; multi-purpose hidden treasury
- Evidence: A 1.3-million-transaction leak covering 238,000 companies and about $470 billion in wider bank activity, obtained from multiple sources and centered on failed Lithuanian banks Ūkio and Snoras (privileged bank data) (data methodology); Tens of thousands of emails, contracts, invoices, bank forms, and corporate documents in more than 20 formats (privileged/source-provided records) (data methodology); National registries, OCCRP Investigative Dashboard research, and ICIJ Offshore Leaks/Panama/Paradise data (open-public/request-gated and partner-access datasets) (collaboration note)
- Systems: Troika transaction database; Aleph / OCCRP Investigative Dashboard; ICIJ Offshore Leaks Database; national corporate registries
- Signature: Troika transactions + emails/invoices/contracts/company files → control and flow graph: Normalized bank transactions joined to emails, invoices, contracts, and company files on account, company, signatory, address, and email domain revealed both a 76-node flow network and the Troika/formation-agent control plane behind it (data methodology; main investigation).
- Method: https://www.occrp.org/en/project/the-troika-laundromat/about-the-data
- Impact: banks opened internal probes, Spanish authorities examined property links, and German authorities later raided properties in a Troika-related laundering inquiry (initial impact; German raids).
- Dependency: (c) [access-substitution] — full ledger and document corpus unavailable.

### Troika’s control plane leaked through routine operations (2019) — laundromat-canon
- URL: [main investigation](https://www.occrp.org/en/project/the-troika-laundromat/vast-offshore-network-moved-billions-with-help-from-major-russian-bank); [FAQ](https://www.occrp.org/en/project/the-troika-laundromat/frequently-asked-questions); [IOS Group story](https://www.occrp.org/en/project/the-troika-laundromat/how-ios-group-supersized-the-shell-company-game).
- Partner/awards: OCCRP, 15min, and Irish/UK registry researchers inside the 23-outlet consortium traced the formation and operating layer (collaboration note).
- Found: Corporate instructions and transaction documents were sent from **troika.ru** addresses, while hundreds of payments went to Irish formation agent IOS Group, linking shells to their operators (IOS Group story). IOS Group created more than 1,000 companies over 24 years and supplied entities used in several offshore scandals, including the Troika network (IOS Group story).
- Types: control-plane attribution
- Evidence: Internal emails, payment instructions, contracts, and invoices (privileged/source-provided corporate and bank records) (main investigation); Irish and offshore formation/company records (open-public/request-gated registries) (IOS Group story); Payments from shell accounts to IOS Group (privileged transaction ledger)
- Systems: Troika transaction database; internal email/invoice files; Irish and offshore company registries
- Signature: email metadata and formation-agent payments → Troika control plane: Email sender domains and document metadata joined to shell-account service payments and registry formation records on company, agent, signatory, and date revealed a common Troika/IOS operating layer behind the legal entities (main investigation; IOS Group story).
- Method: https://www.occrp.org/en/project/the-troika-laundromat/about-the-data
- Impact: banks and prosecutors opened inquiries into Troika-linked transactions and properties (initial impact; German raids).
- Dependency: (c) [access-substitution] — private operational records attribute shell control.

### Sixteen canceled share deals transferred value to Sergei Roldugin (2019) — laundromat-canon
- URL: [“Money for Nothing”](https://www.occrp.org/en/project/the-troika-laundromat/money-for-nothing-putin-friend-sergei-roldugin-enriched-by-troika-laundromat).
- Partner/awards: OCCRP and 15min led the transaction/document analysis with the wider Troika consortium; project awards are listed by OCCRP (collaboration note; awards).
- Found: Companies connected to cellist Sergei Roldugin received about **$69 million** from the Troika system. Sixteen consecutive canceled agreements involving Rosneft shares generated roughly **$11.6 million** in compensation although no shares changed hands.
- Types: canceled-deal value transfer
- Evidence: Share-purchase and cancellation agreements (privileged/source-provided contract files); Bank payments to Roldugin-linked companies (privileged transaction records); Corporate ownership and Panama Papers records connecting recipients (open-public/request-gated and partner-access offshore data)
- Systems: Troika transaction database; share-purchase/cancellation agreements; Panama Papers / Offshore Leaks records
- Signature: repeated cancelled share deals with no asset transfer → value-transfer pattern: Purchase agreements joined to cancellation deeds and bank payments on parties, underlying security, amount, and sequence number revealed 16 repeated deals where cancellation fees moved value but asset-ownership records showed no corresponding share transfer.
- Method: [inferred]
- Impact: authorities and banks opened Troika-related inquiries, including a German property-laundering investigation (German raids).
- Dependency: (c) [access-substitution] — private contracts prove no-transfer cancellations.

### Plunder and Patronage in the Heart of Central Asia (2019) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia); [Saimaiti archive](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/saimaitis-archive); [“The $700 Million Man”](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/the-700-million-dollar-man).
- Partner/awards: Radio Free Europe/Radio Liberty’s Radio Azattyk, OCCRP, and Kloop jointly investigated the archive with roughly two dozen journalists. OCCRP lists the work among the recipients of an IRE Tom Renner Award and the Egizbaev investigative prize (awards).
- Found: Aierken Saimaiti, who described himself as a money mover, said he transferred more than **$700 million** from 2011–2016 for the Abdukadyr family’s business network; he provided records and was later murdered (“$700 Million Man”). The reporting connected cash couriers, customs officials, investments, and property to a trade and patronage system involving former customs official Raimbek Matraimov and the Abdukadyr network (“$700 Million Man”).
- Types: insider-ledger corroboration; customs-capture finance
- Evidence: Saimaiti’s 843 deduplicated transactions, invoices, sham loans, contracts, ledgers, and interviews (privileged insider material); U.S. bank records, property records, corporate registries, cash declarations, and border/flight data (request-gated/open-public records) (couriers story); Interviews with current/former officials, drivers, brokers, and other participants (reporter-obtained testimony) (“$700 Million Man”)
- Systems: Saimaiti archive; U.S. bank records; corporate and property registries; cash declarations; border/flight data
- Signature: insider transaction rows → independent bank/registry/property/cash/border verification: Insider transaction rows joined to independent U.S. bank records, corporate/property registries, cash declarations, and border events on person, company, amount, account, and date revealed which claimed transfers and relationships could be externally verified.
- Method: https://www.occrp.org/en/project/the-shadow-investor/frequently-asked-questions
- Impact: the reporting prompted large protests; the United States later sanctioned Matraimov, and he pleaded guilty in Kyrgyzstan and paid $24 million to the state (protests; U.S. sanctions; follow-up FAQ).
- Dependency: (b) [access-substitution] — public records verify leak-seeded claims.

### Cash declarations turned couriers into a transport network (2019) — laundromat-canon
- URL: [“The Abdukadyrs’ Cash Couriers”](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/the-abdukadyrs-cash-couriers).
- Partner/awards: Radio Azattyk, Kloop, and OCCRP jointly reported the courier network; project awards are listed by OCCRP (awards).
- Found: Forty-eight cash-declaration forms identified **31 couriers** carrying roughly **$27 million** over two months (couriers story). Names on the forms connected through Turkish corporate records and travel data to the Palvan/Abdukadyr network; reporting also identified **$2.4 million** reaching a charity linked to Matraimov (couriers story).
- Types: courier-network aggregation
- Evidence: Forty-eight customs cash declarations (request-gated/official border records) (couriers story); Flight and border-crossing data (request-gated official/travel records) (couriers story); Turkish company registrations and Saimaiti’s documents (open-public/request-gated registry records plus privileged insider archive) (couriers story)
- Systems: customs cash declarations; flight and border-crossing records; Turkish company registry; Saimaiti archive
- Signature: cash declarations → passenger/flight/company courier-network aggregation: Cash declarations joined to passenger movement and corporate records on traveler name, passport/identity, flight date, destination, employer, and associate revealed repeated couriers converging on one commercial network (couriers story).
- Method: [inferred]
- Impact: U.S. sanctions later described Matraimov’s customs corruption and illicit enrichment (U.S. sanctions).
- Dependency: (a) [access-substitution] — official declarations support courier aggregation.

### Wires became overseas property (2019) — laundromat-canon
- URL: [“A Real Estate Empire Built on Dark Money”](https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/a-real-estate-empire-built-on-dark-money).
- Partner/awards: Kloop, Radio Azattyk, OCCRP, and jurisdictional partners traced properties and companies across the project’s countries.
- Found: Saimaiti’s transfer records linked money from the Abdukadyr network to property and investment structures outside Kyrgyzstan (property story). Corporate and property holdings exposed joint economic relationships that were not visible from customs titles or public biographies alone (property story).
- Types: illicit-to-asset conversion
- Evidence: Bank wires, loan instruments, and insider ledgers (privileged/source-provided transaction records); Property records and corporate registrations across relevant jurisdictions (open-public/request-gated records) (property story); Interviews and on-the-ground property verification (reporter-obtained testimony/observation) (property story)
- Systems: Saimaiti bank-wire/loan ledgers; property registries; corporate registries
- Signature: known wires → overseas property/title: Wires and insider-ledger entries joined to company acquisitions and property records on buyer/beneficial owner, amount band, payment date, address, and intermediary revealed where liquid transfers reappeared as real assets (property story).
- Method: https://www.occrp.org/en/project/the-shadow-investor/frequently-asked-questions
- Impact: Kyrgyz proceedings and U.S. sanctions followed the broader project; Matraimov paid $24 million after pleading guilty to corruption (follow-up FAQ; U.S. sanctions).
- Dependency: (b) [access-substitution] — title verifies endpoints, not payment causation.

### The Riviera Maya Gang (2020) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming); [cash-machine investigation](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming/the-cash-machine-swindle-how-a-mexican-bank-was-dragged-into-a-billion-dollar-atm-heist); [money-laundering investigation](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming/from-bank-machines-to-real-estate-cleaning-the-dirty-money).
- Partner/awards: OCCRP coordinated with Mexico’s Quinto Elemento Lab, the Mexicanos Contra la Corrupción y la Impunidad team, and Romania’s RISE Project; reporters and sources worked across Mexico, Romania, Brazil, Colombia, Indonesia, and the United States (cross-border Q&A). OCCRP lists two 2020 EPPY awards for the series, for collaborative investigative journalism and investigative video (awards).
- Found: A Romanian-led group installed or controlled more than 100 ATMs in Mexican tourist areas, gaining over 10 percent of a market valued at about **$2 billion annually**, while using compromised machines to steal card data. Corporate concessions, bank branding, false identities, and local political/business relationships let the network appear legitimate; proceeds were reinvested in property across Romania, Mexico, the United States, and Brazil (cash-machine investigation; money-laundering investigation).
- Types: criminal-market capture; identity laundering
- Evidence: Mexican and Romanian corporate registrations, concession/license files, contracts, and bank-company records (open-public/request-gated official and commercial records) (cash-machine investigation); Passports, arrest warrants, court/police records, and victim withdrawal evidence (request-gated or source-provided identity and law-enforcement records) (cash-machine investigation); Property, company, loan, and payment records plus interviews with insiders and victims (mixed open-public/request-gated/privileged records and reporter-obtained testimony) (money-laundering investigation)
- Systems: Mexican and Romanian corporate registries; concession/license records; court/police records; property and bank-company records
- Signature: ATM/concession/passport/arrest/company/device/property cross-silo graph: ATM-owner and concession records joined to passports, arrest records, corporate files, device/victim locations, and property transactions on name, photograph, date of birth, company, machine location, and payment date revealed that apparently legitimate market actors were aliases and fronts for a transnational skimming network (cash-machine investigation).
- Method: https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming
- Impact: Mexico’s financial-intelligence authorities and the FBI opened inquiries, 79 of 80 identified Mexican bank accounts were later frozen, and six gang members were sentenced in Romania (probe; account freezes; sentences).
- Dependency: (a) [access-substitution] — public cross-silo records generate the network.

### “Paul Ionete” was Adrian Tiugan (2020) — laundromat-canon
- URL: [“The Cash Machine Swindle”](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming/the-cash-machine-swindle-how-a-mexican-bank-was-dragged-into-a-billion-dollar-atm-heist).
- Partner/awards: Quinto Elemento Lab and Mexicanos Contra la Corrupción y la Impunidad supplied Mexican concession and banking context; RISE Project supplied Romanian criminal-record and identity expertise within the OCCRP collaboration.
- Found: The nominal businessman **Paul Ionete** was identified as convicted Romanian skimmer **Adrian Tiugan** through passport and arrest-related evidence (cash-machine investigation). A Mexican company, Top Life, and its relationship with Multiva bank supplied a legitimate facade for an ATM network that often lacked required local permits (cash-machine investigation).
- Types: hard-identifier alias resolution
- Evidence: Passport/identity documents and Romanian arrest or warrant records (privileged/source-provided identity material and request-gated official records) (cash-machine investigation); Mexican corporate, concession, permit, and bank-contract records (open-public/request-gated records) (cash-machine investigation); Interviews with technicians and other operational sources (reporter-obtained testimony) (cash-machine investigation)
- Systems: passport/identity records; Romanian warrant records; Mexican corporate/concession/permit records
- Signature: passport/arrest/corporate comparison → alias identity resolution: The executive identity in Mexican company and bank records compared with Romanian passport/arrest evidence on face, name variants, birth data, and criminal history revealed Ionete and Tiugan as the same person (cash-machine investigation).
- Method: [inferred]
- Impact: Mexican and U.S. authorities opened investigations after the reporting, and Mexican financial-intelligence authorities froze 79 linked accounts (probe; account freezes).
- Dependency: (a) [access-substitution] — hard-ID public records resolve the alias.

### A loan-and-sale loop washed ATM proceeds through Romanian property (2020) — laundromat-canon
- URL: [“From Bank Machines to Real Estate”](https://www.occrp.org/en/project/how-a-crew-of-romanian-criminals-conquered-the-world-of-atm-skimming/from-bank-machines-to-real-estate-cleaning-the-dirty-money).
- Partner/awards: RISE Project and OCCRP traced the Romanian company/property leg while Mexican partners established the upstream network.
- Found: Rebeca Popescu received network money, lent it to Seven Residence, acquired an apartment, and was repaid after a same-day January 2019 property transaction before money returned toward Mexico (money-laundering investigation). The group accumulated property or related assets in Romania, the United States, Brazil, and Mexico, using loans and companies to change the apparent source and form of funds (money-laundering investigation).
- Types: loan-sale round trip
- Evidence: Bank/payment records and loan agreements (privileged/source-provided financial records) (money-laundering investigation); Romanian company and real-estate records (open-public/request-gated registries) (money-laundering investigation); Cross-border criminal and beneficial-ownership records connecting the parties (request-gated/open-public records) (money-laundering investigation)
- Systems: bank/payment records; Romanian company registry; Romanian real-estate records; cross-border beneficial-ownership records
- Signature: loan-and-sale same-day property round trip: Inbound network payments joined to loan contracts, property sale records, company repayments, and outbound transfers on party, amount, property, and same-day/near-day timing revealed a closed loop whose legal labels changed while beneficial control of value did not (money-laundering investigation).
- Method: [inferred]
- Impact: Mexican account freezes and later Romanian convictions targeted the network exposed by the project (account freezes; sentences).
- Dependency: (b) [access-substitution] — property timing needs private source-of-funds.

### Suisse Secrets (2022) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/suisse-secrets); [FAQ and methodology](https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak); [main findings](https://www.occrp.org/en/project/suisse-secrets/historic-leak-of-swiss-banking-records-reveals-unsavory-clients).
- Partner/awards: An anonymous source supplied the data to Süddeutsche Zeitung; SZ and OCCRP coordinated **163 journalists from 48 outlets in 39 countries**, including many OCCRP member centers.
- Found: The leak covered more than **18,000 accounts**, roughly **30,000 account holders**, and peak balances exceeding **$100 billion**. Public-interest reporting identified criminals, alleged corrupt officials, sanctioned people, intelligence figures, and other high-risk clients; a subset of especially problematic accounts held more than **$8 billion** (main findings).
- Types: high-risk-client retention; account-holder identity resolution
- Evidence: Leaked Credit Suisse account numbers, holders, opening/closing dates, and maximum balances (privileged banking data supplied anonymously to SZ); Corporate registries, official gazettes, court files, criminal investigations, sanctions/PEP data, and prior leaks (open-public/request-gated and partner-access evidence); Client confirmations, bank-insider interviews, and other source interviews (reporter-obtained testimony) (main findings; )
- Systems: Credit Suisse account leak; corporate registries; official gazettes; court/criminal-investigation files; sanctions/PEP lists; prior leak corpora
- Signature: sparse bank-holder/account interval → sanctions/case/corporate/prior-leak enrichment: Leaked holder names and account dates joined to hard identifiers, sanctions/PEP lists, court cases, corporate ownership, and prior leak account numbers revealed high-risk people whose adverse-event or public-role periods overlapped the bank relationship.
- Method: https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak
- Impact: Switzerland’s parliament voted to review the banking-secrecy law used against disclosures following the project (law review).
- Dependency: (b) [access-substitution] — public enrichment cannot enumerate account holders.

### Risk events overlapped live accounts (2022) — laundromat-canon
- URL: [Suisse Secrets FAQ](https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak); [main findings](https://www.occrp.org/en/project/suisse-secrets/historic-leak-of-swiss-banking-records-reveals-unsavory-clients).
- Partner/awards: Süddeutsche Zeitung and OCCRP coordinated the global screening, while national outlets verified local clients and legal histories.
- Found: Reporters identified clients whose convictions, sanctions, corruption allegations, or senior political roles existed before or during their Credit Suisse relationship (main findings). The leak’s opening and closing dates made it possible to separate merely historical relationships from accounts retained after high-risk facts became public.
- Types: risk-event overlap
- Evidence: Credit Suisse account open/close dates and maximum balance (privileged leak); Sanctions designations, court judgments, official investigations, gazettes, and PEP records with event dates (open-public/request-gated records)
- Systems: Credit Suisse account leak; sanctions/PEP lists; court judgments; official investigations and gazettes
- Signature: account-open interval versus risk-event chronology: Account-open/close intervals compared with dated sanctions, convictions, investigations, and political tenure on resolved identity revealed relationships that persisted after a discoverable risk trigger.
- Method: https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak
- Impact: Swiss lawmakers approved a review of banking-secrecy restrictions after the disclosures (law review).
- Dependency: (b) [access-substitution] — risk chronology needs leak-only account dates.

### Venezuela’s PDVSA case graph unlocked Swiss accounts (2022) — laundromat-canon
- URL: [“Black Gold in Swiss Vaults”](https://www.occrp.org/en/project/suisse-secrets/black-gold-in-swiss-vaults-venezuelan-elites-hid-stolen-oil-money-in-credit-suisse); [“The Savage Years”](https://www.occrp.org/en/project/suisse-secrets/the-savage-years-credit-suisse-and-venezuelas-toxic-bond-market).
- Partner/awards: Armando.info and other Latin American reporters worked with OCCRP and Süddeutsche Zeitung’s Suisse Secrets team to verify Venezuelan clients and cases.
- Found: People tied to corruption schemes involving state oil company PDVSA held large Credit Suisse balances while billions were allegedly siphoned from Venezuela’s oil revenues (Black Gold story). A related analysis identified **25 accounts** holding as much as **$273 million** among actors connected to Venezuela’s bond-market and oil-sector scandals (Savage Years story).
- Types: case-graph-to-account match
- Evidence: Suisse Secrets account-holder and balance records (privileged bank leak); U.S. and Venezuelan court, prosecution, corporate, and public-official records (open-public/request-gated official evidence) (Black Gold story; Savage Years story); Prior reporting and interviews used to resolve roles and relationships (secondary leads plus reporter-obtained testimony, re-anchored to primary records) (Black Gold story)
- Systems: Credit Suisse account leak; U.S./Venezuelan court and prosecution records; corporate/public-official records
- Signature: public PDVSA corruption graph → leaked Swiss holders/balances: A PDVSA corruption-case entity graph joined to leaked Credit Suisse holders on full name, birth data, company, relatives/associates, and account period revealed accounts and balances connected to already documented schemes (Black Gold story; Savage Years story).
- Method: [inferred]
- Impact: the project contributed to the Swiss parliamentary review of banking-secrecy law, but the OCCRP pages reviewed do not claim a PDVSA-specific enforcement action caused by this sub-story (law review).
- Dependency: (b) [access-substitution] — public case graph cannot identify accounts.

### NarcoFiles: The New Criminal Order (2023) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order); [FAQ and methodology](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know); [interactive overview](https://www.occrp.org/interactives/narcofiles-the-new-criminal-order/en/).
- Partner/awards: OCCRP, CLIP, Vorágine, and Cerosetenta/070 gained early access from DDoSecrets and Enlace Hacktivista and coordinated more than 40 outlets in 23 countries; this was not a Forbidden Stories project. OCCRP lists a 2024 EPPY for Best Investigative Feature and the Inter American Press Association’s In-Depth Journalism Award (awards).
- Found: The source corpus contained about **5 terabytes** and more than **7 million emails** from Colombia’s prosecutor’s office, mostly covering 2017–2022. Reporters reconstructed routes and alliances linking Colombian producers and brokers to Mexico, Spain, the Netherlands, and other markets, showing how criminal groups share logistics, corrupt officials, and laundering infrastructure (interactive).
- Types: case-file network reconstruction; criminal supply-chain mapping
- Evidence: Hacked Microsoft Exchange email and attachment corpus from Colombia’s Fiscalía, supplied by Guacamaya through DDoSecrets/Enlace Hacktivista (privileged leak; unlawfully obtained by the hackers but received and reported on by journalists); Court case numbers, national IDs, prosecutor/agent records, company registries, and official web pages (open-public/request-gated primary records); Freedom-of-information responses, police/customs data, interviews, and national partners’ case files (request-gated records and reporter-obtained evidence)
- Systems: Colombian Fiscalía Microsoft Exchange corpus; court and company registries; FOI responses; police/customs records
- Signature: prosecutor emails/attachments → public case/registry/FOI corroboration: Email threads and attachments parsed for case number, national ID, person, company, vessel, phone, route, and date, then joined to official case pages, registries, FOI records, and partner-country investigations, revealed cross-border networks that no single prosecutor file described end to end (interactive).
- Method: https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know
- Impact: the FAQ records the Colombian prosecutor’s criminal investigation into the breach and cybersecurity response, but the OCCRP pages reviewed do not claim a distinct enforcement action caused by the published findings.
- Dependency: (b) [access-substitution] — public records authenticate leak-emitted candidates.

### A 1,764-seizure denominator changed the maritime story (2023) — laundromat-canon
- URL: [“Fishing Boats and Cargo Ships”](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/fishing-boats-and-cargo-ships-how-colombian-cocaine-travels-the-world).
- Partner/awards: OCCRP’s data team worked with Colombian partners and Belgian customs data within the NarcoFiles consortium; awards are recorded at project level (awards).
- Found: Reporters combined 158 seizure cases found in the leak with FOI and customs records to build a dataset of **1,764 busts** from 2016 through April 2022 (shipping story). Roughly three-quarters involved small vessels; **431 large ships** accounted for about **264.8 metric tons**, and Maersk and CMA CGM vessels were frequently targeted rather than necessarily complicit (shipping story).
- Types: constructed-denominator correction
- Evidence: 158 prosecutor-corpus seizure files (privileged leak) (shipping story); FOI responses from Colombian defense, prosecutor, navy, and police bodies plus Belgian customs data (request-gated official records) (shipping story); Ship/operator reference data and case reporting (open-public commercial/official data and reporter verification) (shipping story)
- Systems: Colombian Fiscalía seizure files; Colombian defense/prosecutor/navy/police FOI records; Belgian customs data; ship/operator records
- Signature: leak seizure cases + FOI denominator → route prevalence: Leak seizures unioned with FOI/customs seizures and deduplicated on date, location, vessel, case, and quantity revealed a 1,764-event denominator; grouping by vessel class and operator corrected the narrative produced by large headline seizures alone (shipping story).
- Method: https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know
- Impact: no seizure-policy change is claimed on the OCCRP story page; the formal impact documented by OCCRP is the Colombian investigation of the underlying breach.
- Dependency: (b) [access-substitution] — official denominator cannot represent hidden cases.

### Repeated controlled-delivery forms exposed a risky operational pattern (2023) — laundromat-canon
- URL: [“Controlled Drug Deliveries”](https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/colombian-leak-gives-rare-glimpse-into-secretive-world-of-controlled-drug-deliveries).
- Partner/awards: OCCRP and Colombian NarcoFiles partners analyzed prosecutor records with law-enforcement and legal experts.
- Found: The leak revealed **37 controlled-delivery operations**, a normally secretive tactic in which authorities allow drugs to move in order to identify a wider network (controlled-delivery story). Repeated forms and nearly identical language highlighted weak controls in some requests, including one operation involving an unsecured 100-kilogram load; another operation led to a 1.5-ton seizure and nine arrests (controlled-delivery story).
- Types: procedural-template anomaly; control-gap detection
- Evidence: Controlled-delivery requests, approvals, emails, and forms from the prosecutor leak (privileged operational records) (controlled-delivery story); Court/police outcomes and expert interviews (open-public/request-gated official records and reporter-obtained testimony) (controlled-delivery story)
- Systems: Colombian Fiscalía controlled-delivery forms; court/police outcome records
- Signature: controlled-delivery template clustering and unsafe outlier detection: Thirty-seven operation files clustered by near-identical request language and compared field-by-field for authorization, custody, surveillance, quantity, and outcome revealed both the standard template and outlier operations missing expected safeguards (controlled-delivery story).
- Method: https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know
- Impact: OCCRP does not claim a controlled-delivery policy response on the story page; the documented official action concerns the data breach itself.
- Dependency: (c) [access-substitution] — private form corpus supplies denominator.

### Cyprus Confidential (2023) — laundromat-canon
- URL: [OCCRP project page](https://www.occrp.org/en/project/cyprus-confidential); [PwC sanctions story](https://www.occrp.org/en/project/cyprus-confidential/cyprus-wing-of-auditing-giant-pwc-may-have-breached-sanctions-in-work-for-oligarch).
- Partner/awards: **Joint-attribution note:** the global project was led by **ICIJ and Paper Trail Media**, not OCCRP. OCCRP contributed its reporters, member centers, prior Cyprus work, and leak components obtained from DDoSecrets; this entry covers only those OCCRP-side mechanics and stories (PwC story’s source note). OCCRP records the joint project’s 2024 Institute for Nonprofit News collaboration award and TRACE Prize, while explicitly describing itself as a media…
- Found: The global source base comprised more than **3.6 million documents** from six Cypriot service providers and one Latvian firm; OCCRP’s work showed firms organizing assets and transactions for Russian oligarchs as sanctions approached (PwC source note). OCCRP stories documented hurried PwC Cyprus work around Alexey Mordashov’s TUI stake and offshore payments by Roman Abramovich-linked companies for football-related activity (PwC story; football-payments story).
- Types: service-provider facilitation; sanctions-edge execution
- Evidence: Internal emails, checklists, deeds, contracts, corporate files, and client records from Cypcodirect, MeritServus, MeritKapital, DJC Accountants, and other providers (privileged leaks obtained through DDoSecrets or shared by ICIJ/Paper Trail) (PwC source note); Cypriot/offshore corporate registries, EU sanctions notices, market disclosures, and sports rules (open-public/request-gated primary records) (PwC story; football-payments story); Recipient confirmations, expert review, and right-of-reply responses (reporter-obtained testimony) (football-payments story)
- Systems: Cypcodirect/MeritServus/MeritKapital/DJC provider files; Cypriot/offshore corporate registries; EU sanctions notices; market disclosures; football rules
- Signature: Cyprus service instruments → BO/assets/sanctions/rules: Service-provider emails and transaction instruments joined to beneficial owners, public asset disclosures, sanctions-effective timestamps, and governing rules on company, asset, signer, and date revealed facilitators executing structures at legally consequential moments (PwC story).
- Method: https://www.occrp.org/en/project/cyprus-confidential
- Impact: Cyprus’s sanctions unit confirmed that a criminal investigation into the TUI share transfer was underway, without naming the target; this is an official response/context, not proof that publication caused the probe (PwC story).
- Dependency: (c) [access-substitution] — service instruments expose hidden control edges.

### PwC’s document timestamps crossed the sanctions boundary (2023) — laundromat-canon
- URL: [“Cyprus Wing of Auditing Giant PwC May Have Breached Sanctions”](https://www.occrp.org/en/project/cyprus-confidential/cyprus-wing-of-auditing-giant-pwc-may-have-breached-sanctions-in-work-for-oligarch).
- Partner/awards: OCCRP reporters Pete Jones and Graham Stack produced this story within the ICIJ/Paper Trail-led project; Cypcodirect records were shared by ICIJ/Paper Trail, while other OCCRP-held leak sets are separately attributed in the story (PwC story).
- Found: PwC Cyprus helped arrange the transfer of Alexey Mordashov’s TUI stake, reportedly worth more than **$1 billion**, to a BVI company owned by his life partner as EU sanctions arrived (PwC story). Although public statements dated the transaction February 28, leaked records marked urgent were still circulating for approval on March 1–2, after the EU designation took effect (PwC story).
- Types: effective-time compliance diff
- Evidence: Cypcodirect/PwC emails, drafts, approvals, and compliance checklist (privileged service-provider leak shared through the joint project) (PwC story); EU Official Journal sanctions notice and TUI/public transaction disclosures (open-public legal and market records) (PwC story); German and Cypriot authority statements (open-public/request-gated official responses) (PwC story)
- Systems: Cypcodirect/PwC email and checklist files; EU Official Journal; TUI market disclosures; German/Cypriot authority records
- Signature: PwC draft/completion timestamps versus sanctions boundary: Public completion date compared with email send times, draft/signature status, approval requests, and the EU designation’s effective time on transaction/asset/party revealed evidence that material execution steps continued after sanctions began (PwC story).
- Method: [inferred]
- Impact: Cyprus’s sanctions unit confirmed a criminal investigation concerning the TUI transfer, without identifying its target (PwC story).
- Dependency: (c) [access-substitution] — internal timestamps determine sanctions-boundary state.

### Abramovich paid football costs outside Chelsea (2023) — laundromat-canon
- URL: [“Abramovich’s Secret Football Payments”](https://www.occrp.org/en/project/cyprus-confidential/abramovichs-secret-football-payments-may-have-breached-financial-fair-play-rules).
- Partner/awards: OCCRP and the Guardian had previously received MeritServus records from DDoSecrets; the story was published within the ICIJ/Paper Trail-led Cyprus Confidential collaboration and must retain that joint attribution (football-payments story).
- Found: Roman Abramovich’s offshore companies made agreements worth tens of millions of dollars with Chelsea directors, agents, scouts, academies, and others connected to club activity (football-payments story). Ovington Worldwide agreements included £12.5 million in loans to director Marina Granovskaia, with documents contemplating forgiveness of at least £7.5 million; recipients confirmed some payments related to Chelsea activity (football-payments story).
- Types: off-books regulatory circumvention
- Evidence: MeritServus contracts, loan agreements, debt-forgiveness deeds, consultancy agreements, and corporate files (privileged leak supplied by DDoSecrets) (football-payments story); Company registries, football transfer/role histories, and UEFA Financial Fair Play rules (open-public/request-gated records) (football-payments story); Recipient confirmations and sports-law/finance expert review (reporter-obtained testimony) (football-payments story)
- Systems: MeritServus contract and loan files; company registries; football transfer/role records; UEFA Financial Fair Play rules
- Signature: Abramovich outside-club payments versus Chelsea accounts: Offshore agreements and payments joined to beneficiary roles, Chelsea activity dates, player/agent relationships, and FFP accounting categories on person, service, amount, and period revealed costs economically connected to the club but paid by owner-controlled outsiders (football-payments story).
- Method: [inferred]
- Impact: the story records possible FFP issues identified by experts but does not claim an official football-regulator finding on publication (football-payments story).
- Dependency: (c) [access-substitution] — private payments supply off-book population.

### Dubai Unlocked (2024) — laundromat-canon
- URL: [OCCRP project](https://www.occrp.org/en/project/dubai-unlocked); [FAQ and methodology](https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know); [interactive](https://www.occrp.org/interactives/dubai-unlocked).
- Partner/awards: C4ADS obtained the property data and shared it with Norway’s E24 and OCCRP, which coordinated more than **70 media outlets**; OCCRP lists Dubai Unlocked as the 2024 EPPY winner for Best Use of Data/Infographics (awards).
- Found: Leaks covering hundreds of thousands of properties, mostly from 2020 and 2022, identified owners and sometimes renters using fields including date of birth, passport number, nationality, and utility information. Reporters verified around **200 people and more than 1,000 properties**, including alleged money launderers, drug figures, sanctioned businesspeople, and political actors accused of corruption.
- Types: asset-haven screening; post-event asset disposal
- Evidence: Multiple leaked datasets primarily derived from Dubai Land Department and public-utility records, obtained by C4ADS (privileged property/utility data); Official Dubai land-registry checks, national corporate/property registries, and other leaks (open-public/request-gated/partner-access records); Sanctions, court, prosecution, procurement, and public-office records plus interviews/OSINT (open-public/request-gated primary records and reporter verification) (interactive; Afghanistan story)
- Systems: Dubai Land Department/utility leaks; official Dubai land registry; national corporate/property registries; sanctions/court/procurement records
- Signature: Dubai property owners → risk graph and current-status verification: Leaked owners joined to sanctions/PEP/case/procurement graphs on passport, date of birth, nationality, name variants, company, and associate, then compared across 2020/2022 and current official registry status, revealed high-risk holdings and post-event disposals (interactive).
- Method: https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know
- Impact: the Financial Action Task Force said it would review the findings, while EU parliamentarians questioned the UAE’s removal from the FATF gray list (FATF response; EU questions).
- Dependency: (b) [access-substitution] — public risk checks need leak-supplied owners.

### Passport-grade matching reduced Dubai false positives (2024) — laundromat-canon
- URL: [Dubai Unlocked FAQ](https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know); [interactive](https://www.occrp.org/interactives/dubai-unlocked); [crypto-sale story](https://www.occrp.org/en/project/dubai-unlocked/top-crypto-scammers-managed-to-sell-dubai-properties-after-being-charged).
- Partner/awards: C4ADS supplied the data; E24 and OCCRP coordinated more than 70 outlets whose local reporters resolved names and cases; the project won a 2024 EPPY for data/infographics (awards).
- Found: DOB, passport, nationality, and company fields allowed reporters to verify around 200 public-interest owners and more than 1,000 properties. The two-snapshot comparison showed accused OneCoin figure Ruja Ignatova and former security adviser Frank Schneider could dispose of Dubai property after criminal charges (crypto-sale story).
- Types: hard-ID asset resolution; snapshot disposition diff
- Evidence: 2020 and 2022 property/utility leak snapshots (privileged data obtained by C4ADS); Official current land-registry checks (request-gated official records); Court/charge records, sanctions data, passports/birth data, and corporate records (open-public/request-gated primary evidence) (crypto-sale story)
- Systems: Dubai 2020/2022 property snapshots; official Dubai land registry; court/charge records; sanctions data; passport/birth and corporate records
- Signature: passport-grade Dubai owner match + 2020/2022/current-title diff: Property-owner rows joined to case/sanctions identities on passport, birth date, nationality, and name, then 2020 ownership compared with 2022/current title on property identifier revealed verified owners and assets sold after charges (crypto-sale story).
- Method: https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know
- Impact: FATF committed to review the project’s findings (FATF response).
- Dependency: (c) [access-substitution] — hard identifiers and snapshots remain private.

### Afghanistan contractors’ public-money trail ended in Dubai property (2024) — laundromat-canon
- URL: [“Destination Dubai”](https://www.occrp.org/en/project/dubai-unlocked/destination-dubai-as-the-us-was-rebuilding-afghanistan-contractors-snapped-up-properties-in-the-uae).
- Partner/awards: OCCRP reported with Etilaat Roz and the Government Accountability Project, supported by OCCRP’s Research & Data Team and Fact-Checking Desk, inside the wider E24/OCCRP collaboration.
- Found: Afghan contractors and politicians who benefited from the international reconstruction economy accumulated substantial Dubai holdings while allegations and sanctions described procurement corruption. Companies linked to Ajmal Rahmani held hundreds of units, including 110 units at Ocean Residencia with estimated annual rent of **$1.3 million** and 118 units in Fern Heights with estimated rent around **$800,000**.
- Types: public-money-to-foreign-asset link
- Evidence: Dubai ownership and rental records (privileged leak plus request-gated official/property records); U.S. sanctions notices, congressional procurement investigations, contracts, and litigation filed by the subjects (open-public official/court records); UAE/Cypriot company and property records plus expert and subject interviews (open-public/request-gated records and reporter-obtained testimony)
- Systems: Dubai ownership/rental records; U.S. sanctions notices; U.S. congressional procurement investigations; UAE/Cyprus corporate and property registries
- Signature: Afghanistan procurement/sanctions graph → Dubai property endpoint: Reconstruction-contract and sanctions entity graphs joined to Dubai property owners/companies on passport, person, controlled company, associate, and acquisition date revealed overseas holdings accumulated by contractors and political figures tied to public-money allegations.
- Method: [inferred]
- Impact: FATF said it would review Dubai Unlocked’s findings; German prosecutors later terminated a probe into Ajmal Rahmani’s properties, an important negative outcome that limits inference (FATF response; terminated probe).
- Dependency: (b) [access-substitution] — public contractor graph lacks ownership endpoint.

## Methodology infrastructure (report-09)

### Aleph corpus-plus-workflow — meta-methods
- URL: https://aleph.occrp.org/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Aleph Pro is a curated archive and collaborative workflow spanning 4.4 billion-plus entities, maintained sources, alerts, restricted evidence, and private investigations—not merely a search interface.
- Types: not coded (methodology unit)
- Evidence: Aleph Pro product/about/FAQ pages and OCCRP’s 2024 annual report (public documentation).
- Systems: Aleph Pro; Aleph source scrapers
- Signature: corpus-plus-workflow flywheel: recurring public sources are acquired and refreshed, then searched, alerted, and converted into reusable cross-project evidence.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### FollowTheMoney interoperability layer — meta-methods
- URL: https://github.com/alephdata/followthemoney
- Partner/awards: Not applicable (methodology/tool unit)
- Found: FollowTheMoney maps people, companies, assets, accounts, contracts, cases, payments, and relationships into typed, source-bearing entities and exports them across common graph/data formats.
- Types: not coded (methodology unit)
- Evidence: FtM user/developer documentation and open-source repository (public documentation/code).
- Systems: FollowTheMoney; alephclient; memorious
- Signature: typed-entity interoperability: normalize heterogeneous records into typed entities and dated/value-bearing relationships while preserving source references.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Aleph list cross-reference and human match review — meta-methods
- URL: https://docs.aleph.occrp.org/users/investigations/cross-referencing/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Reporters clean and type lists, add discriminating identifiers, map them to FtM, and review candidate matches across every authorized corpus rather than silently auto-merging names.
- Types: not coded (methodology unit)
- Evidence: Aleph cross-referencing, key-terms, and investigation-workspace documentation (public documentation).
- Systems: Aleph Pro; FollowTheMoney; Aleph investigation workspaces
- Signature: candidate-generation-plus-review: compute corpus-scale matches, retain scores/sources/rejections, and require human adjudication before entity merge.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: (d) [access-substitution] — authorized Aleph corpus and groups unavailable.

### Aleph access-class and provenance governance — meta-methods
- URL: https://aleph.occrp.org/pages/content-privacy
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Public, restricted, own-data-only, and project-group materials carry different authorization, purpose, retention, and redistribution boundaries.
- Types: not coded (methodology unit)
- Evidence: Aleph content/privacy policy, FAQ, and search boundary (public policy documentation).
- Systems: Aleph Pro access groups; Aleph project workspaces
- Signature: access-state-as-provenance: carry source class, authorized group, purpose, retention, and redistribution state with every record.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### OCCRP ID source catalogue — meta-methods
- URL: https://id.occrp.org/databases/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP ID indexes more than 1,000 research sources in more than 180 countries with official-source, paywall, and login signals.
- Types: not coded (methodology unit)
- Evidence: OCCRP ID homepage and database catalogue (public documentation).
- Systems: OCCRP ID database catalogue
- Signature: jurisdiction-source routing: turn an unfamiliar country/asset question into a source plan with access conditions before searching.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### OCCRP ID research-request desk — meta-methods
- URL: https://id.occrp.org/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Eligible reporters can request multilingual company, property, ship, aircraft, data-acquisition, wrangling, and analysis help from a staffed research desk.
- Types: not coded (methodology unit)
- Evidence: OCCRP ID service page, terms of use, and annual reports (public service documentation).
- Systems: OCCRP ID request service
- Signature: hypothesis-rich research ticket: scope target, jurisdiction, artifact, deadline, sensitivity, and sharing expectations, then return primary evidence with limitations.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### OCCRP ID ticket-to-scraper escalation — meta-methods
- URL: https://aleph.occrp.org/pages/faq
- Partner/awards: Not applicable (methodology/tool unit)
- Found: A recurring source gap can move from a reporter request through OCCRP ID to a maintained Aleph scraper and reusable corpus source.
- Types: not coded (methodology unit)
- Evidence: Aleph FAQ and OCCRP ID terms/service description (public documentation).
- Systems: OCCRP ID request service; Aleph source scrapers
- Signature: ticket-to-corpus promotion: close each request as one-off, maintained-source candidate, or monitored source with ownership and cadence.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Distributed member-center acquisition network — meta-methods
- URL: https://www.occrp.org/en/about-us/our-global-network
- Partner/awards: Not applicable (methodology/tool unit)
- Found: More than 75 local member centers plus regional and central editors combine local-language records and sources with shared data, security, legal, editorial, and publication support.
- Types: not coded (methodology unit)
- Evidence: OCCRP network, staff, and project-credit pages (public organizational documentation).
- Systems: OCCRP member-center network; OCCRP regional editorial desks
- Signature: distributed-local-verification: decompose by jurisdiction, preserve original-language evidence, and centralize claims/evidence for cross-border review.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Annotated evidence-packet fact checking — meta-methods
- URL: https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved
- Partner/awards: Not applicable (methodology/tool unit)
- Found: A fresh checker receives annotated copy, original documents, notes, and interviews and verifies every substantive assertion rather than trusting prior reporting.
- Types: not coded (methodology unit)
- Evidence: OCCRP fact-checking feature and current editorial FAQ (public methods/policy documentation).
- Systems: OCCRP annotated fact-check packet
- Signature: sentence-to-evidence audit: map each material sentence to original evidence, translation, caveat, and independent corroboration in a fresh review context.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Laundromat two-store ledger normalization — meta-methods
- URL: https://www.occrp.org/en/project/the-troika-laundromat/about-the-data
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP preserved source documents separately from a parsed PostgreSQL ledger, normalized more than 20 formats, retained caveats, and kept transaction rows traceable to evidence.
- Types: not coded (methodology unit)
- Evidence: Troika and Azerbaijani Laundromat data/method pages (public methodology over privileged ledgers).
- Systems: Troika transaction database; PostgreSQL; Aleph document store; Azerbaijani Laundromat payment database
- Signature: two-store-ledger reconstruction: preserve immutable documents while parsing a lineage-bearing analytical ledger with raw values, exceptions, and approximate aggregates.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: (c) [access-substitution] — private ledgers supply the analytical substrate.

### Suisse Secrets sparse-index enrichment — meta-methods
- URL: https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak
- Partner/awards: Not applicable (methodology/tool unit)
- Found: A holder/account/date/balance index without transactions was authenticated and enriched against sanctions, PEP, company, family, and event records without inventing flows.
- Types: not coded (methodology unit)
- Evidence: Suisse Secrets FAQ and OCCRP leak-engineering retrospective (public methodology; privileged account index).
- Systems: Credit Suisse account index; Aleph Pro; sanctions/PEP lists; corporate registries
- Signature: sparse-index enrichment: treat the leak as a candidate universe, align known account intervals to independently verified risk events, and withhold unsupported flow claims.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: (b) [access-substitution] — public enrichment needs leak-supplied account holders.

### NarcoFiles multi-level corpus authentication — meta-methods
- URL: https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Reporters separately tested institutional provenance, artifact authenticity, interpretation, and underlying allegations across a five-terabyte prosecutor corpus.
- Types: not coded (methodology unit)
- Evidence: NarcoFiles FAQ and OCCRP leak-engineering retrospective (public methodology; hacked institutional corpus).
- Systems: Colombian Fiscalía Microsoft Exchange corpus; court/company registries; FOI and police/customs records
- Signature: four-proposition authentication: verify institution, artifact, interpretation, and allegation independently; success at one layer does not validate the next.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: (b) [access-substitution] — public records authenticate leak-emitted candidates.

### Depth-first forensic archive triage — meta-methods
- URL: https://medium.com/occrp-unreported/how-to-eat-an-elephant-9da7e146e475
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP hashes and preserves originals, separates processing/analyst copies, unpacks forensic formats, deduplicates, filters known files, and prioritizes the most probative device or hypothesis.
- Types: not coded (methodology unit)
- Evidence: OCCRP Unreported forensic-processing retrospective (public methods article).
- Systems: hashdeep; Cellebrite; EnCase; Aleph
- Signature: depth-first archive triage: inventory and hash everything, but process the highest-probative device/date/person first and expand only after testing a hypothesis.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Synonames multilingual name matching — meta-methods
- URL: https://medium.com/occrp-unreported/an-%D0%B0%D0%BB%D0%B5%D0%BA%D1%81%D0%B0%D0%BD%D0%B4%D1%80-by-any-other-name-819525c82d8c
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Wikipedia/Wikidata across 41 languages and four scripts yielded roughly 20,000 synonym pairs for Elasticsearch while explicitly preserving alias/transliteration incompleteness.
- Types: not coded (methodology unit)
- Evidence: OCCRP Unreported engineering post (public methods article and public knowledge graphs).
- Systems: Synonames; Wikipedia; Wikidata; Elasticsearch
- Signature: multilingual-alias candidate expansion: generate transliteration and name variants, report coverage, and require hard identifiers before merging.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Dubai property merge and title verification — meta-methods
- URL: https://medium.com/occrp-unreported/verifying-who-owns-property-in-dubai-takes-lots-of-data-and-persistence-and-partners-d76ecff77e96
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Millions of property records were merged on a shared identifier, deduplicated, exposed through Datasette, and verified through land-department checks and contracts/invoices rather than map proximity.
- Types: not coded (methodology unit)
- Evidence: OCCRP Unreported Dubai property data account (public method description; non-public bulk data).
- Systems: Dubai property/utility datasets; Datasette; official Dubai land registry
- Signature: property-snapshot identity hardening: merge on stable property/person IDs, deduplicate, then prove current title with official checks and transaction documents.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: (c) [access-substitution] — bulk snapshots and hard identifiers remain private.

### Overseas Entities register to UK property join — meta-methods
- URL: https://medium.com/occrp-unreported/new-legislation-reveals-u-k-offshore-property-ownership-sort-of-2da278a2b2aa
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP downloaded the UK overseas-entities register, cross-referenced owners in Aleph, and joined them to scraped land-registry material.
- Types: not coded (methodology unit)
- Evidence: OCCRP Unreported engineering post (public registers plus constructed join).
- Systems: UK Register of Overseas Entities; UK Land Registry; Aleph Pro
- Signature: offshore-owner-to-title join: resolve disclosed overseas owners, cross-reference risk/context, and connect vehicles to land-title records.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Unreported methods publication channel — meta-methods
- URL: https://medium.com/occrp-unreported/introducing-occrp-unreported-30ea1b43904a
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP created a publication channel for editorial, data, research, design, security, and engineering methods behind investigations.
- Types: not coded (methodology unit)
- Evidence: OCCRP Unreported launch post (public first-party documentation).
- Systems: OCCRP Unreported
- Signature: methods-as-investigation-exhaust: publish operational lessons, boundaries, and tooling so one project’s engineering becomes reusable newsroom knowledge.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Six-level leak authentication doctrine — meta-methods
- URL: https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP separates transport/custody, archive integrity, institutional authenticity, artifact authenticity, claim corroboration, and selection/missingness audits.
- Types: not coded (methodology unit)
- Evidence: OCCRP leak retrospectives plus NarcoFiles, Suisse Secrets, and Plunder examples (public methods documentation).
- Systems: hash manifests; email metadata/headers; official case and registry systems
- Signature: layered-leak verification: pass six independent gates and document gaps; authentic transport or artifacts do not establish the embedded allegation.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Independent fact-checking provenance audit — meta-methods
- URL: https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved
- Partner/awards: Not applicable (methodology/tool unit)
- Found: A fact-checker tests identity, date, amount, translation, attribution, source independence, contrary evidence, and whether prose outruns the source.
- Types: not coded (methodology unit)
- Evidence: OCCRP fact-checking feature and editorial FAQ (public first-party methods/policy).
- Systems: OCCRP annotated fact-check packet
- Signature: fresh-context entailment review: give claims and evidence—not drafting-agent reasoning—to an independent reviewer who reproduces each material assertion.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Right-of-reply publication gate — meta-methods
- URL: https://www.occrp.org/en/announcement/attack-on-poroshenko-reporting-is-pr-not-analysis
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP practice identifies adversely portrayed subjects, sends specific pre-publication questions, preserves delivery/response state, tests answers, and fairly represents denials.
- Types: not coded (methodology unit)
- Evidence: OCCRP response statement plus Suisse Secrets and NarcoFiles question/response disclosures (public first-party records).
- Systems: subject-response log
- Signature: claim-specific response gate: enumerate allegations and evidence, send precise questions with a reasonable deadline, preserve delivery, and adjudicate answers before publication.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Reporters Shield and hostile-jurisdiction review — meta-methods
- URL: https://www.occrp.org/en/announcement/occrp-and-partners-announce-reporters-shield
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP and the Vance Center created a multi-jurisdiction network for training, pre-publication review, and defense; Suisse Secrets also showed jurisdiction-specific access/publication constraints.
- Types: not coded (methodology unit)
- Evidence: Reporters Shield announcement and Suisse Secrets Swiss-law reporting (public first-party documentation).
- Systems: Reporters Shield
- Signature: jurisdictional legal-risk gate: map access, privacy, source-protection, defamation, and publication risks to counsel before release.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### OCCRP corrections process — meta-methods
- URL: https://www.occrp.org/en/corrections-policy
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Requests identify exact material, URL, reason, and support; confirmed errors receive corrections and formal notes, while unclear accurate wording may receive clarification.
- Types: not coded (methodology unit)
- Evidence: OCCRP corrections policy (public policy documentation).
- Systems: OCCRP corrections intake
- Signature: versioned-correction path: preserve the challenged claim, submitted support, editorial decision, and dated correction/clarification note.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Aleph/FtM open-source ecosystem — meta-methods
- URL: https://github.com/alephdata
- Partner/awards: Not applicable (methodology/tool unit)
- Found: The public stack includes FollowTheMoney, alephclient, memorious, and the prior Aleph line; old ingest-file is archived and old Aleph maintenance ended after December 2025.
- Types: not coded (methodology unit)
- Evidence: alephdata GitHub organization, ingest-file repository, and Aleph FAQ (public code/documentation).
- Systems: Aleph; FollowTheMoney; alephclient; memorious; ingest-file
- Signature: forkability-support diff: inventory open components and distinguish architectural availability from current upstream product support.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### OCCRP reporter/data utility set — meta-methods
- URL: https://github.com/occrp
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP publishes practical investigation exhaust for file inventory, Cronos parsing, air-traffic analysis, Aleph classification, collaborative spending data, and a historical ID frontend.
- Types: not coded (methodology unit)
- Evidence: OCCRP GitHub repositories (public code/data; archival status varies).
- Systems: datasurvey; cronosparser; airtraffic; clcnn-classifier; COVID-19-spending-2020; id-frontend
- Signature: small-tool exhaust capture: package bounded parsers, environments, and cleaned datasets from investigations while labeling age and support state.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### VIS typed investigative visual grammar — meta-methods
- URL: https://www.occrp.org/en/feature/history-of-occrp
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Visual Investigative Scenarios made ownership, payment, association, and proxy relationships shareable; the standalone service is historical and Aleph diagrams now cover part of the role.
- Types: not coded (methodology unit)
- Evidence: OCCRP history/year-end pages, current redirect, and Aleph network-diagram documentation (public documentation).
- Systems: Visual Investigative Scenarios (historical); Aleph network diagrams
- Signature: typed-scenario visualization: render evidence-bearing ownership, payment, association, and proxy edges in a common visual language.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Russian Asset Tracker documentary inclusion rule — meta-methods
- URL: https://www.occrp.org/en/project/russian-asset-tracker
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP ID, a data specialist, fact-checkers, and jurisdictional partners included assets only when documentary ownership evidence supported the connection and disclosed the tracker’s final vintage.
- Types: not coded (methodology unit)
- Evidence: Russian Asset Tracker project and interactive pages (public methodology; mixed registry/leak inputs).
- Systems: Russian Asset Tracker; land/company/asset registries; ICIJ leak corpora
- Signature: verified-asset register: include an asset only after documentary ownership/control proof, expose the evidence edge, and publish update/sunset state.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Funding provenance and firewall control — meta-methods
- URL: https://www.occrp.org/en/gift-and-donation-acceptance-policy
- Partner/awards: Not applicable (methodology/tool unit)
- Found: OCCRP discloses institutional donors and restrictions, rejects conflicts, bars donor control of specific stories, and treats funding geography as a possible corpus-coverage bias to audit.
- Types: not coded (methodology unit)
- Evidence: Gift/donation policy, editorial FAQ, annual reports, and tax statements (public first-party records).
- Systems: OCCRP donor disclosures; OCCRP annual reports and tax statements
- Signature: funding-provenance audit: record funder, restriction, period, and firewall so later users can test source-program coverage for donor-shaped gaps.
- Method: same as URL
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

## Regional state capture and elite networks (report-11)

### All the President’s Men: State Projects Handed to Apparent Proxies in Kyrgyzstan (2024) — state-capture
- URL: https://www.occrp.org/en/investigation/all-the-presidents-men-state-projects-handed-to-apparent-proxies-in-kyrgyzstan
- Partner/awards: OCCRP-hosted joint reporting by Eldiyar Arykbaev (OCCRP), Bolot Temirov (Temirov Live), and Kloop; partner editions appeared at Kloop, Kazakhstan’s Vlast, and Temirov LIVE. The story calls Temirov Live an OCCRP member center and describes Kloop as a collaborating outlet. No ICIJ or Forbidden Stories coordination is stated (article credits and partner editions).
- Found: Reporters identified **at least 11 projects** run through the Presidential Administrative Directorate. Costs were available for only six, totaling **$137 million**; the other five had disappeared behind reduced procurement and budget transparency. Five apparent contractors were interlinked through directors, shareholders, workers, telephone labels, hometown and employment ties. Their formal owners or directors included friends and associates of President Sadyr Japarov, his son, or Directorate chief Kanybek Tumanbayev.
- Types: capture-by-opacity; proxy-contractor graph; state-to-private asset drift
- Evidence: **Corporate registry records** — incorporation, shareholder, director, and re-registration histories collected after procurement records became unavailable; used to connect the five companies and time their creation or transfer; **Land records and official decrees** — cadastral ownership and the decree granting Presidential Palace land; obtained from official/public records and direct agency requests; **Government video and state-media captions** — a worker identified as belonging to Sapat Zhol and contractor-linked people present at project sites; obtained from public broadcasts; **Social media and open-web evidence** — TikTok factory videos, worker overlap, photographs, GetContact labels, and posts by associates; collected from the public web, with the source accounts listed by OCCRP; **Confidential operational sources** — a Directorate insider, a railway insider, and company insiders supplied contractor names and alleged true-control details; reporter-obtained, not publicly reproducible
- Systems: Corporate registry records; Land records and official decrees; GetContact; TikTok
- Signature: hidden-contract proxy join: state project announcements and official site footage joined to corporate and land records on project site, contractor name, director/shareholder, incorporation date, and parcel, then joined to appointments and social connections on person/phone/employer, revealed five nominal contractors converging on one presidential-administration circle.
- Method: https://www.occrp.org/en/investigation/all-the-presidents-men-state-projects-handed-to-apparent-proxies-in-kyrgyzstan
- Impact: No discrete official investigation or policy response attributable to this May 2024 story was identified on its page; Japarov, Tumanbayev, the Directorate, airport management, and named owners did not answer detailed questions.
- Dependency: (b) — public re-anchor; hidden discovery remains.

### How to Build a Customs Empire (2020) — state-capture
- URL: https://www.occrp.org/en/project/the-matraimov-kingdom/how-to-build-a-customs-empire
- Partner/awards: Explicit project collaboration among OCCRP, **Kloop**, RFE/RL’s **Radio Azattyk**, and **Bellingcat**. The landing page lists the four organizations and protects unnamed local reporters for safety; no ICIJ or Forbidden Stories lead is stated (project credits).
- Found: The Matraimov and Abdukadyr families appeared to control **three key customs terminals**, which had become the only practical option for trucks importing Chinese goods into Kyrgyzstan; one southern terminal was used almost exclusively by the Abdukadyrs’ Abu Sahiy network. UniLab, a licensed **37-hectare** logistics center, opened in 2016 but received no trucks while customs officers redirected traffic elsewhere. It began receiving the northern-route traffic only after the founder and his partners sold it in November 2016 and ownership cycled through a wrestler, a police officer, and people connected to the Abdukadyr network.
- Types: regulatory-chokepoint capture; proxy succession; market-access coercion
- Evidence: **Company histories** — registry records for UniLab, Fast Cargo, Tarim Trans, Mega Logistik, and related firms; obtained from Kyrgyz corporate records and used to reconstruct short ownership tenures; **Land and license records** — parcel owners beneath terminals plus warehouse and customs-service permissions; public/requestable administrative records; **Social media and local-language reporting** — photographs linked nominal owners to network figures; Radio Azattyk documented UniLab’s difficulties; obtained from public profiles and partner archives; **Industry and operational interviews** — drivers, logistics professionals, former partners, and three protected sources described truck redirection, terminal use, and coercive pressure; reporter-obtained; **Prior source archive** — the earlier Saimaiti material seeded the Abdukadyr–Matraimov network and customs-fraud hypothesis; obtained from an insider and later published by OCCRP (Saimaiti archive)
- Systems: Company histories; Land and license records; Saimaiti archive
- Signature: chokepoint ownership succession: customs licenses and truck-route destinations compared before and after ownership changes on terminal, date, and traffic corridor, then joined to corporate/land records on company, shareholder, director, and parcel, revealed that traffic migrated to facilities after control passed to Matraimov–Abdukadyr associates and proxies.
- Method: [inferred]
- Impact: The broader Matraimov investigations were cited when Kyrgyz security services arrested Matraimov in October 2020; the United States later sanctioned him, and he pleaded guilty to corruption and paid about **$24.5 million** to the state. These are project-level impacts, not outcomes uniquely attributable to this article (arrest, U.S. sanctions, guilty plea).
- Dependency: (b) — public re-anchor; hidden discovery remains.

### The ‘Beautiful’ Life of a Kyrgyz Customs Official (2020) — state-capture
- URL: https://www.occrp.org/en/project/the-matraimov-kingdom/the-beautiful-life-of-a-kyrgyz-customs-official
- Partner/awards: Part of the explicit OCCRP–Kloop–Radio Azattyk–Bellingcat collaboration. OCCRP published two linked reporters’ notebooks showing the open-source geolocation work (project credits, Dubai notebook, Karven notebook).
- Found: Matraimov’s 2011–2017 declarations listed two Soviet-era apartments, but his wife’s posts showed the family using an Osh mansion and a **279-square-meter Bishkek penthouse**, both registered to Matraimov’s mother before passing to family members. Reporters reviewed roughly **100 travel photographs** posted since 2015, reconstructing stays at five-star hotels, luxury travel, and later repeated use of a Dubai penthouse; comparable units sold for about **$1 million** (Dubai notebook).
- Types: declared-means/lived-assets divergence; kin-title parking; social-post property attribution
- Evidence: **Asset and income declarations** — official filings for 2011–2017, obtained by reporters and used as the declared baseline; **Property records** — title and inheritance histories for the Osh, Bishkek, and Issyk-Kul properties; obtained from land/property records; **Public social media** — posts by Uulkan Turgunova, a household employee, relatives, and associates; collected from Instagram, Facebook, and Odnoklassniki; **Open-source geolocation** — skyline, window geometry, façade, floor height, interiors, and satellite imagery matched posts to Al Fattan Marine Towers and specific lakeside cottages (Dubai notebook, Karven notebook); **Leaked Dubai property data** — used in the earlier $12 million finding; non-public at acquisition and not required for the newly geolocated penthouse or the domestic declaration diff
- Systems: Asset and income declarations; Property records; Leaked Dubai property data; Instagram; Facebook; Odnoklassniki
- Signature: declared-wealth lifestyle diff: official asset declarations joined to title records on official/relative and property, then compared with geolocated family posts on interior, skyline, date, and recurring use, revealed high-value properties and travel absent from the declared household balance sheet.
- Method: https://www.occrp.org/en/project/the-matraimov-kingdom/the-matraimovs-dubai-apartment
- Impact: Matraimov had already been arrested and had agreed to compensate the state before this December article; the story therefore reports official status rather than claiming causation. Later proceedings recorded a guilty plea and approximately $24.5 million paid to the state (story chronology, plea).
- Dependency: (a) — open records carry the decisive detector.

### Money for Nothing: South Africa Paid a Firm Millions for Pretending to Manage Its Properties (2020) — state-capture
- URL: https://www.occrp.org/en/project/the-state-capture-papers/money-for-nothing-south-africa-paid-a-firm-millions-for-pretending-to-manage-its-properties
- Partner/awards: OCCRP publication by Khadija Sharife and Mark Anderson. The State Capture Papers page says OCCRP exclusively obtained the Trillian server; no external coordinator, ICIJ role, Forbidden Stories role, or story-specific award is stated ().
- Found: Transnet paid Trillian the equivalent of **$2.8 million** in 2016 for property-management services, although OCCRP found no evidence Trillian or its two front companies managed the properties. The proposal would move nearly **150 properties worth over 4 billion rand ($275 million)** and producing **610 million rand ($41.8 million)** annually into a private trust; the private managers would take **27.5 percent** of income.
- Types: pre-authorization billing; service-without-performance; front-company procurement insertion
- Evidence: **Trillian server** — internal emails, proposals, PowerPoints, confidential invoices, and legal advice; exclusively obtained by OCCRP, not a public record source (); **Corporate records** — Avren’s incorporation date and proxy links; public/company-registry verification of internal claims; **Procurement law and tender notices** — requirements for public competition and the later tender with no announced winner; open legal/administrative records; **State Capture Commission testimony** — Lynne Brown’s sworn account used to test what the ministry knew; public inquiry record
- Systems: Trillian server; Corporate records; Procurement law and tender notices
- Signature: invoice-authorization chronology: internal invoices and emails compared with proposal, approval, incorporation, tender, and payment dates on project/vendor/date revealed billing beginning before legal authorization and a vendor incorporated only after entering the bid.
- Method: https://www.occrp.org/en/project/the-state-capture-papers
- Impact: The named Trillian and Gupta transactions were already subjects of South African government investigations and the State Capture Commission. No separate official outcome caused by this July 2020 article was identified, so ongoing proceedings are not presented as story impact.
- Dependency: (c) — central proposition needs non-public records.

### The 700-Million-Dollar Man (2019) — state-capture
- URL: https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/the-700-million-dollar-man
- Partner/awards: Joint RFE/RL, OCCRP, and **Kloop** reporting; OCCRP explicitly calls Kloop its Kyrgyz member center. The project won the **2019 IRE Tom Renner Award** and an Egizbaev investigative prize (award announcement).
- Found: Aierken Saimaiti said he moved at least **$700 million** in wire transfers and cash from Kyrgyzstan to roughly a dozen countries over five years, largely for the Abdukadyr network; Kyrgyz financial police separately reported hundreds of millions wired through his company and wife. Five source-provided sales contracts called for **$114 million** in goods in one year, while the bazaar supposedly receiving them had total turnover of only **$16.5 million across six years**—a paper-versus-capacity mismatch.
- Types: insider-ledger re-anchoring; trade-cover capacity mismatch; customs-patronage revenue share
- Evidence: **Saimaiti archive** — ledgers, 843 deduplicated transaction records, invoices, bank slips, sham loan and sales contracts, and interviews; insider-supplied and later released with redactions; **Corporate registries** — company trails in China, Kyrgyzstan, Uzbekistan, the UAE, Germany, the UK, and the US; independently obtained public/requestable records; **Official records** — Kyrgyz financial-police figures, a Kazakh court ruling on improper cargo paperwork, government agreements, and public asset declarations; **Operational testimony and site reporting** — officials, customs officers, business competitors, drivers, and visits to bazaars and terminals; reporter-obtained corroboration; **Property data** — a leaked Dubai database plus public property/company information tied the Matraimov and Abdukadyr families to a joint development
- Systems: Saimaiti archive; Corporate registries; Official records; Property data
- Signature: insider-ledger/public-record reconciliation: insider transaction and contract rows joined to financial-police totals, bank confirmations, corporate registrations, property records, and court findings on company, amount, date, signatory, and stated goods revealed which transfers were independently anchored and where paper trade dwarfed real business capacity.
- Method: [inferred]
- Impact: The reporting led to protests, and Prime Minister Mukhammedkalyi Abylgaziev requested an investigation into customs corruption. The United States later sanctioned Matraimov; Kyrgyz proceedings produced a guilty plea and roughly $24.5 million in compensation (award/impact announcement, sanctions, plea).
- Dependency: (b) — public re-anchor; hidden discovery remains.

### A Real Estate Empire Built on Dark Money (2019) — state-capture
- URL: https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/a-real-estate-empire-built-on-dark-money
- Partner/awards: Part of the Tom Renner-winning joint project by OCCRP, RFE/RL’s Radio Azattyk, and member center Kloop, with jurisdictional reporting across Germany, the UK, the US, and Dubai (award).
- Found: Saimaiti’s records showed at least **$75 million** wired to EU accounts, **$31 million** to Bank of America accounts, and **$104 million** to Dubai accounts or developers. These totals tracked closely with Kyrgyz financial-police country totals. Land and company records identified at least **20 properties**. Known purchase value was at least **$65 million**: roughly $44 million in the UK, $19 million in Dubai, and $2 million in the US, excluding incomplete German and development costs.
- Types: flow-to-asset conversion; purpose-code contradiction; phantom-development parking
- Evidence: **Source-provided wires and contracts** — Saimaiti’s transaction spreadsheet, transfer orders, sham loans, and contracts; insider material later released by OCCRP; **Land/deed and permitting records** — title, purchase values, planning applications, and parcel histories in the UK and US; public or requestable local records (published UK ownership records); **Corporate filings and financial statements** — Companies House and German company accounts established owners, intercompany funding, assets, and operating capacity; **Dubai property database** — compiled by real-estate professionals, obtained by C4ADS, and provided to OCCRP; non-public at acquisition; **Shipping/import records and site visits** — US imports of construction materials, furniture, and luxury vehicles plus physical checks of addresses and development sites; public commercial records and constructed reporting
- Systems: Land/deed and permitting records; Corporate filings and financial statements; Dubai property database; UK Companies House
- Signature: wire-to-property reappearance join: source transfer rows joined to corporate funding and deeds on beneficiary company, amount band, date, and property, with wire purpose text compared to recipient business and parcel identifier, revealed “textile” or “loan” payments reappearing as land, homes, and stalled developments.
- Method: [inferred]
- Impact: The project-level protests, customs investigation request, U.S. sanctions, and Kyrgyz guilty plea apply here; no separate property forfeiture was identified as a direct result of this article (award/impact announcement, sanctions).
- Dependency: (b) — public re-anchor; hidden discovery remains.

### Azerbaijani First Family Big on Banking (2015) — state-capture
- URL: https://www.occrp.org/en/project/corruptistan-azerbaijan/azerbaijani-first-family-big-on-banking
- Partner/awards: OCCRP-hosted and credited simply to OCCRP. One supporting offshore-company link came from earlier ICIJ work, but the article is not presented as an ICIJ-coordinated project; no Forbidden Stories role or story-specific award is stated.
- Found: Aliyev family members and close advisers were significant shareholders in at least **eight banks controlling more than $3 billion in assets**, equal to **19 percent of Azerbaijan’s banking assets** at the start of 2014. Pasha, Kapital, and Xalq were among the four largest private banks. Public bank statements or audits identified daughters Leyla and Arzu Aliyeva as ultimate owners/controllers of Pasha and Kapital and “L. Aliyeva” as Xalq’s ultimate controlling party.
- Types: elite-sector concentration; related-market enclosure; address-based ownership bridge
- Evidence: **Audited bank financial statements** — Pasha, Kapital, Xalq, Expressbank, and other reports identifying shareholders, ultimate controllers, and asset totals; publicly released bank disclosures; **Holding-company and corporate records** — Ata, Pasha, Gilan, ADOR, United Enterprises, and shareholder companies; public/historical corporate records, though OCCRP noted Azerbaijan had restricted commercial-registry access in 2012; **Address co-registration** — ADOR shared an address with Mehriban, Leyla, and Arzu Aliyeva; registry/address evidence used as a relationship lead, not alone as beneficial-ownership proof; **Central-bank sector data and macro statistics** — bank asset shares, borrower count, interest rates, inflation, and exchange-rate changes; official/public statistics; **ICIJ offshore-company reporting** — supporting evidence for one connected industrial-bank family, not the decisive dataset for the eight-bank concentration
- Systems: Audited bank financial statements; Holding-company and corporate records; Address co-registration; Central Bank of Azerbaijan data; ICIJ offshore-company reporting
- Signature: beneficial-owner sector concentration: bank financial statements and audits joined to holding-company ownership on ultimate controller, shareholder, and reporting date, then divided by central-bank sector assets, revealed one ruling-family network controlling at least eight banks and 19 percent of sector assets.
- Method: [inferred]
- Impact: No official divestiture, enforcement action, or registry reform attributable to this June 2015 article was identified. The article itself notes that a 2005 asset-declaration law was not enforced and that commercial-registry access had already been restricted.
- Dependency: (a) — open records carry the decisive detector.

### Aliyevs’ Secret Mining Empire (2016) — state-capture
- URL: https://www.occrp.org/en/project/the-panama-papers/aliyevs-secret-mining-empire
- Partner/awards: **ICIJ-organized Panama Papers collaboration**. Süddeutsche Zeitung obtained Mossack Fonseca’s documents and ICIJ shared them with OCCRP and more than 100 media partners; OCCRP published this article, and RFE/RL contributed reporting. This is not an OCCRP-coordinated leak and has no Forbidden Stories role (Panama Papers project, story attribution).
- Found: President Ilham Aliyev had awarded six gold fields worth billions to a consortium of one UK and three offshore companies. Earlier reporting linked his daughters to an 11 percent share; Mossack Fonseca files revealed their control of another 45 percent through Londex Resources, bringing control to **56 percent**. The consortium spent nearly **$230 million** and produced up to **$30 million in gold** before stopping. About **300 workers** were left unpaid for nearly two years while remaining formally employed and unable to take other jobs.
- Types: self-dealing concession; offshore ownership peel-back; enforcement immunity for insiders
- Evidence: **Mossack Fonseca records** — shareholder/control documents for Londex and related offshore companies; leaked to Süddeutsche Zeitung and shared by ICIJ (project methodology); **Government and parliamentary records** — the concession award, parliamentary debate, profit split, lease term, and absence of a visible tender; official/public proceedings, although the full agreement was unpublished; **Financial statements and audit records** — $230 million spent, $146 million borrowed, unpaid bonus, penalty, and related-family bank loans; obtained financial records and audits; **Labor/court and ministry records** — worker emails, legal filings, and unanswered petitions to ministries; source-provided and public litigation/administrative material; **Worker/executive interviews and site reporting** — miners, former CEO Carl Caumartin, and mining executives; reporter-obtained and physically checked at Chovdar
- Systems: Mossack Fonseca / Panama Papers; Government and parliamentary records; Financial statements and audit records; Labor/court and ministry records
- Signature: concession-to-hidden-owner conflict join: public concession partners and percentage interests joined to offshore provider records on company, shareholder, intermediary, and date revealed that the awarding president’s daughters controlled 56 percent of the favored consortium.
- Method: [inferred]
- Impact: On May 25, 2016, President Aliyev ordered state-owned AzerGold to acquire the four-company consortium, including the two companies OCCRP and earlier reporting linked to his daughters. This was an official state takeover, though the terms and causal relationship to the April story were unclear (follow-up).
- Dependency: (c) — central proposition needs non-public records.

### Azerbaijani Insiders Benefited from Currency Collapse (2016) — state-capture
- URL: https://www.occrp.org/en/project/corruptistan-azerbaijan/azerbaijani-insiders-benefited-from-currency-collapse
- Partner/awards: OCCRP publication reported by Dave Bloss, Miranda Patrucic, Khadija Ismayilova, and OCCRP Azerbaijan. No external coordinator, ICIJ project role, Forbidden Stories role, or story-specific award is stated.
- Found: Two transactions by the Aliyev family’s network and close associate Ashraf Kamilov produced at least **100 million manat ($64 million)** around the 2015 devaluations, while the banking sector lost over **$1 billion** and four banks lost licenses. Synergy bought a nearly inactive bank in late December 2014, recapitalized it, obtained a renewed license on January 26, and three days later lent state oil company SOCAR **$52 million in dollars**. Three weeks later the first devaluation produced a 13 million manat gain; after the second, the loan’s gain reached **39.2 million manat**.
- Types: event-eve currency positioning; captured-regulator tolerance; state-company value transfer
- Evidence: **Bank annual reports and independent audits** — loan currency, related parties, capital, collateral, foreign-exchange gains, and violations; public financial disclosures; **Holding-company records** — ownership of Caspian Development Bank, AtaBank, Pasha Bank, Synergy, and AAC; public/historical corporate and bank disclosures; **Central-bank and executive records** — license date, exchange-rate decisions, prudential limits, and creation/appointments of the new Financial Market Supervisory Board; official/public records; **SOCAR financial statements** — showed roughly $1.8 billion in cash and equivalents, including more than $1 billion in dollars, testing whether it needed the $52 million loan; public company accounts; **Reporter calculations** — before/after currency conversion and profit reconstruction from filed amounts and official rates; constructed analysis
- Systems: Bank annual reports and independent audits; Holding-company records; Central-bank and executive records; SOCAR financial statements; Reporter calculations
- Signature: event-window balance-sheet diff: year-end and transaction disclosures compared with devaluation dates on borrower, lender, currency, amount, and restructuring date revealed insider-linked entities switching into dollar assets days before the manat fell and capturing gains unavailable to ordinary borrowers.
- Method: [inferred]
- Impact: Azerbaijan created a new Financial Market Supervisory Board after the crisis, but the story notes that its CEO previously chaired Caspian Development Bank’s supervisory board. No post-publication enforcement attributable to the article was found.
- Dependency: (a) — open records carry the decisive detector.

### Montenegro: Buying up Paradise (Part 2) (2014) — state-capture
- URL: https://www.occrp.org/en/project/unholy-alliances/montenegro-buying-up-paradise-part-2
- Partner/awards: OCCRP story by Miranda Patrucic with contributions from **Dejan Milovac (MANS)**, **Stevan Dojčinović (CINS)**, and Lejla Camdžić (OCCRP); the series was published by OCCRP and regional outlets including Vijesti, Dan, Delo, and Oslobođenje. Unholy Alliances won the **2015 Global Shining Light Award** and was nominated for the European Press Prize; OCCRP’s award record preserves CINS in the story-era credit while later identifying Dojčinović with KRIK…
- Found: Stanko Subotić borrowed almost **€21 million** from the Đukanović family-controlled First Bank to buy coastal property, becoming its largest debtor; loans were often weakly secured, exceeded legal concentration limits, and allowed lump-sum maturity payments. Seven secret Central Bank/PwC reports showed San Investments was new, lacked income and a business plan, and had more loans than First Bank disclosed to examiners. The bank knew exposure exceeded **25 percent of its capital** and concealed it.
- Types: elite-credit privilege; criminal-collateral bridge; private-risk/public-rescue cascade
- Evidence: **Seven Central Bank/PwC examination reports** — loan files, collateral, concentration breaches, liquidity, and regulatory orders; secret reports obtained by OCCRP; **Internal bank records** — loan and deposit agreements, collateral substitutions, debt splits, and account information; non-public documents obtained by reporters; **Corporate and offshore records** — San Investments, Samuelson, Velo Business Services, Adriatic Overseas Holdings, and Lafino Trade; public/requestable records plus opaque BVI/Panama layers; **Land, mortgage, auction, tender, and bailout records** — island acquisition, failed auctions, bank mortgage, Duvankomerc bid, and state liquidity loan; public administrative/property records; **Court and law-enforcement records** — Šarić/Subotić cases, Interpol status, and later litigation revealing beneficial deposit ownership; public judicial records
- Systems: central-bank examination reports; Internal bank records; Corporate and offshore records; Land, mortgage, auction, tender, and bailout records; Court and law-enforcement records
- Signature: loan-to-land-to-bailout reconstruction: secret loan and examiner records joined to company ownership, parcel/mortgage events, criminal cases, and the state rescue on borrower, guarantor, property, amount, and date revealed private coastal speculation financed by a family bank and ultimately absorbed by taxpayers.
- Method: [inferred]
- Impact: Within a week of the series, MANS asked Montenegro’s Special Prosecutor for Organized Crime and Corruption to investigate a dozen officials and First Bank. OCCRP did not report an enforcement outcome in that notice (formal complaints).
- Dependency: (c) — central proposition needs non-public records.

### Montenegro: Prime Minister’s Family Bank Catered to Organized Crime (2014) — state-capture
- URL: https://www.occrp.org/en/project/unholy-alliances/montenegro-prime-ministers-family-bank-catered-to-organized-crime
- Partner/awards: OCCRP story by Miranda Patrucic with contributions from **Stevan Dojčinović (CINS)** and **Dejan Milovac (MANS)**; project-level Global Shining Light and European Press Prize recognition as above. MANS is described by OCCRP as its Montenegrin member center in a later institutional statement; the article preserves the historical CINS label (MANS member-center statement, award record).
- Found: Over **1,000 pages** of internal bank and Central Bank records showed First Bank opened accounts, accepted deposits, and issued favorable loans to Darko Šarić’s companies and associates while repeatedly failing anti-money-laundering and internal controls. Camarilla’s First Bank account was used to launder **€7.4 million**, according to the criminal case in which Duško Šarić was convicted; Lafino Trade made a **€6 million five-year deposit** and received only 1.5 percent interest while the bank was in a liquidity crisis.
- Types: criminal-client bank capture; KYC nullification; reciprocal liquidity
- Evidence: **Central Bank reports and internal bank files** — accounts, deposits, KYC gaps, loans, collateral, rates, and bank violations; non-public records obtained by OCCRP; **Corporate registries** — Delaware records for Lafino and related entities plus Montenegro company histories; public/requestable records used to resolve formal owners and proxies; **Court, prosecution, and trial records** — cocaine and money-laundering cases, convictions, transfers, and AML-agency testimony; public judicial records; **Land and mortgage records** — collateral properties and related Budva transactions; public title/security records; **Financial statements** — borrower losses, liquidity, and capacity; company accounts compared against loans
- Systems: central-bank examination reports; Corporate registries; Court, prosecution, and trial records; Land and mortgage records; Financial statements
- Signature: regulator-file/criminal-docket join: bank examiner accounts and loan rows joined to corporate ownership and criminal cases on company, beneficial owner, proxy, amount, account, and date revealed that convicted or accused traffickers were among a ruling-family bank’s most important and favorably treated clients.
- Method: [inferred]
- Impact: MANS’s post-series complaints asked the Special Prosecutor to examine First Bank and a dozen senior officials. No resulting prosecution was verified in the OCCRP follow-up used here (formal complaints).
- Dependency: (c) — central proposition needs non-public records.

## Kleptocracy and asset tracing (report-13)

### Newfound Assets of Russian Billionaire Besties: London Flats and Show Horses (2022) — asset-tracing
- URL: [OCCRP story](https://www.occrp.org/en/news/newfound-assets-of-russian-billionaire-besties-london-flats-and-show-horses); underlying [Russian Asset Tracker project](https://www.occrp.org/en/project/russian-asset-tracker).
- Partner/awards: This was OCCRP reporting inside the OCCRP-coordinated Russian Asset Tracker. The project credits OCCRP ID and 25 media/research partners, including OCCRP member centers or network partners BIRD, Investigative Center of Ján Kuciak, Investigace.cz, IrpiMedia, MANS, Oštro, Re:Baltica, and Siena; ICIJ supplied access to earlier leak projects but did not coordinate this story (project credits).
- Found: Eugene Shvidler controlled two London flats bought in 2010 for £20 million (then about $30.5 million), while his son Daniel owned a New York apartment bought for $2.7 million (London asset card, New York asset card). Roman Abramovich's daughter Sofia was linked to two elite show horses, while the oligarch's Airbus Eurocopter G-CLUL was valued at $4.9 million and held through BVI company Wenham Overseas (helicopter asset card).
- Types: Sanctions-edge asset surfacing; registry-flight; kinship-held wealth
- Evidence: **Sanctions/designation records — public government records:** target names and effective dates supplied the person universe and timing axis; the article links the applicable U.K. and EU designations; **Land/title records — public record or paid public lookup:** London and New York ownership and purchase prices anchored the residences (London asset card, New York asset card); **Aircraft registry history — public registry:** registration, beneficial-owner confirmation, and the U.K.-to-Russia change established the helicopter's asset identity and movement (helicopter asset card); **Equestrian competition and ownership records — specialist public sources:** the horses were linked to Sofia Abramovich through competition/ownership reporting cited by OCCRP
- Systems: government sanctions/designation lists; Land/title records; aircraft registries; Equestrian competition and ownership records
- Signature: Sanctions-date registry diff: sanctions subjects and first-degree relatives joined to land, aircraft, and specialist asset registries on normalized name, corporate owner, address, and asset registration, then registry state before/after the sanctions date compared on asset ID, revealed unlisted property and a helicopter's pre-sanctions jurisdictional flight.
- Method: https://www.occrp.org/en/project/russian-asset-tracker
- Impact: The story notes that U.K. authorities were already holding two Shvidler aircraft; that enforcement predated publication and should not be counted as story-caused impact.
- Dependency: (a) — open records carry the decisive detector.

### Mysterious Group of Companies Tied to Bank Rossiya Unites Billions in Assets Connected to Vladimir Putin (2022) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/russian-asset-tracker/mysterious-group-of-companies-tied-to-bank-rossiya-unites-billions-of-dollars-in-assets-connected-to-vladimir-putin).
- Partner/awards: OCCRP coordinated the investigation with Meduza and a cross-border team including Le Monde, Der Spiegel, profil, Investigace.cz, Siena, The Guardian, Follow the Money, IrpiMedia, and Yle; ICIJ was not the coordinator and the story's discovery leak was not an ICIJ project (story credits, tracker credits).
- Found: An email domain invisible on the public web, LLCInvest.ru, linked dozens of nominally separate companies holding at least $4.5 billion in cash and assets tied to Vladimir Putin's circle. The network included palaces, resorts, vineyards, aircraft, and yachts; companies appeared to transfer money and assets among themselves while relying on Bank Rossiya-linked infrastructure and personnel.
- Types: Latent infrastructure consortium; registry-route co-occurrence; communal balance-sheet
- Evidence: **Leaked email metadata — non-public discovery source:** Moskomsvyaz material exposed LLCInvest.ru in sender/recipient metadata and subject lines; OCCRP says reporters did not possess message bodies; **Corporate registries and company accounts — public records:** entity officers, owners, balance sheets, transactions, and common personnel established the public graph behind the domain; **Aircraft registry and flight tracking — public/specialist open data:** Russian aviation registrations and Flightradar records connected aircraft to private routes and LLCInvest entities; **Vessel registry, AIS, and customs records — public or commercially accessible records:** MarineTraffic and import/customs records established yacht identities, movement, winter storage, and valuation inputs; **U.S. Treasury designations — public government records:** designation narratives independently tied some assets and actors to Putin's circle
- Systems: Leaked email metadata; Corporate registries and company accounts; aircraft registries; AIS vessel tracking; U.S. Treasury designations; MarineTraffic / AIS; Flightradar; vessel registries
- Signature: Hidden-domain multiplex join: leaked sender/recipient metadata joined to corporate filings, company accounts, aircraft/vessel registries, and movement histories on email domain, legal entity, officer, registration number, and route revealed a cooperative-like $4.5 billion network behind formally separate owners.
- Method: https://www.occrp.org/en/project/russian-asset-tracker/mysterious-group-of-companies-tied-to-bank-rossiya-unites-billions-of-dollars-in-assets-connected-to-vladimir-putin
- Impact: The story cites sanctions and asset designations already in force as corroboration; no project-specific post-publication official action is asserted on the story page.
- Dependency: (b) — public re-anchor; hidden discovery remains.

### Sanctioned VTB Bank and Putin Ally Andrei Kostin Behind Luxury Austrian Hotel (2022) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/russian-asset-tracker/sanctioned-vtb-bank-and-putin-ally-andrei-kostin-behind-luxury-austrian-hotel).
- Partner/awards: Reported by OCCRP's Graham Stack and republished by iStories; it sits within the OCCRP-coordinated Russian Asset Tracker rather than an ICIJ or Forbidden Stories collaboration (tracker credits).
- Found: Sanctioned Russian state bank VTB secretly owned the five-star Hotel Tannenhof in St. Anton, Austria, through a Cyprus structure until 2015; the hotel was then moved into Cahulia Limited. Around the introduction of Austrian beneficial-ownership disclosure, half of Cahulia was sold for a nominal €500 (then $584) to Aktien Enterprises, producing two equal shareholders and avoiding the threshold that would identify a single UBO.
- Types: Threshold-engineered ownership; related-party control residue; proxy-capacity mismatch
- Evidence: **Cyprus beneficial-ownership register — official record, historically public:** natural-person UBOs supplied the decisive bridge between the two shareholder vehicles and the Kostin network; **Cyprus and Austrian corporate filings/accounts — public official records:** ownership changes, consideration, loans, receivables, and related-party classifications preserved the restructuring chronology; **Austrian land and business records — public or fee-access records:** tied the corporate chain to Hotel Tannenhof and its operating entities; **Sanctions lists and press reporting — public government/secondary sources:** supplied the risk status and background on Kostin and VTB; they were corroborative, not proof of hotel ownership
- Systems: Cyprus beneficial-ownership register; Cyprus and Austrian corporate filings/accounts; Austrian land and business records; Sanctions lists and press reporting
- Signature: Threshold-fragmentation ownership diff: pre/post-disclosure corporate ownership snapshots compared on entity and effective date, then joined to the contemporaneous UBO entry and financial-statement related-party balances on shareholder and counterparty, revealed a nominal 50/50 split that obscured continuing VTB/Kostin-network control.
- Method: [inferred]
- Impact: The relevant sanctions and ownership changes preceded publication; the investigation page does not claim a later official action caused by the story.
- Dependency: (c) — authoritative UBO access is no longer public.

### What Is “Dubai Unlocked”? Everything You Need to Know (2024) — asset-tracing
- URL: [OCCRP methodology/FAQ](https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know); [project hub](https://www.occrp.org/en/project/dubai-unlocked).
- Partner/awards: C4ADS obtained the data; Norwegian outlet E24 and OCCRP coordinated the reporting with 75 outlets. ICIJ was one listed participant, not the coordinator. OCCRP member centers and network partners named by the project include BIC, BIRD, Context Romania, Direkt36, Frontstory.pl/Reporters Foundation, Investigative Center of Ján Kuciak, Investigace.cz, IrpiMedia, iStories, KRIK, Oštro, Re:Baltica, Siena, and Slidstvo.Info (FAQ and full partner list).
- Found: Multiple leaks, mostly from the Dubai Land Department and public utility companies, described hundreds of thousands of properties and their owners or users, largely in 2020 and 2022. The data contained controlling parties plus dates of birth, passport numbers, and nationalities, though some records described renters rather than owners.
- Types: Property-owner risk overlay; identity-hardening; tenure-state disambiguation
- Evidence: **Dubai Land Department and utility leaks — non-public bulk records:** supplied the property/person candidate universe, historical snapshots, and identifying fields; C4ADS obtained and shared them with E24 and OCCRP; **Official Dubai land registry — public but query-constrained government service:** reporters checked whether a named person remained an owner and, where necessary, matched passport information through a public government owner-check database; **Sanctions, court, government, and corporate records — public official records:** established public-interest status, legal allegations, company links, and cross-border identities; the FAQ describes these collectively as official records and open-source research; **Other leaked datasets — non-public corroboration:** passports and cross-border ownership traces strengthened identity resolution but did not substitute for independent confirmation
- Systems: Dubai Land Department records; official Dubai land registry; Sanctions, court, government, and corporate records; Other leaked datasets
- Signature: Bulk property-risk list join: leaked Dubai property/controller records joined to sanctions, criminal-case, fugitive, and PEP lists on name plus DOB/passport/nationality, then compared to the current official land registry on person/property ID, revealed roughly 200 high-interest people connected to more than 1,000 properties.
- Method: https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know
- Impact: After publication, the Financial Action Task Force said the findings would be reviewed during its next UAE assessment; this is project-level official uptake, not proof of enforcement against every named owner (OCCRP impact report).
- Dependency: (c) — central proposition needs non-public records.

### Destination Dubai: As the U.S. Was Rebuilding Afghanistan, Contractors Snapped Up Properties in the UAE (2024) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/dubai-unlocked/destination-dubai-as-the-us-was-rebuilding-afghanistan-contractors-snapped-up-properties-in-the-uae).
- Partner/awards: Joint reporting by Lighthouse Reports and OCCRP, with Afghan reporting and records work involving Etilaat Roz; it was published inside the OCCRP/E24-coordinated Dubai Unlocked collaboration. ICIJ participated in the umbrella project but did not coordinate this story (story credits, project partner list).
- Found: Afghan contractors Mir Rahman Rahmani and Ajmal Rahmani, whom the U.S. Treasury sanctioned in December 2023 over an alleged fuel-procurement corruption scheme, held at least $15.2 million in Dubai property. Their portfolio included two residential towers and villas, with 228 units across Ocean Residencia and Fern Heights; obtained rental contracts indicated more than $2 million a year in rent.
- Types: Procurement-to-property conversion; cross-jurisdiction portfolio assembly; rent-yield corroboration
- Evidence: **Dubai property leaks — non-public bulk records:** supplied the owner/property candidates and historic portfolio snapshot (project method); **Dubai official property checks — public query service:** confirmed ownership status under the Dubai Unlocked verification protocol (project method); **U.S. Treasury sanctions and U.S. procurement/court records — public official records:** supplied the alleged $200 million fuel scheme, contractor identities, and the government-revenue context; allegations remain allegations because the Rahmanis contest them in court; **Rental agreements — obtained private contracts:** established an income-based check exceeding $2 million annually; **German land/company records and valuation work — public or fee-access official records plus partner analysis:** extended the same beneficiary network to €197 million in German real estate
- Systems: Dubai property leaks; Dubai official property checks; U.S. Treasury sanctions and U.S. procurement/court records; Rental agreements; German land/company records and valuation work
- Signature: Procurement-event property timeline join: U.S. contractor awards, sanctions allegations, and court records joined to leaked Dubai owner/transaction snapshots and German land companies on person, company, passport/DOB, parcel, and acquisition date revealed a cross-border property portfolio accumulated during and after the reconstruction-contract period.
- Method: https://www.occrp.org/en/project/dubai-unlocked/what-is-dubai-unlocked-everything-you-need-to-know
- Impact: The umbrella investigation prompted FATF to say it would review the findings in its next UAE assessment; no story-specific forfeiture or contractor enforcement is attributed to this article (OCCRP impact report).
- Dependency: (c) — central proposition needs non-public records.

### Leaked Emails Reveal How Putin's Friends Dodged Sanctions With Help of Western Enablers (2023) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/the-rotenberg-files/leaked-emails-reveal-how-putins-friends-dodged-sanctions-with-help-of-western-enablers); [official FAQ](https://www.occrp.org/en/project/the-rotenberg-files/frequently-asked-questions).
- Partner/awards: The Rotenberg Files was jointly obtained and coordinated by OCCRP and Russian investigative outlet iStories, with more than 60 reporters and 17 outlets, including OCCRP network partners IrpiMedia, Re:Baltica, Delfi, Yle, and Transparency International UK. It was not an ICIJ or Forbidden Stories project (project hub, ).
- Found: More than 50,000 records, including nearly 30,000 emails from 2013–2020, documented how a management firm and Western lawyers, bankers, and service providers helped Boris and Arkady Rotenberg respond to sanctions (). Advisers considered ownership transfers and structures involving employees, a bodyguard, and Boris Rotenberg's romantic partner; a Helsinki arena plan explicitly centered on removing sanctions exposure.
- Types: Sanctions-response choreography; proxy-role reassignment; professional-enabler workflow
- Evidence: **Evocorp emails and files — anonymous non-public leak:** instructions, draft structures, client communications, and timing supplied intent and coordination; **Leaked Central Bank document — non-public regulatory record:** enumerated 13 closed-end mutual funds that public records did not transparently attribute to the Rotenbergs; **Company and land registries — public official records:** verified entities, transfers, assets, and nominal owners named in the leak; **Sanctions lists and bank actions — public government and obtained institutional records:** fixed the enforcement calendar and showed operational consequences such as blocked accounts
- Systems: Evocorp emails and files; Leaked Central Bank document; Company and land registries; Sanctions lists and bank actions
- Signature: Sanctions-event corporate-state diff: corporate, fund, land, and banking states immediately before and after designation compared on owner, asset, account, and effective date, then joined to internal email instructions on client/entity/date, revealed a coordinated sanctions-evasion workflow implemented by Western enablers.
- Method: https://www.occrp.org/en/project/the-rotenberg-files/frequently-asked-questions
- Impact: The investigation documented sanctions and bank restrictions that predated publication; the project page does not identify a post-publication official action attributable to the lead story (project hub).
- Dependency: (c) — central proposition needs non-public records.

### Russian Oligarch Boris Rotenberg Spent Years Trying to Hide His Spanish Villa. The Authorities Froze It Anyway (2023) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/the-rotenberg-files/russian-oligarch-boris-rotenberg-spent-years-trying-to-hide-his-spanish-villa-the-authorities-froze-it-anyway).
- Partner/awards: Joint work by OCCRP, Spanish outlet infoLibre, and iStories, with republication by Yle; it belongs to the OCCRP/iStories-coordinated Rotenberg Files and not to ICIJ or Forbidden Stories (story credits, project hub).
- Found: A Costa del Sol villa commissioned by Boris Rotenberg's wife Karina was valued at $10.8 million, with interior spending that included about $256,000 for curtains. Internal emails described efforts to fund and distance the villa through Cypriot companies, including Logotax and Spanish owner Bangalor, and contemplated backdating or relabeling transactions.
- Types: Loan-label laundering; document-to-ledger consistency test; freeze-resistant proxy title
- Evidence: **Evocorp emails, invoices, and drafts — anonymous non-public leak:** established who commissioned the villa, how advisers discussed financing it, and apparent attempts to distance Rotenberg; **Cyprus company accounts — public filings:** annual balance-sheet and related-party classifications provided the externally reproducible residue of the financing; **Spanish land registry — fee-access official record:** identified title and the October 2022 freeze; **Sanctions records — public government records:** established Boris Rotenberg's status and the legal relevance of beneficial control
- Systems: Evocorp emails, invoices, and drafts; Cyprus company accounts; Spanish land registry; Sanctions records
- Signature: Loan-classification longitudinal diff: consecutive Cyprus financial statements compared on the same debtor, amount, and reporting period, then joined to Spanish title/freeze records and internal emails on company, property, and date, revealed a third-party debt relabeled as shareholder financing for Rotenberg's villa.
- Method: https://www.occrp.org/en/project/the-rotenberg-files/frequently-asked-questions
- Impact: Spanish authorities froze the villa in October 2022, before the June 2023 publication. It is an official action documented by the story, not a publication impact claim.
- Dependency: (c) — central proposition needs non-public records.

### How Yahya Jammeh Stole a Country (2019) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/the-great-gambia-heist/how-yahya-jammeh-stole-a-country); [project hub and “About the Data”](https://www.occrp.org/en/project/the-great-gambia-heist).
- Partner/awards: OCCRP coordinated and published the project, led by Khadija Sharife and Mark Anderson with Gambian journalist Saikou Jammeh and data work by Daniela Lepiz. The project credits do not identify ICIJ or Forbidden Stories as partners (project credits).
- Found: OCCRP estimated that former president Yahya Jammeh and associates stole or misappropriated nearly $1 billion during 22 years in power. The sector reconstruction attributed about $363.9 million to telecoms, $325.5 million to illegal timber, more than $100 million to Taiwanese aid, $71.2 million to central-bank accounts, $60 million to pensions/social security, and $55.2 million to oil-related transactions (project hub).
- Types: State-ledger extraction; sectoral loss rollup; command-account fusion
- Evidence: **Confidential bank statements and transfer records — non-public financial records:** supplied account-level inflows, outflows, beneficiaries, dates, and amounts (project “About the Data”); **Contracts, government correspondence, internal reports, and Jammeh directives — confidential state records:** supplied transaction purpose, authorization, and institutional context (project “About the Data”); **Janneh Commission testimony and records — public official inquiry:** corroborated signatory changes, withdrawals, account uses, and witness explanations while preserving the distinction between testimony and bank proof; **Corporate and trade records — public/obtained official records:** identified companies and counterparties in the timber, telecom, oil, and aid flows
- Systems: Confidential bank statements and transfer records; Contracts, government correspondence, internal reports, and Jammeh directives; Corporate and trade records
- Signature: State-account beneficiary rollup: confidential bank ledgers joined to government directives, contracts, company ownership, and commission testimony on account, date, amount, signatory, and beneficiary, then deduplicated and aggregated by sector, revealed nearly $1 billion in state extraction.
- Method: https://www.occrp.org/en/project/the-great-gambia-heist
- Impact: U.S. authorities later sought forfeiture of Jammeh's approximately $3.5 million Maryland property; OCCRP reported the action but did not claim the Great Gambia Heist caused it (OCCRP report on U.S. forfeiture action).
- Dependency: (c) — central proposition needs non-public records.

### The State Company That Fell Prey to the President (2019) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/the-great-gambia-heist/the-state-company-that-fell-prey-to-the-president).
- Partner/awards: OCCRP reporting by Khadija Sharife and Mark Anderson with data analysis by Daniela Lepiz inside the OCCRP-coordinated Great Gambia Heist; the project does not credit ICIJ or Forbidden Stories (project credits).
- Found: Yahya Jammeh made himself a signatory to Gambia National Petroleum Corporation accounts, bypassing ordinary board control; OCCRP identified at least $55 million in suspect or illicit transactions. Jammeh personally authorized about $18.5 million and roughly $30 million went to purposes unrelated to the company's oil mandate.
- Types: Mandate-payment divergence; purpose-field void rate; signatory capture
- Evidence: **GNPC bank statements — confidential financial records:** supplied the approximately 8,000-row transaction population and beneficiary concentration; **Presidential directives, correspondence, and internal reports — confidential government records:** established authorization and off-mandate instructions (project “About the Data”); **GNPC mandate and governance records — public/official records:** supplied the expected-purpose baseline against which payments were classified; **Janneh Commission testimony — public official inquiry:** corroborated Jammeh's signatory role and institutional override; **Corporate records — public official records:** resolved major beneficiaries and their relationship to government or the petroleum sector
- Systems: GNPC bank statements; Presidential directives, correspondence, and internal reports; GNPC mandate and governance records; Corporate records
- Signature: Mandate-to-ledger anomaly join: the GNPC transaction ledger compared to the company's statutory oil mandate and joined to directives, signatory records, and beneficiary companies on account/date/amount/payee revealed more than $55 million in diversions and a 40-percent purpose-record gap.
- Method: https://www.occrp.org/en/project/the-great-gambia-heist
- Impact: The Janneh Commission had already investigated Jammeh-era finances, and the later U.S. property action concerned his wider asset network; the story page does not claim a GNPC-specific post-publication recovery (U.S. action reported by OCCRP).
- Dependency: (c) — central proposition needs non-public records.

### Nigerian Oil and Dubai Land (2018) — asset-tracing
- URL: [OCCRP/Finance Uncovered investigation](https://www.occrp.org/en/project/dubais-golden-sands/nigerian-oil-and-dubai-land); [Dubai's Golden Sands hub](https://www.occrp.org/en/project/dubais-golden-sands).
- Partner/awards: Reported by Finance Uncovered journalists Margot Gibbs, Ted Jeory, and Lionel Faull and published by OCCRP. The Golden Sands data came from C4ADS and the project formed part of the Global Anti-Corruption Consortium, an OCCRP–Transparency International partnership; it was not coordinated by ICIJ or Forbidden Stories (story credits, project hub).
- Found: Shell and Eni paid $1.3 billion for the OPL 245 oil license; Nigeria transferred about $1.1 billion onward, and Malabu Oil and Gas received $801.5 million. About $336.5 million moved through Rocky Top Resources; an FBI analysis cited by the story traced $54 million toward a private jet, $34.2 million to Dubai, and $21.5 million to Gunes General Trading.
- Types: Contact-identifier bridge; proceeds-to-asset trace; selector triangulation
- Evidence: **Leaked Dubai property/residency data — non-public records obtained by C4ADS:** supplied owner/user contacts, property descriptions, and estimated net value (project hub, ); **OPL 245 payment authorizations, bank-flow records, and court/investigative documents — obtained or public legal records:** supplied the payment chain and the matching email address; **FBI financial analysis — government analysis cited in legal/investigative material:** supplied the jet and Dubai money-flow allocations; it is an official analytical assertion rather than independently published bank statements; **Phone and interview checks — direct verification:** a listed number and responses from relevant parties tested the Etete identity and alternative explanations
- Systems: Leaked Dubai property/residency data; OPL 245 payment authorizations, bank-flow records, and court/investigative documents; FBI financial analysis; AIS vessel tracking
- Signature: Exact-contact proceeds bridge: leaked Dubai property data joined to OPL 245 payment authorizations and financial-flow records on an exact email, then corroborated on phone/person identity, revealed Etete's Dubai property at the destination side of a disputed oil-license payment chain.
- Method: https://www.occrp.org/en/project/dubais-golden-sands
- Impact: The story reports ongoing and prior legal investigations into OPL 245 but does not assert a property seizure or other post-publication official action caused by this article.
- Dependency: (c) — central proposition needs non-public records.

### Yanukovych's Real Estate (2014) — asset-tracing
- URL: [OCCRP investigation](https://www.occrp.org/en/project/yanukovychleaks-national-project/yanukovychs-real-estate); [YanukovychLeaks project hub](https://www.occrp.org/en/project/yanukovychleaks-national-project).
- Partner/awards: This was a Ukrainian national collaborative project, not an OCCRP-originated leak or an ICIJ/Forbidden Stories collaboration. The story credits Lesya Ivanova of Nashi Groshi, Kateryna Kapliuk of OCCRP member center Slidstvo.Info, and Denys Bigus of ZIK; OCCRP hosted the project and its English-language publication (story credits, project hub).
- Found: After Viktor Yanukovych fled, divers recovered nearly 200 folders that departing staff had thrown into a lake at the Mezhyhirya residence; journalists and activists dried, organized, and investigated the records (project hub). Documents contradicted a claimed $33 million apartment sale to Serhiy Klyuyev by showing that Tantalit still managed or paid for relevant property, and they exposed common managers and payment channels around nominally separate homes.
- Types: Payer-over-title control; rescued-record reconstruction; claim-document contradiction
- Evidence: **Recovered Tantalit/Mezhyhirya files — rescued non-public records:** contracts, bills, plans, invoices, and correspondence supplied payer, manager, cost, and address links (project hub, ); **State architecture, permit, land, and technical-inventory records — public official records:** identified formal owners, construction status, parcel rights, and building specifications; **Corporate and employment records — public official records:** connected payers, managers, officials, and Tantalit-linked entities; **Site visits, neighbors, and photographs — direct observation/interviews:** checked whether the documentary address and physical property aligned
- Systems: Recovered Tantalit/Mezhyhirya files; State architecture, permit, land, and technical-inventory records; Corporate and employment records
- Signature: Utility-payer ownership override: recovered utility and construction payments joined to public title, permit, company, and employment records on address, payer, contractor, and manager revealed de facto presidential-network control of properties nominally held or claimed by others.
- Method: https://www.occrp.org/en/project/yanukovychleaks-national-project/yanukovychs-real-estate
- Impact: The story says Ukraine's Prosecutor General had received the documents and investigations had begun; this is an official response to the recovered archive, although the article does not quantify a recovery attributable to this particular real-estate analysis.
- Dependency: (c) — central proposition needs non-public records.

## Illicit trade, smuggling, and trafficking corridors (report-14)

### Illegal Chinese Cigarettes Flooding Latin America Flow Through Panama (2021) — illicit-trade
- URL: https://www.occrp.org/en/project/china-tobacco-goes-global/illegal-chinese-cigarettes-flooding-latin-america-flow-through-panama
- Partner/awards: OCCRP-coordinated joint reporting by Nathan Jaccard and Lilia Saúl (OCCRP), Sol Lauría (**Concolón**, Panama), and David Tarazona and Mateo Yepes (**Cuestión Pública**, Colombia); the project credits also name the Houston Chronicle and other country partners. No story-specific award was located.
- Found: Four Panama-registered firms tied by ownership, officers, or supply relationships to China Tobacco exported cigarettes into Latin American countries where official agencies or market checks found no legal CNTC retail market. Reporters tested 18 Spanish-speaking countries plus Spain; 11 governments said CNTC brands could not legally be sold, Chile said they could, and checks in the remaining six found none in normal legal outlets. (OCCRP) Finta exported more than **632 metric tons** of cigarettes from May 2013 to October 2018; over **599 metric tons in 44 shipments** went to Victor M. Guerra Inc., whose owner was convicted in the United…
- Types: unauthorized-market seeding; free-zone route laundering; smuggler-customer overlap
- Evidence: **Legal-market matrix — official/requested**: online regulator records and FOIA responses from health, tax, and tobacco-control bodies in 19 jurisdictions; acquired by country reporters through government websites and records requests. (OCCRP, “About This Investigation”); **Customs/trade ledgers — official or commercial trade data, acquisition vendor not disclosed**: Panamanian export records and U.S. import data supplied exporter, buyer, route, weight, value, and shipment count. (OCCRP); **Seizure microdata — records request**: Colombia Tax and Customs Police database and Brazilian seizure data obtained by FOIA; these supplied brand, year, and quantity but not always the companies involved. (OCCRP); **Corporate and litigation records — public/requestable**: Panama registry documents, U.S. court records for Guerra, and Colombian proceedings against Maestre tied legal entities to alleged smugglers. The public ICIJ Offshore Leaks database corroborated common officers; leaked Panama Papers emails…; **Field verification — constructed**: reporters checked supermarkets, tobacconists, kiosks, and street markets and bought CNTC brands in Panama, Colombia, and Mexico. (OCCRP)
- Systems: Legal-market matrix; Customs/trade ledgers; Seizure microdata; Corporate and litigation records; Mossack Fonseca / Panama Papers
- Signature: legal-market/manifest contradiction join: destination-country brand authorization and retail-availability records joined to customs shipments on **brand + destination country**, then joined to corporate and criminal records on **buyer legal name/owner**, revealed high-volume exports into countries with no lawful market and repeated sales to accused smugglers.
- Method: https://www.occrp.org/en/project/china-tobacco-goes-global/illegal-chinese-cigarettes-flooding-latin-america-flow-through-panama
- Impact: No post-publication enforcement action directly attributed to this story was located. The factory closure and export-permit cancellation described in the article predated publication and are evidence, not impact. (OCCRP)
- Dependency: (a) — open records carry the decisive detector.

### A Fake Shipping Container Leads to Chinese Cigarettes — and Italy's Camorra Crime Group (2021) — illicit-trade
- URL: https://www.occrp.org/en/project/china-tobacco-goes-global/a-fake-shipping-container-leads-to-chinese-cigarettes-and-italys-camorra-crime-group
- Partner/awards: OCCRP-coordinated reporting by Alessia Cerantola and Andrei Ciurcanu; the project credits identify Ciurcanu with OCCRP member center **RISE Romania**. This was not an ICIJ- or Forbidden Stories-led project, and no story-specific award was located.
- Found: Italian and Moldovan smugglers, some linked by prosecutors to the Camorra, bought **8.9 million cigarettes for $66,200**, loaded them into a cloned Messina Line container, and prepared an identically numbered container of bricks, mattresses, and cardboard at the same weight for formal export to Libya. Black-market resale could have yielded about **$1 million**. (OCCRP) Wiretaps and court records placed CTIEC executive Adina Ionescu inside the logistics, including customs-procedure advice; Italian prosecutors called her a “central pawn.” CTIEC said it fired her after learning of the case, and Ionescu denied involvement. (OCCRP)
- Types: documented-cargo substitution; corporate-insider facilitation; recipient-demand mismatch; smuggler-customer overlap
- Evidence: **Criminal case file — obtained from authorities/court**: Italian wiretap transcripts, search records, arrest/prosecution documents, and photographs of both containers supplied coordination, container identity, seizure, and corporate-stamp evidence. (OCCRP); **Factory trade/customs ledger — reporter-obtained, access path undisclosed**: ten years of CTIEC exports supplied buyers, destinations, quantities, shipment counts, and values. OCCRP says it “managed to obtain” the dataset but does not identify a public portal or records-request route. (OCCRP); **Corporate/physical-presence checks — public plus field**: Iraqi registration claims, an on-site check at Devmak's listed Duhok address, and interviews with occupants tested whether the high-volume buyer had a real operating presence. (OCCRP); **Illicit-market benchmarks — industry/regulatory**: a confidential tobacco-industry report, KPMG estimates, Italian customs observations, and seizure shares established Regina and Marble's black-market prevalence. (OCCRP)
- Systems: Criminal case file; Factory trade/customs ledger; Corporate/physical-presence checks; Illicit-market benchmarks
- Signature: container-identity twin diff: shipping and court records for two containers compared on **container number + declared route + weight**, then joined to physical seizure inventories and CTIEC buyer records, revealed the same identifier and mass attached to cigarettes in one location and junk formally exported from another, while the purported buyer's stamp sat with the factory insider.
- Method: [inferred]
- Impact: The prosecutions, arrests, extradition, and CTIEC's dismissal of Ionescu preceded publication; no later official action was located that OCCRP attributes to this story. (OCCRP)
- Dependency: (b) — public re-anchor; hidden discovery remains.

### Huge Quantities of Chinese Cigarettes Smuggled Into Ukraine (2021) — illicit-trade
- URL: https://www.occrp.org/en/project/china-tobacco-goes-global/huge-quantities-of-chinese-cigarettes-smuggled-into-ukraine
- Partner/awards: Joint OCCRP–**Kyiv Post** investigation reported by Anna Myroniuk; OCCRP coordinated the wider project, whose credits also name **RISE Romania** and other partners. No story-specific award was located. (Project credits)
- Found: CTIEC's Romanian factory exported at least **half a billion cigarettes** to 14 Ukrainian companies over seven years even though the State Fiscal Service and major producers said none of the Chinese brands was legally sold in Ukraine. (OCCRP/Kyiv Post) At least three recipient companies were subjects of a large-scale smuggling investigation. Duty Free Odesa imported 12.5 million Reginas in April 2017, one month before another 12.5-million-cigarette truck was stopped; linked Travel Retail Ukraine had imported 15.5 million in 2015. (OCCRP/Kyiv Post)
- Types: unlicensed-recipient concentration; duty-free diversion; regulator-silo failure
- Evidence: **Romanian export ledger — leaked**: CTIEC declarations supplied shipper, Ukrainian recipient, date, volume, and brand. The story explicitly calls the Romanian data leaked to OCCRP. (OCCRP/Kyiv Post); **Ukrainian court and investigation records — public/requestable**: search warrants, court orders, the smuggling case, and a judge's order compelling Odesa Customs to release documents supplied the intercepted shipment and falsified-refusal-letter trail. (OCCRP/Kyiv Post); **Registry/licensing records — public and commercial-public interface**: the official Ukrainian register, YouControl ownership histories, and regulator confirmations supplied officers, ownership changes, common addresses, and absence of licenses. (OCCRP/Kyiv Post); **Customs/seizure and pack evidence — official plus field**: Italian tax-police data attributed 17 percent of 41 metric tons of seized Regina/D&B/Dubao cigarettes in 2017–2019 to Ukraine; reporters found “duty-free sale only” packs in Ukrainian shops and online. (OCCRP/Kyiv Post); **Interviews — constructed**: detectives, a health-ministry tobacco-control official, experts, companies, and the state security service tested the documentary interpretation and recorded denials/limitations. (OCCRP/Kyiv Post)
- Systems: Romanian export ledger; Ukrainian court and investigation records; Registry/licensing records; Customs/seizure and pack evidence
- Signature: licensed-market/export-recipient join: leaked exporter rows joined to the destination's company register, license table, and criminal docket on **recipient legal name + registration number + shipment date**, then compared with lawful brand availability, revealed hundreds of millions of cigarettes going to unlicensed, linked, or investigated buyers in a market with no legal sale channel.
- Method: [inferred]
- Impact: Ukraine's smuggling investigation had been closed in December 2020 and was **reopened on April 29, 2021, one week after journalists asked the prosecutor general's office about it**—a documented pre-publication response to reporting activity. (OCCRP/Kyiv Post)
- Dependency: (b) — public re-anchor; hidden discovery remains.

### Making a Killing: The €1.2 Billion Arms Pipeline to the Middle East (2016) — illicit-trade
- URL: https://www.occrp.org/en/project/making-a-killing/making-a-killing-the-eur12-billion-arms-pipeline-to-middle-east
- Partner/awards: Joint **Balkan Investigative Reporting Network (BIRN)**–OCCRP project, also published with *The Guardian*; additional reporting included OCCRP member/partner reporters and **RISE Moldova**. The project was a 2017 Global Shining Light Award finalist.
- Found: Eight Central and Eastern European states approved at least **€1.2 billion** in arms and ammunition exports to Saudi Arabia, Jordan, the UAE, and Turkey after 2012; about **€500 million** was known delivered. Several years/countries were missing, so OCCRP described the total as a floor. (OCCRP/BIRN) The recipient states had little or no pre-2012 history of buying the relevant Soviet/Yugoslav-pattern weapons and did not generally use them, while more than 50 battlefield photographs/videos showed matching arms with Syrian and Yemeni factions, including groups accused of serious abuses. (OCCRP/BIRN)
- Types: conflict-supply surge; end-use diversion; license-despite-diversion-risk
- Evidence: **National/EU arms-export licenses and reports — public official**: values, commodity classes, exporter states, destination states, approval years, and known deliveries. (OCCRP/BIRN); **UN trade data and UN reports — public official**: delivered-value checks and sanctions/diversion context. (OCCRP/BIRN); **Flight and shipping records — public, observed, and requested**: timetables, flight tracking, carrier histories, air-traffic-control sources, port/transport documents, and U.S. procurement records reconstructed air and sea routes. (OCCRP/BIRN); **Battlefield imagery — open web**: more than 50 social-media photographs/videos; weapon markings supplied model, manufacturer country, and sometimes production year. (OCCRP/BIRN); **Confidential/leaked deal files — non-public**: Serbian Ministry of Defense papers and meeting minutes, cargo-carrier documents, two end-user certificates, and an export license supplied intent, inventory, and routing detail. (OCCRP/BIRN)
- Systems: national/EU arms-export registers; UN Comtrade; Flight and shipping records; Battlefield imagery; Confidential/leaked deal files
- Signature: trade-step-change/end-use contradiction: national export approvals and UN delivery values compared with each recipient military's **pre-conflict import baseline + compatible inventory**, then joined to battlefield images on **weapon model/marking + production country/year**, revealed a €1.2 billion surge whose goods appeared with undeclared users in Syria and Yemen.
- Method: [inferred]
- Impact: Within days, the EU External Action Service said it was examining the report and gathering data; OCCRP later reported that the EU announced monitoring and several countries reviewed policies. (Immediate reaction; award/impact summary)
- Dependency: (a) — open records carry the decisive detector.

### The Middle East Airlift (2016) — illicit-trade
- URL: https://www.occrp.org/en/project/making-a-killing/the-middle-east-airlift
- Partner/awards: Joint **BIRN–OCCRP** reporting by Lawrence Marzouk and Ivan Angelovski, with Atanas Tchobanov and Pavla Holcová; part of the Global Shining Light finalist *Making a Killing* project.
- Found: Reporters identified **68 cargo flights over 13 months** from Serbia, Slovakia, Bulgaria, and the Czech Republic to Saudi Arabia, the UAE, and Jordan—about one every six days. Eleven carriers appeared; Belarusian Ruby Star Airways operated nearly half. (OCCRP/BIRN) Serbia's Civil Aviation Directorate confirmed **49** flights carried arms after reporters presented their evidence, and Bulgarian customs confirmed one more. The remaining 18 were classified as highly likely based on military-airport destination, carrier arms history, or connection to confirmed flights. (OCCRP/BIRN)
- Types: cargo-route anomaly; carrier-risk recurrence; military-destination concentration
- Evidence: **Flight-event ledger — open and archival**: airport timetables, flight-tracking histories, aircraft/carrier history, and plane-spotter observations supplied dates, routes, equipment, stops, and operator. (OCCRP/BIRN); **Aviation/customs confirmations — obtained by reporter query**: Serbia's Civil Aviation Directorate and Bulgaria's customs agency confirmed 50 flight contents after reporters presented route evidence and loading photographs. (OCCRP/BIRN); **Contracts/end-user certificates — leaked**: arms contracts and certificates connected some flight events to specific cargo and declared users. (OCCRP/BIRN); **Loading photographs and destination classification — observed/open**: photographs at Belgrade and public identification of Prince Sultan, Al Dhafra, and Aqaba as military destinations strengthened the route inference. (OCCRP/BIRN)
- Systems: Flight-event ledger; Aviation/customs confirmations; Contracts/end-user certificates
- Signature: route-intent triangulation: flight schedules and tracks joined to **aircraft registration + timestamp + origin/destination**, compared with carrier arms history and military-airport status, then reconciled to customs/aviation confirmations, revealed a recurring air bridge whose frequency and cargo differed sharply from the pre-2012 baseline.
- Method: [inferred]
- Impact: Project-level, after the initial *Making a Killing* publication, the EU said it was monitoring the flow and looking at the report; several countries reviewed policy. (OCCRP)
- Dependency: (a) — open records carry the decisive detector.

### The Coyote's Trail: A Machine Gun's Path from Serbia to Syria (2017) — illicit-trade
- URL: https://www.occrp.org/en/project/making-a-killing/the-coyotes-trail-a-machine-guns-path-from-serbia-to-syria
- Partner/awards: Joint **BIRN–OCCRP** reporting by Ivan Angelovski, Jelena Cosić, Lawrence Marzouk, and Maria Cheresheva; part of the Global Shining Light finalist *Making a Killing* project.
- Found: A pristine M02 Coyote heavy machine gun visible with a Syrian Free Syrian Army fighter carried a serial number that Serbia's Ministry of Defense eventually confirmed was sold by state-owned Zastava Arms to Bulgarian broker BIEM in 2015 for declared export to Saudi Arabia. (OCCRP/BIRN) Zastava's 2015 accounts and official fragments indicated BIEM paid about **€2.75 million for 205 Coyotes**. The end-user certificate named Saudi security forces, which did not normally use the weapon, yet multiple new Coyotes and manuals appeared across Syrian battlefields. (OCCRP/BIRN)
- Types: serialized-item provenance; end-use diversion; risk-warning reversal
- Evidence: **Battlefield imagery — open web/direct source**: Facebook, Twitter, and YouTube images showed model, condition, crates/manuals, locations claimed by posters, and one unique serial number. (OCCRP/BIRN); **Serial lookup — official response obtained by repeated query**: reporters sent the image and serial to Serbia's Ministry of Defense; after follow-ups, it confirmed sale to BIEM in 2015. (OCCRP/BIRN); **Export/end-user records and company accounts — official/public plus confidential**: the end-user certificate and export-license process named Saudi forces; Zastava accounts supported the 205-gun order and price; confidential ministry minutes showed the earlier risk assessment. (OCCRP/BIRN); **Fighter and official interviews — constructed**: a Syrian fighter described training and delivery; Serbian officials and BIEM answered or declined specific claims. (OCCRP/BIRN)
- Systems: Battlefield imagery; Serial lookup; Export/end-user records and company accounts; Facebook
- Signature: serial-number chain-of-custody join: a battlefield photograph joined to manufacturer and ministry sale records on **weapon serial number**, then compared with the export certificate's **declared end user**, revealed a specific Saudi-certified Serbian weapon in the hands of a Syrian rebel unit.
- Method: [inferred]
- Impact: The documented EU monitoring response belongs to the 2016 project launch and should not be attributed specifically to this May 2017 follow-up; no separate official action tied to the Coyote story was located. (OCCRP impact summary)
- Dependency: (a) — open records carry the decisive detector.

### Ukraine's “Lost” Cigarettes Flood Europe (2008) — illicit-trade
- URL: https://www.occrp.org/en/project/tobacco-underground/ukraines-lost-cigarettes-flood-europe
- Partner/awards: **ICIJ-led**, not OCCRP-coordinated. The OCCRP project page says ICIJ worked with OCCRP journalists in Bosnia and Herzegovina, Romania, Russia, and Ukraine; this story was reported by Vlad Lavrov. The full project won IRE's 2008 Tom Renner Award; OCCRP says five of its contributors participated.
- Found: Ukraine's legal consumption plus exports exceeded 100 billion cigarettes, but companies manufactured/imported nearly **130 billion in 2008**, leaving a **30 percent/30-billion-stick surplus** that could not be absorbed by the declared market. ICIJ conservatively valued the illicit trade at **$2.1 billion annually**. (OCCRP/ICIJ) Production rose from **96.8 billion in 2003 to 129.8 billion in 2008**; Philip Morris alone produced 44 billion in 2008, up more than 85 percent since 2003, while JTI produced roughly 37 billion. (OCCRP/ICIJ)
- Types: production-absorption surplus; excise-gradient corridor; enforcement-capture gap
- Evidence: **Production/import/consumption/export series — official and industry-public**: Ukraine government statistics, Ministry of Health figures, and SOVAT tobacco/alcohol association data supplied annual national totals. (OCCRP/ICIJ); **Customs seizures and criminal cases — official/reporter-obtained**: national and regional case counts, pack quantities, brands, concealment methods, and customs-officer prosecutions tested where the calculated surplus surfaced. (OCCRP/ICIJ); **Excise stamps, prices, and corporate reports — public/physical**: marked packs, legal price comparisons, and BAT's published acknowledgment that Pall Mall output exceeded local demand established product origin and commercial incentive. (OCCRP/ICIJ); **Online seller test — open web/constructed**: searches found Moldova-based stores and bulk-delivery advertisements; a reporter inquiry obtained a quote for 1,000 cartons delivered to Germany. (OCCRP/ICIJ)
- Systems: Production/import/consumption/export series; Customs seizures and criminal cases; Excise stamps, prices, and corporate reports; Online seller test
- Signature: production-absorption gap: annual cigarette **production + imports** compared with **estimated lawful consumption + recorded exports** on country/year revealed roughly 30 billion unexplained sticks; that residual joined to neighboring-country seizure brands and excise stamps revealed the direction of leakage.
- Method: [inferred]
- Impact: No story-specific policy response was located. Project-level recognition: IRE awarded *Tobacco Underground* the 2008 Tom Renner Award for organized-crime reporting. (OCCRP award announcement)
- Dependency: (a) — open records carry the decisive detector.

### Going Undercover — Inside Baltic Tobacco's Smuggling Empire (2008) — illicit-trade
- URL: https://www.occrp.org/en/project/tobacco-underground/going-undercover-inside-baltic-tobaccos-smuggling-empire
- Partner/awards: **ICIJ-led** *Tobacco Underground* reporting in cooperation with OCCRP contributors; ICIJ's staff page names Stefan Candea, Roman Shleynov, Paul Christian Radu, Drew Sullivan, and the wider multinational team. The project won IRE's 2008 Tom Renner Award.
- Found: Jin Ling cigarettes were unavailable in Kaliningrad's ordinary shops and markets, yet Baltic Tobacco Factory managers offered an undercover reporter posing as a Romanian smuggler a **10-million-cigarette container for $102,500**, ready in two weeks. (OCCRP/ICIJ) Logistics manager Dmitry Gyrja said the factory could make a container in eight hours and operated continuously; director Vladimir Kazakov advised on Kaliningrad/Constanța and Lviv/Odesa routes and offered company trucks. (OCCRP/ICIJ)
- Types: covert supplier intent; smuggler-only product; border-tolerance observation
- Evidence: **Undercover audio/video — covertly constructed**: in June 2008 a reporter posed as a Romanian smuggler and carried concealed recording equipment through meetings and a factory tour. (OCCRP/ICIJ); **Direct factory observation — constructed**: machinery, brand mix, operating speed, trucks, loading activity, physical scale, and manager price/route quotes tested whether the offer was operationally plausible. (OCCRP/ICIJ); **Retail and border observation — constructed**: local-market checks established absence; route-following to Bagrationovsk established availability, repacking, price uplift, and visible customs tolerance. (OCCRP/ICIJ); **Wider project trade/customs data — public/commercial/requested**: ICIJ's project page identifies PIERS trade-data assistance, while the companion Jin Ling work used Russian and Polish customs records to reconstruct inputs and European routes. (ICIJ about page; ICIJ companion story)
- Systems: Undercover audio/video; Wider project trade/customs data
- Signature: market-absence/supplier-offer contradiction: lawful retail checks compared with factory output observation and EU seizure volumes on **brand + producer**, then linked to the supplier's covert route/price offer, revealed a product manufactured at industrial scale for customers who could not be found in its stated home market.
- Method: [inferred]
- Impact: No official enforcement response caused by this specific undercover story was located; the wider project received the Tom Renner Award. (OCCRP)
- Dependency: (c) — central proposition needs non-public records.

### Latin America's Lucrative People-Smuggling Networks (2020) — illicit-trade
- URL: https://www.occrp.org/en/project/the-cruel-road-north/latin-americas-lucrative-people-smuggling-networks
- Partner/awards: OCCRP and **Centro Latinoamericano de Investigación Periodística (CLIP)** coordinated the project “along with 16 media outlets in 14 countries.” The full credit page separately describes 18 partner organizations and names Animal Político, Periodistas de a Pie, Chiapas Paralelo, Voz Alterna, Univision Noticias, FACTum, La Prensa, El Universo, Anfibia, La Voz de Guanacaste, Profissão Repórter, Confluence Media, Efecto Cocuyo, The Museba Project,…
- Found: Reporters mapped two major networks moving African and Asian migrants through Brazil and as many as ten Latin American countries toward the United States, using airlines, buses, taxis, boats, false visas, seamen's books, local “coyotes,” and corrupt officials. (OCCRP/CLIP) Saifullah Al-Mamun's alleged network charged about **$7,600** from Bangladesh to Brazil and **$14,200** to the United States; Brazilian and U.S. authorities arrested Al-Mamun and six associates in 2019. (OCCRP/CLIP)
- Types: corridor-as-marketplace; policy-friction exploitation; distributed-fee extraction
- Evidence: **Police/investigative files — official/requested**: Brazilian, Honduran, Colombian, Guatemalan, Mexican, and U.S. cases supplied phone extractions, intercepted calls, money-transfer records, fake-visa evidence, route roles, arrests, and alleged official corruption. (OCCRP/CLIP); **Court and DOJ records — public**: U.S. indictments/pleas and Latin American prosecutions supplied defendants, aliases, charged conduct, convictions, and case status. (OCCRP/CLIP); **National encounter/immigration statistics — public official**: Costa Rica, Mexico, and U.S. counts supplied route-volume bounds and temporal growth. (OCCRP/CLIP); **Migrant itinerary/payment interviews — constructed**: dozens of migrants supplied origin, legs, transport mode, facilitators, prices, extortion, documents, and harms; country partners checked the route locally. (OCCRP project); **OSINT/field verification — open and constructed**: Bellingcat investigators and local outlets geolocated or checked route claims, documents, border sites, shelters, camps, and facilitator identities. (Collaboration credits)
- Systems: Police/investigative files; Court and DOJ records; National encounter/immigration statistics
- Signature: cross-border corridor stitching + fee-volume model: country-level apprehension events and police cases joined to migrant itineraries on **alias/person + border node + time window + transport leg**, then route volume multiplied by reported low/high package prices, revealed recurring handoff nodes and a bounded $150–350 million annual market.
- Method: [inferred]
- Impact: No post-publication policy or prosecution directly attributed to the project was located. Arrests and convictions in the story largely predated publication and form part of the evidence. (OCCRP/CLIP)
- Dependency: (a) — open records carry the decisive detector.

### Made in China: How Czech Companies Bought Tens of Millions of Rounds of Old Ammunition (2018) — illicit-trade
- URL: https://www.occrp.org/en/project/war-dog-millionaire/made-in-china-how-czech-companies-bought-tens-of-millions-of-rounds-of-old-ammunition
- Partner/awards: OCCRP collaboration with **BIRN Albania**, the **Czech Center for Investigative Journalism** (an OCCRP member center), Serbia's **Crime and Corruption Reporting Network (KRIK)** (OCCRP member center), and **NOVA TV** in North Macedonia. Reporters were Aubrey Belford, Saska Cvetkovska, Pavla Holcová, Maja Jovanovska, Pavle Petrović, and Lindita Çela. No award was located. (OCCRP)
- Found: Internal records from Albania's state-owned MEICO documented nine deals from 2010–2015 sending more than **81 million rounds**, 358 mortar rounds, and nearly **110 tons of RDX** to the Czech Republic. (OCCRP) Strnad-linked Real Trade Praha bought nearly **34 million rounds**; Martin Drda's STV Group bought about **31 million 7.62×39 mm rounds for $920,160**, roughly three cents each; the buyer of the remaining nearly 17 million rounds was unclear. (OCCRP)
- Types: inventory-destination void; obsolescent-stock brokerage; conflict-market inference
- Evidence: **MEICO inventory and sales files — internal/non-public**: nine-deal records supplied caliber, origin, quantity, price, buyer/destination, contract, and transport responsibility. (OCCRP); **Company emails — leaked**: Real Trade correspondence supplied internal participants, desired ammunition, proposed land route, and the Crnogorac referral. (OCCRP); **Diplomatic cable — publicly released leak**: a 2009 State Department cable on WikiLeaks recorded U.S. concern about the RDX and a rumored Czech buyer. (OCCRP); **Military/company statements and expert interviews — constructed**: Czech defense officials excluded domestic military use; MEICO's former director confirmed sales; companies described compliance; SIPRI/GRIP experts assessed plausible markets and uncertainty. (OCCRP); **Corporate/UN/public records — open**: company ownership and accounts, prior criminal proceedings, and a UN panel report contextualized the brokers. (OCCRP)
- Systems: MEICO inventory and sales files; Company emails; Diplomatic cable; Corporate/UN/public records
- Signature: stockpile-destination void: MEICO sale inventory joined to Czech buyer identities and compared with **Czech military caliber standards + disclosed domestic procurement**, then joined to leaked route emails on **deal date/item/buyer**, revealed 81 million obsolete rounds entering an intermediary market with no identified end user.
- Method: [inferred]
- Impact: No official action directly attributed to this story was located.
- Dependency: (c) — central proposition needs non-public records.

### Building a Highway to Crime From the Middle East Into Europe (2014) — illicit-trade
- URL: https://www.occrp.org/en/project/veggie-scam/building-a-highway-to-crime-from-the-middle-east-into-europe
- Partner/awards: Presented jointly by OCCRP and Romanian member center **RISE Project (RISE Romania)**; reported by RISE co-founder Romana Puiuleț with Daniel Bojin and Cristi Ciupercă. No story-specific award was located. (Project page)
- Found: A Swedish citizen of Iranian origin identified as AB appeared in Romanian records as owner of at least **80 companies** and was tried for **€16 million** in tax evasion, although his passport had been stolen and canceled in Sweden and he had never been to Romania; the court acquitted him in December 2013. (OCCRP/RISE) The wider network transferred debt-ridden Romanian companies to people whose identities were stolen or who did not understand the documents, leaving false targets for tax investigators; OCCRP estimated at least **€50 million** defrauded in 2008–2009. (OCCRP/RISE)
- Types: liability dumping; identity-reuse fan-out; straw-person victimization
- Evidence: **Romanian company/tax records — public/requestable**: ownership, company count, transfer timing, and tax debts supplied the portfolio and liability pattern. (OCCRP/RISE); **Court/prosecution files — public/requestable**: Ilfov tax-evasion proceedings, terrorism/migrant-smuggling files, witness statements, and a Romanian intelligence letter attached to the case supplied allegations, case outcomes, and the stolen-passport mechanism. (OCCRP/RISE); **Passport cancellation and foreign correspondence — official/personal record**: Swedish cancellation timing and AB's notices to Romanian authorities established that the identity document was invalid before the company takeovers. (OCCRP/RISE); **Victim/defendant/prison interviews — constructed**: AB, Morad Ahmed, and Al Dulaimi supplied competing accounts of identity use, document signing, migration assistance, and knowledge. (OCCRP/RISE)
- Systems: Romanian company/tax records; Court/prosecution files; Passport cancellation and foreign correspondence
- Signature: debt-dump identity reuse join: corporate ownership events and tax balances joined to passport-validity and court records on **person identity + transfer date + company**, revealed one canceled stolen identity attached to at least 80 companies and repeat migrant straw owners taking control after liabilities had accumulated.
- Method: [inferred]
- Impact: AB's acquittal and Al Dulaimi's conviction predated publication and should not be claimed as journalistic impact; no later action attributed to the story was located. (OCCRP/RISE)
- Dependency: (a) — open records carry the decisive detector.

## Human harms and public-service failures (report-16)

### System Failure: How Banned Doctors Move Across Europe, Leaving Patients Vulnerable (2025) — public-services
- URL: [OCCRP investigation](https://www.occrp.org/en/project/bad-practice/system-failure-banned-doctors-can-easily-move-across-europe-leaving-patients-vulnerable); [project page](https://www.occrp.org/en/project/bad-practice); [methods feature](https://www.occrp.org/en/project/bad-practice/bad-practice-how-we-built-a-database-of-delicensed-doctors)
- Partner/awards: A joint project coordinated by Kira Zalan of OCCRP, Eiliv Frich Flydal of Norway's VG, and George Greenwood of *The Times*, with reporters at roughly 50 outlets. Current OCCRP member centers in the credited team include Public Record, RISE Moldova, Re:Baltica, Hetq, KRIK, Investigace.cz, Oštro, and the Investigative Center of Ján Kuciak; Public Record did the Romanian reporting on Iuliu Stan. It was not ICIJ- or Forbidden Stories-led. Bad Practice won…
- Found: OCCRP and its partners confirmed **more than 100** physicians who were banned or suspended for serious wrongdoing in at least one jurisdiction but licensed in another; reporters confirmed through calls, appointments, or visits that a majority were actively practicing, not merely listed in stale registers. British regulators struck orthopedic doctor Iuliu Stan from the register after a tribunal found that he had administered rectal medication **278 times** to patients, mostly male, for sexual gratification. He remained licensed and employed at a Romanian public hospital after the British General Medical Council said it had notified Romania.
- Types: cross-border-sanction escape; warning-system non-use; disciplinary opacity
- Evidence: **Professional licensing registers — public administrative data, scraped or manually queried**: reporters sought every licensed physician in 49 countries; some countries offered downloadable registers, while Spain and Austria required multiple regional scrapers. Methods; **Discipline and revocation lists — public or request-obtained regulatory records**: only seven countries openly published inactive, suspended, or banned practitioners; reporters filed dozens of requests, with authorities in 17 countries supplying at least some licensing or discipline data. Methods; **Tribunal decisions, judgments, and court records — public adjudicative records**: these established that a sanction reflected substantial patient harm or crime rather than an administrative technicality. British tribunal decisions were public; Scandinavian board decisions were obtained by…; **IMI alert history — European Commission response to a records request**: anonymized case numbers and sanction dates were date-matched to known decisions, then followed with national requests for identities; **Active-practice checks — constructed verification**: partner reporters called employers, booked online appointments, or visited practices. Victim interviews and regulator/employer responses tested the human consequence and current status
- Systems: national professional licensing registers; professional discipline/revocation registers; Tribunal decisions, judgments, and court records; EU Internal Market Information system; Active-practice checks
- Signature: sanction-license cross-border anti-join: disciplinary/revocation records joined to active-license registers on normalized name plus date of birth, specialty, graduation date, and sanction date revealed practitioners present in the banned ledger of jurisdiction A but the active ledger of jurisdiction B; IMI alert history compared with that result on country and sanction date revealed non-filing and non-response.
- Method: https://www.occrp.org/en/project/bad-practice/bad-practice-how-we-built-a-database-of-delicensed-doctors
- Impact: The European Commission said it would examine regulatory solutions; Norway reopened dozens of cases and notified **nine doctors** of immediate suspension or revocation, while the U.K. regulator said it would tighten registration checks. OCCRP impact report
- Dependency: (a) — open records carry the decisive detector.

### How Private Equity and an Ambitious Landlord Put Steward Health Care on Life Support (2024) — public-services
- URL: [OCCRP investigation](https://www.occrp.org/en/investigation/how-private-equity-and-an-ambitious-landlord-put-steward-healthcare-on-life-support); [Steward Files project](https://www.occrp.org/en/project/the-steward-files)
- Partner/awards: OCCRP-hosted investigation by Khadija Sharife, also published with *The Boston Globe*. The project says nearly 300,000 Steward documents were leaked to OCCRP and shared with *The Boston Globe* and *Times of Malta*; the Daphne Caruana Galizia Foundation also contributed. The project was OCCRP-coordinated, not ICIJ- or Forbidden Stories-led. No story-specific award was listed on the project or OCCRP awards pages checked.
- Found: Cerberus, CEO Ralph de la Torre, and associated interests extracted **more than $1.3 billion** while Steward became dependent on its landlord, Medical Properties Trust (MPT), and headed toward bankruptcy. In 2016 MPT paid **$1.2 billion** for nine Massachusetts hospital properties and leased them back. OCCRP calculated that the real estate price was almost nine times what Cerberus had paid for the properties with the hospital businesses; Carney Hospital alone went from a **$12.5 million** Steward purchase to a **$263 million** MPT real-estate valuation.
- Types: care-asset stripping; disclosure divergence; regulatory-threshold engineering
- Evidence: **Internal Steward archive — leaked corporate records**: audited statements, operating agreements, ownership schedules, board presentations, loan and dividend correspondence, chats, and insolvency memoranda from the nearly 300,000-document trove; **SEC filings and correspondence — public regulatory records**: MPT annual reports, earnings disclosures, declared ownership percentages, tenant exposure, rent revenue, and SEC questions supplied the public representation; **Property transaction, lease, and valuation records — mixed public and leaked documents**: hospital acquisition prices, the $1.2 billion sale-leaseback, master-lease terms, and comparative valuations reconstructed the extraction mechanism; **Massachusetts attorney-general review — public oversight report**: the state-approved conversion terms and a 2015 review documented promised versus delivered capital investment; **Bankruptcy filings and congressional record — public legal/oversight records**: liability totals, compensation, hospital sales, and the subpoena conflict anchored the end state
- Systems: Internal Steward archive; SEC EDGAR filings; Property transaction, lease, and valuation records; Massachusetts attorney-general review; U.S. bankruptcy court filings; U.S. congressional records
- Signature: sale-leaseback solvency-disclosure divergence: hospital deed and acquisition values joined to sale-leaseback prices and rent obligations on facility and transaction date, then compared with public SEC ownership/health claims and private ownership, loan, and insolvency records on entity and reporting period, revealed value extraction, threshold engineering, and a publicly concealed dependence.
- Method: [inferred]
- Impact: No discrete government or corporate action was identified as caused by this October 2024 story. Congressional, grand-jury, SEC, and bankruptcy scrutiny was already underway when it appeared. Contemporaneous status
- Dependency: (c) — central proposition needs non-public records.

### ‘Robbing Peter to Pay Paul’: Inside Steward’s Crumbling Massachusetts Hospitals (2024) — public-services
- URL: [OCCRP feature](https://www.occrp.org/en/feature/robbing-peter-to-pay-paul-inside-stewards-crumbling-massachusetts-hospitals); [Steward Files project](https://www.occrp.org/en/project/the-steward-files)
- Partner/awards: OCCRP feature by Brian Fitzpatrick with reporting contributed by Khadija Sharife and *The Boston Globe*. It is an OCCRP-hosted part of the OCCRP/*Boston Globe*/*Times of Malta* Steward Files collaboration, not an ICIJ or Forbidden Stories project. No story-specific award was listed on the checked OCCRP pages.
- Found: Internal emails showed vendors discontinuing services over unpaid invoices by January 2019 and an executive warning in April 2020 that suppliers might stop providing surgical materials. Steward shareholders later received a roughly **$111 million dividend**. Nurses and clinicians described missing IV tubing and medication dosages, broken elevators and equipment, personal credit-card purchases for supplies, and newborn remains placed in staff-bought cardboard boxes after a bereavement-box vendor went unpaid.
- Types: vendor-arrears service collapse; extraction-harm contrast; facility-level safety degradation
- Evidence: **Vendor and executive emails — leaked internal records**: dated warnings about invoice backlogs, credit holds, and surgical-supply interruptions established the upstream financial sequence. Feature; **Federal regulator findings — public/request-obtained administrative records reported by the Globe**: facility inspections and patient-peril determinations supplied an external outcome ledger. Feature; **Senate hearing — public sworn oversight record**: nurses described the care consequences under congressional scrutiny. Feature; **Frontline interviews — constructed evidence**: long-tenured nurses and clinicians independently described shortages, workarounds, credit holds, staffing, and broken equipment by facility and period. Feature; **Bankruptcy, closure, and sale records — public legal/administrative records**: they established the system's financial end state and which hospitals survived or closed. Feature
- Systems: Vendor and executive emails; federal hospital-regulator findings; U.S. congressional records; Bankruptcy, closure, and sale records
- Signature: vendor-arrears-to-patient-harm timeline: unpaid-invoice and credit-hold events joined to supply interruptions, staffing shortages, regulator peril findings, and adverse patient events on facility plus date, then compared with distributions and executive asset purchases in the same period, revealed that financial extraction preceded measurable care failure.
- Method: [inferred]
- Impact: No action was identified as attributable specifically to this feature; the six hospital sales, two closures, bankruptcy, and Senate inquiry were contemporaneous events and evidence, not claimed effects of publication. Feature
- Dependency: (b) — public re-anchor; hidden discovery remains.

### The Worker (2020) — public-services
- URL: [OCCRP story](https://www.occrp.org/en/project/slaves-to-progress/the-worker); [Slaves to Progress project](https://www.occrp.org/en/project/slaves-to-progress); [ASTRA report hosted by OCCRP](https://www.occrp.org/documents/slaves-to-progress/AstraReport.pdf)
- Partner/awards: OCCRP-led project under Miranda Patrucić, written by Patrucić and Ilya Lozovsky with reporting across the Balkans and Azerbaijan. The page does not assign this story to an outside originating outlet or a named member center, and it is not ICIJ- or Forbidden Stories-led. The related OCCRP documentary *Building Baku* aired on Al Jazeera Balkans; no story-specific prize was listed on the project page. OCCRP 2020 report
- Found: From 2006 to 2009, SerbAz recruited **more than 700** men from Bosnia and Herzegovina, Serbia, and North Macedonia to build prominent Baku projects, at least three financed by the state. Many worked 12-hour days, had passports confiscated, lived with little food, and received sharply reduced wages or none. At least **two workers died**. Seudin Zoletić described a colleague dying in his arms while police who attended did not investigate the workers' broader condition or deficient immigration documents.
- Types: coercive-labor confinement; victim-cohort reconstruction; protection-agency indifference
- Evidence: **Victim interviews — constructed firsthand evidence**: Zoletić met a reporter three times over several months; multiple workers were separately interviewed about food, hours, beatings, passports, wages, and fines; **ASTRA anti-trafficking report — NGO case record built immediately after repatriation**: it compiled worker statements and helped initiate the Bosnian prosecution. Report; **Bosnian criminal and civil-case documents — public litigation records**: indictments, testimony, employer findings, and dispositions tested the workers' account and the employer's legal identity; **Azerbaijani proceedings and ECtHR case — public court records**: these documented the rejected domestic claim and eventual international protection claim; **Contemporaneous photographs and RFE/RL reporting — open corroborative media**: images of the compound, worksites, the body of a worker, and the SerbAz office supported location and condition reconstruction
- Systems: ASTRA anti-trafficking report; Bosnian criminal and civil-case documents; ECtHR / HUDOC
- Signature: victim-cohort-to-case-file reconstruction: independently collected worker accounts joined to recruiter/employer documents, criminal and civil cases, site photographs, and repatriation records on worker, employer, worksite, and date revealed a common coercion system and the authorities' repeated failure to recognize it as trafficking.
- Method: [inferred]
- Impact: In 2021 the European Court of Human Rights found a violation of the procedural duty under Article 4 §2 to investigate possible forced labor and awarded **€5,000 to each of 33 applicants**. The judgment is an official validation of the investigation failure, not a finding that OCCRP caused the ruling. ECtHR registry summary
- Dependency: (a) — open records carry the decisive detector.

### The Minister (2020) — public-services
- URL: [OCCRP story](https://www.occrp.org/en/project/slaves-to-progress/the-minister); [Slaves to Progress project](https://www.occrp.org/en/project/slaves-to-progress)
- Partner/awards: OCCRP-led investigation reported by Miranda Patrucić, Ilya Lozovsky, Madina Mammadova, and Kelly Bloss under the same OCCRP project team as *The Worker*. No outside coordinator, ICIJ, or Forbidden Stories role is credited. No story-specific award was listed on the checked project and awards pages.
- Found: Archived pages identified SerbAz as a subsidiary of ItalDizain. Scraped Azerbaijani records and Luxembourg ownership records then showed ItalDizain was ultimately owned by Zulfiya Rahimova, the wife of Youth and Sports Minister Azad Rahimov, and associate Elchin Zeynalov. Rahimov had directed ItalDizain before entering government. SerbAz's more than 700 laborers worked on at least six projects. Two ministry-financed examples were a **17-million-manat ($20.9 million)** restoration and a **32-million-manat ($38.8 million)** rowing center.
- Types: beneficial-owner procurement conflict; post-notice payment continuation; offshore accountability truncation
- Evidence: **Insider tip — non-public lead**: a source said Creacon Construction took over SerbAz's work, opening the route to ItalDizain; **Wayback Machine corporate chart and archived company pages — open web archive**: a January 2009 ItalDizain structure chart and employment advertisements called SerbAz a subsidiary; **Pre-closure Azerbaijani registry scrape — publicly acquired historical data**: journalists had copied part of the registry before Azerbaijan restricted ownership access in 2012; the records connected Creacon to ItalDizain; **Luxembourg and Azerbaijani corporate records — registry evidence**: these traced ItalDizain through Argulux to Rahimova and Zeynalov; address records linked Rahimova and the minister; **Ministry report, letter to prosecutors, and meeting record — official documents**: project values, contract reasons, notice of abuse, and payments made before and after notice established the public-money timeline; **Worker statements, photographs, court records, and intercepted texts in the Bosnian case — mixed firsthand and litigation evidence**: these tied ownership and officials to operations while preserving the distinction between ownership and day-to-day abusers
- Systems: Wayback Machine; Pre-closure Azerbaijani registry scrape; Luxembourg and Azerbaijani corporate records; Ministry report, letter to prosecutors, and meeting record
- Signature: hidden-owner-to-public-payer join: archived subsidiary charts and registry ownership records joined to ministry contracts, payment reports, and the minister's household/address record on company, beneficial owner, project, and date revealed that the contracting official's wife benefited, while payments compared with the authority's recorded notice date revealed millions continuing after abuse was known.
- Method: [inferred]
- Impact: No official action tied specifically to the Rahimova ownership finding was located. The later ECtHR judgment found Azerbaijan failed to investigate the workers' credible forced-labor claim, but it did not adjudicate the beneficial-ownership allegation. ECtHR summary
- Dependency: (b) — public re-anchor; hidden discovery remains.

### Venezuelan Newborns Suffer as Mothers Struggle with Hunger (2018) — public-services
- URL: [OCCRP story](https://www.occrp.org/en/project/birth-and-death-in-venezuelas-time-of-hunger/venezuelan-newborns-suffer-as-mothers-struggle-with-hunger); [project page](https://www.occrp.org/en/project/birth-and-death-in-venezuelas-time-of-hunger)
- Partner/awards: Joint Efecto Cocuyo–OCCRP project. The story byline belongs to Edgar López, Ana Carolina Griffin, and Cristina González of Efecto Cocuyo; OCCRP's team provided the cross-border publication and production role shown on the project page. Efecto Cocuyo is not on OCCRP's current member-center roster, so it is recorded here as a publishing partner. No ICIJ or Forbidden Stories role and no story-specific award were found on the checked pages.
- Found: At Concepción Palacios Maternity Hospital, low-birth-weight births increased from **11.6 percent in 2015 to 16 percent in 2016**. At Santa Ana Maternity Hospital the rate rose from **11.2 percent in 2015 to 13.1 percent in 2016 and 13.9 percent in 2017**. These were leaked ward statistics at a time when national authorities minimized the crisis. Lisbeth Perez's daughter was born at **2.2 kilograms** and died ten days later; her death certificate recorded septic shock. The story carefully presented low birth weight as a possible contributing vulnerability rather than claiming it caused the child's congenital condition or death.
- Types: hidden-health time-series deterioration; quantified-victim bridge; service-capacity cascade
- Evidence: **Two maternity-hospital statistical series — leaked administrative data**: annual birth-weight aggregates from the two major Caracas maternity hospitals supplied the decisive trend; **Death certificate and clinical history — family-held/medical records**: the certificate established cause of death; reported diagnosis and treatment history supplied the case chronology; **Mother and patient interviews — constructed firsthand evidence**: the Perez case and seven additional project voices documented food intake, prenatal access, and hospital navigation; **WHO thresholds and expert interviews — open benchmark and interpretation**: the story compared the hospital trend with the WHO low-birth-weight threshold and 2025 reduction goal and sought maternal-fetal and nutrition expertise; **Hospital-director response and field observation — first-party and constructed checks**: reporters put the rising figures and missing micronutrients to officials and documented the care path
- Systems: Two maternity-hospital statistical series; Death certificate and clinical history; WHO health thresholds
- Signature: suppressed-ward time-series vs benchmark: leaked low-birth-weight counts divided by annual hospital births and compared across year, facility, and WHO target revealed a synchronized deterioration; those rates joined to named mothers' prenatal-care paths and death/medical records on hospital and period showed how the aggregate appeared in lived service failure without asserting individual causation.
- Method: [inferred]
- Impact: No discrete official response attributable to this series was located on the OCCRP project or impact pages checked.
- Dependency: (c) — central proposition needs non-public records.

### Romania: Prosecutors Overwhelmed (2009) — public-services
- URL: [OCCRP story](https://www.occrp.org/en/project/battered-justice/romania-prosecutors-overwhelmed); [Battered Justice project](https://www.occrp.org/en/project/battered-justice)
- Partner/awards: OCCRP-hosted and credited simply to OCCRP. The project page does not identify an outside coordinator or originating member center. It predates the consortium mega-project model and has no ICIJ or Forbidden Stories role. No story-specific award was listed on the checked OCCRP pages.
- Found: Romania's organized-crime prosecution directorate DIICOT reported more than **16,000 assigned cases in 2007**, about 90 per prosecutor, but only roughly **7,200 completed**, about 40 per prosecutor. Police seized about **84 kilograms of heroin worth more than €4 million** from an international ring, but judges released the suspects on unconditional bail; one was arrested again three months later with multiple false identity documents.
- Types: justice-throughput gap; high-harm release anomaly; protection inversion
- Evidence: **DIICOT annual report — open official performance data**: assigned and completed cases and prosecutor workload supplied the system denominator; **Seizure, arrest, bail, and trial records — law-enforcement and court records**: heroin, cocaine, cigarette, kidnapping, and corruption cases supplied transaction-level examples of attrition; **Statutory rules and ethics code — public legal texts**: surveillance limits, the border-point smuggling gap, and restrictions on magistrates criticizing colleagues supplied institutional explanations; **Police, prosecutor, anti-drug, and witness-protection interviews — constructed evidence**: mostly anonymous officials explained why cases stalled; named agency statistics and dispositions were used to test their claims
- Systems: DIICOT annual reports/case records; Seizure, arrest, bail, and trial records; Statutory rules and ethics code
- Signature: case-load-to-disposition attrition join: annual cases assigned joined to cases completed on prosecutor and year revealed a throughput shortfall, while major seizure/arrest records joined to bail, detention length, trial delay, and final disposition on case and defendant revealed high-harm cases dropping out at successive justice stages.
- Method: [inferred]
- Impact: No discrete official reform or case action attributable to this story was located on the OCCRP project or impact pages checked.
- Dependency: (a) — open records carry the decisive detector.

### Europe's COVID-19 Spending Spree Unmasked (2020) — public-services
- URL: [OCCRP investigation and data notes](https://www.occrp.org/en/project/crime-corruption-and-coronavirus/europes-covid-19-spending-spree-unmasked); [parent project](https://www.occrp.org/en/project/crime-corruption-and-coronavirus)
- Partner/awards: OCCRP-coordinated data project by Adriana Homolova and Dada Lyndell with media partners in 37 countries. The contributor list includes current OCCRP member centers Hetq, Bivol, Investigace.cz, Atlatszo, IRPI/IrpiMedia, Re:Baltica, KRIK, and RISE Project; other contributors included *The Times*, *Irish Times*, NRK, YLE, DR, *Publico*, *Times of Malta*, and Finance Uncovered. It was not ICIJ- or Forbidden Stories-led. No story-specific award was found on…
- Found: Partners assembled **more than 37,800** COVID-related tenders and contracts worth more than **€21 billion**, covering February through October 2020 and PPE, ventilators, tests, drugs, and temporary hospitals. In the collected data, respirator unit prices ranged from **€0.20 to €37**. Large hydroxychloroquine/chloroquine contracts rose 15-fold and dexamethasone contracts 36-fold from the comparison period.
- Types: emergency-procurement opacity; unit-price dispersion; no-bid concentration; transparency missingness
- Evidence: **EU Tenders Electronic Daily records — open supranational procurement data**: common notices supplied part of the cross-border backbone; **National and regional contract portals — open administrative data**: local partners collected and interpreted jurisdiction-specific records; **Public-record requests — request-obtained procurement data and refusal records**: partial Norwegian data and full refusals elsewhere made missingness an explicit result; **Published normalized tables — OCCRP-created open data**: a spending tracker, unit-price master list, top-one-percent table, and top-50 suppliers table made the analysis inspectable; **Supplier identifiers and contract descriptions — public but frequently incomplete fields**: VAT numbers, product types, unit counts, values, dates, and award procedures supported matching and normalization; missing VAT numbers were a documented limitation
- Systems: EU Tenders Electronic Daily; National and regional contract portals; Public-record requests; Published normalized tables; Supplier identifiers and contract descriptions
- Signature: emergency-contract unit-price/competition diff: tender and award records normalized to product class, unit, currency, date, buyer, supplier, and procedure, then like-for-like unit prices compared across buyer-country-month and high-value records grouped by competition method, revealed price outliers and direct-award concentration; country record counts compared with refusal logs revealed transparency black holes.
- Method: [inferred]
- Impact: No single official action attributable to this cross-border interactive was located. Its direct product was the downloadable public corpus and country-level leads.
- Dependency: (a) — open records carry the decisive detector.

### China’s Oppressed Uighurs Made COVID-19 Protection Sold Throughout Europe (2020) — public-services
- URL: [OCCRP investigation](https://www.occrp.org/en/project/crime-corruption-and-coronavirus/chinas-oppressed-uighurs-made-covid-19-protection-sold-throughout-europe); [parent project](https://www.occrp.org/en/project/crime-corruption-and-coronavirus)
- Partner/awards: OCCRP-coordinated collaboration with SVT, NRK, DR, IRPI Media, Follow the Money, De Tijd, Eesti Päevaleht, and Siena.lt. IRPI Media and Siena are current OCCRP member centers; Eesti Päevaleht is a publication of current member center Delfi Estonia. It was not led by ICIJ or Forbidden Stories. No story-specific award was listed on the checked OCCRP awards page.
- Found: Public records showed Hubei Haixin Protective Products had employed at least **130 transferred Uighur workers**. Its medical goods were distributed in Europe by McKesson subsidiaries and OneMed even after the coercion risk became public. Governments and health bodies in at least **five countries** bought goods from the implicated supply chains. OneMed's Norwegian shipments included at least **one million masks and 2.3 million gowns**; a 100,000-mask airlift containing Hubei Haixin products was publicly welcomed by Norway's prime minister.
- Types: coercion-risk supply chain; ethical-policy contradiction; public-stockpile contamination
- Evidence: **Chinese local-government reports, news, and videos — open first-party/public records**: they identified labor transfers, worker counts, housing, training, and factory locations; **ASPI and prior *New York Times* factory identification — open secondary leads**: these supplied an existing risk list that OCCRP extended into European distribution; **Company filings, websites, sourcing policies, and product catalogs — open corporate records**: these mapped factory, listed-company, subsidiary, distributor, and public ethical commitments; **Public procurement and stockpile records plus official shipment photographs — administrative and visual records**: they tied manufacturer products to government and hospital buyers; **Test purchase and package inspection — constructed physical verification**: the Italian order preserved manufacturer and importer markings that bridged the online catalog to the McKesson entity; **Distributor/factory correspondence and labor-expert interviews — obtained first-party and expert evidence**: these tested alternative explanations and the limits of proving coercion under restricted access
- Systems: Chinese local-government reports, news, and videos; ASPI and prior *New York Times* factory identification; Company filings, websites, sourcing policies, and product catalogs
- Signature: labor-risk-to-government-purchase supply-chain join: public labor-transfer and factory records joined to manufacturer and distributor product catalogs, procurement/stockpile records, and package importer markings on manufacturer, model/SKU, importer, supplier, and buyer revealed coercion-risk goods inside European public-health supply chains; sourcing dates compared with the public risk-notice date revealed continued purchasing after warning.
- Method: [inferred]
- Impact: No discrete procurement suspension, investigation, or supplier action attributable to this story was located on OCCRP's project or impact pages checked.
- Dependency: (a) — open records carry the decisive detector.

### Mr. HispanoPreneur™: The Man Behind Honduras’ $47-Million Coronavirus Disaster (2020) — public-services
- URL: [OCCRP investigation](https://www.occrp.org/en/project/crime-corruption-and-coronavirus/mr-hispanopreneur-the-man-behind-honduras-47-million-coronavirus-disaster); [parent project](https://www.occrp.org/en/project/crime-corruption-and-coronavirus); [official-impact follow-up](https://www.occrp.org/en/news/honduras-sentences-ex-official-to-over-10-years-for-buying-useless-mobile-hospitals)
- Partner/awards: Joint OCCRP–El Pulso investigation by OCCRP's Daniela Castro and El Pulso's Joan Suazo. El Pulso is not listed on OCCRP's current member-center roster, so it is recorded as a Honduran publishing partner. The story was not ICIJ- or Forbidden Stories-led. No story-specific award was listed on the checked OCCRP awards page.
- Found: INVEST-H bought seven mobile hospitals for **more than $47 million**, paying the full amount in advance without a signed contract, performance guarantee, or late-delivery penalties to an unfamiliar company found online. The goal had been to add more than 450 beds. Intermediary Axel López sought underlying prices of **$4.45 million** for a 91-bed unit and **$3.175 million** for a 51-bed unit, then invoiced Honduras **$7.95 million** and **$5.75 million** respectively. OCCRP and El Pulso calculated a markup above 50 percent, more than **$16 million**; Honduras's anti-corruption council estimated 69 percent and more than $32.5 million.
- Types: emergency-middleman markup; advance-payment control failure; spec-to-delivery failure
- Evidence: **Confidential proposals, emails, purchase confirmations, and invoices — non-public transaction records**: these revealed order sequencing, confidentiality demands, claimed manufacturer, source price, and government invoice; **Bank-payment and INVEST-H purchase records — official financial records**: two payments on March 20 and April 2 established the $47 million outflow and lack of normal protections; **ASJ and National Anti-Corruption Council reports — public watchdog/audit records**: they tested procedure, obtained independent Turkish comparables, and estimated overpayment; **Public Ministry and official inspection/audit records — public enforcement and performance evidence**: physical condition, absent ventilators, installation failure, and technical deficiencies established nonperformance; **Florida corporate, address, website, social-media, and trade records — open corporate/OSINT evidence**: these tested Elmed's existence, capacity, history, representations, and López's political proximity; **Patient, physician, supplier, and official interviews — constructed/first-party evidence**: they established the bed shortage and intended clinical function and put the documentary contradictions to the participants
- Systems: Confidential proposals, emails, purchase confirmations, and invoices; INVEST-H purchase records; Honduras National Anti-Corruption Council reports; Public Ministry and official inspection/audit records; Florida corporate, address, website, social-media, and trade records; ASJ audit reports
- Signature: middleman quote-invoice-delivery three-way diff: upstream manufacturer quote compared with intermediary invoice on identical bed-count unit, then joined to payment date and delivery/inspection record on purchase order and unit, revealed the markup, payment before supplier commitment, delay, missing ventilators, and inability to perform the purchased clinical function.
- Method: [inferred]
- Impact: Former INVEST-H director Marco Bográn was sentenced in 2022 to nearly **11 years in prison** and ordered to return roughly **$60 million**; López was subject to an international warrant, and U.S. authorities had ordered seizure of about **$4 million** from his company's account.
- Dependency: (b) — public re-anchor; hidden discovery remains.
