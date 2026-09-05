#!/usr/bin/env python3
"""Query the Texas Judicial Branch TAMES appellate case-search portal.

TAMES covers the Supreme Court of Texas, Court of Criminal Appeals, and all
fifteen Courts of Appeals.  The public WebForms portal exposes case indexes,
case events, parties and representatives, calendars, trial-court references,
and public PDF documents.

Examples:
    uv run python tools/query_texas_appellate.py search Tesla --json
    uv run python tools/query_texas_appellate.py search Smith \
        --scope style --limit 50 --output smith.json
    uv run python tools/query_texas_appellate.py search D-1-GN-24-008508 \
        --scope trial-case-number --county Travis --json
    uv run python tools/query_texas_appellate.py case 03-25-00287-CV --json
    uv run python tools/query_texas_appellate.py docket 03-25-00287-CV --json
    uv run python tools/query_texas_appellate.py documents \
        03-25-00287-CV --json
    uv run python tools/query_texas_appellate.py download \
        03-25-00287-CV bc16a831-998e-449f-9d28-84b61486178b \
        /tmp/notice.pdf --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    from tools.public_records_http import inferred_schema, schema_fingerprint
    from tools.public_records_store import canonical_court_ref
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
    from public_records_http import inferred_schema, schema_fingerprint
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-tx-appellate-tames"
STATE_CODE = "TX"
STATE_GEOID = "48"
BASE_URL = "https://search.txcourts.gov"
SEARCH_URL = f"{BASE_URL}/CaseSearch.aspx?coa=cossup"
HELP_URL = f"{BASE_URL}/HelpCaseSearch.aspx"

SOURCE_RESULT_CEILING = 1000
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)


def _ordinal_suffix(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return suffix


COURT_NAMES = {
    "cossup": "Supreme Court of Texas",
    "coscca": "Texas Court of Criminal Appeals",
    **{
        f"coa{number:02d}": (
            f"{number}{_ordinal_suffix(number)} Court of Appeals"
        )
        for number in range(1, 16)
    },
}
COURT_CHECKBOX_INDEX = {
    "cossup": 0,
    "coscca": 1,
    **{f"coa{number:02d}": number + 1 for number in range(1, 16)},
}
SEARCH_SCOPE_FIELDS = {
    "style": "ctl00$ContentPlaceHolder1$txtStyle1",
    "case-number": "ctl00$ContentPlaceHolder1$txtCaseNumber",
    "partial-case-number": "ctl00$ContentPlaceHolder1$txtPartialCaseNumber",
    "trial-case-number": "ctl00$ContentPlaceHolder1$txtTrialCourtCaseNumber",
    "attorney": "ctl00$ContentPlaceHolder1$txtAttorneyNameOrBarNumber",
}
CASE_TYPE_VALUES = {"both": "0", "civil": "1", "criminal": "2"}
CURSOR_RE = re.compile(
    r"^tx-tames:v1:page:(?P<page>\d+):offset:(?P<offset>\d+):"
    r"(?P<fingerprint>[0-9a-f]{12})$"
)

SOURCE_WARNINGS = (
    "TAMES covers Texas appellate courts; trial-court case files remain with "
    "the applicable district or county clerk and re:SearchTX.",
    "The portal states that case data and documents are refreshed nightly.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Texas Judicial Branch TAMES Appellate Case Search",
    source_role="statewide_appellate_case_docket_and_public_document_portal",
    base_url=SEARCH_URL,
    dataset_id="tames-public-search",
    metadata={
        "authority": "Texas Judicial Branch, Office of Court Administration",
        "state_code": STATE_CODE,
        "coverage": (
            "Supreme Court, Court of Criminal Appeals, and 15 Courts of Appeals"
        ),
        "authentication": "none",
        "refresh": "nightly",
        "source_result_ceiling": SOURCE_RESULT_CEILING,
        "platform_family": "tames_webforms",
    },
)


@dataclass(frozen=True)
class TAMESSearchRow:
    case_number: str
    court_code: str
    filed_date: str | None
    style: str | None
    versus: str | None
    case_type: str | None
    coa_case_numbers: tuple[str, ...]
    trial_case_number: str | None
    trial_county: str | None
    trial_court: str | None
    appellate_court_label: str | None
    source_url: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class TAMESSearchPage:
    rows: tuple[TAMESSearchRow, ...]
    current_page: int
    total_pages: int
    total_reported: int
    source_ceiling_reached: bool
    next_control_name: str | None
    schema_fingerprint: str
    html: str


@dataclass(frozen=True)
class TAMESCasePage:
    case_number: str
    court_code: str
    appellate_court_name: str
    fields: Mapping[str, str | None]
    trial_court_fields: Mapping[str, str | None]
    parties: tuple[Mapping[str, Any], ...]
    docket_entries: tuple[Mapping[str, Any], ...]
    calendar_events: tuple[Mapping[str, Any], ...]
    appellate_briefs: tuple[Mapping[str, Any], ...]
    schema_fingerprint: str
    source_url: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class TAMESDownload:
    native_document_id: str
    source_url: str
    content: bytes
    media_type: str
    raw_content_type: str | None
    filename: str | None


class TAMESSelectionError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class TAMESRequestError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable
        self.details = dict(details or {})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return normalized


def _form_date(value: str | None) -> str:
    normalized = _text(value)
    if normalized is None:
        return ""
    try:
        return date.fromisoformat(normalized).strftime("%m/%d/%Y")
    except ValueError as error:
        raise TAMESSelectionError(
            "invalid_date_filter",
            "date filters must use YYYY-MM-DD",
            details={"value": normalized},
        ) from error


def _schema(value: Any) -> str:
    return schema_fingerprint(inferred_schema([value]))


def _court_payload(court_code: str) -> dict[str, Any]:
    normalized = normalize_court_code(court_code)
    return {
        "court_id": f"tx-appellate-{normalized}",
        "native_court_id": normalized,
        "name": COURT_NAMES[normalized],
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "official_url": f"{BASE_URL}/CaseSearch.aspx?coa={normalized}",
    }


def normalize_court_code(value: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise TAMESSelectionError("court_required", "a court code is required")
    folded = normalized.casefold().replace("-", "").replace("_", "")
    aliases = {
        "supreme": "cossup",
        "supremecourt": "cossup",
        "sc": "cossup",
        "cca": "coscca",
        "criminalappeals": "coscca",
        "courtofcriminalappeals": "coscca",
    }
    folded = aliases.get(folded, folded)
    match = re.fullmatch(r"(?:coa)?0?(\d{1,2})", folded)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 15:
            folded = f"coa{number:02d}"
    if folded not in COURT_NAMES:
        raise TAMESSelectionError(
            "invalid_court_code",
            f"unknown Texas appellate court code: {value}",
            details={"supported": sorted(COURT_NAMES)},
        )
    return folded


def infer_court_code(case_number: str) -> str:
    normalized = _text(case_number)
    if normalized is None:
        raise TAMESSelectionError(
            "case_number_required",
            "a case number is required",
        )
    upper = normalized.upper()
    match = re.fullmatch(r"(\d{2})-\d{2}-\d{5}-(?:CV|CR)", upper)
    if match and 1 <= int(match.group(1)) <= 15:
        return f"coa{int(match.group(1)):02d}"
    if re.fullmatch(r"(?:WR|AP|PD)-.+", upper):
        return "coscca"
    if re.fullmatch(r"\d{2}-\d{4}", upper):
        return "cossup"
    raise TAMESSelectionError(
        "court_code_required",
        "could not infer the appellate court; pass --court-code",
        details={"case_number": normalized},
    )


def _case_url(case_number: str, court_code: str) -> str:
    return (
        f"{BASE_URL}/Case.aspx?"
        + urlencode({"cn": case_number, "coa": court_code})
    )


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    return {
        str(node.get("name")): str(node.get("value") or "")
        for node in soup.select("input[type=hidden][name]")
    }


def _select_value(
    soup: BeautifulSoup,
    select_id: str,
    requested: str | None,
) -> str:
    normalized = _text(requested)
    if normalized is None:
        return ""
    select = soup.find("select", id=select_id)
    if not isinstance(select, Tag):
        raise TAMESRequestError(
            "source_schema_changed",
            f"TAMES form no longer exposes {select_id}",
            status=ResultStatus.SOURCE_CHANGED,
        )
    for option in select.find_all("option"):
        label = _text(option.get_text(" ", strip=True))
        value = _text(option.get("value"))
        if normalized.casefold() in {
            (label or "").casefold(),
            (value or "").casefold(),
        }:
            return value or ""
    raise TAMESSelectionError(
        "unknown_form_option",
        f"TAMES does not list {requested!r} for {select_id}",
        details={"field": select_id, "value": requested},
    )


def _criteria_payload(
    soup: BeautifulSoup,
    criteria: Mapping[str, Any],
    *,
    submit: bool,
) -> dict[str, str]:
    payload = _hidden_fields(soup)
    payload.update(
        {
            "ctl00$ContentPlaceHolder1$SearchType": "rbSearchByCase",
            "ctl00$ContentPlaceHolder1$olCaseType": CASE_TYPE_VALUES[
                str(criteria.get("case_type") or "both")
            ],
            "ctl00$ContentPlaceHolder1$txtCaseNumber": "",
            "ctl00$ContentPlaceHolder1$txtPartialCaseNumber": "",
            "ctl00$ContentPlaceHolder1$txtStyle1": "",
            "ctl00$ContentPlaceHolder1$txtStyle2": str(
                criteria.get("style_other") or ""
            ),
            "ctl00$ContentPlaceHolder1$txtAttorneyNameOrBarNumber": "",
            "ctl00$ContentPlaceHolder1$txtTrialCourtCaseNumber": "",
            "ctl00$ContentPlaceHolder1$txtDateFiledStart$dateInput": _form_date(
                criteria.get("date_from")
            ),
            "ctl00$ContentPlaceHolder1$txtDateFiledEnd$dateInput": _form_date(
                criteria.get("date_to")
            ),
            "ctl00$ContentPlaceHolder1$ddlOriginateCOA": _select_value(
                soup,
                "ctl00_ContentPlaceHolder1_ddlOriginateCOA",
                criteria.get("originating_coa"),
            ),
            "ctl00$ContentPlaceHolder1$ddCounty": _select_value(
                soup,
                "ctl00_ContentPlaceHolder1_ddCounty",
                criteria.get("county"),
            ),
            "ctl00$ContentPlaceHolder1$ddlTrialCourt": _select_value(
                soup,
                "ctl00_ContentPlaceHolder1_ddlTrialCourt",
                criteria.get("trial_court"),
            ),
        }
    )
    scope = str(criteria["scope"])
    payload[SEARCH_SCOPE_FIELDS[scope]] = str(criteria["query"])
    if criteria.get("exclude_inactive"):
        payload["ctl00$ContentPlaceHolder1$chkExcludeInactive"] = "on"

    courts = tuple(criteria.get("courts") or ("all",))
    if "all" in courts:
        payload["ctl00$ContentPlaceHolder1$chkAllCourts"] = "on"
    else:
        for court_code in courts:
            index = COURT_CHECKBOX_INDEX[normalize_court_code(str(court_code))]
            payload[
                f"ctl00$ContentPlaceHolder1$chkListCourts${index}"
            ] = "on"
    if submit:
        payload["ctl00$ContentPlaceHolder1$btnSearch"] = "Search"
    return payload


def parse_search_page(html: str) -> TAMESSearchPage:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table[id$='grdCases_ctl00']")
    rows: list[TAMESSearchRow] = []
    if isinstance(table, Tag):
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue
            link = tr.find("a", href=re.compile(r"Case\.aspx\?", re.I))
            if not isinstance(link, Tag):
                continue
            source_url = urljoin(SEARCH_URL, str(link.get("href")))
            parameters = parse_qs(urlparse(source_url).query)
            case_number = _text(parameters.get("cn", [None])[0])
            court_code = _text(parameters.get("coa", [None])[0])
            if case_number is None or court_code is None:
                continue
            values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
            values.extend([None] * (11 - len(values)))
            coa_numbers = tuple(
                token
                for token in re.split(r"\s+", values[5] or "")
                if token
            )
            rows.append(
                TAMESSearchRow(
                    case_number=case_number,
                    court_code=normalize_court_code(court_code),
                    filed_date=_date(values[1]),
                    style=values[2],
                    versus=values[3],
                    case_type=values[4],
                    coa_case_numbers=coa_numbers,
                    trial_case_number=values[6],
                    trial_county=values[7],
                    trial_court=values[8],
                    appellate_court_label=values[9],
                    source_url=source_url,
                    raw={
                        "values": values,
                        "href": str(link.get("href")),
                    },
                )
            )

    pager_text = next(
        (
            _text(node.get_text(" ", strip=True))
            for node in soup.select(".rgInfoPart")
            if _text(node.get_text(" ", strip=True))
        ),
        None,
    )
    pager_match = re.search(
        r"(?P<items>\d+)\s+items?\s+in\s+(?P<pages>\d+)\s+pages?",
        pager_text or "",
        re.I,
    )
    if pager_match:
        total_reported = int(pager_match.group("items"))
        total_pages = int(pager_match.group("pages"))
    elif rows:
        total_reported = len(rows)
        total_pages = 1
    else:
        total_reported = 0
        total_pages = 0

    current_control = soup.select_one(".rgCurrentPage")
    current_text = (
        _text(
            current_control.get("value")
            or current_control.get_text(" ", strip=True)
        )
        if isinstance(current_control, Tag)
        else None
    )
    current_match = re.search(r"\d+", current_text or "")
    current_page = int(current_match.group()) if current_match else 1
    next_control = soup.select_one("input.rgPageNext[name]")
    next_name = (
        str(next_control.get("name")) if isinstance(next_control, Tag) else None
    )

    recognizable = (
        isinstance(soup.find("form", id="aspnetForm"), Tag)
        and (
            isinstance(table, Tag)
            or "no records to display" in soup.get_text(" ", strip=True).casefold()
        )
    )
    if not recognizable:
        raise TAMESRequestError(
            "source_schema_changed",
            "TAMES search response lacks the expected form/results structure",
            status=ResultStatus.SOURCE_CHANGED,
        )
    schema_payload = {
        "table_headers": (
            [
                _text(node.get_text(" ", strip=True))
                for node in table.select("thead th")
            ]
            if isinstance(table, Tag)
            else []
        ),
        "row_keys": list(TAMESSearchRow.__dataclass_fields__),
        "pager": bool(pager_match),
    }
    return TAMESSearchPage(
        rows=tuple(rows),
        current_page=current_page,
        total_pages=total_pages,
        total_reported=total_reported,
        source_ceiling_reached=total_reported == SOURCE_RESULT_CEILING,
        next_control_name=next_name,
        schema_fingerprint=_schema(schema_payload),
        html=html,
    )


def _labeled_fields(container: Tag | None) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    if not isinstance(container, Tag):
        return fields
    for label in container.find_all("label"):
        key = _text(label.get_text(" ", strip=True))
        label_container = label.find_parent("div")
        if key is None or not isinstance(label_container, Tag):
            continue
        value_container = label_container.find_next_sibling("div")
        value = (
            _text(value_container.get_text(" ", strip=True))
            if isinstance(value_container, Tag)
            else None
        )
        fields[key.rstrip(":")] = value
    return fields


def _split_lines(cell: Tag) -> list[str]:
    raw = cell.get_text("\n", strip=True)
    return [
        normalized
        for part in raw.splitlines()
        if (normalized := _text(part)) is not None
    ]


def _file_size(label: str | None) -> int | None:
    normalized = _text(label)
    if normalized is None:
        return None
    match = re.search(r"/\s*([\d.]+)\s*(KB|MB|GB)\s*\]", normalized, re.I)
    if not match:
        return None
    multiplier = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[
        match.group(2).upper()
    ]
    return int(float(match.group(1)) * multiplier)


def _documents_from_cell(
    cell: Tag,
    *,
    filed_date: str | None,
    docket_entry_id: str | None = None,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for link in cell.find_all("a", href=re.compile(r"SearchMedia\.aspx\?", re.I)):
        source_url = urljoin(BASE_URL, str(link.get("href")))
        parameters = parse_qs(urlparse(source_url).query)
        native_id = _text(parameters.get("MediaVersionID", [None])[0])
        if native_id is None:
            continue
        link_cell = link.find_parent("td")
        description_cell = (
            link_cell.find_next_sibling("td")
            if isinstance(link_cell, Tag)
            else None
        )
        description = (
            _text(description_cell.get_text(" ", strip=True))
            if isinstance(description_cell, Tag)
            else None
        )
        document = {
            "native_document_id": native_id,
            "media_version_id": native_id,
            "media_id": _text(parameters.get("MediaID", [None])[0]),
            "court_code": _text(parameters.get("coa", [None])[0]),
            "document_type": _text(parameters.get("DT", [None])[0]),
            "description": description,
            "filed_date": filed_date,
            "source_url": source_url,
            "mime_type": "application/pdf",
            "file_size": _file_size(_text(link.get_text(" ", strip=True))),
            "access_state": "public",
            "native_access_state": "public_pdf_link",
            "certified_record": False,
            "raw": {
                "href": str(link.get("href")),
                "label": _text(link.get_text(" ", strip=True)),
            },
        }
        if docket_entry_id is not None:
            document["docket_entry_native_id"] = docket_entry_id
        documents.append(document)
    return documents


def _table_rows(soup: BeautifulSoup, table_suffix: str) -> list[list[Tag]]:
    table = soup.select_one(f"table[id$='{table_suffix}']")
    if not isinstance(table, Tag):
        return []
    return [
        row.find_all("td", recursive=False)
        for row in table.select("tbody tr")
        if row.find_all("td", recursive=False)
    ]


def parse_case_page(
    html: str,
    *,
    source_url: str,
    expected_case_number: str | None = None,
    expected_court_code: str | None = None,
) -> TAMESCasePage | None:
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find(id="panelTextSelection")
    fields = _labeled_fields(panel if isinstance(panel, Tag) else None)
    case_number = _text(fields.get("Case"))
    if case_number is None:
        page_text = soup.get_text(" ", strip=True).casefold()
        if "case not found" in page_text or "no records" in page_text:
            return None
        raise TAMESRequestError(
            "source_schema_changed",
            "TAMES case response lacks the expected case metadata panel",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if expected_case_number and case_number.casefold() != expected_case_number.casefold():
        raise TAMESRequestError(
            "case_identity_mismatch",
            "TAMES returned a different case number than requested",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "requested": expected_case_number,
                "returned": case_number,
            },
        )
    parameters = parse_qs(urlparse(source_url).query)
    court_code = _text(parameters.get("coa", [None])[0]) or expected_court_code
    if court_code is None:
        raise TAMESRequestError(
            "source_schema_changed",
            "TAMES case URL lacks a court code",
            status=ResultStatus.SOURCE_CHANGED,
        )
    court_code = normalize_court_code(court_code)
    if expected_court_code and court_code != normalize_court_code(expected_court_code):
        raise TAMESRequestError(
            "court_identity_mismatch",
            "TAMES returned a different court than requested",
            status=ResultStatus.SOURCE_CHANGED,
        )
    heading = soup.find("h1")
    appellate_court_name = (
        _text(heading.get_text(" ", strip=True))
        if isinstance(heading, Tag)
        else COURT_NAMES[court_code]
    ) or COURT_NAMES[court_code]

    parties: list[dict[str, Any]] = []
    for sequence, cells in enumerate(
        _table_rows(soup, "grdParty_ctl00"),
        start=1,
    ):
        if len(cells) < 2:
            continue
        raw_name = _text(cells[0].get_text(" ", strip=True))
        role = _text(cells[1].get_text(" ", strip=True))
        if raw_name is None or role is None:
            continue
        representatives = _split_lines(cells[2]) if len(cells) > 2 else []
        parties.append(
            {
                "sequence_no": sequence,
                "role": role,
                "raw_name": raw_name,
                "access_state": "public",
                "attorneys": [
                    {
                        "raw_name": representative,
                        "source_role": "Representative",
                    }
                    for representative in representatives
                ],
                "raw": {
                    "party": raw_name,
                    "party_type": role,
                    "representatives": representatives,
                },
            }
        )

    event_signatures: Counter[str] = Counter()
    docket_entries: list[dict[str, Any]] = []
    for sequence, cells in enumerate(
        _table_rows(soup, "grdEvents_ctl00"),
        start=1,
    ):
        if len(cells) < 3:
            continue
        event_date = _date(cells[0].get_text(" ", strip=True))
        event_type = _text(cells[1].get_text(" ", strip=True)) or "Case event"
        disposition = _text(cells[2].get_text(" ", strip=True))
        preliminary_documents = (
            _documents_from_cell(cells[3], filed_date=event_date)
            if len(cells) > 3
            else []
        )
        signature_payload = {
            "date": event_date,
            "event_type": event_type,
            "disposition": disposition,
            "documents": [
                document["native_document_id"]
                for document in preliminary_documents
            ],
        }
        signature = sha256_fingerprint(signature_payload)[:20]
        event_signatures[signature] += 1
        native_entry_id = (
            f"{case_number}:event:{signature}:{event_signatures[signature]}"
        )
        documents = [
            {
                **document,
                "docket_entry_native_id": native_entry_id,
            }
            for document in preliminary_documents
        ]
        docket_entries.append(
            {
                "native_entry_id": native_entry_id,
                "sequence_no": sequence,
                "event_code": event_type,
                "event_type": event_type,
                "raw_text": event_type,
                "filed_date": event_date,
                "event_date": event_date,
                "disposition": disposition,
                "document_available": bool(documents),
                "access_state": "public",
                "documents": documents,
                "identity_basis": {
                    **signature_payload,
                    "same_signature_occurrence": event_signatures[signature],
                },
                "raw": {
                    "date": event_date,
                    "event_type": event_type,
                    "disposition": disposition,
                },
            }
        )

    calendars: list[dict[str, Any]] = []
    for cells in _table_rows(soup, "grdCalendar_ctl00"):
        values = [
            _text(cell.get_text(" ", strip=True))
            for cell in cells
        ]
        values.extend([None] * (3 - len(values)))
        calendars.append(
            {
                "set_date": _date(values[0]),
                "calendar_type": values[1],
                "reason_set": values[2],
            }
        )

    briefs: list[dict[str, Any]] = []
    for cells in _table_rows(soup, "grdBriefs_ctl00"):
        if len(cells) < 3:
            continue
        filed_date = _date(cells[0].get_text(" ", strip=True))
        briefs.append(
            {
                "filed_date": filed_date,
                "event_type": _text(cells[1].get_text(" ", strip=True)),
                "description": _text(cells[2].get_text(" ", strip=True)),
                "documents": (
                    _documents_from_cell(cells[3], filed_date=filed_date)
                    if len(cells) > 3
                    else []
                ),
            }
        )

    trial_panel = soup.find(id="panelTrialCourtInfo")
    trial_fields = _labeled_fields(
        trial_panel if isinstance(trial_panel, Tag) else None
    )
    raw_payload = {
        "fields": fields,
        "trial_court_fields": trial_fields,
        "parties": parties,
        "docket_entry_count": len(docket_entries),
        "calendar_events": calendars,
        "appellate_briefs": briefs,
    }
    return TAMESCasePage(
        case_number=case_number,
        court_code=court_code,
        appellate_court_name=appellate_court_name,
        fields=fields,
        trial_court_fields=trial_fields,
        parties=tuple(parties),
        docket_entries=tuple(docket_entries),
        calendar_events=tuple(calendars),
        appellate_briefs=tuple(briefs),
        schema_fingerprint=_schema(raw_payload),
        source_url=source_url,
        raw=raw_payload,
    )


def _search_row_from_case(page: TAMESCasePage) -> TAMESSearchRow:
    return TAMESSearchRow(
        case_number=page.case_number,
        court_code=page.court_code,
        filed_date=_date(page.fields.get("Date Filed")),
        style=_text(page.fields.get("Style")),
        versus=_text(page.fields.get("v.")),
        case_type=_text(page.fields.get("Case Type")),
        coa_case_numbers=(),
        trial_case_number=_text(
            page.trial_court_fields.get("Court Case")
        ),
        trial_county=_text(page.trial_court_fields.get("County")),
        trial_court=_text(page.trial_court_fields.get("Court")),
        appellate_court_label=page.appellate_court_name,
        source_url=page.source_url,
        raw={
            "detail_redirect": True,
            "fields": dict(page.fields),
            "trial_court_fields": dict(page.trial_court_fields),
        },
    )


def parse_search_response(
    html: str,
    *,
    source_url: str,
) -> TAMESSearchPage:
    """Parse either a results grid or TAMES's one-match detail redirect."""
    try:
        return parse_search_page(html)
    except TAMESRequestError as search_error:
        try:
            case_page = parse_case_page(html, source_url=source_url)
        except TAMESRequestError:
            raise search_error
        if case_page is None:
            raise search_error
        row = _search_row_from_case(case_page)
        return TAMESSearchPage(
            rows=(row,),
            current_page=1,
            total_pages=1,
            total_reported=1,
            source_ceiling_reached=False,
            next_control_name=None,
            schema_fingerprint=_schema(
                {
                    "response_kind": "single_case_redirect",
                    "case_schema": case_page.schema_fingerprint,
                    "row_keys": list(
                        TAMESSearchRow.__dataclass_fields__
                    ),
                }
            ),
            html=html,
        )


class TexasTAMESClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self._last_request_at = 0.0
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "*/*;q=0.8"
                ),
            }
        )
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    def close(self) -> None:
        self.session.close()

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self._wait()
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as error:
            raise TAMESRequestError(
                "transport_error",
                str(error),
                retryable=True,
                details={"url": url, "method": method},
            ) from error
        finally:
            self._last_request_at = time.monotonic()
        if response.status_code == 429:
            raise TAMESRequestError(
                "rate_limited",
                "TAMES returned HTTP 429",
                status=ResultStatus.RATE_LIMITED,
                retryable=True,
                details={"url": url},
            )
        if response.status_code == 403:
            raise TAMESRequestError(
                "source_rejected_request",
                "TAMES returned HTTP 403",
                status=ResultStatus.RESTRICTED,
                details={"url": url},
            )
        if response.status_code >= 400:
            raise TAMESRequestError(
                "http_error",
                f"TAMES returned HTTP {response.status_code}",
                retryable=response.status_code >= 500,
                details={"url": url, "status_code": response.status_code},
            )
        return response

    def _initial_search_form(self) -> BeautifulSoup:
        response = self._request("GET", SEARCH_URL)
        soup = BeautifulSoup(response.text, "html.parser")
        if not isinstance(soup.find("form", id="aspnetForm"), Tag):
            raise TAMESRequestError(
                "source_schema_changed",
                "TAMES search form is missing",
                status=ResultStatus.SOURCE_CHANGED,
            )
        return soup

    def search_pages(
        self,
        criteria: Mapping[str, Any],
        *,
        target_page: int,
        limit: int,
        offset: int,
    ) -> tuple[list[TAMESSearchRow], TAMESSearchPage, int, int]:
        soup = self._initial_search_form()
        payload = _criteria_payload(soup, criteria, submit=True)
        headers = {"Origin": BASE_URL, "Referer": SEARCH_URL}
        response = self._request(
            "POST",
            SEARCH_URL,
            data=payload,
            headers=headers,
        )
        page = parse_search_response(
            response.text,
            source_url=str(getattr(response, "url", SEARCH_URL)),
        )
        while page.current_page < target_page:
            page_soup = BeautifulSoup(page.html, "html.parser")
            if page.next_control_name is None:
                raise TAMESSelectionError(
                    "cursor_past_end",
                    "cursor points beyond the last source page",
                )
            next_payload = _criteria_payload(
                page_soup,
                criteria,
                submit=False,
            )
            next_payload[page.next_control_name] = " "
            response = self._request(
                "POST",
                SEARCH_URL,
                data=next_payload,
                headers=headers,
            )
            page = parse_search_response(
                response.text,
                source_url=str(getattr(response, "url", SEARCH_URL)),
            )

        selected: list[TAMESSearchRow] = []
        current_offset = offset
        if current_offset > len(page.rows):
            raise TAMESSelectionError(
                "cursor_past_page",
                "cursor offset points beyond the source page",
                details={
                    "page": page.current_page,
                    "offset": current_offset,
                    "row_count": len(page.rows),
                },
            )
        while len(selected) < limit:
            remaining = limit - len(selected)
            available = page.rows[
                current_offset : current_offset + remaining
            ]
            selected.extend(available)
            current_offset += len(available)
            if len(selected) >= limit:
                break
            if (
                page.current_page >= page.total_pages
                or page.next_control_name is None
            ):
                current_offset = len(page.rows)
                break
            page_soup = BeautifulSoup(page.html, "html.parser")
            next_payload = _criteria_payload(
                page_soup,
                criteria,
                submit=False,
            )
            next_payload[page.next_control_name] = " "
            response = self._request(
                "POST",
                SEARCH_URL,
                data=next_payload,
                headers=headers,
            )
            page = parse_search_response(
                response.text,
                source_url=str(getattr(response, "url", SEARCH_URL)),
            )
            current_offset = 0

        consumed_offset = current_offset
        if consumed_offset >= len(page.rows) and page.current_page < page.total_pages:
            next_page = page.current_page + 1
            next_offset = 0
        else:
            next_page = page.current_page
            next_offset = consumed_offset
        return selected, page, next_page, next_offset

    def case(
        self,
        case_number: str,
        *,
        court_code: str,
    ) -> TAMESCasePage | None:
        source_url = _case_url(case_number, court_code)
        response = self._request("GET", source_url)
        return parse_case_page(
            response.text,
            source_url=source_url,
            expected_case_number=case_number,
            expected_court_code=court_code,
        )

    def probe(self) -> dict[str, Any]:
        soup = self._initial_search_form()
        court_labels = [
            _text(label.get_text(" ", strip=True))
            for label in soup.select(
                "#ctl00_ContentPlaceHolder1_chkListCourts label"
            )
        ]
        county_options = soup.select(
            "#ctl00_ContentPlaceHolder1_ddCounty option[value]"
        )
        trial_options = soup.select(
            "#ctl00_ContentPlaceHolder1_ddlTrialCourt option[value]"
        )
        return {
            "source_url": SEARCH_URL,
            "form_action": str(
                soup.find("form", id="aspnetForm").get("action")
            ),
            "court_labels": [label for label in court_labels if label],
            "county_option_count": len(county_options),
            "trial_court_option_count": len(trial_options),
            "schema_fingerprint": _schema(
                {
                    "court_labels": court_labels,
                    "search_fields": sorted(SEARCH_SCOPE_FIELDS),
                    "county_select": bool(county_options),
                    "trial_court_select": bool(trial_options),
                }
            ),
        }

    def download(self, source_url: str, native_document_id: str) -> TAMESDownload:
        response = self._request("GET", source_url)
        raw_content_type = _text(response.headers.get("Content-Type"))
        media_type = (
            raw_content_type.split(";", 1)[0].strip().lower()
            if raw_content_type
            else ""
        )
        if (
            "pdf" not in media_type.casefold()
            and not response.content.startswith(b"%PDF-")
        ):
            raise TAMESRequestError(
                "document_response_not_pdf",
                "TAMES document response is not a PDF",
                status=ResultStatus.SOURCE_CHANGED,
                details={
                    "url": source_url,
                    "content_type": media_type,
                },
            )
        disposition = _text(response.headers.get("Content-Disposition"))
        filename_match = re.search(
            r"filename=(?:\"([^\"]+)\"|([^;\s]+))",
            disposition or "",
            re.I,
        )
        filename = (
            next(
                (
                    value
                    for value in filename_match.groups()
                    if value
                ),
                None,
            )
            if filename_match
            else None
        )
        return TAMESDownload(
            native_document_id=native_document_id,
            source_url=source_url,
            content=response.content,
            media_type=media_type,
            raw_content_type=raw_content_type,
            filename=filename,
        )


