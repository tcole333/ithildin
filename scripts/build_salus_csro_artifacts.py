#!/usr/bin/env python3
"""Build reproducible Salus CSRO matrices and a hashed primary-source manifest.

This script is intentionally scoped to GEO Group investigation lead 62736.  It
does not infer that Salus is related to GEO Group, and it keeps USAspending
award values, obligations, outlays, transaction changes, ceiling values, and
the court opinion's evaluated-price scenario in separate fields.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "investigations/geo-group/sources/2026-07-14-lead-62736"
DEFAULT_REPORT_DIR = ROOT / "investigations/geo-group/reports"
PREFIX = "2026-07-14-lead-62736-salus-csro"


def load(path: Path):
    return json.loads(path.read_text())


def money(value):
    if value is None or value == "":
        return ""
    return format(Decimal(str(value)), ".2f")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    """Use a stable repo-relative label when possible, otherwise an absolute path."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summary_row(label: str, record_kind: str, data: dict, source: str, note: str = "") -> dict:
    contract = data.get("latest_transaction_contract_data") or {}
    pop = data.get("period_of_performance") or {}
    recipient = data.get("recipient") or {}
    return {
        "record_kind": record_kind,
        "label": label,
        "instrument_or_mod": data.get("piid", ""),
        "parent_instrument": (data.get("parent_award") or {}).get("piid", ""),
        "action_date": data.get("date_signed", ""),
        "recipient_legal_name_as_reported": recipient.get("recipient_name", ""),
        "recipient_uei": recipient.get("recipient_uei", ""),
        "obligation_change": "",
        "cumulative_obligation": money(data.get("total_obligation")),
        "cumulative_outlay": money(data.get("total_outlay")),
        "base_and_exercised_options_value": money(data.get("base_exercised_options")),
        "base_and_all_options_or_ceiling_value": money(data.get("base_and_all_options")),
        "evaluated_price_scenario": "",
        "performance_start": pop.get("start_date", ""),
        "current_performance_end": pop.get("end_date", ""),
        "offers_reported": contract.get("number_of_offers_received", ""),
        "competition_reported": contract.get("extent_competed_description", ""),
        "action_or_scope_description": data.get("description", ""),
        "source_file": source,
        "limitation_or_note": note,
    }


def transaction_rows(label: str, instrument: str, parent: str, data: dict, source: str) -> list[dict]:
    rows = []
    cumulative = Decimal("0")
    for item in sorted(data["results"], key=lambda x: (x.get("action_date", ""), x.get("modification_number", ""))):
        change = Decimal(str(item.get("federal_action_obligation") or 0))
        cumulative += change
        rows.append({
            "record_kind": "transaction_action",
            "label": label,
            "instrument_or_mod": f"{instrument}/{item.get('modification_number', '')}",
            "parent_instrument": parent,
            "action_date": item.get("action_date", ""),
            "recipient_legal_name_as_reported": "SALUS WORLDWIDE SOLUTIONS CORP.",
            "recipient_uei": "EA4VD72SB1W3",
            "obligation_change": money(change),
            "cumulative_obligation": money(cumulative),
            "cumulative_outlay": "",
            "base_and_exercised_options_value": "",
            "base_and_all_options_or_ceiling_value": "",
            "evaluated_price_scenario": "",
            "performance_start": "",
            "current_performance_end": "",
            "offers_reported": "",
            "competition_reported": item.get("action_type_description", ""),
            "action_or_scope_description": item.get("description", ""),
            "source_file": source,
            "limitation_or_note": "Transaction change; not an invoice, payment, profit, or stand-alone award value.",
        })
    return rows


