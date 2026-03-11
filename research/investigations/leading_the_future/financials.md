# Leading the Future Network — FEC Financial Analysis

**Date**: 2026-02-25
**Data sources**: FEC API (committee totals, Schedule E independent expenditures)
**Coverage**: 2025-07-01 through 2026-02-24 (latest filing dates)
**Analyst note**: Schedule A (itemized receipts) and Schedule B (itemized disbursements) return 0 results from the FEC API for all six committees. This is a significant data gap discussed in Section 6.

---

## 1. Committee Financial Summary

### Active Committees (with financial data)

| Committee | FEC ID | Type | Treasurer | Filed | Receipts | Disbursements | Cash on Hand | IEs (actual) |
|-----------|--------|------|-----------|-------|----------|---------------|-------------|-------------|
| **Leading the Future** | C00916114 | Super PAC | Gonzalez, Britney | Quarterly | $50,310,579 | $11,039,408 | $39,271,172 | $0 |
| **American Mission** | C00916692 | Super PAC | Gonzalez, Britney | Monthly | $5,250,000 | $1,384,861 | $3,865,139 | $1,767,642 |
| **Think Big** | C00923417 | Super PAC | Vlasto, Josh | Quarterly | $5,500,000 | $118,353 | $5,381,648 | $3,865,136 |
| **Race for the Future** | C00909911 | Super PAC | Gonzalez, Britney | Quarterly | $0 | $0 | $0 | $0 |

### New Committees (no financial data yet)

| Committee | FEC ID | Type | Registered | Status |
|-----------|--------|------|-----------|--------|
| **LTF PAC** | C00939157 | Connected PAC | 2026-02-13 | FEC returns 404 (too new) |
| **AM PAC** | C00939140 | Connected PAC | 2026-02-13 | FEC returns 404 (too new) |

### Network Totals

| Metric | Amount |
|--------|--------|
| **Gross receipts (all committees)** | $61,060,579 |
| **Less: internal transfers (LTF to AM/TB)** | ($10,000,000) |
| **Net external fundraising** | **$51,060,579** |
| **Total disbursements** | $12,542,621 |
| **Total IE spending (from Schedule E filings)** | $5,632,778 |
| **Estimated network cash on hand** | ~$48,500,000 |

Note: News reports cite $125M raised in 2025 with $70M cash on hand entering 2026. The FEC data captures $51M in external fundraising. The delta may include Build American AI (501(c)(4), which does not file with FEC) or additional contributions not yet reflected in processed filings.

---

## 2. Donor Analysis

### What the Data Shows

**Schedule A (itemized receipts) returns 0 results from the FEC API for all three major PACs.** This means individual donor data has not been processed into the API's itemized schedules tables. However, the committee totals provide aggregate donor breakdowns:

#### Leading the Future (C00916114)

| Source | Amount | % of Receipts |
|--------|--------|--------------|
| Individual itemized contributions | $50,100,000 | 99.58% |
| Individual unitemized contributions | $0 | 0% |
| Other political committee contributions | $0 | 0% |
| Other receipts | $210,579 | 0.42% |
| **Total** | **$50,310,579** | **100%** |

Key observations:
- **100% of contributions are itemized** ($0 unitemized) — every single donor gave over the $200 itemization threshold
- **$50.1M from individuals** — consistent with news reports of mega-donors (Brockman $12.5M, a16z partners $12.5M+, Lonsdale, Conway, etc.)
- **$210,579 in "other receipts"** — likely interest income or refund proceeds

#### American Mission (C00916692)

| Source | Amount | % of Receipts |
|--------|--------|--------------|
| Individual contributions | $250,000 | 4.76% |
| Other political committee contributions | $5,000,000 | 95.24% |
| **Total** | **$5,250,000** | **100%** |

Key observations:
- **$5M (95%) came from another political committee** — this is the LTF-to-AM transfer
- Only $250,000 from individuals (a single donor, given the itemized-only pattern)

#### Think Big (C00923417)

