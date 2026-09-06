#!/usr/bin/env python3
"""Query the U.S. Virgin Islands Recorder of Deeds CountyFusion index.

This adapter follows the anonymous guest workflow linked by the Office of the
Lieutenant Governor.  It searches the source's native index, walks every native
result page, retrieves instrument detail, and can fetch one caller-selected PNG
page from the session-scoped image viewer.

Examples:
    uv run python tools/query_usvi_recorder.py search "SMITH" \
        --district "ST THOMAS" --date-from 2025-01-01 \
        --output /tmp/usvi-smith.json
    uv run python tools/query_usvi_recorder.py search \
        --document-number 2026000625 --district "ST THOMAS" --json
    uv run python tools/query_usvi_recorder.py document 2026000625 \
        --district "ST THOMAS" --inst-id 903442 --json
    uv run python tools/query_usvi_recorder.py page 2026000625 1 \
        --district "ST THOMAS" --inst-id 903442 /tmp/2026000625-1.png --json
    uv run python tools/query_usvi_recorder.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

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
    )
    from tools.public_records_store import canonical_property_ref
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
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-vi-recorder-of-deeds-countyfusion"
SOURCE = SOURCE_ID
TERRITORY_GEOID = "78"
STATE_CODE = "VI"
COUNTY_NAME = "U.S. Virgin Islands"
OBSERVED_AT = "2026-07-30"

BASE_URL = "https://countyfusion6.kofiletech.us"
ALLOWED_HOST = "countyfusion6.kofiletech.us"
COUNTYWEB = f"{BASE_URL}/countyweb"
LOGIN_DISPLAY_URL = f"{COUNTYWEB}/loginDisplay.action"
LOGIN_URL = f"{COUNTYWEB}/login.action"
DISCLAIMER_URL = f"{COUNTYWEB}/disclaimer.do"
SEARCH_MAIN_URL = f"{COUNTYWEB}/search/searchMain.do"
SEARCH_CRITERIA_URL = f"{COUNTYWEB}/search/searchCriteria.do"
DYNAMIC_CRITERIA_URL = f"{COUNTYWEB}/search/dyncriteria/dynCriteria.do"
SEARCH_EXECUTE_URL = f"{COUNTYWEB}/search/searchExecute.do"
SEARCH_RESULTS_URL = f"{COUNTYWEB}/search/searchResults.do"
RESULT_LIST_URL = (
    f"{COUNTYWEB}/search/USVI/docs_SearchResultList.jsp"
)
INSTRUMENT_TYPES_URL = (
    f"{COUNTYWEB}/search/getInstrumentCategories.do"
)
DOCUMENT_INFO_URL = f"{COUNTYWEB}/search/docInfoView.do"
DISPLAY_DOCUMENT_URL = f"{COUNTYWEB}/search/displayDocument.do"
DETAIL_PAGE_URL = f"{COUNTYWEB}/transaction/transAddDoc.do"
IMAGE_VIEWER_URL = f"{COUNTYWEB}/imageViewApplet.do"
IMAGE_PAGE_STATE_URL = f"{COUNTYWEB}/imageViewer/getPage.do"
IMAGE_PNG_URL = f"{COUNTYWEB}/viewImagePNG.do"

OFFICIAL_LINKING_PAGE = (
    "https://ltg.gov.vi/departments/recorder-of-deeds/"
)
CURRENT_PUBLICSEARCH_COMPLEMENT = "https://usvi.publicsearch.us/"
CAMA_COMPLEMENT = "https://usvi.capturecama.com/"

USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
TIMEOUT = 30.0
MINIMUM_INTERVAL = 0.2
MAX_ATTEMPTS = 3
RETRY_BACKOFF = 0.5

NATIVE_PAGE_SIZES = (10, 15, 20, 40, 60, 80, 100)
NATIVE_SEARCH_TYPES = (
    "allNames",
    "allNamesMultiple",
    "lbs",
    "fileNum",
    "docNum",
    "bookPage",
)
NATIVE_MULTIPLE_NAME_LIMIT = 10

PROBE_DISTRICT = "ST THOMAS"
PROBE_INST_ID = "903442"
PROBE_INSTRUMENT_NUMBER = "2026000625"
PROBE_INSTRUMENT_TYPE = "DEED"
PROBE_RECORDED_DATE = "2026-02-05"
PROBE_PAGE_COUNT = 6
PROBE_OBSERVED_PAGE_1_SHA256 = (
    "de7fafb8c6b441f45891d01917cc6b1d"
    "886cd849323c711b54fbfe89cda4b4f9"
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="U.S. Virgin Islands Recorder of Deeds CountyFusion",
    source_role="territorial_recorder_instrument_index_and_public_images",
    base_url=LOGIN_DISPLAY_URL,
    dataset_id="usvi-countyfusion-recorder-index",
    metadata={
        "authority": "U.S. Virgin Islands Recorder of Deeds",
        "official_linking_page": OFFICIAL_LINKING_PAGE,
        "territory_geoid": TERRITORY_GEOID,
        "platform_family": "kofile_countyfusion_legacy",
        "record_identity_key": "district_plus_inst_id",
        "native_districts": ["ST THOMAS", "ST CROIX"],
        "observed_at": OBSERVED_AT,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=TERRITORY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    locality=COUNTY_NAME,
    metadata={
        "district_identity_is_preserved": True,
    },
)

SOURCE_WARNINGS = (
    (
        "The Recorder states that online index data and images are reference "
        "material; only the official record and copies from the Recorder are "
        "official."
    ),
    (
        "The Recorder describes historical data from the 1800s through 1999 "
        "as a work in progress that may be incomplete or inaccurate."
    ),
    (
        "Instrument numbers and book/page values are lookup keys. Stable "
        "instrument identity uses the emitted district and source instId."
    ),
)

COMMON_FORM_FIELDS = {
    "searchCategory": "ADVANCED",
    "searchSessionId": "searchJobMain",
    "PLATS": "",
    "QUARTER": "",
    "RECSPERPAGE": "",
    "userRefCode": "",
    "INSTTYPEALL": "true",
    "INSTTYPE": "",
    "CASETYPE": "",
    "ORDERBY_LIST": "",
    "DATERANGE": "",
}

LEGAL_ARGUMENT_FIELDS = {
    "parcel": "LBS_LGL_ADDL_INDEX4",
    "qtr_condo": "LBS_LGL_ADDL_INDEX3",
    "estate": "LBS_LGL_ADDL_INDEX2",
    "building": "LBS_LGL_ADDL_INDEX6",
    "unit": "LBS_LGL_ADDL_INDEX7",
    "plot": "LBS_LGL_ADDL_INDEX5",
    "land_comment": "LBS_LGL_ADDL_INDEX1",
}

PARTY_VALUES = {
    "both": "both",
    "grantor": "7",
    "grantee": "6",
}

MATCH_FIELDS = {
    "exact": "EXACTNAMEMATCH",
    "alpha-numeric": "REMOVECHARACTERS",
    "similar": "SIMILAR",
    "surrounding": "SCROLLTONAME",
}


class USVIRecorderError(RuntimeError):
    """Base error for a source request, query, or parser failure."""


class USVIRecorderQueryError(USVIRecorderError):
    """The requested selector combination is not a native source form."""


class USVIRecorderSourceChanged(USVIRecorderError):
    """The returned portal no longer matches the verified source contract."""


class USVIRecorderTransportError(USVIRecorderError):
    """The source could not be reached after bounded transport retries."""


class USVIRecorderRateLimited(USVIRecorderError):
    """The source continued returning HTTP 429 after retries."""


class USVIRecorderHTTPError(USVIRecorderError):
    """The source returned a non-success HTTP response."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"USVI Recorder returned HTTP {status_code} for {url}")


class USVIRecorderPartialSearch(USVIRecorderError):
    """A native pagination failure after at least one page was retrieved."""

    def __init__(
        self,
        message: str,
        *,
        records: Sequence[Mapping[str, Any]],
        cause: USVIRecorderError,
    ) -> None:
        self.records = [dict(record) for record in records]
        self.cause = cause
        super().__init__(message)


@dataclass(frozen=True)
class NativeSearchPage:
    """Source pagination state parsed from SearchResultsView.jsp."""

    no_results: bool
    total_count: int
    page_count: int
    result_list_size: int
    start_cursor: int
    sort_column: str
    sort_direction: str
    list_url: str | None
    display_message: str | None


