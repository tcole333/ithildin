# Ohio corporate and property-vehicle reconstruction

## Objective

Reconstruct the Ohio entities used around the Epstein-Wexner relationship even
when a current company index no longer shows Epstein. The unit of analysis is
not just a person-name hit. It is a time-bounded tuple:

> legal-name variant + address or parcel + person/agent + role or property
> action + date + primary record

The durable outputs are:

- `ohio-corporate-property-index.csv` — one row per entity or vehicle.
- `ohio-corporate-property-evidence.csv` — one row per filing, deed, parcel
  observation, or corpus record.
- `dorothy-snow-ohio-entities.csv` — the 101-entity Ohio agent-export
  denominator and review state.
- `dorothy-snow-ohio-agent-date-clusters.csv` — exact agent-date batches,
  explicitly separated from formation and terminal-action dates.
- `dorothy-snow-ohio-entity-review.xlsx` — working review dashboard and
  evidence-entry workbook.
- `outputs/019fb3a7-511b-7b50-bf21-df954c6b7490/ohio-epstein-property-corporate-reconstruction.xlsx`
  — consolidated 11-sheet handoff covering entity-family search scope,
  116 normalized parcel/instrument events, 110 family-ledger rows, merger
  transactions and constituent edges, the Morsham successor chain, timeline
  clusters, and search-QA limitations.
- `dorothy-snow-ohio-entity-analysis.md` — cohort methodology, 15-entity pilot,
  merger resolution, property workflow, and completion criteria.
- `ohio-sos-filing-manifest.csv` — exact filing rows and image availability.
- `ohio-epstein-officer-filing-coverage.csv` — every in-cohort and external
  officer-company seed, exact charter, primary-review state, and next action.
- `ohio-sos-merger-transactions.csv` and `ohio-sos-merger-parties.csv` —
  one-to-many successor-chain model with property-search rules.
- Curated findings #14519-#14582 and the linked canonical entities in
  `investigation.db`.

## Results from the first implementation

Twelve officer-role or successor entries are now primary-verified:

1. **N.A. Property, Inc. (Ohio 832364)** — five Ohio annual reports identify
   Epstein as president from the early through late 1990s.
2. **The New Albany Company LLC (Ohio 1034132)** — the 1998 foreign-LLC
   registration identifies N.A. Property as managing member, Epstein as its
   president/signatory, and Leslie Wexner as another managing member.
3. **Parkview Financial, Inc. / LEWEX, INC. (Ohio 623762)** — its 1990
   dissolution identifies Epstein as vice president and treasurer and Wexner
   as director and president.
4. **INN Investment Corp. (Ohio 678033)** — its 1992 dissolution identifies
   Epstein as president, Wexner as director, Robert S. Schwartz as assistant
   secretary, and Dorothy Snow as statutory agent. The unnamed sole shareholder
   remains unknown.
5. **Cherry Bottom Investors / Properties (Ohio 719718 / 719719)** — Epstein
   signed as Investors' president and Properties' vice president when Investors
   merged into Properties in 1990. Properties' 1998 dissolution later lists
   Wexner as president/director and Darren Indyke as secretary.
6. **LEWEX, Inc. (Ohio 658220)** — its 1992 dissolution identifies Epstein as
   vice president and treasurer and Wexner as director and president. This is
   a separate corporation from Parkview Financial/former LEWEX, Ohio 623762.
7. **West First Plaza, Inc. (Ohio 777500)** — its 1992 dissolution identifies
   Epstein as president, Wexner as director, George Pryor Jr. as vice
   president, and Jeffrey Smith as secretary.
8. **Park Properties, Inc. (Ohio 626053)** — its 1992 dissolution identifies
   Epstein as vice president and Wexner as sole director and president.
9. **C-Wren Investment Corp. (Ohio 803531)** — its 1993 dissolution identifies
   Epstein as vice president and treasurer and Wexner as sole director and
   president.
10. **PFI Leasing, Inc. (Ohio 624047)** — its 1990 dissolution identifies
    Epstein as vice president and treasurer and Wexner as director and
    president.
11. **Rocky Fork Development Corporation (Ohio 706978)** — its 1992
    dissolution identifies Epstein as vice president and Wexner as sole
    director and president. Its 1987 agreement identifies Rocky Fork as
    survivor of Bearce Hollow, Inc.; neither man appears in that earlier
    transaction.
