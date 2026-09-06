#!/usr/bin/env python3
"""Los Angeles Superior Court paid civil party-name index adapter.

The court's Public Access Online Services (PAOS) name index discovers case
numbers from a person's first/last name or a company name.  The adapter probes
the live access contract, prepares a guest query through the court shopping-cart
boundary, reconnects guest receipts to purchased searches, and normalizes saved
or retrieved result HTML.

Examples:
    uv run python tools/query_los_angeles_name_index.py sources --json
    uv run python tools/query_los_angeles_name_index.py probe \
        --output /tmp/la-name-index-probe.json
    uv run python tools/query_los_angeles_name_index.py prepare \
        --company "Example Holdings LLC" --output /tmp/la-name-cart.json
    uv run python tools/query_los_angeles_name_index.py receipt \
        PA-2026-123456789 1234 --retrieve --output /tmp/la-name-results.json
    uv run python tools/query_los_angeles_name_index.py parse-results \
        purchased-results.html --output /tmp/la-name-results.json
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
from urllib.parse import parse_qs, urljoin, urlparse

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
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ca-los-angeles-superior-civil-name-index"
CORE_CIVIL_SOURCE_ID = "us-ca-los-angeles-superior-civil"
DOCUMENT_IMAGES_SOURCE_ID = (
    "us-ca-los-angeles-superior-civil-document-images"
)
ARCHIVES_SOURCE_ID = (
    "us-ca-los-angeles-superior-civil-archives-records-center"
)
DIVORCE_JUDGMENT_SOURCE_ID = (
    "us-ca-los-angeles-superior-divorce-judgment-orders"
)
FAMILY_SOURCE_ID = "us-ca-los-angeles-superior-family-case-summary"
SMALL_CLAIMS_SOURCE_ID = (
    "us-ca-los-angeles-superior-small-claims-case-summary"
)
PROBATE_SOURCE_ID = "us-ca-los-angeles-superior-probate"
SECOND_DISTRICT_SOURCE_ID = (
    "us-ca-second-district-appellate-case-information"
)
TRELLIS_SOURCE_ID = "us-ca-trellis-los-angeles-superior-court"
STATE_CODE = "CA"
COUNTY_GEOID = "06037"
COURT_ID = "ca-los-angeles-superior-court"
CORE_CIVIL_COURT_ID = "ca-los-angeles-superior-court-civil"
FAMILY_COURT_ID = "ca-los-angeles-superior-court-family-law"
SMALL_CLAIMS_COURT_ID = "ca-los-angeles-superior-court-small-claims"
PROBATE_COURT_ID = "ca-los-angeles-superior-court-probate"
COURT_NAME = "Superior Court of California, County of Los Angeles"

BASE_URL = "https://www.lacourt.ca.gov"
PAOS_BASE_URL = f"{BASE_URL}/paos/v2web3"
CIVIL_INDEX_URL = f"{PAOS_BASE_URL}/CivilIndex"
SEARCH_URL = f"{CIVIL_INDEX_URL}/Search"
GUEST_INFORMATION_URL = f"{PAOS_BASE_URL}/GuestInformation"
FEE_INFORMATION_URL = f"{PAOS_BASE_URL}/FeeInformation"
FAQ_URL = f"{PAOS_BASE_URL}/FAQ"
PAYMENT_URL = f"{PAOS_BASE_URL}/Payment"
DOCUMENT_IMAGES_URL = f"{PAOS_BASE_URL}/DocumentImages/"

EXACT_CASE_URL = f"{BASE_URL}/casesummary/v2web3/UDCaseSearch"
TENTATIVE_RULINGS_URL = (
    f"{BASE_URL}/tentativeRulingNet/ui/main.aspx?casetype=civil"
)
DIVORCE_JUDGMENT_URL = f"{BASE_URL}/ldos/v2pubweb3/"
ARCHIVES_URL = (
    "https://www.lacourt.org/generalinfo/Archives/GI_AR001.aspx"
)
COURTHOUSE_DIRECTORY_URL = f"{BASE_URL}/apps/courthouse"
APPELLATE_CASE_URL = "https://appellatecases.courtinfo.ca.gov/"
TRELLIS_LA_URL = "https://trellis.law/coverage/california/losangeles"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

SOURCE_WARNINGS = (
    "The CivilIndex is a paid name-to-case-number index; search results appear "
    "after the court payment confirmation flow.",
    "The court warns that a name search can return different people who share "
    "the same name and can omit the intended person.",
    "Unlawful Detainer case information has source-specific public-access "
    "delays and prevailing-defendant suppression described by the court.",
    "The online index points older-case research to the court Archives and "
    "Records Center.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Los Angeles Superior Court Civil Party Name Search",
    source_role="county_superior_civil_party_to_case_index",
    base_url=CIVIL_INDEX_URL,
    dataset_id="lasc-paos-civil-index",
    metadata={
        "authority": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_id": COURT_ID,
        "record_identity_source_id": CORE_CIVIL_SOURCE_ID,
        "case_family_identity_sources": {
            "civil": CORE_CIVIL_SOURCE_ID,
            "family_law": FAMILY_SOURCE_ID,
            "small_claims": SMALL_CLAIMS_SOURCE_ID,
            "probate": PROBATE_SOURCE_ID,
        },
        "access_model": "paid_guest_or_registered_search",
        "search_url": SEARCH_URL,
        "fee_url": FEE_INFORMATION_URL,
        "guest_information_url": GUEST_INFORMATION_URL,
        "receipt_recovery": "receipt_number_plus_last_four_card_digits",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Los Angeles County, California",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
)


class LANameIndexError(RuntimeError):
    """Structured source or workflow error."""

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


class LANameIndexSourceChanged(LANameIndexError):
    """The live PAOS HTML or redirect flow no longer matches the contract."""

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
class SearchForm:
    token: str
    field_names: tuple[str, ...]
    method: str
    action_url: str
    remark_max_length: int | None
    schema_fingerprint: str


@dataclass(frozen=True)
class CartItem:
    description: str
    amount_text: str
    amount_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "amount_text": self.amount_text,
            "amount_usd": self.amount_usd,
        }


@dataclass(frozen=True)
class CartSummary:
    items: tuple[CartItem, ...]
    total_text: str
    total_usd: float
    checkout_form_action: str
    schema_fingerprint: str


@dataclass(frozen=True)
class GuestTransaction:
    receipt_number: str | None
    transaction_date: str | None
    amount_text: str | None
    description: str | None
    action_id: str | None
    case_type: str | None
    raw: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_number": self.receipt_number,
            "transaction_date": self.transaction_date,
            "amount_text": self.amount_text,
            "description": self.description,
            "action_id": self.action_id,
            "case_type": self.case_type,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class GuestPage:
    token: str
    field_names: tuple[str, ...]
    services: tuple[Mapping[str, str], ...]
    transactions: tuple[GuestTransaction, ...]
    no_valid_receipts: bool
    result_availability_statement: str | None
    schema_fingerprint: str


@dataclass(frozen=True)
class IndexMatch:
    party_name: str
    case_number: str
    case_type: str | None
    filing_date: str | None
    filing_location: str | None
    available_image_count: int | None
    raw: Mapping[str, str]
    source_url: str


@dataclass(frozen=True)
class IndexResultPage:
    matches: tuple[IndexMatch, ...]
    no_results_message: str | None
    headers: tuple[str, ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class PreparedSearch:
    criteria: Mapping[str, str]
    cart: CartSummary
    checkout_url: str
    search_redirect_url: str


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _label(value: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", _text(value).lower())).strip(
        "_"
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _money(value: str) -> float:
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)", value.replace(",", ""))
    if not match:
        raise LANameIndexSourceChanged(
            "money_value_missing",
            f"Could not parse a dollar value from {value!r}",
        )
    return float(match.group(1))


def _source_date(value: str | None) -> str | None:
    if not value:
        return None
    candidate = _text(value)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _table_rows(table: Tag) -> tuple[list[str], list[list[str]]]:
    header_cells = table.select("thead tr th, thead tr td")
    headers = [_text(cell.get_text(" ", strip=True)) for cell in header_cells]
    rows: list[list[str]] = []
    for row in table.select("tbody tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if cells:
            rows.append([_text(cell.get_text(" ", strip=True)) for cell in cells])
    if not headers:
        first = table.find("tr")
        if first and first.find("th"):
            headers = [
                _text(cell.get_text(" ", strip=True))
                for cell in first.find_all(["th", "td"], recursive=False)
            ]
            rows = [
                [
                    _text(cell.get_text(" ", strip=True))
                    for cell in row.find_all(["th", "td"], recursive=False)
                ]
                for row in first.find_all_next("tr")
                if row.find_parent("table") is table
            ]
    return headers, rows


def parse_civil_index_html(html: str) -> dict[str, Any]:
    """Parse the court's advertised result fields, coverage, and archive route."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    required_phrases = (
        "Search for Case by Name",
        "Civil",
        "Small Claims",
        "Family Law",
        "Probate",
    )
    missing = [phrase for phrase in required_phrases if phrase not in page_text]
    if missing:
        raise LANameIndexSourceChanged(
            "civil_index_contract_missing",
            "CivilIndex landing page is missing required source descriptions",
            details={"missing_phrases": missing},
        )

    coverage: list[dict[str, str]] = []
    for table in soup.find_all("table"):
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 2:
                continue
            period = _text(cells[1].get_text(" ", strip=True))
            if not re.search(r"\b(?:19|20)\d{2}\b", period):
                continue
            case_types = [
                _text(item.get_text(" ", strip=True))
                for item in cells[0].find_all("li")
            ]
            if not case_types:
                case_types = [_text(cells[0].get_text(" ", strip=True))]
            for case_type in case_types:
                if case_type:
                    coverage.append(
                        {
                            "case_type": case_type,
                            "source_date_range": period,
                        }
                    )

    expected_types = {
        "Unlimited Civil",
        "Probate",
        "Family Law",
        "Limited Civil",
        "Small Claims",
    }
    observed_types = {row["case_type"] for row in coverage}
    if not expected_types.issubset(observed_types):
        raise LANameIndexSourceChanged(
            "coverage_table_changed",
            "CivilIndex coverage table no longer exposes all expected case types",
            details={"observed_case_types": sorted(observed_types)},
        )

    archive_link = None
    for anchor in soup.find_all("a", href=True):
        if "archive" in _text(anchor.get_text(" ", strip=True)).casefold():
            archive_link = urljoin(CIVIL_INDEX_URL, str(anchor["href"]))
            break

    result_fields = (
        "litigant_name",
        "case_number",
        "case_type",
        "filing_date",
        "filing_location",
        "available_imaged_document_count",
    )
    return {
        "coverage": coverage,
        "result_fields": list(result_fields),
        "updated_daily": "updated daily" in page_text.casefold(),
        "archive_url": archive_link,
        "schema_fingerprint": _fingerprint(
            {"coverage": coverage, "result_fields": result_fields}
        ),
    }