def build_money_matrix(source_dir: Path, report_dir: Path) -> Path:
    usa = source_dir / "usaspending"
    parent = load(usa / "usa-csro-parent-detail.json")
    order18 = load(usa / "usa-csro-award-detail.json")
    order37 = load(usa / "usa-csro-order-0037-detail.json")
    ice = load(usa / "usa-salus-ice-70CDCR26P00000010-detail.json")
    care = load(usa / "usaspending-care-salus-subaward-search.json")["results"][0]

    rows = [
        summary_row(
            "CSRO single-award IDIQ",
            "instrument_summary",
            parent,
            "usaspending/usa-csro-parent-detail.json",
            "The $915 million figure is the IDIQ base-and-all-options/maximum value, not obligations or outlays. USAspending's latest solicitation field conflicts with the court record.",
        ),
        summary_row(
            "CSRO task order 1",
            "instrument_summary",
            order18,
            "usaspending/usa-csro-award-detail.json",
            "Award-level obligations, outlays, exercised value, and potential value are separate USAspending metrics as of the retrieval snapshot.",
        ),
        summary_row(
            "Secure commercial aviation platform order",
            "instrument_summary",
            order37,
            "usaspending/usa-csro-order-0037-detail.json",
            "Outlays slightly exceed obligations in the current reporting snapshot; do not infer an overpayment without transaction/account reconciliation.",
        ),
        {
            "record_kind": "derived_summary",
            "label": "Two identified CSRO child orders combined",
            "instrument_or_mod": "70RDA225FR0000018 + 70RDA225FR0000037",
            "parent_instrument": "70RDA225D00000005",
            "action_date": "",
            "recipient_legal_name_as_reported": "SALUS WORLDWIDE SOLUTIONS CORP.",
            "recipient_uei": "EA4VD72SB1W3",
            "obligation_change": "",
            "cumulative_obligation": money(Decimal(str(order18["total_obligation"])) + Decimal(str(order37["total_obligation"]))),
            "cumulative_outlay": money(Decimal(str(order18["total_outlay"])) + Decimal(str(order37["total_outlay"]))),
            "base_and_exercised_options_value": money(Decimal(str(order18["base_exercised_options"])) + Decimal(str(order37["base_exercised_options"]))),
            "base_and_all_options_or_ceiling_value": money(Decimal(str(order18["base_and_all_options"])) + Decimal(str(order37["base_and_all_options"]))),
            "evaluated_price_scenario": "",
            "performance_start": "",
            "current_performance_end": "",
            "offers_reported": "",
            "competition_reported": "",
            "action_or_scope_description": "Arithmetic sum of the two identified child-order award-level metrics.",
            "source_file": "usaspending/usa-csro-award-detail.json; usaspending/usa-csro-order-0037-detail.json",
            "limitation_or_note": "Excludes the IDIQ's own $250 minimum obligation and excludes the separate ICE aircraft-maintenance purchase order.",
        },
        {
            "record_kind": "evaluation_scenario",
            "label": "Salus total evaluated price",
            "instrument_or_mod": "RFP 70RDA225R0000008 (court record)",
            "parent_instrument": "70RDA225D00000005",
            "action_date": "2025-05-20",
            "recipient_legal_name_as_reported": "SALUS WORLDWIDE SOLUTIONS CORP.",
            "recipient_uei": "EA4VD72SB1W3",
            "obligation_change": "",
            "cumulative_obligation": "",
            "cumulative_outlay": "",
            "base_and_exercised_options_value": "",
            "base_and_all_options_or_ceiling_value": "",
            "evaluated_price_scenario": "1409688.00",
            "performance_start": "",
            "current_performance_end": "",
            "offers_reported": "4",
            "competition_reported": "Limited competition under FAR 6.302-2",
            "action_or_scope_description": "Court-reported total evaluated price used in the source-selection comparison.",
            "source_file": "courtlistener/gov.uscourts.uscfc.52685.70.0.pdf",
            "limitation_or_note": "Evaluation scenario only; not the ceiling, award value, obligation, outlay, payment, or revenue.",
        },
        summary_row(
            "Separate ICE aircraft-maintenance purchase order",
            "peripheral_instrument_summary",
            ice,
            "usaspending/usa-salus-ice-70CDCR26P00000010-detail.json",
            "Separate ICE purchase order; excluded from every CSRO total. USAspending reports one offer, only-one-source procedures, no competition, and urgency authority.",
        ),
        {
            "record_kind": "antecedent_subaward_summary",
            "label": "Afghan CARE antecedent subaward",
            "instrument_or_mod": care["Sub-Award ID"],
            "parent_instrument": care["Prime Award ID"],
            "action_date": care["Sub-Award Date"],
            "recipient_legal_name_as_reported": care["Sub-Awardee Name"],
            "recipient_uei": "",
            "obligation_change": "",
            "cumulative_obligation": money(care["Sub-Award Amount"]),
            "cumulative_outlay": "",
            "base_and_exercised_options_value": "",
            "base_and_all_options_or_ceiling_value": "",
            "evaluated_price_scenario": "",
            "performance_start": "",
            "current_performance_end": "",
            "offers_reported": "",
            "competition_reported": "",
            "action_or_scope_description": care["Sub-Award Description"],
            "source_file": "usaspending/usaspending-care-salus-subaward-search.json",
            "limitation_or_note": "USAspending reports LLC, while the CSRO awardee is Corp.; the public records reviewed do not resolve that legal-entity relationship. Do not collapse them without a primary bridge.",
        },
    ]

    rows.extend(transaction_rows("CSRO IDIQ action", parent["piid"], "", load(usa / "usaspending-csro-idv-transactions.json"), "usaspending/usaspending-csro-idv-transactions.json"))
    rows.extend(transaction_rows("CSRO task order 1 action", order18["piid"], parent["piid"], load(usa / "usaspending-csro-order18-transactions.json"), "usaspending/usaspending-csro-order18-transactions.json"))
    rows.extend(transaction_rows("Commercial aviation order action", order37["piid"], parent["piid"], load(usa / "usaspending-csro-order37-transactions.json"), "usaspending/usaspending-csro-order37-transactions.json"))

    fields = list(rows[0])
    output = report_dir / f"{PREFIX}-money-vehicle-matrix.csv"
    write_csv(output, rows, fields)
    return output


