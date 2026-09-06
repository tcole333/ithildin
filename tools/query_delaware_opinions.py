#!/usr/bin/env python3
"""Query Delaware Courts' official Opinions and Orders archive.

The official archive exposes anonymous GET filters for court, Civil/Criminal
case type, the Complex Commercial Litigation Division, revision date windows,
one metadata-search field, sorting, native page sizes, and page number. Direct
document links return PDFs from the same official host.

Examples:
    uv run python tools/query_delaware_opinions.py search Intel \
        --year 2026 --output intel-opinions.json
    uv run python tools/query_delaware_opinions.py search \
        --judge Mitchell --court "Court of Chancery" --year 2026
    uv run python tools/query_delaware_opinions.py search \
        --case-number 4373-LM --year 2026
    uv run python tools/query_delaware_opinions.py search \
        --description "Letter Decision" --revised-after 2026-07-01 \
        --revised-before 2026-07-15
    uv run python tools/query_delaware_opinions.py download \
        398840 intel-nvidia.pdf
    uv run python tools/query_delaware_opinions.py options --json
    uv run python tools/query_delaware_opinions.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlencode, urlparse

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


SOURCE_ID = "us-de-opinions-orders"
STATE_CODE = "DE"
STATE_GEOID = "10"
SOURCE_NAME = "Delaware Courts Opinions and Orders"
LANDING_URL = "https://courts.delaware.gov/opinions/"
INDEX_URL = "https://courts.delaware.gov/opinions/index.aspx"
DOWNLOAD_URL = "https://courts.delaware.gov/opinions/download.aspx"
COURTCONNECT_URL = (
    "https://courtconnect.courts.delaware.gov/cc/cconnect/"
    "ck_public_qry_main.cp_main_srch_options"
)
COURT_RECORDS_REQUEST_URL = (
    "https://www.courts.delaware.gov/Forms/Download.aspx?id=43418"
)

PROBE_DOCUMENT_ID = "398840"
PROBE_YEAR = 2026
PROBE_CASE_NUMBER = "4373-LM"
PROBE_CAPTION = "Intel Corp vs Nvidia Corp"
CURRENT_YEAR = date.today().year
NATIVE_PAGE_SIZES = frozenset({25, 50, 100})
MAX_SEARCH_TEXT_LENGTH = 25
DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

SORT_FIELDS = frozenset(
    {"", "parties", "date", "number", "court", "type", "officer"}
)
SORT_ORDERS = {"desc": "0", "asc": "1"}
FIELD_FILTERS = frozenset(
    {"all", "caption", "case-number", "judge", "description"}
)

SOURCE_WARNINGS = (
    "This source is Delaware Courts' published Opinions and Orders archive, "
    "not CourtConnect docket/activity metadata.",
    "An archive PDF is an electronic court publication, not a clerk-certified "
    "copy or a substitute for the separate court-records request process.",
    "The archive states that electronic orders may contain computer-generated "
    "or other deviations; the printed or later official version controls when "
    "versions differ.",
    "Judge, case-number, caption, and description modes use the archive's one "
    "metadata-search field and then transparently filter the requested result "
    "field.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="official_published_opinion_order_and_pdf_archive",
    base_url=LANDING_URL,
    dataset_id="delaware-opinions-orders-public",
    metadata={
        "authority": "Delaware Judiciary",
        "state_code": STATE_CODE,
        "authentication": "none",
        "access_class": "anonymous_public",
        "platform_family": "delaware_official_opinion_archive",
        "index_url": INDEX_URL,
        "download_url": DOWNLOAD_URL,
        "native_page_sizes": sorted(NATIVE_PAGE_SIZES),
        "native_result_ceiling": None,
        "search_text_maxlength": MAX_SEARCH_TEXT_LENGTH,
        "date_filter_label": "Revision Date",
        "search_scope": "listed opinion/order metadata",
        "distinct_from": [
            {
                "source_id": "us-de-courtconnect",
                "role": "civil case and docket metadata",
                "url": COURTCONNECT_URL,
            },
            {
                "source_id": "us-de-court-records-access",
                "role": "clerk copies, certified records, and record requests",
                "url": COURT_RECORDS_REQUEST_URL,
            },
        ],
    },
)


class DelawareOpinionsError(RuntimeError):
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


class DelawareOpinionsSelectionError(DelawareOpinionsError):
    """The requested query cannot be represented by the source contract."""

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


class DelawareOpinionsSourceChangedError(DelawareOpinionsError):
    """The official page or document no longer matches the verified contract."""

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


class DelawareOpinionNotFoundError(DelawareOpinionsError):
    """The official server returned a resource-level 404."""

    def __init__(self, document_id: str, *, url: str) -> None:
        super().__init__(
            "document_not_found",
            f"Delaware opinion/order document {document_id} was not found",
            category="source",
            details={"document_id": document_id, "url": url},
        )


@dataclass(frozen=True)
class OpinionIndexPage:
    """One parsed native archive page."""

    records: tuple[Mapping[str, Any], ...]
    source_total: int
    current_page: int
    total_pages: int
    page_size: int
    authoritative_empty: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class OpinionIndexFetch:
    """One or more native archive pages."""

    records: tuple[Mapping[str, Any], ...]
    source_total: int
    pages_fetched: int
    source_pages: int
    next_url: str | None
    schema_fingerprint: str
    source_url: str
    field_filter: str
    source_records_before_field_filter: int


@dataclass(frozen=True)
class DelawareOpinionDownload:
    """One validated PDF from the official download route."""

    document_id: str
    content: bytes
    media_type: str
    filename: str
    source_url: str
    content_disposition: str | None
    etag: str | None
    last_modified: str | None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def receipt(self, destination: Path | None = None) -> dict[str, Any]:
        return {
            "source_id": SOURCE_ID,
            "native_document_id": self.document_id,
            "source_url": self.source_url,
            "storage_path": (
                str(destination.resolve()) if destination is not None else None
            ),
            "bytes": len(self.content),
            "sha256": self.sha256,
            "media_type": self.media_type,
            "filename": self.filename,
            "content_disposition": self.content_disposition,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "acquired_at": (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            ),
        }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(
        str(value).replace("\x00", "").replace("\xa0", " ").split()
    ).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise DelawareOpinionsSourceChangedError(
            "required_field_missing",
            f"Delaware Opinions result lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _required_selector(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise DelawareOpinionsSelectionError(
            "required_selector_missing",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return normalized


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (_text(value) or "").casefold())


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise DelawareOpinionsSelectionError(
            "invalid_positive_integer",
            f"{field_name} must be a positive integer",
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise DelawareOpinionsSelectionError(
            "invalid_positive_integer",
            f"{field_name} must be a positive integer",
        ) from error
    if parsed <= 0:
        raise DelawareOpinionsSelectionError(
            "invalid_positive_integer",
            f"{field_name} must be a positive integer",
        )
    return parsed


def _document_id(value: Any) -> str:
    normalized = _required_selector(value, "document ID")
    if not normalized.isdigit() or int(normalized) <= 0:
        raise DelawareOpinionsSelectionError(
            "invalid_document_id",
            "document ID must be a positive source-native integer",
            details={"value": normalized},
        )
    return str(int(normalized))


def _parse_document_date(value: Any) -> str:
    normalized = _required_text(value, "document date")
    try:
        return datetime.strptime(normalized, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise DelawareOpinionsSourceChangedError(
            "document_date_format_changed",
            f"Delaware Opinions returned an unrecognized date: {normalized}",
            details={"value": normalized},
        ) from error


def _source_date(value: Any, field_name: str) -> tuple[str, date]:
    normalized = _required_selector(value, field_name)
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(normalized, date_format).date()
            return parsed.strftime("%m/%d/%Y"), parsed
        except ValueError:
            continue
    raise DelawareOpinionsSelectionError(
        "invalid_revision_date",
        f"{field_name} must be YYYY-MM-DD or MM/DD/YYYY",
        details={"value": normalized},
    )


def _publication_kind(description: str | None) -> str:
    value = (description or "").casefold()
    has_opinion = "opinion" in value
    has_order = "order" in value
    has_decision = "decision" in value
    if has_opinion and has_order:
        return "opinion_and_order"
    if has_opinion:
        return "opinion"
    if has_order:
        return "order"
    if has_decision:
        return "decision"
    return "published_court_document"


def _court_id(court_name: str) -> str:
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", court_name.casefold()))
    return f"de-{slug.strip('-')}"


def _pdf_document_record(
    document_id: str,
    *,
    publication_kind: str,
    document_date: str,
    source_url: str,
) -> dict[str, Any]:
    return {
        "native_document_id": document_id,
        "document_type": publication_kind,
        "filed_date": document_date,
        "source_url": source_url,
        "access_state": "public",
        "native_access_state": "official anonymous PDF",
        "certification_status": "uncertified_official_site_copy",
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "published_opinion_or_order",
        "metadata_search": True,
        "pdf_download": True,
        "pdf_body_full_text_search_verified": False,
        "courtconnect_docket_metadata": False,
        "clerk_certified_record": False,
        "date_filter_native_label": "Revision Date",
    }


def _alert_message(soup: BeautifulSoup) -> str | None:
    alert = soup.select_one(".alert-danger")
    if not isinstance(alert, Tag):
        return None
    return _text(alert.get_text(" ", strip=True))


def _find_index_table(
    soup: BeautifulSoup,
    *,
    source_url: str,
) -> tuple[Tag, list[str]]:
    expected = {
        "partiescaption",
        "date",
        "filenumber",
        "court",
        "type",
        "judicialofficer",
        "description",
    }
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        header_row = table.find("tr")
        if not isinstance(header_row, Tag):
            continue
        headers = [
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in header_row.find_all("th")
        ]
        if expected.issubset({_header_key(header) for header in headers}):
            return table, headers
    raise DelawareOpinionsSourceChangedError(
        "index_table_missing",
        "Delaware Opinions page lacks the expected metadata table",
        details={"source_url": source_url},
    )


def _total_count(soup: BeautifulSoup, *, source_url: str) -> int:
    for label in soup.select("span.label.label-default"):
        value = _text(label.get_text(" ", strip=True)) or ""
        match = re.fullmatch(r"([\d,]+)\s+Opinions?", value, flags=re.I)
        if match is not None:
            return int(match.group(1).replace(",", ""))
    raise DelawareOpinionsSourceChangedError(
        "source_total_missing",
        "Delaware Opinions page lacks its source result count",
        details={"source_url": source_url},
    )


def _selected_page_size(soup: BeautifulSoup, *, source_url: str) -> int:
    select = soup.find("select", attrs={"name": "ctlOpinions1selresults"})
    if not isinstance(select, Tag):
        raise DelawareOpinionsSourceChangedError(
            "page_size_selector_missing",
            "Delaware Opinions page lacks its result-size selector",
            details={"source_url": source_url},
        )
    selected = select.find("option", selected=True)
    value = (
        _text(selected.get("value"))
        if isinstance(selected, Tag)
        else None
    )
    if value is None:
        first_option = select.find("option")
        value = (
            _text(first_option.get("value"))
            if isinstance(first_option, Tag)
            else None
        )
    try:
        page_size = int(value or "")
    except ValueError as error:
        raise DelawareOpinionsSourceChangedError(
            "page_size_value_changed",
            "Delaware Opinions returned a nonnumeric page size",
            details={"value": value, "source_url": source_url},
        ) from error
    if page_size not in NATIVE_PAGE_SIZES:
        raise DelawareOpinionsSourceChangedError(
            "page_size_value_changed",
            "Delaware Opinions returned an unverified native page size",
            details={"value": page_size, "source_url": source_url},
        )
    return page_size


def _page_position(
    soup: BeautifulSoup,
    *,
    total: int,
    page_size: int,
    source_url: str,
) -> tuple[int, int]:
    current_button = soup.select_one("button[aria-current='page']")
    if isinstance(current_button, Tag):
        label = _text(current_button.get("aria-label"))
        match = re.fullmatch(
            r"Page\s+(\d+)\s+of\s+(\d+)",
            label or "",
            flags=re.I,
        )
        if match is None:
            raise DelawareOpinionsSourceChangedError(
                "pagination_label_changed",
                "Delaware Opinions active-page label is unrecognized",
                details={"label": label, "source_url": source_url},
            )
        return int(match.group(1)), int(match.group(2))
    if total <= page_size:
        return 1, 1
    raise DelawareOpinionsSourceChangedError(
        "pagination_missing",
        "Delaware Opinions reports more records than one page without pagination",
        details={
            "source_total": total,
            "page_size": page_size,
            "source_url": source_url,
        },
    )


def parse_index_page(
    html: str,
    *,
    source_url: str = INDEX_URL,
    expected_page: int | None = None,
) -> OpinionIndexPage:
    """Parse one official Opinions and Orders result page."""

    soup = BeautifulSoup(html, "html.parser")
    alert = _alert_message(soup)
    if alert and alert.casefold().startswith("no results found"):
        page_size = _selected_page_size(soup, source_url=source_url)
        return OpinionIndexPage(
            records=(),
            source_total=0,
            current_page=expected_page or 1,
            total_pages=0,
            page_size=page_size,
            authoritative_empty=True,
            schema_fingerprint=schema_fingerprint(
                {"kind": "delaware_opinions", "state": "authoritative_empty"}
            ),
            source_url=source_url,
        )
    if alert:
        raise DelawareOpinionsSelectionError(
            "source_rejected_filters",
            alert,
            details={"source_url": source_url},
        )

    table, headers = _find_index_table(soup, source_url=source_url)
    total = _total_count(soup, source_url=source_url)
    page_size = _selected_page_size(soup, source_url=source_url)
    current_page, total_pages = _page_position(
        soup,
        total=total,
        page_size=page_size,
        source_url=source_url,
    )
    expected_total_pages = math.ceil(total / page_size)
    if total_pages != expected_total_pages:
        raise DelawareOpinionsSourceChangedError(
            "pagination_total_changed",
            "Delaware Opinions pagination disagrees with its reported "
            "record total and page size",
            details={
                "source_total": total,
                "page_size": page_size,
                "reported_total_pages": total_pages,
                "expected_total_pages": expected_total_pages,
                "source_url": source_url,
            },
        )
    if expected_page is not None and current_page != expected_page:
        raise DelawareOpinionsSourceChangedError(
            "unexpected_page",
            "Delaware Opinions returned a different page than requested",
            details={
                "expected_page": expected_page,
                "observed_page": current_page,
                "source_url": source_url,
            },
        )

    body = table.find("tbody")
    row_parent = body if isinstance(body, Tag) else table
    records: list[dict[str, Any]] = []
    for row in row_parent.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != 7:
            raise DelawareOpinionsSourceChangedError(
                "index_row_shape_changed",
                "Delaware Opinions result row does not contain seven fields",
                details={
                    "cell_count": len(cells),
                    "source_url": source_url,
                },
            )
        link = cells[0].find("a", href=True)
        if not isinstance(link, Tag):
            raise DelawareOpinionsSourceChangedError(
                "document_link_missing",
                "Delaware Opinions result lacks its PDF link",
                details={"source_url": source_url},
            )
        pdf_url = requests.compat.urljoin(source_url, str(link["href"]))
        document_id = _required_text(
            (parse_qs(urlparse(pdf_url).query).get("id") or [None])[0],
            "document ID",
        )
        if not document_id.isdigit():
            raise DelawareOpinionsSourceChangedError(
                "document_id_format_changed",
                "Delaware Opinions PDF link lacks a numeric document ID",
                details={"pdf_url": pdf_url},
            )
        caption = _required_text(
            cells[0].get_text(" ", strip=True),
            "caption",
        )
        document_date = _parse_document_date(
            cells[1].get_text(" ", strip=True)
        )
        file_number = _text(cells[2].get_text(" ", strip=True))
        court_name = _required_text(
            cells[3].get_text(" ", strip=True),
            "court",
        )
        case_type = _text(cells[4].get_text(" ", strip=True))
        officer_parts = [
            _text(value)
            for value in cells[5].stripped_strings
            if _text(value) is not None
        ]
        judicial_officer = _text(" ".join(officer_parts))
        description = _text(cells[6].get_text(" ", strip=True))
        publication_kind = _publication_kind(description)
        court_id = _court_id(court_name)
        records.append(
            {
                "canonical_ref": f"DEOPINION:{document_id}",
                "evidence_ref": f"DEOPINION:{document_id}",
                "source_id": SOURCE_ID,
                "record_kind": "published_opinion_or_order",
                "native_document_id": document_id,
                "caption": caption,
                "document_date": document_date,
                "source_date_label": "Date",
                "file_number": file_number,
                "raw_case_number": file_number,
                "court": {
                    "court_id": court_id,
                    "native_court_id": court_id,
                    "name": court_name,
                    "state_code": STATE_CODE,
                    "official_url": LANDING_URL,
                },
                "case_type": case_type,
                "judicial_officer": judicial_officer,
                "judicial_officer_name": judicial_officer,
                "judicial_officer_title": None,
                "description": description,
                "publication_kind": publication_kind,
                "publication_kind_basis": "description_keyword",
                "source_url": pdf_url,
                "pdf_url": pdf_url,
                "access_state": "public",
                "native_access_state": "official anonymous PDF",
                "certified_record": False,
                "documents": [
                    _pdf_document_record(
                        document_id,
                        publication_kind=publication_kind,
                        document_date=document_date,
                        source_url=pdf_url,
                    )
                ],
                "source_scope": _source_scope(),
                "raw": {
                    "caption": caption,
                    "date": _text(cells[1].get_text(" ", strip=True)),
                    "file_number": file_number,
                    "court": court_name,
                    "type": case_type,
                    "judicial_officer_parts": officer_parts,
                    "description": description,
                },
            }
        )
    if not records and total:
        raise DelawareOpinionsSourceChangedError(
            "index_rows_missing",
            "Delaware Opinions reports results but exposes no parseable rows",
            details={"source_total": total, "source_url": source_url},
        )
    if len(records) > page_size or len(records) > total:
        raise DelawareOpinionsSourceChangedError(
            "index_count_inconsistent",
            "Delaware Opinions row count conflicts with source metadata",
            details={
                "rows": len(records),
                "page_size": page_size,
                "source_total": total,
                "source_url": source_url,
            },
        )
    return OpinionIndexPage(
        records=tuple(records),
        source_total=total,
        current_page=current_page,
        total_pages=total_pages,
        page_size=page_size,
        authoritative_empty=False,
        schema_fingerprint=schema_fingerprint(
            {
                "kind": "delaware_opinions",
                "headers": headers,
                "record_schema": inferred_schema(records[:1]),
            }
        ),
        source_url=source_url,
    )


def _option_records(
    soup: BeautifulSoup,
    *,
    select_name: str,
    option_group: str,
    source_url: str,
) -> list[dict[str, Any]]:
    select = soup.find("select", attrs={"name": select_name})
    if not isinstance(select, Tag):
        raise DelawareOpinionsSourceChangedError(
            "source_options_missing",
            f"Delaware Opinions form lacks select {select_name}",
            details={"source_url": source_url, "select_name": select_name},
        )
    records: list[dict[str, Any]] = []
    for option in select.find_all("option"):
        value = _text(option.get("value")) or _text(
            option.get_text(" ", strip=True)
        )
        label = _text(option.get_text(" ", strip=True))
        if value is None or label is None:
            continue
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "source_option",
                "option_group": option_group,
                "native_value": value,
                "label": label,
                "source_url": source_url,
            }
        )
    if not records:
        raise DelawareOpinionsSourceChangedError(
            "source_options_empty",
            f"Delaware Opinions form select {select_name} has no options",
            details={"source_url": source_url, "select_name": select_name},
        )
    return records


def parse_options_page(
    html: str,
    *,
    source_url: str = INDEX_URL,
) -> list[dict[str, Any]]:
    """Return the source's live court, period, year, and page-size options."""

    soup = BeautifulSoup(html, "html.parser")
    records = [
        *_option_records(
            soup,
            select_name="ctlOpinions1selAgencies",
            option_group="court",
            source_url=source_url,
        ),
        *_option_records(
            soup,
            select_name="ctlOpinions1selperiods",
            option_group="revision_period",
            source_url=source_url,
        ),
        *_option_records(
            soup,
            select_name="ctlOpinions1selyears",
            option_group="year",
            source_url=source_url,
        ),
        *_option_records(
            soup,
            select_name="ctlOpinions1selresults",
            option_group="page_size",
            source_url=source_url,
        ),
    ]
    return records


