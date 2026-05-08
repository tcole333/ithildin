# Runa Capital
**Stats**: 9 findings, 5 connections, 0 entities
**Dossier**: /dossiers/runa-capital

## Key Findings
- **[relationship/confirmed]** 11 corporate entities across 7 jurisdictions identified via OpenCorporates (Finding #9793)
- **[relationship/confirmed]** Shared registered agent (INCORP SERVICES INC) between Runa Capital Inc Delaware and NGINX Software Inc Delaware (Finding #9807)
- **[relationship/confirmed]** LittleSis: DFJ Fund VIII Partners LP ownership stake in Runa Capital confirmed (Finding #9812)
- **[relationship/confirmed]** LittleSis: Masha Bucher (Drokova) links Runa Capital to Alexander Mamut (CAATSA-listed Russian billionaire) via Day One Ventures (Finding #9816)
- **[financial/confirmed]** Runa Capital is a Cayman Islands entity (Paradise Papers) with shareholders Chikhachev, Beloussov, Galitsky, Zubarev, Shokina as CFO (Finding #9870)
- **[negative_result/medium]** No direct board interlock found between Runa Capital entities and NGINX Inc via OpenCorporates; Beloussov absent from Runa corporate filings (Finding #9806)
- **[negative_result/medium]** No direct code-level connection found between Beloussov/Runa Capital network and nginx contributors. No @runa domain emails in git history. The Runa-NGINX connection remains at corporate/investment level (shared registered agent INCORP SERVICES INC) not developer level. Martin Duke (F5/Moscow) and Nikolay Morozov (securitycode.ru/TLS contributor) are not linked to Beloussov entities. (Finding #9852)
- **[relationship/medium]** Runa Capital is the dominant hub-broker in the nginx investigation graph: degree=7 (rank 1 of 29 nodes), betweenness centrality=0.687 (rank 1), brokerage score=1.0 (all 7 neighbors are disconnected from each other). It sits between NGINX Software Inc, Serguei Beloussov, Dmitry Chikhachev, DFJ Fund VIII Partners LP, Masha Bucher, DFJ Fund VIII LP, and Runa Capital Inc — controlling all information flow between these actors. (Finding #9969)

## Top Connections
- **NGINX Software, Inc.** [funds/strong]: Runa Capital led Series A investment in NGINX Inc (~2013). Shared registered agent (INCORP SERVICES INC) in Delaware. No direct board interlock found via OpenCorporates.
- **Serguei Beloussov** [corporate/strong]: Founding partner of Runa Capital, confirmed via LittleSis and OpenCorporates. No positions at any NGINX entity despite 17 officer positions globally at SWSoft/Parallels/Acronis entities.
- **Dmitry Chikhachev** [corporate/strong]: Managing Partner of Runa Capital, confirmed via OpenCorporates occupation field. Russian nationality, Luxembourg-based. Director of 3 Runa portfolio companies. No positions at any NGINX entity.
- **DFJ Fund VIII Partners LP** [owns/strong]: DFJ Fund VIII Partners LP (Tim Draper) confirmed as owner of Runa Capital via LittleSis.
- **Masha Bucher** [employment/strong]: PR Director, June 2011 - July 2013. Overlaps with Runa Capital nginx Series A (Aug 2011)
