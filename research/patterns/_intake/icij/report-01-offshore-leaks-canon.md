# ICIJ Evidence Ontology — Cluster 01: Offshore-Finance Leak Canon

Reviewed: 2026-07-29. Method: live verification against ICIJ project hubs, reporting, data notes, “about” pages, methodology articles, and impact follow-ups. The coded unit is the **ICIJ-coordinated project**; stories by member outlets count only when ICIJ identifies them as output of that project. A project entry captures the leak and collaboration machinery. Thread-level sub-entries are used where one project contains several independently generalizable analytic methods—here, Offshore Leaks, Panama Papers, Paradise Papers, FinCEN Files, Pandora Papers and Cyprus Confidential; smaller or methodologically tighter projects remain single entries. “Impact” means a documented official consequence, not proof that publication alone caused it.

## Scope corrections

- The candidate list is substantially correct. The verified sequence is **Offshore Leaks (2013), China Leaks (2014), LuxLeaks (2014), Swiss Leaks (2015), Panama Papers (2016), Bahamas Leaks (2016), Paradise Papers (2017), West Africa Leaks (2018), Mauritius Leaks (2019), Luanda Leaks (2020), FinCEN Files (2020), Pandora Papers (2021), Cyprus Confidential (2023), and Swazi Secrets (2024)**. ICIJ itself described China Leaks and West Africa Leaks as named offshore investigations in its pre-Pandora canon, and both have project pages; Swazi Secrets is a later ICIJ-coordinated financial-intelligence leak project ([ICIJ canon reference](https://www.icij.org/investigations/fincen-files/icij-nominated-for-nobel-peace-prize-for-combating-dark-money-flows/), [West Africa Leaks hub](https://www.icij.org/investigations/west-africa-leaks/), [Swazi Secrets hub](https://www.icij.org/investigations/swazi-secrets/)).
- **China Leaks is retained as a project, not collapsed into Offshore Leaks.** It reused the original provider corpus but had a distinct project banner, country-specific verification problem, reporting team, publication cycle, and public data release ([China Leaks methodology](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/)).
- **Bahamas Leaks is retained.** Its stories sit in ICIJ’s broad “Secrecy for Sale” archive, but ICIJ called the 1.3-million-file release “Bahamas Leaks” and published the records as a distinct addition to the Offshore Leaks Database ([announcement](https://www.icij.org/inside-icij/2016/09/icij-publishes-leaked-bahamas-info-offshore-database/)).
- **Coin Laundry is excluded from the leak canon.** It is adjacent and highly transferable, but its core dataset was constructed from wallet addresses supplied by victims, police, court and sanctions records, complaints, test transactions, and public blockchains rather than a privileged offshore-finance leak ([ICIJ’s methodology](https://www.icij.org/investigations/coin-laundry/about-coin-laundry-investigation-cryptocurrency/)).
- **Thematic archives and adjacent corporate leaks are not separate canon entries.** Hidden Treasures is explicitly a collection of art/antiquities stories from Panama Papers, Pandora Papers, FinCEN Files and other work, so counting it would duplicate project output; Uber Files is an ICIJ/Guardian leak project with an offshore-tax thread, but its primary unit is a ride-hailing company’s lobbying, labor and regulatory campaign rather than the offshore-finance system ([Hidden Treasures hub](https://www.icij.org/investigations/hidden-treasures/), [Uber Files about page](https://www.icij.org/investigations/uber-files/about-uber-files-investigation/)).

---

### PROJECT: Offshore Leaks (2013) — the first provider-scale leak mapped the people, intermediaries, companies and trusts inside a global secrecy industry

- **URL**: [Project hub](https://www.icij.org/investigations/offshore/); [global overview](https://www.icij.org/investigations/offshore/secret-files-expose-offshores-global-impact/)
- **Partner/awards** (lead outlets; prizes): ICIJ coordinated 86 journalists in 46 countries for the initial publication; later phases involved more than 110 reporters in 60 countries. The project won the IRE Multiplatform/Large prize, Scripps Howard’s William Brewster Styles Award, and the Overseas Press Club’s best-investigative-reporting award ([team description](https://www.icij.org/inside-icij/2013/04/offshore-expose-bigger-wikileaks-cablegate/), [awards](https://www.icij.org/inside-icij/2014/04/tribute-paid-journalisms-silent-heroes-award-win/)).
- **What they found**:
  - A 260 GB cache contained about 2.5 million files, including more than 2 million emails, four databases, and half a million documents; it described more than 122,000 offshore companies or trusts, nearly 12,000 intermediaries, and about 130,000 people or agents ([ICIJ methodology](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/)).
  - The records reached across more than 170 countries and territories and exposed beneficial owners, directors, shareholders, trustees, settlors, protectors and powers of attorney hidden behind nominee structures ([overview](https://www.icij.org/investigations/offshore/secret-files-expose-offshores-global-impact/)).
  - The population included political families, sanctioned or criminally implicated actors, banks and professional firms, but ICIJ cautioned that appearing offshore is not by itself evidence of illegality ([hub](https://www.icij.org/investigations/offshore/)).
- **Finding type(s)**: **hidden-beneficial-ownership** (the economic controller is obscured by legal owners, nominees or layered vehicles); **intermediary-enablement** (a bank, law firm, accountant or formation agent supplies the machinery); **offshore-risk-concentration** (high-risk actors recur inside the same provider ecosystem).
- **Evidence & sources**:
  - Leaked corporate-provider databases and email/document stores from Portcullis TrustNet and Commonwealth Trust Limited, obtained on a hard drive by ICIJ director Gerard Ryle through his prior Firepower reporting [privileged] ([methodology](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/)).
  - OCR text and deduplicated, normalized tables constructed from scans, PDFs, spreadsheets, web files and emails using Nuix and ICIJ’s Interdata search system [constructed] ([methodology](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/)).
  - Corporate registries, court files, asset declarations, sanctions records, prior reporting and subject interviews used by country partners to identify and verify names [open-public/request-gated] ([overview](https://www.icij.org/investigations/offshore/secret-files-expose-offshores-global-impact/)).
- **Access tier**: mixed — privileged provider leak; constructed search/entity layer; open-public and request-gated corroboration.
- **Detection signature**: **provider records joined to external identity/risk records on normalized person, address, company and officer keys revealed hidden controllers and risky networks** — deduplicate the corpus, extract role-bearing edges (`person → role → entity → intermediary → jurisdiction`), then resolve those nodes against public officials, sanctions, courts and registries.
- **Corroboration structure**: leak-derived entity/role edge → underlying email, incorporation form or passport copy → public registry, official disclosure or court/sanctions record → local reporter and subject contact. Duplicate appearances across leak files established consistency, not independent corroboration.
- **Methodology notes**: ICIJ explicitly described the four-database extraction, OCR, duplicate rate (about 40%), Nuix network analysis and Interdata distribution system in [“How ICIJ’s Project Team Analyzed the Offshore Files”](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/). The formal graph-and-risk-list expression above is **[inferred]** from those stated operations.
- **Impact**: ICIJ documented tax investigations, resignations and policy responses across multiple countries; the EU tax commissioner called the project a major trigger for Europe’s renewed offshore crackdown ([impact roundup](https://www.icij.org/inside-icij/2013/04/release-offshore-records-draws-worldwide-response/)).
- **Generalization**: any leaked or obtained service-provider corpus can be turned into a role graph. A generic detector normalizes names, dates, addresses and identifiers; preserves role semantics; expands two hops from each high-risk seed; and requires a second record system before promoting identity-sensitive claims.

### SUB-ENTRY: The Aliyev family–contractor network (2013) — hidden BVI ownership linked Azerbaijan’s ruling family to a construction magnate receiving billions in state contracts

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)
- **Partner/awards** (lead outlets; prizes): ICIJ with regional partners in the Offshore Leaks collaboration; covered by the project-level awards ([project awards](https://www.icij.org/inside-icij/2014/04/tribute-paid-journalisms-silent-heroes-award-win/)).
- **What they found**:
  - President Ilham Aliyev’s daughters were listed as shareholders in at least four British Virgin Islands companies; the companies were created in 2008 when they were 19 and 23 ([ICIJ investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)).
  - Hassan Gozal appeared as a director in the same offshore structure while his family’s businesses had won roughly $4.5 billion in Azerbaijani construction contracts ([ICIJ investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)).
  - Incorporation agents and nominees obscured the family’s connection in ordinary public-facing records ([ICIJ investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)).
- **Finding type(s)**: hidden-beneficial-ownership; **state-linked-benefit** (a concealed private network overlaps with recipients of state-granted contracts or assets); **public-private-conflict** (a hidden economic interest creates a conflict with public power).
- **Evidence & sources**:
  - Leaked BVI incorporation and shareholder/director records [privileged].
  - Azerbaijani contract and corporate records identifying Gozal-controlled businesses and awarded work [open-public/request-gated].
  - Public biographical records fixing ages and family relationships; earlier property reporting on Aliyev family assets [open-public] ([all sources described in the investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)).
- **Access tier**: mixed — privileged ownership evidence plus open-public/request-gated contract and identity records.
- **Detection signature**: **leaked shareholder/director records joined to public-contract recipients on shared director and family keys revealed a concealed ruling-family–contractor overlap**; the load-bearing move is a two-hop traversal `official family → offshore entity → contractor principal`, followed by aggregation of awards to the contractor’s operating companies.
- **Corroboration structure**: offshore forms fixed the ownership edge; public biographical records resolved the daughters; local corporate and procurement records established the contractor and award value; subjects were offered comment ([ICIJ investigation](https://www.icij.org/investigations/offshore/offshore-companies-provide-link-between-corporate-mogul-and-azerbaijans-president/)).
- **Methodology notes**: no separate thread methodology page. **[Inferred]** from the article’s named document types and sequence; the parent project’s extraction method is documented [here](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/).
- **Impact**: no distinct official sanction tied to this thread is documented in ICIJ’s Offshore Leaks impact roundup; the broader project triggered international investigations and disclosure reform efforts ([impact roundup](https://www.icij.org/inside-icij/2013/04/release-offshore-records-draws-worldwide-response/)).
- **Generalization**: run this against procurement, concessions, privatizations, licenses and subsidies: expand from every official and close relative into hidden-company roles, then join directors, addresses and controllers to state-benefit recipients and sum benefits by network.

### SUB-ENTRY: Bayartsogt Sangajav’s undeclared company and Swiss account (2013) — a leaked BVI file exposed an omitted $1 million account held by Mongolia’s deputy speaker

- **URL**: [ICIJ disclosure story](https://www.icij.org/investigations/offshore/disclosure-secret-offshore-documents-may-force-top-mongolian-lawmaker-resign/)
- **Partner/awards** (lead outlets; prizes): ICIJ and Mongolian partners under Offshore Leaks; project-level IRE, Scripps Howard and OPC honors ([awards](https://www.icij.org/inside-icij/2014/04/tribute-paid-journalisms-silent-heroes-award-win/)).
- **What they found**:
  - Deputy parliamentary speaker Bayartsogt Sangajav admitted that the BVI company Legend Plus Capital Ltd. and a Swiss bank account containing more than $1 million were his after ICIJ confronted him with the records ([ICIJ story](https://www.icij.org/investigations/offshore/disclosure-secret-offshore-documents-may-force-top-mongolian-lawmaker-resign/)).
  - The interest had not appeared in his required asset declarations, creating a direct document-to-disclosure contradiction ([ICIJ story](https://www.icij.org/investigations/offshore/disclosure-secret-offshore-documents-may-force-top-mongolian-lawmaker-resign/)).
- **Finding type(s)**: hidden-beneficial-ownership; **disclosure-gap** (an externally evidenced asset or role is absent from a legally required declaration); public-private-conflict.
- **Evidence & sources**:
  - Leaked BVI company records and bank-account information [privileged].
  - Mongolian official asset declarations and disclosure law [open-public/request-gated].
  - On-record admission by Sangajav after document confrontation [constructed interview evidence] ([ICIJ story](https://www.icij.org/investigations/offshore/disclosure-secret-offshore-documents-may-force-top-mongolian-lawmaker-resign/)).
- **Access tier**: mixed — privileged leak; open-public/request-gated official disclosures; constructed interview confirmation.
- **Detection signature**: **leaked asset/company ownership compared to the same official’s filed declaration on person, asset class and reporting period revealed an omitted interest**; after exact-name and alias resolution, the analytic move is a field-level anti-join: `evidenced interests MINUS declared interests`.
- **Corroboration structure**: leaked ownership/account record → official declaration absence → disclosure-law check → direct admission. The admission confirms identity but does not independently prove every balance or legal conclusion.
- **Methodology notes**: no standalone thread method; **[inferred]** from the article’s confrontation and disclosure comparison. Parent corpus handling is documented in [ICIJ’s project methodology](https://www.icij.org/investigations/offshore/how-icijs-project-team-analyzed-offshore-files/).
- **Impact**: Sangajav said he would consider resigning and later stepped down as parliamentary deputy speaker after the disclosure ([ICIJ Mongolia follow-up](https://www.icij.org/investigations/panama-papers/panama-papers-helps-break-new-reporting-ground-mongolia/)).
- **Generalization**: compare any mandatory disclosure—assets, gifts, outside employment, related parties, campaign finance, conflicts registers—with registries, property deeds, leaks and litigation exhibits. Preserve filing dates so later amendments do not erase the original omission.

---

### PROJECT: China Leaks (2014) — offshore-provider records penetrated the wealth networks of China’s political and commercial elite despite transliteration and censorship barriers

- **URL**: [Main investigation](https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/); [methodology](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/)
- **Partner/awards** (lead outlets; prizes): ICIJ led a separate China-focused phase with 15 ICIJ members and partners across Asia, Europe and North America; it reused the Offshore Leaks corpus but had its own reporting and release cycle ([methodology](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/)). Project-specific prize not identified in the reviewed ICIJ record.
- **What they found**:
  - Nearly 22,000 offshore clients from mainland China and Hong Kong appeared in the files, including close relatives of at least five current or former Politburo Standing Committee members and at least 15 of China’s richest citizens ([main investigation](https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/)).
  - PwC helped incorporate more than 400 offshore entities and UBS more than 1,000; three state-owned oil companies were linked to dozens of BVI entities ([main investigation](https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/)).
  - TrustNet’s China-related company formations roughly tripled from about 1,500 in 2003 to about 4,800 in 2007 ([main investigation](https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/)).
- **Finding type(s)**: **elite-cohort-penetration** (measure how much of a defined political or wealth cohort appears in a hidden system); intermediary-enablement; hidden-beneficial-ownership.
- **Evidence & sources**:
  - The TrustNet/Commonwealth provider corpus from Offshore Leaks, including incorporation records, passports, addresses and role records [privileged].
  - Constructed aliases for Chinese names in Mandarin, Cantonese and romanization systems; passport numbers, birth dates and addresses used as disambiguators [constructed] ([methodology](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/)).
  - Public leadership rosters, rich lists, state-enterprise records, company registries and reporting archives [open-public].
  - Local-source and subject verification under conditions of state censorship [constructed interviews/reporting] ([main investigation](https://www.icij.org/investigations/offshore/leaked-records-reveal-offshore-holdings-of-chinas-elite/)).
- **Access tier**: mixed — privileged leak; constructed multilingual identity layer; open-public lists and registries.
- **Detection signature**: **a multilingual alias pipeline joined leak identities to fixed elite cohorts on passport, birth-date, address, kinship and romanized-name keys revealed both named connections and cohort prevalence**; aggregate provider/intermediary counts by year and client origin to expose system growth.
- **Corroboration structure**: fuzzy name candidate → hard identifier or family/address match → underlying provider document → public family/office/company record → regional reporter review and subject contact. ICIJ explicitly treated name-only matches as insufficient ([methodology](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/)).
- **Methodology notes**: ICIJ’s [“How We Did Offshore Leaks China”](https://www.icij.org/inside-icij/2014/01/how-we-did-offshore-leaks-china/) describes the name-variation problem, cross-border team and verification process. The formal cohort-penetration detector is **[inferred]** from those operations and the published counts.
- **Impact**: Chinese web access to ICIJ and partner stories was blocked, and Transparency International later cited China Leaks as a factor in China’s worsening corruption-perception ranking ([ICIJ impact coverage](https://www.icij.org/inside-icij/2014/01/highlights-chinaleaks/), [later impact roundup](https://www.icij.org/inside-icij/2013/04/release-offshore-records-draws-worldwide-response/)).
- **Generalization**: the exact pattern applies whenever the target population uses multiple scripts, patronymics or naming orders. Generate aliases but score candidates with stable identifiers and relationship context; publish cohort rates only from a fixed, reproducible roster.

---

### PROJECT: LuxLeaks (2014) — leaked advance tax rulings showed Luxembourg approving industrial-scale profit shifting for hundreds of multinationals

- **URL**: [Project hub](https://www.icij.org/investigations/luxembourg-leaks/); [about page](https://www.icij.org/investigations/luxembourg-leaks/about-project-luxembourg-leaks/)
- **Partner/awards** (lead outlets; prizes): ICIJ coordinated more than 80 journalists in 26 countries; major partners included The Guardian, Le Monde, Süddeutsche Zeitung and NDR. The project drew on records first obtained by French journalist Édouard Perrin and later disclosed by whistleblowers Antoine Deltour and Raphaël Halet ([about page](https://www.icij.org/investigations/luxembourg-leaks/about-project-luxembourg-leaks/), [whistleblower history](https://www.icij.org/investigations/luxembourg-leaks/european-court-reverses-course-to-rule-in-favor-of-luxleaks-whistleblower/)).
- **What they found**:
  - About 28,000 leaked pages exposed confidential Luxembourg tax rulings for roughly 340 companies; PwC had obtained at least 548 rulings between 2002 and 2010 ([about page](https://www.icij.org/investigations/luxembourg-leaks/about-project-luxembourg-leaks/), [hub](https://www.icij.org/investigations/luxembourg-leaks/)).
  - Structures routed hundreds of billions of dollars through Luxembourg, often using hybrid loans and intra-group interest to drive effective tax rates below 1% ([overview](https://www.icij.org/investigations/luxembourg-leaks/leaked-documents-expose-global-companies-secret-tax-deals-luxembourg/)).
  - FedEx’s structure produced an effective rate near 0.25%, while Coach reported €36.7 million of profit and about €250,000 of Luxembourg tax in a cited period ([overview](https://www.icij.org/investigations/luxembourg-leaks/leaked-documents-expose-global-companies-secret-tax-deals-luxembourg/)).
  - One address, 5 rue Guillaume Kroll, housed more than 1,600 companies, illustrating the difference between legal domicile and operating substance ([hub](https://www.icij.org/investigations/luxembourg-leaks/)).
- **Finding type(s)**: **policy-arbitrage** (exploit mismatched rules across jurisdictions or legal categories); **corporate-profit-shifting** (move taxable profit away from the activity that generated it); **letterbox-substance-gap** (legal presence exists without commensurate employees, operations or assets).
- **Evidence & sources**:
  - Leaked PwC advance-tax-ruling applications, diagrams and approval letters [privileged].
  - Luxembourg company accounts and registry filings used to calculate effective rates and locate entities [open-public/request-gated] ([ICIJ reading guide](https://www.icij.org/investigations/luxembourg-leaks/your-head-spinning-5-tips-understand-lux-leaks-files/)).
  - Corporate annual reports, subsidiary lists and public tax disclosures [open-public].
  - Physical visits to registered addresses and interviews with tax experts, companies and authorities [constructed] ([letterbox reporting](https://www.icij.org/investigations/luxembourg-leaks/day-fiscal-paradise-chasing-letterbox-leads-luxembourg/)).
- **Access tier**: mixed — privileged rulings; open-public/fee-gated accounts and filings; constructed rate calculations and field verification.
- **Detection signature**: **leaked transaction diagrams joined to group accounts and jurisdictional tax rules on entity, payment type and fiscal year revealed where operating profit was converted into intra-group interest and where tax fell below the rate implied by business activity**; a second join of registered address to occupant count exposed letterbox concentration.
- **Corroboration structure**: ruling diagram/approval → statutory treatment in each jurisdiction → entity accounts and annual reports → recomputed effective tax rate → address inspection and subject/expert comment. The approval proves official authorization, not necessarily illegality.
- **Methodology notes**: ICIJ’s [five-step reading guide](https://www.icij.org/investigations/luxembourg-leaks/your-head-spinning-5-tips-understand-lux-leaks-files/) explicitly instructs readers to trace the transaction sequence, test business reality, obtain annual accounts and calculate effective rates; the address fieldwork is documented [separately](https://www.icij.org/investigations/luxembourg-leaks/day-fiscal-paradise-chasing-letterbox-leads-luxembourg/). The generalized join notation is **[inferred]**.
- **Impact**: LuxLeaks helped drive EU state-aid investigations and tax-transparency reforms; in 2023 the European Court of Human Rights ruled that Halet’s whistleblower conviction violated free-expression rights ([ten-year review](https://www.icij.org/investigations/luxembourg-leaks/ten-years-on-lux-leaks-remains-a-byword-for-corporate-tax-chicanery/), [ECHR follow-up](https://www.icij.org/investigations/luxembourg-leaks/european-court-reverses-course-to-rule-in-favor-of-luxleaks-whistleblower/)).
- **Generalization**: reconstruct any cross-border scheme as an ordered payment graph, attach the rule and rate that each edge triggers, then compare profit location to employees, sales, assets and physical presence. The detector flags high profit with near-zero substance, circular payments and hybrid instruments classified differently by two authorities.

---

### PROJECT: Swiss Leaks (2015) — internal HSBC files showed how a global bank serviced tax evaders and clients linked to arms, diamonds, corruption and sanctions

- **URL**: [Project hub](https://www.icij.org/investigations/swiss-leaks/); [about page](https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/)
- **Partner/awards** (lead outlets; prizes): Le Monde obtained the data from French tax authorities and shared it with ICIJ; ICIJ coordinated about 140 journalists in 45 countries, including BBC, The Guardian and other partners ([about page](https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/)). Project-specific prize not identified in the reviewed ICIJ pages.
- **What they found**:
  - More than 60,000 leaked files described over 100,000 HSBC Private Bank clients and accounts associated with more than $100 billion ([about page](https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/)).
  - The data included client/account records largely spanning 1988–2007, maximum balances around 2006–2007, and banker notes from 2005 that recorded client instructions and staff knowledge ([data notes](https://www.icij.org/investigations/swiss-leaks/100000-clients-100-billion-swiss-leaks-data/)).
  - ICIJ identified almost 2,000 diamond-industry clients and clients linked in public records to dictators, arms dealing, conflict and sanctions ([overview](https://www.icij.org/investigations/swiss-leaks/banking-giant-hsbc-sheltered-murky-cash-linked-dictators-and-arms-dealers/), [diamond thread](https://www.icij.org/investigations/swiss-leaks/diamond-dealers-deep-trouble-bank-documents-shine-light-secret-ways/)).
  - Banker notes showed accounts shifted into offshore companies as the European Savings Directive approached, preserving secrecy or avoiding the rule’s original individual-account scope ([loophole investigation](https://www.icij.org/investigations/swiss-leaks/new-law-new-loophole-new-business-giant-global-bank-hsbc/)).
- **Finding type(s)**: **high-risk-client-servicing** (an institution maintains relationships with clients bearing serious public risk indicators); **compliance-knowledge-gap** (internal notes show knowledge or warnings inconsistent with external policy or action); policy-arbitrage.
- **Evidence & sources**:
  - HSBC client and account tables, maximum-balance data and internal banker notes originally extracted by Hervé Falciani and held by French tax authorities [privileged], obtained for the project through Le Monde ([about page](https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/)).
  - UN sanctions material, court cases, government investigations and public criminal or business records [open-public].
  - Corporate registries for client-owned shells and interviews with clients, bank representatives and enforcement experts [open-public/constructed].
- **Access tier**: mixed — privileged bank leak; open-public sanctions, court and company sources; constructed client-risk classification.
- **Detection signature**: **bank-client records joined to sanctions, court, criminal, industry and political-risk lists on resolved identity keys revealed the risky-client cohort; banker notes compared to bank policy and later account activity revealed what the institution knew and did**. A date join around the EU directive exposed entity conversions clustered near the rule change.
- **Corroboration structure**: leaked account row → banker note or account document → public risk record and registry identity → client/bank comment. Balance fields were maxima over a period, not current holdings, and ICIJ warned that inclusion did not itself prove wrongdoing ([data notes](https://www.icij.org/investigations/swiss-leaks/100000-clients-100-billion-swiss-leaks-data/)).
- **Methodology notes**: [ICIJ’s about page](https://www.icij.org/investigations/swiss-leaks/about-project-swiss-leaks/) describes custom tools and collaborative analysis; the [data page](https://www.icij.org/investigations/swiss-leaks/100000-clients-100-billion-swiss-leaks-data/) defines the three core record types and date caveats. The risk-list and policy-diff formulation is **[inferred]** from the reported joins.
- **Impact**: Geneva prosecutors raided HSBC’s office and opened a money-laundering investigation shortly after publication; multiple tax authorities pursued account holders ([ICIJ raid report](https://www.icij.org/inside-icij/2015/02/hsbcs-geneva-office-raided-swiss-open-investigation/)).
- **Generalization**: for any customer ledger, resolve clients against multiple risk lists, then compare internal narrative notes and monitoring events with policy thresholds and service continuation. The strongest finding is not “risky name present” but “documented knowledge + subsequent enabling action.”

---

### PROJECT: Panama Papers (2016) — 11.5 million Mossack Fonseca files exposed a worldwide shell-company factory and the political, criminal and commercial networks it served

- **URL**: [Project hub](https://www.icij.org/investigations/panama-papers/); [about page](https://www.icij.org/investigations/panama-papers/about-the-investigation/)
- **Partner/awards** (lead outlets; prizes): Süddeutsche Zeitung received the leak and shared it with ICIJ; ICIJ coordinated more than 370 journalists from over 100 media organizations in nearly 80 countries, including The Guardian, BBC, Le Monde and OCCRP. The project won the 2017 Pulitzer Prize for Explanatory Reporting ([about](https://www.icij.org/investigations/panama-papers/about-the-investigation/), [Pulitzer announcement](https://www.icij.org/investigations/panama-papers/panama-papers-wins-pulitzer-prize/)).
- **What they found**:
  - The 2.6 TB leak held 11.5 million files concerning more than 214,000 offshore entities and people in more than 200 countries and territories ([about page](https://www.icij.org/investigations/panama-papers/about-the-investigation/)).
  - The files linked 140 politicians in more than 50 countries, including 12 current or former national leaders, to offshore structures ([FAQ](https://www.icij.org/investigations/panama-papers/faqs/)).
  - Mossack Fonseca worked through more than 14,000 banks, law firms, incorporators and other intermediaries to form and administer entities ([key figures](https://www.icij.org/investigations/panama-papers/explore-panama-papers-key-figures/)).
- **Finding type(s)**: hidden-beneficial-ownership; intermediary-enablement; offshore-risk-concentration; **networked-asset-concealment** (a multi-entity chain obscures the owner, asset or transaction path).
- **Evidence & sources**:
  - Leaked Mossack Fonseca emails, databases, incorporation files, images and office documents obtained by Süddeutsche Zeitung [privileged].
  - OCR and structured extraction using Extract/Blacklight, Talend ETL, Neo4j and Linkurious; reporter annotations and shared search [constructed] ([technology methodology](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/)).
  - Company and property registries, court cases, sanctions lists, asset declarations, securities filings, interviews and field reporting [open-public/request-gated/constructed].
- **Access tier**: mixed — privileged leak; constructed document and graph systems; open-public/request-gated corroboration.
- **Detection signature**: **heterogeneous leak files normalized into an entity-role graph and joined to public officials, sanctions, registries, disclosures and dockets revealed hidden ownership and transaction paths**; two-degree graph expansion exposed intermediaries or shells shared across otherwise separate targets.
- **Corroboration structure**: graph candidate → source document and email context → stable-identifier or multi-attribute identity confirmation → public record establishing office, asset, legal status or transaction consequence → local partner verification and subject contact.
- **Methodology notes**: ICIJ explicitly describes SQL extraction, Talend transformation, Neo4j loading, Linkurious exploration and two-degree graph queries in [“The Data and Tech Team”](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/); the OCR/search stack’s evolution is documented [here](https://www.icij.org/investigations/panama-papers/a-decade-of-digital-evolution-to-help-reporting-revolutions-at-icij/). The generic join formulation is **[inferred]**.
- **Impact**: Iceland’s prime minister resigned, governments opened scores of investigations, and tax authorities had recovered at least $1.36 billion by 2021 ([resignation](https://www.icij.org/investigations/panama-papers/20160405-iceland-pm-resignation/), [revenue recovery](https://www.icij.org/investigations/panama-papers/panama-papers-revenue-recovery-reaches-1-36-billion-as-investigations-continue/)).
- **Generalization**: treat a document leak as a graph-construction problem but force every promising path back to source documents. Generic screening expands from high-risk seeds through owners, nominees, intermediaries, addresses and bank accounts; scores repeated enablers; and tests each path against external records.

### SUB-ENTRY: The Putin-circle cello network (2016) — transactions around Sergei Roldugin traced at least $2 billion through shells tied to the Russian president’s inner circle

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-putin-russia-offshore-network/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung, OCCRP, Novaya Gazeta and other Panama Papers partners; covered by the project’s 2017 Pulitzer ([award](https://www.icij.org/investigations/panama-papers/panama-papers-wins-pulitzer-prize/)).
- **What they found**:
  - Cellist Sergei Roldugin, a close friend of Vladimir Putin, appeared behind companies in a network that moved at least $2 billion through banks and offshore entities ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-putin-russia-offshore-network/)).
  - Network companies obtained unusual loans and trades and secretly acquired influence in a Russian truckmaker and television-advertising business ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-putin-russia-offshore-network/)).
  - The documents supported a frontman hypothesis: Roldugin’s declared public profile was difficult to reconcile with control of the transaction scale, while counterparties and associates led back toward Putin’s circle ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-putin-russia-offshore-network/)).
- **Finding type(s)**: networked-asset-concealment; **proxy-ownership** (a nominal controller’s economic profile or relationships indicate assets may be held for another); **value-transfer-anomaly** (loans, trades or rights transfer value on implausibly favorable terms).
- **Evidence & sources**:
  - Mossack Fonseca ownership records, emails, contracts, loan agreements and transaction documents [privileged].
  - Russian and foreign corporate records, bank and securities information, and public biographies/relationship reporting [open-public/request-gated].
  - Constructed transaction and relationship graph [constructed] ([project technology](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/)).
- **Access tier**: mixed — privileged transactional documents; constructed graph; public corporate and relationship records.
- **Detection signature**: **leaked contracts and payments joined into a dated transaction graph on company, account, signatory and counterparty keys revealed a $2 billion flow network; the nominal owner’s public wealth/profile compared with controlled value and proximity to political power surfaced the proxy hypothesis**.
- **Corroboration structure**: each graph edge traced to a contract, email or payment record; registries confirmed legal roles; public records established relationships and operating assets; reporting distinguishes documented Roldugin control from the **[inferred]** proposition that he held value for Putin.
- **Methodology notes**: graph technology is quoted at project level in [ICIJ’s data-team account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/). The proxy-capacity test is **[inferred]** from the story’s comparison of Roldugin’s profile, relationships and the network’s value.
- **Impact**: the U.S. later sanctioned Roldugin as a custodian of Putin’s offshore wealth; the sanction post-dated and cited the broader public record around his offshore role ([ICIJ sanctions follow-up](https://www.icij.org/investigations/russia-archive/putin-allies-mordashov-and-roldugin-targeted-in-latest-round-of-us-sanctions/)).
- **Generalization**: rank nominees by `controlled value / plausible independent capacity`, then examine favorable transactions, common counterparties and personal ties to a likely principal. This yields a lead, not automatic proof of the true beneficial owner.

### SUB-ENTRY: Iceland’s prime minister and Wintris (2016) — a $1 transfer and omitted offshore interest exposed a conflict with failed-bank creditors

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung, Reykjavík Media and other Panama Papers partners; part of the Pulitzer-winning project ([award](https://www.icij.org/investigations/panama-papers/panama-papers-wins-pulitzer-prize/)).
- **What they found**:
  - Sigmundur Davíð Gunnlaugsson and his wife bought Wintris Inc. in 2007; he still co-owned it when he entered parliament in 2009 ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/)).
  - He transferred his half to his wife for $1 on Dec. 31, 2009, the last day before a new disclosure rule took effect ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/)).
  - Court records showed Wintris held roughly $4 million in claims, with a pre-crash face value near $8 million, against Iceland’s failed banks while Gunnlaugsson’s government influenced creditor policy ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/)).
- **Finding type(s)**: disclosure-gap; public-private-conflict; **deadline-adjacent-restructuring** (ownership or transaction terms change immediately before a rule, sanction or filing deadline).
- **Evidence & sources**:
  - Mossack Fonseca incorporation, ownership and transfer records [privileged].
  - Icelandic parliamentary disclosures and the effective date of the disclosure rule [open-public].
  - Failed-bank insolvency claims and court records [open-public/request-gated].
- **Access tier**: mixed — privileged ownership files; public disclosures, law and insolvency records.
- **Detection signature**: **offshore ownership history compared to parliamentary disclosures on person and reporting date revealed the omission; the share-transfer date joined to the new rule’s effective date and insolvency claims joined to government policy revealed timing and conflict**.
- **Corroboration structure**: provider record → official disclosure and law → court-proven creditor position → direct interview/confrontation and expert review ([ICIJ investigation](https://www.icij.org/investigations/panama-papers/20160403-iceland-prime-minister/)).
- **Methodology notes**: no standalone thread methodology; **[inferred]** from the dated-document comparison. Project graph and verification mechanics are described [here](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).
- **Impact**: Gunnlaugsson resigned as prime minister two days after publication amid public protests ([ICIJ follow-up](https://www.icij.org/investigations/panama-papers/20160405-iceland-pm-resignation/)).
- **Generalization**: join every ownership or control change to upcoming disclosure, tax, sanctions, procurement and eligibility deadlines; then test whether economic benefit really changed or only the legal label did.

### SUB-ENTRY: Mossack Fonseca’s sanctions and compliance behavior (2016) — internal files showed continued service to blacklisted clients and controls applied after exposure

- **URL**: [Sanctions investigation](https://www.icij.org/investigations/panama-papers/20160404-sanctioned-blacklisted-offshore-clients/); [provider overview](https://www.icij.org/investigations/panama-papers/20160403-mossack-fonseca-offshore-secrets/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung and the Panama Papers consortium; part of the Pulitzer-winning project ([award](https://www.icij.org/investigations/panama-papers/panama-papers-wins-pulitzer-prize/)).
- **What they found**:
  - At least 33 Mossack Fonseca clients or related companies appeared on U.S. sanctions blacklists ([sanctions investigation](https://www.icij.org/investigations/panama-papers/20160404-sanctioned-blacklisted-offshore-clients/)).
  - Internal files showed the firm continued or attempted to continue work for some clients after sanctions or public accusations, sometimes through intermediaries ([sanctions investigation](https://www.icij.org/investigations/panama-papers/20160404-sanctioned-blacklisted-offshore-clients/)).
  - The firm adopted a comprehensive OFAC-check policy only in July 2015, decades after beginning operations ([sanctions investigation](https://www.icij.org/investigations/panama-papers/20160404-sanctioned-blacklisted-offshore-clients/)).
- **Finding type(s)**: high-risk-client-servicing; compliance-knowledge-gap; **compliance-after-the-fact** (screening or remediation appears only after public, regulatory or transactional warning).
- **Evidence & sources**:
  - Mossack Fonseca client files, compliance emails, invoices and service histories [privileged].
  - U.S. Treasury/OFAC sanctions lists and designation dates [open-public].
  - Public court, regulatory and media records describing alleged misconduct [open-public].
- **Access tier**: mixed — privileged service and communications records; open-public sanctions and legal records.
- **Detection signature**: **provider client master joined to OFAC designations on normalized identity and effective date revealed sanctioned relationships; service invoices, emails and resignation dates compared to designation dates revealed continued service and delayed controls**.
- **Corroboration structure**: sanctions candidate → exact entity/alias confirmation → internal client/service records → timeline review for pre- and post-designation conduct → firm and client comment.
- **Methodology notes**: project data mechanics are documented in [ICIJ’s technology account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/); the event-timeline diff is **[inferred]** from the sanctions story’s dated evidence.
- **Impact**: Mossack Fonseca closed in 2018 after the Panama Papers investigations and prosecutions; the project generated regulatory and criminal inquiries globally ([ICIJ follow-up on the firm’s scramble](https://www.icij.org/investigations/panama-papers/new-panama-papers-leak-reveals-mossack-fonsecas-chaotic-scramble/)).
- **Generalization**: for any regulated intermediary, join customers and beneficial owners to time-versioned sanctions/debarment/discipline lists, then compare designation or warning dates with onboarding, payments, renewals, monitoring and exit. Separate lawful wind-down from new or concealed service.

---

### PROJECT: Bahamas Leaks (2016) — a leaked registry made 175,000 Bahamas entities searchable and exposed a former EU commissioner’s omitted directorship

- **URL**: [Main investigation](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/); [database release](https://www.icij.org/inside-icij/2016/09/icij-publishes-leaked-bahamas-info-offshore-database/)
- **Partner/awards** (lead outlets; prizes): Süddeutsche Zeitung obtained the files and shared them with ICIJ; the release was reported with ICIJ’s offshore partners. No distinct project prize was identified in the reviewed ICIJ pages.
- **What they found**:
  - About 1.3 million files covered more than 175,000 companies, trusts and foundations registered from 1990 to early 2016 and named 539 registered agents ([main investigation](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/)).
  - Mossack Fonseca was the registered agent for 15,915 Bahamas entities, allowing a provider-overlap check against the Panama Papers ([main investigation](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/)).
  - Former EU competition commissioner Neelie Kroes was a director of Mint Holdings Ltd. from 2000 to 2009 but did not disclose it while in office; the company had been intended for a possible $6 billion transaction involving Enron assets ([main investigation](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/)).
  - The official Bahamas registry charged per document and did not permit director-name searching, while the leak enabled bulk person-to-company search ([main investigation](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/)).
- **Finding type(s)**: disclosure-gap; hidden-beneficial-ownership; **registry-opacity-as-control-failure** (search, pricing or field restrictions prevent public reconstruction even when records nominally exist).
- **Evidence & sources**:
  - Leaked Bahamas corporate-registry files obtained by Süddeutsche Zeitung [privileged].
  - Panama Papers/Offshore Leaks entities used for cross-corpus provider and person matching [privileged/constructed].
  - European Commission declarations, official biographies and Enron transaction records [open-public/request-gated].
  - Official Bahamas registry documents purchased selectively for verification [request-gated].
- **Access tier**: mixed — privileged registry leak; constructed cross-leak index; public/fee-gated official records.
- **Detection signature**: **bulk registry roles joined to public-official disclosures on person and tenure revealed omitted directorships; Bahamas entities joined to Panama Papers on agent and entity name revealed provider overlap that neither corpus showed alone**.
- **Corroboration structure**: leaked registry row → company document and matching biographical details → official disclosure anti-join → subject response; cross-corpus hits were checked at document level to avoid same-name collisions.
- **Methodology notes**: ICIJ’s [main story](https://www.icij.org/investigations/offshore/former-eu-official-among-politicians-named-new-leak-offshore-files-bahamas/) explains the registry’s search limitations and the Panama Papers comparison; the formal anti-join is **[inferred]**. The [release note](https://www.icij.org/inside-icij/2016/09/icij-publishes-leaked-bahamas-info-offshore-database/) documents publication to the Offshore Leaks Database.
- **Impact**: the European Commission sought clarification and European lawmakers called for investigation after Kroes acknowledged the omission ([ICIJ reaction roundup](https://www.icij.org/inside-icij/2016/09/bahamas-leaks-prompts-swift-reaction-outrage-europe/)).
- **Generalization**: nominally public but non-searchable registries become analytically useful after bulk acquisition. Build person-role and agent indexes, compare them with declarations, and cross-corpus-match providers to see whether one jurisdiction is a migration destination after scrutiny elsewhere.

---

### PROJECT: Paradise Papers (2017) — 13.4 million files exposed the offshore playbooks, client risks and regulatory arbitrage of elite law firms and corporate-service providers

- **URL**: [Project hub](https://www.icij.org/investigations/paradise-papers/); [about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/)
- **Partner/awards** (lead outlets; prizes): Süddeutsche Zeitung obtained the leak and shared it with ICIJ; 380 journalists from 95 media partners worked in 30 languages, including The Guardian, BBC, The New York Times and Le Monde ([about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/)). Project-specific major prize not identified in the reviewed ICIJ material.
- **What they found**:
  - The 13.4 million files came principally from offshore law firm Appleby, corporate-services provider Asiaciti Trust and company registries in 19 secrecy jurisdictions ([about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/)).
  - The corpus exposed hidden interests and transactions involving more than 120 politicians and world leaders, multinational companies and wealthy individuals ([hub](https://www.icij.org/investigations/paradise-papers/)).
  - Appleby’s own and regulators’ audits repeatedly found missing source-of-funds records, weak monitoring and high proportions of noncompliant files ([Appleby compliance investigation](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/)).
- **Finding type(s)**: intermediary-enablement; compliance-knowledge-gap; corporate-profit-shifting; networked-asset-concealment.
- **Evidence & sources**:
  - Appleby and Asiaciti emails, client files, opinions, compliance reviews and transaction documents, plus leaked registry datasets [privileged].
  - OCR/search, Neo4j and Linkurious entity graph, and reporter annotations [constructed] ([about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/)).
  - Court records, financial disclosures, company and property registries, securities filings, freedom-of-information records and interviews [open-public/request-gated/constructed].
- **Access tier**: mixed — privileged provider/registry files; constructed graph; open-public and request-gated corroboration.
- **Detection signature**: **provider client/transaction files transformed into a role-and-payment graph and joined to public ownership, securities, sanctions, disclosure and litigation records revealed hidden controllers, policy arbitrage and the enablers connecting them**.
- **Corroboration structure**: graph lead → underlying file/email → public registry or filing → external rule, event or asset record → local reporter verification and subject/expert comment. A provider memo stated advice; public filings and subsequent conduct tested whether it was implemented.
- **Methodology notes**: ICIJ’s [about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/) names the leak components, collaboration, external sources and Neo4j/Linkurious workflow. Thread-level joins below are **[inferred]** where no separate method sidebar exists.
- **Impact**: ICIJ recorded arrests, audits, investigations and company/government responses in multiple jurisdictions after publication ([response roundup](https://www.icij.org/investigations/paradise-papers/paradise-papers-response-arrest-investigation-audit/)).
- **Generalization**: combine three layers—provider advice, client implementation and regulator response. Search not only for hidden ownership but for repeated templates, common advisers and internal audits that convert isolated client stories into an institutional-control finding.

### SUB-ENTRY: Appleby’s repeated compliance failures (2017) — internal and regulatory audits showed known defects recurring across offices and years

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung and Paradise Papers partners; no thread-specific prize identified.
- **What they found**:
  - A 2006 Cayman review identified roughly 600 clients as noncompliant with documentation rules ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/)).
  - A BVI review found only one of 45 files met required standards, while a 2014 Bermuda regulator review found source-of-funds information absent in 46% of tested files and nine significant weakness areas ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/)).
  - The leak showed repeated remediation promises alongside continuing deficiencies, allowing a control history rather than a one-time snapshot ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/)).
- **Finding type(s)**: compliance-knowledge-gap; **repeat-control-failure** (the same control weakness recurs after audits, warnings or remediation commitments); intermediary-enablement.
- **Evidence & sources**:
  - Appleby internal audits, compliance reports, client-review spreadsheets and remediation communications [privileged].
  - Bermuda, BVI and Cayman regulatory inspections quoted or reproduced in the leak [privileged official records].
  - Public regulator rules and Appleby policies [open-public].
- **Access tier**: mixed — privileged internal and regulatory reports; open-public standards.
- **Detection signature**: **audit findings compared across office, control category and year revealed persistent defect recurrence; remediation promises joined to subsequent retest results on the same control exposed closure without cure**.
- **Corroboration structure**: internal finding → regulator finding → governing standard → later retest or client-file evidence → firm response. Independent regulators strengthened the internal-document account even though some reports arrived through the same leak.
- **Methodology notes**: the [article](https://www.icij.org/investigations/paradise-papers/appleby-offshore-magic-circle-law-firm-record-of-compliance-failures-icij/) quotes audit dates, samples and failure rates. The longitudinal control matrix is **[inferred]** from those reports.
- **Impact**: regulators in several jurisdictions opened reviews or investigations of Paradise Papers revelations; Appleby disputed ICIJ’s characterization and announced security and compliance responses ([project response roundup](https://www.icij.org/investigations/paradise-papers/paradise-papers-response-arrest-investigation-audit/)).
- **Generalization**: normalize audit observations into `(control, business unit, severity, date, promised fix, retest result)`. Flag the same failure after its promised closure and calculate whether risky clients continued receiving service during the gap.

### SUB-ENTRY: Wilbur Ross, Navigator and Sibur (2017) — a Cayman ownership chain concealed the U.S. commerce secretary’s continuing stake in a firm earning millions from Putin-linked owners

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/paradise-papers/donald-trumps-commerce-secretary-wilbur-ross-and-his-russian-business-ties/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung, The New York Times, NBC News and Paradise Papers partners; no thread-specific prize identified.
- **What they found**:
  - Commerce Secretary Wilbur Ross retained an economic interest in shipping company Navigator Holdings through a chain of Cayman entities after entering office ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/donald-trumps-commerce-secretary-wilbur-ross-and-his-russian-business-ties/)).
  - Navigator had earned about $68 million since 2014 from Sibur, whose owners included Putin’s son-in-law and sanctioned billionaire Gennady Timchenko ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/donald-trumps-commerce-secretary-wilbur-ross-and-his-russian-business-ties/)).
  - Ross’s public disclosures did not make the full customer and ownership relationship readily visible ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/donald-trumps-commerce-secretary-wilbur-ross-and-his-russian-business-ties/)).
- **Finding type(s)**: public-private-conflict; disclosure-gap; **hidden-counterparty-exposure** (a disclosed or partly disclosed investment has a material customer, supplier or owner relationship invisible at the reporting layer).
- **Evidence & sources**:
  - Appleby files mapping Ross’s Cayman holding chain [privileged].
  - Navigator SEC filings identifying revenue and major customers [open-public].
  - Ross’s federal financial disclosures and confirmation-hearing materials [open-public].
  - Sibur ownership records and OFAC sanctions data [open-public].
- **Access tier**: mixed — privileged ownership chain; open-public securities, disclosure, ownership and sanctions records.
- **Detection signature**: **leaked fund ownership traversed to the operating company, then SEC customer-revenue disclosures joined to public counterparty ownership and sanctions records revealed the politically exposed business relationship concealed by the top-level asset label**.
- **Corroboration structure**: provider ownership file → SEC confirmation of operating-company economics → public disclosure comparison → counterparty ownership and sanctions verification → subject/company comment.
- **Methodology notes**: no separate methods page; **[inferred]** from the article’s ownership-chain, SEC-revenue and sanctions sourcing. Project graph mechanics are stated on the [about page](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/).
- **Impact**: Ross later confirmed that he would divest the remaining Navigator interest after the revelations and ethics questions ([ICIJ follow-up](https://www.icij.org/investigations/paradise-papers/questions-remain-over-wilbur-ross-disclosure-as-he-confirms-divestment/)).
- **Generalization**: public disclosures should be expanded through every fund, holding company and subsidiary to operating assets, then joined to material customers, suppliers, lenders and sanctioned owners. The conflict may sit in a portfolio company’s counterparty, not the disclosed asset name.

### SUB-ENTRY: Apple’s post-Ireland island hop (2017) — leaked adviser correspondence captured a multinational shopping for a new tax residence after a rule change

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung, The New York Times and Paradise Papers partners; no thread-specific prize identified.
- **What they found**:
  - After Ireland moved to close the “Double Irish” arrangement, Apple’s adviser Baker McKenzie asked Appleby to compare six offshore jurisdictions through a 14-question questionnaire ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/)).
  - Apple shifted the tax residence of key subsidiaries to Jersey while holding about $252 billion in cash offshore ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/)).
  - The correspondence documented criteria such as tax treatment, disclosure and the likelihood of legal change, making jurisdiction selection observable rather than speculative ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/)).
- **Finding type(s)**: policy-arbitrage; corporate-profit-shifting; **rule-change-migration** (a structure moves jurisdictions or legal form in direct response to a closing loophole).
- **Evidence & sources**:
  - Appleby/Baker McKenzie emails and jurisdiction questionnaire [privileged].
  - Irish tax-law change and government statements [open-public].
  - Apple SEC filings for cash, subsidiaries and tax disclosures [open-public].
- **Access tier**: mixed — privileged adviser communications; open-public law and securities filings.
- **Detection signature**: **adviser jurisdiction-comparison records joined to the date of Ireland’s rule change and the later corporate-residence records revealed a rule-triggered migration; decision criteria in the questionnaire explained why Jersey won**.
- **Corroboration structure**: internal questionnaire/email → public legal change → public corporate and SEC records confirming the resulting structure → company/adviser response.
- **Methodology notes**: no standalone method; **[inferred]** from the dated email-to-law-to-filing sequence in the [story](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/).
- **Impact**: the disclosures intensified EU and national scrutiny of corporate tax arrangements; Apple defended the reorganization as compliant and said it paid all taxes due ([ICIJ investigation and response](https://www.icij.org/investigations/paradise-papers/apples-secret-offshore-island-hop-revealed-by-paradise-papers-leak-icij/)).
- **Generalization**: diff structures immediately before and after a regulatory change, then recover the adviser’s jurisdiction-comparison criteria. Generic cues are redomiciliation, new IP owners, trust migrations or renamed vehicles within the rule’s transition period.

### SUB-ENTRY: Nike’s royalty conduit and the substance test (2017) — offshore entities captured brand income despite negligible personnel or physical operations

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Süddeutsche Zeitung, Dutch partners Trouw and Het Financieele Dagblad, and Paradise Papers collaborators; no thread-specific prize identified.
- **What they found**:
  - Nike shifted European profits through royalties paid for use of the Swoosh and other intellectual property to offshore entities, first in Bermuda and later through a Dutch structure ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/)).
  - A key Bermuda entity had no employees or physical office while receiving large royalty flows ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/)).
  - ICIJ reported $6.6 billion in profits taxed at about 3% and used U.S. Tax Court material showing $3.86 billion in royalties over 2010–2012 ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/)).
- **Finding type(s)**: corporate-profit-shifting; letterbox-substance-gap; policy-arbitrage.
- **Evidence & sources**:
  - Appleby legal and corporate-administration files [privileged].
  - U.S. Tax Court records quantifying royalty flows [open-public].
  - Dutch and Bermuda company records, annual reports and tax rules [open-public/request-gated].
  - Field checks and product purchases tracing which entity licensed the mark [constructed] ([ICIJ investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/)).
- **Access tier**: mixed — privileged provider files; open-public court/company records; constructed substance and product-path checks.
- **Detection signature**: **royalty payments from court and company records joined to the IP-owning entities, then compared with employee, office and operating-asset indicators, revealed profit concentrated where productive substance was absent**.
- **Corroboration structure**: internal legal structure → court-quantified payments → registry and field check of the recipient’s substance → transaction/product documentation → tax-law experts and company response.
- **Methodology notes**: the source chain is described in the [investigation](https://www.icij.org/investigations/paradise-papers/swoosh-owner-nike-stays-ahead-of-the-regulator-icij/); the formal `profit-to-substance` ratio is **[inferred]**.
- **Impact**: the European Commission opened a state-aid investigation into Nike’s Dutch tax rulings and said the rulings might not reflect economic reality ([ICIJ EU follow-up](https://www.icij.org/investigations/paradise-papers/nikes-sweetheart-dutch-tax-deal-ignored-economic-reality-eu-says/)).
- **Generalization**: calculate profit, payments or assets per employee, office and operating cost for every group entity. High-value intangibles in a no-substance entity are a lead; related-party contracts and comparable-market pricing determine whether it is merely lean or artificially allocated.

---

### PROJECT: West Africa Leaks (2018) — localizing four global leak corpora exposed offshore actors and tax losses across 11 West African countries

- **URL**: [Project hub](https://www.icij.org/investigations/west-africa-leaks/); [about page](https://www.icij.org/about-the-investigation/)
- **Partner/awards** (lead outlets; prizes): ICIJ and the Norbert Zongo Cell for Investigative Journalism in West Africa (CENOZO) coordinated reporters across 11 countries; local partners supplied language, registry and political context ([about page](https://www.icij.org/about-the-investigation/)). No project-specific prize identified in the reviewed ICIJ pages.
- **What they found**:
  - Reporters re-searched 27.5 million documents from Offshore Leaks, Swiss Leaks, Panama Papers and Paradise Papers for West African persons, companies, addresses and transactions ([about page](https://www.icij.org/about-the-investigation/)).
  - The resulting stories connected officials, businesspeople, alleged traffickers and multinational structures to offshore accounts and companies in 11 countries ([overview](https://www.icij.org/investigations/west-africa-leaks/officials-businesses-traffickers-hide-billions-cash-starved-governments-offshore/)).
  - SNC-Lavalin routed $44.7 million of Senegal-related payments through a Mauritius company with no employees or office; ICIJ’s partner estimated Senegal may have lost up to $8.9 million in tax ([overview](https://www.icij.org/investigations/west-africa-leaks/officials-businesses-traffickers-hide-billions-cash-starved-governments-offshore/), [Senegal investigation](https://www.icij.org/investigations/west-africa-leaks/one-companys-tax-heaven-senegals-tax-hell/)).
- **Finding type(s)**: **corpus-relocalization** (re-query a global corpus through a defined geography, sector or community); letterbox-substance-gap; corporate-profit-shifting.
- **Evidence & sources**:
  - Four prior ICIJ leak corpora containing accounts, emails, contracts, passports and company records [privileged].
  - Local corporate, tax, procurement and public-official records from 11 countries [open-public/request-gated].
  - Interviews, physical-address checks and country-partner knowledge [constructed].
- **Access tier**: mixed — privileged historical corpora; open-public/request-gated local records; constructed localization and verification.
- **Detection signature**: **a cross-project leak index filtered on West African names, addresses, citizenship, intermediaries and transactions, then joined to local registries, contracts and tax rules, revealed stories missed by the original global searches**.
- **Corroboration structure**: corpus hit → local identity resolution → company/contract/tax record → field or interview check → subject and authority response. The local record supplied the public consequence that a bare offshore hit lacked.
- **Methodology notes**: ICIJ explicitly describes the reuse of 27.5 million records and country collaboration in the [about page](https://www.icij.org/about-the-investigation/) and the localization rationale in [“Why We Decided to Dig”](https://www.icij.org/investigations/west-africa-leaks/decided-dig-west-africas-offshore-links/). The filter/join notation is **[inferred]**.
- **Impact**: ICIJ documented probes and dismissals in some countries alongside official inaction in others, illustrating heterogeneous enforcement after the same publication ([impact review](https://www.icij.org/investigations/west-africa-leaks/probed-sacked-and-ignored-how-countries-reacted-to-west-africa-leaks/)).
- **Generalization**: old corpora should be periodically re-indexed against new place dictionaries, cohorts, sanctions and local registries. A global search misses spelling, kinship and institutional context that local partners can supply.

---

### PROJECT: Mauritius Leaks (2019) — provider files showed how treaty networks and low-substance Mauritius entities diverted taxable profit from poorer countries

- **URL**: [Project hub](https://www.icij.org/investigations/mauritius-leaks/); [about page](https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/)
- **Partner/awards** (lead outlets; prizes): ICIJ coordinated 54 journalists from 18 countries; partners included Le Monde, Süddeutsche Zeitung, NDR and Quartz, whose machine-learning team assisted document triage ([about page](https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/)). No project-specific major prize identified in the reviewed record.
- **What they found**:
  - More than 200,000 files from Conyers Dill & Pearman’s Mauritius office described structures designed to obtain treaty benefits and effective corporate tax rates of 3% or less ([about page](https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/)).
  - Bob Geldof’s 8 Miles private-equity fund used a Mauritius vehicle while investing across Africa; internal material cited tax reasons, and four of seven investment countries had treaties with Mauritius ([overview](https://www.icij.org/investigations/mauritius-leaks/treasure-island-leak-reveals-how-mauritius-siphons-tax-from-poor-nations-to-benefit-elites/)).
  - Senegal’s government estimated its treaty with Mauritius had cost about $257 million over 17 years; India lost a $2.2 billion Vodafone tax case involving a Mauritius-linked structure ([overview](https://www.icij.org/investigations/mauritius-leaks/treasure-island-leak-reveals-how-mauritius-siphons-tax-from-poor-nations-to-benefit-elites/)).
  - ICIJ cross-checked leaked companies against the Mauritius corporate registry and Financial Services Commission licensee lists before publishing a company list ([about page](https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/), [company-list release](https://www.icij.org/investigations/mauritius-leaks/icij-publishes-list-of-mauritian-companies-used-by-conyers-corporate-clients/)).
- **Finding type(s)**: **treaty-shopping** (route an investment through a jurisdiction to obtain treaty rights unavailable to the real investor); corporate-profit-shifting; letterbox-substance-gap.
- **Evidence & sources**:
  - Conyers client files, plans, tax opinions, emails and administration records [privileged].
  - Mauritius registry and Financial Services Commission licensee data [open-public/request-gated].
  - Bilateral tax treaties, tax-court decisions and government revenue estimates [open-public].
  - Corporate annual reports, investment records, address checks and responses [open-public/constructed].
- **Access tier**: mixed — privileged provider leak; open-public/request-gated registries, treaties and judgments; constructed entity matching and document classification.
- **Detection signature**: **leaked investment structures joined to the bilateral-treaty graph on source country, intermediary jurisdiction and payment type revealed treaty paths; tax outcomes compared with entity substance and direct-route treatment quantified the advantage**.
- **Corroboration structure**: provider plan → registry confirmation of entity/license → treaty article and court precedent → company accounts/investment record → government and subject response. ICIJ distinguished a legal treaty claim from evidence of economic substance.
- **Methodology notes**: the [about page](https://www.icij.org/investigations/mauritius-leaks/about-the-mauritius-leaks-investigation/) explicitly describes registry/FSC corroboration and Quartz’s machine-learning assistance; ICIJ’s [treaty explainer](https://www.icij.org/investigations/mauritius-leaks/whats-a-tax-treaty-and-why-should-i-care/) sets out the rule mechanics. The shortest-path treaty detector is **[inferred]**.
- **Impact**: Senegal terminated its tax treaty with Mauritius, and several governments reviewed or renegotiated treaties after publication ([Senegal follow-up](https://www.icij.org/investigations/mauritius-leaks/senegal-nixes-unbalanced-tax-treaty-with-mauritius/), [broader impact](https://www.icij.org/investigations/mauritius-leaks/tax-treaties-scrutinized-re-negotiated-in-wake-of-mauritius-leaks-investigation/)).
- **Generalization**: encode treaties as directed edges with tax rates, eligibility tests and dates; compare actual transaction routes with the shortest commercial route. Flag an intermediate entity whose main observable function is changing the governing treaty.

---

### PROJECT: Luanda Leaks (2020) — a document and transaction reconstruction showed how Isabel dos Santos converted public position and state-company relationships into a 400-company private empire

- **URL**: [Project hub](https://www.icij.org/investigations/luanda-leaks/); [about page](https://www.icij.org/investigations/luanda-leaks/about-the-luanda-leaks-investigation/)
- **Partner/awards** (lead outlets; prizes): The Platform to Protect Whistleblowers in Africa (PPLAAF) supplied the files; ICIJ coordinated more than 120 journalists from 36 organizations in 20 countries, including BBC, The Guardian, Expresso and The New York Times ([about page](https://www.icij.org/investigations/luanda-leaks/about-the-luanda-leaks-investigation/)). No project-specific major prize identified in the reviewed pages.
- **What they found**:
  - More than 715,000 records mapped over 400 companies and subsidiaries in 41 countries, including 94 in secrecy jurisdictions, connected to Isabel dos Santos and Sindika Dokolo ([about page](https://www.icij.org/investigations/luanda-leaks/about-the-luanda-leaks-investigation/)).
  - Hours after dos Santos was fired as chair of state oil company Sonangol, it transferred about $38 million to a Dubai company controlled by an associate under a disputed consulting arrangement ([global overview](https://www.icij.org/investigations/luanda-leaks/how-africas-richest-woman-exploited-family-ties-shell-companies-and-inside-deals-to-build-an-empire/)).
  - State-linked deals and financing helped transfer valuable stakes and contracts; ICIJ reported more than $1 billion in allegedly inflated or questionable contracts connected to her network ([global overview](https://www.icij.org/investigations/luanda-leaks/how-africas-richest-woman-exploited-family-ties-shell-companies-and-inside-deals-to-build-an-empire/)).
  - Western accountants, consultants, lawyers and banks received millions while establishing, auditing or moving money for the network ([enablers investigation](https://www.icij.org/investigations/luanda-leaks/western-advisers-helped-an-autocrats-daughter-amass-and-shield-a-fortune/)).
- **Finding type(s)**: **state-asset-conversion** (public assets, contracts or authority are converted into private network value); public-private-conflict; intermediary-enablement; deadline-adjacent-restructuring.
- **Evidence & sources**:
  - Emails, contracts, spreadsheets, ledgers, audits, incorporation files, organization charts, loans, deeds, public contracts, invoices and tax returns supplied through PPLAAF [privileged] ([about page](https://www.icij.org/investigations/luanda-leaks/about-the-luanda-leaks-investigation/)).
  - OCR and entity extraction in ICIJ Datashare; tagged document collections and constructed organization/transaction maps [constructed] ([data methodology](https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/)).
  - Registries, deeds, public contracts, court filings, bank records, site visits and more than 200 interviews [open-public/request-gated/constructed] ([beyond-the-documents methodology](https://www.icij.org/investigations/luanda-leaks/reporting-beyond-the-luanda-leaks-documents/)).
- **Access tier**: mixed — privileged business leak; constructed document/entity system; public, request-gated and interview corroboration.
- **Detection signature**: **contracts, invoices, ownership and bank records joined into a dated entity-payment graph on company, signatory, account and beneficial owner revealed value moving from state bodies through related companies; office-change dates compared with payment authorization exposed last-minute transfers**.
- **Corroboration structure**: internal contract/ledger → bank or invoice evidence → registry/deed/public-contract anchor → site visit or recipient interview → legal and financial expert review → extensive subject contact. ICIJ separated documents showing transfers from allegations about criminality.
- **Methodology notes**: ICIJ’s [data account](https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/) describes Datashare, OCR, entity extraction and tagging; [reporting beyond the documents](https://www.icij.org/investigations/luanda-leaks/reporting-beyond-the-luanda-leaks-documents/) describes public-record, travel and interview verification. The state-to-private graph abstraction is **[inferred]**.
- **Impact**: Angola charged dos Santos with 12 crimes, courts froze or invalidated assets, and the United States later sanctioned her for corruption; she has denied wrongdoing ([charges](https://www.icij.org/investigations/luanda-leaks/isabel-dos-santos-charged-with-12-crimes-in-angola-over-her-dealings-as-sonangol-chair/), [U.S. sanctions](https://www.icij.org/investigations/luanda-leaks/us-sanctions-angolan-billionaire-isabel-dos-santos-for-corruption/)).
- **Generalization**: build a dated graph from every public-asset decision through beneficial ownership to recipients and advisers. Rank transfers by proximity to appointment, dismissal, election, privatization or regulatory deadlines and by deviations from independent valuation or procurement norms.

---

### PROJECT: FinCEN Files (2020) — leaked suspicious-activity reports reconstructed $2 trillion in flagged payments and showed global banks repeatedly moving money after warnings and penalties

- **URL**: [Project hub](https://www.icij.org/investigations/fincen-files/); [about page](https://www.icij.org/investigations/fincen-files/about-the-fincen-files-investigation/)
- **Partner/awards** (lead outlets; prizes): BuzzFeed News obtained and shared the records; ICIJ coordinated more than 400 journalists from 108 organizations in 88 countries. The project was a 2021 Pulitzer finalist and won IRE’s Tom Renner Award ([about](https://www.icij.org/investigations/fincen-files/about-the-fincen-files-investigation/), [awards](https://www.icij.org/investigations/fincen-files/fincen-files-investigation-named-pulitzer-prize-finalist/)).
- **What they found**:
  - More than 2,100 suspicious activity reports (SARs) described over $2 trillion in flagged transactions from 1999 through 2017, but represented less than 0.02% of the more than 12 million SARs filed from 2011 through 2017 ([about page](https://www.icij.org/investigations/fincen-files/about-the-fincen-files-investigation/)).
  - Reporters manually structured more than 55,000 records covering over 200,000 transactions and about 6,900 correspondent-bank connections ([data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/)).
  - Five major banks continued moving funds for suspect clients after U.S. penalties; Deutsche Bank appeared in about $1.3 trillion and JPMorgan in about $514 billion of flagged transactions ([global overview](https://www.icij.org/investigations/fincen-files/global-banks-defy-u-s-crackdowns-by-serving-oligarchs-criminals-and-terrorists/)).
  - About half the reports lacked information for at least one entity, demonstrating how incomplete customer information propagates through correspondent banking ([about page](https://www.icij.org/investigations/fincen-files/about-the-fincen-files-investigation/)).
- **Finding type(s)**: high-risk-client-servicing; compliance-knowledge-gap; **enforcement-recidivism** (risky conduct or control failure continues after a penalty, monitor or formal warning); **correspondent-opacity** (an intermediary bank processes transactions without reliable information on the originator or beneficiary).
- **Evidence & sources**:
  - Leaked FinCEN SAR forms and narrative attachments obtained by BuzzFeed News [privileged official records].
  - Manually extracted transaction, entity and correspondent-bank tables; narrative-derived values and normalized identifiers [constructed] ([data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/)).
  - Court cases, enforcement settlements, sanctions lists, corporate registries, bank filings, audit reports and interviews [open-public/request-gated/constructed].
- **Access tier**: mixed — privileged regulatory reports; constructed transaction layer; open-public/request-gated corroboration.
- **Detection signature**: **SAR narratives parsed into transactions and joined on account, bank, entity, amount and date created a cross-bank flow graph; clients and banks joined to sanctions, cases, penalties and warning dates revealed service continuing after documented risk events**.
- **Corroboration structure**: SAR allegation/flag → underlying transaction fields → public registry/court/enforcement record → second bank report or external audit where available → bank/client response. ICIJ stressed that a SAR records suspicion, not proof of crime, and that multiple banks reporting one transfer are not independent proof of illegality.
- **Methodology notes**: ICIJ’s [“Mining the SARs”](https://www.icij.org/investigations/fincen-files/mining-sars-data/) documents the 85-reporter manual extraction, three million narrative words, 200,000 transactions and correspondent connections; the [download page](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/) defines the released data and limitations. The recidivism event join is **[inferred]**.
- **Impact**: the U.S. enacted the Corporate Transparency Act, and regulators and banks announced reforms and inquiries after publication ([ICIJ impact review](https://www.icij.org/investigations/fincen-files/heres-what-is-changing-after-the-fincen-files-shook-the-world-of-banking/)).
- **Generalization**: narrative regulatory filings can be converted into a transaction graph, but suspicion must remain a claim status. Join flows to the full event history—onboarding, SAR, sanctions, enforcement, monitor reports and exit—to distinguish isolated flags from institutional recidivism.

### SUB-ENTRY: HSBC and the WCM Ponzi network (2020) — SARs showed billions moving through HSBC after its record laundering settlement and despite fraud warnings

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/fincen-files/hsbc-moved-vast-sums-of-dirty-money-after-paying-record-laundering-fine/)
- **Partner/awards** (lead outlets; prizes): ICIJ, BuzzFeed News, BBC Panorama and FinCEN Files partners; part of the Pulitzer-finalist/Tom Renner-winning project ([awards](https://www.icij.org/investigations/fincen-files/fincen-files-investigation-named-pulitzer-prize-finalist/)).
- **What they found**:
  - HSBC moved money for the WCM777 Ponzi scheme after warnings and during a five-year U.S. probation imposed under its $1.92 billion 2012 anti-money-laundering settlement ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/hsbc-moved-vast-sums-of-dirty-money-after-paying-record-laundering-fine/)).
  - Seventy-three HSBC SARs described $4.4 billion in suspicious transactions; nearly $900 million was tied to shell-company networks that authorities later alleged were criminal ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/hsbc-moved-vast-sums-of-dirty-money-after-paying-record-laundering-fine/)).
  - Victim accounts and criminal proceedings connected the abstract flow failure to a specific fraud and human losses ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/hsbc-moved-vast-sums-of-dirty-money-after-paying-record-laundering-fine/)).
- **Finding type(s)**: enforcement-recidivism; high-risk-client-servicing; **warning-to-action-lag** (risk information exists materially before effective restriction, reporting or exit).
- **Evidence & sources**:
  - HSBC-filed SARs and narratives [privileged official records].
  - The 2012 deferred-prosecution agreement, monitor/probation history and later criminal cases [open-public/request-gated].
  - Company registries, websites and victim/family interviews identifying WCM entities and consequences [open-public/constructed].
- **Access tier**: mixed — privileged SARs; public enforcement and court records; constructed flow and victim chronology.
- **Detection signature**: **SAR transactions joined to the bank’s penalty/probation timeline and fraud-warning dates on client, account and date revealed payments continuing during remediation; shell recipients expanded through registry ownership connected the flows to WCM**.
- **Corroboration structure**: bank-authored SAR → payment extraction → criminal and enforcement records → registry/entity resolution → victim and bank response. The bank’s suspicion and later prosecution corroborated risk but did not make each payment criminal.
- **Methodology notes**: transaction extraction follows ICIJ’s quoted [SAR methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/); the warning-lag calculation is **[inferred]** from the dated settlement, warnings and payments in the thread story.
- **Impact**: the story contributed to renewed scrutiny of HSBC’s deferred-prosecution regime and to the broader FinCEN Files legislative response; no thread-specific new prosecution of HSBC is claimed here ([project impact review](https://www.icij.org/investigations/fincen-files/heres-what-is-changing-after-the-fincen-files-shook-the-world-of-banking/)).
- **Generalization**: after any corporate settlement, compare the monitor period with customer- and transaction-level conduct. A generic detector measures days from first warning to SAR, restriction and exit, then ranks value moved during each lag.

### SUB-ENTRY: Britain’s shell-company factories (2020) — recurring signatures clustered thousands of nominally separate firms into four formation networks and exposed unreported billions

- **URL**: [Factory investigation](https://www.icij.org/investigations/fincen-files/inside-scandal-rocked-danske-estonia-and-the-shell-company-factories-that-served-it/); [signature methodology](https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/)
- **Partner/awards** (lead outlets; prizes): ICIJ, BuzzFeed News, Finance Uncovered and FinCEN Files partners; covered by the project’s awards ([awards](https://www.icij.org/investigations/fincen-files/fincen-files-investigation-named-pulitzer-prize-finalist/)).
- **What they found**:
  - Reporters identified 3,267 U.K. limited partnerships and LLPs in the relevant network, about half traceable to four formation factories ([factory investigation](https://www.icij.org/investigations/fincen-files/inside-scandal-rocked-danske-estonia-and-the-shell-company-factories-that-served-it/)).
  - Repeated formation signatures—addresses, officers, partners, naming and filing patterns—linked companies that appeared independent in Companies House ([methodology](https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/)).
  - Comparing public accounts with SAR payment totals found about $4.5 billion that the shell firms did not report in U.K. accounts from 2012 through 2017 ([methodology](https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/)).
- **Finding type(s)**: **formation-factory** (many legal entities share a repeated incorporation template and controlling service network); correspondent-opacity; **cross-ledger-mismatch** (the same entity has incompatible values in two reporting systems).
- **Evidence & sources**:
  - FinCEN SAR transactions and narratives [privileged official records].
  - Companies House incorporation, officer, partner, address and annual-account filings [open-public].
  - Constructed signature clusters and company-to-factory network [constructed].
- **Access tier**: mixed — privileged transaction records; open-public registry/accounts; constructed clustering.
- **Detection signature**: **Companies House entities clustered on repeated officer, partner, address, filing and signature features revealed formation factories; SAR inflows compared to filed turnover/income on company and year revealed $4.5 billion absent from public accounts**.
- **Corroboration structure**: cluster feature → source filings → SAR transaction evidence → company accounts → site/subject checks. Reporters manually inspected signature matches to avoid treating common professional addresses alone as ownership.
- **Methodology notes**: ICIJ explicitly explains signature comparison and the SAR-to-accounts mismatch in [“How Signatures in Public Data…”](https://www.icij.org/investigations/fincen-files/how-signatures-in-public-data-helped-expose-the-uks-dirty-money-cottage-industry/). No inference marker is needed for the core move; thresholds and generic feature weights below are **[inferred]**.
- **Impact**: FinCEN Files added pressure for U.K. company-formation and beneficial-ownership reform; the U.S. adopted beneficial-ownership legislation at project level ([ICIJ impact review](https://www.icij.org/investigations/fincen-files/heres-what-is-changing-after-the-fincen-files-shook-the-world-of-banking/)).
- **Generalization**: fingerprint entity factories with feature combinations, not a single shared address. Then compare registry accounts with payments, customs, payroll, procurement or tax ledgers for the same entity-year.

### SUB-ENTRY: Kolomoisky’s U.S. property trail (2020) — bank records, audits and deeds traced more than $750 million from a Ukrainian bank into a shell-company real-estate network

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/)
- **Partner/awards** (lead outlets; prizes): ICIJ, BuzzFeed News, Pittsburgh Post-Gazette, Miami Herald and FinCEN Files partners; part of the awarded project ([awards](https://www.icij.org/investigations/fincen-files/fincen-files-investigation-named-pulitzer-prize-finalist/)).
- **What they found**:
  - Deutsche Bank moved more than $750 million that authorities alleged had been siphoned from Ukraine’s PrivatBank into the United States ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/)).
  - More than half of the money went into commercial real estate, including factories and office buildings in U.S. communities ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/)).
  - Layered U.S. LLCs and intermediaries separated the bank transfers from the visible property buyers, while confidential audits and litigation alleged coordinated insider lending at PrivatBank ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/)).
- **Finding type(s)**: networked-asset-concealment; state-asset-conversion; **flow-to-asset-conversion** (funds are traced through entities into identifiable real property or operating assets).
- **Evidence & sources**:
  - SARs and bank transaction records [privileged official records].
  - Confidential PrivatBank audits and civil complaints [privileged/request-gated and open-public litigation].
  - U.S. deeds, mortgages, company registries, property records and site visits [open-public/request-gated/constructed].
  - Interviews with workers, officials, lawyers and company representatives [constructed].
- **Access tier**: mixed — privileged bank/audit records; public litigation, corporate and property records; constructed flow graph and field checks.
- **Detection signature**: **bank transfers traversed through shell accounts on amount, date, counterparty and signatory, then joined to LLC ownership and property deeds on buyer and closing date, revealed conversion of alleged bank proceeds into U.S. assets**.
- **Corroboration structure**: SAR payment → audit/litigation allegation about source → registry resolution of intermediate LLC → deed/mortgage confirmation of asset → field and subject verification. Criminality remains attributed to authorities where not adjudicated.
- **Methodology notes**: transaction structuring follows [ICIJ’s SAR method](https://www.icij.org/investigations/fincen-files/mining-sars-data/); the payment-to-deed traversal is **[inferred]** from the source sequence in the [investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/).
- **Impact**: U.S. authorities pursued civil forfeiture and Ukraine litigated over PrivatBank assets; this entry states those as official allegations/actions, not proof of the full theory ([ICIJ investigation](https://www.icij.org/investigations/fincen-files/with-deutsche-banks-help-an-oligarchs-buying-spree-trails-ruin-across-the-us-heartland/)).
- **Generalization**: represent money and title as separate but linkable graphs. Look for amount/date proximity between wire exits and acquisitions, common signatories, mortgage lenders, closing agents and rapid refinancing.

---

### PROJECT: Pandora Papers (2021) — the largest ICIJ offshore leak resolved owners across 14 providers and exposed how leaders, oligarchs and criminals used a fragmented global secrecy market

- **URL**: [Project hub](https://www.icij.org/investigations/pandora-papers/); [about page](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-investigation/)
- **Partner/awards** (lead outlets; prizes): ICIJ coordinated more than 600 journalists from about 150 outlets in 117 countries and territories, including The Washington Post, The Guardian, BBC, Le Monde and Süddeutsche Zeitung ([about page](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-investigation/)). The project won or was recognized by multiple international journalism organizations; no single prize is used as an evidentiary claim here.
- **What they found**:
  - The 2.94 TB corpus contained 11.9 million records from 14 offshore service providers; only about 4% was structured at receipt ([data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)).
  - ICIJ identified more than 29,000 beneficial owners of over 27,000 offshore companies and linked structures to 35 current or former national leaders and more than 330 politicians and public officials in 91 countries and territories ([about page](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-investigation/), [global overview](https://www.icij.org/investigations/pandora-papers/global-investigation-tax-havens-offshore/)).
  - ICIJ counted 956 companies tied to 336 politicians and officials; more than two-thirds were incorporated in the BVI ([global overview](https://www.icij.org/investigations/pandora-papers/global-investigation-tax-havens-offshore/)).
  - Provider records showed due diligence and suspicious-activity reporting often followed public exposure rather than preceding it ([data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)).
- **Finding type(s)**: hidden-beneficial-ownership; intermediary-enablement; elite-cohort-penetration; compliance-after-the-fact.
- **Evidence & sources**:
  - Emails, spreadsheets, PDFs, images, passports, incorporation and beneficial-ownership files from 14 providers [privileged].
  - Deduplicated master spreadsheets, Python extraction, OCR, machine-learning models, manual transcription, Neo4j/Linkurious and Datashare [constructed] ([data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)).
  - Sanctions lists, prior ICIJ leaks, corporate/property records, public-official and billionaire rosters, asset declarations, courts and interviews [open-public/request-gated/constructed].
- **Access tier**: mixed — privileged multi-provider leaks; constructed entity/document/graph systems; open-public and request-gated verification.
- **Detection signature**: **fourteen heterogeneous provider corpora normalized to a common beneficial-owner/entity model and joined to sanctions, prior leaks, registries and fixed official/billionaire cohorts revealed cross-provider ownership, prevalence and repeated enablers**.
- **Corroboration structure**: model/search candidate → manual source-document review → second provider or public registry where available → official/asset/risk record → local-partner verification and subject contact. ICIJ excluded due-diligence news clippings from ownership counts and did not treat name appearance as ownership ([data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)).
- **Methodology notes**: [ICIJ’s dataset methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) explicitly describes the 4% structured-data problem, master-spreadsheet deduplication, Python/ML extraction, manual handwriting review, external-list matching and graph tools. The common-model formulation is **[inferred]**.
- **Impact**: governments opened investigations, officials resigned or faced elections and authorities announced reforms within months of publication ([2021 impact review](https://www.icij.org/investigations/pandora-papers/pandora-papers-caps-off-2021-with-consequences-felt-around-the-globe/)).
- **Generalization**: cross-provider analysis requires a common role ontology and provenance at the edge level. Deduplicate source copies without collapsing distinct corroboration, and measure which provider, jurisdiction and intermediary combinations recur across the risk cohort.

### SUB-ENTRY: King Abdullah’s 14 hidden homes (2021) — 36 front companies were linked to more than $106 million in U.K. and U.S. property

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/pandora-papers/jordan-king-abdullah-luxury-property/)
- **Partner/awards** (lead outlets; prizes): ICIJ, The Washington Post, The Guardian, BBC and Pandora Papers partners; no thread-specific prize identified.
- **What they found**:
  - Jordan’s King Abdullah II acquired 14 luxury homes in the United States and United Kingdom from 2003 through 2017 for more than $106 million ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/jordan-king-abdullah-luxury-property/)).
  - At least 36 front companies obscured the ownership chain ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/jordan-king-abdullah-luxury-property/)).
  - The portfolio included high-value Malibu, Washington, D.C., and London properties while Jordan received substantial foreign aid; the king’s lawyers said the purchases used personal wealth and secrecy was for security ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/jordan-king-abdullah-luxury-property/)).
- **Finding type(s)**: networked-asset-concealment; **portfolio-reconstruction** (aggregate assets hidden behind distinct nominees or entities into one controlled portfolio); public-private-conflict.
- **Evidence & sources**:
  - Provider ownership and company-administration records [privileged].
  - U.S. and U.K. deeds, land records and company registries [open-public/request-gated].
  - Sale prices, mortgages and property-company link records [open-public].
- **Access tier**: mixed — privileged controller records; public/request-gated property and corporate records.
- **Detection signature**: **leaked beneficial-owner records joined to property-title companies and deeds on company name, address and acquisition date revealed 14 assets; grouping all title entities by common controller reconstructed the $106 million portfolio**.
- **Corroboration structure**: provider file identifies controller → title registry confirms company-owned parcel → deed fixes date/price → public biography and security explanation → lawyer/royal-court response.
- **Methodology notes**: multi-provider extraction is documented in [ICIJ’s Pandora methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/); the portfolio aggregation is **[inferred]** from the story’s company-to-deed sequence.
- **Impact**: Jordanian authorities restricted access to the reporting, while the revelations prompted domestic and international scrutiny; no confiscation or adjudicated illegality is claimed ([project impact review](https://www.icij.org/investigations/pandora-papers/pandora-papers-caps-off-2021-with-consequences-felt-around-the-globe/)).
- **Generalization**: map every asset-holding entity to controllers and cluster by common adviser, contact, address and funding source. The story is often the portfolio total and timeline, not any single property.

### SUB-ENTRY: Andrej Babiš’s French estate chain (2021) — a circular $22 million offshore loan bought property omitted from the Czech prime minister’s declarations

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/pandora-papers/czech-prime-minister-andrej-babis-french-property/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Investigace.cz, Le Monde and Pandora Papers partners; no thread-specific prize identified.
- **What they found**:
  - In 2009 Babiš moved about $22 million through a BVI company, a Washington, D.C., company and a Monaco company using back-to-back loans to acquire a French Riviera estate ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/czech-prime-minister-andrej-babis-french-property/)).
  - The offshore companies and estate did not appear in declarations he filed after entering Czech politics ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/czech-prime-minister-andrej-babis-french-property/)).
  - The chain created the appearance of financing between entities ultimately linked to the same controller ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/czech-prime-minister-andrej-babis-french-property/)).
- **Finding type(s)**: disclosure-gap; networked-asset-concealment; **self-financing-loop** (related entities lend through a chain that obscures the common source or controller).
- **Evidence & sources**:
  - Provider loan, incorporation and ownership files [privileged].
  - French property records and company registries in the BVI, U.S. and Monaco [open-public/request-gated].
  - Czech political asset declarations [open-public].
- **Access tier**: mixed — privileged transaction/ownership files; public/request-gated registries, deeds and disclosures.
- **Detection signature**: **loan agreements ordered by date and joined on amount, lender, borrower and common beneficial owner revealed a circular financing chain; terminal property title compared with official declarations revealed the omission**.
- **Corroboration structure**: each loan edge traced to source document → registry confirms each entity → deed fixes the asset → declaration anti-join → subject response.
- **Methodology notes**: no separate thread method; **[inferred]** from the loan-chain reconstruction. The parent project’s extraction process is [documented here](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/).
- **Impact**: Babiš’s party narrowly lost the election held days after publication; the result cannot be attributed solely to Pandora Papers, but ICIJ documented the timing and political salience ([ICIJ election follow-up](https://www.icij.org/investigations/pandora-papers/czech-prime-ministers-party-narrowly-loses-re-election-days-after-pandora-papers-revelations-in-surprise-outcome/)).
- **Generalization**: collapse all entities to beneficial owners before evaluating loans. Flag cycles, equal-value same-day transfers, loans without independent economic purpose and assets missing from the controller’s declarations.

### SUB-ENTRY: South Dakota’s foreign trust vault (2021) — provider files showed more than $1 billion in U.S. trusts tied to foreign clients, including people accused of wrongdoing

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/pandora-papers/us-trusts-offshore-south-dakota-tax-havens/)
- **Partner/awards** (lead outlets; prizes): ICIJ, The Washington Post and Pandora Papers partners; no thread-specific prize identified.
- **What they found**:
  - Pandora files identified 206 U.S.-based trusts with clients from 41 countries holding assets worth more than $1 billion ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/us-trusts-offshore-south-dakota-tax-havens/)).
  - Nearly 30 trusts were linked to people or companies accused in public records of fraud, bribery or human-rights abuses ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/us-trusts-offshore-south-dakota-tax-havens/)).
  - South Dakota trust assets had grown to about $360 billion as state law strengthened secrecy and asset protection ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/us-trusts-offshore-south-dakota-tax-havens/)).
- **Finding type(s)**: **jurisdictional-risk-migration** (risky assets or clients move to a jurisdiction whose rules offer greater secrecy/protection); high-risk-client-servicing; elite-cohort-penetration.
- **Evidence & sources**:
  - Trident Trust and other provider trust records [privileged].
  - Court cases, government allegations, sanctions/adverse records and public biographies [open-public].
  - South Dakota statutes and official/industry trust-asset statistics [open-public].
- **Access tier**: mixed — privileged trust identities and values; public risk, law and aggregate data.
- **Detection signature**: **provider trust records grouped by U.S. situs and settlor origin, then joined to court/government risk records on resolved identity, revealed the foreign high-risk cohort; trust-creation dates compared with state-law changes exposed jurisdictional migration**.
- **Corroboration structure**: provider trust document → client identity confirmation → independent allegation or judgment → law/date comparison → trustee, subject and authority comment. Accusations were labeled and not converted into findings of guilt.
- **Methodology notes**: external-list matching and structured extraction are quoted in [ICIJ’s data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/); the law-change migration test is **[inferred]**.
- **Impact**: the revelations intensified U.S. debate over domestic trust secrecy and informed calls for trust and beneficial-ownership reform; no single federal trust-transparency measure is attributed solely to this thread ([project impact review](https://www.icij.org/investigations/pandora-papers/pandora-papers-caps-off-2021-with-consequences-felt-around-the-globe/)).
- **Generalization**: monitor whether entity/trust formation shifts after one haven is exposed or restricted. Join formation dates and client risk to legal changes, provider migrations and asset transfers across jurisdictions.

### SUB-ENTRY: Alcogal’s politician-heavy client book and late SARs (2021) — provider data showed a political client concentration and suspicious reports filed after public exposure

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/pandora-papers/alcogal-panama-latin-america-politicians/); [data release](https://www.icij.org/investigations/pandora-papers/icij-releases-new-pandora-papers-data-from-two-offshore-service-providers/)
- **Partner/awards** (lead outlets; prizes): ICIJ, La Prensa, El País and Latin American Pandora Papers partners; no thread-specific prize identified.
- **What they found**:
  - More than 2 million Alcogal files described over 14,000 entities and about 15,000 clients; nearly half of the politicians in Pandora Papers were clients of the Panama-headquartered firm ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/alcogal-panama-latin-america-politicians/), [data release](https://www.icij.org/investigations/pandora-papers/icij-releases-new-pandora-papers-data-from-two-offshore-service-providers/)).
  - Alcogal created more than 200 shell companies for clients of Banca Privada d’Andorra, a bank later accused by U.S. authorities of laundering criminal proceeds ([ICIJ investigation](https://www.icij.org/investigations/pandora-papers/alcogal-panama-latin-america-politicians/)).
  - Of 109 Alcogal suspicious-activity reports identified by ICIJ, 87 were written only after authorities or journalists had publicly identified the clients ([data methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)).
- **Finding type(s)**: elite-cohort-penetration; intermediary-enablement; compliance-after-the-fact; warning-to-action-lag.
- **Evidence & sources**:
  - Alcogal client, entity, due-diligence and SAR files [privileged].
  - Fixed politician roster and identity-resolution table [constructed].
  - Public enforcement records, news publication dates and bank-risk records [open-public].
- **Access tier**: mixed — privileged provider/compliance files; constructed cohort; public enforcement and publication timeline.
- **Detection signature**: **provider clients joined to a fixed politician roster revealed exceptional cohort concentration; SAR creation dates compared with first public-risk dates revealed that 87 of 109 reports followed exposure rather than detecting it**.
- **Corroboration structure**: candidate name → source ownership/service document → official-role record → SAR and first-public-warning dates → provider/client response. Due-diligence news clippings were not counted as evidence of ownership.
- **Methodology notes**: the SAR count and external-list protocol are stated in [ICIJ’s dataset methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/); the provider-level concentration measure is **[inferred]** from the project’s counts and [Alcogal reporting](https://www.icij.org/investigations/pandora-papers/alcogal-panama-latin-america-politicians/).
- **Impact**: authorities across Latin America opened tax and corruption reviews of Pandora Papers subjects; the broader investigation prompted official inquiries in many jurisdictions ([2021 impact review](https://www.icij.org/investigations/pandora-papers/pandora-papers-caps-off-2021-with-consequences-felt-around-the-globe/)).
- **Generalization**: compute the share of each provider’s clientele that belongs to high-risk cohorts and benchmark it against peers. For compliance, compare alert/SAR dates with the first event the institution could reasonably have known, not only with the filing date.

---

### PROJECT: Cyprus Confidential (2023) — seven leaks exposed Cyprus’s service industry as a major shelter and transfer hub for sanctioned Russian wealth

- **URL**: [Project hub](https://www.icij.org/investigations/cyprus-confidential/); [about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)
- **Partner/awards** (lead outlets; prizes): ICIJ and Munich-based Paper Trail Media led 272 journalists from 69 media partners in 54 countries and one territory; partners included The Guardian, The Bureau of Investigative Journalism, Der Spiegel, Le Monde, OCCRP and The Washington Post ([about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)). No single project-wide prize is claimed here.
- **What they found**:
  - More than 3.6 million files came from six Cyprus-based financial-service providers and Latvian registry reseller i-Cyprus in seven leaks obtained through Distributed Denial of Secrets and Paper Trail Media ([about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)).
  - ICIJ identified nearly 800 companies and trusts in secrecy jurisdictions owned or controlled by Russians sanctioned since 2014 ([about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)).
  - Cypriot firms had provided services to at least 25 Russians already sanctioned after 2014 and at least 71 more sanctioned after the 2022 invasion; PwC Cyprus had worked with 12 of the pre-2022 sanctioned group ([global overview](https://www.icij.org/investigations/cyprus-confidential/cyprus-russia-eu-secrecy-tax-haven/), [methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/)).
  - Manual review of 1,100 company accounts found PwC audited 38 oligarch-owned companies, including 25 owned by Alexey Mordashov ([methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/)).
- **Finding type(s)**: jurisdictional-risk-migration; high-risk-client-servicing; intermediary-enablement; elite-cohort-penetration.
- **Evidence & sources**:
  - Company charts, emails, financial statements, annual reports, invoices, wire transfers, trust and ownership documents from seven leaks [privileged].
  - NLP/entity extraction, keyword classification and a manually reviewed company/auditor table [constructed] ([methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/)).
  - Forbes’s 2023 billionaires list, Dow Jones risk data, sanctions lists, official political/PEP records, company accounts and open-source reporting [open-public/request-gated].
  - Interviews, travel, experts and subject responses [constructed] ([about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)).
- **Access tier**: mixed — privileged service-provider leaks; licensed/open-public risk and company sources; constructed NLP, cohort and manual-review layers.
- **Detection signature**: **leak-derived beneficial owners and clients joined to time-versioned sanctions, billionaire and political-risk lists revealed the exposed cohort; company accounts joined to auditor names and manually verified ownership quantified professional-firm concentration**.
- **Corroboration structure**: NLP/keyword candidate → manual source-document and financial-statement review → sanctions/role record → provider/auditor confirmation → local partner and subject contact. ICIJ manually confirmed both oligarch ownership and PwC’s audit role rather than counting every text mention ([methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/)).
- **Methodology notes**: [ICIJ’s data methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/) states the cohort sources, NLP retraining, keyword variants, 1,100-account search and manual fact-checking. The concentration metric and event-join expression are **[inferred]**.
- **Impact**: within 24 hours Cyprus’s president promised an investigation; U.S. financial-crime experts were deployed, and Cyprus later authorized a dedicated sanctions unit ([sanctions-unit follow-up](https://www.icij.org/investigations/cyprus-confidential/cyprus-greenlights-sanctions-unit-following-icij-investigation-into-the-countrys-financial-services-sector/)).
- **Generalization**: create a time-versioned client-risk table, then measure each adviser’s exposure before and after key sanctions or political events. Require manual confirmation where auditor or law-firm names can occur in irrelevant document contexts.

### SUB-ENTRY: PwC and Mordashov’s $1.4 billion TUI transfer (2023) — service records captured an ownership move as EU sanctions approached

- **URL**: [Global investigation](https://www.icij.org/investigations/cyprus-confidential/cyprus-russia-eu-secrecy-tax-haven/); [official-response follow-up](https://www.icij.org/investigations/cyprus-confidential/cypriot-authorities-face-scrutiny-over-probe-into-russian-billionaires-moves-to-dodge-sanctions/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Paper Trail Media and Cyprus Confidential partners; no thread-specific prize identified.
- **What they found**:
  - PwC Cyprus assisted Alexey Mordashov in transferring a $1.4 billion holding in travel company TUI to Marina Mordashova as EU sanctions approached ([global investigation](https://www.icij.org/investigations/cyprus-confidential/cyprus-russia-eu-secrecy-tax-haven/)).
  - Marina Mordashova was sanctioned by the United States and EU about three months later; the German government and TUI treated the share transfer as invalid ([follow-up](https://www.icij.org/investigations/cyprus-confidential/cypriot-authorities-face-scrutiny-over-probe-into-russian-billionaires-moves-to-dodge-sanctions/)).
  - The case sat inside a larger PwC Cyprus portfolio that included clients already sanctioned after Russia’s 2014 actions in Ukraine ([about page](https://www.icij.org/investigations/cyprus-confidential/about-cyprus-confidential-investigation/)).
- **Finding type(s)**: deadline-adjacent-restructuring; sanctions-evasion-risk; high-risk-client-servicing; compliance-knowledge-gap.
- **Evidence & sources**:
  - PwC/provider emails, instructions, ownership and transfer records [privileged].
  - EU, U.S. and U.K. sanctions designation dates [open-public].
  - TUI disclosures, German government statements and corporate ownership records [open-public].
- **Access tier**: mixed — privileged transaction/service records; open-public sanctions and issuer/government records.
- **Detection signature**: **share-transfer instructions and completion records compared to sanctions-announcement and designation dates on owner, asset and effective date revealed a pre-freeze ownership shift; pre/post beneficial ownership identified the closely related recipient**.
- **Corroboration structure**: internal transfer record → public issuer ownership/disclosure → sanctions timeline → German and Cypriot authority response → PwC and Mordashov response. “Bid to elude sanctions” is ICIJ’s supported interpretation; breach findings remain for authorities.
- **Methodology notes**: the parent [data methodology](https://www.icij.org/investigations/cyprus-confidential/leaked-data-journalism-methodology/) documents sanctions matching and account review. The event-window detector is **[inferred]** from the dated facts in ICIJ’s reporting.
- **Impact**: Cyprus opened a criminal investigation of the transaction, and German authorities/TUI rejected the transfer’s validity ([ICIJ follow-up](https://www.icij.org/investigations/cyprus-confidential/cypriot-authorities-face-scrutiny-over-probe-into-russian-billionaires-moves-to-dodge-sanctions/)).
- **Generalization**: for every pending freeze, debarment, insolvency or disclosure rule, compare asset ownership and control immediately before and after the event. Related-party recipients, unchanged managers and retained benefits are recognition cues.

### SUB-ENTRY: Petr Aven’s same-day $5 million payment (2023) — a transfer initiated on the day of EU designation exposed the value of hour-level sanctions chronology

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/)
- **Partner/awards** (lead outlets; prizes): ICIJ, Paper Trail Media, The Guardian and Cyprus Confidential partners; no thread-specific prize identified.
- **What they found**:
  - A $5 million payment connected to Petr Aven was initiated on Feb. 28, 2022, the same day the EU imposed sanctions on him ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/)).
  - Abacus employees served as directors of the investment fund and other Cyprus entities holding Aven interests, including entities linked to a Surrey estate ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/)).
  - Previously unpublished U.K. National Crime Agency court documents supplied an independent official account of the transfer timing ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/)).
- **Finding type(s)**: deadline-adjacent-restructuring; sanctions-evasion-risk; intermediary-enablement.
- **Evidence & sources**:
  - Trust/company ownership files, emails, invoices and wire records [privileged].
  - U.K. National Crime Agency court filings [open-public/request-gated litigation].
  - Cyprus corporate records and EU sanctions notices [open-public].
- **Access tier**: mixed — privileged service/transaction records; public/request-gated court, registry and sanctions sources.
- **Detection signature**: **wire initiation timestamp compared to the sanctions effective date on sender/beneficiary and owner revealed a same-day transfer; public records joined Abacus nominee directors to the asset-holding entities**.
- **Corroboration structure**: leaked wire/instruction → NCA court filing → sanctions notice → registry/director confirmation → subject/provider response. The chronology establishes risk and official concern, while legal liability remains a matter for proceedings.
- **Methodology notes**: no standalone thread methodology; **[inferred]** from the wire–court–sanctions triangulation in the [story](https://www.icij.org/investigations/cyprus-confidential/russian-oligarch-sanctions-petr-aven-luxury/).
- **Impact**: a person associated with Aven later forfeited about $1 million at the center of the U.K. sanctions-evasion case, as recorded on the [Cyprus Confidential project hub](https://www.icij.org/investigations/cyprus-confidential/).
- **Generalization**: preserve timestamps, time zones, settlement dates and rule effective times. Day-level dates can conceal whether a transfer preceded or followed a freeze; compare instruction, booking, value and settlement separately.

### SUB-ENTRY: Abramovich’s hidden Chelsea payments (2023) — offshore records exposed tens of millions in club-related payments omitted from football accounts

- **URL**: [ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/); [2026 enforcement outcome](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-fined-millions-over-secret-payments-under-abramovich-ownership/)
- **Partner/awards** (lead outlets; prizes): The Guardian and The Bureau of Investigative Journalism led this thread under the ICIJ/Paper Trail Media Cyprus Confidential banner ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/)).
- **What they found**:
  - Leaked files showed a decade-long pattern of payments worth tens of millions of pounds through Abramovich-owned offshore vehicles to agents, intermediaries and other football figures ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/)).
  - Beneficiaries reportedly included Eden Hazard’s agent, an associate of manager Antonio Conte and Chelsea officials, while the payments appeared absent from Chelsea’s financial accounts ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/)).
  - Sports-law experts said payments benefiting the club should have counted under financial-fair-play, accurate-accounting and agent-disclosure rules ([ICIJ investigation](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/)).
- **Finding type(s)**: cross-ledger-mismatch; networked-asset-concealment; **off-books-benefit** (a related party pays expenses or consideration benefiting a regulated entity outside its reported accounts).
- **Evidence & sources**:
  - Offshore-company invoices, payment records, ownership files and emails [privileged].
  - Chelsea financial accounts and football regulatory submissions/rules [open-public/request-gated].
  - Player-transfer dates, agent identities and corporate records [open-public].
  - Review by four sports-law experts [constructed].
- **Access tier**: mixed — privileged payment/ownership records; public/request-gated accounts and rules; constructed legal review.
- **Detection signature**: **payments by owner-controlled offshore entities joined to player/manager transactions on beneficiary, amount and date, then compared with club accounts and required agent disclosures, revealed club-benefiting costs outside the regulated ledger**.
- **Corroboration structure**: offshore payment document → beneficial ownership → transfer/beneficiary event → club accounts/regulatory rule → multi-expert review → club/owner response.
- **Methodology notes**: the article describes expert review and the leaked-payment/account comparison; the owner-controlled “shadow ledger” formalization is **[inferred]** from the [thread reporting](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-once-owned-by-roman-abramovich-could-face-punishment-over-secret-payments-experts-warn/).
- **Impact**: in March 2026 the Premier League fined Chelsea £10.75 million, imposed an academy transfer ban and a suspended first-team transfer ban for undisclosed third-party payments under Abramovich; separate Football Association charges remained possible ([ICIJ enforcement follow-up](https://www.icij.org/investigations/cyprus-confidential/chelsea-fc-fined-millions-over-secret-payments-under-abramovich-ownership/)).
- **Generalization**: regulated accounts often exclude expenses paid by owners, affiliates or sponsors. Join external payments to the regulated entity’s acquisitions, employees, vendors and benefits, then compare with consolidated accounts and related-party disclosures.

---

### PROJECT: Swazi Secrets (2024) — Africa’s largest known FIU leak exposed Eswatini as a possible conduit for suspicious gold, banking and political money flows

- **URL**: [Project hub](https://www.icij.org/investigations/swazi-secrets/); [about page](https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/)
- **Partner/awards** (lead outlets; prizes): Distributed Denial of Secrets obtained the records and shared them with ICIJ; ICIJ coordinated 38 journalists across 11 countries ([about page](https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/)). No project-specific prize identified in the reviewed ICIJ pages.
- **What they found**:
  - More than 890,000 internal Eswatini Financial Intelligence Unit records included bank records, police reports, court affidavits and confidential interagency exchanges ([about page](https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/)).
  - Millions of dollars moved from a notorious South African cash-in-transit company through an Eswatini gold-refining company and onward to Dubai; two nominal refineries had little or no operating reality ([about page](https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/), [gold investigation](https://www.icij.org/investigations/swazi-secrets/eswatini-mswati-economic-zone-gold-dubai/)).
  - One refinery involved a son-in-law of King Mswati III, while central-bank and FIU officials raised tax-evasion, illegal-capital-flight and money-laundering concerns ([gold investigation](https://www.icij.org/investigations/swazi-secrets/eswatini-mswati-economic-zone-gold-dubai/)).
  - Separate files showed the central bank resisting Farmers Bank licensing discrepancies while the king’s allies and finance minister intervened around the project ([bank investigation](https://www.icij.org/investigations/swazi-secrets/eswatini-farmers-bank-rijkenberg-belumbu/)).
- **Finding type(s)**: flow-to-asset-conversion; letterbox-substance-gap; state-linked-benefit; **regulator-override** (political or elite pressure displaces an independent regulator’s documented risk judgment).
- **Evidence & sources**:
  - FIU bank records, intelligence reports, police records, affidavits and interagency communications [privileged official records].
  - Corporate registries, bank-license documents, economic-zone records and court material [open-public/request-gated].
  - Payment-flow reconstruction, site visits to purported refineries, interviews and right-of-reply reporting [constructed].
- **Access tier**: mixed — privileged FIU/government leak; public/request-gated corporate, licensing and court records; constructed flow and field verification.
- **Detection signature**: **FIU bank transactions joined across sender, refinery and Dubai recipient revealed the cross-border flow; those companies compared with registry, license and physical-operation evidence exposed phantom substance; regulator objections compared with later political interventions revealed override**.
- **Corroboration structure**: FIU suspicion/transaction → bank or interagency record → registry and license → physical-site check → police/court material where available → subject and authority comment. ICIJ noted that the leak did not reveal the final disposition of some official investigations ([gold investigation](https://www.icij.org/investigations/swazi-secrets/eswatini-mswati-economic-zone-gold-dubai/)).
- **Methodology notes**: [ICIJ’s about page](https://www.icij.org/investigations/swazi-secrets/about-swazi-secrets-investigation/) identifies the record types, source path and collaboration. The payment-path, substance and override detectors are **[inferred]** from the project’s gold and bank stories.
- **Impact**: after publication, Eswatini lawmakers signaled possible press restrictions, and journalists later faced a $9.9 million lawsuit—official reactions that raise retaliation concerns rather than remedial reform ([press-freedom follow-up](https://www.icij.org/investigations/swazi-secrets/lawmakers-signal-crackdown-on-press-freedom-following-swazi-secrets/), [lawsuit follow-up](https://www.icij.org/investigations/swazi-secrets/businessman-targets-eswatini-journalists-with-9-9m-lawsuit/)).
- **Generalization**: FIU or regulator files are leads, not verdicts. Trace transactions to real-world operations, compare licensed purpose with observed behavior, and preserve the sequence from regulator warning to political intervention and final decision.

## Cluster Synthesis

### 1. Recurring evidence-source types

Counts are non-exclusive across the **33 coded entries** above; a sub-entry is counted because it has an independent detection signature even when it inherits the parent leak.

| Evidence-source family | Frequency | What it contributes |
|---|---:|---|
| Privileged leaked provider, bank, registry, SAR, FIU or company records | 33/33 | The non-public ownership, service, transaction or knowledge edge. |
| Public or fee/request-gated corporate, property, securities or licensing records | 27/33 | Legal existence, officers, assets, accounts, operating companies and dates. |
| Government, court, sanctions, disclosure, tax-rule or enforcement records | 26/33 | Risk status, legal duty, public role, official allegation and event timeline. |
| Constructed entity, document, transaction, cohort or signature layer | 24/33 | Makes heterogeneous files searchable and turns documents into comparable edges or populations. |
| Subject, expert, victim, local-source or field verification | 20/33 | Resolves identity and purpose, tests physical substance and supplies context missing from files. |
| Internal or public policy, audit, due-diligence or compliance material | 13/33 | Establishes what the intermediary knew, promised or was required to do. |

The dominant corroboration pattern is therefore not “three outlets found the same record.” It is **privileged edge → constructed relationship → independent public consequence**. The leak establishes who owned, paid or serviced; the public system establishes office, asset, sanction, contract, rule or enforcement context.

### 2. Recurring detection signatures

Manual, non-exclusive coding of primary and strong secondary moves:

| Signature tag | Frequency | Operational form |
|---|---:|---|
| **ENTITY-EXTERNAL-JOIN** | 23/33 | Leak person/entity/role joined to registry, office, sanctions, court, property, securities or disclosure record. |
| **GRAPH-PATH-RECONSTRUCTION** | 16/33 | Traverse owners, nominees, providers, accounts, counterparties and assets until the hidden controller or consequence becomes visible. |
| **EVENT-TIMELINE-DIFF** | 14/33 | Compare service, transfer, restructuring or filing dates with sanctions, rules, warnings, appointments, dismissals or publication. |
| **CROSS-LEDGER-MISMATCH** | 9/33 | Compare the same entity/asset/payment in leak records with disclosures, accounts, tax records or another ledger. |
| **COHORT-PREVALENCE** | 8/33 | Resolve a fixed politician, billionaire, sanctioned or geographic cohort and calculate its penetration by provider or jurisdiction. |
| **RULE-TO-FLOW-MAP** | 6/33 | Attach treaty, tax, disclosure, sanctions or league-rule effects to transaction edges and compare actual with direct-route treatment. |
| **REPEATED-TEMPLATE/CONTROL-CLUSTER** | 5/33 | Shared signatures, provider templates or recurring audit failures convert cases into an institutional pattern. |
| **SUBSTANCE-GAP-TEST** | 5/33 | Compare profit, payments, licensing or declared purpose with employees, office, assets and observed operations. |
| **CORPUS-RELOCALIZATION/CROSS-CORPUS-JOIN** | 3/33 | Re-query old leaks for a new geography/cohort or join two leak generations on entity/provider keys. |

Frequencies measure the coded entries, not all ICIJ output. They are intentionally non-exclusive because the strongest stories compound moves: for example, a sanctions match becomes consequential only after a timeline diff shows continued service, and a hidden-company match becomes a public-interest finding only after a contract, asset or disclosure join.

### 3. Transferable pattern candidates

#### Pattern candidate A — Hidden Controller-to-Consequence Join

- **Mechanics**: normalize leak roles into `person → role → entity → intermediary`; resolve the controller; continue the path into a public consequence such as a contract, property, regulated company, major customer, license or required disclosure.
- **Minimum data**: one ownership/control source, one public consequence dataset, stable identity features, and role-aware graph edges.
- **Recognition cues in any domain**: nominee officers, generic holding-company labels, shared contact data, portfolio-company disclosures that stop above the operating asset, or a declared asset whose counterparty remains hidden.
- **Boundary/falsifier**: a shared address or name alone is not control; require document-level role evidence and an external record establishing the consequence.

#### Pattern candidate B — Deadline Edge Detector

- **Mechanics**: create time-versioned ownership, service and payment events; join them to sanctions, rule changes, filing deadlines, appointments, dismissals, insolvencies or publication; inspect changes inside defined pre/post windows.
- **Minimum data**: event timestamps, effective dates, prior and subsequent controller/service states, and relationship data for recipients.
- **Recognition cues in any domain**: $1 transfers, same-day wires, last-day ownership changes, rapid redomiciliation, new family or affiliate owners, abrupt resignation as agent, or late compliance reviews.
- **Boundary/falsifier**: coincidence is common around known regulatory dates; test whether economic benefit, control and service actually changed and whether the action was lawful wind-down.

#### Pattern candidate C — Enabler Recidivism Matrix

- **Mechanics**: normalize every warning, audit defect, sanctions hit, penalty, SAR, remediation promise and exit event for each intermediary and client; compare later service and retest results.
- **Minimum data**: client/service history, dated risk events, policy or audit controls, and subsequent transactions or filings.
- **Recognition cues in any domain**: repeated “missing source of funds,” service after a designation, SAR only after press exposure, reopened findings, the same defect across branches, or monitorships without behavioral change.
- **Boundary/falsifier**: distinguish pre-existing lawful service and required wind-down from new work; a SAR is suspicion, not proof; an internal audit delivered through a leak is not independent corroboration merely because it is an official-looking document.

#### Pattern candidate D — Shadow-Ledger / Flow-to-Asset Reconstruction

- **Mechanics**: turn invoices, wires, loans and contracts into a dated flow graph; collapse related entities to controllers; join terminal payments to deeds, acquisitions, public contracts, club/player transactions or state assets; compare the result with the regulated or public ledger.
- **Minimum data**: at least partial transactions, controller resolution, terminal asset/event records, and the ledger or disclosure expected to contain the value.
- **Recognition cues in any domain**: round-number chains, equal-value back-to-back loans, related-party payers, owner-paid expenses, property bought shortly after wire exits, or declared losses/turnover incompatible with observed flows.
- **Boundary/falsifier**: amount/date proximity alone does not trace funds; corroborate with accounts, signatories, closing records, loan terms or authoritative allegations, and label unadjudicated source-of-funds claims.

#### Pattern candidate E — Jurisdiction Migration and Substance Gap

- **Mechanics**: encode jurisdictional rules and treaties by date; compare entity migrations and transaction routes with rule changes; calculate profit, assets or payments relative to staff, offices, operating costs and real activity.
- **Minimum data**: entity/residence history, dated rule or treaty table, related-party flows, and basic substance indicators.
- **Recognition cues in any domain**: jurisdiction questionnaires, redomiciliation after reform, treaty-conduit entities, large IP/royalty profit with no staff, many companies at one address, or a licensed plant/refinery with no physical operation.
- **Boundary/falsifier**: low headcount can be commercially legitimate for capital-intensive or IP entities; require the rule benefit, related-party route and absence of relevant decision-making or risk-bearing substance.

### 4. What this platform can run today

**Runnable now with the platform’s existing Offshore Leaks Database/ICIJ integration, GLEIF, OpenSanctions and registry adapters:**

- Entity-to-external joins: resolve Offshore Leaks people, officers, intermediaries and addresses against registries, GLEIF legal entities and OpenSanctions persons/companies.
- Two-hop controller/enabler expansion: find shared nominees, providers, officers, addresses and jurisdictions around a target, with source-document provenance where the ICIJ integration supplies it.
- Provider and jurisdiction risk concentration: for a fixed sanctions/PEP cohort, count matches by service provider, officer, address, legal form and jurisdiction.
- Cross-registry/cross-corpus identity checks: use incorporation numbers, dates, addresses and officers to validate or reject fuzzy name matches.
- Public-record consequence joins where an adapter exists: U.S. securities, procurement, court, lobbying, sanctions and selected corporate-registry records can extend an offshore hit into a public-interest relationship.

**Missing or incomplete for the full canon detectors:**

- Full raw leak corpora and internal document context. The public Offshore Leaks Database is a curated entity/role subset, not the emails, invoices, audits, SAR narratives, bank wires and transaction documents required for many chronology and knowledge findings ([ICIJ database history](https://www.icij.org/investigations/pandora-papers/the-inside-story-of-how-the-offshore-leaks-database-became-a-go-to-resource-on-offshore-finance/)).
- Time-versioned beneficial ownership, agent-service and address histories across all jurisdictions; many registries expose only current state or non-searchable/fee-gated documents.
- Bulk global property/deed data, official asset declarations and historical related-party accounts needed for portfolio and disclosure anti-joins.
- Bank transaction/SAR access and a provenance-preserving narrative-to-transaction extractor. Publicly released FinCEN Files data is partial and carries suspicion-status caveats ([ICIJ data download](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/)).
- A machine-readable, time-versioned treaty/tax-rule graph and entity-level substance data (employees, offices, functions and decision makers).
- A multilingual alias/kinship resolver with script-aware transliteration and hard-identifier scoring sufficient for China-style elite-cohort work.
- A longitudinal compliance-control schema for audits, warnings, promised remediation, retests and service continuation.

The immediate opportunity is therefore **lead generation, not automatic adjudication**: run controller/enabler/risk-cohort joins today; promote only after retrieving the underlying ICIJ document or an independent primary record. The missing layer is less “another name database” than dated transactions, disclosure histories, rules and document-level evidence of institutional knowledge.
