# ICIJ Story Index — Per-Story Evidence Base

The coded corpus behind the ICIJ layer of the investigative pattern library. Distilled from the
full extraction reports in `_intake/icij/`, which carry the complete entries and per-claim citations;
this index compresses each story or methodology unit to its evidence skeleton.

**Entry fields** — URL; Partner/awards; Found (core finding); Types (finding-type tags exactly as
coded in the source report); Evidence (typed sources with acquisition mode); Systems (specific named
record systems, conservatively derived from the entry’s evidence); Signature (coined detection move
plus one-line mechanics); Method (cited methodology page vs `[inferred]`); Impact (official
consequences); Dependency (input class and a short reason). Report-01 predates inline dependency
fields, so its classes come from `_intake/access-substitution-analysis.md` and are marked
`[access-substitution]`. Report-09 is methodology infrastructure; units without a plausible row in
that same dependency table remain `unassessed`. Report-10 is excluded because it is the sampling frame.

---

## Offshore-finance leak canon (report-01)

### Offshore Leaks (2013) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/offshore/; https://www.icij.org/investigations/offshore/secret-files-expose-offshores-global-impact/
- Partner/awards: ICIJ coordinated 86 journalists in 46 countries for the initial publication; later phases involved more than 110 reporters in 60 countries. The project won the IRE Multiplatform/Large prize, Scripps Howard’s William Brewster Styles Award, and the Overseas Press Club’s best-investigative-reporting award (team description, awards).
- Found: the first provider-scale leak mapped the people, intermediaries, companies and trusts inside a global secrecy industry
- Types: hidden-beneficial-ownership; intermediary-enablement; offshore-risk-concentration
- Evidence: Leaked corporate-provider databases and email/document stores from Portcullis TrustNet and Commonwealth Trust Limited, obtained on… [privileged]; OCR text and deduplicated, normalized tables constructed from scans, PDFs, spreadsheets, web files and emails using Nuix and ICIJ’s… [constructed]; Corporate registries, court files, asset declarations, sanctions records, prior reporting and subject interviews used by country… [open-public/request-gated]
- Systems: Portcullis TrustNet provider database; Commonwealth Trust provider database; Nuix; Interdata; corporate registries; sanctions lists
- Signature: provider-records-to-risk-graph: provider records joined to external identity/risk records on normalized person, address, company and officer keys revealed hidden controllers and risky networks — deduplicate the corpus, extract role-bearing edges (person → role → entity → intermediary → jurisdiction), then resolve those nodes against public officials, sanctions, courts and registries.
- Method: https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/
- Impact: ICIJ documented tax investigations, resignations and policy responses across multiple countries; the EU tax commissioner called the project a major trigger for Europe’s renewed offshore crackdown (impact roundup)
- Dependency: (a) [access-substitution] — public offshore graph plus risk lists

### The Aliyev family–contractor network (2013) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/
- Partner/awards: ICIJ with regional partners in the Offshore Leaks collaboration; covered by the project-level awards (project awards).
- Found: hidden BVI ownership linked Azerbaijan’s ruling family to a construction magnate receiving billions in state contracts
- Types: hidden-beneficial-ownership; state-linked-benefit; public-private-conflict
- Evidence: Leaked BVI incorporation and shareholder/director records . [privileged]; Azerbaijani contract and corporate records identifying Gozal-controlled businesses and awarded work . [open-public/request-gated]; Public biographical records fixing ages and family relationships; earlier property reporting on Aliyev family assets [open-public]
- Systems: BVI corporate records; Azerbaijani procurement records; Azerbaijani corporate registry
- Signature: offshore-owner-to-state-contractor-join: leaked shareholder/director records joined to public-contract recipients on shared director and family keys revealed a concealed ruling-family–contractor overlap; the load-bearing move is a two-hop traversal official family → offshore entity → contractor principal, followed by aggregation of awards to the contractor’s operating companies.
- Method: [inferred]
- Impact: no distinct official sanction tied to this thread is documented in ICIJ’s Offshore Leaks impact roundup; the broader project triggered international investigations and disclosure reform efforts (impact roundup)
- Dependency: (a) [access-substitution] — public ownership and procurement records

### Bayartsogt Sangajav’s undeclared company and Swiss account (2013) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/offshore/disclosure-secret-offshore-documents-may-force-top-mongolian-lawmaker-resign/
- Partner/awards: ICIJ and Mongolian partners under Offshore Leaks; project-level IRE, Scripps Howard and OPC honors (awards).
- Found: a leaked BVI file exposed an omitted $1 million account held by Mongolia’s deputy speaker
- Types: hidden-beneficial-ownership; disclosure-gap; public-private-conflict
- Evidence: Leaked BVI company records and bank-account information . [privileged]; Mongolian official asset declarations and disclosure law . [open-public/request-gated]; On-record admission by Sangajav after document confrontation [constructed interview evidence]
- Systems: BVI corporate records; Mongolian asset declarations
- Signature: financial-disclosure-anti-join: leaked asset/company ownership compared to the same official’s filed declaration on person, asset class and reporting period revealed an omitted interest; after exact-name and alias resolution, the analytic move is a field-level anti-join: evidenced interests MINUS declared interests.
- Method: [inferred]
- Impact: Sangajav said he would consider resigning and later stepped down as parliamentary deputy speaker after the disclosure (ICIJ Mongolia follow-up)
- Dependency: (b) [access-substitution] — public declarations verify known hidden interests

### China Leaks (2014) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/; https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/
- Partner/awards: ICIJ led a separate China-focused phase with 15 ICIJ members and partners across Asia, Europe and North America; it reused the Offshore Leaks corpus but had its own reporting and release cycle (methodology). Project-specific prize not identified in the reviewed ICIJ record.
- Found: offshore-provider records penetrated the wealth networks of China’s political and commercial elite despite transliteration and censorship barriers
- Types: elite-cohort-penetration; intermediary-enablement; hidden-beneficial-ownership
- Evidence: The TrustNet/Commonwealth provider corpus from Offshore Leaks, including incorporation records, passports, addresses and role records . [privileged]; Constructed aliases for Chinese names in Mandarin, Cantonese and romanization systems; passport numbers, birth dates and addresses… [constructed]; Public leadership rosters, rich lists, state-enterprise records, company registries and reporting archives . [open-public]; Local-source and subject verification under conditions of state censorship [constructed interviews/reporting]
- Systems: Portcullis TrustNet provider database; Commonwealth Trust provider database; Chinese leadership and wealth rosters; company registries
- Signature: multilingual-elite-cohort-match: a multilingual alias pipeline joined leak identities to fixed elite cohorts on passport, birth-date, address, kinship and romanized-name keys revealed both named connections and cohort prevalence; aggregate provider/intermediary counts by year and client origin to expose system growth.
- Method: https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/
- Impact: Chinese web access to ICIJ and partner stories was blocked, and Transparency International later cited China Leaks as a factor in China’s worsening corruption-perception ranking (ICIJ impact coverage, later impact roundup)
- Dependency: (a) [access-substitution] — public graph plus multilingual official cohorts

### LuxLeaks (2014) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/luxembourg-leaks/; https://www.icij.org/investigations/luxembourg-leaks/about-project-luxembourg-leaks/
- Partner/awards: ICIJ coordinated more than 80 journalists in 26 countries; major partners included The Guardian, Le Monde, Süddeutsche Zeitung and NDR.
- Found: leaked advance tax rulings showed Luxembourg approving industrial-scale profit shifting for hundreds of multinationals
- Types: policy-arbitrage; corporate-profit-shifting; letterbox-substance-gap
- Evidence: Leaked PwC advance-tax-ruling applications, diagrams and approval letters . [privileged]; Luxembourg company accounts and registry filings used to calculate effective rates and locate entities [open-public/request-gated]; Corporate annual reports, subsidiary lists and public tax disclosures . [open-public]; Physical visits to registered addresses and interviews with tax experts, companies and authorities [constructed]
- Systems: LuxLeaks advance tax rulings; Luxembourg company registry and accounts; corporate annual reports
- Signature: tax-ruling-flow-and-substance-test: leaked transaction diagrams joined to group accounts and jurisdictional tax rules on entity, payment type and fiscal year revealed where operating profit was converted into intra-group interest and where tax fell below the rate implied by business activity; a second join of registered address to occupant count exposed letterbox concentration.
- Method: https://www.icij.org/investigations/luxembourg-leaks/your-head-spinning-5-tips-understand-lux-leaks-files/
- Impact: LuxLeaks helped drive EU state-aid investigations and tax-transparency reforms; in 2023 the European Court of Human Rights ruled that Halet’s whistleblower conviction violated free-expression rights (ten-year review, ECHR follow-up)
- Dependency: (a) [access-substitution] — published rulings, filings, and tax rules

### Swiss Leaks (2015) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/swiss-leaks/; https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/
- Partner/awards: Le Monde obtained the data from French tax authorities and shared it with ICIJ; ICIJ coordinated about 140 journalists in 45 countries, including BBC, The Guardian and other partners (about page). Project-specific prize not identified in the reviewed ICIJ pages.
- Found: internal HSBC files showed how a global bank serviced tax evaders and clients linked to arms, diamonds, corruption and sanctions
- Types: high-risk-client-servicing; compliance-knowledge-gap; policy-arbitrage
- Evidence: HSBC client and account tables, maximum-balance data and internal banker notes originally extracted by Hervé Falciani and held by… [privileged]; UN sanctions material, court cases, government investigations and public criminal or business records . [open-public]; Corporate registries for client-owned shells and interviews with clients, bank representatives and enforcement experts . [open-public/constructed]
- Systems: HSBC Private Bank client files; sanctions lists; court and enforcement records
- Signature: bank-client-risk-and-policy-timeline: bank-client records joined to sanctions, court, criminal, industry and political-risk lists on resolved identity keys revealed the risky-client cohort; banker notes compared to bank policy and later account activity revealed what the institution knew and did. A date join around the EU directive exposed entity conversions clustered near the rule change.
- Method: https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/
- Impact: Geneva prosecutors raided HSBC’s office and opened a money-laundering investigation shortly after publication; multiple tax authorities pursued account holders (ICIJ raid report)
- Dependency: (b) [access-substitution] — public risk records verify known clients

### Panama Papers (2016) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/panama-papers/; https://www.icij.org/investigations/panama-papers/about-the-investigation/
- Partner/awards: Süddeutsche Zeitung received the leak and shared it with ICIJ; ICIJ coordinated more than 370 journalists from over 100 media organizations in nearly 80 countries, including The Guardian, BBC, Le Monde and OCCRP. The project won the 2017 Pulitzer Prize for Explanatory Reporting (about, Pulitzer announcement).
- Found: 11.5 million Mossack Fonseca files exposed a worldwide shell-company factory and the political, criminal and commercial networks it served
- Types: hidden-beneficial-ownership; intermediary-enablement; offshore-risk-concentration; networked-asset-concealment
- Evidence: Leaked Mossack Fonseca emails, databases, incorporation files, images and office documents obtained by Süddeutsche Zeitung . [privileged]; OCR and structured extraction using Extract/Blacklight, Talend ETL, Neo4j and Linkurious; reporter annotations and shared search [constructed]; Company and property registries, court cases, sanctions lists, asset declarations, securities filings, interviews and field reporting . [open-public/request-gated/constructed]
- Systems: Mossack Fonseca files; Offshore Leaks Database; corporate registries
- Signature: heterogeneous-provider-graph-join: heterogeneous leak files normalized into an entity-role graph and joined to public officials, sanctions, registries, disclosures and dockets revealed hidden ownership and transaction paths; two-degree graph expansion exposed intermediaries or shells shared across otherwise separate targets.
- Method: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Impact: Iceland’s prime minister resigned, governments opened scores of investigations, and tax authorities had recovered at least $1.36 billion by 2021 (resignation, revenue recovery)
- Dependency: (a) [access-substitution] — public Panama graph supports role joins

### The Putin-circle cello network (2016) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/panama-papers/20160403-putin-russia-offshore-network/
- Partner/awards: ICIJ, Süddeutsche Zeitung, OCCRP, Novaya Gazeta and other Panama Papers partners; covered by the project’s 2017 Pulitzer (award).
- Found: transactions around Sergei Roldugin traced at least $2 billion through shells tied to the Russian president’s inner circle
- Types: networked-asset-concealment; proxy-ownership; value-transfer-anomaly
- Evidence: Mossack Fonseca ownership records, emails, contracts, loan agreements and transaction documents . [privileged]; Russian and foreign corporate records, bank and securities information, and public biographies/relationship reporting . [open-public/request-gated]; Constructed transaction and relationship graph [constructed]
- Systems: Mossack Fonseca transaction files; corporate registries
- Signature: Roldugin-transfer-and-proxy-chain: leaked contracts and payments joined into a dated transaction graph on company, account, signatory and counterparty keys revealed a $2 billion flow network; the nominal owner’s public wealth/profile compared with controlled value and proximity to political power surfaced the proxy hypothesis.
- Method: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Impact: the U.S. later sanctioned Roldugin as a custodian of Putin’s offshore wealth; the sanction post-dated and cited the broader public record around his offshore role (ICIJ sanctions follow-up)
- Dependency: (c) [access-substitution] — private transfers supply the value path

### Iceland’s prime minister and Wintris (2016) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/
- Partner/awards: ICIJ, Süddeutsche Zeitung, Reykjavík Media and other Panama Papers partners; part of the Pulitzer-winning project (award).
- Found: a $1 transfer and omitted offshore interest exposed a conflict with failed-bank creditors
- Types: disclosure-gap; public-private-conflict; deadline-adjacent-restructuring
- Evidence: Mossack Fonseca incorporation, ownership and transfer records . [privileged]; Icelandic parliamentary disclosures and the effective date of the disclosure rule . [open-public]; Failed-bank insolvency claims and court records . [open-public/request-gated]
- Systems: Mossack Fonseca files; Icelandic asset declarations; Landsbanki creditor records
- Signature: ownership-disclosure-conflict-timeline: offshore ownership history compared to parliamentary disclosures on person and reporting date revealed the omission; the share-transfer date joined to the new rule’s effective date and insolvency claims joined to government policy revealed timing and conflict.
- Method: [inferred]
- Impact: Gunnlaugsson resigned as prime minister two days after publication amid public protests (ICIJ follow-up)
- Dependency: (a) [access-substitution] — public ownership and declarations reproduce mismatch

### Mossack Fonseca’s sanctions and compliance behavior (2016) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/panama-papers/20160404-sanctioned-blacklisted-offshore-clients/; https://www.icij.org/investigations/panama-papers/20160403-mossack-fonseca-offshore-secrets/
- Partner/awards: ICIJ, Süddeutsche Zeitung and the Panama Papers consortium; part of the Pulitzer-winning project (award).
- Found: internal files showed continued service to blacklisted clients and controls applied after exposure
- Types: high-risk-client-servicing; compliance-knowledge-gap; compliance-after-the-fact
- Evidence: Mossack Fonseca client files, compliance emails, invoices and service histories . [privileged]; U.S. Treasury/OFAC sanctions lists and designation dates . [open-public]; Public court, regulatory and media records describing alleged misconduct . [open-public]
- Systems: Mossack Fonseca client-service files; U.N. sanctions list; EU sanctions list; U.S. sanctions list; enforcement records
- Signature: sanctioned-client-service-timeline: provider client master joined to OFAC designations on normalized identity and effective date revealed sanctioned relationships; service invoices, emails and resignation dates compared to designation dates revealed continued service and delayed controls.
- Method: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Impact: Mossack Fonseca closed in 2018 after the Panama Papers investigations and prosecutions; the project generated regulatory and criminal inquiries globally (ICIJ follow-up on the firm’s scramble)
- Dependency: (c) [access-substitution] — internal service actions and knowledge required

### Bahamas Leaks (2016) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/; https://www.icij.org/inside-icij/2016/09/icij-publishes-leaked-bahamas-info-offshore-database/
- Partner/awards: Süddeutsche Zeitung obtained the files and shared them with ICIJ; the release was reported with ICIJ’s offshore partners. No distinct project prize was identified in the reviewed ICIJ pages.
- Found: a leaked registry made 175,000 Bahamas entities searchable and exposed a former EU commissioner’s omitted directorship
- Types: disclosure-gap; hidden-beneficial-ownership; registry-opacity-as-control-failure
- Evidence: Leaked Bahamas corporate-registry files obtained by Süddeutsche Zeitung . [privileged]; Panama Papers/Offshore Leaks entities used for cross-corpus provider and person matching . [privileged/constructed]; European Commission declarations, official biographies and Enron transaction records . [open-public/request-gated]; Official Bahamas registry documents purchased selectively for verification . [request-gated]
- Systems: Bahamas corporate registry; Offshore Leaks Database; official asset declarations
- Signature: Bahamas-role-and-disclosure-join: bulk registry roles joined to public-official disclosures on person and tenure revealed omitted directorships; Bahamas entities joined to Panama Papers on agent and entity name revealed provider overlap that neither corpus showed alone.
- Method: https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/
- Impact: the European Commission sought clarification and European lawmakers called for investigation after Kroes acknowledged the omission (ICIJ reaction roundup)
- Dependency: (a) [access-substitution] — public Bahamas roles support disclosure joins

