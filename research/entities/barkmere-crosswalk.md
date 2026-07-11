# Barkmere Group Ltd — Corporate-Registry Crosswalk & Epstein-Overlap Test

**Compiled:** 2026-07-02 | **Updated:** 2026-07-09 (lead #49533) | **Analyst run:** registry crosswalk agent (raw working file, not user-facing)
**Scope:** (a) fully document BARKMERE GROUP LTD (BVI); (b) test whether Alessandro Benedetti's offshore infrastructure intersects Jeffrey Epstein's shell infrastructure at any shared registered agent, nominee director, address, or incorporation service.

**Sources queried:** i-BVI public company index; BVI FSC Public Search/terms pages; Virgin Islands Official Gazette web index; ICIJ Offshore Leaks reconciliation API and public entity pages; OCCRP Aleph cloud; GLEIF; OpenSanctions (local bulk); unified `registry.db`; CourtListener; OffshoreAlert public API; SEC EDGAR; and exact web searches of BVI/ECCS/BAILII/JCPC sources. **OpenCorporates remained unavailable** (invalid API token; public page presented hCaptcha). i-BVI is an aggregator, not an official ownership record.

---

## 1. BARKMERE GROUP LTD (BVI) — Registry Card

**RESOLUTION: BASIC IDENTITY ONLY.** A public BVI company index now supplies a company number and registration date. No public person-level or service-provider fields were retrieved.

| Attribute | Value | Source / Status |
|-----------|-------|-----------------|
| Registration date | **14 February 2006** | i-BVI public index; aggregator, not certified extract |
| Registered agent | **Not retrievable** | — |
| Registered address | **Not retrievable** | — |
| Directors / nominees | **Not retrievable** | — |
| Status (active/struck) | **Not retrievable** | — |
| Company number | **1010725** | i-BVI public index; aggregator, not certified extract |

**What was checked:**
- i-BVI exact record → **BARKMERE GROUP LTD., no. 1010725, registered 14 February 2006**. Its page exposes no status, director, shareholder, registered-agent, address, charge, or continuation field. Treat this only as an index lead.
- ICIJ Reconciliation API "Barkmere Group Ltd" → only fuzzy false positives; "Barkmere" and "1010725" → **0 exact matches**. The public page for reconciled Alessandro Benedetti node **56105421** lists exactly one entity connection, Malta **Tree of Life Limited**, not Barkmere.
- OCCRP Aleph cloud "Barkmere", exact name, and "1010725" → **0 results**.
- GLEIF exact name/number → **0 results**; the broader place-name hit in Barkmere, Québec is unrelated.
- OpenSanctions exact name/number → **0 results**.
- Local `registry.db` exact name → **0 results**.
- CourtListener, OffshoreAlert public API, SEC EDGAR, USAspending, LDA, and FARA exact-name searches → **0 true matches**.
- Exact searches of BVI FSC publications, Virgin Islands Official Gazette PDFs, ECCS/BVI judgments, BAILII, JCPC, and The Gazette → **0 indexed Barkmere/1010725 notices**. The Gazette's own archive search requires login, so that negative is not exhaustive.
- BVI FSC now advertises an official Public Search & BO Search portal. A later in-app-browser attempt reached the entity-search form, which requires a **Primary Email Address** together with entity number/name. No Barkmere query was submitted because no research email was authorised for transmission. Some certificates, records, or ownership requests may additionally require login, fees, or legal eligibility. No account was created and no purchase was made.
- OpenCorporates API token remained invalid; the public page presented hCaptcha.

**Interpretation (INFERENCE, not fact):** Company 1010725 predates the reported April 2015 payment by nine years. The earlier late-2014/purpose-built-shell inference is therefore wrong. The 2006 date does not identify who controlled the company in 2015: control could have changed, or the company could have remained with an original owner. Absence from the offshore-leak indexes is consistent with use of a BVI agent whose files were not leaked, but does not establish which agent was used or whether ownership changed.

**Recommended next step to resolve:** use an authorised project/research email to conduct a lawful exact-number search for **1010725** in the BVI FSC Public Search portal and preserve the returned current name/status/type and any previous names. Then, if authorised and still material, obtain the official historical company report/list of directors/registered-agent and charge records. The WSJ remains the source for Benedetti control and the reported April-2015 transfer; the i-BVI card does not corroborate ownership or payment.

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
| **Shared registered agent** | Tree of Life used the Malta AEGIS/Mifsud service layer. Barkmere's BVI agent is unknown. No known agent appears on both the documented Malta and Epstein sides, but the Barkmere-specific test cannot yet be run. | **UNRESOLVED FOR BARKMERE** |
| **Shared nominee director** | Mifsud/Ledwon do not appear on indexed Epstein entities. Barkmere's directors are unknown, so a Barkmere-specific nominee test is not possible. | **NO KNOWN MATCH; BARKMERE UNTESTED** |
| **Shared specific address** | No indexed Epstein entity appears at Tree of Life's Malta addresses. No registered address is known for Barkmere itself; PO Box 3483 belongs to other Benedetti-associated BVI vehicles and must not be imputed to Barkmere. | **NO KNOWN MATCH; BARKMERE UNTESTED** |
| **Shared incorporation service** | AEGIS/Mifsud is documented only for Tree of Life. Barkmere's incorporation service is unknown. | **UNRESOLVED FOR BARKMERE** |

**BOTTOM LINE: NO OVERLAP FOUND IN THE INDEXED DATA; THE KEY BARKMERE TEST REMAINS OPEN.** The available records do not show a common agent, nominee, address, or incorporation service. Because Barkmere's directors, agent, and address are all unknown, this is not a strong-confidence disproof of a shared-service-provider bridge.

**Caveat on the negative:** both sides are thinly represented in the leaks. A true test at the **BVI-agent** level (does Barkmere's registered agent also serve an Epstein-linked BVI entity?) requires Barkmere's official historical registered-agent record. The public index does not provide it. So: no overlap found, but the specific high-value test is **UNTESTED**, not disproven.

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
| ICIJ Offshore Leaks | Reconciliation API and public entity pages **WORKING**; local Neo4j unavailable because Docker was not running. Public Benedetti node 56105421 resolved the needed edge denominator. |
| GLEIF | **WORKING** |
| OpenSanctions (local bulk) | **WORKING** |
| Unified `registry.db` | **WORKING** |
| i-BVI index | **WORKING** — basic name/no./date only; aggregator, not ownership proof. |
| BVI FSC Public Search | Portal and entity-search form reached; exact record **NOT RETRIEVED** because the form requires transmission of a Primary Email Address and none was authorised. |
| Virgin Islands Official Gazette | Indexed exact-name/number searches returned zero; archive's own search requires login. |
| **OpenCorporates** | **FAILED — "Invalid API token";** public page presented hCaptcha. It may corroborate basic indexed fields if coverage exists, but an official historical BVI file is still needed for the agent-level test. |
| BVI official company documents / BO request | **NOT ACCESSED** — some records/requests require authentication, fees, and/or legal eligibility; no purchase or account creation was authorised. |

**Nothing in this file is a fabricated registry attribute.** Every "Not retrievable" is exactly that — not retrieved from any available source.
