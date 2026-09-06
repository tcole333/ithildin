# Card-validation memo — card 4 `enforcement-gap-ratio (captured self-regulator)`

**Card under test:** `research/patterns/detection-signatures.md`, card 4 (Tier 1; cross-outlet family F10,
graduated to a four-outlet universal on 2026-07-29).
**Regulator / population pair:** U.S. Securities and Exchange Commission (SEC) / persons and entities within
nationwide U.S. federal securities-law jurisdiction whose Exchange Act §10(b) / Rule 10b-5 misconduct reached a
final merits adjudication in a non-SEC-initiated federal court matter, 2021-01-01..2025-12-31.
**Why this pair:** it is the fairest available test, not the easiest. The platform holds a nationwide structured
SEC action index and CourtListener offers a facially independent nationwide judicial channel. Comparing SEC
press releases to SEC action releases, or DOJ releases to SEC actions, would be easier but would compare one
enforcement-output series with another and assume away the card's central independence requirement. FINRA would
fit the card's “self-regulator” subtitle more literally, but the platform does not hold a complete FINRA
discipline output series or an independently enumerated broker violation census.
**Test bed:** `datasets/sec_enforcement.db` (37,592 action rows, 77,515 parsed defendants,
1965-03-30..2026-03-19; selected window = **5,464** action rows: 368 AAER, 3,649 administrative, 1,447
litigation); `datasets/government_releases.db` (282,951 agency-release rows overall, including 6,801 complete
SEC press releases; selected window = **1,122 complete SEC press releases**); five pre-registered CourtListener
opinion searches (92 result rows, 74 clusters, 66 dockets, of which 48 were federal); and read-only
`investigation.db` (14,502 findings, only 10 containing `10b-5` or `Section 10(b)`).
**Window:** 2021-01-01..2025-12-31 inclusive, with SEC follow-up visibility only through 2026-03-19.
**Posture:** read-only, zero database writes, no tracker calls, no profile switch, no search-log writes. All
scratch in `/tmp/osint-nMqnygO0/`; the CourtListener wrapper's normal `log_search` path was disabled because it
would otherwise write to `investigation.db`, and the post-run audit found no matching rows in either
`search_log` or `search_history`.

---

## 1. EXECUTABILITY, field by field

### Mechanics — **un-executable as written; the advertised ratio has no fixed unit and the independent half is not a base rate**

The card says: *“Construct the violation base rate independently … obtain the regulator's own output series …
and publish the ratio.”* That is an intelligible investigative question, but not an executable statistic.

First, a **rate divided by a series is dimensionally undefined** unless both are reduced to compatible units.
The card's examples mix at least five:

- journalist-found violations, complaints, deficiencies, and deadlocked votes on the “violation” side;
- referrals, investigations, sanctions, and penalty dollars on the output side.

A deficiency count divided by penalty dollars is not the same measure as unique adjudicated violators divided
by unique sanction matters. A regulator can also issue a litigation release, an administrative order, an AAER,
and a press release for one underlying matter. The card supplies no event unit, no matter-deduplication rule, no
conduct taxonomy, no regulated-population denominator, and no entity/matter join. An agent following the text
can choose the unit after seeing the result.

Second, the card alternates between an **aggregate ratio** and a **case-linked sanction-outcome diff**. Its
variant says: *“join adjudicated wrongdoing in ledger A to the discipline/license registry in ledger B.”* That
is the stronger design. It asks what fraction of independently adjudicated events received a qualifying
regulator response within a fixed lag. The aggregate ratio does not: 20 unrelated SEC matters and 10 unrelated
court matters could yield “2:1” even if none of the ten adjudicated matters ever reached the SEC.

Third, “base rate” requires an at-risk population or a complete eligible event census. The pre-registered
CourtListener retrieval produced a **located-proxy count**, not a base rate: the tool can enumerate hits for
fixed phrases, but it cannot state how many eligible federal §10(b)/Rule 10b-5 dispositions lacked those phrases
or were never published as searchable opinions.

The strict run therefore did not produce a ratio. It produced:

```
admissible independent final-merits §10(b)/Rule 10b-5 matters located = 0
comparable, category-classified SEC output matters from the action corpus = unavailable
enforcement-gap ratio = undefined
```

The zero is a valid retrieval result. It is not evidence that no violations occurred.

### Minimum data — **partially sufficient; it names both halves but omits the properties that make either half usable**

The card requires: *“the regulator's output series (annual reports, FOIA) + an independently constructible
violation proxy for the same period.”* Both nouns are right. Four binding properties are missing.