### Paradise Papers (2017) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/paradise-papers/; https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/
- Partner/awards: Süddeutsche Zeitung obtained the leak and shared it with ICIJ; 380 journalists from 95 media partners worked in 30 languages, including The Guardian, BBC, The New York Times and Le Monde (about page). Project-specific major prize not identified in the reviewed ICIJ material.
- Found: 13.4 million files exposed the offshore playbooks, client risks and regulatory arbitrage of elite law firms and corporate-service providers
- Types: intermediary-enablement; compliance-knowledge-gap; corporate-profit-shifting; networked-asset-concealment
- Evidence: Appleby and Asiaciti emails, client files, opinions, compliance reviews and transaction documents, plus leaked registry datasets . [privileged]; OCR/search, Neo4j and Linkurious entity graph, and reporter annotations [constructed]; Court records, financial disclosures, company and property registries, securities filings, freedom-of-information records and… [open-public/request-gated/constructed]
- Systems: Appleby/Estera files; Offshore Leaks Database; corporate registries
- Signature: Paradise-provider-risk-graph: provider client/transaction files transformed into a role-and-payment graph and joined to public ownership, securities, sanctions, disclosure and litigation records revealed hidden controllers, policy arbitrage and the enablers connecting them.
- Method: [inferred]
- Impact: ICIJ recorded arrests, audits, investigations and company/government responses in multiple jurisdictions after publication (response roundup)
- Dependency: (a) [access-substitution] — public Paradise graph supports external joins

### Appleby’s repeated compliance failures (2017) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/
- Partner/awards: ICIJ, Süddeutsche Zeitung and Paradise Papers partners; no thread-specific prize identified.
- Found: internal and regulatory audits showed known defects recurring across offices and years
- Types: compliance-knowledge-gap; repeat-control-failure; intermediary-enablement
- Evidence: Appleby internal audits, compliance reports, client-review spreadsheets and remediation communications . [privileged]; Bermuda, BVI and Cayman regulatory inspections quoted or reproduced in the leak . [privileged official records]; Public regulator rules and Appleby policies . [open-public]
- Systems: Appleby internal audits; regulatory audit records
- Signature: audit-defect-recurrence-diff: audit findings compared across office, control category and year revealed persistent defect recurrence; remediation promises joined to subsequent retest results on the same control exposed closure without cure.
- Method: https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/
- Impact: regulators in several jurisdictions opened reviews or investigations of Paradise Papers revelations; Appleby disputed ICIJ’s characterization and announced security and compliance responses (project response roundup)
- Dependency: (c) [access-substitution] — internal audits and remediation evidence required

### Wilbur Ross, Navigator and Sibur (2017) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/paradise-papers/donald-trumps-commerce-secretary-wilbur-ross-and-his-russian-business-ties/
- Partner/awards: ICIJ, Süddeutsche Zeitung, The New York Times, NBC News and Paradise Papers partners; no thread-specific prize identified.
- Found: a Cayman ownership chain concealed the U.S. commerce secretary’s continuing stake in a firm earning millions from Putin-linked owners
- Types: public-private-conflict; disclosure-gap; hidden-counterparty-exposure
- Evidence: Appleby files mapping Ross’s Cayman holding chain . [privileged]; Navigator SEC filings identifying revenue and major customers . [open-public]; Ross’s federal financial disclosures and confirmation-hearing materials . [open-public]; Sibur ownership records and OFAC sanctions data . [open-public]
- Systems: Appleby ownership files; SEC filings; U.S. financial disclosures; sanctions lists
- Signature: ownership-chain-to-disclosure-and-risk-join: leaked fund ownership traversed to the operating company, then SEC customer-revenue disclosures joined to public counterparty ownership and sanctions records revealed the politically exposed business relationship concealed by the top-level asset label.
- Method: [inferred]
- Impact: Ross later confirmed that he would divest the remaining Navigator interest after the revelations and ethics questions (ICIJ follow-up)
- Dependency: (a) [access-substitution] — public ownership, SEC, customer, and risk records

### Apple’s post-Ireland island hop (2017) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/
- Partner/awards: ICIJ, Süddeutsche Zeitung, The New York Times and Paradise Papers partners; no thread-specific prize identified.
- Found: leaked adviser correspondence captured a multinational shopping for a new tax residence after a rule change
- Types: policy-arbitrage; corporate-profit-shifting; rule-change-migration
- Evidence: Appleby/Baker McKenzie emails and jurisdiction questionnaire . [privileged]; Irish tax-law change and government statements . [open-public]; Apple SEC filings for cash, subsidiaries and tax disclosures . [open-public]
- Systems: Appleby adviser correspondence; Apple corporate filings; Irish and Jersey tax-residence rules
- Signature: post-rule-change-jurisdiction-migration: adviser jurisdiction-comparison records joined to the date of Ireland’s rule change and the later corporate-residence records revealed a rule-triggered migration; decision criteria in the questionnaire explained why Jersey won.
- Method: [inferred]
- Impact: the disclosures intensified EU and national scrutiny of corporate tax arrangements; Apple defended the reorganization as compliant and said it paid all taxes due (ICIJ investigation and response)
- Dependency: (b) [access-substitution] — public filings verify leak-seeded migration

### Nike’s royalty conduit and the substance test (2017) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/
- Partner/awards: ICIJ, Süddeutsche Zeitung, Dutch partners Trouw and Het Financieele Dagblad, and Paradise Papers collaborators; no thread-specific prize identified.
- Found: offshore entities captured brand income despite negligible personnel or physical operations
- Types: corporate-profit-shifting; letterbox-substance-gap; policy-arbitrage
- Evidence: Appleby legal and corporate-administration files . [privileged]; U.S. Tax Court records quantifying royalty flows . [open-public]; Dutch and Bermuda company records, annual reports and tax rules . [open-public/request-gated]; Field checks and product purchases tracing which entity licensed the mark [constructed]
- Systems: Appleby/Nike records; Dutch company accounts; IP ownership records
- Signature: royalty-conduit-substance-gap: royalty payments from court and company records joined to the IP-owning entities, then compared with employee, office and operating-asset indicators, revealed profit concentrated where productive substance was absent.
- Method: https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/
- Impact: the European Commission opened a state-aid investigation into Nike’s Dutch tax rulings and said the rulings might not reflect economic reality (ICIJ EU follow-up)
- Dependency: (a) [access-substitution] — public accounts and substance indicators suffice

### West Africa Leaks (2018) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/west-africa-leaks/; https://www.icij.org/about-the-investigation/
- Partner/awards: ICIJ and the Norbert Zongo Cell for Investigative Journalism in West Africa (CENOZO) coordinated reporters across 11 countries; local partners supplied language, registry and political context (about page). No project-specific prize identified in the reviewed ICIJ pages.
- Found: localizing four global leak corpora exposed offshore actors and tax losses across 11 West African countries
- Types: corpus-relocalization; letterbox-substance-gap; corporate-profit-shifting
- Evidence: Four prior ICIJ leak corpora containing accounts, emails, contracts, passports and company records . [privileged]; Local corporate, tax, procurement and public-official records from 11 countries . [open-public/request-gated]; Interviews, physical-address checks and country-partner knowledge . [constructed]
- Systems: Offshore Leaks Database; West African corporate registries; tax and contract records
- Signature: cross-leak-corpus-relocalization: a cross-project leak index filtered on West African names, addresses, citizenship, intermediaries and transactions, then joined to local registries, contracts and tax rules, revealed stories missed by the original global searches.
- Method: https://www.icij.org/about-the-investigation/
- Impact: ICIJ documented probes and dismissals in some countries alongside official inaction in others, illustrating heterogeneous enforcement after the same publication (impact review)
- Dependency: (a) [access-substitution] — public leak vintages support local joins

### Mauritius Leaks (2019) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/mauritius-leaks/; https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/
- Partner/awards: ICIJ coordinated 54 journalists from 18 countries; partners included Le Monde, Süddeutsche Zeitung, NDR and Quartz, whose machine-learning team assisted document triage (about page). No project-specific major prize identified in the reviewed record.
- Found: provider files showed how treaty networks and low-substance Mauritius entities diverted taxable profit from poorer countries
- Types: treaty-shopping; corporate-profit-shifting; letterbox-substance-gap
- Evidence: Conyers client files, plans, tax opinions, emails and administration records . [privileged]; Mauritius registry and Financial Services Commission licensee data . [open-public/request-gated]; Bilateral tax treaties, tax-court decisions and government revenue estimates . [open-public]; Corporate annual reports, investment records, address checks and responses . [open-public/constructed]
- Systems: Conyers Mauritius files; Mauritius corporate registry; tax-treaty texts; company accounts
- Signature: treaty-route-counterfactual: leaked investment structures joined to the bilateral-treaty graph on source country, intermediary jurisdiction and payment type revealed treaty paths; tax outcomes compared with entity substance and direct-route treatment quantified the advantage.
- Method: https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/
- Impact: Senegal terminated its tax treaty with Mauritius, and several governments reviewed or renegotiated treaties after publication (Senegal follow-up, broader impact)
- Dependency: (b) [access-substitution] — public records verify leak-seeded treaty route

### Luanda Leaks (2020) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/luanda-leaks/; https://www.icij.org/investigations/luanda-leaks/about-the-luanda-leaks-investigation/
- Partner/awards: The Platform to Protect Whistleblowers in Africa (PPLAAF) supplied the files; ICIJ coordinated more than 120 journalists from 36 organizations in 20 countries, including BBC, The Guardian, Expresso and The New York Times (about page). No project-specific major prize identified in the reviewed pages.
- Found: a document and transaction reconstruction showed how Isabel dos Santos converted public position and state-company relationships into a 400-company private empire
- Types: state-asset-conversion; public-private-conflict; intermediary-enablement; deadline-adjacent-restructuring
- Evidence: Emails, contracts, spreadsheets, ledgers, audits, incorporation files, organization charts, loans, deeds, public contracts,… [privileged]; OCR and entity extraction in ICIJ Datashare; tagged document collections and constructed organization/transaction maps [constructed]; Registries, deeds, public contracts, court filings, bank records, site visits and more than 200 interviews [open-public/request-gated/constructed]
- Systems: Luanda Leaks corpus; Datashare; corporate registries; Sonangol records
- Signature: state-body-payment-and-office-change-graph: contracts, invoices, ownership and bank records joined into a dated entity-payment graph on company, signatory, account and beneficial owner revealed value moving from state bodies through related companies; office-change dates compared with payment authorization exposed last-minute transfers.
- Method: https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/
- Impact: Angola charged dos Santos with 12 crimes, courts froze or invalidated assets, and the United States later sanctioned her for corruption; she has denied wrongdoing (charges, U.S. sanctions)
- Dependency: (c) [access-substitution] — full payment and document graph unavailable

### FinCEN Files (2020) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/fincen-files/; https://www.icij.org/investigations/fincen-files/about-the-fincen-files-investigation/
- Partner/awards: BuzzFeed News obtained and shared the records; ICIJ coordinated more than 400 journalists from 108 organizations in 88 countries. The project was a 2021 Pulitzer finalist and won IRE’s Tom Renner Award (about, awards).
- Found: leaked suspicious-activity reports reconstructed $2 trillion in flagged payments and showed global banks repeatedly moving money after warnings and penalties
- Types: high-risk-client-servicing; compliance-knowledge-gap; enforcement-recidivism; correspondent-opacity
- Evidence: Leaked FinCEN SAR forms and narrative attachments obtained by BuzzFeed News . [privileged official records]; Manually extracted transaction, entity and correspondent-bank tables; narrative-derived values and normalized identifiers [constructed]; Court cases, enforcement settlements, sanctions lists, corporate registries, bank filings, audit reports and interviews . [open-public/request-gated/constructed]
- Systems: FinCEN suspicious activity reports; ICIJ FinCEN transaction dataset; U.S. enforcement records
- Signature: SAR-transaction-and-correspondent-graph: SAR narratives parsed into transactions and joined on account, bank, entity, amount and date created a cross-bank flow graph; clients and banks joined to sanctions, cases, penalties and warning dates revealed service continuing after documented risk events.
- Method: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Impact: the U.S. enacted the Corporate Transparency Act, and regulators and banks announced reforms and inquiries after publication (ICIJ impact review)
- Dependency: (c) [access-substitution] — raw SAR narratives and transaction population withheld

### HSBC and the WCM Ponzi network (2020) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/fincen-files/hsbc-moved-vast-sums-of-dirty-money-after-paying-record-laundering-fine/
- Partner/awards: ICIJ, BuzzFeed News, BBC Panorama and FinCEN Files partners; part of the Pulitzer-finalist/Tom Renner-winning project (awards).
- Found: SARs showed billions moving through HSBC after its record laundering settlement and despite fraud warnings
- Types: enforcement-recidivism; high-risk-client-servicing; warning-to-action-lag
- Evidence: HSBC-filed SARs and narratives . [privileged official records]; The 2012 deferred-prosecution agreement, monitor/probation history and later criminal cases . [open-public/request-gated]; Company registries, websites and victim/family interviews identifying WCM entities and consequences . [open-public/constructed]
- Systems: FinCEN suspicious activity reports; HSBC settlement records; WCM court filings
- Signature: post-warning-client-flow-timeline: SAR transactions joined to the bank’s penalty/probation timeline and fraud-warning dates on client, account and date revealed payments continuing during remediation; shell recipients expanded through registry ownership connected the flows to WCM.
- Method: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Impact: the story contributed to renewed scrutiny of HSBC’s deferred-prosecution regime and to the broader FinCEN Files legislative response; no thread-specific new prosecution of HSBC is claimed here (project impact review)
- Dependency: (c) [access-substitution] — client-level flows and knowledge dates withheld

### Britain’s shell-company factories (2020) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/fincen-files/inside-scandal-rocked-danske-estonia-and-the-shell-company-factories-that-served-it/; https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/
- Partner/awards: ICIJ, BuzzFeed News, Finance Uncovered and FinCEN Files partners; covered by the project’s awards (awards).
- Found: recurring signatures clustered thousands of nominally separate firms into four formation networks and exposed unreported billions
- Types: formation-factory; correspondent-opacity; cross-ledger-mismatch
- Evidence: FinCEN SAR transactions and narratives . [privileged official records]; Companies House incorporation, officer, partner, address and annual-account filings . [open-public]; Constructed signature clusters and company-to-factory network . [constructed]
- Systems: UK Companies House; FinCEN suspicious activity reports
- Signature: shell-factory-signature-clustering: Companies House entities clustered on repeated officer, partner, address, filing and signature features revealed formation factories; SAR inflows compared to filed turnover/income on company and year revealed $4.5 billion absent from public accounts.
- Method: https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/
- Impact: FinCEN Files added pressure for U.K. company-formation and beneficial-ownership reform; the U.S. adopted beneficial-ownership legislation at project level (ICIJ impact review)
- Dependency: (a) [access-substitution] — Companies House supports formation-cluster testing

### Kolomoisky’s U.S. property trail (2020) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/
- Partner/awards: ICIJ, BuzzFeed News, Pittsburgh Post-Gazette, Miami Herald and FinCEN Files partners; part of the awarded project (awards).
- Found: bank records, audits and deeds traced more than $750 million from a Ukrainian bank into a shell-company real-estate network
- Types: networked-asset-concealment; state-asset-conversion; flow-to-asset-conversion
- Evidence: SARs and bank transaction records . [privileged official records]; Confidential PrivatBank audits and civil complaints . [privileged/request-gated and open-public litigation]; U.S. deeds, mortgages, company registries, property records and site visits . [open-public/request-gated/constructed]; Interviews with workers, officials, lawyers and company representatives . [constructed]
- Systems: PrivatBank audit records; U.S. property deeds; federal forfeiture complaints; state corporate registries
- Signature: bank-transfer-to-property-chain: bank transfers traversed through shell accounts on amount, date, counterparty and signatory, then joined to LLC ownership and property deeds on buyer and closing date, revealed conversion of alleged bank proceeds into U.S. assets.
- Method: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Impact: U.S. authorities pursued civil forfeiture and Ukraine litigated over PrivatBank assets; this entry states those as official allegations/actions, not proof of the full theory (ICIJ investigation)
- Dependency: (c) [access-substitution] — private bank ledger supplies missing value path

