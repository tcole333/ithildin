# Craft Principles for Agent-Generated Content

Distilled from studying the best financial explainers (McKenzie, Levine, Hobart), narrative nonfiction writers (McPhee, Keefe, Caro), investigative data platforms (ICIJ, ProPublica, OCCRP, Bellingcat), interactive explanation designers (Bret Victor, Nicky Case), and conceptual model builders (Alexander, Thompson, Meadows, Taleb).

Organized by *what agents DO*, not by source cluster. See `research/craft-research/` for the full source documents.

---

## 1. Explanation Architecture

These principles govern how agents explain systems, mechanisms, and structures. Every mechanism explainer, analytical article, and dossier narrative should follow these rules.

### Three-Part Structure

Every mechanism explanation follows this pattern:

1. **Conceptual frame** — What is this thing? What problem does it solve? What role does it play in the system?
2. **Specific story/evidence** — A particular instance from the investigation. Exact dates, exact amounts, exact parties. This is where EFTA references and DS10 transactions live.
3. **Analysis connecting them** — Why does this specific instance illuminate the general mechanism? What does it reveal that the frame alone wouldn't?

A section that has (1) without (2) is a Wikipedia article. A section that has (2) without (1) is a document dump. A section that has both without (3) is journalism. All three together is explanation.

### Perspective Internalization

Don't describe systems from outside. Put the reader inside.

Bad: "The Bank Secrecy Act requires banks to file Suspicious Activity Reports."
Good: "You're a compliance officer at Deutsche Bank's Jacksonville branch. A wire transfer for $4.4 million arrives from a client flagged in your system. Your BSA obligations are clear: file an SAR within 30 days. But your relationship manager has already approved the transaction, and the client is one of the bank's most profitable. What do you do?"

The reader should experience the system's pressures, not read about them. This technique works for compliance desks, trust administrators, shell company registrars, offshore bankers, and every other institutional actor in the investigation.

### Infrastructure Reveal / Waterfall

Peel back layers. Show the invisible automatic mechanisms that most people never see.

The compliance cascade: A suspicious transaction triggers an SAR, which goes to FinCEN, which routes to the FBI, which refers to the DOJ. But at each stage, there's a falloff rate. Show the waterfall — how many transactions become SARs, how many SARs become investigations, how many investigations become prosecutions. The gap between the top and the bottom of the waterfall IS the story.

The liability waterfall: When a trust company fails to conduct adequate CDD, who bears the liability? The registered agent? The trustee? The bank? The regulator? Show the chain — and show where it breaks.

### Evolutionary Explanation

Don't just say "here's how it works." Explain WHY it works this way.

The pattern:
1. How it works today
2. Why that seems weird or counterintuitive
3. The historical/structural reason it evolved this way
4. What would happen if you tried to change it
5. Now you understand why it persists

Example: USVI trust companies seem like an absurd regulatory gap. But they exist because (a) the USVI needs economic development, (b) the federal government gave territories tax autonomy, (c) onshore trust companies had legitimate clients who needed offshore structures, (d) attempts to close the gap face opposition from the legitimate trust industry. The "loophole" is load-bearing.

### Counterintuitive Hook

Open with a structural truth that contradicts naive assumptions, then systematically demonstrate why it's right.

Bad opening: "Jeffrey Epstein used shell companies to hide his wealth."
Good opening: "The most striking thing about Epstein's corporate network isn't that it was hidden. It's that it was *legal*. Every entity was properly filed. Every trust had a registered agent. Every bank account passed KYC. The system worked exactly as designed — and that's the problem."

The reader should think "wait, that can't be right" and then spend the next 4,000 words discovering that it is.

### Concrete First, Abstract Second

Introduce through a specific, vivid evidence instance BEFORE defining the pattern.

Bad: "Manufactured dependency is a pattern where actors create conditions for problems, then sell the solution."
Good: "In 2012, Epstein introduced Leon Black to a man who would later attempt to extort him. In 2015, Epstein offered to make the problem go away — for a fee. [EFTA reference.] This isn't improvisation. It's a business model."

