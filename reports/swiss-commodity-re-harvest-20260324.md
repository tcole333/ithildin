# Swiss Commodity Re / CRML Harvest

Date: 2026-03-24

Source run:
- Stalled Claude `deep-investigate` run on Swiss Commodity Re Limited
- Harvested completed sub-agent reports from `/private/tmp/osint-VprDOrLV/`
- Completed standalone Claude `trace-entity` run on Swiss Commodity Re Limited

## Completed Sub-Agents

- Agent A: SEC / EDGAR
- Agent C: legal / court / regulatory
- Agent D: network / OSINT / open web / resale window

Missing:
- Agent B report was never produced. Partial `b-*.json` artifacts exist in the temp workdir, but the report file is absent.

## Key Harvested Findings

### Transaction mechanics
- The announced `2,000,000` ASA shares were actually split:
  - `1,800,000` to Swiss Commodity Re Limited
  - `200,000` to Malcolm Scott Macintyre
- The split was visible in the F-3 / 424B3 resale registration, not in the original 6-K press release.
- Copper was booked at `USD 15.8M`, not `USD 20M`, based on share FMV at close rather than the announced deal price.

### Accounting / controls
- CRML disclosed a **material weakness** tied specifically to valuation and accounting for the copper powder.
- The copper was carried as a **non-current** inventory asset, undercutting the idea of near-term commercial monetization.
- Swiss Commodity Re, Deayton, and Macintyre were absent from the related-party note in the Dec. 31, 2025 half-year financials.

### Seller structure
- Swiss Commodity Re appears to be a Hong Kong shell, not a Swiss family office.
- Kenneth Raymond Deayton is disclosed as the person who "may be deemed" to have voting and investment control over the Swiss Commodity Re shares.
- The entity uses the Wyndham Place address associated with Hong Kong Corporate Services Group.
- The separate trace run further identified Swiss Commodity Re as Hong Kong company `79047415`, allegedly incorporated on `2025-10-30`, 22 days before the deal announcement.

### Fraud-pattern alignment
- The CRML press release used the same `USD 1,500–2,500 per gram` copper pricing language described in Financely Group's pre-existing copper-powder fraud warnings.
- No independent valuation, assay-backed pricing support, storage disclosure, or custody trail was identified in the reviewed SEC materials.

### Legal / enforcement posture
- No public SEC comment letters were found after the copper deal.
- No US federal litigation, FARA registrations, or lobbying filings were found for Swiss Commodity Re or Deayton.
- Prior intelligence tying a `USD 9.36M` confiscation order to Tony Sage was flagged as incorrect by Agent C; that order related to Oz Minerals / Oxiana Cambodia, not Sage.

### Share monetization
- No Form 144 filings were found for Swiss Commodity Re or Macintyre.
- That does not prove no sale occurred, because the shares were registered for resale under an effective F-3.
- Agent D noted an 18.3% CRML decline during the March 4-23, 2026 resale window, which is consistent with selling pressure but not proof of Swiss / Macintyre sales.

## Best Open Questions

- What exactly was Malcolm Scott Macintyre's role in the ASA?
- Is Deayton acting only as a nominee, and if so, who is the beneficial owner behind Swiss Commodity Re?
- Where was the copper physically stored, and who verified its existence, purity, and custody?
- Did Swiss Commodity Re or Macintyre monetize the shares after F-3 effectiveness?
- Are there overlaps between Deayton's other entities and any CRML / European Lithium / Perth mining intermediaries?

## Leads Spawned / Reinforced

- `#32278` Trace Sprocket HK Limited
- `#32280` Identify Malcolm Macintyre's role in the CRML copper powder ASA
- `#32283` Trace Grande Holdings / Nimble Holdings
- `#32315` Macintyre / Swiss Commodity Re connection via ASIC and broker-disclosure checks
- `#32317` Swiss Commodity Re Hong Kong registry verification
- `#32319` Copper powder custody / storage verification

## Operational Note

The stalled `deep-investigate` run appears to have hung after Agents A, C, and D completed. The latest artifact in the temp workdir was `report-agent-d.md` at `2026-03-24 10:45:47 EDT`. No `report-agent-b.md` was produced.
