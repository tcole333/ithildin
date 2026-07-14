#!/usr/bin/env python3
"""Build the bounded Tier-2 detention guarantee/utilization synthesis package."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "investigation.db"
REPORTS = ROOT / "investigations/geo-group/reports"
PREFIX = REPORTS / "2026-07-14-tier2-detention-guarantee-utilization-wave11"

REPORT = Path(f"{PREFIX}-report.md")
MATRIX = Path(f"{PREFIX}-facility-period-comparison-matrix.csv")
ACH = Path(f"{PREFIX}-ach.json")
NOVELTY = Path(f"{PREFIX}-novelty.json")
MANIFEST = Path(f"{PREFIX}-source-db-manifest.json")
SHA = Path(f"{PREFIX}-sha256.csv")

FINDING_IDS = [
    12398, 12422, 12425, 12426, 12427, 12428, 12447,
    12554, 12642, 12644, 12645, 12646, 12648, 12652, 12653,
    12654, 12655, 12801, 12818, 12819, 12820, 12821, 12822,
    12823, 12861, 12875, 12876, 12877, 12990,
    *range(13017, 13029), 13032,
]

SOURCE_FILES = [
    "investigations/geo-group/sources/2026-07-14-lead-60208-southtexas-folkston-economics-wave11/south-texas/OIG-22-40.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60208-southtexas-folkston-economics-wave11/folkston/OIG-22-47.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60208-southtexas-folkston-economics-wave11/folkston/EROIGSA170002-P00022.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60208-southtexas-folkston-economics-wave11/county/charlton-agenda-packet-2026-01-22.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/oversight/OIG-23-26-May23.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY25_detentionStats.xlsx",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-detainment-statistics/FY26_detentionStats_04092026.xlsx",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-contracts/70CDCR20D00000009-org-Adelanto-DetFac.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-contracts/ice-aurora-70CDCR22D00000001-P00011.pdf",
    "investigations/geo-group/sources/2026-07-14-lead-60206-western-cdf-economics-wave11/ice-contracts/ice-tacoma-HSCEDM15D00015-P00049.pdf",
]

PRIOR_ARTIFACTS = [
    "investigations/geo-group/reports/2026-07-14-lead-60206-western-cdf-economics-wave11-report.md",
    "investigations/geo-group/reports/2026-07-14-lead-60206-western-cdf-economics-wave11-facility-period-ledger.csv",
    "investigations/geo-group/reports/2026-07-14-lead-60208-southtexas-folkston-economics-wave11-report.md",
    "investigations/geo-group/reports/2026-07-14-lead-60208-southtexas-folkston-economics-wave11-facility-period-ledger.csv",
    "investigations/geo-group/reports/2026-07-14-geo-grade-component-consequence-systemic-report.md",
    "investigations/geo-group/reports/2026-07-14-geo-grade-component-consequence-ach.json",
    "investigations/geo-group/reports/2026-07-13-tier2-systemic-contract-architecture.md",
    "investigations/geo-group/reports/2026-07-14-lead-57842-geo-fy25-fy26-action-report.md",
]


def ratio(adp: str, minimum: str) -> str:
    return f"{(Decimal(adp) / Decimal(minimum)):.6f}"


def row(**kwargs: str) -> dict[str, str]:
    fields = [
        "facility", "evidence_group", "period", "guaranteed_minimum", "adp_or_occupancy",
        "utilization_to_minimum", "rate", "payment_or_flow", "response_or_remedy",
        "later_comparison", "h1_diagnosticity", "h0_diagnosticity", "dependency_group",
        "interpretation_limit", "finding_ids",
    ]
    return {field: kwargs.get(field, "") for field in fields}


ROWS = [
    row(
        facility="South Texas ICE Processing Center", evidence_group="OIG historical unused-capacity finding",
        period="2020-11 through 2021-10", guaranteed_minimum="1350", adp_or_occupancy="36% of guaranteed space unused on average",
        utilization_to_minimum="0.64 complement of reported unused share; not a recovered ADP", rate="$100.86/day; $101.36 beginning 2021-08",
        payment_or_flow="approximately $18m paid for unused space", response_or_remedy="ICE combined housing units; OIG recommendation closed",
        later_comparison="FY2025 completed task: $60.524m obligation/$60.524m outlay; current guarantee/ADP/invoice absent",
        h1_diagnosticity="Unused payment is consistent, but closure/response cuts against a blanket no-remedy account",
        h0_diagnosticity="Pandemic response and closure are consistent; cost-effectiveness and rate/minimum change unproved",
        dependency_group="South Texas OIG-22-40 chain", interpretation_limit="Historical pandemic-period rate cannot be carried forward; outlay is not invoice",
        finding_ids="13017;13018;12818;13019;13020",
    ),
    row(
        facility="Tacoma / Northwest ICE Processing Center", evidence_group="OIG historical unused-capacity finding",
        period="2021-09 through 2022-08; OIG unused-payment window overlaps but is not identical",
        guaranteed_minimum="1181", adp_or_occupancy="ADP 374; OIG separately reported 31% of minimum for 2021-10 through 2022-08",
        utilization_to_minimum="period mismatch prevents one recomputed ratio", rate="$138.86/day as of 2021-10",
        payment_or_flow=">$40m paid for unused space; nearly $5m/month", response_or_remedy="ICE declined minimum update; OIG recommendation remained open",
        later_comparison="FY25 YTD 1179.616046/1181; FY26 YTD 1289.437159/1181",
        h1_diagnosticity="Declined adjustment/open recommendation is diagnostic for consequence gap",
        h0_diagnosticity="Later use is consistent with readiness, but does not prove prior forecast or cost-effectiveness",
        dependency_group="Tacoma OIG-23-26 plus shared IIDS snapshot group", interpretation_limit="Later occupancy neither reprices nor validates historical unused-bed payment",
        finding_ids="13028;12819;12822;12823;13027",
    ),
    row(
        facility="Golden State Annex", evidence_group="OIG historical unused-capacity finding",
        period="2022-04-20 through 2023-04-19", guaranteed_minimum="560", adp_or_occupancy="ADP 136; 424 average unused guaranteed beds",
        utilization_to_minimum=ratio("136", "560"), rate="redacted", payment_or_flow="approximately $25.3m paid for unused space",
        response_or_remedy="minimum-update recommendation now closed; revised terms/savings unavailable",
        later_comparison="no matched current rate/invoice package in this synthesis",
        h1_diagnosticity="Large unused payment is consistent; public closure without economics is not diagnostic",
        h0_diagnosticity="Closure is consistent with ordinary remedy, but cannot show proportional adjustment",
        dependency_group="Golden State OIG-24-23 chain", interpretation_limit="Closed status is not a price change or invoice deduction",
        finding_ids="12398;12422;12642;12644",
    ),
    row(
        facility="Folkston IPC and Annex", evidence_group="OIG staffing consequence plus county cash-flow chain",
        period="FY2021 inspection through calendar 2025", guaranteed_minimum="not recovered",
        adp_or_occupancy="IPC ADP/capacity 286/780; Annex 88/338", utilization_to_minimum="not calculable without minimum",
        rate="not recovered", payment_or_flow="full funding during OIG period; 2025 county receipts $53.777m/expenditures $51.802m",
        response_or_remedy="attempted penalties not enforced; vendor-paid overtime; recommendation closed",
        later_comparison="post-OIG invoices/deductions/downstream allocation unresolved",
        h1_diagnosticity="Direct non-enforcement/full-funding statement is diagnostic for H1 in the inspected period",
        h0_diagnosticity="Vendor expense and closure are ordinary-response evidence; later financial effect unknown",
        dependency_group="Folkston OIG/county/IGSA chain", interpretation_limit="Capacity is not minimum; county cash flow is not GEO revenue or invoice proof",
        finding_ids="12425;12426;12427;12652;13021;13022;13023",
    ),
    row(
        facility="Adelanto ICE Processing Center", evidence_group="shared ICE IIDS FY25/FY26 snapshots",
        period="FY25 YTD as of 2025-09-15", guaranteed_minimum="640", adp_or_occupancy="575.544413",
        utilization_to_minimum=ratio("575.544413", "640"), rate="not recovered", payment_or_flow="not recovered",
        response_or_remedy="2024 ODO follow-up reported no findings", later_comparison="FY26 YTD 1733.153006/640 = " + ratio("1733.153006", "640"),
        h1_diagnosticity="Neutral without consequences", h0_diagnosticity="Later above-minimum use is consistent with readiness/expansion",
        dependency_group="shared Western IIDS two-snapshot group", interpretation_limit="Current reported minimum is not a funded CLIN or invoice",
        finding_ids="12645;12801;13024",
    ),
    row(
        facility="Desert View Annex", evidence_group="shared ICE IIDS FY25/FY26 snapshots",
        period="FY25 YTD as of 2025-09-15", guaranteed_minimum="480", adp_or_occupancy="423.303725",
        utilization_to_minimum=ratio("423.303725", "480"), rate="not recovered", payment_or_flow="not recovered",
        response_or_remedy="reported minimum differs from historical 600; governing current CLIN not recovered",
        later_comparison="FY26 YTD 425.606557/120 = " + ratio("425.606557", "120"),
        h1_diagnosticity="Neutral without current rates/invoices", h0_diagnosticity="Later use and lower reported floor are consistent with adjustment, but not proof of contract remedy",
        dependency_group="shared Western IIDS two-snapshot group; same Adelanto IDV chain", interpretation_limit="Workbook-to-workbook minimum change is not labeled a contract amendment",
        finding_ids="12646;12849;13025",
    ),
    row(
        facility="Aurora / Denver CDF", evidence_group="shared ICE IIDS FY25/FY26 snapshots",
        period="FY25 YTD as of 2025-09-15", guaranteed_minimum="600", adp_or_occupancy="1180.948424",
        utilization_to_minimum=ratio("1180.948424", "600"), rate="redacted", payment_or_flow="not recovered",
        response_or_remedy="2025 maximum-bed increase and added funding; performance rationale absent",
        later_comparison="FY26 YTD 1260.038251/600 = " + ratio("1260.038251", "600"),
        h1_diagnosticity="Neutral to financial-consequence question", h0_diagnosticity="Continued above-minimum use is consistent with demand",
        dependency_group="shared Western IIDS two-snapshot group", interpretation_limit="Maximum beds, minimum, ADP, funding, and invoice are distinct",
        finding_ids="12654;12655;12820;13026",
    ),
    row(
        facility="Tacoma / Northwest ICE Processing Center", evidence_group="shared ICE IIDS FY25/FY26 snapshots",
        period="FY25 YTD as of 2025-09-15", guaranteed_minimum="1181", adp_or_occupancy="1179.616046",
        utilization_to_minimum=ratio("1179.616046", "1181"), rate="redacted current schedule", payment_or_flow="not recovered",
        response_or_remedy="extension/added funding; performance treatment not stated",
        later_comparison="FY26 YTD 1289.437159/1181 = " + ratio("1289.437159", "1181"),
        h1_diagnosticity="Later use is neutral to whether past consequences were proportional",
        h0_diagnosticity="Later above-minimum use is consistent with surge-readiness capacity becoming used",
        dependency_group="shared Western IIDS two-snapshot group; Tacoma historical chain", interpretation_limit="Partial YTD averages are not billed bed-days",
        finding_ids="12823;12990;13027;13032",
    ),
    row(
        facility="Torrance County Detention Facility (non-GEO)", evidence_group="limited external remedy comparator",
        period="through 2022-01", guaranteed_minimum="714 reduced to 505", adp_or_occupancy="not used here",
        utilization_to_minimum="not calculated", rate="fixed monthly charges disclosed", payment_or_flow="25% monthly-billing penalty assessed",
        response_or_remedy="minimum reduction and billing penalty for staffing problems",
        later_comparison="not a prevalence denominator", h1_diagnosticity="Shows ICE can impose explicit remedies; does not prove GEO treatment",
        h0_diagnosticity="Consistent with ordinary-remedy capability", dependency_group="Torrance OIG-22-75 comparator",
        interpretation_limit="One non-GEO comparator cannot establish base rates", finding_ids="12428;12653",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scores(db: sqlite3.Connection) -> list[dict[str, object]]:
    result = []
    for hypothesis_id in (335, 336):
        h = db.execute("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
        counts = {key: 0 for key in ("consistent", "inconsistent", "neutral", "not_applicable")}
        for assessment, count in db.execute(
            "SELECT assessment, COUNT(*) FROM hypothesis_evidence_matrix WHERE hypothesis_id=? GROUP BY assessment",
            (hypothesis_id,),
        ):
            counts[assessment] = count
        total = counts["consistent"] + counts["inconsistent"] + counts["neutral"]
        result.append({
            "id": hypothesis_id, "title": h["title"], "is_null": bool(h["is_null_hypothesis"]),
            **counts, "total_evaluated": total,
            "inconsistency_ratio": round(counts["inconsistent"] / total, 4) if total else None,
        })
    return sorted(result, key=lambda item: item["inconsistency_ratio"])


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    finding_rows = []
    for finding_id in FINDING_IDS:
        found = db.execute(
            "SELECT id,target_name,summary,confidence,claim_type,verification_status,thread_id,profile_id FROM findings WHERE id=?",
            (finding_id,),
        ).fetchone()
        if not found:
            raise RuntimeError(f"Missing finding {finding_id}")
        if found["verification_status"] != "verified":
            raise RuntimeError(f"Finding {finding_id} is not verified")
        finding_rows.append(dict(found))

    competition = scores(db)
    ach = {
        "generated_on": "2026-07-14",
        "analysis_runs": [122, 123],
        "question": "Do historical unused-bed payments and the FY25-to-FY26 YTD utilization shift distinguish H1 #335 from H0 #336?",
        "competition_group": "geo-performance-consequence-gap",
        "pre_wave11_snapshot_from_run_97": [
            {"hypothesis_id": 336, "total_evaluated": 37, "inconsistent": 5, "inconsistency_ratio": 0.1351},
            {"hypothesis_id": 335, "total_evaluated": 37, "inconsistent": 7, "inconsistency_ratio": 0.1892},
        ],
        "post_wave11_snapshot": competition,
        "new_assessments": [
            {"hypothesis_id": 335, "finding_id": 13032, "assessment": "neutral", "assessed_by": "agent:systemic-analysis:run-122"},
            {"hypothesis_id": 336, "finding_id": 13032, "assessment": "consistent", "assessed_by": "agent:systemic-analysis:run-122"},
        ],
        "dependency_collapse": {
            "finding_group": [13024, 13025, 13026, 13027],
            "collapsed_to": 13032,
            "reason": "Four facility rows share the same agency IIDS templates and the same two partial periods; treating them as four independent evidence sources would inflate diagnosticity.",
        },
        "verdict": "H0 #336 remains least inconsistent, not confirmed. The later utilization group is consistent with surge readiness but does not refute H1 #335 or establish prior cost-effectiveness. Folkston non-enforcement and Tacoma's unresolved minimum response remain diagnostic for H1; ordinary closure/vendor-cost evidence and the non-GEO Torrance remedy remain diagnostic for H0.",
        "ratio_warning": "Inconsistency ratios are row-level matrix summaries, not probabilities, likelihood ratios, or independent-source weights.",
        "falsification": {
            "335": "Matched QASP, invoice, CPARS, deduction, corrective-action and option files show routine severity- and utilization-proportionate consequences across GEO and non-GEO controls.",
            "336": "Primary records across at least three independent chains show absent or nominal consequences, persistent unsupported minimums, or renewals/expansions despite comparable unresolved deficiencies after controlling for operational demand.",
        },
    }
    ACH.write_text(json.dumps(ach, indent=2) + "\n", encoding="utf-8")

    novelty = {
        "generated_on": "2026-07-14", "analysis_run": 123,
        "candidate_count": 4, "surviving_hunches": 0, "hypotheses_created": 0, "leads_created": 0,
        "candidates": [
            {"candidate": "surge-readiness option premium", "decision": "filtered", "reason": "Already encoded in H0 #336; only Tacoma currently links a historical unused-payment period to later same-minimum utilization, and forecast/counterfactual cost records are absent."},
            {"candidate": "adaptive guaranteed-minimum resizing", "decision": "filtered", "reason": "Adelanto/Desert View are one IDV family and shared-template source; current workbook minimums are not authenticated funded CLIN amendments or invoice terms."},
            {"candidate": "fixed floor plus above-minimum surge upside", "decision": "filtered", "reason": "Contract architecture is known and current rates are redacted; the candidate overlaps #335/#336 and lacks three independent period-compatible rate/invoice chains."},
            {"candidate": "post-OIG cash flow proves continued no-consequence funding", "decision": "filtered", "reason": "Folkston county cash flow lacks gross invoices, deductions and downstream payee allocation; finding #13023 already records the unresolved negative result."},
        ],
        "synthesis_finding": 13032,
        "finding_role": "Descriptive dependency-collapsed temporal result, not a new hypothesis or causal mechanism.",
        "existing_nonduplicate_research_routes": ["human_actions:38", "human_actions:60", "human_actions:61", "human_actions:74", "human_actions:75", "infra_request:150"],
        "auto_leads_run": False,
    }
    NOVELTY.write_text(json.dumps(novelty, indent=2) + "\n", encoding="utf-8")

    fieldnames = list(ROWS[0])
    with MATRIX.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ROWS)

    h0 = next(item for item in competition if item["id"] == 336)
    h1 = next(item for item in competition if item["id"] == 335)
    report = f"""# Detention guarantee and utilization systemic synthesis