### Pandora Papers (2021) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/pandora-papers/; https://www.icij.org/investigations/pandora-papers/about-pandora-papers-investigation/
- Partner/awards: ICIJ coordinated more than 600 journalists from about 150 outlets in 117 countries and territories, including The Washington Post, The Guardian, BBC, Le Monde and Süddeutsche Zeitung (about page). The project won or was recognized by multiple international journalism organizations; no single prize is used as an evidentiary claim here.
- Found: the largest ICIJ offshore leak resolved owners across 14 providers and exposed how leaders, oligarchs and criminals used a fragmented global secrecy market
- Types: hidden-beneficial-ownership; intermediary-enablement; elite-cohort-penetration; compliance-after-the-fact
- Evidence: Emails, spreadsheets, PDFs, images, passports, incorporation and beneficial-ownership files from 14 providers . [privileged]; Deduplicated master spreadsheets, Python extraction, OCR, machine-learning models, manual transcription, Neo4j/Linkurious and Datashare [constructed]; Sanctions lists, prior ICIJ leaks, corporate/property records, public-official and billionaire rosters, asset declarations, courts… [open-public/request-gated/constructed]
- Systems: Pandora Papers provider databases; Datashare; Offshore Leaks Database; sanctions lists; PEP lists; wealth lists
- Signature: fourteen-provider-risk-and-cohort-graph: fourteen heterogeneous provider corpora normalized to a common beneficial-owner/entity model and joined to sanctions, prior leaks, registries and fixed official/billionaire cohorts revealed cross-provider ownership, prevalence and repeated enablers.
- Method: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Impact: governments opened investigations, officials resigned or faced elections and authorities announced reforms within months of publication (2021 impact review)
- Dependency: (a) [access-substitution] — selected public Pandora graph supports joins

### King Abdullah’s 14 hidden homes (2021) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/pandora-papers/jordan-king-abdullah-luxury-property/
- Partner/awards: ICIJ, The Washington Post, The Guardian, BBC and Pandora Papers partners; no thread-specific prize identified.
- Found: 36 front companies were linked to more than $106 million in U.K. and U.S. property
- Types: networked-asset-concealment; portfolio-reconstruction; public-private-conflict
- Evidence: Provider ownership and company-administration records . [privileged]; U.S. and U.K. deeds, land records and company registries . [open-public/request-gated]; Sale prices, mortgages and property-company link records . [open-public]
- Systems: Pandora Papers property files; UK Land Registry; U.S. deed and title records
- Signature: hidden-property-portfolio-join: leaked beneficial-owner records joined to property-title companies and deeds on company name, address and acquisition date revealed 14 assets; grouping all title entities by common controller reconstructed the $106 million portfolio.
- Method: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Impact: Jordanian authorities restricted access to the reporting, while the revelations prompted domestic and international scrutiny; no confiscation or adjudicated illegality is claimed (project impact review)
- Dependency: (a) [access-substitution] — public offshore roles and title records

### Andrej Babiš’s French estate chain (2021) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/pandora-papers/czech-prime-minister-andrej-babis-french-property/
- Partner/awards: ICIJ, Investigace.cz, Le Monde and Pandora Papers partners; no thread-specific prize identified.
- Found: a circular $22 million offshore loan bought property omitted from the Czech prime minister’s declarations
- Types: disclosure-gap; networked-asset-concealment; self-financing-loop
- Evidence: Provider loan, incorporation and ownership files . [privileged]; French property records and company registries in the BVI, U.S. and Monaco . [open-public/request-gated]; Czech political asset declarations . [open-public]
- Systems: Pandora Papers loan files; French property records; Czech asset declarations
- Signature: circular-loan-property-disclosure-chain: loan agreements ordered by date and joined on amount, lender, borrower and common beneficial owner revealed a circular financing chain; terminal property title compared with official declarations revealed the omission.
- Method: [inferred]
- Impact: Babiš’s party narrowly lost the election held days after publication; the result cannot be attributed solely to Pandora Papers, but ICIJ documented the timing and political salience (ICIJ election follow-up)
- Dependency: (c) [access-substitution] — private circular-loan path remains indispensable

### South Dakota’s foreign trust vault (2021) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/pandora-papers/us-trusts-offshore-south-dakota-tax-havens/
- Partner/awards: ICIJ, The Washington Post and Pandora Papers partners; no thread-specific prize identified.
- Found: provider files showed more than $1 billion in U.S. trusts tied to foreign clients, including people accused of wrongdoing
- Types: jurisdictional-risk-migration; high-risk-client-servicing; elite-cohort-penetration
- Evidence: Trident Trust and other provider trust records . [privileged]; Court cases, government allegations, sanctions/adverse records and public biographies . [open-public]; South Dakota statutes and official/industry trust-asset statistics . [open-public]
- Systems: Pandora Papers trust files; South Dakota trust statutes; risk and court records
- Signature: foreign-trust-risk-cohort: provider trust records grouped by U.S. situs and settlor origin, then joined to court/government risk records on resolved identity, revealed the foreign high-risk cohort; trust-creation dates compared with state-law changes exposed jurisdictional migration.
- Method: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Impact: the revelations intensified U.S. debate over domestic trust secrecy and informed calls for trust and beneficial-ownership reform; no single federal trust-transparency measure is attributed solely to this thread (project impact review)
- Dependency: (a) [access-substitution] — public trust roles and risk timelines

### Alcogal’s politician-heavy client book and late SARs (2021) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/pandora-papers/alcogal-panama-latin-america-politicians/; https://www.icij.org/investigations/pandora-papers/icij-releases-new-pandora-papers-data-from-two-offshore-service-providers/
- Partner/awards: ICIJ, La Prensa, El País and Latin American Pandora Papers partners; no thread-specific prize identified.
- Found: provider data showed a political client concentration and suspicious reports filed after public exposure
- Types: elite-cohort-penetration; intermediary-enablement; compliance-after-the-fact; warning-to-action-lag
- Evidence: Alcogal client, entity, due-diligence and SAR files . [privileged]; Fixed politician roster and identity-resolution table . [constructed]; Public enforcement records, news publication dates and bank-risk records . [open-public]
- Systems: Alcogal client and SAR files; Offshore Leaks Database; public enforcement records
- Signature: politician-concentration-and-late-SAR-timing: provider clients joined to a fixed politician roster revealed exceptional cohort concentration; SAR creation dates compared with first public-risk dates revealed that 87 of 109 reports followed exposure rather than detecting it.
- Method: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Impact: authorities across Latin America opened tax and corruption reviews of Pandora Papers subjects; the broader investigation prompted official inquiries in many jurisdictions (2021 impact review)
- Dependency: (b) [access-substitution] — public cohort test; SAR timestamps withheld

### Cyprus Confidential (2023) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/cyprus-confidential/; https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/
- Partner/awards: ICIJ and Munich-based Paper Trail Media led 272 journalists from 69 media partners in 54 countries and one territory; partners included The Guardian, The Bureau of Investigative Journalism, Der Spiegel, Le Monde, OCCRP and The Washington Post (about page). No single project-wide prize is claimed here.
- Found: seven leaks exposed Cyprus’s service industry as a major shelter and transfer hub for sanctioned Russian wealth
- Types: jurisdictional-risk-migration; high-risk-client-servicing; intermediary-enablement; elite-cohort-penetration
- Evidence: Company charts, emails, financial statements, annual reports, invoices, wire transfers, trust and ownership documents from seven… [privileged]; NLP/entity extraction, keyword classification and a manually reviewed company/auditor table [constructed]; Forbes’s 2023 billionaires list, Dow Jones risk data, sanctions lists, official political/PEP records, company accounts and… [open-public/request-gated]; Interviews, travel, experts and subject responses [constructed]
- Systems: Cyprus Confidential provider files; Dow Jones Risk & Compliance; Forbes billionaires list; sanctions lists; company accounts
- Signature: Cyprus-client-risk-and-auditor-join: leak-derived beneficial owners and clients joined to time-versioned sanctions, billionaire and political-risk lists revealed the exposed cohort; company accounts joined to auditor names and manually verified ownership quantified professional-firm concentration.
- Method: https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/
- Impact: within 24 hours Cyprus’s president promised an investigation; U.S. financial-crime experts were deployed, and Cyprus later authorized a dedicated sanctions unit (sanctions-unit follow-up)
- Dependency: (b) [access-substitution] — public records verify leak-created client roster

### PwC and Mordashov’s $1.4 billion TUI transfer (2023) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/cyprus-confidential/cyprus-russia-eu-secrecy-tax-haven/; https://www.icij.org/investigations/cyprus-confidential/cypriot-authorities-face-scrutiny-over-probe-into-russian-billionaires-moves-to-dodge-sanctions/
- Partner/awards: ICIJ, Paper Trail Media and Cyprus Confidential partners; no thread-specific prize identified.
- Found: service records captured an ownership move as EU sanctions approached
- Types: deadline-adjacent-restructuring; sanctions-evasion-risk; high-risk-client-servicing; compliance-knowledge-gap
- Evidence: PwC/provider emails, instructions, ownership and transfer records . [privileged]; EU, U.S. and U.K. sanctions designation dates . [open-public]; TUI disclosures, German government statements and corporate ownership records . [open-public]
- Systems: PwC Cyprus files; EU sanctions list; U.S. sanctions list; U.K. sanctions list; TUI disclosures; German corporate records
- Signature: sanctions-cutoff-transfer-timeline: share-transfer instructions and completion records compared to sanctions-announcement and designation dates on owner, asset and effective date revealed a pre-freeze ownership shift; pre/post beneficial ownership identified the closely related recipient.
- Method: https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/
- Impact: Cyprus opened a criminal investigation of the transaction, and German authorities/TUI rejected the transfer’s validity (ICIJ follow-up)
- Dependency: (c) [access-substitution] — internal instruction and completion timestamps required

### Petr Aven’s same-day $5 million payment (2023) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/
- Partner/awards: ICIJ, Paper Trail Media, The Guardian and Cyprus Confidential partners; no thread-specific prize identified.
- Found: a transfer initiated on the day of EU designation exposed the value of hour-level sanctions chronology
- Types: deadline-adjacent-restructuring; sanctions-evasion-risk; intermediary-enablement
- Evidence: Trust/company ownership files, emails, invoices and wire records . [privileged]; U.K. National Crime Agency court filings . [open-public/request-gated litigation]; Cyprus corporate records and EU sanctions notices . [open-public]
- Systems: Abacus files; U.K. National Crime Agency court filings; Cyprus corporate registry; EU sanctions notices
- Signature: same-day-wire-sanctions-clock: wire initiation timestamp compared to the sanctions effective date on sender/beneficiary and owner revealed a same-day transfer; public records joined Abacus nominee directors to the asset-holding entities.
- Method: [inferred]
- Impact: a person associated with Aven later forfeited about $1 million at the center of the U.K. sanctions-evasion case, as recorded on the Cyprus Confidential project hub
- Dependency: (c) [access-substitution] — private wire timestamp is decisive

### Abramovich’s hidden Chelsea payments (2023) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/; https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-fined-millions-over-secret-payments-under-abramovich-ownership/
- Partner/awards: The Guardian and The Bureau of Investigative Journalism led this thread under the ICIJ/Paper Trail Media Cyprus Confidential banner (ICIJ investigation).
- Found: offshore records exposed tens of millions in club-related payments omitted from football accounts
- Types: cross-ledger-mismatch; networked-asset-concealment; off-books-benefit
- Evidence: Offshore-company invoices, payment records, ownership files and emails . [privileged]; Chelsea financial accounts and football regulatory submissions/rules . [open-public/request-gated]; Player-transfer dates, agent identities and corporate records . [open-public]; Review by four sports-law experts . [constructed]
- Systems: Cyprus Confidential payment files; Chelsea financial accounts; Premier League/FA submissions; corporate records
- Signature: offshore-payment-to-football-accounts-diff: payments by owner-controlled offshore entities joined to player/manager transactions on beneficiary, amount and date, then compared with club accounts and required agent disclosures, revealed club-benefiting costs outside the regulated ledger.
- Method: https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/
- Impact: in March 2026 the Premier League fined Chelsea £10.75 million, imposed an academy transfer ban and a suspended first-team transfer ban for undisclosed third-party payments under Abramovich; separate Football Association charges remained possible (ICIJ enforcement follow-up)
- Dependency: (c) [access-substitution] — private off-book payment population is decisive

### Swazi Secrets (2024) — offshore-leaks-canon
- URL: https://www.icij.org/investigations/swazi-secrets/; https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/
- Partner/awards: Distributed Denial of Secrets obtained the records and shared them with ICIJ; ICIJ coordinated 38 journalists across 11 countries (about page). No project-specific prize identified in the reviewed ICIJ pages.
- Found: Africa’s largest known FIU leak exposed Eswatini as a possible conduit for suspicious gold, banking and political money flows
- Types: flow-to-asset-conversion; letterbox-substance-gap; state-linked-benefit; regulator-override
- Evidence: FIU bank records, intelligence reports, police records, affidavits and interagency communications . [privileged official records]; Corporate registries, bank-license documents, economic-zone records and court material . [open-public/request-gated]; Payment-flow reconstruction, site visits to purported refineries, interviews and right-of-reply reporting . [constructed]
- Systems: Eswatini FIU records; corporate registries; bank-licensing records; economic-zone records; court records
- Signature: FIU-flow-substance-and-regulator-override: FIU bank transactions joined across sender, refinery and Dubai recipient revealed the cross-border flow; those companies compared with registry, license and physical-operation evidence exposed phantom substance; regulator objections compared with later political interventions revealed override.
- Method: https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/
- Impact: after publication, Eswatini lawmakers signaled possible press restrictions, and journalists later faced a $9.9 million lawsuit—official reactions that raise retaliation concerns rather than remedial reform (press-freedom follow-up, lawsuit follow-up)
- Dependency: (b) [access-substitution] — public records verify FIU-seeded flow candidates

## Methodology infrastructure (report-09)