| Source | Amount | % of Receipts |
|--------|--------|--------------|
| Individual contributions | $500,000 | 9.09% |
| Other political committee contributions | $5,000,000 | 90.91% |
| **Total** | **$5,500,000** | **100%** |

Key observations:
- **$5M (91%) came from another political committee** — this is the LTF-to-TB transfer
- $500,000 from individuals

### Known Donors (from news reporting, not yet confirmed in Schedule A)

| Donor | Reported Amount | Source |
|-------|----------------|--------|
| Greg Brockman (OpenAI co-founder) | $12,500,000 | Axios, CNBC |
| Andreessen Horowitz (a16z) partners | $12,500,000+ | Axios |
| Joe Lonsdale (Palantir co-founder) | Undisclosed | Multiple |
| Ron Conway (SV Angel) | Undisclosed | Multiple |
| Perplexity AI | Undisclosed | Multiple |

These await confirmation when Schedule A data is processed by FEC.

---

## 3. Disbursement Analysis

### Summary (from Committee Totals)

**Schedule B (itemized disbursements) returns 0 results from the FEC API for all three PACs.** This is the most significant data gap in this analysis — LTF has $11M in disbursements that we cannot trace at the line-item level through the API.

However, we can reconstruct the disbursement categories from the totals:

#### Leading the Future — $11,039,408 Disbursed

| Category | Amount | % | Notes |
|----------|--------|---|-------|
| Fed candidate committee contributions | $10,000,000 | 90.6% | Transfers to AM ($5M) and TB ($5M) |
| Operating expenditures | $539,408 | 4.9% | Admin, legal, compliance, etc. |
| Other disbursements | $500,000 | 4.5% | Unknown recipients |
| Independent expenditures | $0 | 0% | LTF itself has made NO independent expenditures |

**Critical finding**: LTF functions as a **fundraising hub**, not a spending entity. It collects money from donors and redistributes to the partisan affiliate Super PACs (AM for Republicans, TB for cross-partisan). The $500K in "other disbursements" is unaccounted for at the itemized level.

#### American Mission — $1,384,861 Disbursed

| Category | Amount | % |
|----------|--------|---|
| Independent expenditures | $1,256,617 | 90.7% |
| Operating expenditures | $128,244 | 9.3% |

#### Think Big — $118,353 Disbursed (through 12/31/2025 only)

| Category | Amount | % |
|----------|--------|---|
| Independent expenditures | $118,350 | 99.997% |
| Operating expenditures | $2.50 | 0.003% |

Note: Think Big's $2.50 in operating expenditures is remarkable — this PAC had essentially zero overhead in 2025. All spending was through IEs. The 2026 IE spending ($3.75M since Jan 1) will appear in the next quarterly filing.

---

## 4. Independent Expenditure Analysis

### American Mission (C00916692) — Republican Primaries

All 6 IE filings use the same vendor: **Summit Ridge Media Group LLC** (Reno, NV).
All expenditures **support** Republican primary candidates.

| Date | Amount | Candidate | Race | Type | Description |
|------|--------|-----------|------|------|-------------|
| 2025-12-12 | $235,000 | Chris Gober | TX-10 (R) | Support | Media placement |
| 2025-12-16 | $8,525 | Chris Gober | TX-10 (R) | Support | Media production |
| 2026-01-20 | $354,025 | Chris Gober | TX-10 (R) | Support | Media placement/production |
| 2026-01-21 | $150,000 | Chris Gober | TX-10 (R) | Support | Digital/SMS |
| 2026-02-11 | $509,067 | Laurie Buckhout | NC-01 (R) | Support | Media production/placement |
| 2026-02-20 | $511,025 | Jessica Hart Steinmann | TX-08 (R) | Support | Media placement/production |

**Subtotals by candidate:**
| Candidate | Total | Race |
|-----------|-------|------|
| Chris Gober (R) | $747,550 | TX-10 primary |
| Jessica Hart Steinmann (R) | $511,025 | TX-08 primary |
| Laurie Buckhout (R) | $509,067 | NC-01 primary |
| **Total** | **$1,767,642** | |

### Think Big (C00923417) — Cross-Partisan (Dem Support + Dem Oppose)

