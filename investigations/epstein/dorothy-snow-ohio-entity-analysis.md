# Dorothy Snow Ohio entity-cohort analysis

Date: 2026-07-30

## Outcome

The user-supplied Ohio Secretary of State agent/registrant export establishes a
closed starting universe of 101 entities associated with Dorothy Snow. It is
large enough to support a real cohort analysis, but its date field is
`Agent Effective Date`, not formation date. Its `Dead` status is also
non-diagnostic: the export does not say whether an entity merged, dissolved,
converted, surrendered, or was administratively cancelled.

The filing-history reconstruction is now complete for the fixed 101-entity
denominator. Every exact live Ohio history has been enumerated and every
available filing page has been visually reviewed. The manifest contains 302
history rows: 254 reviewed images and 48 rows whose images are unavailable.
The review-state breakdown is 88 `primary_filings_reviewed`, two
`primary_available_filings_reviewed`, ten `primary_merger_reviewed`, and one
`history_enumerated_image_unavailable`. An unavailable image is preserved as
a source limit, not converted into a negative finding.

Primary images confirm six direct Epstein-role corporations inside the Snow
denominator: INN Investment, Cherry Bottom Investors, LEWEX Ohio 658220, West
First Plaza, Park Properties, and C-Wren Investment.
Corporate filings, merger chains, property instruments, corpus mentions, and
professional-provider changes remain separate dated events. Shared agent,
same-day activity, or a return address creates a lead; it does not establish
ownership or common control.

The original priority model was not completeness-safe. West First Plaza, Park
Properties, C-Wren, and the distinct LEWEX charter were all present in the
101-row table but had not been substantively reviewed; 80 rows were still
`not_started` before the coverage audit. No row is now `not_started` or has a
pending exact-history status. Exact corpus searches also did not recover West
First Plaza. The completion layer was therefore the filing histories and
scanned terminal packets, not company-name scoring or email hits.

The merger result changes the shape of the project. One December 1989 agreement
merged 23 corporations into Architonics, Inc.; 18 of those predecessors plus
Architonics are in the 101-row export, while five predecessors are outside it.
The Snow export remains the fixed denominator, but every named transaction
party and every external officer-company seed must enter a separate rolling
coverage ledger. That ledger now contains 112 exact charters: all 101
denominator entities plus 11 external entities. The external set includes
primary-confirmed PFI Leasing, Rocky Fork Development, and City Centre
Investment.
Wexner Investment Company is also in the ledger: its 1994 dissolution does not
list Epstein, so any claimed earlier role remains unresolved rather than
discarded.

Investigation lead #83246 tracks the corporate-file work. Lead #84287 tracks
the successor-aware Franklin County recorder sweep.

## Source and denominator

Source:
`/Users/travcole/Downloads/Ohio Secretary of State Business Search-AgentRegistrant-.csv`

SHA-256:
`910362535be7d588022b6a7183f5e7da0d0747c52d958056885388590ca8dc74`

| Measure | Count |
|---|---:|
| Unique entity rows / Ohio entity numbers / normalized names | 101 / 101 / 101 |
| For-profit corporations | 99 |
| Nonprofit corporations | 1 |
| Domestic LLCs | 1 |
| Export status `Dead` | 96 |
| Export status `Active` | 2 |
| Export status `Cancelled` | 2 |
| Export status `Permanently Cancelled` | 1 |
| Franklin County rows | 100 |
| Agent-effective dates in 1987-1988 | 85 |
| 1987-1988 rows on one of 11 shared dates | 76 |
| Rows in same-date consecutive-number runs | 62 |

Thirty-eight of 44 rows with a 1987 agent-effective date fall in December.
Fifty-six of the 101 legal names contain at least one declared
property/vehicle term such as `land`, `property`, `development`, `farm`,
`acre`, `holding`, `investment`, `improvement`, `conservation`, `realty`, or
`management`. These are triage signals only.

The export does not supply:

- formation or qualification date;
- whether Snow was the initial or a replacement agent;
- Snow's address or the appointment instrument;
- prior/successor agents;
- filing history or image IDs;
- officers, directors, incorporators, signers, or owners;
- principal, preparer, or return-to addresses;
- merger/dissolution date or terminal cause;
- merger constituents or survivor;
- parcel, deed, mortgage, easement, or other property data.

## Initial anchors

### INN Investment Corp. - Ohio 678033

This is now primary-image confirmed. Ohio packet `H363_1780`, filed
1992-06-02, identifies Leslie H. Wexner as director, Jeffrey E. Epstein as
president, Robert S. Schwartz as assistant secretary, and Dorothy Snow as
statutory agent. Epstein and Schwartz signed the certificate. The action was
authorized by an unnamed sole shareholder; the filing therefore does not prove
who owned the company.

The affidavit says the corporation had no **personal property** in an Ohio
county. That is not a statement that it held no real property, and dissolution
does not supply a corporate survivor or identify an asset recipient.

Exact-name local corpus searches returned no Kabasshouse or Unified-email hits.
The official filing remains the controlling evidence.

### Cherry Bottom Investors / Cherry Bottom Properties - Ohio 719718 / 719719

