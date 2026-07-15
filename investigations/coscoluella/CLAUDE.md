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

### Current verification status (updated 2026-07-10)

**SUPPORTED BY PRIMARY RECORDS:**
- Gie Reodica Marinese worked as a J. Epstein & Co. bookkeeper/shipping-account sender. Ten released corpus documents resolve to seven invoices and ten 1999 airbills.
- Rebecca is Gie's sister. Obituary and family-tree records identify Rebecca R. Coscolluela (1945–2020) and their sister Marion R. Lorico.
- Canonical Kabasshouse page **EFTA01315387** (invoice **EFTA01315380**) names Gie as sender and **“BECKY COCOLLUELA”** as recipient at **20021 Vintage St, Chatsworth CA 91311**. The older EFTA00220017 page is a degraded duplicate. Independent family and corporate records make Rebecca the leading identity resolution.
- Eminiano A. Reodica Jr. ran the Grand Wilshire fraud, fled under the Roberto Coscolluela alias, was arrested in 2012, sentenced in 2017, and died in custody in 2021.
- Sentencing memo document 173 identifies Ed Coscolluela as Reodica's long-time friend, trained CPA, and dealership-management associate. Irving Sulmeyer—not Ed—was the bankruptcy trustee.
- Jun is not a blood sibling of Gie/Rebecca. Their documented parents differ; any distant-cousin relationship remains unestablished.

**CURRENT HIGH-PRIORITY GAPS:**
- **Keystone identity:** CA corporate filings, shared-address records, family-tree evidence, and the Terry York chronology support at high-confidence synthesis that the doc-173 CPA Ed was Eduardo S. Coscolluela Sr., Rebecca's husband. This is not single-document proof; a marriage, obituary, or historical CPA record would still independently confirm it.
- **20021 Vintage title chain:** the FedEx destination is now confirmed by EFTA01315387, and LA County confirms parcel APN 2726-022-025. Owner names remain suppressed online. Lead #53153 is blocked because recorder document 0002438 requires a paid/manual county order; human action #28 preserves the exact request. Do not infer ownership from residence/delivery.
- **Ed's current status and historical CPA licensure** remain unresolved.
- **Nevada:** records show an organizational tie through Phil-Am Ballroom Dancers Association, but no Ed/Rebecca Nevada property or consulting company. RE Consulting & Investments LLC is a California entity at 20021 Vintage.
- **Grand Wilshire:** CA entity numbers are recovered; the remaining gaps are the four 1984 LPs, two late-1988 entities, and the unidentified external auditor.
- **Ramon Coscolluela disambiguation:** keep four records separate pending identifiers: the 1990 California corporate agent (#4242), the 2002 C.D. Cal. debtor tied to 23716 Sandalwood (#4524), the 2009–2010 Union NJ/Florida operator (#4520), and the 2018–2020 N.D. Texas defendant (#4523). Hypothesis #308 tests only the NJ/FL→Texas identity; no kinship to Ed/Rebecca is established. Human action #29 queues the unavailable C.D. Cal. schedules.

### Tooling gaps surfaced

DugganUSA was retired on 2026-06-29 after its endpoint permanently returned HTTP 403; infra request #123 was rejected because DOJ Vol 11, LMSBAND, and Unified retain the underlying DOJ datasets. Nevada recorder/name history still requires a browser/recaptcha-capable session, and LA County's online systems do not expose owner names or the grantor/grantee index. CA SOS/OpenCorporates records were recovered through later work, so the earlier blanket CA-registry blocker is historical rather than current.

## Central Structural Assessment

The Reodica surname does not bridge the two halves: Jun is not documented as kin to Gie/Rebecca. What recurs is the **Coscolluela** surname, and current evidence supports at synthesis strength that **Ed Coscolluela is the human hinge**:

- **Epstein half:** Gie was a J. Epstein & Co. bookkeeper; her sister Rebecca married Ed Coscolluela; EFTA01315387 records Gie using the employer FedEx account to send a package to Becky at 20021 Vintage St.
- **Fraud half:** document 173 names an Ed Coscolluela as a CPA on Jun's management team; Jun separately adopted Coscolluela as an alias and married Leticia Coscolluela.

The working assessment is that the two Ed references identify one person, but downstream writing must label this as a high-confidence synthesis rather than a direct primary-source identification. The highest-leverage next tests are the 20021 Vintage deed, historical CPA files, and a marriage/obituary record. The distant-cousin question between the two Reodica lines remains secondary.

## Cross-Link to the `epstein` Profile

This investigation overlaps the active **`epstein`** profile via Gie's bookkeeping role. The Epstein document corpora are wired into this profile's `corpus_tools` for exactly this reason. Primary verification step: search **Reodica / Marinese / Gie** across:

| Corpus | Tool |
|--------|------|
| **Kabasshouse (primary full corpus)** | `tools/ingest_kabasshouse.py` |
| Unified DB | `tools/query_unified.py` |
| Epstein Files 20K | `tools/ingest_epstein_20k.py` |
| EpsteinExposed | `tools/ingest_epstein_exposed.py` |
| LMSBAND / DOJ Vol 11 (legacy crosswalk only) | `tools/query_lmsband.py` / `tools/query_doj.py` |

Entities are shared across investigations, so a Gie/Reodica entity found here also enriches the Epstein graph. Use Kabasshouse EFTA IDs as canonical citations; legacy LMSBAND/DOJ pages are duplicate crosswalks, not independent corroboration.

## Search Tips

- **Name variants** — "Reodica" is a Filipino surname; watch for OCR/transcription drift (Reodica / Reodika / Rodica) and given-name forms (Gie may be a nickname for e.g. Georgie/Regina/Gigi — keep the maiden+married pair "Reodica Marinese" together when possible). "Jun" is commonly a Filipino nickname (often for a "Jr."); search for the full legal first name too.
- **Coscoluella** is rare — high-signal exact-match term across registries, court records, and property data.
- **"Grand Wilshire"** — exact California entity names and numbers are now mapped. Use those identifiers to retrieve filings, UCC records, LP agreements, and bankruptcy schedules rather than repeating broad name searches.

## Jurisdiction Notes

- **Grand Wilshire fraud / bankruptcy / Jun Reodica criminal matter** → most likely **C.D. Cal** (Los Angeles). Check CourtListener/PACER and the US Bankruptcy Court for the Central District of California.
- **Consulting-company hypothesis** → RE Consulting & Investments LLC is in **California**; Nevada work should focus on historical officer/association records, not an assumed Ed/Rebecca company.
- **Coscolluela residence / property history** → 20021 Vintage St, Chatsworth; recorder document 0002438 for APN 2726-022-025 is queued as paid/manual human action #28.
- **Same-name Ramon records** → 23716 Sandalwood (C.D. Cal. debtor) and 1010 Adams Ave, Union NJ (NJ/FL operator); never collapse them into the 1990 California agent on surname alone.
- **Jun Reodica flight & 2012 capture** → DOJ/USAO/FBI records and Australian/Philippine identity records.
