# ICIJ Methodology Infrastructure: The Reusable Machinery Behind Cross-Border Investigations

**Agent:** meta-methods reviewer  
**Date:** 2026-07-29  
**Method:** Primary-source review of ICIJ methodology, policy, training, database, and investigation pages; ICIJ's GitBook documentation; and public GitHub repositories maintained by ICIJ or explicitly linked by ICIJ. This report separates ICIJ's stated or demonstrated methodology from conclusions marked **[inferred]**. Short passages explicitly introduced as “ICIJ's words” are quotations; everything else is paraphrase or analysis. No investigation database was read or written.

---

## 1. DOCUMENT INTAKE AND ANALYSIS: EXTRACT, DATASHARE, AND THE PUBLIC TOOLCHAIN

ICIJ's document infrastructure is best understood as an evolution, not one timeless stack. Extract was the parallel extraction engine used in the Panama Papers era; the historical investigation stack then exposed extracted content through Solr and Blacklight. Datashare subsequently consolidated secure ingestion, OCR, search, named-entity recognition (NER), batch queries, and multi-user access around Elasticsearch. Current repositories add a separate web client, Neo4j extension, bulk-action client, and fact-checking application. [ICIJ's Panama Papers technical account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/), [Datashare documentation](https://icij.gitbook.io/datashare), and [ICIJ's public GitHub organization](https://github.com/ICIJ).

### 1.1 Extract: turn heterogeneous files into text at leak scale

Extract is an MIT-licensed, cross-platform command-line tool for parallelized content extraction and analysis. Its library wraps Apache Tika; its CLI can place jobs on Redis, run workers across machines, invoke Tesseract OCR, and send output to Solr, plain text, or standard output. ICIJ says it used Extract for Swiss Leaks, Luxembourg Leaks, and the Panama Papers. [ICIJ/Extract repository](https://github.com/ICIJ/extract).

The reusable pattern is a queue-backed fan-out/fan-in pipeline:

1. Enumerate files and enqueue extraction jobs.
2. Let workers identify formats and extract text/metadata with Tika.
3. OCR image-only material with Tesseract.
4. Emit normalized text and metadata into a search index or filesystem.
5. Scale by adding short-lived workers, not by changing the reporting interface.

That pattern was explicit in the Panama Papers: ICIJ used 30–40 temporary Amazon servers to parallelize OCR, while the searchable corpus remained a shared Solr/Blacklight service. [ICIJ's words: “we would have needed 24 years to get through all the files” on one machine; the temporary cluster reduced that to days.](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/)

**Failure modes exposed by the record:** extraction and OCR are CPU-intensive; unsupported or malformed formats require exception handling; OCR output is searchable evidence discovery, not an authoritative transcription; and elastic cloud processing must not become uncontrolled source exposure. ICIJ's later generic leak recipe places files on encrypted disks, uses scalable servers for processing, and distinguishes extraction from final reporting verification. [ICIJ's massive-leak methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/).

### 1.2 Datashare: self-hosted corpus search rather than a hosted evidence custodian

Datashare is an AGPL-licensed, self-hosted document search and analysis system. It accepts PDFs, emails, spreadsheets, images, and archives; extracts text and metadata; performs OCR; identifies named entities; exposes a web interface and REST API; and keeps source documents under the operator's control. [Datashare repository](https://github.com/ICIJ/datashare) and [product page](https://datashare.icij.org/).

Its documented processing chain combines:

- Extract and Apache Tika for file parsing;
- Tesseract for OCR;
- CoreNLP and OpenNLP pipelines for named entities;
- Elasticsearch for full-text and metadata search;
- an application layer and web client for projects, document viewing, tagging, filters, and saved/batch searches.

[Datashare “About” documentation](https://icij.gitbook.io/datashare) and [Datashare client repository](https://github.com/ICIJ/datashare-client).

Datashare deliberately supports four operational modes. **Local** mode embeds the application, Elasticsearch, SQLite, and an in-memory key-value store on one machine. **Server** mode supports multiple authenticated users against shared projects. **CLI** mode distributes expensive scan, index, and NER work. **Task-runner** mode handles asynchronous batch searches, downloads, and processing jobs. [Datashare running modes](https://icij.gitbook.io/datashare/concepts/running-modes).

The architecture therefore separates three concerns that investigative systems often conflate: custody of source material, compute-heavy derivation, and collaborative access. **[inferred]** This is a security and operability principle more than a product feature: raw custody can remain local while derived indexes and job execution scale to the risk and size of a project. The inference follows from Datashare's local/server/CLI/task-runner modes and ICIJ's encrypted-disk/cloud-processing descriptions. [Datashare running modes](https://icij.gitbook.io/datashare/concepts/running-modes) and [massive-leak methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/).

### 1.3 Named entities are candidate pivots, not verified identities

Datashare's NER detects mentions including people, organizations, locations, and email addresses. The interface lets a reporter filter by entity type, open the documents where a name occurs, and inspect mention context and extraction information. [Datashare named-entity definition](https://icij.gitbook.io/datashare/usage/faq/definitions/what-is-a-named-entity) and [document exploration](https://icij.gitbook.io/datashare/usage/explore-a-document).

The important methodological boundary is that a detected mention is neither entity resolution nor proof that two identical strings denote the same person. **[inferred]** ICIJ's Offshore Leaks identity warning supplies the downstream discipline Datashare's search results require: confirm identities using addresses or other identifying information because people and entities can share names. [Offshore Leaks search gate and warning](https://offshoreleaks.icij.org/?e=true).

### 1.4 Batch search makes hypothesis lists reproducible

Datashare accepts a CSV of queries and runs it against a project, preserving a result count and matching documents for each row. Queries can use field filters and Boolean operators, and a completed batch can be relaunched as the corpus changes. The public product page advertises batches of up to 10,000 queries. [Batch-search documentation](https://icij.gitbook.io/datashare/usage/batch-search-documents) and [Datashare product page](https://datashare.icij.org/).

This turns “try these names” into a reviewable method:

1. Define a list and its source: politicians, sanctions targets, companies, addresses, aliases.
2. Preserve each exact query string and optional filters.
3. Execute the same list over a named corpus snapshot.
4. Store hits by query, not only a flat pile of documents.
5. Re-run when documents, aliases, or parsers change.

The documentation identifies practical failure modes: one malformed query can stop a batch; commas and reserved characters require care; a query can exceed Elasticsearch's response-size limits; and Elasticsearch host-resolution errors can block execution. [Batch-search troubleshooting](https://icij.gitbook.io/datashare/usage/batch-search-documents). **[inferred]** A production agent should lint and dry-run every query file before the expensive run and record both zero-hit and failed-query states; otherwise “not found” silently mixes absence with execution failure.

### 1.5 Scaling is observable and separable

Datashare's performance guidance recommends separating scan from index, distributing index operations, tuning parallelism, and using a remote Elasticsearch cluster when required. ICIJ reports that processing the 2.94 TB Pandora Papers corpus used as many as ten servers and cost several thousand dollars, with Tika and Tesseract among the expensive stages. [Datashare performance considerations](https://icij.gitbook.io/datashare/server-mode/performance-considerations).

**[inferred]** The reusable machinery is not “put everything in the cloud.” It is: benchmark each stage, scale only the bottleneck, preserve job state, and shut elastic capacity down after derivation. That follows from ICIJ's separate scan/index/NER controls, task-runner model, and temporary-worker history. [Datashare running modes](https://icij.gitbook.io/datashare/concepts/running-modes), [performance considerations](https://icij.gitbook.io/datashare/server-mode/performance-considerations), and [Panama Papers technical account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).

### 1.6 Public repository map

| Repository | Reusable role | Evidentiary boundary |
|---|---|---|
| [ICIJ/datashare](https://github.com/ICIJ/datashare) | Server, API, ingestion, indexing, search, projects, and NER orchestration | Extracted text and machine entities remain derived representations |
| [ICIJ/datashare-client](https://github.com/ICIJ/datashare-client) | Web interface for corpus navigation and review | Interface state is not source provenance |
| [ICIJ/extract](https://github.com/ICIJ/extract) | Queueable Tika/Tesseract extraction CLI and library | OCR/parser output must retain a pointer to the original |
| [ICIJ/datashare-extension-neo4j](https://github.com/ICIJ/datashare-extension-neo4j) | Builds Neo4j graphs from Datashare projects and exposes a graph widget | A generated co-occurrence graph is not a verified relationship graph |
| [ICIJ/datashare-tarentula](https://github.com/ICIJ/datashare-tarentula) | Bulk tagging, metadata listing, export, download, and cleanup | Bulk actions need a logged selection rule and undo/review path |
| [ICIJ/prophecies](https://github.com/ICIJ/prophecies) | Self-hosted data cleaning and labor-intensive fact-checking | Human validation decisions need reviewer and change history |
| [ICIJ/offshoreleaks-data-packages](https://github.com/ICIJ/offshoreleaks-data-packages) | Reproducible Neo4j packages, browser guide, Cypher and language examples, and sample GraphQL server | The example server is not itself a promise of a hosted public GraphQL service |
| [HazyResearch/icij-maude](https://github.com/HazyResearch/icij-maude) | Public weak-supervision code and sample data for Implant Files sex classification | Model coverage and accuracy limits must accompany outputs |

Datashare's Neo4j extension connects document search to graph exploration, but it should not be confused with the separately curated Offshore Leaks ownership graph. The extension says it builds graphs from Datashare projects; the Offshore Leaks packages distribute a graph constructed from provider databases and ICIJ transformation work. [Datashare Neo4j extension](https://github.com/ICIJ/datashare-extension-neo4j) and [Offshore Leaks packages](https://github.com/ICIJ/offshoreleaks-data-packages).

---

## 2. OFFSHORE LEAKS DATABASE: FROM PROVIDER RECORDS TO A QUERYABLE PUBLIC GRAPH

### 2.1 The graph model preserves investigative roles

ICIJ converted structured and semi-structured offshore-provider records into a Neo4j property graph. Its public model has four principal node classes:

- **Entity:** an offshore company, trust, foundation, or fund.
- **Officer:** a person or company connected in a role such as beneficiary, director, or shareholder.
- **Intermediary:** the middleman or service provider, often a law firm, that connects a client to an offshore entity.
- **Address:** the address associated with another node.

Edges include `officer_of`, `intermediary_of`, and `registered_address`, plus entity-to-entity links represented in source data. [Official Neo4j data-shape guide](https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html) and [Offshore Leaks schema](https://offshoreleaks.icij.org/schema/oldb).

This is more disciplined than flattening every name into a generic “related to” link: node type, source role, and edge type preserve what the underlying provider asserted. The downloadable package demonstrates path queries over those typed edges and supports loading a Neo4j dump into Desktop, Server, or Aura. [ICIJ Offshore Leaks data packages](https://github.com/ICIJ/offshoreleaks-data-packages).

### 2.2 Provider-specific reverse engineering precedes normalization

The database is not the output of one universal parser. ICIJ says it used reverse engineering to extract source records and applied programming, scraping, machine learning, or manual extraction through processes that differed by provider. Source codes served as unique identifiers where available; when Panama Papers shareholder and beneficiary records lacked codes, ICIJ merged records only where both name and address matched. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).

ICIJ also enriched location fields without overwriting the original address. For the early Offshore Leaks release, scripts normalized country signals, Google Maps geocoding handled part of the residue, and people manually matched what automation could not; the new country field was added while the leaked address text remained unchanged. [ICIJ's country-search construction note](https://www.icij.org/inside-icij/2013/10/users-can-now-search-country-icij-offshore-leaks-database/).

**[inferred]** The correct reusable ETL unit is a *provider recipe*, not “the offshore schema.” Each recipe should record source tables/files, source IDs, generated IDs, field mappings, rejected rows, manual edits, and enrichment fields. The unified graph is a publication layer above those recipes, not a substitute for them. This inference follows from ICIJ's provider-by-provider extraction account and ID policy. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).

### 2.3 Public release is deliberately narrower than the leak

ICIJ publishes basic corporate relationships in the public interest, not the full leaked corpus. The public database excludes bulk raw documents and does not publish bank-account data, emails, financial transactions, passports, telephone numbers, or personal information en masse. [Panama Papers data-release explanation](https://www.icij.org/inside-icij/2016/05/icij-releases-panama-papers-offshore-company-data/) and [“not a data dump” explanation](https://www.icij.org/investigations/offshore/unlocking-chinas-secrets/).

The downloadable release is licensed as Open Database License data with database contents under CC BY-SA. It is available as CSV files separating node types and relationships and as Neo4j versioned dumps; ICIJ's package repository adds an interactive guide, code examples, and a GraphQL server example. [Download page](https://offshoreleaks.icij.org/pages/database) and [package repository](https://github.com/ICIJ/offshoreleaks-data-packages).

In January 2025, ICIJ launched a reconciliation API that lets users match their own names, addresses, and corporate entities against more than 810,000 offshore entities. It is an enrichment/matching interface, not a release of the underlying raw leaks. [ICIJ reconciliation API announcement](https://www.icij.org/inside-icij/2025/01/explore-the-latest-tool-to-power-up-investigations-via-the-offshore-leaks-database/). The schema site separately labels general REST API access as private beta, so it should not be represented as an unrestricted public API. [Offshore Leaks schema/API page](https://offshoreleaks.icij.org/schema/oldb).

### 2.4 Updates are investigation-triggered and vintage-specific, not periodic

The public database launched with Offshore Leaks data in June 2013, added Greater China records in January 2014, Panama and Bahamas records in 2016, staged Paradise Papers data across 2017–2018, and staged Pandora Papers data across 2021–2022. Its FAQ promises to describe updates when they occur but publishes no monthly, quarterly, or annual refresh SLA. [Offshore Leaks FAQ update history](https://offshoreleaks.icij.org/pages/faq) and [dataset/source chronology](https://offshoreleaks.icij.org/pages/data).

Every constituent leak also has a different cutoff: for example, Panama Papers data runs to 2015, while Paradise Papers provider and registry subsets have different dates and Pandora Papers providers span several later years. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq). **[inferred]** The operative cadence is editorial release after a project or tranche is ready, not live registry synchronization. An autonomous agent must therefore attach investigation, provider, and vintage to every database hit.

### 2.5 Caveat discipline is part of the interface

Before searching, a user must acknowledge a statement that legitimate offshore structures exist; inclusion does not imply illegal or improper conduct; common names require identity confirmation; each dataset covers a defined period; and information may have changed. The searchable page repeats those warnings and provides an error contact. [Offshore Leaks search gate](https://offshoreleaks.icij.org/?e=true) and [full disclaimer](https://offshoreleaks.icij.org/pages/disclaimer).

ICIJ's “how to use” page makes the same methodological demand positively: describe a record carefully, do not infer wrongdoing from inclusion, and verify a person's identity with addresses or other identifiers. It also warns that some registry-derived entities are ordinary local businesses rather than offshore structures in the colloquial sense. [How to use the database](https://offshoreleaks.icij.org/pages/howtouse).

This is publication infrastructure, not boilerplate. **[inferred]** It makes the caveat unavoidable at query time, attaches it to individual-result interpretation, and routes errors back to curators. A copy should treat caveats as data-bound UI state, not a disclaimer buried in terms. [Offshore Leaks search gate](https://offshoreleaks.icij.org/?e=true) and [full disclaimer](https://offshoreleaks.icij.org/pages/disclaimer).

### 2.6 Correction, pruning, and takedown are distinct

ICIJ says it removed isolated people, entities, and addresses with no apparent database connections from the public graph, and it documents a 2016 relationship error and its correction in the FAQ. Those are structural curation and factual correction, not a merits-based takedown rule. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).

The database directs users to contact ICIJ about errors. ICIJ's corporate page provides a confidential-capable complaints address, while its terms contain a copyright/DMCA removal process. [Database disclaimer](https://offshoreleaks.icij.org/pages/disclaimer), [corporate/editorial policy](https://www.icij.org/about/corporate/), and [terms of use](https://www.icij.org/about/corporate/terms-of-use/).

**[inferred from the reviewed public record, as of 2026-07-29]:** ICIJ does not publish a general procedure promising removal of accurate, lawfully published leak-derived database records merely on a subject's request. Its visible controls are error correction, editorial complaints, selective publication/redaction, structural pruning, and copyright notice-and-takedown. This is an absence finding limited to the cited FAQ, disclaimer, database pages, corporate policies, privacy policy, and terms—not a claim about unpublished internal legal practice. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq), [database disclaimer](https://offshoreleaks.icij.org/pages/disclaimer), [ICIJ privacy policy](https://www.icij.org/about/corporate/privacy-policy/), and [terms of use](https://www.icij.org/about/corporate/terms-of-use/).

---

## 3. COLLABORATION AS A HUMAN CONTROL PLANE

### 3.1 “Radical sharing” reverses newsroom default incentives

ICIJ describes its Panama Papers model as “radical sharing”: hundreds of journalists shared leads, notes, documents, and planned stories across organizations that might ordinarily compete. The 2016 project involved 376 reporters in almost 80 countries and rested on trust accumulated over roughly two decades. [ICIJ's “Radical Sharing” essay](https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/).

ICIJ's words: “By sharing information, all participants obtained a more complete picture.” [“Radical Sharing”](https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/). The machinery behind that norm is membership selection, written agreements, access control, shared workspaces, regional coordinators, editorial calendars, and an embargo—not goodwill alone.

### 3.2 Global I-Hub is the secure virtual newsroom

ICIJ launched the Global I-Hub as a secure collaboration platform built around the open-source Oxwall community system, adding security and encryption layers and designing it with user input. [I-Hub launch announcement](https://www.icij.org/inside-icij/2014/07/icij-build-global-i-hub-new-secure-collaboration-tool/).

In practice, I-Hub functions like a private social network: journalists organize by country, topic, or investigative subject; post findings and questions; cross-check information; exchange documents and notes; and coordinate work across time zones. Regional coordinators help partners meet technical and security standards. [ICIJ's massive-leak methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/).

ICIJ migrated the platform and described integrations that bring Datashare activity and document discussion into the collaboration environment. [ICIJ 2020 technology note](https://www.icij.org/inside-icij/2020/01/how-icij-will-rock-its-tech-in-2020/). **[inferred]** I-Hub is the coordination system of record, while Datashare is the evidence-discovery system; bridges between them prevent a document hit and the discussion about its significance from becoming two untraceable histories.

### 3.3 Partners are vetted for behavior as well as skill

ICIJ's Panama Papers FAQ lists four partner-selection considerations: a proven investigative record, organizational support for a slow deep dive, willingness to share discoveries with the global team, and interpersonal fit. ICIJ says prospective partners are vetted and trained in the required tools. [Panama Papers FAQ](https://www.icij.org/investigations/panama-papers/faqs/).

Pandora Papers guidance similarly prioritizes quality, collaborative willingness, and geographic need, while noting that onboarding and training consume scarce resources and therefore limit late additions. [Pandora Papers FAQ](https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/). **[inferred]** Partner vetting is access-risk management: technical security cannot compensate for a participant who will not respect source protection, attribution, sharing norms, or an embargo.

### 3.4 Embargoes are contractual coordination infrastructure

Panama Papers participants signed an agreement to respect the embargo and simultaneous publication. ICIJ argues that coordinated release produces a “big bang” that makes suppression and localized dismissal harder. [Panama Papers technical/team account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).

Earlier Offshore Leaks participants also agreed in writing not to share material with third parties, to respect the embargo, and to act as team players; regional coordinators reduced the central bottleneck. [ICIJ's 2013 collaboration retrospective](https://www.icij.org/inside-icij/2013/04/how-we-all-survived-likely-largest-collaboration-journalism-history/).

FinCEN Files shows the model above the 100-outlet threshold: more than 400 journalists from 110 media outlets in 88 countries coordinated through ICIJ's encrypted virtual newsroom, communicating across time zones, exchanging documents, and comparing findings in real time. [ICIJ's FinCEN/Luanda collaboration lessons](https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/).

**[inferred]** The embargo is not merely a publish date. It is a state machine: invited → vetted → agreement accepted → trained → scoped corpus access → reporting → fact-check/legal readiness → coordinated release → post-publication follow-up. A software clone without the legal agreement, people who enforce it, and outlets able to publish cannot reproduce this capability. [Panama Papers embargo account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/) and [ICIJ's 2013 collaboration retrospective](https://www.icij.org/inside-icij/2013/04/how-we-all-survived-likely-largest-collaboration-journalism-history/).

### 3.5 Multilingual fact-checking is federated

ICIJ's network has more than 290 invite-only members in more than 100 countries and says peer scrutiny across cultural and linguistic traditions improves accuracy and depth. [ICIJ About page](https://www.icij.org/about/). Paradise Papers credits record 380 journalists on six continents working in 30 languages, with named data, editorial, fact-checking, and research roles. [Paradise Papers project credits/method](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/).

The West Africa Leaks collaboration worked across English, French, and Portuguese, used regional editors and a libel specialist, and trained reporters in encryption and offshore-data reporting. [West Africa Leaks behind the scenes](https://www.icij.org/investigations/west-africa-leaks/behind-the-scenes-of-the-largest-ever-west-african-journalism-collaboration/).

**[inferred]** “Fact-checking across languages” is not one centralized translation queue. It is layered: local reporters resolve names, institutions, idiom, and public records; regional or language editors normalize and challenge the work; central data and editorial teams test cross-border consistency; counsel reviews jurisdiction-specific risk. The cited project pages demonstrate these layers but do not publish one universal multilingual checklist. [West Africa Leaks](https://www.icij.org/investigations/west-africa-leaks/behind-the-scenes-of-the-largest-ever-west-african-journalism-collaboration/) and [Paradise Papers credits/method](https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/).

### 3.6 What is a tool and what is a human capability

| Component | Toolable portion | Irreducibly human portion |
|---|---|---|
| Secure newsroom | Authentication, permissions, encrypted transport, groups, audit logs | Trust, discretion, resolving conflicts, enforcing norms |
| Partner onboarding | Invitations, agreements, training modules, access scopes | Vetting reputation, institutional commitment, interpersonal fit |
| Embargo | Readiness dashboard, timestamps, acknowledgements, publication schedule | Outlets' agreement to hold, legal accountability, emergency judgment |
| Cross-language verification | Translation memory, entity aliases, assignment tracking | Local meaning, source judgment, defamation context, cultural competence |
| Global fact-check | Claim ledger, evidence links, reviewer votes, conflicts | Editorial sufficiency, proportionality, public-interest judgment |

Each toolable element is supported by ICIJ's I-Hub, Datashare, Prophecies, and written-agreement descriptions; the human/tool boundary is **[inferred]** from the roles ICIJ assigns to partner selection, regional coordination, editing, fact-checking, and legal review. [I-Hub methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/), [partner criteria](https://www.icij.org/investigations/panama-papers/faqs/), and [Prophecies repository](https://github.com/ICIJ/prophecies).

---

## 4. MACHINE LEARNING AND DATA ENGINEERING: MODELS PROPOSE, REPORTERS ADJUDICATE

### 4.1 Panama Papers: two pipelines, one reporting surface

For unstructured files, the Panama team used Extract, Tika, Tesseract, Solr, and Blacklight. For structured Mossack Fonseca databases, it reverse-engineered schemas, used Talend to extract and transform records, loaded relationships into Neo4j, and exposed graph exploration through Linkurious. The search and graph services were connected to the collaborative reporting environment. [Panama Papers data/tech account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).

The repeatable design is dual:

- **Document pipeline:** preserve file → extract/OCR → index → query → open original.
- **Relational pipeline:** reverse-engineer provider schema → preserve identifiers → transform types/roles → graph → traverse → return to source records.

**[inferred]** Converting every source into a graph too early would erase record structure; leaving every relationship trapped in SQL would obstruct network reasoning. ICIJ uses the source's structure to select the first representation, then links representations during reporting. [Panama Papers data/tech account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).

### 4.2 Implant Files: text classification with explicit abstention

ICIJ gathered more than eight million medical-device records through over 1,500 public-record requests and downloads. For U.S. FDA adverse-event data, the team used Talend, Microsoft SQL Server, R, text mining, clustering, rules, and classification to identify deaths that appeared misclassified as other outcomes. A seed list of 121 death terms grew to more than 3,400 phrases; reporters inspected false positives and manually reviewed candidates. The published result identified 2,100 reports of deaths and 220 reports where an event may have contributed to death that had not been classified as deaths. [Implant Files adverse-event methodology](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/).

The article preserves the central causal caveat: an adverse-event report does not establish that the device caused the injury or death. [Implant Files methodology](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/).

For sex classification, ICIJ and Stanford's Hazy Research used Snorkel weak supervision. Reporters manually labeled a training sample, wrote multiple labeling functions, iterated with two fact-checkers, and caught traps such as references to “female” connectors and reports covering multiple people. The system assigned a sex to only 23% of records at a reported 96% accuracy and left 77% unknown. ICIJ published the code and sample data. [ICIJ's weak-supervision write-up](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/) and [public MAUDE repository](https://github.com/HazyResearch/icij-maude).

**Reusable doctrine [inferred]:** permit abstention; test feature leakage and polysemy; give reviewers candidate text, not only a label; publish coverage alongside accuracy; and never transform a probabilistic classification into a causal finding. [ICIJ's weak-supervision write-up](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/) and [adverse-event methodology](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/).

### 4.3 FinCEN Files: manual extraction won when language defeated automation

The FinCEN Files contained more than 2,100 suspicious activity reports and other records, including roughly three million words of narrative and inconsistent transaction attachments. Eighty-five journalists in 30 countries manually extracted details into a structured system, producing more than 55,000 records covering over 200,000 transactions and thousands of correspondent-bank relationships. Each extraction was reviewed three times, and fact-checking took seven months. [FinCEN Files data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/).

ICIJ tested machine learning, but variable language and complex transaction descriptions caused it to miss material details. A model helped identify addresses, but reporters still reviewed them. The team used SQL and Python for text analysis, then Neo4j and Linkurious to analyze hundreds of spreadsheets and roughly 100,000 transactions. [FinCEN Files data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/).

This is a strong negative-method lesson. **[inferred]** “Manual” is not methodological failure when the source is irregular, stakes are high, and the review system captures contributor, record, field, and repeated checks. Automation should earn deployment against an audited sample; it should not be adopted because the corpus is large. [FinCEN Files data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/).

### 4.4 Luanda Leaks: multilingual corpus plus selected machine assistance

ICIJ loaded more than 715,000 Luanda Leaks records into Datashare for about 120 journalists. More than half the corpus was in Portuguese. The team wrapped the open-source Apertium translator for offline use to protect source material, used batch searches and NER, and combined Talend, SQL, Neo4j, and Linkurious for structured relationships. It also tested Quartz AI Studio for clustering and classification, while people verified and supplemented outputs. ICIJ reported roughly $13,300 in server costs. [Luanda Leaks data methodology](https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/).

ICIJ released a documented company network derived from leaked records, registries, databases, and corporate documents and explicitly warned that the list was likely incomplete. [Luanda Leaks company network and download](https://www.icij.org/investigations/luanda-leaks/explore-how-to-build-a-business-empire/).

### 4.5 Pandora Papers: one leak, fourteen provider-specific data projects

Pandora Papers comprised 11.9 million files totaling 2.94 TB from 14 providers, with only about 4% in spreadsheet form. ICIJ built provider-specific pipelines, deduplicated source spreadsheets, used Python to extract data, applied tools including Fonduer and scikit-learn to recurring forms, and manually handled handwriting and formats automation could not resolve. The team then unified selected fields and matched people and companies against public lists and records. [Pandora Papers dataset methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/).

ICIJ used public records to verify identities and details and compared names with sanctions lists, prior leaks, corporate records, billionaire lists, and political-leader lists. [Pandora Papers dataset methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/). **[inferred]** The provider is the correct partition for extraction QA; the person/entity is the correct partition for cross-provider reporting.

### 4.6 Prophecies turns validation into a first-class application

ICIJ's FinCEN custom Django fact-checking tool evolved into Prophecies, an AGPL, self-hosted platform for data cleaning and labor-intensive fact-checking, with documented APIs. [FinCEN Files methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/) and [ICIJ/Prophecies repository](https://github.com/ICIJ/prophecies).

In a later passport-image project, a computer-vision service reduced about 75,000 image-bearing documents to roughly 1,000 candidates; reviewers conducted three rounds of review and retained about 500 unique passport images, which were then tagged in Datashare. ICIJ published the service code but restricted the trained model to protect confidential source material. [ICIJ passport machine-learning methodology](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/).

The reusable separation is:

1. Model or rule proposes a candidate.
2. Prophecies assigns and records human validation.
3. Approved outputs become structured tags or data.
4. Datashare returns reviewers to source context.
5. Publication uses only the validated subset and carries coverage limits.

**[inferred]** This is ICIJ's clearest machine/human contract. It is cheaper to copy than any particular model because the validation state machine generalizes across classifiers. [Passport machine-learning methodology](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/) and [Prophecies repository](https://github.com/ICIJ/prophecies).

---

## 5. VERIFICATION AND STANDARDS DOCTRINE

### 5.1 Leak authentication is triangulation, not a single ritual

ICIJ says Pandora Papers teams rigorously verified and cross-checked material for authenticity and verified every fact used in stories; the source was anonymous, unpaid, and imposed no conditions. [Pandora Papers FAQ](https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/).

The public record shows recurring authentication moves rather than one published cryptographic protocol:

- compare internal records with official corporate, regulatory, court, sanctions, and historical records;
- test dates, names, ranks, locations, identifiers, and organizational details;
- interview employees, officials, contractors, experts, and other knowledgeable people;
- verify key details across independent records before relying on the leak;
- distinguish authentic records from the truth of every allegation inside them.

Examples include cross-checking Ericsson records with other documents and interviews, Pandora identities with public records, and leaked military details against official U.S. Defense Department records and archived military material. [Ericsson List verification account](https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/), [Pandora methodology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/), and [ICIJ's leaked-military-record verification description](https://www.icij.org/news/2025/10/arab-states-deepened-military-ties-with-israel-while-denouncing-gaza-war-leak-reveals/).

**[inferred]** Authentication should be recorded at corpus, collection, document, and claim levels. A genuine corpus can contain stale, false, speculative, or internally inconsistent statements; “the leak is authentic” cannot substitute for claim verification. [Pandora Papers FAQ](https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/) and [Ericsson List verification account](https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/).

### 5.2 Source-to-claim distance controls confidence

ICIJ's public tools preserve several layers: original file; extracted text/OCR; named entity or model output; normalized record; resolved entity; graph relationship; journalist claim. [Datashare document exploration](https://icij.gitbook.io/datashare/usage/explore-a-document), [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq), and [Implant Files weak-supervision method](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/).

**[inferred]** Every step away from the original should add transformation metadata and reduce the permissible certainty unless independently corroborated. ICIJ demonstrates this through original-address preservation, source-vintage warnings, model abstention, human validation, and causal caveats. [Country-field enrichment note](https://www.icij.org/inside-icij/2013/10/users-can-now-search-country-icij-offshore-leaks-database/), [Offshore Leaks search warning](https://offshoreleaks.icij.org/?e=true), and [Implant Files methodology](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/).

### 5.3 Subject response is a pre-publication evidence channel

ICIJ's Panama Papers retrospective states that reporters lay out their findings before publication and give subjects a chance to respond, normally allowing weeks when security and timing permit. [Panama Papers ten-year retrospective](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/).

Project practice shows detailed, early questions rather than a token last-minute request. Implant Files reporters contacted regulators before launch; Ericsson List reporters sent multi-page questions and allowed a grace period; published stories incorporate denials, explanations, and documentary responses. [Implant Files pre-publication response](https://www.icij.org/investigations/implant-files/implant-files-prompt-immediate-response-before-first-stories-published/) and [Ericsson response process](https://www.icij.org/investigations/ericsson-list/ericsson-facing-ongoing-probes-and-fallout-months-after-icij-revealed-new-corruption-breach/).

**[inferred]** A response is not just copy for a “declined to comment” line. It can reveal an identity collision, missing contract, alternative chronology, legal privilege issue, or new primary evidence. It belongs in the claim ledger with the question, delivery proof, deadline, full answer, reporter assessment, and resulting revision. [Panama Papers subject-response account](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/) and [Ericsson response process](https://www.icij.org/investigations/ericsson-list/ericsson-facing-ongoing-probes-and-fallout-months-after-icij-revealed-new-corruption-breach/).

### 5.4 Fact-checking, editorial vetting, and legal review are separate gates

ICIJ describes the FinCEN Files and Luanda Leaks as undergoing rigorous fact-checking, editorial vetting, and legal review. FinCEN's underlying manual data extraction was itself reviewed three times before story-level checks. [ICIJ lessons from FinCEN and Luanda](https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/) and [FinCEN data methodology](https://www.icij.org/investigations/fincen-files/mining-sars-data/).

These gates answer different questions:

- **Data validation:** was the source field transcribed and transformed correctly?
- **Fact-check:** does each factual statement match adequate evidence?
- **Editorial review:** is the framing fair, intelligible, proportional, and newsworthy?
- **Legal review:** are defamation, privacy, source, injunction, privilege, and jurisdiction risks handled?

The separation above is **[inferred]** from ICIJ's naming of the gates and its project workflows; ICIJ does not publish one universal gate schema. [ICIJ lessons page](https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/).

### 5.5 Corrections and complaints are visible but less systematized publicly

ICIJ's editorial policy adopts the Society of Professional Journalists Code of Ethics and provides `complaints@icij.org`, including confidential handling where appropriate. [ICIJ corporate/editorial policy](https://www.icij.org/about/corporate/). The linked SPJ code requires verification, subject response, and prompt, prominent correction. [SPJ Code of Ethics PDF hosted by ICIJ](https://media.icij.org/uploads/2018/02/spj-code-of-ethics.pdf).

ICIJ sometimes appends dated update or correction notes to methodology and story pages, and the Offshore Leaks FAQ records a database relationship error with its correction. [Implant Files methodology update](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/), [ICIJ correction example](https://www.icij.org/investigations/interpols-red-flag/interpol-reacts-icij-story/), and [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).

**[inferred from the reviewed official pages]:** ICIJ's public correction infrastructure is less centralized than its collaboration and data systems. A complaint route and article/database annotations are visible, but no organization-wide, queryable corrections ledger was located. An adopting platform should copy the ethical rule and improve the machinery with a correction object that links old claim, new claim, reason, evidence, decision-maker, date, and every affected output. [ICIJ corporate/editorial policy](https://www.icij.org/about/corporate/), [ICIJ correction example](https://www.icij.org/investigations/interpols-red-flag/interpol-reacts-icij-story/), and [Offshore Leaks correction record](https://offshoreleaks.icij.org/pages/faq).

---

## 6. REPEATABLE REPORTING RECIPES: A CATALOG

These pages teach a method rather than merely describe an outcome.

| Recipe | Trigger | Repeatable method taught | Principal failure mode/caveat |
|---|---|---|---|
| [How ICIJ's data and tech team deciphered the Panama Papers](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/) | Heterogeneous leak with files plus databases | Parallel extraction/OCR; Solr search; reverse-engineer SQL; Talend-to-Neo4j; Linkurious; embargoed collaboration | Collapsing file and relational pipelines or losing source links |
| [How ICIJ deals with massive data leaks](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/) | Large confidential corpus | Encrypted storage; scalable processing; Tika/Tesseract; shared search; graph analysis; I-Hub groups; regional support | Security varies by partner; scale can outrun verification |
| [How we mined more than 715,000 Luanda Leaks records](https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/) | Multilingual mixed-format leak | Datashare, offline translation, NER, batches, structured graph, clustering, manual validation | Translation/classification errors and incomplete network data |
| [From a jumble of secret reports, damning data](https://www.icij.org/investigations/fincen-files/mining-sars-data/) | Narrative regulatory reports with irregular transactions | Distributed manual extraction, triple review, SQL/Python analysis, graph construction | Automation misses complex language; SAR suspicion is not proof |
| [About the Pandora Papers leak dataset](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) | Many providers, little structured data | Provider-specific ETL, form extraction, manual handwriting review, dedupe, list matching, public-record verification | No single parser; provider vintages and schemas differ |
| [Algorithms, analysis and adverse events](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/) | Misclassified outcomes in regulatory text | Seed lexicon, expand phrases, cluster/classify, review false positives, adjudicate candidates | Mentions do not establish outcome or causation |
| [Using AI to identify sex in device reports](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/) | Missing field inferable from noisy text | Manual labels, weak-supervision rules, two-reviewer iteration, publish code, abstain heavily | Polysemy, multiple people, low coverage |
| [Passport-image machine learning](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/) | Rare visual document class in a huge corpus | Computer-vision candidate generation, Prophecies review rounds, Datashare tagging | Confidential training data, duplicate images, false candidates |
| [Behind the scenes of the Bribery Division](https://www.icij.org/investigations/bribery-division/behind-the-scenes-of-the-bribery-division/) | Early leak whose news value must be tested | Small initial review, expand partners when warranted, shared corpus, reporting beyond leaked files, coordinated publication | Treating an incomplete leak as the whole factual universe |
| [How to investigate companies in Offshore Leaks](https://www.icij.org/inside-icij/2018/01/investigate-companies-found-offshore-leaks-database/) | Known names or lists need offshore cross-match | Download data, use OpenRefine/Excel fuzzy matching, follow graph, verify in outside registries and records | False-positive name matches and assuming database inclusion proves misconduct |
| [How to search Offshore Leaks by location](https://www.icij.org/inside-icij/2018/01/offshore-leaks-database-tips-location-geogrpahy/) | Geography-first reporting | Search linked country, jurisdiction, or an address discovered elsewhere | Country association may derive from an address, not nationality or control |
| [Getting the most out of Offshore Leaks data](https://www.icij.org/inside-icij/2014/03/getting-most-out-offshore-leaks-data/) | Bulk cross-match and network exploration | Match external watchlists, investigate indirect connections, ask local reporters, return to source documents | Incomplete links, spelling variants, and overreliance on obvious names |
| [About the Solitary Voices data](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/) | FOIA spreadsheet with sensitive person-level records | Preserve original fields, document calculated fields, publish transformation notes, suppress identifying free text | Agency undercount and re-identification risk |
| [Analyzing the data behind Skin and Bone](https://www.icij.org/inside-icij/2012/07/analyzing-data-behind-skin-and-bone/) | Regulatory records acquired over time | FOIA, OCR/search, structured review, and source-document access for reporters, fact-checkers, and lawyers | Scanned records and jurisdictional inconsistency |
| [Hake DNA testing: how we did it](https://www.icij.org/investigations/looting-the-seas-ii/hake-dna-testing-how-we-did-it/) | A physical product claim needs scientific testing | Document sampling, blind laboratory analysis, chain-of-custody controls, duplicate validation | Sample representativeness and contamination |

**[inferred]:** Together these recipes form a decision tree: inspect source shape first; choose document, relational, manual-extraction, classification, field, or laboratory methods accordingly; build validation into the method; and publish the method's denominator, coverage, and uncertainty. The table's methods and caveats are grounded in each linked ICIJ page, including the [generic massive-leak recipe](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/) and [FinCEN manual-extraction account](https://www.icij.org/investigations/fincen-files/mining-sars-data/).

---

## 7. PUBLIC DATA RELEASES AND APIS BEYOND THE OFFSHORE LEAKS SEARCH SITE

ICIJ's release doctrine is selective. It publishes enough structured data or source material to make important findings inspectable and reusable while withholding raw leaks and fields that would expose sources, private communications, financial details, or vulnerable people. That pattern appears in Offshore Leaks, FinCEN Files, Solitary Voices, and Lux Leaks. [Panama Papers release explanation](https://www.icij.org/inside-icij/2016/05/icij-releases-panama-papers-offshore-company-data/), [FinCEN download page](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/), [Solitary Voices methodology/download](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/), and [Lux Leaks Datashare release](https://www.icij.org/investigations/luxembourg-leaks/explore-company-secrets-in-lux-leaks-using-datashare/).

### 7.1 Dataset and document releases

| Release | What is public | What is deliberately bounded |
|---|---|---|
| [FinCEN Files transaction data](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/) | Downloadable map data covering more than $35 billion in transactions with sufficient originator and beneficiary bank details | A fraction of the more than $2 trillion described in the files; not raw SARs; suspicious activity does not establish wrongdoing |
| [International Medical Devices Database](https://medicaldevices.icij.org/p/about) | Searchable global recall/safety-notice database assembled from public/FOI records in 46 countries, with more than 120,000 records and an ODbL/CC BY-SA raw download | Jurisdictions differ in disclosure and terminology; reports and recalls do not alone establish causation |
| [Solitary Voices data](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/) | Downloadable FOIA-derived placement records with transparent calculated/standardized fields | Narrative fields withheld to reduce re-identification; ICE's source universe itself is incomplete |
| [Luanda Leaks company network](https://www.icij.org/investigations/luanda-leaks/explore-how-to-build-a-business-empire/) | Spreadsheet of documented company/shareholding links used in the visualization | Only links supported by documents; known incompleteness disclosed |
| [Lux Leaks documents in Datashare](https://www.icij.org/investigations/luxembourg-leaks/explore-company-secrets-in-lux-leaks-using-datashare/) | More than 1,000 leaked files made searchable in a public Datashare instance, with local Datashare also available | A selected investigation corpus, not a general leak API |

The FinCEN page is especially disciplined: it states the released denominator, why only records with both bank endpoints were included, that the data is a fraction of the leak, and that flagged transactions do not necessarily establish misconduct. [FinCEN Files download and caveats](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/).

### 7.2 Software APIs versus evidence APIs

Datashare exposes a REST API for a self-hosted corpus and Prophecies publishes an application API; these are interfaces to software an operator controls, not centralized ICIJ evidence feeds. [Datashare repository](https://github.com/ICIJ/datashare) and [Prophecies repository/API link](https://github.com/ICIJ/prophecies).

The Offshore Leaks reconciliation API is the clearest hosted data API ICIJ publicly announced: it matches and enriches user-supplied data against the curated Offshore Leaks graph. [Reconciliation API announcement](https://www.icij.org/inside-icij/2025/01/explore-the-latest-tool-to-power-up-investigations-via-the-offshore-leaks-database/).

**[inferred from the official pages and repositories reviewed]:** ICIJ does not offer one general-purpose public API spanning all investigations or raw leak corpora. Its reusable publication pattern is per-project: searchable app, selected download, selected document corpus, and methodology/caveat page. The absence finding is limited to the public ICIJ site, [Datashare](https://github.com/ICIJ/datashare), [Prophecies](https://github.com/ICIJ/prophecies), and [Offshore Leaks API/schema](https://offshoreleaks.icij.org/schema/oldb) materials reviewed here.

---

# SYNTHESIS

## A. Bottom-up evidence-source taxonomy

This taxonomy starts with the material ICIJ repeatedly acquires, not with story topics. “Typical use” and “control” are synthesis **[inferred]** from the linked examples.

| # | Evidence-source class | ICIJ examples | Typical use | Minimum control |
|---|---|---|---|---|
| 1 | Leaked provider relational databases | Mossack Fonseca and other offshore providers in [Panama](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/) and [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) | Ownership, officer, intermediary, address, event, and service-provider graphs | Provider-specific schema map; original/generated ID distinction |
| 2 | Leaked unstructured documents and communications | PDFs, emails, images, and archives processed in [Datashare](https://icij.gitbook.io/datashare) | Claims, contracts, correspondence, instructions, invoices, context | Immutable original; extraction/OCR lineage; page/offset citation |
| 3 | Leaked regulatory/compliance narratives | SARs in [FinCEN Files](https://www.icij.org/investigations/fincen-files/mining-sars-data/) | Suspicion narratives, parties, bank routes, dates, amounts | Preserve report boundaries; distinguish allegation/suspicion from fact |
| 4 | Leaked or attached spreadsheets/transaction tables | FinCEN attachments and provider spreadsheets in [FinCEN](https://www.icij.org/investigations/fincen-files/mining-sars-data/) and [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) | Transaction reconstruction and entity lists | Source sheet/cell lineage; dedupe log; currency/date normalization |
| 5 | Corporate registries and company filings | Verification and augmentation in [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) and [Luanda](https://www.icij.org/investigations/luanda-leaks/explore-how-to-build-a-business-empire/) | Identity, ownership, officers, incorporation, status | Registry, jurisdiction, retrieval date, document ID, vintage |
| 6 | Sanctions, PEP, officeholder, and wealth lists | List matching in [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) and [Offshore Leaks training](https://www.icij.org/inside-icij/2014/03/getting-most-out-offshore-leaks-data/) | Prioritization and cross-match leads | List version/date; fuzzy-match score; manual identity adjudication |
| 7 | Court, regulatory, enforcement, and official records | Cross-checking in [Ericsson List](https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/) and public-record verification in [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) | Authentication, chronology, allegation/status, independent corroboration | Exact procedural status and official source; do not convert allegation to proof |
| 8 | FOIA and public administrative bulk records | MAUDE in [Implant Files](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/) and ICE records in [Solitary Voices](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/) | Systemic pattern measurement | Request/release scope; agency undercount; field dictionary; withheld fields |
| 9 | Cross-jurisdiction recall, safety, or notice records | [International Medical Devices Database](https://medicaldevices.icij.org/p/about) | Compare regulatory response and device problems | Country-specific definitions; dedupe; causation warning |
| 10 | Interviews and local-source reporting | Employee/official/contractor checks in [Ericsson List](https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/) | Authenticate, contextualize, contradict, discover missing records | Source basis, access, directness, date, language, corroboration |
| 11 | Subject responses and supplied records | Pre-publication practice in [Panama retrospective](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/) | Correct identities, test claims, capture denial/explanation, acquire documents | Exact questions, deadline, full response, delivery proof, revisions |
| 12 | Field samples and laboratory evidence | [Hake DNA testing](https://www.icij.org/investigations/looting-the-seas-ii/hake-dna-testing-how-we-did-it/) | Verify product identity or physical-world claims | Sampling frame, chain of custody, blind testing, replicate validation |
| 13 | Partner-constructed structured datasets | Manual extraction in [FinCEN Files](https://www.icij.org/investigations/fincen-files/mining-sars-data/) | Convert narratives to comparable rows and networks | Reviewer identity, field-level source, triple-check/conflict resolution |
| 14 | Machine-derived candidates and classifications | NER, Implant weak supervision, and passport CV in [Datashare](https://icij.gitbook.io/datashare), [Implant Files](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/), and [passport detection](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/) | Triage, tagging, missing-field inference, rare-document discovery | Model/rule version, input snapshot, score, abstention, sampled and human validation |

### Taxonomy rule

**[inferred]:** A graph edge, normalized row, or classifier label is not a new independent source. It is a derived evidence object that must point backward through every transformation to one or more items in classes 1–13. Three tools returning the same leaked record remain one evidentiary origin. ICIJ's preservation of original addresses, source vintages, and human validation supports this lineage rule. [Country enrichment method](https://www.icij.org/inside-icij/2013/10/users-can-now-search-country-icij-offshore-leaks-database/), [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq), and [passport ML method](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/).

## B. Acquisition and processing playbooks

### Playbook 1 — Confidential heterogeneous corpus intake

**Trigger [inferred]:** A source supplies mixed files whose authenticity and contents are not yet known.

**Steps [inferred operationalization]:**

1. Isolate and preserve the received corpus; record acquisition channel, custodian, date, byte count, file manifest, and hashes.
2. Work from a protected copy and store originals on encrypted media.
3. Sample formats and corruption before selecting parsers.
4. Run Extract/Tika; route image-only pages through Tesseract; record tool versions and errors.
5. Index extracted text in a self-hosted Datashare project.
6. Authenticate corpus structure and sampled records against external official records before expanding reporting access.

**Failure modes [inferred unless directly noted]:** source exposure during cloud processing; parser silently skipping files; OCR mistaken for exact text; archive bombs or duplicate inflation; declaring the entire corpus authentic from a few matches. The processing pattern is documented by [ICIJ's massive-leak method](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/) and [Extract](https://github.com/ICIJ/extract); the manifest/hash details are **[inferred]** controls an autonomous system should add.

### Playbook 2 — Provider database to typed graph

**Trigger [inferred]:** Source material contains one or more business databases whose tables encode entities and roles.

**Steps [inferred operationalization]:**

1. Preserve the source database and inspect schema, keys, encoding, and deleted/status fields.
2. Write a provider-specific mapping to `Entity`, `Officer`, `Intermediary`, and `Address`, retaining the source's role text.
3. Preserve source IDs; namespace and record every generated ID.
4. Transform into node and relationship tables; reconcile duplicates without overwriting original values.
5. Load Neo4j and run count, orphan, cardinality, role, and referential-integrity checks.
6. Return every graph path to the provider row and, where possible, an original document.

**Failure modes [inferred unless directly noted]:** treating a role as ownership; merging names without identity proof; dropping isolated records without a logged rule; creating relationships from co-occurrence; losing source vintage. This playbook derives from the [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq), [data shape](https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html), and [package repository](https://github.com/ICIJ/offshoreleaks-data-packages).

### Playbook 3 — Reproducible watchlist or seed-list search

**Trigger [inferred]:** Reporting begins with a bounded list of people, companies, addresses, domains, sanctions targets, or officeholders.

**Steps [inferred operationalization]:**

1. Save the list's issuer, version, retrieval date, and each original identifier.
2. Generate exact-name, alias, transliteration, address, and identifier queries; preserve the transformation rule.
3. Lint the batch CSV and dry-run representative queries.
4. Run Datashare batch search and/or Offshore Leaks reconciliation.
5. Store hit, zero-hit, and failed-query states separately.
6. Manually adjudicate identity using address, date, jurisdiction, associates, and independent public records.

**Failure modes [inferred unless directly noted]:** commas/reserved syntax stopping a batch; fuzzy-match floods; list staleness; identical names; mistaking a sanctions-list or offshore-database hit for misconduct. Sources: [Datashare batch search](https://icij.gitbook.io/datashare/usage/batch-search-documents), [Offshore Leaks matching recipe](https://www.icij.org/inside-icij/2018/01/investigate-companies-found-offshore-leaks-database/), and [identity warning](https://offshoreleaks.icij.org/?e=true).

### Playbook 4 — Distributed manual extraction

**Trigger [inferred]:** Material facts are present in narrative documents, but automated extraction fails an audited sample.

**Steps [inferred operationalization]:**

1. Define a field dictionary with allowed null/unknown states and examples.
2. Build a form that displays source context beside the extraction fields.
3. Assign bounded records to trained reviewers.
4. Require independent repeated review and route disagreements to adjudication.
5. Record reviewer, timestamps, field edits, and source coordinates.
6. Freeze a versioned dataset for analysis; never silently edit published numbers.

**Failure modes [inferred unless directly noted]:** reviewer drift, copy/paste errors, inconsistent currencies or date ranges, ambiguous nulls, fatigue, and consensus without returning to the source. The three-reviewer precedent comes from [FinCEN Files](https://www.icij.org/investigations/fincen-files/mining-sars-data/); the explicit ledger controls are **[inferred]** extensions consistent with [Prophecies](https://github.com/ICIJ/prophecies).

### Playbook 5 — Machine-assisted classification with abstention

**Trigger [inferred]:** A large corpus contains a recurring class or missing field that can be inferred from text or images.

**Steps [inferred operationalization]:**

1. Define the claim the model is *not* allowed to make, especially causation or identity.
2. Hand-label a stratified sample; preserve disagreements and edge cases.
3. Train rules/model and evaluate precision, recall, coverage, subgroup/language errors, and leakage.
4. Set an abstention band; “unknown” is an acceptable output.
5. Send candidates and evidence context to human review in Prophecies.
6. Publish model/rule version, validation design, accuracy, coverage, and residual uncertainty.

**Failure modes [inferred unless directly noted]:** polysemy, multiple subjects per document, imbalanced classes, language transfer, deduplicated train/test leakage, confidential model artifacts, and reporting only accuracy while hiding low coverage. Sources: [Implant weak supervision](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/), [adverse-event classification](https://www.icij.org/investigations/implant-files/algorithms-analysis-and-adverse-events-how-icij-used-machine-learning-to-help-find-medical-device-issues/), and [passport CV](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/).

### Playbook 6 — Multilingual cross-border corroboration

**Trigger [inferred]:** A lead crosses jurisdictions or languages and cannot be verified centrally.

**Steps [inferred operationalization]:**

1. Assign a local partner with language, registry, political, and legal context.
2. Share the exact source record, claim, identity candidates, and uncertainties through the secure newsroom.
3. Use offline translation for confidential triage where practical, but verify consequential wording in the original language.
4. Have local reporters retrieve primary records and interview sources.
5. Run regional/language editorial review, then central cross-border consistency and legal review.
6. Preserve translations, translator/reviewer, and which language controls the claim.

**Failure modes [inferred unless directly noted]:** transliteration collisions, machine-translation leakage, literal translation losing legal meaning, inconsistent outlet standards, and inaccessible local registries. Sources: [West Africa Leaks](https://www.icij.org/investigations/west-africa-leaks/behind-the-scenes-of-the-largest-ever-west-african-journalism-collaboration/), [Luanda offline translation](https://www.icij.org/investigations/luanda-leaks/how-we-mined-more-than-715000-luanda-leaks-records/), and [ICIJ network model](https://www.icij.org/about/).

### Playbook 7 — Subject response as adversarial verification

**Trigger [inferred]:** A report is approaching publication and contains consequential claims about identifiable subjects.

**Steps [inferred operationalization]:**

1. Convert the draft into precise factual propositions and attach the evidence basis for each.
2. Send detailed questions early enough for a meaningful answer.
3. Log delivery, deadline, extensions, reply, attachments, and non-response.
4. Test every responsive assertion against primary records.
5. Correct identity, chronology, amount, role, or framing where evidence requires it.
6. Include the material response fairly and send unresolved legal issues to counsel.

**Failure modes [inferred unless directly noted]:** vague questions, deadline theater, leaking source-sensitive details, treating denial as exculpation or guilt, paraphrasing away the response's strongest point. Sources: [Panama subject-response account](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/) and [Ericsson question process](https://www.icij.org/investigations/ericsson-list/ericsson-facing-ongoing-probes-and-fallout-months-after-icij-revealed-new-corruption-breach/).

### Playbook 8 — Selective public data release

**Trigger [inferred]:** A project has structured evidence of durable public value, but the source corpus contains private or dangerous material.

**Steps [inferred operationalization]:**

1. Define the public-interest purpose and the minimum fields needed.
2. Exclude source communications, credentials, bank-account details, passports, telephone numbers, and unnecessary personal text.
3. Publish source investigations/providers, coverage period, transformation notes, exclusions, denominators, and known missingness.
4. Attach licenses, schema/data dictionary, stable IDs, and machine-readable downloads where safe.
5. Put identity/wrongdoing/vintage caveats at entry and result points.
6. Provide error, complaint, and correction routes; retain a version history.

**Failure modes [inferred unless directly noted]:** a “data dump” that re-victimizes people; false identity; derived fields mistaken for originals; silent refreshes; released denominator overstated as the full leak. Sources: [Offshore Leaks release policy](https://www.icij.org/inside-icij/2016/05/icij-releases-panama-papers-offshore-company-data/), [FinCEN download caveats](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/), and [Solitary Voices redaction](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/).

### Playbook 9 — Embargoed network publication

**Trigger [inferred]:** A verified cross-border story needs simultaneous publication to maximize reach or reduce suppression risk.

**Steps [inferred operationalization]:**

1. Vet partners for track record, institutional support, collaboration, and security.
2. Obtain a written confidentiality, non-redistribution, and embargo agreement.
3. Train participants and scope access.
4. Coordinate claims, local reporting, graphics/data, translations, fact-check, legal review, and readiness in a secure hub.
5. Freeze the release time and define emergency decision authority.
6. Publish simultaneously; continue sharing impact, corrections, and follow-up leads.

**Failure modes [inferred unless directly noted]:** partner leak, uneven legal readiness, premature local publication, ambiguous time zones, one outlet's claim unsupported elsewhere, and assuming software can create trust. Sources: [Panama embargo account](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/), [early written agreements](https://www.icij.org/inside-icij/2013/04/how-we-all-survived-likely-largest-collaboration-journalism-history/), and [partner selection](https://www.icij.org/investigations/panama-papers/faqs/).

## C. Provenance checklist for an autonomous research agent

An autonomous agent can adopt the following **16-point checklist**. Items marked **[inferred]** are controls synthesized from ICIJ's demonstrated machinery rather than a verbatim ICIJ checklist.

1. **Acquisition identity:** record source class, acquisition channel, custodian, received/retrieved time, authorization/public status, and confidentiality restrictions. **[inferred]** from ICIJ's leak-security and public-record distinctions. [Massive-leak methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/).
2. **Immutable source manifest:** preserve original files, relative paths, byte sizes, cryptographic hashes, archive membership, and a read-only working-copy boundary. **[inferred]** implementation control for ICIJ's encrypted source custody. [Massive-leak methods](https://www.icij.org/inside-icij/2018/07/how-icij-deals-with-massive-data-leaks-like-the-panama-papers-and-paradise-papers/).
3. **Authentication scope:** state whether authentication applies to corpus, collection, document, field, or claim; list independent records and inconsistencies. **[inferred]** from ICIJ's cross-check practice. [Pandora FAQ](https://www.icij.org/investigations/pandora-papers/frequently-asked-questions-about-the-pandora-papers-and-icij/).
4. **Extraction lineage:** record parser/OCR tool, version, options, language, timestamp, status, errors, and the pointer from extracted text to original file/page. **[inferred]** from [Extract](https://github.com/ICIJ/extract) and [Datashare document exploration](https://icij.gitbook.io/datashare/usage/explore-a-document).
5. **Source coordinates:** cite the canonical document ID plus page, sheet/cell, database/table/row, message, or text offset sufficient for another reviewer to reopen the evidence. **[inferred]** from ICIJ's source-document and structured-review workflows. [FinCEN method](https://www.icij.org/investigations/fincen-files/mining-sars-data/).
6. **Transformation ledger:** preserve every parse, normalization, translation, calculation, dedupe, join, geocode, and manual edit with before/after values and code/rule version. **[inferred]** from ICIJ's explicit added country fields and Solitary Voices derived fields. [Country enrichment](https://www.icij.org/inside-icij/2013/10/users-can-now-search-country-icij-offshore-leaks-database/) and [Solitary Voices](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/).
7. **Identifier discipline:** retain provider IDs; namespace generated IDs; never present an internal resolved-entity ID as a source identifier. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).
8. **Entity-resolution basis:** for every merge or match, store names/aliases, addresses, dates, identifiers, associates, jurisdiction, match method/score, reviewer, and counterevidence; common names alone are insufficient. [Offshore Leaks identity warning](https://offshoreleaks.icij.org/?e=true).
9. **Derived-output label:** mark NER mentions, co-occurrences, model classifications, graph projections, and inferences as derived; record model/rule version, score, coverage, abstention, and validation. **[inferred]** from [Datashare NER](https://icij.gitbook.io/datashare/usage/faq/definitions/what-is-a-named-entity) and [Implant weak supervision](https://www.icij.org/investigations/implant-files/we-used-ai-to-identify-the-sex-of-340000-people-harmed-by-medical-devices/).
10. **Role and relationship semantics:** use the source's exact role and edge type; distinguish officer, beneficiary, shareholder, intermediary, registered address, co-occurrence, and inferred control. [Offshore Leaks data shape](https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html).
11. **Vintage and coverage:** attach provider/investigation, start/end or “as of” dates, included jurisdictions, missing categories, and source-system undercount; do not treat no hit as present-day absence. [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq) and [Solitary Voices limitations](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/).
12. **Independent corroboration:** distinguish repeated copies of one record from independent origin; seek official records, local reporting, interviews, or physical/laboratory evidence appropriate to the claim. **[inferred]** from [Ericsson verification](https://www.icij.org/investigations/ericsson-list/ericsson-leak-isis-iraq-corruption/) and [hake DNA method](https://www.icij.org/investigations/looting-the-seas-ii/hake-dna-testing-how-we-did-it/).
13. **Human validation:** record assignments, reviewer identities, decisions, conflicts, adjudication, and edit history; require redundant review for high-stakes manually extracted or model-derived data. [FinCEN triple review](https://www.icij.org/investigations/fincen-files/mining-sars-data/) and [Prophecies](https://github.com/ICIJ/prophecies).
14. **Subject response:** preserve exact questions, sent/delivery time, response deadline, extension, full response and attachments, non-response, verification of new assertions, and resulting draft changes. **[inferred]** from [Panama response practice](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/).
15. **Editorial/legal/release gates:** separately record fact-check, editorial, legal, privacy/redaction, licensing, and embargo approvals; include caveats that inclusion or suspicion does not establish wrongdoing. **[inferred]** from [ICIJ review gates](https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/) and [Offshore Leaks search gate](https://offshoreleaks.icij.org/?e=true).
16. **Correction and supersession:** give findings and datasets a version; link complaints/errors to the affected claim or edge; preserve the prior state; publish what changed, why, when, and by whom. **[inferred]** extension of [ICIJ's complaint policy](https://www.icij.org/about/corporate/) and [Offshore Leaks correction record](https://offshoreleaks.icij.org/pages/faq).

## D. Cross-walk: what Ithildin already mirrors and what it can copy cheapest

**Platform baseline supplied by the commissioning brief:** Ithildin runs a local OpenAleph instance, holds the Offshore Leaks database, and has a corpus-ingest plus OCR pipeline. The assessments below are **[inferred]** from that stated baseline and ICIJ's cited infrastructure; they are not a code audit.

### Already mirrored or functionally adjacent

- **Confidential corpus custody, extraction, OCR, and search:** local OpenAleph plus the existing ingest/OCR pipeline is functionally adjacent to Extract + Datashare's document path. The cheapest gain is not another corpus platform; it is extraction provenance, batch-query reproducibility, and a clean pointer from derived text to original. ICIJ comparator: [Datashare](https://github.com/ICIJ/datashare) and [Extract](https://github.com/ICIJ/extract).
- **Offshore graph acquisition:** holding the Offshore Leaks database already supplies the public Neo4j/CSV entity-officer-intermediary-address evidence base. The cheapest gain is to retain provider, investigation, vintage, original ID, and caveat at every imported edge. ICIJ comparator: [data shape](https://offshoreleaks-data.icij.org/offshoreleaks/neo4j/guide/datashape.html) and [FAQ](https://offshoreleaks.icij.org/pages/faq).
- **Corpus-to-network reasoning:** OpenAleph entity extraction and the platform's own entity/connection layer are adjacent to Datashare NER plus graph analysis. The missing discipline may be explicit separation of mention, resolved identity, source-stated relationship, and analyst inference. ICIJ comparator: [Datashare NER](https://icij.gitbook.io/datashare/usage/faq/definitions/what-is-a-named-entity) and [Offshore graph schema](https://offshoreleaks.icij.org/schema/oldb).

### Cheapest high-value copies

1. **Caveat object and mandatory query gate — very cheap.** Add source vintage, identity-collision warning, “inclusion does not imply wrongdoing,” and error-reporting link to relevant dataset/search results, modeled on [Offshore Leaks](https://offshoreleaks.icij.org/?e=true).
2. **Provider/corpus transformation manifest — cheap.** For each ingest, store file/table counts, hashes, parser/OCR versions, mapping rules, source versus generated IDs, rejected records, enrichment fields, and validation counts. This operationalizes ICIJ's provider-specific [Pandora](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) and [Offshore Leaks](https://offshoreleaks.icij.org/pages/faq) practice.
3. **Batch-search run object — cheap.** Accept a CSV of exact/alias queries, lint it, store query-list provenance, distinguish zero hits from failures, and permit reruns against corpus snapshots. Model: [Datashare batch search](https://icij.gitbook.io/datashare/usage/batch-search-documents).
4. **Prophecies-like review state machine — cheap to moderate.** Extend existing findings/evidence review with assignments, independent votes, disagreement, adjudication, and immutable edits for manual extraction and model candidates. Model: [Prophecies](https://github.com/ICIJ/prophecies) and [FinCEN triple review](https://www.icij.org/investigations/fincen-files/mining-sars-data/).
5. **Subject-response packet — cheap.** Generate claim/evidence/question bundles and track delivery, deadline, full response, verification, and revision. This is mostly workflow and schema, modeled on [ICIJ's pre-publication practice](https://www.icij.org/investigations/panama-papers/cracking-the-veil-of-secrecy-ten-years-of-the-panama-papers-part-2/).
6. **Correction/supersession ledger — cheap.** Turn corrections into linked data rather than silent overwrites; ICIJ's public correction machinery shows the ethical requirement but leaves room for a more systematic implementation. Comparator: [ICIJ corporate policy](https://www.icij.org/about/corporate/) and [Offshore Leaks FAQ](https://offshoreleaks.icij.org/pages/faq).
7. **Selective-release manifest and template — cheap.** Require purpose, released denominator, excluded fields, privacy test, schema, license, limitations, and feedback route before any public export. Models: [FinCEN](https://www.icij.org/investigations/fincen-files/download-fincen-files-transaction-data/) and [Solitary Voices](https://www.icij.org/investigations/solitary-voices/about-the-solitary-voices-data/).

### Moderate engineering, high leverage

- **Search/review/graph context bridges:** deep links that carry corpus ID, document, query, page/offset, resolved entity, and discussion/review state across OpenAleph and Ithildin. ICIJ comparator: Datashare/I-Hub bridges in [ICIJ's 2020 technology note](https://www.icij.org/inside-icij/2020/01/how-icij-will-rock-its-tech-in-2020/) and [Datashare Neo4j extension](https://github.com/ICIJ/datashare-extension-neo4j).
- **Model-candidate gateway:** require every classifier or LLM extractor to emit candidates into the same human-review contract, with abstention, source context, model version, coverage, and reviewer decision. ICIJ comparator: [passport ML + Prophecies](https://www.icij.org/inside-icij/2025/05/how-we-use-machine-learning-to-find-passports-and-unlock-one-key-to-offshore-secrecy/).
- **Versioned public reconciliation endpoint:** because Ithildin already holds Offshore Leaks data, a bounded local reconciliation service could match research lists while enforcing vintage and identity warnings. ICIJ comparator: [2025 reconciliation API](https://www.icij.org/inside-icij/2025/01/explore-the-latest-tool-to-power-up-investigations-via-the-offshore-leaks-database/).

### Genuinely missing if the organization does not already supply them

- **Invitation-only trusted partner network:** no software feature creates ICIJ's decades of reputation, partner vetting, and willingness to share. Comparator: [radical sharing](https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/) and [partner criteria](https://www.icij.org/investigations/panama-papers/faqs/).
- **Cross-outlet embargo authority:** a dashboard can track readiness, but simultaneous publication requires written agreements, trusted editors, outlet commitment, emergency authority, and consequences. Comparator: [Panama embargo](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).
- **Multilingual local verification capacity:** translation software cannot replace reporters who understand registries, politics, naming conventions, defamation law, and source risk in each jurisdiction. Comparator: [West Africa Leaks](https://www.icij.org/investigations/west-africa-leaks/behind-the-scenes-of-the-largest-ever-west-african-journalism-collaboration/).
- **Editorial and legal accountability:** claim scoring can queue work, but public-interest balancing, fairness, source protection, privacy, and publication risk require accountable humans. Comparator: [ICIJ review doctrine](https://www.icij.org/investigations/luanda-leaks/lessons-from-award-winning-fincen-files-and-luanda-leaks-investigations/).

### Bottom line

**[inferred]:** Ithildin already owns much of the expensive machine substrate ICIJ had to build: local corpus search, OCR/ingest, a graph-capable investigation model, and the Offshore Leaks data. Its cheapest methodological advance is a *control plane for lineage and review*: provider manifests, reproducible batches, model/manual validation, subject-response packets, caveat gates, selective-release manifests, and correction objects. The expensive gap is organizational—trusted international partners who agree to share, verify locally, accept common security standards, and hold an embargo. ICIJ's machinery works because the machine and human control planes are coupled; copying only the software would copy the least distinctive half. ICIJ comparators: [Datashare](https://github.com/ICIJ/datashare), [Prophecies](https://github.com/ICIJ/prophecies), [radical sharing](https://www.icij.org/inside-icij/2016/12/radical-sharing-breaking-paradigms-achieve-change/), and [Panama Papers embargo coordination](https://www.icij.org/investigations/panama-papers/data-tech-team-icij/).
