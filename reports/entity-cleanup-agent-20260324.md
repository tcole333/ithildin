# Entity Cleanup Report — CRML/Swiss Commodity Re Investigation
**Date:** 2026-03-24
**Scope:** Duplicate entity normalization introduced during Swiss Commodity Re / CRML investigation
**Database:** investigation.db

---

## 1. What Was Inspected

Four duplicate entity pairs were identified for audit:

| Duplicate Set | Canonical ID | Duplicate ID |
|---|---|---|
| Swiss Commodity Re Limited | 843 | 1480 |
| Kenneth Raymond Deayton | 1257 | 1481 |
| Hong Kong Corporate Services Group | 873 | 1258 |
| Malcolm Scott Macintyre | 1344 | 874 |

Each pair was inspected via `entity_tracker.py show --json` before any action. Canonical records were selected based on richness of existing data (roles, addresses, relations). The `entity_dedup.py` merge tool does not copy the `notes` field from deleted entities, so all four canonical records were manually enriched via `sqlite3` before merging to preserve provenance.

---

## 2. Duplicate Analysis

### 2.1 Swiss Commodity Re Limited (#843 vs #1480)

**Canonical: #843** — SEC-sourced, had 2 roles, 1 address, 3 relations.
**Duplicate: #1480** — HK Companies Registry-sourced, had 0 roles/addresses/relations but contained unique facts: Company No. 79047415, incorporation date Oct 30 2025 (22 days before copper deal announcement).

**Action:** Notes on #843 updated to include company number and incorporation date. #1480 merged into #843 (no data rows to migrate).

### 2.2 Kenneth Raymond Deayton (#1257 vs #1481)

**Canonical: #1257** — SEC-sourced, richly detailed bio, 1 role, 1 residential address, 2 outbound relations.
**Duplicate: #1481** — HK Companies Registry + Panama Papers-sourced, had 0 roles/addresses/relations but contained unique facts: controlled Newbury Investment Limited (BVI) via Mossack Fonseca (incorporated Sep 4 1991); corporate insider at Nimble Holdings (0186.HK).

**Action:** Notes on #1257 updated to include Panama Papers provenance and Nimble Holdings connection. #1481 merged into #1257 (no data rows to migrate).

### 2.3 Hong Kong Corporate Services Group (#873 vs #1258)

**Canonical: #873** — older record, had 1 role, inbound relation from #843.
**Duplicate: #1258** — web-sourced, had 1 role (with date range), 1 business address, 1 outbound relation. Added Callan Anderson as a named principal.

**Action:** Notes on #873 updated to include Callan Anderson. #1258 merged into #873, migrating: 1 role, 1 address, 1 entity_relation (`--services--> Swiss Commodity Re #843`).

### 2.4 Malcolm Scott Macintyre (#874 vs #1344)

**Canonical: #1344** — more complete record, confirmed identity (MD of Capella Capital), 1 role, 1 residential address.
**Duplicate: #874** — SEC 424B3-sourced, had 1 registered address (same physical location), 0 roles. Identity was noted as uncertain ("may be same Malcolm Macintyre").

**Action:** Notes on #1344 updated to cross-reference both SEC filing accession numbers. #874 merged into #1344, migrating 1 address record (same physical location, slightly different formatting).

---

## 3. Dry-Run Results

All four merges were run in `--dry-run` mode before execution. Output confirmed:

| Merge | Rows Migrated |
|---|---|
| #1480 -> #843 | 0 data rows (notes-only enrichment) |
| #1481 -> #1257 | 0 data rows (notes-only enrichment) |
| #1258 -> #873 | 1 entity_roles, 1 entity_addresses, 1 entity_relations |
| #874 -> #1344 | 1 entity_addresses |

No unexpected conflicts were reported by the dry-run.

---

## 4. Actual Merges Performed

All four merges executed successfully. All deleted entity IDs (874, 1258, 1480, 1481) confirmed absent from `entities` table post-merge.

---

## 5. Surviving Canonical Records (Post-Merge Verification)

