# GEO Group litigation and procurement case forensics

Generated: 2026-07-13  
Investigation profile: `geo-group`  
Lead: `#59509`

## Result

This wave created a bounded, deduplicated CourtListener inventory of 458 dockets connected to current GEO names, legacy entities, or targeted supplemental searches. It then deep-read the material procurement, False Claims Act, securities/derivative, insurance, employment, and tax records that were publicly accessible.

The accessible record did not produce a merits judgment establishing fraud in an ICE procurement. The most directly procurement-related case concerned a Bureau of Prisons Brooklyn residential reentry-center contract, not an ICE award. The unresolved *Burciaga* False Claims Act docket remains a material source gap because the complaint and dispositive filings were not publicly available through RECAP.

Durable data artifacts:

- [Deduplicated docket inventory (CSV)](./geo-courtlistener-dockets-deduplicated.csv)
- [Deduplicated docket inventory with metadata (JSON)](./geo-courtlistener-dockets-deduplicated.json)
- [Reproducible inventory builder](./build_inventory.py)

## Inventory and coverage

Nine party-name queries returned 495 rows and 453 unique CourtListener docket IDs. Five nonduplicative targeted dockets were added: *GEO Group, Inc. v. United States*, *Hartel*, *Zhang*, *Maldonado*, and the Florida GEO-HCC insurance action.

| Query name | Raw rows |
|---|---:|
| The GEO Group, Inc. | 200 |
| GEO Corrections Holdings, Inc. | 6 |
| GEO Secure Services, LLC | 35 |
| GEO Care, Inc. | 31 |
| B.I. Incorporated | 16 |
| Cornell Companies, Inc. | 49 |
| Correctional Services Corporation | 36 |
| Community Education Centers, Inc. | 104 |
| Wackenhut Corrections Corporation | 18 |

Deterministic screening labels divided the 458 dockets into 302 detention/civil-rights/tort matters, 53 employment/labor matters, 14 contract/commercial matters, three securities/derivative matters, two FCA matters, one procurement/bid protest, and 83 other matters. These labels are triage aids, not legal conclusions.

The inventory flags 16 `B.I. Incorporated` results for manual identity confirmation because that name is not unique. It also flags 202 legacy-name results for corporate-lineage review before attributing them to GEO. The principal GEO party query reached the 200-row collection cap, so the inventory must not be represented as a complete PACER census.

An additional nine-name opinion sweep produced 900 raw results and 793 unique opinion clusters; 175 referred to a target name and 21 combined a target reference with a priority legal keyword. Broad Federal Judicial Center queries repeatedly stalled; only a bounded one-record sample completed. This is a coverage limitation, not evidence of an absence of cases.

## Procurement case

### *GEO Group, Inc. v. United States*, No. 11-490C (Fed. Cl.)

The case concerned BOP solicitation RFP-200-1042-NE for residential reentry services in Brooklyn or Queens. The published opinion records BOP's February 16, 2011 award to Community First Services. Finding `#12573`.

At the temporary-restraining-order stage, the Court of Federal Claims concluded that GEO had not demonstrated a likelihood of success on the merits. Finding `#12560`. The opinion also said there was no indication that the former GEO employee's conduct gave rise to a Procurement Integrity Act violation. Finding `#12574`. The court denied the TRO application. Finding `#12592`.

Those were preliminary findings on expedited relief, not a final merits adjudication of every protest theory. On October 27, 2011, the court entered Rule 41(a) judgment dismissing GEO's complaint with prejudice after its voluntary-dismissal motion. Finding `#12614`.