def parse_fee_html(html: str) -> dict[str, Any]:
    """Parse registered and guest name-search fee tiers."""

    soup = BeautifulSoup(html, "html.parser")
    schedules: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        heading = _text(table.get_text(" ", strip=True))
        if "Name Search Fee Schedule" not in heading:
            continue
        account_type = "guest" if "Guest User" in heading else "registered"
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 2:
                continue
            description = _text(cells[0].get_text(" ", strip=True))
            amount_text = _text(cells[1].get_text(" ", strip=True))
            schedules.append(
                {
                    "account_type": account_type,
                    "description": description,
                    "amount_text": amount_text,
                    "amount_usd": _money(amount_text),
                }
            )
    if not any(row["account_type"] == "guest" for row in schedules):
        raise LANameIndexSourceChanged(
            "guest_fee_missing",
            "Fee page no longer exposes a guest name-search fee",
        )
    if not any(row["account_type"] == "registered" for row in schedules):
        raise LANameIndexSourceChanged(
            "registered_fee_missing",
            "Fee page no longer exposes registered name-search tiers",
        )
    return {
        "name_search_fees": schedules,
        "schema_fingerprint": _fingerprint(schedules),
    }


def _form_action(form: Tag, base_url: str) -> str:
    action = _text(form.get("action"))
    return urljoin(base_url, action) if action else base_url