def _caption(style: str | None, versus: str | None) -> str | None:
    if style and versus:
        return f"{style} v. {versus}"
    return style or versus


def _originating_case_relation(
    *,
    appellate_case_number: str,
    appellate_court_code: str,
    raw_case_number: str,
    court_name: str | None,
    county: str | None,
    judge: str | None = None,
    reporter: str | None = None,
    source_url: str,
) -> dict[str, Any]:
    identity_basis = {
        "appellate_case_number": appellate_case_number,
        "appellate_court_code": appellate_court_code,
        "raw_case_number": raw_case_number,
        "court_name": court_name,
        "county": county,
    }
    return {
        "native_relation_id": (
            f"{appellate_court_code}:{appellate_case_number}:"
            f"originating-trial:{sha256_fingerprint(identity_basis)[:20]}"
        ),
        "relation_type": "originating_trial_case",
        "raw_case_number": raw_case_number,
        "court_name": court_name,
        "county": county,
        "judge": judge,
        "reporter": reporter,
        "source_url": source_url,
        "identity_basis": identity_basis,
    }


def _calendar_case_events(
    case_number: str,
    calendar_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    signatures: Counter[str] = Counter()
    events: list[dict[str, Any]] = []
    for calendar in calendar_events:
        identity_basis = {
            "set_date": _date(calendar.get("set_date")),
            "calendar_type": _text(calendar.get("calendar_type")),
            "reason_set": _text(calendar.get("reason_set")),
        }
        signature = sha256_fingerprint(identity_basis)[:20]
        signatures[signature] += 1
        events.append(
            {
                "native_event_id": (
                    f"{case_number}:calendar:{signature}:"
                    f"{signatures[signature]}"
                ),
                "event_type": "calendar_setting",
                "event_date": identity_basis["set_date"],
                "disposition": identity_basis["reason_set"],
                "assertion_kind": "docket_metadata",
                "calendar_type": identity_basis["calendar_type"],
                "reason_set": identity_basis["reason_set"],
                "identity_basis": {
                    **identity_basis,
                    "same_signature_occurrence": signatures[signature],
                },
                "raw": dict(calendar),
            }
        )
    return events


def normalize_search_row(row: TAMESSearchRow, schema: str) -> dict[str, Any]:
    originating_cases = (
        [
            {
                "case_number": row.trial_case_number,
                "county": row.trial_county,
                "court": row.trial_court,
            }
        ]
        if row.trial_case_number
        else []
    )
    case_relations = (
        [
            _originating_case_relation(
                appellate_case_number=row.case_number,
                appellate_court_code=row.court_code,
                raw_case_number=row.trial_case_number,
                court_name=row.trial_court,
                county=row.trial_county,
                source_url=row.source_url,
            )
        ]
        if row.trial_case_number
        else []
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            f"tx-appellate-{row.court_code}",
            row.case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(row.court_code),
        "raw_case_number": row.case_number,
        "display_case_number": row.case_number,
        "source_internal_id": f"{row.court_code}:{row.case_number}",
        "caption": _caption(row.style, row.versus),
        "case_type": row.case_type,
        "filing_date": row.filed_date,
        "status": None,
        "access_state": "public",
        "certified_record": False,
        "source_url": row.source_url,
        "originating_court_cases": originating_cases,
        "case_relations": case_relations,
        "related_appellate_case_numbers": list(row.coa_case_numbers),
        "parties": [],
        "docket_entries": [],
        "documents": [],
        "schema_fingerprint": schema,
        "raw": dict(row.raw),
    }


def normalize_case(page: TAMESCasePage) -> dict[str, Any]:
    caption = _caption(
        _text(page.fields.get("Style")),
        _text(page.fields.get("v.")),
    )
    trial_case = _text(page.trial_court_fields.get("Court Case"))
    trial_judge = _text(page.trial_court_fields.get("Court Judge"))
    trial_county = _text(page.trial_court_fields.get("County"))
    trial_court = _text(page.trial_court_fields.get("Court"))
    trial_reporter = _text(page.trial_court_fields.get("Reporter"))
    originating_cases = (
        [
            {
                "case_number": trial_case,
                "county": trial_county,
                "court": trial_court,
                "judge": trial_judge,
                "reporter": trial_reporter,
            }
        ]
        if trial_case
        else []
    )
    case_relations = (
        [
            _originating_case_relation(
                appellate_case_number=page.case_number,
                appellate_court_code=page.court_code,
                raw_case_number=trial_case,
                court_name=trial_court,
                county=trial_county,
                judge=trial_judge,
                reporter=trial_reporter,
                source_url=page.source_url,
            )
        ]
        if trial_case
        else []
    )
    calendar_events = list(page.calendar_events)
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            f"tx-appellate-{page.court_code}",
            page.case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(page.court_code),
        "raw_case_number": page.case_number,
        "display_case_number": page.case_number,
        "source_internal_id": f"{page.court_code}:{page.case_number}",
        "caption": caption,
        "case_type": _text(page.fields.get("Case Type")),
        "filing_date": _date(page.fields.get("Date Filed")),
        "status": None,
        "access_state": "public",
        "certified_record": False,
        "source_url": page.source_url,
        "original_proceeding": _text(page.fields.get("Orig Proc")),
        "transfer": {
            key: value
            for key, value in page.fields.items()
            if key.startswith("Transfer") and value
        },
        "originating_court_cases": originating_cases,
        "case_relations": case_relations,
        "parties": list(page.parties),
        "judicial_assignments": [],
        "docket_entries": list(page.docket_entries),
        "documents": [],
        "case_events": _calendar_case_events(
            page.case_number,
            calendar_events,
        ),
        "calendar_events": calendar_events,
        "appellate_briefs": list(page.appellate_briefs),
        "schema_fingerprint": page.schema_fingerprint,
        "raw": dict(page.raw),
    }