1. **The violation side must be enumerable, not merely searchable.** CourtListener is a search index of opinions
   and RECAP materials, not a census of every filed private securities matter or every final disposition. The
   five fixed searches returned all of their reported upstream hits, but recall against all eligible
   adjudications is unknowable from held data.
2. **The proxy must be independent by construction.** DOJ charging releases, SEC releases, and criminal
   opinions in `United States v.` matters are government-enforcement outputs. They may be independent of the
   SEC's publication system, but they are not an independently observed violation base and are exactly the
   jurisdiction-split alternative the card warns about.
3. **The output side needs full text, outcome tags, and a matter key.** In the selected window all **5,464 of
   5,464** `sec_enforcement.db` rows have empty `body_text`. The entire database is the same: **37,592 of
   37,592** empty. Within the window, 1,824 action rows (33.4%) also have no `file_number`; 3,640 rows have a
   file number but only 2,300 distinct nonblank values. The corpus can count releases, but it cannot classify
   §10(b)/Rule 10b-5 conduct or reliably collapse all releases to underlying matters.
4. **The two sides need a hard join and event dates.** CourtListener supplies docket/cluster IDs and party
   strings; the SEC action index supplies release/file numbers and parsed respondent strings. There is no shared
   case or entity identifier, and opinion filing date is not misconduct date, complaint date, intake date, or
   regulator-eligibility date.

The 10 matching `investigation.db` findings do not repair the gap. They are investigation-selected assertions
spread across six profiles, not an enumerated population. They include dismissed claims, allegations,
inferences, and one claim that survived dismissal and later settled; none forms an independently sampled base.

### Pre-registration — **un-executable as written; field absent**

Card 4 carries no Pre-registration field even though every one of these choices moves the number: regulator,
regulated population, conduct class, jurisdiction, event unit, date field, observation window, independence
exclusions, regulator output types, matter deduplication, entity resolution, evidentiary threshold, and lag.

I fixed those choices in `/tmp/osint-nMqnygO0/preregistration.md` before the result queries. The decisive
choices were: nationwide federal §10(b)/Rule 10b-5; 2021–2025; unique CourtListener docket/cluster; final merits
only; exclude SEC- and United States-initiated matters from the strict numerator; unique SEC `file_number`
(fallback release key); and a two-year follow-up sensitivity. See §2 for the complete table.

This absence is also a **card-layer finding**. The header says statistic-producing cards carry discipline fields
and then names cards *“3, 5, 14, 21, 29”* as the unvalidated to-do list. It does not name card 4. Card 4 produces
a computed ratio and carries none of Pre-registration / Coverage / Control / Preconditions. Its omission from
that list silently treats it as exempt when the live run shows it is at least as parameter-sensitive as the
listed cards.

### Coverage statement — **un-executable as written; field absent and the ceiling cannot be estimated**

The numerator search was exhaustive only **within the five literal query definitions**:

| final-merits phrase | upstream results returned |
|---|---:|
| `jury found` | 8 / 8 |
| `final judgment` | 34 / 34 |
| `convicted` | 41 / 41 |
| `pleaded guilty` | 8 / 8 |
| `found liable` | 1 / 1 |
| **Raw total** | **92** |

After cross-query deduplication those were 66 dockets, 48 in U.S. federal courts. That is complete pagination,
not corpus recall. “Final judgment” often meant final procedural judgment after dismissal; “found liable” in
the only hit described unrelated termite arbitrations inside a securities complaint that was itself dismissed.
No held list permits an estimate of the false-negative population.

The output-side coverage is quantifiable in one narrow and devastating sense: **0 of 5,464 selected SEC action
rows contain body text**, so exact statutory-conduct classifiability from the named action corpus is 0%. The
separate government-release corpus has complete text for 1,122 selected SEC press releases, but press-release
selection is not the universe of SEC enforcement actions. It returned 33 action announcements with the
pre-registered law phrases after one rulemaking release was excluded; the percentage of all §10(b)/Rule 10b-5
actions represented by those 33 is unknown.

Accordingly the coverage ceiling for the promised ratio is **unquantifiable**, not 0%. The platform located zero
admissible numerator events; it did not establish zero eligible events.

### Control — **un-executable as written; field absent and no valid null is held**

The card provides no null population and no lift definition. I pre-registered SEC/United States-captioned
CourtListener matters as an **independence negative control**: if the search preferentially retrieves those,
the purported independent proxy is contaminated by enforcement output. It did:

| federal phrase-hit dockets | count |
|---|---:|
| SEC matter or review of SEC action | 14 |
| United States criminal matter | 6 |
| private/other caption | 28 |
| **Total** | **48** |

