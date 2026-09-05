#!/usr/bin/env python3
"""Query Deschutes County DIAL property accounts, history, and reports.

DIAL complements the county's ArcGIS taxlot graph with account-level tax,
assessment, ownership, sale, improvement, development, and document records.
The two sources stay separate and can be joined on DIAL account ID and map /
taxlot.

Examples:
    uv run python tools/query_deschutes_dial.py search VACH --field owner \
        --output /tmp/deschutes-dial-search.json
    uv run python tools/query_deschutes_dial.py account 135278 \
        --output /tmp/deschutes-dial-account.json
    uv run python tools/query_deschutes_dial.py account 141031B000700 \
        --field taxlot --components summary,tax,sales
    uv run python tools/query_deschutes_dial.py permit 135278 \
        247-16-000505-SEP --permit-type Septic
    uv run python tools/query_deschutes_dial.py download 135278 ownership \
        --destination /tmp/deschutes-ownership.pdf
    uv run python tools/query_deschutes_dial.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args
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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args
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
        sha256_fingerprint,
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-or-deschutes-dial-property"
SOURCE_NAME = "Deschutes County DIAL Property Information"
PUBLISHER = "Deschutes County"
BASE_URL = "http://dial.deschutes.org"
TAX_STORE_BASE_URL = "https://store.deschutes.org"
COUNTY_GEOID = "41017"
STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_NAME = "Deschutes County, Oregon"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
PROBE_ACCOUNT = "135278"
PROBE_TAXLOT = "141031B000700"
CURSOR_PREFIX = "deschutes-dial:v1:"
CURSOR_VERSION = 1

SEARCH_FIELDS = (
    "general",
    "owner",
    "account",
    "taxlot",
    "situs",
    "subdivision",
    "mobile-park",
)
SEARCH_PATHS = {
    "general": "/results/general",
    "owner": "/results/ownername",
    "account": "/results/account",
    "taxlot": "/results/taxlot",
    "situs": "/results/situs",
    "subdivision": "/results/subdivision",
    "mobile-park": "/results/mobileparkname",
}
SEARCH_COLUMNS = (
    "rank",
    "map_taxlot",
    "account_id",
    "owner_name",
    "situs_address",
    "city",
    "subdivision",
    "property_type",
    "agent_name",
    "block",
    "direction",
    "house_number",
    "lot",
    "mobile_park_name",
    "manufactured_structure_id",
    "state",
    "street_name",
    "street_type",
    "unit",
    "zip",
)
PROPERTY_TYPE_PATHS = {
    "real": "/Real/Index/{account_id}",
    "r": "/Real/Index/{account_id}",
    "utility": "/Utility/Index/{account_id}",
    "u": "/Utility/Index/{account_id}",
    "mfd structure": "/Manufactured/Index/{account_id}",
    "m": "/Manufactured/Index/{account_id}",
    "personal": "/Personal/Index/{account_id}",
    "p": "/Personal/Index/{account_id}",
    "cancelled": "/Cancelled/Index/{account_id}",
    "c": "/Cancelled/Index/{account_id}",
    "inactive": "/Inactive/Index/{account_id}",
    "i": "/Inactive/Index/{account_id}",
}


@dataclass(frozen=True)
class ComponentConfig:
    key: str
    path: str
    parser: Callable[[str, str], Mapping[str, Any]]
    linked_system: str | None = None


@dataclass(frozen=True)
class HTMLPage:
    html: str
    url: str


@dataclass(frozen=True)
class DownloadedPDF:
    content: bytes
    source_url: str
    media_type: str
    filename: str | None
    job_id: str | None = None


@dataclass(frozen=True)
class SearchPage:
    rows: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    authoritative_empty: bool = False
    direct_summary: Mapping[str, Any] | None = None


class DialSelectionError(ValueError):
    """A selector, component, or continuation does not match the source."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="selection",
            details=self.details,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    return text or None


def _slug(value: str | None) -> str:
    text = _clean(value) or ""
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def _source_label(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    return _clean(re.sub(r"\s+\d{5,}\s*$", "", text))


def _label_slug(value: Any) -> str:
    return _slug(_source_label(value))


def _money(value: Any) -> int | float | None:
    text = _clean(value)
    if text is None:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if negative:
        number = -abs(number)
    return int(number) if number.is_integer() else number


def _number(value: Any) -> int | float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _source_date(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for source_format in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, source_format).date().isoformat()
        except ValueError:
            continue
    return None


def _safe_url(
    value: str,
    *,
    base: str = BASE_URL,
    allowed_hosts: Sequence[str] = ("dial.deschutes.org", "store.deschutes.org"),
) -> str:
    parsed = urlparse(urljoin(base, value))
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise SourceSchemaError(
            "Deschutes source response left a verified county host",
            url=base,
            details={"observed_host": host or None},
        )
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _linked_url(value: str, *, base: str) -> str | None:
    parsed = urlparse(urljoin(base, value))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _text_after_strong(node: Tag) -> str | None:
    parts: list[str] = []
    for sibling in node.next_siblings:
        if isinstance(sibling, Tag) and sibling.name == "strong":
            break
        if isinstance(sibling, Tag) and sibling.name == "br":
            if parts:
                break
            continue
        if isinstance(sibling, NavigableString):
            text = _clean(sibling)
        elif isinstance(sibling, Tag):
            text = _clean(sibling)
        else:
            text = None
        if text:
            parts.append(text)
    return _clean(" ".join(parts))


def _strong_fields(container: Tag | None) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    if container is None:
        return fields
    for node in container.find_all("strong"):
        direct_text = " ".join(
            str(child) for child in node.children if isinstance(child, NavigableString)
        )
        label = _clean(direct_text) or _source_label(node)
        if label is None:
            continue
        label = re.sub(r"\s*:\s*$", "", label)
        if not label or node.find("a") is not None:
            continue
        fields[_label_slug(label)] = _text_after_strong(node)
    return fields


def _table_matrix(table: Tag) -> tuple[list[str], list[list[str | None]]]:
    rows = table.find_all("tr")
    headers: list[str] = []
    values: list[list[str | None]] = []
    for row in rows:
        direct_cells = row.find_all(["th", "td"], recursive=False)
        if not direct_cells:
            direct_cells = row.find_all(["th", "td"])
        if not direct_cells:
            continue
        if all(cell.name == "th" for cell in direct_cells) and not headers:
            headers = [_source_label(cell) or "" for cell in direct_cells]
            continue
        if any(cell.name == "td" for cell in direct_cells):
            values.append([_clean(cell) for cell in direct_cells])
    return headers, values


def _find_table(
    soup: BeautifulSoup,
    expected_headers: Sequence[str],
    *,
    table_id: str | None = None,
    source_url: str,
) -> tuple[Tag, list[str], list[list[str | None]]]:
    candidates: Sequence[Tag]
    if table_id is not None:
        selected = soup.find("table", id=table_id)
        candidates = [selected] if isinstance(selected, Tag) else []
    else:
        candidates = soup.find_all("table")
    expected = [_label_slug(value) for value in expected_headers]
    for table in candidates:
        headers, rows = _table_matrix(table)
        if [_label_slug(value) for value in headers[: len(expected)]] == expected:
            return table, headers, rows
    raise SourceSchemaError(
        "Deschutes DIAL table schema changed",
        url=source_url,
        details={"expected_headers": list(expected_headers), "table_id": table_id},
    )


def _table_records(
    headers: Sequence[str],
    rows: Sequence[Sequence[str | None]],
) -> list[dict[str, Any]]:
    keys = [
        _label_slug(header) or f"column_{index + 1}"
        for index, header in enumerate(headers)
    ]
    records = []
    for values in rows:
        if not any(value for value in values):
            continue
        record = {
            key: values[index] if index < len(values) else None
            for index, key in enumerate(keys)
        }
        if len(values) > len(keys):
            record["extra_values"] = list(values[len(keys) :])
        records.append(record)
    return records


def _document_link(
    anchor: Tag,
    *,
    source_url: str,
    account_id: str | None,
) -> dict[str, Any] | None:
    href = anchor.get("href")
    if not isinstance(href, str):
        return None
    absolute = _linked_url(href, base=source_url)
    if absolute is None:
        return None
    parsed = urlparse(absolute)
    host = (parsed.hostname or "").casefold()
    query = parse_qs(parsed.query)
    label = _clean(anchor)
    document: dict[str, Any] | None = None
    if host == "dial.deschutes.org" and "/api/real/getreport" in (
        parsed.path.casefold()
    ):
        report = (query.get("report") or [None])[0]
        if report is None:
            return None
        report_kinds = {
            "taxmap": "tax_map",
            "names": "ownership",
            "taxsummary": "current_balance",
            "taxstatement": "tax_statement",
            "improvement": "improvement",
            "ledger": "current_ledger",
            "historicalledger": "historic_ledger",
            "historicledger": "historic_ledger",
        }
        native_id_parts = [
            account_id or "",
            report,
            (query.get("year") or [""])[0],
            (query.get("ImpID") or [""])[0],
            (query.get("asOfDate") or [""])[0],
        ]
        document = {
            "document_kind": report_kinds.get(
                report.casefold(),
                _slug(report),
            ),
            "native_document_id": ":".join(native_id_parts),
            "source_url": absolute,
            "label": label,
            "artifact_format": "pdf",
            "retrieval_state": "link_available",
            "source_system": "deschutes_dial",
        }
    elif host == "recordings.deschutes.org" and "documentimage" in (
        parsed.path.casefold()
    ):
        year = (query.get("year") or [None])[0]
        item_id = (query.get("itemId") or [None])[0]
        document = {
            "document_kind": "recording_image_reference",
            "native_document_id": f"{year or ''}:{item_id or ''}",
            "source_url": absolute,
            "label": label,
            "recording_year": year,
            "recording_item_id": item_id,
            "retrieval_state": "external_viewer_link",
            "source_system": "deschutes_digital_research_room",
        }
    elif host == "weblink.deschutes.org" and parsed.path.casefold().endswith(
        "/docview.aspx"
    ):
        document_id = (query.get("id") or [None])[0]
        document = {
            "document_kind": "development_document_reference",
            "native_document_id": document_id,
            "source_url": absolute,
            "label": label,
            "retrieval_state": "external_viewer_link",
            "source_system": "deschutes_cdd_weblink",
        }
    if document is None:
        return None
    native_id = _clean(document.get("native_document_id")) or sha256_fingerprint(
        {"source_url": absolute}
    )
    document["canonical_ref"] = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "document",
        native_id,
    )
    document["evidence_ref"] = document["canonical_ref"]
    return document