def build_timeline(report_dir: Path) -> Path:
    rows = [
        ("2025-01-20", "policy", "President issued Executive Orders 14159 and 14165.", "Court-reported background; temporal sequence alone does not prove influence or favoritism."),
        ("2025-01-23", "unsolicited proposal", "Salus submitted its initial unsolicited CSRO proposal to DHS.", "Court finding from administrative record; three days after the executive orders."),
        ("2025-02-10", "unsolicited proposal", "Salus resubmitted its proposal; USAspending separately reports a $112.888 million CARE subaward to a Salus LLC on this date.", "Same-date events; no causal inference. LLC/Corp relationship unresolved."),
        ("2025-02-18", "agency review", "DHS acknowledged the unsolicited proposal.", "Court finding."),
        ("2025-02-22", "agency review", "PLCY completed a favorable initial review.", "Court finding."),
        ("2025-02-24", "agency review", "DHS accepted the proposal for comprehensive evaluation.", "Court finding."),
        ("2025-03-07", "agency review", "DHS completed a favorable comprehensive evaluation.", "Court finding."),
        ("2025-04-04", "scope development", "DHS separated voluntary returns and involuntary removals; Salus proposed a concept covering 276,000 movements and three international staging areas.", "Court finding; proposal volume was a plan, not achieved output."),
        ("2025-04-17", "scope development", "Last precompetition Salus white paper identified in the court's chronology.", "Court finding."),
        ("2025-04-18", "OCI review", "An inadvertent DHS email disclosure prompted contracting-officer and counsel review of potential organizational conflicts.", "Court finding; waiver later acknowledged appearances, not an adjudicated actual conflict."),
        ("2025-05-13", "market engagement", "Six vendors joined the industry meeting; DHS circulated a draft SOW/pricing schedule to those firms and a seventh firm.", "Court finding."),
        ("2025-05-14", "market engagement", "DHS held a presolicitation conference and one-on-one/question activity.", "Court finding."),
        ("2025-05-15", "solicitation", "DHS distributed RFP 70RDA225R0000008 to seven potential offerors under an urgency J&A.", "Court record number conflicts with USAspending latest field 70RDA225R00000018."),
        ("2025-05-18", "OCI waiver", "The contracting officer executed and the HCA approved an OCI waiver.", "Agency procurement judgment; not proof that no conflict existed."),
        ("2025-05-19", "proposals and GAO", "Four timely proposals were submitted; CSI filed a pre-award GAO protest around 9 a.m.", "Court finding."),
        ("2025-05-20", "award and stay override", "DHS overrode the CICA stay and awarded the IDIQ to Salus; parent minimum obligation was $250.", "CSI did not challenge the override in the COFC case."),
        ("2025-05-22", "task order", "DHS issued task order 70RDA225FR0000018 with an initial $30 million obligation.", "USAspending transaction record; instrument date differs from the IDIQ award date."),
        ("2025-07-21", "GAO ADR", "GAO conducted outcome-predictive ADR.", "The expected-denial account is attributed by the court to CSI; there was no GAO merits decision."),
        ("2025-08-06", "GAO disposition", "GAO confirmed CSI's withdrawal of the protest.", "Withdrawal, not a merits ruling."),
        ("2025-08-11", "COFC filing", "CSI filed No. 25-1338C in the Court of Federal Claims.", "Public docket."),
        ("2026-02-05", "replacement notice", "DHS posted a CSRO presolicitation notice, then removed it the following day.", "Public RECAP exhibit; replacement procurement was not completed in this record."),
        ("2026-05-05", "COFC judgment", "Judgment dismissed CSI's complaint.", "Threshold and alternative grounds must be stated separately."),
        ("2026-05-12", "reported opinion", "The court publicly filed its 66-page reported opinion.", "The opinion was first issued under seal on May 4."),
        ("2026-05-22", "task-order modification", "P00022 added $200 million, bringing task-order obligations to $697.707 million.", "USAspending transaction sum; not a payment or revenue figure."),
        ("2026-05-27", "separate ICE award", "ICE signed purchase order 70CDCR26P00000010 for aircraft-maintenance operational support.", "Separate $4.317 million instrument; excluded from CSRO totals."),
        ("2026-07-14", "appeal check", "Exact-party CourtListener search found no Federal Circuit appeal.", "Bounded database search as of this date; not proof that no filing exists elsewhere or later."),
    ]
    output = report_dir / f"{PREFIX}-protest-case-timeline.csv"
    write_csv(output, [dict(zip(("date", "event_class", "event", "evidentiary_limit"), row)) for row in rows], ["date", "event_class", "event", "evidentiary_limit"])
    return output


