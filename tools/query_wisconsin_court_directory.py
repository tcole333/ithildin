#!/usr/bin/env python3
"""Query the Wisconsin Court System's official directory family.

The publisher maintains several complementary current-state directories:
county circuit-court offices, clerks, judge rosters, judicial administrative
districts, Court of Appeals offices, and Supreme Court/state court offices.
This adapter keeps those roles distinct and returns them as source snapshots,
not as cases.

Examples:
    uv run python tools/query_wisconsin_court_directory.py sources --json
    uv run python tools/query_wisconsin_court_directory.py routes --json
    uv run python tools/query_wisconsin_court_directory.py list \
        --component clerks --output /tmp/wi-clerks.json
    uv run python tools/query_wisconsin_court_directory.py county Dane --json
    uv run python tools/query_wisconsin_court_directory.py search Ashley \
        --component administrative-districts --json
    uv run python tools/query_wisconsin_court_directory.py discovery \
        --query Dane --json
    uv run python tools/query_wisconsin_court_directory.py probe --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


SOURCE_ID = "us-wi-court-directory"
STATE_CODE = "WI"
STATE_GEOID = "55"
AUTHORITY = "Wisconsin Court System"
BASE_URL = "https://www.wicourts.gov"
DIRECTORIES_URL = f"{BASE_URL}/contact/directories.htm"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.15
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

CIRCUIT_COMPONENT = "circuit-courts"
CLERK_COMPONENT = "clerks"
JUDGE_COMPONENT = "judges"
DISTRICT_COMPONENT = "administrative-districts"
APPEALS_COMPONENT = "court-of-appeals"
STATE_OFFICE_COMPONENT = "supreme-state-offices"
COMPONENTS = (
    CIRCUIT_COMPONENT,
    CLERK_COMPONENT,
    JUDGE_COMPONENT,
    DISTRICT_COMPONENT,
    APPEALS_COMPONENT,
    STATE_OFFICE_COMPONENT,
)
COUNTY_COMPONENTS = frozenset(
    {CIRCUIT_COMPONENT, CLERK_COMPONENT, JUDGE_COMPONENT}
)

COMPONENT_DEFINITIONS: Mapping[str, Mapping[str, str]] = {
    CIRCUIT_COMPONENT: {
        "name": "Circuit Courts directory",
        "url": f"{BASE_URL}/contact/Circuit_Courts.html",
        "record_kind": "circuit_court_office_directory",
        "function": (
            "County courthouse addresses, judicial districts, judges, "
            "reporters, and published telephone contacts"
        ),
    },
    CLERK_COMPONENT: {
        "name": "Clerks of circuit court directory",
        "url": f"{BASE_URL}/courts/circuit/clerkcontact.htm",
        "record_kind": "circuit_court_clerk_directory",
        "function": (
            "Current clerk name, mailing or street contact, telephone, and "
            "official county court website"
        ),
    },
    JUDGE_COMPONENT: {
        "name": "Circuit court judges and court websites",
        "url": f"{BASE_URL}/courts/circuit/judges.htm",
        "record_kind": "circuit_court_judge_roster",
        "function": (
            "Current county judge roster and official county court website"
        ),
    },
    DISTRICT_COMPONENT: {
        "name": "Committee of Chief Judges",
        "url": f"{BASE_URL}/courts/committees/chiefjudges.htm",
        "record_kind": "judicial_administrative_district_directory",
        "function": (
            "Administrative district counties, chief and deputy chief judges, "
            "and district court administrator contacts"
        ),
    },
    APPEALS_COMPONENT: {
        "name": "Court of Appeals directory",
        "url": f"{BASE_URL}/contact/Court_of_Appeals.html",
        "record_kind": "appellate_court_office_directory",
        "function": (
            "Court of Appeals clerk, four districts, judges, staff, addresses, "
            "and published telephone contacts"
        ),
    },
    STATE_OFFICE_COMPONENT: {
        "name": "Supreme Court and state court offices directory",
        "url": f"{BASE_URL}/contact/SC_Admin_Offices.html",
        "record_kind": "state_court_office_directory",
        "function": (
            "Supreme Court justices and the state-level administrative, "
            "regulatory, library, and court-program offices"
        ),
    },
}

COUNTY_FIPS: Mapping[str, str] = {
    "Adams": "55001",
    "Ashland": "55003",
    "Barron": "55005",
    "Bayfield": "55007",
    "Brown": "55009",
    "Buffalo": "55011",
    "Burnett": "55013",
    "Calumet": "55015",
    "Chippewa": "55017",
    "Clark": "55019",
    "Columbia": "55021",
    "Crawford": "55023",
    "Dane": "55025",
    "Dodge": "55027",
    "Door": "55029",
    "Douglas": "55031",
    "Dunn": "55033",
    "Eau Claire": "55035",
    "Florence": "55037",
    "Fond du Lac": "55039",
    "Forest": "55041",
    "Grant": "55043",
    "Green": "55045",
    "Green Lake": "55047",
    "Iowa": "55049",
    "Iron": "55051",
    "Jackson": "55053",
    "Jefferson": "55055",
    "Juneau": "55057",
    "Kenosha": "55059",
    "Kewaunee": "55061",
    "La Crosse": "55063",
    "Lafayette": "55065",
    "Langlade": "55067",
    "Lincoln": "55069",
    "Manitowoc": "55071",
    "Marathon": "55073",
    "Marinette": "55075",
    "Marquette": "55077",
    "Menominee": "55078",
    "Milwaukee": "55079",
    "Monroe": "55081",
    "Oconto": "55083",
    "Oneida": "55085",
    "Outagamie": "55087",
    "Ozaukee": "55089",
    "Pepin": "55091",
    "Pierce": "55093",
    "Polk": "55095",
    "Portage": "55097",
    "Price": "55099",
    "Racine": "55101",
    "Richland": "55103",
    "Rock": "55105",
    "Rusk": "55107",
    "St. Croix": "55109",
    "Sauk": "55111",
    "Sawyer": "55113",
    "Shawano": "55115",
    "Sheboygan": "55117",
    "Taylor": "55119",
    "Trempealeau": "55121",
    "Vernon": "55123",
    "Vilas": "55125",
    "Walworth": "55127",
    "Washburn": "55129",
    "Washington": "55131",
    "Waukesha": "55133",
    "Waupaca": "55135",
    "Waushara": "55137",
    "Winnebago": "55139",
    "Wood": "55141",
}

DISTRICT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
ROMAN_DISTRICTS = {"I": 1, "II": 2, "III": 3, "IV": 4}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Wisconsin Court System official directories",
    source_role="official_statewide_court_and_personnel_directory_family",
    base_url=DIRECTORIES_URL,
    dataset_id="wisconsin-court-system-directories",
    metadata={
        "authority": AUTHORITY,
        "authentication": "none",
        "coverage": "statewide_current_directory_snapshot",
        "parsed_components": list(COMPONENTS),
        "county_count": len(COUNTY_FIPS),
        "case_records": False,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Wisconsin",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_court_directory"},
)

SOURCE_WARNINGS = (
    "Directory entries describe current offices, assignments, and contacts; "
    "they are preserved as snapshots rather than case records.",
    "The component pages serve different functions and retain separate record "
    "kinds even when they describe the same county or person.",
    "County website links are publisher-provided discovery routes whose case, "
    "calendar, filing, and copy capabilities should be assessed separately.",
)

_PHONE_RE = re.compile(r"\bPh:\s*(.+)", flags=re.IGNORECASE)
_DISTRICT_RE = re.compile(
    r"\b(\d+)(?:st|nd|rd|th)\s+Judicial\s+District\b",
    flags=re.IGNORECASE,
)
_APPEALS_DISTRICT_RE = re.compile(
    r"^District\s+([IV]+)\s+-\s+(.+?)\s+Count(?:y|ies)$",
    flags=re.IGNORECASE,
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _county_key(value: str) -> str:
    normalized = (
        value.replace("’", "'")
        .replace("&", " and ")
        .strip()
        .removesuffix(" Counties")
        .removesuffix(" County")
    )
    return re.sub(r"[^a-z0-9]+", " ", normalized.casefold()).strip()


COUNTY_BY_KEY = {_county_key(name): name for name in COUNTY_FIPS}
COUNTY_BY_GEOID = {geoid: name for name, geoid in COUNTY_FIPS.items()}
COUNTY_BY_COURT_ID = {
    f"wi-{_slug(name)}-circuit": name for name in COUNTY_FIPS
}


class WisconsinCourtDirectoryError(RuntimeError):
    """One source error represented in the common public-records envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class WisconsinCourtDirectoryChangedError(WisconsinCourtDirectoryError):
    """The official page no longer matches its verified structure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="schema",
            details=details,
        )


@dataclass(frozen=True)
class WisconsinDirectoryPage:
    """One parsed official directory component."""

    component: str
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    snapshot_fingerprint: str
    coverage: Mapping[str, Any]


def _canonical_county(value: str) -> str:
    key = _county_key(value)
    county = COUNTY_BY_KEY.get(key)
    if county is None:
        raise WisconsinCourtDirectoryChangedError(
            "unknown_county",
            f"Wisconsin directory published an unknown county name: {value!r}",
            details={"normalized_county": key},
        )
    return county


def resolve_county_selector(value: str) -> str:
    """Resolve a county name, county GEOID, or canonical circuit court ID."""

    normalized = str(value).strip()
    if normalized in COUNTY_BY_GEOID:
        return COUNTY_BY_GEOID[normalized]
    if normalized in COUNTY_BY_COURT_ID:
        return COUNTY_BY_COURT_ID[normalized]
    county = COUNTY_BY_KEY.get(_county_key(normalized))
    if county is None:
        raise ValueError(f"unknown Wisconsin county selector: {value!r}")
    return county


def _element_lines(element: Any) -> list[str]:
    return [
        line
        for value in element.get_text("\n", strip=True).splitlines()
        if (line := _text(value)) is not None
    ]


def _links(element: Any, source_url: str) -> list[dict[str, str | None]]:
    links: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str]] = set()
    for anchor in element.find_all("a", href=True):
        url = urljoin(source_url, str(anchor["href"]).strip())
        label = _text(anchor.get_text(" ", strip=True))
        identity = (label, url)
        if identity in seen:
            continue
        seen.add(identity)
        links.append({"label": label, "url": url})
    return links


def _table(
    html_text: str,
    *,
    table_id: str | None,
    expected_headers: Sequence[str],
    component: str,
) -> tuple[Any, str]:
    lower = html_text.casefold()
    if any(marker in lower for marker in _CHALLENGE_MARKERS):
        raise WisconsinCourtDirectoryError(
            "challenge_page",
            f"Wisconsin {component} directory returned an interstitial",
            status=ResultStatus.RESTRICTED,
            category="access",
        )
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", id=table_id) if table_id else soup.find("table")
    if table is None:
        raise WisconsinCourtDirectoryChangedError(
            "directory_table_missing",
            f"Wisconsin {component} directory lacks its expected table",
            details={"table_id": table_id},
        )
    headers = tuple(
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in table.select("thead th")
    )
    if headers != tuple(expected_headers):
        raise WisconsinCourtDirectoryChangedError(
            "directory_headers_changed",
            f"Wisconsin {component} directory headers changed",
            details={
                "expected_headers": list(expected_headers),
                "observed_headers": list(headers),
            },
        )
    fingerprint = sha256_fingerprint(
        {
            "component": component,
            "table_id": table.get("id"),
            "table_classes": sorted(table.get("class", [])),
            "headers": headers,
        }
    )
    return table, fingerprint


def _county_record_base(
    *,
    component: str,
    record_kind: str,
    county: str,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    county_geoid = COUNTY_FIPS[county]
    return {
        "canonical_ref": (
            f"WI-COURT-DIRECTORY:{component}:{county_geoid}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": record_kind,
        "directory_component": component,
        "snapshot_only": True,
        "county": county,
        "county_fips": county_geoid,
        "county_geoid": county_geoid,
        "court_id": f"wi-{_slug(county)}-circuit",
        "court_name": f"{county} County Circuit Court",
        "source_url": source_url,
        "provenance": {
            "authority": AUTHORITY,
            "response_schema_fingerprint": schema_fingerprint,
            "personnel_and_office_snapshot": True,
        },
    }


def _finish_page(
    component: str,
    records: Sequence[Mapping[str, Any]],
    *,
    source_url: str,
    schema_fingerprint: str,
    coverage: Mapping[str, Any],
) -> WisconsinDirectoryPage:
    return WisconsinDirectoryPage(
        component=component,
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        snapshot_fingerprint=sha256_fingerprint(records),
        coverage=dict(coverage),
    )


def _validate_county_records(
    records: Sequence[Mapping[str, Any]],
    *,
    component: str,
    require_complete: bool,
) -> None:
    counties = [str(record["county"]) for record in records]
    duplicates = sorted(
        county for county in set(counties) if counties.count(county) > 1
    )
    if duplicates:
        raise WisconsinCourtDirectoryChangedError(
            "duplicate_counties",
            f"Wisconsin {component} directory repeats counties",
            details={"counties": duplicates},
        )
    if require_complete and set(counties) != set(COUNTY_FIPS):
        raise WisconsinCourtDirectoryChangedError(
            "county_coverage_changed",
            f"Wisconsin {component} directory no longer covers all 72 counties",
            details={
                "expected_count": len(COUNTY_FIPS),
                "observed_count": len(records),
                "missing_counties": sorted(set(COUNTY_FIPS) - set(counties)),
                "unexpected_counties": sorted(set(counties) - set(COUNTY_FIPS)),
            },
        )


def parse_clerks_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[CLERK_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse the official 72-row clerks of circuit court table."""

    table, schema_fingerprint = _table(
        html_text,
        table_id="clerks",
        expected_headers=("County", "Clerk", "Contact"),
        component=CLERK_COMPONENT,
    )
    records: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            raise WisconsinCourtDirectoryChangedError(
                "clerk_row_shape_changed",
                "Wisconsin clerk directory row no longer has three cells",
                details={"cell_count": len(cells)},
            )
        county = _canonical_county(
            _text(cells[0].get_text(" ", strip=True)) or ""
        )
        website_routes = _links(cells[2], source_url)
        labels = {
            str(link["label"])
            for link in website_routes
            if link["label"] is not None
        }
        contact_lines = [
            line for line in _element_lines(cells[2]) if line not in labels
        ]
        phone = next(
            (
                match.group(1).strip()
                for line in contact_lines
                if (match := _PHONE_RE.search(line))
            ),
            None,
        )
        record = _county_record_base(
            component=CLERK_COMPONENT,
            record_kind="circuit_court_clerk_directory",
            county=county,
            source_url=source_url,
            schema_fingerprint=schema_fingerprint,
        )
        record.update(
            {
                "clerk_name": _text(cells[1].get_text(" ", strip=True)),
                "contact_lines": contact_lines,
                "phone": phone,
                "website_routes": website_routes,
            }
        )
        records.append(record)
    _validate_county_records(
        records,
        component=CLERK_COMPONENT,
        require_complete=require_complete,
    )
    return _finish_page(
        CLERK_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={
            "county_count": len(records),
            "county_geoids": [record["county_geoid"] for record in records],
        },
    )


