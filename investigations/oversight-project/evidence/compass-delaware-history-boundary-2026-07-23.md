# Compass suite: Delaware history and name-continuity boundary

Date checked: 2026-07-23  
Lead: 73881  
Profile: oversight-project  
Global thread: 180

## Question tested

Do current allowed records establish the Delaware file identities and histories
of the five-company Compass service suite, and do they prove that `Compass
Legal Services Inc` became `Compass Legal Group Inc` by statutory name change?

## Current evidence matrix

| Scoped entity | Primary-record identity already established | Delaware result available now | Unresolved corporate fields |
|---|---|---|---|
| Compass Professional Inc | EIN 86-2783829; 300 Independence Ave SE; Schedule R identifies a Delaware C corporation providing shared services | No allowed official Delaware file result is held | File number, exact formation date, current status, registered agent, charter, amendments, officers/directors, stock history |
| Compass Legal Group Inc / Compass Legal Services Inc | EIN 86-2833005; CPI TY2021 and TY2022 Schedule R use `Compass Legal Group Inc`, Delaware C corporation; a 2021 FEC designation uses `Compass Legal Services, Inc.`; the 2024 DOL plan row uses `COMPASS LEGAL GROUP` as sponsor and `COMPASS LEGAL SERVICES INC` as DBA | No allowed official Delaware file result or amendment is held | Whether the two names are one file or separate files; exact statutory name sequence; formation date; current status; agent; charter/amendments; officers/directors; stock history |
| Compass Property Management Inc | EIN 87-4314495; 300 Independence Ave SE; 2024 DOL plan row signed by Shirley Horner; CPI reports it as a property-management contractor | The investigation previously described Delaware domicile and an approximate 2022 formation year, but no allowed underlying Delaware primary record is held | File number, exact formation date, state status, agent, charter/amendments, officers/directors, stock history |
| Compass Direct LLC | Current state fundraiser records identify the same-name professional fundraiser at 300 Independence Ave SE and CPI/AFL client relationships; a prior application reportedly identified Delaware and 2023-07-24, but the underlying Delaware record is not held | No allowed official Delaware file result is held; EIN and owners remain unresolved | Exact Delaware identity/file, status, agent, formation instrument, amendments, members/managers, EIN |
| Conservative Partnership Campus, Inc. | CPI contractor and taxable affiliate context is separately established | Official Delaware result: file 6864831; formed 2022-06-17; Corporation / General; Domestic; current agent The Corporation Trust Company | Current status/status-as-of, incorporator, charter, amendments, former names, annual-report officers/directors |

Preserved official Campus excerpt:

- `DE-SOS:6864831`: “File Number: 6864831 Incorporation Date /
  Formation Date: 6/17/2022 Entity Name: CONSERVATIVE PARTNERSHIP CAMPUS,
  INC. Name: THE CORPORATION TRUST COMPANY”

The five names are an operational service-suite grouping based on primary
federal and state records. The grouping is not evidence that the entities share
equity ownership, a parent, or one Delaware file.

## Legal Services / Legal Group test

The 2024 DOL Form 5500-SF row uses:

- sponsor name: `COMPASS LEGAL GROUP`;
- sponsor DBA name: `COMPASS LEGAL SERVICES INC`;
- sponsor EIN: `862833005`;
- sponsor address: `300 INDEPENDENCE AVE SE`;
- filing signer: `PATRICK CORRIGAN`;
- acknowledgement: `20250723122721NAL0003438097001`.

That is strong primary evidence that both names operated under the same federal
employer identifier in the plan filing. It does **not** identify which name was
the Delaware statutory name on any date or prove that a certificate of
amendment changed one name to the other.

The Delaware field guide defines `ENTITY NAME` as:

> The current name of an entity as set forth in their certificate of
> incorporation or formation; or as amended by subsequent documents.

Because the free page displays only the current name, a current-name hit cannot
reconstruct a former name or distinguish a DBA from a filed name amendment.
The competing explanations remain:

1. one Delaware corporation changed its statutory name;
2. one corporation retained one statutory name and used the other as a DBA or
   brand;
3. two corporations existed and federal filings collapsed or related the names.

Only unique Delaware file numbers plus a complete history and the underlying
formation/amendment documents can discriminate among them.

## Access checks

- Delaware's FAQ says its free search returns active and inactive entities but
  “does not provide entity status.”
- Delaware's USD 20 product returns only the last five filings and no document
  images or officer/director information.
- A long-form certificate reports all filed documents, dates/times, name
  changes, and current status. Formation and amendment images must still be
  requested through the Document Filing and Certificate Request Service.
- The official search portal prohibits automated tools, mining, or extraction.
  It was not automated, and no CAPTCHA was bypassed.
- The configured OpenCorporates API returned an invalid-token failure in the
  prior work. Its current web portal requires registration for advanced
  searching.
- Exact official DC open-data searches previously returned zero for Compass
  Professional, Compass Legal, and Compass Direct; the 2026-07-23 exact Compass
  Property Management search also returned zero. Those are bounded DC
  registration results, not proof that the Delaware entities do not exist.
- The local unified-registry exact-name pass returned no relevant records for
  the four for-profits. One `ENCOMPASS PROPERTY MANAGEMENT INC.` result was a
  different Florida company and was excluded.

## Paid/manual remainder

Human action 99 already includes Campus file 6864831. Extend the action with
four manual exact-name searches:

1. `COMPASS PROFESSIONAL INC`
2. `COMPASS LEGAL GROUP INC` and `COMPASS LEGAL SERVICES INC`
3. `COMPASS PROPERTY MANAGEMENT INC`
4. `COMPASS DIRECT LLC`

For every uniquely matched file:

1. preserve the free result and file-number mapping;
2. obtain current status and status-as-of date;
3. obtain a long-form certified history;
4. order the initial formation document and all amendments, former-name,
   merger, conversion, dissolution/revival, and agent-change filings;
5. order annual-report images needed for officers, directors, principal office,
   and signatories;
6. extract incorporator/authorized person, counsel or filing contact,
   historical agents, dates, addresses, officers/directors, members/managers,
   and stock fields.

Prioritize the Legal Group/Services file-number and amendment test because it
answers the specific statutory-continuity hypothesis. Do not purchase records
without budget approval; the investigation already records a user preference
against low-value Delaware certificate spending in lead 75290.

## Official and internal source trail

- `DE-SOS:6864831`
- `IRS:202223199349329357` — CPI TY2021 Schedule R
- `IRS:202343199349307579` — CPI TY2022 Schedule R
- `IRS:202513189349303026` — CPI TY2024 contractor and Schedule G rows
- `DOL:EFAST2:20250723122721NAL0003438097001`
- findings 13961, 14074, 14078, 14081, 14082, 14235, 14237, and 14319
- <https://corp.delaware.gov/faqs/>
- <https://corp.delaware.gov/onlinestatus/>
- <https://corp.delaware.gov/directweb/>
- <https://corp.delaware.gov/document-upload-service-information/>
- <https://icis.corp.delaware.gov/Ecorp/FieldDesc.aspx>
