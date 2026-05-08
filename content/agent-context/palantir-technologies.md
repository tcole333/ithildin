# Palantir Technologies
**Stats**: 70 findings, 40 connections, 0 entities
**Dossier**: /dossiers/palantir-technologies

> Palantir Technologies functions as the primary data integration layer between U.S. government agencies and AI-driven decision-making, occupying a structural position where defense procurement, immigration enforcement, tax administration, and healthcare data converge into a single commercial platform operated by a company whose former employees hold senior technology positions at multiple client agencies.

## Key Findings
- **[identity/confirmed]** Palantir Technologies UK Ltd & Eagle Ltd - UK Corporate Structure (2009-10-14) (Finding #4931)
- **[None/confirmed]** Palantir Technologies Inc (CIK 1321655, PLTR on Nasdaq, EIN 68-0551851). Headquarters: 518 17th Street Suite 1015, Denver CO 80202. Large accelerated filer, SIC 7372 (Prepackaged Software). SEC-registered entities include: Palantir Investments LLC (CIK 1554804, DE), Palantir Private Stock 1 LLC (CIK 1825891, DE), Palantir Insider Stock Acquisitions LLC (CIK 1601748, NV). Lobbying confirmed: first registered 2006 via Morgan and Cunningham LLC (Bryan Cunningham, former Deputy Legal Adviser NSC) for Defense, Homeland Security, Law Enforcement. (Finding #2705)
- **[financial/high]** Palantir has received .4B+ in federal government spending across all agencies, with DoD (.3B), HHS (M), DHS (M), DOJ (M), and Treasury (M) as top agencies (Finding #4622)
- **[intelligence/medium]** Palantir FALCON system provides ICE dragnet access to dozens of government and commercial databases including DMV photos, SEVIS student records, IRS data, Social Security files, and license-plate readers (Finding #4666)
- **[intelligence/medium]** Palantir ELITE tool uses Medicaid data from 80M patients to generate ICE deportation targets with confidence-scored dossiers and map-based raid planning (Finding #4668)
- **[financial/high]** Palantir: $30M ImmigrationOS contract (2025-2027) for AI-driven deportation targeting. Has supplied ICE with FALCON and ICM since 2013. New system integrates passport, SSN, IRS, license plate data. 25 new AI use cases added in 6 months. (Finding #4802)

## Top Connections
- **Department of Defense** [financial/strong]: Palantir DoD obligations: 2.31B all-time. Army dominant. FY2025: 1.02B. IDIQ W519TC25D0039.
- **Stephen Miller** [financial/strong]: Miller holds K-K in Palantir stock while directing immigration enforcement policy that drives Palantir contracts
- **Peter Thiel** [corporate/strong]: Co-founder of Palantir; key political donor and backer of JD Vance
- **ICE** [corporate/strong]: Palantir provides FALCON, ICM, ELITE, and ImmigrationOS systems to ICE for immigration enforcement and deportation operations; total contracts at least .3M
- **Alex Karp** [corporate/strong]: CEO of Palantir Technologies; leads company strategy including government contracting
- **Department of Defense** [corporate/strong]: Palantir has .3B+ in DoD contracts including .3B Maven Smart System and B Army Enterprise Agreement
- **DOGE** [corporate/strong]: Multiple ex-Palantir employees hired into DOGE. Palantir helping build IRS mega-API. DOGE restructures agencies where Palantir wins contracts. Structural conflict of interest.
- **Israeli Defense Ministry** [corporate/strong]: Strategic partnership (Jan 2024) providing AI platforms including Gotham. Allegedly powers Lavender/Gospel/Where's Daddy targeting systems. Permanent desk at CMCC in southern Israel.
- **NATO** [corporate/strong]: NATO acquired Maven Smart System in fastest-ever procurement (6 months, sole-source). Extends US military AI to alliance-wide warfighting. Joint Warfare Centre already training on MSS.
- **NHS England** [corporate/strong]: GBP 330M Federated Data Platform contract (Nov 2023, 7 years). Rejected by 75%+ of hospital trusts. BMA urged doctors to pull back after ICE revelations. Heavily redacted contract.
- **NSA** [intelligence/strong]: Snowden docs: Palantir helped build XKEYSCORE, deployed across 3 Five Eyes nations by 2010. GCHQ cited faster analytics. CIA In-Q-Tel provided initial USD 2M seed investment in 2005.
- **8VC** [financial/strong]: 8VC investor in Palantir; Lonsdale co-founded Palantir; Alex Moore was Palantir employee #1
- ... and 28 more

## Open Questions
- What is the specific data pipeline between GEO Group's SmartLINK monitoring system ($2.2 billion contract) and Palantir's ImmigrationOS/ELITE platforms? While the systems are designed for interoperability, no public documentation confirms a direct data feed.
- Has Clark Minor formally recused from decisions affecting Palantir contracts at HHS, given his reported Palantir stockholdings, and if so, what is the scope and verification mechanism of that recusal?
- What role does Palantir play in the Golden Dome missile defense program's command-and-control layer, and do the identified conflicts (Williams/Palantir stock, Barbaccia/former Palantir employee) affect procurement decisions for that program?
- To what extent does the IRS 'unified API' project enable cross-agency data sharing beyond authorized IRS tax administration purposes, and has any Privacy Act system of records notice been published covering the expanded data access?
- What are the terms and scope of the Israeli Defense Ministry 'strategic partnership' announced in January 2024, and which Palantir products are deployed under it?
- Is there a contractual or technical link between Palantir's alleged involvement with Lavender/Gospel/Where's Daddy targeting systems and its U.S. military AI contracts such as Maven?

## Applicable Models
- manufactured-dependency
- enabler-gradient
- bridge-tax
- complexity-as-credential
- private-order
