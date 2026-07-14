# B.I. Incorporated legal-lineage trace

Lead: #57846  
Profile: `geo-group`  
Scope: legal identity, registry history, holding-company lineage, GEO acquisition mechanics, current status, roles, and addresses. Contract economics and performance were excluded.

## Bottom line

The public record supports one Colorado legal corporation, **B.I. Incorporated**, formed on September 28, 1978. `BI Incorporated`, `B.I. Inc`, and Florida's `BI INCORPORATED OF COLORADO` are not separate operating companies in the reviewed evidence. They are punctuation/abbreviation and foreign-qualification forms of the same corporation. The resolution rests on exact identifiers, not on shared officers or addresses:

- Colorado entity ID `19871356363` is `B.I. INCORPORATED`, a domestic profit corporation in Good Standing, formed September 28, 1978.
- SEC co-registrant CIK `0001517758` is `B.I. Inc`, incorporated in Colorado, EIN `84-0769926`.
- Florida document `F95000000233` is `BI INCORPORATED OF COLORADO`, an active foreign-profit registration with FEI `84-0769926` and Colorado as its formation state.
- GEO's fiscal-2025 annual filing uses `B.I. Incorporated (CO)` in Exhibit 21 and `BI Incorporated` in Exhibit 22.
- The March 2026 SAM public extract uses `B.I. INCORPORATED`, UEI `PKK6L9KLMYR5`, CAGE `3CUH9`, a September 28, 1978 entity start date, and Colorado incorporation.

Finding #13056 records this as a synthesis at medium confidence. Alias rows #226 and #227 now route both unpunctuated and Florida-qualified forms to canonical entity #4810. Legacy entity rows #4861 and #5155 were deliberately preserved; no merge or deletion was performed.

## Formation and pre-GEO statutory history

Colorado's official entity dataset says B.I. Incorporated filed its Articles of Incorporation on September 28, 1978 under that exact name. The retrieved transaction history contains no explicit name-change entry. It does contain amendments and registered-office/agent changes, but most amendment descriptions are too sparse to infer their substance.

The Colorado history also records B.I. as the surviving entity in four merger events:

1. June 30, 1994: Guardian Technologies, Inc. and BI Monitoring Corporation were listed as non-survivors.
2. June 30, 1999: Peregrine Corrections, Inc. was listed as the non-survivor.
3. April 10, 2000: Community Corrections Corporation was listed as the non-survivor.
4. October 6, 2000: KBII Acquisition Company, Inc. was listed as the non-survivor.

Those entries establish statutory survival only. They do not, without the merger instruments, establish which business lines, contracts, liabilities, or assets continued. Findings #13051 and #13052 preserve the direct formation record and the bounded merger-history paraphrase.

## The 2008 holding structure

The clearest pre-acquisition ownership chain appears in BII Holding Corporation's financial statements filed with GEO's 2011 Form S-4/A. Note 1 states that BII Holding Corporation was incorporated in Delaware in August 2008 to acquire 100% of Behavioral Holding Corp.; the transaction took effect on August 15, 2008. It then states that B.I. Incorporated was a wholly owned subsidiary of Behavioral Holding Corp.

The evidenced historical chain is therefore:

`BII Holding Corporation -> Behavioral Holding Corp. -> B.I. Incorporated`

The database records this as relations #855 and #856, bounded to the 2010/2011 financial-statement period. Finding #13053 preserves the two quoted ownership statements.

The same S-4/A identifies a separate Delaware entity, BII Holding I Corporation, EIN `26-3334669`, alongside BII Holding Corporation, Behavioral Holding Corp., Behavioral Acquisition Corp., and B.I. Incorporated. The reviewed public filing does not place BII Holding I in the historical chain quoted above. Its exact intermediate position remains unresolved.

## GEO acquisition mechanics

On December 21, 2010, GEO signed an agreement under which its wholly owned Delaware merger subsidiary, GEO Acquisition IV, Inc., would merge into BII Holding Corporation. BII Holding—not the merger subsidiary—would survive and become a wholly owned GEO subsidiary. The announced consideration was $415 million in cash, subject to adjustments.

GEO's 2011 Form 10-K states that the transaction closed on February 10, 2011. It describes BII Holding as the Delaware owner of the Colorado BI corporation, says BII Holding survived the merger, and reports $409.6 million in cash consideration excluding acquired cash, transaction expenses, and potential adjustments. The difference between the announced $415 million and reported $409.6 million is therefore a planned-versus-closing measurement difference disclosed by GEO, not two acquisitions.

Existing verified finding #12783 already records the GEO/BII acquisition structure in the broader recipient-lineage analysis, so this pass did not create a duplicative acquisition finding. Relation #857 records BII Holding's GEO-subsidiary status with the 2010 merger agreement, 2011 closing disclosure, and 2025 guarantor exhibit as support.