def _criteria_from_args(args: argparse.Namespace) -> dict[str, Any]:
    query = _text(getattr(args, "query", None))
    if query is None:
        raise TAMESSelectionError(
            "search_query_required",
            "search requires a query",
        )
    courts = tuple(getattr(args, "courts", None) or ("all",))
    normalized_courts = tuple(
        "all" if value.casefold() == "all" else normalize_court_code(value)
        for value in courts
    )
    if "all" in normalized_courts and len(normalized_courts) > 1:
        raise TAMESSelectionError(
            "conflicting_court_selection",
            "--court all cannot be combined with individual courts",
        )
    date_from = _text(getattr(args, "date_from", None))
    date_to = _text(getattr(args, "date_to", None))
    _form_date(date_from)
    _form_date(date_to)
    if date_to and not date_from:
        raise TAMESSelectionError(
            "date_start_required",
            "--date-to requires --date-from",
        )
    return {
        "query": query,
        "scope": args.scope,
        "style_other": _text(getattr(args, "style_other", None)),
        "case_type": args.case_type,
        "exclude_inactive": bool(args.exclude_inactive),
        "date_from": date_from,
        "date_to": date_to,
        "courts": normalized_courts,
        "originating_coa": _text(getattr(args, "originating_coa", None)),
        "county": _text(getattr(args, "county", None)),
        "trial_court": _text(getattr(args, "trial_court", None)),
    }


