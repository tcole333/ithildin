# GEO legacy commercial litigation — CourtListener deep read

**Research cutoff:** July 14, 2026  
**Lead:** #59720  
**Thread:** 113 — Litigation, Oversight & Detention Conditions  
**Starting inventory:** 458 deduplicated GEO/legacy dockets  
**Machine-readable outputs:** `2026-07-14-geo-legacy-commercial-ranked-case-matrix.csv`; `2026-07-14-geo-legacy-commercial-source-manifest.json`

## Bottom line

The residual commercial cluster produced three materially different records:

1. **A direct GEO insurance dispute:** GEO alleged that HCC Life Insurance failed to reimburse **$2,088,402.98** under a stop-loss policy after a dependent of a GEO employee incurred more than $6.8 million in medical charges. HCC filed a competing Texas declaratory action; that action was voluntarily dismissed. The first-filed Florida action was reported **“Settled in full”** after mediation in May 2017. No settlement amount or agreement is public in RECAP.
2. **A large pre-acquisition CEC vendor judgment:** the Federal Judicial Center data embedded in CourtListener codes *ARAMARK Correctional Services v. Community Education Centers* as a plaintiff-favoring, pretrial-motion judgment, a monetary award only, and `amount_received: 7240`. The CourtListener model defines that field in thousands of dollars, yielding a structured amount of **$7.240 million**. A contemporary report said ARAMARK sought about $7.3 million for correctional-facility food services and alleged payment default since June 2008. The underlying complaint and judgment are not in RECAP, so the FJC amount should be reported with its explicit non-uniform-use caveat.
3. **Two executive-contract disputes at later-acquired companies:** *Gilliland* generated a substantive summary-judgment opinion against several Cornell defenses and counterclaims before a voluntary dismissal. *Watson* alleged $1.2 million due under a CEC executive employment agreement, was transferred from Florida to New Jersey, and then settled on terms not public in RECAP.

The acquisition timing prevents a common overstatement. GEO acquired Cornell on **August 12, 2010** and CEC on **April 5, 2017**. Every named Cornell/CEC case in this cluster was terminated before GEO acquired the company. They illuminate the commercial history of companies GEO later bought; the reviewed records do **not** show that GEO originated the alleged conduct or paid the resolved judgment/settlements.

## Scope and method

The lead-59509 docket matrix was re-screened for non-routine contract, insurance, vendor, executive-compensation, and other commercial disputes. Priority was given to:

- named cases in lead #59720;
- an actual monetary judgment, pleaded amount, or settlement record;
- a dispositive merits order rather than a docket caption alone;
- direct GEO litigation over legacy-company litigation;
- a defensible acquisition-timing and entity-lineage analysis.

CourtListener docket detail, FJC Integrated Database fields, RECAP docket entries, and available PDFs were queried separately. Primary PDFs were rendered to PNG and visually checked. Public document absence is treated as an access gap, not as evidence of sealing. PACER case identifiers are included in the ranked matrix for a paid follow-up.

## 1. GEO v. HCC Life Insurance: $2.088 million stop-loss claim, settled in full on undisclosed terms

GEO filed its Palm Beach County complaint on March 2, 2016. HCC later removed it to the Southern District of Florida, No. 9:16-cv-80465. The complaint concerns stop-loss policy HCL31368, effective November 1, 2014 through October 31, 2015, for GEO's self-insured employee health plan. GEO alleged it paid about $140,000 per month in premium.

The covered person was Terrin Lee, the 18-year-old son of GEO employee Keith Lee. According to GEO's complaint, Terrin incurred at least **$6,814,341.44** in charges; Florida Blue determined that at least **$4,318,894** for the HCC coverage period were allowed amounts; and HCC initially reimbursed **$1,880,491.02**. GEO alleged that HCC's consultant challenged extended ECMO, nitric oxide, and antithrombin treatment as not medically necessary or appropriate. GEO sought the remaining **$2,088,402.98**, prejudgment interest, costs, expert fees, and attorneys' fees.

These are allegations in GEO's complaint, not merits findings. The exact demand is:

> “Award GEO damages for unpaid Covered Expenses resulting from Terrin's claim in the amount of $2,088,402.98.”

HCC filed a competing Texas declaratory action on March 7, 2016 against The GEO Group and GEO Corrections Holdings, S.D. Tex. No. 4:16-cv-00587. GEO's motion to dismiss or stay described the two actions as involving the same parties, policy, and approximately $2 million dispute, and invoked the first-to-file rule because GEO filed in Florida first. HCC voluntarily dismissed the Texas action in July 2016.

The Florida docket records a May 9, 2017 final mediation report with the disposition **“Settled in full.”** The court stayed and administratively closed the case that day; the parties filed stipulations of dismissal with prejudice in June. RECAP does not provide the mediation agreement or a settlement amount. The $2.088 million complaint demand must not be reported as the settlement payment.

