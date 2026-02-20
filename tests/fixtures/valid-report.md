---
agent: agent-a
target: "Leon Black"
skill: deep-investigate
status: completed
findings_added: 5
connections_added: 3
entities_registered: 2
leads_spawned: 2
---
# Agent A Report: Leon Black

## Key Discoveries
- Found 5 emails between Black and Epstein discussing STC transfers
- Identified BV70 LLC as conduit entity

## Findings Added
5 findings (IDs: 3180, 3181, 3182, 3183, 3184)

## Connections Added
3 connections

## Negative Results
- No FARA registrations found
- No CourtListener hits for Black-Epstein litigation

## Follow-Up Leads
- Lead #1714: Investigate BV70 LLC formation and dissolution timeline

## Learnings
- [Friction] query_doj.py FTS5 times out for common single words like "black" — need to use quoted phrases
- [Surprise] STC balance sheet shows $121M in assets despite Epstein's claimed modest income
- [Methodology] Cross-referencing 990 grants against entity_roles reveals hidden board memberships
