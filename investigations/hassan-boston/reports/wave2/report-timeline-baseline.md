# Property ownership timeline — local baseline

This baseline contains 395 dated events across 62 property/context keys. It preserves all 147 assessment observations,200 existing permits and32 registry instruments, plus existing property-related court and development records. No new online searches were performed. It is a source chronology, not a completed legal title chain.

**Files:** `evidence/wave2/timeline-baseline/events.csv` follows the exact 25-column WAVE2 contract. `coverage-manifest.json` and `property-coverage.csv` expose gaps and aliases; `event-metrics.csv` keeps assessed values out of consideration/loan fields.

**Critical distinctions:** The corrected 1993 acquisition consideration is $1,925,000, replacing the erroneous earlier $1,725,000 reading. The two 2016 quitclaims state less than $100; numeric consideration stays blank. A mortgage grantee may be lender. FY years have year precision and are not assigned a fabricated January1 date. Current ownership/beneficial shares are not inferred from officer, assessment, permit, court pleading or index records.

**Unresolved joins:** 33Havre versus 31Havre is separate. The 1992 Four Seasons Place unit candidate is separate from the modern condominium parcel. Houssam mortgagee candidates and Talal unit-deed candidate remain unverified in capacity/identity. Family agreement claims remain under an unallocated case-context key rather than manufacturing property shares.

## Property-by-property chronology

### 141 Dorchester Avenue unit601

`US-MA-SUFFOLK:ADDRESS:BOSTON:141-DORCHESTER-AVENUE-UNIT601` — association group: `index_only_property_candidate`; join: `index_address_candidate_unjoined`.

