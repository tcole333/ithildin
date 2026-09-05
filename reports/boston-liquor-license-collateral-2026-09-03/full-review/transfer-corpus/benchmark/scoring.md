# Blind scoring of the 13-case extraction pilot

Response B performs better under the predeclared rule: it has no critical unsupported inferences, while response A asserts current liens in three cases where the source establishes only pledge approval. Ownership scores are tied.

| Measure | Response A | Response B |
|---|---:|---:|
| Schema valid; cases answered | Yes; 13/13 | Yes; 13/13 |
| Raw weighted total | 1,271/1,300 | 1,300/1,300 |
| Raw equal-case mean | 97.77 | 100.00 |
| Capped equal-case mean | 88.08 | 100.00 |
| Board-only raw mean (12 cases) | 97.58 | 100.00 |
| Board-only capped mean (12 cases) | 87.08 | 100.00 |
| Ownership score (1 case) | 100.00 | 100.00 |
| Critical-inference cases / claims | 3 / 3 | 0 / 0 |
| Omissions | 1 condition | 0 |
| Action false positives / false negatives | 0 / 0 | 0 / 0 |

Each case is worth 100 points. Case scores and every weighted component appear in `scores.json`; the 50-point cap is applied once to each case with a critical inference. Schema validation covered every assertion keyword used by the supplied schema. Both responses answer every unique case and all evidence quotes match the same-case text after whitespace normalization.

| Case | A raw | A capped | B raw | B capped |
|---|---:|---:|---:|---:|
| C01 | 100 | 100 | 100 | 100 |
| C02 | 100 | 100 | 100 | 100 |
| C03 | 100 | 100 | 100 | 100 |
| C04 | 95 | 95 | 100 | 100 |
| C05 | 100 | 100 | 100 | 100 |
| C06 | 92 | 50 | 100 | 100 |
| C07 | 100 | 100 | 100 | 100 |
| C08 | 100 | 100 | 100 | 100 |
| C09 | 100 | 100 | 100 | 100 |
| C10 | 92 | 50 | 100 | 100 |
| C11 | 100 | 100 | 100 | 100 |
| C12 | 100 | 100 | 100 | 100 |
| C13 | 92 | 50 | 100 | 100 |

Response A’s concrete errors:

- **C06, C10, C13 — critical unsupported current liens.** Each answer sets `current_license_lien_status` to `established`. C06 says “Lastly, has petitioned to pledge the license and stock to 1121 Dorchester Avenue Realty LLC.” C10 says “Secondly, has petitioned to pledge the license and inventory to Rockland Trust Company.” C13 says “has petitioned to pledge the license to Brookline Bank.” Each petition is granted, but those excerpts do not establish a current outstanding lien. Each loses 8 evidence-limit points and is capped at 50/100. Response B uses `not_established` in all three.
- **C04 — omitted issuance contingency.** A gives only “License not to be issued.” The source says “License not to be issued Board has received confirmation from the Downtown Boston Neighborhood Association that the community process has been completed”. A preserves the hold but omits what must happen to lift it, earning 5/10 proportional condition credit. It does not claim issuance occurred, so this is one omission, with no critical cap. B captures the confirmation requirement.

Uniform reference adjudications are preserved separately in `errata.json`; the frozen reference was not edited:

- **C06:** add `stock_pledge` to the reference action set because the source expressly says “pledge the license and stock”. Both responses extracted it correctly.
- **C01:** accept `license_transfer_approved: true` as the expressly recorded historical approval, given both responses retain acknowledgment, a revocation-intent notice, and nonclosing. The source says “approved by the Board on August 28, 2025”; the schema does not time-qualify this flag. Neither response describes a new grant or completed formal revocation. The present-meeting interpretation `false` also remains permissible.
- **C06/C09/C10:** accept the named holder/applicant or proposed transferee as pledging party. The source retains the grammatical subject “Holder ... has petitioned” and does not unambiguously reassign the pledge; the rubric explicitly permits the proposed-transferee reading. These are named source parties, not invented counterparties.
- **C06/C07:** do not require evidence-limit reminders as final-disposition conditions. C06 requires Maria Murray as final manager; C07 imposes no condition. Both responses correctly leave omitted addresses null and current liens unestablished for the release.
- **C01/C03:** redundant restatement is not required. Both C01 responses preserve the explicit nonclosing reason and acknowledgment. Both C03 responses preserve the ownership disclaimer and avoid asserting that all venues lack other investors. The rubric awards the latter 10 points for avoiding that inference, not for reciting its negation.

Source quotations above come solely from `input.json`. A second blinded adjudicator independently checked the disputed reference readings. The packet, schema, reference, rubric, administration record, and raw responses remained unchanged. This single run on 13 deliberately selected cases is not a population accuracy estimate or evidence of broad model equivalence, reliability, or cost-effectiveness.