@dataclass(frozen=True)
class PageImage:
    """One verified image-viewer response."""

    page_number: int
    page_count: int
    source_url: str
    media_type: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _unique(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = _text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _iso_date(value: Any) -> str | None:
    normalized = _text(value)
    if not normalized:
        return None
    for date_format in (
        "%m/%d/%Y",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _source_date(value: str | None, option: str) -> str:
    normalized = _text(value)
    if not normalized:
        return ""
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(normalized, date_format)
            return parsed.strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise USVIRecorderQueryError(
        f"{option} must be YYYY-MM-DD or MM/DD/YYYY"
    )


def normalize_district(value: str | None) -> str | None:
    """Return one of the two district labels emitted by the source."""

    normalized = _text(value)
    if not normalized:
        return None
    key = re.sub(r"[^A-Z]", "", normalized.upper())
    aliases = {
        "STTHOMAS": "ST THOMAS",
        "SAINTTHOMAS": "ST THOMAS",
        "STJOHN": "ST THOMAS",
        "SAINTJOHN": "ST THOMAS",
        "STCROIX": "ST CROIX",
        "SAINTCROIX": "ST CROIX",
    }
    district = aliases.get(key)
    if district is None:
        raise USVIRecorderQueryError(
            "district must identify the source's ST THOMAS or ST CROIX index"
        )
    return district


def native_instrument_identity(district: str, inst_id: str | int) -> str:
    normalized_district = normalize_district(district)
    normalized_inst_id = _text(inst_id)
    if normalized_district is None or normalized_inst_id is None:
        raise USVIRecorderSourceChanged(
            "instrument identity requires an emitted district and instId"
        )
    return f"{normalized_district}:{normalized_inst_id}"


def instrument_ref(district: str, inst_id: str | int) -> str:
    return canonical_property_ref(
        SOURCE_ID,
        TERRITORY_GEOID,
        "instrument",
        native_instrument_identity(district, inst_id),
    )


def _js_scalar(html: str, field: str, pattern: str) -> str:
    match = re.search(
        rf"searchResultObj\.{re.escape(field)}\s*=\s*({pattern})\s*;",
        html,
    )
    if match is None:
        raise USVIRecorderSourceChanged(
            f"search results no longer emit {field}"
        )
    return match.group(1)


def parse_search_page(html: str, *, source_url: str = SEARCH_RESULTS_URL) -> NativeSearchPage:
    """Parse authoritative count, no-result state, and native paging fields."""

    no_results = _js_scalar(html, "noResults", r"true|false") == "true"
    page_count = int(_js_scalar(html, "numRecordPages", r"\d+"))
    result_list_size = int(_js_scalar(html, "resultListSize", r"\d+"))
    total_count = int(_js_scalar(html, "resultsCount", r"\d+"))
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", attrs={"name": "resultForm"})
    if not isinstance(form, Tag):
        raise USVIRecorderSourceChanged(
            "search results no longer contain resultForm"
        )

    def hidden(name: str) -> str:
        element = form.find("input", attrs={"name": name})
        value = element.get("value") if isinstance(element, Tag) else None
        return str(value) if value is not None else ""

    raw_cursor = hidden("startCursor")
    if no_results:
        start_cursor = 0
    elif not re.fullmatch(r"\d+", raw_cursor):
        raise USVIRecorderSourceChanged(
            "non-empty results do not expose a numeric startCursor"
        )
    else:
        start_cursor = int(raw_cursor)

    iframe = soup.find("iframe", id="resultListFrame")
    list_url = None
    if isinstance(iframe, Tag) and iframe.get("src"):
        list_url = urljoin(source_url, str(iframe["src"]))
    display_match = re.search(
        r'Displaying\s+(\d+)\\?-(\d+)\s+of\s+(\d+)\s+Items',
        html,
        flags=re.IGNORECASE,
    )
    display_message = (
        f"Displaying {display_match.group(1)}-{display_match.group(2)} "
        f"of {display_match.group(3)} Items"
        if display_match
        else None
    )

    if no_results:
        message_present = (
            "No documents were found that match the specified criteria."
            in soup.get_text(" ", strip=True)
        )
        if (
            total_count != 0
            or page_count != 0
            or result_list_size != 0
            or not message_present
        ):
            raise USVIRecorderSourceChanged(
                "source no-result state is internally inconsistent"
            )
    elif (
        total_count <= 0
        or page_count <= 0
        or result_list_size <= 0
        or list_url is None
    ):
        raise USVIRecorderSourceChanged(
            "source non-empty result state is internally inconsistent"
        )

    return NativeSearchPage(
        no_results=no_results,
        total_count=total_count,
        page_count=page_count,
        result_list_size=result_list_size,
        start_cursor=start_cursor,
        sort_column=hidden("sortColumn"),
        sort_direction=hidden("sortDirection"),
        list_url=list_url,
        display_message=display_message,
    )


def _result_js_rows(html: str) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for match in re.finditer(
        r"documentRowInfo\[(?P<index>\d+)\]\."
        r"(?P<field>instId|instNum|instType|cursorPosition)"
        r"\s*=\s*(?:\"(?P<quoted>[^\"]*)\"|(?P<number>\d+))\s*;",
        html,
    ):
        index = int(match.group("index"))
        rows.setdefault(index, {})[match.group("field")] = (
            match.group("quoted")
            if match.group("quoted") is not None
            else match.group("number")
        )
    return rows


def _cell_names(cell: Tag) -> list[str]:
    titled = cell.find("span", title=True)
    if isinstance(titled, Tag):
        title = _text(titled.get("title"))
        if title:
            return _unique(part.strip() for part in title.split("::"))
        visible = _text(titled.get_text(" ", strip=True))
        if visible:
            return [visible]
    return _unique([cell.get_text(" ", strip=True)])


def parse_result_list(
    html: str,
    *,
    page_number: int,
    start_cursor: int,
) -> list[dict[str, Any]]:
    """Normalize one source result-list iframe."""

    soup = BeautifulSoup(html, "html.parser")
    js_rows = _result_js_rows(html)
    records: list[dict[str, Any]] = []
    source_rows = [
        row
        for row in soup.find_all("tr")
        if row.find("input", attrs={"name": "navCB"}) is not None
    ]
    if len(source_rows) != len(js_rows):
        raise USVIRecorderSourceChanged(
            "result row HTML and documentRowInfo metadata disagree"
        )

    for local_index, row in enumerate(source_rows):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 16:
            raise USVIRecorderSourceChanged(
                f"result row {local_index} has {len(cells)} columns; expected at least 16"
            )
        js = js_rows.get(local_index)
        if js is None or not {"instId", "instNum", "instType", "cursorPosition"} <= js.keys():
            raise USVIRecorderSourceChanged(
                f"result row {local_index} lacks complete documentRowInfo"
            )
        checkbox = cells[0].find("input", attrs={"name": "navCB"})
        checkbox_id = (
            _text(checkbox.get("value"))
            if isinstance(checkbox, Tag)
            else None
        )
        document_number = _text(cells[1].get_text(" ", strip=True))
        if checkbox_id != js["instId"] or document_number != js["instNum"]:
            raise USVIRecorderSourceChanged(
                f"result row {local_index} selector metadata does not match its cells"
            )

        party_1_type = _text(cells[2].get_text(" ", strip=True))
        party_1_names = _cell_names(cells[3])
        party_2_type = _text(cells[4].get_text(" ", strip=True))
        party_2_names = _cell_names(cells[5])
        instrument_type = _text(cells[6].get_text(" ", strip=True))
        if instrument_type != _text(js["instType"]):
            raise USVIRecorderSourceChanged(
                f"result row {local_index} instrument type disagrees with documentRowInfo"
            )
        recording_date_raw = _text(cells[7].get_text(" ", strip=True))
        district = normalize_district(cells[14].get_text(" ", strip=True))
        if district is None:
            raise USVIRecorderSourceChanged(
                f"result row {local_index} does not emit a district"
            )
        verified_image = cells[15].find("img")
        verified_src = (
            str(verified_image.get("src", ""))
            if isinstance(verified_image, Tag)
            else ""
        )
        verified = (
            True
            if "verified" in verified_src.casefold()
            and "unverified" not in verified_src.casefold()
            else False
            if "unverified" in verified_src.casefold()
            else None
        )
        inst_id = js["instId"]
        native_id = native_instrument_identity(district, inst_id)
        canonical_ref = instrument_ref(district, inst_id)
        parties = [
            {
                "name": name,
                "role": "grantor",
                "native_role": "Party 1",
                "native_name_type": party_1_type,
            }
            for name in party_1_names
        ] + [
            {
                "name": name,
                "role": "grantee",
                "native_role": "Party 2",
                "native_name_type": party_2_type,
            }
            for name in party_2_names
        ]
        legal = {
            "parcel": _text(cells[8].get_text(" ", strip=True)),
            "estate": _text(cells[9].get_text(" ", strip=True)),
            "qtr_condo": _text(cells[10].get_text(" ", strip=True)),
            "unit": _text(cells[11].get_text(" ", strip=True)),
            "building": _text(cells[12].get_text(" ", strip=True)),
            "plot": _text(cells[13].get_text(" ", strip=True)),
        }
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "recorded_instrument",
                "record_scope": "recorder_index_metadata",
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "native_document_id": native_id,
                "native_inst_id": inst_id,
                "district": district,
                "instrument_number": document_number,
                "document_number": document_number,
                "instrument_type": instrument_type,
                "recording_date": _iso_date(recording_date_raw),
                "recording_date_raw": recording_date_raw,
                "party_1_name_type": party_1_type,
                "party_1_names": party_1_names,
                "party_2_name_type": party_2_type,
                "party_2_names": party_2_names,
                "grantors": party_1_names,
                "grantees": party_2_names,
                "parties": parties,
                "legal": legal,
                "parcel_ids": [legal["parcel"]] if legal["parcel"] else [],
                "verified_index_row": verified,
                "source_locator": {
                    "district": district,
                    "inst_id": inst_id,
                    "instrument_number": document_number,
                    "instrument_type": instrument_type,
                    "search_session_id": "searchJobMain",
                },
                "source_position": {
                    "native_page_number": page_number,
                    "native_start_cursor": start_cursor,
                    "native_local_cursor": int(js["cursorPosition"]),
                    "absolute_offset": start_cursor + local_index,
                },
                "source_url": LOGIN_DISPLAY_URL,
                "jurisdiction": {
                    "geoid": TERRITORY_GEOID,
                    "name": COUNTY_NAME,
                    "state_code": STATE_CODE,
                    "district": district,
                },
                "raw": {
                    "result_cells": [
                        _text(cell.get_text(" ", strip=True))
                        for cell in cells[:16]
                    ],
                    "document_row_info": dict(js),
                },
            }
        )
    return records