This is the strongest direct-GEO commercial case in the cluster. It is material insurance litigation, but it is unrelated to a government contract and should not be folded into the ICE/DHS procurement totals.

## 2. ARAMARK v. CEC: structured $7.240 million plaintiff judgment before GEO acquisition

*ARAMARK Correctional Services, LLC v. Community Education Centers, Inc.*, E.D. Pa. No. 2:10-cv-00685, was filed February 18, 2010 and terminated August 2, 2010. No pleading, order, or judgment is downloadable in RECAP.

The strongest primary-data result is the FJC record embedded in CourtListener:

- procedural progress `4`: judgment on motion;
- disposition `6`: motion before trial;
- nature of judgment `1`: monetary award only;
- judgment favored `1`: plaintiff;
- amount received `7240`, a field defined in thousands of dollars.

That combination records a **$7.240 million monetary judgment for ARAMARK on a pretrial motion**. CourtListener's model warns that `amount_received` was not used uniformly, so the number should be attributed to the structured FJC record unless the underlying judgment is purchased from PACER.

A contemporary Prison Legal News report, citing the complaint, described the theory as $7.3 million owed for food services at CEC's privately operated correctional facilities and said ARAMARK alleged CEC had been in payment default since June 2008. Because the complaint is unavailable and that description is secondary, it is suitable as a theory-of-case lead, not as a confirmed court finding.

GEO bought CEC nearly seven years later. The record therefore belongs to CEC's pre-acquisition vendor history; it is not evidence that GEO incurred or paid this judgment.

## 3. Watson v. CEC and John J. Clancy: $1.2 million allegation, transfer, then undisclosed settlement

David N.T. Watson sued CEC and its chairman and CEO, John J. Clancy, in M.D. Fla. No. 2:10-cv-00778. The transfer order says Watson worked as a Wackenhut Corrections senior executive from 1999 to 2007, joined CEC as senior vice president and CFO in September 2009, and was terminated in New Jersey on December 15, 2010.

Watson's amended complaint asserted breach of contract, breach of the covenant of good faith and fair dealing, fraudulent inducement, promissory estoppel, New Jersey wage-law violations, and declaratory judgment. The court summarized his allegation that CEC's true financial condition was hidden or grossly misstated during recruitment. It also recorded Watson's allegation that defendants failed to pay **$1.2 million** under the employment agreement.

Those are complaint allegations. On August 11, 2011, the Florida court decided venue only: the employment agreement was performed in New Jersey, the termination occurred there, New Jersey law governed, and the operative facts and key witnesses favored transfer. The court transferred the case to D.N.J. No. 2:11-cv-04855.

The downstream FJC record codes the New Jersey action as `origin: 5` (transferred from another district), `disposition: 13` (settled), and terminated October 3, 2012. RECAP has no settlement agreement, amount, or final approval/dismissal document. The **$1.2 million demand is not a documented settlement payment**.

CEC was not acquired by GEO until April 2017. Watson's earlier work at Wackenhut does not make GEO a defendant in this suit; he left Wackenhut two years before joining CEC, and the pleaded dispute concerned the CEC agreement.

## 4. Gilliland v. Cornell: substantive defense losses, unresolved severance fact issue, voluntary dismissal

Michael Gilliland alleged that Cornell Companies terminated him without cause but failed to pay the one-year salary severance required by his October 2004 employment contract. Cornell said he voluntarily resigned and counterclaimed under a later independent-contractor agreement.

In a 39-page November 10, 2008 opinion, the court held that the independent-contractor agreement did not supersede the employment contract. It granted Gilliland summary judgment on Cornell's declaratory claim and rejected Cornell's breach counterclaim because the later contract contained no implied covenant not to sue. The opinion states:

> “Because the court declines to imply a covenant not to sue in the Independent Contractor Agreement, Defendant's argument that Plaintiff breached the Independent Contractor Agreement fails as a matter of law.”

The court did not award Gilliland severance in that opinion. Whether he was terminated or resigned remained a factual issue, and the court deferred attorney-fee questions. The FJC record says the case was voluntarily dismissed on March 20, 2009. No final settlement or dismissal document is in RECAP, and no public amount was established.

GEO acquired Cornell on August 12, 2010, about seventeen months after the case ended. The matter is therefore pre-acquisition Cornell history, not an adjudication against GEO.

## 5. CEC v. McDougall: voluntarily dismissed; complaint theory unavailable

*Community Education Centers, Inc. v. McDougall*, E.D. Pa. No. 2:13-cv-02763, was filed May 20 and terminated July 29, 2013. The CourtListener/FJC record identifies only “MCDOUGALL,” not a full name. It codes the procedural stage as no court action before issue was joined and the disposition as voluntarily dismissed. It records no monetary award.