The specific instance anchors the abstraction. The reader remembers the story, not the definition.

### Jargon Handling

Contextualize through operational description, not definition.

Bad: "A Grantor Retained Annuity Trust (GRAT) is a type of irrevocable trust designed to transfer wealth to beneficiaries while minimizing gift and estate taxes."
Good: "Black set up a GRAT — a structure that works like this: you put assets in a trust, the trust pays you an annuity for a fixed period, and whatever's left over passes to your heirs tax-free. The trick is the annuity rate. The IRS requires it to beat the Section 7520 rate, which in 2013 was 1.0%. If the assets grow faster than 1%, the excess escapes the estate tax. In Black's case, the assets were Apollo shares."

Show the term in action, not in a glossary. The reader learns what a GRAT is by seeing one used.

### Calibrated Precision

"$56,542,688.38" when you have the exact figure from a source document. "$10 to $20 billion" when the range is uncertain. "We do not know" when you don't.

Precision is not about showing off — it's about honesty. A writer who says "$56.5 million" when the source says "$56,542,688.38" is *less* trustworthy, because they're obscuring their access to the primary source. A writer who says "$40 million" when the actual amount is uncertain is committing to a precision they don't have.

Calibrated imprecision increases credibility. Admit uncertainty. Give ranges. Flag what you don't know.

---

## 2. Narrative Structure

These principles govern how agents organize articles, dossiers, and long-form content. They determine the sequence, pacing, and architecture of a piece.

### Keefe's Eight-Beat Envelope

Before writing, identify the structural beats:

1. **Opening scene** — The image, fact, or moment that hooks the reader
2. **First transition** — How you move from the hook to the body
3. **First turning point** — Where the reader's understanding shifts
4. **Development** — The main body of evidence and explanation
5. **Second turning point** — Where the pattern becomes visible
6. **Complication** — The counterargument, the thing that doesn't fit
7. **Climax** — The moment of maximum clarity or revelation
8. **Ending** — What the reader takes away

Map the topography before entering the terrain. You don't need all eight beats in every piece, but you need to know where they are.

### McPhee's Dual-Spine

Every long piece needs two spines working simultaneously:

- **Holding spine**: The thing the reader holds onto — a timeline, a person's story, a transaction chain, a legal proceeding. This provides forward momentum.
- **Depth spine**: The thing that provides understanding — system explanation, corporate structure analysis, regulatory framework. This provides meaning.

Neither alone works. A piece that's all holding spine is a chronology. A piece that's all depth spine is a textbook. The art is in the weaving — when to pause the story to explain a mechanism, and when to resume the story to demonstrate it.

For Ithildin articles:
- Holding spine options: A specific person's trajectory, a single transaction chain, the timeline of a legal proceeding, the formation-to-dissolution of an entity
- Depth spine options: How the trust industry works, what compliance theater looks like in practice, how offshore structures create deniability, why certain jurisdictions attract certain activities

### Character-Web Technique

People make systems legible. But too many people make content illegible.

- **3-5 principals**: Appear throughout the piece. The reader knows their names, roles, and motivations. They carry the narrative.
- **8-12 supporting characters**: Appear in specific sections. Introduced with role context ("Brad Karp, then the managing partner of Paul Weiss"), not expected to be remembered across sections.
- **Everyone else**: Referenced but not characterized. "A Deutsche Bank relationship manager" not "Deutsche Bank relationship manager Patricia Villareal, who had joined the bank in 2008 after..."

Character ceiling: 7-12 named characters max before readers lose track. If an article needs to reference more people than this, most should be unnamed roles, not named individuals.

### Evidence Budget / Selection

200+ findings on a target cannot all be in one article. Selection criteria:

1. **Does this reveal a mechanism?** A finding that shows HOW something works is worth more than one that shows THAT something happened.
2. **Does this connect to another thread?** Findings that bridge investigation threads (e.g., a Deutsche Bank transaction that links to an Apollo payment) are structurally important.
3. **Does this contradict the public narrative?** The gap between the official story and the evidence is where the best writing lives.
4. **Is it primary-sourced?** EFTA documents and court filings outrank media reports.
5. **Is it specific?** "$23.5 million on March 14, 2014" is worth more than "millions over several years."

A 5,000-word article should cite 30-50 findings. If you have 200, you're selecting the best 25%, not summarizing 100%.

### Documents as Plot Points

Paraphrase context, then quote the devastating line.

Bad: "According to EFTA02576529, the ARRC reviewed the relationship. The document states: 'The Committee reviewed the client relationship for Jeffrey Epstein. After reviewing all available information including the financial profile, transaction history, and compliance screening results, the Committee determined that the relationship should continue. The Committee was comfortable with things continuing.'"

Good: "The Account Review and Reputational Committee met in January 2015. They had before them Epstein's full file: the 2008 conviction, the ongoing lawsuits, the media coverage. Their determination, per the internal minutes: they were 'comfortable with things continuing.' [EFTA02576529]"

The paraphrase provides context. The quote delivers the payload. Never dump document lists.

### The Missing Document as Evidence

Absence of expected records is itself evidence. Note what should exist but doesn't.

- If a bank filed SARs on 90% of Epstein's transactions but not the largest ones, the missing SARs are the story.
- If there are emails between two people from 2015-2017 but nothing in 2018-2019, the gap is investigatively significant.
- If a corporate entity has no annual reports after a certain date, when was it abandoned and why?

Always ask: what SHOULD be here that isn't?

### Stakes Before Mechanism

Establish what happens if the system fails BEFORE explaining how it works.

Bad: "The BSA requires banks to file Currency Transaction Reports for transactions over $10,000. Here's how the process works..."
Good: "Between 2013 and 2019, Deutsche Bank processed 579 transactions totaling $304 million for a convicted sex offender. The BSA exists precisely to prevent this. Here's how it's supposed to work — and where it broke down."

The reader needs to care before they'll learn. Stakes create urgency through technical exposition.

### Progressive Revelation

Control WHEN the reader learns WHAT. Sequence information so each fact recontextualizes what came before.

Example sequence:
1. Epstein paid Black's extortionist — reader thinks: that's strange but maybe a favor
2. Epstein introduced Black to the extortionist years earlier — reader thinks: wait, did he set this up?
3. Epstein's payments from Black tripled after the extortion rescue — reader thinks: this is a business model
4. The same pattern appears with other clients — reader thinks: this is systematic

The reader does the math themselves. Each fact changes the meaning of the previous facts. This is more powerful than any summary statement.

### Structure from Evidence, Not Templates

Don't impose a predetermined outline. Find the most surprising evidence, the strongest chain, and the thesis — let those determine the structure.

Two articles about shell companies should have different structures if the evidence tells different stories. One might lead with a trust formation document that reveals the entire architecture. Another might lead with a bank transfer that traces backward to an invisible entity. The evidence determines the entry point, and the entry point determines the structure.

The MDX template in `/write-article` is a starting scaffold, not a mandatory outline. Every article's structure should be different because every evidence base is different.

---

## 3. Analytical Model Deployment

These principles govern how agents reference and apply the 8 analytical models across content.

### Name the Gap, Not the Thing

Model names identify something people already experience but lack vocabulary for.

"Bridge Tax" names the phenomenon where an intermediary extracts value from connecting parties who could, in theory, find each other. People recognize this immediately in their own experience — they just didn't have the term.

Don't define models abstractly. Show the reader experiencing the phenomenon, THEN name it.

### Personify Abstractions

"The Bridge Tax operates here" not "this is an example of brokerage intermediation."

"Manufactured Dependency at work" not "this illustrates a pattern of creating and then solving problems."