### Extract: turn heterogeneous files into text at leak scale — meta-methods
- URL: https://github.com/ICIJ/extract; https://www.icij.org/investigations/panama-papers/data-tech-team-icij/; https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Extract is an MIT-licensed, cross-platform command-line tool for parallelized content extraction and analysis. Its library wraps Apache Tika; its CLI can place jobs on Redis, run workers across machines, invoke Tesseract OCR, and send output to Solr, plain text, or standard output. ICIJ says it used Extract for Swiss Leaks, Luxembourg…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Extract; Apache Tika; Redis; Tesseract; Solr; Blacklight; Amazon Web Services
- Signature: queue-backed-extraction: fan workers through Tika/OCR into searchable text while preserving original files
- Method: https://github.com/ICIJ/extract
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Datashare: self-hosted corpus search rather than a hosted evidence custodian — meta-methods
- URL: https://github.com/ICIJ/datashare; https://datashare.icij.org/; https://icij.gitbook.io/datashare
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare is an AGPL-licensed, self-hosted document search and analysis system. It accepts PDFs, emails, spreadsheets, images, and archives; extracts text and metadata; performs OCR; identifies named entities; exposes a web interface and REST API; and keeps source documents under the operator's control. Datashare repository and…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare; Elasticsearch; SQLite; CoreNLP; OpenNLP; Apache Tika; Tesseract
- Signature: custody-compute-access-separation: separate local evidence custody, scalable derivation, and collaborative search
- Method: https://github.com/ICIJ/datashare
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Named entities are candidate pivots, not verified identities — meta-methods
- URL: https://icij.gitbook.io/datashare/usage/faq/definitions/what-is-a-named-entity; https://icij.gitbook.io/datashare/usage/explore-a-document; https://offshoreleaks.icij.org/?e=true
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare's NER detects mentions including people, organizations, locations, and email addresses. The interface lets a reporter filter by entity type, open the documents where a name occurs, and inspect mention context and extraction information. Datashare named-entity definition and document exploration
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare NER; Offshore Leaks Database
- Signature: entity-mention-candidate-boundary: treat NER output as a review pivot requiring identity evidence
- Method: https://icij.gitbook.io/datashare/usage/faq/definitions/what-is-a-named-entity
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Batch search makes hypothesis lists reproducible — meta-methods
- URL: https://icij.gitbook.io/datashare/usage/batch-search-documents; https://datashare.icij.org/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare accepts a CSV of queries and runs it against a project, preserving a result count and matching documents for each row. Queries can use field filters and Boolean operators, and a completed batch can be relaunched as the corpus changes. The public product page advertises batches of up to 10,000 queries. Batch-search…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare batch search; Elasticsearch
- Signature: reproducible-batch-watchlist: preserve exact seed queries and rerun them over named corpus snapshots
- Method: https://icij.gitbook.io/datashare/usage/batch-search-documents
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Scaling is observable and separable — meta-methods
- URL: https://icij.gitbook.io/datashare/server-mode/performance-considerations; https://icij.gitbook.io/datashare/concepts/running-modes; https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare's performance guidance recommends separating scan from index, distributing index operations, tuning parallelism, and using a remote Elasticsearch cluster when required. ICIJ reports that processing the 2.94 TB Pandora Papers corpus used as many as ten servers and cost several thousand dollars, with Tika and Tesseract among…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare; Elasticsearch; task runner
- Signature: observable-stage-scaling: benchmark scan, index, OCR, and NER separately and scale only the bottleneck
- Method: https://icij.gitbook.io/datashare/server-mode/performance-considerations
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Public repository map — meta-methods
- URL: https://github.com/ICIJ/datashare; https://github.com/ICIJ/datashare-client; https://github.com/ICIJ/extract
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare's Neo4j extension connects document search to graph exploration, but it should not be confused with the separately curated Offshore Leaks ownership graph. The extension says it builds graphs from Datashare projects; the Offshore Leaks packages distribute a graph constructed from provider databases and ICIJ transformation…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: ICIJ GitHub repositories; Datashare; Extract; Neo4j extension; Tarentula; Prophecies; ICIJ MAUDE
- Signature: tool-boundary-repository-map: map each open tool to its role and evidentiary limit before reuse
- Method: https://github.com/ICIJ/datashare
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### The graph model preserves investigative roles — meta-methods
- URL: https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html; https://offshoreleaks.icij.org/schema/oldb; https://github.com/ICIJ/offshoreleaks-data-packages
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ converted structured and semi-structured offshore-provider records into a Neo4j property graph. Its public model has four principal node classes:
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks Database; Neo4j
- Signature: role-preserving-provider-graph: retain entity, officer, intermediary, address, and typed-edge semantics in Neo4j
- Method: https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Provider-specific reverse engineering precedes normalization — meta-methods
- URL: https://offshoreleaks.icij.org/pages/faq; https://www.icij.org/inside-icij/2013/10/users-can-now-search-country-icij-offshore-leaks-database/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: The database is not the output of one universal parser. ICIJ says it used reverse engineering to extract source records and applied programming, scraping, machine learning, or manual extraction through processes that differed by provider. Source codes served as unique identifiers where available; when Panama Papers shareholder and…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks provider databases; Offshore Leaks Database; Google Maps geocoding
- Signature: provider-recipe-before-normalization: reverse-engineer each source schema and preserve IDs before graph unification
- Method: https://offshoreleaks.icij.org/pages/faq
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Public release is deliberately narrower than the leak — meta-methods
- URL: https://www.icij.org/inside-icij/2016/05/icij-releases-panama-papers-offshore-company-data/; https://www.icij.org/investigations/offshore/unlocking-chinas-secrets/; https://offshoreleaks.icij.org/pages/database
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ publishes basic corporate relationships in the public interest, not the full leaked corpus. The public database excludes bulk raw documents and does not publish bank-account data, emails, financial transactions, passports, telephone numbers, or personal information en masse. Panama Papers data-release explanation and “not a data…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks CSV/Neo4j releases; Offshore Leaks reconciliation API
- Signature: selective-public-graph-release: publish bounded relationships and reconciliation interfaces without dumping raw leaks
- Method: https://www.icij.org/inside-icij/2016/05/icij-releases-panama-papers-offshore-company-data/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Updates are investigation-triggered and vintage-specific, not periodic — meta-methods
- URL: https://offshoreleaks.icij.org/pages/faq; https://offshoreleaks.icij.org/pages/data
- Partner/awards: Not applicable (methodology/tool unit)
- Found: The public database launched with Offshore Leaks data in June 2013, added Greater China records in January 2014, Panama and Bahamas records in 2016, staged Paradise Papers data across 2017–2018, and staged Pandora Papers data across 2021–2022. Its FAQ promises to describe updates when they occur but publishes no monthly, quarterly, or…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks Database release history
- Signature: vintage-bound-release-cadence: attach provider, investigation, and cutoff date to every public-graph hit
- Method: https://offshoreleaks.icij.org/pages/faq
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Caveat discipline is part of the interface — meta-methods
- URL: https://offshoreleaks.icij.org/?e=true; https://offshoreleaks.icij.org/pages/disclaimer; https://offshoreleaks.icij.org/pages/howtouse
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Before searching, a user must acknowledge a statement that legitimate offshore structures exist; inclusion does not imply illegal or improper conduct; common names require identity confirmation; each dataset covers a defined period; and information may have changed. The searchable page repeats those warnings and provides an error…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks search gate; Offshore Leaks disclaimer
- Signature: caveat-as-query-interface: bind identity and legality warnings to search and result interpretation
- Method: https://offshoreleaks.icij.org/?e=true
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Correction, pruning, and takedown are distinct — meta-methods
- URL: https://offshoreleaks.icij.org/pages/faq; https://offshoreleaks.icij.org/pages/disclaimer; https://www.icij.org/about/corporate/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ says it removed isolated people, entities, and addresses with no apparent database connections from the public graph, and it documents a 2016 relationship error and its correction in the FAQ. Those are structural curation and factual correction, not a merits-based takedown rule. Offshore Leaks FAQ
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Offshore Leaks FAQ correction log; ICIJ complaints process; DMCA process
- Signature: correction-pruning-takedown-split: record factual correction, structural curation, and legal removal as distinct actions
- Method: https://offshoreleaks.icij.org/pages/faq
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### “Radical sharing” reverses newsroom default incentives — meta-methods
- URL: https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ describes its Panama Papers model as “radical sharing”: hundreds of journalists shared leads, notes, documents, and planned stories across organizations that might ordinarily compete. The 2016 project involved 376 reporters in almost 80 countries and rested on trust accumulated over roughly two decades. ICIJ's “Radical Sharing” essay
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub; Datashare
- Signature: radical-sharing-control-plane: combine shared evidence, notes, agreements, permissions, and coordinated publication
- Method: https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Global I-Hub is the secure virtual newsroom — meta-methods
- URL: https://www.icij.org/inside-icij/2014/07/icij-build-global-i-hub-new-secure-collaboration-tool/; https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/; https://www.icij.org/inside-icij/2020/01/how-icij-will-rock-its-tech-in-2020/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ launched the Global I-Hub as a secure collaboration platform built around the open-source Oxwall community system, adding security and encryption layers and designing it with user input. I-Hub launch announcement
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub; Oxwall; Datashare
- Signature: evidence-discussion-history-bridge: link document discovery in Datashare to discussion and assignments in I-Hub
- Method: https://www.icij.org/inside-icij/2014/07/icij-build-global-i-hub-new-secure-collaboration-tool/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Partners are vetted for behavior as well as skill — meta-methods
- URL: https://www.icij.org/investigations/panama-papers/faqs/; https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's Panama Papers FAQ lists four partner-selection considerations: a proven investigative record, organizational support for a slow deep dive, willingness to share discoveries with the global team, and interpersonal fit. ICIJ says prospective partners are vetted and trained in the required tools. Panama Papers FAQ
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub onboarding; partner agreements
- Signature: partner-vetting-as-access-control: gate corpus access on skill, collaboration, security, and institutional commitment
- Method: https://www.icij.org/investigations/panama-papers/faqs/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Embargoes are contractual coordination infrastructure — meta-methods
- URL: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/; https://www.icij.org/inside-icij/2013/04/how-we-all-survived-likely-largest-collaboration-journalism-history/; https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Panama Papers participants signed an agreement to respect the embargo and simultaneous publication. ICIJ argues that coordinated release produces a “big bang” that makes suppression and localized dismissal harder. Panama Papers technical/team account
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub; embargo agreements; publication calendar
- Signature: embargo-readiness-state-machine: move partners from invitation through reviewed coordinated release with explicit states
- Method: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Multilingual fact-checking is federated — meta-methods
- URL: https://www.icij.org/about/; https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/; https://www.icij.org/investigations/west-africa-leaks/behind-the-scenes-of-the-largest-ever-west-african-journalism-collaboration/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's network has more than 290 invite-only members in more than 100 countries and says peer scrutiny across cultural and linguistic traditions improves accuracy and depth. ICIJ About page. Paradise Papers credits record 380 journalists on six continents working in 30 languages, with named data, editorial, fact-checking, and research…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub; Datashare; Prophecies
- Signature: federated-multilingual-verification: layer local, regional, central, and legal review across languages
- Method: https://www.icij.org/about/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### What is a tool and what is a human capability — meta-methods
- URL: https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/; https://www.icij.org/investigations/panama-papers/faqs/; https://github.com/ICIJ/prophecies
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Each toolable element is supported by ICIJ's I-Hub, Datashare, Prophecies, and written-agreement descriptions; the human/tool boundary is [inferred] from the roles ICIJ assigns to partner selection, regional coordination, editing, fact-checking, and legal review. I-Hub methods, partner criteria, and Prophecies repository
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Global I-Hub; Datashare; Prophecies
- Signature: tool-human-boundary: automate permissions and tracking while reserving trust and judgment for people
- Method: https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Panama Papers: two pipelines, one reporting surface — meta-methods
- URL: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: For unstructured files, the Panama team used Extract, Tika, Tesseract, Solr, and Blacklight. For structured Mossack Fonseca databases, it reverse-engineered schemas, used Talend to extract and transform records, loaded relationships into Neo4j, and exposed graph exploration through Linkurious. The search and graph services were…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Extract; Apache Tika; Tesseract; Solr; Blacklight; Talend; Neo4j; Linkurious
- Signature: dual-representation-pipeline: process documents and relational records separately, then connect both to originals
- Method: https://www.icij.org/investigations/panama-papers/data-tech-team-icij/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Implant Files: text classification with explicit abstention — meta-methods
- URL: https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/; https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/; https://github.com/HazyResearch/icij-maude
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ gathered more than eight million medical-device records through over 1,500 public-record requests and downloads. For U.S. FDA adverse-event data, the team used Talend, Microsoft SQL Server, R, text mining, clustering, rules, and classification to identify deaths that appeared misclassified as other outcomes. A seed list of 121…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: FDA MAUDE; Talend; Microsoft SQL Server; R; Snorkel; ICIJ MAUDE
- Signature: regulatory-text-semantic-scan: expand adverse-event terms, classify candidates, and manually review false positives; missing-field-weak-supervision: combine audited labeling rules with explicit abstention and publish coverage
- Method: https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/
- Impact: Not applicable (methodology infrastructure)
- Dependency: (a) [access-substitution] — public regulatory text supports audited classifiers

### FinCEN Files: manual extraction won when language defeated automation — meta-methods
- URL: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: The FinCEN Files contained more than 2,100 suspicious activity reports and other records, including roughly three million words of narrative and inconsistent transaction attachments. Eighty-five journalists in 30 countries manually extracted details into a structured system, producing more than 55,000 records covering over 200,000…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: FinCEN suspicious activity reports; SQL/Python extraction; Neo4j; Linkurious
- Signature: reviewed-manual-extraction: structure irregular SAR narratives through field-level entry and three review passes
- Method: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Luanda Leaks: multilingual corpus plus selected machine assistance — meta-methods
- URL: https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/; https://www.icij.org/investigations/luanda-leaks/explore-how-to-build-a-business-empire/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ loaded more than 715,000 Luanda Leaks records into Datashare for about 120 journalists. More than half the corpus was in Portuguese. The team wrapped the open-source Apertium translator for offline use to protect source material, used batch searches and NER, and combined Talend, SQL, Neo4j, and Linkurious for structured…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare; Apertium; Talend; Neo4j; Linkurious; Quartz AI Studio
- Signature: offline-multilingual-assisted-analysis: translate and classify confidential multilingual text locally, then verify outputs
- Method: https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Pandora Papers: one leak, fourteen provider-specific data projects — meta-methods
- URL: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Pandora Papers comprised 11.9 million files totaling 2.94 TB from 14 providers, with only about 4% in spreadsheet form. ICIJ built provider-specific pipelines, deduplicated source spreadsheets, used Python to extract data, applied tools including Fonduer and scikit-learn to recurring forms, and manually handled handwriting and formats…
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Pandora provider databases; Python; Fonduer; scikit-learn; public risk lists
- Signature: provider-partitioned-ETL: build and audit one extraction recipe per provider before cross-provider matching
- Method: https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Prophecies turns validation into a first-class application — meta-methods
- URL: https://www.icij.org/investigations/fincen-files/mining-sars-data/; https://github.com/ICIJ/prophecies; https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's FinCEN custom Django fact-checking tool evolved into Prophecies, an AGPL, self-hosted platform for data cleaning and labor-intensive fact-checking, with documented APIs. FinCEN Files methodology and ICIJ/Prophecies repository
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Prophecies; Datashare; passport computer-vision service
- Signature: rare-document-image-classifier: reduce a large image corpus to candidates and adjudicate them through repeated human review
- Method: https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Impact: Not applicable (methodology infrastructure)
- Dependency: (a) [access-substitution] — public corpora support classifier and review

### Leak authentication is triangulation, not a single ritual — meta-methods
- URL: https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/; https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/; https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ says Pandora Papers teams rigorously verified and cross-checked material for authenticity and verified every fact used in stories; the source was anonymous, unpaid, and imposed no conditions. Pandora Papers FAQ
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare; Offshore Leaks Database; official corporate/regulatory/court records
- Signature: multi-level-leak-authentication: triangulate corpus, document, identity, and claim against independent records
- Method: https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Source-to-claim distance controls confidence — meta-methods
- URL: https://icij.gitbook.io/datashare/usage/explore-a-document; https://offshoreleaks.icij.org/pages/faq; https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's public tools preserve several layers: original file; extracted text/OCR; named entity or model output; normalized record; resolved entity; graph relationship; journalist claim. Datashare document exploration, Offshore Leaks FAQ, and Implant Files weak-supervision method
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare provenance layers; Offshore Leaks Database; model-validation records
- Signature: source-to-claim-distance: carry transformation lineage and reduce certainty with each derivative step
- Method: https://icij.gitbook.io/datashare/usage/explore-a-document
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Subject response is a pre-publication evidence channel — meta-methods
- URL: https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/; https://www.icij.org/investigations/implant-files/implant-files-prompt-immediate-response-before-first-stories-published/; https://www.icij.org/investigations/ericsson-list/ericsson-facing-ongoing-probes-and-fallout-months-after-icij-revealed-new-corruption-breach/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's Panama Papers retrospective states that reporters lay out their findings before publication and give subjects a chance to respond, normally allowing weeks when security and timing permit. Panama Papers ten-year retrospective
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: ICIJ subject-response workflow; Global I-Hub
- Signature: subject-response-as-evidence: log detailed questions, full answers, evidence supplied, and resulting revisions
- Method: https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Fact-checking, editorial vetting, and legal review are separate gates — meta-methods
- URL: https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/; https://www.icij.org/investigations/fincen-files/mining-sars-data/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ describes the FinCEN Files and Luanda Leaks as undergoing rigorous fact-checking, editorial vetting, and legal review. FinCEN's underlying manual data extraction was itself reviewed three times before story-level checks. ICIJ lessons from FinCEN and Luanda and FinCEN data methodology
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Prophecies; Global I-Hub; claim and review records
- Signature: separate-review-gates: distinguish data validation, fact-check, editorial judgment, and legal review
- Method: https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Corrections and complaints are visible but less systematized publicly — meta-methods
- URL: https://www.icij.org/about/corporate/; https://media.icij.org/uploads/2018/02/spj-code-of-ethics.pdf; https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: ICIJ's editorial policy adopts the Society of Professional Journalists Code of Ethics and provides complaints@icij.org, including confidential handling where appropriate. ICIJ corporate/editorial policy. The linked SPJ code requires verification, subject response, and prompt, prominent correction. SPJ Code of Ethics PDF hosted by ICIJ
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: ICIJ complaints channel; Offshore Leaks FAQ; article correction notes
- Signature: correction-object-ledger: link old claim, correction, evidence, reason, decision-maker, and affected outputs
- Method: https://www.icij.org/about/corporate/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Dataset and document releases — meta-methods
- URL: https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/; https://medicaldevices.icij.org/p/about; https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: The FinCEN page is especially disciplined: it states the released denominator, why only records with both bank endpoints were included, that the data is a fraction of the leak, and that flagged transactions do not necessarily establish misconduct. FinCEN Files download and caveats
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: ICIJ FinCEN transaction dataset; International Medical Devices Database; Solitary Voices dataset; Luanda Leaks company network; LuxLeaks Datashare
- Signature: bounded-release-with-denominator: publish selected datasets with coverage, exclusions, and non-causation caveats
- Method: https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