def _field_after_label(soup: BeautifulSoup, element_id: str) -> str | None:
    label = soup.find(id=element_id)
    if not isinstance(label, Tag):
        raise USVIRecorderSourceChanged(
            f"instrument detail no longer emits {element_id}"
        )
    label_cell = label.find_parent("td")
    value_cell = (
        label_cell.find_next_sibling("td")
        if isinstance(label_cell, Tag)
        else None
    )
    if not isinstance(value_cell, Tag):
        raise USVIRecorderSourceChanged(
            f"instrument detail field {element_id} has no value cell"
        )
    return _text(value_cell.get_text(" ", strip=True))


def _party_section(soup: BeautifulSoup, header_id: str) -> list[str]:
    header = soup.find(id=header_id)
    if not isinstance(header, Tag):
        raise USVIRecorderSourceChanged(
            f"instrument detail no longer emits party section {header_id}"
        )
    heading_table = header.find_parent("table")
    if not isinstance(heading_table, Tag):
        raise USVIRecorderSourceChanged(
            f"party section {header_id} has no table"
        )
    names_table = heading_table.find_next_sibling("table")
    if not isinstance(names_table, Tag):
        raise USVIRecorderSourceChanged(
            f"party section {header_id} has no values"
        )
    return _unique(
        row.get_text(" ", strip=True)
        for row in names_table.find_all("tr", class_="evenrow")
    )


def _parse_legal_text(value: str) -> dict[str, Any]:
    cleaned = re.sub(r"^\s*\d+\.\s*", "", value).strip()
    labels = {
        "PARCEL": "parcel",
        "QTR CONDO": "qtr_condo",
        "ESTATE": "estate",
        "BUILDING": "building",
        "BLDG": "building",
        "UNIT": "unit",
        "PLOT": "plot",
        "LAND COMMENT": "land_comment",
    }
    components: dict[str, str] = {}
    marker = "|".join(re.escape(label) for label in labels)
    matches = list(
        re.finditer(
            rf"\b(?P<label>{marker})\s*:\s*",
            cleaned,
            flags=re.IGNORECASE,
        )
    )
    description_end = matches[0].start() if matches else len(cleaned)
    description = _text(cleaned[:description_end])
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        native_label = match.group("label").upper()
        component = _text(cleaned[match.end():end])
        if component:
            components[labels[native_label]] = component
    return {
        "description": description,
        "components": components,
        "raw": value,
    }


def parse_detail_page(html: str) -> dict[str, Any]:
    """Parse page one of a selected CountyFusion instrument."""

    soup = BeautifulSoup(html, "html.parser")
    tab_iframe = soup.find("iframe", id="tabs")
    tab_src = (
        str(tab_iframe.get("src"))
        if isinstance(tab_iframe, Tag) and tab_iframe.get("src")
        else ""
    )
    max_page_match = re.search(r"(?:[?&])maxpage=(\d+)", tab_src)
    if max_page_match is None:
        raise USVIRecorderSourceChanged(
            "instrument detail no longer emits its form-page count"
        )

    fields = {
        "document_type": _field_after_label(soup, "fc0span"),
        "description": _field_after_label(soup, "fc134span"),
        "district": _field_after_label(soup, "fc101span"),
        "document_number": _field_after_label(soup, "fc2span"),
        "recorded_date_raw": _field_after_label(soup, "fc1span"),
        "book_page_raw": _field_after_label(soup, "fc4span"),
        "instrument_date_raw": _field_after_label(soup, "fc107span"),
    }
    district = normalize_district(fields["district"])
    if district is None:
        raise USVIRecorderSourceChanged(
            "instrument detail does not contain a district"
        )
    party_1_names = _party_section(soup, "7header")
    party_2_names = _party_section(soup, "6header")

    legal_heading = next(
        (
            heading
            for heading in soup.find_all(["h2", "span"])
            if _text(heading.get_text(" ", strip=True)) == "Legal Description"
        ),
        None,
    )
    if not isinstance(legal_heading, Tag):
        raise USVIRecorderSourceChanged(
            "instrument detail no longer emits Legal Description"
        )
    legal_rows: list[dict[str, Any]] = []
    for cell in legal_heading.find_all_next("td", class_="basesm"):
        value = _text(cell.get_text(" ", strip=True))
        if value:
            legal_rows.append(_parse_legal_text(value))

    book = None
    page = None
    book_page_raw = fields["book_page_raw"]
    if book_page_raw:
        match = re.fullmatch(r"\s*([^/]*)\s*/\s*([^/]*)\s*", book_page_raw)
        if match:
            book = _text(match.group(1))
            page = _text(match.group(2))

    return {
        "document_type": fields["document_type"],
        "description": fields["description"],
        "district": district,
        "instrument_number": fields["document_number"],
        "document_number": fields["document_number"],
        "recording_date": _iso_date(fields["recorded_date_raw"]),
        "recording_date_raw": fields["recorded_date_raw"],
        "book": book,
        "page": page,
        "book_page_raw": book_page_raw,
        "instrument_date": _iso_date(fields["instrument_date_raw"]),
        "instrument_date_raw": fields["instrument_date_raw"],
        "party_1_names": party_1_names,
        "party_2_names": party_2_names,
        "grantors": party_1_names,
        "grantees": party_2_names,
        "parties": [
            {
                "name": name,
                "role": "grantor",
                "native_role": "Party 1",
                "native_name_type": "1",
            }
            for name in party_1_names
        ] + [
            {
                "name": name,
                "role": "grantee",
                "native_role": "Party 2",
                "native_name_type": "2",
            }
            for name in party_2_names
        ],
        "legal_descriptions": legal_rows,
        "detail_page_count": int(max_page_match.group(1)),
        "raw_detail_fields": fields,
    }


def parse_associated_documents(html: str) -> list[dict[str, Any]]:
    """Parse only source-emitted associated-document selectors."""

    grouped: dict[int, dict[str, str]] = {}
    for match in re.finditer(
        r"assocDocRowInfo\[(?P<index>\d+)\]\."
        r"(?P<field>instId|instNum|instType)"
        r"\s*=\s*\"(?P<value>[^\"]*)\"\s*;",
        html,
    ):
        grouped.setdefault(int(match.group("index")), {})[
            match.group("field")
        ] = match.group("value")
    documents: list[dict[str, Any]] = []
    for index in sorted(grouped):
        item = grouped[index]
        if set(item) != {"instId", "instNum", "instType"}:
            raise USVIRecorderSourceChanged(
                f"associated document {index} has incomplete selectors"
            )
        documents.append(
            {
                "native_inst_id": item["instId"],
                "instrument_number": item["instNum"],
                "instrument_type": item["instType"],
                "relationship": "source_associated_document",
            }
        )
    return documents


