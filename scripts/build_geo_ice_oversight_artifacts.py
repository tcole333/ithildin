#!/usr/bin/env python3
"""Build lead 57703 GEO/ICE oversight crosswalk artifacts from saved primary sources.

The script intentionally separates quote-reviewed findings from source-denominator
indexes.  A link in the inspection or death-review indexes is not itself a finding.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString
from dateutil import parser as date_parser


FACILITIES = {
    "Adelanto ICE Processing Center": {
        "patterns": ["adelanto ice processing center", "adelanto detention facility", "desert view annex"],
        "geo_role": "GEO operator; historical City of Adelanto D-IGSA and later direct ICE procurement periods must not be merged",
        "contract_channel": "direct ICE contract for current period; historical D-IGSA",
        "award_or_vehicle": "70CDCR20D00000009",
    },
    "Denver Contract Detention Facility": {
        "patterns": ["denver contract detention facility", "aurora ice processing center"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE contract",
        "award_or_vehicle": "HSCEDM11D00003 (historical); 70CDCR20D00000001 (newer period)",
    },
    "Folkston ICE Processing Center": {
        "patterns": ["folkston ice processing center", "folkston main ice processing center", "folkston processing center", "folkston annex"],
        "geo_role": "GEO downstream operator",
        "contract_channel": "Charlton County IGSA pass-through",
        "award_or_vehicle": "EROIGSA-17-0002",
    },
    "Golden State Annex": {
        "patterns": ["golden state annex"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE contract",
        "award_or_vehicle": "70CDCR20D00000008",
    },
    "Mesa Verde ICE Processing Center": {
        "patterns": ["mesa verde ice processing center", "mesa verde ice processing facility", "mesa verde detention facility"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE contract",
        "award_or_vehicle": "70CDCR20D00000008",
    },
    "Northwest ICE Processing Center": {
        "patterns": ["northwest ice processing center", "northwest detention center", "tacoma ice processing center"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE contract",
        "award_or_vehicle": "not normalized in this wave",
    },
    "South Texas ICE Processing Center": {
        "patterns": ["south texas ice processing center", "south texas processing center"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE contract",
        "award_or_vehicle": "HSCEDM12D00001",
    },
    "Karnes County Residential Center": {
        "patterns": ["karnes county residential center", "karnes county residential facility"],
        "geo_role": "GEO operator",
        "contract_channel": "historical county/ICE arrangement",
        "award_or_vehicle": "do not automatically merge with current Karnes IPC award 70CDCR24DIG000018",
    },
    "Joe Corley Processing Center": {
        "patterns": ["joe corley processing center"],
        "geo_role": "GEO downstream operator",
        "contract_channel": "Montgomery County IGSA pass-through",
        "award_or_vehicle": "70CDCR18DIG000013 (period/modification crosswalk required)",
    },
    "Montgomery Processing Center": {
        "patterns": ["montgomery processing center"],
        "geo_role": "GEO operator",
        "contract_channel": "ICE procurement",
        "award_or_vehicle": "not normalized in this wave",
    },
    "Pine Prairie ICE Processing Center": {
        "patterns": ["pine prairie ice processing center"],
        "geo_role": "GEO downstream operator",
        "contract_channel": "Evangeline Parish IGSA pass-through",
        "award_or_vehicle": "EROIGSA-15-0006",
    },
    "South Louisiana ICE Processing Center": {
        "patterns": ["south louisiana ice processing center"],
        "geo_role": "GEO downstream operator",
        "contract_channel": "Evangeline Parish IGSA pass-through",
        "award_or_vehicle": "EROIGSA-15-0006",
    },
    "Broward Transitional Center": {
        "patterns": ["broward transitional center"],
        "geo_role": "GEO operator",
        "contract_channel": "ICE procurement",
        "award_or_vehicle": "not normalized in this wave",
    },
    "LaSalle ICE Processing Center": {
        "patterns": ["lasalle ice processing center"],
        "geo_role": "GEO-owned/GEO-operated during OIG-19-47 review period",
        "contract_channel": "historical ICE procurement",
        "award_or_vehicle": "not normalized in this wave",
    },
    "Moshannon Valley Processing Center": {
        "patterns": ["moshannon valley processing center"],
        "geo_role": "GEO downstream operator",
        "contract_channel": "Clearfield County IGSA pass-through",
        "award_or_vehicle": "70CDCR21DIG000012",
    },
    "Rio Grande Processing Center": {
        "patterns": ["rio grande processing center", "rio grande detention center"],
        "geo_role": "GEO operator",
        "contract_channel": "direct ICE agreement / DOJ rider history",
        "award_or_vehicle": "HSCEDM14A00001",
    },
}


URLS = {
    "OIG-18-86": "https://www.oig.dhs.gov/sites/default/files/assets/Mga/2018/oig-18-86-sep18.pdf",
    "OIG-19-18": "https://www.oig.dhs.gov/sites/default/files/assets/2019-02/OIG-19-18-Jan19.pdf",
    "OIG-19-47": "https://www.oig.dhs.gov/sites/default/files/assets/2019-06/OIG-19-47-Jun19.pdf",
    "OIG-20-45": "https://www.oig.dhs.gov/sites/default/files/assets/2020-07/OIG-20-45-Jul20.pdf",
    "OIG-22-40": "https://www.oig.dhs.gov/sites/default/files/assets/2022-05/OIG-22-40-Apr22.pdf",
    "OIG-22-47": "https://www.oig.dhs.gov/sites/default/files/assets/2022-07/OIG-22-47-July22.pdf",
    "OIG-23-26": "https://www.oig.dhs.gov/sites/default/files/assets/2023-05/OIG-23-26-May23.pdf",
    "OIG-24-03": "https://www.oig.dhs.gov/sites/default/files/assets/2023-11/OIG-24-03-Nov23.pdf",
    "OIG-24-23": "https://www.oig.dhs.gov/sites/default/files/assets/2024-04/OIG-24-23-Apr24.pdf",
    "OIG-24-29": "https://www.oig.dhs.gov/sites/default/files/assets/2024-06/OIG-24-29-Jun24.pdf",
    "DHS-OIG-KARNES-2015": "https://www.oversight.gov/sites/default/files/documents/reports/2017-07/OIG_mga-010715.pdf",
    "ICE-ODO-2024-002-386": "https://www.ice.gov/doclib/foia/odo-compliance-inspections/2024-AdelantoIPC-AdelantoCA-July.pdf",
    "ICE-ODO-2024-002-330": "https://www.ice.gov/doclib/foia/odo-compliance-inspections/denverCDF_AuroraCO_Aug13-15_2024.pdf",
    "ICE-ODO-2024-005-389": "https://www.ice.gov/doclib/foia/odo-compliance-inspections/tacomaIPC_NorthwestDetCTR_TacomaWA_Aug13-15_2024.pdf",
    "ICE-ODO-OPR-201200440": "https://www.ice.gov/doclib/foia/odo-compliance-inspections/2012northwest-detention-center-tacoma-wa-jan10-12.pdf",
    "ICE-DDR-GONZALEZ-2017": "https://www.ice.gov/doclib/foia/reports/ddrGonzalez.pdf",
    "GAO-15-153": "https://www.gao.gov/products/gao-15-153",
    "GAO-20-596": "https://www.gao.gov/products/gao-20-596",
    "GAO-21-149": "https://www.gao.gov/products/gao-21-149",
    "GAO-25-107580": "https://www.gao.gov/products/gao-25-107580",
}


PDF_FILES = {
    "OIG-18-86": "adelanto-oig-18-86.pdf",
    "OIG-19-18": "accountability-oig-19-18.pdf",
    "OIG-19-47": "four-oig-19-47.pdf",
    "OIG-20-45": "capping-oig-20-45.pdf",
    "OIG-22-40": "south-texas-oig-22-40.pdf",
    "OIG-22-47": "folkston-oig-22-47.pdf",
    "OIG-23-26": "northwest-oig-23-26.pdf",
    "OIG-24-03": "mesa-oig-24-03.pdf",
    "OIG-24-23": "golden-oig-24-23.pdf",
    "OIG-24-29": "aurora-oig-24-29.pdf",
    "DHS-OIG-KARNES-2015": "karnes.pdf",
    "ICE-ODO-2024-002-386": "odo-adelanto-2024-07.pdf",
    "ICE-ODO-2024-002-330": "odo-denver-2024-08.pdf",
    "ICE-ODO-2024-005-389": "odo-tacoma-2024-08.pdf",
    "ICE-ODO-OPR-201200440": "odo-tacoma-2012-01.pdf",
    "ICE-DDR-GONZALEZ-2017": "ddr-gonzalez-2017.pdf",
}


MATRIX_COLUMNS = [
    "facility",
    "geo_role",
    "contract_channel",
    "award_or_vehicle",
    "oversight_body",
    "report_id",
    "report_date",
    "record_type",
    "finding_class",
    "issue_domain",
    "exact_quote",
    "quote_locator",
    "agency_or_geo_response",
    "corrective_action_status",
    "source_url",
    "identity_and_scope_note",
    "financial_consequence_scope",
]


def row(
    facility: str,
    body: str,
    report_id: str,
    date: str,
    record_type: str,
    finding_class: str,
    domain: str,
    quote: str,
    locator: str,
    response: str = "",
    corrective: str = "",
    scope_note: str = "",
) -> dict[str, str]:
    if facility == "Systemwide ICE detention oversight":
        meta = {
            "geo_role": "GEO is within the regulated/contracted universe; report is not facility-specific",
            "contract_channel": "multiple direct contracts and IGSAs",
            "award_or_vehicle": "systemwide; do not attribute to a single award",
        }
    else:
        meta = FACILITIES[facility]
    return {
        "facility": facility,
        "geo_role": meta["geo_role"],
        "contract_channel": meta["contract_channel"],
        "award_or_vehicle": meta["award_or_vehicle"],
        "oversight_body": body,
        "report_id": report_id,
        "report_date": date,
        "record_type": record_type,
        "finding_class": finding_class,
        "issue_domain": domain,
        "exact_quote": quote,
        "quote_locator": locator,
        "agency_or_geo_response": response,
        "corrective_action_status": corrective,
        "source_url": URLS[report_id],
        "identity_and_scope_note": scope_note,
        "financial_consequence_scope": "Excluded from this lead; any payment or award consequence belongs in lead 57784 unless the source directly states it.",
    }


def matrix_rows() -> list[dict[str, str]]:
    rows = [
        row("Adelanto ICE Processing Center", "DHS OIG", "OIG-18-86", "2018-09-27", "unannounced inspection", "inspection observation", "PBNDS / health and safety", "serious issues that violate ICE’s 2011 Performance-Based National Detention Standards and pose significant health and safety risks at the facility", "Highlights, PDF p. 2", "ICE stated that it conducted a full inspection and a Special Assessment Review.", "At issuance OIG treated the recommendation as resolved and open.", "Historical City of Adelanto D-IGSA period; do not project the observation onto later direct-contract periods."),
        row("Adelanto ICE Processing Center", "DHS OIG", "OIG-19-47", "2019-06-03", "unannounced inspection", "inspection observation", "segregation", "Our spot inspections of the Adelanto, Essex, and Aurora facilities identified serious issues with the administrative and disciplinary segregation of detainees.", "Report body, PDF p. 8", "ICE stated field offices had taken corrective action at each facility when warranted.", "Aggregate recommendation response; facility-specific closure requires recommendation-file review.", "The quoted sentence covers Adelanto and Aurora plus non-GEO Essex; it is not independent corroboration for each facility."),
        row("Denver Contract Detention Facility", "DHS OIG", "OIG-19-47", "2019-06-03", "unannounced inspection", "inspection observation", "segregation", "Our spot inspections of the Adelanto, Essex, and Aurora facilities identified serious issues with the administrative and disciplinary segregation of detainees.", "Report body, PDF p. 8", "ICE stated field offices had taken corrective action at each facility when warranted.", "Aggregate recommendation response; facility-specific closure requires recommendation-file review.", "Aurora is the Denver Contract Detention Facility; the sentence also covers Adelanto and non-GEO Essex."),
        row("Northwest ICE Processing Center", "DHS OIG", "OIG-20-45", "2020-07-01", "unannounced inspection", "inspection observation", "grievance timeliness", "Of the 467 grievances filed from September 2018 to March 2019 at Northwest, 222 (47 percent) did not meet the 5-calendar-day response requirement, with 144 taking 10 days or longer to provide a response.", "Report body, PDF p. 11", "ICE concurred and directed field offices to take ongoing actions.", "The report describes Special Assessment Reviews as part of ICE's response; later completion was not established in this wave."),
        row("South Texas ICE Processing Center", "DHS OIG", "OIG-22-40", "2022-04-22", "unannounced inspection", "inspection observation", "grievances / segregation / COVID-19 / communication", "South Texas did not meet standards for grievances, segregation, COVID-19 response, or detainee communication.", "Highlights, PDF p. 3", "ICE concurred with all five recommendations.", "At issuance: three resolved and closed, two resolved and open; public page displayed recommendations 2 and 4 as open on 2026-07-14."),
        row("South Texas ICE Processing Center", "DHS OIG", "OIG-22-40", "2022-04-22", "unannounced inspection", "compliant finding / counterevidence", "legal services / voluntary work / classification / medical", "South Texas complied with standards for legal services, the voluntary work program, and detainee classification and provided sufficient medical care to detainees.", "Highlights, PDF p. 3"),
        row("Folkston ICE Processing Center", "DHS OIG", "OIG-22-47", "2022-07-01", "unannounced inspection", "inspection observation", "conditions / medical / grievances / segregation / communication / property", "Folkston did not meet standards for facility conditions, medical care, grievances, segregation, staff-detainee communication, and detainee property.", "Highlights, PDF p. 3", "ICE concurred with all 13 recommendations.", "At issuance: 12 resolved and closed, one resolved and open.", "Covers the main and annex collectively; the report does not assign every observation to a single building."),
        row("Folkston ICE Processing Center", "DHS OIG", "OIG-22-47", "2022-07-01", "unannounced inspection", "compliant finding / counterevidence", "legal services / voluntary work / classification", "Folkston complied with standards for access to legal services, the voluntary work program, and detainee classification.", "Highlights, PDF p. 3", scope_note="Covers the main and annex collectively."),
        row("Northwest ICE Processing Center", "DHS OIG", "OIG-23-26", "2023-05-22", "unannounced inspection", "inspection observation", "grievances / language / food / medical staffing", "Northwest did not always provide timely responses to detainee grievances and did not always respond to detainee requests and grievances in a language understood by the detainee.", "Highlights, PDF p. 3", "ICE concurred with seven recommendations and did not concur with one.", "At issuance: three resolved and closed, four resolved and open, one unresolved and open; public pages displayed recommendations 1, 2, 3, 7, and 8 as open on 2026-07-14."),
        row("Northwest ICE Processing Center", "DHS OIG", "OIG-23-26", "2023-05-22", "unannounced inspection", "compliant finding / counterevidence", "intake / classification / conditions / legal / recreation / segregation / use of force / requests", "the facility complied with standards for intake and classification; facility conditions, including housing and hygiene; detainee access to law library and legal services; recreation; segregation; use of force; and providing timely responses to detainee requests", "Highlights, PDF p. 3"),
        row("Mesa Verde ICE Processing Center", "DHS OIG", "OIG-24-03", "2023-11-02", "limited-scope unannounced inspection", "inspection observation", "use of force reporting / optometry", "the facility did not accurately report or fully record an event that met the requirements of a use of force incident", "Highlights, PDF p. 3", "ICE concurred with all three recommendations.", "At issuance all three were resolved and open; the public page displayed recommendation 1 as open on 2026-07-14."),
        row("Mesa Verde ICE Processing Center", "DHS OIG", "OIG-24-03", "2023-11-02", "limited-scope unannounced inspection", "compliant finding / counterevidence", "voluntary work / conditions / grievances", "the facility complied with standards for the voluntary work program, facility conditions, and grievances", "Highlights, PDF p. 3"),
        row("Golden State Annex", "DHS OIG", "OIG-24-23", "2024-04-18", "unannounced inspection", "inspection observation", "classification / grievances / segregation recreation / requests / conditions", "The facility could not ensure it was completing detainee classification within the required 12 hours, or that all required reclassification paperwork was in detainees’ files.", "Highlights, PDF p. 3", "ICE concurred with all seven recommendations.", "At issuance recommendations 1, 2, 3, 5, and 7 were resolved/open and 4 and 6 resolved/closed; public page displayed 1, 2, and 3 as open on 2026-07-14."),
        row("Golden State Annex", "DHS OIG", "OIG-24-23", "2024-04-18", "unannounced inspection", "compliant finding / counterevidence", "use of force / voluntary work / legal / segregation", "Golden State complied with ICE’s Performance-Based National Detention Standards 2011 (PBNDS 2011), as revised in December 2016, for use of force, the voluntary work program, access to the law library and legal services, and detainee segregation with one noted exception.", "Highlights, PDF p. 3"),
        row("Denver Contract Detention Facility", "DHS OIG", "OIG-24-29", "2024-06-12", "unannounced inspection", "inspection observation", "communication / grievances", "facility and ICE staff did not comply with standards related to staff-detainee communication and grievance practices", "Highlights, PDF p. 3", "ICE concurred with all 14 recommendations.", "At issuance six were resolved/closed and eight resolved/open; public page displayed recommendations 1, 4, 6, 7, 8, and 13 as open on 2026-07-14."),
        row("Denver Contract Detention Facility", "DHS OIG", "OIG-24-29", "2024-06-12", "unannounced inspection", "compliant finding / counterevidence", "recreation / use of force / library / voluntary work", "Denver’s staff complied with Performance-Based National Detention Standards 2011, revised in December 2016, for recreation, use of force, library, and the voluntary work program.", "Highlights, PDF p. 3"),
        row("Karnes County Residential Center", "DHS OIG", "DHS-OIG-KARNES-2015", "2015-01-07", "investigative summary", "investigative conclusion", "alleged staff sexual misconduct", "We found no evidence to substantiate the allegations and were unable to identify a victim or suspect in this matter.", "Conclusions, PDF p. 4", "A report was provided to ICE and DHS CRCL before a scheduled CRCL inspection.", "ICE complied with PREA reporting requirements.", "This is a non-substantiation conclusion about specified allegations, not a general compliance finding."),
        row("Adelanto ICE Processing Center", "ICE Office of Detention Oversight", "ICE-ODO-2024-002-386", "2024-07-18", "follow-up compliance inspection", "compliant finding / counterevidence", "18 reviewed standards", "There were no findings during the inspection.", "Conclusion, physical PDF p. 7", corrective="The report's follow-up result is later-period counterevidence; it does not supersede OIG-18-86."),
        row("Denver Contract Detention Facility", "ICE Office of Detention Oversight", "ICE-ODO-2024-002-330", "2024-08-15", "follow-up compliance inspection", "inspection observation", "four deficient standards", "ODO found six deficiencies in the remaining four standards.", "Conclusion, physical PDF p. 11", corrective="The report states the facility completed a prior UCAP and likely resolved the earlier cited deficiencies; that statement is not proof that every new deficiency was closed."),
        row("Denver Contract Detention Facility", "ICE Office of Detention Oversight", "ICE-ODO-2024-002-330", "2024-08-15", "follow-up compliance inspection", "compliant finding / counterevidence", "14 reviewed standards", "found the facility in compliance with 14 of those standards", "Conclusion, physical PDF p. 11"),
        row("Denver Contract Detention Facility", "ICE Office of Detention Oversight", "ICE-ODO-2024-002-330", "2024-08-15", "follow-up compliance inspection", "area of concern", "contract staffing", "ODO noted the facility’s staffing levels as an Area of Concern.", "Report body, physical PDF p. 10", scope_note="The report also says ERO kept ADP sufficiently below maximum capacity for adequate coverage; no financial consequence is inferred."),
        row("Northwest ICE Processing Center", "ICE Office of Detention Oversight", "ICE-ODO-2024-005-389", "2024-08-15", "follow-up compliance inspection", "inspection observation", "six deficient standards", "ODO found 11 deficiencies in the remaining 6 standards.", "Conclusion, extracted PDF p. 9", corrective="ODO recommended ERO Seattle continue working with the facility to resolve outstanding deficiencies."),
        row("Northwest ICE Processing Center", "ICE Office of Detention Oversight", "ICE-ODO-2024-005-389", "2024-08-15", "follow-up compliance inspection", "repeat inspection observation", "repeat deficiencies / corrective action", "which included 2 repeat deficiencies. NDCTR completed its UCAP for its last inspection in January 2024, which may not have been sufficient to prevent the repeat deficiencies", "Conclusion, extracted PDF p. 9", corrective="A completed UCAP did not establish durable correction of the two repeated items."),
        row("Northwest ICE Processing Center", "ICE Office of Detention Oversight", "ICE-ODO-2024-005-389", "2024-08-15", "follow-up compliance inspection", "compliant finding / counterevidence", "14 reviewed standards", "found the facility in compliance with 14 of those standards", "Conclusion, extracted PDF p. 9"),
        row("Northwest ICE Processing Center", "ICE Office of Detention Oversight", "ICE-ODO-OPR-201200440", "2012-01-12", "compliance inspection", "mixed inspection result", "13 compliant standards / three documentation deficiencies", "ODO verified that NWDC was in full compliance with 13 of the 15 PBNDS reviewed. ODO recorded only three deficiencies in the following two standards: Disciplinary System (1 deficiency), and Use of Force and Restraints (2).", "Executive summary, extracted PDF p. 4", corrective="ERO was to receive the report to assist in developing corrective actions."),
        row("Adelanto ICE Processing Center", "ICE Office of Professional Responsibility", "ICE-DDR-GONZALEZ-2017", "2017-03-28", "detainee death review", "causation caveat", "death-review deficiencies", "Their inclusion in the report should not be construed in any way as indicating the deficiency contributed to the death of the detainee.", "Synopsis, extracted PDF p. 1", scope_note="The death certificate described the manner as suicide; the review's listed deficiencies are not, by themselves, proof of causation or liability."),
        row("Systemwide ICE detention oversight", "GAO", "GAO-15-153", "2014-10-10", "performance audit", "systemic oversight finding", "inspection consistency", "inspection results differed for 29 of 35 facilities inspected by both ICE's Enforcement and Removal Operations (ERO) and Office of Detention Oversight (ODO) in fiscal year 2013", "GAO product page, What GAO Found", "ICE later modified contractor procedures and GAO closed the related recommendation as implemented.", "Current GAO page status reviewed 2026-07-14.", "Do not apply this systemic denominator to a particular GEO facility without the underlying facility table."),
        row("Systemwide ICE detention oversight", "GAO", "GAO-20-596", "2020-08-19", "performance audit", "systemic oversight finding", "inspection and complaint trend analysis", "ICE collects the results of its various inspections, such as deficiencies they identify, but does not comprehensively analyze them to identify trends or record all inspection results in a format conducive to such analyses.", "GAO product page, What GAO Found", "DHS concurred with all six recommendations.", "GAO's current page records implementation updates; status is recommendation-specific.", "This is a systemwide data-governance finding, not a finding that every GEO facility was deficient."),
        row("Systemwide ICE detention oversight", "GAO", "GAO-21-149", "2021-01-13", "performance audit", "systemic contract-oversight finding", "acquisition documentation", "28 of 40 of these contracts and agreements did not have documentation from ICE field offices showing a need for the space, outreach to local officials, or the basis for ICE's decisions to enter into them, as required by ICE's process.", "GAO product page, What GAO Found", "DHS concurred with four of five recommendations.", "Recommendation 1 was open/partially addressed on the current GAO page reviewed 2026-07-14.", "Do not attribute the 28 acquisitions to GEO without the underlying contract list."),
        row("Systemwide ICE detention oversight", "GAO", "GAO-21-149", "2021-01-13", "performance audit", "systemic contract-oversight finding", "COR independence", "the COR's supervisory structure—where field office management, rather than headquarters, oversee COR work and assess COR performance—does not provide sufficient independence for effective oversight", "GAO product page, What GAO Found", "DHS disagreed with revising the supervisory structure; GAO maintained the recommendation.", "Recommendation status is tracked in existing finding 12396; this row adds no facility-specific consequence."),
        row("Systemwide ICE detention oversight", "GAO", "GAO-25-107580", "2025-05-21", "performance audit", "systemic oversight finding", "inspection-program goals and measures", "ODO rated facilities as acceptable or above in 238 of 241 inspections during this period. But it found deficiencies related to, for example, environmental health and safety, such as water quality; and food service, such as sanitary conditions.", "GAO product page, What GAO Found", "GAO made three recommendations; DHS concurred with two.", "ODO performance-goal recommendation remained open as of May 2026.", "This balanced systemic result is not a facility-specific pass or deficiency determination."),
    ]
    return rows


def canonical_facilities(text: str) -> list[str]:
    low = text.lower()
    return [name for name, meta in FACILITIES.items() if any(p in low for p in meta["patterns"])]


def direct_li_text(li) -> str:
    return " ".join(str(child).strip() for child in li.children if isinstance(child, NavigableString) and str(child).strip())


def iso_date(text: str) -> str:
    cleaned = text.replace("Sept.", "Sep").replace("Oct.", "Oct").replace("Nov.", "Nov").replace("Dec.", "Dec")
    cleaned = cleaned.replace("Jan.", "Jan").replace("Feb.", "Feb").replace("Aug.", "Aug")
    return date_parser.parse(cleaned, fuzzy=True).date().isoformat()


def build_inspection_index(workdir: Path) -> dict:
    soup = BeautifulSoup((workdir / "ice-facility-inspections.html").read_text(errors="replace"), "html.parser")
    events = []
    seen = set()
    for li in soup.select("li"):
        label = re.sub(r"\s+", " ", direct_li_text(li)).strip()
        facilities = canonical_facilities(label)
        if not label or not facilities:
            continue
        match = re.search(r"\s+-\s+(.+?\d{4})\s*$", label)
        if not match:
            continue
        links = []
        for anchor in li.select(":scope > ul a[href]"):
            links.append({"label": anchor.get_text(" ", strip=True), "url": anchor["href"]})
        key = (label, tuple(item["url"] for item in links))
        if key in seen:
            continue
        seen.add(key)
        facility = facilities[0]
        meta = FACILITIES[facility]
        events.append({
            "source_label": label,
            "inspection_date": iso_date(match.group(1)),
            "canonical_facility": facility,
            "geo_role": meta["geo_role"],
            "contract_channel": meta["contract_channel"],
            "award_or_vehicle": meta["award_or_vehicle"],
            "artifacts": links,
            "review_status": "denominator only; linked PDFs require quote-level extraction",
            "not_a_finding": True,
        })
    events.sort(key=lambda item: (item["inspection_date"], item["canonical_facility"], item["source_label"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": "https://www.ice.gov/detain/facility-inspections",
        "scope_note": "Every event matching the declared GEO facility alias set on ICE's public 2018-2022 inspection index. Inclusion is not evidence of a deficiency or GEO responsibility for a finding.",
        "event_count": len(events),
        "linked_artifact_count": sum(len(event["artifacts"]) for event in events),
        "events": events,
    }


DEATH_MATCH_BASENAMES = {
    "dderGabrielGarciaAviles", "ddrAHNChoungWoong", "ddrAmarMergensana", "ddrArriagoSantoyaPedro",
    "ddrDanielCharlesLeo", "ddrEscobarMejiaCarlosErnesto", "ddrFarias-FariasEdixondelJesus",
    "ddrFernandoSabongerGarcia", "ddrFranciscoGasparAndres", "ddrIsmaelUribeAyala", "ddrKaiYinWong",
    "ddrKuanHuiLee", "ddrLuisNunezCaceres", "ddrMarieAngeBlaise", "ddrMelvinCaleroMendoza",
    "ddrSinghJaspar", "ddr_Balderramos-Torres", "ddr_GUTIERREZReyes", "ddr_MONTEJOPeteSumalo",
    "ddr_RAMOSSolanoJoseGuadalupe",
}


def source_snippet(text: str) -> tuple[str, list[str]]:
    normalized = re.sub(r"\s+", " ", text).strip()
    names = canonical_facilities(normalized)
    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        if canonical_facilities(sentence):
            return sentence[:1000], names
    for name, meta in FACILITIES.items():
        for pattern in meta["patterns"]:
            at = normalized.lower().find(pattern)
            if at >= 0:
                return normalized[max(0, at - 300): at + 700], names
    return "", names


def build_death_rows(workdir: Path) -> list[dict[str, str]]:
    soup = BeautifulSoup((workdir / "ice-death-reporting.html").read_text(errors="replace"), "html.parser")
    metadata = {}
    for tr in soup.select("table tr"):
        cells = tr.find_all("td")
        anchor = tr.find("a", href=True)
        if len(cells) != 2 or not anchor:
            continue
        stem = Path(urlparse(anchor["href"]).path).stem
        metadata[stem] = {
            "date_of_death": iso_date(cells[0].get_text(" ", strip=True)),
            "name": anchor.get_text(" ", strip=True),
            "source_url": anchor["href"].replace("http://", "https://"),
        }
    death_texts = list((workdir / "death-reports").glob("*.txt"))
    matched_stems = set(DEATH_MATCH_BASENAMES)
    matched_stems.update(path.stem for path in death_texts if canonical_facilities(path.read_text(errors="replace")))
    rows = []
    for stem in sorted(matched_stems):
        txt = workdir / "death-reports" / f"{stem}.txt"
        snippet, facilities = source_snippet(txt.read_text(errors="replace"))
        md = metadata.get(stem, {})
        rows.append({
            "date_of_death": md.get("date_of_death", ""),
            "name": md.get("name", ""),
            "report_file": stem + ".pdf",
            "source_url": md.get("source_url", ""),
            "matched_canonical_facilities": " | ".join(facilities),
            "exact_facility_context_excerpt": snippet,
            "linkage_class": "timeline linkage only",
            "causation_or_death_location_inference": "none; requires report-level adjudication",
            "review_status": "alias hit reviewed for inclusion; substantive causation/deficiency extraction transferred to follow-on lead",
        })
    rows.append({
        "date_of_death": "2017-03-28",
        "name": "Gonzalez-Gadba, Osmar Epifanio",
        "report_file": "ddrGonzalez.pdf",
        "source_url": URLS["ICE-DDR-GONZALEZ-2017"],
        "matched_canonical_facilities": "Adelanto ICE Processing Center",
        "exact_facility_context_excerpt": "Their inclusion in the report should not be construed in any way as indicating the deficiency contributed to the death of the detainee.",
        "linkage_class": "quote-reviewed facility death review",
        "causation_or_death_location_inference": "report says death occurred at Victor Valley Global Medical Center and expressly disclaims treating a listed deficiency as causation",
        "review_status": "quote-reviewed; finding 12806",
    })
    rows.sort(key=lambda item: (item["date_of_death"], item["name"]))
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inspections = build_inspection_index(args.workdir)
    inspection_path = args.output_dir / "2026-07-14-lead-57703-geo-ice-inspection-index.json"
    inspection_path.write_text(json.dumps(inspections, indent=2, ensure_ascii=False) + "\n")

    deaths = build_death_rows(args.workdir)
    death_path = args.output_dir / "2026-07-14-lead-57703-geo-ice-death-review-index.csv"
    write_csv(death_path, deaths, list(deaths[0]))

    matrix = matrix_rows()
    matrix_path = args.output_dir / "2026-07-14-lead-57703-geo-ice-oversight-matrix.csv"
    write_csv(matrix_path, matrix, MATRIX_COLUMNS)

    source_files = []
    for report_id, filename in PDF_FILES.items():
        path = args.workdir / filename
        source_files.append({
            "report_id": report_id,
            "official_url": URLS[report_id],
            "local_snapshot_name": filename,
            "sha256": sha256(path),
            "text_extracted": path.with_suffix(".txt").exists(),
        })
    manifest = {
        "lead_id": 57703,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Primary-source crosswalk: DHS OIG/Oversight.gov, ICE ODO inspection index and PDFs, ICE death-review index and PDFs, and GAO product pages.",
        "separation_rules": [
            "inspection observations, investigative allegations, adjudicated findings, and compliant counterevidence remain distinct",
            "an inspection-index link is not a finding",
            "a death-review facility mention is a timeline linkage unless the report itself establishes location, deficiency, or causation",
            "no financial consequence is inferred; lead 57784 owns that analysis",
        ],
        "coverage": {
            "quote_reviewed_matrix_rows": len(matrix),
            "ice_inspection_events_indexed": inspections["event_count"],
            "ice_inspection_artifacts_linked": inspections["linked_artifact_count"],
            "death_review_alias_hits": len(deaths) - 1,
            "older_quote_reviewed_death_review": 1,
            "unreviewed_residual": f"The linked ICE inspection PDFs and {len(deaths) - 1} current death-review alias hits require document-by-document quote extraction in a follow-on lead.",
        },
        "current_public_recommendation_snapshot": {
            "as_of": "2026-07-14",
            "scope_warning": "Numbers below are recommendations displayed as open on the public Oversight.gov report pages checked in this wave; absence from a page was not treated as proof of closure.",
            "OIG-22-40": [2, 4],
            "OIG-23-26": [1, 2, 3, 7, 8],
            "OIG-24-03": [1],
            "OIG-24-23": [1, 2, 3],
            "OIG-24-29": [1, 4, 6, 7, 8, 13],
        },
        "visual_qa": {
            "method": "Rendered primary PDFs with Poppler; reviewed contact sheets and selected conclusion/highlight pages.",
            "contact_sheets": ["contact-1.jpg", "contact-2.jpg", "contact-3.jpg"],
            "selected_pages": [
                "adelanto-oig-18-86-p2.png", "four-oig-19-47-p3.png", "capping-oig-20-45-p3.png",
                "south-texas-oig-22-40-p3.png", "folkston-oig-22-47-p3.png", "northwest-oig-23-26-p3.png",
                "mesa-oig-24-03-p3.png", "golden-oig-24-23-p3.png", "aurora-oig-24-29-p3.png",
                "karnes-p4.png", "odo-adelanto-2024-7.png", "odo-denver-2024-p10.png", "odo-denver-2024-p11.png",
            ],
        },
        "primary_source_files": source_files,
        "gao_product_pages": [{"report_id": report_id, "official_url": URLS[report_id]} for report_id in ("GAO-15-153", "GAO-20-596", "GAO-21-149", "GAO-25-107580")],
        "artifacts": [matrix_path.name, inspection_path.name, death_path.name],
    }
    manifest_path = args.output_dir / "2026-07-14-lead-57703-geo-ice-oversight-source-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({
        "matrix_rows": len(matrix),
        "inspection_events": inspections["event_count"],
        "inspection_links": inspections["linked_artifact_count"],
        "death_rows": len(deaths),
        "outputs": [str(matrix_path), str(inspection_path), str(death_path), str(manifest_path)],
    }, indent=2))


if __name__ == "__main__":
    main()
