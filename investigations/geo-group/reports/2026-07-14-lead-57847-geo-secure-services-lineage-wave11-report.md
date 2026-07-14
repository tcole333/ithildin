# GEO Secure Services legal-identity and lineage trace

Lead: #57847  
Profile: `geo-group`  
Scope: corporate identity, statutory lineage, status, names, officers/managers, addresses, GEO parent disclosure, merger boundary, and federal registration identity. Award, wage-case, contract-performance, and facility analysis were excluded.

## Bottom line

**GEO Secure Services, LLC is one active Florida LLC, document L12000160666.** Florida lists a December 26, 2012 filing date, an October 2, 2012 effective date, FEI `46-1258100`, and active status. The entity began as the conversion result of the distinct Florida corporation **GEO Corrections & Detention, Inc.**, P12000083665. The LLC later used the legal name **GEO Corrections and Detention, LLC** before changing its name to GEO Secure Services on August 1, 2019. That former legal name and SAM's punctuation-only DBA `GEO SECURE SERVICES LLC` are aliases of canonical entity #4811, not separate companies.

Florida also resolves the otherwise ambiguous **GEO GSS Holdings, LLC**. L22000531201 was formed on December 20, 2022. Its event history says it was part of a January 23, 2023 merger whose qualified corporation was L12000160666; the GEO Secure Services event record says L12000160666 was the merger result. The two registry rows are one reciprocal event chain. The evidence supports relation #861, `#5146 --merged_into--> #4811`. It does **not** support treating GSS Holdings as a parent, subsidiary, or intermediate owner.

## Statutory identity and name history

Florida's event history provides the exact legal chain:

1. P12000083665, GEO Corrections & Detention, Inc., was filed as a Florida profit corporation on October 2, 2012.
2. On December 26, 2012, P12000083665 converted into Florida LLC L12000160666. The LLC's filing date is December 26 and its effective date is October 2.
3. The LLC's old name was GEO CORRECTIONS AND DETENTION, LLC. A Florida LLC name-change event filed August 1, 2019 produced the current legal name.
4. On January 23, 2023, the short-lived GSS Holdings entity merged into L12000160666. GEO Secure Services survived and remains active.

These events are recorded as predecessor entity #5165, conversion relation #860, former-name alias #228, merger relation #861, and finding #13062-#13063. Compound auto-entities #4870 and #4977 remain finding-cluster nodes; they were not merged into or substituted for the legal entity.

## Current status, roles, and addresses

The March 24, 2026 Florida annual report lists five managers for GEO Secure Services: George C. Zoley, J. David Donahue, Wayne Calabrese, Scott Schipma, and Shayn March. Sunbiz lists `4955 Technology Way, Boca Raton, FL 33431` as the entity's principal and mailing address and Corporate Creations Network, Inc., `801 US Highway 1, North Palm Beach, FL 33408`, as registered agent. Finding #13064 and roles #2626-#2630 preserve that current snapshot without inventing appointment dates.

The GSS Holdings detail record lists nine merger-era roles. Role #2587 was corrected in place from a truncated Florida title code to `Manager, Executive Chairman`; roles #2631-#2638 add the remaining exact titles. The entity's principal, mailing, and agent addresses are stored separately. Shared managers and addresses corroborate group context but are not the legal basis for the merger relation.

## Parent, guarantor, and ownership boundary

GEO's fiscal-2025 Exhibit 21 lists `GEO Secure Services, LLC (FL)` and states that GEO holds directly or indirectly 100% of the listed subsidiaries unless otherwise noted. Existing verified finding #12382 and preserved relation #817 already record that boundary. The exhibit does not state whether GEO's ownership of this LLC is direct and does not identify an intermediate owner.

Exhibit 22 separately lists GEO Secure Services as a subsidiary guarantor for GEO's outstanding senior notes. A bounded CourtListener RECAP search also returned a 2024 docket-entry description identifying The GEO Group, Inc. as GEO Secure Services' corporate parent. The underlying RECAP document was unavailable, so the SEC filing remains the controlling ownership source. No additional ownership edge was created.

## Federal registration identity

The March 2026 SAM public extract identifies GEO Secure Services as UEI `JLG3JBCL4CC7`, CAGE `7G0P0`, state of incorporation Florida, entity start date October 2, 2012, and DBA `GEO SECURE SERVICES LLC`. Existing verified finding #12665 records the July 13, 2026 live SAM update: active registration through May 20, 2027, last updated and activated June 1, 2026. This lead reused that verified live control rather than consuming another limited SAM call.

SAM is an identity/status source, not evidence of parentage. The no-comma DBA is alias #229, marked by `created_by=lead57847:sam_dba` while retaining the schema's `entity_variant` alias type.

## Database actions

- Enriched canonical GEO Secure Services entity #4811 with FEI, formation date, official address, status, and Sunbiz lineage provenance.
- Created distinct predecessor corporation #5165; created conversion relation #860 to #4811.
- Enriched GEO GSS Holdings #5146 with formation date and exact merger boundary; created merger relation #861 to #4811.
- Added aliases #228 (former legal name) and #229 (SAM DBA), with explicit `created_by` provenance.
- Corrected role #2587 in place and added roles #2626-#2638.
- Added address records #1076-#1081 while preserving existing SAM physical-address row #1065.
- Added and verified findings #13062-#13064 in global thread 111.
- Preserved relation #817 and all compound auto-entities; no merge or deletion was performed.

## Limits

No reviewed filing reveals whether GEO's 100% interest is direct or routed through an intermediate owner. No Delaware certificate or foreign-qualification record was recovered; Florida's own record establishes domestic Florida formation. OpenCorporates could not be used because the configured token was invalid, and no inference was drawn from the failed secondary lead check. The precise party to the 2017 zero-qualified-corporation Florida merger was not resolved because it does not change the supported 2012 conversion, 2019 name change, or 2023 GSS Holdings bridge.

See the legal-lineage/status matrix, officer-role/address matrix, parent/affiliate matrix, negative log, source/DB manifest, and SHA-256 ledger for the full audit trail.