### Software APIs versus evidence APIs — meta-methods
- URL: https://github.com/ICIJ/datashare; https://github.com/ICIJ/prophecies; https://www.icij.org/inside-icij/2025/01/explore-the-latest-tool-to-power-up-investigations-via-the-offshore-leaks-database/
- Partner/awards: Not applicable (methodology/tool unit)
- Found: Datashare exposes a REST API for a self-hosted corpus and Prophecies publishes an application API; these are interfaces to software an operator controls, not centralized ICIJ evidence feeds. Datashare repository and Prophecies repository/API link
- Types: not coded (methodology unit)
- Evidence: ICIJ documentation and public repositories [open-public]; project method pages [open-public]; analysis marked [inferred] in the source report
- Systems: Datashare REST API; Prophecies API; Offshore Leaks reconciliation API
- Signature: software-API-versus-evidence-API: distinguish self-hosted tool interfaces from bounded hosted evidence feeds
- Method: https://github.com/ICIJ/datashare
- Impact: Not applicable (methodology infrastructure)
- Dependency: unassessed

## Extractives and environment (report-12)

### Australian mining companies digging a deadly footprint in Africa (2015) — extractives-environment
- URL: https://www.icij.org/investigations/fatal-extraction/australian-mining-companies-digging-deadly-footprint-africa/
- Partner/awards: ICIJ coordinated the investigation with the African Network of Centers for Investigative Reporting (ANCIR), fielding 13 reporters in 13 African countries; local reporting partners included Mmegi, Nyasa Times, Dépêches du Mali, Daily News, The Post of Zambia, Citi FM, L’Evénement, and Voice of America.
- Found: Resolving African mines and deaths back to Australian-listed parents exposed a far larger human toll than issuer disclosures conveyed
- Types: Disclosure-footprint gap
- Evidence: Issuer disclosures — public securities records, downloaded and reviewed; License and project records — public and commercial reference records, cross-checked manually; Incident and legal records — public/local records, gathered country by country; Field evidence — first-hand reporting
- Systems: ASX issuer filings; SNL Metals & Mining; InfoMine; Investogain; mining-license records
- Signature: Issuer-to-harm reconciliation: ASX issuer filings and mining-license/project records joined to local court, government, and incident records on parent/subsidiary + mine/site + event date revealed deaths and abuses dispersed across local records, including events absent from parent-company disclosures. Methodology
- Method: https://www.icij.org/investigations/fatal-extraction/data-and-field-work-combine-reveal-australian-minings-impact-africa/
- Impact: No official consequence coded in source report
- Dependency: (a) — decisive inputs are obtainable public records

### How auditing firms help companies hide environmental damage and human rights abuses (2023) — extractives-environment
- URL: https://www.icij.org/investigations/deforestation-inc/auditors-green-labels-sustainability-environmental-harm/
- Partner/awards: ICIJ led a collaboration of 43 media partners in 28 countries, including Der Spiegel, NDR, Süddeutsche Zeitung, Le Monde, Radio France, NRC, Tempo, The Indian Express, CBC/Radio-Canada, and Convoca. The project won the 2024 John B. Oakes Award for Distinguished Environmental Journalism. Project attribution Award
- Found: Certification periods overlapped hundreds of alleged or adjudicated harms that “sustainable” labels were supposed to screen out
- Types: Assurance-conduct contradiction
- Evidence: Allegation/adjudication case corpus — public records and reports, collected and structured; Certification records — public certification databases, downloaded and normalized; Corporate hierarchy — commercial and public company research, reconciled manually; Regulatory coverage — public and freedom-of-information records
- Systems: FSC certification registry; PEFC certification registry; Orbis; EU forestry monitoring reports
- Signature: Certificate-violation temporal overlap: court, regulator, community, and NGO cases joined to FSC/PEFC certificate records on resolved corporate group + operating unit + event/certificate dates revealed alleged or adjudicated harms occurring while certificates issued by 48 auditors were active. Methodology
- Method: https://www.icij.org/investigations/deforestation-inc/how-we-used-data-to-expose-flaws-in-hundreds-of-green-claims-by-forest-products-companies/
- Impact: No official consequence coded in source report
- Dependency: (a) — decisive inputs are obtainable public records

### Companies are importing teak from Myanmar despite sanctions and military rule (2023) — extractives-environment
- URL: https://www.icij.org/investigations/deforestation-inc/myanmar-teak-trade-sanctions-military-regime/
- Partner/awards: This is ICIJ-led reporting by Scilla Alecci and Jelena Cosic within Deforestation Inc.; reporting contributions named in the story include the Miami Herald, NRC, Commonwealth Magazine, New Zealand Herald, L’Espresso/IRPI Media, The Indian Express, Paper Trail Media, and NDR.
- Found: Trade and tax records traced restricted timber through intermediaries into certified Western supply chains
- Types: Intermediary sanctions bypass; Assurance-conduct contradiction
- Evidence: Myanmar tax records — leaked administrative data, obtained through collaborators; International trade records — licensed and public datasets, queried by company and product; Sanctions and corporate records — public government and registry sources; Certification records — public databases
- Systems: Myanmar tax records; ImportGenius; UN Comtrade; U.S. sanctions list; U.K. sanctions list; EU sanctions list; Myanmar company records; FSC certification registry; PEFC certification registry
- Signature: Sanctions-window supply-chain trace: leaked Myanmar tax transactions and international shipment records joined to sanctions lists, exporter ownership, and certificate validity on supplier/intermediary/importer + product + transaction date revealed state-linked teak moving after sanctions through formally unsanctioned counterparties under green labels. Story
- Method: https://www.icij.org/investigations/deforestation-inc/how-we-used-data-to-expose-flaws-in-hundreds-of-green-claims-by-forest-products-companies/
- Impact: After ICIJ’s questions, the Forest Stewardship Council said it was investigating certified companies’ Myanmar teak supply chains. Story
- Dependency: (b) — public verification follows a private discovery anchor

### The Mediterranean feeding frenzy (2010) — extractives-environment
- URL: https://www.icij.org/investigations/looting-the-seas/part-i-mediterranean-feeding-frenzy/
- Partner/awards: ICIJ coordinated a seven-month investigation by 12 journalists with BBC World News, Le Soir, Stern, The Sunday Times, and Il Fatto Quotidiano; the methodology names ICIJ data editor Kate Willson as the analyst of the confidential bluefin catch-document database.
- Found: Catch-chain records and quota arithmetic showed that industrial bluefin trade substantially exceeded lawful and sustainable limits
- Types: Paper-chain laundering
- Evidence: Bluefin Catch Document database — password-protected regulator data, accessed through a member-state source; Confidential complete file — non-public source material, used for validation; Quota and scientific estimates — public international-regulator records; Market valuation — trade and price research
- Systems: ICCAT Bluefin Catch Document database; ICCAT quota and scientific records
- Signature: Regulated-chain mass balance: Bluefin Catch Document catch, transfer, ranch, harvest, and export rows joined on catch-document ID + vessel + ranch + date, then compared with vessel quotas and biological minimum weights, revealed missing verification data, harvest exceeding recorded input, and suspicious exact-threshold weights. Project and methodology
- Method: https://www.icij.org/investigations/looting-the-seas/about-project-3/
- Impact: No official consequence coded in source report
- Dependency: (d) — decisive ledger sits behind closed access

### Nearly €6 billion in subsidies fuel Spain’s ravenous fleet (2011) — extractives-environment
- URL: https://www.icij.org/investigations/looting-the-seas-ii/nearly-eu6-billion-subsidies-fuel-spains-ravenous-fleet/
- Partner/awards: ICIJ led a two-year investigation with The Sunday Times, El País, EUobserver, HuffPost, and Trouw.
- Found: A reconstructed benefits ledger showed public aid continuing to firms and vessels with adverse fishing records
- Types: Public-aid recidivism
- Evidence: Subsidy awards — government administrative records, obtained from multiple levels; Indirect aid — public budget and policy records, modeled conservatively; Adverse records — court and regulator documents, matched to beneficiaries; Economic denominator — official statistics
- Systems: Spanish subsidy and gazette records; fishing-vessel and ownership registries; court and enforcement records
- Signature: Subsidy-to-sanction continuation join: paid subsidy rows joined to final court and enforcement records on beneficiary/company group + vessel + award/adverse-decision date revealed firms that kept receiving aid after adverse findings; aggregating all aid categories and comparing them with sector gross value added revealed the scale of dependence. Methodology
- Method: https://www.icij.org/investigations/looting-the-seas-ii/subsidy-methodology/
- Impact: After publication, EU Fisheries Commissioner Maria Damanaki said the European Commission was investigating possible illegalities and misuse of aid by Spanish fishing companies. ICIJ impact report
- Dependency: (a) — decisive inputs are obtainable public records

### The hake hoax: cheaper fish sold as premium species in Spanish markets (2011) — extractives-environment
- URL: https://www.icij.org/investigations/looting-the-seas-ii/hake-hoax-spanish-markets/
- Partner/awards: ICIJ commissioned and coordinated the test within Spain’s $8 Billion Fish, working with the University of Oviedo; the parent project’s lead publishing partners were The Sunday Times, El País, EUobserver, HuffPost, and Trouw.
- Found: Blind DNA tests converted retail labels into falsifiable species claims
- Types: Label-substance mismatch
- Evidence: Retail sample corpus — investigator-created evidence; Blind laboratory testing — commissioned scientific analysis; Reference sequence comparison — public scientific database; Vendor retest — independent commercial corroboration
- Systems: retail sample ledger; GenBank genetic reference database; laboratory test records
- Signature: Label-to-genome identity diff: retail label and purchase metadata joined to blinded COI sequence matches on coded sample ID, then compared on claimed species versus genetic species, revealed an 8.6% mislabeling rate and the implicated vendors. DNA methodology
- Method: https://www.icij.org/investigations/looting-the-seas-ii/hake-dna-testing-how-we-did-it/
- Impact: El Corte Inglés withdrew the independently confirmed 1.4-ton batch and announced routine genetic testing. Story
- Dependency: (a) — decisive inputs are obtainable public records

### Lords of the fish (2012) — extractives-environment
- URL: https://www.icij.org/investigations/looting-the-seas/lords-fish/
- Partner/awards: ICIJ coordinated Plunder in the Pacific with Chilean lead outlet CIPER, whose Juan Pablo Figueroa Lasch reported this story, alongside partners including Le Monde, the International Herald Tribune, El Mundo, and Trouw. The project received a citation (honorable mention) from the Overseas Press Club’s Whitman Bassow Award judges for international environmental reporting. Project attribution and award
- Found: Rolling nominal quota holders up to merged groups and controlling families revealed that eight groups held 87% of Chile’s jack-mackerel rights
- Types: Fragmented-rights concentration
- Evidence: Quota records — public administrative data; Ownership and corporate events — public securities and legal records; Policy and scientific baselines — public council and government records
- Systems: Chilean quota reports; official gazette notices; securities filings; scientific catch advice
- Signature: Beneficial-control quota rollup: nominal company quota rows joined to securities filings, gazette merger notices, and family ownership on company identifier/name + effective date + controlling group revealed eight groups holding 87% of the quota despite more fragmented official presentation. Methodology
- Method: https://www.icij.org/investigations/looting-seas-iii/methodology-behind-numbers/
- Impact: At the project level, Chile’s Senate voted 26–0 to ratify the South Pacific Regional Fisheries Management Organization treaty after publication; ICIJ reported that Chile, Russia, and South Korea’s ratifications cleared the way for binding regional quotas. ICIJ impact report
- Dependency: (a) — decisive inputs are obtainable public records

### Peru’s vanishing fish (2012) — extractives-environment
- URL: https://www.icij.org/investigations/looting-seas-iii/perus-vanishing-fish/
- Partner/awards: ICIJ coordinated the project; Peruvian lead outlet IDL-Reporteros and reporter Milagros Salazar led this investigation, with the wider Plunder in the Pacific partnership including Le Monde, the International Herald Tribune, El Mundo, and Trouw.
- Found: Comparing two mandatory measurements of the same landings exposed 630,000 metric tons disappearing between vessel declaration and plant scale
- Types: Process-stage shrinkage
- Evidence: Landing-level paired measurements — non-public administrative database, obtained from sources; Scale inspections — government records, manually entered; Quota and ownership records — public administrative and corporate material; Price records — official data; Field reporting — first-hand inspection and interviews
- Systems: Peruvian landing database; 2009 scale-inspection report; quota and ownership records; official fish-price records
- Signature: Two-stage weighing shrinkage: vessel-declared catch joined to processing-plant scale weight on landing/vessel + plant + landing date, then filtered at a greater-than-10% discrepancy and rolled up by company, revealed 630,000 metric tons and roughly $200 million missing between adjacent controls. Methodology
- Method: https://www.icij.org/investigations/looting-seas-iii/methodology-behind-numbers/
- Impact: No official consequence coded in source report
- Dependency: (c) — decisive relation requires non-public source material

### Water and politics: The fall of Suharto and Jakarta’s no-bid privatization (2003) — extractives-environment
- URL: https://www.icij.org/investigations/waterbarons/water-and-politics-fall-suharto/
- Partner/awards: The Water Barons was produced by ICIJ at the Center for Public Integrity; this story is credited to Andreas Harsono on ICIJ’s project site, and the page does not identify a separate lead member outlet.
- Found: Contracts, political directives, and performance records reconstructed how crony-linked firms acquired the city’s water system while public risk and weak oversight persisted
- Types: Concession capture
- Evidence: Concession contracts — obtained primary documents; Political directives and correspondence — obtained government and company documents; Development-finance records — public institutional documents; Ownership and financial disclosures — public corporate research; Performance and price records — utility/contract records and interviews
- Systems: Jakarta concession contracts; World Bank project database; PAM Jaya performance and tariff records; corporate filings
- Signature: Concession promise/control-rights reconstruction: concession clauses and political directives joined to World Bank financing, local-partner ownership, tariffs, investment, and service metrics on concession + counterparty + obligation + due date revealed no-bid entry, public assumption of downside risk, limited financial oversight, and missed service promises. Story
- Method: [inferred]
- Impact: No official consequence coded in source report
- Dependency: (c) — decisive relation requires non-public source material

### Colombia’s black-market coltan tied to drug traffickers and paramilitaries (2012) — extractives-environment
- URL: https://www.icij.org/investigations/coltan/colombias-black-market-coltan-tied-drug-traffickers-paramilitaries/
- Partner/awards: ICIJ coordinated reporting across six countries; Colombian reporting involved Ignacio Gómez and lead outlet Noticias Uno, with project partners including El Universal, Armando.info, Noticias Uno, and El Espectador.
- Found: Permits, export forms, seizures, sanctions, and field reporting showed how mineral from a protected conflict zone could approach the legal supply chain
- Types: Conflict-commodity laundering
- Evidence: Mining licenses and tax export forms — public/government primary records; Criminal and sanctions records — public primary records; Seizure and mineral-composition evidence — law-enforcement records and source account; Field observation and interviews — first-hand reporting
- Systems: Colombian mining licenses; tax export forms; seizure records; U.S. Treasury Kingpin designations; court records
- Signature: Origin-legality chain reconstruction: mining permits and export forms joined to protected-area seizures, license actions, and criminal/sanctions records on permit holder/exporter + mine origin + shipment date + foreign buyer revealed how a scarce legal title could serve as an apparent gateway for ore originating outside the licensed chain. Story
- Method: [inferred]
- Impact: After the investigation, Colombian President Juan Manuel Santos announced plans to make coltan a strategic mineral reserve and to clean up its mining and trade. ICIJ impact report
- Dependency: (a) — decisive inputs are obtainable public records