That control diagnoses circularity; it is not a no-capture baseline. A valid lift calculation would require a
comparable regulator/conduct cell with the same independent ascertainment, event threshold, jurisdiction,
severity mix, and follow-up window. The platform does not hold that cell. It therefore cannot report the
discipline header's required “screen lift over control.”

### Preconditions — **un-executable as written; field absent and three blockers are active**

The move currently requires:

- a CourtListener credential and live API; current v4 field semantics must use `__istartswith` where a party
  prefix is required, not the obsolete `contains` / `icontains` filters that now return 400;
- a non-writing query mode. Both `query_courtlistener.py` and `query_sec_enforcement.py` normally call
  `lead_tracker.log_search`, so a read-only validation must disable that path or use direct read-only SQL;
- a populated full-text/outcome layer for `sec_enforcement.db`, plus stable matter and respondent identifiers;
- an official, versioned statute/rule source for the powers-on-paper check;
- a completed lag window and a disclosed right-censor rule.

The second and third are not cautions; the third is a present **BLOCKED** condition for conduct-matched SEC
output, and the second conflicts with a read-only audit unless explicitly handled.

### Ithildin mapping — **un-executable as written; all named sources exist, but none supplies the promised paired statistic**

The card maps to: *“query_sec_enforcement + government_release_corpus (federal output series),
query_courtlistener (adjudicated-misconduct corpus), source_reliability discipline for self-reported stats;
hypothesis_tracker for the capture hypothesis.”*

What actually ran:

- `query_sec_enforcement.py stats --by-year` correctly reported 37,592 action rows and the selected five-year
  total. Its two pre-registered searches (`10b-5`, `Section 10(b)`) returned **zero**. The null was caused by
  corpus construction, not absence of enforcement: `body_text` is empty in every row, so FTS is effectively a
  respondent-title search. Calling this a conduct-searchable enforcement corpus is an overstatement.
- `government_release_corpus.py` supplied full official SEC press-release text. It found 34 exact-law phrase
  releases in the window; one was a rule amendment, leaving 33 enforcement announcements. These primary agency
  statements prove what the SEC announced, charged, alleged, settled, admitted, or obtained—not that charged
  conduct occurred. They are also a selective communications series, not the complete action series.
- `query_courtlistener.py` returned the full reported result sets for the fixed queries and full opinion text
  for all 28 non-government-caption federal dockets. CourtListener is an adjudicated-document corpus, not a
  preclassified “adjudicated-misconduct corpus”: half of those 28 were not §10(b)/Rule 10b-5 merits matters, and
  none of the 14 relevant private securities matters ended in a final merits finding of a violation.
- `source_reliability` is evidence discipline, not an adapter. It correctly tells the analyst not to treat SEC
  allegations as proven violations, but does not construct either series.
- `hypothesis_tracker` records an interpretation after the statistic exists. It cannot create a missing
  independent base or control, and invoking it would have violated this run's zero-write posture.

The mapping therefore names discovery surfaces, not an end-to-end implementation.

### Failure modes — **partially sufficient; all three stated modes fired, but the fatal circularity mode is absent**

The card names three modes and an authority check.

1. **“Enforcement lag misread as absence” — binding and not adjustable here.** An opinion's filing date is
   already downstream of the underlying conduct and often years after it. The SEC corpus ends 2026-03-19, so
   2025 events have at most 78 days of post-window visibility at year end; no 2025 event has the pre-registered
   two-year follow-up. With zero admissible events there was no event-level lag curve to compute. A same-year
   aggregate ratio would systematically mis-time both streams.
2. **“Jurisdiction splits (cases handled elsewhere)” — observed directly.** Twenty of 48 federal phrase-hit
   dockets were government matters: 14 SEC matters/reviews and six United States criminal matters. Counting
   the six criminal cases as independent violations would make DOJ prosecution look like SEC non-use when it
   may instead represent parallel or allocated jurisdiction. Several private-caption opinions also matched
   because they recited a prior guilty plea, conviction, or SEC settlement rather than adjudicating the private
   §10(b) claim.
3. **“Intake composition shifts” — visible but not diagnosable.** SEC action rows changed from 762 admin / 78
   AAER / 292 litigation in 2021 to 365 / 24 / 249 in 2025. Complete SEC press-release volume changed from 270
   to 146, while exact-law enforcement announcements fell from 15 to one. Those could reflect enforcement,
   intake, charging mix, publication policy, leadership, or ingestion differences. The platform holds no
   annual complaint/referral/intake census with which to separate them. One press-release record also carries
   an internally conflicting time key: `SEC-PR:2022-123` has `published_at=2023-06-29` and a 2022 release
   number, making “same period” classification itself require reconciliation.