def _document_links(
    soup: BeautifulSoup,
    *,
    source_url: str,
    account_id: str | None,
) -> list[dict[str, Any]]:
    documents = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        document = _document_link(
            anchor,
            source_url=source_url,
            account_id=account_id,
        )
        if document is None or document["source_url"] in seen:
            continue
        seen.add(str(document["source_url"]))
        documents.append(document)
    return documents


def _account_information(
    soup: BeautifulSoup,
    *,
    source_url: str,
    require_real: bool = True,
) -> dict[str, Any]:
    container = soup.select_one(".uxAccountInformation")
    if not isinstance(container, Tag):
        raise SourceSchemaError(
            "Deschutes DIAL account information is missing",
            url=source_url,
        )
    fields = _strong_fields(container)
    account_id = _clean(fields.get("account"))
    taxlot = _clean(fields.get("map_and_taxlot"))
    if account_id is None or (require_real and taxlot is None):
        raise SourceSchemaError(
            "Deschutes DIAL account identity changed",
            url=source_url,
            details={"observed_labels": sorted(fields)},
        )
    return {
        "mailing_name": _clean(fields.get("mailing_name")),
        "map_taxlot": taxlot,
        "account_id": account_id,
        "situs_address": _clean(fields.get("situs_address")),
        "tax_status": _clean(fields.get("tax_status")),
        "source_fields": fields,
    }


def parse_summary_page(html: str, source_url: str) -> Mapping[str, Any]:
    """Parse the source-native account summary and current value snapshot."""
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    account_id = str(account["account_id"])
    results = soup.select_one("#results-data")
    if not isinstance(results, Tag):
        raise SourceSchemaError(
            "Deschutes DIAL summary content is missing",
            url=source_url,
        )
    mailing_lines: list[str] = []
    mailing_label = results.find(
        "strong", string=lambda value: bool(value and "Mailing To" in value)
    )
    if isinstance(mailing_label, Tag) and isinstance(mailing_label.parent, Tag):
        strings = [
            _clean(value)
            for value in mailing_label.parent.stripped_strings
            if _clean(value)
        ]
        try:
            start = next(
                index
                for index, value in enumerate(strings)
                if value and value.startswith("Mailing To")
            )
        except StopIteration:
            start = len(strings)
        mailing_lines = [
            value
            for value in strings[start + 1 :]
            if value
            and value
            not in {
                "Change of Mailing Address Form",
                "View Overview Map",
            }
        ]
    tax_code_match = re.search(
        r"Tax Code Area:\s*([A-Za-z0-9-]+)",
        results.get_text(" ", strip=True),
        re.I,
    )
    middle = soup.select_one("#uxReportMiddleColumn")
    middle_fields = _strong_fields(middle if isinstance(middle, Tag) else None)
    acres = _number(middle_fields.get("assessor_acres"))
    property_class = _clean(middle_fields.get("property_class"))
    recorder_link = next(
        (
            anchor
            for anchor in results.find_all("a", href=True)
            if "recordings.deschutes.org" in str(anchor.get("href"))
            and "DocumentImage" in str(anchor.get("href"))
        ),
        None,
    )
    description = _clean(recorder_link) if isinstance(recorder_link, Tag) else None
    right = soup.select_one("#uxReportRightColumn")
    value_tables = right.find_all("table") if isinstance(right, Tag) else []
    value_rows: dict[str, int | float | None] = {}
    for table in value_tables:
        _headers, rows = _table_matrix(table)
        for row in rows:
            if len(row) >= 2 and row[0]:
                value_rows[_label_slug(row[0])] = _money(row[1])
    right_text = _clean(right) or ""
    as_of_match = re.search(
        r"As of\s+Jan\.?\s*1,\s*(\d{4})",
        right_text,
        re.I,
    )
    tax_year_match = re.search(r"(\d{4})\s*-\s*(\d{4})\s+Tax Year", right_text)
    return {
        **account,
        "mailing_address_lines": mailing_lines,
        "tax_code_area": tax_code_match.group(1) if tax_code_match else None,
        "assessor_description": description,
        "assessor_acres": acres,
        "property_class": property_class,
        "value_as_of_year": int(as_of_match.group(1)) if as_of_match else None,
        "tax_year": (
            f"{tax_year_match.group(1)}-{tax_year_match.group(2)}"
            if tax_year_match
            else None
        ),
        "assessment": {
            "land_value": value_rows.get("land"),
            "improvement_value": value_rows.get("structures"),
            "parcel_value": value_rows.get("total"),
            "maximum_assessed_value": value_rows.get("maximum_assessed"),
            "assessed_value": value_rows.get("assessed_value"),
            "veterans_exemption": value_rows.get("veterans_exemption"),
        },
        "documents": _document_links(
            soup,
            source_url=source_url,
            account_id=account_id,
        ),
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "summary",
                "account_labels": sorted(account["source_fields"]),
                "value_labels": sorted(value_rows),
                "has_tax_code_area": tax_code_match is not None,
            }
        ),
    }


def parse_valuation_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    _table, headers, rows = _find_table(
        soup,
        ("",),
        source_url=source_url,
    )
    if len(headers) < 2 or not all(re.search(r"\d{4}", value) for value in headers[1:]):
        raise SourceSchemaError(
            "Deschutes DIAL valuation-year columns changed",
            url=source_url,
            details={"headers": headers},
        )
    by_label = {_label_slug(row[0]): row[1:] for row in rows if row and row[0]}
    required = {
        "real_market_value_land",
        "real_market_value_structures",
        "total_real_market_value",
        "maximum_assessed_value",
        "total_assessed_value",
    }
    if not required.issubset(by_label):
        raise SourceSchemaError(
            "Deschutes DIAL valuation rows changed",
            url=source_url,
            details={"observed_labels": sorted(by_label)},
        )
    history = []
    for index, header in enumerate(headers[1:]):
        year_match = re.findall(r"\d{4}", header)
        tax_year = "-".join(year_match[:2]) if year_match else _clean(header)
        history.append(
            {
                "tax_year": tax_year,
                "land_value": _money(by_label["real_market_value_land"][index]),
                "improvement_value": _money(
                    by_label["real_market_value_structures"][index]
                ),
                "parcel_value": _money(by_label["total_real_market_value"][index]),
                "maximum_assessed_value": _money(
                    by_label["maximum_assessed_value"][index]
                ),
                "assessed_value": _money(by_label["total_assessed_value"][index]),
                "veterans_exemption": _money(
                    (by_label.get("veterans_exemption") or [None] * (len(headers) - 1))[
                        index
                    ]
                ),
            }
        )
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "assessment_history": history,
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "valuation",
                "tax_year_columns": len(headers) - 1,
                "row_labels": sorted(by_label),
            }
        ),
    }


def parse_tax_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    account_id = str(account["account_id"])
    original_headers: list[str] = []
    original_rows: list[list[str | None]] = []
    for candidate in soup.find_all("table"):
        candidate_headers, candidate_rows = _table_matrix(candidate)
        if candidate_headers and all(
            re.fullmatch(r"Tax Year \d{4}", header) for header in candidate_headers
        ):
            original_headers = candidate_headers
            original_rows = candidate_rows
            break
    if not original_headers:
        raise SourceSchemaError(
            "Deschutes DIAL original-tax table changed",
            url=source_url,
        )
    tax_years = []
    for index, header in enumerate(original_headers):
        match = re.search(r"(\d{4})", header)
        if match and original_rows:
            tax_years.append(
                {
                    "tax_year": match.group(1),
                    "original_tax_amount": _money(original_rows[0][index]),
                }
            )
    _payment_table, payment_headers, payment_rows = _find_table(
        soup,
        (
            "Year",
            "Date Due",
            "Transaction Type",
            "Transaction Date",
            "As Of Date",
            "Amount Received",
            "Tax Due",
            "Discount Amount",
            "Interest Charged",
            "Refund Interest",
        ),
        table_id="uxTaxPaymentHistory",
        source_url=source_url,
    )
    payment_history = []
    for row in payment_rows:
        if len(row) < 10 or _slug(row[0]) == "total":
            continue
        payment_history.append(
            {
                "tax_year": _clean(row[0]),
                "date_due": _source_date(row[1]),
                "date_due_raw": _clean(row[1]),
                "transaction_type": _clean(row[2]),
                "transaction_date": _source_date(row[3]),
                "transaction_date_raw": _clean(row[3]),
                "as_of_date": _source_date(row[4]),
                "as_of_date_raw": _clean(row[4]),
                "amount_received": _money(row[5]),
                "tax_due_delta": _money(row[6]),
                "discount_amount": _money(row[7]),
                "interest_charged": _money(row[8]),
                "refund_interest": _money(row[9]),
                "source_row_fingerprint": sha256_fingerprint(list(row)),
            }
        )
    page_text = soup.get_text(" ", strip=True)
    tax_code_match = re.search(
        r"Tax Code Area:\s*([A-Za-z0-9-]+)",
        page_text,
        re.I,
    )
    statement_note = next(
        (
            _clean(paragraph)
            for paragraph in soup.find_all("p")
            if "certified property tax" in ((_clean(paragraph) or "").casefold())
        ),
        None,
    )
    return {
        "account_id": account_id,
        "map_taxlot": account["map_taxlot"],
        "tax_code_area": tax_code_match.group(1) if tax_code_match else None,
        "original_tax_amounts": tax_years,
        "payment_history": payment_history,
        "statement_scope_note": statement_note,
        "future_balance_report_parameters": {
            "report": "TaxSummary",
            "type": "R",
            "id": account_id,
            "as_of_date_format": "MM/DD/YYYY",
        },
        "documents": _document_links(
            soup,
            source_url=source_url,
            account_id=account_id,
        ),
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "tax",
                "original_tax_columns": len(original_headers),
                "payment_headers": payment_headers,
            }
        ),
    }