def parse_instrument_types(payload: Any) -> dict[str, str]:
    """Flatten the source's document-type tree into code-to-label mappings."""

    if not isinstance(payload, list):
        raise USVIRecorderSourceChanged(
            "instrument-type endpoint no longer returns a JSON array"
        )
    types: dict[str, str] = {}

    def visit(node: Any) -> None:
        if not isinstance(node, Mapping):
            raise USVIRecorderSourceChanged(
                "instrument-type tree contains a non-object node"
            )
        node_id = _text(node.get("id"))
        label = _text(node.get("text"))
        children = node.get("children")
        if node_id and node_id != "Root":
            if not label:
                raise USVIRecorderSourceChanged(
                    f"instrument type {node_id!r} has no label"
                )
            prior = types.get(node_id)
            if prior is not None and prior != label:
                raise USVIRecorderSourceChanged(
                    f"instrument type {node_id!r} has conflicting labels"
                )
            types[node_id] = label
        if children is not None:
            if not isinstance(children, list):
                raise USVIRecorderSourceChanged(
                    "instrument-type children are not an array"
                )
            for child in children:
                visit(child)

    for root in payload:
        visit(root)
    if not types:
        raise USVIRecorderSourceChanged(
            "instrument-type endpoint returned no source codes"
        )
    return types