4. **“Confirm the powers exist on paper” — only partially checkable from held sources.** A held federal opinion
   quotes §10(b) and Rule 10b-5's substantive prohibition; `SEC-PR:2004-132` cites a civil penalty pursuant to
   Exchange Act §21(d)(3); hundreds of held SEC releases state that the agency sought injunctions, disgorgement,
   civil penalties, or bars. That establishes announced and exercised remedies. The selected test beds do not
   hold a canonical, versioned U.S. Code/CFR text proving the exact investigatory, civil, and administrative
   power applicable to each candidate event. Agency descriptions of their own authority are not a complete
   powers-on-paper check. The card needs an explicit official-law input, not an instruction to infer authority
   from enforcement announcements.

The missing fatal mode is **proxy circularity**: a conviction, substantiated complaint, deficiency, or
adjudication may itself exist only because another enforcement body investigated and published it. “Independent
of this regulator's release index” is weaker than “independently ascertained violation.” The card currently
conflates them.

---

## 2. THE RUN

### Pre-registered parameters — fixed before result queries

| parameter | fixed definition |
|---|---|
| Regulator | U.S. Securities and Exchange Commission |
| Population / conduct | Persons and entities within nationwide federal securities jurisdiction; §10(b) / Rule 10b-5 |
| Window | 2021-01-01..2025-12-31 inclusive |
| Jurisdiction | U.S. federal district and appellate courts; nationwide SEC |
| Numerator unit | Unique CourtListener docket/cluster |
| Numerator threshold | Opinion records a final merits determination that a named actor violated §10(b)/Rule 10b-5 |
| Independence exclusions | SEC-initiated/review matters and United States criminal matters excluded from strict numerator |
| Retrieval anchors | `Rule 10b-5` or `Section 10(b)` plus one of five final-merits phrases |
| Denominator unit | Unique nonblank SEC `file_number`; fallback `source_type:release_number` |
| Denominator threshold | Filed, ordered, adjudged, or settled SEC action containing the same law anchor |
| Language discipline | Charges/allegations/settlements are outputs, not proof of conduct |
| Lag sensitivity | Two-year post-adjudication follow-up; mark right-censored rows |
| Strict pass rule | Reproducibly enumerable independent matters + defensible coverage + comparable SEC matters |

The pre-registration also said not to call the result a base rate or capture measure if the platform could not
enumerate all eligible private matters.

### Numerator: the apparent independent corpus collapsed to zero admissible events

The fixed phrase family returned 92 result rows. Deduplication and review produced this funnel:

| stage | remaining |
|---|---:|
| Raw CourtListener result rows | 92 |
| Unique opinion clusters | 74 |
| Unique dockets | 66 |
| U.S. federal dockets | 48 |
| Exclude SEC/review dockets | 34 |
| Exclude United States criminal dockets | 28 |
| Substantively relevant private §10(b)/Rule 10b-5 matters | 14 |
| Final merits finding that a named actor violated §10(b)/Rule 10b-5 | **0** |

The 14 relevant private matters failed admission for substantive reasons:

| outcome class | matters | result |
|---|---:|---|
| Claim dismissed / dismissal affirmed / no primary violation adequately pleaded | 8 | no violation adjudicated |
| Dismissal reversed or vacated and remanded at pleading stage | 3 | allegation allowed to proceed, no merits finding |
| Class-certification or interlocutory procedure | 3 | no merits finding |
| **Admissible final merits violations** | **0** | **strict numerator = 0** |

Examples show why literal outcome phrases are unsafe:

- *Teamsters v. ServiceMaster* was the sole `found liable` result. The phrase described Terminix being found
  liable in unrelated private termite arbitrations. The §10(b)/Rule 10b-5 claim was dismissed for failure to
  plead scienter, and the Sixth Circuit affirmed.
- *Prodanova v. H.C. Wainwright* contained `final judgment` because the district court entered judgment after
  dismissing the complaint; the Ninth Circuit said no primary §10(b)/Rule 10b-5 violation was adequately
  pleaded.
- *Archegos 20A Litigation* contained `pleaded guilty` in a description of an earlier Tiger Asia criminal case
  and SEC settlement. The private insider-trading claims under review were dismissed.
- *NextEra* contained `convicted` in a hypothetical/conditional disclosure and ended in reversal and remand on
  loss causation, not a finding of securities fraud.

This resolves the hard independence question:

- **DOJ/United States and SEC cases are available, but enforcement-derived.** Using them would be circular or a
  jurisdiction-allocation comparison.
- **Private federal opinions are institutionally independent of SEC publication, but the held search interface
  cannot turn them into an enumerable violation base rate.** In this run it located no final merits violation
  meeting the fixed threshold.