## Current disclosed status

GEO's fiscal-2025 Exhibit 21 lists `B.I. Incorporated (CO)` among subsidiaries held directly or indirectly 100% as of December 31, 2025. Existing finding #12382 was rechecked against the source, its missing URL-row quote was restored, and the finding was verified.

Exhibit 22 to the same filing names `BI Incorporated`, `Behavioral Holding Corp.`, `BII Holding Corporation`, and `BII Holding I Corporation` as subsidiary guarantors. Finding #13054 and relations #858-#859 record only what that document establishes: each is a direct-or-indirect GEO subsidiary/guarantor. Exhibit 22 does not establish the exact current chain among them.

Colorado's live official dataset reports B.I. Incorporated in Good Standing. The last Colorado transaction-history rows retrieved were a September 29, 2025 file report and a December 22, 2025 registered-agent change. The March 2026 SAM public extract reports an active registration through November 13, 2026. Florida's official bulk snapshot reports the foreign registration active, but the live Sunbiz page was blocked by a Cloudflare managed challenge, so the Florida filing chronology and officer dates could not be refreshed in this pass.

## Roles and addresses

The June 2, 2011 S-4/A signature blocks show the same six signatories for BII Holding Corporation, BII Holding I Corporation, Behavioral Holding Corp., and B.I. Incorporated: Bruce Thacher; Brian R. Evans; William Bradley Cooper; John J. Bulfin; George C. Zoley; and Jorge A. Dominicis. These are filing-date observations, not appointment or termination dates, and were therefore not inserted into the entity-role table.

The Florida bulk snapshot lists George C. Zoley and Joe Negron with director title codes and four additional persons with truncated `VP,` title strings. Their effective dates are absent. The rows are retained in the officer matrix without expanding the incomplete title codes. Existing Zoley role #2597 remains attached to legacy Florida entity row #5155; it was not duplicated onto canonical #4810.

Address records are jurisdiction- and source-specific:

- Colorado and Florida registry records: 4955 Technology Way, Boca Raton, Florida 33431.
- March 2026 SAM registration: 6265 Gunbarrel Avenue, Suite B, Boulder, Colorado 80301.
- SEC co-registrant pages for the holding entities: 621 Northwest 53rd Street, Suite 700, Boca Raton, Florida 33487.
- Colorado registered agent: Corporate Creations Network Inc., 201 E 4th Street, Loveland, Colorado 80537.
- Florida registered agent snapshot: Corporate Creations Network Inc., 801 US Highway 1, North Palm Beach, Florida 33408.

The address differences are not evidence of separate BI corporations or of a particular ownership path. They are recorded as registry, SAM, SEC, and registered-agent addresses with their source capacities preserved.

## Database actions

- Backfilled canonical entity #4810 with Colorado jurisdiction, EIN `840769926`, formation date `1978-09-28`, and primary-source notes.
- Added aliases #226 (`BI Incorporated`) and #227 (`BI INCORPORATED OF COLORADO`) to canonical #4810.
- Created BII Holding Corporation #5159, BII Holding I Corporation #5160, and Behavioral Holding Corp. #5161 with SEC CIK/EIN provenance.
- Added entity relations #855-#859 and addresses #1072-#1075.
- Added and verified findings #13051-#13056; verified existing finding #12382; reused existing verified acquisition finding #12783.
- Preserved legacy duplicate rows #4861 and #5155; no merge/delete was attempted.
- Findings tracker automatically created three compound `auto:finding` target rows when findings #13053, #13054, and #13056 were added: #5162 (`BII Holding Corporation / Behavioral Holding Corp. / B.I. Incorporated`), #5163 (`B.I. Incorporated corporate lineage`), and #5164 (`B.I. Incorporated identity resolution`). These are analytical target nodes with entity type `unknown`, not canonical legal entities. They are excluded from the legal lineage and were not renamed, enriched, related, merged, or deleted during the audit repair. Papercut #1064 records this side effect.

Final artifact QA parsed all 20 JSON files, all three CSVs, and seven SEC HTML files; checked the principal Colorado, SAM, and SEC source assertions; and returned `ok` from SQLite `PRAGMA quick_check`. `PRAGMA foreign_key_check` returned the unchanged pre-existing repository baseline of 64 rows; no new task-scoped violation was introduced.

## Source limits

The exact position of BII Holding I is unresolved. Colorado amendment metadata does not reveal the substance of most amendments. Live Florida filing PDFs and precise current officer titles/dates were not recovered. No Delaware certificate or current status certificate was purchased or inferred from a private aggregator. No ownership conclusion rests on a common officer, address, SAM record, or foreign qualification alone.

See the accompanying timeline, registry/status matrix, officer-role/address matrix, negative log, manifest, and SHA-256 ledger for the audit trail.