12. **City Centre Investment Corp. (Ohio 712332)** — its 1994 dissolution
    identifies Epstein as president and Wexner as director. Vorys, Sater,
    Seymour and Pease submitted the packet.

West First, Park Properties, C-Wren, and LEWEX 658220 were all in the Snow
denominator but had remained unreviewed. PFI Leasing, Rocky Fork, and City
Centre were outside it. The two failures require a dual-universe workflow:
complete all 101 Snow histories and maintain a rolling external-seed ledger.

A separate systemic result materially expands the property search:

- **Architonics, Inc. (Ohio 713548)** survived a single 23-corporation merger
  effective 1989-12-22. Eighteen predecessors plus Architonics appear in the
  fixed 101-row Dorothy Snow export; five named predecessors do not. The filing
  names Dorothy Snow and Richard W. Rubenstein, but neither Epstein nor Wexner.
  It confirms a successor chain, not beneficial ownership.

- **Autumn Acres, Inc. (Ohio 706250)** survived a seven-predecessor merger
  effective 1990-12-28. The predecessors were Deerfield Meadows, Landes
  Management, Maycor, New Albany 74, 129 Associates, Rockyridge Development,
  and Tumbleweed Estates. Their reciprocal MEX stubs omit the survivor; the
  substantive agreement `H052_1482` supplies the edges and transfers any
  property interests to Autumn. Autumn's separate next-day dissolution image
  is unavailable, so the final disposition remains unresolved.
- **Bearce Hollow, Inc. (Ohio 689665)** merged into Rocky Fork Development
  Corporation on 1987-12-31. The agreement transfers any Bearce property to
  Rocky Fork without another deed but proves no parcel. Rocky Fork's later
  Epstein/Wexner filing makes this a confirmed corporate-successor bridge, not
  evidence that either man held a 1987 role.
- **New Albany 84, Inc. and New Albany 74, Inc.** are the same Ohio charter
  698295. The 1987 amendment supplies the former-name chain and prevents both
  duplicate entity creation and missed recorder/corpus matches.

The property lane produced one strong single-home vehicle:

- **HHD & B LLC** — Epstein acquired the 30.368-acre tract now identified as
  Franklin parcel 222-001350-00 in 1992 and deeded it to the LLC in 1998. The
  deed faces show $3,500 and $8,000 conveyance-tax stamps, not sale prices; the
  separate Auditor sales records report $3.5 million and $8 million. The
  Auditor currently lists HHD & B LLC as owner of the residential parcel at
  5025 Dublin-Granville Road. The deed does not reveal the LLC's members or
  prove Epstein retained control.

The most useful unresolved candidates are:

- **The Wexner Foundation (Ohio 436405)** — the exact Ohio nonprofit charter
  is now resolved. A primary SEC filing identifies Epstein in its trustee
  context, and a commissioned review reports underlying corporate actions,
  but the Ohio charter history has not been retrieved. **The Leslie H. Wexner
  Foundation (Ohio 658659)** is a reported 1993 merger predecessor; do not
  assign Epstein a predecessor role from a survivor-side trustee signature.
- **Morsham Land Corp.** — this is no longer an unresolved survivor question.
  Ohio packet `5422_1190` expressly names **Eastern Ohio Holding Company,
  Inc. (855092)** as the surviving entity in the merger effective
  1995-12-29; Morsham (712296) is one of eight merging corporations. Later
  Franklin deeds independently call Eastern Ohio Morsham's successor by
  merger. A 2016 affidavit then asserts that The New Albany Company LLC is the
  ultimate successor-in-interest to all Morsham real estate and assets. Those
  are three distinct claims: statutory survivor, intermediate recorder-title
  successor, and asserted ultimate asset/title successor.
- **R.A. Property, Inc.** — a 2004 NES, LLC check paid the company $7,173.96
  at 423 West Campus Drive in New Albany.
- **New Albany Realty** — appears as a subsidiary-funding label in a 2005 New
  Albany Company cash-flow report.
- **L.A.W. Plantation Management Corp.** — embedded business-information
  reports place Epstein and Indyke in officer roles at New Albany addresses,
  but no primary registry filing has been recovered.
- **Wexner Investment Company (Ohio 715158)** — the reviewed 1994 dissolution
  lists Wexner, Peggy Ugland, Jeffrey Smith, and Robert Schwartz but not
  Epstein. That is a bounded terminal-filing negative; articles and earlier
  contemporaneous records remain necessary to resolve an earlier-role claim.

