#!/usr/bin/env python3
"""Query Delaware CourtConnect's public civil case and judgment index.

CourtConnect is the Delaware Judiciary's anonymous, server-rendered civil
index. It supports party/business searches, judgment searches, and case-level
docket reports. The source serves 20 search hits per page and exposes native
continuation links; this adapter follows every page unless ``--page`` requests
one native page.

Examples:
    uv run python tools/query_delaware_courts.py cases TESLA --partial \
        --output tesla-cases.json
    uv run python tools/query_delaware_courts.py case JP13-23-013991 \
        --output jp-case.json
    uv run python tools/query_delaware_courts.py judgments TESLA --partial \
        --output tesla-judgments.json
    uv run python tools/query_delaware_courts.py judgment 775119 4623454 \
        --name "TESLA BIOHEALING" --json
    uv run python tools/query_delaware_courts.py options --json
    uv run python tools/query_delaware_courts.py probe --json
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
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import acquisition_result_status
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
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import acquisition_result_status
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
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-de-courtconnect"
STATE_CODE = "DE"
STATE_GEOID = "10"
COURT_ID = "de-courtconnect-statewide"
COURT_NAME = "Delaware Judiciary CourtConnect"
OFFICIAL_CIVIL_SEARCH_URL = "https://courts.delaware.gov/docket.aspx"
HOST_ROOT = "https://courtconnect.courts.delaware.gov"
BASE_URL = f"{HOST_ROOT}/cc/cconnect"
SEARCH_HOME_URL = (
    f"{BASE_URL}/ck_public_qry_main.cp_main_srch_options"
)
DISCLAIMER_URL = f"{BASE_URL}/ck_public_qry_main.cp_main_disclaimer"
DISCLAIMER_DOCUMENT_URL = f"{HOST_ROOT}/cconnect/docs/disclaim.htm"
HELP_URL = f"{HOST_ROOT}/cconnect/docs/help.htm"
PARTY_SETUP_URL = (
    f"{BASE_URL}/ck_public_qry_cpty.cp_personcase_srch_setup"
)
PARTY_RESULTS_URL = (
    f"{BASE_URL}/ck_public_qry_cpty.cp_personcase_srch_details"
)
CASE_REPORT_URL = (
    f"{BASE_URL}/ck_public_qry_doct.cp_dktrpt_docket_report"
)
JUDGMENT_SETUP_URL = (
    f"{BASE_URL}/ck_public_qry_judg.cp_judgment_srch_setup"
)
JUDGMENT_RESULTS_URL = (
    f"{BASE_URL}/ck_public_qry_judg.cp_judgment_srch_rslt"
)
JUDGMENT_DETAIL_URL = (
    f"{BASE_URL}/ck_public_qry_judg.cp_judgment_dtl_rslt"
)
OPINIONS_URL = "https://courts.delaware.gov/Opinions/"
SUPERIOR_DOCUMENT_ACCESS_URL = (
    "https://www.courts.delaware.gov/forms/download.aspx?id=191608"
)
COURT_RECORDS_REQUEST_URL = (
    "https://www.courts.delaware.gov/Forms/Download.aspx?id=43418"
)
FILE_AND_SERVEXPRESS_URL = "https://www.fileandservexpress.com"

PROBE_CASE_IDS = ("2026-0094", "JP13-23-013991")
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DELAWARE_TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

COMPLEMENTARY_SOURCES = (
    {
        "name": "Delaware Courts Opinions and Orders",
        "url": OPINIONS_URL,
        "role": "official_published_opinions_and_orders_with_pdf_downloads",
    },
    {
        "name": "Superior Court Access to Court Documents and Docket",
        "url": SUPERIOR_DOCUMENT_ACCESS_URL,
        "role": (
            "official_document_access_guidance_for_public_terminals_copies_"
            "and_remote_subscription_access"
        ),
    },
    {
        "name": "Application for Access to Court Records",
        "url": COURT_RECORDS_REQUEST_URL,
        "role": "official_request_route_for_dispositions_and_copies",
    },
    {
        "name": "File & ServeXpress",
        "url": FILE_AND_SERVEXPRESS_URL,
        "role": (
            "external_remote_docket_and_filing_route_named_by_delaware_"
            "court_materials"
        ),
    },
)

SOURCE_WARNINGS = (
    "CourtConnect identifies itself as not for official use; obtain an "
    "official or certified court record when that distinction matters.",
    "The source disclaimer says CourtConnect data may change and prohibits "
    "commercial use of data obtained through the site.",
    "The Delaware Judiciary advertises CourtConnect for Superior Court, Court "
    "of Common Pleas, and Justice of the Peace civil matters. Other records, "
    "including some Court of Chancery case stubs, may appear but should not be "
    "treated as complete coverage.",
    "CourtConnect exposes docket metadata, not a general public filing-image "
    "download service. Official opinions/orders, public terminals, records "
    "requests, and source-named remote services complement that ceiling.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Delaware Judiciary CourtConnect",
    source_role="state_civil_case_party_judgment_and_docket_index",
    base_url=OFFICIAL_CIVIL_SEARCH_URL,
    dataset_id="delaware-courtconnect-public",
    metadata={
        "authority": "Delaware Judiciary",
        "state_code": STATE_CODE,
        "authentication": "none",
        "access_class": "anonymous_public_with_source_disclaimer",
        "platform_family": "courtconnect_contexte",
        "search_home_url": SEARCH_HOME_URL,
        "help_url": HELP_URL,
        "disclaimer_url": DISCLAIMER_DOCUMENT_URL,
        "native_page_size": 20,
        "native_result_ceiling": None,
        "officially_advertised_courts": [
            "Superior Court",
            "Court of Common Pleas",
            "Justice of the Peace Court",
        ],
        "observed_additional_scope": (
            "Some Court of Chancery case stubs appear, without a complete "
            "filing-document collection."
        ),
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
    },
)


class CourtConnectError(RuntimeError):
    """Source, transport, or query error with result-envelope semantics."""

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


class CourtConnectSelectionError(CourtConnectError):
    """The requested selector does not match the source's native contract."""

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
            category="query_selection",
            details=details,
        )


class CourtConnectSourceChangedError(CourtConnectError):
    """The official HTML no longer matches the verified source contract."""

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
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


@dataclass(frozen=True)
class CourtConnectPage:
    """One parsed native CourtConnect result page."""

    records: tuple[Mapping[str, Any], ...]
    next_url: str | None
    page_number: int
    record_start: int | None
    record_end: int | None
    authoritative_empty: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class CourtConnectFetch:
    """One or more native pages fetched without an adapter-level cap."""

    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    next_url: str | None
    schema_fingerprint: str
    source_url: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(
        str(value).replace("\x00", "").replace("\xa0", " ").split()
    ).strip()
    return normalized or None


