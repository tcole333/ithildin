---
name: Infrastructure Concentration
slug: infrastructure-concentration
domain: financial-crime
source: "Patrick McKenzie, 'Fraud investigation is believing your lying eyes' (Bits About Money, 2024); concept from AML/KYC investigation practice"
status: adopted
created: 2026-02-20
grounding_findings: [2822, 2858, 2839, 321, 327, 604, 2226]
related_models: [enabler-gradient, complexity-as-credential, private-order]
detection_keywords:
  - ["same registered agent", "same formation agent", "same address"]
  - ["shared agent", "shared address", "shared counsel", "shared accountant"]
  - ["captive service", "single-client", "exclusive provider"]
  - ["all entities", "every entity", "all registered", "all formed"]
  - ["service provider cluster", "infrastructure hub", "corporate services"]
  - ["kahn", "indyke", "kellerhals", "bbvi", "hbrk"]
---

## Definition

Fraud operations — like legitimate businesses — require supporting infrastructure: incorporation agents, banks, accountants, lawyers, mail services, registered agents. But unlike legitimate businesses that use a diverse ecosystem of independent providers, fraud operations tend to concentrate their infrastructure around a small number of trusted service providers. This concentration is detectable.

The pattern emerges because fraud infrastructure requires trust — the service providers must be either complicit, captured, or specifically chosen for their lack of scrutiny. This creates clustering: the same formation attorney appears across seemingly unrelated entities, the same registered agent address houses dozens of shells, the same accountant manages books for the entire network. The concentration IS the signal.

In this investigation: The Epstein network demonstrates extreme infrastructure concentration. Richard Kahn (HBRK Associates) served as accountant/financial manager across the entire entity network — his personal entity Coatue Enterprises LLC used HBRK's address, and HBRK managed entities from STC to the personal trusts. Business Basics VI LLC served as registered agent for 14 entities, all Epstein-connected, with zero outside clients — a captive service provider, not an independent registered agent. Darren Indyke served as attorney and co-executor, with his own entities (Indyke Law Firm, Harlequin Dane LLC) operating from the same infrastructure. The three-person core (Kahn, Indyke, Kellerhals) formed an infrastructure hub that serviced the entire multi-jurisdictional corporate structure.

The investigative insight: when you find one node in the infrastructure concentration, pull the thread. Every entity using the same service provider is worth investigating. Every address shared by multiple entities is a lead. The supply chain reveals the network.

## Detection Markers

- Same registered agent serving 5+ entities that appear unrelated on the surface but share beneficial ownership
- Same attorney or accountant appearing across entities in different jurisdictions or different investigation threads
- Address shared by multiple entities with no obvious business reason for co-location
- Service provider with no clients outside the network under investigation (captive/single-client provider)
- Same formation date patterns — entities formed by the same agent within narrow time windows
- Same bank or bank branch servicing multiple network entities (relationship manager concentration)
- Infrastructure provider whose own corporate structure mirrors the network's patterns (Kahn's HBRK using same addresses as client entities)

## Limitations

- Shared service providers can be legitimate — large law firms and accounting firms serve many clients, and co-location at prestigious addresses is common
- The lens is strongest when the service provider is small/niche and the concentration is extreme (14/14 clients from one network)
- Shared registered agents are normal in some jurisdictions (Delaware, Nevada) where statutory agents serve thousands of entities — the signal is in the ratio of network entities to total clients
- Infrastructure concentration proves operational connection, not necessarily criminal intent — it may reflect convenience, cost, or trust rather than concealment
