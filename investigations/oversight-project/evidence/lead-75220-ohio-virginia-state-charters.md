# Lead 75220 — Ohio/Virginia state-charter evidence

Date checked: 2026-07-23  
Profile: `oversight-project`  
Thread: 183  

## Virginia SCC public report export

Source: Virginia State Corporation Commission, Clerk's Information System,
public **Download Reports** service:
`https://cis.scc.virginia.gov/EntitySearch/DownloadReports`

The no-login report was run for `Entity Type = Stock Corporation`, with all
statuses and jurisdictions included. The SCC page reported 352,206 results and
offered a CSV export. The downloaded file was saved locally as
`.playwright-cli/Search-Results.csv`; SHA-256:
`c81d9620ec6dc3ab884fee284e5d60388808441b8cf16e2ca61efcf692bdd7c7`.

Parsing the CSV with its header and searching case-insensitively for
`EXTERNAL AFFAIRS` returned exactly one row:

```csv
Entity ID,Entity Name,Name Type,Entity Type,Principal Office Address,RA Name,Status
07616725,"CC: EXTERNAL AFFAIRS, INC.",Legal Name,Stock Corporation,"433 N FAYETTE ST, ALEXANDRIA, VA, 22314 - 0000, USA",CHARLES CIRAME,Active
```

This resolves the current public index fields but not the formation date,
officer/governor list, or historical registered-agent and filing images. The
ordinary no-login entity-name search rejected one exact query with the site's
message, `Please try again. You may be a bot!`; no reCAPTCHA interaction or
workaround was attempted. Direct navigation from the report result to the
individual record returned an empty HTTP 200 response in this session.

## Ohio access boundary

Targets requiring a permitted human search:

- `AX CAPITAL`
- `AX CAPITAL LLC`
- `HENRYALAN LLC`

The Ohio Secretary of State Business Search is protected by Cloudflare
Turnstile. The repository's `tools/ingest_ohio.py` requires exporting a
`cf_clearance` cookie and browser impersonation, so it was not used. No
Turnstile interaction, copied challenge cookie, or challenge-bypass request was
made.

Known target discriminators to apply during the manual searches:

- HenryAlan/AX Capital campaign records use Dublin, Ohio, including 75 S. High
  Street, Suite 4, Dublin, OH 43017 and P.O. Box 3653, Dublin, OH 43016.
- The first-party AX Capital site identifies the business as the combination of
  9Seven Consulting and HenryAlan and names Thomas Datwyler and Rob Phillips.
- Same-name entities must remain separate unless the official Ohio record
  matches a known address or person.

## Certainty boundary

The SCC row is a direct official record of the legal name, entity ID, entity
type, current status, principal office, and registered-agent name. It does not
establish ownership, beneficial ownership, or an officer role for the
registered agent. No Ohio charter fact is treated as resolved.