def _form_hidden_values(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for element in form.find_all(["input", "select"]):
        name = element.get("name")
        if not name:
            continue
        if element.name == "input":
            input_type = str(element.get("type", "text")).casefold()
            if input_type in {"checkbox", "radio"} and not element.has_attr(
                "checked"
            ):
                continue
            values[str(name)] = str(element.get("value", ""))
        else:
            selected = element.find("option", selected=True)
            if not isinstance(selected, Tag):
                selected = element.find("option")
            values[str(name)] = (
                str(selected.get("value", ""))
                if isinstance(selected, Tag)
                else ""
            )
    return values


class USVIRecorderClient:
    """Stateful anonymous CountyFusion guest session."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = TIMEOUT,
        minimum_interval: float = MINIMUM_INTERVAL,
        max_attempts: int = MAX_ATTEMPTS,
        retry_backoff: float = RETRY_BACKOFF,
        request_budget: int | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_attempts = max_attempts
        self.retry_backoff = retry_backoff
        self.request_budget = request_budget
        self._request_count = 0
        self._last_request_at: float | None = None
        self._bootstrapped = False
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/json,"
                        "image/png;q=0.9,*/*;q=0.8"
                    ),
                }
            )

    @property
    def request_count(self) -> int:
        """Return actual transport attempts made by this client."""

        return self._request_count

    def close(self) -> None:
        """Close only sessions created by this client."""

        if self._owns_session:
            self.session.close()

    def __enter__(self) -> USVIRecorderClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _pace(self) -> None:
        if self.minimum_interval <= 0 or self._last_request_at is None:
            return
        remaining = (
            self.minimum_interval
            - (time.monotonic() - self._last_request_at)
        )
        if remaining > 0:
            time.sleep(remaining)

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            if (
                self.request_budget is not None
                and self._request_count >= self.request_budget
            ):
                raise USVIRecorderQueryError(
                    "explicit request budget exhausted"
                )
            self._pace()
            self._request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
            except requests.RequestException as error:
                last_error = error
                if attempt < self.max_attempts:
                    time.sleep(self.retry_backoff * attempt)
                    continue
                raise USVIRecorderTransportError(
                    f"could not reach USVI Recorder: {error}"
                ) from error

            final_url = str(getattr(response, "url", url))
            final_host = (urlparse(final_url).hostname or "").casefold()
            if final_host != ALLOWED_HOST:
                raise USVIRecorderSourceChanged(
                    f"source redirected to unexpected host {final_host or '<none>'}"
                )
            status_code = int(getattr(response, "status_code", 0))
            if status_code == 429:
                if attempt < self.max_attempts:
                    time.sleep(self.retry_backoff * attempt)
                    continue
                raise USVIRecorderRateLimited(
                    f"USVI Recorder rate-limited {url}"
                )
            if status_code >= 500 and attempt < self.max_attempts:
                time.sleep(self.retry_backoff * attempt)
                continue
            if status_code < 200 or status_code >= 300:
                raise USVIRecorderHTTPError(status_code, final_url)
            return response
        raise USVIRecorderTransportError(
            f"could not reach USVI Recorder: {last_error}"
        )

    @staticmethod
    def _html(response: Any, *, purpose: str) -> str:
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise USVIRecorderSourceChanged(
                f"{purpose} returned no HTML"
            )
        content_type = str(
            getattr(response, "headers", {}).get("Content-Type", "")
        ).casefold()
        if content_type and not any(
            marker in content_type
            for marker in ("text/html", "application/xhtml+xml")
        ):
            raise USVIRecorderSourceChanged(
                f"{purpose} returned unexpected media type {content_type!r}"
            )
        return text

    @staticmethod
    def _assert_not_error_page(html: str, *, purpose: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        title = _text(soup.title.get_text(" ", strip=True)) if soup.title else None
        page_text = _text(soup.get_text(" ", strip=True)) or ""
        if (
            title == "error.jsp"
            or "Server Error. Click here to logout" in page_text
        ):
            raise USVIRecorderSourceChanged(
                f"{purpose} reached CountyFusion's generic error page"
            )

    def bootstrap(self, *, force: bool = False) -> None:
        """Create and accept one anonymous public guest session."""

        if self._bootstrapped and not force:
            return
        display = self._request(
            "GET",
            LOGIN_DISPLAY_URL,
            params={"countyname": "USVI"},
        )
        display_html = self._html(display, purpose="login display")
        soup = BeautifulSoup(display_html, "html.parser")
        form = soup.find("form", attrs={"name": "loginform"})
        if not isinstance(form, Tag):
            raise USVIRecorderSourceChanged(
                "login display no longer contains loginform"
            )
        token = form.find("input", attrs={"name": "token"})
        token_value = (
            _text(token.get("value"))
            if isinstance(token, Tag)
            else None
        )
        token_name = form.find(
            "input",
            attrs={"name": "struts.token.name"},
        )
        if (
            token_value is None
            or not isinstance(token_name, Tag)
            or token_name.get("value") != "token"
        ):
            raise USVIRecorderSourceChanged(
                "login display no longer emits its per-session Struts token"
            )
        login_payload = _form_hidden_values(form)
        login_payload.update(
            {
                "cmd": "login",
                "countyname": "USVI",
                "scriptsupport": "yes",
                "public": "true",
                "guest": "false",
                "CountyFusionForceNewSession": "true",
                "struts.token.name": "token",
                "token": token_value,
            }
        )
        action = urljoin(str(getattr(display, "url", LOGIN_DISPLAY_URL)), str(form.get("action", "")))
        if urlparse(action).hostname != ALLOWED_HOST or not action.endswith(
            "/countyweb/login.action"
        ):
            raise USVIRecorderSourceChanged(
                "loginform action no longer targets CountyFusion login.action"
            )
        login_response = self._request("POST", action, data=login_payload)
        login_html = self._html(login_response, purpose="guest login")
        self._assert_not_error_page(login_html, purpose="guest login")

        disclaimer = self._request("GET", DISCLAIMER_URL)
        disclaimer_html = self._html(disclaimer, purpose="disclaimer")
        disclaimer_soup = BeautifulSoup(disclaimer_html, "html.parser")
        disclaimer_form = disclaimer_soup.find(
            "form",
            attrs={"name": "disclaimerform"},
        )
        disclaimer_text = disclaimer_soup.get_text(" ", strip=True)
        if (
            not isinstance(disclaimer_form, Tag)
            or "Only the official record on file at the Recorder of Deeds"
            not in disclaimer_text
        ):
            raise USVIRecorderSourceChanged(
                "Recorder disclaimer no longer matches the verified guest flow"
            )
        disclaimer_action = urljoin(
            str(getattr(disclaimer, "url", DISCLAIMER_URL)),
            str(disclaimer_form.get("action", "")),
        )
        if (
            urlparse(disclaimer_action).hostname != ALLOWED_HOST
            or not disclaimer_action.endswith("/countyweb/disclaimer.do")
        ):
            raise USVIRecorderSourceChanged(
                "disclaimer form action changed"
            )
        accepted = self._request(
            "POST",
            disclaimer_action,
            data={"cmd": "Accept"},
        )
        accepted_html = self._html(
            accepted,
            purpose="accepted disclaimer",
        )
        self._assert_not_error_page(
            accepted_html,
            purpose="accepted disclaimer",
        )
        self._bootstrapped = True

    def _prepare_search_form(self, search_type: str) -> str:
        if search_type not in NATIVE_SEARCH_TYPES:
            raise USVIRecorderQueryError(
                f"unknown native search type {search_type!r}"
            )
        self.bootstrap()
        search_main = self._request(
            "GET",
            SEARCH_MAIN_URL,
            params={"defaultType": "Public"},
        )
        search_main_html = self._html(
            search_main,
            purpose="search main",
        )
        self._assert_not_error_page(
            search_main_html,
            purpose="search main",
        )
        criteria = self._request(
            "GET",
            SEARCH_CRITERIA_URL,
            params={
                "searchCategory": "ADVANCED",
                "dynamic": "true",
                "enhanced": "true",
            },
        )
        criteria_html = self._html(criteria, purpose="search criteria")
        self._assert_not_error_page(
            criteria_html,
            purpose="search criteria",
        )
        dynamic = self._request(
            "GET",
            DYNAMIC_CRITERIA_URL,
            params={
                "searchType": search_type,
                "searchCategory": "ADVANCED",
            },
        )
        dynamic_html = self._html(
            dynamic,
            purpose=f"{search_type} criteria",
        )
        dynamic_soup = BeautifulSoup(dynamic_html, "html.parser")
        form = dynamic_soup.find("form", id="searchForm")
        if not isinstance(form, Tag):
            raise USVIRecorderSourceChanged(
                f"{search_type} criteria no longer contains searchForm"
            )
        action = urljoin(
            str(getattr(dynamic, "url", DYNAMIC_CRITERIA_URL)),
            str(form.get("action", "")),
        )
        if (
            urlparse(action).hostname != ALLOWED_HOST
            or urlparse(action).path != "/countyweb/search/searchExecute.do"
            or urlparse(action).query != "assessor=false"
        ):
            raise USVIRecorderSourceChanged(
                f"{search_type} searchForm action changed"
            )
        native_type = form.find("input", attrs={"name": "SEARCHTYPE"})
        if (
            not isinstance(native_type, Tag)
            or native_type.get("value") != search_type
        ):
            raise USVIRecorderSourceChanged(
                f"{search_type} criteria emits a different SEARCHTYPE"
            )
        return dynamic_html

    def instrument_types(self) -> dict[str, str]:
        """Fetch and validate the live source document-type vocabulary."""

        self.bootstrap()
        response = self._request(
            "GET",
            INSTRUMENT_TYPES_URL,
            params={
                "ordertypes": "1",
                "rootstring": "All Document Types",
            },
        )
        try:
            payload = response.json()
        except (ValueError, AttributeError) as error:
            raise USVIRecorderSourceChanged(
                "instrument-type endpoint did not return JSON"
            ) from error
        return parse_instrument_types(payload)

    def search(
        self,
        *,
        search_type: str,
        payload: Mapping[str, str],
    ) -> dict[str, Any]:
        """Execute a native form and exhaust all native result pages."""

        form_html = self._prepare_search_form(search_type)
        form_soup = BeautifulSoup(form_html, "html.parser")
        form = form_soup.find("form", id="searchForm")
        assert isinstance(form, Tag)
        native_fields = {
            str(element.get("name"))
            for element in form.find_all(["input", "select"])
            if element.get("name")
        }
        unexpected = sorted(
            key
            for key, value in payload.items()
            if value and key not in native_fields
        )
        if unexpected:
            raise USVIRecorderSourceChanged(
                f"{search_type} form no longer exposes: {', '.join(unexpected)}"
            )
        response = self._request(
            "POST",
            SEARCH_EXECUTE_URL,
            params={"assessor": "false"},
            data=dict(payload),
        )
        result_html = self._html(response, purpose="search results")
        self._assert_not_error_page(result_html, purpose="search results")
        page = parse_search_page(
            result_html,
            source_url=str(getattr(response, "url", SEARCH_RESULTS_URL)),
        )
        if page.no_results:
            return {
                "records": [],
                "total_count": 0,
                "native_page_count": 0,
                "native_page_size": int(payload["RECSPERPAGE"]),
                "authoritative_no_results": True,
            }

        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        current_page = page
        for page_number in range(1, page.page_count + 1):
            try:
                list_response = self._request(
                    "GET",
                    current_page.list_url or RESULT_LIST_URL,
                    params=(
                        None
                        if current_page.list_url
                        and "searchSessionId=" in current_page.list_url
                        else {
                            "scrollPos": "0",
                            "searchSessionId": "searchJobMain",
                        }
                    ),
                )
                list_html = self._html(
                    list_response,
                    purpose=f"result list page {page_number}",
                )
                page_records = parse_result_list(
                    list_html,
                    page_number=page_number,
                    start_cursor=current_page.start_cursor,
                )
                if len(page_records) != current_page.result_list_size:
                    raise USVIRecorderSourceChanged(
                        f"page {page_number} advertises "
                        f"{current_page.result_list_size} rows but emits "
                        f"{len(page_records)}"
                    )
                for record in page_records:
                    native_id = str(record["native_document_id"])
                    if native_id in seen:
                        raise USVIRecorderSourceChanged(
                            f"native paging repeated instrument {native_id}"
                        )
                    seen.add(native_id)
                records.extend(page_records)
                if page_number == page.page_count:
                    break
                next_response = self._request(
                    "GET",
                    SEARCH_RESULTS_URL,
                    params={
                        "searchSessionId": "searchJobMain",
                        "resultPageAction": "nav",
                        "sortColumn": current_page.sort_column,
                        "sortDirection": current_page.sort_direction,
                        "navDirection": "next",
                        "startCursor": str(current_page.start_cursor),
                        "pageNumber": "",
                    },
                )
                next_html = self._html(
                    next_response,
                    purpose=f"result navigation page {page_number + 1}",
                )
                next_page = parse_search_page(
                    next_html,
                    source_url=str(
                        getattr(next_response, "url", SEARCH_RESULTS_URL)
                    ),
                )
                if next_page.no_results:
                    raise USVIRecorderSourceChanged(
                        "non-empty pagination unexpectedly became no-results"
                    )
                if (
                    next_page.total_count != page.total_count
                    or next_page.page_count != page.page_count
                    or next_page.start_cursor <= current_page.start_cursor
                ):
                    raise USVIRecorderSourceChanged(
                        "native paging count or cursor changed during traversal"
                    )
                current_page = next_page
            except USVIRecorderError as error:
                if records:
                    raise USVIRecorderPartialSearch(
                        f"retrieved {len(records)} of {page.total_count} "
                        f"rows before native page {page_number} failed: {error}",
                        records=records,
                        cause=error,
                    ) from error
                raise

        if len(records) != page.total_count:
            raise USVIRecorderPartialSearch(
                f"native paging emitted {len(records)} of "
                f"{page.total_count} advertised rows",
                records=records,
                cause=USVIRecorderSourceChanged(
                    "native page traversal did not reproduce the advertised count"
                ),
            )
        return {
            "records": records,
            "total_count": page.total_count,
            "native_page_count": page.page_count,
            "native_page_size": int(payload["RECSPERPAGE"]),
            "authoritative_no_results": False,
        }

    @staticmethod
    def _document_params(record: Mapping[str, Any]) -> dict[str, str]:
        locator = record.get("source_locator")
        if not isinstance(locator, Mapping):
            raise USVIRecorderSourceChanged(
                "selected result has no source locator"
            )
        required = {
            "instId": _text(locator.get("inst_id")),
            "instNum": _text(locator.get("instrument_number")),
            "instType": _text(locator.get("instrument_type")),
        }
        if any(value is None for value in required.values()):
            raise USVIRecorderSourceChanged(
                "selected result has incomplete source selectors"
            )
        return {
            "searchSessionId": "searchJobMain",
            "instId": required["instId"] or "",
            "instNum": required["instNum"] or "",
            "instType": required["instType"] or "",
            "assocDoc": "undefined",
            "assocParentNum": "undefined",
            "parcelNum": "undefined",
            "assocType": "undefined",
            "onloadAction": "parent.documentLoaded();",
        }

    def select_exact(
        self,
        *,
        district: str,
        inst_id: str | int,
        instrument_number: str,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Reacquire a detail-capable session and verify all three selectors."""

        normalized_district = normalize_district(district)
        normalized_inst_id = _text(inst_id)
        normalized_number = _text(instrument_number)
        if (
            normalized_district is None
            or normalized_inst_id is None
            or normalized_number is None
        ):
            raise USVIRecorderQueryError(
                "detail selection requires district, instId, and instrument number"
            )
        selectors = {
            "names": [],
            "party": "both",
            "name_match": None,
            "district": normalized_district,
            "from_date": None,
            "to_date": None,
            "document_types": [],
            "document_number": normalized_number,
            "document_number_end": None,
            "book": None,
            "page": None,
            "page_end": None,
            **{key: None for key in LEGAL_ARGUMENT_FIELDS},
        }
        payload = build_search_payload(
            selectors,
            search_type="docNum",
            page_size=page_size,
        )
        search = self.search(search_type="docNum", payload=payload)
        number_candidates = [
            record
            for record in search["records"]
            if record.get("instrument_number") == normalized_number
        ]
        exact = [
            record
            for record in number_candidates
            if record.get("district") == normalized_district
            and str(record.get("native_inst_id")) == normalized_inst_id
        ]
        if len(exact) != 1:
            candidate_selectors = [
                {
                    "district": record.get("district"),
                    "inst_id": record.get("native_inst_id"),
                    "instrument_number": record.get("instrument_number"),
                }
                for record in number_candidates
            ]
            if len(exact) > 1:
                raise USVIRecorderSourceChanged(
                    "exact instrument search emitted duplicate rows for "
                    f"{normalized_district}:{normalized_inst_id}:"
                    f"{normalized_number}; candidates={candidate_selectors}"
                )
            raise USVIRecorderQueryError(
                "exact instrument reacquisition did not match district, "
                f"instId, and instrument number; candidates={candidate_selectors}"
            )
        record = dict(exact[0])
        params = self._document_params(record)
        outer = self._request("GET", DOCUMENT_INFO_URL, params=params)
        outer_html = self._html(outer, purpose="instrument detail shell")
        self._assert_not_error_page(
            outer_html,
            purpose="instrument detail shell",
        )
        selector_markers = (
            f"instId={params['instId']}",
            f"instNum={params['instNum']}",
            f"instType={params['instType']}",
        )
        if not all(marker in outer_html for marker in selector_markers):
            raise USVIRecorderSourceChanged(
                "instrument detail shell does not preserve selected selectors"
            )
        detail_response = self._request(
            "GET",
            DISPLAY_DOCUMENT_URL,
            params=params,
        )
        detail_html = self._html(
            detail_response,
            purpose="instrument detail",
        )
        self._assert_not_error_page(
            detail_html,
            purpose="instrument detail",
        )
        detail = parse_detail_page(detail_html)
        if (
            detail["district"] != normalized_district
            or detail["instrument_number"] != normalized_number
        ):
            raise USVIRecorderSourceChanged(
                "selected instrument detail does not match its district and "
                "instrument number"
            )
        associated: list[dict[str, Any]] = []
        if detail["detail_page_count"] >= 2:
            page_2 = self._request(
                "GET",
                DETAIL_PAGE_URL,
                params={
                    "readonly": "true",
                    "onloadAction": "parent.documentLoaded();",
                    "seltab": "2",
                    "usage": "ADVSCH",
                    "searchSessionId": "searchJobMain",
                    "pagenum": "2",
                    "countyname": "USVI",
                    "skipDBSwitch": "true",
                },
            )
            page_2_html = self._html(
                page_2,
                purpose="instrument associated documents",
            )
            self._assert_not_error_page(
                page_2_html,
                purpose="instrument associated documents",
            )
            associated = parse_associated_documents(page_2_html)
        record.update(detail)
        record.update(
            {
                "record_scope": "recorder_instrument_detail",
                "native_document_id": native_instrument_identity(
                    normalized_district,
                    normalized_inst_id,
                ),
                "native_inst_id": normalized_inst_id,
                "canonical_ref": instrument_ref(
                    normalized_district,
                    normalized_inst_id,
                ),
                "evidence_ref": instrument_ref(
                    normalized_district,
                    normalized_inst_id,
                ),
                "associated_documents": associated,
                "source_locator": {
                    **dict(record["source_locator"]),
                    "detail_requires_search_selection": True,
                },
            }
        )
        return record

    def fetch_page_image(
        self,
        record: Mapping[str, Any],
        page_number: int,
    ) -> PageImage:
        """Fetch one page after exact session selection."""

        if page_number <= 0:
            raise USVIRecorderQueryError("page number must be positive")
        params = self._document_params(record)
        viewer = self._request(
            "GET",
            IMAGE_VIEWER_URL,
            params={**params, "manual": "true"},
        )
        viewer_html = self._html(viewer, purpose="instrument image viewer")
        self._assert_not_error_page(
            viewer_html,
            purpose="instrument image viewer",
        )
        if "InstrumentImageViewInternal.jsp" not in str(
            getattr(viewer, "url", "")
        ) and "getPage.do" not in viewer_html:
            raise USVIRecorderSourceChanged(
                "instrument image viewer no longer exposes the verified PNG route"
            )
        page_state = self._request(
            "POST",
            IMAGE_PAGE_STATE_URL,
            data={
                "addWatermarks": "true",
                "isPreview": "false",
                "instnum": params["instId"],
                "pageNumber": str(page_number),
            },
        )
        try:
            state = page_state.json()
        except (ValueError, AttributeError) as error:
            raise USVIRecorderSourceChanged(
                "image page-state endpoint did not return JSON"
            ) from error
        if not isinstance(state, Mapping) or state.get("status") != "success":
            raise USVIRecorderSourceChanged(
                f"image page-state request failed: {state!r}"
            )
        page_count = state.get("numberOfPages")
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count <= 0
        ):
            raise USVIRecorderSourceChanged(
                "image page-state response has no positive page count"
            )
        if page_number > page_count:
            raise USVIRecorderQueryError(
                f"page {page_number} exceeds source page count {page_count}"
            )
        image = self._request(
            "GET",
            IMAGE_PNG_URL,
            params={
                "instnum": params["instId"],
                "isPreview": "false",
            },
        )
        media_type = str(
            getattr(image, "headers", {}).get("Content-Type", "")
        ).split(";", 1)[0].strip().casefold()
        content = bytes(getattr(image, "content", b""))
        if media_type != "image/png":
            raise USVIRecorderSourceChanged(
                f"image endpoint returned {media_type or 'no media type'}"
            )
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise USVIRecorderSourceChanged(
                "image endpoint response does not have a PNG signature"
            )
        return PageImage(
            page_number=page_number,
            page_count=page_count,
            source_url=str(getattr(image, "url", IMAGE_PNG_URL)),
            media_type=media_type,
            content=content,
        )


