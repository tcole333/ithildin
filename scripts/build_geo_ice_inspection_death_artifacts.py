#!/usr/bin/env python3
"""Build lead 61953 quote-level inspection/death-review coverage artifacts.

Input is the downloaded/extracted source-denominator manifest created by
``extract_geo_ice_source_denominator.py``. The output deliberately separates an
inspection's overall rating from its component deficiencies and treats a death
report's facility mention as a timeline linkage unless the source itself makes
a standards or causation finding.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


COLUMNS = [
    "record_id", "record_type", "canonical_facility", "subject_name",
    "event_or_death_date", "source_label", "inspection_or_review_type",
    "grade_or_compliance_outcome", "standards_version", "meets_standard_count",
    "does_not_meet_count", "not_applicable_count", "deficient_component_count",
    "deficient_standard_count", "deficient_standards_or_review_deficiencies",
    "repeat_issue_language", "agency_or_facility_response",
    "ucap_or_corrective_action_language", "transfer_or_custody_timeline",
    "death_location", "medical_or_custody_conclusion", "standards_deficiency",
    "causation_caveat", "control_class", "award_period_label", "artifact_count",
    "source_urls", "source_hashes", "evidence_quotes", "review_status",
    "scope_note", "routed_payment_or_remedy_language",
]


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "thirty-two": 32, "thirty-eight": 38, "thirty-nine": 39,
    "forty-one": 41, "forty-two": 42, "forty-three": 43,
}


FACILITY_AWARD_PERIODS = {
    "LaSalle ICE Processing Center": "Historical GEO-operated ICE procurement period; award ID not supported by the reviewed direct-prime ledger",
    "Folkston ICE Processing Center": "Charlton County IGSA pass-through, EROIGSA-17-0002",
    "Karnes County Residential Center": "Historical Karnes County/ICE family-residential arrangement; do not merge with current Karnes IPC award 70CDCR24DIG000018",
    "South Louisiana ICE Processing Center": "Evangeline Parish IGSA pass-through, EROIGSA-15-0006",
    "Pine Prairie ICE Processing Center": "Evangeline Parish IGSA pass-through, EROIGSA-15-0006",
    "Joe Corley Processing Center": "Montgomery County IGSA pass-through, 70CDCR18DIG000013",
    "Moshannon Valley Processing Center": "Clearfield County IGSA pass-through, 70CDCR21DIG000012",
    "Rio Grande Processing Center": "Direct ICE agreement/BPA HSCEDM14A00001",
}


DEATH_LOCATIONS = {
    "death-001": "Victor Valley Global Medical Center, after transfer from Adelanto",
    "death-002": "Unnamed local hospital, after the hanging at Northwest",
    "death-003": "Memorial Hermann Northeast Hospital, after transfer from Montgomery",
    "death-004": "Piedmont Columbus Regional Midtown Hospital, after earlier transfer from Folkston to Stewart",
    "death-005": "Paradise Valley Hospital, after transfer from Adelanto",
    "death-006": "Mesa Verde ICE Processing Facility; EMS pronounced death at the facility",
    "death-007": "Kendall Regional Medical Center, after transfers away from Broward",
    "death-008": "Conroe Regional Medical Center, after transfer from Joe Corley",
    "death-009": "University of Colorado Hospital, after transfer from Denver CDF",
    "death-010": "Moshannon Valley Processing Center; resuscitation ceased at the facility",
    "death-011": "Northwest ICE Processing Center; EMS ceased resuscitation at the facility",
    "death-012": "Southeast Georgia Health System emergency room, after transfer from Folkston",
    "death-013": "Conroe Regional Hospital, after transfer from Joe Corley",
    "death-014": "Broward Transitional Center; EMS declared death at the facility",
    "death-015": "Moshannon Valley Processing Center; county coroner pronounced death at the facility",
    "death-016": "Victor Valley Global Medical Center, after transfer from Adelanto",
    "death-017": "Victor Valley Global Medical Center, after transfer from Adelanto",
    "death-018": "Methodist Metropolitan Hospital, after detention at Denver and later South Texas",
    "death-019": "The Hospitals of Providence East Campus in El Paso, after transfers away from Broward",
    "death-020": "Valley Baptist Medical Center, after cardiac arrest at Treasure Hills Healthcare and Rehabilitation; Montgomery was earlier custody",
    "death-021": "Moshannon Valley Processing Center; resuscitation occurred at the facility",
    "death-022": "Conroe Regional Medical Center, after Montgomery-to-Joe Corley transfer",
    "death-023": "Victor Valley Global Medical Center, after transfer from Adelanto",
    "death-024": "Victor Valley Global Medical Center, after transfer from Adelanto",
}


DEATH_CONCLUSIONS = {
    "death-001": "The State of California’s Certificate of Death, issued June 1, 2017, documented the cause of GONZALEZ’s death as hypoxic encephalopathy1 and hanging, and his manner of death as suicide.",
    "death-002": "On February 28, 2019, the State of Washington Department of Health issued Mr. AMAR’s death certificate and documented Mr. AMAR’s cause of death as anoxic encephalopathy due to hanging.",
    "death-003": "On September 4, 2019, the Assistant Medical Examiner from the Harris County Institute of Forensic Sciences stated the cause of death was sudden cardiac death associated with biventricular cardiac dilation, and the manner of death was natural. Findings of the accompanying Toxicology Report, dated September 4, 2019, were determined to be noncontributory to the death.",
    "death-004": "On January 28, 2020, the Georgia Department of Public Health issued Mr. ARRIAGO’s death certificate and documented his cause of death as valvular heart disease with cardiomegaly and hepatic cirrhosis.",
    "death-005": "The preliminary cause of death is complications due to COVID-19.",
    "death-006": "EMS personnel pronounced Mr. AHN dead at 9:52 p.m.; the report separately states that an autopsy is pending.",
    "death-007": "The Miami-Dade County Medical Examiner Department concluded Mr. LEE died a natural death caused by hypertensive left thalamic hemorrhage.",
    "death-008": "The cause of death and manner was due to complications of COVID-19 virus infection and natural, respectively.",
    "death-009": "At 12:32 p.m., a UCH physician declared Mr. MENDOZA deceased.",
    "death-010": "The final autopsy report revealed Mr. OKPU’s cause of death was MDMA (ecstasy) toxicity with the following other significant conditions: atherosclerotic coronary artery disease (narrowing of the arteries that deliver blood to the heart), mild cardiomegaly (heart enlargement), and diminutive (severe narrowing) right coronary artery. The coroner determined the manner of death was accidental.",
    "death-011": "At approximately 11:35 a.m., EMS personnel stopped all resuscitative efforts due to unsuccessful attempts to resuscitate Mr. DANIEL.",
    "death-012": "At 2:31 a.m., the attending emergency room physician declared Mr. SINGH deceased.",
    "death-013": "At: 5:15 p.m. a physician pronounced Mr. FARIAS-Farias’s death caused by advanced infectious diseases.",
    "death-014": "At approximately 9:03 p.m., the EMS personnel’s supervising physician instructed them to cease all life-saving measures and declared Ms. BLAISE deceased.",
    "death-015": "Approximately 6:03 a.m., EMS stopped live saving measures after the Clearfield County, PA Coroner pronounced Mr. GE deceased.",
    "death-016": "At 2:32 a.m., a physician pronounced Mr. AYALA Uribe deceased.",
    "death-017": "At 7:45 p.m., a physician pronounced Mr. GARCIA Aviles deceased.",
    "death-018": "At approximately 1:25 p.m., MMH staff informed ERO San Antonio of Mr. WONG’s official time of death was 1:14 p.m.",
    "death-019": "On the same date, Mr. GASPAR-Andres’ autopsy report noted his cause of death as complications of alcoholic hepatic cirrhosis and cardiac hypertrophy (increased size of the heart).",
    "death-020": "Mr. MONTEJO was pronounced deceased at approximately 2:20 p.m.",
    "death-021": "Despite extensive efforts, he was pronounced deceased at approximately 3:21 a.m. on December 14, 2025.",
    "death-022": "On January 5, he experienced three episodes of cardiac arrest and was pronounced deceased at 4:31 a.m.",
    "death-023": "At 12:57 a.m., hospital staff pronounced Mr. GUTIERREZ Reyes deceased.",
    "death-024": "At 6:29 p.m., the emergency room physician pronounced Mr. RAMOS Solano deceased.",
}


ALIASES = {
    "Adelanto ICE Processing Center": ["Adelanto ICE Processing Center", "AIPC", "APC", "ADF"],
    "Northwest ICE Processing Center": ["Northwest ICE Processing Center", "Northwest Detention Center", "NWIPC", "NWDC"],
    "Montgomery Processing Center": ["Montgomery Processing Center", "MPC"],
    "Folkston ICE Processing Center": ["Folkston ICE Processing Center", "Folkston Main ICE Processing Center", "FIPC", "FMIPC"],
    "Mesa Verde ICE Processing Center": ["Mesa Verde ICE Processing Facility", "Mesa Verde ICE Processing Center", "MVIPF", "MVIPC"],
    "Broward Transitional Center": ["Broward Transitional Center", "BTC"],
    "Joe Corley Processing Center": ["Joe Corley Processing Center", "JCPC"],
    "Denver Contract Detention Facility": ["Denver Contract Detention Facility", "DCDF"],
    "Moshannon Valley Processing Center": ["Moshannon Valley Processing Center", "MVPC"],
    "South Texas ICE Processing Center": ["South Texas ICE Processing Center", "STIPC"],
}


def normalized(text: str) -> str:
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def word_number(value: str) -> str:
    value = value.strip().lower().replace(" ", "-")
    if value.isdigit():
        return value
    return str(NUMBER_WORDS[value]) if value in NUMBER_WORDS else ""


def extract(pattern: str, text: str, flags: int = re.I) -> str:
    match = re.search(pattern, text, flags)
    return normalized(match.group(0)) if match else ""


def award_period(facility: str, date: str) -> str:
    if facility == "Adelanto ICE Processing Center":
        return "Historical City of Adelanto D-IGSA" if date < "2019-12-20" else "Direct ICE IDIQ 70CDCR20D00000009"
    if facility == "Denver Contract Detention Facility":
        return "Direct ICE IDIQ HSCEDM11D00003 (historical inspection period)"
    if facility == "Mesa Verde ICE Processing Center":
        if date < "2019-03-06":
            return "Historical City of McFarland IGSA period; direct-prime award ID not supported by the reviewed ledger"
        if date < "2020-09-10":
            return "Direct ICE IDIQ 70CDCR19D00000004"
        return "Direct ICE IDIQ 70CDCR20D00000008"
    if facility == "Golden State Annex":
        return "Direct ICE IDIQ 70CDCR20D00000008"
    if facility == "Northwest ICE Processing Center":
        return "Direct ICE IDIQ HSCEDM15D00015"
    if facility == "Montgomery Processing Center":
        return "Direct ICE IDIQ HSCEDM17D00009"
    if facility == "Broward Transitional Center":
        return "Direct ICE IDIQ HSCEDM15D00006" if date <= "2021-10-21" else "Direct ICE IDIQ 70CDCR21D00000004"
    if facility == "South Texas ICE Processing Center":
        if date < "2020-09-01":
            return "Direct ICE IDIQ 70CDCR20D00000003"
        return "Direct ICE IDIQ 70CDCR20D00000012"
    return FACILITY_AWARD_PERIODS.get(facility, "Award period not normalized in reviewed direct-prime and IGSA records")


def standards_version(text: str) -> str:
    for pattern, label in (
        (r"NDS\s*2019", "NDS 2019"),
        (r"PBNDS\s*2008", "PBNDS 2008"),
        (r"PBNDS\s*2011(?:/2016 Revisions)?", "PBNDS 2011"),
        (r"Family Residential Standards", "Family Residential Standards"),
    ):
        if re.search(pattern, text, re.I):
            return label
    return ""


def inspection_row(event_id: str, associations: list[dict], source_map: dict[str, dict]) -> dict:
    primary = next((x for x in associations if x["artifact_label"] == "Cover Letter"), associations[0])
    texts = [Path(source_map[x["url"]]["local_text"]).read_text(errors="replace") for x in associations]
    text = normalized(texts[0])
    all_text = normalized("\n".join(texts))
    facility = primary["canonical_facility"]
    date = primary["inspection_date"]

    rating_match = re.search(
        r"recommends(?: that)? the facility receive a rating of\s+(.{1,80}?)(?:\.|,? unless| Providing that| The facility)",
        text,
        re.I,
    )
    rating = rating_match.group(1).strip() if rating_match else ""
    outcome_quote = extract(r"Recommended Rating and Justification\s+(.{1,900}?)(?=LCI Assurance Statement)", text)

    deficiency_quote = extract(
        r"(?:The inspection team (?:identified|found|did not identify)|No deficiencies were identified|There were no deficient components identified|No components were rated)\s+(.{0,1100}?)(?=Facility Snapshot|Facility Description|Areas of Concern|Recommended Rating)",
        text,
    )
    if not deficiency_quote:
        deficiency_quote = extract(r"The inspection team identified no deficient components during this inspection\.", text)

    control_class = ""
    response = ""
    corrective = "No UCAP language appears in the linked artifacts."
    rating_status_quote = ""

    if event_id == "inspection-025":
        rating = "Deep-dive recommendations; Issue(s) column: None"
        outcome_quote = extract(r"Inspection Topic\s+Finding\s+Issue\(s\)\s+Education\s+Recommendation\s+None\s+Child Development\s+Recommendation\s+None", text)
        control_class = "deep_dive_recommendations_no_issue"
    elif event_id in {"inspection-036", "inspection-037"}:
        rating = "Not Selected in SIS; conditional compliance after action-plan completion"
        outcome_quote = extract(r"If the facility completes the action plans.{0,500}?Performance-Based National Detention Standards\.", text)
        rating_status_quote = extract(r"Recommended Rating:\s+Not Selected", all_text)
        corrective = outcome_quote
        control_class = "conditional_preoccupancy_action_plans"
    elif event_id == "inspection-055":
        rating = "One area of noncompliance identified"
        outcome_quote = extract(r"The following area of noncompliance was identified:.{0,700}?current COVD protocols\.", text)
        deficiency_quote = outcome_quote
        corrective = extract(r"Mitigation:.{0,300}?current COVD protocols\.", text)
        control_class = "one_noncompliance_with_mitigation"
    elif re.search(r"There were no areas(?: of)? noncompliance", text, re.I):
        rating = "No areas of noncompliance identified"
        outcome_quote = extract(
            r"There were no areas(?: of)? noncompliance(?: identified)?"
            r"(?:(?: during| in) this (?:remote )?(?:monthly )?(?:onsite )?inspection)?\.",
            text,
        )
        control_class = "no_noncompliance_identified"
    elif rating:
        zero_components = bool(re.search(
            r"(?:zero|no)\s*(?:\(0\)\s*)?(?:deficient components|deficiencies)|"
            r"did not identify any deficiencies",
            deficiency_quote,
            re.I,
        ))
        ambiguous_component_status = bool(re.search(
            r"No components were rated Does Not Meet Standards",
            deficiency_quote,
            re.I,
        ))
        if zero_components:
            control_class = "compliant_grade_no_component_deficiencies"
        elif ambiguous_component_status:
            control_class = "compliant_grade_component_status_not_stated"
        elif deficiency_quote:
            control_class = "compliant_grade_with_component_deficiencies"
        else:
            control_class = "compliant_grade_component_status_not_stated"
    else:
        rating = "Outcome requires source-specific reading"
        control_class = "mixed_or_ungraded"

    component_count = ""
    component_match = re.search(
        r"(?:identified|found)\s+([a-z-]+|\d+)(?:\s+\((\d+)\))?\s+"
        r"(?:deficient components?|component deficiencies)",
        deficiency_quote,
        re.I,
    )
    if component_match:
        component_count = component_match.group(2) or (
            "0" if component_match.group(1).lower() == "no" else word_number(component_match.group(1))
        )
    elif re.search(
        r"identified (?:zero|no) deficient components|did not identify any deficiencies|"
        r"No deficiencies were identified|There were no deficient components",
        deficiency_quote,
        re.I,
    ):
        component_count = "0"
    elif event_id == "inspection-055":
        component_count = "1"

    standard_count = ""
    standard_match = re.search(
        r"following\s+([a-z-]+|\d+)(?:\s+\((\d+)\))?\s+standards?",
        deficiency_quote,
        re.I,
    )
    if standard_match:
        standard_count = standard_match.group(2) or word_number(standard_match.group(1))
    elif component_count == "1" and re.search(r"following (?:one \(1\) )?standard", deficiency_quote, re.I):
        standard_count = "1"
    elif component_count == "0":
        standard_count = "0"
    elif event_id == "inspection-055":
        standard_count = "1"

    meets = ""
    meet_match = re.search(r"All remaining\s+([a-z-]+|\d+)\s+standards?", outcome_quote, re.I)
    if meet_match:
        meets = word_number(meet_match.group(1))
    does_not_meet = "0" if re.search(r"No\s*\([0O]\)\s+standards?.{0,50}Does Not Meet", outcome_quote, re.I) else ("1" if event_id == "inspection-055" else "")
    not_applicable = ""
    na_match = re.search(r"(?:and\s+)?(?:one|two|three|\d+)\s*\((\d+)\)\s+standards? (?:were|was) Not Applicable", outcome_quote, re.I)
    if na_match:
        not_applicable = na_match.group(1)

    repeat = deficiency_quote if re.search(r"repeat deficien|Repeat Finding", deficiency_quote, re.I) else "None stated in extracted deficiency section."
    concern = extract(r"Areas of Concern/Significant Observations\s+(.{1,900}?)(?=Recommended Rating)", text)
    if concern and not re.search(r"There were no areas of concern", concern, re.I):
        response = concern
    elif concern:
        response = extract(r"There were no areas of concern(?: or significant observations)?(?: during this inspection)?\.", concern)

    for pattern in (
        r"Corrective action began promptly thereafter\.",
        r"each incident is reviewed and corrective action is implemented when warranted\.",
        r"Facility should ensure corrective action is documented.{0,300}?training procedures\.",
    ):
        quote = extract(pattern, text)
        if quote:
            corrective = quote

    quotes = [
        x for x in (
            rating_status_quote,
            outcome_quote,
            deficiency_quote,
            corrective if corrective != "No UCAP language appears in the linked artifacts." else "",
        ) if x
    ]
    return {
        "record_id": event_id,
        "record_type": "inspection_event",
        "canonical_facility": facility,
        "subject_name": "",
        "event_or_death_date": date,
        "source_label": primary["source_label"],
        "inspection_or_review_type": "Deep Dive Compliance Inspection" if event_id == "inspection-025" else ("pre-occupancy inspection" if event_id in {"inspection-036", "inspection-037"} else "ICE indexed compliance inspection"),
        "grade_or_compliance_outcome": rating,
        "standards_version": standards_version(text),
        "meets_standard_count": meets,
        "does_not_meet_count": does_not_meet,
        "not_applicable_count": not_applicable,
        "deficient_component_count": component_count,
        "deficient_standard_count": standard_count,
        "deficient_standards_or_review_deficiencies": deficiency_quote,
        "repeat_issue_language": repeat,
        "agency_or_facility_response": response or "No substantive agency/facility response stated in the linked artifacts; an outbrief is not treated as corrective closure.",
        "ucap_or_corrective_action_language": corrective,
        "transfer_or_custody_timeline": "",
        "death_location": "",
        "medical_or_custody_conclusion": "",
        "standards_deficiency": deficiency_quote,
        "causation_caveat": "Not a death review; no causation inference made from chronology or rating.",
        "control_class": control_class,
        "award_period_label": award_period(facility, date),
        "artifact_count": len(associations),
        "source_urls": " | ".join(x["url"] for x in associations),
        "source_hashes": " | ".join(source_map[x["url"]]["sha256"] for x in associations),
        "evidence_quotes": " || ".join(dict.fromkeys(quotes)),
        "review_status": "all linked artifacts downloaded, hash-checked, text-extracted/OCRed, and outcome fields quote-audited",
        "scope_note": "Overall grade and component deficiencies are independent fields; Meets Standards is not recoded as zero deficiencies.",
        "routed_payment_or_remedy_language": "No applied payment or award remedy stated; any direct remedy language belongs with completed lead 57784 or a nonduplicative follow-up.",
    }


def facility_timeline(text: str, facilities: str) -> tuple[str, list[str]]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    picked = []
    facility_terms = []
    for facility in [x.strip() for x in facilities.split("|")]:
        facility_terms.extend(ALIASES.get(facility, [facility]))
    route_pattern = re.compile(
        r"\b(?:detained|booked|housed|transferred|transported|arrived|admitted|"
        r"hospital|medical center|emergency room|pronounced|declared|died|death)\b",
        re.I,
    )
    for sentence in sentences:
        has_facility = any(
            re.search(rf"\b{re.escape(term)}\b", sentence, re.I)
            for term in facility_terms
        )
        if has_facility or route_pattern.search(sentence):
            candidate = normalized(sentence)
            if candidate not in picked:
                picked.append(candidate)
    picked = picked[:20]
    return " ".join(picked)[:5000], picked


def death_row(association: dict, source: dict) -> dict:
    event_id = association["event_id"]
    text = normalized(Path(source["local_text"]).read_text(errors="replace"))
    facilities = association["canonical_facility"]
    primary_facility = facilities.split("|")[0].strip()
    timeline, timeline_quotes = facility_timeline(text, facilities)
    conclusion = DEATH_CONCLUSIONS[event_id]
    deficiency_quotes = []
    corrective_quotes = []

    if event_id == "death-001":
        deficiency = (
            "Nine enumerated PBNDS 2011 deficiencies: Medical Care translation/language access; psychotropic-medication informed consent; medication-refusal counseling/documentation; Sexual Abuse and Assault Prevention and Intervention prompt/effective intervention; Special Management Units segregation order; Special Management Units status-review interview/documentation; Special Management Units 30-minute observation; Custody Classification System disciplinary-infraction scoring; Funds and Personal Property currency documentation."
        )
        causation = "Their inclusion in the report should not be construed in any way as indicating the deficiency contributed to the death of the detainee."
        corrective = "The review says the HSA initiated corrective actions before ERAU's review and that the Security Chief required 20-minute segregation rounds after the death."
        deficiency_quotes = [
            extract(r"ERAU reviewed the medical care GONZALEZ was provided by ADF,.{0,260}?ICE PBNDS 2011:", text),
            extract(r"1\. ICE PBNDS 2011, Medical Care, section \(V\)\(E\), Translation and Language Access for Detainees with Limited English Proficiency", text),
            extract(r"2\. ICE PBNDS 2011, Medical Care, section \(V\)\(X\)\(4\), Informed Consent and Involuntary Treatment", text),
            extract(r"3\. ICE PBNDS 2011, Medical Care, sections \(V\)\(X\)\(7\)\(9\) and \(10\), Informed Consent and Involuntary Treatment", text),
            extract(r"4\. ICE PBNDS 2011, Sexual Abuse and Assault Prevention and Intervention, section \(V\)\(H\), Prompt and Effective Intervention", text),
            extract(r"5\. ICE PBNDS 2011, Special Management Units, section \(V\)\(A\)\(2\), Administrative Segregation Order", text),
            extract(r"6\. ICE PBNDS 2011, Special Management Units, section \(V\)\(A\)\(3\)\(c\), Review of Detainee Status in Administrative Segregation", text),
            extract(r"7\. ICE PBNDS 2011, Special Management Units, section \(V\)\(L\)", text),
            extract(r"8\. ICE PBNDS 2011, Custody Classification System, Appendix 2\.2\.B, section \(2\)\(C\)\(7\), Number of Sustained Institutional Disciplinary Infractions", text),
            extract(r"9\. ICE PBNDS 2011, Funds and Personal Property, section \(V\)\(G\)\(1\)", text),
        ]
        corrective_quotes = [
            extract(r"proactively identified process failures by medical staff with regard to GONZALEZ’s care and initiated corrective actions in advance of ERAU’s review\.", text),
            extract(r"instituted a requirement that officers in segregation units complete security rounds every 20 minutes to help ensure those officers do not exceed the mandated 30-minute timeframe for those rounds\.", text),
        ]
        response = corrective
        control_class = "full_death_review_with_deficiencies_and_explicit_noncausation_caveat"
        grade = "Nine enumerated PBNDS deficiencies; not a facility-wide grade"
        standards = "PBNDS 2011"
    else:
        deficiency = "Not stated; this public Detainee Death Report is treated as a timeline/medical summary, not recoded as a detention-standards compliance adjudication."
        causation = "No explicit facility-causation conclusion stated; absence of a causation finding is not a finding of no causation."
        corrective = "No UCAP or detention-standards corrective-action conclusion stated in this public death summary."
        response = "No facility response or detention-standards compliance conclusion stated in this public death summary."
        control_class = "timeline_linkage_only_no_standards_adjudication"
        grade = "No detention-standards grade or compliance outcome stated"
        standards = ""

    award_labels = []
    for facility in [x.strip() for x in facilities.split("|")]:
        award_labels.append(f"{facility}: {award_period(facility, association['inspection_date'])}")
    conclusion_quotes = [conclusion]
    if event_id == "death-006":
        conclusion_quotes = [
            extract(r"Despite continued life saving measures, the EMS personnel efforts were unsuccessful, and the EMS personnel pronounced Mr\. AHN dead at 9:52 p\.m\.", text),
            extract(r"An autopsy is pending\.", text),
        ]
    quotes = [*timeline_quotes, *conclusion_quotes]
    if event_id == "death-001":
        quotes.extend([*deficiency_quotes, causation, *corrective_quotes])
    return {
        "record_id": event_id,
        "record_type": "death_review",
        "canonical_facility": facilities,
        "subject_name": association["source_label"],
        "event_or_death_date": association["inspection_date"],
        "source_label": "ICE Detainee Death Review" if event_id == "death-001" else "ICE Detainee Death Report",
        "inspection_or_review_type": "full External Reviews and Analysis Unit death review" if event_id == "death-001" else "public death timeline/medical summary",
        "grade_or_compliance_outcome": grade,
        "standards_version": standards,
        "meets_standard_count": "",
        "does_not_meet_count": "",
        "not_applicable_count": "",
        "deficient_component_count": "",
        "deficient_standard_count": "9" if event_id == "death-001" else "",
        "deficient_standards_or_review_deficiencies": deficiency,
        "repeat_issue_language": "Not characterized as repeat findings in the report.",
        "agency_or_facility_response": response,
        "ucap_or_corrective_action_language": corrective,
        "transfer_or_custody_timeline": timeline,
        "death_location": DEATH_LOCATIONS[event_id],
        "medical_or_custody_conclusion": conclusion,
        "standards_deficiency": deficiency,
        "causation_caveat": causation,
        "control_class": control_class,
        "award_period_label": " | ".join(award_labels),
        "artifact_count": 1,
        "source_urls": association["url"],
        "source_hashes": source["sha256"],
        "evidence_quotes": " || ".join(x for x in quotes if x),
        "review_status": "full PDF downloaded, hash-checked, text-extracted, and transfer/location/conclusion fields quote-audited",
        "scope_note": "A facility mention is a timeline linkage unless the report itself supplies a standards or causation conclusion; death location is kept separate from prior custody locations.",
        "routed_payment_or_remedy_language": "No payment or contract-remedy conclusion stated; none inferred.",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads(args.source_manifest.read_text())
    source_map = {x["url"]: x for x in source_manifest["sources"]}

    inspections = []
    inspection_ids = sorted({x["event_id"] for x in source_manifest["associations"] if x["association_type"] == "inspection"})
    for event_id in inspection_ids:
        associations = [x for x in source_manifest["associations"] if x["event_id"] == event_id]
        inspections.append(inspection_row(event_id, associations, source_map))
    deaths = [
        death_row(x, source_map[x["url"]])
        for x in source_manifest["associations"]
        if x["association_type"] == "death_review"
    ]
    rows = inspections + deaths

    coverage_path = args.output_dir / "2026-07-14-lead-61953-geo-ice-inspection-death-coverage.csv"
    write_csv(coverage_path, rows)
    source_files = [
        {
            "official_url": x["url"],
            "source_types": x["source_types"],
            "sha256": x["sha256"],
            "bytes": x["bytes"],
            "pages": x["pages"],
            "extraction_method": x["extraction_method"],
            "text_nonspace_chars": x["text_nonspace_chars"],
            "association_count": x["association_count"],
        }
        for x in source_manifest["sources"]
    ]
    manifest = {
        "profile": "geo-group",
        "lead_id": 61953,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Document-by-document quote extraction from the complete lead 57703 ICE inspection/death-review denominator, with Apple Vision OCR for image-only pages and period-aware award labels from the audited GEO/DHS contract ledger.",
        "coverage": {
            "inspection_events": len(inspections),
            "inspection_artifact_associations": source_manifest["inspection_associations"],
            "unique_inspection_pdfs": sum("inspection" in x["source_types"] for x in source_files),
            "unique_inspection_content_hashes": len({
                x["sha256"] for x in source_files if "inspection" in x["source_types"]
            }),
            "death_reviews": len(deaths),
            "unique_official_pdf_urls": len(source_files),
            "unique_content_hashes": len({x["sha256"] for x in source_files}),
            "successful_downloads": source_manifest["successful_downloads"],
            "failed_downloads": source_manifest["failed_downloads"],
            "ocr_documents": source_manifest["ocr_documents"],
        },
        "inspection_outcomes": dict(Counter(x["grade_or_compliance_outcome"] for x in inspections)),
        "inspection_control_classes": dict(Counter(x["control_class"] for x in inspections)),
        "death_control_classes": dict(Counter(x["control_class"] for x in deaths)),
        "separation_rules": [
            "overall inspection grades and component deficiencies are independent fields",
            "a Meets Standards recommendation is not recoded as zero deficient components",
            "zero standards rated Does Not Meet, or a statement that no component was rated Does Not Meet, is not recoded as zero deficient components unless the source explicitly says no deficient components/deficiencies",
            "inspection observations, OIG findings, adjudicated court findings, and death-review conclusions remain different evidence classes",
            "death location remains separate from prior custody and transfer locations",
            "the 23 current death summaries are not recoded as standards inspections",
            "no medical or custodial causation is inferred; explicit source caveats are preserved",
            "no financial consequence is inferred; applied remedy language routes to completed lead 57784 or a nonduplicative follow-up",
        ],
        "award_period_caveat": "Award labels are period-aware routing labels, not proof that a particular task order funded the inspected building or caused any inspection outcome. County/parish IGSAs and direct ICE IDIQs remain distinct.",
        "duplicate_content_note": "Two Karnes official inspection URLs (kcrcFIR_073019.pdf and kcrcFinalInspReport_07-30-2019.pdf) have the same SHA-256; both indexed event associations remain represented, while content-hash counts disclose the duplication.",
        "visual_qa": {
            "method": "Representative source pages rendered with Poppler and visually compared to extracted/OCR text.",
            "checked": [
                "Mesa Verde 2018 cover-letter p.2 (rating table/deficient components)",
                "Golden State 2020 cover-letter p.3 (conditional action-plan language)",
                "Karnes 2021-06 inspection p.2 (Personal Hygiene noncompliance/mitigation)",
                "Northwest 2022 cover-letter p.2 (rating table/deficient components/repeat)",
                "Gonzalez-Gadba review pp.1,18,23 (causation caveat, death location/cause, PBNDS review, corrective action)",
            ],
        },
        "source_files": source_files,
        "artifacts": [coverage_path.name, "2026-07-14-lead-61953-geo-ice-inspection-death-source-manifest.json"],
    }
    manifest_path = args.output_dir / "2026-07-14-lead-61953-geo-ice-inspection-death-source-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "coverage_rows": len(rows),
        "inspection_rows": len(inspections),
        "death_rows": len(deaths),
        "outputs": [str(coverage_path), str(manifest_path)],
    }, indent=2))


if __name__ == "__main__":
    main()