def parse_sales_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    _table, headers, rows = _find_table(
        soup,
        ("Sale Date", "Seller", "Buyer", "Sale Amount", "Recording Instrument"),
        source_url=source_url,
    )
    sales = []
    for row in rows:
        if len(row) < 5:
            continue
        instrument = _clean(row[4])
        sale_date = _source_date(row[0])
        native_id = instrument or sha256_fingerprint(list(row))[:20]
        sales.append(
            {
                "native_sale_id": native_id,
                "sale_date": sale_date,
                "sale_date_raw": _clean(row[0]),
                "seller": _clean(row[1]),
                "buyer": _clean(row[2]),
                "consideration": _money(row[3]),
                "sale_amount_raw": _clean(row[3]),
                "source_document_ref": instrument,
            }
        )
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "sale_history": sales,
        "recorder_search_url": next(
            (
                _linked_url(str(anchor.get("href")), base=source_url)
                for anchor in soup.find_all("a", href=True)
                if "DigitalResearchRoomPublic" in str(anchor.get("href"))
            ),
            None,
        ),
        "schema_fingerprint": schema_fingerprint(
            {"component": "sales", "headers": headers}
        ),
    }


def parse_improvements_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    account_id = str(account["account_id"])
    structures_table, structure_headers, structure_rows = _find_table(
        soup,
        ("Description", "Stat Class", "Year Built", "SQFT", ""),
        source_url=source_url,
    )
    _land_table, land_headers, land_rows = _find_table(
        soup,
        ("Land Description", "Acres", "Land Classification"),
        source_url=source_url,
    )
    structures = []
    structure_row_tags = [
        row for row in structures_table.find_all("tr") if row.find("td") is not None
    ]
    for index, row in enumerate(structure_rows):
        if len(row) < 4:
            continue
        report_anchor = (
            structure_row_tags[index].find("a", href=True)
            if index < len(structure_row_tags)
            else None
        )
        report_url = (
            _linked_url(str(report_anchor.get("href")), base=source_url)
            if isinstance(report_anchor, Tag)
            else None
        )
        improvement_id = None
        if report_url:
            improvement_id = (
                parse_qs(urlparse(report_url).query).get("ImpID") or [None]
            )[0]
        structures.append(
            {
                "native_improvement_id": improvement_id,
                "description": _clean(row[0]),
                "stat_class": _clean(row[1]),
                "year_built": _number(row[2]),
                "square_feet": _number(row[3]),
                "report_url": report_url,
            }
        )
    land = [
        {
            "description": _clean(row[0]),
            "acres": _number(row[1]),
            "land_classification": _clean(row[2]),
        }
        for row in land_rows
        if len(row) >= 3
    ]
    return {
        "account_id": account_id,
        "map_taxlot": account["map_taxlot"],
        "structures": structures,
        "land_characteristics": land,
        "documents": _document_links(
            soup,
            source_url=source_url,
            account_id=account_id,
        ),
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "improvements",
                "structure_headers": structure_headers,
                "land_headers": land_headers,
            }
        ),
    }


def parse_special_assessments_page(
    html: str,
    source_url: str,
) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    _table, headers, rows = _find_table(
        soup,
        ("Description", "Amount", "Year"),
        source_url=source_url,
    )
    assessments = [
        {
            "description": _clean(row[0]),
            "amount": _money(row[1]),
            "year": _clean(row[2]),
        }
        for row in rows
        if len(row) >= 3
    ]
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "special_assessments": assessments,
        "schema_fingerprint": schema_fingerprint(
            {"component": "special_assessments", "headers": headers}
        ),
    }


def parse_taxlot_history_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    account_id = str(account["account_id"])
    documents = _document_links(
        soup,
        source_url=source_url,
        account_id=account_id,
    )
    resource_links = []
    for anchor in soup.find_all("a", href=True):
        absolute = _linked_url(str(anchor.get("href")), base=source_url)
        if absolute is None:
            continue
        if any(item["source_url"] == absolute for item in documents):
            continue
        label = _clean(anchor)
        if label and ("index" in label.casefold() or "research" in label.casefold()):
            resource_links.append({"label": label, "source_url": absolute})
    if not documents:
        raise SourceSchemaError(
            "Deschutes DIAL taxlot-history report links are missing",
            url=source_url,
        )
    return {
        "account_id": account_id,
        "map_taxlot": account["map_taxlot"],
        "documents": documents,
        "additional_research_resources": resource_links,
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "taxlot_history",
                "document_kinds": sorted(
                    str(document["document_kind"]) for document in documents
                ),
            }
        ),
    }


def parse_related_accounts_page(
    html: str,
    source_url: str,
) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    explicit_empty = "No related accounts." in soup.get_text(" ", strip=True)
    related_accounts: list[dict[str, Any]] = []
    headers: list[str] = []
    if not explicit_empty:
        table, headers, rows = _find_table(
            soup,
            ("Account", "Description", "Owner"),
            source_url=source_url,
        )
        data_rows = table.find_all("tr")
        row_tags = [row for row in data_rows if row.find("td") is not None]
        for index, row in enumerate(rows):
            if len(row) < 3:
                continue
            link = (
                row_tags[index].find("a", href=True) if index < len(row_tags) else None
            )
            related_accounts.append(
                {
                    "account_id": _clean(row[0]),
                    "description": _clean(row[1]),
                    "owner": _clean(row[2]),
                    "source_url": (
                        _linked_url(str(link.get("href")), base=source_url)
                        if isinstance(link, Tag)
                        else None
                    ),
                }
            )
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "related_accounts": related_accounts,
        "authoritative_empty": explicit_empty,
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "related_accounts",
                "headers": headers or ["Account", "Description", "Owner"],
                "empty_marker": explicit_empty,
            }
        ),
    }


def parse_warnings_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    notations: list[dict[str, Any]] = []
    headers: list[str] = []
    try:
        _table, headers, rows = _find_table(
            soup,
            ("Type", "Description"),
            source_url=source_url,
        )
    except SourceSchemaError:
        rows = []
    for row in rows:
        if len(row) >= 2:
            notations.append(
                {
                    "type": _clean(row[0]),
                    "description": _clean(row[1]),
                }
            )
    warnings_heading = next(
        (
            node
            for node in soup.select(".uxReportSectionHeader")
            if _clean(node) == "Warnings/Notations"
        ),
        None,
    )
    narrative = None
    if isinstance(warnings_heading, Tag):
        paragraph = warnings_heading.find_next_sibling("p")
        narrative = _clean(paragraph)
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "development_notations": notations,
        "warnings_narrative": narrative,
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "warnings",
                "headers": headers,
                "has_narrative": narrative is not None,
            }
        ),
    }


def parse_service_providers_page(
    html: str,
    source_url: str,
) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    table, headers, rows = _find_table(
        soup,
        (
            "Service",
            "Service Provider",
            "Phone",
            "Address",
            "City/State",
            "Zip",
        ),
        table_id="reportTable",
        source_url=source_url,
    )
    row_tags = [row for row in table.find_all("tr") if row.find("td")]
    providers = []
    for index, row in enumerate(rows):
        if len(row) < 6:
            continue
        provider_link = (
            row_tags[index].find("a", href=True) if index < len(row_tags) else None
        )
        providers.append(
            {
                "service": _clean(row[0]),
                "provider": _clean(row[1]),
                "provider_url": (
                    _linked_url(str(provider_link.get("href")), base=source_url)
                    if isinstance(provider_link, Tag)
                    else None
                ),
                "phone": _clean(row[2]),
                "address": _clean(row[3]),
                "city_state": _clean(row[4]),
                "zip": _clean(row[5]),
            }
        )
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "service_providers": providers,
        "schema_fingerprint": schema_fingerprint(
            {"component": "service_providers", "headers": headers}
        ),
    }


def parse_development_summary_page(
    html: str,
    source_url: str,
) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    account_id = str(account["account_id"])
    results = soup.select_one("#results-data")
    if not isinstance(results, Tag):
        raise SourceSchemaError(
            "Deschutes DIAL development summary content is missing",
            url=source_url,
        )
    all_fields: dict[str, str | None] = {}
    for container_id in ("uxReportMiddleColumn", "uxReportRightColumn"):
        for container in soup.select(f"#{container_id}"):
            all_fields.update(_strong_fields(container))
    _zoning_table, zoning_headers, zoning_rows = _find_table(
        soup,
        ("Jurisdiction", "Zone", "Description", "Link to Zoning Code"),
        source_url=source_url,
    )
    zoning = []
    zoning_row_tags = [
        row for row in _zoning_table.find_all("tr") if row.find("td") is not None
    ]
    for index, row in enumerate(zoning_rows):
        if len(row) < 4:
            continue
        link = (
            zoning_row_tags[index].find("a", href=True)
            if index < len(zoning_row_tags)
            else None
        )
        zoning.append(
            {
                "jurisdiction": _clean(row[0]),
                "zone": _clean(row[1]),
                "description": _clean(row[2]),
                "zoning_code_url": (
                    _linked_url(str(link.get("href")), base=source_url)
                    if isinstance(link, Tag)
                    else None
                ),
            }
        )
    details: dict[str, Any] = {}
    details_headers: list[str] = []
    details_heading = next(
        (
            node
            for node in soup.select(".uxReportSectionHeader")
            if _clean(node) == "County Development Details"
        ),
        None,
    )
    if isinstance(details_heading, Tag):
        details_table = details_heading.find_next("table")
        if isinstance(details_table, Tag):
            _headers, rows = _table_matrix(details_table)
            for row in rows:
                if len(row) >= 2 and row[0]:
                    key = _label_slug(row[0])
                    details_headers.append(_clean(row[0]) or key)
                    details[key] = _clean(row[1])
    return {
        "account_id": account_id,
        "map_taxlot": account["map_taxlot"],
        "subdivision": all_fields.get("subdivision"),
        "lot": all_fields.get("lot"),
        "block": all_fields.get("block"),
        "acres": _number(all_fields.get("acres")),
        "planning_jurisdiction": all_fields.get("planning_jurisdiction"),
        "urban_growth_boundary": all_fields.get("urban_growth_boundary"),
        "urban_reserve_area": all_fields.get("urban_reserve_area"),
        "zoning": zoning,
        "county_development_details": details,
        "documents": _document_links(
            soup,
            source_url=source_url,
            account_id=account_id,
        ),
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "development_summary",
                "zoning_headers": zoning_headers,
                "development_detail_labels": sorted(details_headers),
            }
        ),
    }


