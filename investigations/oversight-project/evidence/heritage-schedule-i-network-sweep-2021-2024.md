# Heritage Schedule I expansion-network sweep, TY2021-TY2024

Checked 2026-07-23 for lead #74543. Filers: The Heritage Foundation,
EIN 23-7327730, and Heritage Action for America, EIN 27-2244700.

## Availability and denominator

The latest actually public return for both filers is TY2024. Exact-EIN searches of
the current official 2026 XML index returned zero rows for both filers; TY2025 is
therefore not treated as available.

| Filer | TY | IRS object | Schedule I organization rows | Cash | Non-cash |
|---|---:|---|---:|---:|---:|
| Heritage Foundation | 2021 | 202231649349300228 | 2 | $115,000 | $0 |
| Heritage Foundation | 2022 | 202311789349301501 | 16 | $1,641,000 | $0 |
| Heritage Foundation | 2023 | 202443129349303214 | 13 | $1,465,000 | $0 |
| Heritage Foundation | 2024 | 202523199349302027 | 26 | $8,720,000 | $0 |
| Heritage Action | 2021 | 202212179349300026 | 0 | $0 | $0 |
| Heritage Action | 2022 | 202321869349301002 | 1 | $4,250,000 | $17,967 |
| Heritage Action | 2023 | 202443129349302144 | 1 | $500,000 | $76,095 |
| Heritage Action | 2024 | 202513189349313311 | 1 | $40,000 | $0 |

Combined denominator: 60 filed organization rows, 48 distinct recipient-name
strings, $16,731,000 cash, and $94,062 non-cash.

The latest TY2024 objects were extracted from the official IRS
`2025_TEOS_XML_11C.zip` and `2025_TEOS_XML_11D.zip`. The TY2023 objects were
extracted from official `2024_TEOS_XML_11A.zip`. Their byte hashes exactly matched
the previously parsed object copies. The current 2026 index SHA-256 is
`00c1d156ef89fc676c2a3f59c81100dc0d9f7601d251fdfcd02ba58c0877110f`.

## Explicit comparison roster

The roster was built from existing findings and canonical entities, with aliases
and service companies searched but not double-counted:

- **Klimon seven-organization book** (#14116): Frontier Foundation; State
  Leadership Foundation; The Oversight Project; American Ideas
  Foundation/Institute; Blueprint for America Coalition; Rural Washington Voter
  League; Safer Missouri.
- **CPI/accountability and 300 Independence cohort** (#13962, #14089, #14160):
  Conservative Partnership Institute; American Accountability Foundation; AAF
  Action; Personnel Policy Operations; Edmund Burke Foundation; Immigration
  Accountability Project; FAIR Elections Fund; Election Integrity Action; Election
  Integrity Network; Conservative Partnership Campus; Compass Professional; Art &
  Literature Foundation; Blue Energy Nation.
- **New Founding/tech-right orbit** (#14117, #14141, #14149, #14230): American
  Reformer; New Founding Corporation; Frontier Network Operations (a New Founding
  trade name); Frontier Foundation; Blueprint; American Ideas Institute. State
  Leadership Foundation is the board bridge and is not counted twice.
- **502 Sixth Street/external election-operations orbit** (#14123, #14132, #14135,
  #14198-#14200): Look Ahead America; Rural Washington Voter League; Safer
  Missouri; Green Dragon Society; Green Dragon Coalition; Constitutional
  Conservatives Fund; 9Seven Consulting; Same Day Processing.
- **PAC adjacency tested separately:** Sentinel Action Fund (#14100, #14101).

## Six strict direct matches

| Direct filer | TY | Recipient | EIN | Cash | Non-cash | Filed purpose | Placement |
|---|---:|---|---|---:|---:|---|---|
| Heritage Foundation | 2023 | American Reformer | 87-0851385 | $50,000 | $0 | GENERAL OPERATIONS | Fischer/tech-right |
| Heritage Foundation | 2024 | American Accountability Foundation | 85-4391204 | $100,000 | $0 | INNOVATION PRIZE | CPI/accountability |
| Heritage Foundation | 2024 | Edmund Burke Foundation | 83-3008254 | $250,000 | $0 | GENERAL OPERATIONS | CPI/accountability |
| Heritage Foundation | 2024 | Personnel Policy Operations | 88-1773001 | $500,000 | $0 | GENERAL OPERATIONS | CPI/accountability |
| Heritage Foundation | 2024 | Immigration Accountability Project | 93-3772296 | $100,000 | $0 | INNOVATION PRIZE | CPI/accountability |
| Heritage Action | 2022-2023 | Sentinel Action Fund | 87-3739115 | $4,750,000 | $94,062 | POLITICAL ACTIVITIES | Stoltzfus-linked PAC layer |

Heritage Foundation's five strict recipients total $1,000,000. Adding Heritage
Action's one distinct recipient produces six recipients and $5,750,000 cash plus
$94,062 non-cash.

## Direct, affiliate, and designated flows

- Heritage Foundation separately paid Heritage Action $400,000 in TY2022, $500,000
  in TY2023, and $200,000 in TY2024, all for `PUBLIC POLICY EDUCATION`. This
  $1.1 million affiliate flow is not counted as a seventh expansion grantee and
  cannot be traced to Sentinel from the filed purpose lines.
- DonorsTrust's $50,000 FY2022 grant to Heritage `for the Heritage Oversight
  Project` (#13966) is an inbound, donor-designated grant. It is not a Heritage
  Schedule I outflow to an independent Oversight entity. Heritage reported
  Oversight as an internal program in TY2023 and TY2024 (#14005).
- DonorsTrust's separate $250,000 grant to CPI `to support the State Leadership
  Initiative`, followed by CPI's $250,000 grant to State Leadership Foundation
  (#14157), is a DonorsTrust/CPI route, not Heritage funding.

## Falsifier and innocent-alternative result

The literal five-recipient criterion is met: six distinct strict network recipients
appear. The stronger all-four-lobe test fails. Four of Heritage Foundation's five
hits cluster in the TY2024 CPI/accountability core, American Reformer is the sole
Fischer/tech-right hit, and Heritage Action's sole network recipient is Sentinel.
No direct Schedule I row reaches the target State Leadership Foundation or the
Braynard/Datwyler external election-operations roster.

Accordingly, the full sweep rejects the narrow “only two cherry-picked grants”
baseline, but it does not establish a systematic mothership seeding all four lobes
or common operating command. The supported conclusion is partial cross-lobe
funding, at medium confidence.

Name traps were resolved rather than counted: State Government Leadership
Foundation is not the target State Leadership Foundation; State Financial Officers
Foundation is a personnel predecessor; American Movement Foundation is not American
Moment or New Founding; and Vote for America, Feds for Freedom, and Claremont
Institute lacked an established roster link.

## Official sources

- https://www.irs.gov/charities-non-profits/form-990-series-downloads
- https://apps.irs.gov/pub/epostcard/990/xml/2026/index_2026.csv
- https://apps.irs.gov/pub/epostcard/990/xml/2025/2025_TEOS_XML_11C.zip
- https://apps.irs.gov/pub/epostcard/990/xml/2025/2025_TEOS_XML_11D.zip
- https://apps.irs.gov/pub/epostcard/990/xml/2024/2024_TEOS_XML_11A.zip