- **2010-10-01 — mortgage_index_candidate**; HASSAN HOUSSAM; index_only_candidate. [SUFFOLK-DEEDS:46991/183](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Mortgage grantee may be lender; do not label borrower; recorded_date=2010-10-01; execution date not established unless separately stated. Release candidate48231/216 dated2011-08-04. Mortgage index grantee may denote mortgagee/lender; do not label Houssam as borrower. 

Outstanding: No original title deed reviewed in baseline; Read originals: 46991/183; Resolve parcel and party identity before assigning to a current holding.

### 143 West Canton Street unit1

`US-MA-SUFFOLK:ADDRESS:BOSTON:143-WEST-CANTON-STREET-UNIT1` — association group: `index_only_property_candidate`; join: `index_address_candidate_unjoined`.

- **2009-02-19 — foreclosure_deed_index_candidate**; HASSAN HOUSSAM; index_only_candidate. [SUFFOLK-DEEDS:44562/27](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Identity capacity and financing unresolved; recorded_date=2009-02-19; execution date not established unless separately stated. . 

Outstanding: No original title deed reviewed in baseline; Read originals: 44562/27; Resolve parcel and party identity before assigning to a current holding.

### 33 Havre Street

`US-MA-SUFFOLK:ADDRESS:BOSTON:33-HAVRE-STREET` — association group: `index_only_property_candidate`; join: `index_address_candidate_unjoined`.

- **2021-01-27 — deed_index_candidate**; HASSAN TAREK A; index_only_candidate. [SUFFOLK-DEEDS:64658/183](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Mortgage64658/186 same date; later deed64812/156; recorded_date=2021-01-27; execution date not established unless separately stated. . Index address is 33 Havre, not the current 31 Havre parcel; address discrepancy unresolved and properties are not merged. 

Outstanding: No original title deed reviewed in baseline; Read originals: 64658/183; Resolve parcel and party identity before assigning to a current holding; Do not merge33Havre with31Havre without original-document address bridge.

### 360 Newbury Street unit601

`US-MA-SUFFOLK:ADDRESS:BOSTON:360-NEWBURY-STREET-UNIT601` — association group: `index_only_property_candidate`; join: `index_address_candidate_unjoined`.

- **2025-12-03 — unit_deed_index_candidate**; HASSAN TALAL; index_only_candidate. [SUFFOLK-DEEDS:72170/29](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Homestead72170/34; identity unresolved; omit precise unit from public report; recorded_date=2025-12-03; execution date not established unless separately stated. . Talal person identity remains unresolved. Precise unit detail is an internal matching pivot, not a verified subject residence. 

Outstanding: No original title deed reviewed in baseline; Read originals: 72170/29; Resolve parcel and party identity before assigning to a current holding.

### Four Seasons Place unit 1001

`US-MA-SUFFOLK:ADDRESS:BOSTON:FOUR-SEASONS-PLACE-UNIT-1001` — association group: `index_only_property_candidate`; join: `index_address_candidate_unjoined`.

- **1992-03-03 — foreclosure_deed_index_candidate**; HASSAN ABDUL R; index_only_candidate. [SUFFOLK-DEEDS:17328/343](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Full-name expansion unresolved; recorded_date=1992-03-03; execution date not established unless separately stated. . HASSAN ABDUL R is not expanded to Abdul Rahman for this instrument. No automatic join to the modern 220 Boylston condominium from a shared unit number. 
- **1992-03-03 — mortgage_index_candidate**; HASSAN ABDUL R; index_only_candidate. [SUFFOLK-DEEDS:17329/1](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=First image attempted: Image is Unavailable; Viewer reports 29 pages; first page unavailable. Full identity, principal and lender unresolved.; recorded_date=1992-03-03; execution date not established unless separately stated. . HASSAN ABDUL R is not expanded to Abdul Rahman for this instrument. No automatic join to the modern 220 Boylston condominium from a shared unit number. 

Outstanding: No original title deed reviewed in baseline; Read originals: 17328/343, 17329/1; Resolve parcel and party identity before assigning to a current holding.

### 238 Lexington ST

`US-MA-SUFFOLK:PARCEL:0103178000` — association group: `tarek_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ANKIEWICZ STANLEY R. [BOSTONASSESS:FY2014:0103178000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 238LS LLC. [BOSTONASSESS:FY2021:0103178000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 238LS LLC. [BOSTONASSESS:FY2026:0103178000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **2020-06-26 — deed_index_candidate**; HASSAN TAREK A; index_only_candidate. [SUFFOLK-DEEDS:63244/72](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Mortgage63244/75 same date; deed63420/121 on2020-07-24; recorded_date=2020-06-26; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 

Outstanding: No original title deed reviewed in baseline; Read originals: 63244/72; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 334 Meridian ST

`US-MA-SUFFOLK:PARCEL:0103648004` — association group: `tarek_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — DONATO FRANCES. [BOSTONASSESS:FY2014:0103648004](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — 334 MERIDIAN ST LLC. [BOSTONASSESS:FY2026:0103648004](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **2023-10-03 — deed_index_candidate**; HASSAN TAREK ALI; index_only_candidate. [SUFFOLK-DEEDS:69490/332](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Mortgage69491/1 same date; deed69706/3 on2023-12-08; recorded_date=2023-10-03; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 

Outstanding: No original title deed reviewed in baseline; Read originals: 69490/332; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 31 Havre ST

`US-MA-SUFFOLK:PARCEL:0105622000` — association group: `tarek_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — BROGNA ALBERT H. [BOSTONASSESS:FY2014:0105622000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — 31 HAVRE ST LLC. [BOSTONASSESS:FY2026:0105622000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 18 Meridian ST

`US-MA-SUFFOLK:PARCEL:0105676000` — association group: `tarek_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — MAYA CECILIA. [BOSTONASSESS:FY2014:0105676000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — MAVERICK SQUARE LLC. [BOSTONASSESS:FY2019:0105676000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — MAVERICK SQUARE LLC. [BOSTONASSESS:FY2021:0105676000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — MAVERICK SQUARE LLC. [BOSTONASSESS:FY2026:0105676000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 143 Meridian ST

`US-MA-SUFFOLK:PARCEL:0105898000` — association group: `tarek_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — BETANCOURT LEONEL. [BOSTONASSESS:FY2014:0105898000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 143-145 MERIDIAN STREET LLC. [BOSTONASSESS:FY2021:0105898000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 143-145 MERIDIAN STREET LLC. [BOSTONASSESS:FY2026:0105898000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 31 Dwight ST

`US-MA-SUFFOLK:PARCEL:0305735000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — DWIGHT TOWNHOUSE CONDO TR. [BOSTONASSESS:FY2014:0305735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — DWIGHT TOWNHOUSE CONDO TR. [BOSTONASSESS:FY2019:0305735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — DWIGHT TOWNHOUSE CONDO TR. [BOSTONASSESS:FY2021:0305735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — DWIGHT TOWNHOUSE CONDO TR. [BOSTONASSESS:FY2026:0305735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 1180 Washington ST

`US-MA-SUFFOLK:PARCEL:0306395010` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 1 observations from 2010-03-04 through 2010-03-04. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 1180 Washington ST unit 501

`US-MA-SUFFOLK:PARCEL:0306395182` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — HACIN DAVID J. [BOSTONASSESS:FY2014:0306395182](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 1200 WASHINGTON STREET. [BOSTONASSESS:FY2019:0306395182](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 1200 WASHINGTON STREET. [BOSTONASSESS:FY2021:0306395182](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 1200 WASHINGTON STREET. [BOSTONASSESS:FY2026:0306395182](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 81 WARREN AV

`US-MA-SUFFOLK:PARCEL:0400130000` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ROBERTSON NIEL. [BOSTONASSESS:FY2014:0400130000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 81 WARREN AVENUE LLC. [BOSTONASSESS:FY2021:0400130000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — NAPOLITANO ANGELA. [BOSTONASSESS:FY2026:0400130000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 1 observations from 2021-04-21 through 2021-04-21. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 83 Warren AV

`US-MA-SUFFOLK:PARCEL:0400131000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 3 observations from 2010-11-30 through 2011-09-16. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 93 Warren AV

`US-MA-SUFFOLK:PARCEL:0400136000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 4 observations from 2011-04-07 through 2012-09-21. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 95 Warren AV

`US-MA-SUFFOLK:PARCEL:0400137000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 4 observations from 2011-04-07 through 2012-09-21. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 77 Montgomery ST

`US-MA-SUFFOLK:PARCEL:0400327000` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — RIOLO JUDITH A. [BOSTONASSESS:FY2014:0400327000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 77 MONTGOMERY STREET LLC. [BOSTONASSESS:FY2021:0400327000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 77 MONTGOMERY STREET LLC. [BOSTONASSESS:FY2026:0400327000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 183 W Canton ST

`US-MA-SUFFOLK:PARCEL:0400349000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 2 observations from 2011-05-23 through 2011-08-31. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 201 W BROOKLINE ST unit 203

`US-MA-SUFFOLK:PARCEL:0400450012` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2026** — 201 WEST BROOKLINE STREET UNIT 203 LLC. [BOSTONASSESS:FY2026:0400450012](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 201 W BROOKLINE ST unit PS-3

`US-MA-SUFFOLK:PARCEL:0400450021` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2026** — 201 WEST BROOKLINE STREET UNIT 203 LLC. [BOSTONASSESS:FY2026:0400450021](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 201 W BROOKLINE ST unit PS-4

`US-MA-SUFFOLK:PARCEL:0400450022` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2026** — 201 WEST BROOKLINE STREET UNIT 203 LLC. [BOSTONASSESS:FY2026:0400450022](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 85 Pembroke ST

`US-MA-SUFFOLK:PARCEL:0400484000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 4 observations from 2011-02-04 through 2012-05-29. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 85 Pembroke ST unit 1

`US-MA-SUFFOLK:PARCEL:0400484002` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — HASSAN HOUSSAM ALI. [BOSTONASSESS:FY2014:0400484002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — SCHROEDER JAMES. [BOSTONASSESS:FY2026:0400484002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 85 Pembroke ST unit PS-1

`US-MA-SUFFOLK:PARCEL:0400484006` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — HASSAN HOUSSAM ALI. [BOSTONASSESS:FY2014:0400484006](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — SCHROEDER JAMES. [BOSTONASSESS:FY2026:0400484006](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 95 Pembroke ST

`US-MA-SUFFOLK:PARCEL:0400489000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 4 observations from 2010-05-04 through 2011-04-21. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 121 Pembroke ST

`US-MA-SUFFOLK:PARCEL:0400502000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ONE 121 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2014:0400502000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — ONE 121 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2026:0400502000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 4 observations from 2012-03-08 through 2013-07-05. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 196 W Brookline ST

`US-MA-SUFFOLK:PARCEL:0400519000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — WEBSTER MARGARET L ETAL. [BOSTONASSESS:FY2014:0400519000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 196 WEST BROOKLINE TOWNHOUSE. [BOSTONASSESS:FY2019:0400519000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 196 WEST BROOKLINE TOWNHOUSE. [BOSTONASSESS:FY2021:0400519000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 196 WEST BROOKLINE TOWNHOUSE. [BOSTONASSESS:FY2026:0400519000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 2 observations from 2014-01-23 through 2014-09-18. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 174 W Brookline ST

`US-MA-SUFFOLK:PARCEL:0400530000` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — MOONEY DAVID E. [BOSTONASSESS:FY2014:0400530000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 174 WEST BROOKLINE LLC. [BOSTONASSESS:FY2019:0400530000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 174 WEST BROOKLINE LLC. [BOSTONASSESS:FY2021:0400530000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 174 WEST BROOKLINE LLC. [BOSTONASSESS:FY2026:0400530000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 36 Holyoke ST

`US-MA-SUFFOLK:PARCEL:0400735000` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ERNSTOFF STEVEN E. [BOSTONASSESS:FY2014:0400735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 36 HOLYOKE TOWNHOUSE LLC. [BOSTONASSESS:FY2019:0400735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 36 HOLYOKE TOWNHOUSE LLC. [BOSTONASSESS:FY2021:0400735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 36 HOLYOKE TOWNHOUSE LLC. [BOSTONASSESS:FY2026:0400735000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 14 Holyoke ST

`US-MA-SUFFOLK:PARCEL:0400746000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — FORD THOMAS E 3RD ETAL. [BOSTONASSESS:FY2014:0400746000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — 14 HOLYOKE STREET CONDOMINIUM TRUST. [BOSTONASSESS:FY2026:0400746000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 5 observations from 2021-07-01 through 2023-07-11. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 28 BRADDOCK PK

`US-MA-SUFFOLK:PARCEL:0400779000` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — TWENTY 8 BRADDOCK TOWNHOUSE. [BOSTONASSESS:FY2014:0400779000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 28 BRADDOCK TOWNHOUSE LLC. [BOSTONASSESS:FY2021:0400779000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 28 BRADDOCK TOWNHOUSE LLC. [BOSTONASSESS:FY2026:0400779000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 18 Claremont PK

`US-MA-SUFFOLK:PARCEL:0402517000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 1 observations from 2017-01-23 through 2017-01-23. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 18 CLAREMONT PK unit 1

`US-MA-SUFFOLK:PARCEL:0402517002` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2019** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2019:0402517002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2021:0402517002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2026:0402517002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 18 CLAREMONT PK unit PS-1

`US-MA-SUFFOLK:PARCEL:0402517005` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2019** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2019:0402517005](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2021:0402517005](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 18 CLAREMONT PARK LLC. [BOSTONASSESS:FY2026:0402517005](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 9 Wellington ST

`US-MA-SUFFOLK:PARCEL:0402538000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 5 observations from 2010-09-15 through 2013-07-30. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 21 Rutland SQ

`US-MA-SUFFOLK:PARCEL:0402740000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — STEPHENSON THOMAS P. [BOSTONASSESS:FY2014:0402740000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 21 RUTLAND SQUARE LLC. [BOSTONASSESS:FY2019:0402740000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 21 RUTLAND SQUARE LLC. [BOSTONASSESS:FY2021:0402740000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 21 RUTLAND SQUARE LLC. [BOSTONASSESS:FY2026:0402740000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **2017-06-16 — mortgage_index_candidate**; HASSAN HOUSSAM; index_only_candidate. [SUFFOLK-DEEDS:58093/179](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Potential lending activity; capacity not read; recorded_date=2017-06-16; execution date not established unless separately stated. Release candidate58465/84 dated2017-08-31. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Mortgage index grantee may denote mortgagee/lender; do not label Houssam as borrower. 
- **Municipal permit history:** 1 observations from 2019-03-29 through 2019-03-29. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Read originals: 58093/179; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 149 W Newton ST

`US-MA-SUFFOLK:PARCEL:0402822000` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — LESNER WILLIAM. [BOSTONASSESS:FY2014:0402822000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 149 WEST NEWTON STREET LLC. [BOSTONASSESS:FY2021:0402822000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — WILLIAMSON STEPHEN. [BOSTONASSESS:FY2026:0402822000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 3 observations from 2022-06-24 through 2023-09-14. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 167 W Newton ST

`US-MA-SUFFOLK:PARCEL:0402831000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 1 observations from 2020-07-10 through 2020-07-10. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 126 Pembroke ST

`US-MA-SUFFOLK:PARCEL:0402845000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ONE 26 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2014:0402845000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 126 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2019:0402845000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 126 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2021:0402845000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 126 PEMBROKE TOWNHOUSE. [BOSTONASSESS:FY2026:0402845000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 3 observations from 2013-01-31 through 2014-06-25. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 126 Pembroke ST unit 2

`US-MA-SUFFOLK:PARCEL:0402845004` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2019** — 126 PEMBROKE TOWNHOUSE LLC. [BOSTONASSESS:FY2019:0402845004](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 126 PEMBROKE TOWNHOUSE LLC. [BOSTONASSESS:FY2021:0402845004](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — PEMBROKE SVR PROPERTIES LLC. [BOSTONASSESS:FY2026:0402845004](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 126 Pembroke ST unit PS- UNIT 2

`US-MA-SUFFOLK:PARCEL:0402845008` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2019** — 126 PEMBROKE TOWNHOUSE LLC. [BOSTONASSESS:FY2019:0402845008](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 126 PEMBROKE TOWNHOUSE LLC. [BOSTONASSESS:FY2021:0402845008](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — PEMBROKE SVR PROPERTIES LLC. [BOSTONASSESS:FY2026:0402845008](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 400 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501159000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2008:0501159000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2014:0501159000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 392-402 BOYLSTON STREET. [BOSTONASSESS:FY2019:0501159000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2021:0501159000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2026:0501159000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1993-01-15 — deed_recorded**; Boylston Boston Corporation → Hicham Ali Hassan; Abdul Rahman Ali Hassan; Zouhair Ali Hassan; consideration $1,925,000; original_complete_review. [SUFFOLK-DEEDS:17988/312](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=all three original pages read; execution_date=1992-12-23; acknowledgment_date=1992-12-23; recorded_date=1993-01-15; recording_time=13:47; document_number=357. Page 1 describes 392–394 and 396–398 Boylston; page 2 describes 400–402 Boylston and references predecessor deed 17463/182 dated 1992-05-07. Current title and source of purchase funds are not established by this acquisition alone. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 3 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. Corrected original-image reading: consideration $1,925,000; handwritten words One Million Nine Hundred Twenty Five Thousand Dollars replace crossed-out typed Two Million Dollars. The full review is recorded in evidence/wave2/suffolk/scan-observations.md and audited finding 15578. The trust beneficiary schedule remains separate from this deed. 
- **2026-02-18 — demolition_permit**; Carlos Ferreira; official_permit_observation. [BOSTONPERMIT:SF1790036](https://data.boston.gov/dataset/approved-building-permits/resource/6ddcd912-32a0-43df-9908-63574f8c7e77?filters=permitnumber%3ASF1790036). issued_timestamp_raw=2026-02-18T15:19:17; status=Open; declared_work_valuation_raw=$100,000.00; worktype=RAZE; Applicant is not necessarily owner. Permit issuance/status does not prove work completion. Address labels can span multiple parcels; only the source parcel_id is joined.
- **Municipal permit history:** 4 observations from 2018-07-13 through 2025-04-15. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: Complete acquisition deed reviewed; intervening instruments, beneficiary schedule, and current recorder search remain needed; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 396 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501160000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2008:0501160000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2014:0501160000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 392-402 BOYLSTON STREET. [BOSTONASSESS:FY2019:0501160000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2021:0501160000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2026:0501160000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1993-01-15 — deed_recorded**; Boylston Boston Corporation → Hicham Ali Hassan; Abdul Rahman Ali Hassan; Zouhair Ali Hassan; consideration $1,925,000; original_complete_review. [SUFFOLK-DEEDS:17988/312](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=all three original pages read; execution_date=1992-12-23; acknowledgment_date=1992-12-23; recorded_date=1993-01-15; recording_time=13:47; document_number=357. Page 1 describes 392–394 and 396–398 Boylston; page 2 describes 400–402 Boylston and references predecessor deed 17463/182 dated 1992-05-07. Current title and source of purchase funds are not established by this acquisition alone. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 3 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. Corrected original-image reading: consideration $1,925,000; handwritten words One Million Nine Hundred Twenty Five Thousand Dollars replace crossed-out typed Two Million Dollars. The full review is recorded in evidence/wave2/suffolk/scan-observations.md and audited finding 15578. The trust beneficiary schedule remains separate from this deed. 
- **2025-10-10 — demolition_permit**; Carlos Ferreira; official_permit_observation. [BOSTONPERMIT:SF1742941](https://data.boston.gov/dataset/approved-building-permits/resource/6ddcd912-32a0-43df-9908-63574f8c7e77?filters=permitnumber%3ASF1742941). issued_timestamp_raw=2025-10-10T19:43:45; status=Open; declared_work_valuation_raw=$100,000.00; worktype=RAZE; Applicant is not necessarily owner. Permit issuance/status does not prove work completion. Address labels can span multiple parcels; only the source parcel_id is joined.
- **Municipal permit history:** 3 observations from 2018-01-25 through 2018-08-06. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: Complete acquisition deed reviewed; intervening instruments, beneficiary schedule, and current recorder search remain needed; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 392 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501161000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2008:0501161000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2014:0501161000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 392-402 BOYLSTON STREET. [BOSTONASSESS:FY2019:0501161000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2021:0501161000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 392-402 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2026:0501161000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1993-01-15 — deed_recorded**; Boylston Boston Corporation → Hicham Ali Hassan; Abdul Rahman Ali Hassan; Zouhair Ali Hassan; consideration $1,925,000; original_complete_review. [SUFFOLK-DEEDS:17988/312](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=all three original pages read; execution_date=1992-12-23; acknowledgment_date=1992-12-23; recorded_date=1993-01-15; recording_time=13:47; document_number=357. Page 1 describes 392–394 and 396–398 Boylston; page 2 describes 400–402 Boylston and references predecessor deed 17463/182 dated 1992-05-07. Current title and source of purchase funds are not established by this acquisition alone. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 3 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. Corrected original-image reading: consideration $1,925,000; handwritten words One Million Nine Hundred Twenty Five Thousand Dollars replace crossed-out typed Two Million Dollars. The full review is recorded in evidence/wave2/suffolk/scan-observations.md and audited finding 15578. The trust beneficiary schedule remains separate from this deed. 
- **2016-07-19 — deed_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:56448/321](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Read grantee consideration capacity; recorded_date=2016-07-19; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **Municipal permit history:** 2 observations from 2018-07-13 through 2018-07-31. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: Complete acquisition deed reviewed; intervening instruments, beneficiary schedule, and current recorder search remain needed; Read originals: 56448/321; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 384 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501162000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — HASSAN HICHAM ALI. [BOSTONASSESS:FY2014:0501162000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 384 BOYLSTON STREET. [BOSTONASSESS:FY2019:0501162000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 384 BOYLSTON STREET  REALTY LLC. [BOSTONASSESS:FY2021:0501162000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 384 BOYLSTON STREET  REALTY LLC. [BOSTONASSESS:FY2026:0501162000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **2010-06-16 — court_order**; Participants: Andrew Fienberg, trustee of Aidee Realty Trust; Hicham Ali Hassan; judicial_text_reviewed_property_join_candidate. [https://www.masscasesarchive.com/masscases.com/cases/app/77/77massappct901.html](https://www.masscasesarchive.com/masscases.com/cases/app/77/77massappct901.html). 2010 appellate decision ordered Boylston property conveyance following $4.5 million offer Fienberg v Hassan, 77 Mass. App. Ct. 901, 09-P-1545, June16 2010. Andrew Fienberg as trustee of Aidee Realty Trust owned 382-390 Boylston; Rattlesnake Bar & Grill Inc held right of first refusal. Opinion records May14 2008 Hassan offer of $4.5m with $500k deposit paid with offer, accepted by Fienberg, and May22 purchase-and-sale agreement. Appeals Court reversed trial judgment because Rattlesnake offer materially differed in timing and remanded to order conveyance to Hassan. This is a contract/judicial-order record; deed and source of deposit/final funds remain to be traced. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Court address is382–390 Boylston; correspondence to assessment384–390 is an address-range candidate until the deed/legal description is reviewed.
- **2016-07-19 — deed_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:56448/317](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Read grantee consideration capacity; recorded_date=2016-07-19; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2026-02-11 — demolition_permit**; Carlos Ferreira; official_permit_observation. [BOSTONPERMIT:SF1805998](https://data.boston.gov/dataset/approved-building-permits/resource/6ddcd912-32a0-43df-9908-63574f8c7e77?filters=permitnumber%3ASF1805998). issued_timestamp_raw=2026-02-11T16:50:25; status=Open; declared_work_valuation_raw=$200,000.00; worktype=RAZE; Applicant is not necessarily owner. Permit issuance/status does not prove work completion. Address labels can span multiple parcels; only the source parcel_id is joined.
- **Municipal permit history:** 4 observations from 2010-10-14 through 2018-07-27. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Read originals: 56448/317; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 372 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501164000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN HICHAM A. [BOSTONASSESS:FY2008:0501164000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — HASSAN HICHAM A. [BOSTONASSESS:FY2014:0501164000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 376 BOYLSTON STREET REALTY. [BOSTONASSESS:FY2019:0501164000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 376 BOYLSTON STREET REALTY  LLC. [BOSTONASSESS:FY2021:0501164000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 376 BOYLSTON STREET REALTY  LLC. [BOSTONASSESS:FY2026:0501164000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1995-04-03 — deed_index_candidate**; HASSAN HICHAM A; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:19678/333](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Acquisition counterpart of mortgage19679/1; recorded_date=1995-04-03; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **1995-04-03 — mortgage_recorded**; Hicham Ali Hassan; Zouhair Ali Hassan → Berkshire Life Insurance Company; mortgage face amount $1,000,000; original_partial_review. [SUFFOLK-DEEDS:19679/1](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=original page1 read and saved; 19pages; historical face amount not balance; recorded_date=1995-04-03; execution date not established unless separately stated. Index references27659/170 RELEASE2001. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2016-08-17 — deed_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:56617/271](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Read full instrument; recorded_date=2016-08-17; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **Municipal permit history:** 31 observations from 2011-09-15 through 2025-06-03. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Read originals: 19678/333, 56617/271; Assessment snapshots do not fill title intervals or establish beneficial shares; Berkshire release27659/170 unread; acquisition19678/333 and2016transfer56617/271 originals needed.

### 220 Boylston ST unit 1001

`US-MA-SUFFOLK:PARCEL:0501185054` — association group: `hicham_trust_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2008:0501185054](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2014:0501185054](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — ALI HASSAN HICHAM. [BOSTONASSESS:FY2019:0501185054](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 400 BOYLSTON STREET  REALTY TRUST. [BOSTONASSESS:FY2021:0501185054](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 400 BOYLSTON STREET  REALTY TRUST. [BOSTONASSESS:FY2026:0501185054](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 419 Boylston ST

`US-MA-SUFFOLK:PARCEL:0501234000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN ZOUHAIR A. [BOSTONASSESS:FY2008:0501234000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — HASSAN ZOUHAIR A. [BOSTONASSESS:FY2014:0501234000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 419 BOYLSTON STREET REALTY. [BOSTONASSESS:FY2019:0501234000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 419 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2021:0501234000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 419 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2026:0501234000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1996-03-20 — deed_index_candidate**; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:20428/305](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Acquisition deed followup; recorded_date=1996-03-20; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2007-05-15 — lien_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:41799/224](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Related index liens41799/226,/285,/287; recorded_date=2007-05-15; execution date not established unless separately stated. Unresolved. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2016-08-17 — deed_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:56617/263](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Read full instrument; recorded_date=2016-08-17; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2026-05-14 — development_approval**; 419 Boylston Street Realty LLC; official_board_document_reviewed. [BPDABOARD:8308:2026-05-14](https://bpda.box.com/s/2xynvi7uzas3muawzc3u2091euhsylh8). Approved plan:41 rental units,7 income-restricted; development_cost_estimate_usd=7761888; PILOT_application_date=2025-08-29. Plan webpage still describes44 units; prefer dated approved document. Approval is not evidence of construction completion, executed PILOT agreement, or funded financing.
- **Municipal permit history:** 40 observations from 2010-09-22 through 2026-08-17. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Read originals: 20428/305, 41799/224, 56617/263; Assessment snapshots do not fill title intervals or establish beneficial shares; 419:acquisition20428/305;transfer56617/263;historical lien releases;executed PILOT agreement and project financing.

### 18 Brimmer ST

`US-MA-SUFFOLK:PARCEL:0502425000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN ZOUHAIR A TS. [BOSTONASSESS:FY2008:0502425000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — HASSAN ZOUHAIR A TS. [BOSTONASSESS:FY2014:0502425000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — HASSAN RESIDENTIAL. [BOSTONASSESS:FY2019:0502425000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — HASSAN RESIDENTIAL. [BOSTONASSESS:FY2021:0502425000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — HASSAN RESIDENTIAL. [BOSTONASSESS:FY2026:0502425000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1997-12-02 — trust_agreement_index_candidate**; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:21956/113](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index plus2016deed reference; Trust dated1997-12-01; read beneficiaries and trustee provisions; recorded_date=1997-12-02; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **1997-12-02 — foreclosure_deed_recorded**; Institutional Asset LLC → Zouhair Ali Hassan; consideration $325,000; original_partial_review. [SUFFOLK-DEEDS:21956/120](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=original page1 read; 4pages; consideration not total acquisition economics; recorded_date=1997-12-02; execution date not established unless separately stated. Subject to1994mortgage19143/176 andtaxes/liens. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2000-08-22 — lien_index_candidate**; HASSAN ZOUHAIR; index_only_candidate. [SUFFOLK-DEEDS:25267/67](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; No outstanding-liability claim; recorded_date=2000-08-22; execution date not established unless separately stated. Unresolved. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2003-11-17 — lien_index_candidate**; HASSAN ZOUHAIR; index_only_candidate. [SUFFOLK-DEEDS:33269/285](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; No outstanding-liability claim; recorded_date=2003-11-17; execution date not established unless separately stated. Unresolved. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2003-12-19 — lien_index_candidate**; HASSAN ZOUHAIR; index_only_candidate. [SUFFOLK-DEEDS:33486/4](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; No outstanding-liability claim; recorded_date=2003-12-19; execution date not established unless separately stated. Unresolved. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2016-08-17 — deed_recorded**; Hicham Ali Hassan → Hassan Residential Properties LLC; original_partial_review. [SUFFOLK-DEEDS:56617/279](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=original page1 read; Trust21956/113; index100.00 differs from image less than100; recorded_date=2016-08-17; execution date not established unless separately stated. Prior foreclosure21956/120. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. consideration_comparator=less_than; consideration_upper_bound_usd=100; exact consideration unknown, numeric consideration field intentionally blank. 
- **Municipal permit history:** 4 observations from 2012-04-18 through 2018-01-29. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: Reviewed deeds are partial-page observations; complete legal descriptions, execution dates, intervening instruments, and current recorder search remain needed; Read originals: 21956/113, 25267/67, 33269/285, 33486/4; Assessment snapshots do not fill title intervals or establish beneficial shares; Brimmer:21956/113 trust;19143/176 senior mortgage;21879/264 foreclosing mortgage; remaining21956/120 pages; lien releases.

### 33 Exeter ST

`US-MA-SUFFOLK:PARCEL:0503202000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — BOYLSTON ST PROPERTIES INC. [BOSTONASSESS:FY2008:0503202000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — BOYLSTON ST PROPERTIES INC. [BOSTONASSESS:FY2014:0503202000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 711 BOYLSTON STREET REALTY. [BOSTONASSESS:FY2019:0503202000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 711 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2021:0503202000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 711 BOYLSTON STREET REALTY LLC. [BOSTONASSESS:FY2026:0503202000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 50 observations from 2010-08-12 through 2026-04-16. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 218 NEWBURY ST

`US-MA-SUFFOLK:PARCEL:0503224000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN ZOUHAIR ALI. [BOSTONASSESS:FY2008:0503224000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — HASSAN ZOUHAIR ALI. [BOSTONASSESS:FY2014:0503224000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 216-218 NEWBURY STREET. [BOSTONASSESS:FY2019:0503224000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 216-218 NEWBURY STREET REALTY LLC. [BOSTONASSESS:FY2021:0503224000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 216-218 NEWBURY STREET REALTY LLC. [BOSTONASSESS:FY2026:0503224000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1996-06-10 — deed_index_candidate**; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:20630/164](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index plus later deed reference; Later deed identifies216 and218; executed1996-06-05; recorded_date=1996-06-10; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. execution_date=1996-06-05 as cited by 2016 deed56617/267; two-parcel scope is documented in that later deed reference. 
- **2016-08-17 — deed_recorded**; Hicham Ali Hassan → 216-218 Newbury Street Realty LLC; original_partial_review. [SUFFOLK-DEEDS:56617/267](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=original page1 read; Trust dated1996-05-24 at20592/119; previous deed20630/164; recorded_date=2016-08-17; execution date not established unless separately stated. Attachment72957/242 recorded2026-07-01. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. consideration_comparator=less_than; consideration_upper_bound_usd=100; exact consideration unknown, numeric consideration field intentionally blank. 
- **2022-10-12 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://masslawyersweekly.com/wp-content/blogs.dir/1/files/2022/12/09-097-22.pdf](https://masslawyersweekly.com/wp-content/blogs.dir/1/files/2022/12/09-097-22.pdf). 2022 court granted Tivoli summary judgment in Newbury retail-lease termination dispute Suffolk Superior 21-205-BLS1 / 2184CV00205-BLS1, 216-218 Newbury Street Realty LLC v Tivoli Audio Inc. Court describes Newbury as owner of 216-218 Newbury Street and January2019 lease of just under2,000 square feet for five years/two months. Lease permitted termination if 2020 premises gross sales did not exceed $500,000; Tivoli invoked option October20 2020 and vacated March31 2021. Newbury sued January2021, alleging sales exceeded threshold. Judge Peter Krupp denied Newbury Rule56(f) request, found no adequate showing that further evidence probably existed and no substantive opposition to Tivoli summary judgment; judgment ordered for Tivoli. This judicial order concerns the LLC, not a personal judgment against Hicham. Full nine-page opinion read via browser-source extraction; direct PDF request returned403. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2023-07-17 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://www.nutter.com/assets/htmldocuments/newbury%20vs.%20tivoli.pdf](https://www.nutter.com/assets/htmldocuments/newbury%20vs.%20tivoli.pdf). 2023 judgment awarded Tivoli security deposit, fees and interest after court found LLC claims frivolous Same Suffolk Superior 21-205-BLS1 case. Judge Krupp found Newbury claims, defenses and setoff wholly insubstantial, frivolous and not advanced in good faith under G.L.c231 §6F; this is a judicial finding, not merely a tenant allegation. Final judgment directed payment of $58,548 security deposit plus interest at18% from May10 2021 through judgment and continuing on that principal until paid, plus $241,620.30 legal fees/expenses/costs. Court declared Tivoli satisfied termination conditions. Award is against 216-218 Newbury Street Realty LLC; does not establish Hicham personal liability or whether amounts were later paid. Seven-page primary opinion obtained from counsel website and fully read. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2025-07-25 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://masslawyersweekly.com/files/2025/08/09-111-25.pdf](https://masslawyersweekly.com/files/2025/08/09-111-25.pdf). 2025 order denied Newbury relief from judgment and added $100,000 in Tivoli legal fees Same Suffolk Superior 21-205-BLS1 case. Judge Krupp denied Newbury December21 2023 Rule60(b) motion as untimely and because excusable neglect was not established; new counsel had criticized earlier counsel handling of summary judgment. Court reduced Tivoli additional-fee request of $133,652.70 to $100,000, finding parts of the fee applications duplicative and excessive, and ordered amendment of the judgment. This is an addition to the2023 award, not a separate debtor or proof of remaining collectible balance. Five-page opinion fully read via browser extraction; direct PDF request returned403. Deeds agent separately verified June2026 writ of attachment in the same docket, amount $405,000; attachment should not be added to these overlapping judgment amounts. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2026-07-01 — attachment_recorded**; 216-218 Newbury Street Realty LLC → Tivoli Audio Inc.; original_complete_review. [SUFFOLK-DEEDS:72957/242](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=both original pages read; 2184CV00205-BLS1; approved2026-06-29; issued2026-06-30; sheriff attaches2026-07-01 at10:40am; recorded_date=2026-07-01; execution date not established unless separately stated. No later release search completed. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. attachment_amount_usd=405000; approval_date=2026-06-29; issuance_date=2026-06-30; sheriff_attachment=2026-07-01 10:40; overlaps underlying court awards, not an additional debt. 
- **Municipal permit history:** 2 observations from 2011-04-08 through 2011-05-25. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: Reviewed deeds are partial-page observations; complete legal descriptions, execution dates, intervening instruments, and current recorder search remain needed; Read originals: 20630/164; Assessment snapshots do not fill title intervals or establish beneficial shares; Newbury:trust20592/119;acquisition20630/164;mortgage20630/170;financing20630/196;certificate56617/269;attachment72957/242 satisfaction and updated court balance.

### 216 NEWBURY ST

`US-MA-SUFFOLK:PARCEL:0503225000` — association group: `hicham_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN ZOUHAIR ALI. [BOSTONASSESS:FY2008:0503225000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — HASSAN ZOUHAIR ALI. [BOSTONASSESS:FY2014:0503225000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 216-218 NEWBURY STREET. [BOSTONASSESS:FY2019:0503225000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 216-218 NEWBURY STREET  REALTY LLC. [BOSTONASSESS:FY2021:0503225000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 216-218 NEWBURY STREET  REALTY LLC. [BOSTONASSESS:FY2026:0503225000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **1996-06-10 — deed_index_candidate**; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:20630/164](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index plus later deed reference; Later deed identifies216 and218; executed1996-06-05; recorded_date=1996-06-10; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. execution_date=1996-06-05 as cited by 2016 deed56617/267; two-parcel scope is documented in that later deed reference. 
- **1996-06-10 — mortgage_index_candidate**; HASSAN ZOUHAIR A; index_only_candidate. [SUFFOLK-DEEDS:20630/170](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Acquisition financing followup; recorded_date=1996-06-10; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **1996-06-10 — financing_statement_index_candidate**; HASSAN ZOUHAIR; index_only_candidate. [SUFFOLK-DEEDS:20630/196](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Read collateral secured party continuation termination; recorded_date=1996-06-10; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 
- **2016-08-17 — deed_recorded**; Hicham Ali Hassan → 216-218 Newbury Street Realty LLC; original_partial_review. [SUFFOLK-DEEDS:56617/267](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=original page1 read; Trust dated1996-05-24 at20592/119; previous deed20630/164; recorded_date=2016-08-17; execution date not established unless separately stated. Attachment72957/242 recorded2026-07-01. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. consideration_comparator=less_than; consideration_upper_bound_usd=100; exact consideration unknown, numeric consideration field intentionally blank. 
- **2022-10-12 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://masslawyersweekly.com/wp-content/blogs.dir/1/files/2022/12/09-097-22.pdf](https://masslawyersweekly.com/wp-content/blogs.dir/1/files/2022/12/09-097-22.pdf). 2022 court granted Tivoli summary judgment in Newbury retail-lease termination dispute Suffolk Superior 21-205-BLS1 / 2184CV00205-BLS1, 216-218 Newbury Street Realty LLC v Tivoli Audio Inc. Court describes Newbury as owner of 216-218 Newbury Street and January2019 lease of just under2,000 square feet for five years/two months. Lease permitted termination if 2020 premises gross sales did not exceed $500,000; Tivoli invoked option October20 2020 and vacated March31 2021. Newbury sued January2021, alleging sales exceeded threshold. Judge Peter Krupp denied Newbury Rule56(f) request, found no adequate showing that further evidence probably existed and no substantive opposition to Tivoli summary judgment; judgment ordered for Tivoli. This judicial order concerns the LLC, not a personal judgment against Hicham. Full nine-page opinion read via browser-source extraction; direct PDF request returned403. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2023-07-17 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://www.nutter.com/assets/htmldocuments/newbury%20vs.%20tivoli.pdf](https://www.nutter.com/assets/htmldocuments/newbury%20vs.%20tivoli.pdf). 2023 judgment awarded Tivoli security deposit, fees and interest after court found LLC claims frivolous Same Suffolk Superior 21-205-BLS1 case. Judge Krupp found Newbury claims, defenses and setoff wholly insubstantial, frivolous and not advanced in good faith under G.L.c231 §6F; this is a judicial finding, not merely a tenant allegation. Final judgment directed payment of $58,548 security deposit plus interest at18% from May10 2021 through judgment and continuing on that principal until paid, plus $241,620.30 legal fees/expenses/costs. Court declared Tivoli satisfied termination conditions. Award is against 216-218 Newbury Street Realty LLC; does not establish Hicham personal liability or whether amounts were later paid. Seven-page primary opinion obtained from counsel website and fully read. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2025-07-25 — court_order**; Participants: 216-218 Newbury Street Realty LLC; Tivoli Audio Inc.; judicial_text_reviewed. [https://masslawyersweekly.com/files/2025/08/09-111-25.pdf](https://masslawyersweekly.com/files/2025/08/09-111-25.pdf). 2025 order denied Newbury relief from judgment and added $100,000 in Tivoli legal fees Same Suffolk Superior 21-205-BLS1 case. Judge Krupp denied Newbury December21 2023 Rule60(b) motion as untimely and because excusable neglect was not established; new counsel had criticized earlier counsel handling of summary judgment. Court reduced Tivoli additional-fee request of $133,652.70 to $100,000, finding parts of the fee applications duplicative and excessive, and ordered amendment of the judgment. This is an addition to the2023 award, not a separate debtor or proof of remaining collectible balance. Five-page opinion fully read via browser extraction; direct PDF request returned403. Deeds agent separately verified June2026 writ of attachment in the same docket, amount $405,000; attachment should not be added to these overlapping judgment amounts. Judicial order is not a recorded deed, evidence of payment, or current debt balance. Same court action affects both Newbury parcels; any award must be counted once, never once per property.
- **2026-07-01 — attachment_recorded**; 216-218 Newbury Street Realty LLC → Tivoli Audio Inc.; original_complete_review. [SUFFOLK-DEEDS:72957/242](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=both original pages read; 2184CV00205-BLS1; approved2026-06-29; issued2026-06-30; sheriff attaches2026-07-01 at10:40am; recorded_date=2026-07-01; execution date not established unless separately stated. No later release search completed. Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. Shared instrument covering 2 property events; transaction amounts must be deduplicated by instrument_id, not summed across rows. attachment_amount_usd=405000; approval_date=2026-06-29; issuance_date=2026-06-30; sheriff_attachment=2026-07-01 10:40; overlaps underlying court awards, not an additional debt. 

Outstanding: Reviewed deeds are partial-page observations; complete legal descriptions, execution dates, intervening instruments, and current recorder search remain needed; Read originals: 20630/164, 20630/170, 20630/196; Assessment snapshots do not fill title intervals or establish beneficial shares; Newbury:trust20592/119;acquisition20630/164;mortgage20630/170;financing20630/196;certificate56617/269;attachment72957/242 satisfaction and updated court balance.

### 384 Marlborough ST

`US-MA-SUFFOLK:PARCEL:0503608000` — association group: `tarek_individual_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — POKORNY MARGARET ETAL. [BOSTONASSESS:FY2014:0503608000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — HASSAN TAREK. [BOSTONASSESS:FY2026:0503608000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **2021-09-02 — deed_index_candidate**; HASSAN TAREK; index_only_candidate. [SUFFOLK-DEEDS:66220/61](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Mortgage66220/65; mortgage67902/248 on2022-07-05; assignment69839/16 on2024-01-26; recorded_date=2021-09-02; execution date not established unless separately stated. . Property join uses the instrument address/description and existing Boston assessment PID; the deed/index does not itself supply this PID. 

Outstanding: No original title deed reviewed in baseline; Read originals: 66220/61; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 1692 Washington ST unit 1

`US-MA-SUFFOLK:PARCEL:0801499002` — association group: `houssam_historical_other_owner_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2008** — HASSAN HOUSSAM. [BOSTONASSESS:FY2008:0801499002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/81f34da8-ec6d-45f6-8d6c-65c57e71023e/download/property-assessment-fy08.csv)
- **FY2014** — WILLIAMSON CARROLL M JR TS. [BOSTONASSESS:FY2014:0801499002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2026** — VAZIRANI YASH A. [BOSTONASSESS:FY2026:0801499002](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Historical subject/vehicle label differs from FY2026; disposition deed and consideration needed.

### 137 W Concord ST

`US-MA-SUFFOLK:PARCEL:0900512000` — association group: `houssam_vehicle_current`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — ONE 37 W CONCORD LLC. [BOSTONASSESS:FY2014:0900512000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2021** — 137 WEST CONCORD LLC. [BOSTONASSESS:FY2021:0900512000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 137 WEST CONCORD LLC. [BOSTONASSESS:FY2026:0900512000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 5 observations from 2012-05-18 through 2013-09-18. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares.

### 142 W Concord ST

`US-MA-SUFFOLK:PARCEL:0900582000` — association group: `permit_only_context`; join: `source_exact_parcel_id`.

- **Municipal permit history:** 3 observations from 2013-08-22 through 2014-10-16. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline.

### 204 W Springfield ST

`US-MA-SUFFOLK:PARCEL:0900774000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — TWO-04 W SPRINGFIELD ST. [BOSTONASSESS:FY2014:0900774000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — TWO-04 W SPRINGFIELD ST. [BOSTONASSESS:FY2019:0900774000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — TWO-04 W SPRINGFIELD ST. [BOSTONASSESS:FY2021:0900774000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — TWO-04 W SPRINGFIELD ST. [BOSTONASSESS:FY2026:0900774000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)


Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### 196 W Springfield ST

`US-MA-SUFFOLK:PARCEL:0900778000` — association group: `houssam_condo_master_or_name_candidate`; join: `source_exact_parcel_id`.

Assessment owner observations (not title transfers):
- **FY2014** — FORD ALBERT F II. [BOSTONASSESS:FY2014:0900778000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/7190b0a4-30c4-44c5-911d-c34f60b22181/download/property-assessment-fy2014.csv)
- **FY2019** — 196 WEST SPRINGFIELD LLC. [BOSTONASSESS:FY2019:0900778000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/695a8596-5458-442b-a017-7cd72471aade/download/fy19fullpropassess.csv)
- **FY2021** — 196 WEST SPRINGFIELD STREET CONDOMINIUM TRUST. [BOSTONASSESS:FY2021:0900778000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/c4b7331e-e213-45a5-adda-052e4dd31d41/download/data2021-full.csv)
- **FY2026** — 196 WEST SPRINGFIELD STREET CONDOMINIUM TRUST. [BOSTONASSESS:FY2026:0900778000](https://data.boston.gov/dataset/e02c44d2-3c64-459c-8fe2-e1ce5f38a035/resource/ee73430d-96c0-423e-ad21-c4cfb54c8961/download/fy2026-property-assessment-data_rev.csv)

- **Municipal permit history:** 1 observations from 2017-10-12 through 2017-10-12. Exact permit IDs, applicants, raw timestamps, status and quotes are in events.csv; none establishes title.

Outstanding: No original title deed reviewed in baseline; Assessment snapshots do not fill title intervals or establish beneficial shares; Condominium master: join individual units and deed/disposition schedule.

### Boylston Street

`US-MA-SUFFOLK:UNRESOLVED:42126-208` — association group: `index_only_property_candidate`; join: `property_unresolved`.

- **2007-07-11 — lien_index_candidate**; HASSAN HICHAM A; index_only_candidate. [SUFFOLK-DEEDS:42126/208](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Related complaints42275/98,/107,/114 on2007-08-06; recorded_date=2007-07-11; execution date not established unless separately stated. Unresolved. 

Outstanding: No original title deed reviewed in baseline; Read originals: 42126/208; Resolve parcel and party identity before assigning to a current holding.

### Property unspecified in indexed tax lien

`US-MA-SUFFOLK:UNRESOLVED:56891-170` — association group: `index_only_property_candidate`; join: `property_unresolved`.

- **2016-10-04 — tax_lien_index_candidate**; HASSAN TAREK A; index_only_candidate. [SUFFOLK-DEEDS:56891/170](https://www.masslandrecords.com/SUFFOLK/D/Default.aspx). review_state=index only; Identity and linkage require original instruments; recorded_date=2016-10-04; execution date not established unless separately stated. Release candidate56999/289 dated2016-10-25. 

Outstanding: No original title deed reviewed in baseline; Read originals: 56891/170; Resolve parcel and party identity before assigning to a current holding.

### Family-property interests described in case2084CV00531 (property allocation unresolved)

`US-MA-SUFFOLK:UNRESOLVED:FAMILY-INTERESTS-2084CV00531` — association group: `family_claims_not_title`; join: `unallocated_case_context`.

- **2000-12-14 — alleged_family_agreement**; Participants: Hicham Ali Hassan; Tarek Ali Hassan; allegations_in_judicial_opinion. [https://masslawyersweekly.com/files/2020/08/Rule-12c.SOL_.hassan.pdf](https://masslawyersweekly.com/files/2020/08/Rule-12c.SOL_.hassan.pdf). 2020 family-property opinion recounts alleged 2000 buyout and retained minority interests Tarek Ali Hassan v Hicham Ali Hassan et al, Suffolk Superior BLS 2020CV0531-BLS2, July23 2020: complaint allegations assumed true only for pleading motions. Court recounts a December14 2000 Settlement Agreement under which Hicham would purchase family interests while Tarek retained 5% beneficial interests in three trusts and director/minority-shareholder positions in two corporations. Named exactly as printed: 376 Boston Street Realty Trust; 4000 Boylston Street Realty Trust; Eighteen Brimmer Street Realty Trust; 419 Boylston Street Corporation; 216-218 Newbury Street Corporation. First two names may contain typographical errors and are not normalized as title evidence. Opinion calls Hicham Tarek's uncle, says unnamed father and other family members held interests. Original agreement/exhibits and later disposition required; this motion decision did not adjudicate ownership. No ownership interval or beneficial share is created from this event. The original agreement and settlement terms remain outstanding.
- **2020-07-23 — court_order**; Participants: Hicham Ali Hassan; Tarek Ali Hassan; judicial_text_reviewed. [https://masslawyersweekly.com/files/2020/08/Rule-12c.SOL_.hassan.pdf](https://masslawyersweekly.com/files/2020/08/Rule-12c.SOL_.hassan.pdf). Court allowed Tarek property claims to proceed and dismissed Hicham counterclaims at pleading stage in 2020 Same Suffolk BLS case. Defendants' limitations motion for judgment on the pleadings denied; Tarek's motion to dismiss counterclaims allowed July23 2020. Counterclaims alleged diversion of goods/cash, including an amount exceeding $700,000 for 2012-14 purportedly found in a 2016 audit; these are allegations, not established facts. Court applied three-year tort limitation, noted other pleading defects, and ordered counterclaims dismissed. No ultimate finding on the merits of Tarek's beneficial-interest claim is made by this order. No ownership interval or beneficial share is created from this event. The original agreement and settlement terms remain outstanding.
- **2022-08-18 — case_disposition**; Participants: Hicham Ali Hassan; Tarek Ali Hassan; public_filed_document_reproduction. [https://trellis.law/doc/270321173/party-s-file-stipulation-dismissal-filed-8-17-22-as-to-plff-vs-defts-with-prejudice-without-costs-with-all-rights-appeal-waived-judgment-entered-on-docket-pursuant-to-mass-r-civ-p-58-a-as-amended-notice-sent-to-parties-pursuant-to-mass](https://trellis.law/doc/270321173/party-s-file-stipulation-dismissal-filed-8-17-22-as-to-plff-vs-defts-with-prejudice-without-costs-with-all-rights-appeal-waived-judgment-entered-on-docket-pursuant-to-mass-r-civ-p-58-a-as-amended-notice-sent-to-parties-pursuant-to-mass). Public reproduction of August 2022 stipulation records dismissal with prejudice of Hassan family business case; docket calls case settled. Suffolk Superior Court 2084CV00531 (2020CV0531-BLS2), Tarek Ali Hassan individually/derivatively v Hicham Ali Hassan individually/as trustee, 419 Boylston Street Corporation Inc, 216-218 Newbury Street Corporation Inc et al. Public Trellis preview of signed stipulation is stamped filed August 17, 2022 and dated that day; operative language dismisses claims/counterclaims with prejudice, without costs, appeal rights waived. Trellis docket reproduction records judgment entry August 18, 2022 and October 7 cancellation of October 13 Rule 56 hearing because Case Settled. Source caveat: court document reproduced as public preview by Trellis, not an independently obtained official docket/PDF; archived manual excerpt in investigations/hassan-boston/evidence/litigation/family-case-2022-disposition-preview.md. Settlement terms, payment, adjudicated equity, father identity and original 2000 agreement not established. No ownership interval or beneficial share is created from this event. The original agreement and settlement terms remain outstanding.Stipulation signed/filed2022-08-17; reproduced docket judgment2022-08-18; execution and docket dates are distinct.

Outstanding: No original title deed reviewed in baseline; Resolve parcel and party identity before assigning to a current holding.

## Coverage and learnings

All exact parcel IDs in this baseline are Boston/Suffolk. Outside-county sources are assigned to other wave2 agents; this local baseline makes no claim to have searched Plymouth, Norfolk or Middlesex. Historical sold/renamed assets and condominium units remain included. No acquired property is inferred from a mortgagee candidate.

No new repository papercut was encountered beyond known first-wave source/data limitations. The source-owner correction to 17988/312 was received before event generation; a validation assertion prevents reuse of the old $1,725,000 quote. Every event has a source URL and source quote. All 32 instruments have stable registry/book/page IDs; multi-parcel repetitions share instrument_id.
