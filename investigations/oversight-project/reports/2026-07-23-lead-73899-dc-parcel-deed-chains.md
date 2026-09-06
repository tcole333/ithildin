---
agent: pursue-lead
target: "CPI campus parcels and McAllister Holdings LLC parcels"
skill: pursue-lead
status: blocked
findings_added: 1
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 73899
---

# Lead #73899 Report: DC parcel and Recorder instrument chains

## Key Discoveries

- The official DC OTR Owner Polygons layer resolved every scoped parcel:
  seven Schedule R parcels in square 0762, CPI's 126 3rd Street parcel
  0788-0805, and the McAllister 313/315 Pennsylvania Avenue parcels
  0790-0017 and 0790-0016.
- The exact seven Schedule R address/SSL pairs are:
  0762-0038 / 225 Pennsylvania Ave SE; 0762-0818 / 209 Pennsylvania Ave
  SE; 0762-0840 / 203 3rd St SE; and 0762-0844 through 0762-0847 /
  229, 231, 203, and 233 Pennsylvania Ave SE.
- CPI's direct parcel is 0788-0805 / 126 3rd St SE. McAllister Holdings
  LLC's current OTR parcels are 0790-0016 / 315 Pennsylvania Ave SE and
  0790-0017 / 313 Pennsylvania Ave SE.
- OTR's current `INSTNO` field is null on all ten rows. That is an absence
  from the current tax extract, not proof that no instrument was recorded.
- OTR labels sale dates/prices for several parcels, but those fields were not
  reported as deed execution dates or stated consideration. The four current
  lots 0762-0844 through 0762-0847 show an OTR recordation-date field of
  2025-10-07; no legal event was inferred without the underlying record.
- The Recorder search requires a registered account. Registration permits
  free search and image viewing; downloads cost $4 per document plus a $1.50
  transaction surcharge. No account was created, credentials used, or
  document purchased.

## Findings Added

- **#14376** — official ten-parcel OTR index and precise Recorder
  registration boundary; claim type `paraphrase`, confidence `high`, global
  thread 180. Its scoped evidence audit found zero issues, and the finding
  was marked verified.

## Connections Added

None. The common 300 Independence Avenue SE tax-mailing address does not
establish ownership, membership, management, or control.

## Entities Registered

None.

## Negative Results

- No Recorder instrument number, grantor/grantee index row, or image was
  accessible without registration.
- No deed, deed of trust, assignment, modification, release, satisfaction,
  or immediate prior deed was reviewed.
- No signatory, capacity, lender, trustee, title company, notary, return
  address, or deed consideration was extracted.
- `OWNNAME2=CLEAR PLAIN LLC` on 0762-0845 and 0762-0846 remains only an OTR
  secondary billing-owner field; no actual instrument yet shows that spelling
  as a recorded party.

## Sources Checked

| Source | Access | Result | Findings Created |
|---|---|---|---|
| DC GIS / OTR Owner Polygons layer 40 | Official ArcGIS query limited to ten SSLs | Exact SSL/address/current-name and OTR sale fields; all ten `INSTNO` values null | #14376 |
| DC GIS PropertyQuest parcel layer | Official duplicate presentation of the OTR public extract | Same ten rows and same null instrument fields; redundancy, not corroboration | None |
| DC OTR Recorder of Deeds page | Official referral page | Confirms Recorder as the land-record repository and links the public search | #14376 |
| DC Recorder PublicSearch landing | Recorder-linked search vendor | Registration required for free search/view; paid downloads | #14376 |

Durable parcel and retrieval matrix:
`investigations/oversight-project/evidence/lead-73899-dc-parcel-recorder-index.md`

## Gaps / Follow-up Needed

Human action **#103** preserves the exact registered-account remainder for
only the ten scoped SSLs:

1. preserve every relevant Recorder index row's instrument number, recording
   date, document type, grantor, grantee, and image availability;
2. review the current acquisition deed, immediate prior deed, and deeds of
   trust, assignments, modifications, releases, and satisfactions needed for
   each chain;
3. extract stated consideration, execution date, signatory/capacity, lender,
   trustee, title company, notary, return address, and legal description only
   from the actual image;
4. test whether `CLEAR PLAIN LLC` singular appears as a recorded party;
5. do not purchase a download without separate approval.

Lead #73899 is blocked only on that Recorder instrument/index/image layer.

## Leads Spawned

None.

## Learnings

- [Methodology] A shared tax-mailing address is a routing fact, not evidence
  of ownership or control.
- [Source quality] A null `INSTNO` in OTR's current public extract means the
  tax layer did not expose an instrument number; it does not establish that
  the Recorder has no deed.
- [Access] DC Recorder registration provides free search and image viewing,
  while downloads are separately priced; preserve index metadata before
  deciding whether any paid copy is necessary.