The 1990 merger packet is the first direct demonstration of how to solve an
opaque `Merged Out of Existence` row. Jeffrey E. Epstein signed as president of
Cherry Bottom Investors and vice president of Cherry Bottom Properties.
Effective at close of business on 1990-08-31, Investors merged into Properties,
which survived under the name Cherry Bottom Properties, Inc.

The three-page Investors MEX packet `G946_1539` does not name the survivor.
Companion packets `G946_1531` and `G946_1533` contain the controlling
agreement. It says all assets and property interests vest in the survivor
without further act or deed and that real-estate title is not impaired.
Dorothy Snow was statutory agent; Stephen P. Campbell was secretary of both.
Wexner and the shareholders are not named in that transaction.

Properties' later dissolution, filed 1998-12-28 as `199836304760`, lists Leslie
H. Wexner as the sole listed director and president at N.A. Property, Inc.,
Darren K. Indyke as secretary at J. Epstein & Company, Inc., and Peggy W.
Ugland as statutory agent at N.A. Property. This is a later officer
observation, not proof of the 1990 shareholder identities.

### Direct-role anchors recovered by the coverage audit

Four Snow-export companies moved from unreviewed to primary-confirmed:

- **LEWEX, Inc. - Ohio 658220.** The complete available history shows that
  this charter formed on 1985-07-08 as **Samax Trading Corporation**, with
  Snow as incorporator/original agent, and changed its name to LEWEX in 1987.
  Packet `H503_1252`, filed 1992-12-22, identifies Wexner as director and
  president, Epstein as vice president and treasurer, Jeffrey J. Smith as
  secretary, and Snow as statutory agent. Neither man appears in the earlier
  available packets, so the filing history does not establish when either
  relationship began.
- **West First Plaza, Inc. - Ohio 777500.** Articles `G909_1798` and
  dissolution `H503_1258` establish Snow's original appointment and later
  identify Epstein as president, Wexner as director, George M. Pryor Jr. as
  vice president, and Smith as secretary.
- **Park Properties, Inc. - Ohio 626053.** Packet `H526_0788`, filed
  1992-12-22, identifies Epstein as vice president and Wexner as sole director
  and president; Snow accepts a subsequent-agent appointment in the same
  packet.
- **C-Wren Investment Corp. - Ohio 803531.** Packet `9420_1032`, filed
  1993-12-30, identifies Epstein as vice president and treasurer and Wexner as
  sole director and president.

Three externally named companies outside the Snow denominator are also now
primary-confirmed:

- **PFI Leasing, Inc. - Ohio 624047.** Packet `H043_1630`, filed 1990-12-26,
  identifies Epstein as vice president and treasurer and Wexner as director
  and president.
- **Rocky Fork Development Corporation - Ohio 706978.** Packet `H509_0296`,
  filed 1992-12-29, identifies Epstein as vice president and Wexner as sole
  director and president. The separately reviewed 1987 agreement
  `G313_0688` identifies Rocky Fork as survivor of Bearce Hollow, Inc.
  Neither man appears in that earlier packet.
- **City Centre Investment Corp. - Ohio 712332.** Packet `5024_1021`, filed
  1994-12-28, identifies Epstein as president and Wexner as director. It was
  submitted by Vorys, Sater, Seymour and Pease, giving primary evidence of the
  later Ohio filing channel.

Every one of these terminal actions was a dissolution rather than a merger, so
none supplies a corporate survivor or asset recipient. Each also refers to an
unnamed sole shareholder. The personal-property affidavits do not answer
whether a corporation held real estate.

The audit also validates roll/frame adjacency as a discovery method.
`H503_1252` spans the distinct LEWEX packet and the immediately following
`H503_1258` packet is West First Plaza. Both were filed on 1992-12-22, returned
to the same firm and contact, and contain Epstein/Wexner officer lists. A
lateral scan of neighboring packets can therefore recover related companies
that a person-name index cannot.

### Architonics 23-company merger - Ohio 713548

Primary packet `G774_0107` identifies Architonics as the survivor of 23 named
Ohio corporations effective 1989-12-22. Richard W. Rubenstein and Dorothy Snow
signed as vice president and secretary for the survivor and every predecessor.
The agreement transfers all predecessor assets, property interests, and
obligations to Architonics and preserves real-estate title.

Ohio stored the transaction as a nine-page substantive merger packet followed
by 23 separate three-page predecessor MEX stubs in constituent-list order.
Frames run from `G774_0116` through `G774_0182`; receipt numbers run from 48726
through 48748. The complete exact histories and party-specific stubs for all
18 in-cohort predecessors have now been visually reviewed, replacing the
initial sequence-derived candidates with exact-charter evidence. The five
off-export predecessors remain separate coverage items; adjacency alone is
not treated as primary review of their individual stubs. Neither Epstein nor
Wexner appears in the substantive merger agreement or the reviewed in-cohort
formation/stub packets, so the cluster is confirmed corporate structure, not
confirmed common ownership.

Architonics' own complete history now closes an important successor gap.
Articles `G284_0971` identify Robert N. Wistner as incorporator and original
agent. Dissolution packet `G805_0277` shows that Architonics dissolved on
1989-12-29, only seven days after absorbing the 23 predecessors. Stanley
Schwartz Jr. was chairman/president, Richard W. Rubenstein vice
president/treasurer, Snow secretary and statutory agent, and Schwartz and
Rubenstein the listed directors. An unnamed sole shareholder authorized
dissolution. The packet names no final asset recipient or parcel, and its
no-personal-property affidavit does not address real estate. The predecessor
property chain must therefore continue into Architonics through 1989-12-29
and then branch to deeds, distributions, assignments, or other primary
instruments; the signers alone do not supply that edge.