- **`investigation.db` is curated, not independent sampling infrastructure.** Its 10 keyword-matching findings
  cannot supply a denominator or recall estimate.

The platform therefore cannot currently build the card's promised independent base rate for this pair.

### Denominator: the structured action count exists, but the conduct-matched output series does not

The selected SEC action ledger is real and sizable:

| year | AAER | admin | litigation | total |
|---|---:|---:|---:|---:|
| 2021 | 78 | 762 | 292 | 1,132 |
| 2022 | 88 | 825 | 304 | 1,217 |
| 2023 | 113 | 840 | 314 | 1,267 |
| 2024 | 65 | 857 | 288 | 1,210 |
| 2025 | 24 | 365 | 249 | 638 |
| **Total** | **368** | **3,649** | **1,447** | **5,464** |

But the pre-registered `10b-5` and `Section 10(b)` searches returned zero because the action bodies are absent.
This is not a zero-output result:

```
selected SEC action rows                                 5,464
selected action rows with body_text                          0
selected action rows with nonblank file_number           3,640
distinct nonblank file_number values                     2,300
selected action rows without file_number                 1,824
conduct-matched unique §10(b)/Rule 10b-5 matters    unavailable
```

The government-release corpus was tested as a repair, not substituted silently. Its 1,122 complete SEC press
releases in the window yielded 34 exact-law phrase hits; one was `SEC-PR:2022-222`, a Rule 10b5-1 amendment
announcement, leaving 33 enforcement announcements:

| year by stored `published_at` | all complete SEC press releases | exact-law action announcements |
|---|---:|---:|
| 2021 | 270 | 15 |
| 2022 | 236 | 6 |
| 2023 | 258 | 7 |
| 2024 | 212 | 4 |
| 2025 | 146 | 1 |
| **Total** | **1,122** | **33** |

Those titles and bodies preserve materially different postures: “SEC Charges,” “SEC Halts Alleged,” “SEC
Obtains Emergency Relief,” and “Agree to Settle.” They are counted only as agency outputs. They are not treated
as proof of the charged or alleged conduct. Nor are 33 selected press announcements a substitute for all SEC
§10(b)/Rule 10b-5 matters: the platform has no reconciliation showing which action rows received a press
release or how that selection changed by year.

### Statistic

The pre-registered statistic is **undefined**, not zero:

| construction | arithmetic | admissibility |
|---|---:|---|
| Strict independent final-merits matters / conduct-matched SEC matters | `0 / unavailable` | **required; cannot compute** |
| Located strict matters / all SEC action releases | `0 / 5,464 = 0.000%` | invalid category and unit mismatch |
| Located strict matters / selected exact-law SEC press announcements | `0 / 33 = 0.0%` | invalid selective-output denominator |

The two numeric fallbacks are shown to prevent accidental reuse. Neither is an enforcement-gap ratio, neither
supports “capture,” and neither has a coverage denominator or control lift.

---

## 3. CONTROL / BASELINE

**No valid null population or lift figure can be constructed from held data.**

The government-caption result set did perform one useful control function. Twenty of 48 federal phrase-hit
dockets were SEC or United States matters. That 41.7% contamination rate shows that outcome-language search
strongly retrieves enforcement-derived material and validates the card's most important missing warning.
However, it cannot answer whether the SEC acted unusually little.

A valid control would require one of:

1. a matched federal regulator/statute pair (for example CFTC/CEA) with the **same** independent final-merits
   census, conduct severity, entity mix, jurisdiction, and follow-up period; or
2. a preregistered historical SEC comparison window processed through the same complete independent census and
   the same action-classification pipeline; or
3. within one independent violation cohort, matched matters that differ on a capture hypothesis exposure while
   holding conduct, evidence strength, time, and jurisdiction constant.

None is held in executable form. The platform would need:

- an enumerated private federal securities docket/disposition universe, not phrase search;
- reviewed final-merits labels and event dates;
- complete SEC action text/outcome tags and stable matter keys;
- entity resolution between docket parties and SEC respondents;
- an intake/referral series to model composition and a completed lag window.

Only then can the card report follow-through in the target versus control and a lift such as:

```
target non-response rate / matched-control non-response rate
```

A raw target rate, even if computable, would not satisfy the library's current Control discipline.

---

## 4. AMENDMENTS REQUIRED