Primary records: [published TRO opinion](https://www.courtlistener.com/opinion/6778735/geo-group-inc-v-united-states/), [dismissal judgment docket entry](https://www.courtlistener.com/docket/15787536/58/geo-group-inc-the-v-united-states/).

## False Claims Act cases

### *Hynd v. The GEO Group, Inc.*, No. 5:19-cv-00067 (S.D. Ga.)

The magistrate judge summarized the pro se plaintiff's allegation that GEO conspired to provide GEDs to inmates who already had high-school diplomas or post-secondary qualifications. This records the allegation, not its truth. Finding `#12615`.

The report stated that the FCA does not permit pro se qui tam suits. Finding `#12575`. It recommended dismissal for failure to state a qui tam claim on behalf of the United States. Finding `#12561`. The recommendation therefore reflects the relator's inability to proceed pro se, not a merits exoneration of GEO on the alleged scheme.

Primary record: [report and recommendation](https://storage.courtlistener.com/recap/gov.uscourts.gasd.78732/gov.uscourts.gasd.78732.5.0.pdf).

### *Burciaga v. The GEO Group Inc.*, No. 3:12-cv-02059 (S.D. Cal.)

CourtListener metadata classifies the action under the False Claims Act, and the RECAP index exposes 52 docket-document records. The complaint, the referenced summary-judgment filing, and terminal merits papers were not publicly retrievable in this wave. The accessible settlement-scheduling entry does not establish the allegations, disposition, payment, or liability.

No merits finding was created. Lead `#59716` is the bounded document-acquisition task for the complaint and dispositive record.

Primary index: [CourtListener docket](https://www.courtlistener.com/docket/6114747/burciaga-v-the-geo-group-inc/).

## Securities and derivative litigation

### *Hartel v. The GEO Group, Inc.*, No. 9:20-cv-81063 (S.D. Fla.)

The September 23, 2021 pleading-stage order left Count I standing only insofar as it concerned statements about pending lawsuits. Finding `#12595`. It also held that plaintiffs had adequately pleaded scienter as to statements about the potential costs of lawsuits against GEO. Finding `#12562`. Count II was dismissed as to Evans, Donahue, and Schlarb. Finding `#12596`.

The settlement specified a $3 million cash fund. Finding `#12577`. The action was ultimately dismissed with prejudice. Finding `#12593`. Defendants expressly denied fault, liability, wrongdoing, and damages, so the settlement must not be characterized as an admission. Finding `#12594`.

Lead `#59718` seeks docket entry 63, an unavailable June 2022 order needed to reconcile the surviving theory between the 2021 dismissal order and settlement.

Primary records: [September 2021 dismissal order](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.45.0.pdf), [settlement agreement](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.86.0.pdf), [final judgment](https://storage.courtlistener.com/recap/gov.uscourts.flsd.573828/gov.uscourts.flsd.573828.104.0.pdf).

### *Zhang v. Zoley*, No. 9:21-cv-82061 (S.D. Fla.)

The court approved the shareholder-derivative settlement under Rule 23.1 and dismissed the action with prejudice. Findings `#12599` and `#12600`. The final order expressly stated that the settlement was not an admission or concession by GEO or the settling defendants. Finding `#12601`.

The court-approved settlement required the following governance measures:

- A one-time Board presentation evaluating existing governance practices against peer practices. Finding `#12602`.
- Use of an independent search firm if an independent-director vacancy arose during the specified two-year period. Finding `#12603`.
- A formal Legal Steering Committee charter, an independent committee chair, and website publication of the charter and membership. Findings `#12604`, `#12605`, and `#12606`.
- A formal management-level Disclosure Committee charter. Finding `#12584`.
- A Chief Compliance Officer position separate from the General Counsel, reporting to the CFO and Audit and Finance Committee. Findings `#12607` and `#12613`.
- Amendment of the Audit Committee charter. Finding `#12609`.
- Governance-program education for each new director within one year of joining the Board. Finding `#12610`.
- Four-year retention of reporting-hotline complaint logs. Finding `#12611`.

These are verified settlement requirements; this wave did not independently test subsequent implementation of every measure.

Primary records: [preliminary settlement approval and governance terms](https://storage.courtlistener.com/recap/gov.uscourts.flsd.603241/gov.uscourts.flsd.603241.46.0.pdf), [final settlement order](https://storage.courtlistener.com/recap/gov.uscourts.flsd.603241/gov.uscourts.flsd.603241.64.0.pdf).

## Insurance and commercial dispute

In the Texas HCC action, GEO alleged that HCC failed to reimburse approximately $2 million in medical expenses under a stop-loss insurance policy. That is GEO's allegation, not an adjudicated debt. Finding `#12612`. The related Florida docket later reported that the matter was settled in full, but the public docket did not reveal the terms. Finding `#12598`.

Primary records: [Texas filing](https://storage.courtlistener.com/recap/gov.uscourts.txsd.1340513/gov.uscourts.txsd.1340513.7.0.pdf), [Florida docket](https://www.courtlistener.com/docket/13426410/the-geo-group-inc-v-hcc-life-insurance-company/).

Lead `#59720` preserves the lower-priority legacy commercial cluster, including ARAMARK/Community Education Centers, *Gilliland*, *Watson*, and *McDougall*, for a separate bounded review.

## Employment appellate sample

In *Arizona ex rel. Horne v. GEO Group*, the Ninth Circuit vacated summary judgment and directed reinstatement of EEOC and Arizona Civil Rights Division claims brought on behalf of aggrieved employees. Finding `#12566`. The panel's decision addressed Title VII and Arizona Civil Rights Act class claims and did not establish GEO's ultimate liability.

In *EEOC v. GEO Group*, the Third Circuit majority affirmed summary judgment for GEO in the Muslim-khimar religious-accommodation case. Finding `#12585`. Judge Tashima's published dissent would have reversed; that dissent is not the court's holding. Finding `#12567`.

Primary records: [Ninth Circuit opinion](https://www.courtlistener.com/opinion/3185240/arizona-ex-rel-thomas-horne-v-the-geo-group/), [Third Circuit opinion](https://www.courtlistener.com/opinion/152022/equal-employment-opportunity-commission-v-geo-group-inc/).

Lead `#59722` preserves the larger employment/wage cluster for ranked review beyond this appellate sample.

## Tax disputes and disclosures

In GEO's Texas sales-tax case, the parties stipulated to a conditional refund of $3,937,103.71 plus interest if GEO's purchases qualified for the claimed exemption. Finding `#12586`. The appellate court affirmed the judgment denying the refund. Finding `#12588`. Its reasoning concluded that GEO had not established that it was a federal or state government agency or instrumentality immune from the state tax. Finding `#12616`. That holding arose in a Texas tax-exemption context and should not be generalized mechanically to every statutory setting.

Separately, GEO's 2025 Form 10-K reported an approximately $18.9 million July 2024 payment toward estimated liability for an audited-period New Mexico tax assessment. Finding `#12589`.

Primary records: [Texas appellate opinion](https://www.courtlistener.com/opinion/9370725/the-geo-group-inc-and-geo-corrections-and-detention-llc-v-glenn-hegar/), [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm).

## Evidence QA and limits

All 37 finding IDs cited in this report are retained one-fact records, each linked to an exact quotation from a primary court record or SEC filing and marked verified by source QA. The report does not rely on compound or retracted predecessor records.

Important limits:

- CourtListener and RECAP coverage depends on contributed PACER documents and index quality.
- Search counts are bounded by query limits and are not a complete litigation census.
- Multiple databases reproducing the same court document would be redundant, not corroborating evidence.
- Complaint allegations, pleading-stage rulings, majority holdings, dissents, settlements, and tax disclosures are labeled separately throughout.
- *Burciaga* cannot be characterized on the merits until its unavailable complaint and dispositive record are acquired.
