# Barkmere Group Ltd — Corporate-Registry Crosswalk & Epstein-Overlap Test

**Compiled:** 2026-07-02 | **Analyst run:** registry crosswalk agent (raw working file, not user-facing)
**Scope:** (a) fully document BARKMERE GROUP LTD (BVI); (b) test whether Alessandro Benedetti's offshore infrastructure intersects Jeffrey Epstein's shell infrastructure at any shared registered agent, nominee director, address, or incorporation service.

**Sources queried:** ICIJ Offshore Leaks (Neo4j, local — Panama/Paradise/Pandora/Offshore Leaks), GLEIF, OpenSanctions (local bulk), unified `registry.db`, WebSearch (BVI FSC). **OpenCorporates was UNAVAILABLE** (API token rejected — "Invalid API token"), so no OpenCorporates cross-check was possible this run.

---

## 1. BARKMERE GROUP LTD (BVI) — Registry Card

**RESOLUTION: NEGATIVE.** No registry attributes were retrievable from any available source.

| Attribute | Value | Source / Status |
|-----------|-------|-----------------|
| Formation date | **Not retrievable** | — |
| Registered agent | **Not retrievable** | — |
| Registered address | **Not retrievable** | — |
| Directors / nominees | **Not retrievable** | — |
| Status (active/struck) | **Not retrievable** | — |
| Company number | **Not retrievable** | — |

**What was checked and returned nothing:**
- ICIJ Offshore Leaks full-text search "Barkmere" → **0 matches** (Entity/Officer/Intermediary).
- ICIJ Reconciliation API "Barkmere Group Ltd" → only fuzzy false positives (top hit "AYESA GROUP LTD." 66.7, "KBO Capital Group" 47.6 — all noise, no true match).
- GLEIF "Barkmere" → 1 hit, **"R. COOK HOLDINGS INC." in Barkmere, Québec (CA)** — a place-name coincidence (Barkmere is a Québec municipality), not the BVI entity.
- OpenSanctions "Barkmere" → 0 results.
- Local `registry.db` "Barkmere" → 0 entities.
- WebSearch `"Barkmere Group" BVI` → no company hits; only generic BVI-registered-agent explainer pages.