1. **Replace the aggregate-ratio mechanics with a case-linked primary statistic.** Reason: aggregate counts can
   concern disjoint matters and the current “base rate divided by output series” mixes incompatible units.

   Proposed text:

   > **Mechanics:** Build an independently ascertained, enumerable cohort of violation events in a fixed
   > regulator × population × conduct × jurisdiction cell. Join each event/subject to the regulator's
   > matter-level output within a pre-registered lag. Primary statistic = qualifying regulator responses /
   > eligible independent violations; companion gap multiple = eligible independent violations / qualifying
   > responses, with zero responses reported as an unbounded gap rather than divided silently. Deduplicate
   > releases, orders, AAERs, and press announcements to one underlying matter. Do not call an aggregate count
   > ratio “capture” when the event-level join cannot be made.

2. **Define “independent” operationally and add circularity as the first failure mode.** Reason: DOJ releases,
   SEC releases, government prosecutions, and opinions arising from them are outputs of enforcement systems,
   not independent violation ascertainment.

   Proposed sentence:

   > “Independent” means the event entered the numerator without using this regulator's action, referral,
   > investigation, announcement, or a parallel enforcement body's case as the discovery predicate. Report
   > private audit/inspection/journalist measurement separately from other-agency adjudication; the latter is a
   > jurisdiction-split sensitivity, not the strict numerator.

3. **Replace Minimum data with an auditable schema contract.** Reason: “output series + proxy” does not require
   enumeration, matching, event dates, or authority.

   Proposed text:

   > **Minimum data:** (i) an enumerable independent violation cohort with at-risk population or documented
   > event-census coverage, reviewed final-merits/substantiation labels, and event dates; (ii) regulator output
   > with full text, action/outcome type, stable matter key, respondent key, and complete annual coverage;
   > (iii) a hard or audited entity/matter join; (iv) complaint/referral/intake counts for composition checks;
   > (v) official, versioned statute/rule text establishing jurisdiction and the exact available remedies.

4. **Add the missing Pre-registration field.** Reason: card 4 is outcome-sensitive to more choices than several
   statistic cards already named in the header.

   Proposed text:

   > **Pre-registration:** fix the regulator; regulated population; conduct category; jurisdiction; eligible
   > violation event and evidentiary threshold; independence exclusions; numerator and output units; observation
   > window and date fields; qualifying regulator outputs; matter-deduplication and entity-resolution rules;
   > enforcement lag and right-censor rule; severity strata; control population; and sensitivity analyses before
   > retrieving results. Register whether the primary measure is event-linked follow-through or an aggregate
   > gap multiple; never switch between them after seeing counts.

5. **Add the missing Coverage statement field.** Reason: complete query pagination was not corpus recall, and the
   action corpus's statutory classifiability was 0%.

   Proposed text:

   > **Coverage statement:** report separately (a) independent-cohort recall or the reason it is unknowable,
   > (b) the fraction of regulator outputs with full text and matter/respondent keys, (c) the fraction of
   > numerator events resolved to regulator subjects, and (d) the fraction with a completed lag window. A located
   > zero with unknown recall is “no qualifying event located,” not a zero violation rate. Do not publish the
   > ratio when either cohort coverage or join coverage is unquantified.

6. **Add the missing Control field.** Reason: near-zero output has no scale without comparable enforcement
   propensity, severity, and intake.

   Proposed text:

   > **Control:** construct from the same held-data pipeline a matched regulator/statute, historical period, or
   > within-cohort comparison with the same ascertainment, jurisdiction, conduct severity, entity mix, and lag.
   > Report the target's event-linked non-response rate, the control rate, and lift; never promote a raw target
   > rate. Government-initiated cases may test numerator independence but are not a no-capture control.

7. **Add the missing Preconditions field and mark the present SEC leg blocked.** Reason: credentials, logging,
   full text, legal authority, and censoring determine whether the card can run.

   Proposed text:

   > **Preconditions:** CourtListener token/live API (v4 party-prefix filters use `__istartswith`, not
   > `contains`/`icontains`); read-only/no-log query mode when required; full-text regulator corpus with
   > matter/outcome tags; official law source; completed lag window; audited entity resolution. **BLOCKED on
   > current `sec_enforcement.db`: `body_text` is empty in 37,592/37,592 actions, so conduct-matched output is
   > not constructible from the named tool. Both named query wrappers normally write search-log rows; a
   > read-only/no-log mode is required.**

8. **Correct the Ithildin mapping's capability claim.** Reason: the tools are discovery surfaces, not a paired
   ratio pipeline.

   Proposed text:

   > **Ithildin mapping:** `query_sec_enforcement` currently supports release/year/respondent counts but not
   > conduct classification because action bodies are empty; `government_release_corpus` supplies selective SEC
   > press-announcement text, not the complete action series; `query_courtlistener` supplies searchable
   > opinions, not an enumerated misconduct cohort, and normally writes a search log. A separate cohort builder,
   > disposition reviewer, matter deduplicator, and party/respondent resolver are required before the move is
   > runnable. `source_reliability` governs language; `hypothesis_tracker` records, but does not compute, the
   > capture hypothesis.

