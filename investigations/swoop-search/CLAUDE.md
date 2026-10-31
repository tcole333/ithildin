# Swoop Search / Swoop Technologies investigation

Profile `swoop-search`. Question: who is the company behind SwoopOS, and how did it
join the original Golden Dome command-and-control (C2) software group?

## Identity anchors (verify before connecting any record)

- **SAM.gov:** SWOOP TECHNOLOGIES, LLC — UEI `WVT6SJYYJFC5`, CAGE `76XE1`,
  Delaware LLC, entity start 2012-10-10, first SAM registration 2014-07-20,
  NAICS 513210, physical/mailing address 2877 Itasca Ave S, Lakeland, MN 55043,
  government and electronic POC Paul Bottum (local `datasets/sam.db` extract).
- **Aggregator profiles (tertiary):** Crunchbase "Swoop Search" (Madison, WI,
  founded 2011, lists SwoopOS) and Bloomberg "Swoop Search, LLC" (2310209D:US).
  The relationship between Swoop Search, LLC and Swoop Technologies, LLC is an
  open question, not an established fact.
- **First-party:** swooptech.com; job postings on Ashby (`jobs.ashbyhq.com/Swoop`)
  describe SwoopOS, the Valhalla SDK and the Surf browser and recruit cleared
  engineers in Minneapolis.

"Swoop" is a common name. Do not attach records by name alone. Known
non-matches: Swoop (Canadian airline), SwoopThat, LLC (San Diego), Swoop Funding
LLC, U Swoop LLC (Griffin, GA, UEI F1DQAT3NJS66), Swoop Inc (DE, UEI
N9JFUJ3N4V95), Swoop Analytics Pty Ltd (Australia), Swoop Aero (Australian
drones). Resolve by UEI, CAGE, registry number, officer, or address.

## Source reliability

- The Golden Dome C2 roster comes from Reuters (2026-03-24), which cites a
  single unnamed source; later outlets repeat it. Treat roster membership as
  reported, not confirmed, until a primary record (award, agreement, official
  statement, company statement) corroborates it. Syndicated copies of the
  Reuters item are one source, not several.
- Crunchbase, ZoomInfo, Bloomberg company profiles, PitchBook snippets and
  LinkedIn are tertiary: use them to find leads, then confirm against
  registries, SAM, EDGAR or first-party statements.
- Company job postings and website copy are first-party statements of what
  Swoop says about itself; they are not proof of capability or of a contract.

## Procurement routing notes

- As of 2026-10-31, USASpending recipient autocomplete returns no recipient for
  "swoop search", "swoop tech" or "swoopos". That bounded zero covers
  autocomplete only, not UEI-keyed award or subaward queries.
- Other transaction (OTA) awards made through a consortium manager (for
  example ATI for the C5 consortium, NSTXL for SpEC and S2MARTS) are reported
  under the manager's name, not the performing company. A missing prime award is
  therefore not evidence that no award exists.
- Golden Dome space-based interceptor work used classified OTAs (tech-right
  #4720), so some C2 work may never appear in public award data. Record that as
  a collection gap, not a negative.

## Cross-profile context

Golden Dome program facts are in `tech-right` thread 13 (global thread id 13).
Cite them instead of re-documenting: #4726 and #6132 (Guetlein reports only to
DepSecDef Feinberg), #4718 (SHIELD IDIQ), #4720 (classified SBI OTAs), #4731 and
#5097 (Palantir positioned for C2), #5102 (C2 demo planned for summer 2026),
#6136 and #6139 (architecture, BMC3 ground segment).

## Working rules

- Pin `ITHILDIN_PROFILE=swoop-search` and `ITHILDIN_DB_PATH` to the main
  checkout database; never run `investigation_context.py set`.
- Do not contact Swoop, its employees, or its investors.