**Profile / thread:** `geo-group` / 110  
**Analysis runs:** systemic-analysis #122; generate-hunches #123  
**ACH competition:** #335 versus #336 (`geo-performance-consequence-gap`)  
**New synthesis:** verified finding #13032

## Bottom line

The newly comparable Western facility data document a real but bounded temporal shift: Adelanto, Desert View, and Tacoma were below or nearly at their reported minimums in the ICE FY25 YTD snapshot as of September 15, 2025, while all four Western CDFs were above their reported minimums in the FY26 YTD snapshot as of April 2, 2026. Aurora was already above its minimum in both snapshots.

That result is consistent with the surge-readiness component of H0 #336 and weakens a claim that all sampled guaranteed capacity remained chronically unused. It does not establish that the historical South Texas, Tacoma, or Golden State unused-bed payments were cost-effective readiness purchases. It also does not refute H1 #335: current unit rates, funded CLIN schedules, billed bed-days, gross invoices, deductions, forecasts, and counterfactual capacity costs remain unavailable.

H0 #336 remains **least inconsistent, not confirmed**: {h0['inconsistent']} inconsistent rows among {h0['total_evaluated']} evaluated ({h0['inconsistency_ratio']:.4f}), versus {h1['inconsistent']} among {h1['total_evaluated']} ({h1['inconsistency_ratio']:.4f}) for H1 #335. These ratios are bookkeeping summaries of heterogeneous rows, not probabilities or independent-source weights.

