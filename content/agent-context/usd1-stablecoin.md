# USD1 Stablecoin
**Stats**: 5 findings, 2 connections, 0 entities
**Dossier**: /dossiers/usd1-stablecoin

> USD1 is a case study in the intersection of cryptocurrency issuance, presidential financial interests, and foreign sovereign capital flows. Analysis involves tracking the reserve structure, profit-sharing arrangements, regulatory framework (particularly the GENIUS Act), Binance supply concentration, and the network of UAE-linked entities — including MGX, Aryam Investment 1, and G42 — that connect the stablecoin to both sovereign wealth capital and US technology export policy.

## Key Findings
- **[financial/high]** USD1 stablecoin launched March 2025 by World Liberty Financial. As of Feb 2026: $5.37B market cap, with Binance holding ~87% ($4.7B) of total supply. Reserves backed by short-term US Treasuries, USD deposits, cash equivalents. Custodian: BitGo Trust Company (South Dakota). Monthly third-party attestations. Key event: Abu Dhabi-backed MGX used $2B worth of USD1 to settle investment in Binance (May 2025), which placed massive supply on Binance. Deployed on Ethereum, BNB Chain, Solana, Tron. USD1 brand co-owned by SC Financial Technologies LLC (Zach Witkoff CEO). (Finding #4167)
- **[financial/high]** USD1 is 100% backed by short-term US government Treasuries (<=93 day maturity), US dollar deposits, and other cash equivalents. Reserves are held by BitGo Trust Company (South Dakota-chartered trust company) with Fidelity Investments managing the investment portfolio. Monthly attestation reports are published by an independent accounting firm per 2025 AICPA Criteria for Asset-Backed Fiat-Pegged Tokens, though reporting gaps have occurred (e.g., July 2025 was the most recent report as of October 2025). (Finding #4188)
- **[financial/medium]** The first major use of USD1 was settling MGX's $2B investment in Binance (announced May 2025). The timing is significant: the UAE-based MGX (led by Sheikh Tahnoon bin Zayed Al Nahyan) purchased $2B in USD1 tokens weeks before the Trump administration signed a framework granting the UAE access to hundreds of thousands of advanced AI chips. Separately, Tahnoon-backed entity Aryam Investment 1 had secretly acquired a 49% stake in World Liberty Financial for $500M four days before inauguration, with $187M flowing to Trump family entities. (Finding #4197)
- **[financial/high]** USD1 currently operates under BitGo's regulatory umbrella: BitGo Trust Company Inc. (SD-chartered trust company) holds reserves, while BitGo Technologies LLC is a federally registered money services business and state-licensed money transmitter. USD1 is deployed on both Ethereum and Binance Smart Chain (BNB Chain), with BNB running zero-fee stablecoin transfers for USD1. The stablecoin reached $1B market cap within its first month (April 2025), $3B by December 2025, and approximately $5.37B by February 2026, with ~87% ($4.7B) held on Binance. It also integrates with Tron blockchain. (Finding #4201)
- **[intelligence/high]** On Feb 23, 2026, USD1 experienced a coordinated attack: hackers compromised co-founder accounts, paid influencers to spread FUD, and opened short positions on WLFI to trigger panic. USD1 briefly depegged to $0.994 (0.6% below peg) before recovering within ~30 minutes. No smart contracts or treasury reserves were compromised. WLFI credited the 1:1 dollar redemption feature for maintaining confidence. The attack may test the structural resilience of a politically-connected stablecoin and its dependence on centralized trust rather than market mechanisms. (Finding #4206)

## Top Connections
- **Binance** [financial/strong]: Binance holds ~87% of all USD1 supply ($4.7B of $5.4B). MGX used $2B USD1 to settle investment in Binance (May 2025), placing massive supply on platform. Binance launched 20% yield promotion for USD1, driving market cap surge. This concentration creates systemic risk and mutual dependency between Trump family stablecoin and world's largest crypto exchange.
- **BitGo Holdings** [financial/strong]: BitGo is the custodian and infrastructure provider for USD1. BitGo Trust Company (SD trust charter, now converting to national bank) holds reserves. BitGo Technologies LLC is the licensed money transmitter. BitGo's Stablecoin-as-a-Service uses USD1 as its blueprint.

## Open Questions
- Was the second $250M Aryam Investment 1 tranche (due July 15, 2025) paid in full? Representative Ro Khanna demanded documentation by March 1, 2026; no public disclosure has confirmed payment or default.
- Who are the non-US buyers of the approximately 90% of WLFI tokens sold under Regulation S? Their identities are not disclosed under US law, and no foreign disclosure requirement has surfaced.
- Has a CFIUS review of the Aryam Investment 1 stake in WLFI been initiated or completed? No formal review was on record as of February 26, 2026.
- Which independent accounting firm publishes USD1's monthly attestation reports, and what accounts for the gap between the July 2025 attestation and the October 2025 NYDIG observation? [Finding #4188]
- If the World Liberty Trust Company N.A. charter is approved by OCC, would BitGo's custody role be replaced, and what transition period would apply to the $5.37B in existing reserves?

## Applicable Models
- jurisdictional-arbitrage
- manufactured-dependency