def _available_text(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.casefold() in {"unavailable", "none", "none."}:
        return None
    return normalized


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise CourtConnectSourceChangedError(
            "required_field_missing",
            f"CourtConnect result lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (_text(value) or "").casefold())


def _same_origin(first: str, second: str) -> bool:
    first_url = urlparse(first)
    second_url = urlparse(second)
    return (
        first_url.scheme.casefold(),
        first_url.netloc.casefold(),
    ) == (
        second_url.scheme.casefold(),
        second_url.netloc.casefold(),
    )


def _url_with_params(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params, doseq=True)}"


def _source_date(value: Any, field_name: str) -> str:
    normalized = _required_selector(value, field_name)
    for date_format in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            parsed = datetime.strptime(normalized, date_format).date()
            return parsed.strftime("%d-%b-%Y").upper()
        except ValueError:
            continue
    raise CourtConnectSelectionError(
        "invalid_date",
        f"{field_name} must be YYYY-MM-DD or DD-MON-YYYY",
        details={"value": normalized},
    )


def _optional_source_date(value: Any, field_name: str) -> str:
    return "" if _text(value) is None else _source_date(value, field_name)


def _parse_source_date(value: Any, field_name: str) -> str | None:
    normalized = _available_text(value)
    if normalized is None:
        return None
    try:
        return datetime.strptime(normalized.upper(), "%d-%b-%Y").date().isoformat()
    except ValueError as error:
        raise CourtConnectSourceChangedError(
            "source_date_format_changed",
            f"CourtConnect returned an unrecognized {field_name}: {normalized}",
            details={"field": field_name, "value": normalized},
        ) from error


def _parse_long_date(value: Any, field_name: str) -> str | None:
    normalized = _available_text(value)
    if normalized is None:
        return None
    match = re.search(
        r"([A-Za-z]+)\s*,\s*([A-Za-z]+)\s+"
        r"(\d+)(?:st|nd|rd|th)\s*,\s*(\d{4})",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise CourtConnectSourceChangedError(
            "source_long_date_format_changed",
            f"CourtConnect returned an unrecognized {field_name}: {normalized}",
            details={"field": field_name, "value": normalized},
        )
    try:
        return datetime.strptime(
            f"{match.group(2)} {match.group(3)} {match.group(4)}",
            "%B %d %Y",
        ).date().isoformat()
    except ValueError as error:
        raise CourtConnectSourceChangedError(
            "source_long_date_format_changed",
            f"CourtConnect returned an invalid {field_name}: {normalized}",
            details={"field": field_name, "value": normalized},
        ) from error


def _parse_source_datetime(
    value: Any,
    *,
    field_name: str = "docket date/time",
) -> tuple[str | None, str | None]:
    normalized = _available_text(value)
    if normalized is None:
        return None, None
    compact = _text(normalized)
    if compact is None:
        return None, None
    try:
        parsed = datetime.strptime(compact.upper(), "%d-%b-%Y %I:%M %p")
    except ValueError as error:
        raise CourtConnectSourceChangedError(
            "docket_datetime_format_changed",
            f"CourtConnect returned an unrecognized {field_name}: {compact}",
            details={"field": field_name, "value": compact},
        ) from error
    localized = parsed.replace(tzinfo=DELAWARE_TIMEZONE)
    return parsed.date().isoformat(), localized.isoformat()


def _required_selector(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise CourtConnectSelectionError(
            "required_selector_missing",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return normalized


def _positive_page(value: Any) -> int:
    if isinstance(value, bool):
        raise CourtConnectSelectionError(
            "invalid_page",
            "native page must be a positive integer",
        )
    try:
        page = int(value)
    except (TypeError, ValueError) as error:
        raise CourtConnectSelectionError(
            "invalid_page",
            "native page must be a positive integer",
        ) from error
    if page <= 0:
        raise CourtConnectSelectionError(
            "invalid_page",
            "native page must be a positive integer",
        )
    return page


def _retry_after_seconds(value: Any) -> float | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return max(0.0, float(normalized))
    except ValueError:
        return None


def _raise_search_error(html: str, *, source_url: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.title)
    if title is None or title.casefold() != "search error":
        return
    message = _text(soup.get_text(" ", strip=True)) or "CourtConnect search error"
    raise CourtConnectSelectionError(
        "invalid_search_criteria",
        message,
        details={"source_url": source_url},
    )


def _find_result_table(
    soup: BeautifulSoup,
    expected_headers: Sequence[str],
    *,
    source_url: str,
) -> tuple[Tag, list[str]]:
    expected = {_header_key(header) for header in expected_headers}
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        first_row = table.find("tr")
        if not isinstance(first_row, Tag):
            continue
        headers = [
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in first_row.find_all("th")
        ]
        if expected.issubset({_header_key(header) for header in headers}):
            return table, headers
    raise CourtConnectSourceChangedError(
        "result_table_missing",
        "CourtConnect result page lacks the expected table",
        details={
            "expected_headers": list(expected_headers),
            "source_url": source_url,
        },
    )


def _page_metadata(
    soup: BeautifulSoup,
) -> tuple[int, int | None, int | None]:
    page_number = 1
    record_start: int | None = None
    record_end: int | None = None
    for table in soup.find_all("table"):
        text = _text(table.get_text(" ", strip=True)) or ""
        page_match = re.search(r"\bPage:\s*(\d+)", text, flags=re.IGNORECASE)
        records_match = re.search(
            r"\bRecords:\s*(\d+)\s*-\s*(\d+)",
            text,
            flags=re.IGNORECASE,
        )
        if page_match:
            page_number = int(page_match.group(1))
        if records_match:
            record_start = int(records_match.group(1))
            record_end = int(records_match.group(2))
        if page_match or records_match:
            break
    return page_number, record_start, record_end


def _next_url(soup: BeautifulSoup, source_url: str) -> str | None:
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        label = (_text(link.get_text(" ", strip=True)) or "").casefold()
        if label.replace(" ", "") == "next->":
            return urljoin(source_url, str(link["href"]))
    return None


def _case_caption_from_cell(cell: Tag, case_id: str) -> str | None:
    italic = cell.find("i")
    value = _text(
        italic.get_text(" ", strip=True)
        if isinstance(italic, Tag)
        else cell.get_text(" ", strip=True)
    )
    if value is None:
        return None
    if value.casefold().startswith(case_id.casefold()):
        value = value[len(case_id) :].strip()
    return _text(value.lstrip("-").strip())


def _leading_cell_text(
    cell: Tag,
    *,
    stop_tags: frozenset[str] = frozenset({"tr"}),
) -> str | None:
    """Read a malformed CourtConnect cell before its nested next row/cell."""

    parts: list[str] = []
    for child in cell.contents:
        if isinstance(child, Tag) and child.name in stop_tags:
            break
        if isinstance(child, Tag):
            value = child.get_text(" ", strip=True)
        else:
            value = str(child)
        normalized = _text(value)
        if normalized is not None:
            parts.append(normalized)
    return _text(" ".join(parts))


def _address_from_case_cell(cell: Tag) -> tuple[str | None, str | None]:
    full_text = _text(cell.get_text(" ", strip=True)) or ""
    address_raw = full_text.split("Case:", 1)[0].strip()
    return _available_text(address_raw), _text(address_raw)


def parse_party_results_page(
    html: str,
    *,
    source_url: str = PARTY_RESULTS_URL,
) -> CourtConnectPage:
    """Parse one CourtConnect person/company case-search result page."""

    _raise_search_error(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    if "no records found" in (
        _text(soup.get_text(" ", strip=True)) or ""
    ).casefold():
        return CourtConnectPage(
            records=(),
            next_url=None,
            page_number=1,
            record_start=None,
            record_end=None,
            authoritative_empty=True,
            schema_fingerprint=schema_fingerprint(
                {"kind": "party_results", "state": "authoritative_empty"}
            ),
            source_url=source_url,
        )

    table, headers = _find_result_table(
        soup,
        (
            "ID",
            "Name/Corporation",
            "Address",
            "Party Type",
            "Party End Date",
            "Filing Date",
            "Case Status",
        ),
        source_url=source_url,
    )
    rows: list[dict[str, Any]] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) != 7:
            continue
        case_link = cells[2].find("a", href=True)
        if not isinstance(case_link, Tag):
            raise CourtConnectSourceChangedError(
                "case_link_missing",
                "CourtConnect party result lacks its case link",
                details={"source_url": source_url},
            )
        case_id = _required_text(
            case_link.get_text(" ", strip=True),
            "case ID",
        )
        address, address_raw = _address_from_case_cell(cells[2])
        party_id = _required_text(
            cells[0].get_text(" ", strip=True),
            "party ID",
        )
        party_end_raw = _text(cells[4].get_text(" ", strip=True))
        filing_raw = _text(cells[5].get_text(" ", strip=True))
        case_url = urljoin(source_url, str(case_link["href"]))
        rows.append(
            {
                "search_hit_id": f"{party_id}:{case_id}",
                "party_id": party_id,
                "party_name": _required_text(
                    cells[1].get_text(" ", strip=True),
                    "party name",
                ),
                "address": address,
                "party_role": _text(cells[3].get_text(" ", strip=True)),
                "party_end_date": _parse_source_date(
                    party_end_raw,
                    "party end date",
                ),
                "filing_date": _parse_source_date(
                    filing_raw,
                    "filing date",
                ),
                "case_id": case_id,
                "caption": _case_caption_from_cell(cells[2], case_id),
                "case_status": _text(cells[6].get_text(" ", strip=True)),
                "case_url": case_url,
                "party_url": (
                    urljoin(source_url, str(cells[0].find("a")["href"]))
                    if isinstance(cells[0].find("a", href=True), Tag)
                    else None
                ),
                "raw": {
                    "party_id": _text(cells[0].get_text(" ", strip=True)),
                    "party_name": _text(cells[1].get_text(" ", strip=True)),
                    "address": address_raw,
                    "party_role": _text(cells[3].get_text(" ", strip=True)),
                    "party_end_date": party_end_raw,
                    "filing_date": filing_raw,
                    "case_status": _text(cells[6].get_text(" ", strip=True)),
                },
            }
        )
    if not rows:
        raise CourtConnectSourceChangedError(
            "party_rows_missing",
            "CourtConnect party result table contains no parseable rows",
            details={"source_url": source_url},
        )
    page_number, record_start, record_end = _page_metadata(soup)
    observed_schema = schema_fingerprint(
        {
            "kind": "party_results",
            "headers": headers,
            "record_schema": inferred_schema(rows[:1]),
        }
    )
    return CourtConnectPage(
        records=tuple(rows),
        next_url=_next_url(soup, source_url),
        page_number=page_number,
        record_start=record_start,
        record_end=record_end,
        authoritative_empty=False,
        schema_fingerprint=observed_schema,
        source_url=source_url,
    )


def _decimal_amount(value: Any) -> str | None:
    normalized = _available_text(value)
    if normalized is None:
        return None
    candidate = normalized.replace("$", "").replace(",", "").strip()
    try:
        return format(Decimal(candidate), "f")
    except InvalidOperation as error:
        raise CourtConnectSourceChangedError(
            "judgment_amount_format_changed",
            f"CourtConnect returned an unrecognized judgment amount: {normalized}",
            details={"value": normalized},
        ) from error


def parse_judgment_results_page(
    html: str,
    *,
    source_url: str = JUDGMENT_RESULTS_URL,
) -> CourtConnectPage:
    """Parse one CourtConnect judgment-search result page."""

    _raise_search_error(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    if "no records found" in (
        _text(soup.get_text(" ", strip=True)) or ""
    ).casefold():
        return CourtConnectPage(
            records=(),
            next_url=None,
            page_number=1,
            record_start=None,
            record_end=None,
            authoritative_empty=True,
            schema_fingerprint=schema_fingerprint(
                {"kind": "judgment_results", "state": "authoritative_empty"}
            ),
            source_url=source_url,
        )

    table, headers = _find_result_table(
        soup,
        (
            "Person ID",
            "Party End Date",
            "Name / Company",
            "Address",
            "Joint & Several",
            "Amount",
            "Judgment Status",
            "Judgment Date",
        ),
        source_url=source_url,
    )
    rows: list[dict[str, Any]] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) not in {6, 8}:
            continue
        detail_link = cells[5].find("a", href=True)
        if not isinstance(detail_link, Tag):
            raise CourtConnectSourceChangedError(
                "judgment_detail_link_missing",
                "CourtConnect judgment result lacks its related-case link",
                details={"source_url": source_url},
            )
        detail_url = urljoin(source_url, str(detail_link["href"]))
        query = parse_qs(urlparse(detail_url).query, keep_blank_values=True)
        sequence_no = _required_text(
            (query.get("in_seq_no") or [None])[0],
            "judgment sequence number",
        )
        pidm = _required_text(
            (query.get("in_pidm") or [None])[0],
            "judgment PIDM",
        )
        if len(cells) == 8:
            amount_raw = _text(cells[5].get_text(" ", strip=True))
            judgment_status = _text(
                cells[6].get_text(" ", strip=True)
            )
            judgment_date_raw = _text(
                cells[7].get_text(" ", strip=True)
            )
        else:
            nested_cells = cells[5].find_all("td", recursive=False)
            if len(nested_cells) < 2:
                raise CourtConnectSourceChangedError(
                    "judgment_row_shape_changed",
                    "CourtConnect judgment row lacks status and date cells",
                    details={"source_url": source_url},
                )
            amount_raw = _leading_cell_text(
                cells[5],
                stop_tags=frozenset({"td", "tr"}),
            )
            judgment_status = _text(
                nested_cells[0].get_text(" ", strip=True)
            )
            judgment_date_raw = _text(
                nested_cells[1].get_text(" ", strip=True)
            )
        party_end_raw = _text(cells[1].get_text(" ", strip=True))
        address_raw = _text(cells[3].get_text(" ", strip=True))
        rows.append(
            {
                "judgment_id": f"{sequence_no}:{pidm}",
                "sequence_no": sequence_no,
                "pidm": pidm,
                "person_id": _required_text(
                    cells[0].get_text(" ", strip=True),
                    "person ID",
                ),
                "party_end_date": _parse_source_date(
                    party_end_raw,
                    "party end date",
                ),
                "name": _required_text(
                    cells[2].get_text(" ", strip=True),
                    "judgment name",
                ),
                "address": _available_text(address_raw),
                "joint_and_several": _text(
                    cells[4].get_text(" ", strip=True)
                ),
                "amount": _decimal_amount(amount_raw),
                "currency": "USD",
                "judgment_status": judgment_status,
                "judgment_date": _parse_source_date(
                    judgment_date_raw,
                    "judgment date",
                ),
                "detail_url": detail_url,
                "raw": {
                    "party_end_date": party_end_raw,
                    "address": address_raw,
                    "amount": amount_raw,
                    "judgment_status": judgment_status,
                    "judgment_date": judgment_date_raw,
                },
            }
        )
    if not rows:
        raise CourtConnectSourceChangedError(
            "judgment_rows_missing",
            "CourtConnect judgment result table contains no parseable rows",
            details={"source_url": source_url},
        )
    page_number, record_start, record_end = _page_metadata(soup)
    observed_schema = schema_fingerprint(
        {
            "kind": "judgment_results",
            "headers": headers,
            "record_schema": inferred_schema(rows[:1]),
        }
    )
    return CourtConnectPage(
        records=tuple(rows),
        next_url=_next_url(soup, source_url),
        page_number=page_number,
        record_start=record_start,
        record_end=record_end,
        authoritative_empty=False,
        schema_fingerprint=observed_schema,
        source_url=source_url,
    )


def _section_table(soup: BeautifulSoup, anchor_name: str) -> Tag | None:
    anchor = soup.find(
        "a",
        attrs={"name": lambda value: value and value.casefold() == anchor_name},
    )
    if not isinstance(anchor, Tag):
        return None
    for candidate in anchor.find_all_next(["a", "table"]):
        if candidate is anchor or not isinstance(candidate, Tag):
            continue
        if candidate.name == "a" and candidate.get("name"):
            return None
        if candidate.name == "table":
            return candidate
    return None


def _value_cell(table: Tag, label: str) -> Tag | None:
    target = _header_key(label)
    for bold in table.find_all("b"):
        if _header_key(bold.get_text(" ", strip=True)) != target:
            continue
        cell = bold.find_parent("td")
        if not isinstance(cell, Tag):
            continue
        sibling = cell.find_next_sibling("td")
        if isinstance(sibling, Tag):
            return sibling
        following = bold.find_next("td")
        if isinstance(following, Tag):
            return following
    return None


def _split_code_label(value: Any) -> tuple[str | None, str | None]:
    normalized = _available_text(value)
    if normalized is None:
        return None, None
    if " - " not in normalized:
        return None, normalized
    code, label = normalized.split(" - ", 1)
    return _text(code), _text(label)


def _detail_value(row: Tag, label: str) -> Tag | None:
    target = _header_key(label)
    for bold in row.find_all("b"):
        if _header_key(bold.get_text(" ", strip=True)) != target:
            continue
        cell = bold.find_parent("td")
        if not isinstance(cell, Tag):
            continue
        sibling = cell.find_next_sibling("td")
        if isinstance(sibling, Tag):
            return sibling
    return None


def _split_aliases(value: Any) -> list[str]:
    normalized = _available_text(value)
    if normalized is None:
        return []
    return [
        alias.strip()
        for alias in re.split(r"[\r\n;]+", normalized)
        if alias.strip()
    ]


def _parse_parties(soup: BeautifulSoup, source_url: str) -> list[dict[str, Any]]:
    table = _section_table(soup, "parties")
    if table is None:
        raise CourtConnectSourceChangedError(
            "case_parties_table_missing",
            "CourtConnect docket report lacks its Case Parties table",
            details={"source_url": source_url},
        )
    rows = table.find_all("tr")
    parties: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            continue
        sequence_raw = _text(cells[0].get_text(" ", strip=True))
        if sequence_raw is None or not sequence_raw.isdigit():
            continue
        detail_row = rows[index + 1] if index + 1 < len(rows) else None
        address_cell = (
            _detail_value(detail_row, "Address:")
            if isinstance(detail_row, Tag)
            else None
        )
        aliases_cell = (
            _detail_value(detail_row, "Aliases:")
            if isinstance(detail_row, Tag)
            else None
        )
        id_link = cells[4].find("a", href=True)
        party_end_raw = _text(cells[2].get_text(" ", strip=True))
        address_raw = (
            _text(address_cell.get_text("\n", strip=True))
            if isinstance(address_cell, Tag)
            else None
        )
        aliases_raw = (
            _text(aliases_cell.get_text("\n", strip=True))
            if isinstance(aliases_cell, Tag)
            else None
        )
        parties.append(
            {
                "sequence_no": int(sequence_raw),
                "associated_sequence_no": _text(
                    cells[1].get_text(" ", strip=True)
                ),
                "party_end_date": _parse_source_date(
                    party_end_raw,
                    "party end date",
                ),
                "role": _text(cells[3].get_text(" ", strip=True)),
                "native_party_id": _text(
                    cells[4].get_text(" ", strip=True)
                ),
                "raw_name": _required_text(
                    cells[5].get_text(" ", strip=True),
                    "party name",
                ),
                "normalized_name": None,
                "address": _available_text(address_raw),
                "aliases": _split_aliases(aliases_raw),
                "source_url": (
                    urljoin(source_url, str(id_link["href"]))
                    if isinstance(id_link, Tag)
                    else None
                ),
                "access_state": "public",
                "raw": {
                    "associated_sequence_no": _text(
                        cells[1].get_text(" ", strip=True)
                    ),
                    "party_end_date": party_end_raw,
                    "address": address_raw,
                    "aliases": aliases_raw,
                },
            }
        )
    if not parties:
        raise CourtConnectSourceChangedError(
            "case_parties_missing",
            "CourtConnect Case Parties table contains no parseable parties",
            details={"source_url": source_url},
        )
    return parties


def _parse_docket_entries(
    soup: BeautifulSoup,
    source_url: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table = _section_table(soup, "dockets")
    if table is None:
        raise CourtConnectSourceChangedError(
            "docket_entries_table_missing",
            "CourtConnect docket report lacks its Docket Entries table",
            details={"source_url": source_url},
        )
    rows = table.find_all("tr")
    entries: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        date_raw = _text(cells[0].get_text(" ", strip=True))
        if date_raw is None or not re.match(
            r"^\d{2}-[A-Za-z]{3}-\d{4}\b",
            date_raw,
        ):
            continue
        filing_date, filed_at = _parse_source_datetime(date_raw)
        description_cell = cells[1]
        if len(cells) >= 4:
            description = _available_text(
                description_cell.get_text(" ", strip=True)
            )
            filed_by = _available_text(
                cells[2].get_text(" ", strip=True)
            )
            monetary_raw = _text(cells[3].get_text(" ", strip=True))
        else:
            nested_cells = description_cell.find_all(
                "td",
                recursive=False,
            )
            if len(nested_cells) < 2:
                raise CourtConnectSourceChangedError(
                    "docket_row_shape_changed",
                    "CourtConnect docket row lacks name and monetary cells",
                    details={"source_url": source_url, "date": date_raw},
                )
            description = _available_text(
                _leading_cell_text(
                    description_cell,
                    stop_tags=frozenset({"td", "tr"}),
                )
            )
            filed_by = _available_text(
                _leading_cell_text(nested_cells[0])
            )
            monetary_raw = _leading_cell_text(nested_cells[1])
        entry_text: str | None = None
        if index + 1 < len(rows):
            entry_row = rows[index + 1]
            entry_cells = entry_row.find_all("td", recursive=False)
            if (
                entry_cells
                and _header_key(entry_cells[0].get_text(" ", strip=True))
                == "entry"
            ):
                if len(entry_cells) > 1:
                    entry_text = _available_text(
                        entry_cells[1].get_text(" ", strip=True)
                    )
        links: list[dict[str, Any]] = []
        for link in description_cell.find_all("a", href=True):
            if not isinstance(link, Tag):
                continue
            link_record = {
                "label": _text(link.get_text(" ", strip=True)),
                "url": urljoin(source_url, str(link["href"])),
            }
            links.append(link_record)
            href = str(link["href"]).casefold()
            if any(token in href for token in (".pdf", "download", "document")):
                documents.append(
                    {
                        "document_type": "docket_link",
                        "filed_date": filing_date,
                        "source_url": link_record["url"],
                        "label": link_record["label"],
                        "access_state": "public_link",
                    }
                )
        entries.append(
            {
                "sequence_no": len(entries) + 1,
                "filing_date": filing_date,
                "filed_at": filed_at,
                "description": description,
                "filed_by": filed_by,
                "monetary": _available_text(monetary_raw),
                "entry_text": entry_text,
                "links": links,
                "documents": [],
                "raw": {
                    "filing_date_time": date_raw,
                    "monetary": monetary_raw,
                },
            }
        )
    return entries, documents


def _generic_section_rows(
    soup: BeautifulSoup,
    anchor_name: str,
) -> list[dict[str, Any]]:
    table = _section_table(soup, anchor_name)
    if table is None:
        return []
    table_rows = table.find_all("tr")
    if not table_rows:
        return []
    headers = [
        _text(cell.get_text(" ", strip=True)) or f"column_{index + 1}"
        for index, cell in enumerate(table_rows[0].find_all("th"))
    ]
    if not headers:
        return []
    records: list[dict[str, Any]] = []
    for row in table_rows[1:]:
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        records.append(
            {
                _header_key(headers[index]) or f"column_{index + 1}": _text(
                    cell.get_text(" ", strip=True)
                )
                for index, cell in enumerate(cells[: len(headers)])
            }
        )
    return records


def _normalize_case_events(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Map CourtConnect's event table into the shared case-event shape."""

    events: list[dict[str, Any]] = []
    identity_counts: dict[str, int] = {}
    for row in rows:
        if "event" not in row or "datetime" not in row:
            raise CourtConnectSourceChangedError(
                "case_event_schema_changed",
                "CourtConnect case-event rows lack Event or Date/Time",
                details={"observed_fields": sorted(row)},
            )
        event_type = _required_text(row.get("event"), "case event type")
        event_date_raw = _required_text(
            row.get("datetime"),
            "case event date/time",
        )
        scheduled_date, scheduled_at = _parse_source_datetime(
            event_date_raw,
            field_name="case event date/time",
        )
        identity_basis = {
            "event_type": event_type,
            "event_date_raw": event_date_raw,
            "room": _available_text(row.get("room")),
            "location": _available_text(row.get("location")),
            "judge": _available_text(row.get("judge")),
        }
        basis_json = canonical_json(identity_basis)
        identity_counts[basis_json] = identity_counts.get(basis_json, 0) + 1
        occurrence = identity_counts[basis_json]
        digest = hashlib.sha256(
            canonical_json(
                {
                    "identity_basis": identity_basis,
                    "occurrence": occurrence,
                }
            ).encode("utf-8")
        ).hexdigest()
        events.append(
            {
                "native_event_id": f"courtconnect-event:{digest}",
                "event_type": event_type,
                "event_date": scheduled_at,
                "scheduled_date": scheduled_date,
                "event_date_raw": event_date_raw,
                "room": identity_basis["room"],
                "location": identity_basis["location"],
                "judge_raw": identity_basis["judge"],
                "assertion_kind": "docket_metadata",
                "native_assertion_kind": "case_event_schedule",
                "identity_kind": "source_fields_sha256_with_occurrence",
                "identity_basis": identity_basis,
                "occurrence": occurrence,
                "raw": dict(row),
            }
        )
    return events


def _document_access(
    docket_entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    native_notices: list[str] = []
    for entry in docket_entries:
        for field_name in ("description", "entry_text"):
            value = _text(entry.get(field_name))
            if value and (
                "fileandservexpress" in value.casefold()
                or "public access terminal" in value.casefold()
            ):
                native_notices.append(value)
    return {
        "courtconnect_filing_documents": "not_exposed_as_a_general_download_set",
        "native_docket_notices": native_notices,
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
    }


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "court_level": "statewide_multi_court_portal",
        "official_url": OFFICIAL_CIVIL_SEARCH_URL,
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "civil_case_and_docket_index",
        "fields": [
            "case_id",
            "caption",
            "filing_date",
            "case_type",
            "case_status",
            "parties",
            "related_cases",
            "case_events",
            "docket_entries",
            "judgments",
        ],
        "party_business_search": True,
        "phonetic_search": True,
        "partial_last_name_search": True,
        "judgment_search": True,
        "filing_documents_available": False,
        "certified_record": False,
    }


def parse_case_report(
    html: str,
    *,
    source_url: str = CASE_REPORT_URL,
) -> dict[str, Any]:
    """Parse one full CourtConnect docket report."""

    _raise_search_error(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    description_table = _section_table(soup, "description")
    if description_table is None:
        raise CourtConnectSourceChangedError(
            "case_description_missing",
            "CourtConnect docket report lacks Case Description",
            details={"source_url": source_url},
        )
    case_cell = _value_cell(description_table, "Case ID:")
    filing_cell = _value_cell(description_table, "Filing Date:")
    type_cell = _value_cell(description_table, "Type:")
    status_cell = _value_cell(description_table, "Status:")
    if case_cell is None:
        raise CourtConnectSourceChangedError(
            "case_id_missing",
            "CourtConnect docket report lacks its case ID value",
            details={"source_url": source_url},
        )
    case_raw = _required_text(
        _leading_cell_text(case_cell),
        "case description",
    )
    case_match = re.match(r"(?P<id>\S+)\s*-\s*(?P<caption>.*)", case_raw)
    if case_match is None:
        raise CourtConnectSourceChangedError(
            "case_description_format_changed",
            "CourtConnect case description no longer begins with case ID and caption",
            details={"value": case_raw, "source_url": source_url},
        )
    case_id = case_match.group("id")
    subtype_tag = case_cell.find("i")
    subtype_raw = (
        _text(subtype_tag.get_text(" ", strip=True))
        if isinstance(subtype_tag, Tag)
        else None
    )
    caption = case_match.group("caption")
    if subtype_raw and caption.endswith(subtype_raw):
        caption = caption[: -len(subtype_raw)].strip()
    caption = _text(caption.rstrip("-").strip())
    subtype = _text((subtype_raw or "").lstrip("-"))

    filing_raw = (
        _leading_cell_text(filing_cell)
        if isinstance(filing_cell, Tag)
        else None
    )
    type_raw = (
        _leading_cell_text(type_cell)
        if isinstance(type_cell, Tag)
        else None
    )
    status_raw = (
        _leading_cell_text(status_cell)
        if isinstance(status_cell, Tag)
        else None
    )
    case_type_code, case_type = _split_code_label(type_raw)
    status_code, status = _split_code_label(status_raw)
    parties = _parse_parties(soup, source_url)
    docket_entries, documents = _parse_docket_entries(soup, source_url)
    identity_counts: dict[str, int] = {}
    for entry in docket_entries:
        identity_basis = {
            "filing_date": entry.get("filing_date"),
            "filed_at": entry.get("filed_at"),
            "description": entry.get("description"),
            "filed_by": entry.get("filed_by"),
            "monetary": entry.get("monetary"),
            "entry_text": entry.get("entry_text"),
        }
        basis_json = canonical_json(identity_basis)
        identity_counts[basis_json] = identity_counts.get(basis_json, 0) + 1
        occurrence = identity_counts[basis_json]
        digest = hashlib.sha256(
            canonical_json(
                {
                    "identity_basis": identity_basis,
                    "occurrence": occurrence,
                }
            ).encode("utf-8")
        ).hexdigest()
        entry.update(
            {
                "native_entry_id": f"courtconnect-docket:{digest}",
                "event_code": entry.get("description"),
                "raw_text": " | ".join(
                    value
                    for value in (
                        _text(entry.get("description")),
                        _text(entry.get("entry_text")),
                    )
                    if value is not None
                )
                or None,
                "entered_date": entry.get("filed_at"),
                "filed_date": entry.get("filing_date"),
                "filer_raw": entry.get("filed_by"),
                "document_available": bool(entry.get("documents")),
                "access_state": "public",
                "native_access_state": "CourtConnect public docket index",
                "identity_kind": "source_fields_sha256_with_occurrence",
                "identity_basis": identity_basis,
                "occurrence": occurrence,
            }
        )
    for index, document in enumerate(documents, start=1):
        digest = hashlib.sha256(
            canonical_json(
                {
                    "source_url": document.get("source_url"),
                    "filed_date": document.get("filed_date"),
                    "label": document.get("label"),
                    "occurrence": index,
                }
            ).encode("utf-8")
        ).hexdigest()
        document.update(
            {
                "native_document_id": f"courtconnect-document:{digest}",
                "certification_status": "uncertified",
                "native_access_state": "CourtConnect public link",
            }
        )
    related_cases = _generic_section_rows(soup, "related")
    native_case_event_rows = _generic_section_rows(soup, "events")
    case_events = _normalize_case_events(native_case_event_rows)
    observed_schema = schema_fingerprint(
        {
            "description_fields": [
                "case_id",
                "caption",
                "filing_date",
                "type",
                "status",
            ],
            "party_schema": inferred_schema(parties[:1]),
            "docket_schema": inferred_schema(docket_entries[:1]),
            "related_case_schema": inferred_schema(related_cases[:1]),
            "case_event_schema": inferred_schema(case_events[:1]),
        }
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(),
        "raw_case_number": case_id,
        "display_case_number": case_id,
        "source_internal_id": case_id,
        "caption": caption,
        "case_subtype": subtype,
        "case_type": case_type,
        "native_case_type_code": case_type_code,
        "filing_date": _parse_long_date(filing_raw, "filing date"),
        "status": status,
        "native_status_code": status_code,
        "access_state": "public",
        "native_access_state": "CourtConnect public docket index",
        "certified_record": False,
        "source_url": source_url,
        "parties": parties,
        "related_cases": related_cases,
        "case_events": case_events,
        "native_case_event_rows": native_case_event_rows,
        "docket_entries": docket_entries,
        "documents": documents,
        "document_access": _document_access(docket_entries),
        "source_scope": _source_scope(),
        "schema_fingerprint": observed_schema,
        "raw": {
            "case_description": case_raw,
            "filing_date": filing_raw,
            "case_type": type_raw,
            "status": status_raw,
        },
    }


def parse_judgment_detail_page(
    html: str,
    *,
    source_url: str = JUDGMENT_DETAIL_URL,
) -> CourtConnectPage:
    """Parse one related-case page for a selected judgment."""

    _raise_search_error(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    if "no records found" in (
        _text(soup.get_text(" ", strip=True)) or ""
    ).casefold():
        return CourtConnectPage(
            records=(),
            next_url=None,
            page_number=1,
            record_start=None,
            record_end=None,
            authoritative_empty=True,
            schema_fingerprint=schema_fingerprint(
                {"kind": "judgment_detail", "state": "authoritative_empty"}
            ),
            source_url=source_url,
        )
    table, headers = _find_result_table(
        soup,
        (
            "Case ID",
            "Case Description",
            "Docket Description",
            "Case Status",
        ),
        source_url=source_url,
    )
    rows: list[dict[str, Any]] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) not in {3, 4}:
            continue
        case_link = cells[0].find("a", href=True)
        case_id = _required_text(
            cells[0].get_text(" ", strip=True),
            "related case ID",
        )
        if len(cells) == 4:
            docket_description = _text(
                cells[2].get_text(" ", strip=True)
            )
            case_status = _text(cells[3].get_text(" ", strip=True))
        else:
            nested_cells = cells[2].find_all("td", recursive=False)
            if not nested_cells:
                raise CourtConnectSourceChangedError(
                    "judgment_related_case_shape_changed",
                    "CourtConnect judgment detail lacks its case-status cell",
                    details={"source_url": source_url},
                )
            docket_description = _leading_cell_text(
                cells[2],
                stop_tags=frozenset({"td", "tr"}),
            )
            case_status = _text(
                nested_cells[0].get_text(" ", strip=True)
            )
        rows.append(
            {
                "case_id": case_id,
                "caption": _text(cells[1].get_text(" ", strip=True)),
                "docket_description": docket_description,
                "case_status": case_status,
                "case_url": (
                    urljoin(source_url, str(case_link["href"]))
                    if isinstance(case_link, Tag)
                    else None
                ),
            }
        )
    if not rows:
        raise CourtConnectSourceChangedError(
            "judgment_related_cases_missing",
            "CourtConnect judgment detail contains no parseable related cases",
            details={"source_url": source_url},
        )
    page_number, record_start, record_end = _page_metadata(soup)
    return CourtConnectPage(
        records=tuple(rows),
        next_url=_next_url(soup, source_url),
        page_number=page_number,
        record_start=record_start,
        record_end=record_end,
        authoritative_empty=False,
        schema_fingerprint=schema_fingerprint(
            {
                "kind": "judgment_detail",
                "headers": headers,
                "record_schema": inferred_schema(rows[:1]),
            }
        ),
        source_url=source_url,
    )


def parse_options_page(
    html: str,
    *,
    select_name: str,
    option_group: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Parse a source-native select list without hard-coding its values."""

    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", attrs={"name": select_name})
    if not isinstance(select, Tag):
        raise CourtConnectSourceChangedError(
            "source_options_missing",
            f"CourtConnect form lacks select {select_name}",
            details={"source_url": source_url, "select_name": select_name},
        )
    records: list[dict[str, Any]] = []
    for option in select.find_all("option"):
        value = _text(option.get("value")) or _text(
            option.get_text(" ", strip=True)
        )
        if value is None:
            continue
        code, label = _split_code_label(value)
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "source_option",
                "option_group": option_group,
                "native_value": value,
                "native_code": code,
                "label": label or value,
                "source_url": source_url,
            }
        )
    if not records:
        raise CourtConnectSourceChangedError(
            "source_options_empty",
            f"CourtConnect form select {select_name} has no options",
            details={"source_url": source_url, "select_name": select_name},
        )
    return records


class DelawareCourtConnectClient:
    """Transport-injectable client for the official CourtConnect HTML routes."""

    _MODE_SETUP_HINTS = {
        "party": "cp_personcase_setup_idx",
        "docket": "cp_dktrpt_setup_idx",
        "judge": "cp_judgment_setup_idx",
    }

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0
        self._accepted_modes: set[str] = set()

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        referer: str | None = None,
    ) -> Any:
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }
        if referer is not None:
            headers["Referer"] = referer
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise CourtConnectError(
                    "transport_error",
                    f"CourtConnect request failed after {attempt} attempts: {error}",
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt, "url": url},
                ) from error
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(
                            attempt,
                            _retry_after_seconds(
                                response.headers.get("Retry-After")
                            ),
                        )
                    )
                    continue
                raise CourtConnectError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"CourtConnect returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit"
                        if status_code == 429
                        else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise CourtConnectError(
                    "source_access_failed",
                    f"CourtConnect returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code >= 400:
                raise CourtConnectError(
                    "http_status_error",
                    f"CourtConnect returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            return response
        raise AssertionError("retry loop exhausted without returning or raising")

    @staticmethod
    def _response_url(
        response: Any,
        fallback_url: str,
        params: Mapping[str, Any] | None = None,
    ) -> str:
        return (
            _text(getattr(response, "url", None))
            or _url_with_params(fallback_url, params)
        )

    def _accept(self, mode: str) -> None:
        if mode in self._accepted_modes:
            return
        if mode not in self._MODE_SETUP_HINTS:
            raise ValueError(f"unsupported CourtConnect disclaimer mode: {mode}")
        disclaimer = self._request(
            "GET",
            DISCLAIMER_URL,
            params={"search_option": mode},
        )
        disclaimer_url = self._response_url(
            disclaimer,
            DISCLAIMER_URL,
            {"search_option": mode},
        )
        soup = BeautifulSoup(disclaimer.text, "html.parser")
        action_frame = None
        for frame in soup.find_all("frame", src=True):
            if "cp_disclaimer_srch_link" in str(frame["src"]):
                action_frame = frame
                break
        if not isinstance(action_frame, Tag):
            raise CourtConnectSourceChangedError(
                "disclaimer_action_frame_missing",
                "CourtConnect disclaimer lacks its Accept action frame",
                details={"mode": mode, "source_url": disclaimer_url},
            )
        action_url = urljoin(disclaimer_url, str(action_frame["src"]))
        action = self._request("GET", action_url, referer=disclaimer_url)
        action_response_url = self._response_url(action, action_url)
        action_soup = BeautifulSoup(action.text, "html.parser")
        accept_form = None
        for form in action_soup.find_all("form", action=True):
            if self._MODE_SETUP_HINTS[mode] not in str(form["action"]):
                continue
            submit = form.find("input", attrs={"value": re.compile("^Accept$", re.I)})
            if isinstance(submit, Tag):
                accept_form = form
                break
        if not isinstance(accept_form, Tag):
            raise CourtConnectSourceChangedError(
                "disclaimer_accept_form_missing",
                "CourtConnect disclaimer lacks the expected Accept form",
                details={"mode": mode, "source_url": action_response_url},
            )
        setup_url = urljoin(action_response_url, str(accept_form["action"]))
        setup = self._request("POST", setup_url, referer=action_response_url)
        setup_text = _text(setup.text) or ""
        if "frameset" not in setup_text.casefold():
            raise CourtConnectSourceChangedError(
                "search_setup_frameset_missing",
                "CourtConnect did not return the expected search setup frameset",
                details={"mode": mode, "source_url": setup_url},
            )
        self._accepted_modes.add(mode)

    def _fetch_pages(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        parser: Callable[..., CourtConnectPage],
        one_page: bool,
        referer: str,
    ) -> CourtConnectFetch:
        response = self._request(
            "GET",
            url,
            params=params,
            referer=referer,
        )
        response_url = self._response_url(response, url, params)
        page = parser(response.text, source_url=response_url)
        collected = list(page.records)
        page_schemas = {page.schema_fingerprint}
        pages_fetched = 1
        if one_page:
            return CourtConnectFetch(
                records=tuple(collected),
                pages_fetched=pages_fetched,
                next_url=page.next_url,
                schema_fingerprint=schema_fingerprint(
                    {"pages": sorted(page_schemas)}
                ),
                source_url=response_url,
            )

        seen_urls = {response_url}
        while page.next_url is not None:
            if not _same_origin(BASE_URL, page.next_url):
                raise CourtConnectSourceChangedError(
                    "pagination_origin_changed",
                    "CourtConnect pagination points outside the official host",
                    details={"next_url": page.next_url},
                )
            if page.next_url in seen_urls:
                raise CourtConnectSourceChangedError(
                    "pagination_loop",
                    "CourtConnect returned a repeated continuation link",
                    details={"next_url": page.next_url},
                )
            seen_urls.add(page.next_url)
            response = self._request(
                "GET",
                page.next_url,
                referer=page.source_url,
            )
            response_url = self._response_url(response, page.next_url)
            page = parser(response.text, source_url=response_url)
            collected.extend(page.records)
            page_schemas.add(page.schema_fingerprint)
            pages_fetched += 1
        return CourtConnectFetch(
            records=tuple(collected),
            pages_fetched=pages_fetched,
            next_url=None,
            schema_fingerprint=schema_fingerprint(
                {"pages": sorted(page_schemas)}
            ),
            source_url=response_url,
        )

    def options(self) -> tuple[Mapping[str, Any], ...]:
        """Return live case-type and judgment-status options."""

        self._accept("party")
        party_response = self._request(
            "GET",
            PARTY_SETUP_URL,
            referer=SEARCH_HOME_URL,
        )
        party_url = self._response_url(party_response, PARTY_SETUP_URL)
        case_types = parse_options_page(
            party_response.text,
            select_name="case_type",
            option_group="case_type",
            source_url=party_url,
        )
        self._accept("judge")
        judgment_response = self._request(
            "GET",
            JUDGMENT_SETUP_URL,
            referer=SEARCH_HOME_URL,
        )
        judgment_url = self._response_url(
            judgment_response,
            JUDGMENT_SETUP_URL,
        )
        statuses = parse_options_page(
            judgment_response.text,
            select_name="sat_ind",
            option_group="judgment_status",
            source_url=judgment_url,
        )
        return tuple([*case_types, *statuses])

    def search_cases(
        self,
        last_name_or_company: str,
        *,
        first_name: str | None = None,
        middle_name: str | None = None,
        partial: bool = False,
        phonetic: bool = False,
        filed_after: str | None = None,
        filed_before: str | None = None,
        case_type: str = "ALL",
        page: int | None = None,
    ) -> CourtConnectFetch:
        """Search cases through the source-native party/company index."""

        last_name = _required_selector(
            last_name_or_company,
            "last name or company name",
        )
        native_page = 1 if page is None else _positive_page(page)
        self._accept("party")
        params = {
            "backto": "P",
            "soundex_ind": "checked" if phonetic else "",
            "partial_ind": "checked" if partial else "",
            "last_name": last_name,
            "first_name": _text(first_name) or "",
            "middle_name": _text(middle_name) or "",
            "begin_date": _optional_source_date(
                filed_after,
                "filed-after",
            ),
            "end_date": _optional_source_date(
                filed_before,
                "filed-before",
            ),
            "case_type": _text(case_type) or "ALL",
            "id_code": "",
            "PageNo": native_page,
        }
        return self._fetch_pages(
            PARTY_RESULTS_URL,
            params=params,
            parser=parse_party_results_page,
            one_page=page is not None,
            referer=PARTY_SETUP_URL,
        )

    def get_case(
        self,
        case_id: str,
        *,
        docket_after: str | None = None,
        docket_before: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a full public docket report by source-native case ID."""

        native_case_id = _required_selector(case_id, "case ID")
        self._accept("docket")
        params = {
            "backto": "P",
            "case_id": native_case_id,
            "begin_date": _optional_source_date(
                docket_after,
                "docket-after",
            ),
            "end_date": _optional_source_date(
                docket_before,
                "docket-before",
            ),
        }
        response = self._request(
            "GET",
            CASE_REPORT_URL,
            params=params,
            referer=SEARCH_HOME_URL,
        )
        response_url = self._response_url(response, CASE_REPORT_URL, params)
        return parse_case_report(response.text, source_url=response_url)

    def search_judgments(
        self,
        last_name_or_company: str,
        *,
        first_name: str | None = None,
        middle_name: str | None = None,
        partial: bool = False,
        phonetic: bool = False,
        judgment_after: str | None = None,
        judgment_before: str | None = None,
        status: str = "All",
        page: int | None = None,
    ) -> CourtConnectFetch:
        """Search the source-native judgment index."""

        last_name = _required_selector(
            last_name_or_company,
            "last name or company name",
        )
        native_page = 1 if page is None else _positive_page(page)
        self._accept("judge")
        params = {
            "soundex_ind": "checked" if phonetic else "",
            "partial_ind": "checked" if partial else "",
            "last_name": last_name,
            "first_name": _text(first_name) or "",
            "middle_name": _text(middle_name) or "",
            "begin_date": _optional_source_date(
                judgment_after,
                "judgment-after",
            ),
            "end_date": _optional_source_date(
                judgment_before,
                "judgment-before",
            ),
            "sat_ind": _text(status) or "All",
            "PageNo": native_page,
        }
        return self._fetch_pages(
            JUDGMENT_RESULTS_URL,
            params=params,
            parser=parse_judgment_results_page,
            one_page=page is not None,
            referer=JUDGMENT_SETUP_URL,
        )

    def judgment_detail(
        self,
        sequence_no: str,
        pidm: str,
        *,
        name: str,
        page: int | None = None,
    ) -> CourtConnectFetch:
        """Fetch cases linked to one source-native judgment identity."""

        native_sequence = _required_selector(
            sequence_no,
            "judgment sequence number",
        )
        native_pidm = _required_selector(pidm, "judgment PIDM")
        native_name = _required_selector(name, "judgment name")
        native_page = 1 if page is None else _positive_page(page)
        self._accept("judge")
        params = {
            "in_seq_no": native_sequence,
            "in_pidm": native_pidm,
            "in_name": native_name,
            "PageNo": native_page,
        }
        return self._fetch_pages(
            JUDGMENT_DETAIL_URL,
            params=params,
            parser=parse_judgment_detail_page,
            one_page=page is not None,
            referer=JUDGMENT_RESULTS_URL,
        )

    def probe(self) -> tuple[Mapping[str, Any], ...]:
        """Verify two stable case-report sentinels with distinct depth."""

        records = []
        for case_id in PROBE_CASE_IDS:
            record = self.get_case(case_id)
            if record.get("raw_case_number") != case_id:
                raise CourtConnectSourceChangedError(
                    "probe_case_mismatch",
                    "CourtConnect probe returned an unexpected case ID",
                    details={
                        "expected": case_id,
                        "observed": record.get("raw_case_number"),
                    },
                )
            probe_record = dict(record)
            probe_record["probe"] = {
                "sentinel_case_id": case_id,
                "docket_entry_count": len(record.get("docket_entries") or []),
                "party_count": len(record.get("parties") or []),
            }
            records.append(probe_record)
        return tuple(records)


def _case_hit_record(
    row: Mapping[str, Any],
    *,
    fetched: CourtConnectFetch,
) -> dict[str, Any]:
    case_id = _required_text(row.get("case_id"), "case ID")
    party = {
        "native_party_id": row.get("party_id"),
        "raw_name": row.get("party_name"),
        "normalized_name": None,
        "role": row.get("party_role"),
        "party_end_date": row.get("party_end_date"),
        "address": row.get("address"),
        "source_url": row.get("party_url"),
        "access_state": "public",
    }
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case_party_index_hit",
        "court": _court_payload(),
        "raw_case_number": case_id,
        "display_case_number": case_id,
        "source_internal_id": case_id,
        "caption": row.get("caption"),
        "case_type": None,
        "filing_date": row.get("filing_date"),
        "status": row.get("case_status"),
        "access_state": "public",
        "native_access_state": "CourtConnect public party/case index",
        "certified_record": False,
        "source_url": row.get("case_url"),
        "parties": [party],
        "docket_entries": [],
        "documents": [],
        "source_scope": _source_scope(),
        "search_hit_id": row.get("search_hit_id"),
        "search_metadata": {
            "pages_fetched": fetched.pages_fetched,
            "schema_fingerprint": fetched.schema_fingerprint,
        },
        "raw": dict(row.get("raw") or {}),
    }


def _judgment_hit_record(
    row: Mapping[str, Any],
    *,
    fetched: CourtConnectFetch,
) -> dict[str, Any]:
    judgment_id = _required_text(row.get("judgment_id"), "judgment ID")
    return {
        "canonical_ref": f"DECOURTCONNECT:JUDGMENT:{judgment_id}",
        "source_id": SOURCE_ID,
        "record_kind": "judgment_index_hit",
        "native_judgment_id": judgment_id,
        "sequence_no": row.get("sequence_no"),
        "pidm": row.get("pidm"),
        "person_id": row.get("person_id"),
        "name": row.get("name"),
        "party_end_date": row.get("party_end_date"),
        "address": row.get("address"),
        "joint_and_several": row.get("joint_and_several"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "judgment_status": row.get("judgment_status"),
        "judgment_date": row.get("judgment_date"),
        "source_url": row.get("detail_url"),
        "access_state": "public_index",
        "certified_record": False,
        "related_cases": [],
        "search_metadata": {
            "pages_fetched": fetched.pages_fetched,
            "schema_fingerprint": fetched.schema_fingerprint,
        },
        "raw": dict(row.get("raw") or {}),
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    """Build the shared public-record query envelope."""

    command = args.command
    parameters: dict[str, Any]
    cursor: str | None = None
    requested_limit: int | None = None
    if command == "cases":
        parameters = {
            "last_name_or_company": args.last_name_or_company,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "partial": args.partial,
            "phonetic": args.phonetic,
            "filed_after": args.filed_after,
            "filed_before": args.filed_before,
            "case_type": args.case_type,
            "page": args.page,
            "limit": getattr(args, "limit", None),
        }
        requested_limit = getattr(args, "limit", None)
        if args.page is not None:
            cursor = f"courtconnect:party:page:{args.page}"
    elif command == "case":
        parameters = {
            "case_id": args.case_id,
            "docket_after": args.docket_after,
            "docket_before": args.docket_before,
        }
    elif command == "judgments":
        parameters = {
            "last_name_or_company": args.last_name_or_company,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "partial": args.partial,
            "phonetic": args.phonetic,
            "judgment_after": args.judgment_after,
            "judgment_before": args.judgment_before,
            "status": args.status,
            "page": args.page,
            "limit": getattr(args, "limit", None),
        }
        requested_limit = getattr(args, "limit", None)
        if args.page is not None:
            cursor = f"courtconnect:judgment:page:{args.page}"
    elif command == "judgment":
        parameters = {
            "sequence_no": args.sequence_no,
            "pidm": args.pidm,
            "name": args.name,
            "page": args.page,
        }
        if args.page is not None:
            cursor = f"courtconnect:judgment-detail:page:{args.page}"
    elif command == "probe":
        parameters = {"case_ids": list(PROBE_CASE_IDS)}
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Delaware",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _make_client(args: argparse.Namespace) -> DelawareCourtConnectClient:
    return DelawareCourtConnectClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: CourtConnectError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _apply_caller_limit(
    records: Sequence[Mapping[str, Any]],
    limit: int | None,
) -> tuple[list[Mapping[str, Any]], tuple[str, ...]]:
    selected = list(records)
    if limit is None or len(selected) <= limit:
        return selected, SOURCE_WARNINGS
    return (
        selected[:limit],
        (
            *SOURCE_WARNINGS,
            f"Caller limit returned {limit} of {len(selected)} source hits "
            "fetched.",
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DelawareCourtConnectClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one official CourtConnect operation."""

    query = build_query(args)
    if access_decision is not None and not access_decision.get(
        "allowed", False
    ):
        result = _decision_failure(query, access_decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        if args.command == "options":
            result = PublicRecordsResult.success(
                query,
                source_client.options(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "cases":
            fetched = source_client.search_cases(
                args.last_name_or_company,
                first_name=args.first_name,
                middle_name=args.middle_name,
                partial=args.partial,
                phonetic=args.phonetic,
                filed_after=args.filed_after,
                filed_before=args.filed_before,
                case_type=args.case_type,
                page=args.page,
            )
            selected_rows, warnings = _apply_caller_limit(
                fetched.records,
                getattr(args, "limit", None),
            )
            records = [
                _case_hit_record(row, fetched=fetched)
                for row in selected_rows
            ]
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_url,
                warnings=warnings,
            )
        elif args.command == "case":
            result = PublicRecordsResult.success(
                query,
                [
                    source_client.get_case(
                        args.case_id,
                        docket_after=args.docket_after,
                        docket_before=args.docket_before,
                    )
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "judgments":
            fetched = source_client.search_judgments(
                args.last_name_or_company,
                first_name=args.first_name,
                middle_name=args.middle_name,
                partial=args.partial,
                phonetic=args.phonetic,
                judgment_after=args.judgment_after,
                judgment_before=args.judgment_before,
                status=args.status,
                page=args.page,
            )
            selected_rows, warnings = _apply_caller_limit(
                fetched.records,
                getattr(args, "limit", None),
            )
            records = [
                _judgment_hit_record(row, fetched=fetched)
                for row in selected_rows
            ]
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_url,
                warnings=warnings,
            )
        elif args.command == "judgment":
            fetched = source_client.judgment_detail(
                args.sequence_no,
                args.pidm,
                name=args.name,
                page=args.page,
            )
            native_id = f"{args.sequence_no}:{args.pidm}"
            record = {
                "canonical_ref": f"DECOURTCONNECT:JUDGMENT:{native_id}",
                "source_id": SOURCE_ID,
                "record_kind": "judgment_related_cases",
                "native_judgment_id": native_id,
                "sequence_no": args.sequence_no,
                "pidm": args.pidm,
                "name": args.name,
                "source_url": fetched.source_url,
                "related_cases": list(fetched.records),
                "search_metadata": {
                    "pages_fetched": fetched.pages_fetched,
                    "schema_fingerprint": fetched.schema_fingerprint,
                },
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                next_cursor=fetched.next_url,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                source_client.probe(),
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise CourtConnectSelectionError(
                "unsupported_command",
                f"unsupported CourtConnect command: {args.command}",
            )
    except CourtConnectError as error:
        result = _failure_result(query, error)
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

    if log_results:
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
        summary=f"Delaware CourtConnect {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Delaware CourtConnect {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("native_judgment_id")
            or record.get("native_value")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def _add_name_search(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("last_name_or_company")
    parser.add_argument("--first-name")
    parser.add_argument("--middle-name")
    parser.add_argument(
        "--partial",
        action="store_true",
        help="Use the source's partial-last-name mode",
    )
    parser.add_argument(
        "--phonetic",
        action="store_true",
        help="Use the source's phonetic mode",
    )
    parser.add_argument(
        "--page",
        type=_positive_int,
        default=None,
        help="Fetch one native page; defaults to following all pages",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help=(
            "Maximum hits to return after fetching the selected native "
            "page(s); defaults to all"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Delaware Judiciary CourtConnect civil cases, dockets, "
            "and judgments"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    options = subparsers.add_parser(
        "options",
        help="List live source-native case types and judgment statuses",
    )
    _add_runtime_and_output(options)

    cases = subparsers.add_parser(
        "cases",
        help="Search civil cases by party or business name",
    )
    _add_name_search(cases)
    cases.add_argument("--filed-after", help="YYYY-MM-DD or DD-MON-YYYY")
    cases.add_argument("--filed-before", help="YYYY-MM-DD or DD-MON-YYYY")
    cases.add_argument(
        "--case-type",
        default="ALL",
        help="Source-native value shown by the options command",
    )
    _add_runtime_and_output(cases)

    case = subparsers.add_parser(
        "case",
        help="Fetch a full docket report by source-native case ID",
    )
    case.add_argument("case_id")
    case.add_argument("--docket-after", help="YYYY-MM-DD or DD-MON-YYYY")
    case.add_argument("--docket-before", help="YYYY-MM-DD or DD-MON-YYYY")
    _add_runtime_and_output(case)

    judgments = subparsers.add_parser(
        "judgments",
        help="Search judgments by person or business name",
    )
    _add_name_search(judgments)
    judgments.add_argument(
        "--judgment-after",
        help="YYYY-MM-DD or DD-MON-YYYY",
    )
    judgments.add_argument(
        "--judgment-before",
        help="YYYY-MM-DD or DD-MON-YYYY",
    )
    judgments.add_argument(
        "--status",
        default="All",
        help="Source-native value shown by the options command",
    )
    _add_runtime_and_output(judgments)

    judgment = subparsers.add_parser(
        "judgment",
        help="Fetch cases linked to a source-native judgment identity",
    )
    judgment.add_argument("sequence_no")
    judgment.add_argument("pidm")
    judgment.add_argument("--name", required=True)
    judgment.add_argument(
        "--page",
        type=_positive_int,
        default=None,
        help="Fetch one native page; defaults to following all pages",
    )
    _add_runtime_and_output(judgment)

    probe = subparsers.add_parser(
        "probe",
        help="Verify two stable case-report sentinels",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
