# The Oversight Project — Wave 1 Synthesis (2026-07-21)

**Method:** 7 Codex `gpt-5.6-sol` @ xhigh agents dispatched per-skill, read-only on
the DB, emitting structured findings/entities/leads reviewed and committed by the
orchestrator. **Committed:** 81 findings (#13959, #13960–#14039), 91 entities, 135
leads (77 open + 58 auto-generated pending triage). All claim-typed and confidence-
capped; primary sources prioritized.

## Established facts (primary-sourced)

### Corporate structure & Heritage spin-out
- The Oversight Project was chartered in **Wyoming as a nonprofit corporation on
  2025-02-21** (filing 2025-001619271; office 211 N Union St, Alexandria VA 22314) —
  from the WY SOS quarterly Domestic Entity Charters PDF (primary; the per-entity
  WyoBiz lookup is CAPTCHA-gated). Heritage publicly announced the split on
  **2025-03-31** ("become its own entity … set up as a 501(c)(4)"), i.e. **38 days
  after** the WY charter.
- Heritage's FY2023/FY2024 990s treated the Oversight Project as an internal
  **program service** (2,100 FOIA requests in 2023 → 65,000 in 2024); it was **not**
  a Heritage Schedule I grantee or Schedule R related org.
- Howell's 2025-04-08 Senate testimony and a 2025 D.D.C. complaint both describe the
  entity as a **Wyoming-based 501(c)(4)** with a Virginia office. Litigation captions
  shifted from *Heritage Foundation v. …* (through 2024) to *Oversight Project v. …*
  (from Sept 2025).
- **No own EIN / 990 located** in the IRS EO BMF (posted 2026-07-14) or ProPublica —
  consistent with a new (c)(4) that files Form 8976 and may have no public return yet.
- **211 N Union St is a generic multi-tenant commercial building** (9+ unrelated
  exempt orgs; owner CIA-211 N Union Street LLC) — low-specificity, unlike CPI's campus.

### Governing persons (beneficial owners, user-supplied roster, now profiled)
- **Mike Howell** — President; former **DHS Oversight Counsel** (Office of General
  Counsel), Heritage, Senate HSGAC + House Oversight staff; Project 2025 contributor.
- **Kyle Brosnan** — General Counsel; ex-Heritage Oversight chief counsel; Senate PSI
  counsel (Ron Johnson); HHS/DHS in first Trump admin; attorney of record in 8+
  Heritage/Howell D.D.C. FOIA suits (2023–2025).
- **Thomas R. Olohan** — VP of Investigations; retired **FBI special agent** (Washington
  Field Office; signed a Jan 2021 J6-case statement of facts).
- **Adrienne Price** — COO/CDO; ex-Heritage Senior Advisor; **former Chief Development
  Officer at America First Legal** (which CPI granted $1.33M in 2021).
- **Nicholas Stoltzfus** — ex-Heritage Controller; **treasurer of the Sentinel Action
  Fund Super PAC ($16.47M receipts)** and Defend Developers PAC; associated with
  **Compass Professional**.

### CPI ecosystem at 300 Independence Ave SE (the structural hub)
- CPI's 2024 Schedule R reports **13 controlled Delaware real-estate holding LLCs** at
  the address (~$54M year-end assets).
- A captive **"Compass" services suite** at the address: Compass Professional (admin,
  $986K), Compass Legal Group (legal, $609K), Compass Property Management ($360K),
  Compass Direct (direct-marketing, $2.57M gross), plus **$2.04M "Workspace Share
  Revenue."** PPO and Election Integrity Action name Compass Professional as their
  books-and-records custodian.
- CPI granted **92.66% of its $8.45M (2024) to seven same-address orgs**: FAIR
  Elections Fund ($6.04M), Personnel Policy Operations ($1.075M), Edmund Burke
  Foundation, State Leadership Foundation, Conservative Partnership International,
  American Moment, and **American Accountability Foundation ($25K)**.
- AAF controls **AAF Action Inc** (DE 501(c)(4)) at the address; AAF officers = Thomas
  Jones (pres.), Brian Darling, Tripp Baird. Matthew Buckham sits on **PPO**, not AAF's
  latest board.

### The Klimon nexus (narrower than the original premise)
- Klimon (700+ nonprofits; 20+ yrs Caplin & Drysdale exempt-orgs) **co-founded Compass
  Legal Group in 2021 — CPI's in-house legal arm at 300 Independence Ave** — then joined
  **Holtzman Vogel on 2025-04-01**. He is the IRS care-of contact for newer nonprofits
  at the address (e.g., Art & Literature Foundation).
- **He is not named in the Oversight Project's or the cluster orgs' 990s** (all Delaware-
  domiciled). The specific claim "Klimon incorporated the Oversight Project" is
  **plausible but unproven** — blocked by the WyoBiz/Virginia SCC CAPTCHAs.

### Funding
- **DonorsTrust → Heritage $50,000 (FY2022), earmarked "for the Heritage Oversight
  Project"** (primary Schedule I; confirmed). Bradley Foundation → CPI $450K (2020–23).
  Donors Capital Fund → DonorsTrust $5.3M.

### Digital infrastructure
- **itsyourgov.org** is the Oversight domain, registered **2025-01-23** (before the WY
  charter), Cloudflare cert issued **2025-02-21** (charter day) — pre-announcement staging.
- **Oversight does NOT share web infrastructure with CPI/AAF/CUFI.** Oversight =
  Cloudflare + Sanity CMS, "Digital Cardinal" developer. AAF + CPI share WP Engine
  hosting (141.193.213.20/.21) and a "39Bravo" bootScore build — a link between *those
  two*, not to Oversight. CUFI Action Fund (cufiactionfund.org / cufiaf.org, San Antonio,
  formed 2013) is a separate WP Engine tenant.

## The load-bearing insight
The Oversight Project is bound to the CPI network **organizationally, not digitally**:
both its likely formation counsel (**Klimon / Compass Legal**) and beneficial owner
**Stoltzfus (Compass Professional)** run through CPI's captive **"Compass" shared-services
suite** at 300 Independence Ave SE — plus the personnel pipeline (Heritage/AFL/DHS/FBI →
Oversight) and the DonorsTrust project-designated grant.

## Blockers → Wave 2 priorities
1. **Break the CAPTCHA wall on WY/VA primary records.** `tools/query_wyoming.py warmup`
   solves the WyoBiz F5 CAPTCHA in a browser (human, once) and caches cookies — then pull
   the full WY record (incorporator = Klimon?, registered agent). Virginia SCC (CIS) is
   similarly gated. A valid OpenCorporates token would also help (rejected in-sandbox).
2. **Confirm Compass Professional (Stoltzfus) = CPI's Compass Professional Inc.** — the
   single most load-bearing person-link (needs a corporate-registry / EIN confirmation).
3. **The Oversight Project's Form 1024-A / EIN** once public.
4. **FOIA-litigation catalog** (analyze-case) now that the entity names are pinned.
5. **CUFI Action Fund** governance/Klimon test (thread 6; cross-link the `hagee` profile).

## Method note — CAPTCHA discipline
Every Wave 1 agent prompt carried an explicit "no CAPTCHA solving; passive lookups only"
rule; agents respected it (op-entity stopped at the WyoBiz/VA SCC challenges rather than
bypassing). This aligns with `research/INVESTIGATIVE_METHODOLOGY.md` ("if it has CAPTCHAs,
create a human_action item") and the platform's human-in-the-loop registry tooling
(`query_wyoming.py warmup`, `ingest_maryland` manual CAPTCHA).
