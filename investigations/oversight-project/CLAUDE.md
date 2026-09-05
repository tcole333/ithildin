# The Oversight Project / Mike Howell — Investigation Context

Case-specific instructions for agents working this profile. Loaded automatically
when working in or below `investigations/oversight-project/`.

## Scope & Working Hypotheses

The Oversight Project is a government-accountability / FOIA-litigation operation
led by **Mike Howell**. It launched (~2022) inside the **Heritage Foundation** and
was later stood up as an **independent Wyoming entity** with a DC/Virginia office
at **211 North Union St, Alexandria, VA 22314**. The Wyoming incorporation was
reportedly executed by attorney **William M. Klimon** (Caplin & Drysdale), whose
name also appears on filings for a cluster of nonprofits at **300 Independence
Ave SE, Washington DC 20003** — the **Conservative Partnership Institute (CPI)**
building — including the **American Accountability Foundation (AAF)** and,
potentially, the **CUFI Action Fund**.

Hypotheses to test (confirm/refute against primary records — do not assume):
1. **Corporate**: The Oversight Project spun out of Heritage into an independent
   WY nonprofit; the VA office is a foreign registration / branch of that entity.
   Find the WY SOS filing, the VA SCC registration, EIN, and 990s.
2. **Nexus**: Klimon (and/or Caplin & Drysdale) is the common incorporator /
   registered agent binding Oversight Project ↔ AAF ↔ CPI ↔ (?) CUFI Action Fund.
   His incorporation portfolio is a network multiplier — enumerate it.
3. **Address**: 300 Independence Ave SE is the shared-services hub. Enumerate
   every entity registered there and the shared officers among them.
4. **Money**: Map grant flows (990 Schedule I/R), donor-advised routing
   (DonorsTrust), and foundation funding (Bradley) into and out of the cluster.
5. **Infrastructure**: The org websites share hosting / certificate / analytics
   signals that reveal relationships the public sites don't advertise.

## Source Reliability (this case)

- **Primary (highest trust)**: Wyoming Secretary of State business filings;
  Virginia SCC (Clerk's Information System) registrations; IRS Form 990 / 990-EZ /
  990-N (ProPublica Nonprofit Explorer + `query_990.py` bulk DB); FEC filings;
  federal/state court dockets (CourtListener); lobbying (LDA) and FARA
  registrations; certificate transparency (crt.sh); passive infra (Shodan,
  URLScan, Wayback). Cite these directly.
- **Secondary (verify against primary)**: Investigative journalism on CPI / the
  MAGA nonprofit network (e.g., watchdog outlets). Useful for leads and named
  relationships, **not** as proof. Both the subject organizations' own materials
  and their partisan critics are interested parties — treat advocacy content from
  either direction as a claim to verify, never as corroboration.
- **Tertiary (starting point only)**: Wikipedia, social media, org "About" pages.

Label fact vs. inference. Claim-type discipline is mandatory: `direct_quote` →
can be `confirmed` (primary only); `paraphrase` → max `high`;
`inference`/`synthesis` → max `medium`.

## Cross-Profile Links (do NOT re-derive)

Entities are shared across investigations; findings are profile-scoped. Before
documenting a shared person/org, run `entity_tracker.py lookup` and
`findings_tracker.py search` and **cite** existing cross-profile findings rather
than re-creating them:

- **`hagee` profile** (John Hagee / Christians United for Israel) — directly
  relevant to the **CUFI Action Fund** thread. Check it before documenting Hagee,
  CUFI, or CUFI Action Fund.
- **`mike-johnson` profile** (Speaker Mike Johnson) — CPI-adjacent political
  figure; check before documenting overlapping political entities.

Re-documenting a shared entity creates duplicate findings (a known past failure
mode). Cite, don't duplicate.

## Known Identifiers (verify, expand)

- Oversight Project DC/VA office: **211 North Union St, Alexandria, VA 22314**
- CPI building / shared address: **300 Independence Ave SE, Washington, DC 20003**
- Incorporator/attorney: **William M. Klimon** (Caplin & Drysdale)
- Principal: **Mike Howell** (Exec. Director; former DHS official — role/dates to verify)
- Cluster orgs: Oversight Project, American Accountability Foundation, Conservative
  Partnership Institute, (potentially) CUFI Action Fund.

## Ethics

Open-source intelligence: public government records, court filings, corporate
registries, public 990s, certificate-transparency and passive-infrastructure
data, plus already-published leaked/hacked datasets (ICIJ, OCCRP, DDoSecrets,
etc.). Analyzing already-public material is in scope; acquiring non-public data
yourself is not — **do not** attempt intrusion, run active scans against target
hosts, or circumvent authentication. **Do not** contact investigation subjects.
These are public political organizations and public figures; document provenance
for every finding.
