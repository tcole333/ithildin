# Coscoluella / Reodica Investigation — Agent Context Addendum

Case-specific context for agents working the `coscoluella` profile. Supplements the generic platform instructions in the root `CLAUDE.md`.

## CRITICAL: Verification Posture

**Every foundational fact in this investigation is USER-PROVIDED and unverified.** The originating account (paraphrased):

- Rebecca Coscoluella is the sister of **Gie Reodica Marinese**, a bookkeeper who reportedly worked for **Jeffrey Epstein in the 1990s** before dying in the early 2000s.
- Rebecca was married to **Ed (Edward) Coscoluella** and lived in California.
- Ed was a close friend of **Jun Reodica**, who ran a large 1980s Los Angeles fraud via **"Grand Wilshire"**, then fled to the **Philippines** and **Australia**, and was reportedly caught re-entering the US around **2013**.
- Ed reportedly served as a **trustee** or assisted in the related **bankruptcy** proceedings.
- Ed and Rebecca later ran a **consulting company in Las Vegas** and may still be there.

Treat each as a lead to confirm or refute against primary sources. Label findings `inference`/`paraphrase` until a primary record corroborates. Do **not** mark anything `confirmed` on the strength of this brief alone.

### Wave 1 verification status (2026-05-31)

A 6-agent wave ran the originating account against primary sources. Status:

**CONFIRMED (primary documents):**
- **Gie Reodica Marinese WAS J. Epstein & Co Inc's bookkeeper.** 1999 FedEx airbills in the DOJ/LMSBAND corpus name her as the firm's shipping-account sender at 457 Madison Ave, NYC: **EFTA00220010, EFTA00220054, EFTA01319595, EFTA01319611** (FedEx acct 1144.2081.6). Obituary corroborates ("bookkeeper for J. Epstein Co., NYC, the past seven years").
- **Rebecca is Gie's sister.** Obituary + Ancestry tree. Rebecca R. Coscolluela: b.1945 Luisiana Laguna, d.2020 Chatsworth CA. Third sister: Marion R. Lorico (Chino Hills).
- **Epstein office → Rebecca direct tie:** airbill **EFTA00220010** ships from J. Epstein & Co to recipient "BECKY COCOLLUELA" (= Rebecca). Other recipients place Gie's shipping in Epstein's Palm Beach orbit ("Mike Alton / Smith Bro", West Palm Beach; co-listed with John Alessi).
- **"Jun Reodica" = Eminiano A. Reodica Jr.**, principal of the **Grand Wilshire Group of Companies (GWG)** auto-finance bank fraud (Glendora CA, 1984-88, ~$64-90M loss, 5 banks). Case **2:94-cr-00121-SJO** (C.D. Cal), CourtListener docket **5859431** (PACER 276473). Fled 1988 → Australia as "Roberto Coscolluela" → arrested LAX 27 Nov 2012 → 10 yrs (2017) → died in custody 17 Mar 2021.
- **Ed Coscolluela appears in the criminal record** (sentencing memo doc 173) as a "long-time friend" and CPA on Reodica's dealership management team (from Terry York Chevrolet, 1970s).

**CORRECTED (originating account was wrong):**
- **Ed was NOT the bankruptcy trustee** — the Chapter 11 trustee was **Irving Sulmeyer** (Sulmeyer Kupetz). Ed's documented role is CPA/management-team associate, not a fiduciary in the bankruptcy.
- **Jun Reodica is NOT a blood sibling of Gie/Rebecca.** His parents (Eminiano Rivera Reodica Sr. + Lolita Abrian Aquino) differ from Gie/Rebecca's (Gregorio P. Reodica + Nieves/Onisima Estrellado). The shared "Coscolluela" surname is explained by Jun's **alias** ("Roberto Abrian Coscolluela Jr.", 1988), his **2nd wife Leticia Coscolluela**, and his **CPA associate Ed Coscolluela** — NOT by kinship to the Reodica line. (Whether the two Reodica lines are distant cousins is unestablished.)
- **Capture was Nov 2012, not 2013.** Amended restitution was **2019**, not 2017.

**STILL OPEN (highest priority):**
- **THE KEYSTONE:** Is the doc-173 CPA "Ed Coscolluela" (an older man, active 1970s) the same Ed who married Rebecca (Eduardo Sr., father of Eduardo II b.1970 d.2024)? If yes, **Ed is the single human bridge** linking the Grand Wilshire fraud to the Epstein-bookkeeper household. Not yet confirmed.
- **Ed's full identity & current status** (alive? Las Vegas?) — unconfirmed.
- **The Las Vegas consulting company** — NOT FOUND (NV SOS registry was unreachable; see tooling gaps). Note: Jun's sister **Remedios Reodica Lasangria lives in Las Vegas** — possible source of the user's "Vegas" recollection.
- **Exact CA SOS entity numbers** for the GWG companies — CA registry was unreachable.

