# Cluster B: Investigative Data Platforms

## How the Best Investigative Data Organizations Present Complex Evidence to Multiple Audiences

*Research dossier for Ithildin content generation system design*

---

## 1. Executive Summary

Seven principles emerge from studying how the four leading investigative data platforms --- ICIJ, ProPublica, OCCRP, and Bellingcat --- handle the problem of presenting complex investigative data to audiences ranging from expert researchers to general readers. These should govern the design of Ithildin's output layer.

**Principle 1: The Three-Tier Output Model.** Every successful platform produces at least three output layers: (a) a searchable database for researchers who want to interrogate raw data, (b) curated narrative articles for general audiences who want to understand what the data means, and (c) methodology documentation for journalists and analysts who need to verify claims and reproduce results. ICIJ does this most explicitly with Offshore Leaks Database + partner articles + methodology pages. No platform does all three equally well. Ithildin must.

**Principle 2: Graph Databases Are the Right Substrate for Investigative Data.** Both ICIJ (Neo4j) and OCCRP (FollowTheMoney/PostgreSQL with graph semantics) converge on the same insight: investigative data is fundamentally about relationships, not records. The entity-relationship model --- people connected to companies connected to addresses connected to jurisdictions --- is a graph problem. Ithildin already uses this model in investigation.db. The content layer must expose graph structure to readers, not flatten it into tables.

**Principle 3: Network Visualization Works at Small Scale, Fails at Large Scale.** ICIJ's node-link diagrams are effective for showing how 3-8 entities relate to each other. They become unintelligible hairballs above ~50 nodes. No platform has solved the large-scale network visualization problem. ProPublica avoids it entirely. OCCRP limits diagrams to user-constructed subgraphs. Bellingcat does not attempt it. This is an open problem and a genuine opportunity.

**Principle 4: Show the Evidence, Not Just the Conclusion.** Bellingcat's signature technique --- walking readers through annotated screenshots, metadata analysis, and step-by-step verification --- is the gold standard for evidence presentation. ICIJ shows source data but not analytical reasoning. ProPublica shows methodology but not source documents. OCCRP shows entity connections but not the evidence behind them. Ithildin should combine Bellingcat's process transparency with ICIJ's data access and ProPublica's analytical methodology disclosure.

**Principle 5: The "Lookup Tool" Pattern Drives Engagement.** ProPublica's most successful applications (Dollars for Docs, Nonprofit Explorer, Surgeon Scorecard) share a design pattern: "Look up YOUR doctor / YOUR nonprofit / YOUR representative." Personalizing a massive dataset through individual lookup dramatically increases public engagement. The investigative equivalent is: "Search for any name, company, or address and see what connections exist." ICIJ's Offshore Leaks Database is exactly this pattern applied to offshore entities.

**Principle 6: Interstitial Entities Model Relationships Better Than Edge Properties.** OCCRP's FollowTheMoney data model represents relationships (Ownership, Directorship, Membership) as entities in their own right, not as edges with properties. An Ownership has an owner, an asset, a percentage, a start date, and a source document. This is more expressive than a simple edge and allows relationships themselves to carry evidence. Ithildin's connections table already works this way. The content layer should expose this richness.