### The climate lobby from soup to nuts (2009) — extractives-environment
- URL: https://www.icij.org/investigations/global-climate-change-lobby/climate-lobby-soup-nuts/
- Partner/awards: ICIJ coordinated reporters in eight major economies; this U.S.
- Found: Lobby registrations and successive bill versions exposed a surge of regulated interests seeking delays, free allowances, and weaker near-term targets
- Types: Policy-delay lobbying
- Evidence: Lobby registrations — public administrative records; Campaign contributions — public political-finance records; Bill versions and policy documents — public legislative records; Cross-country registers and corporate records — public but structurally incomplete data; Interviews — first-hand reporting
- Systems: U.S. lobbying disclosures; Canadian Lobbying Registry; campaign-finance records; successive climate-bill versions
- Signature: Lobby-entry-to-policy delta: quarterly lobby filings joined to clients and industries on registrant/client + issue/bill + quarter, then compared with successive bill versions on provision + version date, revealed a surge of 140 new interests and contemporaneous weakening, delay, and carveouts. The join identifies actors, demands, and temporal alignment; it does not by itself prove that any one lobbyist caused a particular textual change. Story Project attribution and methodology
- Method: https://www.icij.org/investigations/global-climate-change-lobby/about-project-global-climate-change-lobby/
- Impact: No official consequence coded in source report
- Dependency: (a) — decisive inputs are obtainable public records

## Conflict, repression, and transnational rights (report-13)

### Exposed: China's Operating Manuals for Mass Internment and Arrest by Algorithm (2019) — conflict-repression
- URL: https://www.icij.org/investigations/china-cables/exposed-chinas-operating-manuals-for-mass-internment-and-arrest-by-algorithm/; https://www.icij.org/investigations/china-cables/read-the-china-cables-documents/; https://www.icij.org/investigations/china-cables/about-the-china-cables-investigation/
- Partner/awards: This was an ICIJ-coordinated investigation, not a member-outlet story merely republished under the banner.
- Found: Secret directives showed that Xinjiang's “training centers” were coercive camps supplied with detainees by a predictive-policing system
- Types: coercive-rulebook exposure; algorithm-to-custody pipeline; euphemism-record contradiction
- Evidence: Leaked state directives — non-public primary records:; Document-authentication panel — expert verification:; Former-detainee and diaspora interviews — firsthand corroboration:; Prior open reporting and official responses — contextual checks:
- Systems: China Cables directives; IJOP bulletins; satellite camp records
- Signature: Rulebook-to-practice conformance match: the camp telegram and IJOP bulletins were compared to former-detainee accounts, public descriptions, and observed camp features on keys facility routine, prohibited conduct, decision rule, date, and responsible authority, revealing that “vocational” sites were secured detention facilities fed by algorithmic selection.
- Method: https://www.icij.org/investigations/china-cables/about-the-china-cables-investigation/
- Impact: A 2026 peer-reviewed study reported by ICIJ concluded that the project and parallel coverage helped force a public policy shift; days after publication, Xinjiang officials claimed all “trainees” had “graduated,” and the study associated the scrutiny with partial dismantling of the camp system. This is a…
- Dependency: (c) — decisive relation requires non-public source material

### How China Targets Uighurs “One by One” for Using a Mobile App (2019) — conflict-repression
- URL: https://www.icij.org/investigations/china-cables/how-china-targets-uighurs-one-by-one-for-using-a-mobile-app/; https://www.icij.org/investigations/china-cables/about-the-china-cables-investigation/
- Partner/awards: This is an ICIJ-authored story within the ICIJ-coordinated China Cables project, by Scilla Alecci.
- Found: An IJOP bulletin made ordinary religious file-sharing a selector for individual investigation and possible internment
- Types: identity-proxy targeting; selector-scale repression
- Evidence: Leaked IJOP bulletin — non-public primary record:; Detainee/refugee testimony — firsthand corroboration:; Contemporaneous case reporting — external corroboration:; Technical and human-rights research — system context:
- Systems: IJOP bulletin; Zapya case records; mobile-forensics procurement records
- Signature: Selector-to-person funnel reconstruction: the IJOP bulletin was compared to individual detention accounts and later implementation reports on keys app name, protected-content indicator, date, locality, and custody outcome, revealing that use of Zapya functioned as a population-scale religious proxy feeding individual detention decisions.
- Method: https://www.icij.org/investigations/china-cables/about-the-china-cables-investigation/
- Impact: No app-specific official change is documented. Project-wide, a later study credited the broader China Cables reporting with helping force Beijing to change its public position and partly dismantle the mass-camp system. ICIJ impact report
- Dependency: (c) — decisive relation requires non-public source material

### Inside China's Machinery of Repression—and How It Crushes Dissent Around the World (2025) — conflict-repression
- URL: https://www.icij.org/investigations/china-targets/china-transnational-repression-dissent-around-world/; https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/; https://www.icij.org/investigations/china-targets/about-china-targets-investigation/
- Partner/awards: ICIJ led the 10-month collaboration with 42 media partners.
- Found: A standardized case matrix showed the same state playbook recurring against 105 critics in 23 countries
- Types: repression-playbook replication; family-hostage coercion; host-state protection gap
- Evidence: Standardized victim cohort — original interviews:; Internal police/security doctrine — confidential primary records:; Recorded operations — private digital evidence:; Public legal and policy records — verification/context:
- Systems: China Targets case matrix; court and police records; parliamentary inquiries; cyber-threat advisories
- Signature: Playbook-to-case matrix: internal Chinese tactic guides were compared to a coded cohort of 105 target histories on keys tactic, actor role, target affiliation, relative relationship, jurisdiction, and event sequence, revealing a systematic cross-border program rather than a collection of idiosyncratic disputes.
- Method: https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/
- Impact: Canadian lawmakers explicitly invoked the ICIJ/CBC reporting while urging implementation of the Countering Foreign Interference Act and stronger action against transnational repression. The law predated publication, so the documented impact is renewed implementation pressure, not passage of the statute. ICIJ impact…
- Dependency: (c) — decisive relation requires non-public source material

### Case Involving Alibaba's Jack Ma Shows How China Weaponizes Interpol (2025) — conflict-repression
- URL: https://www.icij.org/investigations/china-targets/interpol-red-notice-police-warrant-jack-ma/; https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/
- Partner/awards: The article is an ICIJ-authored China Targets story by Scilla Alecci with network reporting.
- Found: A Red Notice's stated charge diverged from recorded demands that its subject help an unrelated corruption case
- Types: international-warrant weaponization; accusation-purpose mismatch; remedy-capacity gap
- Evidence: Extradition and court files — legal records:; Recorded calls/messages — private direct evidence:; Confidential CCF decisions and target interviews — non-public case records:; Interpol annual statistics and public reports — open trend data:
- Systems: Interpol Red Notices; CCF decisions; French extradition records; Interpol annual reports
- Signature: Accusation-purpose mismatch reconstruction: the Red Notice and extradition allegation were compared to recorded pressure calls and the Sun Lijun case on keys subject, requested act, alleged offense, intermediary, and date, revealing that the notice was being used to compel cooperation in a different investigation.
- Method: https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/
- Impact: The French court's 2021 refusal and CCF's 2022 deletion are official outcomes in the reconstructed case, but both predate the 2025 story and therefore are not publication impact. ICIJ story
- Dependency: (b) — public verification follows a private discovery anchor

### At the UN, China Is Deploying a Growing Army of Puppet Organizations to Monitor and Intimidate Human Rights Activists (2025) — conflict-repression
- URL: https://www.icij.org/investigations/china-targets/united-nations-ngo-gongo-intimidate-human-rights/; https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/
- Partner/awards: This is an ICIJ-authored network story by Tamsin Lee-Smith and Jelena Cosic within the ICIJ-led China Targets collaboration.
- Found: Open records exposed state-linked groups occupying the privileges and speaking space reserved for independent civil society
- Types: state-proxy civil society; speaking-slot capture; accreditation-integrity gap
- Evidence: U.N. accreditation and speaker data — open administrative records:; Organizational records — open web and filed documents:; Person-role records — open official sources:; Speech-content corpus — public statements:; Interviews, observation, photos, and complaints — firsthand/incident evidence:
- Systems: ECOSOC NGO database; U.N. Human Rights Council speaker lists; NGO accreditation applications; archived organization websites
- Signature: Status-independence conformance join: the U.N.-accredited NGO roster was joined to government/party role records, state-funding disclosures, governance clauses, and speech positions on keys organization name, officer identity, date, and consultative status, revealing 59 nominal NGOs whose observable dependencies conflicted with the independent role their accreditation implied.
- Method: https://www.icij.org/investigations/china-targets/inside-china-targets-the-data-footprints-of-chinas-transnational-repression/
- Impact: The U.N. Human Rights Office said it reviewed the March 2024 evidence and raised the situation with the Chinese government, but it did not include the episode in the secretary-general's reprisals report. That is a documented official disposition, not a demonstrated post-publication reform. ICIJ story
- Dependency: (a) — decisive inputs are obtainable public records

### Thousands of Immigrants Suffer in U.S. Solitary Confinement (2019) — conflict-repression
- URL: https://www.icij.org/investigations/solitary-voices/thousands-of-immigrants-suffer-in-us-solitary-confinement/; https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-investigation/; https://media.icij.org/uploads/2019/05/icij-solitary-voices-final-dataset-for-publication.csv
- Partner/awards: ICIJ led and published the analysis with lead reporter Spencer Woodman and data journalist Karrie Kehoe; Maryam Saleh and Hannah Rappleye co-reported.
- Found: A FOIA ledger converted isolated incidents into a measurable system of prolonged and vulnerability-driven segregation
- Types: vulnerability-as-isolation trigger; civil-detention punishment; policy-practice divergence
- Evidence: ICE segregation logs — FOIA primary dataset:; ICE directives and inspection/audit reports — public policy records:; Detainee, family, attorney, and clinician interviews — firsthand/context evidence:; Whistleblower records — internal corroboration:
- Systems: ICE segregation logs; Solitary Voices CSV; ICE directives; DHS inspection and audit reports
- Signature: Placement-to-policy conformance audit: FOIA incident logs were joined to ICE directives and the U.N. 15-day and vulnerability standards on keys detainee, facility, placement reason, start/end date, mental-health indicator, and duration, revealing prolonged and vulnerability-driven segregation at scale.
- Method: [inferred]
- Impact: U.S. senators Kamala Harris, Cory Booker, Richard Durbin, and Brian Schatz introduced legislation sharply limiting ICE solitary confinement and cited the ICIJ findings; senators also sought DHS records and explanations. Introduction is an official response, not evidence that the proposed limits became law. ICIJ…
- Dependency: (a) — decisive inputs are obtainable public records

### Interpol's Red Notices Used by Some to Pursue Political Dissenters, Opponents (2011) — conflict-repression
- URL: https://www.icij.org/investigations/interpols-red-flag/interpols-red-notices-used-some-pursue-political-dissenters-opponents/; https://www.icij.org/investigations/interpols-red-flag/about-project-4/
- Partner/awards: This was an ICIJ project reported and written by Libby Lewis of CNN Radio, whose broadcast was the lead outlet product.
- Found: A complete public-notice snapshot and rights-risk overlay showed authoritarian requests entering a trusted global police channel
- Types: asylum-warrant contradiction; authoritarian-trust laundering; unreviewed-alert propagation
- Evidence: Public Red Notice census — open platform records:; Freedom House and Transparency International indices — open contextual datasets:; Interpol constitution, guidance, and statistics — institutional records:; Court, asylum, police, and public records across countries — case verification:; Dozens of interviews — firsthand and expert evidence:
- Systems: Interpol public Red Notice roster; Freedom House indices; Transparency International indices; court and asylum records
- Signature: Notice-to-regime-risk overlay: the public Red Notice roster was joined to political-freedom, corruption, refugee-status, and court-outcome records on keys requesting country, subject identity, alleged conduct, notice date, and protection status, revealing clusters of politically suspect requests and direct asylum-notice contradictions.
- Method: [inferred]
- Impact: Interpol issued a same-day formal rebuttal disputing ICIJ's interpretation and emphasizing internal review safeguards. That is an official response, not a remedial policy change. ICIJ publication of Interpol's response
- Dependency: (a) — decisive inputs are obtainable public records

### Assad's Archive of Death (2025) — conflict-repression
- URL: https://www.icij.org/investigations/damascus-dossier/syria-assad-mass-murder-photos-evidence/; https://www.icij.org/investigations/damascus-dossier/inside-the-damascus-dossier-from-leaked-images-to-verified-data/; https://www.icij.org/investigations/damascus-dossier/about-damascus-dossier-syria-investigation/
- Partner/awards: The Damascus Dossier was jointly led by ICIJ and German broadcaster NDR; NDR obtained and shared the central cache.
- Found: File-tree reconstruction, statistical image review, and identity linkage turned a leaked photo archive into evidence of industrialized prison killing
- Types: bureaucratized-atrocity archive; victim-identity recovery; official-cause-of-death falsification
- Evidence: Leaked intelligence/prison archive — non-public primary corpus:; Image metadata and file hierarchy — digital forensic evidence:; Random sample and coded questionnaire — statistical/visual evidence:; Arabic OCR and entity resolution — computational evidence:; Forensic/pathology experts, survivors, families, and rights groups — independent corroboration:
- Systems: Damascus Dossier archive; file metadata; Arabic OCR; arrest and death records
- Signature: Forensic-folder census and stratified image coding: file-tree metadata and Arabic labels were joined to deduplicated image coding, arrest/death records, and identity evidence on keys detainee number, date, security branch, folder path, and body features, revealing the victim count, industrial tempo, recurring injury/starvation pattern, and recoverable names.
- Method: https://www.icij.org/investigations/damascus-dossier/inside-the-damascus-dossier-from-leaked-images-to-verified-data/
- Impact: ICIJ/NDR shared name lists with the U.N. International, Impartial and Independent Mechanism for Syria and Syrian documentation groups; German and Swedish prosecutors said the material could support existing investigations. This is an official evidence handoff and investigative use, not yet a reported judgment…
- Dependency: (c) — decisive relation requires non-public source material

### UN Paid $11M to Assad-Linked Syrian Security Firm, Documents Show (2025) — conflict-repression
- URL: https://www.icij.org/investigations/damascus-dossier/assad-intelligence-security-united-nations-aid/; https://www.icij.org/investigations/damascus-dossier/inside-the-damascus-dossier-from-leaked-images-to-verified-data/
- Partner/awards: The story was written by ICIJ's David Kenner inside the ICIJ/NDR-led Damascus Dossier.
- Found: Secret ownership records joined to an open procurement ledger traced humanitarian spending to an intelligence-controlled contractor
- Types: aid-to-repressor flow; concealed-state ownership; warning-to-renewal failure
- Evidence: Internal Shorouk and intelligence records — leaked primary evidence:; U.N. procurement data — open transaction records:; U.N. and human-rights reporting — public risk records:; Company website, local observation, and response letters — open/firsthand checks:
- Systems: U.N. procurement data; Shorouk internal records; human-rights and sanctions records
- Signature: Beneficial-controller-to-payments join: secret ownership/profit-share records were joined to U.N. procurement transactions and public abuse warnings on keys vendor name and aliases, controller, agency, contract date, and amount, revealing at least $11 million in aid-system payments to an intelligence-controlled security firm and continued awards after warning.
- Method: [inferred]
- Impact: At publication, U.N. agencies defended or explained their procurement controls and the constraints of operating in Syria; the article reported that Shorouk remained a contractor in 2025. No post-publication suspension or investigation was identified on the seeded project pages. ICIJ story
- Dependency: (b) — public verification follows a private discovery anchor

### The Merchant of Death (2002) — conflict-repression
- URL: https://www.icij.org/investigations/makingkilling/merchant-death/; https://www.icij.org/investigations/makingkilling/
- Partner/awards: This was an original ICIJ/Center for Public Integrity investigation, reported by André Verlöy as part of the nearly two-year Making a Killing project.
- Found: Corporate and aircraft continuity exposed Victor Bout's supposedly separate cargo companies as one embargo-evasion network
- Types: asset-identity laundering; embargo-evasion network; dual-use legitimacy shield
- Evidence: Corporate registries — open primary records:; Aircraft registrations and flight records — aviation records:; U.N. embargo-panel reports — public international records:; Belgian and African intelligence records — non-public government material:; Former associates, officials, and investigators — interview evidence:
- Systems: corporate registries; aircraft registries; U.N. embargo-panel reports; sanctions and flight records
- Signature: Airframe-company continuity graph: corporate filings and aircraft histories were joined to U.N. flight and embargo records on keys tail number, operator, director, address, telephone, route, and transfer date, revealing that renamed and reflagged companies remained one controlled transport network serving embargoed clients.
- Method: [inferred]
- Impact: No publication-triggered official action is stated on the project page. Belgium's February 2002 arrest warrant for Bout was part of the contemporaneous record and preceded the article, so it is context rather than impact. ICIJ story
- Dependency: (b) — public verification follows a private discovery anchor

