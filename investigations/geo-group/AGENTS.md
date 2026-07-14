# GEO Group Investigation Context

## Scope priority

Treat ICE contracting as the priority workstream within a broader investigation
of GEO's corporate, financial, political, legal, and facility network. Rebuild
the procurement record at transaction level rather than relying on company-wide
headline totals.

## Canonical identifiers

- The GEO Group, Inc.: CIK `0000923796`; UEI `JMLKZZ1NL2Z6`; CAGE `3JMR1`;
  HigherGov awardee key `10000076`; headquarters `4955 Technology Way, Boca
  Raton, FL 33431`.
- B.I. Incorporated: UEI `PKK6L9KLMYR5`; CAGE `3CUH9`; HigherGov awardee key
  `10147020`; SAM address `6265 Gunbarrel Ave, Boulder, CO 80301`.
- Initial ICE-relevant legal-name variants: The GEO Group, Inc.; B.I.
  Incorporated; GEO Secure Services, LLC; GEO Transport, Inc.; GEO Corrections
  Holdings, Inc.; GEO Care, Inc.; GEO Care Services, LLC; GEO Management
  Services, Inc.; GEO Reentry Services, LLC; Cornell legacy entities; Protocol
  Criminal Justice, Inc.; Correctional Properties entities.

The 2025 10-K Exhibit 21 omits 75 domestic and 20 foreign subsidiaries. Do not
treat it as a complete entity list; use Exhibit 22 and registry/SAM/award pivots.

## Contract-analysis rules

1. Separate direct ICE prime awards from ICE intergovernmental service
   agreements (IGSAs), county/city pass-throughs, subawards, and facility leases.
2. Separate base awards, task orders, and modifications. Deduplicate by the full
   award/transaction key before summing.
3. Label dollars precisely: current obligations, cumulative obligations,
   potential/ceiling value, outlays, guaranteed minimums, per-diems, or company
   revenue are not interchangeable.
4. Preserve PIID, parent IDV/vehicle, modification number, action date, awardee
   legal name/UEI, contracting office, place of performance, facility, PSC/NAICS,
   and description for every transaction.
5. Crosswalk each GEO/BI facility to contracts, local agreements, ownership,
   capacity, guaranteed minimums, invoices, inspections, deductions, CPARS,
   renewals, and company revenue disclosures.
6. Multiple databases reproducing the same federal award record are redundant,
   not corroborating sources. Prefer the agency contract/solicitation, signed
   instrument, audit, filing, or local agreement when available.
7. Treat lobbying/contribution timing as a lead. Do not infer influence, quid pro
   quo, or procurement causation without direct evidence.
8. Preserve allegation/holding distinctions in litigation and oversight. A filed
   complaint, inspector finding, appellate holding, and pending petition have
   different evidentiary status.

## Source order and rate limits

1. USAspending (no key) for recipient, award, transaction, and subaward baselines.
2. Local SAM public extracts for entity/exclusion pivots without consuming quota.
3. HigherGov for IDV/task-order hierarchy, awardee relationships, subcontracts,
   partnerships, people, and opportunities.
4. Live SAM.gov for current entity, contract-award, exclusion, and opportunity
   confirmation. The present personal key may be limited to 10 requests/day;
   check `search_log`, batch filters, and conserve calls.
5. SEC EDGAR for subsidiary lists, government-revenue concentration, material
   contract disclosures, risks, related parties, debt, and facility portfolio.
6. ICE/DHS/DHS OIG/GAO, signed local IGSAs, county agendas, and court filings for
   primary corroboration and performance evidence.
7. Senate LDA and FEC for political records, with amendment/termination
   deduplication and careful client-expense versus registrant-income labeling.

Always use a unique `/tmp/osint-XXXXXXXX` workdir and `--output FILE`, and follow
the root AGENTS.md audit-sourcing and papercut requirements.
