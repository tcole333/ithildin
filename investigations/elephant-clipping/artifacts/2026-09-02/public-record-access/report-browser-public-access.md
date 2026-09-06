---
agent: public_records_access
target: Monster Lab normal logged-out application entry
skill: investigate-infra
profile: elephant-clipping
status: completed_bounded_pass_lead_unresolved
findings_added: 1
finding_ids: [15446]
connections_added: 0
entities_registered: 0
leads_spawned: 0
lead_id: 94310
---

# Browser public-access follow-up

## Outcome

**The normal dashboard entry renders a login page, not a public campaign listing. No actual campaign or payment data was recovered.** This resolves the earlier HTML-only loading-shell uncertainty for that entry path; it does not establish that every backend resource is protected or that no deliberately public share page exists.

In a new dedicated browser tab, the public `https://monsterlab.io/clipit` page exposed its ordinary Login link to `/dashboard`. Clicking it ended at `https://monsterlab.io/login`. After a single 30-second wait, the page fully rendered **Welcome Back**, empty email/password fields, LOGIN and sign-in/register controls. No authenticated account state appeared, no credentials were used and no form was submitted.

## Findings Added

**15446**, paraphrase / high, documents the normal entry-path login observation and its limits under lead 94310 / thread 206. Its quoted first-party text is “Login to your account and continue the motion.” Source URLs and minimized browser observations are in `browser-public-access-notes.md`.

The earlier findings 15444–15445 remain marketing-testimonial observations, not payment-ledger evidence. The first pass report and its notes were left unchanged.

## Passive Network Observation

The page's own network list contained **11 non-static requests**: Firebase web configuration and Installations startup, analytics/RUM, and Next.js login/forgot-password/signup page-data requests. The tool reported 68 successful static requests omitted. No Firestore, Storage or campaign-data endpoint appeared in this bounded non-static list.

An attempted inspection of the already-recorded login page-data response failed when the tool unexpectedly reported `about:blank` and said its request number no longer existed. Root had not operated the browser. **No body was recovered or replayed.** This is an unexplained tool/session limitation, not a target-site denial or evidence that the returned page-data body was empty. Configuration/installation/analytics bodies were not inspected.

## Negative Results and Limits

- No campaign listing, actual payment record, invoice, campaign row or account-to-campaign mapping was visible or retrieved through this normal entry flow.
- Firebase data permissions remain untested; public configuration and an Installations startup response do not establish Storage/Firestore exposure.
- No login, account, credential, private collection/bucket query, hidden endpoint, parameter tampering, guessed selector, access request, purchase, community join, contact, request replay or manual target write was used. Ordinary page startup itself emitted POST analytics/installation traffic; that was passively observed, not manually initiated as an investigative API query.
- No browser-infrastructure debugging or alternative unsafe automation was attempted. The supported browser initially worked; later context loss curtailed response-body inspection.

## Preservation and Lead Status

Lead **94310 remains in progress**, with a note recording the rendered result, network scope and missing body. This bounded follow-up is complete. No new lead, entity or relationship was created. One `browser_public` navigation check was logged.

Durable candidates: this report, `browser-public-access-notes.md`, and the public login accessibility snapshot if useful. The raw network log stays only in the temporary workdir because it can contain session/query material. No underlying record or sensitive account data was acquired. Parent owns evidence review, preservation and Learnings ingestion.

## Learnings

- [Methodology] A normal rendered navigation can resolve an HTML-only loading shell into an observed login surface without substituting guessed identifiers or querying hidden backend collections.
- [Source quality] Successful Firebase configuration and Installations startup requests are not campaign records or evidence of Storage/Firestore data exposure.
- [Friction] The browser tool rejected the assigned tmp output directory, so its documented relative-file behavior was used and generated artifacts were moved to the task workdir; papercut 2597 records the storage constraint.
- [Friction] The browser unexpectedly lost its context and the recorded request index before response-body inspection; papercut 2598 preserves the unresolved tool limitation without calling it a site denial.
