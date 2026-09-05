#!/usr/bin/env python3
"""Query Lane County property-account and tax-map source components.

The two official applications publish different native records:

* Property Account Information exposes an anonymous JSON search index and a
  session-backed account page with account, tax, receipt, and valuation data.
* Tax Map Search exposes map-lot/address and map-name locators whose document
  links resolve to official PDF tax-map images.

The adapter keeps assessor account labels, tax-map locator occurrences, and
tax-map document identities separate.  Omitted ``--limit`` values return every
row supplied by the selected source query.

Examples:
    uv run python tools/query_oregon_lane_property.py sources
    uv run python tools/query_oregon_lane_property.py search 0057313 \
      --source us-or-lane-property-account-information --field account
    uv run python tools/query_oregon_lane_property.py account 0057313
    uv run python tools/query_oregon_lane_property.py search 1605070001100 \
      --source us-or-lane-tax-maps --field map_lot
    uv run python tools/query_oregon_lane_property.py download-tax-map 326 \
      --destination /tmp/lane-tax-map-326.pdf
    uv run python tools/query_oregon_lane_property.py probe \
      --source us-or-lane-property-account-information
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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

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
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


ACCOUNT_SOURCE_ID = "us-or-lane-property-account-information"
TAX_MAP_SOURCE_ID = "us-or-lane-tax-maps"
SOURCE_IDS = (ACCOUNT_SOURCE_ID, TAX_MAP_SOURCE_ID)
LANE_PARCELS_SOURCE_ID = "us-or-lane-county-assessor-parcels"
LANE_SALES_SOURCE_ID = "us-or-lane-county-recent-property-sales"
LANE_RECORDER_SOURCE_ID = "us-or-lane-deeds-records"
LANE_RLID_SOURCE_ID = "us-or-lane-rlid-property"

COUNTY_GEOID = "41039"
COUNTY_NAME = "Lane County, Oregon"
STATE_CODE = "OR"
STATE_FIPS = "41"
PUBLISHER = "Lane County Assessment and Taxation"

APP_HOST = "apps.lanecounty.org"
ACCOUNT_ROOT_URL = "https://apps.lanecounty.org/PropertyAccountInformation/"
ACCOUNT_API_URL = f"{ACCOUNT_ROOT_URL}api"
ACCOUNT_DETAIL_URL = f"{ACCOUNT_ROOT_URL}Account/{{account}}"
TAX_MAP_SEARCH_URL = "https://apps.lanecounty.org/TaxMap/Search.aspx"
TAX_MAP_DOCUMENT_URL = "https://apps.lanecounty.org/TaxMap/ViewFile.aspx"

TAX_MAP_ORDER_URL = (
    "https://www.lanecountyor.gov/government/county_departments/"
    "assessment___taxation/tax_maps/ordering_tax_maps"
)
LANE_CARTOGRAPHY_URL = (
    "https://www.lanecountyor.gov/government/county_departments/"
    "assessment___taxation/cartography"
)

ACCOUNT_SENTINEL = "0057313"
MAP_TAXLOT_SENTINEL = "1605070001100"
TAX_MAP_DOCUMENT_SENTINEL = "326"

ACCOUNT_SEARCH_ROUTES = {
    "account": "accountnumbersearch",
    "map_taxlot": "maptaxlotsearch",
    "address": "propertyaddresssearch",
    "name": "taxpayernamesearch",
}
TAX_MAP_SEARCH_FIELDS = frozenset({"map_lot", "address", "map_name"})

CURSOR_PREFIX = "oregon-lane-property:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
OUTPUT_SCHEMA_VERSION = "oregon-lane-property-sources/1.0"


JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Lane County",
    metadata={"state_fips": STATE_FIPS},
)

SOURCE_METADATA = {
    ACCOUNT_SOURCE_ID: SourceMetadata(
        source_id=ACCOUNT_SOURCE_ID,
        name="Lane County Property Account Information",
        source_role=(
            "county_assessor_property_account_tax_receipt_and_valuation_detail"
        ),
        base_url=ACCOUNT_ROOT_URL,
        dataset_id="lane-county-property-account-information",
        metadata={
            "publisher": PUBLISHER,
            "county_geoid": COUNTY_GEOID,
            "platform_family": "lane_county_mvc_and_webforms_property_portal",
            "native_search_fields": list(ACCOUNT_SEARCH_ROUTES),
            "representations": {
                "search_index": "anonymous_json",
                "account_detail": "anonymous_cookie_session_html",
                "tax_statements": "linked_account_documents",
            },
            "join_keys": {
                LANE_PARCELS_SOURCE_ID: ["account_number", "map_taxlot"],
                LANE_SALES_SOURCE_ID: ["account_number", "map_taxlot"],
                TAX_MAP_SOURCE_ID: ["map_taxlot", "tax_map_document_id"],
                LANE_RECORDER_SOURCE_ID: ["instrument_number"],
            },
        },
    ),
    TAX_MAP_SOURCE_ID: SourceMetadata(
        source_id=TAX_MAP_SOURCE_ID,
        name="Lane County Tax Map Search",
        source_role="county_assessor_tax_map_locator_and_pdf_images",
        base_url=TAX_MAP_SEARCH_URL,
        dataset_id="lane-county-tax-map-search",
        metadata={
            "publisher": PUBLISHER,
            "county_geoid": COUNTY_GEOID,
            "platform_family": "lane_county_webforms_tax_map_portal",
            "native_search_fields": sorted(TAX_MAP_SEARCH_FIELDS),
            "representations": {
                "search_result": "map_lot_or_map_name_locator",
                "document": "official_pdf_tax_map_image",
            },
            "official_bulk_complement": {
                "url": TAX_MAP_ORDER_URL,
                "relationship": (
                    "full_image_set_or_daily_weekly_monthly_update_subscription"
                ),
            },
            "join_keys": {
                ACCOUNT_SOURCE_ID: ["map_taxlot", "tax_map_document_id"],
                LANE_PARCELS_SOURCE_ID: ["map_taxlot", "map_number"],
            },
        },
    ),
}


@dataclass(frozen=True)
class TextPage:
    text: str
    source_url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class BinaryDocument:
    content: bytes
    source_url: str
    headers: Mapping[str, str]


class SourceSelectionError(ValueError):
    """A caller selection or continuation does not match the source contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
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
            category="selection_or_continuation",
            retryable=False,
            details=self.details,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Tag):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    normalized = " ".join(text.replace("\xa0", " ").split())
    return normalized or None


