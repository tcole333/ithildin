#!/usr/bin/env python3
"""Query the official USVI Capture CAMA assessment and property-tax portal.

The Office of the Lieutenant Governor links to a territory-wide anonymous
E-Ring/Capture Citizen Access Portal.  Search observations are versioned by
the publisher's formatted parcel number and tax year.  The internal
``ParcelId`` changes across tax years and is therefore retained only as the
tax-year-specific locator used to open detail components.

Owner names, mailing addresses, values, balances, sales labels, statements,
and payments are assessment/tax observations.  They are not recorder
instruments or assertions of current title.

Omitting ``--limit`` exhausts the native GridView pages.  When ``--limit`` is
explicit, the adapter still exhausts the source pages before applying the
caller window and returns a query-bound continuation cursor.

Examples:
    uv run python tools/query_usvi_property_tax.py source --json
    uv run python tools/query_usvi_property_tax.py search legal "ST JAMES" \
      --tax-year 2026 --output /tmp/usvi-st-james.json
    uv run python tools/query_usvi_property_tax.py parcel 1-09801-0101-00 \
      --tax-year 2026 --output /tmp/usvi-parcel.json
    uv run python tools/query_usvi_property_tax.py artifact \
      1-09801-0101-00 --tax-year 2026 --kind bill \
      --statement 24457395 --destination /tmp/usvi-bill.html
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


OBSERVED_AT = "2026-07-30"
SOURCE_ID = "us-vi-property-tax-capture-cama"
PLATFORM_FAMILY = "ering_capture_cama_webforms"
JURISDICTION_ID = "78"
STATE_CODE = "VI"
STATE_FIPS = "78"
AUTHORITY_URL = "https://ltg.gov.vi/departments/office-of-tax-assesment/"
BASE_URL = "https://propertytax.vi.gov/CAMA/CAPortal/"
SEARCH_URL = urljoin(BASE_URL, "Custom/CZ_RealPropertySearch54.aspx")
INFO_URL = urljoin(BASE_URL, "CZ_RealPropertyInfo.aspx")
FAILOVER_BASE_URL = "https://usvi.capturecama.com/CAMA/CAPortal/"
OFFICIAL_HOST = "propertytax.vi.gov"
FAILOVER_HOST = "usvi.capturecama.com"
NATIVE_PAGE_SIZE = 200
NATIVE_PAGE_SIZES = (10, 50, 200)
CURSOR_PREFIX = "usvi-capture-cama:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 60.0
DEFAULT_MINIMUM_INTERVAL = 0.2
PROBE_PARCEL_NUMBER = "1-09801-0101-00"
PROBE_TAX_YEAR = "2026"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

_GUID_RE = re.compile(r"SessionGUID=([0-9a-fA-F-]{36})")
_DETAIL_RE = re.compile(r"GoToInfoPage\(['\"](?P<parcel_id>[^'\"]+)['\"]\)")
_LEGEND_RE = re.compile(
    r"^\s*(?P<parcel>.+?)\s*,\s*(?P<tax_year>\d{4})\s*$"
)
_TOTAL_RE = re.compile(r"(?P<count>\d[\d,]*)\s+Records?\s+Found", re.I)
_POSTBACK_RE = re.compile(
    r"__doPostBack\(['\"](?P<target>[^'\"]+)['\"],"
    r"['\"](?P<argument>[^'\"]+)['\"]\)"
)
_ARTIFACT_ONCLICK_RE = re.compile(
    r"OnOpenWindow\(\s*['\"][^'\"]+['\"]\s*,\s*"
    r"['\"](?P<path>[^'\"]+)['\"]\s*,\s*"
    r"['\"](?P<selectors>[^'\"]+)['\"]"
)


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="USVI Office of the Tax Assessor Capture CAMA Portal",
    source_role=(
        "territory_parcel_assessment_property_tax_statements_and_payments"
    ),
    base_url=SEARCH_URL,
    dataset_id="usvi-capture-cama",
    metadata={
        "authority": "USVI Office of the Lieutenant Governor",
        "authority_url": AUTHORITY_URL,
        "operator": "E-Ring, Inc.",
        "platform_family": PLATFORM_FAMILY,
        "authentication": "none",
        "observed_at": OBSERVED_AT,
        "native_search_fields": ["owner", "parcel", "address", "legal"],
        "native_page_sizes": list(NATIVE_PAGE_SIZES),
        "alternate_tenant_host": FAILOVER_HOST,
        "alternate_tenant_role": "same_source_failover_not_corroboration",
        "observation_identity": ["formatted_parcel_number", "tax_year"],
        "source_internal_locator": "ParcelId",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=JURISDICTION_ID,
    name="United States Virgin Islands",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS, "scope": "territory"},
)
SOURCE_WARNINGS = (
    "Published owner, mailing, value, balance, sale, statement, and payment "
    "fields are assessor/tax observations rather than recorded-title evidence.",
    "ParcelId is a tax-year-specific portal locator. Durable observation "
    "identity combines the formatted parcel number and tax year.",
    "The usvi.capturecama.com alias is the same Capture CAMA tenant and is "
    "failover redundancy, not independent corroboration.",
)

SOURCE_CAPABILITIES: Mapping[str, Any] = {
    "record_kind": "source_capabilities",
    "source_id": SOURCE_ID,
    "platform_family": PLATFORM_FAMILY,
    "observed_at": OBSERVED_AT,
    "routes": [
        {
            "role": "owner_parcel_address_legal_search",
            "method": "POST",
            "url": SEARCH_URL,
            "transport": "aspnet_webforms",
            "native_pagination": {
                "control": "GridView1",
                "page_arguments": [
                    "Page$First",
                    "Page$Prev",
                    "Page$Next",
                    "Page$Last",
                ],
                "verified_page_transition": True,
            },
        },
        {
            "role": "parcel_detail_shell",
            "method": "GET",
            "path": "/CAMA/CAPortal/CZ_RealPropertyInfo.aspx",
            "selector": "tax_year_specific_ParcelId",
        },
        {
            "role": "parcel_components",
            "method": "GET",
            "components": [
                "valuation",
                "land",
                "buildings",
                "sales",
                "photographs",
                "maps",
                "property_card",
            ],
        },
        {
            "role": "bill_and_receipt_print_views",
            "method": "GET",
            "path": "/CAMA/CAPortal/CZ_ReceiptPrint.aspx",
            "representation": "printable_html",
        },
    ],
    "official_field_matched_complements": [
        {
            "authority": "USVI Office of the Tax Collector",
            "fields": [
                "tax_status",
                "tax_clearance",
                "delinquency",
                "payment_plan",
            ],
            "url": "https://ltg.gov.vi/departments/office-of-tax-collector/",
        },
        {
            "authority": "USVI Recorder of Deeds",
            "fields": [
                "recorded_instrument",
                "grantor",
                "grantee",
                "recording_date",
                "legal_description",
            ],
            "url": "https://ltg.gov.vi/departments/recorder-of-deeds/",
        },
    ],
}


class USVICAMAError(RuntimeError):
    """Base adapter error with result semantics."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "usvi_cama_error",
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