**Principle 7: Methodology Transparency Increases Rather Than Decreases Trust.** Every platform that publishes its methods in detail (Bellingcat's step-by-step walkthroughs, ProPublica's Nerd Blog, ICIJ's data processing documentation) reports that transparency increases credibility. Readers who can see HOW a conclusion was reached trust it more than readers who are simply told WHAT the conclusion is. This is counterintuitive to journalists trained to foreground conclusions. Ithildin must show analytical process as a first-class output.

---

## 2. ICIJ (International Consortium of Investigative Journalists) Deep Dive

### The Offshore Leaks Database

The Offshore Leaks Database is the most important reference implementation for Ithildin's public-facing search layer. It contains information on more than 810,000 offshore entities from five major investigations: the Offshore Leaks (2013), Panama Papers (2016), Bahamas Leaks (2016), Paradise Papers (2017), and Pandora Papers (2021). Records span 80+ years and link to people and companies in more than 200 countries.

**Data model.** The database uses Neo4j with four node types: Entity (the offshore company, trust, or foundation), Officer (director, shareholder, or beneficiary of an entity), Intermediary (the law firm or service provider that created the entity), and Address (registered address as it appears in leaked records). Relationships include `OFFICER_OF`, `INTERMEDIARY_OF`, `REGISTERED_ADDRESS`, `CONNECTED_TO`, and `RELATED_ENTITY`. This is a simple but effective model --- four node types and five relationship types can represent the entire offshore corporate ecosystem.

**Search interface design.** The search box accepts names, jurisdictions, and locations. Results are organized into four tabs: Offshore Entities, Officers, Intermediaries, and Addresses. Each tab shows count badges so users immediately know the distribution of results. Left-side filters let users narrow by investigation dataset (Panama Papers, Pandora Papers, etc.) and by node type.

**How they handle 810K entities without overwhelming users.** Three mechanisms:

1. *Search-first, not browse-first.* The homepage is a search bar, not a list. Users must enter a query to see anything. This forces specificity and prevents information overload.
2. *Progressive disclosure.* Search results show minimal information (name, jurisdiction, investigation source). Clicking into a result reveals connections, addresses, officers, and the interactive visualization.
3. *The Power Players feature.* For general audiences who do not know what to search for, ICIJ curates a list of "notable names linked to offshore connections of world leaders, politicians, and their relatives and associates." This is editorial curation layered on top of the raw database --- exactly the three-tier model. The general reader gets Power Players. The journalist gets the search interface. The researcher downloads the CSV/Neo4j dump.

**Visualization.** When you click into a specific entity, the database shows an interactive node-link diagram. Nodes are color-coded by type (Entity, Officer, Intermediary, Address). Edges are labeled with relationship types. Clicking a node reveals its properties and expands its connections. The visualization uses a force-directed layout. External links to OpenCorporates provide supplementary corporate registry data.

**What works.** The visualization is excellent for small neighborhoods: "show me everyone connected to this specific shell company." It intuitively communicates the mediating role of intermediaries and the hub structure of service providers. The wildcard search (`Allaw*`) and fuzzy matching (`Allawi~2`) accommodate the messy, misspelled names common in leaked documents. Country-linked search lets investigators find all entities connected to a specific jurisdiction through registered addresses.

**What does not work.** The visualization breaks down above approximately 20 nodes. For a major intermediary or a politically exposed person with dozens of connections, the graph becomes an unintelligible tangle. There is no hierarchical view showing ownership chains from beneficial owner down to operating entity. There is no temporal dimension --- you cannot see when entities were created, transferred, or dissolved. There is no financial data --- the database tracks structural relationships but not money flows, account balances, or transaction histories. As ICIJ itself acknowledges: "In isolation, the Offshore Leaks Database does not tell the full story about an offshore business." It shows structure without context.

### The Technology Stack

ICIJ's investigative infrastructure rests on three platforms:

**Datashare.** An open-source document analysis tool built by ICIJ with EPFL (Ecole Polytechnique Federale de Lausanne). It processes millions of documents in multiple languages and formats, using NLP to extract named entities (people, organizations, locations, email addresses). Its killer feature is batch search: a journalist can search for all 535 members of the US Congress across millions of documents in a single operation. Datashare has been downloaded over 20,000 times. ICIJ does not track user data for privacy reasons. In 2024, ICIJ added a Neo4j plugin to Datashare, allowing journalists to extrapolate information from documents into graph visualizations connecting people and corporate entities.

**I-Hub.** A secure social media and messaging platform that served as the digital newsroom for Pandora Papers. 150 media partners worked in regional groups, sharing discoveries, forming story teams, and coordinating publication timing. I-Hub is essentially a private, secure Slack for investigative journalists working on the same dataset.

**Linkurious on Neo4j.** Linkurious is a commercial graph visualization and exploration tool that sits on top of Neo4j. It was chosen because it required no technical expertise --- journalists around the globe could search and explore the graph database visually without writing Cypher queries. During the Panama Papers, 370 journalists used Linkurious to investigate. For published articles, ICIJ used the Linkurious Enterprise API to create and embed graph visualizations directly into stories.

**Data processing pipeline.** Raw leaked documents are processed through Apache Solr and Tika for metadata extraction. Structured data from leaked databases is used to connect extracted entities. The result is loaded into Neo4j. For the Pandora Papers, ICIJ also used Python for automated data extraction, machine learning (Fonduer, Scikit-learn) to identify and separate form types from longer documents, and custom scripts for cross-referencing entities across the 14 different offshore service firms in the dataset.

### The Collaboration Model

The Pandora Papers involved 600+ journalists from 150 media outlets in 117 countries. This is unprecedented scale for investigative collaboration. Three design decisions made it work:

1. **Coordinated publication.** All partner organizations agreed to publish on the same date. This created global impact that no single outlet could achieve alone and prevented competitive scooping.
2. **Regional working groups.** Journalists worked in regional teams, sharing leads relevant to their jurisdictions. A German journalist finding a connection to a Czech politician would pass it to the Czech team.
3. **Central data team.** ICIJ's technical team processed, structured, and hosted the data. Individual journalists did not need to set up their own infrastructure. This solved the "lowest common denominator" problem of multi-organizational tech collaboration.

The collaboration model's weakness is selectivity. ICIJ profiled 60 of the biggest political names in their Power Players feature but acknowledged there were "likely more political figures in the documents than 336" --- the published figure represented those that passed their verification criteria. Resource constraints forced editorial choices that left most of the data unexplored by the consortium's journalists.

### The 2025 API Update

In January 2025, ICIJ introduced a reconciliation API for the Offshore Leaks Database, funded by the German development agency GIZ. The API enables automated data matching: users can submit their own datasets (names, addresses, corporate entities) and get back matches against the Offshore Leaks data. This moves ICIJ from a search-and-browse model to a programmatic integration model. The database attracts ~250,000 monthly visitors. The reconciliation API is designed for financial regulators, compliance teams, and investigative journalists who want to cross-reference their own data against the leaks.

### The Layered Output Model

ICIJ's output model is the clearest implementation of the three-tier approach:

| Layer | Audience | Product | Access |
|-------|----------|---------|--------|
| Raw data | Researchers, regulators | Neo4j database dump, CSV downloads | Free download |
| Searchable interface | Journalists, investigators | Offshore Leaks Database | Web, free |
| Curated narratives | General public | Partner articles (Guardian, WaPo, etc.) | Via partner outlets |
| Methodology | Journalism community | How-to guides, data documentation | ICIJ.org |
| Highlighted findings | Politically engaged public | Power Players | Web, free |

### What to Steal for Ithildin

- The four-node-type data model (Entity, Officer, Intermediary, Address) as a minimal graph schema for corporate networks. Ithildin already has this in entities/connections.
- Search-first interface design. Never show a raw list. Force the user to query.
- Progressive disclosure: minimal search results expanding to full entity profiles with embedded visualizations.
- The reconciliation API concept: let external tools query Ithildin's entity database for matches.
- The batch search feature from Datashare: search for a list of names simultaneously.
- The Power Players editorial curation layer on top of raw data.

### What to Avoid

- ICIJ's visualizations break at scale. Do not use force-directed graph layouts for any graph larger than ~20 nodes without aggressive filtering, clustering, or hierarchical decomposition.
- The database contains no financial data, no temporal data, no evidence quality metadata. It is structure without substance. Ithildin must pair structure with evidence, confidence levels, and financial flows.
- ICIJ's collaboration model is designed for one-time leak events. Ithildin's investigation is ongoing and cumulative. The output system must handle continuously evolving data, not static snapshots.
- No explanatory layer. ICIJ shows connections but never explains WHY a particular corporate structure was chosen or what purpose it serves. That is the gap Cluster A's writers fill with text, and Ithildin must fill with both text and interactive explanation.

---

## 3. ProPublica Deep Dive

### The "News Apps" Philosophy

ProPublica's news applications team, led for many years by Scott Klein, defined the practice of building custom interactive software for specific investigations. The team's composition is revealing: journalists, statisticians, designers, and programmers, with each member expected to have at least two of the three core skills (code, design, journalism) and learn the third. The team is treated as a news desk, not an engineering shop. Everyone is expected to be a journalist first.

The philosophy that produced ProPublica's best work can be summarized: do not put a pretty interface around publicly available data. Analyze it, clean it, mash it together with other data, and tease out trends and outliers. Then build an interface that lets readers explore those findings. The interactive tool is not a visualization of raw data --- it is a visualization of analytical results.

This distinction matters for Ithildin. The temptation is to expose investigation.db directly through a web interface. ProPublica's lesson is that the value comes from the analysis layer between raw data and presentation: risk-adjusting surgeon complication rates, normalizing pharmaceutical payment data across companies with different disclosure formats, computing effective tax rates from raw 990 filings. The tool shows the result of that analysis, not the raw inputs.

### Key Applications and Their Design Patterns

**Nonprofit Explorer.** The most relevant ProPublica application for Ithildin. It makes IRS Form 990 data searchable and browsable. ProPublica parses the 990 XML data (1.9+ million electronically filed documents since 2010) and presents it in a layered interface:

- *Summary view:* Organization name, EIN, location, NTEE category, total revenue, total expenses, executive compensation. This is the "card" that appears in search results.
- *Detail view:* Full financial breakdown rendered to look like the paper 990 form. ProPublica adapted open-source IRS stylesheets to render digital forms visually identical to paper filings from 2013 onward.
- *PDF access:* Links to original PDF filings going back to 2001.
- *API:* A public API (v2) that developers can use to access organization profiles and full-text search programmatically.

The critical design decision: ProPublica shows the SUMMARY (revenue, expenses, compensation) on the search results page, and the FULL FORM on the detail page. The summary answers "is this organization interesting?" The full form answers "what exactly are its finances?" This two-level structure prevents both information overload (showing everything at once) and information starvation (showing too little to make decisions).

**Dollars for Docs.** Tracked ~$12 billion in pharmaceutical company payments to more than 1 million US physicians. The design pattern is the "personal lookup": enter your doctor's name, see what payments they received. By default, payments under $250 are hidden to reduce noise. The app includes a methodology explanation ("About the Data") and a data dictionary. The raw data was also sold through the ProPublica Data Store for journalists and researchers who wanted to do their own analysis.

**Surgeon Scorecard.** Calculated risk-adjusted complication rates for surgeons performing eight elective procedures using Medicare data. The visualization presents each surgeon's adjusted complication rate (ACR) not as a single number but as a confidence interval, shaded to reflect probability concentration. Green, yellow, and red segments provide national benchmarks. This is sophisticated statistical communication --- the confidence interval is the honest way to represent uncertainty, and the color coding makes it immediately comprehensible.

Surgeon Scorecard was also ProPublica's most controversial application. Academic researchers (RAND, PubMed studies) criticized the methodology: 82% of operations were excluded by inclusion criteria, and 84% of complications occurred during inpatient hospitalization and were missed by the measure. ProPublica published a detailed rebuttal. The controversy itself is instructive: when you publish methodology, you invite methodological critique. ProPublica chose transparency and weathered the challenge rather than hiding behind proprietary methods.

**FEC Itemizer.** Allows browsing of electronic campaign finance filings from the FEC. Updated every 15 minutes for electronic filings. ProPublica also created a visualization showing the 200 biggest recipients of expenditure money from presidential campaigns and super PACs, using a Sankey diagram (flow diagram showing direction and volume simultaneously). The Sankey diagram is one of the few visualization choices in investigative journalism that effectively communicates money flows at scale.

### The "Nerd Box" and Methodology Transparency

The "Nerd Box" is a term of art in data journalism for the methodology section that accompanies an interactive database. ProPublica's approach goes beyond what most newsrooms do. Their Nerd Blog (propublica.org/nerds) is a full publication explaining the technical decisions behind their news applications: what data sources they used, how they cleaned and processed data, what statistical methods they applied, what limitations exist, and what caveats readers should keep in mind.

For Surgeon Scorecard, the methodology documentation included: what procedures were analyzed, what data sources were used (Medicare claims), how risk adjustment worked (mixed effects model controlling for patient age, gender, comorbidities), what the inclusion criteria were, what the confidence intervals meant, and a detailed FAQ addressing the most common questions. When RAND published a critique, ProPublica published a point-by-point rebuttal. This level of transparency is rare in journalism and unprecedented in most analytical contexts.

The key insight: the Nerd Box is not just for credibility. It is a form of data journalism in itself. The methodology explanation often reveals as much about the subject as the findings do. In the Surgeon Scorecard case, the methodology debate revealed fundamental disagreements about how to measure surgical quality --- which is itself a story about the state of medical accountability.

### ProPublica's Conceptual Model for News Apps

ProPublica developed a formal framework for understanding interactive databases, structured around six interdependent categories:

1. **Code:** Production software, data acquisition tools, proprietary libraries
2. **Data/Input:** Raw and cleaned datasets, metadata, data dictionaries, structural documentation
3. **Story/Output:** Narrative content, published APIs, visual elements, information architecture
4. **Infrastructure:** Browsers, servers, frameworks, external API dependencies
5. **Process:** Code documentation, version histories, data transformation records, FOIA requests
6. **Response:** User comments, metrics, awards, real-world impact measurements

The deliberate choice of "interdependent, non-hierarchical categories" over layers reflects ProPublica's insight that building a news application requires simultaneous consideration of all six dimensions. For Ithildin, this framework suggests that the content output system should not be designed as a presentation layer on top of a data layer. The presentation, data, methodology, and response layers are all intertwined and should be designed together.

### The ProPublica Data Store

ProPublica operated a Data Store from 2013 to 2023, packaging datasets for download by journalists, researchers, and the public. The store is no longer updated but remains available as an archive. It represented ProPublica's commitment to making their analytical products available as raw materials for further investigation --- a principle Ithildin should adopt.

### What to Steal for Ithildin

- The "personal lookup" pattern: make the first interaction "search for a name" rather than "read an article." Ithildin's entity search should be the front door.
- The summary/detail two-level structure from Nonprofit Explorer. Entity search results show name, type, connection count, evidence confidence. Click through to full entity dossier.
- The confidence interval visualization from Surgeon Scorecard. Finding confidence levels should be shown as ranges with visual indicators, not single values.
- The Sankey diagram for money flows. This is the correct visualization for following financial flows through intermediary entities.
- The Nerd Blog model: methodology documentation as a first-class output. Every analytical method used by Ithildin agents should have a corresponding methodology explanation accessible to readers.
- The six-category conceptual model for designing the output system holistically.
- The API-first approach: build the data API first, then build the UI on top of it. Nonprofit Explorer's API predated and enabled its interface.

### What to Avoid

- ProPublica builds each application as a standalone project. Dollars for Docs, Nonprofit Explorer, and Surgeon Scorecard share no common infrastructure. Each is a custom web application. This does not scale. Ithildin needs a unified platform that can host many different types of investigative content.
- ProPublica does not attempt network visualization. Their strength is tabular/statistical data (payments, filings, scores), not relational data (ownership chains, money flows, corporate hierarchies). Ithildin must handle both.
- The Data Store is dead. The model of packaging datasets for download has been superseded by APIs. Ithildin should expose data through APIs and embeddable widgets, not downloadable CSVs.
- ProPublica's applications do not link to each other. A nonprofit found in Nonprofit Explorer has no connection to its officers' Dollars for Docs payments or its political contributions in FEC Itemizer. Ithildin's power is precisely in connecting across data domains.

---

## 4. OCCRP (Organized Crime and Corruption Reporting Project) Deep Dive

### Aleph: The Investigative Data Platform

Aleph is the closest existing system to what Ithildin aims to be: a cross-border investigation platform that combines document search, entity extraction, network visualization, and collaborative analysis. It was created by OCCRP and is being rebuilt as Aleph Pro, which launched in October 2025. Understanding Aleph's architecture, strengths, and limitations is essential for Ithildin's design.

**Architecture.** Aleph's core components:

- *FollowTheMoney store (PostgreSQL):* Stores all structured data as FtM entities.
- *App database (PostgreSQL):* Stores metadata --- users, permissions, collections, notifications.
- *Elasticsearch:* Makes FtM entities searchable. Aleph maintains a separate Elasticsearch index per FtM schema, with automatically configured mappings for each entity type. This "hybrid" mapping enables both full-text search across all properties and structured filtering on specific fields (email addresses, dates, etc.).
- *Entity extraction (spaCy):* When files are uploaded, Aleph uses language-specific spaCy NLP models (e.g., en_core_web_sm for English, es_core_news_sm for Spanish) to extract names of people, companies, countries, plus phone numbers, email addresses, and IBANs. A custom fastText classifier reduces false positives.
- *File processing:* Documents are converted to text, indexed, and linked to extracted entities.

**Search capabilities.** Aleph provides full-text search across millions of documents, cross-referencing across datasets (linking people and companies that appear in multiple collections), and entity-focused browsing. Users can search by name, address, phone number, email, or document content. Results show both structured entity data and document excerpts with highlighted matches.

### The FollowTheMoney Data Model

FollowTheMoney (FtM) is the conceptual core of Aleph and the most sophisticated investigative data model in public use. Key design decisions:

**Entity types for investigations.** FtM defines entities commonly used in anti-corruption reporting. The schema includes:

| Category | Entity Types |
|----------|-------------|
| People & Organizations | Person, Company, Organization, PublicBody |
| Documents | Document, Email, Pages, Table, Audio, Video, Image |
| Financial | Payment, BankAccount, CryptoWallet, Debt |
| Relationships | Ownership, Directorship, Membership, Representation |
| Legal | CourtCase, Sanction |
| Identity | Passport, Identification |
| Physical | Address, RealEstate, Vehicle, Vessel |
| Events | Event, Trip |
| Analytical | Mention, UnknownLink |

**Interstitial entities for relationships.** This is FtM's most important design decision. Rather than modeling relationships as edges with properties (the typical graph database approach), FtM models relationships as entities in their own right. An Ownership is not just an edge between a Person and a Company --- it is an entity with its own properties: owner (reference to Person), asset (reference to Company), percentage, startDate, endDate, and crucially, its own source document references. This means:

- Relationships can carry evidence. "Person X owns Company Y" can cite a specific corporate filing as its source.
- Relationships have temporal extent. Ownership begins and ends.
- Relationships have quantitative attributes. 51% ownership is materially different from 5%.
- Relationships can participate in other relationships. A Directorship can be connected to a Sanction.

When converting to a property graph for visualization, these interstitial entities "contract" into edges. A Membership entity connecting a Person to an Organization becomes an edge in the network diagram. But the underlying data model retains the full richness.

**Schema hierarchy.** Entity types inherit from base types: Thing (the root), Interval (entities with temporal extent), LegalEntity (Person, Organization, Company), and Analyzable (entities that can be processed for NER and other analysis). Properties are multi-valued (a Person can have multiple names, nationalities, or addresses) and always stored as strings.

### Network Diagrams in Aleph

Aleph's network diagram feature is a manual investigation tool, not an automated visualization. To create a network diagram, a user:

1. Opens an investigation workspace
2. Clicks "New diagram"
3. Manually adds entities to the canvas (from search results or by creating new ones)
4. Draws relationships between entities
5. Arranges the layout manually or with auto-layout

This is fundamentally different from ICIJ's approach, where the visualization is generated automatically from the database. Aleph's diagrams are user-constructed analytical artifacts --- they represent what the investigator has found and how they interpret it, not the raw data. This is closer to how Ithildin's analysis agents work: they construct an interpretation of the evidence, not just a dump of the data.

The diagrams can be exported as images or as Neo4j-compatible graph data. They can also be shared with other Aleph users within the same investigation workspace.

**Limitation:** The diagrams are purely qualitative. They show that connections exist but do not encode financial amounts, temporal sequences, or evidence confidence. There is no way to filter a diagram by date range, minimum ownership percentage, or evidence quality.

### Visual Investigative Scenarios (VIS)

VIS is OCCRP's publication-focused visualization tool, separate from Aleph's investigation diagrams. It provides "professionally designed, customizable, dynamic HTML5 visualization templates" for translating complex investigations into publishable graphics. VIS visualizations can illustrate "entities, networks and complex configurations of data" and can be exported for online, print, or broadcast media.

VIS emerged from OCCRP's and RISE Project's need to make cross-border investigations understandable to wider audiences. Unlike Aleph's investigation-oriented diagrams, VIS is designed for communication: the output is a polished, editorial graphic that explains a finding, not a workspace for exploring data.

The distinction between Aleph (investigation tool) and VIS (communication tool) maps directly onto Ithildin's need for both analytical workspaces (investigation agents) and publication outputs (explainer/dossier writers).

### The Laundromat Investigations

OCCRP's Russian Laundromat and Azerbaijani Laundromat investigations are the best examples of how they present complex corporate networks to readers. The Azerbaijani Laundromat traced $2.9 billion through four UK-registered shell companies (Polux Management LP, Metastar Invest LLP, Hilux Services LP, LCM Alliance LLP) to Danske Bank accounts in Estonia.

**Presentation approach.** OCCRP used clickable thumbnail images of actual filed corporate documents rather than abstract corporate diagrams. Readers could click to see what each company filed with banking and regulatory authorities. The narrative text explained connections between entities while the documentary evidence provided verifiable proof. Comparison tables highlighted discrepancies between UK Companies House filings and Estonian bank filings.

This approach --- source documents as evidence, narrative as explanation, comparison tables as analysis --- emphasizes authenticity over abstraction. The reader is not asked to trust a diagram; they can inspect the actual documents. However, it does not scale: presenting source documents for a network of 50+ entities would be unwieldy.

### Aleph Pro and the Future

In 2025, OCCRP announced Aleph Pro as a complete rebuild of the platform. Key changes:

- **Performance and stability improvements** across the board
- **Confidence labeling on connections** --- finally allowing evidence quality metadata on relationships
- **Enhanced knowledge graph generation** --- better data models for linking, filtering, and insights
- **Free for non-profit journalism**, at-cost for public interest groups, commercial pricing planned for 2026
- **Open source divergence:** OCCRP will no longer contribute to the open-source Aleph codebase. DARC (Data and Research Center) has spun off OpenAleph as the community-maintained open-source fork. This is significant: the open-source investigative platform ecosystem is fragmenting.

### Relationship to ICIJ

OCCRP and ICIJ collaborate frequently but serve different functions. ICIJ is an investigation coordination body --- it organizes large-scale collaborative investigations around specific leaks. OCCRP is an ongoing investigation platform --- it maintains persistent data infrastructure and pursues investigations continuously. ICIJ's investigations are event-driven (a new leak arrives); OCCRP's are target-driven (follow specific corruption networks over years).

ICIJ's data is leak-centric: everything in the Offshore Leaks Database came from specific leaked datasets. OCCRP's Aleph aggregates data from many sources: corporate registries, financial records, court filings, sanctions lists, and leaks. This makes Aleph's data more heterogeneous and harder to search but more comprehensive.

For Ithildin, the model is closer to OCCRP's: an ongoing investigation platform aggregating multiple data sources, not a one-time leak analysis.

### What to Steal for Ithildin

- The FollowTheMoney interstitial entity model for relationships. Ithildin's connections table already works this way; the content layer should expose relationship evidence, dates, and confidence.
- The separation between investigation workspace (Aleph) and publication output (VIS). Ithildin agents investigate; the content pipeline publishes. These are different tools with different design requirements.
- Aleph's hybrid search: full-text across all properties PLUS structured filtering on dates, entity types, jurisdictions. Ithildin's search must do both.
- Source document presentation from the Laundromat investigations: show the actual filing alongside the analytical claim.
- Confidence labeling on connections (from Aleph Pro roadmap).

### What to Avoid

- Aleph's network diagrams are manual and qualitative. For Ithildin, diagrams should be generated from the database with user-configurable filters, not hand-drawn.
- Aleph's entity extraction (spaCy) produces many false positives that require manual review. Ithildin's agents should do the curation before entities reach the content layer.
- The open source / commercial split (Aleph vs. Aleph Pro) has fragmented the community. Ithildin should avoid architectural decisions that force a similar choice.
- OCCRP's publication output (VIS) uses pre-designed templates. This limits the types of structures that can be visualized. Ithildin needs a more flexible visualization system that can render arbitrary graph subsets.

---

## 5. Bellingcat Deep Dive

### The Open Source Investigation Methodology

Bellingcat's contribution to investigative data presentation is not technical infrastructure (they build no databases, no search platforms, no visualization tools). It is methodological: they invented and popularized the practice of showing readers every step of an investigation, making the process itself the evidence.

This is philosophically distinct from what ICIJ, ProPublica, and OCCRP do. Those organizations present conclusions backed by data. Bellingcat presents the reasoning chain itself: here is the photo, here is the metadata, here is what we compared it to, here is why we conclude this. The reader can follow the logic and, in principle, reproduce it.

### Evidence Presentation: The Step-by-Step Walkthrough

Bellingcat's signature presentation technique is the annotated visual walkthrough. In the MH17 investigation:

1. Open-source photographs and videos posted online were collected
2. Landmarks visible in images were compared to satellite imagery (Google Maps, Google Earth)
3. Geolocation confirmed: matching multiple unique objects in each image to establish precise locations
4. The missile launcher was tracked from its origin at a Russian military base in Kursk through separatist territory
5. Forensic image analysis (using Tungstene software) confirmed photographs were not digitally altered
6. Russian Ministry of Defense satellite imagery was shown to be "so heavily manipulated that it lacks any credibility"

Each step is presented with annotated images: circles highlighting matching features, side-by-side comparison of ground-level and satellite views, arrows indicating direction of travel. The reader does not have to trust Bellingcat's conclusion; they can inspect the evidence and follow the logic.

**Why this works:** The evidence chain is laid bare. Each inference step is small enough to evaluate independently. The reader accumulates confidence through a series of individually verifiable claims rather than being asked to accept a single complex conclusion.

### The Navalny Investigation: Data-Driven Evidence Chains

The 2020 investigation identifying FSB operatives who poisoned Alexey Navalny demonstrates Bellingcat's most sophisticated evidence presentation:

**Data sources.** Russia's porous data infrastructure provided: phone records with geolocation data, passenger manifests, vehicle registration databases, Telegram bot services providing passport numbers and traffic violations. These were accessed through leaked databases and cryptocurrency-purchased services.

**Cross-referencing methodology.** Bellingcat built the case through layered corroboration:

- *Parallel flight matching:* Cross-referencing Navalny's travel itinerary against passenger manifests from parallel flights identified suspicious travelers with mismatched departure dates.
- *Phone metadata analysis:* Cell tower location data showed FSB operatives' phones activating near Navalny's hotels.
- *Pattern recognition:* Fake personas used predictable algorithms --- same first names, birth dates shifted by one year, surnames matching wives' maiden names.
- *Co-traveler analysis:* Tracking co-occurrence of multiple operatives across years of travel records.

**Presentation to readers.** The methodology article walks readers through the investigative workflow step by step: how they connected one operative's phone to an FSB identity via the GetContact app, how vehicle registration addresses revealed an FSB facility, how parking payment records linked operatives to specific targets. The narrative structure is "here is what we found, and here is exactly how we found it."

Christo Grozev, Bellingcat's lead researcher on the investigation, published a publicly accessible Google Sheets database containing the travel history of alleged FSB operatives: dates, departure and arrival locations, flight and train numbers. This is evidence transparency taken to its logical extreme --- the raw data is public, the analytical method is documented, and the conclusions are falsifiable.

### The Skripal Investigation: Identity Unmasking

The Skripal poisoning investigation identified three GRU officers (Anatoliy Chepiga, Alexander Mishkin, Denis Sergeev) through:

- Cross-referencing cover identities against leaked Russian databases
- Telephone metadata showing coordination patterns (11 calls between Sergeev in London and a Moscow contact during the attack weekend)
- Vehicle registration data linking cover identities to real identities
- Travel record analysis showing Chepiga and Mishkin at the same London location as Sergeev at precisely the time they took a train to Salisbury

**The identity confirmation technique.** Bellingcat establishes identity through convergent evidence from multiple independent databases. No single database proves identity; the accumulation of consistent data points across phone records, travel records, vehicle records, and residential records creates a mosaic that makes alternative explanations implausible.

### Evidence Preservation

Bellingcat's Auto Archiver, launched in 2022, has preserved over 150,000 web pages and social media posts. This addresses the fundamental problem of digital evidence: content can be deleted, modified, or taken down after publication. Archiving serves both investigative (preserving evidence) and legal (maintaining chain of custody) functions. Courts require documented chain of custody for digital evidence, which also applies to social media posts that may corroborate testimony.

### The Berkeley Protocol and Legal Admissibility

Bellingcat's methodology has been tested in court. In a 2023 case before the European Court of Human Rights, open-source evidence was upheld. The court stated it did "not accept that these criticisms show any general tendency to manipulate evidence or any general flaws in the analysis or approach taken by the authors of the reports." The key to legal admissibility was explaining and documenting how discrepancies arose (e.g., metadata timezone issues, compression artifacts) and proving they were not signs of manipulation.

The Berkeley Protocol on Digital Open Source Investigations provides the framework: investigators must document their search methodology, archive original sources, maintain chain of custody, and be transparent about limitations.

### Limitations for Financial Investigations

Bellingcat's methodology has a fundamental limitation that is directly relevant to Ithildin: it does not work well for financial investigations. As multiple sources note:

- "Open source information alone will not allow you to conduct a full investigation into money laundering."
- To trace money laundering, "one must have access to financial records, be able to follow paper trails through foreign banks, closely read loan contracts with shell companies."
- "IFF-related corporate networks are likely to be large and complex. Without the right technology, investigators can only get so far."

Bellingcat's strength is visual and geospatial evidence: photographs, satellite imagery, social media posts, phone metadata, travel records. Financial evidence --- transaction records, corporate filings, trust instruments, compliance reports --- lives in documents and databases, not in photographs. Bellingcat's tools and techniques are poorly suited to this domain.

Bellingcat's own toolkit acknowledges this by linking to ICIJ's Offshore Leaks Database and OCCRP's Aleph for financial investigations. For corporate structure research, they recommend OpenCorporates, ICIJ data, and national corporate registries rather than their own OSINT techniques.

### What to Steal for Ithildin

- The step-by-step evidence walkthrough as a content format. For each major finding, show: (1) what we found, (2) in which source, (3) how we verified it, (4) what it connects to, (5) what remains uncertain. This is exactly what Ithildin's `claim_type`, `source_quote`, and `verification_status` fields were designed to support.
- The convergent evidence technique: establish conclusions through multiple independent data points, not single sources. "3 sources returning the same document is redundancy, not corroboration" is already an Ithildin principle.
- Evidence preservation and archiving. Ithildin already stores source quotes and EFTA IDs, but should also archive the original documents/pages cited.
- The annotated visual technique applied to corporate documents: annotate 990 filings to highlight key line items, annotate corporate filings to highlight key relationships, annotate financial records to highlight suspicious transactions.
- Publish raw evidence data (like Grozev's Google Sheets travel database) to enable independent verification.

### What to Avoid

- Do not attempt to apply Bellingcat's visual/geospatial methods to financial evidence. They do not transfer. A corporate filing cannot be "geolocated."
- Bellingcat's investigations are episodic (a specific event triggers investigation). Ithildin's investigation is cumulative (every finding feeds the next lead). The evidence presentation must support accumulation, not just individual investigations.
- Bellingcat's evidence chains are typically linear (this photo proves this location proves this identity). Financial evidence chains are typically networked (this entity connects to that entity through three different mechanisms). Linear presentation does not work for network evidence.
- Bellingcat produces no interactive tools for readers to explore data themselves. Everything is editorial: the investigator chooses what to show and how to show it. For Ithildin's three-tier model, this covers only the curated narrative layer. The raw data and search tool layers need different approaches.

---

## 6. Cross-Cutting Analysis

### 6.1 Layered Presentation

How does each platform handle the tension between researchers (who want raw data), journalists (who want curated leads), and the general public (who want narrative)?

| Platform | Researcher Layer | Journalist Layer | Public Layer | Integration |
|----------|-----------------|-----------------|-------------|-------------|
| ICIJ | Neo4j dump, CSV download, reconciliation API | Offshore Leaks search, Datashare, I-Hub | Power Players, partner articles | Weak --- layers are separate products |
| ProPublica | API, Data Store (archived) | Same tools as public (no journalist-specific layer) | Interactive apps (Nonprofit Explorer, Dollars for Docs) | Moderate --- API enables journalist use of public tools |
| OCCRP | Aleph search, FtM data export | Aleph investigation workspaces, network diagrams | VIS published graphics, curated articles | Strong --- Aleph serves multiple layers through access controls |
| Bellingcat | Published datasets (Google Sheets), toolkit | Methodology guides, training materials | Narrative articles with step-by-step evidence | Weak --- no unified platform |

**Synthesis for Ithildin:** OCCRP's approach is closest to right: a single platform with different access levels and views for different audiences. But OCCRP's public layer (VIS graphics) is too static, and its researcher layer (raw FtM export) is too raw. Ithildin should provide:

1. *Researcher layer:* API + bulk data export + investigation.db direct access
2. *Journalist layer:* Entity search + finding search + connection browser + methodology documentation
3. *Public layer:* Curated dossiers + mechanism explainers + interactive visualizations with guided navigation

### 6.2 Evidence Presentation and the Trust Gap

The "trust gap" is the problem of presenting evidence that readers cannot independently verify. A reader can verify a public corporate filing. They cannot verify a leaked email's authenticity. They cannot reproduce a statistical analysis. They cannot evaluate whether an entity extraction algorithm correctly identified a name.

| Platform | Trust Mechanism | Limitation |
|----------|----------------|------------|
| ICIJ | "The data came from leaked documents. We show you the connections." | No explanation of how connections were extracted from documents. Reader trusts ICIJ's data processing. |
| ProPublica | "Here is our methodology. Here is the raw data. Here are the caveats." | Methodology can be scrutinized (Surgeon Scorecard RAND critique), but most readers will not. |
| OCCRP | "Here are the source documents. Click to see the filings." | Document presentation works for individual claims. Does not scale to network-level claims. |
| Bellingcat | "Here is every step of our reasoning. Follow along." | Works for visual/geospatial evidence. Does not work for financial evidence that requires domain expertise to evaluate. |

**Synthesis for Ithildin:** Layer the trust mechanisms:

1. *For claims based on primary sources:* Show the source document (OCCRP approach). Link to EFTA ID, 990 filing, corporate registration.
2. *For analytical conclusions:* Show the methodology (ProPublica approach). Explain claim_type, confidence levels, what evidence supports the claim.
3. *For network claims:* Show the evidence chain (Bellingcat approach). Walk through: "Entity A filed at this address → the same address appears on Entity B's registration → Entity B's officer is Person C → Person C is also an officer of Entity D."
4. *For inferences:* Label them explicitly. "This is an inference based on temporal correlation, not documented causation."

### 6.3 Network Visualization

What approaches do they use for corporate networks, ownership hierarchies, and money flows?

**ICIJ: Force-directed node-link diagrams.** Nodes are color-coded by type (Entity, Officer, Intermediary, Address). Edges show relationship type. Force-directed layout automatically positions connected nodes near each other.

- *What works:* Intuitive for small graphs (3-15 nodes). Color coding immediately distinguishes entity types. Clicking expands connections progressively.
- *What fails:* Force-directed layout produces "hairball" visualizations above ~20 nodes. No hierarchical view (ownership chains should flow top-to-bottom). No temporal dimension (when were entities created?). No financial data (how much money flows through each connection?).

**OCCRP/Aleph: Manual network diagrams.** Users construct diagrams by dragging entities onto a canvas and drawing connections.

- *What works:* The investigator controls what is shown. Diagrams represent analytical conclusions, not raw data. Can be curated for clarity.
- *What fails:* Does not scale. Cannot handle automatically generated visualizations. No quantitative encoding (thickness, color intensity for amounts/confidence).

**ProPublica: Sankey diagrams (for FEC data).** Flow diagrams showing money moving from sources through intermediaries to recipients.

- *What works:* Excellent for showing volume and direction of flows. Width encodes amount. Direction encodes flow.
- *What fails:* Only works for flows, not for static network structure. Cannot show ownership hierarchies or non-financial relationships.

**Bellingcat: No network visualization.** All evidence is presented through annotated images and narrative text.

**The unsolved problem:** No platform effectively visualizes a network of 50-500 entities with heterogeneous relationship types, temporal dynamics, and quantitative attributes. This is Ithildin's opportunity.

**Candidate solutions from the visualization research literature:**

1. *Hierarchical layouts* for ownership chains: top-to-bottom flow showing beneficial owner → holding company → operating entity → subsidiary.
2. *Adjacency matrices* for large networks: a grid where each cell represents a relationship, with color encoding relationship type and intensity encoding strength/confidence. Less intuitive than node-link but scales to hundreds of entities without becoming a hairball.
3. *Ego networks* for focused views: show one entity at the center with its immediate connections, with option to expand any connected node. ICIJ's visualization is already close to this.
4. *Small multiples* for temporal evolution: show the same network at different time points side by side, with additions, deletions, and changes highlighted.
5. *Clustered layouts* for thematic grouping: group entities by jurisdiction, thread, or functional role, with inter-group connections shown as bundle edges.

### 6.4 Interactive vs. Static

Where does each platform use interactive tools vs. static articles?

| Use Case | ICIJ | ProPublica | OCCRP | Bellingcat |
|----------|------|-----------|-------|-----------|
| Entity lookup | Interactive (OL Database) | Interactive (Nonprofit Explorer) | Interactive (Aleph search) | None |
| Network visualization | Interactive (node expansion) | None | Interactive (manual diagrams) | None |
| Money flow | None | Interactive (Sankey for FEC) | None | None |
| Evidence presentation | Static (articles) | Static + interactive (methodology docs) | Static (articles) + documents | Static (annotated images) |
| Investigation narrative | Static (partner articles) | Static (articles) | Static (articles + VIS graphics) | Static (step-by-step articles) |

**Pattern:** Lookup and search are always interactive. Narrative and evidence presentation are always static. Network visualization is interactive when it exists but limited in scale.

**Synthesis for Ithildin:** Interactive for exploration (search, browse, filter, drill down). Static but linked for explanation (dossiers, explainers with embedded evidence and visualization). The key bridging element is the embedded interactive: a static dossier article that contains an interactive visualization of the specific corporate structure under discussion, with clickable nodes that link to entity detail pages.

### 6.5 Methodology Transparency

| Platform | How Much Process They Show | Effect on Trust |
|----------|--------------------------|-----------------|
| ICIJ | Data processing methodology, search instructions, data caveats | Increases trust with researchers; irrelevant to general public |
| ProPublica | Full statistical methodology, data sources, limitations, FAQ | Increases trust AND invites productive criticism (Surgeon Scorecard debate) |
| OCCRP | Minimal public methodology; investigation methods protected | Neutral --- trust comes from source document presentation |
| Bellingcat | Maximum transparency: every step shown, raw data published | Highest trust; methodology has been upheld in courts |

**Clear finding:** More transparency correlates with more trust. No platform has found that showing their work reduces credibility. The risk is that transparency invites critique (ProPublica's Surgeon Scorecard experience), but surviving critique increases credibility more than avoiding it.

**For Ithildin:** Maximum analytical transparency. Every finding should expose: source documents (with IDs), claim type, confidence level, corroborating evidence, and the analytical chain from evidence to conclusion. The content system should generate this transparency automatically from investigation.db metadata, not require agents to write it manually.

### 6.6 What None of Them Do

Six significant gaps exist across all four platforms:

**1. No platform explains WHY corporate structures are configured as they are.** ICIJ shows that Company A is in BVI and Company B is in Panama, but never explains why those jurisdictions were chosen (BVI for confidentiality, Panama for bearer shares, etc.). This is the Cluster A gap: text-based explanation of mechanisms is missing from all data platforms. Ithildin's explainer personas must fill this.

**2. No platform tracks investigation provenance.** None of them show: "This entity was first identified on [date] through [source]. It was connected to [other entity] based on [evidence]. The confidence level was upgraded from medium to high when [additional source] confirmed the relationship." Ithildin's corrections table, verification_status, and search_log already capture this. The content layer should expose it.

**3. No platform handles contradictory evidence.** When one source says X and another says not-X, existing platforms either suppress the contradiction or show both without comment. There is no systematic way to present competing claims with evidence and let the reader evaluate. Ithildin's dispute/retract/correct workflow is designed for this; the content layer must surface it.

**4. No platform supports temporal exploration of networks.** How did this corporate structure evolve over time? When were entities created, transferred, dissolved? All four platforms show static snapshots. Temporal dynamics --- which are often the most revealing analytical signal (entities formed right before a legal deadline, dissolved right after an investigation begins) --- are invisible.

**5. No platform integrates financial and structural data.** ICIJ shows structure (who owns what) but no money. ProPublica shows money (payments, donations, revenue) but no structure. OCCRP's FollowTheMoney has Payment and BankAccount entity types but these are sparsely populated. Bellingcat does neither. No platform shows: "This entity received $X from Entity A, passed $Y to Entity B, and the ownership chain runs through these 4 jurisdictions." Ithildin has both DS10 financial data and corporate structure data. Integrating them is a genuine differentiator.

**6. No platform generates hypotheses from patterns.** All four platforms are tools for confirming or presenting findings that humans already made. None of them analyze the data to suggest: "These three entities share an address, were formed within 6 months of each other, and have no other connections in common --- this is a potential undiscovered network cluster." Ithildin's hypothesis_tracker and generate-hunches skill are designed for exactly this.

---

## 7. Specific Recommendations for Ithildin

### Recommendation 1: Build a Three-Layer Content Architecture

Following ICIJ's model but with stronger integration:

**Layer 1: The Entity Explorer (researcher/journalist).** A searchable database of all entities, findings, connections, and evidence in investigation.db. Search by name, EIN, address, jurisdiction. Results show entity cards (name, type, connection count, finding count, confidence summary). Click through to full entity dossier. Filter by thread, jurisdiction, date range, confidence level. API access for programmatic queries. This is the "Offshore Leaks Database" of Ithildin.

**Layer 2: Curated Dossiers (journalist/public).** Authored content pieces generated by dossier_writer and explainer_writer personas. Each dossier embeds interactive elements: a visualization of the relevant corporate structure, links to source documents, confidence indicators on each claim. The dossier provides narrative context that the Entity Explorer cannot: why this structure exists, what purpose it serves, how it connects to the broader network.

**Layer 3: Mechanism Explainers (public).** Standalone pieces explaining how specific techniques work: how shell companies in USVI differ from those in Delaware, how trust structures obscure beneficial ownership, how compliance frameworks are exploited. These are not tied to specific entities but to patterns that recur across the investigation. They use the Cluster A writing techniques (McKenzie's perspective internalization, Levine's three-part structure) to make mechanisms comprehensible.

### Recommendation 2: Implement Hybrid Network Visualization

Combine the best elements of ICIJ and OCCRP's approaches:

- **Default view: Ego network.** When viewing any entity, show it at center with immediate connections. Color-code by entity type (ICIJ's approach). Size nodes by connection count. Encode edge thickness by evidence confidence.
- **Expandable exploration.** Click any node to expand its connections (ICIJ's progressive disclosure). But add a "maximum depth" control and a "filter by relationship type" control to prevent hairball growth.
- **Hierarchical view for ownership chains.** When the graph contains ownership/control relationships, offer a top-to-bottom hierarchical layout showing the chain from beneficial owner to operating entity. This is what ICIJ's database cannot do.
- **Sankey view for money flows.** When financial data exists (DS10 transactions, IRS 990 grants, FEC contributions), offer a Sankey diagram showing flow direction and volume. This is ProPublica's contribution.
- **Timeline view for temporal dynamics.** Show entity formation, dissolution, and key events on a timeline. Allow filtering the network graph to a specific date range to see how the structure existed at that point in time.

### Recommendation 3: Adopt ProPublica's Summary/Detail Pattern

For every content type, implement a two-level view:

- **Summary:** The minimum information needed to decide whether to investigate further. Entity name, type, jurisdiction, key connections, finding count, confidence summary.
- **Detail:** The full dossier. All findings, all connections, all evidence, all source documents, all temporal events, all hypotheses. With embedded interactive visualizations.

The summary appears in search results, connection lists, and cross-references. The detail appears when the user clicks through. This is how ProPublica's Nonprofit Explorer works, and it is the correct pattern for any system with more than a few hundred records.

### Recommendation 4: Implement Bellingcat-Style Evidence Chains

Every finding in the content layer should include a machine-generated evidence chain:

```
Claim: Leon Black paid $158M+ to Southern Trust Company
Type: direct_quote (from KPMG review)
Confidence: confirmed
Evidence chain:
  1. KPMG review document (EFTA02576529) states: "[specific quote]"
  2. Corroborated by: 990 filing for Apollo Foundation (EIN xx-xxxxxxx)
  3. Additional context: DS10 transaction records show STC balance trajectory
What remains uncertain:
  - Exact total may be higher (some payments through entities not in our data)
  - Purpose of individual payments not documented in available sources
```

This is Bellingcat's step-by-step transparency applied to financial evidence. It is generated automatically from investigation.db's finding_evidence, source_quote, claim_type, and verification_status fields.

### Recommendation 5: Build the ICIJ Reconciliation Pattern

Implement an API that lets external tools cross-reference against Ithildin's entity database. Input: a name, address, or corporate identifier. Output: matching entities in investigation.db with their connections and findings. This enables:

- Journalists working on related investigations to check if their subjects appear in Ithildin's data
- Researchers to batch-match their own datasets against Ithildin's entity registry
- Automated tools to query Ithildin as a data source

### Recommendation 6: Surface Contradictions and Uncertainty

Unlike any existing platform, Ithildin should make disagreement visible:

- When findings from different sources conflict, show both with their evidence and confidence levels
- When a finding has been disputed or retracted, show the correction history (from the corrections table)
- When a connection is based on inference rather than direct evidence, make the inference step explicit
- When temporal gaps exist in the evidence, show them as gaps rather than hiding them

### Recommendation 7: Generate Methodology Documentation Automatically

Following ProPublica's Nerd Blog model, every analytical method used by Ithildin agents should have a corresponding methodology page. But rather than writing these manually, generate them from the tool reference documentation and agent persona descriptions:

- "How we search corporate registries" (from tool_reference.md)
- "How we verify findings across multiple sources" (from INVESTIGATIVE_METHODOLOGY.md)
- "How we calculate network centrality" (from graph_tools.py documentation)
- "How we assess evidence confidence" (from the audit sourcing system documentation)

These methodology pages serve the same function as ProPublica's Nerd Box: they explain HOW analytical claims were produced, enabling readers to evaluate the methodology independently.

---

## 8. Appendix: Key Links and Examples to Study

### ICIJ

| Resource | Why It Matters |
|----------|---------------|
| [Offshore Leaks Database](https://offshoreleaks.icij.org/) | The primary reference implementation for entity search + visualization |
| [How to Use the Offshore Leaks Database](https://offshoreleaks.icij.org/pages/howtouse) | Search patterns: wildcards, fuzzy matching, country-linked search, jurisdiction browsing |
| [Download page](https://offshoreleaks.icij.org/pages/database) | CSV and Neo4j dump formats; data model visible in file structure |
| [Pandora Papers technology](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/) | Data processing methodology: 11.9M records, 14 providers, NLP extraction |
| [Datashare platform](https://www.icij.org/investigations/pandora-papers/we-wouldnt-have-been-able-to-do-pandora-papers-without-it-the-powerful-platform-behind-icijs-biggest-investigations/) | Open-source document analysis: batch search, NER, graph plug-in |
| [Datashare Neo4j plug-in](https://www.icij.org/inside-icij/2024/02/datashares-new-plug-in-helps-investigative-journalists-connect-the-dots-with-graphs/) | 2024 addition: document-to-graph extraction for journalists |
| [2025 Reconciliation API](https://www.icij.org/inside-icij/2025/01/explore-the-latest-tool-to-power-up-investigations-via-the-offshore-leaks-database/) | Automated data matching against Offshore Leaks entities |
| [Panama Papers and Linkurious](https://linkurious.com/blog/panama-papers-how-linkurious-enables-icij-to-investigate-the-massive-mossack-fonseca-leaks/) | How 370 journalists used Linkurious + Neo4j for graph exploration |
| [Neo4j Panama Papers data model](https://neo4j.com/blog/developer/digging-into-the-icij-pandora-papers-dataset-with-neo4j/) | Technical: node types, relationships, Cypher queries |
| [ICIJ Neo4j case study](https://neo4j.com/case-studies/the-international-consortium-of-investigative-journalists-icij/) | Architecture: Solr + Tika for extraction, Neo4j for graph, Linkurious for visualization |
| [How to refine searches](https://www.icij.org/investigations/pandora-papers/how-to-refine-your-searches-on-the-offshore-leaks-database/) | Advanced search patterns for the Offshore Leaks Database |

### ProPublica

| Resource | Why It Matters |
|----------|---------------|
| [Nonprofit Explorer](https://projects.propublica.org/nonprofits/) | The reference implementation for summary/detail 990 presentation |
| [Nonprofit Explorer API v2](https://projects.propublica.org/nonprofits/api) | API design patterns for investigative data access |
| [Dollars for Docs](https://projects.propublica.org/docdollars/) | The "personal lookup" pattern applied to pharmaceutical payments |
| [Dollars for Docs methodology](https://www.propublica.org/article/about-our-pharma-data) | Data documentation: sources, caveats, data dictionary |
| [Surgeon Scorecard](https://projects.propublica.org/surgeons/) | Confidence interval visualization, risk-adjusted methodology |
| [Surgeon Scorecard methodology FAQ](https://www.propublica.org/article/surgeon-level-risk-faq) | Detailed statistical methodology documentation |
| [FEC Itemizer](https://projects.propublica.org/itemizer/) | Campaign finance lookup; Sankey diagram for money flows |
| [FEC Itemizer methodology](https://www.propublica.org/nerds/untangling-a-web-of-fec-data) | Data processing for campaign finance |
| [Nerd Blog](https://www.propublica.org/nerds) | Full archive of technical methodology articles |
| [Conceptual Model for Interactive Databases](https://www.propublica.org/nerds/a-conceptual-model-for-interactive-databases-in-news) | Six-category framework for news app design |
| [News Apps Archive](https://www.propublica.org/newsapps) | Complete list of interactive projects |
| [News Apps Guides (GitHub)](https://github.com/propublica/guides/blob/master/news-apps.md) | Open-source coding philosophy and style guides |
| [Data Store Archive](https://projects.propublica.org/datastore/) | Historical dataset packaging (discontinued but informative) |
| [Campaign Finance API](https://projects.propublica.org/api-docs/campaign-finance/) | RESTful API design for FEC data |

### OCCRP

| Resource | Why It Matters |
|----------|---------------|
| [Aleph](https://aleph.occrp.org/) | The primary investigative search platform (now Aleph Pro) |
| [Aleph architecture docs](https://docs.aleph.occrp.org/developers/explanation/architecture/) | Technical: PostgreSQL + Elasticsearch + spaCy + FtM |
| [FollowTheMoney docs](https://docs.aleph.occrp.org/developers/explanation/followthemoney/) | The interstitial entity data model for investigative data |
| [FtM Model Explorer](https://followthemoney.tech/docs/) | Complete schema reference: entity types, properties, hierarchy |
| [FtM Schema (GitHub)](https://github.com/alephdata/followthemoney/tree/main/followthemoney/schema) | YAML schema definitions for all entity types |
| [Network Diagrams in Aleph](https://docs.aleph.occrp.org/users/investigations/network-diagrams/) | Manual network diagram construction |
| [Aleph search documentation](https://docs.aleph.occrp.org/developers/explanation/search/) | Elasticsearch indexing: per-schema indexes, hybrid mappings |
| [Aleph entity extraction](https://docs.aleph.occrp.org/developers/explanation/entity-extraction/) | NLP pipeline: spaCy models + fastText false positive reduction |
| [Export network graphs](https://docs.aleph.occrp.org/developers/how-to/data/export-network-graphs/) | FtM to Neo4j export, graph generation logic |
| [FtM network graph semantics](https://followthemoney.tech/docs/graphs/) | How interstitial entities contract into edges |
| [Aleph Pro FAQ](https://www.occrp.org/en/announcement/aleph-pro-frequently-asked-questions-on-the-future-of-occrps-investigative-data-platform) | Future direction: confidence labels, knowledge graphs, pricing |
| [OpenAleph (fork)](https://openaleph.org/faq/) | Community-maintained open-source fork after Aleph Pro transition |
| [Azerbaijani Laundromat](https://www.occrp.org/en/project/the-azerbaijani-laundromat) | Reference investigation: corporate network presentation |
| [Azerbaijani Laundromat: Core Companies](https://www.occrp.org/en/project/the-azerbaijani-laundromat/the-core-companies) | Source document presentation: clickable filings as evidence |
| [Russian Laundromat](https://www.occrp.org/en/laundromat/) | Cross-border money laundering investigation presentation |
| [VIS platform](https://vis.occrp.org/) | Publication-grade investigation visualizations |
| [Aleph tipsheet (GIJN)](https://gijn.org/resource/using-aleph/) | Practical guide to using Aleph for investigations |
| [Maltego-Aleph transforms](https://www.maltego.com/transform-hub/occrp-aleph/) | Integration: Aleph entities as Maltego transforms |

### Bellingcat

| Resource | Why It Matters |
|----------|---------------|
| [Online Investigation Toolkit](https://bellingcat.gitbook.io/toolkit) | Comprehensive tool reference for OSINT investigations |
| [MH17 Open Source Evidence (PDF)](https://www.bellingcat.com/app/uploads/2015/10/MH17-The-Open-Source-Evidence-EN.pdf) | The canonical example of step-by-step evidence presentation |
| [MH17 Three Years Later](https://www.bellingcat.com/news/uk-and-europe/2017/07/17/mh17-open-source-investigation-three-years-later/) | How evidence presentation evolves over multi-year investigations |
| [Navalny FSB Methodology](https://www.bellingcat.com/resources/2020/12/14/navalny-fsb-methodology/) | Maximum methodological transparency: every investigative step documented |
| [Navalny FSB Findings](https://www.bellingcat.com/news/uk-and-europe/2020/12/14/fsb-team-of-chemical-weapon-experts-implicated-in-alexey-navalny-novichok-poisoning/) | The investigative findings corresponding to the methodology article |
| [Skripal: Mishkin identification](https://www.bellingcat.com/news/uk-and-europe/2018/10/09/full-report-skripal-poisoning-suspect-dr-alexander-mishkin-hero-russia/) | Identity unmasking through convergent database evidence |
| [Skripal: Sergeev identification](https://www.bellingcat.com/news/uk-and-europe/2019/02/14/third-suspect-in-skripal-poisoning-identified-as-denis-sergeev-high-ranking-gru-officer/) | Phone metadata + travel record + geolocation convergence |
| [How Open Source Evidence Was Upheld in Court](https://www.bellingcat.com/resources/2023/03/28/how-open-source-evidence-was-upheld-in-a-human-rights-court/) | Legal admissibility of OSINT evidence; chain of custody requirements |
| [Justice and Accountability Manual (PDF)](https://www.bellingcat.com/app/uploads/2022/12/JA-Manual-for-PUBLICATION.pdf) | Berkeley Protocol-aligned methodology for legally admissible OSINT |
| [How to Uncover Corruption Using Open Source Research](https://www.bellingcat.com/resources/2016/09/05/how-to-uncover-corruption-using-open-source-research/) | Bellingcat's approach to financial/corruption investigations (note limitations) |
| [Companies & Finance toolkit](https://bellingcat.gitbook.io/toolkit/categories/companies-and-finance) | Tool recommendations for corporate/financial OSINT |
| [Auto Archiver](https://www.bellingcat.com/resources/2025/08/13/the-open-source-tool-that-has-preserved-150000-pieces-of-online-evidence/) | Evidence preservation: 150K+ archived pages |
| [Beginner's Guide to Social Media Verification](https://www.bellingcat.com/resources/2021/11/01/a-beginners-guide-to-social-media-verification/) | Verification methodology fundamentals |
| [Beginner's Guide to Geolocation](https://www.bellingcat.com/resources/how-tos/2014/07/09/a-beginners-guide-to-geolocation/) | The foundational geolocation technique |

### Cross-Platform and Analytical Resources

| Resource | Why It Matters |
|----------|---------------|
| [Flourish: Company Network Visualizations](https://flourish.studio/blog/company-network-visualisations/) | Best practices for corporate ownership diagrams |
| [OpenOwnership: Beneficial Ownership Visualization](https://www.openownership.org/en/news/visualising-beneficial-ownership-data-with-our-new-tool/) | Specialized visualization for ownership chains |
| [GIJN: Social Network Analysis for Investigative Journalism](https://gijn.org/stories/power-social-network-analysis-investigative-journalism/) | Network analysis methodology for journalists |
| [GIJN: Researching Corporations and Their Owners](https://gijn.org/resource/researching-corporations-and-their-owners/) | Practitioner guide to corporate research |
| [GIJN: Visualization Tools](https://gijn.org/visualization-tools/) | Survey of visualization tools used in investigative journalism |
| [Online Journalism Blog: Network Analysis for Journalists](https://onlinejournalismblog.com/2020/06/08/a-journalists-introduction-to-network-analysis/) | Introductory network analysis concepts for non-technical journalists |
| [Neo4j Graph Visualization of Panama Papers](https://medium.com/neo4j/graph-visualization-of-panama-papers-data-in-neo4j-9c08ca17039c) | Technical walkthrough: Neo4j Bloom and neovis.js for Panama Papers data |
| [Linkurious: FinCEN Files Technology](https://linkurious.com/blog/technology-fincen-files-investigation/) | How the FinCEN Files investigation used graph technology |

---

*Research compiled February 2026 for Ithildin content generation system design.*
