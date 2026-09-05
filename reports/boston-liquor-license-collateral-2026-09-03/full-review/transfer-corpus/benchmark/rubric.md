# Predeclared pilot scoring rubric

Freeze this rubric and the input/reference hashes before either model runs. This is a deliberately challenging 13-case pilot: 12 Board items and one ownership excerpt packet, not a population estimate of model accuracy. Report licensing and ownership results separately as well as the equal-case mean. No model has been invoked to build the pack.

## Administration

Use fresh, blinded agents with identical instructions and the identical complete contents of `input.json`. Do not pass `reference.json`, this rubric, `ownership-cases.json`, `build_pack.py`, corpus files, report summaries, or their paths to either agent. Do not let either agent browse or inspect files/tools. Use the same reasoning effort and model settings where supported; record any differences, model identifier, elapsed time, token usage if available, and raw output. Do not give corrective follow-ups before scoring. Freeze and preserve both raw outputs.

The supplied cases are independent. A later case about the same license must not silently alter the answer to a source packet from an earlier date. Legal/business names may differ in punctuation without being substantively different. Source corrections override proposed names or details. Do not grade spelling/punctuation normalization as a substantive error unless it changes entity identity.

## Case scores

Each Board case is worth 100 points:

| Component | Points | Rule |
|---|---:|---|
| Action classification | 20 | Correct set of listed actions. For multiple true actions, divide equally. An extra incorrect action loses its proportional share; minimum zero. Omission and false positive are recorded separately. Ancillary actions outside the schema are not required. |
| Disposition and approval flags | 15 | 5 each for disposition, license-transfer approval flag, and new-license-pledge approval flag. Acknowledgment of a notice/release is not a grant. |
| Explicit license number | 5 | Correct normalized number; source whitespace/hyphen differences are harmless. |
| Relevant parties and DBA | 20 | 4 each for transferor, transferee, transferee DBA, pledging party, and license-pledge recipient. Correct null is credit when the relevant license action is absent. Stock-only actors must not become license parties. |
| Locations | 5 | 2.5 each for from/to address. Equivalent abbreviation/spacing is accepted. An omitted source address must remain null. |
| Conditions and corrections | 10 | Credit proportional to the materially required conditions/corrections in the reference. Equivalent concise language is accepted. Do not require every operating detail. When no required condition exists, full credit for an empty list or only accurate nonmaterial detail. |
| Limits of evidence | 20 | 8 for sale-completion status, 8 for current-license-lien status, 4 for loan amount. Correctly distinguishing explicitly unclosed from simply unproved is required. |
| Evidence quotes | 5 | At least one short, faithful quote supports the classification or disposition and appears in that case's text. Whitespace normalization allowed. A valid alternate quote earns full credit. |

The ownership case is worth 100 points:

| Component | Points | Rule |
|---|---:|---|
| Relationship and subject | 25 | 20 for portfolio affiliation without group equity ownership; 5 for identifying Lyons Group/listed venues. |
| Investor and percentage | 15 | 7.5 each for correct null investor and percentage. |
| Establishment flags | 25 | 12.5 each for private-equity backing and current-equity-ownership flags. |
| Material qualifications | 25 | 15 for explicit ownership disclaimer overriding marketing language; 10 for avoiding the inference that every venue therefore lacks other investors/common beneficial owners. |
| Evidence quotes | 10 | Faithful explicit ownership-disclaimer quote from provided text. |

## Critical unsupported inferences versus omissions

Score all components above, and separately tag each material error as **unsupported positive inference**, **omission**, or **incorrect extraction/classification**. Count the following as critical unsupported inferences whenever asserted in any output field:

1. A Board approval proves a completed sale, ABCC approval, satisfied issuance condition, current owner, or current outstanding license lien.
2. A transfer revocation notice acknowledged by the Board is a new grant or a formal revocation order; or the unclosed transaction is described as completed.
3. A pledge release is a new pledge, proves no other current liens, or implies all debt is repaid.
4. A stock-only transfer/pledge is asserted to be a license transfer/pledge.
5. A loan amount, address, investor, equity percentage, or named counterparty absent from the provided evidence is invented.
6. Lyons portfolio marketing is treated as equity ownership or PE sponsorship despite the explicit disclaimer; or the disclaimer is treated as proof that every venue has no other institutional investor.

A case with any critical unsupported inference is capped at **50/100** after component scoring. Multiple critical claims remain separately counted but do not produce repeated numeric penalties. Plain omission of a supported action/party/condition loses the relevant component points and is reported as an omission, without the critical-inference cap. A missing condition coupled with an affirmative claim that the license was issued is an unsupported inference, not merely an omission.

Report: schema validity; cases answered; raw weighted component score; capped equal-case score; Board-only score; ownership score; number of critical-inference cases and claims; omission count by component; false-positive and false-negative action counts; and a short list of concrete errors with case IDs and source quotes. For this pilot, prefer fewer critical-inference cases, then higher capped score; do not turn a small score difference into a general model-quality claim.

## Ambiguity and adjudication

The answer key is a reviewed reference, not an authority above the source. If either model provides a plausible answer that conflicts with the reference, an independent adjudicator should receive anonymized answers, the source packet, schema, and rubric. It should distinguish permissible semantic variants from source-supported corrections to the key. Record any correction once and apply it equally to both models. Do not adjust weights after viewing results.

Known interpretation allowances: pledge parties in a combined transfer petition may be described as the proposed transferee/pledger; spelling or punctuation variants of legal names are acceptable. The revocation item records mutual intent and acknowledgment, so do not require a finding that a formal Board revocation was consummated. A release's recipient denotes the creditor releasing its previous pledge. For the Lyons case, wording such as 'marketing/portfolio affiliation; exact operating relationship not specified' is accepted; do not require an operational-management inference.