def parse_judges_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[JUDGE_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse the county-level circuit judge rosters and court routes."""

    table, schema_fingerprint = _table(
        html_text,
        table_id="judges",
        expected_headers=("County", "Name", "Court website"),
        component=JUDGE_COMPONENT,
    )
    records: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            raise WisconsinCourtDirectoryChangedError(
                "judge_row_shape_changed",
                "Wisconsin judge directory row no longer has three cells",
                details={"cell_count": len(cells)},
            )
        source_county_label = (
            _text(cells[0].get_text(" ", strip=True)) or ""
        )
        assigned_counties = [
            _canonical_county(value)
            for value in source_county_label.split("/")
            if value.strip()
        ]
        county = assigned_counties[0]
        judge_items = cells[1].find_all("li")
        judges = [
            value
            for item in judge_items
            if (value := _text(item.get_text(" ", strip=True))) is not None
        ]
        if not judges:
            judges = _element_lines(cells[1])
        record = _county_record_base(
            component=JUDGE_COMPONENT,
            record_kind="circuit_court_judge_roster",
            county=county,
            source_url=source_url,
            schema_fingerprint=schema_fingerprint,
        )
        record.update(
            {
                "judges": judges,
                "source_county_label": source_county_label,
                "assigned_counties": assigned_counties,
                "assigned_county_geoids": [
                    COUNTY_FIPS[value] for value in assigned_counties
                ],
                "website_routes": _links(cells[2], source_url),
            }
        )
        records.append(record)
    _validate_county_records(
        records,
        component=JUDGE_COMPONENT,
        require_complete=require_complete,
    )
    return _finish_page(
        JUDGE_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={
            "county_count": len(records),
            "judge_assignment_count": sum(
                len(record["judges"]) for record in records
            ),
            "county_geoids": [record["county_geoid"] for record in records],
        },
    )


def _parse_county_list(value: str) -> list[str]:
    cleaned = re.sub(r"\s+Count(?:y|ies)\s*$", "", value.strip())
    pieces = re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", cleaned)
    return [_canonical_county(piece) for piece in pieces if piece.strip()]


def parse_administrative_districts_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[DISTRICT_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse the current nine judicial administrative districts."""

    table, schema_fingerprint = _table(
        html_text,
        table_id=None,
        expected_headers=(
            "District",
            "Counties",
            "Chief Judge/Deputy Chief Judge",
            "District Court Administrator",
        ),
        component=DISTRICT_COMPONENT,
    )
    records: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 4:
            raise WisconsinCourtDirectoryChangedError(
                "district_row_shape_changed",
                "Wisconsin administrative district row no longer has four cells",
                details={"cell_count": len(cells)},
            )
        district_label = (
            _text(next(iter(cells[0].stripped_strings), "")) or ""
        )
        district_number = DISTRICT_WORDS.get(district_label.casefold())
        if district_number is None:
            raise WisconsinCourtDirectoryChangedError(
                "district_identifier_changed",
                f"Unknown Wisconsin administrative district: {district_label!r}",
            )
        counties = _parse_county_list(
            _text(cells[1].get_text(" ", strip=True)) or ""
        )
        officers = [
            value
            for item in cells[2].find_all("li")
            if (value := _text(item.get_text(" ", strip=True))) is not None
        ]
        if not officers:
            officers = _element_lines(cells[2])
        administrator_lines = _element_lines(cells[3])
        phone = next(
            (
                match.group(1).strip()
                for line in administrator_lines
                if (match := _PHONE_RE.search(line))
            ),
            None,
        )
        records.append(
            {
                "canonical_ref": (
                    "WI-COURT-DIRECTORY:administrative-district:"
                    f"{district_number:02d}"
                ),
                "source_id": SOURCE_ID,
                "record_kind": "judicial_administrative_district_directory",
                "directory_component": DISTRICT_COMPONENT,
                "snapshot_only": True,
                "district_number": district_number,
                "district_label": district_label,
                "counties": counties,
                "county_geoids": [COUNTY_FIPS[county] for county in counties],
                "chief_and_deputy_judges": officers,
                "district_court_administrator": administrator_lines,
                "administrator_phone": phone,
                "map_routes": _links(cells[0], source_url),
                "source_url": source_url,
                "provenance": {
                    "authority": AUTHORITY,
                    "response_schema_fingerprint": schema_fingerprint,
                    "personnel_and_office_snapshot": True,
                },
            }
        )
    district_numbers = [int(record["district_number"]) for record in records]
    if len(district_numbers) != len(set(district_numbers)):
        raise WisconsinCourtDirectoryChangedError(
            "duplicate_districts",
            "Wisconsin administrative district table repeats a district",
        )
    observed_counties = {
        county for record in records for county in record["counties"]
    }
    if require_complete and (
        set(district_numbers) != set(DISTRICT_WORDS.values())
        or observed_counties != set(COUNTY_FIPS)
    ):
        raise WisconsinCourtDirectoryChangedError(
            "administrative_district_coverage_changed",
            "Wisconsin administrative district coverage changed",
            details={
                "expected_districts": sorted(DISTRICT_WORDS.values()),
                "observed_districts": sorted(district_numbers),
                "missing_counties": sorted(set(COUNTY_FIPS) - observed_counties),
                "unexpected_counties": sorted(
                    observed_counties - set(COUNTY_FIPS)
                ),
            },
        )
    return _finish_page(
        DISTRICT_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={
            "district_count": len(records),
            "county_count": len(observed_counties),
            "district_numbers": sorted(district_numbers),
        },
    )


def _contact_rows(table: Any, source_url: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        entry: dict[str, Any] = {
            "label": _text(cells[0].get_text(" ", strip=True)),
            "value": (
                _text(cells[1].get_text(" ", strip=True))
                if len(cells) > 1
                else None
            ),
        }
        links = _links(row, source_url)
        if links:
            entry["links"] = links
        entries.append(entry)
    return entries


def _legacy_sections(
    html_text: str,
    *,
    component: str,
    source_url: str,
) -> tuple[list[dict[str, Any]], str]:
    lower = html_text.casefold()
    if any(marker in lower for marker in _CHALLENGE_MARKERS):
        raise WisconsinCourtDirectoryError(
            "challenge_page",
            f"Wisconsin {component} directory returned an interstitial",
            status=ResultStatus.RESTRICTED,
            category="access",
        )
    soup = BeautifulSoup(html_text, "html.parser")
    content = soup.select_one("div.content")
    if content is None:
        raise WisconsinCourtDirectoryChangedError(
            "legacy_directory_content_missing",
            f"Wisconsin {component} directory lacks its content container",
        )
    markers = [
        anchor
        for anchor in content.find_all("a", id=True, recursive=False)
        if anchor.find("h2", recursive=False) is not None
    ]
    if not markers:
        raise WisconsinCourtDirectoryChangedError(
            "legacy_directory_sections_missing",
            f"Wisconsin {component} directory has no named sections",
        )
    sections: list[dict[str, Any]] = []
    observed_block_types: set[str] = set()
    for marker in markers:
        heading = _text(
            marker.find("h2", recursive=False).get_text(" ", strip=True)
        )
        locations: list[dict[str, Any]] = []
        contact_groups: list[dict[str, Any]] = []
        paragraphs: list[str] = []
        section_links: list[dict[str, str | None]] = []
        current_location: dict[str, Any] | None = None
        node = marker.next_sibling
        while node is not None:
            node_name = getattr(node, "name", None)
            if (
                node_name == "a"
                and node.get("id")
                and node.find("h2", recursive=False) is not None
            ):
                break
            if node_name == "p":
                classes = set(node.get("class", []))
                lines = _element_lines(node)
                if "address" in classes:
                    current_location = {
                        "address_lines": lines,
                        "published_contacts": [],
                    }
                    locations.append(current_location)
                    observed_block_types.add("address")
                elif lines:
                    paragraphs.extend(lines)
                    observed_block_types.add("paragraph")
            elif node_name == "table" and "location_contact_table" in set(
                node.get("class", [])
            ):
                contacts = _contact_rows(node, source_url)
                if current_location is None:
                    current_location = {
                        "address_lines": [],
                        "published_contacts": [],
                    }
                    locations.append(current_location)
                current_location["published_contacts"].extend(contacts)
                observed_block_types.add("location_contact_table")
            elif node_name == "div" and "groups_container" in set(
                node.get("class", [])
            ):
                location_index = len(locations) - 1 if locations else None
                for table in node.select("table.group_contact_table"):
                    entries = _contact_rows(table, source_url)
                    if entries:
                        contact_groups.append(
                            {
                                "location_index": location_index,
                                "entries": entries,
                            }
                        )
                observed_block_types.add("groups_container")
            if node_name is not None:
                section_links.extend(_links(node, source_url))
            node = node.next_sibling
        deduplicated_links: list[dict[str, str | None]] = []
        seen_links: set[tuple[str | None, str | None]] = set()
        for link in section_links:
            identity = (link["label"], link["url"])
            if identity not in seen_links:
                seen_links.add(identity)
                deduplicated_links.append(link)
        sections.append(
            {
                "heading": heading,
                "source_anchor": str(marker.get("id")),
                "locations": locations,
                "contact_groups": contact_groups,
                "paragraphs": paragraphs,
                "links": deduplicated_links,
            }
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "component": component,
            "container": "div.content",
            "section_marker": "a[id]>h2",
            "block_types": sorted(observed_block_types),
        }
    )
    return sections, schema_fingerprint


def parse_circuit_courts_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[CIRCUIT_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse county circuit-court locations and published personnel groups."""

    sections, schema_fingerprint = _legacy_sections(
        html_text,
        component=CIRCUIT_COMPONENT,
        source_url=source_url,
    )
    records: list[dict[str, Any]] = []
    for section in sections:
        heading = str(section["heading"] or "")
        county = _canonical_county(heading)
        districts = sorted(
            {
                int(match.group(1))
                for location in section["locations"]
                for line in location["address_lines"]
                if (match := _DISTRICT_RE.search(line))
            }
        )
        record = _county_record_base(
            component=CIRCUIT_COMPONENT,
            record_kind="circuit_court_office_directory",
            county=county,
            source_url=source_url,
            schema_fingerprint=schema_fingerprint,
        )
        record.update(
            {
                "judicial_districts": districts,
                "office_locations": section["locations"],
                "personnel_groups": section["contact_groups"],
                "published_notes": section["paragraphs"],
                "published_links": section["links"],
                "source_anchor": section["source_anchor"],
            }
        )
        records.append(record)
    _validate_county_records(
        records,
        component=CIRCUIT_COMPONENT,
        require_complete=require_complete,
    )
    return _finish_page(
        CIRCUIT_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={
            "county_count": len(records),
            "county_geoids": [record["county_geoid"] for record in records],
            "location_count": sum(
                len(record["office_locations"]) for record in records
            ),
            "personnel_group_count": sum(
                len(record["personnel_groups"]) for record in records
            ),
        },
    )


def parse_court_of_appeals_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[APPEALS_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse appellate clerk, district, judge, and staff office sections."""

    sections, schema_fingerprint = _legacy_sections(
        html_text,
        component=APPEALS_COMPONENT,
        source_url=source_url,
    )
    records: list[dict[str, Any]] = []
    district_counties: set[str] = set()
    for section in sections:
        heading = str(section["heading"] or "")
        match = _APPEALS_DISTRICT_RE.match(heading)
        district_number = None
        counties: list[str] = []
        if match:
            district_number = ROMAN_DISTRICTS.get(match.group(1).upper())
            if district_number is None:
                raise WisconsinCourtDirectoryChangedError(
                    "appellate_district_identifier_changed",
                    f"Unknown Court of Appeals district in {heading!r}",
                )
            counties = _parse_county_list(match.group(2))
            district_counties.update(counties)
        native_id = (
            f"district-{district_number}"
            if district_number is not None
            else _slug(heading)
        )
        records.append(
            {
                "canonical_ref": (
                    f"WI-COURT-DIRECTORY:{APPEALS_COMPONENT}:{native_id}"
                ),
                "source_id": SOURCE_ID,
                "record_kind": "appellate_court_office_directory",
                "directory_component": APPEALS_COMPONENT,
                "snapshot_only": True,
                "section_name": heading,
                "district_number": district_number,
                "counties": counties,
                "county_geoids": [COUNTY_FIPS[county] for county in counties],
                "court_id": (
                    f"wi-court-of-appeals-district-{district_number}"
                    if district_number is not None
                    else "wi-court-of-appeals"
                ),
                "office_locations": section["locations"],
                "personnel_groups": section["contact_groups"],
                "published_notes": section["paragraphs"],
                "published_links": section["links"],
                "source_anchor": section["source_anchor"],
                "source_url": source_url,
                "provenance": {
                    "authority": AUTHORITY,
                    "response_schema_fingerprint": schema_fingerprint,
                    "personnel_and_office_snapshot": True,
                },
            }
        )
    district_numbers = {
        int(record["district_number"])
        for record in records
        if record["district_number"] is not None
    }
    expected_sections = {
        "Clerk of Court of Appeals",
        "Court of Appeals - Staff Attorneys",
    }
    observed_sections = {str(record["section_name"]) for record in records}
    if require_complete and (
        district_numbers != set(ROMAN_DISTRICTS.values())
        or district_counties != set(COUNTY_FIPS)
        or not expected_sections.issubset(observed_sections)
    ):
        raise WisconsinCourtDirectoryChangedError(
            "appellate_directory_coverage_changed",
            "Wisconsin Court of Appeals directory coverage changed",
            details={
                "observed_districts": sorted(district_numbers),
                "missing_counties": sorted(
                    set(COUNTY_FIPS) - district_counties
                ),
                "missing_sections": sorted(
                    expected_sections - observed_sections
                ),
            },
        )
    return _finish_page(
        APPEALS_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={
            "section_count": len(records),
            "district_count": len(district_numbers),
            "county_count": len(district_counties),
        },
    )


def parse_state_offices_page(
    html_text: str,
    *,
    source_url: str = COMPONENT_DEFINITIONS[STATE_OFFICE_COMPONENT]["url"],
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Parse Supreme Court and statewide administrative office sections."""

    sections, schema_fingerprint = _legacy_sections(
        html_text,
        component=STATE_OFFICE_COMPONENT,
        source_url=source_url,
    )
    records: list[dict[str, Any]] = []
    for section in sections:
        heading = str(section["heading"] or "")
        records.append(
            {
                "canonical_ref": (
                    f"WI-COURT-DIRECTORY:{STATE_OFFICE_COMPONENT}:{_slug(heading)}"
                ),
                "source_id": SOURCE_ID,
                "record_kind": "state_court_office_directory",
                "directory_component": STATE_OFFICE_COMPONENT,
                "snapshot_only": True,
                "section_name": heading,
                "office_locations": section["locations"],
                "personnel_groups": section["contact_groups"],
                "published_notes": section["paragraphs"],
                "published_links": section["links"],
                "source_anchor": section["source_anchor"],
                "source_url": source_url,
                "provenance": {
                    "authority": AUTHORITY,
                    "response_schema_fingerprint": schema_fingerprint,
                    "personnel_and_office_snapshot": True,
                },
            }
        )
    required_sections = {
        "Office of Justices",
        "Director of State Courts",
        "Clerk of Supreme Court",
    }
    observed_sections = {str(record["section_name"]) for record in records}
    if require_complete and (
        len(records) < 10
        or not required_sections.issubset(observed_sections)
    ):
        raise WisconsinCourtDirectoryChangedError(
            "state_office_directory_coverage_changed",
            "Wisconsin Supreme Court/state office directory coverage changed",
            details={
                "observed_count": len(records),
                "missing_sections": sorted(
                    required_sections - observed_sections
                ),
            },
        )
    return _finish_page(
        STATE_OFFICE_COMPONENT,
        records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        coverage={"section_count": len(records)},
    )


def parse_component_page(
    component: str,
    html_text: str,
    *,
    source_url: str | None = None,
    require_complete: bool = True,
) -> WisconsinDirectoryPage:
    """Dispatch one verified official page to its component parser."""

    if component not in COMPONENT_DEFINITIONS:
        raise ValueError(f"unknown Wisconsin directory component: {component}")
    resolved_url = source_url or COMPONENT_DEFINITIONS[component]["url"]
    if component == CIRCUIT_COMPONENT:
        return parse_circuit_courts_page(
            html_text,
            source_url=resolved_url,
            require_complete=require_complete,
        )
    if component == CLERK_COMPONENT:
        return parse_clerks_page(
            html_text,
            source_url=resolved_url,
            require_complete=require_complete,
        )
    if component == JUDGE_COMPONENT:
        return parse_judges_page(
            html_text,
            source_url=resolved_url,
            require_complete=require_complete,
        )
    if component == DISTRICT_COMPONENT:
        return parse_administrative_districts_page(
            html_text,
            source_url=resolved_url,
            require_complete=require_complete,
        )
    if component == APPEALS_COMPONENT:
        return parse_court_of_appeals_page(
            html_text,
            source_url=resolved_url,
            require_complete=require_complete,
        )
    return parse_state_offices_page(
        html_text,
        source_url=resolved_url,
        require_complete=require_complete,
    )


class WisconsinCourtDirectoryClient:
    """Paced, retrying anonymous client for the official directory pages."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.5",
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def fetch(self, component: str) -> WisconsinDirectoryPage:
        if component not in COMPONENT_DEFINITIONS:
            raise ValueError(
                f"unknown Wisconsin directory component: {component}"
            )
        url = COMPONENT_DEFINITIONS[component]["url"]
        response = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise WisconsinCourtDirectoryError(
                        "transport_error",
                        (
                            f"Wisconsin {component} directory request failed: "
                            f"{error}"
                        ),
                        category="transport",
                        retryable=True,
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 200:
                break
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise WisconsinCourtDirectoryError(
                    "rate_limited",
                    f"Wisconsin {component} directory returned HTTP 429",
                    status=ResultStatus.RATE_LIMITED,
                    category="transport",
                    retryable=True,
                )
            if status_code in {401, 403}:
                raise WisconsinCourtDirectoryError(
                    "access_response",
                    (
                        f"Wisconsin {component} directory returned "
                        f"HTTP {status_code}"
                    ),
                    status=ResultStatus.RESTRICTED,
                    category="access",
                )
            raise WisconsinCourtDirectoryError(
                "http_error",
                (
                    f"Wisconsin {component} directory returned "
                    f"HTTP {status_code}"
                ),
                category="transport",
                details={"status_code": status_code},
            )
        if response is None:
            raise AssertionError("directory request ended without a response")
        final_url = str(getattr(response, "url", url))
        return parse_component_page(
            component,
            str(response.text),
            source_url=final_url,
            require_complete=True,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def source_routes() -> tuple[dict[str, Any], ...]:
    """Return parsed components and complementary official directory routes."""

    parsed = [
        {
            "canonical_ref": f"WI-COURT-DIRECTORY-ROUTE:{component}",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": component,
            "route_kind": "parsed_html_directory_component",
            "name": definition["name"],
            "official_url": definition["url"],
            "function": definition["function"],
            "machine_query_status": "implemented",
            "record_role": definition["record_kind"],
        }
        for component, definition in COMPONENT_DEFINITIONS.items()
    ]
    complementary = [
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:landing",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "directory-landing",
            "route_kind": "publisher_directory_index",
            "name": "Wisconsin Court System directories",
            "official_url": DIRECTORIES_URL,
            "function": "Publisher index for court-system directory products",
            "machine_query_status": "mapped",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:employees",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "alphabetical-employee-listing",
            "route_kind": "complementary_personnel_directory",
            "name": "Alphabetical employee listing",
            "official_url": f"{BASE_URL}/contact/Alpha.html",
            "function": (
                "Alphabetical state court-system employee contacts across "
                "office boundaries"
            ),
            "machine_query_status": "mapped",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:municipal-pdf",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "municipal-court-directory-pdf",
            "route_kind": "complementary_municipal_court_directory",
            "name": "Wisconsin municipal court directory",
            "official_url": f"{BASE_URL}/contact/docs/muni.pdf",
            "function": (
                "Downloadable municipal court, judge, clerk, address, and "
                "contact directory"
            ),
            "machine_query_status": "mapped_pdf",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:juror-contacts",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "county-juror-contacts",
            "route_kind": "complementary_county_contact_directory",
            "name": "County juror contacts",
            "official_url": f"{BASE_URL}/services/juror/contacts.htm",
            "function": (
                "County jury-service contacts and local court website routes"
            ),
            "machine_query_status": "mapped",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:wcca",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "wcca-circuit-case-search",
            "route_kind": "complementary_case_index",
            "related_source_id": "us-wi-wcca-public",
            "name": "Wisconsin Circuit Court Access",
            "official_url": "https://wcca.wicourts.gov/",
            "function": "Statewide public circuit-court case search",
            "machine_query_status": "separate_source",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:wscca",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "wscca-appellate-case-search",
            "route_kind": "complementary_case_index",
            "related_source_id": "us-wi-wscca-public",
            "name": "Wisconsin Supreme Court and Court of Appeals Case Access",
            "official_url": "https://wscca.wicourts.gov/",
            "function": "Public appellate case search and case detail",
            "machine_query_status": "separate_source",
        },
        {
            "canonical_ref": "WI-COURT-DIRECTORY-ROUTE:opinions",
            "source_id": SOURCE_ID,
            "record_kind": "official_directory_route",
            "route_id": "appellate-opinions",
            "route_kind": "complementary_opinion_corpus",
            "related_source_id": "us-wi-court-opinions",
            "name": "Wisconsin appellate opinions and orders",
            "official_url": f"{BASE_URL}/opinions/",
            "function": "Official appellate opinion, order, and disposition corpus",
            "machine_query_status": "separate_source",
        },
    ]
    return tuple(parsed + complementary)


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": "WI-COURT-DIRECTORY-SOURCE",
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "name": SOURCE_METADATA.name,
        "authority": AUTHORITY,
        "official_url": DIRECTORIES_URL,
        "parsed_components": [
            {
                "component": component,
                "record_kind": COMPONENT_DEFINITIONS[component]["record_kind"],
                "function": COMPONENT_DEFINITIONS[component]["function"],
            }
            for component in COMPONENTS
        ],
        "coverage": {
            "state_geoid": STATE_GEOID,
            "county_count": len(COUNTY_FIPS),
            "county_geoids": list(COUNTY_FIPS.values()),
        },
        "operations": [
            "sources",
            "routes",
            "list",
            "county",
            "search",
            "discovery",
            "probe",
        ],
        "ingestion_mode": "snapshot_only",
        "case_index": False,
    }


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters = {
        "query": getattr(args, "query", None),
        "county": getattr(args, "county", None),
        "components": list(getattr(args, "components", ()) or ()),
    }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
        ),
    )


def _requested_components(args: argparse.Namespace) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(getattr(args, "components", ()) or ()))
    if selected:
        return selected
    if args.command == "discovery":
        return (CLERK_COMPONENT, JUDGE_COMPONENT)
    return COMPONENTS