The Franklin County Recorder index supplies the first concrete post-merger
property trail. It records Architonics acquiring 24.642 acres from Ted R.
Meteer on 1987-12-08 (`198712080212780`), conveying 24.642 acres to New Albany
Co. on 1989-12-28 (`198912280188790`), and conveying a multi-tract property
set to New Albany Co. on 1989-12-29 (`198912290189094`). The latter two dates
are six and seven days after the merger, and the final deed date is also the
dissolution date.

That timing is strong successor-disposition evidence, but it does not by
itself show which predecessor supplied any parcel, whether every vested asset
was conveyed, whether a deed was caused by the merger, or who beneficially
owned the corporations. The deed images and legal descriptions must be
compared against each predecessor before assigning parcel lineage.

### Autumn Acres seven-predecessor merger - Ohio 706250

Primary packet `H052_1482` identifies Autumn Acres as the survivor of
Deerfield Meadows, Landes Management, Maycor, New Albany 74, 129 Associates,
Rockyridge Development, and Tumbleweed Estates effective 1990-12-28. Richard
W. Rubenstein and Dorothy Snow signed as vice president and secretary for the
survivor and all seven predecessors. Each predecessor's sole shareholder is
referenced but unnamed. Neither Epstein nor Wexner appears.

The agreement transfers all predecessor assets, property, real-estate
interests, obligations, and liabilities to Autumn by operation of law. It does
not identify a parcel. Each short constituent MEX packet omits the survivor;
the substantive agreement supplies the missing edge. The portal shows Autumn
dissolving the next day, but image `G052_1517` is unavailable, leaving the
ultimate asset recipient unresolved.

Ohio charter 698295 also supplies an identity correction. It was formed as
New Albany 84, Inc. and renamed New Albany 74, Inc. on 1987-04-16. They are
one corporation, not two entities, and both names must be searched in property
and corpus records.

### Bearce Hollow into Rocky Fork - Ohio 689665 / 706978

Agreement `G313_0688` defines Bearce Hollow as the merging corporation and
Rocky Fork Development Corporation as survivor effective 1987-12-31. The
portal history independently ties Bearce's exact name to charter 689665 and
the reciprocal merger/MEX rows. The agreement transfers any Bearce property
and real-estate interests to Rocky Fork without another deed, but identifies
no actual holding.

Harold L. Levin was president of both entities; Paul S. Coppel was Bearce
secretary; Richard W. Rubenstein was Rocky Fork secretary. The agreement
describes a mutual shareholder and Bearce's sole shareholder, but names no
person. Epstein, Wexner, and Snow are absent from the 1987 merger packet.
Rocky Fork's 1992 dissolution later names Epstein and Wexner, creating a
confirmed corporate-successor link without retroactively assigning them a
1987 role.

### December 17 agent cluster: full-history controls and unresolved mergers

Nine additional Snow-cohort charters from the 1987-12-17 agent-date cluster
now have complete available primary-file review. The results show why shared
agent dates and adjacent film frames must remain discovery clues:

- **Brewer Farms, Inc. (689664)** and **Central Falls, Inc. (689666)** each
  merged out effective 1987-12-31. Their three-page MEX packets
  `G313_0675` and `G313_0685` name no survivor, other constituent,
  shareholder, parcel, or asset recipient. Shared date, counsel, return
  contact, and nearby frames do not establish a common survivor.
- **Carlisle Meadows (689663), Frontier Hills (689662), Gahanna Trucking
  (689906), and Greystone Acres (689446)** dissolved on 1988-12-28.
  **Daiseyland Farms (689454)** dissolved on 1990-12-28; its terminal packet
  uses the spelling `Daisyland`, preserved as a document variant rather than
  a separate corporation. Each dissolution leaves the sole shareholder
  unnamed, and the no-personal-property affidavit does not address real
  estate.
- **Great Eastern Fastening (689907)** merged into **Eastside Industrial
  (689908)** effective 1989-12-22 under agreement `G769_0688`. Eastside then
  dissolved on 1989-12-29. The agreement supplies the survivor edge omitted
  from Great Eastern's MEX stub, but neither the merger nor the dissolution
  identifies an actual parcel or the recipient of Eastside's remaining
  assets.

Epstein and Wexner do not appear in the reviewed packets for these nine
charters. That is a bounded filing-level negative, not proof that an unnamed
shareholder or undisclosed interest was unrelated.

### Community Projects, Inc. - Ohio 801367

The exact-charter file is now reviewed. The 1998 dissolution
`199831701001` lists Leslie H. Wexner as the sole listed director and
president and Darren K. Indyke as secretary. The principal office is New
Albany; the packet gives One Whitebarn Road and 5906 East Dublin-Granville
Road as their addresses.

A separate September 1998 filing `199826701876` identifies Community
Projects, Inc., an Ohio corporation signed by Wexner as president, and N.A.
Property, Inc., signed by Epstein as president, as the two general partners of
The New Albany Company Limited Partnership. Exact name, jurisdiction, officer,
chronology, and address make the join to charter 801367 a high-confidence
identity synthesis, but the contextual page does not print the Community
Projects charter number.