def _token(form: Tag) -> str:
    element = form.find("input", attrs={"name": "__RequestVerificationToken"})
    value = _text(element.get("value")) if element else ""
    if not value:
        raise LANameIndexSourceChanged(
            "antiforgery_token_missing",
            "The court form no longer exposes an antiforgery token",
        )
    return value


def parse_search_form_html(html: str, *, source_url: str = SEARCH_URL) -> SearchForm:
    """Parse the verified PAOS civil-name search form."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="paosForm")
    if not isinstance(form, Tag):
        raise LANameIndexSourceChanged(
            "search_form_missing",
            "The PAOS civil-name search form was not found",
        )
    fields = tuple(
        str(element.get("name"))
        for element in form.find_all(["input", "select", "textarea"])
        if element.get("name")
    )
    required = {
        "LastName",
        "FirstName",
        "CompanyName",
        "Remark",
        "FilingDateStart",
        "FilingDateEnd",
        "__RequestVerificationToken",
    }
    missing = sorted(required.difference(fields))
    if missing:
        raise LANameIndexSourceChanged(
            "search_fields_changed",
            "The PAOS civil-name search form fields changed",
            details={"missing_fields": missing, "observed_fields": list(fields)},
        )
    remark = form.find("input", attrs={"name": "Remark"})
    max_length = None
    if remark and remark.get("maxlength"):
        try:
            max_length = int(str(remark["maxlength"]))
        except ValueError:
            pass
    schema = {
        "fields": list(fields),
        "method": _text(form.get("method")).lower() or "get",
        "action_url": _form_action(form, source_url),
        "remark_max_length": max_length,
    }
    return SearchForm(
        token=_token(form),
        field_names=fields,
        method=schema["method"],
        action_url=schema["action_url"],
        remark_max_length=max_length,
        schema_fingerprint=_fingerprint(schema),
    )


def parse_cart_html(html: str, *, source_url: str) -> CartSummary:
    """Parse the official shopping-cart summary reached before checkout."""

    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.get_text(" ", strip=True))
    if "Online Services Purchase Summary" not in title:
        raise LANameIndexSourceChanged(
            "cart_summary_missing",
            "The court shopping cart no longer exposes its purchase summary",
            details={"source_url": source_url},
        )
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise LANameIndexSourceChanged(
            "checkout_form_missing",
            "The court shopping cart no longer exposes its checkout form",
        )
    table = form.find("table")
    if not isinstance(table, Tag):
        raise LANameIndexSourceChanged(
            "cart_table_missing",
            "The court shopping cart no longer exposes item rows",
        )
    items: list[CartItem] = []
    total_text = ""
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        description = _text(cells[0].get_text(" ", strip=True))
        amount_text = _text(cells[1].get_text(" ", strip=True))
        if "total" in row.get("class", []) or description.casefold() == "total":
            total_text = amount_text
            continue
        items.append(
            CartItem(
                description=description,
                amount_text=amount_text,
                amount_usd=_money(amount_text),
            )
        )
    if not items or not total_text:
        raise LANameIndexSourceChanged(
            "cart_rows_changed",
            "The court shopping cart item or total rows changed",
        )
    schema = {
        "headers": [
            _text(cell.get_text(" ", strip=True))
            for cell in table.select("thead th")
        ],
        "checkout_form_action": _form_action(form, source_url),
    }
    return CartSummary(
        items=tuple(items),
        total_text=total_text,
        total_usd=_money(total_text),
        checkout_form_action=schema["checkout_form_action"],
        schema_fingerprint=_fingerprint(schema),
    )


_TRANSACTION_ALIASES = {
    "receipt": "receipt_number",
    "receipt_number": "receipt_number",
    "receipt_no": "receipt_number",
    "date": "transaction_date",
    "transaction_date": "transaction_date",
    "amount": "amount_text",
    "description": "description",
    "action": "action",
}


def _extract_search_action(row: Tag) -> tuple[str | None, str | None, str | None]:
    for element in row.find_all(["input", "button", "a"]):
        onclick = _text(element.get("onclick"))
        match = re.search(
            r"getSearch\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
            r"['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
            onclick,
        )
        if match:
            return match.group(1), match.group(2) or None, match.group(3)
    return None, None, None


def parse_guest_html(html: str, *, source_url: str = GUEST_INFORMATION_URL) -> GuestPage:
    """Parse guest services, receipt form, and attached transaction rows."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="paosForm")
    if not isinstance(form, Tag):
        raise LANameIndexSourceChanged(
            "guest_form_missing",
            "The PAOS Guest Information receipt form was not found",
        )
    fields = tuple(
        str(element.get("name"))
        for element in form.find_all(["input", "select", "textarea"])
        if element.get("name")
    )
    required = {
        "ReceiptNumber",
        "Last4CC",
        "ActionToPerform",
        "ActionDocumentID",
        "ActionReceiptNumber",
        "SecurityKey",
        "__RequestVerificationToken",
    }
    missing = sorted(required.difference(fields))
    if missing:
        raise LANameIndexSourceChanged(
            "guest_fields_changed",
            "The PAOS guest receipt form fields changed",
            details={"missing_fields": missing, "observed_fields": list(fields)},
        )

    services: list[dict[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        title = _text(anchor.get("title"))
        href = str(anchor["href"])
        if title.startswith("Click here to search"):
            services.append(
                {
                    "name": _text(anchor.get_text(" ", strip=True)),
                    "url": urljoin(source_url, href),
                }
            )

    transactions: list[GuestTransaction] = []
    for table in soup.find_all("table"):
        header_elements = table.select("thead th")
        if not header_elements:
            first_row = table.find("tr")
            header_elements = first_row.find_all("th") if first_row else []
        headers = [_label(cell.get_text(" ", strip=True)) for cell in header_elements]
        canonical_headers = [_TRANSACTION_ALIASES.get(value, value) for value in headers]
        if "receipt_number" not in canonical_headers:
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
            raw = {
                canonical_headers[index]: value
                for index, value in enumerate(values)
                if index < len(canonical_headers)
            }
            action_id, case_type, action_receipt = _extract_search_action(row)
            receipt_number = raw.get("receipt_number") or action_receipt
            transactions.append(
                GuestTransaction(
                    receipt_number=receipt_number,
                    transaction_date=raw.get("transaction_date"),
                    amount_text=raw.get("amount_text"),
                    description=raw.get("description"),
                    action_id=action_id,
                    case_type=case_type,
                    raw=raw,
                )
            )

    page_text = _text(soup.get_text(" ", strip=True))
    availability_match = re.search(
        r"Name Search results remain available for [^.]+\.",
        page_text,
        flags=re.IGNORECASE,
    )
    schema = {
        "fields": list(fields),
        "services": [service["name"] for service in services],
        "transaction_headers": sorted(
            {
                key
                for transaction in transactions
                for key in transaction.raw
            }
        ),
    }
    return GuestPage(
        token=_token(form),
        field_names=fields,
        services=tuple(services),
        transactions=tuple(transactions),
        no_valid_receipts=(
            "You have not added any valid receipt numbers" in page_text
            or "You have no transactions" in page_text
        ),
        result_availability_statement=(
            _text(availability_match.group(0)) if availability_match else None
        ),
        schema_fingerprint=_fingerprint(schema),
    )


_RESULT_HEADER_ALIASES = {
    "litigant": "party_name",
    "litigant_name": "party_name",
    "party": "party_name",
    "party_name": "party_name",
    "name": "party_name",
    "case": "case_number",
    "case_no": "case_number",
    "case_number": "case_number",
    "case_#": "case_number",
    "case_type": "case_type",
    "type": "case_type",
    "filing_date": "filing_date",
    "filed": "filing_date",
    "file_date": "filing_date",
    "filing_location": "filing_location",
    "filing_courthouse": "filing_location",
    "location": "filing_location",
    "court_location": "filing_location",
    "number_of_imaged_documents": "available_image_count",
    "number_of_available_imaged_documents": "available_image_count",
    "available_imaged_documents": "available_image_count",
    "imaged_documents": "available_image_count",
    "document_images": "available_image_count",
    "documents": "available_image_count",
}

_NO_RESULT_PATTERNS = (
    "no match found",
    "no matches found",
    "no records found",
    "your search returned no",
    "there are no records",
)


def _result_headers(table: Tag) -> tuple[list[str], Tag | None]:
    header_row = None
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        labels = [_label(cell.get_text(" ", strip=True)) for cell in cells]
        canonical = [_RESULT_HEADER_ALIASES.get(value, value) for value in labels]
        if len({"party_name", "case_type", "filing_date", "filing_location"}.intersection(canonical)) >= 3:
            header_row = row
            return canonical, header_row
    return [], None


def _case_number_from_row(row: Tag) -> str | None:
    for anchor in row.find_all("a", href=True):
        anchor_text = _text(anchor.get_text(" ", strip=True))
        if anchor_text and re.search(r"\d", anchor_text):
            return anchor_text
        parsed = urlparse(urljoin(BASE_URL, str(anchor["href"])))
        query = parse_qs(parsed.query)
        for key in ("caseNumber", "casenumber", "case", "CaseNumber"):
            values = query.get(key)
            if values and _text(values[0]):
                return _text(values[0])
    return None


def _image_count(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group(0)) if match else None


def parse_results_html(
    html: str,
    *,
    source_url: str = CIVIL_INDEX_URL,
) -> IndexResultPage:
    """Normalize a purchased CivilIndex result page.

    The parser keys rows from visible headers rather than fixed column
    positions.  This supports saved pages and receipt-recovered pages while
    retaining the native text of every observed field.
    """

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    for phrase in _NO_RESULT_PATTERNS:
        if phrase in page_text.casefold():
            return IndexResultPage(
                matches=(),
                no_results_message=next(
                    (
                        _text(node.get_text(" ", strip=True))
                        for node in soup.find_all(["p", "div", "td"])
                        if phrase in _text(node.get_text(" ", strip=True)).casefold()
                    ),
                    phrase,
                ),
                headers=(),
                schema_fingerprint=_fingerprint({"no_results_phrase": phrase}),
            )

    matches: list[IndexMatch] = []
    matched_headers: list[str] = []
    for table in soup.find_all("table"):
        headers, header_row = _result_headers(table)
        if not headers or header_row is None:
            continue
        matched_headers = headers
        for row in header_row.find_all_next("tr"):
            if row.find_parent("table") is not table:
                break
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
            raw = {
                headers[index]: value
                for index, value in enumerate(values)
                if index < len(headers)
            }
            case_number = _text(raw.get("case_number")) or _case_number_from_row(row)
            party_name = _text(raw.get("party_name"))
            if not case_number and not party_name:
                continue
            if not case_number:
                raise LANameIndexSourceChanged(
                    "result_case_number_missing",
                    "A CivilIndex result row did not expose a case number",
                    details={"raw_row": raw},
                )
            if not party_name:
                raise LANameIndexSourceChanged(
                    "result_party_name_missing",
                    "A CivilIndex result row did not expose a litigant name",
                    details={"case_number": case_number, "raw_row": raw},
                )
            matches.append(
                IndexMatch(
                    party_name=party_name,
                    case_number=case_number,
                    case_type=_text(raw.get("case_type")) or None,
                    filing_date=_text(raw.get("filing_date")) or None,
                    filing_location=_text(raw.get("filing_location")) or None,
                    available_image_count=_image_count(
                        raw.get("available_image_count")
                    ),
                    raw=raw,
                    source_url=source_url,
                )
            )
        if matches:
            break

    if not matches:
        raise LANameIndexSourceChanged(
            "result_table_missing",
            "The supplied page is neither a recognized CivilIndex result table "
            "nor an authoritative no-results page",
            details={"source_url": source_url},
        )
    return IndexResultPage(
        matches=tuple(matches),
        no_results_message=None,
        headers=tuple(matched_headers),
        schema_fingerprint=_fingerprint({"headers": matched_headers}),
    )


def _query_criteria(
    *,
    first_name: str | None,
    last_name: str | None,
    company: str | None,
    filing_date_start: str | None,
    filing_date_end: str | None,
    remark: str | None,
) -> dict[str, str]:
    first = _text(first_name)
    last = _text(last_name)
    company_name = _text(company)
    if company_name and (first or last):
        raise ValueError("choose a person name or a company name")
    if company_name:
        search_kind = "company"
    elif first and last:
        search_kind = "person"
    else:
        raise ValueError("person searches require first and last name")
    if remark and len(remark) > 30:
        raise ValueError("remark exceeds the source's 30-character field")

    dates: dict[str, datetime] = {}
    for key, value in (
        ("filing_date_start", filing_date_start),
        ("filing_date_end", filing_date_end),
    ):
        if value:
            try:
                dates[key] = datetime.strptime(value, "%m/%d/%Y")
            except ValueError as error:
                raise ValueError(f"{key} must use mm/dd/yyyy") from error
    if (
        "filing_date_start" in dates
        and "filing_date_end" in dates
        and dates["filing_date_start"] > dates["filing_date_end"]
    ):
        raise ValueError("filing_date_start must not follow filing_date_end")

    return {
        "search_kind": search_kind,
        "first_name": first,
        "last_name": last,
        "company_name": company_name,
        "filing_date_start": _text(filing_date_start),
        "filing_date_end": _text(filing_date_end),
        "remark": _text(remark),
    }


def _payload(criteria: Mapping[str, str], token: str) -> dict[str, str]:
    return {
        "LastName": criteria["last_name"],
        "FirstName": criteria["first_name"],
        "CompanyName": criteria["company_name"],
        "Remark": criteria["remark"],
        "FilingDateStart": criteria["filing_date_start"],
        "FilingDateEnd": criteria["filing_date_end"],
        "__RequestVerificationToken": token,
    }


class LANameIndexClient:
    """Paced same-session client for PAOS guest and receipt workflows."""

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
        self._owns_session = session is None
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
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        referer: str | None = None,
        allow_redirects: bool = True,
        expected_statuses: Sequence[int] = (200,),
    ) -> Any:
        headers = {"Referer": referer} if referer else None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                if method == "GET":
                    response = self.session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=allow_redirects,
                    )
                else:
                    response = self.session.post(
                        url,
                        data=dict(data or {}),
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=allow_redirects,
                    )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise LANameIndexError(
                        "transport_error",
                        f"Los Angeles CivilIndex request failed: {error}",
                        category="transport",
                        retryable=True,
                        details={"url": url, "method": method},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise LANameIndexError(
                    "source_rate_limited",
                    "Los Angeles CivilIndex rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code in {401, 403}:
                raise LANameIndexError(
                    "source_access_restricted",
                    f"Los Angeles CivilIndex returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "http_status": status_code},
                )
            if status_code not in expected_statuses:
                raise LANameIndexError(
                    "source_http_error",
                    f"Los Angeles CivilIndex returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )

            final_url = str(getattr(response, "url", url))
            hostname = urlparse(final_url).hostname
            if hostname and hostname not in {"www.lacourt.ca.gov", "ww2.lacourt.org"}:
                raise LANameIndexSourceChanged(
                    "unexpected_redirect",
                    "The court redirected outside the verified court hosts",
                    details={"requested_url": url, "final_url": final_url},
                )
            if status_code == 200:
                content_type = str(
                    getattr(response, "headers", {}).get("Content-Type", "")
                ).casefold()
                if content_type and "html" not in content_type:
                    raise LANameIndexSourceChanged(
                        "non_html_response",
                        "Los Angeles CivilIndex returned a non-HTML response",
                        details={"url": url, "content_type": content_type},
                    )
            return response
        raise AssertionError("retry loop exhausted")

    def bootstrap_guest(self) -> GuestPage:
        response = self._request("GET", GUEST_INFORMATION_URL)
        return parse_guest_html(response.text, source_url=str(response.url))

    def bootstrap_search(self) -> SearchForm:
        self.bootstrap_guest()
        self._request("GET", CIVIL_INDEX_URL)
        response = self._request("GET", SEARCH_URL)
        return parse_search_form_html(response.text, source_url=str(response.url))

    def probe(self) -> dict[str, Any]:
        landing_response = self._request("GET", CIVIL_INDEX_URL)
        fee_response = self._request("GET", FEE_INFORMATION_URL)
        faq_response = self._request("GET", FAQ_URL)
        guest = self.bootstrap_guest()
        self._request("GET", CIVIL_INDEX_URL)
        search_response = self._request("GET", SEARCH_URL)
        search_form = parse_search_form_html(
            search_response.text,
            source_url=str(search_response.url),
        )
        faq_text = _text(
            BeautifulSoup(faq_response.text, "html.parser").get_text(" ", strip=True)
        )
        redo_match = re.search(
            r'The "Redo Search" button will only be available for [^.]+\.',
            faq_text,
            flags=re.IGNORECASE,
        )
        return {
            "source_id": SOURCE_ID,
            "record_kind": "source_probe",
            "source_url": CIVIL_INDEX_URL,
            "landing": parse_civil_index_html(landing_response.text),
            "fees": parse_fee_html(fee_response.text),
            "search_form": {
                "method": search_form.method,
                "action_url": search_form.action_url,
                "field_names": list(search_form.field_names),
                "remark_max_length": search_form.remark_max_length,
                "schema_fingerprint": search_form.schema_fingerprint,
            },
            "guest": {
                "services": list(guest.services),
                "receipt_field_names": list(guest.field_names),
                "result_availability_statement": (
                    guest.result_availability_statement
                ),
                "faq_redo_statement": (
                    _text(redo_match.group(0)) if redo_match else None
                ),
                "schema_fingerprint": guest.schema_fingerprint,
            },
            "access": {
                "guest_session": "anonymous",
                "query_submission": "same_session_antiforgery_post",
                "result_delivery": "after_payment_confirmation",
                "receipt_recovery": (
                    "receipt_number_plus_last_four_card_digits"
                ),
            },
        }

    def prepare(self, criteria: Mapping[str, str]) -> PreparedSearch:
        form = self.bootstrap_search()
        response = self._request(
            "POST",
            SEARCH_URL,
            data=_payload(criteria, form.token),
            referer=SEARCH_URL,
            allow_redirects=False,
            expected_statuses=(302,),
        )
        payment_location = urljoin(
            SEARCH_URL,
            _text(getattr(response, "headers", {}).get("Location")),
        )
        payment_parts = urlparse(payment_location)
        if (
            payment_parts.hostname != "www.lacourt.ca.gov"
            or payment_parts.path.rstrip("/") != urlparse(PAYMENT_URL).path.rstrip("/")
        ):
            raise LANameIndexSourceChanged(
                "payment_redirect_changed",
                "CivilIndex search no longer redirects to the verified payment route",
                details={"redirect_url": payment_location},
            )

        payment_response = self._request(
            "GET",
            payment_location,
            referer=SEARCH_URL,
            allow_redirects=False,
            expected_statuses=(302,),
        )
        checkout_url = urljoin(
            payment_location,
            _text(getattr(payment_response, "headers", {}).get("Location")),
        )
        checkout_parts = urlparse(checkout_url)
        if (
            checkout_parts.hostname != "ww2.lacourt.org"
            or not checkout_parts.path.startswith("/ShoppingCart/v3/Home/Index")
        ):
            raise LANameIndexSourceChanged(
                "shopping_cart_redirect_changed",
                "PAOS no longer redirects to the verified court shopping cart",
                details={"redirect_url": checkout_url},
            )
        cart_response = self._request(
            "GET",
            checkout_url,
            referer=payment_location,
        )
        cart = parse_cart_html(
            cart_response.text,
            source_url=str(cart_response.url),
        )
        return PreparedSearch(
            criteria=dict(criteria),
            cart=cart,
            checkout_url=checkout_url,
            search_redirect_url=payment_location,
        )

    def attach_receipt(
        self,
        receipt_number: str,
        last_four: str,
    ) -> GuestPage:
        guest = self.bootstrap_guest()
        response = self._request(
            "POST",
            GUEST_INFORMATION_URL,
            data={
                "ReceiptNumber": receipt_number,
                "Last4CC": last_four,
                "ActionToPerform": "addreceipt",
                "ActionDocumentID": "",
                "ActionReceiptNumber": "",
                "SecurityKey": "",
                "__RequestVerificationToken": guest.token,
            },
            referer=GUEST_INFORMATION_URL,
        )
        return parse_guest_html(response.text, source_url=str(response.url))

    def retrieve_receipt_search(
        self,
        receipt_number: str,
        last_four: str,
    ) -> tuple[GuestTransaction, IndexResultPage]:
        guest = self.attach_receipt(receipt_number, last_four)
        candidates = [
            transaction
            for transaction in guest.transactions
            if (
                not transaction.receipt_number
                or transaction.receipt_number == receipt_number
            )
            and transaction.action_id
            and transaction.action_id.upper() == "IDX"
        ]
        if not candidates:
            raise LANameIndexError(
                "civil_search_action_unavailable",
                "The attached receipt does not expose an available civil "
                "name-search retrieval action",
                status=ResultStatus.RESTRICTED,
                category="receipt",
                details={
                    "receipt_number": receipt_number,
                    "transaction_count": len(guest.transactions),
                    "available_action_ids": sorted(
                        {
                            transaction.action_id
                            for transaction in guest.transactions
                            if transaction.action_id
                        }
                    ),
                    "no_valid_receipts": guest.no_valid_receipts,
                },
            )
        transaction = candidates[0]
        response = self._request(
            "POST",
            GUEST_INFORMATION_URL,
            data={
                "ReceiptNumber": "",
                "Last4CC": "",
                "ActionToPerform": transaction.action_id or "IDX",
                "ActionDocumentID": "",
                "ActionReceiptNumber": receipt_number,
                "SecurityKey": "",
                "__RequestVerificationToken": guest.token,
            },
            referer=GUEST_INFORMATION_URL,
        )
        return transaction, parse_results_html(
            response.text,
            source_url=str(response.url),
        )


def _case_family_identity(case_type: str | None) -> tuple[str, str, str]:
    label = _text(case_type).casefold()
    if "probate" in label:
        return PROBATE_SOURCE_ID, PROBATE_COURT_ID, "probate"
    if "family" in label or "divorce" in label or "dissolution" in label:
        return FAMILY_SOURCE_ID, FAMILY_COURT_ID, "family_law"
    if "small claim" in label:
        return (
            SMALL_CLAIMS_SOURCE_ID,
            SMALL_CLAIMS_COURT_ID,
            "small_claims",
        )
    return CORE_CIVIL_SOURCE_ID, CORE_CIVIL_COURT_ID, "civil"


def _court_payload(case_type: str | None) -> dict[str, Any]:
    _identity_source_id, court_id, case_family = _case_family_identity(
        case_type
    )
    return {
        "court_id": court_id,
        "native_court_id": court_id,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "superior",
        "division": case_family,
        "official_url": BASE_URL,
    }


def normalize_matches(page: IndexResultPage) -> list[dict[str, Any]]:
    """Normalize purchased result rows with collision-safe source identities."""

    duplicate_counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    for match in page.matches:
        (
            record_identity_source_id,
            record_identity_court_id,
            case_family,
        ) = _case_family_identity(match.case_type)
        case_identity_basis = {
            "case_number": match.case_number,
            "case_type": match.case_type,
            "filing_date": match.filing_date,
            "filing_location": match.filing_location,
            "record_identity_source_id": record_identity_source_id,
            "record_identity_court_id": record_identity_court_id,
        }
        case_native_id = _fingerprint(case_identity_basis)
        base_match_identity = {
            **case_identity_basis,
            "party_name": match.party_name,
        }
        base_key = canonical_json(base_match_identity)
        ordinal = duplicate_counts.get(base_key, 0)
        duplicate_counts[base_key] = ordinal + 1
        match_identity_basis = {
            **base_match_identity,
            "duplicate_ordinal": ordinal,
        }
        match_native_id = _fingerprint(match_identity_basis)
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    match.case_number,
                    record_kind="case_index_match",
                    native_id=match_native_id,
                ),
                "case_canonical_ref": canonical_court_ref(
                    record_identity_source_id,
                    record_identity_court_id,
                    match.case_number,
                ),
                "source_id": SOURCE_ID,
                "record_identity_source_id": record_identity_source_id,
                "record_kind": "case_index_match",
                "source_internal_id": case_native_id,
                "source_result_id": match_native_id,
                "identity_kind": (
                    "case_number_party_case_type_filing_date_"
                    "filing_location_duplicate_ordinal_sha256"
                ),
                "identity_basis": match_identity_basis,
                "case_identity_kind": (
                    "case_number_case_type_filing_date_"
                    "filing_location_sha256"
                ),
                "case_identity_basis": case_identity_basis,
                "court": _court_payload(match.case_type),
                "raw_case_number": match.case_number,
                "display_case_number": match.case_number,
                "matched_party_name": match.party_name,
                "case_family": case_family,
                "parties": [
                    {
                        "name": match.party_name,
                        "role": "litigant",
                        "native_role": "litigant",
                        "source_match": "civil_party_name_index",
                    }
                ],
                "case_type": match.case_type,
                "filing_date": _source_date(match.filing_date),
                "source_filing_date_raw": match.filing_date,
                "filing_location": match.filing_location,
                "available_imaged_document_count": (
                    match.available_image_count
                ),
                "access_state": "purchased_name_index_result",
                "source_url": match.source_url,
                "result_schema_fingerprint": page.schema_fingerprint,
                "raw": dict(match.raw),
            }
        )
    return records