Models should feel like characters in the investigation — recurring actors that appear in different contexts with the same modus operandi.

### Make Models Deployable Through Repeated Application

Reference models in every dossier and article where they apply. Each appearance is a teaching moment.

The first time a reader sees "Jurisdictional Arbitrage" in an article about USVI trusts, they learn the concept. The third time they see it in an article about Deutsche Bank's Cayman accounts, they own it. By the fifth appearance, they're spotting it themselves.

Consistency matters: always use the same model name, always link to the model page, always provide the specific evidence that triggers the reference.

### Limitation Surfacing

Always note when a model misleads. Intellectual humility separates useful tools from ideology.

"The Enabler Gradient applies here, though it's worth noting that [specific actor] may have been acting under regulatory compulsion rather than institutional complicity."

"This looks like Manufactured Dependency, but we lack evidence that the introduction was intentional rather than coincidental."

A model that's never wrong is never useful. Show the edges.

---

## 4. Visualization Principles

These principles govern network graphs, financial flow diagrams, timelines, and any visual element in articles or on the platform.

### Tufte Data-Ink Ratio for Networks

Every visual element must encode data. A "clean" graph with uniform nodes has a terrible data-ink ratio.

Encode meaning in every visual property:
- **Edge thickness** = relationship strength (transaction volume, communication frequency)
- **Edge color** = relationship type (financial=green, legal=blue, personal=red, intelligence=purple)
- **Edge style** = evidence quality (solid=confirmed, dashed=inferred, dotted=suspected)
- **Node size** = connection count (degree centrality)
- **Node color** = entity type (person=circle, company=square, trust=diamond)
- **Node border** = investigation coverage (thick border=well-investigated, thin=sparse)

### Annotation Is the Critical Layer

A network graph without annotations is topology. A graph with annotations is an investigation.

Amanda Cox's principle: "The annotation layer is the most important thing we do." A node labeled "Maple Inc (USVI)" is data. A node labeled "Maple Inc — formed 48 hours before the $23.5M transfer [EFTA02576529]" is evidence.

Every graph should have 3-5 annotations pointing to the most significant structural features. The annotations tell the reader what to see.

### Small Multiples for Network Evolution

Same layout at 5 time points. Same node positions. New entities appear, dissolved entities fade. Reader sees growth pattern without interaction.

Time periods for Epstein network evolution:
- Pre-2006 (before first investigation)
- 2006-2008 (investigation and plea deal)
- 2008-2013 (rebuilding period)
- 2013-2019 (expansion and second investigation)
- Post-2019 (aftermath and dissolution)

Consistency of layout across panels is critical. Nodes must stay in the same position. Only additions and removals change.

### Graph Hairball Threshold

Force-directed layout fails above ~50 nodes. The graph becomes a hairball that communicates nothing.

Alternatives by context:
- **Ego networks** for person views: center the target, show 1-2 hops, filter by relationship strength
- **Adjacency matrices** for dense relationships: rows and columns are entities, cells are relationships. Good for showing clusters.
- **Hierarchical layouts** for ownership structures: parent-child relationships in a tree. Good for corporate hierarchies.
- **Geographic layouts** for jurisdiction mapping: place entities on a map. Good for showing jurisdictional arbitrage.
- **Bipartite layouts** for person-entity relationships: people on one side, entities on the other. Good for showing who controls what.

### Interaction Should Reveal, Not Require

The static view MUST communicate the key finding. Interaction lets the reader drill deeper.

A network graph that only makes sense when you hover over nodes is a failed visualization. The static image — what you see in a PDF or a screenshot — must tell the story. Interactivity is a bonus layer that provides detail, not the primary communication channel.

### Graceful Degradation

Every interactive element must function as a readable static fallback. Print the page. Does it still make sense? If not, the interactive version is doing too much work.

- Hover states: the information shown on hover should also be available in a legend or annotation
- Collapsible sections: the most important content should be visible by default
- Zoom/pan: the default view should show the most important structure