### Privatizing Combat, the New World Order (2002) — conflict-repression
- URL: https://www.icij.org/investigations/makingkilling/privatizing-combat-new-world-order/; https://www.icij.org/investigations/makingkilling/about-project/
- Partner/awards: This was an original ICIJ/Center for Public Integrity project, with lead reporting by Laura Peterson and Samiya Edwards.
- Found: A contractor census and procurement join quantified the private military industry operating across 110 countries
- Types: war-by-proxy procurement; revolving-door war commerce; oversight fragmentation
- Evidence: Constructed company census — open-source research dataset:; Defense procurement records and contracts — public administrative data:; GAO audits and oversight reports — public evaluative records:; State Department files and FOIA — licensing/oversight evidence:; Corporate, lobbying, personnel, and interview records — network evidence:
- Systems: defense procurement records; GAO audits; State Department export-license files; corporate and lobbying records
- Signature: Contractor-roster-to-conflict map: a constructed private-military-company roster was joined to procurement awards, corporate/personnel records, export approvals, and deployment locations on keys company, parent, officer, contract number, service, country, and date, revealing the scale and geographic reach of privatized military functions.
- Method: [inferred]
- Impact: No story-specific official response is identified on the seeded project page. The GAO findings and State Department actions cited in the investigation predated publication and are evidence, not impact. ICIJ story
- Dependency: (a) — decisive inputs are obtainable public records

### The Truth Left Behind: Inside the Kidnapping and Murder of Daniel Pearl (2011; ICIJ edition 2012) — conflict-repression
- URL: https://www.icij.org/investigations/daniel-pearl/truth-left-behind-inside-kidnapping-and-murder-daniel-pearl/; https://www.icij.org/investigations/daniel-pearl/ebook-truth-left-behind/; https://cloudfront-files-1.publicintegrity.org/documents/pdfs/The_Pearl_Project.pdf
- Partner/awards: This was not originally an ICIJ-coordinated reporting project.
- Found: A role-and-event graph separated the men convicted of kidnapping from the larger, mostly unprosecuted murder conspiracy
- Types: conviction-perpetrator divergence; unprosecuted-conspiracy graph; investigative-silo failure
- Evidence: Pakistani court and police records — legal primary records:; Hundreds of interviews in five countries — original reporting:; FBI reports, State Department cables, and Pearl's notes/emails — government and victim records:; Murder video and biometric comparison — visual forensic evidence:; FOIA litigation and releases — public-record acquisition:; Palantir and i2 relationship analysis — analytical tooling:
- Systems: Pakistani court and police records; FBI and State Department files; FOIA releases; Palantir; i2
- Signature: Role-event graph reconciliation: the official trial narrative was joined to interview, police, FBI, communication, and video evidence on keys person/alias, militant group, phone/contact, location, act, and time, revealing a 27-person conspiracy in which the convicted kidnappers and alleged killer occupied different roles.
- Method: https://cloudfront-files-1.publicintegrity.org/documents/pdfs/The_Pearl_Project.pdf
- Impact: No official action attributable to ICIJ's 2012 edition is stated. The FOIA lawsuit did compel document production during reporting; that is an acquisition outcome, not a criminal-justice remedy. Pearl Project report
- Dependency: (c) — decisive relation requires non-public source material

## Aid, development finance, and public contracting (report-15)

### How the World Bank Broke Its Promise to Protect the Poor (2015) — aid-development-finance
- URL: https://www.icij.org/investigations/world-bank/how-world-bank-broke-its-promise-protect-poor/
- Partner/awards: This was an ICIJ-coordinated investigation led by ICIJ and HuffPost, with The GroundTruth Project, The Investigative Fund, The Guardian, and more than 20 other news organizations; ICIJ says more than 50 journalists reported in 21 countries (project credits). It won the Online News Association's Al Neuharth Innovation in Investigative Journalism Award (ICIJ award notice).
- Found: A reconstructed project ledger showed that Bank-financed development displaced about 3.4 million people while routinely failing to document what happened to them
- Types: safeguard-performance-gap; administrative-undercount
- Evidence: Project-approval and safeguard documents — public administrative records; Resettlement Action Plans and completion reports — public implementation records; Internal Bank review — publicly reported accountability record; Field interviews and observation — original reporting
- Systems: World Bank project database; Resettlement Action Plans; Implementation Completion and Results Reports
- Signature: Fragmented-ledger denominator reconstruction: World Bank project approvals were joined to Resettlement Action Plans and completion reports on project identifier; affected-person fields were normalized and summed, and the result was compared with follow-through documentation on the same projects, revealing both the 3.35-million-person scale and the institution's outcome-record gap (ICIJ data methodology).
- Method: https://www.icij.org/investigations/world-bank/thousands-world-bank-documents-unique-new-database/
- Impact: After the investigation and continued accountability pressure, the Bank adopted a 2020 package that added independent monitoring of action plans, a dispute-resolution service, and a longer complaint window; the source documents the reform but does not isolate ICIJ's causal share (ICIJ impact report)
- Dependency: (a) — decisive inputs are obtainable public records

### New Evidence Ties World Bank to Human Rights Abuses in Ethiopia (2015) — aid-development-finance
- URL: https://www.icij.org/investigations/world-bank/new-evidence-ties-world-bank-human-rights-abuses-ethiopia/
- Partner/awards: This was part of the ICIJ-coordinated Evicted and Abandoned collaboration led by ICIJ and HuffPost; it was not a separately branded member-outlet story (project credits). The project-level Online News Association award applies to the collaboration (ICIJ award notice).
- Found: Former officials linked Bank-supported local budgets to a coercive resettlement campaign affecting hundreds of thousands
- Types: fungible-aid-diversion; safeguard-performance-gap
- Evidence: Former-government-official interviews — insider discovery; World Bank approvals and program documents — public administrative records; Inspection Panel complaint, report, and expert material — lender-accountability files; Human Rights Watch documentation — independently gathered human-rights evidence; Refugee interviews — victim testimony
- Systems: World Bank project database; World Bank Inspection Panel files; Human Rights Watch reports
- Signature: Budget-fungibility triangulation: World Bank program disbursements were compared with villagization place and timing on the key of Gambella/program period, then joined to independent former-official descriptions of budget orders and the Inspection Panel's operational-link finding, revealing a plausible channel from nominal basic-services aid to coercive resettlement (ICIJ Ethiopia story).
- Method: https://www.icij.org/investigations/world-bank/new-evidence-ties-world-bank-human-rights-abuses-ethiopia/
- Impact: No story-specific official remedy is identified on the story page. At project level, later World Bank accountability reforms increased monitoring and complaint options, but the available source does not attribute a distinct Ethiopia remedy to this article (ICIJ impact report)
- Dependency: (b) — public verification follows a private discovery anchor

### Bush's AIDS Initiative: Too Little Choice, Too Much Ideology (2006) — aid-development-finance
- URL: https://www.icij.org/investigations/divine-intervention/bushs-aids-initiative-too-little-choice-too-much-ideology/
- Partner/awards: This was an ICIJ-led investigation under its then-parent, the Center for Public Integrity, involving about a dozen reporters in eight countries; the project page does not name a member outlet as lead (ICIJ methodology).
- Found: Grant records and field reporting showed PEPFAR conditions shifting prevention money toward abstinence programs and away from locally measured risk
- Types: conditionality-misalignment; administrative-undercount
- Evidence: PEPFAR and USAID grant records — FOIA and litigation-produced administrative data; Country Operational Plans — agency planning records; Authorizing law and grant conditions — public legal records; Expert review and government oversight material — program-integrity records; More than 100 interviews and eight-country field reporting — original reporting
- Systems: PEPFAR grant records; USAID award data; Country Operational Plans; GAO reports
- Signature: Conditionality-to-risk mismatch: PEPFAR/USAID activity amounts were grouped by country, year, and prevention mode, then compared with statutory conditions and local epidemiological or target-risk evidence on the same country-year, revealing allocation growth driven by abstinence requirements rather than the observed exposure profile (ICIJ main story).
- Method: https://www.icij.org/investigations/divine-intervention/behind-scenes-questions-lawsuits-and-eventually-some-answers/
- Impact: The public-record lawsuits produced records on a court schedule and ended in a settlement, a concrete transparency impact; the cited pages do not establish that the reporting itself changed PEPFAR's substantive policy (ICIJ methodology)
- Dependency: (a) — decisive inputs are obtainable public records

### U.S.-Trained Forces Linked to Human Rights Abuses (2001; ICIJ archive page dated 2012) — aid-development-finance
- URL: https://www.icij.org/investigations/us-aid-latin-america/us-trained-forces-linked-human-rights-abuses/
- Partner/awards: This was a Center for Public Integrity/ICIJ-led story from the original U.S.
- Found: Training records connected U.S.-supported Mexican special-forces personnel to a torture-and-killing case
- Types: security-assistance-harm-chain
- Evidence: U.S. training and aid records — public or agency-supplied security-assistance records; Mexican criminal and military case records — legal records; Jalisco Human Rights Commission files — accountability records and victim testimony; Pentagon and official responses — on-record confirmation
- Systems: U.S. security-assistance training records; Mexican criminal and military case records; Jalisco Human Rights Commission files
- Signature: Trainer-to-abuse unit join: U.S. training records were joined to Mexican case defendants on person and GAFE unit, revealing that six personnel implicated in the Ocotán abuses had received U.S. training (ICIJ GAFE story).
- Method: https://www.icij.org/investigations/us-aid-latin-america/us-trained-forces-linked-human-rights-abuses/
- Impact: The story describes prosecutions and U.S. screening concerns, but these are evidence in the reported chronology rather than a documented response caused by publication; no post-publication official impact is claimed (ICIJ GAFE story)
- Dependency: (a) — decisive inputs are obtainable public records

### U.S. Shrugged Off Corruption, Abuse in Service of Drug War (2001; ICIJ archive page dated 2012) — aid-development-finance
- URL: https://www.icij.org/investigations/us-aid-latin-america/us-shrugged-corruption-abuse-service-drug-war/
- Partner/awards: This was a Center for Public Integrity/ICIJ-led investigation by Ángel Páez, not a member-outlet banner story.
- Found: Insider evidence about CIA payments was re-anchored to public warnings showing aid continued after U.S. officials knew of Vladimiro Montesinos's abuses
- Types: trusted-intermediary-betrayal; security-assistance-harm-chain
- Evidence: Confidential U.S. and Peruvian sources — insider discovery; Peruvian prosecutorial and court material — public legal records; “Vladivideo” recordings — publicly exposed primary audiovisual evidence; State Department reports, Senate record, and aid budgets — public government records
- Systems: Peruvian court and prosecutorial records; Vladivideos; State Department reports; U.S. Senate records; aid budgets
- Signature: Ally-record contradiction timeline: insider claims about CIA support were re-anchored to public court evidence, videotapes, State Department warnings, Senate scrutiny, and annual aid amounts on actor and date, revealing that support continued and was proposed to increase after serious warning signals were in the public U.S. record (ICIJ Montesinos story).
- Method: [inferred]
- Impact: Montesinos's flight, capture, and prosecution arose from the pre-publication collapse of the Fujimori government and public videotapes; the story does not claim those events as its impact (ICIJ Montesinos story)
- Dependency: (b) — public verification follows a private discovery anchor

### U.S. Hands Out Vast Sums of Money While Ignoring Human Rights Records (2007) — aid-development-finance
- URL: https://www.icij.org/investigations/collateraldamage/us-hands-out-vast-sums-money-while-ignoring-human-rights-records/
- Partner/awards: This was an ICIJ-led Center for Public Integrity project, reported by a ten-journalist team; the project credits do not name a member outlet as lead (ICIJ project credits).
- Found: A cross-program audit found lightly scrutinized counterterrorism vehicles bypassing restrictions and human-rights vetting
- Types: program-vehicle-arbitrage; security-assistance-harm-chain
- Evidence: Coalition Support Fund reimbursements — FOIA-obtained procurement/payment records; Training and security-assistance records — government program records; GAO vetting review — public oversight record; State Department human-rights reporting and official interviews — public accountability evidence
- Systems: Coalition Support Fund reimbursements; IMET; FMF; Counterterrorism Fellowship; Section 1206; GAO reports
- Signature: Parallel-program bypass diff: countries and units restricted under IMET/FMF were compared with recipients in Counterterrorism Fellowship and Section 1206 records on country, unit, and year, then joined to GAO vetting results, revealing that alternate authorities restored support without equivalent documented screening (ICIJ aid story).
- Method: https://www.icij.org/investigations/collateraldamage/about-project-collateral-damage/
- Impact: The article records contemporary congressional concern and GAO scrutiny, but no post-publication official reform is identified; none is inferred (ICIJ aid story)
- Dependency: (a) — decisive inputs are obtainable public records

### Ethiopia Reaps U.S. Aid by Enlisting in War on Terror and Hiring Influential Lobbyists (2007) — aid-development-finance
- URL: https://www.icij.org/investigations/collateraldamage/ethiopia-reaps-us-aid-enlisting-war-terror-and-hiring-influential/
- Partner/awards: This was an ICIJ-led Center for Public Integrity story within Collateral Damage, not a separately led member-outlet publication (ICIJ project credits).
- Found: Lobbying disclosures and aid records exposed a sequence of rising military support, rights warnings, and pressure against congressional restrictions
- Types: influence-aid-sequence; security-assistance-harm-chain
- Evidence: FMF, IMET, counterterrorism, and equipment records — public security-assistance data; Foreign-agent lobbying disclosures — mandatory Justice Department records; Congressional bill history — public legislative record; State Department human-rights reports and interviews — public risk evidence and original reporting
- Systems: FMF; IMET; counterterrorism assistance records; FARA filings; congressional bill history; State Department reports
- Signature: Lobby-contact-to-policy-to-aid sequence: foreign-agent contact filings were joined to bill milestones and annual aid decisions on client country and date, revealing an intensive lobbying period concurrent with the restriction bill's stall and continued security assistance (ICIJ Ethiopia-aid story).
- Method: [inferred]
- Impact: The pending restriction bill's failure and the Humvee pause are events inside the reported chronology, not documented post-publication effects; the page identifies no official response to the story (ICIJ Ethiopia-aid story)
- Dependency: (a) — decisive inputs are obtainable public records

### U.S. Contractors Reap the Windfalls of Post-War Reconstruction (2003; ICIJ archive page dated 2012) — aid-development-finance
- URL: https://www.icij.org/investigations/windfalls-war/us-contractors-reap-windfalls-post-war-reconstruction-0/; https://publicintegrity.org/national-security/winning-contractors/
- Partner/awards: This was Center for Public Integrity-led, with ICIJ as part of the Center, rather than a member-outlet story published under the banner. The project won the George Polk Award for Internet Reporting (Long Island University winners archive).
- Found: Contract, ownership, political-giving, lobbying, and employment records exposed a concentrated reconstruction market entwined with government
- Types: conflict-procurement-concentration
- Evidence: Contract actions — FOIA and GSA procurement data; Corporate ownership and subsidiary history — company and business-reference records; Campaign contributions — Federal Election Commission data; Lobbying filings — Lobbying Disclosure Act records; Personnel biographies and agency histories — public biographical records and interviews
- Systems: GSA contract-action data; FEC campaign-finance records; lobbying disclosures; corporate registries; personnel records
- Signature: Contractor-influence multiplex join: award records were resolved through time-aware parent/subsidiary ownership, then joined to FEC contributions, lobbying filings, and government-employment histories on company, person, and date, revealing procurement concentration inside a dense political and revolving-door network (ICIJ methodology).
- Method: https://www.icij.org/investigations/windfalls-war/methodology-windfalls-war/
- Impact: The article reports that congressional investigators and the GAO were already examining reconstruction awards; it does not establish those probes as effects of publication. The documented external recognition is the project-level Polk Award (original Center story; LIU winners archive)
- Dependency: (a) — decisive inputs are obtainable public records

### Baghdad Bonanza (2007 update; ICIJ archive page dated 2012) — aid-development-finance
- URL: https://www.icij.org/investigations/windfalls-war/baghdad-bonanza/
- Partner/awards: This was a Center for Public Integrity update to Windfalls of War, later migrated to ICIJ, not a member-outlet contribution. The Polk Award belongs to the broader Windfalls project (LIU winners archive).
- Found: Re-ranking procurement data made an anonymous foreign-contractor bucket larger than most named vendors
- Types: opaque-vendor-bucket; administrative-undercount
- Evidence: Federal Procurement Data System records — public procurement data; FOIA-generated contractor list — agency response; Contract documents and agency/company interviews — primary documents and on-record reporting; Corporate identity research — public business records
- Systems: FPDS; USAspending; FOIA contractor lists; contract documents; corporate registries
- Signature: Procurement-identity-gap ranking: FPDS transactions were grouped by time-resolved vendor parent and place of performance, then compared with a FOIA top-contractor list on award and value; ranking the unresolved “foreign contractor” bucket alongside named firms revealed that missing identity represented $20.4 billion rather than trivial data noise (ICIJ Baghdad story).
- Method: https://www.icij.org/investigations/windfalls-war/methodology-windfalls-war/
- Impact: The page does not identify a post-publication government response to the unknown-vendor finding; none is inferred (ICIJ Baghdad story)
- Dependency: (a) — decisive inputs are obtainable public records