def selectors_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Normalize CLI selectors without narrowing source-supported values."""

    names = [
        name
        for name in (
            [getattr(args, "query", None)]
            + list(getattr(args, "name", None) or [])
        )
        if _text(name)
    ]
    names = [_text(name) or "" for name in names]
    if len(names) > NATIVE_MULTIPLE_NAME_LIMIT:
        raise USVIRecorderQueryError(
            "the source's multiple-name form exposes 10 name rows; "
            f"{len(names)} were requested"
        )
    district = normalize_district(getattr(args, "district", None))
    from_date = _source_date(
        getattr(args, "date_from", None),
        "--date-from",
    )
    to_date = _source_date(
        getattr(args, "date_to", None),
        "--date-to",
    )
    if from_date and to_date:
        if datetime.strptime(from_date, "%m/%d/%Y") > datetime.strptime(
            to_date,
            "%m/%d/%Y",
        ):
            raise USVIRecorderQueryError(
                "--date-from cannot be after --date-to"
            )
    document_types = _unique(
        str(value).upper()
        for value in (getattr(args, "document_type", None) or [])
    )
    selectors: dict[str, Any] = {
        "names": names,
        "party": getattr(args, "party", "both"),
        "name_match": getattr(args, "name_match", None),
        "district": district,
        "from_date": from_date or None,
        "to_date": to_date or None,
        "document_types": document_types,
        "document_number": _text(
            getattr(args, "document_number", None)
        ),
        "document_number_end": _text(
            getattr(args, "document_number_end", None)
        ),
        "book": _text(getattr(args, "book", None)),
        "page": _text(getattr(args, "page", None)),
        "page_end": _text(getattr(args, "page_end", None)),
    }
    for argument in LEGAL_ARGUMENT_FIELDS:
        selectors[argument] = _text(getattr(args, argument, None))
    return selectors


def choose_search_type(selectors: Mapping[str, Any]) -> str:
    """Select the native form that can express the requested fields."""

    names = list(selectors.get("names") or [])
    legal_selected = any(
        selectors.get(argument) for argument in LEGAL_ARGUMENT_FIELDS
    )
    document_number_selected = bool(
        selectors.get("document_number")
        or selectors.get("document_number_end")
    )
    book_page_selected = bool(
        selectors.get("book")
        or selectors.get("page")
        or selectors.get("page_end")
    )
    date_or_type = bool(
        selectors.get("from_date")
        or selectors.get("to_date")
        or selectors.get("document_types")
    )

    groups = sum(
        (
            bool(document_number_selected),
            bool(book_page_selected),
            bool(legal_selected),
        )
    )
    if groups > 1:
        raise USVIRecorderQueryError(
            "document-number, book/page, and legal selectors are separate "
            "native CountyFusion search forms"
        )
    if document_number_selected:
        incompatible = names or date_or_type or legal_selected or book_page_selected
        if incompatible:
            raise USVIRecorderQueryError(
                "the native Document Number form combines only document "
                "number/range and district"
            )
        return "docNum"
    if book_page_selected:
        incompatible = names or date_or_type or legal_selected
        if incompatible:
            raise USVIRecorderQueryError(
                "the native Book / Page form combines only book/page/range "
                "and district"
            )
        return "bookPage"
    if legal_selected:
        if len(names) > 1:
            raise USVIRecorderQueryError(
                "the native Condo / Estate form exposes one name field, not "
                "the separate multiple-name form"
            )
        return "lbs"
    if len(names) > 1:
        return "allNamesMultiple"
    if names:
        return "allNames"
    if date_or_type:
        return "fileNum"
    if selectors.get("district"):
        return "allNames"
    raise USVIRecorderQueryError(
        "enter at least one selector accepted by the native source"
    )


def build_search_payload(
    selectors: Mapping[str, Any],
    *,
    search_type: str,
    page_size: int,
) -> dict[str, str]:
    """Map normalized selectors to verified source field names."""

    if page_size not in NATIVE_PAGE_SIZES:
        raise USVIRecorderQueryError(
            "page size must be one of the source's native values: "
            + ", ".join(str(value) for value in NATIVE_PAGE_SIZES)
        )
    if search_type not in NATIVE_SEARCH_TYPES:
        raise USVIRecorderQueryError(
            f"unsupported native search type {search_type!r}"
        )
    payload = {
        **COMMON_FORM_FIELDS,
        "SEARCHTYPE": search_type,
        "RECSPERPAGE": str(page_size),
    }
    district = _text(selectors.get("district"))
    if district:
        payload["MUNI"] = district

    document_types = list(selectors.get("document_types") or [])
    if document_types:
        payload["INSTTYPEALL"] = "false"
        payload["INSTTYPE"] = ",".join(document_types)

    from_date = _text(selectors.get("from_date"))
    to_date = _text(selectors.get("to_date"))
    if from_date:
        payload["FROMDATE"] = from_date
    if to_date:
        payload["TODATE"] = to_date
    if from_date or to_date:
        payload["daterange_TODATE"] = "User Defined"
        payload["DATERANGE"] = json.dumps(
            [{"name": "TODATE", "value": "User Defined"}],
            separators=(",", ":"),
        )

    names = list(selectors.get("names") or [])
    if names:
        payload["PARTY"] = PARTY_VALUES[str(selectors.get("party", "both"))]
        name_match = selectors.get("name_match")
        if name_match:
            payload[MATCH_FIELDS[str(name_match)]] = "true"
        if search_type == "allNamesMultiple":
            payload["MULTIPLENAMES"] = json.dumps(
                [{"type": "a", "allName": name} for name in names],
                separators=(",", ":"),
            )
        else:
            payload["ALLNAMES"] = str(names[0])
            payload["SELECTEDNAMES"] = ""
            if search_type == "allNames":
                payload["DISTINCTRESULTS"] = "true"

    if search_type == "docNum":
        if selectors.get("document_number"):
            payload["INSTNUM"] = str(selectors["document_number"])
        if selectors.get("document_number_end"):
            payload["INSTNUMEND"] = str(selectors["document_number_end"])
    elif search_type == "bookPage":
        for source_field, selector in (
            ("BOOK", "book"),
            ("PAGE", "page"),
            ("PAGEEND", "page_end"),
        ):
            if selectors.get(selector):
                payload[source_field] = str(selectors[selector])
    elif search_type == "lbs":
        for selector, source_field in LEGAL_ARGUMENT_FIELDS.items():
            value = _text(selectors.get(selector))
            if not value:
                continue
            if (
                selector
                in {"parcel", "building", "unit", "plot"}
                and not value.endswith("*")
            ):
                value += "*"
            elif selector == "land_comment":
                if not value.startswith("*"):
                    value = "*" + value
                if not value.endswith("*"):
                    value += "*"
            payload[source_field] = value
    return payload


def validate_document_types(
    client: USVIRecorderClient | Any,
    selectors: Mapping[str, Any],
) -> None:
    selected = list(selectors.get("document_types") or [])
    if not selected:
        return
    vocabulary = client.instrument_types()
    unknown = [code for code in selected if code not in vocabulary]
    if unknown:
        raise USVIRecorderQueryError(
            "document type code(s) are not in the live source vocabulary: "
            + ", ".join(unknown)
        )


def build_query(
    args: argparse.Namespace,
    *,
    selectors: Mapping[str, Any] | None = None,
    search_type: str | None = None,
) -> PublicRecordsQuery:
    """Build the shared public-record query envelope."""

    operation = args.command
    parameters: dict[str, Any] = {
        "route": "anonymous_countyfusion_guest",
    }
    requested_limit = None
    if operation == "search":
        candidate_limit = getattr(args, "limit", None)
        requested_limit = (
            candidate_limit
            if isinstance(candidate_limit, int)
            and not isinstance(candidate_limit, bool)
            and candidate_limit > 0
            else None
        )
        parameters.update(
            {
                "native_search_type": search_type,
                "selectors": dict(selectors or {}),
                "native_page_size": getattr(args, "page_size", 100),
                "offset": getattr(args, "offset", 0),
                "native_paging": "exhaustive_before_caller_window",
            }
        )
    elif operation in {"document", "page"}:
        parameters.update(
            {
                "district": _text(getattr(args, "district", None)),
                "inst_id": str(getattr(args, "inst_id", "")),
                "instrument_number": str(
                    getattr(args, "instrument_number", "")
                ),
            }
        )
        if operation == "page":
            parameters["page_number"] = getattr(args, "page_number", None)
    elif operation == "probe":
        parameters.update(
            {
                "district": PROBE_DISTRICT,
                "inst_id": PROBE_INST_ID,
                "instrument_number": PROBE_INSTRUMENT_NUMBER,
                "page_number": 1,
            }
        )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
        ),
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: USVIRecorderError,
) -> PublicRecordsResult:
    records: Sequence[Mapping[str, Any]] = ()
    details: dict[str, Any] = {}
    if isinstance(error, USVIRecorderPartialSearch):
        status = ResultStatus.PARTIAL
        code = "native_pagination_incomplete"
        category = "pagination"
        retryable = isinstance(
            error.cause,
            (
                USVIRecorderTransportError,
                USVIRecorderRateLimited,
                USVIRecorderHTTPError,
            ),
        )
        records = error.records
        details["cause"] = type(error.cause).__name__
    elif isinstance(error, USVIRecorderSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, USVIRecorderRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
        retryable = True
    elif isinstance(error, USVIRecorderTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    elif isinstance(error, USVIRecorderHTTPError):
        if error.status_code in {401, 403}:
            status = ResultStatus.RESTRICTED
            category = "authentication"
        elif error.status_code in {404, 410}:
            status = ResultStatus.SOURCE_CHANGED
            category = "source_route"
        else:
            status = ResultStatus.UNAVAILABLE
            category = "http"
        code = f"source_http_{error.status_code}"
        retryable = error.status_code >= 500
        details["status_code"] = error.status_code
        details["url"] = error.url
    else:
        status = ResultStatus.UNAVAILABLE
        code = "source_query_not_executable"
        category = "source_query"
        retryable = False
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=retryable,
                details=details,
            )
        ],
        records=records,
        warnings=SOURCE_WARNINGS,
    )


def _page_artifact(
    record: Mapping[str, Any],
    image: PageImage,
    destination: Path | None,
) -> dict[str, Any]:
    district = str(record["district"])
    inst_id = str(record["native_inst_id"])
    return {
        "native_artifact_id": (
            f"{native_instrument_identity(district, inst_id)}:"
            f"page:{image.page_number}"
        ),
        "artifact_kind": "instrument_page_image",
        "representation_of": record["canonical_ref"],
        "page_number": image.page_number,
        "page_count": image.page_count,
        "mime_type": image.media_type,
        "byte_count": len(image.content),
        "sha256": image.sha256,
        "source_url": image.source_url,
        "local_path": str(destination) if destination else None,
        "source_copy_status": (
            "recorder_hosted_reference_image_not_official_record_copy"
        ),
        "identity_note": (
            "nested page artifact of the selected instrument; not a separate "
            "instrument or independent corroboration"
        ),
    }


def _write_page(
    destination: Path,
    content: bytes,
    *,
    overwrite: bool,
) -> Path:
    target = destination.expanduser().resolve()
    if target.exists() and not overwrite:
        raise USVIRecorderQueryError(
            f"destination exists; use --overwrite to replace it: {target}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def execute(
    args: argparse.Namespace,
    *,
    client: USVIRecorderClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one command through the shared public-record contract."""

    selectors: dict[str, Any] | None = None
    search_type: str | None = None
    try:
        if args.command == "search":
            if getattr(args, "offset", 0) < 0:
                raise USVIRecorderQueryError("--offset cannot be negative")
            limit = getattr(args, "limit", None)
            if limit is not None and limit <= 0:
                raise USVIRecorderQueryError("--limit must be positive")
            selectors = selectors_from_args(args)
            search_type = choose_search_type(selectors)
        elif args.command in {"document", "page"}:
            normalize_district(getattr(args, "district", None))
            if not _text(getattr(args, "inst_id", None)):
                raise USVIRecorderQueryError("--inst-id cannot be blank")
            if not _text(getattr(args, "instrument_number", None)):
                raise USVIRecorderQueryError(
                    "instrument number cannot be blank"
                )
            if args.command == "page" and args.page_number <= 0:
                raise USVIRecorderQueryError(
                    "page number must be positive"
                )
        query = build_query(
            args,
            selectors=selectors,
            search_type=search_type,
        )
    except USVIRecorderError as error:
        query = build_query(args)
        result = _source_failure(query, error)
        _log(query, None)
        return result

    source_client = client or USVIRecorderClient(
        timeout=getattr(args, "timeout", TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            MINIMUM_INTERVAL,
        ),
        max_attempts=getattr(args, "max_attempts", MAX_ATTEMPTS),
        retry_backoff=getattr(args, "retry_backoff", RETRY_BACKOFF),
    )
    should_close = client is None
    count: int | None = None
    try:
        if args.command == "search":
            assert selectors is not None and search_type is not None
            validate_document_types(source_client, selectors)
            payload = build_search_payload(
                selectors,
                search_type=search_type,
                page_size=args.page_size,
            )
            native = source_client.search(
                search_type=search_type,
                payload=payload,
            )
            all_records = list(native["records"])
            offset = args.offset
            limit = args.limit
            records = all_records[offset:]
            if limit is not None:
                records = records[:limit]
            next_offset = offset + len(records)
            next_cursor = (
                f"usvi-recorder:offset:{next_offset}"
                if next_offset < len(all_records)
                else None
            )
            for record in records:
                record["search_metadata"] = {
                    "source_total_count": native["total_count"],
                    "native_page_count": native["native_page_count"],
                    "native_page_size": native["native_page_size"],
                    "native_pages_exhausted": True,
                    "caller_offset": offset,
                    "caller_limit": limit,
                }
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
            count = len(records)
        elif args.command == "document":
            record = source_client.select_exact(
                district=args.district,
                inst_id=args.inst_id,
                instrument_number=args.instrument_number,
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=SOURCE_WARNINGS,
            )
            count = 1
        elif args.command == "page":
            record = source_client.select_exact(
                district=args.district,
                inst_id=args.inst_id,
                instrument_number=args.instrument_number,
            )
            image = source_client.fetch_page_image(
                record,
                args.page_number,
            )
            destination = (
                _write_page(
                    args.destination,
                    image.content,
                    overwrite=args.overwrite,
                )
                if args.destination
                else None
            )
            page_record = dict(record)
            page_record["record_scope"] = (
                "recorder_instrument_detail_with_selected_page"
            )
            page_record["documents"] = [
                _page_artifact(record, image, destination)
            ]
            result = PublicRecordsResult.success(
                query,
                [page_record],
                raw_artifact_refs=(
                    [str(destination)] if destination else []
                ),
                warnings=SOURCE_WARNINGS,
            )
            count = 1
        elif args.command == "probe":
            record = source_client.select_exact(
                district=PROBE_DISTRICT,
                inst_id=PROBE_INST_ID,
                instrument_number=PROBE_INSTRUMENT_NUMBER,
            )
            image = source_client.fetch_page_image(record, 1)
            observed_matches = image.sha256 == PROBE_OBSERVED_PAGE_1_SHA256
            checks = {
                "identity": (
                    record.get("native_document_id")
                    == f"{PROBE_DISTRICT}:{PROBE_INST_ID}"
                ),
                "instrument_number": (
                    record.get("instrument_number")
                    == PROBE_INSTRUMENT_NUMBER
                ),
                "instrument_type": (
                    record.get("instrument_type")
                    == PROBE_INSTRUMENT_TYPE
                ),
                "recording_date": (
                    record.get("recording_date")
                    == PROBE_RECORDED_DATE
                ),
                "page_count": image.page_count == PROBE_PAGE_COUNT,
                "png_signature": image.content.startswith(
                    b"\x89PNG\r\n\x1a\n"
                ),
            }
            if not all(checks.values()):
                raise USVIRecorderSourceChanged(
                    f"live sentinel changed: {checks}"
                )
            probe_record = dict(record)
            probe_record["probe"] = {
                "observed_at": OBSERVED_AT,
                "checks": checks,
                "page_1": {
                    "page_count": image.page_count,
                    "media_type": image.media_type,
                    "byte_count": len(image.content),
                    "sha256": image.sha256,
                    "observed_baseline_sha256": (
                        PROBE_OBSERVED_PAGE_1_SHA256
                    ),
                    "matches_observed_baseline": observed_matches,
                    "baseline_is_not_identity": True,
                },
            }
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                warnings=SOURCE_WARNINGS,
            )
            count = 1
        else:
            raise USVIRecorderQueryError(
                f"unknown operation {args.command!r}"
            )
    except USVIRecorderError as error:
        result = _source_failure(query, error)
        count = len(result.records) if result.records else None
    finally:
        if should_close:
            source_client.close()
    _log(query, count)
    return result


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=RETRY_BACKOFF,
    )
    add_output_args(parser)