### Hover-to-Highlight + Progressive Disclosure

Best cost-to-comprehension ratio for interactive network graphs:

1. **Default view**: Annotated graph with key features highlighted
2. **Hover**: Highlight the hovered entity and its direct connections. Show a tooltip with entity details.
3. **Click**: Expand to show full entity profile, all connections, evidence references
4. **Filter controls**: Toggle by relationship type, time period, evidence quality

This three-level progressive disclosure (see → highlight → detail) handles most reader needs without requiring them to learn a complex interface.

### Ladder of Abstraction

Move between levels of detail:

1. **Single transaction**: $4.4 million wire from Southern Trust to Deutsche Bank on March 14, 2014
2. **Quarterly pattern**: 12 transactions averaging $2.1M each from Q1 2014 to Q3 2014
3. **Structural observation**: Southern Trust served as a pass-through entity, receiving funds from Epstein's trust accounts and wiring them to his personal Deutsche Bank accounts
4. **System explanation**: USVI trust companies create a layer of separation between beneficial owners and their bank accounts, making it harder for compliance systems to detect patterns

Each level reveals something invisible at the other levels. The single transaction is meaningless without the pattern. The pattern is invisible without the transactions. The structure is abstract without the pattern. The system explanation is theoretical without the structure.

---

## 5. Platform Design

These principles govern how the Ithildin platform organizes and presents content.

### Three-Tier Output

The platform serves three distinct audiences:

1. **Searchable database** for researchers: Full evidence access, EFTA references, entity relationships, timeline data. Search-first interface. Power users who want to verify claims and explore connections.
2. **Curated narrative articles** for general audiences: Crafted explanations following all the principles above. These are the "front page" of the investigation. Accessible to intelligent non-specialists.
3. **Methodology documentation** for verification: How findings were sourced, what tools were used, what searches returned nothing. Bellingcat-style transparency. Allows others to reproduce or challenge the analysis.

Every piece of content should know which tier it serves.

### Search-First, Not Browse-First

The platform homepage should be a search bar, not a list. Force specificity.

A user who types "Southern Trust" gets: the entity dossier, all findings mentioning it, all articles that reference it, all connected entities, all connected persons. A user who browses a list of articles might never find the Southern Trust connection.

Search drives discovery. Browse confirms what you already know.

### The Enabler Gap

Across six major investigations (Madoff, BCCI, Wirecard, Danske Bank, 1MDB, Panama Papers), systemic enablers — banks, law firms, accountants, auditors — received far less attention than the principals. This is the gap Ithildin's network-centric approach fills.

When writing about Epstein, the temptation is to focus on Epstein. The platform's value is in making visible the institutional infrastructure that enabled him: the banks that processed his transactions, the law firms that structured his entities, the trust companies that administered his trusts, the compliance officers who looked the other way.

Every article should spend at least as much time on the enablers as on the principal.

### Compliance Theater Is the Hardest Story

Banks filing SARs while continuing to process transactions. Law firms conducting CDD that identifies red flags and then continuing the engagement. Trust companies maintaining KYC files that document problems they're choosing to ignore.

This is structurally different from individual wrongdoing, and it requires different narrative technique:

- Don't say "the bank failed." Say "the bank filed 7 SARs over 3 years, each identifying the same risk, and processed $304M in transactions during the same period."
- Don't say "compliance was inadequate." Show the compliance process working correctly — identifying the problem — and then show the business side continuing anyway.
- The story is not that the system was broken. The story is that the system worked exactly as designed, and that's the problem.

### Show Evidence, Not Just Conclusions

Bellingcat's power comes from methodological transparency: they show HOW they reached a conclusion, step by step. The reader can follow the reasoning and decide for themselves whether they agree.

Every article should include:
- The evidence trail (EFTA references, source documents)
- The reasoning chain (why does this evidence support this conclusion?)
- The confidence level (confirmed, high, medium, low)
- The alternatives (what other explanations are possible?)