**Interpretation (INFERENCE, not fact):** Barkmere Group Ltd's absence from *every* offshore leak (Panama 2016, Paradise 2017, Pandora 2021) plus all live indices is consistent with one or more of:
1. Formation **after** the Pandora Papers document cutoff (~2018–2019), i.e. the entity post-dates all leaks — plausible given the receipt of Misra funds is dated **April 2015** but the entity could have been incorporated shortly before and simply never appeared in a leaked agent's book.
2. Incorporation through a BVI registered agent whose files were **never** part of any leak (most BVI agents were not — Mossack Fonseca and Appleby are the leaked ones; Barkmere used neither, or used one whose records didn't leak).
3. BVI's registry is **not publicly searchable for free**: beneficial ownership sits in the non-public BOSS/VIRRGIN system, and the FSC name-search portal (live since Dec 2025) requires a paid/registered account. Confirming Barkmere therefore requires either a paid BVI VIRRGIN search or a live OpenCorporates BVI (`vg`) query — **both blocked this run** (no OC token; no BVI paid access).

**Recommended next step to resolve:** restore a valid `OPENCORPORATES_API_KEY` and run `query_opencorporates.py entity vg <number>` / `search "Barkmere" --jurisdiction vg`; or commission a BVI VIRRGIN name search. The beneficial-control-by-Benedetti claim and the ~$500K April-2015 Misra transfer remain **DB-sourced assertions not independently corroborated by a registry record** as of this run.

---

## 2. Agent / Address Walk

### 2a. PO Box 3483, R.G. Hodge Plaza, Wickhams Cay 1, Road Town, Tortola (BVI)
The two known co-located entities — **YOUNGSTOWN INVESTMENTS GROUP LTD** (BVI 1688567) and **SATSU FINANCE LTD** (BVI 1583501) — do **not** appear in ICIJ:
- Reconcile "Youngstown Investments Group" → only fuzzy noise (best: "TRILOGY INVESTMENTS GROUP S.A." 62.1); no true match.
- Reconcile "Satsu Finance" → no true match.
- ICIJ full-text "R.G. Hodge Plaza" → 0 matches.

**R.G. Hodge Plaza / PO Box 3483 is a well-known mass registered-agent address in Road Town** (used by numerous BVI corporate-services providers). It is a **WEAK** signal by construction — such addresses host thousands of unrelated IBCs. No Epstein-linked entity was found at this address in any available source (not searchable in ICIJ because none of these entities are in the leaks).

### 2b. 123 Melita Street, Valletta VLT 12, Malta (Benedetti's Malta agent address)
This is the **registered address of TREE OF LIFE LIMITED** (Benedetti's confirmed Malta entity — see §3). Its co-tenants at 123 Melita Street (from ICIJ Paradise Papers, `registered_address` edges) are a cluster of Malta shipping/yacht/aviation/holding shells serviced by **AEGIS Corporate Services Limited** (the Malta CSP operating from this address), including:

> RIKKA PRODUCTS LTD · BLACK AND WHITE YACHT COMPANY LTD · R.T.K INTERNATIONAL LTD · GCCHART LTD · WELLESLEY LTD · SEQUOIA INTERACTIVE LTD · CREDIT SOLUTIONS (ITALIA) LTD · MOSKING CHARTER CO LTD · JRC INTERNATIONAL HOLDINGS LTD · OCEAN FRESH WATER HOLDING LTD · PENTA GRAPH (PRINTERS) CO LTD · REENAM INDUSTRY LTD · EAST COAST NAVIGATION LTD · RIX PARTNER SHIPPING LTD · [and others]

**None of these are Epstein-linked.** The cluster is Malta maritime/industrial, entirely disjoint from Epstein's US/USVI/offshore footprint.

---

## 3. Benedetti-side vs Epstein-side Intermediary Comparison

### Benedetti-side offshore nodes CONFIRMED in ICIJ

| Node | ICIJ ID | Type | Source | Key attributes |
|------|---------|------|--------|----------------|
| **TREE OF LIFE LIMITED** | 55063719 | Entity | Paradise Papers — Malta | Jurisdiction MLT; **reg. address 123 Melita Street, Valletta**; officers below |
| **ALESSANDRO BENEDETTI** | — | Officer | Paradise Papers — Malta | `officer_of` Tree of Life Limited |
| **CEDRIC MIFSUD** | 56023717 | Officer | Paradise Papers — Malta | Malta nominee; `officer_of` **~40 entities** (AEGIS Corporate Services network) |
| **LIANE MARIA LEDWON** | — | Officer | Paradise Papers — Malta | Co-officer of Tree of Life; Malta nominee |
| **AEGIS CORPORATE SERVICES LIMITED** | — | Entity+Officer | Paradise Papers — Malta | The Malta CSP at 123 Melita Street |
| **SPQR CAPITAL LLP** | 11013416 | Entity | (reconcile 70.0) | UK LLP name-match to SPQR Capital — not further traced (no exact leak edge) |
| **BERTRAND GAUQUELIN DES PALLIERES** | 56016709 | Officer | (100% reconcile) | Lugano CH; `officer_of` **APARTNERS CAPITAL INVESTMENT MANAGEMENT LIMITED**; reg. address Via Campo Marzio 1, Stabile Vogue, Lugano CH-6900 |

Mifsud's full `officer_of` set is Malta CSP boilerplate (LUX YACHT LTD, S & D AVIATION LTD, RED SKY NAVIGATION LTD, SEMPER HOLDING LTD, MOBILE VENTURES LTD, ASPIDER SOLUTIONS MALTA LTD, MIDDLESEX UNIVERSITY (MALTA) LTD, etc.). All Malta. **No Epstein-adjacent entity in the list.**

### Epstein-side infrastructure — ICIJ presence

| Epstein shell | In ICIJ? | Notes |
|---------------|----------|-------|
| Jeffrey Epstein (person) | **NO** — 0 matches | Epstein is essentially absent from Offshore Leaks |
| Southern Trust Company | **NO** (as Epstein's) | Only unrelated 1911/1923 Florida "Southern Trust Company" shells in `registry.db`; Epstein's Southern Trust Co. (USVI/DE) is not in ICIJ |
| Financial Trust Company | **No true match** | 56 fuzzy "Financial Trust" hits, all unrelated (Niue/Cook Islands/etc.) |
| Zorro Trust | **NAME-COLLISION ONLY** | "THE ZORRO TRUST" (ICIJ 200801878, **Nevis**, Paradise Papers) is intermediated by **Meridian Trust Company Ltd.** — a Nevis CSP, NOT Epstein's people. Epstein's Zorro Trust was a US/NY vehicle. Different entity. |
| Nautilus Inc | **No true match** | 105 "Nautilus" hits (Panama/Niue/BVI shells) — none tie to Epstein |
| Hyperion Air | **NO** — 0 matches | — |

### OVERLAP VERDICT

| Overlap dimension | Finding | Verdict |
|-------------------|---------|---------|
| **Shared registered agent** | Benedetti = AEGIS Corporate Services (Malta) + unknown BVI agent for Barkmere/Youngstown/Satsu. Epstein = his own USVI/US administrators + (Nevis Zorro) Meridian Trust. No agent appears on both sides. | **NONE** |
| **Shared nominee director** | Mifsud / Ledwon (Benedetti) never appear on any Epstein entity; Epstein's nominees (Indyke, Kahn, etc.) never appear on any Benedetti entity. | **NONE** |
| **Shared specific address** | 123 Melita St (Benedetti-Malta) and PO Box 3483 R.G. Hodge Plaza (Benedetti-BVI) host no Epstein entity; no Epstein address appears on the Benedetti side. | **NONE** |
| **Shared incorporation service** | Benedetti = AEGIS (Malta) + un-leaked BVI agent. Epstein = un-leaked US/USVI. No common CSP. | **NONE** |

**BOTTOM LINE: NO OVERLAP (STRONG-confidence negative on the leaked/indexed data; caveated).** There is zero intersection between Benedetti's offshore infrastructure and Epstein's at agent, nominee, address, or incorporation-service level in any available dataset.

**Caveat on the negative:** the negative is only as strong as the coverage. Both sides are *thinly* represented in the leaks — Epstein is essentially absent from ICIJ, and Barkmere/Youngstown/Satsu are absent too (un-leaked BVI agent). A true test at the **BVI-agent** level (does Barkmere's registered agent also serve any Epstein BVI entity?) **cannot be run without live BVI/OpenCorporates access**, which failed this run. So: no overlap found, but the specific high-value test (shared BVI agent) is **UNTESTED**, not disproven.

---

## 4. des Pallieres Reconciliation

**CONCLUSION: "Bertrand Gauquelin des Pallieres" is a confirmed real person; "Stephane des Pallieres" is UNCORROBORATED and likely NOT a distinct second person.**

- **BERTRAND GAUQUELIN DES PALLIERES** — ICIJ Officer **ID 56016709**, 100% reconcile match. `officer_of` **APARTNERS CAPITAL INVESTMENT MANAGEMENT LIMITED**; registered address **Via Campo Marzio 1, Stabile Vogue, Lugano CH-6900** (Switzerland). This is consistent with the DB's SPQR/OneIM/Attali "Apartners" association — the "APartners"/"Attali Investment Partners" naming aligns. **Confirmed single identity.**
- **"Stephane des Pallieres"** — **no ICIJ match, no OpenSanctions match.** The reconciler's nearest hits for that string are (i) the same Bertrand record (25.0), and (ii) **Jersey place names** — "Rue des Pallieres / La Rue des Pallieres, St. Ouen, Jersey JE3 2BB" (Woodlands/Syon House addresses). "des Pallieres" is a Jersey/Norman toponym.

**Reconciliation verdict (INFERENCE):** The two DB records are most plausibly **the same underlying person recorded under a garbled/erroneous given name**, OR the "Stephane" record originated from a place-name string ("Rue des Pallieres, Jersey") mis-parsed as a person. There is **no independent evidence of a distinct "Stephane des Pallieres" individual.** Recommend merging "Stephane des Pallieres" into "Bertrand Gauquelin des Pallieres" pending a source-of-record check on where the "Stephane" spelling entered the DB — do NOT treat them as two people without a primary source naming a Stephane.

---

## 5. Source / Tool Status (this run)

| Source | Status |
|--------|--------|
| ICIJ Offshore Leaks (Neo4j local) | **WORKING** — Neo4j up at :7689; search/entity/connections/reconcile all functional |
| GLEIF | **WORKING** |
| OpenSanctions (local bulk) | **WORKING** |
| Unified `registry.db` | **WORKING** |
| WebSearch (BVI FSC) | **WORKING** but no Barkmere data (BVI registry not free-searchable) |
| **OpenCorporates** | **FAILED — "Invalid API token".** No global/BVI cross-check possible. Blocks the one test that could resolve Barkmere and the shared-BVI-agent question. |
| BVI VIRRGIN / FSC name search | **NOT ACCESSED** — requires paid/registered account (beneficial ownership non-public by BVI law) |

**Nothing in this file is a fabricated registry attribute.** Every "Not retrievable" is exactly that — not retrieved from any available source.
