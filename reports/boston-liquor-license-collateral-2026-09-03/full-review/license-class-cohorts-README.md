# Boston source-label license cohorts

This offline mapping covers all **1,520 review license IDs**: **1,512 core alcohol licenses**, five separate BYOB records, and three unclear-category records. The IDs correspond to 1,530 of the 3,610 saved source rows and 49 exact license-type strings. The remaining 2,080 source rows are outside the existing review queue.

These are **analytic cohorts from source labels**, not legal findings about transferability, market purchases, acquisition routes, prices, ownership, or control. Assignments use no ownership fields. A complete class mapping does not mean those other reviews are complete.

## Cohorts

Primary cohorts are mutually exclusive. An airport label takes precedence over club, Common Victualler, and general-on-premises; `source_label_family` retains those secondary families.

| Source-label cohort | All review IDs | Core alcohol | Boundary |
| --- | ---: | ---: | ---: |
| Airport-labeled | 51 | 51 | 0 |
| Innholder / hotel-labeled | 82 | 82 | 0 |
| Retail / druggist-labeled | 306 | 305 | 1 |
| Club-labeled — no airport label | 47 | 47 | 0 |
| Producer / farmer-labeled | 30 | 30 | 0 |
| Common Victualler on-premises — no airport label | 968 | 968 | 0 |
| Other on-premises-labeled — no airport label | 29 | 29 | 0 |
| BYOB — separate scope | 5 | 0 | 5 |
| Unresolved source abbreviation | 2 | 0 | 2 |
| **Total** | **1,520** | **1,512** | **8** |

The 51 airport-labeled IDs retain families of 45 Common Victualler, five club, and one general-on-premises. Innholder labels are not a hotel ownership census. Hotel restaurants, arenas, stadiums, bars, and other venues may appear under Common Victualler or another class. A missing airport/hotel label does not prove the venue is an ordinary restaurant.

The retail/druggist cohort includes `LB-101303` (`Druggist`), which **remains an unclear-category boundary record**. `SPCMWA` remains unresolved for `LB-102883` and `LB-102890`; no expansion of that abbreviation is assumed. The five BYOB records retain their separate scope. The source typo `Famer-Brewery Pouring` is preserved exactly.

## Literal flags

Flags inspect `license_type` only. They are separate from venue cohorts and are not a legal transferability classification.

| Wording found in class label | License IDs |
| --- | ---: |
| Restricted or Restrict. | 182 |
| Unrestricted | 2 |
| Special Legislation | 10 |
| Ambiguous Rest abbreviation | 1 |
| Comm Spaces | 6 |

`Unrestricted` cannot match the `Restricted` flag. `Gen Prem All Alcohol Rest` (`LB-352398`, Institute of Contemporary Art) receives the ambiguous `Rest` flag, not a restricted flag. Special-legislation and community-space flags are independent; flag counts should not be summed as exclusive cohorts.

Absence of restriction wording is not proof of unrestricted transferability. For example, `LB-464491` has class `CV7 All Alc.` while its saved comments include “Special Legislation Restricted” and a same-location transfer condition. The JSON preserves this source-field mismatch example. Likewise, the class `CV7 All Alc Unrestricted 2024` does not establish whether a license was purchased or directly awarded. Acquisition route and purchase price remain unknown in this class-only artifact.

## Suggested comparison filters

Use **Source-label venue cohort**, **Source license family**, **Core alcohol / separate boundary records**, **Restriction wording in class label**, **Special Legislation wording in class label**, and **Exact source license type**. Keep restriction choices as literal restricted, literal unrestricted, ambiguous Rest, and no wording in class label; do not rename the last choice unrestricted.

For a restaurant-oriented comparison, show the Common Victualler cohort separately and offer explicit inclusion of other on-premises, airport, innholder, club, and producer cohorts. Show the selected denominator and retain unknown ownership separately. These comparisons can describe source-label composition; testing a price effect still requires actual transactions, acquisition routes, venue context, and ownership evidence.

## Provenance and regeneration

`license-class-cohorts.json` preserves every exact license ID, original class/category strings, scope, source-row IDs and raw-row hashes. It includes the complete 49-class whitelist, cohort counts, flags, limitations, and stable input hashes. `inventory-rows.json` selects the queue; `source-licenses.csv` verifies original class/category fields. `review-data.json` is checked only for the stable ID/class/scope/source-row projection, so ownership updates do not alter the mapping.

Run from the repository root:

```sh
uv run python reports/boston-liquor-license-collateral-2026-09-03/full-review/build_license_class_cohorts.py
```

The generator performs no network requests. It fails before writing if an unknown class, conflicting class/category/scope, unexpected license count, or inventory/source/review mismatch appears. Known opaque `SPCMWA` records are explicitly unresolved. The whitelist and output need deliberate review if the snapshot changes.