def parse_permits_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    table, headers, rows = _find_table(
        soup,
        ("Permit ID", "Permit Type", "Permit Name", "Application Date", "Status"),
        source_url=source_url,
    )
    row_tags = [row for row in table.find_all("tr") if row.find("td")]
    permits = []
    for index, row in enumerate(rows):
        if len(row) < 5:
            continue
        link = row_tags[index].find("a", href=True) if index < len(row_tags) else None
        permit_id = _clean(row[0])
        detail_url = (
            _linked_url(str(link.get("href")), base=source_url)
            if isinstance(link, Tag)
            else None
        )
        permits.append(
            {
                "native_permit_id": permit_id,
                "permit_type": _clean(row[1]),
                "permit_name": _clean(row[2]),
                "application_date": _source_date(row[3]),
                "application_date_raw": _clean(row[3]),
                "status": _clean(row[4]),
                "detail_url": detail_url,
                "canonical_ref": canonical_property_ref(
                    SOURCE_ID,
                    COUNTY_GEOID,
                    "permit",
                    f"{account['account_id']}:{permit_id}",
                )
                if permit_id
                else None,
            }
        )
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "permits": permits,
        "schema_fingerprint": schema_fingerprint(
            {"component": "permits", "headers": headers}
        ),
    }


def parse_development_documents_page(
    html: str,
    source_url: str,
) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    table, headers, rows = _find_table(
        soup,
        ("Date Uploaded", "Document Type", "Description", "File Number", ""),
        source_url=source_url,
    )
    row_tags = [row for row in table.find_all("tr") if row.find("td")]
    documents = []
    for index, row in enumerate(rows):
        if len(row) < 5:
            continue
        link = row_tags[index].find("a", href=True) if index < len(row_tags) else None
        document = (
            _document_link(
                link,
                source_url=source_url,
                account_id=str(account["account_id"]),
            )
            if isinstance(link, Tag)
            else None
        )
        if document is None:
            raise SourceSchemaError(
                "Deschutes DIAL development-document link changed",
                url=source_url,
                details={"row_index": index},
            )
        document.update(
            {
                "date_uploaded": _source_date(row[0]),
                "date_uploaded_raw": _clean(row[0]),
                "document_type": _clean(row[1]),
                "description": _clean(row[2]),
                "file_number": _clean(row[3]),
            }
        )
        documents.append(document)
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "development_documents": documents,
        "schema_fingerprint": schema_fingerprint(
            {"component": "development_documents", "headers": headers}
        ),
    }


def parse_tax_store_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    fields: dict[str, str | None] = {}
    for group in soup.select(".form-group"):
        label = group.find("label")
        value = group.select_one(".form-control-static")
        if isinstance(label, Tag) and isinstance(value, Tag):
            fields[_slug(_clean(label))] = _clean(value)
    account_id = _clean(fields.get("account_id"))
    if account_id is None or "tax_balance_due" not in fields:
        raise SourceSchemaError(
            "Deschutes tax-payment account fields changed",
            url=source_url,
            details={"observed_labels": sorted(fields)},
        )
    notice = _clean(soup.select_one(".alert"))
    return {
        "account_id": account_id,
        "property_owner": _clean(fields.get("property_owner")),
        "property_address": _clean(fields.get("property_address")),
        "tax_balance_due": _money(fields.get("tax_balance_due")),
        "tax_balance_due_raw": _clean(fields.get("tax_balance_due")),
        "account_notice": notice,
        "source_system": "deschutes_county_tax_payments",
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "tax_payment_store",
                "field_labels": sorted(fields),
            }
        ),
    }


def _inspection_fields(container: Tag) -> list[dict[str, Any]]:
    inspections: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for strong in container.find_all("strong"):
        label = _slug(_clean(strong))
        if label not in {"date", "initials", "comments"}:
            continue
        value = _text_after_strong(strong)
        if label == "date" and current:
            inspections.append(current)
            current = {}
        if label == "date":
            current["date"] = _source_date(value)
            current["date_raw"] = value
        else:
            current[label] = value
    if current:
        inspections.append(current)
    return inspections


def parse_permit_detail_page(html: str, source_url: str) -> Mapping[str, Any]:
    soup = _soup(html)
    account = _account_information(soup, source_url=source_url)
    common = soup.select_one("#uxPermitsCommon")
    if not isinstance(common, Tag):
        raise SourceSchemaError(
            "Deschutes DIAL permit detail fields are missing",
            url=source_url,
        )
    fields = _strong_fields(common)
    permit_id = _clean(fields.get("permit_number"))
    if permit_id is None:
        raise SourceSchemaError(
            "Deschutes DIAL permit identity changed",
            url=source_url,
        )
    detail_fields = dict(fields)
    inspections: list[dict[str, Any]] = []
    for section in soup.select(".permitsSections"):
        if section.get("id") == "uxInspections":
            inspections.extend(_inspection_fields(section))
        else:
            detail_fields.update(_strong_fields(section))
    for date_key in ("application_date", "issue_date", "final_date"):
        raw = detail_fields.get(date_key)
        detail_fields[f"{date_key}_raw"] = raw
        detail_fields[date_key] = _source_date(raw)
    return {
        "account_id": account["account_id"],
        "map_taxlot": account["map_taxlot"],
        "native_permit_id": permit_id,
        "permit_type": next(
            (
                re.sub(r"\s+Permit Details$", "", _clean(node) or "", flags=re.I)
                for node in soup.select(".uxReportSectionHeader")
                if (_clean(node) or "").endswith("Permit Details")
            ),
            None,
        ),
        "fields": detail_fields,
        "inspections": inspections,
        "schema_fingerprint": schema_fingerprint(
            {
                "component": "permit_detail",
                "field_labels": sorted(detail_fields),
                "inspection_labels": ["date", "initials", "comments"],
            }
        ),
    }


def _property_detail_url(property_type: str | None, account_id: str) -> str:
    template = PROPERTY_TYPE_PATHS.get((_clean(property_type) or "").casefold())
    if template is None:
        template = "/Search"
    return _safe_url(template.format(account_id=account_id))


def _search_row_record(
    values: Sequence[str | None],
    *,
    source_url: str,
) -> dict[str, Any]:
    if len(values) != len(SEARCH_COLUMNS):
        raise SourceSchemaError(
            "Deschutes DIAL result row width changed",
            url=source_url,
            details={
                "expected_columns": len(SEARCH_COLUMNS),
                "observed_columns": len(values),
            },
        )
    row = dict(zip(SEARCH_COLUMNS, values, strict=True))
    account_id = _clean(row["account_id"])
    if account_id is None:
        raise SourceSchemaError(
            "Deschutes DIAL search row has no account identity",
            url=source_url,
        )
    taxlot = _clean(row["map_taxlot"])
    native_id = taxlot or account_id
    owner = _clean(row["owner_name"])
    situs = _clean(row["situs_address"])
    city = _clean(row["city"])
    state = _clean(row["state"]) or STATE_CODE
    postal_code = _clean(row["zip"])
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "record_kind": "property_search_result",
        "record_view": "search_result",
        "snapshot_complete": False,
        "native_parcel_id": native_id,
        "native_account_id": account_id,
        "assessment_account_ids": [account_id],
        "map_taxlot": taxlot,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_id,
        ),
        "jurisdiction": {
            "country": "US",
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": "Deschutes",
            "county_geoid": COUNTY_GEOID,
            "county_fips": COUNTY_GEOID,
        },
        "rank": _number(row["rank"]),
        "owner_name": owner,
        "owners": [{"raw_name": owner}] if owner else [],
        "situs_address": {
            "raw_address": situs,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": "US",
        }
        if situs
        else None,
        "subdivision": _clean(row["subdivision"]),
        "property_type": _clean(row["property_type"]),
        "detail_url": _property_detail_url(row["property_type"], account_id),
        "source_columns": {key: _clean(value) for key, value in row.items()},
    }


def parse_search_page(html: str, source_url: str) -> SearchPage:
    """Parse a complete source result table, direct account, or source empty."""
    soup = _soup(html)
    no_matches = soup.select_one(".ErrorMsg")
    if isinstance(no_matches, Tag) and "returned no matches" in (
        no_matches.get_text(" ", strip=True).casefold()
    ):
        return SearchPage(
            rows=(),
            source_url=source_url,
            schema_fingerprint=schema_fingerprint(
                {
                    "component": "search",
                    "columns": list(SEARCH_COLUMNS),
                    "empty_marker": "returned no matches",
                }
            ),
            authoritative_empty=True,
        )
    results = soup.select_one("#uxResults")
    if isinstance(results, Tag):
        source_rows = []
        for row in results.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                cells = row.find_all("td")
            source_rows.append([_clean(cell) for cell in cells])
        records = tuple(
            _search_row_record(row, source_url=source_url) for row in source_rows
        )
        return SearchPage(
            rows=records,
            source_url=source_url,
            schema_fingerprint=schema_fingerprint(
                {
                    "component": "search",
                    "columns": list(SEARCH_COLUMNS),
                    "column_count": len(SEARCH_COLUMNS),
                    "pagination": "client_side_complete_html_table",
                }
            ),
        )
    if soup.select_one(".uxAccountInformation") is not None:
        summary = parse_summary_page(html, source_url)
        return SearchPage(
            rows=(),
            source_url=source_url,
            schema_fingerprint=str(summary["schema_fingerprint"]),
            direct_summary=summary,
        )
    raise SourceSchemaError(
        "Deschutes DIAL search response has no result, account, or empty marker",
        url=source_url,
    )