def source_records() -> list[dict[str, Any]]:
    """Return distinct primary and complementary LA court routes."""

    return [
        {
            "source_id": SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "civil_party_name_index",
            "authority": COURT_NAME,
            "url": CIVIL_INDEX_URL,
            "access_model": "paid_guest_or_registered_search",
            "adds": [
                "party-to-case-number discovery",
                "case type",
                "filing date",
                "filing location",
                "available image count",
            ],
            "coverage": (
                "Unlimited Civil, Probate, and Family Law 1983-present; "
                "Limited Civil 1991-present; Small Claims 1992-present"
            ),
        },
        {
            "source_id": CORE_CIVIL_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "exact_case_summary",
            "authority": COURT_NAME,
            "url": EXACT_CASE_URL,
            "access_model": "anonymous_exact_case_number",
            "adds": [
                "parties",
                "future hearings",
                "filed-document index",
                "past proceedings",
                "register of actions",
            ],
            "gap": "requires a known case number",
            "existing_adapter": "tools/query_los_angeles_court.py",
        },
        {
            "source_id": DOCUMENT_IMAGES_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "case_document_images",
            "authority": COURT_NAME,
            "url": DOCUMENT_IMAGES_URL,
            "access_model": "paid_document_download",
            "adds": ["scanned filings and court-generated documents"],
            "gap": (
                "coverage varies by case type, filing courthouse, date, and "
                "whether the document was scanned"
            ),
        },
        {
            "source_id": ARCHIVES_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "archives_and_clerk",
            "authority": COURT_NAME,
            "url": ARCHIVES_URL,
            "access_model": "appointment_mail_or_in_person",
            "adds": [
                "older case-name and case-number index searches",
                "record inspection",
                "copies and certification",
            ],
            "complements": "online-index periods and documents absent online",
            "directory_url": COURTHOUSE_DIRECTORY_URL,
        },
        {
            "source_id": DIVORCE_JUDGMENT_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "divorce_judgment_orders",
            "authority": COURT_NAME,
            "url": DIVORCE_JUDGMENT_URL,
            "access_model": "case_number_order",
            "adds": ["imaged certified divorce judgments"],
            "gap": "requires a known case number and an available imaged judgment",
        },
        {
            "source_id": CORE_CIVIL_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "tentative_rulings",
            "authority": COURT_NAME,
            "url": TENTATIVE_RULINGS_URL,
            "access_model": "anonymous",
            "adds": [
                "full tentative-ruling text",
                "hearing date",
                "department",
                "case caption",
            ],
            "gap": "changing subset of matters with published tentative rulings",
            "existing_adapter": "tools/query_los_angeles_court.py",
        },
        {
            "source_id": SECOND_DISTRICT_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "california_appellate_case_information",
            "authority": "Judicial Branch of California",
            "url": APPELLATE_CASE_URL,
            "access_model": "anonymous",
            "adds": [
                "appellate docket",
                "trial-court case number for appealed matters",
                "briefs and opinions when available",
            ],
            "gap": "only matters that reach a California appellate court",
        },
        {
            "source_id": TRELLIS_SOURCE_ID,
            "record_kind": "source_route",
            "route_id": "trellis_los_angeles",
            "authority": "Trellis.Law",
            "url": TRELLIS_LA_URL,
            "access_model": "commercial_subscription_with_public_previews",
            "adds": [
                "party, attorney, judge, docket-entry, and filing-date search",
                "case summaries and selected documents",
                "tentative-ruling discovery",
            ],
            "gap": (
                "third-party aggregation; field freshness and document "
                "completeness require comparison with the court record"
            ),
        },
    ]