def _cursor_fingerprint(criteria: Mapping[str, Any]) -> str:
    return sha256_fingerprint(criteria)[:12]


def _parse_cursor(
    cursor: str | None,
    criteria: Mapping[str, Any],
) -> tuple[int, int]:
    if cursor is None:
        return 1, 0
    match = CURSOR_RE.fullmatch(cursor)
    if not match:
        raise TAMESSelectionError(
            "invalid_cursor",
            "cursor is not a Texas TAMES search cursor",
        )
    expected = _cursor_fingerprint(criteria)
    if match.group("fingerprint") != expected:
        raise TAMESSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to a different search",
        )
    page = int(match.group("page"))
    offset = int(match.group("offset"))
    if page < 1 or offset < 0:
        raise TAMESSelectionError("invalid_cursor", "invalid cursor position")
    return page, offset


def _cursor(criteria: Mapping[str, Any], page: int, offset: int) -> str:
    return (
        f"tx-tames:v1:page:{page}:offset:{offset}:"
        f"{_cursor_fingerprint(criteria)}"
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "query": getattr(args, "query", None),
            "scope": getattr(args, "scope", None),
            "style_other": getattr(args, "style_other", None),
            "case_type": getattr(args, "case_type", None),
            "exclude_inactive": getattr(args, "exclude_inactive", False),
            "date_from": getattr(args, "date_from", None),
            "date_to": getattr(args, "date_to", None),
            "courts": getattr(args, "courts", None),
            "originating_coa": getattr(args, "originating_coa", None),
            "county": getattr(args, "county", None),
            "trial_court": getattr(args, "trial_court", None),
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif args.command in {"case", "docket", "documents", "download"}:
        parameters = {
            "case_number": args.case_number,
            "court_code": getattr(args, "court_code", None),
        }
        if args.command == "download":
            parameters["document_id"] = args.document_id
            parameters["destination"] = str(args.destination)
    else:
        parameters = {"source_url": SEARCH_URL}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Texas",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: TAMESSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _request_failure(
    query: PublicRecordsQuery,
    error: TAMESRequestError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="source_request",
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: TexasTAMESClient,
) -> PublicRecordsResult:
    criteria = _criteria_from_args(args)
    if criteria["scope"] == "case-number":
        court_code = infer_court_code(str(criteria["query"]))
        page = client.case(str(criteria["query"]), court_code=court_code)
        records = [normalize_case(page)] if page is not None else []
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )
    target_page, offset = _parse_cursor(args.cursor, criteria)
    rows, page, next_page, next_offset = client.search_pages(
        criteria,
        target_page=target_page,
        limit=args.limit,
        offset=offset,
    )
    records = [
        normalize_search_row(row, page.schema_fingerprint)
        for row in rows
    ]
    consumed_all = (
        not records
        or (
            next_page >= page.total_pages
            and next_offset >= len(page.rows)
        )
    )
    next_cursor = (
        None
        if consumed_all
        else _cursor(criteria, next_page, next_offset)
    )
    if page.source_ceiling_reached:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="source_result_ceiling",
                    message=(
                        "TAMES limited this search to 1,000 matched records"
                    ),
                    category="source_pagination",
                    retryable=False,
                    details={
                        "source_result_ceiling": SOURCE_RESULT_CEILING,
                        "total_reported": page.total_reported,
                        "total_pages": page.total_pages,
                    },
                )
            ],
            records=records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _case_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: TexasTAMESClient,
) -> PublicRecordsResult:
    court_code = (
        normalize_court_code(args.court_code)
        if args.court_code
        else infer_court_code(args.case_number)
    )
    page = client.case(args.case_number, court_code=court_code)
    if page is None:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    record = normalize_case(page)
    if args.command == "docket":
        record = {
            **record,
            "parties": [],
            "judicial_assignments": [],
            "calendar_events": [],
            "appellate_briefs": [],
        }
    elif args.command == "documents":
        document_ids = {
            document["native_document_id"]
            for entry in record["docket_entries"]
            for document in entry.get("documents", [])
        }
        record = {
            **record,
            "parties": [],
            "judicial_assignments": [],
            "calendar_events": [],
            "appellate_briefs": [],
            "document_ids": sorted(document_ids),
        }
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=SOURCE_WARNINGS,
    )