9. **Expand Failure modes.** Reason: the current three are valid but downstream of more basic validity threats.

   Add:

   > Circular proxy (another enforcement output used as “independent” violation evidence); publication and
   > opinion-selection bias; allegation/charge/settlement treated as adjudicated conduct; release-to-matter
   > duplication; event-date mismatch; entity-resolution false negatives; communications-policy change mistaken
   > for enforcement change; severity and regulated-population mix; incomplete lag/right censoring; and
   > numerator/denominator units that do not match.

10. **Make the powers-on-paper instruction a data requirement, not an analyst reminder.** Reason: the held
    releases show remedies sought or imposed but are not a canonical authority compilation.

    Proposed text:

    > Before interpreting non-response, cite the operative statute/regulation and version that gives this
    > regulator jurisdiction over the population/conduct and the exact power counted as “available” (investigate,
    > refer, sue, fine, suspend, revoke, bar). Distinguish mandatory from discretionary powers and record
    > concurrent/primary jurisdiction. Agency press releases are evidence of announced exercise, not sufficient
    > proof of the legal power.

11. **Add card 4 to the discipline-field header's explicit to-do list.** Reason: the present list names cards 3,
    5, 14, 21, and 29 but omits this computed-statistic card. That omission helped a universally observed family
    appear operationally graduated without a live execution.

12. **Separate ontology graduation from platform readiness.** Reason: four-outlet recurrence validates the
    detection family, not the local adapters.

    Proposed status suffix:

    > **Cross-outlet universal; platform execution blocked pending an independently enumerable violation cohort
    > and a conduct-classifiable, matter-deduplicated regulator output series.**

---

## 5. VERDICT

**blocked-on-independent-violation-census-and-classifiable-output.** Cross-outlet graduation is supported as an
editorial/detection-family claim, but it is overstated if read as “runnable on Ithildin.” For the fairest held
pair, the platform could count 5,464 SEC action releases but could not classify them to the selected conduct
because 100% lacked body text; its independent CourtListener leg returned 28 non-government-caption federal
dockets, only 14 substantively relevant private securities matters, and **zero final merits §10(b)/Rule 10b-5
violations**. The strict ratio was therefore undefined, and no null population, lift, coverage fraction, or
complete lag adjustment could be built. A future agent invoking the current card should expect an apparent
output count plus a search-hit sample—not a defensible enforcement-gap statistic—until both named blockers are
repaired.

---

### Artifacts (scratch, not persisted to repo)

`/tmp/osint-nMqnygO0/` — `preregistration.md`; government-release and SEC-action stats/search outputs;
five CourtListener search result files; reviewed full-text opinion bundle and context extracts;
`sec_denominator.py` + `sec-denominator.json`; read-only audit outputs. No database, lead, finding, connection,
hypothesis, infra request, search log, or profile state was written.

---

## 6. ADDENDUM 2026-07-29 — the empty output-side text layer was our defect, and is repaired

The run above reported that **5,464 of 5,464** selected `sec_enforcement.db` rows (and 37,592 of 37,592 overall)
had empty `body_text`. A follow-up investigation established the cause and fixed it. This addendum records the
change; nothing in §§1–5 is rewritten, because that section is the record of what was true at run time.

**Cause: ingestion defect, not upstream unavailability.** `tools/ingest_sec_enforcement.py` was index-only. It
scraped the SEC enforcement index pages and inserted nine columns; `body_text` appeared solely in the table DDL
and in the FTS sync triggers, and no code path ever fetched or wrote it. There was no per-release fetch step to
disable or misconfigure — the feature was never implemented. Bodies were never fetched, not fetched and dropped.

**The source carries the text.** All 37,592 rows already stored a `release_url`. Probing every distinct URL shape
returned HTTP 200 with real content in four templates: PDF orders under `/files/litigation/admin/<year>/`,
Drupal HTML at `/enforcement-litigation/litigation-releases/lr-N`, legacy `.txt`, and legacy `.htm`.

**One genuine source-side limit, and it is small.** Modern `/administrative-proceedings/` and
`/opinions-adjudicatory-orders/` pages are stubs carrying only the respondent name (≈665 chars of site chrome,
no body container, no order link). The ordered text exists only in the order PDF filed under the *page's URL
slug* — not the row's release number, since composite releases (e.g. `AAER-4403` and `34-97381`) share one page
and only the slug resolves. 3,498 rows corpus-wide sit on stub pages, but just **4** fall in the 2021–2025 window.