No new hypothesis or lead survived the novelty gate. Surge readiness is already #336, and the other candidates lack three independent, period-compatible chains. Finding #13032 encodes only the new cross-facility temporal result.

## Dependency collapse and period controls

Findings #13024–#13027 are four facility rows from the same ICE IIDS templates and the same two shared periods. They are collapsed into one temporal evidence group, finding #13032. The facility chains are operationally distinct, but the source and timing dependencies prevent treating the rows as four independent confirmations.

- FY25 is YTD through **September 15, 2025**, not a completed fiscal or performance year.
- FY26 is YTD through **April 2, 2026**. The filename embeds `04092026`; the internal IIDS date is April 2.
- The two windows have different elapsed lengths and are not matched invoice periods.
- `Guaranteed Minimum` in the workbook is not automatically the funded CLIN minimum or invoice quantity.
- ADP is not billed bed-days. Current minimum, capacity, maximum beds, obligation, outlay, invoice, deduction, and GEO revenue remain separate.
- Historical rates are not carried forward.

## Western facility shift

| Facility | FY25 YTD minimum / ADP | FY26 YTD minimum / ADP | Result |
|---|---:|---:|---|
| Adelanto | 640 / 575.544413 | 640 / 1,733.153006 | Below to well above |
| Desert View | 480 / 423.303725 | 120 / 425.606557 | Below to above; governing minimum change not recovered |
| Aurora | 600 / 1,180.948424 | 600 / 1,260.038251 | Above in both |
| Tacoma | 1,181 / 1,179.616046 | 1,181 / 1,289.437159 | Nearly at to above |

