# Leading the Future Super PAC Network — Synthesis

**Date**: 2026-02-25
**Analysis phase**: Phase 4 of investigation plan
**Source reports**: `shell-vendors.md`, `financials.md`, `network-mapping.md`, `recon.md`

---

## 1. Financial Flow Map

```
                    AI INDUSTRY DONORS
            ┌───────────────────────────────┐
            │  Greg Brockman (OpenAI) $12.5M │
            │  Andreessen Horowitz   $12.5M+ │
            │  Joe Lonsdale (Palantir)  ???  │
            │  Ron Conway (SV Angel)    ???  │
            │  Perplexity AI            ???  │
            │  [Others — $12.6M+]           │
            └──────────────┬────────────────┘
                           │
                     $50.1M (100% itemized,
                      all over $200 threshold)
                           │
                           ▼
               ┌───────────────────────┐
               │  LEADING THE FUTURE   │
               │  C00916114 (Super PAC)│
               │  Henderson NV (mailbox)│
               │  Treasurer: Gonzalez  │
               │                       │
               │  Receipts:  $50.3M    │
               │  Disbursed: $11.0M    │
               │  Cash:      $39.3M    │
               │  IEs:       $0        │
               └───────┬───────────────┘
                       │
            ┌──────────┼──────────┐
            │          │          │
         $5.0M     $539K       $500K
            │      (operating)  (unknown
            │                  "other")
            ▼
   ┌────────────────┐     ┌────────────────┐
   │AMERICAN MISSION│     │   THINK BIG    │
   │C00916692 (R)   │     │C00923417 (D/X) │
   │Henderson NV    │     │Reno NV         │
   │Treas: Gonzalez │     │Treas: VLASTO   │
   │                │     │                │
   │ +$250K indiv.  │     │ +$500K indiv.  │
   │ =$5.25M total  │     │ =$5.50M total  │
   └───────┬────────┘     └───────┬────────┘
           │                      │
           ▼                      ▼
  ┌─────────────────┐   ┌──────────────────────┐
  │SUMMIT RIDGE     │   │LANTERN PRODUCTION    │
  │MEDIA GROUP LLC  │   │CONSULTANTS LLC       │
  │Reno NV (mailbox)│   │Sparks NV (mailbox)   │
  │$1.77M in IEs    │   │$3.87M in IEs         │
  │                 │   │                      │
  │NO other clients │   │NO other clients      │
  │NO web presence  │   │NO web presence       │
  │NO registry hits │   │NO registry hits      │
  └───────┬─────────┘   └───────┬──────────────┘
          │                     │
          ▼                     ▼
   R PRIMARY RACES        D PRIMARY RACES
   ┌─────────────┐     ┌──────────────────┐
   │Gober  $748K │     │OPPOSE Bores $1.6M│
   │TX-10 (Supp) │     │NY-12 (AI reg.)   │
   │             │     │                  │
   │Steinmann    │     │Support Bean $1.1M│
   │$511K TX-08  │     │IL-08             │
   │             │     │                  │
   │Buckhout     │     │Support Jackson   │
   │$509K NC-01  │     │$1.1M IL-02       │
   └─────────────┘     └──────────────────┘

DORMANT:
  Race for the Future (C00909911) — $0/$0/$0 (original entity name, placeholder)
  LTF PAC (C00939157) — registered 2026-02-13, no data yet
  AM PAC (C00939140) — registered 2026-02-13, no data yet

DARK MONEY ARM:
  Build American AI (501c4) — undisclosed donors, 500K "activists"
  No 990 filing available, no lobbying registration
  Same web infrastructure as LTF (Webflow, Cloudflare, Google Workspace)
```

---

## 2. Shell Vendor Assessment

**Both Summit Ridge Media Group LLC and Lantern Production Consultants LLC are purpose-built firewall entities** created specifically for this PAC network's media operations.