def _add_exact_selector_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("instrument_number")
    parser.add_argument(
        "--district",
        required=True,
        help="Source district: ST THOMAS or ST CROIX",
    )
    parser.add_argument(
        "--inst-id",
        required=True,
        help="Source instId emitted by a search result",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search the U.S. Virgin Islands Recorder of Deeds "
            "CountyFusion index"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search native name, legal, date/type, number, or book/page fields",
    )
    search.add_argument("query", nargs="?", help="One indexed party name")
    search.add_argument(
        "--name",
        action="append",
        help="Indexed party name; repeat for the native multiple-name form",
    )
    search.add_argument(
        "--party",
        choices=tuple(PARTY_VALUES),
        default="both",
    )
    search.add_argument(
        "--name-match",
        choices=tuple(MATCH_FIELDS),
    )
    search.add_argument("--district")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument(
        "--document-type",
        action="append",
        help="Source code such as DEED or MTG; repeat as needed",
    )
    search.add_argument("--parcel")
    search.add_argument("--qtr-condo")
    search.add_argument("--estate")
    search.add_argument("--building")
    search.add_argument("--unit")
    search.add_argument("--plot")
    search.add_argument("--land-comment")
    search.add_argument("--document-number")
    search.add_argument("--document-number-end")
    search.add_argument("--book")
    search.add_argument("--page")
    search.add_argument("--page-end")
    search.add_argument(
        "--page-size",
        type=int,
        choices=NATIVE_PAGE_SIZES,
        default=100,
        help="Native source page size; all native pages are still exhausted",
    )
    search.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Caller window offset applied after native paging is exhausted",
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Optional caller output limit; there is no adapter default cap",
    )
    _add_runtime_and_output(search)

    document = subparsers.add_parser(
        "document",
        help="Reacquire and fetch exact instrument detail",
    )
    _add_exact_selector_arguments(document)
    _add_runtime_and_output(document)

    page = subparsers.add_parser(
        "page",
        help="Fetch one PNG page after exact instrument reacquisition",
    )
    _add_exact_selector_arguments(page)
    page.add_argument("page_number", type=int)
    page.add_argument("destination", nargs="?", type=Path)
    page.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(page)

    probe = subparsers.add_parser(
        "probe",
        help="Verify known index, detail, and PNG sentinel",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"USVI Recorder {args.command} ({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"USVI Recorder {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"- {record.get('instrument_number') or '?'} | "
            f"{record.get('district') or '?'} | "
            f"instId {record.get('native_inst_id') or '?'} | "
            f"{record.get('instrument_type') or '?'}"
        )
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval cannot be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if args.retry_backoff < 0:
        parser.error("--retry-backoff cannot be negative")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