No complaint, answer, order, docket entry, or party-detail record is available in RECAP. The title and nature-of-suit code establish only that CEC brought an “other contract” action. The contract type, requested relief, counterparty identity, and reason for voluntary dismissal remain unknown. This is a bounded PACER gap, not a basis for inference.

## Lower-ranked control: Klassy v. GEO

*Klassy v. The GEO Group*, N.D. Cal. No. 4:18-cv-07565, appeared in the seed matrix as an “other contract” case, but a public screening order shows it was a pro se tort/statutory pleading about alleged false reporting to the Social Security Administration and property removal. The plaintiff sought $14.4 million based on GEO's CEO salary. The court found the initial complaint deficient and permitted amendment; the FJC record codes the final disposition as want of prosecution. It is not a material contract case and was excluded from the core ranking.

## Acquisition-lineage conclusions

The corporate lineage is real, but the liability inference is limited:

- GEO acquired Cornell on August 12, 2010. *Gilliland* ended March 20, 2009.
- GEO acquired CEC on April 5, 2017 for $360 million. *ARAMARK* ended in 2010, *Watson* in 2012, and *McDougall* in 2013.
- None of the reviewed legacy matters was pending when GEO acquired the relevant company.

Accordingly, these cases may be described as litigation involving companies GEO later acquired. They should not be described as judgments against GEO, post-acquisition resolutions, or proved inherited liabilities.

## Public settlement and paid-document gaps

| Case | Public final record | Missing record | Paid follow-up |
|---|---|---|---|
| HCC Florida | Docket says “Settled in full”; later dismissal with prejudice | Settlement agreement and payment | PACER 481115, ECF 74-77 |
| ARAMARK | FJC structured judgment and amount | Complaint, dispositive motion/order, judgment | PACER 347944; obtain complaint and final judgment |
| Watson New Jersey | FJC disposition says settled | Settlement/dismissal and payment | PACER 263514; obtain final entries around Oct. 3, 2012 |
| Gilliland | Merits opinion; FJC says voluntarily dismissed | Final stipulation/order and any settlement | PACER 507443; obtain entries after ECF 50 |
| CEC v. McDougall | FJC says voluntarily dismissed | Entire docket, complaint, party identity, dismissal | PACER 477174 |

The HCC and Watson public amounts are demands, not settlements. Gilliland and McDougall have no defensible public payment amount. ARAMARK is different: the FJC record itself codes a monetary judgment, but the judgment document should be purchased before quoting the exact award without attribution to the structured dataset.

## Characterization rule

Preferred summary:

> GEO's own most material commercial case in this residual cluster was a $2.088 million stop-loss insurance claim that settled in full on undisclosed terms. Separately, structured federal data records a $7.240 million plaintiff judgment against Community Education Centers in an ARAMARK food-service dispute years before GEO acquired CEC. Executive-contract disputes at Cornell and CEC also predated GEO's acquisitions and ended without public settlement terms.

Do not add the $2.088 million HCC demand, $1.2 million Watson demand, and $7.240 million ARAMARK judgment into a single “GEO liability” total. They are different measures, parties, and acquisition periods.

## Source QA

The Gilliland opinion, Watson transfer order, HCC complaint, and HCC motion to dismiss were downloaded from RECAP. Key pages were rendered and visually checked against extracted text. The HCC complaint required forced OCR; the quoted $2,088,402.98 demand and the $4,318,894 / $1,880,491.02 components were verified on rendered pages 6, 8, and 10. The FJC code mapping was checked against CourtListener's current open-source `FjcIntegratedDatabase` model and the FJC's description of the IDB. The machine-readable manifest records URLs and hashes.

## Audited findings

- #12838 — ARAMARK/CEC structured $7.240 million plaintiff judgment (`paraphrase`, `high`)
- #12839 — GEO's $2,088,402.98 HCC complaint demand (`direct_quote`, `confirmed`)
- #12840 — HCC Florida action “Settled in full,” public payment unavailable (`direct_quote`, `confirmed`)
- #12841 — Watson order records $1.2 million CEC nonpayment allegation (`direct_quote`, `confirmed`)
- #12842 — Watson New Jersey action coded settled, public terms unavailable (`paraphrase`, `high`)
- #12843 — Gilliland court rejected Cornell implied-covenant counterclaim (`direct_quote`, `confirmed`)
- #12844 — acquisition-timing synthesis: every named CEC/Cornell matter ended before acquisition (`synthesis`, `medium`)
- #12845 — McDougall voluntary-dismissal and public-document negative result (`paraphrase`, `high`)

Each finding has quote-bearing evidence rows and was verified by `codex-visible-agent`.