Both are **Delaware LLCs formed on the same day (October 30, 2025)** with the same registered agent (CT Corporation), with company numbers only **10 apart** (#10385832 and #10385842). They were created in a single batch filing — almost certainly by the same law firm in the same session, 41 days before the first FEC payment.

- **Summit Ridge Media Group LLC** — DE Company #10385832, CT Corp agent. Reno NV mailbox on FEC filings. Not registered in Nevada.
- **Lantern Production Consultants LLC** — DE Company #10385842, CT Corp agent. Sparks NV mailbox on FEC filings. Not registered in Nevada.

Delaware chosen specifically because it does not require public disclosure of LLC members/managers — the principals are invisible through state records.

Neither entity has:
- Any other FEC clients
- Any web presence under their exact names
- Any physical office (both use Nevada commercial mailbox services)
- Any publicly identifiable principals (DE LLCs shield member/manager identity)

The vendor pair creates a **compartmentalization firewall**: the actual media buying operation (likely executed by Targeted Victory or its subcontractors) is insulated from FEC disclosure behind these intermediaries. Each partisan arm uses a different vendor, preventing cross-referencing.

This is the same pattern used by Fairshake, which used "Main Street Media Group" — another purpose-named LLC. The naming convention ("geographic feature + Media + Group") appears standardized.

**NV SOS confirmed both are NOT Nevada entities** despite Nevada mailing addresses. Lantern is a Delaware LLC formed Oct 30, 2025 with CT Corporation as agent — Delaware's privacy protections ensure the principals remain invisible in state records. The only paths to identifying who controls these entities: (a) FOIA the FEC for vendor registration documents, (b) trace payments downstream to actual media vendors, (c) check FEC Form 3X/3L attachments.

---

## 3. Network Topology

```
             DEMOCRATIC SIDE                    REPUBLICAN SIDE
            ┌──────────────┐                  ┌──────────────┐
            │ Josh Vlasto  │                  │ Zac Moffatt  │
            │ (BV Strategies)                 │ (Targeted Victory)
            │ Cuomo → JPM →│                  │ Romney 2012 → │
            │ Perelman →   │                  │ TV CEO →      │
            │ Kivvit → BV  │                  │ LTF co-leader │
            │              │                  │               │
            │ All personal │                  │ All personal  │
            │ donations: D │                  │ donations: R  │
            └──────┬───────┘                  └───────┬───────┘
                   │                                  │
                   │    ┌──────────────────┐          │
                   └────┤LEADING THE FUTURE├──────────┘
                        │  (co-leaders)    │
                        └────────┬─────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                  │
          Think Big        Build American AI   American Mission
          (Vlasto treas.)  (Leamer, Exec Dir)  (Gonzalez treas.)
               │           501(c)(4)                │
               │                                    │
         Lantern Prod.                        Summit Ridge
         Consultants                          Media Group
```

### Key People Network

**Josh Vlasto** — The architect. Designed identical structure for Fairshake (crypto, $191M) and LTF (AI, $50M+). ~$300M+ in tech industry political spending under one strategic architect. Personally serves as Think Big treasurer using an informal Gmail address.

**Zac Moffatt** — CEO of Targeted Victory, which is owned by **Mark Penn's Stagwell Inc.** This means the same corporate parent has deep Democratic connections (Penn: Clinton 2008 strategist) and runs the GOP digital firm behind LTF. Targeted Victory is also a **FARA-registered foreign agent for Saudi Arabia** (since April 2016).

**Nathan Leamer** — Executive Director of Build American AI. Ghost in public records: no LittleSis profile, no lobbying registrations, only $1,743 in FEC donations (all Republican: Trump, NATE Tower PAC). His firm "Fixed Gear Strategies" has no public footprint. Perfect profile for running a 501(c)(4) that wants to stay invisible.

**Britney Gonzalez** — Treasurer for 14 FEC committees at Crosby Ottenhoff Group (Mountain Brook, AL). Professional compliance officer, not a political operative. Crosby Ott is a major GOP compliance firm (clients include American Crossroads, Senate Leadership Fund).

---

## 4. Fairshake Playbook Comparison

| Element | Fairshake (Crypto, 2024) | Leading the Future (AI, 2025-26) |
|---------|-------------------------|----------------------------------|
| **Main Super PAC** | Fairshake ($191M CoH) | Leading the Future ($50.3M) |
| **Dem affiliate** | Protect Progress | Think Big |
| **GOP affiliate** | Defend American Jobs | American Mission |
| **501(c)(4)** | Cedar Innovation Foundation | Build American AI |
| **Architect** | Vlasto (spokesman) | Vlasto (co-leader) |
| **GOP firm** | — | Targeted Victory (Moffatt) |
| **Compliance** | — | Crosby Ottenhoff (Gonzalez) |
| **Media vendor** | Main Street Media Group | Summit Ridge / Lantern |
| **Bridge donor** | a16z ($67M+) | a16z ($12.5M+) |
| **Cedar/BAI 990** | $0 revenue/$0 assets | Not yet filed |
| **Strategy** | **Defensive** (anti-regulation) | **Offensive** (pro-AI before regulation) |

The structural mirror is exact. The key evolution: Fairshake was defensive (targeting Elizabeth Warren-aligned crypto critics). LTF is offensive (building political infrastructure for AI before major regulatory battles begin).

The 501(c)(4) dark money arms (Cedar Innovation Foundation and Build American AI) both report zero public financial data. For Cedar, this is suspicious given Fairshake's $191M scale. For BAI, it's too early to tell.

---

## 5. Open Questions

### Highest Priority

1. **~~NV SOS records~~** — RESOLVED. Neither entity registered in Nevada. Both are Delaware LLCs formed Oct 30, 2025 with CT Corp (#10385832 and #10385842 — 10 numbers apart, same batch filing). DE LLCs do not disclose members/managers — principals invisible through state records. New lead: companies #10385833-10385841 filed in same batch may reveal other operation entities or the filing attorney.

2. **Where is the $39.3M war chest going?** — LTF has only deployed $10M to affiliates with $39.3M in reserve. The 2026 midterm cycle is just beginning. At Fairshake's 2024 spending rate ($40M+), this is a massive weapon.

3. **Who are the remaining donors?** — Schedule A data is not yet processed. Only $37.5M of the $50.1M in individual contributions has been attributed to named donors via news reports. The remaining ~$12.6M is unidentified.

4. **What are the $500K in "other disbursements"?** — LTF's totals show $500K in unitemized "other disbursements" with no Schedule B detail. This could be consulting fees, legal costs, or transfers to entities not captured in IE filings.

### Medium Priority

5. **LTF PAC and AM PAC (registered Feb 13, 2026)** — What are these new connected PACs for? Connected PACs can make direct candidate contributions (subject to limits), adding a new channel. Monitor first filings.

6. **Build American AI's actual funding** — The 501(c)(4) claims 500K "activists" but has no public financial data. Who is paying for the grassroots organizing? Is BAI funded by LTF, by its own donors, or by another entity?

7. **Saudi Arabia connection** — Targeted Victory's FARA registration for the Saudi Embassy. While this doesn't imply Saudi involvement in LTF, it reveals the firm's comfort with foreign influence operations. Are any LTF donors connected to Saudi interests?

8. **Fairshake's Main Street Media Group** — Is this the same pattern? Search FEC for this vendor's clients, address, and registry presence. If it mirrors Summit Ridge/Lantern, it confirms a systematic approach.

---

## 6. Key Analytical Judgments

### 6.1 This is a Professionalized Influence Machine

The LTF network is not an ad-hoc political operation. It is a **deliberately designed influence architecture** deployed by the AI industry, using the same template that the crypto industry used to spend $191M in 2024. The architect (Vlasto) improved on the Fairshake model by:
- Adding a dedicated GOP firm (Targeted Victory/Moffatt) as co-leader
- Creating vendor firewalls for both partisan arms
- Launching a 501(c)(4) grassroots arm from the start (BAI)
- Establishing connected PACs (LTF PAC, AM PAC) for direct contributions

### 6.2 The Bipartisan Architecture is Weaponized Ambiguity

Vlasto (D) and Moffatt (R) genuinely support opposite parties — their personal FEC donations confirm this. But the "bipartisan" label serves a strategic purpose: it makes the operation politically palatable to both parties while allowing it to target primaries on both sides. The real goal is not partisan — it's **pro-AI incumbents and candidates regardless of party, anti-regulation candidates regardless of party**.

### 6.3 The Shell Vendors Create Accountability Gaps

By routing $5.6M through two invisible LLCs, the network ensures that:
- The actual media buying firm(s) cannot be identified from public filings
- Competing campaigns cannot monitor ad spending strategy
- Journalists cannot trace the money to its ultimate destination
- The FEC filing technically complies with disclosure rules while revealing nothing useful

### 6.4 The 501(c)(4) is the Hidden Engine

Build American AI is potentially the most important entity in the network — and the least visible. As a 501(c)(4):
- Its donors are never disclosed
- Its spending is not reported to the FEC
- Its IRS filings are delayed by 1-2 years
- Its "grassroots" organizing (500K "activists") creates a voter contact operation that Super PACs cannot legally coordinate with — but structurally, the same people (Vlasto, Moffatt) designed both

### 6.5 $48.5M War Chest Signals Long-Term Campaign

The network has spent only $5.6M of its $48.5M war chest, and the 2026 midterm cycle is just beginning. If the AI industry follows the crypto playbook, expect:
- $30-40M in IE spending in the final 6 months before November 2026
- Expansion to Senate races (currently only House primaries)
- Possible deployment of the new connected PACs for direct candidate contributions
- Escalation of anti-regulation candidate targeting (Bores is the warning shot)

---

*Analysis generated 2026-02-25. Pending data: NV SOS shell vendor registrations, FEC Schedule A/B itemized data, Build American AI 990 filing.*