def build_evidence_matrix(report_dir: Path) -> Path:
    rows = [
        {
            "issue": "Solicitation identifier",
            "record_or_claim": "Reported opinion and public pleadings identify 70RDA225R0000008; USAspending latest IDIQ field reports 70RDA225R00000018.",
            "speaker_or_source_class": "court record + federal spending system",
            "disposition": "unresolved conflict",
            "source": "CourtListener ECF 70; USAspending IDIQ detail",
            "limitation": "No signed public RFP was recovered; neither number should silently replace the other.",
        },
        {
            "issue": "Competition",
            "record_or_claim": "DHS sent the RFP to seven potential offerors and received four timely proposals.",
            "speaker_or_source_class": "court factual chronology from administrative record",
            "disposition": "established in reported opinion",
            "source": "CourtListener ECF 70 pp. 20, 23",
            "limitation": "Potential offeror names remain redacted; limited competition was justified under FAR 6.302-2.",
        },
        {
            "issue": "Source selection",
            "record_or_claim": "Salus alone received high confidence for technical approach and had the lowest $1,409,688 evaluated price.",
            "speaker_or_source_class": "court factual chronology from administrative record",
            "disposition": "established in reported opinion",
            "source": "CourtListener ECF 70 p. 23",
            "limitation": "The evaluated price is a comparison scenario, not the $915 million ceiling, obligation, outlay, payment, or revenue.",
        },
        {
            "issue": "OCI waiver",
            "record_or_claim": "The HCA acknowledged appearances of biased ground rules, unequal information, and impropriety, then approved a waiver based on urgency and mitigation.",
            "speaker_or_source_class": "agency determination quoted in court opinion",
            "disposition": "documented procurement judgment",
            "source": "CourtListener ECF 70 pp. 21-22",
            "limitation": "The waiver is not proof that an actual conflict did or did not exist.",
        },
        {
            "issue": "GAO protest",
            "record_or_claim": "CSI withdrew after outcome-predictive ADR; GAO issued no merits decision.",
            "speaker_or_source_class": "court chronology; expected-denial account attributed to CSI",
            "disposition": "withdrawn",
            "source": "CourtListener ECF 70 pp. 24-25",
            "limitation": "Do not describe the withdrawal as a GAO holding or merits denial.",
        },
        {
            "issue": "Article III standing",
            "record_or_claim": "The court dismissed under RCFC 12(h)(3) for lack of Article III standing.",
            "speaker_or_source_class": "court holding",
            "disposition": "primary ground",
            "source": "CourtListener ECF 70 pp. 65-66; ECF 68",
            "limitation": "Threshold disposition; distinct from statutory standing and alternative merits-prejudice analysis.",
        },
        {
            "issue": "Statutory standing",
            "record_or_claim": "Alternatively, the court granted Salus's RCFC 12(b)(6) motion for lack of statutory standing.",
            "speaker_or_source_class": "court holding",
            "disposition": "alternative ground",
            "source": "CourtListener ECF 70 p. 66",
            "limitation": "Distinct from Article III standing and the further alternative cross-MJAR disposition.",
        },
        {
            "issue": "Interested party and prejudice",
            "record_or_claim": "Alternatively, the court granted the government and Salus cross-MJARs because CSI failed to prove interested-party status and prejudice.",
            "speaker_or_source_class": "court holding",
            "disposition": "alternative merits ground",
            "source": "CourtListener ECF 70 p. 66",
            "limitation": "This was not a general merits adjudication of every procurement criticism.",
        },
        {
            "issue": "Bad faith/unfair dealings",
            "record_or_claim": "The court stated its review of the administrative record yielded no evidence of bad faith or unfair dealings.",
            "speaker_or_source_class": "court observation while denying judicial notice",
            "disposition": "record-bounded observation",
            "source": "CourtListener ECF 70 pp. 65-66",
            "limitation": "The court said CSI had not expressly pleaded those claims and limited these merits-related conclusions to the judicial-notice request.",
        },
        {
            "issue": "Option-period documentation",
            "record_or_claim": "The court said the CO may have misinterpreted FAR 6.302-2 and contemporaneous support for two option years appeared minimal.",
            "speaker_or_source_class": "court footnote",
            "disposition": "possible error not reached",
            "source": "CourtListener ECF 70 p. 19 n.16",
            "limitation": "CSI did not identify the possible error and the court did not decide it because of standing/prejudice conclusions.",
        },
        {
            "issue": "Public structured subawards",
            "record_or_claim": "Correct USAspending advanced and parent-award subaward queries returned zero CSRO rows.",
            "speaker_or_source_class": "federal structured reporting result",
            "disposition": "negative search result",
            "source": "USAspending advanced CSRO subaward export",
            "limitation": "Reporting absence is not proof that Salus used no subcontractors, CTAs, vendors, or affiliates.",
        },
        {
            "issue": "Afghan CARE antecedent",
            "record_or_claim": "The court says Salus performed as a CARE subcontractor; USAspending reports a $112,888,125 subaward to SALUS WORLDWIDE SOLUTIONS LLC under Xator task order 19AQMM23F0766.",
            "speaker_or_source_class": "court record + federal structured subaward",
            "disposition": "antecedent experience documented; entity resolution open",
            "source": "CourtListener ECF 70 pp. 13-14; USAspending PO-0018454",
            "limitation": "CSRO awardee is Corp. with UEI EA4VD72SB1W3; no primary record reviewed links the reported LLC and Corp. legal forms.",
        },
        {
            "issue": "Trump-administration relationship",
            "record_or_claim": "Public court and procurement records establish fast policy-to-proposal chronology but no verified pre-award political-appointee, donation, investment, or favor bridge.",
            "speaker_or_source_class": "multi-source synthesis",
            "disposition": "not established in reviewed public record",
            "source": "CourtListener record; SAM extract; exact FEC searches; USAspending",
            "limitation": "Absence is bounded to reviewed names, systems, public filings, and the public/redacted record; sealed/protected material and unidentified intermediaries remain outside it.",
        },
        {
            "issue": "GEO Group relationship",
            "record_or_claim": "No operational, ownership, subcontract, investment, donation, or procurement relationship between Salus and GEO was identified in the reviewed public record.",
            "speaker_or_source_class": "multi-source negative-result synthesis",
            "disposition": "not established in reviewed public record",
            "source": "Public COFC/RECAP set; Salus corporate disclosure; SAM extract; USAspending CSRO subaward search; exact EDGAR-oriented search",
            "limitation": "Not proof of no relationship. Congressional exhibits mention GEO as a separate comparator/contractor, not as a demonstrated Salus partner.",
        },
        {
            "issue": "Later direct ICE relationship",
            "record_or_claim": "ICE awarded Salus a separate $4,317,331.04 aircraft-maintenance purchase order in May 2026.",
            "speaker_or_source_class": "federal spending system",
            "disposition": "separate verified instrument",
            "source": "USAspending 70CDCR26P00000010",
            "limitation": "Excluded from CSRO totals; one-off award reporting does not establish political influence.",
        },
    ]
    output = report_dir / f"{PREFIX}-evidence-matrix.csv"
    write_csv(output, rows, list(rows[0]))
    return output


