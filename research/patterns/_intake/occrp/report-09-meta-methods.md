# Report 09 — Meta-Methods: OCCRP's Methodology Infrastructure

**Agent:** meta-methods reviewer (web research and analysis only; no database writes)  
**Date:** 2026-07-29  
**Method:** Direct review of OCCRP, OCCRP ID, Aleph/Aleph Pro documentation, OCCRP's GitHub organizations, project methodology pages, annual reports, policies, and OCCRP's own *Unreported* engineering posts. Every external factual claim carries a URL. Short text in quotation marks is OCCRP's published wording; analytical extrapolations are marked **[inferred]**. Local-capability comparisons are based on the repository files cited in each “Ithildin parity” box and on the user-provided fact that Ithildin already runs a local OpenAleph instance.

**Time boundary:** Aleph is in a product transition. OCCRP's FAQ announced that maintenance of the old open-source Aleph “will end after December 2025” while the public service moves to Aleph Pro; the old documentation and GitHub code remain the best public technical specification of the machinery, but not every old UI detail necessarily describes Aleph Pro in July 2026 (https://aleph.occrp.org/pages/faq).

---

## 1. Aleph: common model, searchable corpus, and cross-reference factory

### 1.1 The important asset is the corpus-plus-workflow, not the search box

Aleph Pro describes itself as a global archive of current and historical databases, documents, leaks, and investigations. It searches people, companies, and other entities across thousands of datasets; can alert users as new data arrives; gives accredited journalists access to leaked evidence; and lets users upload documents and person-of-interest lists into private investigations (https://aleph.occrp.org/). OCCRP's 2024 annual report puts its scale at **4.4 billion-plus entities** and 24,100-plus users (https://www.occrp.org/interactives/annual-report-2024/). Those figures are corpus and community scale, not merely software throughput.

The archive is continuously acquired: OCCRP's quoted formulation is that it “regularly fetch[es] public records from over 200 online sources,” while its FAQ says more than 200 scrapers refresh official datasets weekly or monthly and display update frequency in the dataset description (https://aleph.occrp.org/; https://aleph.occrp.org/pages/faq). A proposed new source can move from a reporter's need to OCCRP ID and then to a new Aleph scraper; OCCRP specifically prioritizes beneficial-ownership, real-estate, and government-payment data (https://aleph.occrp.org/pages/faq). **[inferred]** This closes a valuable loop: a story's coverage gap becomes an acquisition request, then a maintained corpus source, then a reusable lead surface for later stories.

The public record also shows corpus curation rather than indiscriminate hoarding. Aleph says the archive was built alongside reporting projects and concentrates on Central and Eastern Europe, sub-Saharan Africa, South America, and offshore jurisdictions (https://aleph.occrp.org/pages/about). In 2024 the data team also used large language models to extract structured data from public sources for Aleph, while the annual report does not describe the validation protocol for those extractions (https://www.occrp.org/interactives/annual-report-2024/). **[inferred]** Treat the LLM step as candidate extraction, not source authentication, until a more detailed OCCRP methods note establishes otherwise.

### 1.2 FollowTheMoney is the interoperability layer

Aleph normalizes heterogeneous source material into **FollowTheMoney (FtM)**. FtM models people, companies, public bodies, assets, vessels, aircraft, bank accounts, contracts, court cases, payments, ownership, directorship, family, employment, and other relationships as typed entities with properties (https://docs.aleph.occrp.org/users/getting-started/key-terms/). Relationships are modeled as entities too, so a payment or ownership can carry dates, amounts, roles, and source references rather than becoming a bare graph edge (https://docs.aleph.occrp.org/users/getting-started/key-terms/; https://github.com/alephdata/followthemoney).

The published FtM toolchain maps CSV or SQL tables into line-oriented entity JSON, aggregates fragments, validates them, imports Open Contracting data, and exports to CSV, Excel, GEXF, Neo4j/Cypher, or RDF (https://docs.aleph.occrp.org/developers/followthemoney/ftm/). Transliteration is part of comparison support, which matters in the multilingual name space OCCRP inhabits (https://docs.aleph.occrp.org/developers/followthemoney/ftm/). The surrounding open-source stack includes the Aleph application, `alephclient` for API/bulk upload, `memorious` for web collection, and the now-archived `ingest-file` document extractors (https://github.com/alephdata).

### 1.3 “Entity resolution” is best understood as candidate generation plus review

Aleph's public documentation calls its primary workflow **cross-referencing**, not automatic canonical entity resolution. A reporter cleans a spreadsheet, separates entity types, adds discriminating identifiers such as birth dates, aliases, addresses, emails, ID numbers, and phone numbers, maps columns to FtM properties, generates entities, and computes matches against every accessible dataset (https://docs.aleph.occrp.org/users/investigations/cross-referencing/). The key-terms page says this exposes leads and patterns across hundreds of datasets (https://docs.aleph.occrp.org/users/getting-started/key-terms/).

**[inferred]** FtM standardization, transliteration, “similar entity” search, and list cross-reference form a corpus-scale *entity-resolution workflow*, but the public documentation does not justify describing Aleph as a single automatically deduplicated master graph. The documented output is matches for journalistic examination. An autonomous clone should preserve candidates, scores, source datasets, and reject decisions instead of silently merging names.

Investigation workspaces supply the human review surface: users can upload and OCR documents, create or edit entities, draw network diagrams and timelines, cross-reference lists, and share the workspace with selected users or access groups (https://docs.aleph.occrp.org/users/investigations/overview/; https://docs.aleph.occrp.org/users/investigations/network-diagrams/; https://docs.aleph.occrp.org/users/getting-started/key-terms/). OCR and extraction turn scanned documents and emails into searchable text and mentions; emails expose sender, recipient, copied parties, and attachments (https://docs.aleph.occrp.org/users/investigations/overview/).

### 1.4 Dataset families and access classes

Aleph's documented subject families are: news archives; leaks; land registries; gazettes; court archives; company registries; sanctions lists; procurement; financial records; grey literature; document libraries; licenses/concessions; regulatory filings; persons of interest; customs declarations; censuses; and air/maritime registers (https://docs.aleph.occrp.org/users/getting-started/key-terms/).

Its current access model is more precise than “public versus member-gated”:

| Access class | What it contains / permits | Documentary basis |
|---|---|---|
| **Public Materials** | Public records, open data, press, and public-domain material selected and curated for public-interest journalism | https://aleph.occrp.org/pages/content-privacy |
| **Restricted Materials** | Sensitive or non-public material, including some leaks, exposed only to verified users with a demonstrated and proportionate need | https://aleph.occrp.org/pages/content-privacy |
| **Tiered corpus access** | Journalists, NGOs, academics, and activists are manually categorized; authorization depends on professional category and public-interest purpose | https://aleph.occrp.org/pages/content-privacy |
| **Own-data-only users** | Users outside recognized public-interest tiers may store, structure, and cross-reference their own uploads but receive no OCCRP corpus Materials | https://aleph.occrp.org/pages/content-privacy |
| **Project groups** | Invite-only, time-limited workspaces; after closure, uploads are reassessed for retention or transition to another access tier | https://aleph.occrp.org/pages/content-privacy |
| **Anonymous/search boundary** | Some sources are hidden until a user signs in and establishes authorization | https://aleph.occrp.org/search |
| **Bulk/API boundary** | REST API access is public but rate-limited; some datasets have FtM bulk downloads, while specific bulk exports are generally offered to journalists rather than banks, due-diligence firms, or ML researchers | https://aleph.occrp.org/pages/faq |

This is a provenance property as much as a security property: access group, source class, purpose, retention state, and redistribution permission must travel with an item. OCCRP says user uploads are visible only to limited data-team staff for support and not to other editorial staff, while the privacy policy says the service is hosted in Finland (https://aleph.occrp.org/pages/faq; https://aleph.occrp.org/pages/content-privacy).

### 1.5 Ithildin parity: software parity is not corpus parity

**WE ALREADY HAVE**

- A user-provided local OpenAleph deployment and an Aleph-compatible wrapper for entity search, schema/country/collection filtering, relationship expansion, similar-entity queries, collection discovery, and controlled import into the investigation graph (`tools/query_aleph.py`).
- FtM JSON-stream export/import/reconciliation with deterministic identifiers and mappings from local people, organizations, assets, roles, and connections (`tools/ftm_bridge.py`; `docs/modules/network-sanctions.md`).
- A typed entity/relationship graph, multiple registry/court/financial/government corpus tools, source reliability metadata, and evidence-linked findings (`docs/TOOL_REFERENCE.md`; `research/INVESTIGATIVE_METHODOLOGY.md`).

**MISSING OR NOT DEMONSTRATED**

- OCCRP's curated **4.4B+ entity corpus**, protected leaks, hundreds of maintained sources, dataset descriptions, and update operations (https://www.occrp.org/interactives/annual-report-2024/; https://aleph.occrp.org/pages/faq).
- Its access-review organization, cross-newsroom groups, and need-to-know lifecycle for restricted material (https://aleph.occrp.org/pages/content-privacy).
- A reporter-visible, batch match-review queue with preserved accepted/rejected candidates and measured false-match performance at OCCRP-like scale. The local API exposes `similar`; that is not evidence that the full human review operation is mirrored.
- The story-gap → ID request → scraper → curated corpus service loop (https://aleph.occrp.org/pages/faq).

**Bottom line [inferred]:** Ithildin mirrors much of Aleph's *schema and query architecture*. OCCRP's harder advantage is the maintained evidence commons, access governance, and people who convert cross-references into reviewed leads.

---

## 2. OCCRP ID: a research desk with a ticketing front door

### 2.1 Two different public products sit behind “Investigative Dashboard”

OCCRP ID's public catalogue indexes more than 1,000 research sources in more than 180 countries, including company, land, and court registries; entries carry descriptions and access signals such as official source, paywall, or login requirement (https://id.occrp.org/; https://id.occrp.org/databases/). That catalogue is a discovery map, not the records themselves.

The second product is a request service for OCCRP member centers, reporting partners, and collaborators. OCCRP says its researchers and data specialists trace people, companies, real estate, ships, and aircraft; use commercial search engines and databases as well as obscure open sources; obtain original data; and wrangle or analyze it (https://id.occrp.org/). The 2024 annual report records **1,360-plus requests fielded** that year (https://www.occrp.org/interactives/annual-report-2024/). An earlier annual report recorded more than 1,700 requests in 2022 and described a team working in more than ten languages and using flight tracking, satellite imagery, and facial recognition; those are dated 2022 capabilities, not proof that every method is still offered in 2026 (https://www.occrp.org/assets/annual-reports/annual-report-2022-latest.pdf).

### 2.2 What an eligible reporter can ask for

The current homepage expressly offers help with tracking people, companies, and valuable assets; navigating paid and open databases; data acquisition; data wrangling; and analysis (https://id.occrp.org/). Aleph's FAQ routes requests for a new maintained dataset or scraper through ID (https://aleph.occrp.org/pages/faq). **[inferred]** The service therefore spans both a bounded lookup (“find the registry record/owner/asset”) and infrastructure escalation (“this recurring source should become an Aleph dataset”).

The terms make the boundary equally important. A user creates a secure account and submits a request; OCCRP reviews it, may assign one or more researchers, may connect journalists pursuing similar work, and may reuse useful information within the wider OCCRP investigation network (https://id.occrp.org/terms-of-use/). ID warns that third-party information should not be the sole basis of a story and leaves responsibility for lawful journalistic reuse with the requester (https://id.occrp.org/terms-of-use/). Requests are not automatically confidential from all OCCRP collaborators, so the request record itself needs an explicit sharing expectation.

### 2.3 Reconstructed research-desk playbook

OCCRP has not published a complete internal ID standard operating procedure. The following is therefore **[inferred]** from the public service description, terms, source catalogue, and Aleph request path:

1. **Scope and eligibility:** verify public-interest purpose, reporter relationship, target, jurisdiction, desired artifact, deadline, and sensitivity (https://id.occrp.org/; https://id.occrp.org/terms-of-use/).
2. **Triage and collision check:** accept/reject, assign one or more researchers, and detect similar requests that may warrant collaboration (https://id.occrp.org/terms-of-use/).
3. **Source plan:** start from ID's country/source catalogue, then use paid databases, obscure open sources, and local-language search (https://id.occrp.org/databases/; https://id.occrp.org/).
4. **Acquire and preserve:** obtain the original registry/data artifact where possible; record access conditions and retrieval date. This preservation step is **[inferred]**, but follows OCCRP's separate insistence on original documents in fact-checking (https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved).
5. **Wrangle and analyze:** normalize names/identifiers, map relationships, and return results with source limitations rather than a bare answer (https://id.occrp.org/).
6. **Escalate reusable gaps:** request a new scraper/dataset through the data team if the source should serve more than one ticket (https://aleph.occrp.org/pages/faq).
7. **Handoff as leads:** warn that third-party material is not sole proof; the reporter independently verifies and handles publication/legal obligations (https://id.occrp.org/terms-of-use/).

**Failure modes [inferred]:** the ticket omits the actual hypothesis; a commercial aggregator result is mistaken for a primary record; two researchers unknowingly duplicate a search; cross-request sharing surprises a reporter; a one-off answer never becomes a maintained dataset; or a result loses query, timestamp, source jurisdiction, and access terms.

### 2.4 Ithildin parity

**WE ALREADY HAVE:** a broad modular source catalogue, 90-plus source tools, investigation profiles, `search_log`, source-health reporting, queued leads/infra requests, and targeted fan-out search (`docs/TOOL_REFERENCE.md`; `research/OSINT_RESOURCES.md`; `scripts/queue_tools.py`).

**MISSING OR NOT DEMONSTRATED:** a human research-desk service with multilingual and commercial-database access; a reporter-facing ticket form that captures sensitivity, deadline, desired artifact, and sharing consent; duplicate-request collision handling; and a formal ticket-to-maintained-source promotion path comparable to ID → Aleph (https://id.occrp.org/terms-of-use/; https://aleph.occrp.org/pages/faq).

**Cheapest approximation [inferred]:** add an intake schema and make every research request produce a small source plan, provenance bundle, coverage-gap decision, and handoff warning. That captures the desk's reusable discipline without pretending agents replace local researchers or licensed databases.

---

## 3. Member centers and regional editors: a distributed acquisition and publication system

### 3.1 Current network topology

The prompt's “~70” understates the current network page: OCCRP lists **75-plus local member centers and four regional partners**, plus more than 60 other publishing partners in a typical year (https://www.occrp.org/en/about-us/our-global-network). OCCRP calls the structure decentralized: member centers contribute local records, sources, language, and publication reach, while the central platform provides editorial coordination, digital and physical security, data/research infrastructure, and cross-border connections (https://www.occrp.org/en/about-us/our-global-network). Regional partners are explicitly networks of reporters with whom OCCRP regularly collaborates, currently ARIJ, CENOZO, CLIP, and RFE/RL (https://www.occrp.org/en/about-us/our-global-network).

The staff directory shows a second regional layer: editors identified with Africa, Asia, Australia/Pacific, the Balkans, the Baltics/Eastern Partnership, the Caucasus, Central Asia, Central Europe, Europe, Latin America, MENA/North Africa, North America, and Ukraine, alongside research/data, security, member-center, legal, visual, and fact-checking roles (https://www.occrp.org/en/about-us/staff). A Latin America editor's profile, for example, says he coordinates cross-border investigations and brings local partners into global projects (https://www.occrp.org/en/staff/nathan-jaccard).

**[inferred]** Public pages do not expose a formal regional-desk organigram or routing SOP. The defensible model is a mesh with three layers: local centers own context and audience; regional editors identify cross-border overlap and coordinate reporting; central services supply data, research, security, legal, visuals, fact-checking, and publication support.

### 3.2 Editorial standards travel through evidence packets, not a single language

OCCRP's fact-checking account says “every fact in an OCCRP story is checked.” The checker receives an annotated draft plus source documents, notes, and interview material; does not simply trust prior news reporting; and returns to original records for substantive claims (https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved). At the time of that write-up, a small central team worked with part-time checkers, often journalists based at member centers, and a well-supported story could take two or three days while missing evidence could stretch checking into weeks (same URL).

The current editorial FAQ says OCCRP requires high proof, rarely uses anonymous sources, and performs detailed fact-checking over notes, interviews, gathered information, and documents (https://www.occrp.org/en/faq-on-occrps-funding-and-editorial-policies). Project credits show the operational division: the Azerbaijani Laundromat separately credits reporting, research, data analysis, editing, visuals, fact-checking, translation, design, and promotion (https://www.occrp.org/en/project/the-azerbaijani-laundromat).

**[inferred]** The evidence packet is the cross-language control surface. A central editor or checker need not reproduce every local reporting interaction if each material sentence maps to an original document, transcript, named interview, translation, and caveat. Translation is a provenance event: the original-language excerpt, translator, translated text, and ambiguity note should remain together.

### 3.3 Ithildin parity

**WE ALREADY HAVE:** investigation profiles and thread ownership; a shared graph; canonical evidence references; source quotes; claim-type/confidence caps; correction and retraction audit trails; agent queues; and multilingual model capacity (`docs/TOOL_REFERENCE.md`; `research/INVESTIGATIVE_METHODOLOGY.md`).

**MISSING OR NOT DEMONSTRATED:** a 75-center local-source network, physical reporting, newsroom safety/legal support, accountable regional editors, human translation review, and a full annotated-copy fact-check pass. Parallel agents are compute capacity, not member-center reciprocity.

**Cheapest copy [inferred]:** require a “regional handoff packet” containing original-language names and excerpts, translation provenance, jurisdiction-specific source notes, unresolved local questions, and a sentence-to-evidence matrix. The expensive moat—trusted people able to acquire and interpret local records—cannot be copied by workflow alone.

---

## 4. Data desk and leak engineering: three recurring architectures

### 4.1 Laundromats: normalize the ledger, preserve the documents

The Troika Laundromat is OCCRP's clearest published data-engineering account. The source data exceeded 1.3 million transactions and US$470 billion and was supported by tens of thousands of corporate records, contracts, invoices, and emails (https://www.occrp.org/en/project/the-troika-laundromat/about-the-data). OCCRP combined multiple leaks with its own data, shared the result with more than 20 partner organizations, placed documents into Aleph, and built a separate structured transaction system (same URL).

The transaction records arrived in more than 20 formats, in Lithuanian and English. OCCRP wrote custom parsers, normalized company-name variants, converted currencies, extracted and verified account numbers and addresses, and loaded the result into PostgreSQL; it explicitly warned that aggregated totals remained approximate because no cleaning system resolves every discrepancy (https://www.occrp.org/en/project/the-troika-laundromat/about-the-data). This is a two-store pattern:

1. **Document store:** immutable records, OCR/search, surrounding contracts and communications, source context.
2. **Analytical ledger:** parsed transaction rows, normalized parties/accounts/currencies, queryable flows, and reproducible aggregates.

The smaller Azerbaijani Laundromat published a searchable database derived from nearly 17,000 payments involving four core UK companies between 2012 and 2014 and warned that appearance in the data does not itself establish wrongdoing (https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-raw-data). OCCRP's general laundromat FAQ describes discovery as iterative graph expansion: start with bank or court/law-enforcement records, identify company nodes, trace flows, and gradually reveal the system; legitimate payments may coexist with laundering (https://www.occrp.org/en/project/laundromats-explained-how-shell-companies-are-used-to-launder-money/frequently-asked-questions).

**Reusable doctrine [inferred]:** never let normalized rows replace source documents; make every transaction traceable to file/page/row; preserve the parser and exception log; distinguish exact amounts from currency-normalized estimates; and treat network position as a lead, not culpability.

### 4.2 Suisse Secrets: enrich a sparse index instead of hallucinating a ledger

Suisse Secrets contained more than 18,000 Credit Suisse accounts and 30,000 holders, with account numbers, names, open/close dates, and maximum balances—but no account type or transaction history (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak). More than 163 journalists at 48 outlets in 39 countries worked on it; raw data was not released because an account is not evidence of wrongdoing and privacy required a compelling public-interest case (same URL).

Authentication and enrichment were layered. Reporters interviewed knowledgeable insiders; matched dozens of account numbers in external documents; matched more than 150 birth dates; cross-checked accounts against earlier Troika/Azerbaijani data; and obtained confirmations from some subjects (same URL). OCCRP's own engineering/editorial retrospective says reporters cross-referenced account holders against sanctions, risk, and PEP lists in Aleph, then expanded families, shareholders, corporate links, and event timelines (https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).

OCCRP's quoted boundary is that the leak was used “only as a starting point” (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak). **[inferred]** A sparse leak supports two honest story modes: link balance/account timing to independently documented events or money sources, or demonstrate a cross-case pattern among independently verified high-risk clients. It does **not** support invented transfers, present-day account status, tax-crime claims, or conclusions about funds' origin.

### 4.3 NarcoFiles: authenticate a hacked institutional corpus at multiple levels

NarcoFiles originated in a five-terabyte leak from Colombia's prosecutor's office, obtained after a hack by Guacamaya and distributed through Distributed Denial of Secrets and Enlace Hacktivista. It contained more than seven million emails plus audio, PDFs, spreadsheets, and calendars; OCCRP coordinated more than 40 media outlets in 23 countries (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know).

Reporters authenticated the corpus by checking case numbers against public records, identity data against databases, companies and owners against registries, and officials' names against official sources. They then corroborated story claims through freedom-of-information records, hundreds of other documents and databases, and interviews with police, criminals, experts, and victims; only a small share of story evidence came directly from the leak (same URL). The team withheld information that could endanger third parties or active cases and sent detailed questions to the prosecutor's office (same URL).

OCCRP's leak retrospective adds source-handling and integrity checks: it does not pay sources; it stops when a source appears to retain live system access; it avoids direct dealings with hackers; and it inspects email headers, timestamp gaps, missingness, and possible cherry-picking (https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c). **[inferred]** There are four distinct propositions to verify: the archive came from the claimed institution; a particular artifact existed in that archive; the artifact says what the reporter claims; and the allegation inside the artifact is independently true. Passing one level does not pass the next.

### 4.4 Published engineering practice beyond the flagship leaks

- **Forensic archive processing:** OCCRP's “How to eat an elephant” describes hashing with `hashdeep`; preserving originals read-only; separating original, processing, and analyst copies; unpacking Cellebrite/EnCase/ISO formats; deduplicating files and excluding known operating-system files; mapping devices; using a controlled access room and encrypted transfers; and exposing curated subsets in Aleph. It reports that a breadth-first pass took roughly six to eight weeks and concludes depth-first triage would have produced earlier reporting value (https://medium.com/occrp-unreported/how-to-eat-an-elephant-9da7e146e475).
- **Name variants:** OCCRP built Synonames from Wikipedia/Wikidata across 41 languages and four scripts, producing roughly 20,000 pairs for Elasticsearch synonym matching while documenting that aliases and transliterations remain incomplete (https://medium.com/occrp-unreported/an-%D0%B0%D0%BB%D0%B5%D0%BA%D1%81%D0%B0%D0%BD%D0%B4%D1%80-by-any-other-name-819525c82d8c).
- **Dubai property:** a published data account describes millions of records, a shared merge identifier, de-duplication, reporter collaboration, a Datasette interface for non-SQL users, land-department checks, and final ownership proof from contracts/invoices rather than map proximity alone (https://medium.com/occrp-unreported/verifying-who-owns-property-in-dubai-takes-lots-of-data-and-persistence-and-partners-d76ecff77e96).
- **Offshore owner → UK property:** OCCRP downloaded the overseas-entities register, cross-referenced owners in Aleph, and scraped land-registry material to join owners to properties (https://medium.com/occrp-unreported/new-legislation-reveals-u-k-offshore-property-ownership-sort-of-2da278a2b2aa).
- **Publication channel:** OCCRP launched *Unreported* specifically to document editorial, data, research, design, security, and engineering work behind investigations (https://medium.com/occrp-unreported/introducing-occrp-unreported-30ea1b43904a).

### 4.5 Ithildin parity

**WE ALREADY HAVE:** corpus/search tooling, OCR-oriented acquisition guidance, typed payments and ownership links, normalized event dates, evidence-linked findings, source reliability, multiple registry and sanctions sources, and regenerable analytical sidecars (`docs/TOOL_REFERENCE.md`; `research/INVESTIGATIVE_METHODOLOGY.md`; investigation-specific sidecar documentation).

**MISSING OR NOT DEMONSTRATED:** a standard immutable leak manifest with hashes and custody events; file-level dedupe/known-file filtering as a routine intake gate; parser version and transaction-to-source-row lineage in one interface; controlled review-room workflows; explicit missingness/cherry-picking analysis; and large-cohort secure collaboration comparable to Suisse Secrets or NarcoFiles.

**Cheapest copy [inferred]:** create a manifest-and-lineage contract before adding more parsing sophistication: artifact hash, source/custody class, original path/ID, parser version, row locator, transformation log, exclusion reason, and linkage confidence.

---

## 5. Verification, response, legal risk, and corrections

### 5.1 Leak authentication doctrine

OCCRP's published cases yield a layered verification stack:

1. **Transport/custody:** record who transmitted the material and whether the source still has live unauthorized access; OCCRP says it stops in that live-access scenario (https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).
2. **Archive integrity:** hash originals, preserve read-only copies, inspect metadata/headers/timestamps, deduplicate, and account for gaps or suspicious selection (https://medium.com/occrp-unreported/how-to-eat-an-elephant-9da7e146e475; https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).
3. **Institutional authenticity:** match case numbers, officials, account numbers, IDs, dates, and source-system conventions to independent official records (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know; https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak).
4. **Artifact authenticity:** seek originals, parallel records, signatures, headers, and subject/insider confirmation. OCCRP has publicly distinguished original bank slips from electronic documents it could not independently verify (https://www.occrp.org/en/project/plunder-and-patronage-in-the-heart-of-central-asia/a-promise-cut-short).
5. **Claim corroboration:** establish the allegation with registries, court records, FOI returns, interviews, and other independent evidence; a real prosecutor email proves the email existed, not that every allegation inside it was true (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know).
6. **Selection audit:** describe what the leak omits and whether a source could have cherry-picked it; do not infer prevalence from an unknown sampling frame (https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).

### 5.2 Fact-checking as an independent provenance audit

OCCRP's fact-checker works against the annotated draft and its documentary packet, checks every substantive assertion, and returns to original records instead of treating other journalism as proof (https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved). The current FAQ confirms detailed review of notes, interviews, information, and documents (https://www.occrp.org/en/faq-on-occrps-funding-and-editorial-policies).

**[inferred]** The autonomous analogue is a fresh agent/context that receives claims and evidence, not the drafting agent's hidden reasoning. It should verify entailment, identity, date, amount, translation, attribution, source independence, contrary evidence, and whether the prose outruns the source.

### 5.3 Subject response / “right of reply”

OCCRP has not surfaced a single public rulebook specifying deadlines or a universal letter template, so those details should not be invented. Its practice is nevertheless documented. OCCRP expressly rejected a claim that it did not seek a right of reply and pointed to extensive pre-publication quotes from a president's advisers plus the president's refusal to speak (https://www.occrp.org/en/announcement/attack-on-poroshenko-reporting-is-pr-not-analysis). Suisse Secrets sent detailed questions to Credit Suisse and published the bank's response and OCCRP's answer; NarcoFiles sent questions to the prosecutor's office (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak; https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know).

**[inferred]** The reusable gate is: enumerate the material allegations and evidence; identify every adversely portrayed subject; send specific questions with a reasonable deadline and secure channel; preserve sent text and delivery state; record response/nonresponse/refusal; test factual answers against the evidence; and represent denials fairly without allowing them to erase documented facts.

### 5.4 Libel and hostile-jurisdiction handling

Suisse Secrets shows jurisdiction as a publication constraint: Swiss partner Tamedia did not participate because Swiss banking-secrecy law could expose journalists handling leaked bank data to prosecution (https://www.occrp.org/en/feature/we-investigate-corruption-swiss-law-calls-that-a-crime; https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak). This is not a clever way to evade law; it is evidence that partner choice, data access, publication location, and counsel must be assessed per jurisdiction.

OCCRP and the Cyrus R. Vance Center launched Reporters Shield to provide training, pre-publication review, and legal defense to public-interest reporting organizations facing defamation and related claims, using counsel across multiple jurisdictions (https://www.occrp.org/en/announcement/occrp-and-partners-announce-reporters-shield). **Boundary:** that announcement documents a network defense program, not OCCRP's entire internal pre-publication legal SOP. **[inferred]** An agent may generate a jurisdictional risk memo and evidence index, but counsel—not a model—must make privilege, defamation, privacy, source-protection, and publication decisions.

### 5.5 Corrections

OCCRP's corrections process asks a requester to identify the exact material, URL, reason, supporting material, and contact information; the editor in chief makes the final decision (https://www.occrp.org/en/corrections-policy). Confirmed errors prompt an article correction and formal note, unclear but accurate wording may receive a clarification note, and some cases receive an editor's note (same URL).

### 5.6 Ithildin parity

**WE ALREADY HAVE:** mandatory evidence references/source quotes, claim-type confidence caps, independence rules (“three copies of one document” are not corroboration), immutable evidence corrections, disputes/retractions, source reliability, and adversarial pre-publication methodology (`docs/TOOL_REFERENCE.md`; `research/INVESTIGATIVE_METHODOLOGY.md`).

**MISSING OR NOT DEMONSTRATED:** a standard custody/hash manifest for leaks; a dedicated right-of-reply record tied to each material claim/subject; deadline/delivery/response fields; a legal-review gate; translation attestations; and a public-facing correction-note workflow. Repository search surfaced correction/retraction machinery for evidence, but not a complete subject-response system.

**Cheapest copy [inferred]:** add response and authentication checklists before expanding legal automation. The data model can record what was asked and answered; it must not simulate consent, legal advice, or human fairness judgment.

---

## 6. Tools and side projects: what is current, historical, or misattributed

### 6.1 Aleph/FtM ecosystem

OCCRP and collaborators open-sourced the prior Aleph stack and continue to publish FtM, `alephclient`, `memorious`, and related libraries under the `alephdata` organization (https://github.com/alephdata). The organization describes Aleph as document/data search, FtM as the investigative entity model, `alephclient` as the bulk API client, and `memorious` as a document/structured-data scraper (https://github.com/alephdata). The old `ingest-file` repository is archived, and OCCRP's FAQ announced that maintenance of the old open-source Aleph would end after December 2025 during transition to Aleph Pro (https://github.com/alephdata/ingest-file; https://aleph.occrp.org/pages/faq).

**[inferred]** Forkability and current upstream support are now separate questions. Ithildin's OpenAleph deployment preserves architectural independence, but it should not assume every Aleph Pro feature will land in the old open-source line.

### 6.2 OCCRP's smaller reporter/data utilities

The OCCRP GitHub organization exposes practical investigation exhaust: `datasurvey` inventories a file directory; `cronosparser` parses CronosPro/CronosPlus databases; `airtraffic` packages an air-traffic analysis environment; `clcnn-classifier` demonstrates neural text classification over Aleph data; `COVID-19-spending-2020` preserves a cross-European collaborative spending dataset; and the archived `id-frontend` shows a prior ID ticketing interface (https://github.com/occrp/datasurvey; https://github.com/occrp/cronosparser; https://github.com/occrp/airtraffic; https://github.com/occrp/clcnn-classifier; https://github.com/occrp/COVID-19-spending-2020; https://github.com/occrp/id-frontend). Repository archival/age varies, so these are patterns and artifacts, not a supported product catalogue.

### 6.3 VIS: historically important, no longer a live standalone service

Visual Investigative Scenarios (VIS) was designed as ID's visual complement: it translated complex international business/crime networks into a common visual language with contributions from OCCRP/GIJN members, programmers, and visual artists (https://www.occrp.org/en/feature/history-of-occrp). OCCRP reported its launch and adoption in 2013 and described it as a prominent visualization tool through 2015 (https://www.occrp.org/en/announcement/occrp-2013-end-of-year-letter; https://www.occrp.org/en/announcement/so-long-2015). As of this review, `https://vis.occrp.org/` redirects to OCCRP's main site, whose current tools footer lists Aleph and ID, not VIS (https://vis.occrp.org/; https://www.occrp.org/en).

**[inferred]** VIS's durable contribution is not its present availability but its visual grammar: ownership, payment, association, and proxy relationships become shareable investigative scenarios. Aleph workspaces' network diagrams now occupy part of that role (https://docs.aleph.occrp.org/users/investigations/network-diagrams/).

### 6.4 Sanctions: correction to the requested label

No first-party OCCRP or GitHub source located in this review identifies an OCCRP product formally named **“Sanctions Explorer”** (current tools page and repository organizations checked: https://www.occrp.org/en; https://github.com/occrp; https://github.com/alephdata). I therefore do not attribute that product name to OCCRP. OCCRP's verified sanctions machinery is:

- sanctions lists as a first-class Aleph dataset family and cross-reference target (https://docs.aleph.occrp.org/users/getting-started/key-terms/; https://docs.aleph.occrp.org/users/investigations/cross-referencing/);
- the **Russian Asset Tracker**, built from land records, company registries, and offshore leaks, with assets included only when researchers found clear ownership evidence; its final August 2022 update documented more than US$19.8 billion (https://www.occrp.org/interactives/russian-asset-tracker/en/; https://www.occrp.org/en/project/russian-asset-tracker);
- sanctions-oriented story interactives such as the Iran sanctions/shipping map, which visualizes vessel movements and AIS gaps rather than serving as a general sanctions database (https://www.occrp.org/interactives/iran-sanctions-map/en/).

The Russian Asset Tracker is especially methodologically revealing: OCCRP ID handled research, a data specialist structured the output, fact-checkers reviewed it, and more than two dozen media/research partners supplied jurisdictional coverage; the project also disclosed its use of Panama/Pandora/Paradise/FinCEN leak collaborations (https://www.occrp.org/en/project/russian-asset-tracker). **[inferred]** This is a verified-asset register whose inclusion rule is documentary ownership evidence, not a sanctions-screening product.

### 6.5 Ithildin parity

**WE ALREADY HAVE:** FtM/OpenAleph, graph and timeline views, sanctions/OpenSanctions tooling, air/ship/infrastructure sources, and evidence-linked relationship visualization (`docs/modules/network-sanctions.md`; `docs/modules/osint-infra.md`; `web/src/pages/viz-demo.astro`).

**MISSING OR NOT DEMONSTRATED:** a stable reporter-facing visual scenario editor; a public asset-tracker inclusion protocol and update/sunset banner; a maintained, documented set of small file-forensics utilities; and upstream support parity with Aleph Pro.

**Cheapest copy [inferred]:** adopt Russian Asset Tracker's explicit inclusion test—documentary evidence of ownership/control—and VIS's typed visual grammar. Do not build a new “Sanctions Explorer” merely to match an unverified name.

---

## 7. Funding provenance as a methodological control (one paragraph)

OCCRP applies a provenance/firewall doctrine to its own funding: it publicly discloses institutional donors through its website, annual reports, and tax statements; may reject funds that threaten independence or create conflicts; does not accept money for specific stories or donor story approval; and says donors do not know, review, or influence specific stories (https://www.occrp.org/en/gift-and-donation-acceptance-policy). Its updated editorial FAQ discloses a mixed governmental/foundation/individual funding model, explains grant limitations and core funding, and says it diversified donors and built guardrails (https://www.occrp.org/en/faq-on-occrps-funding-and-editorial-policies). **Methodological relevance [inferred]:** record funder, restriction, time period, and firewall for any source-acquisition program so later users can test whether corpus coverage reflects donor geography; disclosure is not itself proof that bias is absent.

---

# SYNTHESIS

## A. Bottom-up evidence-source taxonomy (15 categories)

These categories are derived from the acquisition paths above rather than OCCRP's editorial beats. Frequency labels are portfolio-level judgments **[inferred]**.

| # | Evidence source | What arrives | Typical acquisition / verification | OCCRP exemplars | Frequency |
|---|---|---|---|---|---|
| 1 | Company and beneficial-ownership registries | filings, directors, shareholders, legal addresses, identifiers | open/paid registry; preserve filing and vintage; cross-register identifiers | Aleph company registries; Russian Asset Tracker (https://docs.aleph.occrp.org/users/getting-started/key-terms/; https://www.occrp.org/en/project/russian-asset-tracker) | **Dominant** |
| 2 | Land/property/cadastral records | parcel, owner, price, contract, map reference | registry/scrape/partner; contract is stronger than spatial inference | Dubai/property work; Asset Tracker (https://medium.com/occrp-unreported/verifying-who-owns-property-in-dubai-takes-lots-of-data-and-persistence-and-partners-d76ecff77e96; https://www.occrp.org/en/project/russian-asset-tracker) | **Dominant** |
| 3 | Court, prosecutor, and law-enforcement files | complaints, evidence, judgments, case IDs, investigative correspondence | portals/FOI/leak; distinguish allegation, charge, and adjudication | NarcoFiles; Aleph court archives (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know; https://docs.aleph.occrp.org/users/getting-started/key-terms/) | **Dominant** |
| 4 | Government gazettes/regulatory/licensing records | appointments, concessions, licenses, official notices | official publication; record language/date/version | Aleph categories and ID catalogue (https://docs.aleph.occrp.org/users/getting-started/key-terms/; https://id.occrp.org/databases/) | Common |
| 5 | Procurement, spending, customs, and payment disclosures | awards, suppliers, shipments, state payments | scrape/bulk/FOI; normalize party IDs and dates | Aleph prioritized sources and categories (https://aleph.occrp.org/pages/faq; https://docs.aleph.occrp.org/users/getting-started/key-terms/) | Common |
| 6 | Sanctions, PEP, and risk lists | named persons/entities/assets and program basis | list cross-reference; verify identity and designation vintage | Suisse Secrets screening; Aleph sanctions (https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c; https://docs.aleph.occrp.org/users/getting-started/key-terms/) | Common |
| 7 | Transport and luxury-asset registries | vessels, aircraft, movements, ownership clues | registries/AIS/flight data; identify gaps and proxy owners | ID asset tracing; Russian Asset Tracker; Iran map (https://id.occrp.org/; https://www.occrp.org/en/project/russian-asset-tracker; https://www.occrp.org/interactives/iran-sanctions-map/en/) | Common |
| 8 | Leaked transaction ledgers | rows of payments with accounts, counterparties, currencies, dates | custom parse; normalize; reconcile to source row; independently explain purpose | Troika/Azerbaijani Laundromats (https://www.occrp.org/en/project/the-troika-laundromat/about-the-data; https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-raw-data) | Occasional, flagship |
| 9 | Sparse leaked account/customer indexes | holders, account IDs, balance/date snapshots without flows | authenticate fields; x-ref; build case independently; privacy/public-interest gate | Suisse Secrets (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak) | Occasional, flagship |
| 10 | Leaked email/document corpora | emails, attachments, PDFs, office files, metadata | headers/timestamps/gaps; institutional identifiers; independent claim corroboration | NarcoFiles (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know) | Occasional, flagship |
| 11 | Forensic device/archive images | full file systems, chats, media, deleted/duplicate/system files | hash, read-only original, dedupe, known-file filter, controlled access | “How to eat an elephant” (https://medium.com/occrp-unreported/how-to-eat-an-elephant-9da7e146e475) | Rare, high-cost |
| 12 | Commercial research databases | aggregated company, person, asset, litigation, or risk data | licensed ID search; return as lead; obtain primary record | OCCRP ID (https://id.occrp.org/; https://id.occrp.org/terms-of-use/) | Common, desk-mediated |
| 13 | Interviews and subject responses | firsthand account, denial, explanation, confirmation, local context | identity/motive assessment; recording/notes; documentary test | Suisse Secrets/NarcoFiles; right-of-reply example (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak; https://www.occrp.org/en/announcement/attack-on-poroshenko-reporting-is-pr-not-analysis) | **Dominant** |
| 14 | Member-center local knowledge and records | local-language artifacts, sources, physical observations, inaccessible registries | trusted local reporter + regional coordination + central fact-check | network model (https://www.occrp.org/en/about-us/our-global-network) | **Dominant / differentiating** |
| 15 | Prior reporting and investigative archives | leads, names, prior hypotheses, known document references | re-acquire original evidence; do not treat repeated reporting as independent proof | Aleph news/grey literature; OCCRP fact-check doctrine (https://docs.aleph.occrp.org/users/getting-started/key-terms/; https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved) | **Dominant as lead source** |

## B. Acquisition playbooks (9)

### 1. Corpus-first list cross-reference

**Trigger:** a list of people, companies, accounts, ships, addresses, or identifiers arrives.  
**Steps:** clean and type columns → preserve source/vintage → add discriminating identifiers → map to FtM → compute matches only against authorized datasets → review candidate pairs → save accepted and rejected decisions → open corroboration leads (https://docs.aleph.occrp.org/users/investigations/cross-referencing/).  
**Failure modes:** name-only false positives; transliteration collisions; access-restricted sources silently omitted; automatic merge destroys ambiguity; “on a list” becomes guilt.

### 2. Laundromat ledger reconstruction

**Trigger:** leaked bank records span many files/formats/languages.  
**Steps:** hash and preserve originals → inventory formats → parse each format separately → attach row-to-artifact lineage → normalize accounts/names/currencies without overwriting raw values → load analytical ledger → join to contracts/emails/registries → trace flows → publish approximation and coverage caveats (https://www.occrp.org/en/project/the-troika-laundromat/about-the-data).  
**Failure modes:** double-counted duplicates; mistaken debit/credit direction; correspondent bank confused with beneficiary; currency conversion without date/rate; aggregate presented as exact; flow mistaken for criminal purpose.

### 3. Sparse account-leak enrichment

**Trigger:** a leak contains holders and balance/date snapshots but no transactions.  
**Steps:** describe fields and missing fields → authenticate account IDs and DOBs externally → screen sanctions/PEP/risk lists → expand family/corporate/proxy networks → align account dates with independently documented events → apply public-interest/high-risk threshold → seek subject/bank response → withhold raw private data (https://www.occrp.org/en/project/suisse-secrets/what-is-suisse-secrets-everything-you-need-to-know-about-the-swiss-banking-leak; https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).  
**Failure modes:** implying illegal conduct from account ownership; treating maximum balance as transaction volume; assuming current/open/unfrozen status; selection bias; family relation treated as control.

### 4. Hacked institutional corpus authentication

**Trigger:** a mass email/document leak is attributed to an agency or company.  
**Steps:** document transmission and source boundary → hash/inventory → inspect headers/timestamps/gaps → validate institutional case numbers, personnel, IDs, and formats → independently corroborate each story claim → minimize harm to uninvolved people/live cases → obtain institution/subject response (https://www.occrp.org/en/project/narcofiles-the-new-criminal-order/what-is-narcofiles-the-new-criminal-order-everything-you-need-to-know; https://medium.com/occrp-unreported/new-normal-how-occrp-reporters-use-mass-data-leaks-to-expose-secrecy-b1962e067d2c).  
**Failure modes:** authentic archive, false allegation; manipulated subset; missing attachments; ongoing unauthorized access; metadata lost during extraction; publication endangers a source or investigation.

### 5. Depth-first forensic archive triage

**Trigger:** a multi-device archive is too large to process before reporting must begin.  
**Steps:** immutable original and hash manifest → device/file inventory → prioritize the most probative device/date/person → unpack and dedupe → filter known system files → extract a narrow review set → provide controlled access and checkout log → expand only after the first hypothesis is tested (https://medium.com/occrp-unreported/how-to-eat-an-elephant-9da7e146e475).  
**Failure modes:** breadth-first processing delays all value; analysts touch originals; duplicate/system files swamp search; copied subsets lose device provenance; access controls impede but do not audit.

### 6. ID registry/asset request

**Trigger:** a reporter needs a record, owner, company, ship, plane, or source in an unfamiliar jurisdiction.  
**Steps:** hypothesis-rich ticket → source catalogue and duplicate-request check → assign language/jurisdiction researcher → search licensed and open sources → acquire primary artifact → normalize/analyze → deliver evidence and limits → escalate reusable source gap to Aleph ingestion (https://id.occrp.org/; https://id.occrp.org/terms-of-use/; https://aleph.occrp.org/pages/faq).  
**Failure modes:** vague ticket; aggregator substituted for primary record; access terms omitted; result shared beyond expected circle; repeated lookup never becomes maintained infrastructure.

### 7. Distributed local verification

**Trigger:** a target network crosses several countries or languages.  
**Steps:** decompose by jurisdiction → pair local member centers with regional/central editor → share a minimal common entity/identifier pack → collect original-language evidence → translate with provenance → centralize claims/evidence → independent fact-check → coordinated right of reply and publication (https://www.occrp.org/en/about-us/our-global-network; https://www.occrp.org/en/feature/occrps-fact-checking-process-the-first-time-is-torture-for-everyone-involved).  
**Failure modes:** central team erases local nuance; parallel teams duplicate or expose one another; translations flatten legal meaning; inconsistent thresholds; embargo/access leak.

### 8. Story-to-corpus flywheel

**Trigger:** a story repeatedly needs the same public source or creates a cleaned dataset useful beyond one investigation.  
**Steps:** document the gap → file ID/data request → evaluate public-interest reuse and access constraints → build/test scraper or mapping → add dataset description, category, jurisdiction, provenance, update cadence, and owner → monitor freshness → expose through authorized Aleph tiers (https://aleph.occrp.org/pages/faq; https://aleph.occrp.org/pages/content-privacy).  
**Failure modes:** scraper silently stales; terms/access class absent; changed schema corrupts mapping; story-specific inferences are published as source facts; no sunset banner.

### 9. Pre-publication fairness/legal/correction gate

**Trigger:** a finding materially harms a person or organization, exposes sensitive data, or will publish across jurisdictions.  
**Steps:** sentence-to-source fact-check → authentication/independence review → specific right-of-reply questions and preserved delivery → incorporate verified corrections and fair denial → jurisdiction/counsel review → publication note for methods/limitations → standing correction intake and dated notes (https://www.occrp.org/en/announcement/attack-on-poroshenko-reporting-is-pr-not-analysis; https://www.occrp.org/en/announcement/occrp-and-partners-announce-reporters-shield; https://www.occrp.org/en/corrections-policy).  
**Failure modes:** vague “any comment?” outreach; deadline too short; denial omitted; legal review treated as fact-check; correction silently overwrites history; safety concerns discovered after publication.

## C. Provenance checklist for an autonomous agent (15 points)

Before promoting a source-derived finding:

1. **Artifact identity:** canonical source/document ID, original URL or custody reference, retrieval timestamp, and jurisdiction are recorded.
2. **Acquisition class:** open, registry, FOI, licensed, leaked, partner-supplied, scraped, or forensic; terms and redistribution limits travel with it.
3. **Custody and integrity:** original is immutable; cryptographic hash and every transfer/transformation are logged for non-public material.
4. **Access class:** public/restricted/project/own-data status, authorized group, purpose, retention rule, and downstream sharing rule are explicit.
5. **Source system and vintage:** issuing institution, dataset version/date range, update cadence, and staleness are stated.
6. **Raw-to-derived lineage:** parser/mapping version and exact file/page/sheet/row/message locator connect every structured value to the source.
7. **Raw values preserved:** normalization, transliteration, currency conversion, dedupe, and inferred identifiers never overwrite source text.
8. **Entity match review:** match keys, candidate score/reason, accepted/rejected state, reviewer, and conflicting identifiers are preserved; no name-only auto-merge.
9. **Coverage and missingness:** known gaps, excluded files/rows/jurisdictions, possible cherry-picking, and denominator/sampling limits are tested.
10. **Artifact versus allegation:** separately assess institutional authenticity, artifact authenticity, correct interpretation, and truth of the claim inside it.
11. **Independent corroboration:** count independent originating sources, not mirrors or reporting that repeats the same document; explain what each source proves.
12. **Translation provenance:** retain original-language excerpt, translator/tool, translated text, and ambiguity or legal-term notes.
13. **Claim discipline:** direct quote/paraphrase/inference/synthesis and confidence conform to the evidence; association, account holding, or dataset presence is not culpability.
14. **Fairness, safety, and legal state:** affected subjects, questions sent, delivery/deadline, response/nonresponse, harm minimization, and required human/counsel review are recorded.
15. **Audit and correction path:** fact-checker can reproduce the claim; versioned methods/results are retained; corrections, clarifications, disputes, and retractions remain visible.

## D. Cross-walk: what Ithildin can copy cheapest

| OCCRP machinery | Ithildin status | Cheapest useful copy | Cost / boundary |
|---|---|---|---|
| FtM entity model and Aleph query surface | **Already present** via local OpenAleph, `query_aleph.py`, and `ftm_bridge.py` | Preserve upstream schema compatibility and test round trips | Low; do not call this corpus parity |
| Curated dataset descriptions and access classes | **Partial** source docs/reliability exist; Aleph-like public/restricted/project lifecycle not demonstrated | Add source vintage, cadence, steward, access/redistribution class, and sunset state | Low |
| Batch cross-reference review | **Partial** similar search and reconciliation exist | Add candidate review queue, reject memory, keys used, and sampled false-match rate | Low–medium |
| ID ticket discipline | **Partial** leads/infra queues exist | Intake template: hypothesis, jurisdiction, artifact, deadline, sensitivity, sharing, collision check | Low |
| ID → scraper → corpus flywheel | **Partial** infra/source ingestion exists | Make every ticket close with “one-off / add source / monitor source,” owner, and cadence | Low |
| Annotated fact-check packet | **Strong partial** source quotes, evidence refs, audits exist | Export sentence/claim → evidence → quote → caveat → translation matrix for fresh-context review | Low |
| Leak integrity manifest | **Partial** evidence refs exist; routine custody/hash contract not demonstrated | Standard manifest with hashes, custody, parser, exclusions, row lineage, and missingness audit | Low–medium |
| Right of reply | **Gap** dedicated workflow not surfaced | Add subject/claim/question/delivery/deadline/response fields and publication gate | Low technically; human/editorial work remains |
| Corrections transparency | **Strong internal partial** immutable corrections/retractions exist | Generate public dated correction/clarification notes from reviewed audit events | Low |
| VIS / verified-asset inclusion rule | **Partial** visualizations and typed edges exist | Require documentary ownership/control proof before public asset inclusion; expose source on edge | Low |
| 200+ maintained scrapers / 4.4B+ corpus | **Missing at OCCRP scale** | Prioritize sources arising repeatedly from investigations; publish freshness honestly | High and ongoing |
| Multilingual human research desk | **Missing** | Use structured agent triage, then route irreducibly local questions to human actions | High; commercial licenses and local judgment cannot be faked |
| 75+ member-center network | **Missing / non-software moat** | Produce regional handoff packets and cultivate partners rather than simulating them | Very high, relational |
| Legal defense and hostile-jurisdiction counsel | **Missing / must remain human** | Risk memo, evidence index, response log, and explicit counsel-required gate | High; no autonomous substitute |

**Priority order [inferred]:**

1. Implement the **15-point provenance checklist** as a validation/export contract.
2. Add **batch match-review memory** and a **right-of-reply object**.
3. Connect research tickets to **source-gap promotion and freshness ownership**.
4. Standardize **leak manifests and raw-to-derived lineage**.
5. Treat human local reporting, commercial access, safety, and legal counsel as explicit dependencies—not agent capabilities.

The central lesson is that OCCRP's infrastructure is a flywheel: member reporters and ID discover records; the data desk normalizes them into FtM/Aleph; cross-referencing returns leads to reporters; local centers corroborate and publish; central fact-check/legal processes test the work; and useful datasets remain as shared investigative memory. **[inferred]** Ithildin already implements much of the machine-readable middle. Its cheapest gains are in preserving decisions, access/provenance, response state, and freshness—not in rebuilding the search interface.
