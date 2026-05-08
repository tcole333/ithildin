---
name: Durable Deregulation Scaffolding
slug: durable-deregulation-scaffolding
domain: legal-regulatory
source: "Investigation synthesis (Round 6, May 2026); extends Stigler 'Theory of Economic Regulation' (1971) and Levitin/Wachter 'The Great American Housing Bubble' (2020) on regulatory rule-making artifacts"
status: adopted
created: 2026-05-07
grounding_findings: [11236]
related_models: [institutional-capture-lifecycle, regulatory-replacement, personnel-pipeline, temporal-arbitrage]
detection_keywords:
  - ["interpretive letter", "no-action letter", "advisory bulletin", "bulletin", "FAQ", "guidance"]
  - ["IL #", "OCC IL", "SEC no-action", "FinCEN guidance", "CFTC interpretation"]
  - ["citing", "relies on", "as authorized by", "consistent with", "per existing precedent"]
  - ["Brooks", "Skadden", "Sullivan & Cromwell", "Davis Polk", "Wachtell", "vault firm"]
  - ["Acting", "former Comptroller", "former chair", "former general counsel"]
  - ["charter", "trust charter", "national bank charter", "approval", "preemption"]
  - ["crypto", "stablecoin", "digital asset", "fintech charter"]
minimum_trigger: "Same firm: (a) authors a deregulatory legal artifact while in regulator post, (b) returns to private practice or affiliated industry, (c) files for an approval that cites the artifact, AND (d) the artifact's authority survives at least one administration change."
anti_pattern: "Normal precedent citation. Firms routinely cite earlier rule-makings — that's how administrative law works. The pattern requires the *same firm* (or tightly connected partners) on both ends, and the artifact must be deregulatory or expansive of regulated-industry power, not a routine clarification."
canonical_example: "OCC Interpretive Letters 1170 (custody) and 1174 (stablecoin reserves), authored under Acting Comptroller Brian Brooks 2020 (formerly Coinbase CLO), are cited in 2025 Erebor Bank conditional approval letter. Erebor charter filed Jun 11 2025 by Skadden partner Jonathan Gould; Gould joined OCC as Sr Deputy + Chief Counsel Aug 11 2025; approval issued 65 days later. The 2020 letters survived Biden-era OCC and became operative law for Trump-II crypto charter approvals."
---

## Definition

Durable Deregulation Scaffolding is the pattern by which a regulated industry (typically through alumni-of-the-regulator at a small number of vault firms) authors deregulatory legal artifacts — interpretive letters, no-action letters, advisory bulletins, FAQs, guidance documents — during a friendly administration, and those artifacts persist as operative law across administration changes. Subsequent transactions, often filed by partners from the same authoring firm, cite the prior artifacts as authority to obtain charters, approvals, exemptions, or preemption rulings.

The mechanism's value is *durability*. Personnel rotate. Statutes are slow to amend. But interpretive letters and similar agency artifacts have a peculiar status: they are not formal rules subject to APA notice-and-comment, but they are treated as binding agency interpretations that subsequent applicants and courts cite. Once issued, they sit on the agency's website as a structural feature of the regulated industry's permitted activity. They can only be rescinded by a successor agency action — which is itself slow, contested, and politically costly.

The scaffolding is therefore *one-directional*: deregulatory letters issued in 2020 still scaffold approvals in 2025, even after a four-year hostile administration. The Biden-era OCC could have rescinded IL #1170/1174; it did not, both because rescission requires its own political process and because the financial industry mobilizes against rescission. Brooks's 2020 letters became a permanent installation in the regulatory architecture.

This is structurally distinct from Institutional Capture Lifecycle (which describes career-flow phases between regulator and regulated) and from Regulatory Replacement (which describes mission-redefinition under hostile leadership). Durable Deregulation Scaffolding is about *the regulatory artifact itself* as a persistent object of leverage. The artifact outlasts the personnel who authored it; it becomes the durable infrastructure that subsequent personnel rotations exploit.

## Mechanism

1. **Authorship in regulator post.** A vault-firm alumnus enters the regulator (typically Acting Comptroller, Acting Director, Chief Counsel, Senior Advisor) and authors interpretive letters or guidance that expand the regulated industry's permitted activity. Brooks's IL #1170 (Jul 2020, custody of digital assets by national banks) and IL #1174 (Sep 2020, stablecoin reserve activities) are paradigm cases.

2. **Return to private practice.** The authoring official cycles back to private practice or an industry CLO/General Counsel role. Brooks→Bitfury CEO Apr 2021. The artifact remains live on the agency's website.

3. **Survival across administrations.** The successor administration *could* rescind but typically does not, because (a) rescission requires its own administrative process, (b) the regulated industry mobilizes against rescission, and (c) rescission may itself be challenged as arbitrary-and-capricious if reliance interests have built up. The artifact ages into entrenchment.