def source_metadata(relative: str) -> tuple[str, str, str]:
    name = Path(relative).name
    if relative.startswith("courtlistener/"):
        if name.startswith("gov.uscourts"):
            match = re.search(r"\.52685\.(\d+)(?:\.(\d+))?", name)
            if match:
                doc = match.group(1)
                attachment = match.group(2)
                segment = f"{doc}/{attachment}/" if attachment and attachment != "0" else f"{doc}/"
                return "primary_court", f"https://www.courtlistener.com/docket/71090317/{segment}csi-aviation-inc-v-united-states/", "Public RECAP filing; .txt and .ocr derivatives are local extraction aids for the corresponding PDF."
        return "primary_court_index", "https://www.courtlistener.com/docket/71090317/csi-aviation-inc-v-united-states/", "CourtListener search/docket metadata or bounded appeal search."
    if relative.startswith("usaspending/"):
        if "70CDCR26P00000010" in name:
            return "primary_government_spending", "https://www.usaspending.gov/award/CONT_AWD_70CDCR26P00000010_7012_-NONE-_-NONE-", "Official USAspending award/API snapshot."
        if "care" in name.lower() or "19AQMM23F0766" in name:
            return "primary_government_spending", "https://www.usaspending.gov/award/CONT_AWD_19AQMM23F0766_1900_19AQMM19D0119_1900", "Official USAspending award/subaward/API snapshot."
        if "parent" in name or "idv" in name:
            return "primary_government_spending", "https://www.usaspending.gov/award/CONT_IDV_70RDA225D00000005_7001", "Official USAspending award/API snapshot."
        if "0037" in name or "order37" in name:
            return "primary_government_spending", "https://www.usaspending.gov/award/CONT_AWD_70RDA225FR0000037_7001_70RDA225D00000005_7001", "Official USAspending award/API snapshot."
        return "primary_government_spending", "https://www.usaspending.gov/award/CONT_AWD_70RDA225FR0000018_7001_70RDA225D00000005_7001", "Official USAspending award/API snapshot."
    if relative.startswith("sam/"):
        return "primary_government_entity_extract", "https://sam.gov/data-services/Entity%20Management/Public%20V2?privacy=Public", "Local query result from the March 2026 SAM Public Entity Management extract; no secret/API key included."
    if relative.startswith("fec/"):
        return "primary_government_campaign_finance_search", "https://api.open.fec.gov/developers/", "Bounded exact-name/employer FEC API result; zero results are not universal negatives."
    if relative.startswith("sec/"):
        return "primary_government_filing_search", "https://efts.sec.gov/LATEST/search-index", "Bounded EDGAR full-text orientation search; search behavior is broader than an exact-phrase assertion."
    return "other", "", ""


