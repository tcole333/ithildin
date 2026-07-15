# *Hartel v. The GEO Group, Inc.* — DE 63 and public-record case analysis

**Case:** *Steve Hartel, et al. v. The GEO Group, Inc., et al.*, No. 9:20-cv-81063-RS (S.D. Fla.)  
**CourtListener docket:** [17329078](https://www.courtlistener.com/docket/17329078/hartel-v-the-geo-group-inc/)  
**Research cutoff:** July 14, 2026  
**Lead:** #59718  
**Thread:** 113 — Litigation, Oversight & Detention Conditions

## Bottom line

The original court-stamped June 21, 2022 order, DE 63, has now been recovered from a public law-firm repository even though CourtListener indexes the entry without a downloadable RECAP document. It resolves the central ambiguity in the prior case inventory:

> “Defendants’ Motion to Dismiss is GRANTED as to all statements made after July 17, 2019. Plaintiffs’ claim shall proceed only on those statements made before July 17, 2019 and the class period shall be adjusted accordingly.”

Read with the second amended complaint and GEO’s answer, the surviving universe comprised **four pre-cutoff publication events**: GEO’s November 8, 2018 3Q18 Form 10-Q; the February 14, 2019 4Q18 earnings call; the February 25, 2019 FY18 Form 10-K; and the May 6, 2019 1Q19 Form 10-Q. The four later filing events pleaded at paragraphs 115–122—August 2 and November 7, 2019, and February 26 and May 6, 2020—were removed by DE 63. “Four publication events” is the accurate formulation: three SEC filing events contained more than one challenged sentence.

The surviving theory was not an adjudicated finding that GEO or George Zoley committed securities fraud. DE 45 held at the pleading stage that plaintiffs adequately alleged falsity, scienter as to GEO and Zoley, and loss causation for the pending-lawsuit statements. DE 63 then held that plaintiffs had not pleaded loss causation for statements after the July 17, 2019 corrective disclosure. The case ended in a **$3 million no-admission settlement**, settlement-only certification of a November 9, 2018–August 5, 2020 class, and dismissal with prejudice. The broader settlement class did not revive the post-cutoff statements as viable merits claims.

The case is significant to the ICE/DHS investigation because the pleaded contrast depended on alleged private communications in which GEO sought ICE reimbursement or DOJ assistance for detainee-labor litigation costs while making different public statements about litigation contingencies. That is a pleaded securities theory, not proof of the alleged communications or of any ICE reimbursement. The underlying ICE correspondence and contract-adjustment records remain a high-priority document-acquisition track.

## CourtListener coverage and DE 63 acquisition

The CourtListener docket was paginated to exhaustion through the v4 docket-entry API:

- 132 docket-entry objects across seven pages;
- the seventh page returned no `next` link;
- docket metadata reports filing on July 7, 2020, termination on November 17, 2023, Judge Rodney Smith, PACER case ID 573828, and nature-of-suit code 850;
- CourtListener indexes DE 63 as RECAP document 204093103 but reports `is_available: false`, with no local filepath, Internet Archive filepath, page count, file size, or text;
- CourtListener’s short DE 63 description says both the dismissal and strike motions were granted in part and denied in part and gives July 22, 2022 answer deadlines. The order itself controls: the dismissal motion was granted as to post-cutoff statements, the alternative strike motion was denied as moot, answers were due July 1, and the July 22 deadline applied to scheduling disclosures.

The exact ten-page DE 63 PDF was acquired from a [public repository maintained by Freedman Normand Friedland](https://www.fnf.law/assets/3e7fc674-c6c4-40bc-bbdb-256675898ddf). It is court-stamped on every page as “Case 9:20-cv-81063-RS Document 63 Entered on FLSD Docket 06/21/2022,” is signed by Judge Smith, and carries AOUSC/iText PDF metadata dated June 21, 2022. Its SHA-256 is `2dcd9e8f1f1c657ec5ceca464def281b09a7caedd4a9c0a5541a82317253afdd`. Rendered pages 1, 3, 5, 8, 9, and 10 were visually inspected; the text layer, page stamps, signature page, and operative language were legible and consistent.

## Claim and posture matrix

| Question | Supported answer | Evidentiary limit |
|---|---|---|
| What was the surviving securities theory after DE 45? | Count I under § 10(b)/Rule 10b-5 survived only for pending-lawsuit statements by GEO and Zoley; Count II under § 20(a) survived against Zoley. | DE 45 tested pleading sufficiency. It did not establish falsity, scienter, damages, or liability at trial. |
| Which statements remained after DE 63? | Statements made before July 17, 2019—mapped in the SAC to four publication events on November 8, 2018; February 14 and 25, 2019; and May 6, 2019. | DE 63 does not enumerate those dates itself; the mapping is a synthesis of its cutoff with SAC ¶¶107–122 and GEO’s answer. |
| Why were later statements dismissed? | Plaintiffs did not plead loss causation for post–July 17, 2019 statements. The August 6, 2020 dividend press release was not in the SAC and was not specifically tied to litigation expenses. | The ruling did not hold that the later statements were true. It held the loss-causation allegations insufficient. |
| What corrective disclosure did the court accept at pleading stage? | July 17, 2019 articles allegedly revealed requests that ICE help cover litigation-defense costs, followed by a pleaded 7.9% two-day stock decline. | This describes the court’s treatment of allegations, not an independent finding that the articles or alleged requests were accurate. |
| What was the class-period consequence? | DE 63 ordered adjustment to reflect the July 17 corrective-disclosure date. | The order does not write an exact replacement start/end pair or specify whether July 17 itself is inclusive. Do not invent one. |
| Did the later settlement restore the original class period on the merits? | No. The final judgment certified a November 9, 2018–August 5, 2020 class “solely for purposes of effectuating the Settlement.” | Settlement-class scope defines releases and allocation; it is not a merits ruling on dismissed statements. |
| Did GEO admit wrongdoing? | No. The agreement says defendants “expressly deny any and all allegations of fault, liability, wrongdoing, or damages whatsoever.” | A denial is not exoneration, just as settlement is not an admission. |
| What was paid? | The agreement defined a $3 million cash settlement fund; the fee order says it was funded into escrow. | The gross fund is not the amount distributed to investors. Fees, expenses, administration, awards, taxes, and allocation affect net distribution. |
| How did the case end? | Final judgment dismissed the action with prejudice in its entirety on November 17, 2023. | The settlement resolved the case without an adjudicated merits judgment. |

## DE 45: the pleading-stage survival order

The September 23, 2021 [DE 45 order](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.45.0.pdf) dismissed all challenged subject areas except the statements about pending lawsuits. The court described plaintiffs’ allegations that, in communications with ICE, GEO and Zoley had characterized detainee-labor lawsuits as a “potentially catastrophic risk,” with “tens of millions” in potential damages and up to $20 million in legal expenses, and that Zoley’s May 30, 2018 ICE letter said:

> “We are deeply alarmed at the rapidly increasing costs in defending these lawsuits without reimbursement from ICE, or assistance in the defense by the Department of Justice (DOJ.)”

The court then held:

> “Plaintiffs have adequately pled scienter as to GEO’s statements about the potential costs of the lawsuits against GEO.”

It found the allegations sufficient to create a strong inference of intent to deceive or severe recklessness for GEO and Zoley, but not for Brian Evans, J. David Donahue, or Ann Schlarb. Its operative disposition was:

> “Count I is DISMISSED to the extent it is based on any statements other than the statements about the pending lawsuits and against Defendants Evans, Donahue, and Schlarb.”

> “Count II is DISMISSED as to Defendants Evans, Donahue, and Schlarb.”

DE 45 also found loss causation adequately pleaded based on the alleged July 17, 2019 disclosure and subsequent stock decline. Every characterization of this order must retain the phrases **“adequately pleaded”** and **“at the pleading stage.”**

## DE 63: exact cutoff and reasoning

DE 63 explained that the prior order’s loss-causation analysis rested on July 17, 2019 articles allegedly revealing GEO’s requests that ICE cover litigation costs and the subsequent stock decline. Because that corrective disclosure preceded the later statements, plaintiffs needed another adequately pleaded causal disclosure for the later period.

Plaintiffs pointed to GEO’s August 6, 2020 press release announcing a nearly 30% dividend reduction. The court rejected that route because the press release was not part of the SAC, the SAC did not plead a specific reason connecting the dividend cut to litigation expenses, and nothing in the release addressed litigation expenses. It concluded:

> “Consequently, Plaintiffs have failed to plead loss causation as to any statements made after July 17, 2019 and Defendants’ Motion to Dismiss is granted as to all litigation related statements made after July 17, 2019.”

The operative page then ordered that the claim proceed only on statements made before July 17, 2019, with the class period adjusted accordingly. The alternative motion to strike was denied as moot.

Two negative propositions matter:

1. DE 63 did **not** reverse DE 45’s pleading-stage falsity or scienter analysis for the pending-lawsuit statements.
2. DE 63 did **not** adjudicate the post-cutoff statements truthful; it dismissed them for failure to plead loss causation.

GEO’s official [second-quarter 2022 Form 10-Q](https://www.sec.gov/Archives/edgar/data/923796/000095017022015522/geo-20220630.htm), filed August 8, 2022, accurately summarized the result in company-authored language: “the court granted the motion in part, and dismissed all claims in the second amended complaint other than those related to the Company’s statements about pending lawsuits made prior to July 17, 2019.” This is corroboration from an official filing, not a substitute for the order.

## Statement-event reconstruction

The dates and wording below come from [SAC DE 46](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.46.0.pdf). GEO’s [answer, DE 64](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.64.0.pdf), admits the dates and existence of the four pre-cutoff publications while denying the plaintiffs’ allegations. The “status after DE 63” column applies the order’s date rule; it is not a separate factual admission by GEO.

| Date | SAC paragraphs | Publication event and challenged subject | Status after DE 63 |
|---|---:|---|---|
| Nov. 8, 2018 | 107–108 | 3Q18 Form 10-Q: no litigation accrual because loss was not considered probable or reasonably estimable; no expected material adverse effect from pending claims or proceedings. | Survived the date cutoff. |
| Feb. 14, 2019 | 109–110 | 4Q18 earnings call: “we have adequately accounted for known legal cases in our guidance for 2019.” | Survived the date cutoff. |
| Feb. 25, 2019 | 111–112 | FY18 Form 10-K: no accrual because loss was not considered probable or reasonably estimable; no expected material adverse effect. | Survived the date cutoff. |
| May 6, 2019 | 113–114 | 1Q19 Form 10-Q: same accrual and material-adverse-effect subjects. | Survived the date cutoff. |
| Aug. 2, 2019 | 115–116 | 2Q19 Form 10-Q, pending-lawsuit statements. | Dismissed under DE 63. |
| Nov. 7, 2019 | 117–118 | 3Q19 Form 10-Q, pending-lawsuit statements. | Dismissed under DE 63. |
| Feb. 26, 2020 | 119–120 | FY19 Form 10-K, pending-lawsuit statements. | Dismissed under DE 63. |
| May 6, 2020 | 121–122 | 1Q20 Form 10-Q, pending-lawsuit statements. | Dismissed under DE 63. |

The November 8, February 25, and May 6 SEC filings each contain several challenged sentences. Brief references to “four statements” should therefore be normalized to **four publication events** unless quoting a source verbatim.

## ICE/DHS nexus: what the case does and does not establish

The SAC identifies the underlying litigation as detainee-labor and voluntary-work-program cases, including *Menocal v. GEO Group*, No. 1:14-cv-02887 (D. Colo.), and related Washington and California matters. Plaintiffs alleged that GEO privately treated those cases as a potentially catastrophic contractual and financial risk and asked ICE for reimbursement or DOJ defense assistance while publicly reporting no probable/reasonably estimable loss accrual and no expected material adverse effect.

DE 45 treated the alleged ICE communications as enough, at the pleading stage, to support falsity and scienter. That makes the ICE correspondence central evidence in the securities theory. It does not establish:

- that ICE granted reimbursement, a request for equitable adjustment, indemnity, or DOJ representation;
- the precise terms of any ICE contract governing defense costs;
- the authenticity or complete context of the quoted communications independent of the pleadings;
- that GEO’s accounting treatment violated GAAP;
- ultimate securities liability.

A MuckRock request identifies a promising public-record trail: ICE denials relating to Aurora contract HSCEDM-11-D-00003, Northwest contract HSCEDM-15-D-00015, Adelanto IGSA EROIGSA-11-0003, and the May 30, 2018 Zoley letter to ICE official Peter T. Edge. The request description is a discovery lead, not confirmation of the documents’ contents. The next acquisition wave should obtain and authenticate the produced files, then compare each request and ICE response against the contract’s indemnification, litigation-support, allowable-cost, and equitable-adjustment clauses.

The broader DHS relevance in DE 63’s background is also limited. The order recites allegations that 2018–2019 DHS OIG reports found deficiencies at several GEO facilities. Those facility-condition allegations belonged to subject areas DE 45 dismissed; they were not part of the surviving pending-lawsuit claim.

## Settlement, class scope, and final disposition

The [May 1, 2023 settlement agreement filed at DE 86](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.86.0.pdf) defined the “Settlement Amount” as “$3,000,000.00 (Three Million U.S. Dollars).” It also stated:

> “Defendants expressly deny any and all allegations of fault, liability, wrongdoing, or damages whatsoever.”

The November 17, 2023 [final judgment, DE 104](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.104.0.pdf), certified a class of persons and entities acquiring GEO common stock from November 9, 2018 through August 5, 2020, inclusive, **“solely for purposes of effectuating the Settlement.”** It approved the settlement and ordered: “The Action is DISMISSED WITH PREJUDICE in its entirety.”

There is no contradiction between DE 63’s merits cutoff and the broader settlement class. The DE 63 period described which pleaded statements could proceed. The DE 104 period described which investors participated in settlement releases and allocation. The court expressly limited the latter certification to settlement purposes.

## Fees and distribution

The November 17, 2023 [fee order, DE 106](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.106.0.pdf), found that the $3 million cash fund had been funded into escrow and awarded:

- attorneys’ fees equal to 32% of the settlement fund, or $960,000, plus accrued interest;
- $39,727.87 in litigation expenses;
- combined awards of $5,000 to the lead plaintiffs.

Plaintiffs’ September 19, 2024 [distribution motion, DE 107](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.107.0.pdf), reported—through plaintiffs and their claims administrator—that 12,047 proofs of claim were processed and 5,161 claims with $49,227,419.41 in recognized losses were accepted. Those figures are party-submitted administrator representations, not freestanding fact findings in the order.

The November 7, 2024 [distribution order, DE 108](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.108.0.pdf), awarded the claims administrator a $250,438.83 balance and directed pro rata distribution within 30 days, a possible second distribution, and eventual contribution of uneconomic residue to Investor Protection Trust. No exact investor net should be inferred by simple subtraction because taxes, interest, prior administrative charges, and allocation mechanics also affect the fund.

## Source discrepancies and audit cautions

1. **CourtListener DE 63 metadata versus the order:** the short docket description misstates the motion-to-strike treatment and answer deadlines. Cite the PDF for holdings and deadlines.
2. **Original proposed class period versus cutoff:** the SAC pleaded November 9, 2018–August 5, 2020; DE 63 required adjustment to the July 17, 2019 corrective-disclosure date but did not print a replacement date pair.
3. **Merits class versus settlement class:** the 2023 final judgment’s broader class was certified solely for settlement.
4. **Allegations versus adjudicated facts:** the ICE reimbursement requests, internal risk descriptions, expected damages, and defense-cost estimates were allegations accepted for pleading analysis, not trial findings.
5. **Settlement versus admission:** the settlement resolved the action and released claims; defendants expressly denied wrongdoing.
6. **Court order versus company summary:** GEO’s 2022 10-Q accurately summarizes DE 63 but remains a company-authored filing. The original order is the controlling source.

## Follow-up acquisition plan

1. Obtain the ICE productions associated with the Aurora, Northwest, and Adelanto defense-cost/equitable-adjustment requests and authenticate document dates, senders, recipients, attachments, and complete wording.
2. Pull the governing versions and modifications of HSCEDM-11-D-00003, HSCEDM-15-D-00015, and EROIGSA-11-0003; identify indemnification, claims-defense, insurance, allowable-cost, disputes, and equitable-adjustment terms.
3. Trace ICE and DHS Office of General Counsel decision memoranda, any DOJ referral or representation decision, and payment/accounting records. A denial letter alone would not rule out later reimbursement through another vehicle or modification.
4. Reconcile the four underlying detainee-labor matters by exact docket number, claim, facility, contract, and procedural result before making a portfolio-level litigation-cost claim.
5. Compare the underlying communications with GEO’s contemporaneous SEC filings and accounting-policy evidence. The court record alone does not decide GAAP treatment.

## Database outputs

- New findings attached to lead #59718 document the exact DE 63 cutoff, the four-event reconstruction, and the settlement-only class distinction.
- Existing findings #12562, #12577, and #12593–#12596 were reviewed against DE 45, DE 86, and DE 104. Their pleading-stage and no-admission limitations remain necessary.
- Source manifest: `2026-07-14-hartel-geo-de63-source-manifest.json`.
- Timeline/issue matrix: `2026-07-14-hartel-geo-de63-timeline-issue-matrix.csv`.
- Papercut #940 records the EDGAR reader’s missing standard `--output` option.

## Characterization rule

Preferred description:

> *Hartel* was a securities pleading-stage case in which pending-lawsuit statements by GEO and Zoley survived DE 45, after which DE 63 limited the claim to four pre–July 17, 2019 publication events for lack of post-cutoff loss causation. It ended in a $3 million no-admission settlement and dismissal with prejudice; the full 2018–2020 class was certified only for settlement.