**Repair.** A resumable `fetch-bodies` pass now retrieves and extracts bodies, deduplicating by `release_url`
(30,270 distinct documents behind 37,592 rows) and recording per-row provenance in `body_fetch_status`,
`body_source_url`, `body_extraction_method`, and `body_fetched_at`. Text is stored verbatim; a status of `empty`
(source reached, no retrievable text) is kept distinct from `failed` (transport error), and site chrome is never
stored as a body.

**Window result — the §2 Denominator block is superseded on the text line only:**

```
selected SEC action rows                                 5,464
selected action rows with body_text                      5,464   (was 0)
  extracted from PDF orders                              3,993   mean 15,663 chars
  extracted from HTML release pages                      1,471   mean  2,727 chars
unresolved                                                   0
rows containing "10b-5"                                  1,884   (pre-registered search, was 0)
rows containing "Section 10(b)"                          1,657   (pre-registered search, was 0)
```

Posture language survives extraction intact across the window: 4,288 rows contain *alleg\**, 3,191 *consent\**,
2,980 *settle\**, 2,338 *without admitting*, 277 *convicted*. The corpus rule is unchanged — these are agency
statements of what was alleged, ordered, or settled, not proof of the described conduct.

**What this changes for card 4, and what it does not.** The §1 "Minimum data" item (iii) blocker — *the output
side needs full text* — is cleared, and the "Preconditions" item *a populated full-text/outcome layer for
`sec_enforcement.db`* no longer holds. Conduct-classifiability in this cell is no longer 0%.

**The card remains blocked.** The two blockers §5 names as fatal are untouched by this repair:

1. **No enumerable independent numerator.** CourtListener remains a search index, not a census. The strict
   numerator was zero *on substantive review of located matters*, not for want of SEC text.
2. **The aggregate ratio still has no fixed event unit,** no matter-deduplication rule, no control, and no lift.

The remaining output-side gap is also unrepaired: `file_number` is still absent on 1,824 window rows (33.4%),
with only 2,300 distinct nonblank values across 3,640 rows, so releases still cannot be reliably collapsed to
underlying matters. A conduct-matched, matter-deduplicated SEC output series needs that key, not just body text.

**Also found: two upstream `SEC-PR` key typos.** `SEC-PR:2022-123` sits at `/press-releases/2023-123` with
`published_at` 2023-06-29; the SEC's own release-number field publishes `2022-123`, contradicted by its `og:url`
and its linked `comp-pr2023-123.pdf`. The mirror case, `SEC-PR:2013-218`, has a correct release number but a
transposed URL slug (`/press-releases/2103-218`), whose page itself reads `2013-218`. `published_at` is correct in
both, so it is the arbiter rather than the slug. Both agency strings are preserved verbatim;
`government_release_corpus.py audit-keys` reports the disagreement. The **time key needed no reconciliation** —
the citable release-number key did.

### Addendum follow-up — backfill completed corpus-wide, and the "source-side limit" was smaller than first reported

The backfill above finished on 2026-07-29: **37,793 of 37,793 action rows carry verbatim release text, 0
unresolved.** Extraction mix: 20,087 PDF orders, 15,089 Drupal HTML, 2,596 legacy plain text, 15 full-page HTML,
6 via legacy text markers. The index was also brought current in the same session (`ingest --incremental`,
+201 actions through LR-26596 / 2026-07-29), all bodied.

Two corrections to the addendum's account of what the *source* withholds:

1. **The stub-page limit is not the only "no body" shape, and neither is permanent.** Besides stub pages,
   some modern `/litigation-releases/` pages publish a **header-only** body — the container is present but
   holds 54–182 characters. A container-presence check accepts those as bodies; the ladder must key on
   extracted length.
2. **Every row the first full pass left as `empty` was in fact retrievable.** Their text survives in the legacy
   static files, under conventions that differ by URL family *and* by era: `/files/litigation/admin/<year>/…pdf`
   and `/files/litigation/litreleases/<year>/…htm` from roughly 2005, and year-less `…/<slug>.htm` before that.
   Cross-applying one family's convention to the other produces a URL that cannot exist — the initial fallback
   did exactly that for litigation releases, which is what manufactured the apparent limit. After the ladder was
   made family- and era-aware, all 15 cleared.

So the corpus has **no** demonstrated source-side text gap for enforcement actions. The claim in the addendum
that 3,498 stub rows lack retrievable text should be read as unproven: stub pages lack *inline* text, but their
order PDFs resolved.

None of this changes §5. Card 4 remains blocked on the numerator: no enumerable independent violation cohort, no
event unit, no control, no lift. `file_number` remains absent on 33.4% of window rows, so matter deduplication
on the output side is still unavailable.