def _summary_search_record(
    summary: Mapping[str, Any],
    *,
    source_url: str,
) -> dict[str, Any]:
    account_id = str(summary["account_id"])
    taxlot = _clean(summary.get("map_taxlot"))
    native_id = taxlot or account_id
    owner = _clean(summary.get("mailing_name"))
    situs = _clean(summary.get("situs_address"))
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "record_kind": "property_search_result",
        "record_view": "search_result",
        "snapshot_complete": False,
        "native_parcel_id": native_id,
        "native_account_id": account_id,
        "assessment_account_ids": [account_id],
        "map_taxlot": taxlot,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_id,
        ),
        "jurisdiction": {
            "country": "US",
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": "Deschutes",
            "county_geoid": COUNTY_GEOID,
            "county_fips": COUNTY_GEOID,
        },
        "owner_name": owner,
        "owners": [{"raw_name": owner}] if owner else [],
        "situs_address": {"raw_address": situs, "country": "US"} if situs else None,
        "property_type": "Real",
        "detail_url": source_url,
    }


COMPONENTS: dict[str, ComponentConfig] = {
    "summary": ComponentConfig(
        "summary", "/Real/Index/{account_id}", parse_summary_page
    ),
    "valuation": ComponentConfig(
        "valuation",
        "/Real/Valuation/{account_id}",
        parse_valuation_page,
    ),
    "tax": ComponentConfig(
        "tax",
        "/Real/TaxInformation/{account_id}",
        parse_tax_page,
    ),
    "sales": ComponentConfig(
        "sales",
        "/Real/Sales/{account_id}",
        parse_sales_page,
    ),
    "improvements": ComponentConfig(
        "improvements",
        "/Real/Improvements/{account_id}",
        parse_improvements_page,
    ),
    "special_assessments": ComponentConfig(
        "special_assessments",
        "/Real/SpecialAssessments/{account_id}",
        parse_special_assessments_page,
    ),
    "taxlot_history": ComponentConfig(
        "taxlot_history",
        "/Real/TaxLotHistory/{account_id}",
        parse_taxlot_history_page,
    ),
    "related_accounts": ComponentConfig(
        "related_accounts",
        "/Real/RelatedAccounts/{account_id}",
        parse_related_accounts_page,
    ),
    "warnings": ComponentConfig(
        "warnings",
        "/Real/Warnings/{account_id}",
        parse_warnings_page,
    ),
    "service_providers": ComponentConfig(
        "service_providers",
        "/Real/ServiceProviders/{account_id}",
        parse_service_providers_page,
    ),
    "development_summary": ComponentConfig(
        "development_summary",
        "/Real/DevelopmentSummary/{account_id}",
        parse_development_summary_page,
    ),
    "permits": ComponentConfig(
        "permits",
        "/Real/Permits/{account_id}",
        parse_permits_page,
    ),
    "development_documents": ComponentConfig(
        "development_documents",
        "/Real/DevelopmentDocs/{account_id}",
        parse_development_documents_page,
    ),
    "tax_payment_store": ComponentConfig(
        "tax_payment_store",
        "/Taxes/home/account/{account_id}",
        parse_tax_store_page,
        linked_system="deschutes_county_tax_payments",
    ),
}
DEFAULT_COMPONENTS = tuple(COMPONENTS)

