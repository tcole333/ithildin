#!/usr/bin/env python3
"""Query official Harris County Clerk trustee-foreclosure notices.

The verified Clerk route is distinct from the real-property instrument index:
it indexes foreclosure notices by document ID, sale month, or filing month and
serves the notice PDFs anonymously. A notice describes a proposed sale and
often cites liens and recorded instruments; it is not evidence that title
transferred.

Examples:
    uv run python tools/query_harris_foreclosures.py search \
        --document-id FRCL-2026-4797 --output /tmp/harris-frcl.json
    uv run python tools/query_harris_foreclosures.py search \
        --file-date 2026-07 --output /tmp/harris-frcl-july.json
    uv run python tools/query_harris_foreclosures.py download FRCL-2026-4797 \
        --destination /tmp/FRCL-2026-4797.pdf
    uv run python tools/query_harris_foreclosures.py sentinel --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-harris-clerk-foreclosures"
SOURCE = SOURCE_ID
BASE_URL = "https://www.cclerk.hctx.net"
SEARCH_URL = f"{BASE_URL}/applications/websearch/FRCL_R.aspx"
TIMEOUT = 30.0
REQUEST_DELAY = 0.2
MAX_RETRIES = 2
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

DOCUMENT_FIELD = "ctl00$ContentPlaceHolder1$txtFileNo"
DATE_KIND_FIELD = "ctl00$ContentPlaceHolder1$rbtlDate"
YEAR_FIELD = "ctl00$ContentPlaceHolder1$ddlYear"
MONTH_FIELD = "ctl00$ContentPlaceHolder1$ddlMonth"
SEARCH_BUTTON = "ctl00$ContentPlaceHolder1$btnSearch"
GRID_EVENT_TARGET = "ctl00$ContentPlaceHolder1$GridView1"

SENTINEL_DOCUMENT_ID = "FRCL-2026-4797"
SENTINEL_SALE_DATE = "08/04/2026"
SENTINEL_FILE_DATE = "07/08/2026"
SENTINEL_PAGE_COUNT = 2

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE,
    name="Harris County Clerk Trustee Foreclosure Notices",
    source_role="foreclosure_notice_index_and_documents",
    base_url=SEARCH_URL,
    dataset_id="FRCL",
    metadata={
        "authority": "Harris County Clerk",
        "jurisdiction_geoid": "48201",
        "record_identity_key": "document_id",
        "document_access": "anonymous_official_pdf",
        "evidence_scope": "foreclosure_notice_not_title_transfer",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="48201",
    name="Harris County, Texas",
    state_code="TX",
    county_fips="48201",
    locality="Harris County",
)
SOURCE_WARNINGS = (
    (
        "A trustee-foreclosure notice describes a proposed sale and related "
        "claims; it is not evidence that a sale occurred or title transferred."
    ),
    (
        "The Clerk's posting-through date is source-native current-coverage "
        "metadata and can advance independently of the query month."
    ),
)


class HarrisForeclosureError(RuntimeError):
    """Official foreclosure source request or query error."""


class HarrisForeclosureSourceChanged(HarrisForeclosureError):
    """The verified form, row, paginator, or PDF contract changed."""


class HarrisForeclosureTransportError(HarrisForeclosureError):
    """The official source was unreachable after bounded retries."""


class HarrisForeclosureRateLimited(HarrisForeclosureError):
    """The official source returned HTTP 429 after bounded retries."""


class HarrisForeclosureHTTPError(HarrisForeclosureError):
    """The official source returned a non-success HTTP status."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Harris County Clerk returned HTTP {status_code}")


@dataclass(frozen=True)
class TextResponse:
    url: str
    text: str
    status_code: int
    headers: Mapping[str, str]


@dataclass(frozen=True)
class PDFResponse:
    url: str
    content: bytes
    media_type: str
    headers: Mapping[str, str]


