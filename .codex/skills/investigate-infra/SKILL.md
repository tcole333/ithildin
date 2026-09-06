---
name: investigate-infra
description: Investigate domains, IPs, DNS, certificates, hosting, and historical web records through passive public-source queries. Use for an evidenced digital-infrastructure question or to map a known organization's public infrastructure.
---

# $investigate-infra

Map public infrastructure observations and their history. Treat shared hosts,
certificate issuers, analytics IDs, CSP entries, and service names as signals to
test, with shared-provider and historical explanations considered before
attributing ownership, intent, or undisclosed capabilities.

## 1. Establish entry points and context

Accept a domain, IP, organization, or person name plus the factual question.
Read `docs/RESEARCH_WORKFLOW_CONTRACT.md` and `docs/EXECUTION_CONTRACT.md`.
Pin profile/database, inherit parent source ownership and report paths, and create
unique artifacts:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
uv run python tools/investigation_context.py show
uv run python tools/findings_tracker.py search "<TARGET>" --output "$WORKDIR/infra-findings.json"
uv run python tools/lead_tracker.py search "<TARGET>" --output "$WORKDIR/infra-leads.json"
```

| Entry point | Resolve first |
|---|---|
| Domain | Exact hostname/domain, current and historical DNS/certificate evidence |
| IP | Observation date, host/provider, possible shared hosting and historical use |
| Organization | Official domains and registrant/organization identity before broad pivots |
| Person | Existing evidenced public domains/institutional affiliations before infrastructure lookup |

Use passive public records and existing observations. Do not perform active scans,
exploit services, circumvent authentication, or contact subjects. Hypotheses may
guide collection; record the observed signal separately from its interpretation.

## 2. Select observations that can answer the question

Consult `docs/modules/osint-infra.md` for current commands, source health, and
access requirements. Read [references/passive-queries.md](references/passive-queries.md)
when choosing DNS/certificate, historical-web, host, or scan-record operations.
Assess applicability and reuse with the shared contract before repeating queries.

Typical evidence:

- Certificate transparency: SANs, exact certificate identity, issuer and dates;
  issuance and public launch are distinct events.
- DNS/host observations: record type/value, observation time, provider/ASN, and
  historical changes; hosting location is not necessarily operator location.
- Archived web pages: actual archived content and capture dates; first capture
  bounds observation rather than domain creation or first use.
- Existing URLScan records: HTTP transactions, contacted domains, technology
  detections, and screenshots at the scan time.
- Registration and first-party context: domain dates, registrant where public,
  company records, and relevant documented relationships.

Use unique `--output` paths, retain exact query/time, caps/pagination, and warnings.
Check paid query credits with `query_shodan.py info` when using Shodan and respect
the task's authorized budget. Do not hardcode a remembered account balance.

For HTTP headers, inspect existing scan-record transactions or a permitted
ordinary public response through a tool that exposes headers. Record the actual
header value, URL, and observation time. A rendered-page summary may omit headers;
do not invent them. A CSP allowlist is a configured allowance, not proof that a
vendor integration is used.

## 3. Pivot and reconstruct the timeline

Follow discriminating signals toward the original question: certificate SANs,
resolved IPs, registrant/organization identifiers, observed analytics IDs, specific
favicon hashes, and historically associated domains. Assess how common a signal
is before expanding it. Shared cloud IPs, common nameservers, and common
certificate authorities alone are weak attribution.

Use focused queries and preserve scope. If a provider-wide pivot is noisy or
unrelated, record that and choose a narrower selector; an exhaustive provider
inventory is not required for a single-organization question. Native chat
subagents may handle independent timelines/source families under the execution
contract while the parent resolves identity and reconciles observations.

Compare timestamps against known entity and event timelines:

```bash
uv run python tools/event_timeline.py list --output "$WORKDIR/event-timeline.json"
uv run python tools/entity_tracker.py lookup --name "<ENTITY>" --output "$WORKDIR/infra-entity.json"
```

Search only applicable configured corpora for discovered selectors. Validate
derived co-occurrence against the document. Retrieve complete artifacts and read
full source documents or sequential sections when needed; record read scope and
continuation for long material.

A zero supports “this query returned none” within its exact scope. Consider
coverage, observation time, caching, query limits, collection gaps, and ordinary
technical alternatives. Certificate/archive gaps are not automatically service
inactivity, and infrastructure changes do not by themselves establish intent.

## 4. Persist observations and assessed links

Record discrete primary observations separately when the exact row supports the
claim; cross-source conclusions are synthesis with at most medium confidence.
Findings need canonical refs/artifact locations, exact quotes per ref, source
tokens, and claim types under the shared evidence contract.

```bash
uv run python tools/findings_tracker.py add \
  --target "<TARGET>" --type intelligence \
  --summary "Combined DNS and certificate observations at the stated times" \
  --evidence "<DNS_REF>" "<CERT_REF>" --claim-type synthesis \
  --source-quote "<DNS_REF>:exact DNS observation" "<CERT_REF>:exact certificate observation" \
  --sources shodan crtsh --confidence medium
```

Connections need evidence that supports the asserted relationship:

```bash
uv run python tools/findings_tracker.py connect \
  --person-a "<ENTITY_A>" --person-b "<ENTITY_B>" \
  --type intelligence --strength medium \
  --description "Both domains appear on the observed certificate" \
  --evidence "<CERT_REF>" \
  --source-quote "<CERT_REF>:exact certificate row naming both domains" \
  --assessment "<CERT_REF>:Shared certificate observation; ownership remains unresolved"
```

Register identity-resolved entities and useful observed roles/addresses using the
entity tracker. Keep ambiguous attribution as an explicit question. Preserve
ambient dates, selectors, vendors, and relationships relevant to future pivots.

## 5. Finish and hand off

Perform a disconfirmation check on the leading attribution/explanation. Complete
once the requested infrastructure question is answered to its evidence standard
and applicable source coverage is accounted for, or an unresolved gap has a
specific next action. Queue independent deeper questions and missing capabilities
rather than silently broadening to every discovered host.

Return an evidence-linked map of domains, DNS observations, hosts, certificates,
configured/observed vendors, shared signals, and timeline. Include:

- Supported conclusions and alternatives/uncertainties.
- Finding/entity/connection IDs and artifact paths.
- Per-source query/time, caps/pages, outcomes, bounded negatives, and limitations.
- Credit usage when known, remaining source/read continuation, and follow-up leads.

Workers use the assigned report path or
`$WORKDIR/report-infra-<target-slug>.md`. Preserve reports/evidence according to
the Git workflow, and checkpoint progress across interruptions/compaction so the
original question and current attribution uncertainty survive.