All 20 IE filings use the same vendor: **Lantern Production Consultants LLC** (Sparks, NV).
Spending falls into two categories: **supporting** Dem incumbents and **opposing** a Dem incumbent.

#### Opposing: Alex Bores (D, NY-12) — $1,632,155

| Date | Amount | Description |
|------|--------|-------------|
| 2025-12-10 | $118,350 | Digital media placement/production |
| 2026-01-23 | $326,003 | Cable/digital/print advertising |
| 2026-01-29 | $81,648 | Direct mail production/distribution |
| 2026-01-30 | $124,772 | Digital advertising/production |
| 2026-01-30 | $60,000 | SMS/MMS messaging |
| 2026-02-04 | $231,969 | Cable advertising/production |
| 2026-02-04 | $81,623 | Direct mail production/distribution |
| 2026-02-06 | $113,661 | Digital advertising/production |
| 2026-02-13 | $81,623 | Direct mail production/distribution |
| 2026-02-13 | $72,895 | Direct mail production/distribution |
| 2026-02-13 | $11,111 | Digital advertising |
| 2026-02-13 | $113,611 | Digital advertising/production |
| 2026-02-20 | $98,752 | Cable advertising/production |
| 2026-02-20 | $116,136 | Digital advertising/production |

Alex Bores is the NY State Assemblyman who sponsored SB S7623, a bill to pause certain AI development. He is running for Congress in NY-12 (the seat vacated by Jerry Nadler's retirement). Think Big is spending heavily to oppose him — $1.6M and counting — making this one of the most expensive AI-policy-driven House primary campaigns.

#### Supporting: Illinois Democrats — $2,232,981

| Date | Amount | Candidate | Race | Description |
|------|--------|-----------|------|-------------|
| 2026-02-13 | $555,568 | Melissa Luburich Bean | IL-08 (D) | Digital advertising/production |
| 2026-02-13 | $555,568 | Melissa Luburich Bean | IL-08 (D) | Digital advertising/production |
| 2026-02-17 | $4,510 | Melissa Luburich Bean | IL-08 (D) | SMS/MMS messaging |
| 2026-02-13 | $555,568 | Jesse L. Jackson Jr | IL-02 (D) | Digital advertising/production |
| 2026-02-13 | $555,568 | Jesse L. Jackson Jr | IL-02 (D) | Digital advertising/production |
| 2026-02-17 | $6,199 | Jesse L. Jackson Jr | IL-02 (D) | SMS/MMS messaging |

**Subtotals:**
| Candidate | Total |
|-----------|-------|
| Melissa Luburich Bean (D, IL-08) | $1,115,646 |
| Jesse L. Jackson Jr (D, IL-02) | $1,117,335 |

Note: The duplicate $555,568 amounts on the same date (2026-02-13) for each candidate appear to be distinct line items (different sub_ids and transaction_ids), not duplicate records. This suggests separate media buys or placements on the same day.

### IE Summary by PAC

| PAC | Vendor | Total IEs | Candidates | Party Focus |
|-----|--------|-----------|------------|-------------|
| American Mission | Summit Ridge Media Group | $1,767,642 | 3 (all R, Support) | Republican primaries |
| Think Big | Lantern Production Consultants | $3,865,136 | 3 (all D, Support + Oppose) | Democratic primaries |
| Leading the Future | — | $0 | 0 | None (hub only) |

---

## 5. Cross-PAC Financial Patterns

### Money Flow Architecture

```
Individual Donors ($50.1M)
        |
        v
  LEADING THE FUTURE (C00916114)
  [Hub / Treasury - Henderson, NV]
  Treasurer: Gonzalez, Britney
        |
        +--- $5,000,000 ---> AMERICAN MISSION (C00916692)
        |                    [GOP Affiliate - Henderson, NV]
        |                    Treasurer: Gonzalez, Britney
        |                    + $250K individual donors
        |                         |
        |                         +---> Summit Ridge Media Group LLC
        |                               $1.77M in IEs (Support R candidates)
        |
        +--- $5,000,000 ---> THINK BIG (C00923417)
        |                    [Cross-Partisan Affiliate - Reno, NV]
        |                    Treasurer: Vlasto, Josh
        |                    + $500K individual donors
        |                         |
        |                         +---> Lantern Production Consultants LLC
        |                               $3.87M in IEs (Oppose/Support D candidates)
        |
        +--- $500,000 -----> [Unknown - "Other Disbursements"]
        |
        +--- $539,408 -----> [Operating Expenditures]
        |
        +--- $39.3M -------> [Cash on Hand - unspent]

  RACE FOR THE FUTURE (C00909911) — $0 in/$0 out (dormant placeholder)
  LTF PAC (C00939157) — Registered 2026-02-13 (no data)
  AM PAC (C00939140) — Registered 2026-02-13 (no data)
```

### Hub-and-Spoke Model

Leading the Future operates as a **centralized fundraising vehicle** that:
1. Collects all major donor contributions ($50.1M)
2. Retains the bulk as a war chest ($39.3M, 78% of receipts)
3. Distributes operating funds to partisan affiliates ($10M, 20%)
4. Makes zero independent expenditures itself

This is the identical architecture to Fairshake (crypto Super PAC) — designed by the same operative, Josh Vlasto. The hub (LTF) isolates donors from spending decisions, while the spokes (AM, TB) execute the political advertising.

### Shared Infrastructure

| Element | LTF | AM | TB | RFTF |
|---------|-----|----|----|------|
| Treasurer | Gonzalez | Gonzalez | **Vlasto** | Gonzalez |
| State | NV | NV | NV | NV |
| City | Henderson | Henderson | **Reno** | Henderson |
| Compliance firm | Crosby Ott | Crosby Ott | **Blue Horizon** | Crosby Ott |
| Filing frequency | Quarterly | Monthly | Quarterly | Quarterly |

Think Big stands apart: different treasurer (Vlasto personally), different city (Reno), different compliance (informal gmail account). Vlasto directly controls this entity.

### Exclusive Vendors

Both media vendors are used **exclusively** by this network:

| Vendor | Address | Used By | Total Paid | Other FEC Clients |
|--------|---------|---------|-----------|-------------------|
| Summit Ridge Media Group LLC | 5150 Mae Anne Ave, Suite 405 PMB 1141, Reno NV 89523 | American Mission only | $1,767,642 | **None found** |
| Lantern Production Consultants LLC | 1344 Disc Drive #3038, Sparks NV 89436 | Think Big only | $3,865,136 | **None found** |

Both are Nevada LLCs with mailbox-style addresses. Neither has any other FEC clients. This pattern is consistent with purpose-built entities created specifically for this PAC network's media operations — a common structure in major Super PAC operations that consolidates media buying through controlled intermediaries.

---

## 6. Key Findings

### Finding 1: $11M in LTF Disbursements Without Itemized Schedule B Data

Leading the Future reports $11,039,408 in total disbursements in its year-end summary filing, but the FEC API returns **zero itemized Schedule B records**. This means:
- The $10M in transfers to AM/TB are visible in aggregate totals but not traceable at the line-item level through the API
- The $539K in operating expenditures (consultants? legal? compliance?) cannot be identified
- The $500K in "other disbursements" is completely opaque

**Why this matters**: For a committee this large, the absence of Schedule B data suggests either (a) the FEC has not yet processed the year-end filing's itemized schedules into the API, or (b) the committee is filing summary-only reports. Given that the committee was formed in August 2025 and filed its first year-end report on January 30, 2026, processing delays are the most likely explanation. This data should appear eventually.

### Finding 2: $0 Independent Expenditures from the Main Super PAC

Despite raising $50.3M, Leading the Future has made **zero independent expenditures**. All political ad spending flows through the affiliate PACs. This creates a structural separation between donors and spending — a donor to LTF cannot be directly connected to any specific candidate support/opposition, only to the intermediary transfers.

### Finding 3: Think Big's Massive Anti-Bores Campaign

Think Big has spent $1.63M (and counting) opposing NY State Assemblyman Alex Bores in the NY-12 Democratic primary. Bores sponsored AI regulation legislation (SB S7623). This is the single largest expenditure target in the network and represents a direct retaliation against an AI regulation proponent.

### Finding 4: Cross-Partisan Spending Through Separate Entities

The network simultaneously:
- **Supports Republicans** (via American Mission): Gober TX-10, Steinmann TX-08, Buckhout NC-01
- **Supports Democrats** (via Think Big): Bean IL-08, Jackson IL-02
- **Opposes a Democrat** (via Think Big): Bores NY-12

By splitting partisan spending across separate entities, the network avoids the political awkwardness of a single PAC simultaneously backing both parties. Each entity maintains a consistent partisan narrative while the network as a whole is bipartisan.

### Finding 5: Race for the Future — Dormant Precursor Entity

Race for the Future (C00909911) was registered on July 1, 2025 — six weeks before Leading the Future. It shares the same treasurer (Gonzalez) and state (NV) but has $0 in receipts and $0 in disbursements. The LTF website's favicon still references "Race for the Future." This was clearly the original entity name before the rebrand. It remains registered but dormant — possibly held in reserve.

### Finding 6: LTF PAC and AM PAC — Newly Registered Connected PACs

Two new entities — LTF PAC (C00939157) and AM PAC (C00939140) — were both registered on February 13, 2026. They return HTTP 404 from the FEC API, indicating they are too new to have any processed data. Their registration as "connected PACs" (as opposed to Super PACs) suggests they may be designed for direct candidate contributions (subject to contribution limits) rather than independent expenditures. This would add a new spending channel to the network.

### Finding 7: Schedule A Donor Data Not Yet Available

Despite $50.1M in itemized individual contributions to LTF, the FEC API returns zero Schedule A records. This prevents independent verification of the reported mega-donors (Brockman, a16z, Lonsdale, Conway, Perplexity). The data should become available as the FEC processes the year-end filing.

### Finding 8: Think Big's $2.50 Operating Budget

Think Big reported only $2.50 in operating expenditures through year-end 2025, while spending $118,350 in IEs. This suggests Think Big has essentially no independent operational infrastructure — Vlasto runs it personally with compliance handled through an informal gmail address (bluehorizoncompliance@gmail.com). The real operational costs are either absorbed by Vlasto/Bamberger & Vlasto or billed through the media vendor.

### Finding 9: Network Cash Position — $48.5M War Chest

The network holds approximately $48.5M in combined cash on hand (primarily $39.3M at LTF). With only $5.6M spent on IEs to date and the 2026 midterm cycle just beginning, this represents a substantial deployment capacity. For context, Fairshake (the crypto equivalent) spent $40M+ in the 2024 cycle.

---

## Appendix: Data Quality Notes

| Query | Committee | Result | Notes |
|-------|-----------|--------|-------|
| Totals | C00916114 (LTF) | 1 result | Complete through 12/31/2025 |
| Totals | C00916692 (AM) | 1 result | Complete through 02/11/2026 |
| Totals | C00923417 (TB) | 1 result | Complete through 12/31/2025 |
| Totals | C00939157 (LTF PAC) | 0 results | No financial data (new) |
| Totals | C00939140 (AM PAC) | 0 results | No financial data (new) |
| Totals | C00909911 (RFTF) | 1 result | $0 across all categories |
| Schedule A (donors) | All 3 major PACs | 0 results | Not yet processed by FEC |
| Schedule B (disbursements) | All 3 major PACs | 0 results | Not yet processed by FEC |
| Schedule E (IEs) | C00916114 (LTF) | 0 results | Correct — LTF has made no IEs |
| Schedule E (IEs) | C00916692 (AM) | 6 results | Complete through 02/20/2026 |
| Schedule E (IEs) | C00923417 (TB) | 20 results | Complete through 02/20/2026 |
| Committee details | All 6 | HTTP 404 | FEC API endpoint issue |

---

*Analysis based on FEC data retrieved 2026-02-25. All dollar amounts from official FEC filings. News-sourced claims labeled as such.*