def _content_disposition_filename(value: str | None, document_id: str) -> str:
    if value:
        encoded = re.search(
            r"filename\*=UTF-8''([^;]+)",
            value,
            flags=re.I,
        )
        if encoded:
            filename = _text(unquote(encoded.group(1)))
            if filename:
                return filename
        quoted = re.search(r'filename="([^"]+)"', value, flags=re.I)
        if quoted:
            filename = _text(quoted.group(1))
            if filename:
                return filename
        plain = re.search(r"filename=([^;]+)", value, flags=re.I)
        if plain:
            filename = _text(plain.group(1).strip("'\""))
            if filename:
                return filename
    return f"delaware-opinion-{document_id}.pdf"


def _field_match(
    record: Mapping[str, Any],
    *,
    field_filter: str,
    query_text: str,
) -> bool:
    if field_filter == "all" or not query_text:
        return True
    fields = {
        "caption": record.get("caption"),
        "case-number": record.get("file_number"),
        "judge": record.get("judicial_officer"),
        "description": record.get("description"),
    }
    value = _text(fields[field_filter])
    return value is not None and query_text.casefold() in value.casefold()


class DelawareOpinionsClient:
    """Transport-injectable client for the official archive."""

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

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str = "text/html,application/xhtml+xml",
    ) -> Any:
        headers = {"Accept": accept, "User-Agent": self.user_agent}
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise DelawareOpinionsError(
                    "transport_error",
                    f"Delaware Opinions request failed after {attempt} attempts: {error}",
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt, "url": url},
                ) from error
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    retry_after = None
                    raw_retry_after = response.headers.get("Retry-After")
                    if raw_retry_after:
                        try:
                            retry_after = max(0.0, float(raw_retry_after))
                        except ValueError:
                            retry_after = None
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                raise DelawareOpinionsError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"Delaware Opinions returned HTTP {status_code}",
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
            if status_code == 404:
                if (
                    urlparse(url).path.casefold()
                    == urlparse(DOWNLOAD_URL).path.casefold()
                    and params
                    and params.get("id") is not None
                ):
                    raise DelawareOpinionNotFoundError(
                        str(params["id"]),
                        url=url,
                    )
                raise DelawareOpinionsSourceChangedError(
                    "endpoint_not_found",
                    "Delaware Opinions official endpoint returned HTTP 404",
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise DelawareOpinionsError(
                    "source_access_failed",
                    f"Delaware Opinions returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code >= 400:
                raise DelawareOpinionsError(
                    "http_status_error",
                    f"Delaware Opinions returned HTTP {status_code}",
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
        response_url = _text(getattr(response, "url", None))
        if response_url is not None:
            return response_url
        if not params:
            return fallback_url
        return f"{fallback_url}?{urlencode(params, doseq=True)}"

    @staticmethod
    def _index_params(
        *,
        query_text: str,
        court: str,
        case_type: str,
        division: str,
        period: str,
        year: str | None,
        revised_after: str | None,
        revised_before: str | None,
        page_size: int,
        sort_by: str,
        sort_order: str,
        page: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "ag": court,
            "typ": case_type,
            "div": division,
            "period": period,
            "results": page_size,
            "ss": query_text,
            "srt": sort_by,
            "srtord": SORT_ORDERS[sort_order],
            "page": page,
        }
        if period == "year" and year is not None:
            params["year"] = year
        if period == "date":
            params["from"] = revised_after or ""
            params["to"] = revised_before or ""
        return params

    def search(
        self,
        query_text: str = "",
        *,
        field_filter: str = "all",
        court: str = "All Courts",
        case_type: str = "",
        division: str = "",
        period: str | None = None,
        year: str | None = None,
        revised_after: str | None = None,
        revised_before: str | None = None,
        page: int | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> OpinionIndexFetch:
        """Search and follow every native page unless one page is selected."""

        normalized_query = _text(query_text) or ""
        if len(normalized_query) > MAX_SEARCH_TEXT_LENGTH:
            raise DelawareOpinionsSelectionError(
                "search_text_too_long",
                "The official archive search field accepts at most "
                f"{MAX_SEARCH_TEXT_LENGTH} characters",
                details={"length": len(normalized_query)},
            )
        if field_filter not in FIELD_FILTERS:
            raise DelawareOpinionsSelectionError(
                "unsupported_field_filter",
                f"unsupported field filter: {field_filter}",
            )
        if page_size not in NATIVE_PAGE_SIZES:
            raise DelawareOpinionsSelectionError(
                "unsupported_page_size",
                "page size must be one of the live source values "
                f"{sorted(NATIVE_PAGE_SIZES)}",
            )
        if sort_by not in SORT_FIELDS:
            raise DelawareOpinionsSelectionError(
                "unsupported_sort_field",
                f"unsupported sort field: {sort_by}",
            )
        if sort_order not in SORT_ORDERS:
            raise DelawareOpinionsSelectionError(
                "unsupported_sort_order",
                f"unsupported sort order: {sort_order}",
            )
        native_page = 1 if page is None else _positive_int(page, "page")
        native_period = period or str(CURRENT_YEAR)
        if native_period == "date" and (
            revised_after is None or revised_before is None
        ):
            raise DelawareOpinionsSelectionError(
                "incomplete_revision_date_range",
                "The official custom-date filter requires both dates",
            )

        first_params = self._index_params(
            query_text=normalized_query,
            court=_text(court) or "All Courts",
            case_type=_text(case_type) or "",
            division=_text(division) or "",
            period=native_period,
            year=_text(year),
            revised_after=_text(revised_after),
            revised_before=_text(revised_before),
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            page=native_page,
        )
        response = self._request(INDEX_URL, params=first_params)
        response_url = self._response_url(response, INDEX_URL, first_params)
        first_page = parse_index_page(
            response.text,
            source_url=response_url,
            expected_page=native_page,
        )
        if first_page.authoritative_empty:
            return OpinionIndexFetch(
                records=(),
                source_total=0,
                pages_fetched=1,
                source_pages=0,
                next_url=None,
                schema_fingerprint=first_page.schema_fingerprint,
                source_url=response_url,
                field_filter=field_filter,
                source_records_before_field_filter=0,
            )

        collected: dict[str, Mapping[str, Any]] = {}
        page_schemas = {first_page.schema_fingerprint}
        pages_fetched = 0
        last_page = first_page
        pages_to_fetch = (
            [native_page]
            if page is not None
            else list(range(native_page, first_page.total_pages + 1))
        )
        for requested_page in pages_to_fetch:
            if requested_page == native_page:
                current = first_page
            else:
                params = dict(first_params)
                params["page"] = requested_page
                response = self._request(INDEX_URL, params=params)
                response_url = self._response_url(response, INDEX_URL, params)
                current = parse_index_page(
                    response.text,
                    source_url=response_url,
                    expected_page=requested_page,
                )
            pages_fetched += 1
            if (
                current.source_total != first_page.source_total
                or current.total_pages != first_page.total_pages
                or current.page_size != first_page.page_size
            ):
                raise DelawareOpinionsSourceChangedError(
                    "pagination_metadata_changed",
                    "Delaware Opinions changed its total, page count, or "
                    "page size during one traversal",
                    details={
                        "page": current.current_page,
                        "first_source_total": first_page.source_total,
                        "observed_source_total": current.source_total,
                        "first_total_pages": first_page.total_pages,
                        "observed_total_pages": current.total_pages,
                        "first_page_size": first_page.page_size,
                        "observed_page_size": current.page_size,
                    },
                )
            page_schemas.add(current.schema_fingerprint)
            last_page = current
            for record in current.records:
                document_id = _required_text(
                    record.get("native_document_id"),
                    "document ID",
                )
                existing = collected.get(document_id)
                if existing is not None and canonical_json(existing) != canonical_json(
                    record
                ):
                    raise DelawareOpinionsSourceChangedError(
                        "duplicate_document_conflict",
                        "Delaware Opinions returned conflicting rows for one "
                        "document ID",
                        details={"document_id": document_id},
                    )
                collected[document_id] = record

        source_records = list(collected.values())
        if page is None and len(source_records) != first_page.source_total:
            raise DelawareOpinionsSourceChangedError(
                "collection_incomplete",
                "Delaware Opinions traversal did not reconcile to the "
                "source-reported record total",
                details={
                    "source_total": first_page.source_total,
                    "unique_records": len(source_records),
                    "pages_fetched": pages_fetched,
                    "source_pages": first_page.total_pages,
                },
            )
        selected = [
            record
            for record in source_records
            if _field_match(
                record,
                field_filter=field_filter,
                query_text=normalized_query,
            )
        ]
        next_url = None
        if page is not None and last_page.current_page < last_page.total_pages:
            next_params = dict(first_params)
            next_params["page"] = last_page.current_page + 1
            next_url = f"{INDEX_URL}?{urlencode(next_params, doseq=True)}"
        return OpinionIndexFetch(
            records=tuple(selected),
            source_total=first_page.source_total,
            pages_fetched=pages_fetched,
            source_pages=first_page.total_pages,
            next_url=next_url,
            schema_fingerprint=schema_fingerprint(
                {"pages": sorted(page_schemas)}
            ),
            source_url=response_url,
            field_filter=field_filter,
            source_records_before_field_filter=len(source_records),
        )

    def options(self) -> tuple[Mapping[str, Any], ...]:
        """Return the live source-native filter values."""

        params = self._index_params(
            query_text="",
            court="All Courts",
            case_type="",
            division="",
            period="year",
            year=str(CURRENT_YEAR),
            revised_after=None,
            revised_before=None,
            page_size=DEFAULT_PAGE_SIZE,
            sort_by="date",
            sort_order="desc",
            page=1,
        )
        response = self._request(INDEX_URL, params=params)
        response_url = self._response_url(response, INDEX_URL, params)
        return tuple(parse_options_page(response.text, source_url=response_url))

    def download(self, document_id: str) -> DelawareOpinionDownload:
        """Fetch and validate one official archive PDF."""

        native_id = _document_id(document_id)
        params = {"id": native_id}
        response = self._request(
            DOWNLOAD_URL,
            params=params,
            accept="application/pdf",
        )
        source_url = self._response_url(response, DOWNLOAD_URL, params)
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            content = str(getattr(response, "text", "")).encode()
        content_type = _text(response.headers.get("Content-Type")) or ""
        media_type = content_type.split(";", 1)[0].strip().casefold()
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise DelawareOpinionsSourceChangedError(
                "download_not_pdf",
                "Delaware Opinions download did not return a validated PDF",
                details={
                    "document_id": native_id,
                    "content_type": content_type,
                    "content_prefix": content[:16].hex(),
                    "source_url": source_url,
                },
            )
        disposition = _text(response.headers.get("Content-Disposition"))
        return DelawareOpinionDownload(
            document_id=native_id,
            content=content,
            media_type="application/pdf",
            filename=_content_disposition_filename(disposition, native_id),
            source_url=source_url,
            content_disposition=disposition,
            etag=_text(response.headers.get("ETag")),
            last_modified=_text(response.headers.get("Last-Modified")),
        )

    def probe(self) -> Mapping[str, Any]:
        """Verify one stable metadata row and its direct PDF."""

        fetched = self.search(
            PROBE_CASE_NUMBER,
            field_filter="case-number",
            period="year",
            year=str(PROBE_YEAR),
            page=1,
        )
        match = next(
            (
                record
                for record in fetched.records
                if record.get("native_document_id") == PROBE_DOCUMENT_ID
            ),
            None,
        )
        if match is None:
            raise DelawareOpinionsSourceChangedError(
                "probe_document_missing",
                "The stable Delaware Opinions metadata sentinel was not returned",
                details={
                    "document_id": PROBE_DOCUMENT_ID,
                    "case_number": PROBE_CASE_NUMBER,
                },
            )
        if match.get("caption") != PROBE_CAPTION:
            raise DelawareOpinionsSourceChangedError(
                "probe_caption_changed",
                "The Delaware Opinions sentinel caption changed",
                details={
                    "expected": PROBE_CAPTION,
                    "observed": match.get("caption"),
                },
            )
        download = self.download(PROBE_DOCUMENT_ID)
        record = dict(match)
        record["probe"] = {
            "document_id": PROBE_DOCUMENT_ID,
            "pdf_sha256": download.sha256,
            "pdf_bytes": len(download.content),
            "pdf_filename": download.filename,
            "pdf_media_type": download.media_type,
        }
        return record


def _query_selection(args: argparse.Namespace) -> tuple[str, str]:
    candidates = [
        ("all", getattr(args, "query", None)),
        ("all", getattr(args, "text", None)),
        ("caption", getattr(args, "caption", None)),
        ("case-number", getattr(args, "case_number", None)),
        ("judge", getattr(args, "judge", None)),
        ("description", getattr(args, "description", None)),
    ]
    selected = [
        (field_filter, _text(value))
        for field_filter, value in candidates
        if _text(value) is not None
    ]
    if len(selected) > 1:
        raise DelawareOpinionsSelectionError(
            "multiple_search_fields",
            "The source exposes one metadata-search field; select one text, "
            "caption, case-number, judge, or description query",
        )
    if not selected:
        return "", "all"
    field_filter, query_text = selected[0]
    assert query_text is not None
    if len(query_text) > MAX_SEARCH_TEXT_LENGTH:
        raise DelawareOpinionsSelectionError(
            "search_text_too_long",
            "The official archive search field accepts at most "
            f"{MAX_SEARCH_TEXT_LENGTH} characters",
            details={"length": len(query_text)},
        )
    return query_text, field_filter


def _revision_selection(
    args: argparse.Namespace,
) -> tuple[str, str | None, str | None, str | None]:
    period = _text(getattr(args, "period", None))
    year = _text(getattr(args, "year", None))
    after_value = _text(getattr(args, "revised_after", None))
    before_value = _text(getattr(args, "revised_before", None))
    if year and (period or after_value or before_value):
        raise DelawareOpinionsSelectionError(
            "conflicting_revision_filters",
            "--year cannot be combined with --period or custom dates",
        )
    if period and (after_value or before_value):
        raise DelawareOpinionsSelectionError(
            "conflicting_revision_filters",
            "--period cannot be combined with custom dates",
        )
    if after_value or before_value:
        if after_value is None or before_value is None:
            raise DelawareOpinionsSelectionError(
                "incomplete_revision_date_range",
                "The official custom-date filter requires both "
                "--revised-after and --revised-before",
            )
        source_after, parsed_after = _source_date(
            after_value,
            "--revised-after",
        )
        source_before, parsed_before = _source_date(
            before_value,
            "--revised-before",
        )
        if parsed_before < parsed_after:
            raise DelawareOpinionsSelectionError(
                "invalid_revision_date_range",
                "--revised-before must not precede --revised-after",
            )
        return "date", None, source_after, source_before
    if year:
        if not re.fullmatch(r"\d{4}", year):
            raise DelawareOpinionsSelectionError(
                "invalid_revision_year",
                "--year must contain four digits",
                details={"value": year},
            )
        return "year", year, None, None
    period_values = {
        None: str(CURRENT_YEAR),
        "current-year": str(CURRENT_YEAR),
        "7": "7",
        "30": "30",
        "180": "180",
    }
    if period not in period_values:
        raise DelawareOpinionsSelectionError(
            "unsupported_revision_period",
            "--period must be 7, 30, 180, or current-year",
        )
    return period_values[period], None, None, None


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    """Build the shared public-record query envelope."""

    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "query": getattr(args, "query", None),
            "text": getattr(args, "text", None),
            "caption": getattr(args, "caption", None),
            "case_number": getattr(args, "case_number", None),
            "judge": getattr(args, "judge", None),
            "description": getattr(args, "description", None),
            "court": getattr(args, "court", None),
            "case_type": getattr(args, "case_type", None),
            "division": getattr(args, "division", None),
            "period": getattr(args, "period", None),
            "year": getattr(args, "year", None),
            "revised_after": getattr(args, "revised_after", None),
            "revised_before": getattr(args, "revised_before", None),
            "page": getattr(args, "page", None),
            "page_size": getattr(args, "page_size", DEFAULT_PAGE_SIZE),
            "sort_by": getattr(args, "sort_by", "date"),
            "sort_order": getattr(args, "sort_order", "desc"),
            "limit": getattr(args, "limit", None),
        }
        requested_limit = getattr(args, "limit", None)
        if getattr(args, "page", None) is not None:
            cursor = f"delaware-opinions:page:{args.page}"
    elif args.command == "download":
        parameters = {
            "document_id": str(args.document_id),
            "destination": str(args.destination),
        }
    elif args.command == "probe":
        parameters = {
            "document_id": PROBE_DOCUMENT_ID,
            "case_number": PROBE_CASE_NUMBER,
            "year": PROBE_YEAR,
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Delaware",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _make_client(args: argparse.Namespace) -> DelawareOpinionsClient:
    return DelawareOpinionsClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: DelawareOpinionsError,
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


def _caller_limit(
    records: Sequence[Mapping[str, Any]],
    *,
    limit: int | None,
    warnings: Sequence[str],
) -> tuple[list[Mapping[str, Any]], tuple[str, ...]]:
    selected = list(records)
    if limit is None or len(selected) <= limit:
        return selected, tuple(warnings)
    return (
        selected[:limit],
        (
            *warnings,
            f"Caller limit returned {limit} of {len(selected)} matched "
            "archive records fetched.",
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DelawareOpinionsClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one official Delaware Opinions operation."""

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
        elif args.command == "search":
            query_text, field_filter = _query_selection(args)
            period, year, revised_after, revised_before = (
                _revision_selection(args)
            )
            fetched = source_client.search(
                query_text,
                field_filter=field_filter,
                court=args.court,
                case_type=args.case_type,
                division=args.division,
                period=period,
                year=year,
                revised_after=revised_after,
                revised_before=revised_before,
                page=args.page,
                page_size=args.page_size,
                sort_by=args.sort_by,
                sort_order=args.sort_order,
            )
            warnings = list(SOURCE_WARNINGS)
            removed = (
                fetched.source_records_before_field_filter
                - len(fetched.records)
            )
            if removed:
                warnings.append(
                    f"Requested {field_filter} filtering removed {removed} "
                    "records that matched the source-wide metadata search in "
                    "other fields."
                )
            selected, result_warnings = _caller_limit(
                fetched.records,
                limit=args.limit,
                warnings=warnings,
            )
            records = []
            for record in selected:
                normalized = dict(record)
                normalized["search_metadata"] = {
                    "source_total": fetched.source_total,
                    "source_pages": fetched.source_pages,
                    "pages_fetched": fetched.pages_fetched,
                    "source_records_before_field_filter": (
                        fetched.source_records_before_field_filter
                    ),
                    "field_filter": fetched.field_filter,
                    "schema_fingerprint": fetched.schema_fingerprint,
                }
                records.append(normalized)
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_url,
                warnings=result_warnings,
            )
        elif args.command == "download":
            destination = Path(args.destination).expanduser()
            if destination.exists() and not args.overwrite:
                raise OSError(
                    f"destination exists; pass --overwrite: {destination}"
                )
            download = source_client.download(str(args.document_id))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download.content)
            receipt = download.receipt(destination)
            record = {
                "canonical_ref": (
                    f"DEOPINION:{download.document_id}:PDF:"
                    f"{download.sha256}"
                ),
                "evidence_ref": f"DEOPINION:{download.document_id}",
                "source_id": SOURCE_ID,
                "record_kind": "opinion_pdf_artifact",
                "native_document_id": download.document_id,
                "source_url": download.source_url,
                "access_state": "public",
                "native_access_state": "official anonymous PDF",
                "certification_status": "uncertified_official_site_copy",
                "artifact_receipt": receipt,
                "source_scope": _source_scope(),
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[str(destination.resolve())],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                [source_client.probe()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise DelawareOpinionsSelectionError(
                "unsupported_command",
                f"unsupported Delaware Opinions command: {args.command}",
            )
    except DelawareOpinionNotFoundError:
        result = PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    except DelawareOpinionsError as error:
        result = _failure_result(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
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
        summary=f"Delaware Opinions {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Delaware Opinions {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("native_document_id")
            or record.get("native_value")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _arg_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _arg_nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _arg_page_size(value: str) -> int:
    parsed = int(value)
    if parsed not in NATIVE_PAGE_SIZES:
        raise argparse.ArgumentTypeError(
            f"value must be one of {sorted(NATIVE_PAGE_SIZES)}"
        )
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
        type=_arg_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_arg_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Delaware Courts' official Opinions and Orders archive"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search published opinion/order metadata",
    )
    search.add_argument(
        "query",
        nargs="?",
        help="General source-wide metadata search",
    )
    search.add_argument("--text", help="General source-wide metadata search")
    search.add_argument("--caption", help="Search then filter caption")
    search.add_argument(
        "--case-number",
        help="Search then filter the File Number field",
    )
    search.add_argument(
        "--judge",
        help="Search then filter the Judicial Officer field",
    )
    search.add_argument(
        "--description",
        help="Search then filter the Description field",
    )
    search.add_argument(
        "--court",
        default="All Courts",
        help="Source-native court value shown by options",
    )
    search.add_argument(
        "--case-type",
        default="",
        help="Source-native type value, normally Civil or Criminal",
    )
    search.add_argument(
        "--division",
        default="",
        help="Source-native division value, such as ccld",
    )
    search.add_argument(
        "--period",
        choices=("7", "30", "180", "current-year"),
        default=None,
        help="Source revision window; defaults to the current year",
    )
    search.add_argument("--year", help="Custom four-digit revision year")
    search.add_argument(
        "--revised-after",
        help="Custom revision start, YYYY-MM-DD or MM/DD/YYYY",
    )
    search.add_argument(
        "--revised-before",
        help="Custom revision end, YYYY-MM-DD or MM/DD/YYYY",
    )
    search.add_argument(
        "--page",
        type=_arg_positive_int,
        default=None,
        help="Fetch one native page; defaults to following all pages",
    )
    search.add_argument(
        "--page-size",
        type=_arg_page_size,
        default=DEFAULT_PAGE_SIZE,
        help="Native page size: 25, 50, or 100",
    )
    search.add_argument(
        "--sort-by",
        choices=sorted(value for value in SORT_FIELDS if value),
        default="date",
    )
    search.add_argument(
        "--sort-order",
        choices=sorted(SORT_ORDERS),
        default="desc",
    )
    search.add_argument(
        "--limit",
        type=_arg_positive_int,
        default=None,
        help="Caller-side limit after fetching and field filtering",
    )
    _add_runtime_and_output(search)

    options = subparsers.add_parser(
        "options",
        help="List live court, revision-period, year, and page-size values",
    )
    _add_runtime_and_output(options)

    download = subparsers.add_parser(
        "download",
        help="Download and receipt one official opinion/order PDF",
    )
    download.add_argument("document_id")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify a stable metadata row and its direct PDF",
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