### Tooling gaps surfaced (block follow-up)
DugganUSA search API 401/403 (auth wall, infra req #123); Nevada SOS dead (`tools/_nv_browser_helper.js` missing); CA SOS unsearchable (no `CA_SOS_API_KEY`, bizfile Imperva 403); OpenCorporates token invalid; genealogy sites (Legacy/FindAGrave/familytreenow) Cloudflare-gated. Fixing the NV + CA registries is the gate to closing the Vegas-company and CA-entity questions.

## Central Structural Hypothesis (REVISED after Wave 1)

The original hypothesis — *"the **Reodica** surname is the connective tissue"* — is **partly refuted**. The Reodica name does NOT bridge the two halves: Jun Reodica is not kin to Gie/Rebecca (different parents). What actually recurs across both halves is the **Coscolluela** surname, and the live hypothesis is now that **Ed Coscolluela is the human hinge**:

- **Epstein half (CONFIRMED):** Gie Reodica Marinese = J. Epstein & Co bookkeeper; her sister **Rebecca Reodica married Ed Coscolluela**; an Epstein-office airbill even ships to Rebecca directly.
- **Fraud half (CONFIRMED):** Jun Reodica ran the Grand Wilshire fraud; **"Ed Coscolluela," a CPA, was on Jun's management team** (doc 173) — and Jun separately adopted "Coscolluela" as his own alias and married a Leticia Coscolluela.

**The one question that collapses or splits the network:** *Is the CPA "Ed Coscolluela" who worked for Jun the same Ed who married Rebecca?*
- **If yes** → Ed is a single individual who simultaneously (a) was inside the Grand Wilshire fraud and (b) married into the family of Epstein's bookkeeper. That makes Ed — not the Reodica surname — the connective tissue, and turns "coincidence of names" into one tight network.
- **If no** → there are two unrelated Eds, the Grand Wilshire and Epstein threads are largely a coincidence of the common Filipino surnames Reodica/Coscolluela, and the investigation narrows to the (still notable) standalone fact that Epstein's bookkeeper was a Filipina immigrant whose family is documentable.

Resolving Ed's identity (full legal name, DOB, CPA licensure, whether he is Eduardo Sr. and was on Jun's team) is therefore the **highest-leverage task**. Secondary: whether the two Reodica lines are distant cousins (would weakly re-introduce a family link).

## Cross-Link to the `epstein` Profile

This investigation overlaps the active **`epstein`** profile via Gie's bookkeeping role. The Epstein document corpora are wired into this profile's `corpus_tools` for exactly this reason. Primary verification step: search **Reodica / Marinese / Gie** across:

| Corpus | Tool |
|--------|------|
| DOJ Vol 11 (EFTA IDs) | `tools/query_doj.py` |
| LMSBAND | `tools/query_lmsband.py` |
| Unified DB | `tools/query_unified.py` |
| Epstein Files 20K | `tools/ingest_epstein_20k.py` |
| EpsteinExposed | `tools/ingest_epstein_exposed.py` |

Entities are shared across investigations, so a Gie/Reodica entity found here also enriches the Epstein graph. Cite **EFTA IDs** when a hit appears in DOJ Vol 11.

## Search Tips

- **Name variants** — "Reodica" is a Filipino surname; watch for OCR/transcription drift (Reodica / Reodika / Rodica) and given-name forms (Gie may be a nickname for e.g. Georgie/Regina/Gigi — keep the maiden+married pair "Reodica Marinese" together when possible). "Jun" is commonly a Filipino nickname (often for a "Jr."); search for the full legal first name too.
- **Coscoluella** is rare — high-signal exact-match term across registries, court records, and property data.
- **"Grand Wilshire"** — pin down the exact registered entity name(s) early (e.g., Grand Wilshire Financial Corporation vs. Grand Wilshire Insurance Company); the fraud may appear under several affiliated names.

## Jurisdiction Notes

- **Grand Wilshire fraud / bankruptcy / Jun Reodica criminal matter** → most likely **C.D. Cal** (Los Angeles). Check CourtListener/PACER and the US Bankruptcy Court for the Central District of California.
- **Coscoluella consulting company** → **Nevada** SOS business registry; residence likely Clark County (Las Vegas).
- **Coscoluella residence / property history** → **California** county records (pre-Vegas).
- **Jun Reodica flight & ~2013 capture** → DOJ/USAO press releases, CBP/ICE, possible immigration/extradition records (Philippines, Australia).
