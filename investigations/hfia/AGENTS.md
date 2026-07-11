# HFIA Investigation Addendum

## Scope

This profile is not a general foreign-issuer investigation. It is a structured
screening and escalation workflow built around the new Section 16 visibility
created by the Holding Foreign Insiders Accountable Act.

## First-Pass Screening Rules

- Start from Forms `3`, `4`, and `5` filed on or after `2026-03-18`.
- Treat the first wave of Form `3` filings as a universe-building event, not as
  a story by itself.
- Prioritize issuers with:
  - post-`2026-03-18` Form `4` activity, especially near financing or resale windows
  - recent `F-1`, `F-3`, `424B3`, or other selling-shareholder activity
  - small- or mid-cap profiles in hype sectors
  - offshore incorporation and low-transparency service-provider structures
  - repeated insider filings clustered among newly visible executives and directors

## Mandatory SEC EDGAR Bundle

For HFIA issuer work, `query_edgar.py` is mandatory. Do not treat an issuer scan
as complete without checking the following bundle:

```bash
uv run python tools/query_edgar.py company <CIK> --output $WORKDIR/edgar-company.json
uv run python tools/query_edgar.py insider <CIK> --start 2026-03-18 --output $WORKDIR/edgar-insider.json
uv run python tools/query_edgar.py filings <CIK> --form "F-1,F-3,F-4,424B3,424B5,6-K,20-F,40-F" --start 2025-01-01 --output $WORKDIR/edgar-fpi-bundle.json
uv run python tools/query_edgar.py search "<ISSUER_NAME>" --forms "F-1,F-3,F-4,424B3,424B5,6-K,20-F,40-F,3,4,5" --start 2025-01-01 --size 20 --output $WORKDIR/edgar-search.json
```

Prioritize:
- `Form 4` activity after `2026-03-18`
- any `F-1`, `F-3`, `F-4`, `424B3`, `424B5`, `EFFECT`, or `POS AM` activity in 2025-2026
- `6-K`, `20-F`, and `40-F` disclosures that help establish status, financing context, or governance changes

## Deprioritize Early

- Large blue-chip foreign issuers where the first-wave filings are likely a pure
  compliance backlog with little immediate accountability value.
- Issuers with strong governance, heavy analyst coverage, and no obvious
  financing, dilution, or opacity angle.

## Working Heuristic

For quick landscape work, it is acceptable to classify an issuer as a likely
foreign private issuer if its recent SEC filing history includes `6-K`, `20-F`,
 or `40-F`. This is a screening heuristic, not a legal conclusion. If a target
 moves into deeper investigation or publication, confirm status directly from
 issuer filings and exchange disclosures.

## What Makes a Good Story Here

- New insider visibility contradicts an issuer's public promotional narrative.
- A newly visible insider block sits next to dilution, resale registration, or
  financing activity.
- Offshore structure or nominee layers make it unusually hard to tell who
  actually benefits.
- Insider activity helps explain broader governance, disclosure, or related-party risk.