An article that says "Epstein was an intelligence asset" without showing the evidence chain is editorializing. An article that shows the evidence and lets the reader draw their own conclusion is investigation.

---

## 6. Anti-Patterns

What agents must NOT do. These are the most common failure modes in generated content.

### Language Anti-Patterns
- Don't say "shocking," "explosive," "bombshell," or "stunning." If the facts aren't striking on their own, you haven't presented them well.
- Don't say "it is important to note that." If it's important, just say it. If it's not, don't.
- Don't say "as previously mentioned." The reader doesn't need a callback citation to themselves.
- Don't say "this proves" when describing an inference. Say "the timing suggests" or "the evidence indicates."
- Don't use moral language: "heinous," "disgusting," "unconscionable." Let the evidence do the work. The reader will supply the moral judgment.

### Structural Anti-Patterns
- Don't describe events chronologically when thematic organization would be clearer. Chronology is the default structure, which means it's usually the least interesting one.
- Don't explain a system without explaining WHY it evolved this way. "Here are shell companies" without "here's why USVI trust law exists and what makes it attractive for this purpose" is half the explanation.
- Don't present an exhibit list of evidence. "Document 1 shows X. Document 2 shows Y. Document 3 shows Z." is not narrative. Weave documents into the story.
- Don't put all findings in one article. Apply the evidence budget. Selection is an editorial act.
- Don't impose a template and backfill evidence. Let the evidence determine the structure.

### Precision Anti-Patterns
- Don't use abstract descriptions when specific figures exist: "many transactions" when you mean "579 transactions totaling $304M."
- Don't round numbers when you have exact figures from source documents: "about $56 million" when the source says "$56,542,688.38."
- Don't use vague timeframes when you have exact dates: "in the mid-2010s" when you mean "between March 2014 and November 2016."

### Visualization Anti-Patterns
- Don't use force-directed graph layout above 50 nodes. It will be a hairball.
- Don't build interactivity that breaks without JavaScript. Every interactive element needs a static fallback.
- Don't make uniform nodes and edges. Every visual element should encode data.
- Don't create a visualization without annotations. The annotation layer is the most important layer.

### Analytical Anti-Patterns
- Don't make moral judgments. Let the evidence speak. "This was criminal" is an opinion. "This violated 31 CFR 1010.230" is a finding.
- Don't state inferences as facts. Maintain the distinction rigorously. Findings tools enforce claim types for a reason.
- Don't confuse redundancy with corroboration. The same document appearing in 3 databases is one source, not three.
- Don't ignore negative results. "We searched 5 sources and found nothing" is itself a finding. Record it.

---

## Quick Reference for Agent Personas

### ExplainerWriter (mechanism_explainer jobs)
Primary principles: Three-Part Structure, Evolutionary Explanation, Infrastructure Reveal, Counterintuitive Hook, Calibrated Precision, Stakes Before Mechanism

### ContextualAnalyst (analytical_article jobs)
Primary principles: Perspective Internalization, Counterintuitive Hook, Model Deployment, Dual-Spine, Evidence Budget, Structure from Evidence

### EditorReview (editor_review jobs)
Primary checkpoints: Evidence Budget applied? Structure from evidence or template? Perspective internalized? Mechanism explained (not just events)? Anti-patterns absent? Models referenced where applicable?

### DossierWriter (wiki_dossier_update jobs)
Primary principles: Character as System Entry Point, Evidence Budget for key findings selection, Missing Documents noted, Model references where applicable

### Deep-Investigate / Pursue-Lead (investigation agents — Layer 1)
Primary principles: Concrete First, Missing Document as Evidence, Negative Results as Findings, Source Checklist Completion, Ambient Documentation. These are Layer 1 research agents — they do NOT assess narrative potential, article-worthiness, or editorial framing. See `research/INVESTIGATIVE_METHODOLOGY.md` § Two-Layer Agent Architecture.