4. **Citation in subsequent applications.** When the political wind shifts again, partners from the *same firm* (or tightly connected vault firms) file applications that cite the dormant artifacts as binding authority. Skadden partner Jonathan Gould files the Erebor Bank charter on Jun 11 2025 citing IL #1170/1174 + IL #1184 (the latter likely also Brooks-era or related). Gould then enters OCC as Sr Deputy + Chief Counsel on Aug 11 2025. Erebor approval is issued 65 days later.

5. **Approval as legal-artifact validation.** The approval letter itself becomes a new artifact — a precedent that subsequent applicants will cite. The scaffolding extends. What began as one Brooks letter in 2020 now cascades into 2025-2026 charter approvals that cite the chain.

## Detection Markers

- Identify the authoring official's prior firm. If the official came from a vault firm (Skadden, Sullivan & Cromwell, Davis Polk, Wachtell, Latham), check whether partners from that firm subsequently file applications citing the official's artifacts.
- Track the artifact's citation graph. Run a Lexis or full-text search on later approval letters, no-action letters, and court briefs for citation of the original interpretive letter. Frequency matters: a letter cited 3+ times across multiple administrations is durable scaffolding; a letter cited once and forgotten is not.
- Look for charters, approvals, or preemption rulings filed within months of the authoring official's *return* to a regulator post in a successor administration. If the original 2020 letter is being cited in 2025 approvals issued by the same office where the 2020 author now sits, the scaffolding has come full-circle.
- Check whether the successor administration *attempted* rescission. If rescission was considered and dropped, that's evidence of the artifact's durability and of industry mobilization to protect it.
- Map the dormant period. Letters that lay dormant during a hostile administration and were activated immediately when conditions allowed (within 60-90 days of new appointments) are the strongest scaffolding instances.

## Why Existing Models Miss This

- **Institutional Capture Lifecycle** describes career flow but not the *artifacts produced during career rotations*. Personnel can leave; the letter remains.
- **Regulatory Replacement** describes mission redefinition under hostile leadership. Durable Deregulation Scaffolding describes *deregulatory infrastructure built during friendly leadership that survives hostile leadership*. Different temporal logic.
- **Personnel Pipeline** focuses on placing people; this lens focuses on placing *legal artifacts* whose authority outlasts the placers.
- **Temporal Arbitrage** describes acting fast within an administrative window; this describes acting *durably* such that the action survives multiple administrative cycles.

## Boundary Conditions

The framework does NOT apply to:

- **Routine guidance documents** that clarify existing law without expanding regulated-party authority. Most agency FAQs and bulletins are housekeeping, not scaffolding.
- **Statutes and final rules** that go through APA notice-and-comment. Those have their own legitimacy and durability mechanisms.
- **Cases where the artifact was rescinded before being cited again.** If the successor administration successfully rescinded IL #1170 and Erebor was approved without citing it, the framework collapses for this instance.
- **Industry-wide guidance with bipartisan input.** Some interpretive letters reflect agency-staff consensus rather than political appointee initiative. Test: was the letter signed/issued under an Acting head with prior industry ties? If not, scrutinize closely before applying this lens.

## Overfit Risk

Risk: every regulatory artifact cited in a subsequent application looks like scaffolding. To avoid false positives:

- Require the *same firm* on both ends (authoring official's prior firm = applicant's filing firm), not just industry-wide citation.
- Require a *deregulatory or expansionary* effect (the letter expanded what regulated parties could do), not a clarifying or restrictive effect.
- Require *cross-administration durability*. If both authorship and citation occur within the same 4-year window, that's just normal agency rule-making. The framework's value is in identifying *artifacts that survive intervening hostile administrations*.
- Require the citation to be *load-bearing* in the application. The cited letter must be relied upon as authority for the requested action, not merely listed in a survey of relevant precedent.

## Detection Falsification Test

For any candidate instance, ask: "If IL #1170 had been rescinded by the Biden OCC in 2021, would Erebor's 2025 approval still have been issued in the same form?" If the answer is "yes, on other authorities" — the scaffolding hypothesis is weakened. If the answer is "no, the approval depends materially on the dormant letter" — the scaffolding is genuine. The 5-year baseline rate to establish: how often do interpretive letters issued under one Acting Comptroller get cited as binding authority in approvals issued under the *next-but-one* Acting Comptroller, when the firm is the same? Open empirical question.

## Limitations

- Open-source evidence may not reach the *internal* communications between vault-firm partners and successor regulators that would prove deliberate scaffolding strategy. Citations in approval letters are public; the authorship intent isn't.
- The framework can over-attribute design to what may be emergent behavior. Brooks may have authored IL #1170 because he genuinely believed crypto custody was a permissible national bank activity, and Gould may have cited it because it was the on-point authority. The pattern is consistent with both deliberate scaffolding and good-faith administrative law. The diagnostic distinguishing feature is the *firm-level coordination* and the *temporal clustering* of authorship and citation across the same vault-firm network.
- Status: `adopted` based on Round 6 four-instance pattern (Brooks 2020 → Gould 2025; Brooks→Bitfury 2021; Cohen Skadden→OCC 2025; Paoletta 2018+2025 dual-cycle). More instances needed across other agencies (SEC, CFTC, FinCEN) to confirm cross-domain transferability.