This occurred during the separately verified ICE activation and obligation-expansion period (#12447, #12876). “Occurred during” is not a causal attribution to enforcement policy, a forecast, or a contract decision.

## Surge-readiness mechanism test

A defensible surge-readiness inference requires more than later use. At minimum it needs: a contemporaneous demand forecast; proof that retained capacity was the same capacity bought in the low-use period; matched availability and billed-bed-day records; applicable rates and fixed/variable cost structure; time and cost to obtain alternative capacity; and the actual deduction or renegotiation record.

Tacoma supplies the strongest before/after sequence: OIG reported a 1,181 minimum, pandemic-era ADP 374 and more than $40 million for unused space, while the later ICE snapshots show the same reported minimum nearly met and then exceeded. This is consistent with readiness capacity becoming useful. Yet OIG's open recommendation, ICE's earlier refusal to adjust the minimum, and missing forecast/invoice records prevent a conclusion that the prior payment was correctly sized or cost-effective.

South Texas supplies a separate pandemic-era unused-payment context—36% average unused space and approximately $18 million paid—plus a documented housing-unit response and recommendation closure. It lacks a current period-compatible minimum/ADP/invoice package. Golden State supplies a third unused-payment context and a later closed recommendation, but the revised economics are not public. These contexts establish recurrent unused-capacity payments; they do not independently validate the readiness mechanism.

## Consequence evidence remains mixed

- **Folkston:** attempted staffing penalties were not enforced and full funding continued during the inspected period (#12425), which is directly diagnostic for H1. Vendor-paid overtime and recommendation closure (#12426) support an ordinary-response account, but post-OIG invoice treatment remains unresolved (#13023).
- **Tacoma:** the minimum recommendation remained open after ICE declined adjustment (#12819), and repeat deficiencies followed a completed UCAP (#12822). Later extension and higher utilization do not reveal the consequence decision.
- **South Texas and Golden State:** recommendation closures are visible, supporting H0 procedurally, but neither public record proves a proportional price, minimum, invoice, or deduction effect.
- **Adelanto:** a 2024 no-findings follow-up is counterevidence to a monotonic unresolved-performance story (#12801), while current economics remain incomplete.
- **Torrance, non-GEO:** ICE publicly assessed a 25% billing penalty and reduced the minimum from 714 to 505 (#12428, #12653). This proves remedy capability, not equal treatment or a remedy base rate.
- **Inspection grades:** #12861 shows component deficiencies can coexist with compliant aggregate grades, but does not link grade structure to payment or option treatment.

## Best innocent and alternative explanations

1. Pandemic controls, litigation-related transfer restrictions, and operational logistics depressed historical populations temporarily.
2. ICE purchased availability and fixed-cost continuity whose value appears only under later demand, even if ex ante sizing cannot now be tested publicly.
3. Enforcement expansion, new activations, and January FY2026 funding increased demand independently of earlier contract design.
4. Minimums and capacity definitions may have changed through ordinary administration; Desert View's workbook values are suggestive but not authenticated contract amendments.
5. Partial-period averages and shared agency templates create a strong-looking co-directional pattern without four independent evidence sources.
6. Closeout deobligations and award outlays may reflect ordinary accounting rather than performance remedies or invoices.

## ACH verdict

Finding #13032 was scored **neutral** against H1 #335 and **consistent** against H0 #336. It does not make H1 inconsistent because later use says nothing about proportional consequences. It is limited support for H0 because actual later utilization is one prediction of readiness purchasing, while the missing forecast and counterfactual cost evidence prevents confirmation.

The pre-wave run #97 scores were 5/37 inconsistent for H0 and 7/37 for H1. Adding one neutral H1 row and one consistent H0 row changes the denominators to 38 without adding an inconsistency. The least-inconsistent ordering is unchanged.

The fastest discriminator remains matched agency contract-administration data across at least three independent chains: forecasts, funded rate/minimum schedules, daily or monthly billed quantities, invoices, credits/deductions, CPARS/QASP records, corrective-action closure, and option/extension decisions. Existing human actions and infrastructure requests already commission that work; a duplicate lead was not created.

## Novelty and premortem

The surge-readiness candidate fails novelty because it is H0 #336. “Adaptive minimum resizing” fails because the strongest examples share one IDV/template family and the workbook minimums are not contract amendments. “Floor plus surge upside” lacks current rates and invoices and overlaps the existing competition. Post-OIG Folkston cash flow cannot establish no-consequence funding without invoice allocation.

Premortem: the likeliest analytical error is mistaking enforcement-driven later utilization for proof that earlier idle-capacity payments were rational. The evidence enabling that error is the visually strong four-row shift combined with mismatched historical periods. The fastest check is a three-facility matched package of contemporaneous forecasts, rate/minimum modifications, invoices and alternative-capacity cost estimates.

## Database and artifact disposition

- New verified synthesis finding: **#13032**, `claim_type=synthesis`, `confidence=medium`, thread 110.
- New ACH assessments: #13032 → #335 `neutral`; #13032 → #336 `consistent`; assessor `agent:systemic-analysis:run-122`.
- New hypotheses, leads, tags or connections: **0**.
- Analysis runs: #122 and #123 completed.
- No external source query and no `auto_leads` run.

Companion artifacts: [facility-period matrix](./2026-07-14-tier2-detention-guarantee-utilization-wave11-facility-period-comparison-matrix.csv), [ACH](./2026-07-14-tier2-detention-guarantee-utilization-wave11-ach.json), [novelty decisions](./2026-07-14-tier2-detention-guarantee-utilization-wave11-novelty.json), [source/DB manifest](./2026-07-14-tier2-detention-guarantee-utilization-wave11-source-db-manifest.json), and checksum ledger.
"""
    REPORT.write_text(report, encoding="utf-8")

    runs = [dict(row) for row in db.execute("SELECT * FROM analysis_runs WHERE id IN (122,123) ORDER BY id")]
    assessments = [dict(row) for row in db.execute(
        "SELECT * FROM hypothesis_evidence_matrix WHERE finding_id=13032 AND hypothesis_id IN (335,336) ORDER BY hypothesis_id,id"
    )]
    manifest = {
        "generated_on": "2026-07-14", "profile_id": "geo-group", "thread_id": 110,
        "analysis_runs": runs, "hypotheses_reassessed": [335, 336], "new_finding": 13032,
        "finding_records": finding_rows, "new_assessments": assessments,
        "prior_runs_novelty_gate": [86, 94, 97, 116, 117, 118, 119, 120, 121],
        "excluded_retracted_rows": [12633, 12636, 12637, 12649],
        "source_files": SOURCE_FILES, "prior_artifacts": PRIOR_ARTIFACTS,
        "dependency_rules": [
            "13024-13027 collapsed into one shared IIDS/two-period group recorded as 13032",
            "South Texas, Tacoma, Golden State and Folkston each counted once per facility/OIG chain",
            "same-agency templates and same-period facility rows are not independent corroboration",
        ],
        "measure_separation": [
            "current reported minimum is not a funded invoice quantity",
            "ADP is not billed bed-days", "historical rates are not carried forward",
            "obligation, outlay, invoice, deduction and GEO revenue remain distinct",
        ],
        "database_integrity": {
            "quick_check": db.execute("PRAGMA quick_check").fetchone()[0],
            "foreign_key_check_rows": len(db.execute("PRAGMA foreign_key_check").fetchall()),
        },
        "no_external_queries": True, "auto_leads_run": False,
        "outputs": [str(path.relative_to(ROOT)) for path in (REPORT, MATRIX, ACH, NOVELTY, MANIFEST, SHA)],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    hash_paths = [ROOT / path for path in SOURCE_FILES + PRIOR_ARTIFACTS] + [REPORT, MATRIX, ACH, NOVELTY, MANIFEST]
    with SHA.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sha256", "bytes", "path"])
        writer.writeheader()
        for path in sorted(hash_paths):
            if not path.exists():
                raise RuntimeError(f"Missing hash target {path}")
            writer.writerow({"sha256": sha256(path), "bytes": path.stat().st_size, "path": str(path.relative_to(ROOT))})

    print(json.dumps({
        "matrix_rows": len(ROWS), "finding_records": len(finding_rows), "assessments": len(assessments),
        "competition": competition, "outputs": manifest["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