def _record_matches_county(record: Mapping[str, Any], county: str) -> bool:
    if record.get("county") == county:
        return True
    for field_name in ("counties", "assigned_counties"):
        counties = record.get(field_name)
        if isinstance(counties, (list, tuple)) and county in counties:
            return True
    return False


def _select_records(
    records: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> tuple[list[Mapping[str, Any]], int]:
    county_selector = getattr(args, "county", None)
    county = (
        resolve_county_selector(county_selector)
        if county_selector is not None
        else None
    )
    query_text = _text(getattr(args, "query", None))
    query_key = (
        None
        if query_text is None or query_text.casefold() in {"*", "all"}
        else query_text.casefold()
    )
    selected: list[Mapping[str, Any]] = []
    for record in records:
        if county is not None and not _record_matches_county(record, county):
            continue
        if query_key is not None and query_key not in canonical_json(record).casefold():
            continue
        selected.append(record)
    unbounded_count = len(selected)
    limit = getattr(args, "limit", None)
    if limit is not None:
        selected = selected[:limit]
    return selected, unbounded_count


def _discovery_candidates(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        routes = record.get("website_routes")
        if not isinstance(routes, (list, tuple)):
            continue
        for route in routes:
            if not isinstance(route, Mapping) or not route.get("url"):
                continue
            identity = {
                "directory_component": record["directory_component"],
                "county_geoid": record["county_geoid"],
                "candidate_url": route["url"],
            }
            candidates.append(
                {
                    "canonical_ref": (
                        "WI-COURT-DISCOVERY:"
                        + sha256_fingerprint(identity)
                    ),
                    "source_id": SOURCE_ID,
                    "record_kind": "source_discovery_candidate",
                    "candidate_kind": "official_county_court_website",
                    "candidate_url": route["url"],
                    "candidate_label": route.get("label"),
                    "county": record["county"],
                    "county_geoid": record["county_geoid"],
                    "court_id": record["court_id"],
                    "directory_component": record["directory_component"],
                    "source_record_ref": record["canonical_ref"],
                    "assessment_fields": [
                        "case_search",
                        "calendars",
                        "registers_dockets",
                        "opinions_orders",
                        "document_images",
                        "copy_request_routes",
                        "bulk_products",
                        "vendor_family",
                    ],
                    "infra_request_created": False,
                }
            )
    return candidates


def _probe_record(
    pages: Sequence[WisconsinDirectoryPage],
    *,
    requested_components: Sequence[str],
) -> dict[str, Any]:
    by_component = {page.component: page for page in pages}
    component_results: dict[str, Any] = {}
    for component in requested_components:
        page = by_component.get(component)
        if page is None:
            component_results[component] = {"status": "unavailable"}
            continue
        component_results[component] = {
            "status": "ok",
            "record_count": len(page.records),
            "coverage": dict(page.coverage),
            "schema_fingerprint": page.schema_fingerprint,
            "snapshot_fingerprint": page.snapshot_fingerprint,
            "source_url": page.source_url,
        }
    return {
        "canonical_ref": "WI-COURT-DIRECTORY-PROBE",
        "source_id": SOURCE_ID,
        "record_kind": "source_probe",
        "official_url": DIRECTORIES_URL,
        "component_count": len(pages),
        "record_count": sum(len(page.records) for page in pages),
        "components": component_results,
        "county_coverage": {
            "expected_count": len(COUNTY_FIPS),
            "county_geoids": list(COUNTY_FIPS.values()),
            "complete_components": sorted(
                page.component
                for page in pages
                if page.component in COUNTY_COMPONENTS
                and set(page.coverage.get("county_geoids", ()))
                == set(COUNTY_FIPS.values())
            ),
        },
        "snapshot_only": True,
    }


def _result_with_errors(
    query: PublicRecordsQuery,
    records: Sequence[Mapping[str, Any]],
    *,
    pages: Sequence[WisconsinDirectoryPage],
    errors: Sequence[PublicRecordsError],
    warnings: Sequence[str],
) -> PublicRecordsResult:
    artifact_refs = [page.source_url for page in pages]
    if errors:
        status = (
            ResultStatus.PARTIAL
            if pages
            else ResultStatus.UNAVAILABLE
        )
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            raw_artifact_refs=artifact_refs,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        raw_artifact_refs=artifact_refs,
        warnings=warnings,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: WisconsinCourtDirectoryClient | Any | None = None,
    log_results: bool = True,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    """Execute one direct directory operation."""

    del access_decision
    query = _query(args)
    if args.command == "sources":
        result = PublicRecordsResult.success(
            query,
            [_source_record()],
            warnings=SOURCE_WARNINGS,
        )
    elif args.command == "routes":
        result = PublicRecordsResult.success(
            query,
            source_routes(),
            warnings=SOURCE_WARNINGS,
        )
    else:
        own_client = client is None
        source_client = client or WisconsinCourtDirectoryClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(
                max_attempts=args.max_attempts,
                backoff_initial=args.retry_backoff,
            ),
        )
        pages: list[WisconsinDirectoryPage] = []
        errors: list[PublicRecordsError] = []
        components = _requested_components(args)
        try:
            for component in components:
                try:
                    pages.append(source_client.fetch(component))
                except WisconsinCourtDirectoryError as error:
                    contract_error = error.to_contract_error()
                    errors.append(
                        PublicRecordsError(
                            code=contract_error.code,
                            message=contract_error.message,
                            category=contract_error.category,
                            retryable=contract_error.retryable,
                            details={
                                **dict(contract_error.details),
                                "component": component,
                            },
                        )
                    )
        finally:
            if own_client:
                source_client.close()
        records = [
            record for page in pages for record in page.records
        ]
        result_warnings = list(SOURCE_WARNINGS)
        if args.command == "probe":
            selected: list[Mapping[str, Any]] = [
                _probe_record(pages, requested_components=components)
            ]
        else:
            selected, unbounded_count = _select_records(records, args)
            if args.command == "discovery":
                selected = _discovery_candidates(selected)
                unbounded_count = len(selected)
                if args.limit is not None:
                    selected = selected[: args.limit]
            if args.limit is not None and unbounded_count > len(selected):
                result_warnings.append(
                    "The source snapshot was fetched completely; the returned "
                    f"selection was limited to {len(selected)} of "
                    f"{unbounded_count} matching records."
                )
        result = _result_with_errors(
            query,
            selected,
            pages=pages,
            errors=errors,
            warnings=result_warnings,
        )
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def _add_components(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--component",
        dest="components",
        choices=COMPONENTS,
        action="append",
        default=[],
        help=(
            "Select one directory component; repeat to combine components "
            "(default: all)"
        ),
    )


def _add_selection(parser: argparse.ArgumentParser) -> None:
    _add_components(parser)
    parser.add_argument("--county")
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional local result-window ceiling after complete page fetches",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Wisconsin's official court directory family"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe parsed coverage and snapshot semantics",
    )
    _add_runtime_and_output(sources)

    routes = subparsers.add_parser(
        "routes",
        help="List parsed components and complementary official routes",
    )
    _add_runtime_and_output(routes)

    listing = subparsers.add_parser(
        "list",
        help="List complete directory snapshots or selected components",
    )
    _add_selection(listing)
    _add_runtime_and_output(listing)

    county = subparsers.add_parser(
        "county",
        help="Combine records that cover one Wisconsin county",
    )
    county.add_argument("county")
    _add_components(county)
    county.add_argument("--limit", type=int)
    _add_runtime_and_output(county)

    search = subparsers.add_parser(
        "search",
        help="Search names, offices, counties, contacts, and routes",
    )
    search.add_argument("query")
    _add_selection(search)
    _add_runtime_and_output(search)

    discovery = subparsers.add_parser(
        "discovery",
        help="Emit official county court websites for capability assessment",
    )
    discovery.add_argument("--query")
    discovery.add_argument("--county")
    discovery.add_argument("--limit", type=int)
    _add_runtime_and_output(discovery)

    probe = subparsers.add_parser(
        "probe",
        help="Verify all six components and report exact observed coverage",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Wisconsin court directory {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Wisconsin court directory {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        print(
            "  "
            + str(
                record.get("county")
                or record.get("section_name")
                or record.get("district_label")
                or record.get("route_id")
                or record.get("record_kind")
                or "?"
            )
        )
    for error in result.errors:
        print(
            f"ERROR [{error.code}]: {error.message}",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(result, args)


if __name__ == "__main__":
    main()