The second Dorothy Snow filing wave reviewed ten additional exact charters and
raised primary coverage in the fixed denominator from 25 to 35 rows. The next
wave raised it to 47 by completing the six-company December 14 batch, five
Snow-cohort predecessors in the Autumn Acres merger, and Bearce Hollow. These
waves produced no new direct Epstein-officer positive, but established several
important network, successor, and negative controls:

- **Community Projects, Inc. (Ohio 801367)** — its exact dissolution names
  Wexner as president/director and Indyke as secretary. A separate 1998 filing
  places Community Projects and Epstein-led N.A. Property as the two general
  partners of The New Albany Company Limited Partnership. The limited
  partnership, not Community Projects itself, merged into the LLC.
- **ESPER, INC. (Ohio 686166)** — Ohio and Florida primary records repeat the
  same exact name, Ohio origin, Suite 3710 address, and four-person
  officer/director group. The identity match is high-confidence synthesis; the
  available exact Ohio packets name neither Epstein nor Wexner.
- **New Albany Cardinal Associates (Ohio 749169)** — its short MEX packet
  shares the New Albany Company / W. W. Vaughan III return route with Morsham
  but names no survivor. The reciprocal substantive packet `5422_1190` now
  proves that both were among eight predecessors merged into Eastern Ohio
  Holding Company.
- **Northeast Franklin (710453), New Albany Properties (710695), Plain Designs
  (713839), Hareck Enterprises (713840), Maplegrove Properties (713841), and
  Redwood Stables (713842)** — complete available packets show a recurring
  law-firm administration pattern and unnamed sole shareholders, but no
  Epstein or Wexner. These are bounded filing negatives, not property
  negatives.
- **Blackford Investments, Blendon Farms, Harlem Investment, Ivy Hearth
  Properties, and Rockyriver Properties** — complete articles and
  dissolutions repeat the law-firm administration pattern and unnamed sole
  shareholders without naming Epstein or Wexner. Their no-personal-property
  affidavits do not address real estate.

The December 17 wave raised primary coverage from 47 to 56 rows:

- **Great Eastern Fastening (689907)** merged into **Eastside Industrial
  (689908)** on 1989-12-22, and Eastside dissolved one week later. The
  substantive agreement supplies the survivor edge that Great Eastern's MEX
  stub omits. It transfers any property by operation of law but identifies no
  parcel or final asset recipient.
- **Brewer Farms (689664)** and **Central Falls (689666)** merged out on
  1987-12-31, but their status packets name no survivor. They remain explicit
  status-only transactions; the shared date, counsel, return contact, and
  film adjacency are not enough to create a successor edge.
- **Carlisle Meadows, Daiseyland Farms, Frontier Hills, Gahanna Trucking, and
  Greystone Acres** have complete formation, agent-change, and dissolution
  review. Their terminal packets name law-firm administrators and an unnamed
  sole shareholder, but no Epstein, Wexner, parcel, merger, or asset
  recipient. The no-personal-property affidavits do not rule out real estate.

These nine are bounded packet-level negatives, not ownership negatives.

## Franklin Recorder instrument-family expansion

An exhaustive Franklin pass combined complete exact-party pagination,
full-document OCR variants, and visual review of decisive recorder images.
The normalized parcel chronology contains 116 instrument events. Of those,
110 have public images at some review level; six remain official-detail-only
because the portal exposes no page image. The 24-field family ledgers and the
chronology keep index, OCR, and reviewed-image evidence separate.

The most material results are:

- **Cherry Bottom Investors / Properties:** the 1990 Ohio agreement and the
  property record agree that Properties survived Investors. The 25-instrument,
  162-page recorder family shows Properties as a real landholding and
  disposition vehicle. Epstein signed a 1991 KG deed and a 1992 Gahanna deed
  as Properties vice president. A stale 1991 easement using Investors' name
  does not revive the merged corporation. Properties' $1.08 million KG seller
  mortgage was separately satisfied in July 1993.
- **C-Wren / KG Partners:** C-Wren was one of the two named KG members.
  Epstein signed KG's 1991 partnership certificate and a 1993 Columbus
  right-of-way deed as C-Wren vice president. KG acquired the 33.664-acre
  Christopher Wren tract, borrowed under a Bank One package capped at
  $12 million, and gave Cherry Bottom a subordinate $1.08 million seller
  mortgage. Separate July 1993 instruments released both mortgages. No record
  allocates KG's interest between C-Wren and K-L or establishes Epstein's
  beneficial ownership.
