# Midland Consult — ICIJ Offshore Leaks map

## Scope and source

This map was rebuilt on 2026-07-15 from ICIJ's official remote reconciliation/node workflow and the official `full-oldb.LATEST.zip` bulk release generated 2025-03-31 (SHA-256 `a2e37e8b878c12fb8f946d4e85026a4ae9026dc866b1aa925730bc1b50e52914`). The Offshore Leaks portion is current through 2010, so absence is bounded by that coverage.

The ICIJ nodes do not supply corporate registration numbers or officers for the two Midland intermediaries. Corporate-registry evidence linking Maxim A. Stepanov to UK/Cyprus Midland companies must therefore be kept distinct from the ICIJ graph; the ICIJ records alone do not establish that he controlled node 298222 or node 298201.

## Intermediary nodes

| ICIJ node | Record | Registered address | Entity relationships |
|---|---|---|---:|
| `298222` | Midland Consult Ltd.; Russia | Krutisky Val Street 14/16, 3rd Floor, Moscow 109172 | 194 |
| `298201` | Midland Consult (Cyprus) Limited; Cyprus | 69 Makarios Ave., Tlais Tower, Office 301, Nicosia 1070 | 12 |

The two lists contain 206 distinct entities, all recorded with Commonwealth Trust Limited as service provider and undetermined incorporation jurisdiction. Country fields associate the Moscow list with Russia and mostly the BVI, and the Cyprus list with Cyprus and the BVI. The 12 Cyprus entities are Pangasio, Bucatino, Cometta AG, Bresala, Fontina, Illion, Paratiro, Alde Reano, Vienitta, Macdina, Orion Express Worldwide, and Caratelo.

## Overlap result

No exact or stable-identifier overlap was found between the 206 entity nodes, 67 adjacent officer nodes, or the two Midland address nodes and the verified `dfj-network` targets or graph endpoints. This includes:

- Spanish-record entities: Casasol, Louys, Tomillo, Namur, Kost, Sandronella, Eporoyal, Virginia Ventures, Merkin, Kinbow, Sunbridge, Dulcina, and Administral.
- Technology/VC entities: QWave, Centice, Nano-Meta, Fintech Ventures, Ritzio, Finstar, Runa, Acronis, DFJ, Zone, and Day One.
- People: both separately scoped Kouzmine identities, Beloussov, Boyko, Creer, Drokova/Bucher, and Maxim Stepanov.
- Addresses: 2882 Sand Hill Road, 55 E. 3rd Avenue, Calle Asmagui 156, and 835 Central Avenue, Hot Springs.

Matching used Unicode normalization, case-folding, punctuation and legal-suffix removal, exact/core-exact comparison, and manual review of fuzzy candidates. The broad claim that Midland formed the Spanish Kouzmine/QWave/DFJ entities is disconfirmed by the available ICIJ data. [Findings #13742-#13743]

## Important non-Midland ICIJ records

- Appleby data lists **ISB Development Corporation** as a shareholder of **Runa Capital Fund I L.P.** A 2002 SEC prospectus states that the U.S./QWave Serguei Kouzmine owned ISB Development Corp. This independently establishes an ISB→Runa Fund I path for the U.S./QWave person, without reviving the retracted Spanish-to-QWave identity merge. [Finding #13744; connections #6498-#6499]
- Runa Fund I's 51 listed shareholder nodes include Beloussov, Zubarev, Runa Capital, and ISB Development Corporation, but no named DFJ, Draper, Jurvetson, or Creer shareholder. That fund-specific negative does not disprove the FBI memo's differently worded QWave-investment allegation. [Finding #13745]
- Appleby data lists DFJ Fund IX and DFJ Partners IX at **2882 Sand Hill Road** as shareholders of Power Ventures Inc. These records are independent of Midland and Runa. [Finding #13746; connections #6500-#6501]

## Name-collision controls

| Candidate | Assessment |
|---|---|
| Administral Anstalt (`11002639`) | Exact Liechtenstein firm name and four non-Midland clients; no shared registration number or Midland client overlap. |
| Banff Investments S.A. (`10010973`) | Panama candidate has different spelling, incorporation date, intermediary, and address from the Spanish-record entity; unresolved, not merged. |
| Virginia Ventures Limited (`20076539`) | Bahamas 1998 entity with Trident/DEMA records, versus the Spanish-record BVI 1995 vehicle; treated as a false positive. |
| Mr. Stepanov Maxim (`34048`) | No country, DOB, address, or middle identifier; linked only to non-Midland Star Fitness Group; not merged with Maxim A. Stepanov. |
| OLEG BOYKO (`56058520`) | Exact name/Russia record and Allectika shareholder role, but no DOB or other unique identifier; retained as a separately scoped ICIJ record. |

See findings #13747-#13749 for evidence and confidence boundaries.