### Contractors Write the Rules (2004; ICIJ archive page dated 2012) — aid-development-finance
- URL: https://www.icij.org/investigations/windfalls-war/contractors-write-rules/; https://publicintegrity.org/national-security/contractors-write-the-rules/
- Partner/awards: This was a Center for Public Integrity-led Windfalls of War story, originally published June 30, 2004 and later migrated to ICIJ, not a member-outlet story (original Center story). The broader project won the Polk Award for Internet Reporting (LIU winners archive).
- Found: A version diff showed a contractor-authored Army manual omitted an existing limit on outsourced tactical intelligence while the same firm held military contracts
- Types: rule-writer-beneficiary-conflict
- Evidence: Field Manual 100-21 — public policy text; December 2000 Army memorandum — internal policy directive reported from a primary document; MPRI contract records — public/FOIA-obtained procurement documents; Taguba report — official military investigation; Army and contractor interviews — on-record original reporting
- Systems: U.S. Army FM 34-21; Army policy memorandum; procurement records; official investigation records
- Signature: Rule-writer-beneficiary omission diff: the December 2000 policy memorandum was compared with the contractor-authored January 2003 manual on the required tactical-intelligence restriction, revealing its omission; the drafting entity was then joined to active contract awards on company and period, showing that the rule writer participated in the market affected by the missing limit (ICIJ rules story).
- Method: https://www.icij.org/investigations/windfalls-war/contractors-write-rules/
- Impact: The story does not identify a post-publication Army revision or procurement action attributable to the article; none is claimed (ICIJ rules story)
- Dependency: (a) — decisive inputs are obtainable public records

## Corporate lobbying and regulatory capture (report-17)

### Exposed: How billions of cigarettes end up on black markets (2000) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/big-tobacco-smuggling/exposed-how-billions-cigarettes-end-black-markets/
- Partner/awards: ICIJ/Center for Public Integrity original, by Maud Beelman, Duncan Campbell, María Teresa Ronderos, Erik J. No separate lead partner or story-specific award is identified on the seeded ICIJ pages.
- Found: BAT’s own planning records treated contraband as a managed market channel
- Types: coded-channel-governance; illicit-channel-as-market-strategy
- Evidence: Litigation-released internal corporate records — public archive; Court and enforcement records — public legal records; Corporate financial disclosures — public filings; Insider/expert interviews — reporter-obtained
- Systems: UCSF Industry Documents Library; BAT planning records; court and enforcement records
- Signature: corporate-dialect-to-operations join: coded terms in internal correspondence joined to route, volume, price, advertising, and launch fields on country + brand + date + channel revealed that “DNP/GT/transit” was not loose slang but a centrally managed contraband sales ledger.
- Method: https://www.icij.org/investigations/big-tobacco-smuggling/exposed-how-billions-cigarettes-end-black-markets/
- Impact: ICIJ says this series helped prompt lawsuits and government inquiries and led to promises of a global crackdown on illicit tobacco trade; it does not attribute a discrete action solely to this story. ICIJ project impact statement
- Dependency: (a) — decisive inputs are obtainable public records

### Global reach of tobacco company’s involvement in cigarette smuggling exposed in company papers (2000) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/big-tobacco-smuggling/global-reach-tobacco-companys-involvement-cigarette-smuggling-exposed-company-papers/
- Partner/awards: By ICIJ, produced through the Center for Public Integrity. No member outlet or story-specific award is credited on the seeded pages.
- Found: Asian “general trade” plans reconstructed a multinational route portfolio
- Types: route-portfolio-governance; intermediary-deniability
- Evidence: Internal company plans and correspondence — litigation-released public archive; Distributor relationship records — internal corporate records; Anti-corruption prosecution and appeal — public court/enforcement record; Company response — solicited on record
- Systems: UCSF Industry Documents Library; BAT general-trade plans; customs and court records
- Signature: channel-portfolio route reconstruction: country plans and distributor assignments joined to border status, import bans, sales volumes, and court events on market + route hub + year + channel label revealed a managed Asian distribution system that shifted volume between legal, duty-free, and GT paths.
- Method: [inferred]
- Impact: The project-level impact statement says the 2000–2001 findings helped prompt lawsuits and government inquiries; no Asia-story-only causal claim is made. ICIJ project impact statement
- Dependency: (a) — decisive inputs are obtainable public records

### Made To Be Smuggled (2008) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/tobacco-underground/made-be-smuggled/
- Partner/awards: ICIJ-led ten-country story by Roman Shleynov, Stefan Candea, Duncan Campbell, and Vlad Lavrov.
- Found: A factory network’s capacity, absent legal market, and customs footprint identified a contraband-only brand
- Types: capacity-without-lawful-market; contraband-brand-by-design
- Evidence: Corporate, ownership, and trademark records — public registries; Customs seizure records — official administrative data; Trade records — licensed/commercial and unofficial datasets; Retail-market data and field checks — commercial estimate plus constructed observation; Undercover transaction test — reporter-generated non-public encounter, then published; Supply-chain trade records — official/commercial
- Systems: PIERS; Business Analytica; customs seizure records; trademark registries; corporate registries
- Signature: capacity-market-export gap triangulation: factory capacity and company export claims joined to retail share, recorded exports, brand seizures, and input shipments on manufacturer + brand + year + destination revealed industrial output with no plausible lawful end market.
- Method: https://www.icij.org/investigations/tobacco-underground/made-be-smuggled/
- Impact: No post-publication action is attributed to this story on the seeded ICIJ pages. The article notes that OLAF had already launched Operation Baltic before publication, so that is context, not claimed impact. ICIJ story
- Dependency: (a) — decisive inputs are obtainable public records

### Ukraine’s “Lost” Cigarettes Flood Europe (2009) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/tobacco-underground/ukraines-lost-cigarettes-flood-europe/
- Partner/awards: ICIJ project story by Vlad Lavrov, then a *Kyiv Post* staff writer and OCCRP regional editor.
- Found: A national supply balance exposed 30 billion cigarettes missing into illicit trade
- Types: supply-demand-black-hole; price-gradient-smuggling
- Evidence: National production, import, consumption, and export statistics — government/industry administrative data; Company-level output and responsibility reports — corporate disclosure; Customs and criminal-case data — official enforcement records; Online market observation — open-web constructed evidence; Government, company, and expert interviews — on-record reporting
- Systems: SOVAT and Ukrainian production statistics; customs records; seizure records; company reports
- Signature: residual supply-balance reconstruction: national production plus imports compared with domestic consumption plus legal exports on country + product + year produced a 30-billion-unit residual; that residual joined to border price differences, seizure brands, and route cases revealed the likely illicit outflow and its value.
- Method: https://www.icij.org/investigations/tobacco-underground/ukraines-lost-cigarettes-flood-europe/
- Impact: No post-publication impact specific to this story is stated on the seeded ICIJ pages. Tobacco Underground project page
- Dependency: (a) — decisive inputs are obtainable public records

### The tobacco lobby goes global (2012) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/smoke-screen/tobacco-lobby-goes-global/
- Partner/awards: ICIJ global overview by Ricardo Sandoval Palos, Traver Riggins, Solomon Adebayo, Duncan Campbell, Andreas Harsono, Murali Krishnan, and Claudio Paolillo. No story-specific partner or award is listed on the supplied pages.
- Found: The same policy-delay toolkit appeared across emerging markets
- Types: campaign-portability; policy-delay-by-multipronged-pressure
- Evidence: Cross-country lobbying and donation disclosures — public records and company lists; Litigation-released internal tobacco documents — public archive; Legislation, treaty commitments, committee rosters, and official websites — public government records; Court and enforcement files — public legal records; Local government, advocate, expert, and company interviews — reporter-obtained
- Systems: UCSF Industry Documents Library; lobbying and donation disclosures; WHO FCTC; legislation and court records
- Signature: cross-jurisdiction tactic-outcome matrix: lobbying inputs (donation, official access, rule drafting, lawsuit, research sponsorship, investment, payoff) joined to regulatory outputs (delay, exemption, dilution, reversal) on country + policy + actor + date revealed the same corporate campaign architecture adapted to local power structures.
- Method: https://www.icij.org/investigations/smoke-screen/about-project-smoke-screen/
- Impact: No story-specific post-publication action is identified on the supplied Smoke Screen pages. Smoke Screen project page
- Dependency: (a) — decisive inputs are obtainable public records

### Moscow’s open, revolving door for big tobacco (2012) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/smoke-screen/moscows-open-revolving-door-big-tobacco/
- Partner/awards: Member-outlet-led reporting under the ICIJ banner. No story-specific award is listed.
- Found: Industry personnel occupied official seats and helped write weaker tobacco rules
- Types: regulator-seat-capture; revolving-door-rulemaking
- Evidence: Official working-group rosters and draft legislation — public government/association records; WHO convention and Russian law — public legal texts; Litigation-released company records — public archive; State-contract registry and corporate ownership disclosures — public records; Donation and research-sponsorship records — company/institute disclosures; Interviews and company acknowledgments — on record
- Systems: official working-group rosters; Russian Duma bill records; WHO FCTC; UCSF Industry Documents Library; state-contract registry
- Signature: official-roster conflict join + benchmark rule diff: government working-group/delegation rosters joined to corporate employment, association leadership, sponsorship, family ownership, and contract records on person + organization + role + date, then the resulting rule text compared with the WHO benchmark, revealed industry personnel inside the regulator and the precise concessions their preferred bill preserved.
- Method: https://www.icij.org/investigations/smoke-screen/moscows-open-revolving-door-big-tobacco/
- Impact: No specific post-publication action is claimed on the supplied project/story pages. The story reports contemporaneous pushback from Kazakhstan, Belarus, and Tajikistan, which preceded publication and is therefore context rather than impact. ICIJ story
- Dependency: (a) — decisive inputs are obtainable public records

### How Uber won access to world leaders, deceived investigators and exploited violence against its drivers (2022) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/uber-files/uber-global-rise-lobbying-violence-technology/
- Partner/awards: ICIJ newsroom story by Sydney P.
- Found: Launch-first illegality was converted into a global lobbying lever
- Types: permission-after-entry; undisclosed-access-machine; enforcement-obstruction-playbook
- Evidence: Leaked internal company cache — whistleblower material; Structured calendar and communications data — derived from leak; Public lobbying and meeting disclosures — open government records; Public laws, raids, investigations, speeches, and policy outcomes — official records/open web; SEC filings and archived Uber websites — public records/web archives; Company and subject responses — solicited statements
- Systems: Uber Files cache; EU Transparency Register; U.S. Senate lobbying disclosures; French lobbying registry; official calendars; SEC filings; web archives
- Signature: calendar-register-outcome diff: leaked calendars and messages joined to public meeting/lobby registers and official policy/enforcement timelines on official + company + date + jurisdiction revealed more than 100 contacts, 12 undisclosed EU meetings, and a repeated launch-first sequence in which enforcement pressure was followed by high-level lobbying and regulatory concessions.
- Method: https://www.icij.org/investigations/uber-files/how-we-unearthed-ubers-controversial-playbook-from-a-cache-of-employee-communications/
- Impact: France and Belgium opened parliamentary inquiries and the European Parliament held a responsive session; France’s final inquiry criticized an opaque, privileged Uber–Macron relationship and said its creation responded to the Uber Files. ICIJ impact: inquiries | ICIJ impact: final French report
- Dependency: (b) — public verification follows a private discovery anchor

### Uber forged deals with top Putin allies in failed bid to break into Russian market (2022) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/uber-files/uber-deals-russia-putin-allies/
- Partner/awards: ICIJ story by Nicole Sadek and Sydney P. No story-specific award is listed.
- Found: Stock and investment terms were used to purchase political intermediation
- Types: political-investor-conduit; equity-for-access
- Evidence: Leaked strategy memos, emails, briefing books, and contract discussions — non-public whistleblower cache; Public investment announcements and corporate events — open company records/news releases; Sanctions status — public government lists; Legislative and political records — public records; Taxi-union letter and subject responses — documentary/on-record
- Systems: Uber Files cache; corporate investment announcements; U.S. sanctions list; EU sanctions list; Russian Duma records
- Signature: investment-access-intent join: internal investment terms and strategy memos joined to public ownership, sanctions, political-office, meeting, and legislation records on investor + beneficial owner + date + policy target revealed that ostensibly financial deals carried an undisclosed political-access function.
- Method: [inferred]
- Impact: No Russia-specific official inquiry is identified on the supplied pages. Project-wide, the Uber Files triggered protests and inquiries across Europe, including French and Belgian parliamentary processes. ICIJ impact summary
- Dependency: (c) — decisive relation requires non-public source material

### How Merck turned its wonder drug into a blockbuster — and priced out cancer patients worldwide (2026) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/cancer-calculus/merck-keytruda-cancer-drug-price/
- Partner/awards: ICIJ-led overview by Sydney P. The overview draws partner data and field reporting into one project synthesis; no award is listed as of the compilation date.
- Found: Patent families, regulatory shortcuts, pricing secrecy, and influence spending reinforced one monopoly
- Types: patent-thicket-price-defense; regulatory-shortcut-monetization; opaque-price-segmentation; prescriber-influence-spend
- Evidence: Patent applications and family data — open patent records; Public-record requests — request-gated public records; Price and earnings data — mixed public/partner-collected; Regulatory and payment data — public government records; Commercial/exclusive health data — closed but non-decisive enhancement; Company presentations, patent-board records, lawsuits, corporate/regulatory files, and hundreds of interviews — mixed primary/constructed reporting
- Systems: Google Patents; Espacenet; FDA records; CMS Open Payments; ILOSTAT; GÖG price data; IQVIA/Serif/HCCI
- Signature: patent-family exclusivity ladder: 180 verified U.S. applications expanded through family links, assignees, legal status, filing dates, and expiry horizons on invention family + jurisdiction + assignee + priority date, then compared with original-patent expiry, standardized prices, competitor entry, and regulatory/payment timelines, revealed a layered exclusivity strategy whose commercial effect persisted beyond the core patent.
- Method: https://www.icij.org/investigations/cancer-calculus/patents-prices-and-court-files-how-icij-used-data-to-investigate-an-industry-that-thrives-on-secrecy/
- Impact: U.S. Sen. Maggie Hassan cited Cancer Calculus in a letter demanding answers from Merck about secondary patents, product hopping, biosimilar delay, and pricing; she asked for a response by July 20, 2026. ICIJ impact story
- Dependency: (a) — decisive inputs are obtainable public records

### “They deny the medication that is keeping you alive”: Patients wage grueling legal battles for lifesaving cancer drug (2026) — lobbying-regulatory-capture
- URL: https://www.icij.org/investigations/cancer-calculus/cancer-patients-legal-battle-keytruda-lifesaving-drug/
- Partner/awards: ICIJ’s Brenda Medina and Micah Reddy co-bylined with Jody García of Plaza Pública. No award is listed as of the compilation date.
- Found: Court orders became the de facto Keytruda coverage pathway
- Types: litigation-gated-access; adjudication-as-coverage-protocol
- Evidence: Constitutional/amparo and ordinary court rulings — public judicial records; Brazilian judicial-request data — public court statistics/records; U.S. state insurance-regulator complaints — public-record requests; Individual pleadings, appeals, decisions, and insurer correspondence — litigation/subject records; Patient, family, physician, lawyer, regulator, insurer, and expert interviews — constructed reporting
- Systems: Guatemala court system; Mexico court system; Chile court system; Brazil court system; U.S. state insurance-regulator complaints
- Signature: coverage-denial-to-adjudication cohort join: court and regulator decisions joined on drug + payer + patient/case + filing date + outcome and deduplicated across countries revealed that initial denials were overwhelmingly reversed, turning judicial action into a measurable de facto coverage protocol.
- Method: https://www.icij.org/investigations/cancer-calculus/patents-prices-and-court-files-how-icij-used-data-to-investigate-an-industry-that-thrives-on-secrecy/
- Impact: No court-access-story-specific policy response is identified on the supplied ICIJ pages as of 2026-07-29. The project’s documented U.S. Senate inquiry focused primarily on patent and pricing strategy, not this court cohort. ICIJ impact story
- Dependency: (a) — decisive inputs are obtainable public records