- **Park Properties:** Park was a C.H. Development Group general partner and
  mortgagee, not the record fee owner. One partnership loan was capped at
  $5 million; Dean Fried's 23% guaranty was secured up to $1.15 million. Two
  additional apparent $5 million mortgage recordings were recorder-error
  duplicates, not separate loans. The operative mortgage was fully satisfied
  in 1990 before Park dissolved.
- **Rocky Fork:** four December 31, 1987 deeds identify Rocky Fork as successor
  by merger to Hinson, Brewer Farms, Central Falls, and Bearce Hollow and
  convey their described property interests to The New Albany Company. Epstein
  later signed a 1991 amended partnership certificate as Rocky Fork president
  and Community Projects vice president. A 1992 confirmatory deed moved the
  Ohio partnership's Franklin realty to the Delaware limited partnership.
- **Morsham:** 16 targeted instruments and linked same-closing records
  establish Morsham's large-acreage operation, Eastern Ohio's intermediate
  role, immediate New Albany-to-Summit transfers, and the later residual-title
  affidavit. Dorothy Snow appears as Morsham's tax-mailing contact on the
  1987/1988 acquisition; no reviewed family image names Epstein or Wexner.
- **H.H.D.&B.:** the 1992 Epstein acquisition, 1998 Epstein-to-LLC deed, and
  2001 Rotunda House notice are image-confirmed. Six later OCR hits merely use
  the HHD tract as a neighboring boundary. A $50 million New Albany portfolio
  mortgage does not include parcel 222-001350; that exclusion is not a
  complete parcel-lien negative.
- **INN, City Centre, and N.A. Property:** INN was a hotel-venture limited
  partner, not a verified fee owner. City Centre's partnership conveyed parcel
  010-139305 before cancellation, but its residual asset recipients are
  unnamed. N.A. Property appears in the New Albany partnership structure and
  a School House improvement notice whose blank fee-owner field and
  improvement-lender answer do not resolve title or acquisition financing.

The exact Franklin party index returned no tested-name hit for West First
Plaza, PFI Leasing, either LEWEX charter, or Parkview Financial. Those are
bounded Franklin query results, not proof that the entities never held or
financed property under another name, party, address, or county.

## Reproducible workflow

### 1. Corpus discovery

Search Kabasshouse before the structured Unified email layer. The productive
window is 1998-2008, emphasizing 1999-2006.

Use four query families:

- Corporate maintenance: `officer`, `president`, `director`, `secretary`,
  `treasurer`, `authorized representative`, `managing member`, `registered
  agent`, `statutory agent`, `resolution`, `minutes`, `annual report`,
  `resign`, `remove`, `replace`, `dissolution`, `merger`, `tax return`.
- Property operations: `house`, `home`, `residence`, `lot`, `parcel`, `deed`,
  `title`, `closing`, `property tax`, `insurance`, `utilities`, `repairs`,
  `maintenance`, `landscaping`, `security`, `renovation`, `valuation`,
  `managed properties`, `excluded properties`, `HOA`.
- People: Brent Bradbury, Peg/Peggy Ugland, Marc Lundberg, Jeffrey Schontz,
  Stephen Caplinger, Jerry Barton, Darren Indyke, Richard Kahn, Jack Kessler,
  Gideon Kaufman, Jeffrey J. Smith, Dorothy Snow.
- Addresses: 5906 E Dublin-Granville Road, 5025 Dublin-Granville Road,
  6525 W Campus Oval, 8000 Walton Parkway, 423 W Campus Drive, 41/44 S High
  Street, and 457 Madison Avenue.

For each hit, save the exact raw name, canonical evidence ID, document date,
sender/recipient, exact quote, address, role/property action, and whether the
record is a filing, deed, bank record, shipping record, or secondary index.
Do not turn project labels such as `Duke JV` or `Duffy Condo JV` into legal
entities until another record supplies the legal name.

### 2. Name and role normalization

Normalize without collapsing legally distinct concepts:

- Preserve punctuation and OCR variants (`N.A.`, `N A`, `New Albany`).
- Keep officer/director, trustee, beneficial owner, managing member, agent,
  signer, title owner, payer, and operational manager as separate roles.