def _multiline(value: Tag | None) -> str | None:
    if not isinstance(value, Tag):
        return None
    parts = [
        " ".join(part.replace("\xa0", " ").split())
        for part in value.get_text("\n").splitlines()
    ]
    return "\n".join(part for part in parts if part) or None


def _money(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    negative = text.startswith("(") and text.endswith(")")
    candidate = text.strip("()").replace("$", "").replace(",", "")
    try:
        number = Decimal(candidate)
    except InvalidOperation:
        return None
    if negative:
        number = -number
    return format(number, "f")


def _date_iso(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for pattern in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _official_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != APP_HOST:
        raise SourceSchemaError(
            "Lane County application returned an unexpected source URL",
            url=value,
        )
    return value


def _headers(response: Any) -> dict[str, str]:
    return {
        str(key).casefold(): str(value)
        for key, value in dict(getattr(response, "headers", {})).items()
    }


def _retry_after(response: Any) -> float | None:
    value = _headers(response).get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class LaneCountyPropertyClient:
    """Retrying client that retains the anonymous application cookie session."""

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
        data: Mapping[str, Any] | None = None,
        accept: str,
        referer: str | None = None,
    ) -> Any:
        official_url = _official_url(url)
        last_error: requests.RequestException | None = None
        request_headers = {**self.headers, "Accept": accept}
        if referer:
            request_headers["Referer"] = _official_url(referer)
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    official_url,
                    data=data,
                    headers=request_headers,
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
                _official_url(str(getattr(redirect, "url", official_url)))
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                response.close()
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            if status == 429:
                response.close()
                raise RateLimitedHTTPError(status, url=official_url)
            if status in {401, 403}:
                response.close()
                raise RestrictedHTTPError(status, url=official_url)
            if status in {404, 410}:
                response.close()
                raise SourceChangedHTTPError(status, url=official_url)
            if status < 200 or status >= 300:
                response.close()
                raise HTTPStatusError(status, url=official_url)
            return response
        raise TransportError(
            "Lane County application request failed",
            url=official_url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def _text(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        accept: str = "text/html,application/xhtml+xml",
        referer: str | None = None,
    ) -> TextPage:
        response = self._request(
            method,
            url,
            data=data,
            accept=accept,
            referer=referer,
        )
        try:
            response_headers = _headers(response)
            content_type = response_headers.get("content-type", "").casefold()
            if "html" not in content_type:
                raise SourceSchemaError(
                    "Lane County application returned non-HTML content",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": content_type},
                )
            return TextPage(
                text=str(response.text),
                source_url=str(getattr(response, "url", url)),
                headers=response_headers,
            )
        finally:
            response.close()

    def account_search(
        self,
        field: str,
        value: str,
    ) -> tuple[Any, str]:
        route = ACCOUNT_SEARCH_ROUTES[field]
        url = f"{ACCOUNT_API_URL}/{route}/{quote(value, safe='')}"
        response = self._request(
            "GET",
            url,
            accept="application/json,text/javascript",
            referer=ACCOUNT_ROOT_URL,
        )
        try:
            content_type = _headers(response).get("content-type", "").casefold()
            if "json" not in content_type:
                raise SourceSchemaError(
                    "Lane property-account search returned non-JSON content",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": content_type},
                )
            try:
                payload = response.json()
            except (TypeError, ValueError) as error:
                raise SourceSchemaError(
                    "Lane property-account search returned malformed JSON",
                    url=str(getattr(response, "url", url)),
                ) from error
            return payload, str(getattr(response, "url", url))
        finally:
            response.close()

    def account_detail(self, account: str) -> TextPage:
        landing = self._text("GET", ACCOUNT_ROOT_URL)
        detail_url = ACCOUNT_DETAIL_URL.format(account=quote(account, safe=""))
        detail = self._text(
            "GET",
            detail_url,
            referer=landing.source_url,
        )
        parsed = urlparse(detail.source_url)
        expected_suffix = f"/account/{account}".casefold()
        if not parsed.path.casefold().rstrip("/").endswith(expected_suffix):
            raise SourceSchemaError(
                "Lane property-account detail redirected away from the account",
                url=detail.source_url,
                details={"requested_account": account},
            )
        return detail

    def tax_map_search(
        self,
        field: str,
        value: str,
        *,
        city: str | None = None,
    ) -> TextPage:
        form = self._text("GET", TAX_MAP_SEARCH_URL)
        if field == "map_name":
            mode_data = {
                **parse_webforms_hidden_fields(form.text, form.source_url),
                "__EVENTTARGET": "SearchOption$1",
                "__EVENTARGUMENT": "",
                "SearchOption": "1",
            }
            form = self._text(
                "POST",
                TAX_MAP_SEARCH_URL,
                data=mode_data,
                referer=form.source_url,
            )
            search_data = {
                **parse_webforms_hidden_fields(form.text, form.source_url),
                "SearchOption": "1",
                "MapName": value,
                "SearchButton": "Search",
            }
        else:
            search_data = {
                **parse_webforms_hidden_fields(form.text, form.source_url),
                "SearchOption": "0",
                "Address": value if field == "address" else "",
                "City": city or "",
                "MapLot": value if field == "map_lot" else "",
                "SearchButton": "Search",
            }
        return self._text(
            "POST",
            TAX_MAP_SEARCH_URL,
            data=search_data,
            referer=form.source_url,
        )

    def tax_map_document(self, document_id: str) -> BinaryDocument:
        url = f"{TAX_MAP_DOCUMENT_URL}?{urlencode({'type': 'TM', 'id': document_id})}"
        response = self._request(
            "GET",
            url,
            accept="application/pdf",
            referer=TAX_MAP_SEARCH_URL,
        )
        try:
            response_headers = _headers(response)
            content_type = response_headers.get("content-type", "").casefold()
            content = bytes(response.content)
            if "application/pdf" not in content_type or not content.startswith(
                b"%PDF-"
            ):
                raise SourceSchemaError(
                    "Lane tax-map document is not an official PDF response",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": content_type},
                )
            return BinaryDocument(
                content=content,
                source_url=str(getattr(response, "url", url)),
                headers=response_headers,
            )
        finally:
            response.close()


def parse_webforms_hidden_fields(html: str, source_url: str) -> dict[str, str]:
    """Return the current ASP.NET state fields needed for the next form post."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="Form1")
    if not isinstance(form, Tag):
        raise SourceSchemaError(
            "Lane tax-map search form changed",
            url=source_url,
        )
    fields: dict[str, str] = {}
    for element in form.select('input[type="hidden"][name]'):
        name = _clean(element.get("name"))
        if name and name.startswith("__"):
            fields[name] = str(element.get("value") or "")
    for required in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        if required not in fields:
            raise SourceSchemaError(
                "Lane tax-map WebForms state changed",
                url=source_url,
                details={"missing_field": required},
            )
    return fields


def _account_refs(
    account: str,
    *,
    occurrence_id: str | None = None,
) -> tuple[str, str]:
    canonical_ref = canonical_property_ref(
        ACCOUNT_SOURCE_ID,
        COUNTY_GEOID,
        "property_account",
        account,
    )
    evidence_ref = canonical_property_ref(
        ACCOUNT_SOURCE_ID,
        COUNTY_GEOID,
        "property_account_search_index",
        occurrence_id or account,
    )
    return canonical_ref, evidence_ref


def parse_account_search(
    payload: Any,
    source_url: str,
) -> list[dict[str, Any]]:
    """Normalize the verified Lane County JSON account-search representation."""

    if not isinstance(payload, list):
        raise SourceSchemaError(
            "Lane property-account search root is not a JSON list",
            url=source_url,
        )
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(payload):
        if not isinstance(raw, Mapping):
            raise SourceSchemaError(
                "Lane property-account search row is not an object",
                url=source_url,
                details={"row_index": index},
            )
        account = _clean(raw.get("AccountNumber"))
        if account is None:
            raise SourceSchemaError(
                "Lane property-account search row has no account identity",
                url=source_url,
                details={"row_index": index},
            )
        map_taxlot = _clean(raw.get("MapTaxLot"))
        taxpayer_name = _clean(raw.get("TaxPayer"))
        owner_index_name = _clean(raw.get("Owner"))
        situs_address = _clean(raw.get("SitusAddress"))
        occurrence_fingerprint = sha256_fingerprint(
            {
                'map_taxlot': map_taxlot,
                'taxpayer_name': taxpayer_name,
                'owner_index_name': owner_index_name,
                'situs_address': situs_address,
            }
        )
        occurrence_id = f"{account}:{occurrence_fingerprint[:16]}"
        canonical_ref, evidence_ref = _account_refs(
            account,
            occurrence_id=occurrence_id,
        )
        record = {
            "canonical_ref": canonical_ref,
            "evidence_ref": evidence_ref,
            "source_id": ACCOUNT_SOURCE_ID,
            "source_url": source_url,
            "record_kind": "property_account_search_index",
            "representation_kind": "anonymous_json_search_index",
            "source_record_id": occurrence_id,
            "source_account_id": account,
            "account_number": account,
            "map_taxlot": map_taxlot,
            "taxpayer_name": taxpayer_name,
            "owner_index_name": owner_index_name,
            "situs_address": situs_address,
            "account_detail_url": ACCOUNT_DETAIL_URL.format(
                account=quote(account, safe="")
            ),
            "native_fields": dict(raw),
            "join_candidates": {
                LANE_PARCELS_SOURCE_ID: {
                    "account_number": account,
                    "map_taxlot": map_taxlot,
                    "relationship": "parcel_owner_geometry_and_zoning_complement",
                },
                LANE_SALES_SOURCE_ID: {
                    "account_number": account,
                    "map_taxlot": map_taxlot,
                    "relationship": "rolling_sale_analysis_complement",
                },
                TAX_MAP_SOURCE_ID: {
                    "map_taxlot": map_taxlot,
                    "relationship": "tax_map_locator",
                },
            },
        }
        records.append(record)
    return records


def _account_information(soup: BeautifulSoup, source_url: str) -> dict[str, str]:
    table = soup.select_one("table.AccountInformationTable")
    if not isinstance(table, Tag):
        raise SourceSchemaError(
            "Lane property-account information table changed",
            url=source_url,
        )
    values: dict[str, str] = {}
    for row in table.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = _clean(cells[0])
        if label is None or label == "Owner(s)":
            continue
        value = _multiline(cells[1])
        if value is not None:
            values[label] = value
    if "Account Number" not in values:
        raise SourceSchemaError(
            "Lane property-account detail has no account identity",
            url=source_url,
        )
    return values


def _receipt_history(soup: BeautifulSoup) -> tuple[list[str], list[dict[str, Any]]]:
    table = soup.select_one('table[id$="_RadGrid1_ctl00"]')
    if not isinstance(table, Tag):
        return [], []
    headers = [
        _clean(cell) or ""
        for cell in table.select("thead tr:first-child th")
    ]
    expected = ["Date", "Amount Received", "Tax", "Discount", "Interest"]
    if headers != expected:
        return headers, []
    receipts: list[dict[str, Any]] = []
    for row in table.select("tbody tr"):
        values = [_clean(cell) for cell in row.find_all("td", recursive=False)]
        if len(values) != len(expected):
            continue
        receipts.append(
            {
                "date_raw": values[0],
                "date_iso": _date_iso(values[0]),
                "amount_received_raw": values[1],
                "amount_received": _money(values[1]),
                "tax_raw": values[2],
                "tax": _money(values[2]),
                "discount_raw": values[3],
                "discount": _money(values[3]),
                "interest_raw": values[4],
                "interest": _money(values[4]),
            }
        )
    return headers, receipts


def _valuation_history(
    soup: BeautifulSoup,
    source_url: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    table = soup.select_one('table[id$="_valuesGrid_ctl00_DataZone_DT"]')
    if not isinstance(table, Tag):
        return [], []
    year_values = [_clean(cell) for cell in table.select("thead th")]
    if not year_values or any(
        value is None or not value.isdigit() for value in year_values
    ):
        raise SourceSchemaError(
            "Lane property-account valuation years changed",
            url=source_url,
        )
    years = [int(value) for value in year_values if value is not None]
    row_labels = []
    outer = soup.select_one('table[id$="_valuesGrid_OT"]')
    if isinstance(outer, Tag):
        for cell in outer.select("td.rpgRowHeaderField"):
            first = next(cell.stripped_strings, "")
            if first:
                row_labels.append(" ".join(first.split()))
    body = table.find("tbody")
    value_rows = (
        [
            [_clean(cell) for cell in row.find_all("td", recursive=False)]
            for row in body.find_all("tr", recursive=False)
        ]
        if isinstance(body, Tag)
        else []
    )
    if len(row_labels) != len(value_rows) or any(
        len(row) != len(years) for row in value_rows
    ):
        raise SourceSchemaError(
            "Lane property-account valuation matrix changed",
            url=source_url,
            details={
                "year_count": len(years),
                "label_count": len(row_labels),
                "value_row_count": len(value_rows),
            },
        )
    history: list[dict[str, Any]] = []
    field_names = {
        "Assessed Value": "assessed_value",
        "Maximum Assessed Value": "maximum_assessed_value",
        "Real Market Value": "real_market_value",
    }
    for column, year in enumerate(years):
        record: dict[str, Any] = {"tax_year": year}
        raw_values: dict[str, Any] = {}
        for row_index, label in enumerate(row_labels):
            raw_value = value_rows[row_index][column]
            raw_values[label] = raw_value
            record[field_names.get(label, label)] = _money(raw_value)
        record["raw_values"] = raw_values
        history.append(record)
    return row_labels, history


def _link_kind(text: str, href: str) -> str | None:
    joined = f"{text} {href}".casefold()
    if "current tax statement" in joined:
        return "current_tax_statement"
    if "prior year tax statement" in joined or "viewstatement" in joined:
        return "prior_tax_statement_series"
    if "make a tax payment" in joined or "atepay" in joined:
        return "tax_payment"
    if "view the tax map" in joined or "/taxmap/viewfile" in joined:
        return "tax_map_pdf"
    if "appraisal information" in joined:
        return "subscribed_appraisal_information"
    if "property description card" in joined:
        return "subscribed_property_description_card"
    if "additional property information" in joined:
        return "additional_property_information"
    return None


def _related_links(
    soup: BeautifulSoup,
    account: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in soup.find_all("a", href=True):
        text = _clean(anchor) or ""
        href = str(anchor.get("href") or "")
        kind = _link_kind(text, href)
        if kind is None:
            continue
        resolved_url: str | None
        if kind == "current_tax_statement":
            resolved_url = urljoin(
                ACCOUNT_ROOT_URL,
                f"ViewCurrentStatement/{quote(account, safe='')}",
            )
        elif kind == "prior_tax_statement_series":
            match = re.search(r"showStatementDetail\([^,]+,\s*(\d{4})\)", href)
            resolved_url = (
                urljoin(
                    ACCOUNT_ROOT_URL,
                    f"ViewStatement/{quote(account, safe='')}/{match.group(1)}",
                )
                if match
                else None
            )
        elif href.casefold().startswith("javascript:"):
            resolved_url = None
        else:
            resolved_url = urljoin(ACCOUNT_ROOT_URL, href)
        identity = (kind, resolved_url or href)
        if identity in seen:
            continue
        seen.add(identity)
        record = {
            "representation_kind": kind,
            "label": text or None,
            "native_href": href,
            "url": resolved_url,
        }
        if kind == "tax_map_pdf" and resolved_url:
            values = parse_qs(urlparse(resolved_url).query)
            record["tax_map_document_id"] = (
                values.get("id", [None])[0]
            )
            record["related_source_id"] = TAX_MAP_SOURCE_ID
        elif kind in {
            "subscribed_appraisal_information",
            "subscribed_property_description_card",
        }:
            record["related_source_id"] = LANE_RLID_SOURCE_ID
        records.append(record)
    return records


def parse_account_detail(
    html: str,
    source_url: str,
    *,
    expected_account: str | None = None,
    search_record: (
        Mapping[str, Any] | Sequence[Mapping[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """Normalize one session-rendered Lane County property-account page."""

    soup = BeautifulSoup(html, "html.parser")
    values = _account_information(soup, source_url)
    account = values["Account Number"].strip()
    if expected_account and account != expected_account:
        raise SourceSchemaError(
            "Lane property-account detail returned a different account",
            url=source_url,
            details={"requested": expected_account, "returned": account},
        )
    canonical_ref, _ = _account_refs(account)
    detail_evidence_ref = canonical_property_ref(
        ACCOUNT_SOURCE_ID,
        COUNTY_GEOID,
        "property_account_detail",
        account,
    )
    receipt_headers, receipts = _receipt_history(soup)
    valuation_labels, valuation_history = _valuation_history(soup, source_url)
    links = _related_links(soup, account)
    map_taxlot = values.get("Map and Tax Lot #")
    property_class_value = _clean(values.get("Prop Class"))
    property_class_parts = (
        property_class_value.split(" ", 1) if property_class_value else []
    )
    remarks = _clean(soup.select_one("#MainContentPlaceHolder_RemarksLabel"))
    if isinstance(search_record, Mapping):
        search_records = [search_record]
    elif isinstance(search_record, Sequence):
        search_records = [
            record
            for record in search_record
            if isinstance(record, Mapping)
            and _clean(record.get("account_number")) == account
        ]
    else:
        search_records = []
    search_observations = [
        {
            "evidence_ref": record.get("evidence_ref"),
            "source_record_id": record.get("source_record_id"),
            "account_number": _clean(record.get("account_number")),
            "map_taxlot": _clean(record.get("map_taxlot")),
            "taxpayer_name": _clean(record.get("taxpayer_name")),
            "owner_index_name": _clean(record.get("owner_index_name")),
            "situs_address": _clean(record.get("situs_address")),
        }
        for record in search_records
    ]
    detail_taxpayer = _clean(values.get("Tax Payer"))
    taxpayer_names = list(
        dict.fromkeys(
            name
            for name in [
                detail_taxpayer,
                *(
                    observation["taxpayer_name"]
                    for observation in search_observations
                ),
            ]
            if name
        )
    )
    owner_index_names = list(
        dict.fromkeys(
            observation["owner_index_name"]
            for observation in search_observations
            if observation["owner_index_name"]
        )
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": detail_evidence_ref,
        "source_id": ACCOUNT_SOURCE_ID,
        "source_url": source_url,
        "record_kind": "property_account_detail",
        "representation_kind": "anonymous_session_html",
        "source_record_id": account,
        "account_number": account,
        "map_taxlot": map_taxlot,
        "taxpayer_name": detail_taxpayer or (taxpayer_names[0] if taxpayer_names else None),
        "taxpayer_names": taxpayer_names,
        "owner_index_name": owner_index_names[0] if owner_index_names else None,
        "owner_index_names": owner_index_names,
        "search_index_observations": search_observations,
        "situs_address": values.get("Situs Address"),
        "mailing_address": values.get("Mailing Address"),
        "acreage": values.get("Acreage"),
        "tax_code_area": values.get("TCA"),
        "property_class": property_class_parts[0] if property_class_parts else None,
        "property_class_description": (
            property_class_parts[1]
            if len(property_class_parts) > 1
            else None
        ),
        "remarks": remarks,
        "recent_receipts": receipts,
        "valuation_history": valuation_history,
        "related_representations": links,
        "raw_account_fields": values,
        "source_response_schema_fingerprint": sha256_fingerprint(
            {
                "account_labels": sorted(values),
                "receipt_headers": receipt_headers,
                "valuation_labels": valuation_labels,
                "related_representation_kinds": sorted(
                    {
                        str(link["representation_kind"])
                        for link in links
                    }
                ),
            }
        ),
        "join_candidates": {
            LANE_PARCELS_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": map_taxlot,
                "relationship": "parcel_owner_geometry_and_zoning_complement",
            },
            LANE_SALES_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": map_taxlot,
                "relationship": "rolling_sale_analysis_complement",
            },
            TAX_MAP_SOURCE_ID: {
                "map_taxlot": map_taxlot,
                "document_ids": [
                    link.get("tax_map_document_id")
                    for link in links
                    if link.get("tax_map_document_id")
                ],
                "relationship": "tax_map_locator_and_document",
            },
        },
    }


def _table_headers(table: Tag) -> list[str]:
    first_row = table.find("tr")
    if not isinstance(first_row, Tag):
        return []
    return [_clean(cell) or "" for cell in first_row.find_all(["th", "td"])]


def parse_tax_map_search(
    html: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Normalize tax-map locator rows without merging them into PDF identity."""

    soup = BeautifulSoup(html, "html.parser")
    caption = _clean(soup.select_one("#Caption"))
    if caption and "no records matching your search" in caption.casefold():
        return []
    table = soup.select_one("#TMList")
    if not isinstance(table, Tag):
        raise SourceSchemaError(
            "Lane tax-map search returned neither results nor an explicit empty",
            url=source_url,
            details={"caption": caption},
        )
    headers = _table_headers(table)
    expected_schemas = {
        (
            "Address",
            "City",
            "Map Lot",
            "Map Name",
            "Image",
            "Download Time @ 56 kbps",
        ),
        ("Map Name", "Image", "Download Time @ 56 kbps"),
    }
    if tuple(headers) not in expected_schemas:
        raise SourceSchemaError(
            "Lane tax-map result columns changed",
            url=source_url,
            details={"headers": headers},
        )
    records: list[dict[str, Any]] = []
    rows = table.find_all("tr")
    for position, row in enumerate(rows[1:], start=1):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(headers):
            continue
        native = {
            header: _clean(cell)
            for header, cell in zip(headers, cells, strict=True)
        }
        link = row.find("a", href=True)
        if not isinstance(link, Tag):
            raise SourceSchemaError(
                "Lane tax-map result row has no document link",
                url=source_url,
                details={"position": position},
            )
        document_url = urljoin(source_url, str(link.get("href")))
        query = parse_qs(urlparse(document_url).query)
        document_id = _clean(query.get("id", [None])[0])
        document_type = _clean(query.get("type", [None])[0])
        if document_id is None or document_type != "TM":
            raise SourceSchemaError(
                "Lane tax-map document identity changed",
                url=document_url,
                details={"position": position},
            )
        map_taxlot = native.get("Map Lot")
        map_name = native.get("Map Name")
        occurrence_id = f"{map_taxlot or map_name}:{document_id}"
        canonical_ref = canonical_property_ref(
            TAX_MAP_SOURCE_ID,
            COUNTY_GEOID,
            "tax_map_locator",
            occurrence_id,
        )
        document_ref = canonical_property_ref(
            TAX_MAP_SOURCE_ID,
            COUNTY_GEOID,
            "tax_map_document",
            document_id,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": TAX_MAP_SOURCE_ID,
                "source_url": source_url,
                "record_kind": "tax_map_locator",
                "representation_kind": "webforms_search_result",
                "source_record_id": occurrence_id,
                "address": native.get("Address"),
                "city": native.get("City"),
                "map_taxlot": map_taxlot,
                "map_name": map_name,
                "tax_map_document_id": document_id,
                "tax_map_document_ref": document_ref,
                "tax_map_document_url": document_url,
                "estimated_download_time_at_56kbps": native.get(
                    "Download Time @ 56 kbps"
                ),
                "native_fields": native,
                "source_response_schema_fingerprint": sha256_fingerprint(
                    {"headers": headers}
                ),
                "join_candidates": {
                    ACCOUNT_SOURCE_ID: {
                        "map_taxlot": map_taxlot,
                        "tax_map_document_id": document_id,
                        "relationship": "assessment_account_complement",
                    },
                    LANE_PARCELS_SOURCE_ID: {
                        "map_taxlot": map_taxlot,
                        "map_number": map_name,
                        "relationship": "parcel_geometry_complement",
                    },
                },
            }
        )
    if caption:
        count_match = re.search(r"(\d[\d,]*)\s+records?\s+selected", caption, re.I)
        if count_match and int(count_match.group(1).replace(",", "")) != len(records):
            raise SourceSchemaError(
                "Lane tax-map reported count differs from rendered rows",
                url=source_url,
                details={
                    "reported_count": int(
                        count_match.group(1).replace(",", "")
                    ),
                    "rendered_count": len(records),
                },
            )
    return records


def _record_anchor(record: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {
            "canonical_ref": record.get("canonical_ref"),
            "evidence_ref": record.get("evidence_ref"),
            "source_record_id": record.get("source_record_id"),
        }
    )


def _encode_cursor(state: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json({"v": CURSOR_VERSION, **dict(state)}).encode("utf-8")
    ).decode("ascii")
    return f"{CURSOR_PREFIX}{encoded.rstrip('=')}"


def _decode_cursor(value: str) -> dict[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise SourceSelectionError(
            "cursor_source_mismatch",
            "continuation is not a Lane County property cursor",
            status=ResultStatus.SOURCE_CHANGED,
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        state = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise SourceSelectionError(
            "cursor_invalid",
            "Lane County property continuation is malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    required = {"v", "source_id", "query_fingerprint", "offset", "anchor", "total"}
    if not isinstance(state, dict) or not required.issubset(state):
        raise SourceSelectionError(
            "cursor_invalid",
            "Lane County property continuation is incomplete",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if state["v"] != CURSOR_VERSION:
        raise SourceSelectionError(
            "cursor_version_changed",
            "Lane County property continuation version is unsupported",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if (
        not isinstance(state["offset"], int)
        or state["offset"] < 1
        or not isinstance(state["total"], int)
        or state["total"] < state["offset"]
    ):
        raise SourceSelectionError(
            "cursor_invalid",
            "Lane County property continuation boundary is invalid",
            status=ResultStatus.SOURCE_CHANGED,
        )
    return state


def _window_records(
    records: Sequence[Mapping[str, Any]],
    *,
    source_id: str,
    query_fingerprint: str,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    start = 0
    if cursor:
        state = _decode_cursor(cursor)
        if state["source_id"] != source_id:
            raise SourceSelectionError(
                "cursor_source_mismatch",
                "continuation belongs to a different Lane County source",
                status=ResultStatus.SOURCE_CHANGED,
            )
        if state["query_fingerprint"] != query_fingerprint:
            raise SourceSelectionError(
                "cursor_query_mismatch",
                "continuation belongs to a different Lane County query",
                status=ResultStatus.SOURCE_CHANGED,
            )
        if state["total"] != len(records):
            raise SourceSelectionError(
                "cursor_result_set_changed",
                "Lane County result count changed before continuation",
                status=ResultStatus.SOURCE_CHANGED,
                details={
                    "prior_total": state["total"],
                    "current_total": len(records),
                },
            )
        start = state["offset"]
        if start > len(records) or _record_anchor(records[start - 1]) != state["anchor"]:
            raise SourceSelectionError(
                "cursor_anchor_changed",
                "Lane County continuation boundary record changed",
                status=ResultStatus.SOURCE_CHANGED,
            )
    end = len(records) if limit is None else min(len(records), start + limit)
    selected = [dict(record) for record in records[start:end]]
    coverage = {
        "source_query_record_count": len(records),
        "returned_record_count": len(selected),
        "start_offset": start,
        "end_offset": end,
        "complete_for_selected_query": end == len(records),
        "source_returned_single_unpaged_result_set": True,
    }
    for record in selected:
        record["retrieval_coverage"] = coverage
    next_cursor = None
    if end < len(records):
        next_cursor = _encode_cursor(
            {
                "source_id": source_id,
                "query_fingerprint": query_fingerprint,
                "offset": end,
                "anchor": _record_anchor(records[end - 1]),
                "total": len(records),
            }
        )
    return selected, next_cursor


def _source_record(source_id: str) -> dict[str, Any]:
    source = SOURCE_METADATA[source_id].to_dict()
    if source_id == ACCOUNT_SOURCE_ID:
        source["observed_contract"] = {
            "observed_at": "2026-07-30",
            "search_routes": dict(ACCOUNT_SEARCH_ROUTES),
            "detail_session_prerequisite": "anonymous_landing_cookie_and_referer",
            "sentinel_account": ACCOUNT_SENTINEL,
            "account_detail_sections": [
                "account_information",
                "remarks",
                "recent_receipts",
                "valuation_history",
                "related_representations",
            ],
        }
    else:
        source["observed_contract"] = {
            "observed_at": "2026-07-30",
            "search_modes": ["location", "map_name"],
            "search_fields": sorted(TAX_MAP_SEARCH_FIELDS),
            "sentinel_map_taxlot": MAP_TAXLOT_SENTINEL,
            "sentinel_document_id": TAX_MAP_DOCUMENT_SENTINEL,
            "document_media_type": "application/pdf",
        }
    return source


def sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [
            _source_record(ACCOUNT_SOURCE_ID),
            _source_record(TAX_MAP_SOURCE_ID),
        ],
        "source_relationships": [
            {
                "left": ACCOUNT_SOURCE_ID,
                "right": TAX_MAP_SOURCE_ID,
                "relationship": "account_to_tax_map_locator",
                "join_keys": ["map_taxlot", "tax_map_document_id"],
                "independent_corroboration": False,
            },
            {
                "left": ACCOUNT_SOURCE_ID,
                "right": LANE_PARCELS_SOURCE_ID,
                "relationship": "same_assessor_system_complement",
                "join_keys": ["account_number", "map_taxlot"],
                "independent_corroboration": False,
            },
            {
                "left": ACCOUNT_SOURCE_ID,
                "right": LANE_RECORDER_SOURCE_ID,
                "relationship": "recorded_document_verification_route",
                "join_keys": ["instrument_number"],
            },
        ],
        "official_complements": [
            {
                "source_id": LANE_PARCELS_SOURCE_ID,
                "adds": "parcel geometry, owner mailing, zoning, and planning fields",
            },
            {
                "source_id": LANE_SALES_SOURCE_ID,
                "adds": "rolling three-year sale-analysis rows and deed references",
            },
            {
                "source_id": LANE_RECORDER_SOURCE_ID,
                "adds": "recorded instruments and copy or certification routes",
            },
            {
                "source_id": LANE_RLID_SOURCE_ID,
                "adds": "subscribed appraisal and property-description cards",
            },
            {
                "url": TAX_MAP_ORDER_URL,
                "adds": (
                    "official full tax-map image set and update-subscription route"
                ),
            },
            {
                "url": LANE_CARTOGRAPHY_URL,
                "adds": "official tax-map purpose and cadastral context",
            },
        ],
    }


def _query(
    source_id: str,
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: SourceSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
    )


def _schema_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    source_error = SourceSchemaError(
        str(error),
        url=query.source.base_url or "https://apps.lanecounty.org/",
    )
    return failure_result(query, source_error)


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def _validate_search_args(args: argparse.Namespace) -> None:
    value = _clean(args.query)
    if value is None:
        raise SourceSelectionError("empty_query", "search value must not be blank")
    if args.limit is not None and args.limit <= 0:
        raise SourceSelectionError(
            "invalid_limit",
            "--limit must be a positive integer when supplied",
        )
    if args.source == ACCOUNT_SOURCE_ID:
        if args.field not in ACCOUNT_SEARCH_ROUTES:
            raise SourceSelectionError(
                "unsupported_field",
                "property-account search fields are account, map_taxlot, address, name",
            )
        if args.city:
            raise SourceSelectionError(
                "city_not_applicable",
                "--city applies only to tax-map address search",
            )
    else:
        if args.field not in TAX_MAP_SEARCH_FIELDS:
            raise SourceSelectionError(
                "unsupported_field",
                "tax-map search fields are map_lot, address, map_name",
            )
        if args.city and args.field != "address":
            raise SourceSelectionError(
                "city_not_applicable",
                "--city applies only to tax-map address search",
            )


def _execute_search(
    args: argparse.Namespace,
    client: LaneCountyPropertyClient | Any,
) -> PublicRecordsResult:
    _validate_search_args(args)
    value = _clean(args.query)
    assert value is not None
    parameters = {
        "field": args.field,
        "value": value,
        "city": _clean(args.city),
        "completeness": (
            "all_source_returned_rows"
            if args.limit is None
            else "explicit_caller_window"
        ),
    }
    query = _query(
        args.source,
        "search",
        parameters=parameters,
        limit=args.limit,
        cursor=args.cursor,
    )
    fingerprint = sha256_fingerprint(
        {"source_id": args.source, **parameters}
    )
    if args.source == ACCOUNT_SOURCE_ID:
        raw, source_url = client.account_search(args.field, value)
        records = parse_account_search(raw, source_url)
        warning = (
            "Taxpayer and owner are distinct assessor index labels; neither is "
            "a recorded-title determination."
        )
    else:
        page = client.tax_map_search(args.field, value, city=args.city)
        records = parse_tax_map_search(page.text, page.source_url)
        warning = (
            "Tax-map locators and PDFs are assessment cartography, distinct "
            "from recorded title instruments and surveyed legal boundaries."
        )
    selected, next_cursor = _window_records(
        records,
        source_id=args.source,
        query_fingerprint=fingerprint,
        limit=args.limit,
        cursor=args.cursor,
    )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        warnings=[warning],
    )


def _execute_account(
    args: argparse.Namespace,
    client: LaneCountyPropertyClient | Any,
) -> PublicRecordsResult:
    account = _clean(args.account)
    if account is None or not re.fullmatch(r"\d{7}", account):
        query = _query(
            ACCOUNT_SOURCE_ID,
            "account",
            parameters={"account_number": account},
        )
        raise SourceSelectionError(
            "invalid_account",
            "Lane County account numbers contain seven digits",
        )
    query = _query(
        ACCOUNT_SOURCE_ID,
        "account",
        parameters={"account_number": account},
    )
    raw_search, search_url = client.account_search("account", account)
    search_records = parse_account_search(raw_search, search_url)
    matching_search_records = [
        record
        for record in search_records
        if record["account_number"] == account
    ]
    page = client.account_detail(account)
    record = parse_account_detail(
        page.text,
        page.source_url,
        expected_account=account,
        search_record=matching_search_records,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=[
            "Owner is retained as the assessor search-index label and is not "
            "promoted to a recorded-title assertion."
        ],
    )


def _write_document(
    destination: Path,
    content: bytes,
    *,
    overwrite: bool,
) -> None:
    if destination.exists() and not overwrite:
        raise SourceSelectionError(
            "destination_exists",
            "destination already exists; pass --overwrite to replace it",
            details={"destination": str(destination)},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _execute_download(
    args: argparse.Namespace,
    client: LaneCountyPropertyClient | Any,
) -> PublicRecordsResult:
    document_id = _clean(args.document_id)
    query = _query(
        TAX_MAP_SOURCE_ID,
        "download_tax_map",
        parameters={
            "tax_map_document_id": document_id,
            "destination": str(Path(args.destination).expanduser()),
        },
    )
    if document_id is None or not document_id.isdigit():
        raise SourceSelectionError(
            "invalid_tax_map_document_id",
            "tax-map document ID must contain digits",
        )
    document = client.tax_map_document(document_id)
    destination = Path(args.destination).expanduser().resolve()
    _write_document(destination, document.content, overwrite=args.overwrite)
    document_ref = canonical_property_ref(
        TAX_MAP_SOURCE_ID,
        COUNTY_GEOID,
        "tax_map_document",
        document_id,
    )
    record = {
        "canonical_ref": document_ref,
        "evidence_ref": document_ref,
        "source_id": TAX_MAP_SOURCE_ID,
        "source_url": document.source_url,
        "record_kind": "tax_map_document",
        "representation_kind": "official_pdf",
        "source_record_id": document_id,
        "tax_map_document_id": document_id,
        "media_type": document.headers.get("content-type", "").split(";", 1)[0],
        "size_bytes": len(document.content),
        "sha256": hashlib.sha256(document.content).hexdigest(),
        "local_path": str(destination),
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination)],
        warnings=[
            "The downloaded tax map is assessment cartography, not a recorded "
            "title instrument or a surveyed legal-boundary determination."
        ],
    )


def _execute_probe(
    args: argparse.Namespace,
    client: LaneCountyPropertyClient | Any,
) -> PublicRecordsResult:
    source_id = args.source
    query = _query(
        source_id,
        "probe",
        parameters={"structural_sentinel": True},
    )
    if source_id == ACCOUNT_SOURCE_ID:
        raw, search_url = client.account_search("account", ACCOUNT_SENTINEL)
        search_records = parse_account_search(raw, search_url)
        page = client.account_detail(ACCOUNT_SENTINEL)
        detail = parse_account_detail(
            page.text,
            page.source_url,
            expected_account=ACCOUNT_SENTINEL,
            search_record=search_records,
        )
        record = {
            "canonical_ref": (
                f"LANE_PROPERTY_PROBE:{ACCOUNT_SOURCE_ID}:{ACCOUNT_SENTINEL}"
            ),
            "record_kind": "source_probe",
            "source_id": source_id,
            "anonymous_json_search_verified": bool(search_records),
            "anonymous_session_detail_verified": True,
            "sentinel_account": detail["account_number"],
            "sentinel_map_taxlot": detail["map_taxlot"],
            "receipt_count": len(detail["recent_receipts"]),
            "valuation_year_count": len(detail["valuation_history"]),
            "source_response_schema_fingerprint": detail[
                "source_response_schema_fingerprint"
            ],
        }
    else:
        page = client.tax_map_search("map_lot", MAP_TAXLOT_SENTINEL)
        locators = parse_tax_map_search(page.text, page.source_url)
        sentinel = next(
            (
                record
                for record in locators
                if record["map_taxlot"] == MAP_TAXLOT_SENTINEL
            ),
            None,
        )
        if sentinel is None:
            raise SourceSchemaError(
                "Lane tax-map sentinel locator was not returned",
                url=page.source_url,
            )
        document = client.tax_map_document(
            str(sentinel["tax_map_document_id"])
        )
        record = {
            "canonical_ref": (
                f"LANE_PROPERTY_PROBE:{TAX_MAP_SOURCE_ID}:"
                f"{sentinel['tax_map_document_id']}"
            ),
            "record_kind": "source_probe",
            "source_id": source_id,
            "anonymous_webforms_search_verified": True,
            "official_pdf_verified": True,
            "sentinel_map_taxlot": sentinel["map_taxlot"],
            "sentinel_map_name": sentinel["map_name"],
            "sentinel_document_id": sentinel["tax_map_document_id"],
            "document_size_bytes": len(document.content),
            "document_sha256": hashlib.sha256(document.content).hexdigest(),
            "source_response_schema_fingerprint": sentinel[
                "source_response_schema_fingerprint"
            ],
        }
    return PublicRecordsResult.success(query, [record])


def execute(
    args: argparse.Namespace,
    *,
    client: LaneCountyPropertyClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Lane County property-source operation."""

    if args.command == "search":
        source_id = args.source
        parameters = {
            "field": args.field,
            "value": _clean(args.query),
            "city": _clean(args.city),
        }
        query = _query(
            source_id,
            "search",
            parameters=parameters,
            limit=args.limit,
            cursor=args.cursor,
        )
    elif args.command == "account":
        source_id = ACCOUNT_SOURCE_ID
        query = _query(
            source_id,
            "account",
            parameters={"account_number": _clean(args.account)},
        )
    elif args.command == "download-tax-map":
        source_id = TAX_MAP_SOURCE_ID
        query = _query(
            source_id,
            "download_tax_map",
            parameters={
                "tax_map_document_id": _clean(args.document_id),
                "destination": str(Path(args.destination).expanduser()),
            },
        )
    else:
        source_id = args.source
        query = _query(
            source_id,
            "probe",
            parameters={"structural_sentinel": True},
        )

    source_client = client or LaneCountyPropertyClient(timeout=float(args.timeout))
    try:
        if args.command == "search":
            result = _execute_search(args, source_client)
        elif args.command == "account":
            result = _execute_account(args, source_client)
        elif args.command == "download-tax-map":
            result = _execute_download(args, source_client)
        elif args.command == "probe":
            result = _execute_probe(args, source_client)
        else:
            raise SourceSelectionError(
                "unsupported_command",
                f"unsupported command: {args.command}",
            )
    except SourceSelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError, OSError) as error:
        result = _schema_failure(query, error)
    finally:
        if client is None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(query, count)
    return result


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Lane County property-account and tax-map sources"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List the distinct Lane County source components and complements",
    )
    add_output_args(sources)

    search = subparsers.add_parser(
        "search",
        help="Search one official Lane County source",
    )
    search.add_argument("query")
    search.add_argument(
        "--source",
        required=True,
        choices=(ACCOUNT_SOURCE_ID, TAX_MAP_SOURCE_ID),
    )
    search.add_argument(
        "--field",
        required=True,
        choices=(
            "account",
            "map_taxlot",
            "address",
            "name",
            "map_lot",
            "map_name",
        ),
    )
    search.add_argument("--city")
    search.add_argument(
        "--limit",
        type=int,
        help=(
            "Return an explicit caller-selected window; omitted returns every "
            "row supplied by the source query"
        ),
    )
    search.add_argument("--cursor")
    _add_runtime(search)

    account = subparsers.add_parser(
        "account",
        help="Fetch one property account and its tax, receipt, and value detail",
    )
    account.add_argument("account")
    _add_runtime(account)

    download = subparsers.add_parser(
        "download-tax-map",
        help="Download one tax-map PDF by its source-native document ID",
    )
    download.add_argument("document_id")
    download.add_argument("--destination", required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify one source with its structural public sentinel",
    )
    probe.add_argument(
        "--source",
        required=True,
        choices=(ACCOUNT_SOURCE_ID, TAX_MAP_SOURCE_ID),
    )
    _add_runtime(probe)
    return parser


def _emit_sources(args: argparse.Namespace) -> None:
    payload = sources_payload()
    if write_output(
        payload,
        args,
        summary="Lane County property source components",
        result_count=len(payload["sources"]),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for source in payload["sources"]:
        print(
            f"{source['source_id']} | {source['name']} | "
            f"{source['source_role']}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Lane County {result.query.source.source_id} "
            f"{args.command} ({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{result.query.source.name} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            f"{record.get('account_number') or record.get('map_taxlot') or record.get('source_record_id') or '?'}"
            f" | {record.get('record_kind') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "sources":
        _emit_sources(args)
        return
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
