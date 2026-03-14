---
name: Infrastructure Lock-in
slug: infrastructure-lock-in
domain: org-theory
source: "Shapiro & Varian, 'Information Rules' (1999); Arthur, 'Increasing Returns and Path Dependence' (1994); investigation synthesis"
status: adopted
created: 2026-03-14
grounding_findings: []
related_models: [personnel-pipeline, dual-mandate, manufactured-dependency, infrastructure-concentration, exit-cost-escalation]
detection_keywords:
  - ["sole source", "sole provider", "only vendor", "no alternative", "single vendor"]
  - ["palantir", "gotham", "foundry", "anduril", "lattice", "spacex"]
  - ["switching cost", "migration cost", "replacement cost", "lock-in"]
  - ["proprietary", "custom integration", "deep integration", "embedded"]
  - ["across agencies", "multi-agency", "enterprise-wide", "government-wide"]
  - ["ota", "other transaction", "rapid acquisition", "non-competitive"]
---

## Definition

Infrastructure Lock-in is the embedding of proprietary technology or data systems so deeply into state operations that removal becomes prohibitively costly regardless of political change. The dependency is not manufactured -- it is engineered through genuine technical capability that also happens to give the vendor leverage over the state.

This is adjacent to Manufactured Dependency (Tier 1) but the mechanism is fundamentally different. Manufactured Dependency is "create a problem, sell the solution" -- the operator engineers a crisis and then positions themselves as the rescuer. Infrastructure Lock-in is "become the solution to a real problem, then make yourself impossible to replace." The problem is genuine (the government does need data analytics, launch capability, autonomous defense systems). The solution is genuine (Palantir, SpaceX, and Anduril deliver real capability). But the architecture of the solution creates a dependency that transcends democratic accountability.

It is also distinct from Infrastructure Concentration (Tier 2), which describes how fraud operations cluster around shared service providers -- a detection pattern for related entities. And it is distinct from Exit Cost Escalation (Tier 2), which describes how individual professionals become incrementally trapped in complicity through sunk costs. Infrastructure Lock-in operates at institutional scale and through technical architecture, not individual moral drift.

The analytical marker is: **can this vendor be replaced within one election cycle?** If not, you've achieved lock-in that transcends democratic accountability. The vendor's position persists regardless of who wins elections, which policies change, or what oversight bodies recommend. The infrastructure becomes a structural fact that constrains all future decision-making.

## Mechanism

1. **Capability delivery** -- Provide genuine, often superior technical capability that solves a real government need. Palantir's data integration genuinely helps analysts connect disparate data sources. SpaceX genuinely provides cheaper, more reliable launch services. Anduril genuinely builds autonomous systems the military needs. The capability is not theater -- it's real, and it's often better than alternatives.
2. **Deep integration** -- Architect the solution to integrate deeply with existing government systems, data formats, workflows, and personnel training. The deeper the integration, the higher the switching cost. Palantir running analytics across CIA, NSA, FBI, Army, and ICE simultaneously creates interdependencies that no single agency can unwind unilaterally.
3. **Proprietary architecture** -- Build on proprietary rather than open standards where possible. Custom data models, proprietary APIs, non-portable formats, and platform-specific tooling all increase switching costs. The government's data and workflows become encoded in the vendor's proprietary format.
4. **Knowledge monopoly** -- The vendor's personnel develop institutional knowledge about government data and operations that government employees don't retain. When the vendor's engineers understand the data better than the government's own staff, the dependency extends beyond technology to expertise.
5. **Cross-agency spread** -- Extend from one agency to many. A vendor embedded in one agency is replaceable (painful but feasible). A vendor embedded across the intelligence community, military branches, and civilian agencies simultaneously creates a dependency surface so large that no single replacement decision can address it.
6. **Political insulation** -- The lock-in itself becomes a political argument against replacement: "switching would cost X billion," "transition would create a capability gap," "we can't risk losing this during a crisis." The cost of replacement, not the quality of the vendor, becomes the reason for continuation.

## Detection Markers

- Vendor spread: same company providing similar services across 3+ agencies with independent procurement authority
- Sole-source or limited-competition contracts, especially through OTA (Other Transaction Authority) that bypasses normal competitive procurement
- Contract value growth: initial contract → expansion → enterprise-wide deployment over a short timeline
- Proprietary format dependency: government data stored in vendor-proprietary formats or accessible only through vendor tools
- Personnel dependency: vendor engineers with deeper institutional knowledge than government employees
- Switching cost analysis: what would it cost in time and money to migrate to an alternative? If the answer is "multiple years and hundreds of millions," lock-in has been achieved
- Political connections between vendor leadership and government decision-makers (pair with Dual Mandate and Personnel Pipeline)
- The replacement test: can this vendor be fully replaced within one presidential term (4 years)? If not, the lock-in transcends electoral accountability.

## Why Existing Models Miss This

- **Manufactured Dependency** requires the problem to be fabricated. Infrastructure Lock-in works with genuine problems and genuine solutions -- the dependency is a structural consequence of the architecture, not a deliberately manufactured crisis.
- **Infrastructure Concentration** detects shared service providers as signals of related entities in a fraud network. Infrastructure Lock-in is about a single vendor's dominance across government operations -- a different scale and mechanism entirely.
- **Exit Cost Escalation** describes how *individuals* become trapped through incremental moral compromise. Infrastructure Lock-in traps *institutions* through technical architecture and switching costs.
- **Bridge Tax** describes power from connecting otherwise disconnected groups. Infrastructure Lock-in describes power from becoming the substrate on which groups operate -- you don't bridge the gap, you become the ground.

## Transferability

The pattern appears wherever proprietary infrastructure becomes essential to institutional operations: cloud computing providers (AWS GovCloud), electronic health records in hospitals, enterprise software in corporations, social media platforms as communication infrastructure. The government context is distinctive because the stakes include democratic accountability -- private infrastructure lock-in in government means private leverage over public functions.

## Limitations

- Not every government technology contract is lock-in. Genuine competitive procurement with open standards produces healthy vendor relationships. The model applies when proprietary architecture, cross-agency spread, and replacement infeasibility are all present.
- The model can be used to argue against all government technology modernization ("any vendor relationship creates lock-in"). The diagnostic is not whether a vendor relationship exists but whether the architecture *requires* that specific vendor indefinitely.
- Lock-in can be unintentional. A vendor may deliver genuinely superior technology without deliberately engineering irreplaceability. The structural effect is the same, but the intentionality question matters for analysis. Look for architectural decisions that increase switching costs without corresponding capability benefits.
- The model describes a state-vendor power relationship but doesn't explain what the vendor *does* with that power. Pair with Dual Mandate and Personnel Pipeline to trace how lock-in translates into policy influence.