def _official_url(value: str, *, base: str = BASE_URL) -> str:
    parsed = urlparse(urljoin(base, value.strip()))
    if parsed.scheme not in {"http", "https"}:
        raise HarrisForeclosureError("Clerk URL is not HTTP(S)")
    if (parsed.hostname or "").lower() != "www.cclerk.hctx.net":
        raise HarrisForeclosureError("Clerk URL left the official host")
    return urlunparse(("https", parsed.netloc, parsed.path, "", parsed.query, ""))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = (
        value.get_text(" ", strip=True)
        if hasattr(value, "get_text")
        else str(value)
    )
    return re.sub(r"\s+", " ", text).strip()


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _year_month(value: str, name: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m")
    except ValueError as exc:
        raise HarrisForeclosureError(f"{name} must use YYYY-MM") from exc
    return parsed.year, parsed.month


def _positive_limit(value: int | None) -> None:
    if value is not None and value < 1:
        raise HarrisForeclosureError("--limit must be a positive integer")


class HarrisForeclosureClient:
    """Requests-compatible client for the Clerk's ASP.NET foreclosure portal."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = TIMEOUT,
        minimum_interval: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        sleeper=time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/pdf",
                "Accept-Language": "en-US,en;q=0.8",
            })
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._sleeper = sleeper
        self._last_request_at = 0.0

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        safe_url = _official_url(url)
        for attempt in range(self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = time.monotonic()
                response = self.session.request(
                    method,
                    safe_url,
                    data=data,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise HarrisForeclosureTransportError(
                    f"Harris County Clerk request failed: {exc}"
                ) from exc
            status = int(response.status_code)
            if status == 429 or status >= 500:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
            if status == 429:
                raise HarrisForeclosureRateLimited(
                    "Harris County Clerk returned HTTP 429"
                )
            if status < 200 or status >= 300:
                raise HarrisForeclosureHTTPError(status)
            return response
        raise HarrisForeclosureTransportError(
            "Harris County Clerk request exhausted retries"
        )

    def _get_html(self, url: str) -> TextResponse:
        response = self._request("GET", url)
        return TextResponse(
            url=str(response.url),
            text=str(response.text),
            status_code=int(response.status_code),
            headers=dict(response.headers),
        )

    def _post_html(
        self,
        url: str,
        data: Mapping[str, str],
    ) -> TextResponse:
        response = self._request("POST", url, data=data)
        return TextResponse(
            url=str(response.url),
            text=str(response.text),
            status_code=int(response.status_code),
            headers=dict(response.headers),
        )

    @staticmethod
    def _hidden_state(html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        hidden = {
            str(node.get("name")): str(node.get("value", ""))
            for node in soup.select('input[type="hidden"][name]')
        }
        if "__VIEWSTATE" not in hidden or "__EVENTVALIDATION" not in hidden:
            raise HarrisForeclosureSourceChanged(
                "foreclosure form is missing ASP.NET state fields"
            )
        return hidden

    def _postback(
        self,
        html: str,
        *,
        event_target: str,
        controls: Mapping[str, str],
    ) -> TextResponse:
        data = self._hidden_state(html)
        data.update(controls)
        data["__EVENTTARGET"] = event_target
        data["__EVENTARGUMENT"] = ""
        return self._post_html(SEARCH_URL, data)

    def _date_search_first_page(
        self,
        *,
        date_kind: str,
        year: int,
        month: int,
    ) -> TextResponse:
        controls = {
            DATE_KIND_FIELD: date_kind,
            YEAR_FIELD: str(year),
        }
        initial = self._get_html(SEARCH_URL)
        year_response = self._postback(
            initial.text,
            event_target=YEAR_FIELD,
            controls=controls,
        )
        year_soup = BeautifulSoup(year_response.text, "html.parser")
        month_values = {
            str(node.get("value"))
            for node in year_soup.select(f"select[name='{MONTH_FIELD}'] option")
        }
        if str(month) not in month_values:
            return year_response

        controls[MONTH_FIELD] = str(month)
        month_response = self._postback(
            year_response.text,
            event_target=MONTH_FIELD,
            controls=controls,
        )
        data = self._hidden_state(month_response.text)
        data.update(controls)
        data[SEARCH_BUTTON] = "Search"
        return self._post_html(SEARCH_URL, data)

    def search(
        self,
        *,
        document_id: str | None = None,
        file_date: str | None = None,
        sale_date: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        _positive_limit(limit)
        selectors = [
            document_id is not None,
            file_date is not None,
            sale_date is not None,
        ]
        if sum(selectors) != 1:
            raise HarrisForeclosureError(
                "choose exactly one of document ID, file date, or sale date"
            )

        if document_id is not None:
            initial = self._get_html(SEARCH_URL)
            data = self._hidden_state(initial.text)
            data[DOCUMENT_FIELD] = document_id.strip()
            data[SEARCH_BUTTON] = "Search"
            response = self._post_html(SEARCH_URL, data)
            query = {"document_id": document_id.strip()}
        else:
            raw_date = file_date or sale_date or ""
            date_name = "--file-date" if file_date else "--sale-date"
            year, month = _year_month(raw_date, date_name)
            response = self._date_search_first_page(
                date_kind="FileDate" if file_date else "SaleDate",
                year=year,
                month=month,
            )
            query = {
                "file_date" if file_date else "sale_date": (
                    f"{year:04d}-{month:02d}"
                )
            }

        pages_fetched = 0
        records: list[dict[str, Any]] = []
        records_by_id: dict[str, dict[str, Any]] = {}
        source_total: int | None = None
        posting_metadata: dict[str, Any] = {}
        truncated = False
        page_number = 1

        while True:
            parsed = parse_search_page(response.text, response.url)
            pages_fetched += 1
            if source_total is None:
                source_total = parsed["source_reported_total_results"]
                posting_metadata = parsed["coverage"]
            elif parsed["source_reported_total_results"] != source_total:
                raise HarrisForeclosureSourceChanged(
                    "source result total changed during pagination"
                )
            for record in parsed["results"]:
                document_key = str(record["document_id"])
                existing = records_by_id.get(document_key)
                if existing is not None:
                    if canonical_json(existing) != canonical_json(record):
                        raise HarrisForeclosureSourceChanged(
                            "one foreclosure document changed during "
                            f"pagination: {document_key}"
                        )
                    continue
                if limit is not None and len(records) >= limit:
                    truncated = True
                    break
                records.append(record)
                records_by_id[document_key] = record
            if truncated:
                break
            next_page = page_number + 1
            if next_page not in parsed["available_postback_pages"]:
                break
            controls = _selected_controls(response.text)
            paged = self._hidden_state(response.text)
            paged.update(controls)
            paged["__EVENTTARGET"] = GRID_EVENT_TARGET
            paged["__EVENTARGUMENT"] = f"Page${next_page}"
            response = self._post_html(SEARCH_URL, paged)
            page_number = next_page

        if (
            not truncated
            and source_total is not None
            and len(records_by_id) != source_total
        ):
            raise HarrisForeclosureSourceChanged(
                "completed foreclosure traversal did not reconcile to the "
                f"source total ({len(records_by_id)} unique rows versus "
                f"{source_total})"
            )
        return {
            "source": SOURCE,
            "status": "ok",
            "query": query,
            "source_url": SEARCH_URL,
            "coverage": {
                **posting_metadata,
                "source_reported_total_results": source_total,
                "pages_fetched": pages_fetched,
                "adapter_truncated": truncated,
                "returned_results": len(records),
            },
            "pagination": {
                "transport": "aspnet_grid_postback",
                "adapter_followed_all_source_pages": not truncated,
                "next_cursor": None,
            },
            "results": records,
        }

    def fetch_pdf(self, document_url: str) -> PDFResponse:
        response = self._request("GET", document_url)
        content = bytes(response.content)
        media_type = str(response.headers.get("Content-Type") or "")
        if not content.startswith(b"%PDF-"):
            raise HarrisForeclosureSourceChanged(
                "foreclosure document route did not return a PDF"
            )
        return PDFResponse(
            url=str(response.url),
            content=content,
            media_type=media_type,
            headers=dict(response.headers),
        )


def _selected_controls(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    controls: dict[str, str] = {}
    radio = soup.select_one(
        f"input[name='{DATE_KIND_FIELD}'][checked]"
    )
    if radio is not None:
        controls[DATE_KIND_FIELD] = str(radio.get("value", ""))
    for name in (YEAR_FIELD, MONTH_FIELD):
        selected = soup.select_one(f"select[name='{name}'] option[selected]")
        if selected is not None:
            controls[name] = str(selected.get("value", ""))
    return controls


def _coverage_metadata(soup: BeautifulSoup) -> dict[str, Any]:
    text = _clean_text(soup)
    posting_match = re.search(
        r"postings accepted through\s+(\d{1,2}/\d{1,2}/\d{4})",
        text,
        flags=re.I,
    )
    image_match = re.search(
        r"Images available from\s+(\d{1,2}/\d{1,2}/\d{4})",
        text,
        flags=re.I,
    )
    return {
        "postings_accepted_through": (
            _iso_date(posting_match.group(1)) if posting_match else None
        ),
        "postings_accepted_through_raw": (
            posting_match.group(1) if posting_match else None
        ),
        "document_images_available_from": (
            _iso_date(image_match.group(1)) if image_match else None
        ),
        "document_images_available_from_raw": (
            image_match.group(1) if image_match else None
        ),
    }


def parse_search_page(html: str, source_url: str) -> dict[str, Any]:
    """Parse one native GridView page and expose its postback page links."""
    safe_url = _official_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    count_node = soup.select_one("[id$='_lblCount']")
    count_match = re.search(r"(\d+)\s+Row\(s\)\s+Found", _clean_text(count_node))
    source_total = int(count_match.group(1)) if count_match else None
    records: list[dict[str, Any]] = []

    for link in soup.select("[id$='_HyperLinkDocIDEC']"):
        document_id = _clean_text(link)
        row = link.find_parent("tr")
        if not document_id or row is None:
            continue
        sale_date_raw = _clean_text(row.select_one("[id$='_lblSaleDate']"))
        file_date_raw = _clean_text(row.select_one("[id$='_lblFileDate']"))
        pages_raw = _clean_text(row.select_one("[id$='_lblPages']"))
        document_url = _official_url(
            str(link.get("href", "")),
            base=safe_url,
        )
        canonical_ref = canonical_property_ref(
            SOURCE,
            "48201",
            "foreclosure-notice",
            document_id,
        )
        records.append({
            "source_id": SOURCE,
            "record_kind": "foreclosure_notice",
            "record_scope": "proposed_sale_notice",
            "native_document_id": document_id,
            "document_id": document_id,
            "canonical_ref": canonical_ref,
            "evidence_ref": canonical_ref,
            "sale_date": _iso_date(sale_date_raw),
            "sale_date_raw": sale_date_raw or None,
            "file_date": _iso_date(file_date_raw),
            "file_date_raw": file_date_raw or None,
            "page_count": (
                int(pages_raw) if pages_raw.isdigit() else None
            ),
            "jurisdiction": {
                "geoid": "48201",
                "name": "Harris County, Texas",
                "state_code": "TX",
            },
            "source_url": safe_url,
            "document_access": {
                "document_url": document_url,
                "authentication": "anonymous",
                "format": "pdf",
                "access_state": "public",
            },
            "projection": {
                "projectable_as_recorded_instrument": False,
                "scope": "event_document_only",
                "reason": (
                    "notice is not a recorded title-transfer instrument or "
                    "proof that the proposed sale occurred"
                ),
            },
        })

    if source_total is None:
        text = _clean_text(soup).casefold()
        if not records and "no records found" in text:
            source_total = 0
        else:
            raise HarrisForeclosureSourceChanged(
                "result page lacks an authoritative result count"
            )
    if source_total == 0 and records:
        raise HarrisForeclosureSourceChanged(
            "result page reports zero records but contains result rows"
        )

    pages = {
        int(match.group(1))
        for link in soup.select("a[href*='__doPostBack']")
        if (
            match := re.search(
                re.escape(GRID_EVENT_TARGET)
                + r"','Page\$(\d+)'",
                str(link.get("href", "")),
            )
        )
    }
    return {
        "source_reported_total_results": source_total,
        "coverage": _coverage_metadata(soup),
        "available_postback_pages": pages,
        "results": records,
    }


def _selector_parameters(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "search":
        return {
            key: value
            for key, value in {
                "document_id": args.document_id,
                "file_date": args.file_date,
                "sale_date": args.sale_date,
            }.items()
            if value is not None
        }
    if args.command == "download":
        return {
            "document_id": args.document_id,
            "destination": str(args.destination),
        }
    return {"document_id": SENTINEL_DOCUMENT_ID}


def build_query(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    limit = getattr(args, "limit", None) if args.command == "search" else None
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        limit = None
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_selector_parameters(args),
            requested_limit=limit,
            metadata={"access_decision": dict(access_decision or {})},
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE)


def _access_failure(
    args: argparse.Namespace,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = dict(error.decision)
        status = ResultStatus(acquisition_result_status(decision))
        code = str(
            decision.get("reason_code") or "machine_acquisition_unavailable"
        )
        message = str(decision.get("reason") or error)
    else:
        decision = {}
        status = ResultStatus.UNAVAILABLE
        code = "catalog_unavailable"
        message = str(error)
    return PublicRecordsResult.failure(
        build_query(args, access_decision=decision),
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details={"access_decision": decision},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: HarrisForeclosureError,
) -> PublicRecordsResult:
    if isinstance(error, HarrisForeclosureSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, HarrisForeclosureRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
        retryable = True
    elif isinstance(error, HarrisForeclosureTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    elif isinstance(error, HarrisForeclosureHTTPError):
        status = (
            ResultStatus.SOURCE_CHANGED
            if error.status_code in {404, 410}
            else ResultStatus.UNAVAILABLE
        )
        code = f"source_http_{error.status_code}"
        category = "http"
        retryable = error.status_code >= 500
    else:
        status = ResultStatus.UNAVAILABLE
        code = "invalid_or_rejected_query"
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
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    payload: Mapping[str, Any],
) -> PublicRecordsResult:
    records = payload.get("results")
    coverage = payload.get("coverage")
    pagination = payload.get("pagination")
    if not isinstance(records, list) or not isinstance(coverage, Mapping):
        raise HarrisForeclosureSourceChanged(
            "normalized search payload is missing records or coverage"
        )
    normalized = []
    for source_record in records:
        record = dict(source_record)
        record["search_metadata"] = {
            "coverage": dict(coverage),
            "pagination": dict(pagination or {}),
        }
        normalized.append(record)
    if coverage.get("adapter_truncated"):
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=normalized,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        normalized,
        warnings=SOURCE_WARNINGS,
    )


def _artifact_record(
    notice: Mapping[str, Any],
    pdf: PDFResponse,
    destination: Path,
) -> dict[str, Any]:
    record = dict(notice)
    digest = hashlib.sha256(pdf.content).hexdigest()
    record["documents"] = [{
        "record_kind": "document_artifact",
        "document_type": "foreclosure_notice_pdf",
        "native_document_id": f"{notice['native_document_id']}:pdf",
        "source_url": pdf.url,
        "mime_type": pdf.media_type,
        "size": len(pdf.content),
        "sha256": digest,
        "page_count": notice.get("page_count"),
        "storage_path": str(destination.resolve()),
        "access_state": "public",
        "authentication": "anonymous",
        "certification_status": "uncertified",
    }]
    record["artifact_receipt"] = {
        "path": str(destination.resolve()),
        "size": len(pdf.content),
        "sha256": digest,
        "media_type": pdf.media_type,
        "source_url": pdf.url,
    }
    return record


def run_sentinel(
    client: HarrisForeclosureClient | Any | None = None,
) -> dict[str, Any]:
    client = client or HarrisForeclosureClient()
    checks: list[dict[str, Any]] = []
    try:
        payload = client.search(document_id=SENTINEL_DOCUMENT_ID)
        record = next(
            (
                row
                for row in payload["results"]
                if row["document_id"] == SENTINEL_DOCUMENT_ID
            ),
            None,
        )
        if record is None:
            raise HarrisForeclosureSourceChanged(
                "sentinel notice is missing"
            )
        expected = {
            "sale_date_raw": SENTINEL_SALE_DATE,
            "file_date_raw": SENTINEL_FILE_DATE,
            "page_count": SENTINEL_PAGE_COUNT,
        }
        for key, value in expected.items():
            if record.get(key) != value:
                raise HarrisForeclosureSourceChanged(
                    f"sentinel {key} changed from {value!r}"
                )
        checks.append({
            "name": "notice_index",
            "status": "ok",
            "document_id": record["document_id"],
            "sale_date": record["sale_date"],
            "file_date": record["file_date"],
            "page_count": record["page_count"],
            "source_url": record["source_url"],
        })
        pdf = client.fetch_pdf(
            record["document_access"]["document_url"]
        )
        checks.append({
            "name": "anonymous_notice_pdf",
            "status": "ok",
            "source_url": pdf.url,
            "media_type": pdf.media_type,
            "size": len(pdf.content),
            "sha256": hashlib.sha256(pdf.content).hexdigest(),
            "pdf_signature": pdf.content[:5].decode("ascii"),
        })
    except HarrisForeclosureError as exc:
        checks.append({
            "name": "notice_index_or_pdf",
            "status": "error",
            "error": str(exc),
        })
    ok = all(check["status"] == "ok" for check in checks)
    return {
        "source": SOURCE,
        "status": "ok" if ok else "unavailable",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "exact_urls": {"search": SEARCH_URL},
    }


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: HarrisForeclosureClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one foreclosure operation through the shared result contract."""
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (
        AcquisitionUnavailableError,
        CatalogError,
        OSError,
        ValueError,
    ) as error:
        result = _access_failure(args, error)
        _log(result.query, None)
        return result
    if not decision.get("allowed", False):
        result = _access_failure(
            args,
            AcquisitionUnavailableError(decision),
        )
        _log(result.query, None)
        return result

    query = build_query(args, access_decision=decision)
    source_client = client or HarrisForeclosureClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )
    raw_refs: tuple[str, ...] = ()
    try:
        if args.command == "search":
            _positive_limit(args.limit)
            payload = source_client.search(
                document_id=args.document_id,
                file_date=args.file_date,
                sale_date=args.sale_date,
                limit=args.limit,
            )
            result = _search_result(query, payload)
        elif args.command == "download":
            payload = source_client.search(document_id=args.document_id)
            if not payload["results"]:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                notice = payload["results"][0]
                pdf = source_client.fetch_pdf(
                    notice["document_access"]["document_url"]
                )
                destination = Path(args.destination).expanduser()
                if destination.exists() and not args.overwrite:
                    raise OSError(
                        f"destination exists; pass --overwrite: {destination}"
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(pdf.content)
                record = _artifact_record(notice, pdf, destination)
                raw_refs = (str(destination.resolve()),)
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=raw_refs,
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "sentinel":
            sentinel = run_sentinel(source_client)
            if sentinel["status"] != "ok":
                raise HarrisForeclosureSourceChanged(
                    "one or more live sentinel checks failed"
                )
            result = PublicRecordsResult.success(
                query,
                [{
                    **sentinel,
                    "source_id": SOURCE,
                    "record_kind": "source_health_check",
                    "native_document_id": "live-sentinel",
                }],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise HarrisForeclosureError(
                f"unsupported command: {args.command}"
            )
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
    except HarrisForeclosureError as error:
        result = _source_failure(query, error)

    count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    _log(query, count)
    return result


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Harris foreclosure {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Harris foreclosure {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "foreclosure_notice":
            print(
                f"- {record['document_id']} | "
                f"sale {record.get('sale_date') or '?'} | "
                f"filed {record.get('file_date') or '?'}"
            )
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=REQUEST_DELAY,
    )
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Harris County Clerk trustee-foreclosure notices"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search")
    selectors = search.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--document-id")
    selectors.add_argument("--file-date", help="Filing month YYYY-MM")
    selectors.add_argument("--sale-date", help="Sale month YYYY-MM")
    search.add_argument(
        "--limit",
        type=int,
        help="Optional user-requested limit; default follows all source pages",
    )
    _add_runtime_args(search)

    download = subparsers.add_parser("download")
    download.add_argument("document_id")
    download.add_argument("--destination", type=Path, required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_args(download)

    sentinel = subparsers.add_parser("sentinel")
    _add_runtime_args(sentinel)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0 or args.minimum_interval < 0:
        parser.error("--timeout must be positive and --minimum-interval non-negative")
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
