# Ownership timeline and county/court expansion — September 4, 2026

The user requests a property-by-property ownership timeline, pursuit of the
initial report's follow-ups, explicit probate/divorce/local-court coverage,
and expansion beyond Suffolk, especially Plymouth County because Hingham
appears in the records. Hingham is a search lead, not proof of property title.

## Source ownership

| Track | Owner | Mandate |
|---|---|---|
| Timeline reconciliation | properties | Existing parcel, assessment, corporate and instrument evidence; normalize dated observations and reconcile new track exports |
| Suffolk title chains | deeds_finance | Original Suffolk deeds, trust certificates, mortgages and releases; fill priority chains and the 2016 transfers |
| Plymouth County | disclosures | Plymouth recorded and registered land; six people and name variants; Hingham parcels and financing/title/trust changes |
| Other counties | corporate | Evidence-led Norfolk, Middlesex North/South and other county recorder/assessor coverage; exact entity searches |
| Probate and divorce | identities | Public Probate and Family Court indexes, estate notices and property/business disposition records; Suffolk, Plymouth, Norfolk and Middlesex |
| Local civil courts | litigation | Public Superior, District, BMC, Housing and Land Court sources; the 2000 family agreement/2022 outcome and related property disputes |
| Capital and bankruptcy follow-ups | capital_followups | Missing Alana/Nader schedules, amendments, guarantees and Concepts investment documentation; no duplicate recorder searches |
| Assembly and quality review | parent | Source coverage, timeline artifact, confidence/identity review, durable evidence and remaining action list |

Each track has one persistence owner. Flag cross-track documents to the owner.
Use agents in the current task, never the headless dispatcher. Keep evidence
under `evidence/wave2/<track>/` and reports under `reports/wave2/`.

## Event data contract

Export `events.csv` with: event_id, property_key, property_label, municipality,
county, parcel_id, event_date, date_precision, date_basis, event_type,
from_party, from_capacity, to_party, to_capacity, consideration_usd,
loan_amount_usd, registry, book_page, instrument_id, evidence_status,
source_url, source_ref, source_quote, finding_ids, notes.

Use stable county/book/page IDs. Keep execution date and recording date
distinct in notes. If only a fiscal year is known use year precision. Record
deeds, trustee changes, financing, court actions and assessment observations
as different event types. A mortgage or assessment observation alone does
not establish a new title interval. Index-only rows are candidates until
the original document or corroborating record resolves parcel and capacity.

## Evidence and access

Read profile AGENTS.md and the spelling register. Use profile `hassan-boston`
on all scoped writes, existing canonical entity IDs and exact legal names.
Check search_log before queries; save query scopes and result artifacts.
New findings need evidence, source quote and claim type. Do not infer equity,
kinship, paid debt, current ownership or illicit funding from incomplete records.

Public probate/divorce research is limited to identity, case status, estate
administration and relevant property/business interests. Omit incidental
intimate, medical, minor-child or other unnecessary personal information.
Respect public-access restrictions. No contact, paid orders, records requests,
account creation, CAPTCHA bypass or headless dispatch is authorized.

## Completion and review

Produce a usable timeline from the available evidence, pursue each priority
record route, and distinguish searched/no-match, candidate, unavailable,
restricted and not-yet-searched coverage. Record concrete missing instruments
or case documents rather than treating an access gap as a negative finding.
Parent reviews the merged events and ownership intervals before presentation.