def _download_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: TexasTAMESClient,
) -> PublicRecordsResult:
    court_code = (
        normalize_court_code(args.court_code)
        if args.court_code
        else infer_court_code(args.case_number)
    )
    page = client.case(args.case_number, court_code=court_code)
    if page is None:
        raise TAMESSelectionError(
            "case_not_found",
            f"TAMES did not return case {args.case_number}",
        )
    matching = [
        document
        for entry in page.docket_entries
        for document in entry.get("documents", [])
        if str(document.get("native_document_id")) == args.document_id
    ]
    if not matching:
        raise TAMESSelectionError(
            "document_not_found",
            "document id is not present in the public case events",
            details={
                "case_number": args.case_number,
                "document_id": args.document_id,
            },
        )
    source_url = str(matching[0]["source_url"])
    downloaded = client.download(source_url, args.document_id)
    destination = Path(args.destination).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(downloaded.content)
    digest = hashlib.sha256(downloaded.content).hexdigest()
    record = {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/tx-appellate-{court_code}/"
            f"{args.case_number}/document/{args.document_id}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "document_download",
        "case_number": args.case_number,
        "court": _court_payload(court_code),
        "native_document_id": args.document_id,
        "source_url": source_url,
        "storage_path": str(destination.resolve()),
        "sha256": digest,
        "mime_type": downloaded.media_type,
        "raw_content_type": downloaded.raw_content_type,
        "filename": downloaded.filename,
        "byte_count": len(downloaded.content),
        "access_state": "public",
        "native_access_state": "public_pdf_download",
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination.resolve())],
        warnings=SOURCE_WARNINGS,
    )