def _prepared_record(prepared: PreparedSearch) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "record_kind": "prepared_name_search",
        "source_url": CIVIL_INDEX_URL,
        "criteria": dict(prepared.criteria),
        "cart": {
            "items": [item.to_dict() for item in prepared.cart.items],
            "total_text": prepared.cart.total_text,
            "total_usd": prepared.cart.total_usd,
            "currency": "USD",
            "checkout_form_action": prepared.cart.checkout_form_action,
            "schema_fingerprint": prepared.cart.schema_fingerprint,
        },
        "checkout_url": prepared.checkout_url,
        "payment_handoff_url": prepared.search_redirect_url,
        "access_state": "court_cart_prepared",
    }


def _transaction_records(
    transactions: Iterable[GuestTransaction],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for transaction in transactions:
        identity = {
            "receipt_number": transaction.receipt_number,
            "transaction_date": transaction.transaction_date,
            "description": transaction.description,
            "action_id": transaction.action_id,
        }
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "guest_transaction",
                "source_internal_id": _fingerprint(identity),
                **transaction.to_dict(),
                "source_url": GUEST_INFORMATION_URL,
            }
        )
    return records


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    if args.command == "prepare":
        parameters = {
            "criteria": _query_criteria(
                first_name=args.first_name,
                last_name=args.last_name,
                company=args.company,
                filing_date_start=args.filing_date_start,
                filing_date_end=args.filing_date_end,
                remark=args.remark,
            )
        }
    elif args.command == "receipt":
        parameters = {
            "receipt_number": args.receipt_number,
            "retrieve": args.retrieve,
        }
    elif args.command == "parse-results":
        parameters = {
            "input_file": str(Path(args.input_file).resolve()),
            "source_url": args.source_url,
        }
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
        ),
    )