The merger distinction is important. Packet `199828200362` says the limited
partnership, Ohio 958102, merged into The New Albany Company LLC, Ohio
1034132. Community Projects itself separately dissolved. The reviewed evidence
does not show Epstein as a Community Projects officer.

### Morsham Land Corp. - Ohio 712296

Morsham is part of a nine-entity Snow agent-date cohort on 1987-12-14. Franklin
Recorder images show a 50.086-acre acquisition recorded 1988-01-06, multiple
easements, and later dispositions. The acquisition deed sends Morsham tax
statements to Dorothy Snow at 41 South High Street, Suite 2300. That is direct
administrative evidence, not ownership evidence. Filing `G290_1448` separately
confirms Snow as incorporator and original statutory agent.

The former survivor gap is closed. Ohio packet `5422_1190` identifies
**Eastern Ohio Holding Company, Inc. (855092)** as the surviving entity in a
nine-party merger effective 1995-12-29. Morsham and seven other corporations
are the merging predecessors. The form's name-change field is blank, so the
later deed phrase “Morsham ... n.k.a. Eastern Ohio” is conveyancing shorthand,
not a statutory name change. Later deeds more precisely call Eastern Ohio
“successor by merger to Morsham” and convey Morsham-derived tracts to The New
Albany Company Limited Partnership.

A 2016 title affidavit by The New Albany Company LLC's treasurer asserts that
the LLC is successor-in-interest to all Morsham real estate and assets. That is
an attributed ultimate title/asset claim; it does not identify the intervening
corporate mechanism from Eastern Ohio to New Albany. No reviewed Morsham
recorder-family image names Epstein or Wexner.

### Esper, Inc. - Ohio 686166

The Ohio file now confirms the strongest cross-registry match from the 101-name
crosswalk. The 1988 dissolution `G343_1665` lists Harold L. Levin as
director/president/treasurer, Stephen P. Campbell as vice
president/secretary, and John W. Kessler and John B. McCoy as directors. It
uses 41 South High Street, Suite 3710 for Levin and Campbell.