def _probe_result(
    query: PublicRecordsQuery,
    client: TexasTAMESClient,
) -> PublicRecordsResult:
    probe = client.probe()
    record = {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/probe/tames-search",
        "source_id": SOURCE_ID,
        "record_kind": "probe",
        "source_url": SEARCH_URL,
        "help_url": HELP_URL,
        "court_count": len(probe["court_labels"]),
        **probe,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: TexasTAMESClient | Any | None = None,
) -> PublicRecordsResult:
    # The unified router resolves the catalog decision before dispatch.  Keep
    # the direct adapter focused on the source protocol while accepting the
    # shared adapter interface used by that router.
    del access_decision
    query = build_query(args)
    source_client = client or TexasTAMESClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )
    owns_client = client is None
    try:
        if args.command == "search":
            result = _search_result(args, query, source_client)
        elif args.command in {"case", "docket", "documents"}:
            result = _case_result(args, query, source_client)
        elif args.command == "download":
            result = _download_result(args, query, source_client)
        elif args.command == "probe":
            result = _probe_result(query, source_client)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except TAMESSelectionError as error:
        result = _selection_failure(query, error)
    except TAMESRequestError as error:
        result = _request_failure(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            source_client.close()
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Texas appellate {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Texas appellate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number')} | "
                f"{record.get('filing_date') or '?'} | "
                f"{record.get('caption') or '?'}"
            )
        else:
            print(f"  {record.get('record_kind')} | {record.get('source_url')}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    add_output_args(parser)


def _add_case_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("case_number")
    parser.add_argument(
        "--court-code",
        help="cossup, coscca, or coa01 through coa15",
    )
    _add_common(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official Texas TAMES appellate court portal"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search statewide appellate cases")
    search.add_argument("query")
    search.add_argument(
        "--scope",
        choices=tuple(SEARCH_SCOPE_FIELDS),
        default="style",
    )
    search.add_argument(
        "--style-other",
        help="Optional opposite side of the case style",
    )
    search.add_argument(
        "--case-type",
        choices=tuple(CASE_TYPE_VALUES),
        default="both",
    )
    search.add_argument("--exclude-inactive", action="store_true")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument(
        "--court",
        dest="courts",
        action="append",
        help="Repeat for selected courts; default is all",
    )
    search.add_argument("--originating-coa")
    search.add_argument("--county")
    search.add_argument("--trial-court")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--cursor")
    _add_common(search)

    case = sub.add_parser("case", help="Fetch full public case detail")
    _add_case_selector(case)
    docket = sub.add_parser("docket", help="Fetch public case events")
    _add_case_selector(docket)
    documents = sub.add_parser(
        "documents",
        help="Fetch public document metadata attached to case events",
    )
    _add_case_selector(documents)

    download = sub.add_parser("download", help="Download one public PDF")
    download.add_argument("case_number")
    download.add_argument("document_id")
    download.add_argument("destination", type=Path)
    download.add_argument("--court-code")
    _add_common(download)

    probe = sub.add_parser("probe", help="Verify the live source structure")
    _add_common(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