### Entity #843 — Swiss Commodity Re Limited
- Type: ltd | Switzerland | active
- Notes: Includes SEC source, HK company number (79047415), incorporation date (Oct 30 2025), and address co-location with HKCSG
- Roles: 2 (Deayton as controller — minor pre-existing redundancy between un-dated and 2025-dated entries)
- Addresses: 1 (6F Wyndham Place, Central HK)
- Outbound: `--controls--> HKCSG #873`
- Inbound: `HKCSG #873 --services-->`, `Deayton #1257 --controls-->`

### Entity #1257 — Kenneth Raymond Deayton
- Type: person | hk | active
- Notes: Full career bio + Panama Papers (Newbury Investment Ltd BVI, 1991) + Nimble Holdings (0186.HK) insider
- Roles: 1 (CRML independent NED / audit chair, 2016–2017)
- Addresses: 1 (Unit F3, Goodview Garden, 24 Stubbs Road, Hong Kong)
- Outbound: `--controls--> Sprocket HK Limited #1482`, `--controls--> Swiss Commodity Re #843`

### Entity #873 — Hong Kong Corporate Services Group
- Type: inc | HK | active
- Notes: Co-founded by Deayton (CEO/MD) and Callan Anderson; registered address of Swiss Commodity Re
- Roles: 2 (Deayton as MD/CEO/Co-founder + MD and CEO 2001– ; minor pre-existing redundancy)
- Addresses: 1 (6F Wyndham Place, Central HK)
- Outbound: `--services--> Swiss Commodity Re #843`
- Inbound: `Swiss Commodity Re #843 --controls-->` *(see residual issue below)*

### Entity #1344 — Malcolm Scott Macintyre
- Type: person | au | active
- Notes: MD of Capella Capital; 200,000 CRML shares from Nov 2025 copper deal; identity confirmed across two SEC filings
- Roles: 1 (MD of Capella Capital, 2009–)
- Addresses: 2 (same physical location — "22 Faraday Avenue, Rose Bay NSW 2029" — with minor formatting variation between the two records)

---

## 6. Residual Issues (Not Resolved — Require Follow-Up)

### 6.1 Inverted Relation: #843 controls #873
Entity #843 (Swiss Commodity Re Limited) has an outbound `--controls-->` relation pointing to entity #873 (Hong Kong Corporate Services Group). This appears semantically inverted: HKCSG is the corporate services provider; SCR is merely a client/registered entity using HKCSG's address. The correct relation is represented by #873's outbound `--services--> #843`. The `--controls-->` relation on #843 likely originated from a mis-tagged finding during the investigation wave and should be reviewed and corrected or deleted by a researcher.

### 6.2 Duplicate Roles on #843 (Deayton as Controller)
Two roles are recorded on entity #843 for Deayton as controller:
- `Controller (voting and investment control)` (no date)
- `controller (voting/investment) (2025 -> ?)`

These describe the same role from different sources. Not introduced by this cleanup; pre-existed in the original #843 record. A researcher should review and consolidate to one entry.

### 6.3 Duplicate Roles on #873 (Deayton at HKCSG)
Post-merge, entity #873 has two Deayton roles:
- `Managing Director / CEO / Co-founder` (no date, from original #873)
- `Managing Director and CEO (2001 -> ?)` (from merged #1258)

Both are accurate; the second adds the start date. Consolidation to the dated entry is recommended.

### 6.4 Duplicate Addresses on #1344 (Macintyre)
Two address records exist after merge:
- `[residential] 22 Faraday Avenue, Rose Bay NSW 2029, Australia`
- `[registered] 22 Faraday Avenue, Rose Bay, New South Wales, 2029, Australia`

Same physical location, different formatting and address type. Harmless, but could be consolidated to a single record.

---

## MACHINE SUMMARY

```
CANONICAL_ENTITY_IDS:
  swiss_commodity_re_limited:         843
  kenneth_raymond_deayton:           1257
  hk_corporate_services_group:        873
  malcolm_scott_macintyre:           1344

DELETED_ENTITY_IDS: 874, 1258, 1480, 1481
MERGES_APPLIED: 4
MERGES_SKIPPED: 0
RESIDUAL_ISSUES: 4 (inverted relation on #843; duplicate roles on #843, #873; duplicate addresses on #1344)
```