- Keep an Ohio address distinct from Ohio formation or qualification.
- Keep a trade name distinct from the corporation that registered it.
- Never merge a later LLC namesake with a historical corporation without an
  entity number or filing-chain proof.

### 3. Ohio filing-image verification

For each candidate:

1. Search the live Ohio portal by exact name and controlled variants.
2. Record zero results as **bounded exact-name negatives**, not proof of
   absence.
3. Open the entire entity history.
4. Inspect every 1980s-2000s filing image, one row per filing.
5. OCR the page, then visually verify names, roles, signatures, addresses,
   checkboxes, and internal dates.
6. Separate statutory-agent changes from officer removals.
7. Preserve discrepancies between portal dates and dates inside images.

No candidate is complete merely because it was absent from the Snow export or
the local corpus. Every user-supplied or externally reported company is added
immediately to `ohio-epstein-officer-filing-coverage.csv` and must resolve to
an exact charter plus reviewed primary filing, a documented false positive, or
a bounded unresolved state. Same-name charters are reviewed independently.
Same-day and adjacent roll/frame packets sharing counsel, addresses, or
signers receive a lateral scan.

Use the built-in Codex Chrome browser to enumerate an entity's history rows and
capture document IDs. Once those IDs are known, the public image endpoint is
batchable: `tools/ingest_ohio.py download-image` downloads one official packet,
and `download-manifest` validates, hashes, deduplicates, and reports a filing
set. The manifest now also includes the complete portal histories for West
First, LEWEX 658220, Park Properties, C-Wren, PFI Leasing, Rocky Fork, City
Centre, Wexner Investment Company, the ten-entity second wave, the Autumn
Acres transaction parties, and the December 17 cohort. Rows
explicitly lacking an image remain `UNAVAILABLE` rather than errors.

The fixed 101-entity portal histories are enumerated. The continuing task is
to follow newly proved survivors and external variants without losing the
fixed denominator. A filing label still cannot determine merger role: Cherry
Bottom Investors has both a
`MERGER/DOMESTIC` row and a MEX row even though it was the predecessor.

### 4. Merger-successor reconstruction

Store mergers as transactions with many parties, not as isolated terminal
labels:

1. preserve every raw history row and exact image ID;
2. group candidate packets using same legal date, roll/frame adjacency,
   sequential receipts, shared counsel, and named-party overlap;
3. read the certificate/agreement and require explicit survivor or resulting
   entity language before confirming an edge;
4. keep approval, execution, effective, recording, portal, and receipt dates
   separate;
5. create predecessor-to-survivor edges and follow the survivor recursively;
6. search county records under the predecessor through the effective date and
   under the survivor afterward.

The sixth step is essential because both the Cherry Bottom and Architonics
agreements transfer property by operation of law. The recorder may therefore
contain no ordinary deed between predecessor and survivor.

### 5. Recorder and parcel verification

For Franklin County:

1. Search the Recorder by exact entity variants and surname-first personal
   names (`EPSTEIN JEFFREY E`, not only normal-order names).
2. Run full-document OCR variants as a separate discovery lane. C-Wren was
   absent from the indexed party fields but present in two decisive images.
3. Paginate the complete result set and deduplicate by instrument/native
   document ID before interpreting counts.
4. Capture instrument number, date, type, grantor, grantee, legal description,
   acreage, and parcel.
5. Crosswalk the parcel through the Auditor for current situs, land use,
   transfer history, assessed owner, and building facts.
6. Pull the deed image before making claims about consideration, return
   address, preparer, tax mailing, or signer title.
7. Treat Recorder index conflicts and portal placeholder dates as unresolved
   until the image is read.
8. Capture every `successor by merger`, `formerly known as`, and
   `successor-in-interest` recital as a dated title-chain edge, then verify the
   corporate genealogy in the Ohio Secretary of State packet. Recorder
   recitals can reveal the missing survivor and affected land, but they are not
   substitutes for the statutory merger agreement.

The local property catalog currently lacks Franklin County coverage. Empty
local results are `local_scope_not_covered`, not authoritative negatives.

### 6. Agent and return-address clustering

Dorothy Snow is the model for this pivot. Build an agent-cluster table with:

- exact agent name and spelling;
- entity and Ohio entity number;
- filing ID/date/type;
- exact agent role;
- return-to name/address;
- signers and officers;
- overlap with the New Albany, Campus Oval, Walton Parkway, or South High
  Street address clusters;