class USVICAMASourceChanged(USVICAMAError):
    """The live source no longer matches its verified contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "usvi_cama_source_changed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class USVICAMAPaginationError(USVICAMASourceChanged):
    """A native pager did not advance or contradicted its count."""

    def __init__(self, message: str, *, details: Mapping[str, Any]) -> None:
        super().__init__(
            message,
            code="usvi_cama_pagination_stalled",
            details=details,
        )


class USVICAMASelectionError(USVICAMAError):
    """An exact parcel or child artifact selector is absent or ambiguous."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "usvi_cama_selection_error",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.NO_RESULTS,
            category="selection",
            details=details,
        )


@dataclass(frozen=True)
class SearchContract:
    tax_years: tuple[str, ...]
    selected_tax_year: str
    page_sizes: tuple[int, ...]
    session_guid: str


@dataclass(frozen=True)
class SearchFetch:
    records: tuple[dict[str, Any], ...]
    total_count: int
    tax_year: str
    native_pages_fetched: int
    first_page_html: str


def _collapse(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def _normalize_parcel(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    return {
        str(control["name"]): str(control.get("value", ""))
        for control in soup.select("input[type=hidden][name]")
    }


def _selected_option(soup: BeautifulSoup, selector: str) -> str | None:
    control = soup.select_one(selector)
    if not isinstance(control, Tag):
        return None
    selected = control.select_one("option[selected]") or control.select_one(
        "option"
    )
    if not isinstance(selected, Tag):
        return None
    return _collapse(str(selected.get("value") or selected.get_text()))


def parse_search_contract(html: str) -> SearchContract:
    soup = BeautifulSoup(html, "html.parser")
    tax_years = tuple(
        _collapse(str(option.get("value") or option.get_text()))
        for option in soup.select("#TaxYear option")
        if _collapse(str(option.get("value") or option.get_text()))
    )
    page_sizes = tuple(
        int(value)
        for option in soup.select("#RecordsDDL option")
        if (value := _collapse(str(option.get("value") or option.get_text())))
        and value.isdigit()
    )
    selected_tax_year = _selected_option(soup, "#TaxYear")
    guid_match = _GUID_RE.search(html)
    required_controls = {
        "NameSearchText",
        "ParcelSearchText",
        "AddressSearchText",
        "LegalSearchText",
        "RecordsDDL",
        "TaxYear",
    }
    actual_controls = {
        str(control.get("name"))
        for control in soup.select("[name]")
        if control.get("name")
    }
    missing = sorted(required_controls - actual_controls)
    if (
        missing
        or not tax_years
        or not page_sizes
        or selected_tax_year is None
        or guid_match is None
    ):
        raise USVICAMASourceChanged(
            "USVI Capture CAMA search contract changed",
            details={
                "missing_controls": missing,
                "tax_years": list(tax_years),
                "page_sizes": list(page_sizes),
                "has_session_guid": guid_match is not None,
            },
        )
    return SearchContract(
        tax_years=tax_years,
        selected_tax_year=selected_tax_year,
        page_sizes=page_sizes,
        session_guid=guid_match.group(1),
    )


def _cell_lines(cell: Tag) -> list[str]:
    return [
        value
        for text in cell.stripped_strings
        if (value := _collapse(str(text)))
    ]


def _published_field_rows(table: Tag) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.find_all("tr", recursive=False)):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        for label_index, label_cell in enumerate(cells[:-1]):
            labels = _cell_lines(label_cell)
            if not labels or not all(
                label.endswith(":")
                or re.fullmatch(r"DUE IN \d{4}:", label, re.I)
                for label in labels
            ):
                continue
            values = _cell_lines(cells[label_index + 1])
            for offset, label in enumerate(labels):
                if len(labels) == 1:
                    value = " ".join(values)
                else:
                    value = values[offset] if offset < len(values) else ""
                fields.append(
                    {
                        "label": label.rstrip(":").strip(),
                        "value": value,
                        "row": row_index,
                        "label_column": label_index,
                        "value_column": label_index + 1,
                    }
                )
    return fields


def _field_lookup(
    published_fields: Sequence[Mapping[str, Any]],
    prefix: str,
) -> str | None:
    normalized = prefix.upper()
    for field in published_fields:
        label = _collapse(str(field.get("label", ""))).upper()
        if label == normalized or label.startswith(normalized):
            value = _collapse(str(field.get("value", "")))
            if value.startswith("$"):
                amount = re.match(r"^\$[\d,]+(?:\.\d{2})?", value)
                if amount is not None:
                    value = amount.group(0)
            return value or None
    return None


def _observation_native_id(parcel_number: str, tax_year: str) -> str:
    return f"{parcel_number}|tax-year:{tax_year}"


def _child_ref(record_kind: str, native_id: str) -> str:
    return canonical_property_ref(
        SOURCE_ID,
        JURISDICTION_ID,
        record_kind,
        native_id,
    )


def parse_search_row(row: Tag) -> dict[str, Any]:
    legend = row.select_one("legend")
    detail_control = row.select_one("[onclick*='GoToInfoPage']")
    detail_match = (
        _DETAIL_RE.search(str(detail_control.get("onclick", "")))
        if isinstance(detail_control, Tag)
        else None
    )
    legend_text = _collapse(legend.get_text(" ", strip=True) if legend else "")
    legend_match = _LEGEND_RE.match(legend_text)
    table = row.select_one("fieldset > table")
    if (
        legend_match is None
        or detail_match is None
        or not isinstance(table, Tag)
    ):
        raise USVICAMASourceChanged(
            "USVI Capture CAMA result row changed",
            details={
                "row_id": row.get("id"),
                "legend": legend_text,
                "has_detail_locator": detail_match is not None,
            },
        )

    parcel_number = _collapse(legend_match.group("parcel"))
    tax_year = legend_match.group("tax_year")
    parcel_id = detail_match.group("parcel_id")
    fields = _published_field_rows(table)
    published_rows = [
        [_collapse(cell.get_text(" ", strip=True)) for cell in tr.find_all("td", recursive=False)]
        for tr in table.find_all("tr", recursive=False)
    ]
    native_id = _observation_native_id(parcel_number, tax_year)
    return {
        "record_kind": "parcel_assessment_tax_observation",
        "source_id": SOURCE_ID,
        "canonical_ref": _child_ref(
            "parcel_assessment_tax_observation",
            native_id,
        ),
        "observation_identity": {
            "formatted_parcel_number": parcel_number,
            "tax_year": tax_year,
            "native_id": native_id,
        },
        "formatted_parcel_number": parcel_number,
        "tax_year": tax_year,
        "source_internal_parcel_id": parcel_id,
        "source_internal_parcel_id_role": "tax_year_specific_detail_locator",
        "current_published_observation": {
            "owner_name": _field_lookup(fields, "OWNER NAME"),
            "mailing_address": _field_lookup(fields, "MAIL ADDRESS"),
            "property_address": _field_lookup(fields, "PROP ADDRESS"),
            "legal_description": _field_lookup(fields, "LEGAL"),
            "land_value": _field_lookup(fields, "LAND VALUE"),
            "improvement_value": _field_lookup(fields, "IMP VALUE"),
            "total_value": _field_lookup(fields, "TOTAL VALUE"),
            "assessed_value": _field_lookup(fields, "ASSD VALUE"),
            "exemption": _field_lookup(fields, "EXEMPTION"),
            "current_year_due": _field_lookup(fields, "DUE IN"),
            "total_due": _field_lookup(fields, "TOTAL DUE"),
            "property_class": _field_lookup(fields, "CLASS"),
            "municipality": _field_lookup(fields, "MUNICIPALITY"),
            "millage_code": _field_lookup(fields, "MILLAGE CODE"),
        },
        "published_fields": fields,
        "published_rows": published_rows,
        "evidence_domain": "assessment_and_property_tax",
        "recorded_title_evidence": False,
        "independent_corroboration": False,
    }


def parse_search_page(
    html: str,
) -> tuple[list[dict[str, Any]], int, bool, str]:
    soup = BeautifulSoup(html, "html.parser")
    total_node = soup.select_one("#TotalRecFound")
    if not isinstance(total_node, Tag):
        raise USVICAMASourceChanged(
            "USVI Capture CAMA result count is missing"
        )
    total_text = _collapse(total_node.get_text(" ", strip=True))
    total_match = _TOTAL_RE.search(total_text)
    rows = [
        parse_search_row(row)
        for row in soup.select("#GridView1 > tr[id^='GridView1_RowId_']")
        if isinstance(row, Tag)
    ]
    if total_match is None:
        if total_text.lower() == "no records found" and not rows:
            return [], 0, False, ""
        raise USVICAMASourceChanged(
            "USVI Capture CAMA returned an unrecognized result state",
            details={"result_label": total_text, "row_count": len(rows)},
        )
    total_count = int(total_match.group("count").replace(",", ""))
    next_argument = ""
    for link in soup.select("#GridView1 a[href*='__doPostBack']"):
        match = _POSTBACK_RE.search(str(link.get("href", "")))
        if (
            match is not None
            and match.group("target") == "GridView1"
            and match.group("argument") == "Page$Next"
        ):
            next_argument = match.group("argument")
            break
    return rows, total_count, bool(next_argument), next_argument


def _search_query_payload(
    *,
    soup: BeautifulSoup,
    field: str,
    term: str,
    tax_year: str,
    event_target: str,
    event_argument: str = "",
) -> dict[str, str]:
    controls = {
        "owner": "NameSearchText",
        "parcel": "ParcelSearchText",
        "address": "AddressSearchText",
        "legal": "LegalSearchText",
    }
    if field not in controls:
        raise ValueError(f"unsupported search field: {field}")
    payload = _hidden_fields(soup)
    payload.update(
        {
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": event_argument,
            "__LASTFOCUS": "",
            "NameSearchText": "",
            "ParcelSearchText": "",
            "AddressSearchText": "",
            "LegalSearchText": "",
            "RecordsDDL": str(NATIVE_PAGE_SIZE),
            "TaxYear": tax_year,
        }
    )
    payload[controls[field]] = term
    return payload


def _query_binding(field: str, term: str, tax_year: str) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "field": field,
            "term": term,
            "tax_year": tax_year,
            "native_page_size": NATIVE_PAGE_SIZE,
        }
    )


