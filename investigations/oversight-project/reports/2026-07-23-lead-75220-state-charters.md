---
agent: pursue-lead
target: "AX Capital / HenryAlan LLC / CC: External Affairs, Inc."
skill: pursue-lead
status: blocked
findings_added: 1
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 75220
---

# Lead #75220 Report: Ohio and Virginia state charters

## Key Discoveries

- Virginia SCC's no-login **Download Reports** service resolved the relevant
  legal record as **CC: EXTERNAL AFFAIRS, INC.**, entity **07616725**.
- The official current index labels it an **active stock corporation**, lists
  **433 N Fayette St, Alexandria, VA 22314-0000** as the principal office, and
  names **Charles Cirame** as the registered agent.
- A case-insensitive parse of the complete SCC Stock Corporation CSV returned
  exactly one row containing `EXTERNAL AFFAIRS`. The `CC:` prefix is part of
  the legal name and was not silently removed.
- The registered-agent field does not establish an officer, owner, or
  beneficial owner. The public CSV does not include formation date or
  officers/governors.
- Ohio's exact-name records for AX CAPITAL, AX CAPITAL LLC, HENRYALAN, and
  HENRYALAN LLC remain unresolved. The Ohio portal is Turnstile-gated, and the
  repository helper requires exporting a `cf_clearance` challenge cookie and
  browser impersonation; that route was not used.

## Findings Added

- **#14370** — direct official Virginia SCC identity/current-index record;
  claim type `direct_quote`, confidence `confirmed`, global thread 183. Its
  scoped evidence audit reported zero issues, and the finding was marked
  verified.

## Connections Added

None. The SCC record does not by itself establish ownership or a relationship
to any officer, client, or political committee.

## Entities Registered

None.

## Negative Results

- One ordinary Virginia no-login exact-name search was rejected with
  `Please try again. You may be a bot!`; no reCAPTCHA interaction or workaround
  followed.
- Opening the individual Virginia record from the public report context
  returned an empty HTTP 200 response in this session, leaving formation date,
  jurisdiction detail, officer/governor fields, registered-agent history, and
  filing history unresolved.
- No permitted Ohio bulk/indexed source exposed the three requested names.
- Same-name `AX CAPITAL` records outside Ohio were not treated as the target.

## Sources Checked

| Source | Access | Result | Findings Created |
|---|---|---|---|
| Virginia SCC CIS Download Reports | Official, no-login CSV export | Entity 07616725; exact legal name, entity type, status, principal office, RA | #14370 |
| Virginia SCC ordinary business search | Official no-login interface | Exact-name query rejected by bot detection; stopped | None |
| Ohio Secretary of State Business Search | Official Turnstile-gated interface | No challenge-compliant entity result available in this session | None |
| `tools/ingest_ohio.py` | Local integration inspected only | Requires copied `cf_clearance` and browser impersonation; intentionally not used | None |
| Existing first-party/FEC record set | Previously stored context | Dublin-address and Thomas Datwyler/Rob Phillips discriminators preserved for manual matching | None |

Durable evidence note:
`investigations/oversight-project/evidence/lead-75220-ohio-virginia-state-charters.md`

## Gaps / Follow-up Needed

Human action **#101** preserves the precise challenge-compliant remainder:

1. search Ohio for `AX CAPITAL`, `AX CAPITAL LLC`, `HENRYALAN`, and
   `HENRYALAN LLC`;
2. separate every same-name record by charter number, date, address, agent,
   officer/organizer, and status;
3. link the target only when a known Dublin address, Thomas Datwyler, Rob
   Phillips, or another existing discriminator matches;
4. open Virginia entity 07616725 and capture formation date, jurisdiction,
   officers/governors where public, registered-agent history, and
   filing-history/image metadata;
5. do not bypass Turnstile/reCAPTCHA, export challenge cookies, create an
   account, or purchase records without separate approval.

Lead #75220 is blocked only on those fields.

## Leads Spawned

None.

## Learnings

- [Methodology] A registry's legal-name punctuation and prefix are evidence;
  normalize only for searching, not when reporting the legal record.
- [Source quality] Virginia SCC's Download Reports export is a useful official
  fallback for current identity, status, principal-office, and registered-agent
  fields when the ordinary name search rejects automation.
- [Tooling] The Ohio helper's copied challenge-cookie/browser-impersonation
  design is outside this lead's permitted access boundary and should not be
  used to convert a Turnstile stop into an automated result.