Florida Sunbiz record
[P12512](https://search.sunbiz.org/Inquiry/CorporationSearch/SearchByNumber?searchNumber=P12512)
uses the exact name, identifies Ohio as the formation state, gives 41 South
High Street, Suite 3710, Columbus, and lists Harold L. Levin as `PTD`, with
Stephen P. Cambell, John W. Kessler, and John B. McCoy in additional roles.

The six-field match is a high-confidence identity synthesis, not a
single-document charter-number fact because Sunbiz does not print Ohio charter
686166. That address/person combination independently overlaps the verified
Parkview/LEWEX trail: Parkview's move to 41 South High was signed by Levin as
vice president. The available exact Ohio packets name neither Epstein nor
Wexner; two history rows lack live images. The Florida registered-agent
address does not establish Plantation operations or a connection to the
Georgia hunting property.

### New Albany Properties and New Albany Cardinal

**New Albany Properties, Inc. - Ohio 710695** dissolved on 1988-12-28 rather
than merging. Its complete available articles and dissolution identify Robert
N. Wistner and later Schwartz-Kelm-Warren-Rubenstein personnel; an unnamed
sole shareholder authorized dissolution. Neither Epstein nor Wexner appears.
This entity is legally distinct from N.A. Property, Inc., Ohio 832364.

**New Albany Cardinal Associates, Inc. - Ohio 749169** merged out on
1995-12-29. Its short packet `5422_1201` routes a later status statement to
New Albany Company and W. W. Vaughan III at 5906 East Dublin-Granville Road
but does not name the survivor. The substantive reciprocal certificate
`5422_1190` now supplies the missing edge: New Albany Cardinal was one of eight
corporations merged into Eastern Ohio Holding Company. The certificate—not the
shared return address—proves the common survivor.

### December 10, 1987 four-company comparison

Plain Designs 713839, Hareck Enterprises 713840, Maplegrove Properties 713841,
and Redwood Stables 713842 were all formed in the same Snow agent-date batch
and dissolved on 1988-12-28. Complete available packets repeat the same
administrative pattern: Snow as incorporator/original agent and later
secretary, Stanley Schwartz Jr. as chairman/president, and Richard W.
Rubenstein as vice president/treasurer. Each dissolution refers to an unnamed
sole shareholder and a no-personal-property affidavit.

No Epstein or Wexner appears in those eight packets. This is a bounded
exact-file negative, not proof the entities were unrelated or held no real
estate. Shared counsel, templates, dates, and officers establish an
administrative cluster but not common beneficial ownership.

### The explicit 46-corporation December 1988 filing batch

Argotron Corporation's dissolution packet `G532_0974` contains an unusually
valuable seventh page: a Schwartz, Kelm, Warren & Rubenstein cover letter dated
1988-12-28 that transmits dissolution papers for 46 named corporations in one
messenger submission. The list expressly includes Argotron, Wheaton Company,
Mackinaw Marketing Co., and Scripton Products, Inc. The letter has now been
crosswalked to 46 unique Ohio charters, and every exact live filing history
has been enumerated and reviewed. All 46 terminal actions are dissolutions
effective 1988-12-28; none is a merger.
The row-by-row primary-source mapping is preserved in
`ohio-argotron-46-dissolution-crosswalk.csv`.

The reviewed packets repeat a strong administrative pattern: Snow often
appears as incorporator/original agent and later secretary, Stanley Schwartz
Jr. and Richard W. Rubenstein appear as officers/directors, and an unnamed
sole shareholder authorizes dissolution. The exact pattern varies by entity,
so the 46 histories remain separate evidence records. Neither Epstein nor
Wexner appears in any of the reviewed corporate packets. No packet identifies
a merger, corporate survivor, parcel, or asset recipient. The
no-personal-property affidavits do not address real estate.

Four of the final histories closed in this batch were The Encee Holding Corp.
693864, NELC, Inc. 695020, Great Eastern Fastening Corp. II 705933, and Petel
of Columbus Co. #1, Inc. 701784. Encee and NELC have unusually specific
articles: each says it was formed solely to acquire real or personal property
“as agent for others,” without naming the principal or beneficial owner.
Great Eastern Fastening Corp. 689907 formally consented to the similar name
used by Great Eastern Fastening Corp. II; that proves a naming relationship,
not ownership, control, or merger. Petel follows the common
Schwartz/Rubenstein/Snow dissolution pattern and leaves the sole shareholder
unnamed.

Main-High Development Corp. 679415 was reviewed in the same completion pass
but is not printed in the 46-company letter. Its 1990 dissolution identifies
John W. Kessler and Daniel M. Galbreath as directors, Snow as
president/treasurer, and Judy McCoy as vice president/secretary. Its
authorizing shareholders are unnamed.

The cover letter materially strengthens the administrative-cluster evidence:
the 46 companies were not merely inferred to be related from a shared date,
template, address, or adjacent film frame; the law firm directly grouped their
dissolutions in one submission. It still does not establish a common
shareholder, beneficial owner, client, asset pool, property portfolio, or
Epstein/Wexner relationship. Each exact charter and each property name must
therefore remain a separate evidence track. The corrected row-by-row mapping
is preserved in `ohio-argotron-46-dissolution-crosswalk.csv`, with separate
formation, agent-appointment, terminal-document, and shared-cover fields.

### Entity-identity warnings

- LEWEX, INC. in the Snow export is Ohio 658220. It must not be merged by name
  with Parkview Financial/former LEWEX, INC., Ohio 623762. Both are now
  independently confirmed Epstein/Wexner corporations.
- New Albany Properties, Inc. is Ohio 710695. It must not be merged by name
  with N.A. Property, Inc., Ohio 832364.
- A current or later LLC with a similar name is not the historical corporation
  without a primary filing chain.

## The original 15-entity pilot

The pilot tested a user-reported positive, an independently supported New
Albany bridge, a complete same-agent-date comparison set, and several strong
name leads. It remains useful for triage, but it is not a completion boundary:

1. INN Investment Corp. - 678033.
2. Esper, Inc. - 686166.
3. Community Projects, Inc. - 801367.
4. Autumn Acres, Inc. - 706250.
5. Blackford Investments, Inc. - 709782.
6. Blacklick Properties, Inc. - 710873.
7. Blendon Farms, Inc. - 711268.
8. Harlem Investment Corporation - 712106.
9. Ivy Hearth Properties, Inc. - 712170.
10. Leeace Inc. - 712264.
11. Morsham Land Corporation - 712296.
12. Rockyriver Properties, Inc. - 712441.
13. LEWEX, INC. - 658220.
14. New Albany Properties, Inc. - 710695.
15. New Albany Cardinal Associates, Inc. - 749169.

Any survivor or resulting entity needed to complete a chain is added even if
Snow does not appear in its current record. Park Properties has now been
reviewed and confirmed. First Columbus Land Company 785297 has also been
reviewed: its available articles name Ted B. Hipsher as incorporator and Snow
as original agent, identify no parcel, and leave two later portal rows
image-unavailable. Its land-name signal therefore supports a county-record
search but is not title evidence.

## Filing-history workflow

For every entity:

1. Preserve the export observation under its exact source meaning.
2. Capture the current entity header, agent, address, status, and all history
   rows.
3. Inventory every expected filing image and page before selecting apparently
   relevant documents.
4. OCR for discovery, then visually verify names, roles, signatures,
   checkboxes, addresses, and dates.
5. Separate execution, notarization, receipt, filing, approval, recording, and
   effective dates.
6. Classify the Snow event as initial-agent appointment, later agent change,
   bulk change, or unresolved.
7. Store every person and organization under the exact stated capacity.
8. Extract preparer, return-to, agent, officer, signer, director, incorporator,
   organizer, notary, and address observations as separate event-party rows.
9. Classify terminal actions as merger, consolidation, conversion,
   dissolution, cancellation, surrender, or unknown.
10. Link each promoted fact to the exact image ID, page, quote, and
    verification state.

Completion gates now override the original name/date priority:

1. Every one of the 101 Snow rows must have a filing-history success or
   documented error state; an errored enumeration must be retried.
2. Every user-reported, reporting-derived, merger-party, officer-address, or
   filing-neighbor company must enter
   `ohio-epstein-officer-filing-coverage.csv`.
3. Each coverage-ledger row must resolve to an exact charter plus reviewed
   primary filing, a documented false positive, or a bounded unresolved state.
4. Every terminal packet is reviewed even when the name score is low and the
   local corpus returns no hit.
5. Same-name charters branch into separate reviews; a collision is never a
   reason to suppress one charter.
6. Same-day and adjacent roll/frame packets sharing counsel, return contact,
   address, or signers receive a lateral scan.
7. Corpus states name their scope. `no_substantive_local_hit` is not a registry
   negative.

The built-in Codex Chrome browser is the approved interactive route for
enumerating each entity's filing-history rows and document IDs. Once an image
ID is known, `tools/ingest_ohio.py download-image` and `download-manifest`
retrieve, validate, hash, deduplicate, and report the official PDFs directly.
No separate Firefox or desktop-browser permission is needed. The remaining
automation gap is a durable serial history-row harvester, not PDF downloading.

## Merger and dissolution resolution

Yes, the merger target is usually recoverable, but not from `Dead` status or an
MEX stub alone. The controlling source is the substantive certificate or
agreement naming each party and explicitly identifying the survivor or newly
resulting entity.

Two historical storage patterns are now primary-confirmed:

- Cherry Bottom: a constituent can have both a `MERGER/DOMESTIC` row and a
  separate MEX row, while the MEX packet itself omits the survivor.
- Architonics: one substantive MER packet can govern a following block of many
  short MEX packets, each representing one predecessor.

For each possible terminal transaction:

1. retain every raw portal label, displayed date, entity number, document ID,
   receipt number, roll/frame interval, preparer, and return address;
2. treat `MER`, `MEX`, `FMR`, dissolution, conversion, and consolidation labels
   as discovery signals rather than party-role proof;
3. cluster candidate packets by same document, named-party match, legal date,
   contiguous roll/frame interval, sequential receipt number, and shared
   counsel or return address;
4. read the complete substantive image bundle and extract every named party,
   entity number, jurisdiction, signer, capacity, and explicit party role;
5. create one transaction row and one party row per constituent; derive
   directed `merged_into` edges only after the agreement identifies a survivor;
6. preserve board approval, execution, effective, recording, receipt, and
   portal-display dates separately;
7. search every named party, including parties outside the original Snow
   export, for reciprocal rows and later actions;
8. follow the survivor recursively until an active entity, dissolution, later
   merger, or documented gap;
9. model consolidation separately because it creates a new resulting entity
   rather than preserving one constituent as survivor;
10. keep dissolution separate because it has no corporate survivor.

The durable implementation is
`ohio-sos-merger-transactions.csv` plus
`ohio-sos-merger-parties.csv`. The party table also carries the property-search
rule for each predecessor/survivor chain.

A dissolution signer's identity does not establish an asset recipient. Asset
distribution requires a deed, assignment, distribution schedule, or other
primary instrument.

Current [Ohio Form 551](https://www.ohiosos.gov/assets/551.pdf) confirms the
field pattern expected in a merger filing, but each historical image controls
for the 1980s-1990s cohort.

## Property-record workflow

Property research begins with Franklin and Licking Counties and expands when a
filing, address, legal description, parcel, or counterparty identifies another
county. Each exact and historical legal-name variant must be searched as both
grantor and grantee.

The tested property route for the original 14 property/network seeds is:

- Franklin County for all 14 pilot entities;
- Licking County from the outset for Morsham, Community Projects, New Albany
  Properties, New Albany Cardinal, and Blacklick Properties;
- Delaware County only when an address, parcel, legal description, or controlled
  geographic-name test supports it.

Name variants materially change results. A prior Franklin Recorder search for
`MORSHAM LAND CORPORATION` returned no rows, while `MORSHAM LAND CORP` returned
the family. C-Wren's decisive partnership and right-of-way instruments did not
index C-Wren as a party at all; exact full-document OCR of
`C-Wren Investment Corp.` found them. Every query set must therefore combine
the complete party index with OCR variants, suffix substitutions,
punctuation/spacing variants, former names, and primary-confirmed merger
predecessors/survivors.

The same official index now validates the successor-aware branch for
Architonics: search the predecessor through the merger date, the survivor from
that date forward, and both names around the effective date. Capture any
`successor by merger`, `formerly known as`, affidavit, reference-instrument,
or consideration language from the deed image. A survivor's later conveyance
is a disposition fact; it is not enough to assign the land to a particular
predecessor.

Capture more than deeds:

- deeds and land contracts;
- mortgages, assignments, releases, and satisfactions;
- easements and releases;
- options, leases, and memoranda;
- plats, restrictions, and dedications;
- certificates/affidavits of merger;
- notices of commencement;
- parcel splits and consolidations;
- auditor ownership, transfer history, situs, acreage, and tax-mail data;
- zoning, annexation, and development proceedings where a parcel/project is
  identified.

For every instrument, capture execution and recording dates, type, all parties,
preparer, return-to and tax-mail addresses, consideration or loan amount,
parcel/account, acreage, and legal description. Preserve the owner name as
recorded on the historical instrument; store later successor relations
separately.

A merger may transfer title by operation of law, so the absence of an ordinary
deed between predecessor and survivor is not a negative. Search merger
certificates and affidavits and check the statute in force on the effective
date.

The current local property database does not provide a reliable Ohio negative:
an unavailable or uncovered source must remain `source_unavailable` or
`local_scope_not_covered`.

Esper joins the property route after its Ohio filing supplies a principal
address, parcel, legal description, or other substantive property signal.

The targeted Franklin implementation is now substantive even though the local
normalized property database remains uncovered. Complete exact-party
pagination over 49 name variants was paired with OCR-variant searches and
direct page-image retrieval. The consolidated chronology contains 116 events:
110 have public recorder images at some review level, while six are
official-detail-only because the public portal supplies no page image. Separate
24-field family ledgers cover Cherry Bottom, Park Properties, Rocky Fork,
Morsham, C-Wren/KG, and HHD.

The completed families show why source states must remain separate:

- the party index finds candidate instruments but can omit an entity embedded
  in the document;
- OCR discovers body-text and boundary references but can produce
  false-positive adjacency hits;
- the reviewed image controls capacity, consideration language, signature,
  legal description, successor recital, and whether an apparent debt is a
  duplicate or a real transaction.

Delaware County exact-name recorder searches were fully paginated from 1753
through 2026 and returned no exact target hits. Licking County's PAX route was
account-gated and OnTrac denied automated access. Delaware is therefore a
bounded exact-search zero; Licking remains `access_blocked`, not a negative.
The absence of full local Franklin/Licking ingestion remains an infrastructure
coverage gap rather than a reason to discard the completed direct-source work.

Authoritative starting routes include the
[Franklin Recorder](https://www.franklincountyohio.gov/Agency-Directory/Recorder/Real-Estate/Public-Records-Search),
[Franklin Recorder direct search](https://franklin.oh.publicsearch.us/),
[Franklin Auditor](https://property.franklincountyauditor.com/_web/search/commonsearch.aspx?mode=owner),
[Licking Recorder](https://lickingcounty.gov/depts/recorder/default.htm),
[Licking tax parcel viewer](https://apps.lickingcounty.gov/maps/taxparcelviewer/default.html),
[Delaware Recorder](https://recorder.co.delaware.oh.us/records-search-page/),
and [Delaware Auditor](https://auditor.co.delaware.oh.us/real-estate-data-property-search/).
Login gates, maintenance, and incomplete historical digitization remain access
states requiring a manual acquisition path.

## Professional-provider and law-firm track

The provider question does not resolve to one firm-wide successor.

The current evidence supports several role-specific paths:

- A primary Ohio appellate opinion establishes that Russell Kelm left in late
  December 1995, the firm became Schwartz, Warren & Ramirez, and the
  partnership converted to Schwartz, Warren & Ramirez L.L.C. on
  1996-02-01. A retrospective account based on former-partner interviews says
  proposed mergers failed and the firm ceased operating in December 1996.
- Wexner's personal/group Schedule 13D cover contact moved from Robert S.
  Schwartz at Schwartz, Warren & Ramirez on the 1996-02-02 filing to Dennis J.
  Block at Weil, Gotshal & Manges by the
  [1996-04-03 amendment](https://www.sec.gov/Archives/edgar/data/701985/000090951896000087/0000909518-96-000087.txt).
  The February filing already directed transaction notices to Weil, showing
  overlapping, lane-specific roles rather than a clean universal cutover.
- Weil remained the reviewed Schedule 13D contact through 1998. This proves a
  securities/transaction lane, not general Ohio counsel for every entity.
- The Cherry Bottom file now establishes a matter-level filing-channel
  transition. The 1990 merger was returned to Schwartz, Kelm, Warren &
  Rubenstein, attention T. Hipsher, at 41 South High Street. The 1998
  dissolution was returned to `V.S.S. AND P`, attention T. Hipsher, at
  52 East Gay Street. Vorys' official history identifies 52 East Gay as its
  long-standing office, supporting the interpretation that the later
  abbreviation refers to Vorys, Sater, Seymour & Pease. This is continuity of
  a named filing contact on one corporate matter, not proof that all Wexner
  work moved firms on one date.
- The 1994 City Centre Investment and Wexner Investment Company dissolution
  packets were both submitted by Vorys, Sater, Seymour and Pease. These are
  direct primary observations of a later Ohio corporate-filing channel. They
  strengthen the provider-transition hypothesis while still falling short of
  a firm-wide engagement record. Wexner Investment's cover letter also appears
  to copy the City Centre company name, so packet text must be checked rather
  than treated as clean metadata.
- Separate evidence also supports Vorys as a candidate for other Ohio company,
  tax, and property work. Reported 1996 matters place Vorys with The
  Limited/Wexner, while 2000-2005 primary courier records show repeated
  packages from Epstein-affiliated offices to Vorys attorneys in tax, real
  estate, corporate, and other practices. The package contents remain unknown.
- Robert S. Schwartz remained N.A. Property's statutory agent until the
  [2008 replacement filing](https://bizimage.ohiosos.gov/api/image/pdf/200826701516).
  The agent role therefore survived the old firm's closure and cannot be used
  as a proxy for current counsel.
- Dorothy Snow's employment or professional title at the old firm remains
  unverified. The export has no agent address, preparer, return-to field, or
  letterhead and cannot establish her employer.

The old firm itself appears to have converted and closed, not merged wholesale
into another firm. The analysis must therefore use a dated entity-by-entity
sequence:

- last Snow/old-firm agent, preparer, return-to, signer, and address
  observation;
- first later agent/preparer/return-to/signer observation;
- exact firm identity and spelling;
- attorney continuity;
- whether multiple entities moved together;
- whether the new firm handled the same corporate/property function.

A law-firm transition is an evidence-bounded interval unless a direct
engagement/termination record supplies a date. Code the edge by role:
securities/transactions, company litigation/tax, real estate/zoning, entity
formation/filing preparer, statutory agent, or in-house counsel. Do not code a
global firm-successor edge from a lawyer's later employer, one shipment, a
shared building, or the old firm's closure. Lead #84306 tracks the dated
entity-by-entity counsel and filing-channel reconstruction.

## Timeline analyses after image capture

Run separate layers for:

- formation/qualification;
- Snow appointment/change;
- officer/signatory observations;
- merger/dissolution effective dates;
- property execution and recording dates;
- preparer/law-firm observations;
- later corpus mentions.

Use:

- same business day for filing packets;
- rolling 7 days for law-office batches;
- calendar/rolling 30 days for reorganizations;
- 365/730 days after formation for lifecycle outcomes;
- plus/minus 30 and 90 days around formation/terminal events for property
  coupling;
- quarterly windows for provider transitions;
- multi-year chains for land assembly.

Report every rate with a numerator and denominator. The currently valid
statement is that 76 of 85 export entities with 1987-1988 agent-effective dates
share an exact date with at least one other entity. It is not yet valid to call
those 85 entities formations or short-lived shells.

After ingestion, compare network structure with and without Snow and other
professional-service nodes. A cluster that disappears when the professional
agent is removed is weaker evidence of common control than a cluster that
remains connected by officers, merger edges, parcels, lenders, or property
counterparties.

## Evidence states

- `primary_image_confirmed`
- `official_index_only`
- `official_index_conflict_unresolved`
- `direct_quote_primary_business_record`
- `secondary_aggregator_only`
- `user_provided_pending_primary_image`
- `bounded_not_found`
- `source_unavailable`
- `local_scope_not_covered`

No ownership or control conclusion may rest only on Snow, a shared date, a
return address, or a law firm.

## Implemented outputs

- `dorothy-snow-ohio-entities.csv` - 101-row normalized review seed table.
- `dorothy-snow-ohio-agent-date-clusters.csv` - 11 exact-date clusters with
  interpretive guardrails.
- `outputs/019fb3a7-511b-7b50-bf21-df954c6b7490/dorothy-snow-ohio-entity-review-updated.xlsx`
  - finalized source export, normalized entity review table, dashboard,
  coverage and merger sheets, cluster sheet, dedicated Argotron batch
  crosswalk, formulas, validation lists, and data dictionary.
- `outputs/019fb3a7-511b-7b50-bf21-df954c6b7490/ohio-epstein-property-corporate-reconstruction.xlsx`
  - consolidated primary-record property/corporate reconstruction with
  13 entity-family coverage rows, 116 normalized chronology rows,
  110 family-ledger rows, eight normalized merger transactions,
  49 constituent/survivor edges, the Morsham chain, and search-QA rules.
- `ohio-argotron-46-dissolution-crosswalk.csv` - 46 printed cover-letter
  names joined to 46 exact charters, with distinct formation,
  agent-appointment, terminal-document, and shared-cover provenance fields.
- `ohio-corporate-property-index.csv` - existing entity/vehicle index.
- `ohio-corporate-property-evidence.csv` - existing filing/deed/corpus
  evidence ledger.
- `ohio-sos-filing-manifest.csv` - filing-history rows and image availability;
  the manifest feeds the batch PDF downloader.
- `ohio-argotron-46-dissolution-crosswalk.csv` - canonical mapping of all 46
  corporations printed in Argotron packet `G532_0974` page 7 to exact Ohio
  charters and filing histories, with an explicit non-ownership guardrail.
- `ohio-epstein-officer-filing-coverage.csv` - fixed assertions for every
  in-cohort and external Epstein-officer company seed, including primary
  review state and bounded unresolved cases.
- `ohio-sos-merger-transactions.csv` - one row per legal transaction with
  distinct approval, execution, effective, recording, and receipt dates.
- `ohio-sos-merger-parties.csv` - one row per constituent, explicit party role,
  successor, packet-evidence state, and property-search rule.

The 101-row denominator remains intact. All 101 exact histories are enumerated
and all available pages are reviewed; no row remains `not_started` or has a
pending exact-history status. It records six confirmed direct Epstein-role
corporations, the complete 18-predecessor in-cohort Architonics review, the
Autumn Acres chain, Bearce Hollow, the full 46-company Argotron dissolution
batch, and the remaining date clusters. Off-export merger parties remain in
the broader merger index. The rolling officer/company coverage ledger contains
112 exact charters: 101 denominator entities and 11 external entities.

Current ledger sizes are 302 Ohio history rows, 125 property/entity index rows,
317 evidence rows, 8 normalized merger transactions, and 49 merger-party rows.
The reduction in transaction count reflects consolidation of eight
same-transaction MEX stubs into the single nine-party Eastern Ohio merger; it
is not lost evidence. The requested Franklin target families are reviewed at
the image level where pages are public, and the six image-unavailable records
remain explicitly coded as detail-only. Broader parcel-centered and
neighboring-county title work remains open.