def _encode_cursor(*, binding: str, offset: int, total_count: int) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "binding": binding,
        "offset": offset,
        "total_count": total_count,
    }
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode()).decode()
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(
    cursor: str | None,
    *,
    binding: str,
    total_count: int,
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise USVICAMAError(
            "USVI Capture CAMA cursor has the wrong source prefix",
            code="invalid_cursor",
            category="query",
        )
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise USVICAMAError(
            "USVI Capture CAMA cursor is malformed",
            code="invalid_cursor",
            category="query",
        ) from exc
    if (
        payload.get("version") != CURSOR_VERSION
        or payload.get("binding") != binding
        or payload.get("total_count") != total_count
    ):
        raise USVICAMAError(
            "USVI Capture CAMA cursor belongs to a different query snapshot",
            code="cursor_mismatch",
            category="query",
        )
    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise USVICAMAError(
            "USVI Capture CAMA cursor offset is invalid",
            code="invalid_cursor",
            category="query",
        )
    return offset


class CaptureCAMAClient:
    """Verified HTTP transport for one E-Ring/Capture CAMA tenant."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        request_budget: int | None = None,
    ) -> None:
        self._owns_session = session is None
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.request_count = 0
        self.request_budget = request_budget
        self.current_session_guid: str | None = None
        self.session.headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        self.session.headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> CaptureCAMAClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> requests.Response:
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise USVICAMAError(
                    "USVI Capture CAMA request budget exhausted",
                    code="request_budget_exhausted",
                    category="monitor",
                    details={"request_budget": self.request_budget},
                )
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    data=data,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                time.sleep(self.retry_policy.delay(attempt))
                continue
            host = (urlparse(response.url).hostname or "").lower()
            if host != OFFICIAL_HOST:
                raise USVICAMASourceChanged(
                    "USVI Capture CAMA redirected outside the official host",
                    code="unexpected_final_host",
                    details={"requested_url": url, "final_url": response.url},
                )
            if response.status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    time.sleep(self.retry_policy.delay(attempt))
                    continue
            if response.status_code != 200:
                raise USVICAMAError(
                    f"USVI Capture CAMA returned HTTP {response.status_code}",
                    code="http_status",
                    category="http",
                    retryable=response.status_code >= 500,
                    details={
                        "status_code": response.status_code,
                        "url": response.url,
                    },
                )
            return response
        raise USVICAMAError(
            "USVI Capture CAMA request failed",
            code="transport_error",
            category="transport",
            retryable=True,
            details={"url": url, "error": str(last_error or "")},
        )

    def get_html(self, url: str) -> str:
        response = self._request("GET", url)
        media_type = response.headers.get("content-type", "").split(";", 1)[0]
        if media_type.lower() not in {"text/html", "application/xhtml+xml"}:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA returned non-HTML content",
                code="unexpected_media_type",
                details={"url": response.url, "content_type": media_type},
            )
        if b"<html" not in response.content[:4096].lower():
            raise USVICAMASourceChanged(
                "USVI Capture CAMA HTML signature is missing",
                code="invalid_html_signature",
                details={"url": response.url},
            )
        return response.text

    def post_html(self, url: str, data: Mapping[str, str]) -> str:
        response = self._request("POST", url, data=data)
        media_type = response.headers.get("content-type", "").split(";", 1)[0]
        if media_type.lower() not in {"text/html", "application/xhtml+xml"}:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA postback returned non-HTML content",
                code="unexpected_media_type",
                details={"url": response.url, "content_type": media_type},
            )
        return response.text

    def fetch_search(
        self,
        *,
        field: str,
        term: str,
        tax_year: str | None,
    ) -> SearchFetch:
        clean_term = _collapse(term)
        if not clean_term:
            raise ValueError("search term cannot be blank")
        landing_html = self.get_html(SEARCH_URL)
        contract = parse_search_contract(landing_html)
        selected_year = tax_year or contract.selected_tax_year
        if selected_year not in contract.tax_years:
            raise USVICAMAError(
                f"tax year {selected_year} is not published by the portal",
                code="unsupported_tax_year",
                category="query",
                details={"available_tax_years": list(contract.tax_years)},
            )
        if NATIVE_PAGE_SIZE not in contract.page_sizes:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA no longer publishes the verified page size",
                details={
                    "expected_page_size": NATIVE_PAGE_SIZE,
                    "page_sizes": list(contract.page_sizes),
                },
            )

        soup = BeautifulSoup(landing_html, "html.parser")
        payload = _search_query_payload(
            soup=soup,
            field=field,
            term=clean_term,
            tax_year=selected_year,
            event_target="",
        )
        payload["Search"] = "Search"
        first_html = self.post_html(SEARCH_URL, payload)
        first_guid = _GUID_RE.search(first_html)
        if first_guid is None:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA result page lost its session GUID"
            )
        self.current_session_guid = first_guid.group(1)
        records, total_count, has_next, next_argument = parse_search_page(
            first_html
        )
        all_records = list(records)
        pages = 1
        seen_page_signatures = {
            tuple(
                str(record["source_internal_parcel_id"])
                for record in records
            )
        }
        current_html = first_html
        while has_next:
            current_soup = BeautifulSoup(current_html, "html.parser")
            next_payload = _search_query_payload(
                soup=current_soup,
                field=field,
                term=clean_term,
                tax_year=selected_year,
                event_target="GridView1",
                event_argument=next_argument,
            )
            next_html = self.post_html(SEARCH_URL, next_payload)
            next_records, next_total, has_next, next_argument = (
                parse_search_page(next_html)
            )
            signature = tuple(
                str(record["source_internal_parcel_id"])
                for record in next_records
            )
            if next_total != total_count or not signature or signature in seen_page_signatures:
                raise USVICAMAPaginationError(
                    "USVI Capture CAMA native pager did not advance cleanly",
                    details={
                        "page": pages + 1,
                        "expected_total": total_count,
                        "observed_total": next_total,
                        "page_record_count": len(next_records),
                        "repeated_page": signature in seen_page_signatures,
                    },
                )
            seen_page_signatures.add(signature)
            all_records.extend(next_records)
            pages += 1
            current_html = next_html

        unique_ids = {
            str(record["source_internal_parcel_id"]) for record in all_records
        }
        if len(unique_ids) != len(all_records) or len(all_records) != total_count:
            raise USVICAMAPaginationError(
                "USVI Capture CAMA exhaustive result count is inconsistent",
                details={
                    "published_total": total_count,
                    "rows_fetched": len(all_records),
                    "unique_internal_locators": len(unique_ids),
                    "native_pages_fetched": pages,
                },
            )
        return SearchFetch(
            records=tuple(all_records),
            total_count=total_count,
            tax_year=selected_year,
            native_pages_fetched=pages,
            first_page_html=first_html,
        )

    def fetch_print_artifact(self, url: str) -> requests.Response:
        response = self._request("GET", url)
        media_type = response.headers.get("content-type", "").split(";", 1)[0]
        if media_type.lower() not in {"text/html", "application/xhtml+xml"}:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA print artifact changed media type",
                code="unexpected_artifact_media_type",
                details={"url": response.url, "content_type": media_type},
            )
        soup = BeautifulSoup(response.content, "html.parser")
        title = _collapse(soup.title.get_text(" ", strip=True) if soup.title else "")
        if title not in {"Receipt", "PRC Print"}:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA print artifact signature changed",
                code="invalid_artifact_signature",
                details={"url": response.url, "title": title},
            )
        return response


def _slice_results(
    fetch: SearchFetch,
    *,
    field: str,
    term: str,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    binding = _query_binding(field, term, fetch.tax_year)
    offset = _decode_cursor(
        cursor,
        binding=binding,
        total_count=fetch.total_count,
    )
    if offset > fetch.total_count:
        raise USVICAMAError(
            "USVI Capture CAMA cursor starts beyond the result set",
            code="invalid_cursor",
            category="query",
        )
    if limit is None:
        return list(fetch.records[offset:]), None
    end = min(offset + limit, fetch.total_count)
    next_cursor = (
        _encode_cursor(
            binding=binding,
            offset=end,
            total_count=fetch.total_count,
        )
        if end < fetch.total_count
        else None
    )
    return list(fetch.records[offset:end]), next_cursor


def _make_query(
    *,
    operation: str,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _error_result(
    query: PublicRecordsQuery,
    error: USVICAMAError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
) -> PublicRecordsResult:
    status = ResultStatus.PARTIAL if records else error.status
    return PublicRecordsResult(
        query=query,
        status=status,
        records=records,
        warnings=SOURCE_WARNINGS,
        errors=(
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            ),
        ),
    )


def run_search(
    client: CaptureCAMAClient,
    *,
    field: str,
    term: str,
    tax_year: str | None,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    initial_query = _make_query(
        operation="search",
        parameters={"field": field, "term": term, "tax_year": tax_year},
        limit=limit,
        cursor=cursor,
    )
    try:
        fetch = client.fetch_search(field=field, term=term, tax_year=tax_year)
        records, next_cursor = _slice_results(
            fetch,
            field=field,
            term=_collapse(term),
            limit=limit,
            cursor=cursor,
        )
        query = _make_query(
            operation="search",
            parameters={
                "field": field,
                "term": _collapse(term),
                "tax_year": fetch.tax_year,
                "native_page_size": NATIVE_PAGE_SIZE,
                "native_pages_fetched": fetch.native_pages_fetched,
                "published_total": fetch.total_count,
                "window_applied_after_exhaustion": limit is not None,
            },
            limit=limit,
            cursor=cursor,
        )
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except USVICAMAError as exc:
        return _error_result(initial_query, exc)
    except ValueError as exc:
        return _error_result(
            initial_query,
            USVICAMAError(
                str(exc),
                code="invalid_query",
                category="query",
            ),
        )


def _resolve_exact_parcel(
    client: CaptureCAMAClient,
    parcel_number: str,
    tax_year: str | None,
) -> tuple[dict[str, Any], SearchFetch]:
    fetch = client.fetch_search(
        field="parcel",
        term=parcel_number,
        tax_year=tax_year,
    )
    requested = _normalize_parcel(parcel_number)
    exact = [
        record
        for record in fetch.records
        if _normalize_parcel(str(record["formatted_parcel_number"]))
        == requested
    ]
    if len(exact) != 1:
        raise USVICAMASelectionError(
            "USVI Capture CAMA exact parcel selection is absent or ambiguous",
            code="parcel_not_unique",
            details={
                "requested_parcel": parcel_number,
                "tax_year": fetch.tax_year,
                "exact_match_count": len(exact),
                "search_result_count": fetch.total_count,
            },
        )
    return exact[0], fetch


def _same_host_url(base: str, path: str) -> str:
    url = urljoin(base, path.replace("&amp;", "&"))
    if (urlparse(url).hostname or "").lower() != OFFICIAL_HOST:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA component route leaves the official host",
            code="unexpected_component_host",
            details={"base": base, "path": path, "resolved_url": url},
        )
    return url


def _parse_detail_shell(html: str, *, expected_parcel_id: str) -> dict[str, str]:
    if "FILE NOT FOUND" in html.upper():
        raise USVICAMASourceChanged(
            "USVI Capture CAMA detail locator returned FILE NOT FOUND",
            code="detail_locator_rejected",
            details={"source_internal_parcel_id": expected_parcel_id},
        )
    soup = BeautifulSoup(html, "html.parser")
    frames = {
        str(frame.get("id")): str(frame.get("src"))
        for frame in soup.select("iframe[id][src]")
    }
    if not {"Iframe1", "Iframe2"}.issubset(frames):
        raise USVICAMASourceChanged(
            "USVI Capture CAMA detail frames changed",
            details={"frames": frames},
        )
    if f"ParcelId={expected_parcel_id}" not in frames["Iframe1"]:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA valuation frame points to another parcel",
            details={
                "expected_parcel_id": expected_parcel_id,
                "valuation_frame": frames["Iframe1"],
            },
        )
    return frames


def _table_rows(table: Tag) -> list[list[str]]:
    return [
        [
            _collapse(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        for row in table.find_all("tr", recursive=False)
        if row.find_all(["th", "td"], recursive=False)
    ]


def _parse_component_tables(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    tables: list[dict[str, Any]] = []
    for index, table in enumerate(soup.select("table")):
        rows = _table_rows(table)
        if not rows:
            continue
        tables.append(
            {
                "table_id": table.get("id"),
                "table_index": index,
                "rows": rows,
            }
        )
    return tables


def _artifact_selector(link: Tag) -> dict[str, Any] | None:
    onclick = str(link.get("onclick", ""))
    match = _ARTIFACT_ONCLICK_RE.search(onclick)
    if match is None:
        return None
    path = match.group("path")
    first, _, rest = match.group("selectors").partition("&")
    return {
        "route_path": path,
        "item1": first,
        "parameters": dict(parse_qsl(rest, keep_blank_values=True)),
        "published_selector_string": match.group("selectors"),
        "session_guid_persisted": False,
    }


def _grid_records(
    soup: BeautifulSoup,
    table_id: str,
) -> list[dict[str, Any]]:
    table = soup.select_one(f"#{table_id}")
    if not isinstance(table, Tag):
        return []
    rows = table.find_all("tr", recursive=False)
    if not rows:
        return []
    headers = [
        _collapse(cell.get_text(" ", strip=True))
        for cell in rows[0].find_all(["th", "td"], recursive=False)
    ]
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"], recursive=False)
        values = [_collapse(cell.get_text(" ", strip=True)) for cell in cells]
        if not any(values):
            continue
        published = {
            headers[index] if index < len(headers) and headers[index] else f"column_{index}": value
            for index, value in enumerate(values)
        }
        selectors = [
            selector
            for link in row.select("a[onclick]")
            if (selector := _artifact_selector(link)) is not None
        ]
        records.append(
            {
                "published_fields": published,
                "published_cells": values,
                "artifact_selectors": selectors,
            }
        )
    return records


def parse_valuation_component(
    html: str,
    *,
    parcel_number: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("#GridView3") is None or soup.select_one("#GridView1") is None:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA valuation grids changed"
        )
    statements = _grid_records(soup, "GridView3")
    valuations = _grid_records(soup, "GridView1")
    payments = _grid_records(soup, "GridView2")

    for row in statements:
        fields = row["published_fields"]
        year = _collapse(str(fields.get("Year", "")))
        statement = _collapse(str(fields.get("Statement", "")))
        native = (
            f"{parcel_number}|tax-year:{year}|statement:{statement}"
        )
        row.update(
            {
                "record_kind": "property_tax_statement",
                "canonical_ref": _child_ref("property_tax_statement", native),
                "statement_identity": {
                    "formatted_parcel_number": parcel_number,
                    "tax_year": year,
                    "statement_number": statement,
                },
            }
        )
        for selector in row["artifact_selectors"]:
            selector["record_kind"] = "property_tax_bill_print_view"
            selector["canonical_ref"] = _child_ref(
                "property_tax_bill_print_view",
                native,
            )

    for row in valuations:
        fields = row["published_fields"]
        year = _collapse(str(fields.get("Year", "")))
        native = f"{parcel_number}|valuation-year:{year}"
        row.update(
            {
                "record_kind": "assessment_valuation_history",
                "canonical_ref": _child_ref(
                    "assessment_valuation_history",
                    native,
                ),
                "recorded_title_evidence": False,
            }
        )

    for row in payments:
        fields = row["published_fields"]
        transaction_id = _collapse(str(fields.get("Transaction Id", "")))
        native = f"{parcel_number}|payment-transaction:{transaction_id}"
        row.update(
            {
                "record_kind": "property_tax_payment_transaction",
                "canonical_ref": _child_ref(
                    "property_tax_payment_transaction",
                    native,
                ),
                "payment_identity": {
                    "formatted_parcel_number": parcel_number,
                    "transaction_id": transaction_id,
                    "invoice_number": fields.get("Invoice Num"),
                    "record_year": fields.get("Record Year"),
                },
            }
        )
        for selector in row["artifact_selectors"]:
            selector["record_kind"] = "property_tax_payment_receipt"
            selector["canonical_ref"] = _child_ref(
                "property_tax_payment_receipt",
                native,
            )

    return {
        "record_kind": "parcel_valuation_tax_history_component",
        "statements": statements,
        "valuation_history": valuations,
        "payment_transactions": payments,
        "published_tables": _parse_component_tables(html),
        "published_text": _collapse(soup.get_text(" ", strip=True)),
    }


def _script_locator(
    html: str,
    name: str,
) -> str | None:
    pattern = re.compile(
        rf"{re.escape(name)}=(?:[\"']?\s*\+\s*[\"'])?"
        r"(?P<value>[A-Za-z0-9-]+)"
    )
    match = pattern.search(html)
    return match.group("value") if match is not None else None


def _parse_navigation(
    html: str,
    *,
    parcel_number: str,
    tax_year: str,
    parcel_id: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = _collapse(soup.get_text(" ", strip=True))
    if parcel_number not in text or tax_year not in text:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA navigation does not match the selected parcel",
            details={"parcel_number": parcel_number, "tax_year": tax_year},
        )
    guid_match = _GUID_RE.search(html)
    source_parcel_no = _script_locator(html, "ParcelNo") or _script_locator(
        html, "ParcelNum"
    )
    source_record_year = _script_locator(html, "RecordYear") or tax_year
    source_parcel_id = parcel_id or _script_locator(html, "ParcelId")
    if (
        guid_match is None
        or source_parcel_no is None
        or source_parcel_id is None
    ):
        raise USVICAMASourceChanged(
            "USVI Capture CAMA navigation locators changed",
            details={
                "has_session_guid": guid_match is not None,
                "has_parcel_number": source_parcel_no is not None,
                "has_parcel_id": source_parcel_id is not None,
            },
        )
    guid = guid_match.group(1)
    routes: dict[str, str] = {
        "valuation": (
            "CZ_RealPropertyValuation.aspx?"
            + urlencode(
                {"SessionGUID": guid, "ParcelId": source_parcel_id}
            )
        )
    }
    if "CZ_RealPropertyLand.aspx" in html:
        land_id = _script_locator(html, "LandId")
        if land_id is None:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA land locator changed"
            )
        routes["land"] = "CZ_RealPropertyLand.aspx?" + urlencode(
            {
                "SessionGUID": guid,
                "LandId": land_id,
                "ParcelNum": source_parcel_no,
                "RecordYear": source_record_year,
            }
        )
    if "CZ_RealPropertyBuilding.aspx" in html:
        building_id = _script_locator(html, "BuildingId")
        if building_id is None:
            raise USVICAMASourceChanged(
                "USVI Capture CAMA building locator changed"
            )
        routes["buildings"] = "CZ_RealPropertyBuilding.aspx?" + urlencode(
            {
                "SessionGUID": guid,
                "ParcelNum": source_parcel_no,
                "BuildingId": building_id,
                "RecordYear": source_record_year,
            }
        )
    if "CZ_RealPropertySales.aspx" in html:
        routes["sales"] = "CZ_RealPropertySales.aspx?" + urlencode(
            {
                "SessionGUID": guid,
                "ParcelNum": source_parcel_no,
                "RecordYear": source_record_year,
            }
        )
    if "CZ_RealPropertyPhotographs.aspx" in html:
        routes["photographs"] = (
            "CZ_RealPropertyPhotographs.aspx?"
            + urlencode(
                {
                    "SessionGUID": guid,
                    "ParcelNum": source_parcel_no,
                    "RecordYear": source_record_year,
                    "Sketch": "1",
                    "ParcelId": source_parcel_id,
                }
            )
        )
    if "CZ_RealPropertyMap.aspx" in html:
        routes["maps"] = "CZ_RealPropertyMap.aspx?" + urlencode(
            {
                "SessionGUID": guid,
                "RefId1": source_parcel_id,
                "RefType1": "PARCEL",
                "RefId2": "0",
                "RefType2": "",
                "HighlightId": source_parcel_id,
                "MapDispHeight": "650",
            }
        )
    if "CZ_RealPropertyPRCPrint.aspx" in html:
        routes["property_card"] = (
            "../CZ_RealPropertyPRCPrint.aspx?"
            + urlencode(
                {
                    "SessionGUID": guid,
                    "Item1": source_parcel_id,
                    "Item3": "0",
                }
            )
        )
    if "valuation" not in routes:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA valuation route is missing"
        )
    return {
        "published_text": text,
        "published_tables": _parse_component_tables(html),
        "component_routes": routes,
    }


def fetch_parcel_detail(
    client: CaptureCAMAClient,
    *,
    parcel_number: str,
    tax_year: str | None,
    component_names: Sequence[str] = (
        "valuation",
        "land",
        "buildings",
        "sales",
    ),
) -> dict[str, Any]:
    observation, fetch = _resolve_exact_parcel(client, parcel_number, tax_year)
    parcel_id = str(observation["source_internal_parcel_id"])
    guid_match = _GUID_RE.search(fetch.first_page_html)
    if guid_match is None:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA result page lost its session GUID"
        )
    guid = guid_match.group(1)
    info_url = INFO_URL + "?" + urlencode(
        {
            "SessionGUID": guid,
            "FromInvoice": "0",
            "Item1": parcel_id,
        }
    )
    shell_html = client.get_html(info_url)
    frames = _parse_detail_shell(shell_html, expected_parcel_id=parcel_id)
    navigation_url = _same_host_url(BASE_URL, frames["Iframe2"])
    navigation_html = client.get_html(navigation_url)
    navigation = _parse_navigation(
        navigation_html,
        parcel_number=str(observation["formatted_parcel_number"]),
        tax_year=str(observation["tax_year"]),
        parcel_id=parcel_id,
    )

    components: dict[str, Any] = {}
    for name in component_names:
        if name not in {"valuation", "land", "buildings", "sales"}:
            raise ValueError(f"unsupported parcel component: {name}")
        path = navigation["component_routes"].get(name)
        if not path:
            continue
        component_url = _same_host_url(BASE_URL, path)
        component_html = client.get_html(component_url)
        if name == "valuation":
            components[name] = parse_valuation_component(
                component_html,
                parcel_number=str(observation["formatted_parcel_number"]),
            )
        else:
            component_soup = BeautifulSoup(component_html, "html.parser")
            components[name] = {
                "record_kind": f"parcel_{name}_component",
                "published_tables": _parse_component_tables(component_html),
                "published_text": _collapse(
                    component_soup.get_text(" ", strip=True)
                ),
                "recorded_title_evidence": False,
            }

    public_routes = {
        name: {
            "path": re.sub(r"([?&])SessionGUID=[^&]*&?", r"\1", path)
            .replace("?&", "?")
            .rstrip("?&"),
            "session_guid_persisted": False,
        }
        for name, path in navigation["component_routes"].items()
    }
    return {
        **observation,
        "record_kind": "parcel_assessment_tax_detail",
        "canonical_ref": _child_ref(
            "parcel_assessment_tax_detail",
            _observation_native_id(
                str(observation["formatted_parcel_number"]),
                str(observation["tax_year"]),
            ),
        ),
        "search_observation": observation,
        "navigation": {
            "published_text": navigation["published_text"],
            "published_tables": navigation["published_tables"],
            "component_routes": public_routes,
        },
        "components": components,
        "source_internal_parcel_id": parcel_id,
        "source_internal_parcel_id_role": "tax_year_specific_detail_locator",
        "recorded_title_evidence": False,
        "independent_corroboration": False,
    }


def run_parcel(
    client: CaptureCAMAClient,
    *,
    parcel_number: str,
    tax_year: str | None,
) -> PublicRecordsResult:
    query = _make_query(
        operation="parcel",
        parameters={"parcel_number": parcel_number, "tax_year": tax_year},
    )
    try:
        record = fetch_parcel_detail(
            client,
            parcel_number=parcel_number,
            tax_year=tax_year,
        )
        actual_year = record["tax_year"]
        query = _make_query(
            operation="parcel",
            parameters={
                "parcel_number": parcel_number,
                "tax_year": actual_year,
            },
        )
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    except USVICAMAError as exc:
        return _error_result(query, exc)


def _selector_url(
    *,
    selector: Mapping[str, Any],
    session_guid: str,
) -> str:
    published_path = str(selector["route_path"])
    route_name = urlparse(published_path).path.rsplit("/", 1)[-1]
    if route_name != "CZ_ReceiptPrint.aspx":
        raise USVICAMASourceChanged(
            "USVI Capture CAMA print-view route changed",
            details={"published_path": published_path},
        )
    route = _same_host_url(BASE_URL, route_name)
    parameters = {
        "SessionGUID": session_guid,
        "Item1": str(selector["item1"]),
        **{
            str(key): str(value)
            for key, value in dict(selector["parameters"]).items()
        },
    }
    return route + "?" + urlencode(parameters)


def _find_artifact_selector(
    detail: Mapping[str, Any],
    *,
    kind: str,
    statement: str | None,
    transaction_id: str | None,
) -> tuple[Mapping[str, Any], str]:
    valuation = dict(detail["components"]).get("valuation")
    if not isinstance(valuation, Mapping):
        raise USVICAMASelectionError(
            "USVI Capture CAMA valuation component is unavailable"
        )
    if kind == "bill":
        candidates = [
            row
            for row in valuation.get("statements", [])
            if statement is None
            or str(row["statement_identity"]["statement_number"]) == statement
        ]
        selector_kind = "property_tax_bill_print_view"
    elif kind == "receipt":
        candidates = [
            row
            for row in valuation.get("payment_transactions", [])
            if transaction_id is None
            or str(row["payment_identity"]["transaction_id"])
            == transaction_id
        ]
        selector_kind = "property_tax_payment_receipt"
    else:
        raise ValueError(f"unsupported artifact kind: {kind}")
    selectors = [
        selector
        for row in candidates
        for selector in row.get("artifact_selectors", [])
        if selector.get("record_kind") == selector_kind
    ]
    if len(selectors) != 1:
        raise USVICAMASelectionError(
            "USVI Capture CAMA artifact selection is absent or ambiguous",
            code="artifact_not_unique",
            details={
                "kind": kind,
                "statement": statement,
                "transaction_id": transaction_id,
                "selector_count": len(selectors),
            },
        )
    return selectors[0], str(selectors[0]["canonical_ref"])


def fetch_artifact(
    client: CaptureCAMAClient,
    *,
    parcel_number: str,
    tax_year: str | None,
    kind: str,
    statement: str | None,
    transaction_id: str | None,
    destination: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if destination.exists() and not overwrite:
        raise USVICAMAError(
            "artifact destination already exists; pass --overwrite to replace it",
            code="destination_exists",
            category="output",
            details={"destination": str(destination)},
        )
    detail = fetch_parcel_detail(
        client,
        parcel_number=parcel_number,
        tax_year=tax_year,
        component_names=(
            ()
            if kind == "property-card"
            else ("valuation",)
        ),
    )
    guid = client.current_session_guid
    if guid is None:
        raise USVICAMASourceChanged(
            "USVI Capture CAMA retrieval session GUID is unavailable"
        )
    if kind == "property-card":
        parcel_id = str(detail["source_internal_parcel_id"])
        url = _same_host_url(
            BASE_URL,
            "CZ_RealPropertyPRCPrint.aspx",
        ) + "?" + urlencode(
            {
                "SessionGUID": guid,
                "Item1": parcel_id,
                "Item3": "0",
            }
        )
        canonical_ref = _child_ref(
            "property_record_card_print_view",
            _observation_native_id(
                str(detail["formatted_parcel_number"]),
                str(detail["tax_year"]),
            ),
        )
    else:
        selector, canonical_ref = _find_artifact_selector(
            detail,
            kind=kind,
            statement=statement,
            transaction_id=transaction_id,
        )
        url = _selector_url(selector=selector, session_guid=guid)

    response = client.fetch_print_artifact(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return {
        "record_kind": (
            "property_record_card_print_view"
            if kind == "property-card"
            else (
                "property_tax_bill_print_view"
                if kind == "bill"
                else "property_tax_payment_receipt"
            )
        ),
        "source_id": SOURCE_ID,
        "canonical_ref": canonical_ref,
        "native_document_id": canonical_ref,
        "artifact_kind": kind,
        "formatted_parcel_number": detail["formatted_parcel_number"],
        "tax_year": detail["tax_year"],
        "statement_number": statement,
        "transaction_id": transaction_id,
        "media_type": response.headers.get("content-type", "").split(";", 1)[0],
        "html_signature_valid": True,
        "byte_length": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "destination": str(destination),
        "source_url": (
            BASE_URL
            + (
                "CZ_RealPropertyPRCPrint.aspx"
                if kind == "property-card"
                else "CZ_ReceiptPrint.aspx"
            )
        ),
        "final_host": urlparse(response.url).hostname,
        "session_guid_persisted": False,
    }


def source_record() -> dict[str, Any]:
    return {
        "record_kind": "source_description",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "capabilities": dict(SOURCE_CAPABILITIES),
        "warnings": list(SOURCE_WARNINGS),
    }


def probe_source(client: CaptureCAMAClient) -> dict[str, Any]:
    html = client.get_html(SEARCH_URL)
    contract = parse_search_contract(html)
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "available": True,
        "observed_at": OBSERVED_AT,
        "search_url": SEARCH_URL,
        "final_host": OFFICIAL_HOST,
        "tax_years": list(contract.tax_years),
        "selected_tax_year": contract.selected_tax_year,
        "native_page_sizes": list(contract.page_sizes),
        "session_guid_present": True,
        "request_count": client.request_count,
    }


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser("source")
    add_output_args(source_parser)

    probe_parser = subparsers.add_parser("probe")
    add_output_args(probe_parser)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument(
        "field",
        choices=("owner", "parcel", "address", "legal"),
    )
    search_parser.add_argument("term")
    search_parser.add_argument("--tax-year")
    search_parser.add_argument("--limit", type=_positive_int)
    search_parser.add_argument("--cursor")
    add_output_args(search_parser)

    parcel_parser = subparsers.add_parser("parcel")
    parcel_parser.add_argument("parcel_number")
    parcel_parser.add_argument("--tax-year")
    add_output_args(parcel_parser)

    artifact_parser = subparsers.add_parser("artifact")
    artifact_parser.add_argument("parcel_number")
    artifact_parser.add_argument("--tax-year")
    artifact_parser.add_argument(
        "--kind",
        choices=("bill", "receipt", "property-card"),
        required=True,
    )
    artifact_parser.add_argument("--statement")
    artifact_parser.add_argument("--transaction-id")
    artifact_parser.add_argument(
        "--destination",
        type=Path,
        required=True,
    )
    artifact_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing artifact destination",
    )
    add_output_args(artifact_parser)
    return parser


def execute(
    args: argparse.Namespace,
    *,
    client: CaptureCAMAClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source operation through the shared records contract."""

    command = str(args.command)
    if command == "search":
        query = _make_query(
            operation="search",
            parameters={
                "field": args.field,
                "term": args.term,
                "tax_year": getattr(args, "tax_year", None),
            },
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )
    elif command == "parcel":
        query = _make_query(
            operation="parcel",
            parameters={
                "parcel_number": args.parcel_number,
                "tax_year": getattr(args, "tax_year", None),
            },
        )
    elif command == "artifact":
        query = _make_query(
            operation="artifact",
            parameters={
                "parcel_number": args.parcel_number,
                "tax_year": getattr(args, "tax_year", None),
                "kind": args.kind,
                "statement": getattr(args, "statement", None),
                "transaction_id": getattr(args, "transaction_id", None),
            },
        )
    elif command == "probe":
        query = _make_query(operation="probe", parameters={})
    else:
        query = _make_query(operation=command, parameters={})
        return _error_result(
            query,
            USVICAMAError(
                f"unsupported USVI Capture CAMA operation: {command}",
                code="operation_unsupported",
                category="query",
            ),
        )

    active_client = client or CaptureCAMAClient(
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
    )
    should_close = client is None
    try:
        if command == "search":
            result = run_search(
                active_client,
                field=args.field,
                term=args.term,
                tax_year=getattr(args, "tax_year", None),
                limit=getattr(args, "limit", None),
                cursor=getattr(args, "cursor", None),
            )
        elif command == "parcel":
            result = run_parcel(
                active_client,
                parcel_number=args.parcel_number,
                tax_year=getattr(args, "tax_year", None),
            )
        elif command == "probe":
            result = PublicRecordsResult.success(
                query,
                [probe_source(active_client)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            kind = str(args.kind)
            statement = getattr(args, "statement", None)
            transaction_id = getattr(args, "transaction_id", None)
            if kind == "bill" and not statement:
                raise USVICAMASelectionError(
                    "bill retrieval requires a statement number",
                    code="statement_required",
                    category="query",
                )
            if kind == "receipt" and not transaction_id:
                raise USVICAMASelectionError(
                    "receipt retrieval requires a transaction ID",
                    code="transaction_id_required",
                    category="query",
                )
            artifact = fetch_artifact(
                active_client,
                parcel_number=args.parcel_number,
                tax_year=getattr(args, "tax_year", None),
                kind=kind,
                statement=statement,
                transaction_id=transaction_id,
                destination=Path(args.destination),
                overwrite=getattr(args, "overwrite", False),
            )
            result = PublicRecordsResult.success(
                query,
                [artifact],
                raw_artifact_refs=[artifact["destination"]],
                warnings=SOURCE_WARNINGS,
            )
    except USVICAMAError as exc:
        result = _error_result(query, exc)
    except ValueError as exc:
        result = _error_result(
            query,
            USVICAMAError(
                str(exc),
                code="invalid_query",
                category="query",
            ),
        )
    finally:
        if should_close:
            active_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(result.query, count)
    return result


def _emit(data: Mapping[str, Any], args: argparse.Namespace, summary: str) -> None:
    if write_output(data, args, summary=summary):
        return
    print(json.dumps(data, indent=2, default=str))


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "source":
        _emit(source_record(), args, "USVI Capture CAMA source")
        return 0

    client = CaptureCAMAClient(timeout=args.timeout)
    try:
        if args.command == "probe":
            result: Mapping[str, Any] = probe_source(client)
            summary = "USVI Capture CAMA probe"
        elif args.command == "search":
            result_object = run_search(
                client,
                field=args.field,
                term=args.term,
                tax_year=args.tax_year,
                limit=args.limit,
                cursor=args.cursor,
            )
            _log(result_object.query, len(result_object.records))
            result = result_object.to_dict()
            summary = "USVI Capture CAMA search"
        elif args.command == "parcel":
            result_object = run_parcel(
                client,
                parcel_number=args.parcel_number,
                tax_year=args.tax_year,
            )
            _log(result_object.query, len(result_object.records))
            result = result_object.to_dict()
            summary = "USVI Capture CAMA parcel"
        elif args.command == "artifact":
            if args.kind == "bill" and not args.statement:
                parser.error("--statement is required for --kind bill")
            if args.kind == "receipt" and not args.transaction_id:
                parser.error(
                    "--transaction-id is required for --kind receipt"
                )
            result = fetch_artifact(
                client,
                parcel_number=args.parcel_number,
                tax_year=args.tax_year,
                kind=args.kind,
                statement=args.statement,
                transaction_id=args.transaction_id,
                destination=args.destination,
                overwrite=args.overwrite,
            )
            summary = "USVI Capture CAMA artifact"
        else:
            parser.error(f"unsupported command: {args.command}")
            return 2
        _emit(result, args, summary)
        status = result.get("status")
        return 1 if status in {"unavailable", "source_changed", "partial"} else 0
    except (USVICAMAError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
