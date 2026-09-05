# Library Database Search Protocol — ProQuest / Nexis Uni / Factiva

**For:** human operator with Georgia Tech library access. Agents cannot and
must not access these authenticated resources.
**Capture rule:** for every relevant hit, save full text (PDF or text export
where licensing permits personal research use) with the citation intact
(publication, date, page, byline). Drop everything into
`investigations/epstein-oslo/incoming/library/` — flat files, any naming, I
will ingest and classify. If export is blocked, screenshots or copied text
with a hand-typed citation line are fine. Log dead-end queries too (a text
file listing query + database + 0-hits is a coverage record we need).

## Priority 1 — Owens delegation naming (the 1989 question)

The goal: any contemporaneous article that names WHO traveled with Owens.
Every regional/official source says "the delegation accompanying him" without
names; US and Israeli print is where names would appear.

| DB | Query | Date window | Why |
|----|-------|-------------|-----|
| ProQuest (Jerusalem Post if available; else all historical) | `Owens` | 1989-02-01 to 1989-04-15 | JPost coverage of the Herzog/Peres meetings; Israeli papers often listed accompanying businessmen. Also check 1988-12-15/31 and 1989-12-10/20 windows. |
| Nexis Uni | `"Wayne Owens" AND (delegation OR accompanied OR businessmen OR "development bank")` | 1988-11-01 to 1990-12-31 | Wire-service trip coverage; send-off/return items name companions in passing. |
| Nexis Uni | `"Roll Call" AND "Wayne Owens" AND travel` | 1991 | The Roll Call Report Syndicate travel study — its trip-level table resolves the last undated 1989-90 trip slot. |
| Nexis Uni | `"Wayne Owens" AND (Epstein OR Abraham OR Mitchell)` | 1987-1994 | Direct name-pair test. Any hit is gold; expect mostly null. |
| Factiva | `"Wayne Owens" and (Israel or Jordan or Saudi or Egypt or Tunis)` | 1988-1990 | WSJ/DJ newswire trip items. |
| ProQuest + Nexis | `"Middle East Development Bank" AND Owens` | 1989-1990 | Bank-proposal coverage may profile the idea circle (Abraham, Mitchell, Starr). |
| Any | `Owens AND Jeddah` / `Owens AND "Red Sea"` | 1989-03-15 to 1989-05-01 | The unnamed Saudi "one of the world's richest men" host. Also try `Fahd AND congressman AND (yacht OR palace)`. |

## Priority 2 — Center for Middle East Peace and Economic Cooperation

| DB | Query | Date window | Why |
|----|-------|-------------|-----|
| Nexis Uni | `"Center for Middle East Peace"` | 1989-1995 | Early profiles list founders, funders, board, and mission participants. |
| Nexis Uni | `"S. Daniel Abraham" OR "Danny Abraham"` AND (peace OR Israel OR Owens) | 1988-1995 | Abraham-mission coverage; his trips with Owens were occasionally profiled. |
| Factiva | `"Slim-Fast" and Abraham and (Israel or peace or Owens)` | 1988-1995 | Business-press angles on Abraham's diplomacy spending. |

## Priority 3 — David Jan Mitchell

| DB | Query | Date window | Why |
|----|-------|-------------|-----|
| Nexis Uni | `"David Jan Mitchell"` | 1985-1995 | Full-name items: Israel Bonds, Rodman & Renshaw, any peace-process role. |
| Factiva | `"Mitchell Holdings" or ("Rodman & Renshaw" and Mitchell)` | 1988-1993 | Firm-era coverage; deal items sometimes note affiliations. |
| Nexis Uni | `"Israel Bonds" AND Mitchell AND Manhattan` | 1987-1991 | His documented 1989 role; adjacent coverage may name his circle. |

## Priority 4 — Epstein pre-fame press archaeology (fills the WP7 gap)

| DB | Query | Date window | Why |
|----|-------|-------------|-----|
| Nexis Uni | `"Jeffrey Epstein" AND NOT (virus OR Brian OR Jason OR Joshua)` | 1980-1995 | The pre-fame baseline. Capture EVERYTHING plausibly him (financier/NYC context); I will classify collisions. |
| Factiva | `"Jeffrey Epstein"` | 1980-1995 | WSJ/newswire financial mentions: Bear Stearns exit (1981), J. Epstein & Co., Wexner association, Towers. |
| Nexis + Factiva | `"Towers Financial" AND Epstein`; also `Hoffenberg AND Epstein` | 1987-1995 | Contemporaneous (not retrospective) Towers-era naming — would harden or bound the exit-date question (#13878). |
| ProQuest | `Epstein AND Wexner` | 1986-1995 | The 1992 New Albany house purchase and any early association coverage. |
| Any | `"J. Epstein" AND (consultant OR financial)` | 1985-1995 | Variant-name sweep; low expected yield. |

## Priority 5 — Sept 13, 1993 signing guests + Oslo-window checks

| DB | Query | Date window | Why |
|----|-------|-------------|-----|
| ProQuest (WaPo, NYT historical) | signing-ceremony coverage incl. Style/society columns | 1993-09-13 to 1993-09-17 | Guest-list mentions in event/social coverage could resolve Epstein presence/absence at the signing (currently UNKNOWN, #13880). Check "Reliable Source"-type columns specifically. |
| Nexis Uni | `Epstein AND (Oslo OR "Rod-Larsen" OR Larsen OR FAFO)` | 1992-1996 | Direct anachronism test; expected null, cheap, completes the record. |
| Nexis Uni | `"Rod-Larsen" OR "Roed-Larsen"` | 1993-09-01 to 1994-06-30 | How the architects were covered at the moment of fame — context for the mythology H3 says Epstein later bought. |

## Handling notes

- Date-restrict first, then broaden. Nexis and Factiva both support
  date-range + source-type filters; wire services and regional papers are the
  high-yield source types for Priorities 1-3.
- Collisions: Epstein, Mitchell, Abraham, and Owens are all collision-heavy.
  Do not filter aggressively at search time — capture and let classification
  happen on ingest (I would rather discard 50 false positives than lose one
  true hit to a clever NOT clause). The one exception is the NOT clause on
  Priority 4's Nexis query, which removes known-noise first names only.
- When a hit names ANY Owens traveling companion — even a name we do not
  recognize — that is a Priority 1 capture: every named companion is a new
  interviewable/traceable node.
- Provenance: these are licensed copies for personal research; findings will
  cite publication/date/page (the underlying article), not the database.