def build_manifest(source_dir: Path, report_dir: Path, artifacts: list[Path]) -> Path:
    sources = []
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        relative = str(path.relative_to(source_dir))
        source_class, url, note = source_metadata(relative)
        sources.append({
            "path": relative,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "source_class": source_class,
            "source_url": url,
            "retrieved_or_archived_date": "2026-07-14",
            "note": note,
        })

    payload = {
        "profile": "geo-group",
        "lead_id": 62736,
        "scope": "Salus CSRO procurement, protest/litigation, antecedent experience, and bounded GEO/political-link checks",
        "generated_date": "2026-07-14",
        "source_root": display_path(source_dir),
        "source_count": len(sources),
        "sources": sources,
        "generated_artifacts": [
            {
                "path": display_path(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifacts
        ],
        "metric_guardrails": [
            "IDIQ ceiling/base-and-all-options is not an obligation, outlay, payment, profit, or revenue.",
            "Award obligations and outlays are separate federal reporting metrics.",
            "Transaction obligation changes are not invoices or payments.",
            "The court-reported $1,409,688 evaluated price is a source-selection scenario, not an award value.",
            "The separate ICE purchase order and CARE antecedent subaward are excluded from CSRO totals.",
        ],
        "negative_result_guardrail": "No-GEO/no-political-bridge statements are bounded to the reviewed public, redacted, and structured records and are not proof of nonexistence.",
    }
    output = report_dir / f"{PREFIX}-source-manifest.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    args.source_dir = args.source_dir.resolve()
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    money_path = build_money_matrix(args.source_dir, args.report_dir)
    timeline_path = build_timeline(args.report_dir)
    evidence_path = build_evidence_matrix(args.report_dir)
    manifest_path = build_manifest(args.source_dir, args.report_dir, [money_path, timeline_path, evidence_path])
    print(json.dumps({
        "money_matrix": str(money_path),
        "timeline": str(timeline_path),
        "evidence_matrix": str(evidence_path),
        "manifest": str(manifest_path),
    }, indent=2))


if __name__ == "__main__":
    main()