def _execute_command(
    args: argparse.Namespace,
    client: LANameIndexClient | Any | None,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        return PublicRecordsResult.success(
            query,
            source_records(),
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "parse-results":
        html = Path(args.input_file).read_text(encoding="utf-8")
        page = parse_results_html(html, source_url=args.source_url)
        return PublicRecordsResult.success(
            query,
            normalize_matches(page),
            raw_artifact_refs=[str(Path(args.input_file).resolve())],
            warnings=SOURCE_WARNINGS,
        )
    if client is None:
        raise AssertionError("client is required for network commands")
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            [client.probe()],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "prepare":
        criteria = query.query.to_dict()["parameters"]["criteria"]
        return PublicRecordsResult.success(
            query,
            [_prepared_record(client.prepare(criteria))],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "receipt":
        if args.retrieve:
            transaction, page = client.retrieve_receipt_search(
                args.receipt_number,
                args.last_four,
            )
            records = normalize_matches(page)
            for record in records:
                record["receipt_transaction"] = transaction.to_dict()
            return PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        guest = client.attach_receipt(args.receipt_number, args.last_four)
        if not guest.transactions:
            raise LANameIndexError(
                "receipt_not_attached",
                "The supplied guest receipt details did not attach a transaction",
                status=ResultStatus.RESTRICTED,
                category="receipt",
                details={
                    "receipt_number": args.receipt_number,
                    "no_valid_receipts": guest.no_valid_receipts,
                },
            )
        return PublicRecordsResult.success(
            query,
            _transaction_records(guest.transactions),
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: LANameIndexClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one CivilIndex operation and return a public-record envelope."""

    query = build_query(args)
    own_client = (
        client is None
        and args.command not in {"sources", "parse-results"}
    )
    source_client = client
    if own_client:
        source_client = LANameIndexClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(
                max_attempts=args.max_attempts,
                backoff_initial=args.retry_backoff,
            ),
        )
    try:
        result = _execute_command(args, source_client, query)
    except LANameIndexError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        source_error = LANameIndexError(
            "operation_failed",
            str(error),
            category="input_or_normalization",
        )
        result = PublicRecordsResult.failure(
            query,
            source_error.status,
            [source_error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if own_client and source_client is not None:
            source_client.close()

    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum attempts for retryable requests",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=0.25,
        help="Initial retry backoff in seconds",
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources_parser = subparsers.add_parser(
        "sources",
        help="List the paid index and distinct complementary routes",
    )
    _add_output(sources_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Probe live coverage, fees, form fields, and guest recovery",
    )
    _add_runtime_args(probe_parser)
    _add_output(probe_parser)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare a guest name search through the court cart boundary",
    )
    identity = prepare_parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--company", help="Company party name")
    identity.add_argument(
        "--last-name",
        help="Person last name; pair with --first-name",
    )
    prepare_parser.add_argument("--first-name", help="Person first name")
    prepare_parser.add_argument(
        "--filing-date-start",
        help="Optional filing start date (mm/dd/yyyy)",
    )
    prepare_parser.add_argument(
        "--filing-date-end",
        help="Optional filing end date (mm/dd/yyyy)",
    )
    prepare_parser.add_argument(
        "--remark",
        help="Optional source transaction remark (maximum 30 characters)",
    )
    _add_runtime_args(prepare_parser)
    _add_output(prepare_parser)

    receipt_parser = subparsers.add_parser(
        "receipt",
        help="Attach a guest receipt and optionally retrieve its civil search",
    )
    receipt_parser.add_argument("receipt_number")
    receipt_parser.add_argument(
        "last_four",
        help="Last four digits of the card used for the transaction",
    )
    receipt_parser.add_argument(
        "--retrieve",
        action="store_true",
        help="Retrieve and normalize the available civil search result",
    )
    _add_runtime_args(receipt_parser)
    _add_output(receipt_parser)

    parse_parser = subparsers.add_parser(
        "parse-results",
        help="Normalize a saved purchased CivilIndex result page",
    )
    parse_parser.add_argument("input_file")
    parse_parser.add_argument(
        "--source-url",
        default=CIVIL_INDEX_URL,
        help="Source URL associated with the saved page",
    )
    _add_output(parse_parser)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Los Angeles CivilIndex {args.command}",
        result_count=(
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        ),
    ):
        return
    print(json.dumps(payload, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())