- property instruments or parcels tied to the entity;
- independent corpus mentions.

Rank the result:

- **Tier A:** shared agent plus shared return address plus a matching
  officer/property counterparty.
- **Tier B:** shared agent and one additional address/date/property overlap.
- **Tier C:** shared professional agent only.

Tier C is a search lead, never common-control evidence. The residential
Franklin Recorder hits for a person named Dorothy Snow are excluded as
probable homonyms because no identifier connects them to the filing agent.

## Evidence-state vocabulary

- `primary_image_confirmed` — filing/deed page was OCRed and visually checked.
- `primary_sec_filing_confirmed` — direct SEC text.
- `official_index_plus_auditor_crosswalk` — recorder index and parcel history
  agree, but the deed image still needs review.
- `official_index_only` — useful candidate fact; image not inspected.
- `direct_quote_primary_business_record` — contemporaneous email, fax, check,
  or shipping record.
- `secondary_aggregator_only` — search anchor, not a promoted officer fact.
- `bounded_not_found` — exact source/query/variant set returned zero.
- `access_blocked` or `local_scope_not_covered` — no authoritative conclusion.
- `user_observation_pending_transcription` — supplied clue preserved for
  verification, not treated as a database fact.

## Next verification queue

1. For Brewer Farms and Central Falls, reconcile the recorder recitals naming
   Rocky Fork as successor with their missing reciprocal Ohio statutory
   merger agreements; preserve title-recital and statutory-filing claims as
   separate evidence types.
2. Review Wexner Investment Company's articles `G299_0512`, agent filing
   `H703_1588`, and contemporaneous primary records to resolve the claimed
   earlier Epstein role; do not extrapolate from the 1994 terminal negative.
3. For West First, both LEWEX charters, Parkview, and PFI Leasing, pivot from
   the completed Franklin exact-name/OCR zeros to addresses, parcel references,
   counterparties, UCC records, and neighboring counties.
4. Reconstruct Architonics' post-1989 history and terminal action, then run
   Franklin/Licking property searches for each predecessor before 1989-12-22
   and Architonics after that date.
5. Continue the Cherry Bottom / KG chain after the July 1993 deed to
   Christopher Wren Apartments Limited Partnership and obtain the two
   image-unavailable July 1993 financing-statement releases.
6. Request or recover ESPER rows `G028_1046` and `G350_1509`; determine the
   trade name and whether it creates a property or operational link. Run the
   property search under both the Ohio and Florida identity variants.
7. Follow **Eastern Ohio Holding Company, Inc.**, the confirmed Morsham
   statutory survivor, through its later corporate history and document the
   exact bridge to The New Albany Company LLC. Resolve New Albany Cardinal's
   role from the same nine-entity merger packet without treating the return
   address as the merger proof.
8. Run a parcel-centered lien and title search for HHD parcel 222-001350 and
   predecessor parcel 222-293. The exact-name family is complete, but it cannot
   exclude instruments indexed only by parcel, lender, judgment creditor, or
   prior reference.
9. Resolve **R.A. Property, Inc.** in the Ohio registry and Franklin/Licking
   parcel indexes; test 423 W Campus Drive as an administrative address.
10. Resolve the legal identity behind **New Albany Realty** and the 2005
   project/JV labels using deeds, mortgages, tax schedules, and full
   attachments.
11. Retrieve a primary filing for **L.A.W. Plantation Management Corp.**
   before using the embedded officer claims.
12. Retrieve the full Ohio histories for **The Wexner Foundation (436405)**
   and reported merger predecessor **The Leslie H. Wexner Foundation
   (658659)**, including both sides of the 1993 merger and the September 2007
   action said to remove Epstein. The 2008 statutory-agent change is not that
   event.
13. Add Franklin County Recorder/Auditor coverage to the public-records catalog
   so future address and party pivots are reproducible without manual UI work.
14. Continue the fixed Snow denominator after the December 17 packets, using
    the lowest unreviewed exact agent-date cluster and preserving separate
    exact-charter histories, terminal packets, and reciprocal merger parties.

## Maintenance rule

Append evidence rows; do not overwrite historical roles with current status.
Update the entity index only after a supporting evidence row exists, and keep
facts, source-backed inferences, and unresolved search leads in separate
columns.