DIRECT_REPORTS = {
    "ownership": {"report": "Names", "type": "R"},
    "current-balance": {"report": "TaxSummary", "type": "R"},
    "tax-map": {"report": "TaxMap"},
    "tax-statement": {"report": "TaxStatement", "type": "R"},
    "improvement": {"report": "Improvement", "type": "R"},
    "ledger": {"report": "Ledger", "type": "R"},
    "historic-ledger": {"report": "HistoricLedger"},
    "future-balance": {"report": "TaxSummary", "type": "R"},
}
CUSTOM_REPORTS = {
    "basic-report": "basic",
    "full-report": "full",
}
REPORT_TYPES = (*DIRECT_REPORTS, *CUSTOM_REPORTS)


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _retry_after(response: Any) -> float | None:
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class DialClient:
    """Retrying, rate-limited client for DIAL and its linked tax account page."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: MinimumIntervalRateLimiter | Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or MinimumIntervalRateLimiter(
            DEFAULT_MINIMUM_INTERVAL
        )
        self.sleeper = sleeper
        self._owns_session = session is None
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            "Accept-Language": "en-US,en;q=0.8",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        allowed_statuses: Sequence[int] = (),
    ) -> Any:
        safe_url = _safe_url(url)
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    safe_url,
                    params=params,
                    data=data,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for redirect in [*getattr(response, "history", ()), response]:
                _safe_url(str(getattr(redirect, "url", safe_url)))
            status = int(getattr(response, "status_code", 0))
            if status in allowed_statuses:
                return response
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt, _retry_after(response)))
                continue
            if status == 429:
                raise RateLimitedHTTPError(status, url=safe_url)
            if status in {401, 403}:
                raise RestrictedHTTPError(status, url=safe_url)
            if status in {404, 410}:
                raise SourceChangedHTTPError(status, url=safe_url)
            if status < 200 or status >= 300:
                raise HTTPStatusError(status, url=safe_url)
            return response
        raise TransportError(
            "Deschutes DIAL request failed",
            url=safe_url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def get_html(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> HTMLPage:
        response = self._request("GET", url, params=params)
        content_type = (_response_header(response, "content-type") or "").casefold()
        if content_type and "html" not in content_type:
            raise SourceSchemaError(
                "Deschutes DIAL page returned non-HTML content",
                url=str(getattr(response, "url", url)),
                details={"content_type": content_type},
            )
        return HTMLPage(
            html=str(response.text),
            url=_safe_url(str(getattr(response, "url", url))),
        )

    def search(self, query: str, field: str) -> SearchPage:
        page = self.get_html(
            _safe_url(SEARCH_PATHS[field]),
            params={"value": query, "m": "0"},
        )
        return parse_search_page(page.html, page.url)

    def component(self, account_id: str, key: str) -> tuple[Mapping[str, Any], str]:
        config = COMPONENTS[key]
        base = TAX_STORE_BASE_URL if config.linked_system else BASE_URL
        url = _safe_url(config.path.format(account_id=account_id), base=base)
        page = self.get_html(url)
        return config.parser(page.html, page.url), page.url

    def permit_detail(
        self,
        account_id: str,
        permit_id: str,
        permit_type: str,
    ) -> tuple[Mapping[str, Any], str]:
        page = self.get_html(
            _safe_url(f"/Real/PermitDetails/{account_id}"),
            params={"permitID": permit_id, "permitType": permit_type},
        )
        return parse_permit_detail_page(page.html, page.url), page.url

    def _pdf_response(
        self,
        response: Any,
        *,
        source_url: str,
        job_id: str | None = None,
    ) -> DownloadedPDF:
        content = bytes(getattr(response, "content", b""))
        if not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "Deschutes report response is not a PDF artifact",
                url=source_url,
                details={
                    "content_type": _response_header(response, "content-type"),
                    "body_prefix_hex": content[:12].hex(),
                },
            )
        disposition = _response_header(response, "content-disposition") or ""
        filename_match = re.search(
            r"filename\*?=(?:UTF-8''|\"?)([^\";]+)",
            disposition,
            re.I,
        )
        return DownloadedPDF(
            content=content,
            source_url=_safe_url(str(getattr(response, "url", source_url))),
            media_type=(
                _response_header(response, "content-type") or "application/pdf"
            ).split(";", 1)[0],
            filename=filename_match.group(1) if filename_match else None,
            job_id=job_id,
        )

    def direct_report(
        self,
        account_id: str,
        report_type: str,
        *,
        year: str | None = None,
        code_area: str | None = None,
        improvement_id: str | None = None,
        as_of_date: str | None = None,
    ) -> DownloadedPDF:
        params = dict(DIRECT_REPORTS[report_type])
        if report_type == "current-balance":
            params["taxid"] = account_id
        elif report_type == "tax-statement":
            params.update({"year": year, "codeArea": code_area})
        elif report_type == "improvement":
            params["ImpID"] = improvement_id
        elif report_type == "future-balance":
            params.update({"id": account_id, "asOfDate": as_of_date})
        report_path = (
            "/API/Real/GetReport"
            if report_type == "future-balance"
            else f"/API/Real/GetReport/{account_id}"
        )
        url = _safe_url(report_path)
        response = self._request("GET", url, params=params)
        return self._pdf_response(
            response,
            source_url=str(getattr(response, "url", url)),
        )

    def custom_report(
        self,
        account_id: str,
        report_type: str,
        *,
        poll_attempts: int,
        poll_interval: float,
    ) -> DownloadedPDF:
        response = self._request(
            "POST",
            _safe_url("/api/real/GenerateReport"),
            data={
                "id": account_id,
                "SelectedItems": CUSTOM_REPORTS[report_type],
            },
        )
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise SourceSchemaError(
                "Deschutes custom-report job response is not JSON",
                url=str(getattr(response, "url", BASE_URL)),
            ) from error
        job_id = _clean(payload.get("Id")) if isinstance(payload, Mapping) else None
        if job_id is None or not re.fullmatch(r"[A-Za-z0-9-]{20,80}", job_id):
            raise SourceSchemaError(
                "Deschutes custom-report job identity changed",
                url=str(getattr(response, "url", BASE_URL)),
            )
        download_url = _safe_url(f"/api/real/downloadreport/{job_id}")
        for attempt in range(poll_attempts):
            if attempt:
                self.sleeper(poll_interval)
            download = self._request(
                "GET",
                download_url,
                allowed_statuses=(404, 500, 502, 503, 504),
            )
            if int(getattr(download, "status_code", 0)) in {
                404,
                500,
                502,
                503,
                504,
            }:
                continue
            return self._pdf_response(
                download,
                source_url=download_url,
                job_id=job_id,
            )
        raise TransportError(
            "Deschutes custom report was not ready within the requested poll window",
            url=download_url,
            details={"job_id": job_id, "poll_attempts": poll_attempts},
        )


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="county_property_account_detail_tax_and_development",
    base_url=BASE_URL,
    dataset_id="deschutes-dial-property-information",
    metadata={
        "publisher": PUBLISHER,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "authentication": "none",
        "native_identity_key": "account_id",
        "taxlot_join_key": "map_taxlot",
        "arcgis_complement_source_id": "us-or-deschutes-county-taxlots",
        "search_pagination": "client_side_complete_html_table",
        "linked_systems": {
            "tax_balance": TAX_STORE_BASE_URL,
            "recording_images": (
                "https://recordings.deschutes.org/DigitalResearchRoomPublic/"
            ),
            "development_documents": "https://weblink.deschutes.org/cdd/",
        },
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Deschutes County",
    metadata={"state_fips": STATE_FIPS},
)


def _build_query(
    *,
    operation: str,
    selector: str | None,
    field: str | None,
    components: Sequence[str] = (),
    report_type: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "field": field,
                "components": list(components),
                "report_type": report_type,
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "access_decision": dict(access_decision or {}),
                "component_partiality": "independent",
                "document_retrieval_states": (
                    "link_available_external_viewer_link_retrieved"
                ),
            },
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code") or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                details=dict(decision),
            )
        ],
    )


def _enforce_access_decision(
    query: PublicRecordsQuery,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult | None:
    if access_decision is None:
        return None
    decision_source = access_decision.get("source_id")
    if decision_source is not None and decision_source != SOURCE_ID:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message="Catalog decision belongs to another source component",
                    category="access",
                    details={
                        "decision_source_id": decision_source,
                        "query_source_id": SOURCE_ID,
                    },
                )
            ],
        )
    if not access_decision.get("allowed", False):
        return _access_failure(query, access_decision)
    return None


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception:
        return


def _client(
    args: argparse.Namespace,
    access_decision: Mapping[str, Any] | None,
) -> DialClient:
    limits = access_decision.get("limits") or {} if access_decision is not None else {}
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return DialClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        rate_limiter=MinimumIntervalRateLimiter(
            max(args.minimum_interval, reviewed_interval)
        ),
    )


def _query_fingerprint(query: str, field: str) -> str:
    return sha256_fingerprint({"source_id": SOURCE_ID, "query": query, "field": field})


def _row_identity(record: Mapping[str, Any]) -> str:
    return ":".join(
        [
            str(record.get("property_type") or ""),
            str(record.get("native_account_id") or ""),
            str(record.get("map_taxlot") or ""),
        ]
    )


def _search_snapshot(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_fingerprint(
        [
            {
                "identity": _row_identity(record),
                "rank": record.get("rank"),
                "owner": record.get("owner_name"),
                "situs": (
                    record.get("situs_address", {}).get("raw_address")
                    if isinstance(record.get("situs_address"), Mapping)
                    else None
                ),
            }
            for record in records
        ]
    )


def _encode_cursor(
    *,
    query_fingerprint: str,
    offset: int,
    anchor: str,
    total_count: int,
    snapshot: str,
    schema: str,
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "q": query_fingerprint,
        "o": offset,
        "a": anchor,
        "n": total_count,
        "p": snapshot,
        "s": schema,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(
    cursor: str | None,
    *,
    query_fingerprint: str,
) -> Mapping[str, Any] | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise DialSelectionError(
            "invalid_cursor",
            "cursor must be a Deschutes DIAL continuation returned by this tool",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        values = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DialSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(values, Mapping) or values.get("v") != CURSOR_VERSION:
        raise DialSelectionError(
            "invalid_cursor",
            "cursor version or payload is invalid",
        )
    if values.get("q") != query_fingerprint:
        raise DialSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different DIAL search parameters",
        )
    if (
        isinstance(values.get("o"), bool)
        or not isinstance(values.get("o"), int)
        or values["o"] <= 0
        or not isinstance(values.get("a"), str)
        or not isinstance(values.get("n"), int)
        or not isinstance(values.get("p"), str)
        or not isinstance(values.get("s"), str)
    ):
        raise DialSelectionError(
            "invalid_cursor",
            "cursor offset, anchor, count, snapshot, or schema is invalid",
        )
    return values


def _component_result(
    key: str,
    source_url: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    schema_value = _clean(data.get("schema_fingerprint"))
    if schema_value is None:
        raise SourceSchemaError(
            "Deschutes component parser returned no schema fingerprint",
            url=source_url,
            details={"component": key},
        )
    normalized = dict(data)
    normalized.pop("schema_fingerprint", None)
    list_values = [value for value in normalized.values() if isinstance(value, list)]
    status = (
        "no_results"
        if list_values and all(not value for value in list_values)
        else "ok"
    )
    return {
        "status": status,
        "source_url": source_url,
        "source_system": (COMPONENTS[key].linked_system or "deschutes_dial"),
        "schema_fingerprint": schema_value,
        "data": normalized,
    }


def _address(raw: str | None) -> dict[str, Any] | None:
    value = _clean(raw)
    if value is None:
        return None
    match = re.match(
        r"^(?P<street>.+?),\s*(?P<city>[^,]+),\s*"
        r"(?P<state>[A-Z]{2})(?:\s+(?P<zip>\d{5}(?:-\d{4})?))?$",
        value,
    )
    return {
        "raw_address": value,
        "street": _clean(match.group("street")) if match else None,
        "city": _clean(match.group("city")) if match else None,
        "state": (_clean(match.group("state")) if match else STATE_CODE),
        "postal_code": _clean(match.group("zip")) if match else None,
        "country": "US",
    }


def _mailing_address(lines: Any) -> dict[str, Any] | None:
    if not isinstance(lines, list):
        return None
    cleaned = [_clean(value) for value in lines if _clean(value)]
    if not cleaned:
        return None
    address_lines = cleaned[1:] if len(cleaned) > 1 else cleaned
    return {
        "raw_address": ", ".join(address_lines),
        "address_lines": address_lines,
        "country": "US",
    }


def _aggregate_documents(
    components: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    seen: set[str] = set()
    for component in components.values():
        data = component.get("data")
        if not isinstance(data, Mapping):
            continue
        candidates: list[Any] = []
        if isinstance(data.get("documents"), list):
            candidates.extend(data["documents"])
        if isinstance(data.get("development_documents"), list):
            candidates.extend(data["development_documents"])
        for document in candidates:
            if not isinstance(document, Mapping):
                continue
            source_url = _clean(document.get("source_url"))
            if source_url is None or source_url in seen:
                continue
            seen.add(source_url)
            documents.append(dict(document))
    return documents


def _normalize_account_record(
    components: Mapping[str, Mapping[str, Any]],
    *,
    requested_components: Sequence[str],
    component_errors: Sequence[PublicRecordsError],
) -> dict[str, Any]:
    summary_component = components["summary"]
    summary = summary_component["data"]
    account_id = str(summary["account_id"])
    taxlot = _clean(summary.get("map_taxlot"))
    native_id = taxlot or account_id
    valuation_data = (
        components.get("valuation", {}).get("data")
        if isinstance(components.get("valuation"), Mapping)
        else None
    )
    tax_data = (
        components.get("tax", {}).get("data")
        if isinstance(components.get("tax"), Mapping)
        else None
    )
    tax_store = (
        components.get("tax_payment_store", {}).get("data")
        if isinstance(components.get("tax_payment_store"), Mapping)
        else None
    )
    sales_data = (
        components.get("sales", {}).get("data")
        if isinstance(components.get("sales"), Mapping)
        else None
    )
    improvements_data = (
        components.get("improvements", {}).get("data")
        if isinstance(components.get("improvements"), Mapping)
        else None
    )
    permits_data = (
        components.get("permits", {}).get("data")
        if isinstance(components.get("permits"), Mapping)
        else None
    )
    development_documents = (
        components.get("development_documents", {}).get("data")
        if isinstance(components.get("development_documents"), Mapping)
        else None
    )
    related_data = (
        components.get("related_accounts", {}).get("data")
        if isinstance(components.get("related_accounts"), Mapping)
        else None
    )
    assessment_history = (
        list(valuation_data.get("assessment_history") or [])
        if isinstance(valuation_data, Mapping)
        else []
    )
    summary_assessment = summary.get("assessment")
    if not assessment_history and isinstance(summary_assessment, Mapping):
        assessment_history = [
            {
                "tax_year": summary.get("tax_year"),
                **dict(summary_assessment),
            }
        ]
    sales = (
        list(sales_data.get("sale_history") or [])
        if isinstance(sales_data, Mapping)
        else []
    )
    requested = set(requested_components)
    succeeded = set(components)
    empty = {
        key
        for key, component in components.items()
        if component.get("status") == "no_results"
    }
    failed = sorted(
        {
            str(error.details.get("component"))
            for error in component_errors
            if error.details.get("component")
        }
    )
    owner_name = _clean(summary.get("mailing_name"))
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": summary_component["source_url"],
        "record_kind": "property_account",
        "record_view": "full_detail",
        "snapshot_complete": (
            requested == set(DEFAULT_COMPONENTS) and not component_errors
        ),
        "native_parcel_id": native_id,
        "native_account_id": account_id,
        "assessment_account_ids": [account_id],
        "map_taxlot": taxlot,
        "alternate_parcel_ids": [account_id],
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            native_id,
        ),
        "jurisdiction": {
            "country": "US",
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": "Deschutes",
            "county_geoid": COUNTY_GEOID,
            "county_fips": COUNTY_GEOID,
        },
        "tax_year": summary.get("tax_year"),
        "tax_status": summary.get("tax_status"),
        "tax_code_area": summary.get("tax_code_area"),
        "tax_state": {
            "tax_status": summary.get("tax_status"),
            "current_balance_due": (
                tax_store.get("tax_balance_due")
                if isinstance(tax_store, Mapping)
                else None
            ),
            "current_balance_due_raw": (
                tax_store.get("tax_balance_due_raw")
                if isinstance(tax_store, Mapping)
                else None
            ),
            "balance_source_url": (
                components["tax_payment_store"]["source_url"]
                if "tax_payment_store" in components
                else None
            ),
            "original_tax_amounts": (
                tax_data.get("original_tax_amounts")
                if isinstance(tax_data, Mapping)
                else []
            ),
            "payment_history": (
                tax_data.get("payment_history") if isinstance(tax_data, Mapping) else []
            ),
        },
        "situs_address": _address(_clean(summary.get("situs_address"))),
        "mailing_address": _mailing_address(summary.get("mailing_address_lines")),
        "owners": [{"raw_name": owner_name}] if owner_name else [],
        "assessment": (
            dict(assessment_history[-1]) if assessment_history else summary_assessment
        ),
        "assessment_history": assessment_history,
        "sale_history": sales,
        "last_sale": sales[0] if sales else None,
        "assessor_description": summary.get("assessor_description"),
        "physical_characteristics": {
            "assessor_acres": summary.get("assessor_acres"),
            "property_class": summary.get("property_class"),
            "land_characteristics": (
                improvements_data.get("land_characteristics")
                if isinstance(improvements_data, Mapping)
                else []
            ),
        },
        "improvements": (
            improvements_data.get("structures")
            if isinstance(improvements_data, Mapping)
            else []
        ),
        "related_accounts": (
            related_data.get("related_accounts")
            if isinstance(related_data, Mapping)
            else []
        ),
        "permits": (
            permits_data.get("permits") if isinstance(permits_data, Mapping) else []
        ),
        "development_documents": (
            development_documents.get("development_documents")
            if isinstance(development_documents, Mapping)
            else []
        ),
        "documents": _aggregate_documents(components),
        "dial_components": dict(components),
        "component_coverage": {
            "requested": list(requested_components),
            "succeeded": sorted(succeeded),
            "authoritative_empty": sorted(empty),
            "failed": failed,
            "not_requested": sorted(set(DEFAULT_COMPONENTS) - requested),
        },
        "response_schema_fingerprint": sha256_fingerprint(
            {key: value.get("schema_fingerprint") for key, value in components.items()}
        ),
    }
    return record


def _resolve_summary(
    client: DialClient,
    selector: str,
    field: str,
) -> tuple[Mapping[str, Any] | None, str | None]:
    page = client.search(selector, field)
    if page.authoritative_empty:
        return None, None
    if page.direct_summary is not None:
        return page.direct_summary, page.source_url
    exact_key = "native_account_id" if field == "account" else "map_taxlot"
    matches = [
        record
        for record in page.rows
        if _clean(record.get(exact_key)) == _clean(selector)
    ]
    if not matches:
        return None, None
    if len(matches) > 1:
        raise DialSelectionError(
            "ambiguous_account_selector",
            "DIAL returned more than one exact account/taxlot match",
            details={"selector": selector, "field": field, "matches": len(matches)},
        )
    detail_url = _clean(matches[0].get("detail_url"))
    if detail_url is None:
        raise SourceSchemaError(
            "Deschutes DIAL exact result has no detail route",
            url=page.source_url,
        )
    detail = client.get_html(detail_url)
    parsed = parse_summary_page(detail.html, detail.url)
    return parsed, detail.url


def _execute_search(
    args: argparse.Namespace,
    *,
    client: DialClient,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        operation="search",
        selector=args.query,
        field=args.field,
        limit=args.limit,
        cursor=args.cursor,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        return access_failure
    page = client.search(args.query, args.field)
    records = list(page.rows)
    if page.direct_summary is not None:
        records = [
            _summary_search_record(
                page.direct_summary,
                source_url=page.source_url,
            )
        ]
    query_fp = _query_fingerprint(args.query, args.field)
    cursor_state = _decode_cursor(args.cursor, query_fingerprint=query_fp)
    snapshot = _search_snapshot(records)
    offset = int(cursor_state["o"]) if cursor_state else 0
    if cursor_state is not None:
        if (
            cursor_state["n"] != len(records)
            or cursor_state["p"] != snapshot
            or cursor_state["s"] != page.schema_fingerprint
            or offset > len(records)
            or _row_identity(records[offset - 1]) != cursor_state["a"]
        ):
            raise DialSelectionError(
                "cursor_snapshot_changed",
                "DIAL result rows changed since the continuation was issued",
                details={
                    "cursor_count": cursor_state["n"],
                    "current_count": len(records),
                    "cursor_offset": offset,
                },
            )
    selected = records[offset : offset + args.limit]
    next_cursor = None
    next_offset = offset + len(selected)
    if next_offset < len(records):
        next_cursor = _encode_cursor(
            query_fingerprint=query_fp,
            offset=next_offset,
            anchor=_row_identity(selected[-1]),
            total_count=len(records),
            snapshot=snapshot,
            schema=page.schema_fingerprint,
        )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
    )


def _execute_account(
    args: argparse.Namespace,
    *,
    client: DialClient,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    field = args.field
    if field == "auto":
        field = "account" if args.selector.isdigit() else "taxlot"
    requested = tuple(args.components)
    query = _build_query(
        operation="account",
        selector=args.selector,
        field=field,
        components=requested,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        return access_failure
    summary, summary_url = _resolve_summary(client, args.selector, field)
    if summary is None or summary_url is None:
        return PublicRecordsResult.success(query, [])
    account_id = str(summary["account_id"])
    components: dict[str, Mapping[str, Any]] = {
        "summary": _component_result("summary", summary_url, summary)
    }
    errors: list[PublicRecordsError] = []
    for key in requested:
        if key == "summary":
            continue
        try:
            data, source_url = client.component(account_id, key)
            observed_account = _clean(data.get("account_id"))
            if observed_account != account_id:
                raise SourceSchemaError(
                    "Deschutes component account identity changed",
                    url=source_url,
                    details={
                        "component": key,
                        "expected_account_id": account_id,
                        "observed_account_id": observed_account,
                    },
                )
            components[key] = _component_result(key, source_url, data)
        except PublicRecordsHTTPError as error:
            source_error = error.to_contract_error()
            errors.append(
                PublicRecordsError(
                    code=source_error.code,
                    message=source_error.message,
                    category=source_error.category,
                    retryable=source_error.retryable,
                    details={"component": key, **dict(source_error.details)},
                )
            )
    record = _normalize_account_record(
        components,
        requested_components=requested,
        component_errors=errors,
    )
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            errors,
            records=[record],
        )
    return PublicRecordsResult.success(query, [record])


def _execute_permit(
    args: argparse.Namespace,
    *,
    client: DialClient,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        operation="permit",
        selector=f"{args.account_id}:{args.permit_id}",
        field="account_and_permit",
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        return access_failure
    data, source_url = client.permit_detail(
        args.account_id,
        args.permit_id,
        args.permit_type,
    )
    if str(data.get("account_id")) != args.account_id:
        raise SourceSchemaError(
            "Deschutes permit detail account identity changed",
            url=source_url,
        )
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "record_kind": "property_permit",
        "native_account_id": args.account_id,
        "native_permit_id": data["native_permit_id"],
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "permit",
            f"{args.account_id}:{data['native_permit_id']}",
        ),
        "jurisdiction": {
            "country": "US",
            "state_code": STATE_CODE,
            "county_geoid": COUNTY_GEOID,
        },
        **dict(data),
    }
    return PublicRecordsResult.success(query, [record])


def _validate_download_arguments(args: argparse.Namespace) -> None:
    if args.report_type == "tax-statement":
        if args.year is None or args.code_area is None:
            raise DialSelectionError(
                "missing_report_parameter",
                "tax-statement requires --year and --code-area",
                status=ResultStatus.UNAVAILABLE,
            )
    if args.report_type == "improvement" and args.improvement_id is None:
        raise DialSelectionError(
            "missing_report_parameter",
            "improvement requires --improvement-id",
            status=ResultStatus.UNAVAILABLE,
        )
    if args.report_type == "future-balance":
        if args.as_of_date is None or _source_date(args.as_of_date) is None:
            raise DialSelectionError(
                "invalid_report_parameter",
                "future-balance requires --as-of-date in MM/DD/YYYY format",
                status=ResultStatus.UNAVAILABLE,
            )


def _atomic_binary_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _execute_download(
    args: argparse.Namespace,
    *,
    client: DialClient,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        operation="download",
        selector=args.account_id,
        field="account",
        report_type=args.report_type,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        return access_failure
    _validate_download_arguments(args)
    if args.report_type in CUSTOM_REPORTS:
        artifact = client.custom_report(
            args.account_id,
            args.report_type,
            poll_attempts=args.poll_attempts,
            poll_interval=args.poll_interval,
        )
    else:
        artifact = client.direct_report(
            args.account_id,
            args.report_type,
            year=args.year,
            code_area=args.code_area,
            improvement_id=args.improvement_id,
            as_of_date=args.as_of_date,
        )
    destination = Path(args.destination).expanduser().resolve()
    _atomic_binary_write(destination, artifact.content)
    digest = hashlib.sha256(artifact.content).hexdigest()
    native_document_id = ":".join(
        [
            args.account_id,
            args.report_type,
            args.year or "",
            args.improvement_id or "",
            args.as_of_date or "",
        ]
    )
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": artifact.source_url,
        "record_kind": "document_artifact",
        "document_kind": args.report_type,
        "native_document_id": native_document_id,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "document",
            native_document_id,
        ),
        "evidence_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "document",
            native_document_id,
        ),
        "native_account_id": args.account_id,
        "artifact_format": "pdf",
        "media_type": artifact.media_type,
        "source_filename": artifact.filename,
        "retrieval_state": "retrieved",
        "local_path": str(destination),
        "sha256": digest,
        "size_bytes": len(artifact.content),
        "custom_report_job_id": artifact.job_id,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination)],
    )


def _execute_probe(
    args: argparse.Namespace,
    *,
    client: DialClient,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        operation="probe",
        selector=PROBE_ACCOUNT,
        field="account",
        components=DEFAULT_COMPONENTS,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(query, access_decision)
    if access_failure is not None:
        return access_failure
    search_page = client.search(PROBE_TAXLOT, "taxlot")
    if search_page.direct_summary is None:
        raise SourceSchemaError(
            "Deschutes DIAL taxlot sentinel no longer resolves directly",
            url=search_page.source_url,
        )
    account_id = str(search_page.direct_summary["account_id"])
    taxlot = str(search_page.direct_summary["map_taxlot"])
    if account_id != PROBE_ACCOUNT or taxlot != PROBE_TAXLOT:
        raise SourceSchemaError(
            "Deschutes DIAL sentinel identity changed",
            url=search_page.source_url,
            details={
                "expected_account": PROBE_ACCOUNT,
                "observed_account": account_id,
                "expected_taxlot": PROBE_TAXLOT,
                "observed_taxlot": taxlot,
            },
        )
    component_status: dict[str, Any] = {}
    component_errors: list[PublicRecordsError] = []
    for key in DEFAULT_COMPONENTS:
        try:
            if key == "summary":
                data = search_page.direct_summary
                source_url = search_page.source_url
            else:
                data, source_url = client.component(PROBE_ACCOUNT, key)
            component_status[key] = {
                "status": "ok",
                "source_url": source_url,
                "schema_fingerprint": data["schema_fingerprint"],
            }
        except PublicRecordsHTTPError as error:
            contract_error = error.to_contract_error()
            component_errors.append(
                PublicRecordsError(
                    code=contract_error.code,
                    message=contract_error.message,
                    category=contract_error.category,
                    retryable=contract_error.retryable,
                    details={"component": key, **dict(contract_error.details)},
                )
            )
            component_status[key] = {
                "status": "error",
                "error_code": contract_error.code,
            }
    pdf_probe = client.direct_report(PROBE_ACCOUNT, "ownership")
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": BASE_URL,
        "record_kind": "source_probe",
        "sentinel": {
            "native_account_id": account_id,
            "native_parcel_id": taxlot,
        },
        "search": {
            "field": "taxlot",
            "resolution": "direct_account_summary",
            "schema_fingerprint": search_page.schema_fingerprint,
        },
        "components": component_status,
        "pdf_probe": {
            "document_kind": "ownership",
            "source_url": pdf_probe.source_url,
            "signature_verified": True,
            "size_bytes": len(pdf_probe.content),
            "media_type": pdf_probe.media_type,
        },
        "linked_source_observations": {
            "tax_payment_store": (
                component_status.get("tax_payment_store", {}).get("status")
            ),
            "recorder_documents": "external_viewer_links",
            "development_documents": "external_viewer_links",
        },
    }
    if component_errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            component_errors,
            records=[record],
        )
    return PublicRecordsResult.success(query, [record])


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": "deschutes-dial-sources/1.0",
        "source_id": SOURCE_ID,
        "name": SOURCE_NAME,
        "publisher": PUBLISHER,
        "base_url": BASE_URL,
        "jurisdiction": JURISDICTION.to_dict(),
        "identity": {
            "primary_key": "account_id",
            "taxlot_join_key": "map_taxlot",
            "arcgis_complement_source_id": ("us-or-deschutes-county-taxlots"),
        },
        "search": {
            "fields": list(SEARCH_FIELDS),
            "columns": list(SEARCH_COLUMNS),
            "source_delivery": "complete_html_table_with_client_side_paging",
            "cursor": "query_snapshot_count_schema_and_anchor_bound",
        },
        "components": {
            key: {
                "path": config.path,
                "source_system": (config.linked_system or "deschutes_dial"),
            }
            for key, config in COMPONENTS.items()
        },
        "reports": {
            "direct_pdf": list(DIRECT_REPORTS),
            "asynchronous_pdf": list(CUSTOM_REPORTS),
            "retrieval_states": [
                "link_available",
                "external_viewer_link",
                "retrieved",
            ],
        },
        "linked_systems": {
            "tax_payment_store": TAX_STORE_BASE_URL,
            "recorder": ("https://recordings.deschutes.org/DigitalResearchRoomPublic/"),
            "development_documents": "https://weblink.deschutes.org/cdd/",
        },
        "probe_account": PROBE_ACCOUNT,
        "probe_taxlot": PROBE_TAXLOT,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: DialClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, search, account, permit, download, or probe."""
    if args.command == "sources":
        return _sources_payload()
    active_client = client or _client(args, access_decision)
    owns_client = client is None
    query: PublicRecordsQuery | None = None
    try:
        if args.command == "search":
            query = _build_query(
                operation="search",
                selector=args.query,
                field=args.field,
                limit=args.limit,
                cursor=args.cursor,
                access_decision=access_decision,
            )
            result = _execute_search(
                args,
                client=active_client,
                access_decision=access_decision,
            )
        elif args.command == "account":
            field = (
                "account"
                if args.field == "auto" and args.selector.isdigit()
                else ("taxlot" if args.field == "auto" else args.field)
            )
            query = _build_query(
                operation="account",
                selector=args.selector,
                field=field,
                components=args.components,
                access_decision=access_decision,
            )
            result = _execute_account(
                args,
                client=active_client,
                access_decision=access_decision,
            )
        elif args.command == "permit":
            query = _build_query(
                operation="permit",
                selector=f"{args.account_id}:{args.permit_id}",
                field="account_and_permit",
                access_decision=access_decision,
            )
            result = _execute_permit(
                args,
                client=active_client,
                access_decision=access_decision,
            )
        elif args.command == "download":
            query = _build_query(
                operation="download",
                selector=args.account_id,
                field="account",
                report_type=args.report_type,
                access_decision=access_decision,
            )
            result = _execute_download(
                args,
                client=active_client,
                access_decision=access_decision,
            )
        else:
            query = _build_query(
                operation="probe",
                selector=PROBE_ACCOUNT,
                field="account",
                components=DEFAULT_COMPONENTS,
                access_decision=access_decision,
            )
            result = _execute_probe(
                args,
                client=active_client,
                access_decision=access_decision,
            )
    except DialSelectionError as error:
        if query is None:
            raise
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        if query is None:
            raise
        result = failure_result(query, error)
    except (KeyError, TypeError, ValueError) as error:
        if query is None:
            raise
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    finally:
        if owns_client:
            active_client.close()
    _best_effort_log(result.query, result)
    return result


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    output = getattr(args, "output", None)
    if output:
        destination = Path(output).expanduser()
        _atomic_json_write(destination, payload)
        records = payload.get("records")
        count = len(records) if isinstance(records, list) else 1
        print(f"{count} results (Deschutes DIAL {args.command}) saved to {destination}")
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"{SOURCE_NAME}: {len(COMPONENTS)} account components")
        print(
            f"  direct PDFs: {len(DIRECT_REPORTS)}; async PDFs: {len(CUSTOM_REPORTS)}"
        )
        return
    records = payload.get("records", [])
    print(
        f"Deschutes DIAL {args.command}: {payload.get('status')} "
        f"({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        if record.get("record_kind") == "source_probe":
            sentinel = record.get("sentinel", {})
            print(
                f"  sentinel {sentinel.get('native_account_id')} / "
                f"{sentinel.get('native_parcel_id')}"
            )
        elif record.get("record_kind") == "document_artifact":
            print(f"  {record.get('document_kind')} | {record.get('local_path')}")
        else:
            print(
                f"  {record.get('native_account_id')} | "
                f"{record.get('native_parcel_id') or record.get('native_permit_id')}"
            )
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _component_list(value: str) -> tuple[str, ...]:
    requested = tuple(
        dict.fromkeys(item.strip() for item in value.split(",") if item.strip())
    )
    unknown = sorted(set(requested) - set(COMPONENTS))
    if unknown:
        raise argparse.ArgumentTypeError("unknown component(s): " + ", ".join(unknown))
    if "summary" not in requested:
        requested = ("summary", *requested)
    return requested


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Deschutes County DIAL property accounts and reports"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe verified DIAL components, joins, and report routes",
    )
    add_output_args(sources)

    search = sub.add_parser(
        "search",
        help="Search the complete source-returned DIAL result table",
    )
    search.add_argument("query")
    search.add_argument("--field", choices=SEARCH_FIELDS, default="general")
    search.add_argument("--limit", type=int, default=100)
    search.add_argument(
        "--cursor",
        help="Query-bound continuation returned by an earlier search",
    )
    _add_transport_arguments(search)

    account = sub.add_parser(
        "account",
        help="Fetch account detail with independently sourced components",
    )
    account.add_argument("selector")
    account.add_argument(
        "--field",
        choices=("auto", "account", "taxlot"),
        default="auto",
    )
    account.add_argument(
        "--components",
        type=_component_list,
        default=DEFAULT_COMPONENTS,
        metavar="NAME[,NAME...]",
        help="Component names to fetch; summary is always included",
    )
    _add_transport_arguments(account)

    permit = sub.add_parser(
        "permit",
        help="Fetch one source-native permit detail and inspection history",
    )
    permit.add_argument("account_id")
    permit.add_argument("permit_id")
    permit.add_argument("--permit-type", required=True)
    _add_transport_arguments(permit)

    download = sub.add_parser(
        "download",
        help="Retrieve a verified direct or composite DIAL PDF",
    )
    download.add_argument("account_id")
    download.add_argument("report_type", choices=REPORT_TYPES)
    download.add_argument("--destination", required=True)
    download.add_argument("--year")
    download.add_argument("--code-area")
    download.add_argument("--improvement-id")
    download.add_argument("--as-of-date")
    download.add_argument("--poll-attempts", type=int, default=15)
    download.add_argument("--poll-interval", type=float, default=1.5)
    _add_transport_arguments(download)

    probe = sub.add_parser(
        "probe",
        help="Verify all account components and one direct PDF sentinel",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for field_name in ("retry_attempts", "limit", "poll_attempts"):
        value = getattr(args, field_name, 1)
        if value <= 0:
            parser.error(f"--{field_name.replace('_', '-')} must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "poll_interval", 0) < 0:
        parser.error("--poll-interval must not be negative")
    value = execute(args)
    _emit(value, args)
    if isinstance(value, PublicRecordsResult) and value.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
