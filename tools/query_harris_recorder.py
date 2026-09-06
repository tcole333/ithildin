#!/usr/bin/env python3
"""Search the official Harris County Clerk real-property instrument index.

Verified source surfaces (2026-07-29):

* The public ASP.NET search form accepts anonymous index searches and redirects
  each successful query to a single opaque result URL.
* Result rows expose the file number, filing date, instrument code, indexed
  parties, legal-description fields, page count, and document locator.
* Document-image links require a free registered account; the adapter reports
  that access route but does not create accounts or imply that an index row is
  the document image.
* The Clerk separately sells pipe-delimited index data and TIFF images for
  custom date ranges and offers monthly daily-FTP delivery.

The result page has no published count or paginator. A bounded live probe
returned exactly 200 rows, so the adapter flags that observed boundary without
claiming that it is a documented source maximum.

Examples:
    uv run python tools/query_harris_recorder.py search \
        --file-number RP-2026-72194 --output /tmp/harris-recorder.json
    uv run python tools/query_harris_recorder.py search \
        --grantee "HOME LIQUIDATORS 2 LLC"
    uv run python tools/query_harris_recorder.py products --json
    uv run python tools/query_harris_recorder.py sentinel --json
"""

from __future__ import annotations

import argparse
import html as html_lib
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


SOURCE_ID = "us-tx-harris-clerk-real-property"
SOURCE = SOURCE_ID
BASE_URL = "https://www.cclerk.hctx.net"
SEARCH_URL = f"{BASE_URL}/Applications/WebSearch/RP.aspx"
RESULT_PATH = "/Applications/WebSearch/RP_R.aspx"
HELP_URL = f"{BASE_URL}/Applications/WebSearch/help.aspx"
CODE_URL = f"{BASE_URL}/Applications/WebSearch/Codes.aspx?DTI=1"
REGISTRATION_URL = (
    f"{BASE_URL}/Applications/WebSearch/Registration/Welcome.aspx"
)
LOGIN_URL = f"{BASE_URL}/Applications/WebSearch/Registration/Login.aspx"
PUBLIC_RECORDS_URL = f"{BASE_URL}/PublicRecords.aspx"
CONTACT_URL = f"{BASE_URL}/ContactUs.aspx"

USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
TIMEOUT = 30
MAX_RETRIES = 2
REQUEST_DELAY = 0.2
OBSERVED_RESULT_CEILING = 200

SENTINEL_FILE_NUMBER = "RP-2026-72194"
SENTINEL_FILE_DATE = "02/26/2026"
SENTINEL_INSTRUMENT_TYPE = "W/D"
SENTINEL_GRANTOR = "MARTINEZ CHRIS"
SENTINEL_GRANTEE = "HOME LIQUIDATORS 2 LLC"
SENTINEL_DESCRIPTION = "GALENA OAKS"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE,
    name="Harris County Clerk Real Property Records",
    source_role="recorder_instrument_index",
    base_url=SEARCH_URL,
    dataset_id="real-property-web-index",
    metadata={
        "authority": "Harris County Clerk",
        "jurisdiction_geoid": "48201",
        "record_identity_key": "file_number",
        "document_access": "separate_registered_account_route",
        "bulk_access": "separate_data_sales_product",
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
    "Records are Clerk index metadata, not retrieved document-image contents.",
    (
        "The source publishes neither a total count nor pagination; 200 rows is "
        "an observed boundary and queries reaching it may be incomplete."
    ),
)

FORM_FIELDS = {
    "file_number": "ctl00$ContentPlaceHolder1$txtFileNo",
    "film_code": "ctl00$ContentPlaceHolder1$txtFilmCd",
    "from_date": "ctl00$ContentPlaceHolder1$txtFrom",
    "to_date": "ctl00$ContentPlaceHolder1$txtTo",
    "grantor": "ctl00$ContentPlaceHolder1$txtOR",
    "grantee": "ctl00$ContentPlaceHolder1$txtEE",
    "trustee": "ctl00$ContentPlaceHolder1$txtNameTee",
    "description": "ctl00$ContentPlaceHolder1$txtDesc",
    "instrument_type": "ctl00$ContentPlaceHolder1$txtInstrument",
    "volume": "ctl00$ContentPlaceHolder1$txtVolNo",
    "page": "ctl00$ContentPlaceHolder1$txtPageNo",
    "section": "ctl00$ContentPlaceHolder1$txtSection",
    "lot": "ctl00$ContentPlaceHolder1$txtLot",
    "block": "ctl00$ContentPlaceHolder1$txtBlock",
    "unit": "ctl00$ContentPlaceHolder1$txtUnit",
    "abstract": "ctl00$ContentPlaceHolder1$txtAbstract",
    "outlot": "ctl00$ContentPlaceHolder1$txtOutLot",
    "tract": "ctl00$ContentPlaceHolder1$txtTract",
    "reserve": "ctl00$ContentPlaceHolder1$txtReserve",
}
SEARCH_BUTTON = "ctl00$ContentPlaceHolder1$btnSearch"

LEGAL_FIELDS = {
    "SubDivAdd": "description",
    "Section": "section",
    "Lot": "lot",
    "Block": "block",
    "Misc": "miscellaneous",
    "Unit": "unit",
    "Abstract": "abstract",
    "OutLot": "outlot",
    "Tract": "tract",
    "Reserve": "reserve",
    "Comment": "comment",
}


class HarrisRecorderError(RuntimeError):
    """Official recorder request or source-contract error."""


class HarrisRecorderSourceChanged(HarrisRecorderError):
    """The official form or result schema no longer matches the probe."""


class HarrisRecorderTransportError(HarrisRecorderError):
    """The official source could not be reached after bounded retries."""


class HarrisRecorderRateLimited(HarrisRecorderError):
    """The official source returned HTTP 429 after bounded retries."""


class HarrisRecorderHTTPError(HarrisRecorderError):
    """The official source returned a non-success HTTP response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            f"Harris County Clerk returned HTTP {self.status_code}"
        )


@dataclass(frozen=True)
class TextResponse:
    """Small transport-neutral representation of an HTML response."""

    url: str
    text: str
    status_code: int
    headers: Mapping[str, str]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _official_url(value: str, *, base: str = BASE_URL) -> str:
    candidate = urljoin(base, value.strip())
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise HarrisRecorderError("Clerk URL is not HTTP(S)")
    if (parsed.hostname or "").lower() != "www.cclerk.hctx.net":
        raise HarrisRecorderError("Clerk URL left the official cclerk.hctx.net host")
    return urlunparse(("https", parsed.netloc, parsed.path, "", parsed.query, ""))


def _native_date(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    for format_string in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, format_string).strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise HarrisRecorderError(
        f"{name} must use YYYY-MM-DD or the source-native MM/DD/YYYY format"
    )


def _iso_date(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _positive_limit(value: int | None) -> None:
    if value is not None and value < 1:
        raise HarrisRecorderError("--limit must be a positive integer")


def _query_metadata() -> dict[str, Any]:
    return {
        "source_id": SOURCE,
        "authority": "Harris County Clerk",
        "jurisdiction": {
            "county": "Harris County",
            "state": "Texas",
            "county_fips": "48201",
        },
        "source_role": "recorder_instrument_index",
        "record_kind": "recorded_instrument_index_entry",
        "search_url": SEARCH_URL,
        "help_url": HELP_URL,
        "instrument_codes_url": CODE_URL,
        "coverage_statements": {
            "land_records": "1836 to present",
            "online_image_notice": "images available from 1960-11-01",
            "index_freshness_notice": (
                "search may lag recording by one to two business days"
            ),
        },
        "evidence_scope": (
            "Clerk index metadata; document-image contents require a separate "
            "retrieval and should be cited separately"
        ),
    }


def access_and_product_metadata() -> dict[str, Any]:
    """Return the Clerk's separately verified image, copy, and bulk routes."""
    return {
        "source": SOURCE,
        "status": "ok",
        "as_observed": "2026-07-29",
        "index_search": {
            "url": SEARCH_URL,
            "authentication": "anonymous",
            "transport": "aspnet_form_post_to_opaque_single_result_page",
            "published_pagination": None,
            "observed_result_ceiling": OBSERVED_RESULT_CEILING,
            "ceiling_status": "observed_not_published",
        },
        "document_images": {
            "registration_required": True,
            "registration_url": REGISTRATION_URL,
            "login_url": LOGIN_URL,
            "watermarked_view_fee_usd": 0,
            "source_statements": [
                {
                    "scope": "search portal",
                    "coverage": "images available from 1960-11-01",
                },
                {
                    "scope": "deed FAQ",
                    "coverage": (
                        "deeds filed after January 2000 can be viewed as free "
                        "watermarked copies after registration"
                    ),
                },
            ],
        },
        "copy_fees": {
            "source_url": PUBLIC_RECORDS_URL,
            "watermarked_portal_copy_usd": 0,
            "paper_noncertified_per_page_usd": 1.0,
            "electronic_noncertified": {
                "up_to_10_pages_usd": 1.0,
                "each_page_over_10_usd": 0.10,
                "basis": "per_document",
            },
            "certification_per_document_usd": 5.0,
            "map_or_condominium_noncertified_per_page_usd": 10.0,
            "map_or_condominium_certified_per_page_usd": 15.0,
            "staff_search_per_search_usd": 5.0,
            "staff_search_fee_exception": (
                "no search fee when file number or film code is provided"
            ),
            "remote_credit_card_surcharge_percent": 4.0,
        },
        "bulk_data_sales": {
            "source_url": PUBLIC_RECORDS_URL,
            "availability": "custom_date_range",
            "index": {
                "format": "pipe_delimited_text",
                "purchase": "separate_from_images",
            },
            "images": {
                "format": "TIFF",
                "coverage": "most documents recorded by the County Clerk",
                "purchase": "separate_from_index",
            },
            "delivery": [
                "CD",
                "DVD",
                "customer_provided_hard_drive",
            ],
            "daily_ftp": {
                "availability": "most County Clerk record types",
                "purchase_period": "monthly",
            },
            "posted_price": None,
            "price_basis": "contact_data_sales",
            "contact": {
                "url": CONTACT_URL,
                "contact_form_topic": "Data Sales",
                "phone": "713-274-6390",
            },
        },
    }


class HarrisRecorderClient:
    """Requests-compatible client for the verified Clerk form workflow."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: int = TIMEOUT,
        request_delay: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        sleeper=time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.8",
            })
        self.timeout = timeout
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._sleeper = sleeper
        self._last_request_at = 0.0

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        allow_redirects: bool,
    ) -> TextResponse:
        safe_url = _official_url(url)
        for attempt in range(self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.request_delay:
                self._sleeper(self.request_delay - elapsed)
            try:
                self._last_request_at = time.monotonic()
                response = self.session.request(
                    method,
                    safe_url,
                    data=data,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise HarrisRecorderTransportError(
                    f"Harris County Clerk request failed: {exc}"
                ) from exc

            status = int(response.status_code)
            if status == 429 or status >= 500:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
            if status == 429:
                raise HarrisRecorderRateLimited(
                    "Harris County Clerk returned HTTP 429"
                )
            if status < 200 or status >= 400:
                raise HarrisRecorderHTTPError(status)
            return TextResponse(
                url=str(response.url),
                text=str(response.text),
                status_code=status,
                headers=dict(response.headers),
            )
        raise HarrisRecorderError("Harris County Clerk request exhausted retries")

    def get(self, url: str, *, allow_redirects: bool = True) -> TextResponse:
        return self._request(
            "GET",
            url,
            allow_redirects=allow_redirects,
        )

    def _form_state(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        form = soup.select_one("form#aspnetForm") or soup.find("form")
        if form is None:
            raise HarrisRecorderSourceChanged(
                "official search page no longer contains an ASP.NET form"
            )
        hidden = {
            str(node.get("name")): str(node.get("value", ""))
            for node in form.select('input[type="hidden"][name]')
        }
        if "__VIEWSTATE" not in hidden or "__EVENTVALIDATION" not in hidden:
            raise HarrisRecorderSourceChanged(
                "official search form is missing expected ASP.NET state fields"
            )
        return hidden

    def search(self, selectors: Mapping[str, str | None]) -> dict[str, Any]:
        form_response = self.get(SEARCH_URL)
        form_data = self._form_state(form_response.text)
        normalized: dict[str, str] = {}
        for key, form_name in FORM_FIELDS.items():
            value = selectors.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                normalized[key] = text
                form_data[form_name] = text
        form_data[SEARCH_BUTTON] = "Search"

        submitted = self._request(
            "POST",
            SEARCH_URL,
            data=form_data,
            allow_redirects=False,
        )
        location = submitted.headers.get("Location")
        if submitted.status_code in {301, 302, 303, 307, 308} and location:
            result_url = _official_url(location, base=SEARCH_URL)
            if urlparse(result_url).path.lower() != RESULT_PATH.lower():
                raise HarrisRecorderSourceChanged(
                    "search redirected outside the verified result route"
                )
            result_response = self.get(result_url)
        elif "_lblFileNo" in submitted.text:
            result_response = submitted
            result_url = submitted.url
        else:
            message = _form_error(submitted.text)
            suffix = f": {message}" if message else ""
            raise HarrisRecorderError(
                "official search form did not issue a result page" + suffix
            )

        return parse_results(
            result_response.text,
            result_response.url or result_url,
            selectors=normalized,
        )

    def probe_document_access(self, document_url: str) -> dict[str, Any]:
        response = self.get(document_url, allow_redirects=False)
        location = response.headers.get("Location")
        redirect_url = (
            _official_url(location, base=document_url) if location else None
        )
        login_required = bool(
            redirect_url
            and "/registration/login.aspx"
            in urlparse(redirect_url).path.lower()
        )
        return {
            "source_url": _official_url(document_url),
            "http_status": response.status_code,
            "redirect_url": redirect_url,
            "anonymous_status": (
                "login_required" if login_required else "unexpected_response"
            ),
            "registration_required": login_required,
        }


def _form_error(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (
        ".validation-summary-errors",
        "[id*='ValidationSummary']",
        "[id*='lblError']",
    ):
        node = soup.select_one(selector)
        text = _clean_text(node)
        if text:
            return text
    alert = re.search(
        r"(?:window\.)?alert\(\s*['\"](.+?)['\"]\s*\)",
        html,
        flags=re.I | re.S,
    )
    return _clean_text(alert.group(1)) if alert else None


def _row_value(row: Any, suffix: str) -> str | None:
    node = row.select_one(f"[id$='_{suffix}']")
    value = _clean_text(node)
    return value or None


def _parse_parties(row: Any) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    for node in row.select("tr[id*='_lvOR_']"):
        name_node = node.select_one("[id$='_lblNames']")
        name = _clean_text(name_node)
        if not name:
            continue
        role_node = node.find("b")
        raw_role = _clean_text(role_node).rstrip(":") or None
        parties.append({
            "name": name,
            "role": raw_role.casefold() if raw_role else None,
            "raw_role": raw_role,
        })
    return parties


def _parse_legal_descriptions(row: Any) -> list[dict[str, str]]:
    groups: dict[int, dict[str, str]] = {}
    pattern = re.compile(
        r"_lvLegal_ctrl(\d+)_lbl("
        + "|".join(re.escape(value) for value in LEGAL_FIELDS)
        + r")$"
    )
    for node in row.select("[id*='_lvLegal_'][id]"):
        match = pattern.search(str(node.get("id", "")))
        if match is None:
            continue
        value = _clean_text(node)
        if not value:
            continue
        group_index = int(match.group(1))
        field = LEGAL_FIELDS[match.group(2)]
        groups.setdefault(group_index, {})[field] = value
    return [
        {"source_group": str(index), **groups[index]}
        for index in sorted(groups)
        if groups[index]
    ]


def _canonical_document_url(href: str | None, source_url: str) -> str | None:
    if not href or href.lower().startswith("javascript:"):
        return None
    return _official_url(href, base=source_url)


def _legal_description_raw(
    legal_descriptions: list[dict[str, str]],
) -> str | None:
    groups: list[str] = []
    for legal in legal_descriptions:
        parts: list[str] = []
        for key, value in legal.items():
            if key == "source_group":
                continue
            label = key.replace("_", " ").title()
            parts.append(value if key == "description" else f"{label}: {value}")
        if parts:
            groups.append(" | ".join(parts))
    return " || ".join(groups) or None


def parse_results(
    html: str,
    source_url: str,
    *,
    selectors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Parse all rows returned on the Clerk's single result page."""
    safe_source_url = _official_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, Any]] = []

    for file_node in soup.select("[id$='_lblFileNo']"):
        file_number = _clean_text(file_node)
        if not file_number:
            raise HarrisRecorderSourceChanged(
                "result row contains a blank file number"
            )
        row = file_node.find_parent("tr")
        if row is None:
            raise HarrisRecorderSourceChanged(
                "result file number is no longer nested in a table row"
            )
        file_date_raw = _row_value(row, "lblFileDate")
        instrument_type = _row_value(row, "lnkdetailtest")
        volume = _row_value(row, "lblVolNo")
        page = _row_value(row, "lblPageNo")
        page_count_raw = _row_value(row, "lblPgs")
        page_count = (
            int(page_count_raw)
            if page_count_raw and page_count_raw.isdigit()
            else None
        )
        film_node = row.select_one("[id$='_hfFilmCode']")
        document_locator = (
            _clean_text(film_node.get("value"))
            if film_node is not None and film_node.get("value")
            else None
        )
        image_node = row.select_one("[id$='_HyperLinkFCEC']")
        image_href = image_node.get("href") if image_node is not None else None
        document_url = _canonical_document_url(image_href, safe_source_url)
        parties = _parse_parties(row)
        legal_descriptions = _parse_legal_descriptions(row)
        grantors = [
            party["name"]
            for party in parties
            if party["role"] == "grantor"
        ]
        grantees = [
            party["name"]
            for party in parties
            if party["role"] == "grantee"
        ]
        canonical_ref = canonical_property_ref(
            SOURCE,
            "48201",
            "instrument",
            file_number,
        )

        records.append({
            "source_id": SOURCE,
            "record_kind": "recorded_instrument",
            "record_scope": "instrument_index_metadata",
            "canonical_ref": canonical_ref,
            "evidence_ref": canonical_ref,
            "file_number": file_number,
            "native_document_id": file_number,
            "recording_date": (
                _iso_date(file_date_raw) if file_date_raw else None
            ),
            "recording_date_raw": file_date_raw,
            "file_date": (
                _iso_date(file_date_raw) if file_date_raw else None
            ),
            "file_date_raw": file_date_raw,
            "instrument_type": instrument_type,
            "instrument_type_code": instrument_type,
            "book": volume,
            "volume": volume,
            "page": page,
            "page_count": page_count,
            "document_locator": document_locator,
            "parties": parties,
            "grantors": grantors,
            "grantees": grantees,
            "legal_descriptions": legal_descriptions,
            "legal_description_raw": _legal_description_raw(
                legal_descriptions
            ),
            "jurisdiction": {
                "geoid": "48201",
                "name": "Harris County, Texas",
                "state_code": "TX",
            },
            "source_url": safe_source_url,
            "document_access": {
                "document_url": document_url,
                "link_present": document_url is not None,
                "authentication": (
                    "registered_account" if document_url else None
                ),
                "watermarked_view_fee_usd": (
                    0 if document_url else None
                ),
                "evidence_scope": (
                    "separate document-image artifact; not retrieved by this "
                    "index result"
                ),
            },
        })

    for data_node in soup.select(
        "[id$='_lblFileDate'], "
        "[id$='_lnkdetailtest'], "
        "[id$='_HyperLinkFCEC']"
    ):
        row = data_node.find_parent("tr")
        if row is not None and row.select_one("[id$='_lblFileNo']") is None:
            raise HarrisRecorderSourceChanged(
                "data-shaped result row lacks its file-number field"
            )

    if not records:
        page_text = _clean_text(soup)
        no_results = any(
            marker in page_text.casefold()
            for marker in (
                "no records found",
                "no record found",
                "no results found",
            )
        )
        if not no_results:
            raise HarrisRecorderSourceChanged(
                "result page contains neither index rows nor a no-result marker"
            )

    source_count = len(records)
    possible_ceiling = source_count >= OBSERVED_RESULT_CEILING
    return {
        "source": SOURCE,
        "status": "ok",
        "source_metadata": _query_metadata(),
        "query": dict(selectors or {}),
        "source_url": safe_source_url,
        "coverage": {
            "source_rows_returned": source_count,
            "source_reported_total_results": None,
            "observed_result_ceiling": OBSERVED_RESULT_CEILING,
            "ceiling_status": "observed_not_published",
            "possible_source_ceiling_reached": possible_ceiling,
            "completeness": (
                "unknown_at_observed_ceiling"
                if possible_ceiling
                else "single_source_result_page_no_published_total"
            ),
        },
        "pagination": {
            "source_paginator_present": False,
            "source_page_count": 1,
            "adapter_followed_all_source_pages": True,
        },
        "results": records,
    }


def _selectors_from_args(args: argparse.Namespace) -> dict[str, str | None]:
    selectors = {
        key: getattr(args, key, None)
        for key in FORM_FIELDS
    }
    selectors["from_date"] = _native_date(
        selectors["from_date"],
        "--from-date",
    )
    selectors["to_date"] = _native_date(
        selectors["to_date"],
        "--to-date",
    )
    if selectors["from_date"] and selectors["to_date"]:
        from_date = datetime.strptime(
            str(selectors["from_date"]),
            "%m/%d/%Y",
        ).date()
        to_date = datetime.strptime(
            str(selectors["to_date"]),
            "%m/%d/%Y",
        ).date()
        if from_date > to_date:
            raise HarrisRecorderError("--from-date cannot be after --to-date")
    return selectors


def build_query(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    selectors: Mapping[str, str | None] | None = None,
) -> PublicRecordsQuery:
    """Build the shared query envelope used by the unified property router."""
    operation = args.command
    requested_limit = (
        getattr(args, "limit", None)
        if operation == "search"
        else None
    )
    if (
        isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or requested_limit <= 0
    ):
        requested_limit = None
    parameters: dict[str, Any] = {
        "route": (
            "anonymous_aspnet_index"
            if operation in {"search", "sentinel"}
            else "official_access_and_bulk_product_metadata"
        )
    }
    if operation == "search":
        selected = selectors or {
            key: getattr(args, key, None)
            for key in FORM_FIELDS
        }
        parameters["selectors"] = {
            key: value
            for key, value in selected.items()
            if value is not None and str(value).strip()
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            metadata={
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE)


def _access_failure(
    args: argparse.Namespace,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = dict(error.decision)
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "machine_acquisition_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="source_access",
            retryable=False,
            details={"access_decision": decision},
        )
    else:
        decision = {}
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
            details={"access_decision": decision},
        )
    return PublicRecordsResult.failure(
        build_query(args, access_decision=decision),
        status,
        [public_error],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    args: argparse.Namespace,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    normalized = dict(decision)
    return PublicRecordsResult.failure(
        build_query(args, access_decision=normalized),
        ResultStatus(acquisition_result_status(normalized)),
        [
            PublicRecordsError(
                code=str(
                    normalized.get("reason_code")
                    or "machine_acquisition_unavailable"
                ),
                message=str(
                    normalized.get("reason")
                    or "catalog decision does not allow machine acquisition"
                ),
                category="source_access",
                retryable=False,
                details={"access_decision": normalized},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: HarrisRecorderError,
) -> PublicRecordsResult:
    if isinstance(error, HarrisRecorderSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, HarrisRecorderRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
        retryable = True
    elif isinstance(error, HarrisRecorderTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    elif isinstance(error, HarrisRecorderHTTPError):
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
    else:
        status = ResultStatus.UNAVAILABLE
        code = "source_rejected_query"
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


def _contract_search_result(
    query: PublicRecordsQuery,
    payload: Mapping[str, Any],
    *,
    limit: int | None,
) -> PublicRecordsResult:
    source_records = payload.get("results")
    if not isinstance(source_records, list):
        raise HarrisRecorderSourceChanged(
            "normalized search payload no longer contains a result list"
        )
    coverage = payload.get("coverage")
    pagination = payload.get("pagination")
    if not isinstance(coverage, Mapping) or not isinstance(
        pagination,
        Mapping,
    ):
        raise HarrisRecorderSourceChanged(
            "normalized search payload is missing coverage metadata"
        )

    records: list[dict[str, Any]] = []
    for source_record in source_records:
        if not isinstance(source_record, Mapping):
            raise HarrisRecorderSourceChanged(
                "normalized search result is not an object"
            )
        record = dict(source_record)
        record["search_metadata"] = {
            "coverage": dict(coverage),
            "pagination": dict(pagination),
        }
        records.append(record)
    if limit is not None:
        records = records[:limit]

    warnings = list(SOURCE_WARNINGS[:1])
    possible_ceiling = bool(
        coverage.get("possible_source_ceiling_reached")
    )
    if possible_ceiling:
        warnings.append(SOURCE_WARNINGS[1])
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=warnings,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: HarrisRecorderClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one operation through the shared public-record result contract."""
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
        _log(canonical_json(result.query.to_dict()), None)
        return result

    if not decision.get("allowed", False):
        result = _decision_failure(args, decision)
        _log(canonical_json(result.query.to_dict()), None)
        return result

    try:
        if args.command == "search":
            _positive_limit(getattr(args, "limit", None))
            selectors = _selectors_from_args(args)
        else:
            selectors = None
        query = build_query(
            args,
            access_decision=decision,
            selectors=selectors,
        )
    except HarrisRecorderError as error:
        query = build_query(args, access_decision=decision)
        result = _source_failure(query, error)
        _log(canonical_json(query.to_dict()), None)
        return result

    source_client = client or HarrisRecorderClient(
        timeout=getattr(args, "timeout", TIMEOUT),
        request_delay=getattr(args, "minimum_interval", REQUEST_DELAY),
    )
    try:
        if args.command == "search":
            assert selectors is not None
            payload = source_client.search(selectors)
            result = _contract_search_result(
                query,
                payload,
                limit=getattr(args, "limit", None),
            )
        elif args.command == "products":
            record = {
                **access_and_product_metadata(),
                "source_id": SOURCE,
                "record_kind": "source_access_product",
                "native_document_id": "access-and-bulk-products",
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=SOURCE_WARNINGS[:1],
            )
        elif args.command == "sentinel":
            sentinel = run_sentinel(source_client)
            if sentinel["status"] != "ok":
                raise HarrisRecorderSourceChanged(
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
            raise HarrisRecorderError(
                f"unsupported Harris recorder command: {args.command}"
            )
    except HarrisRecorderError as error:
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
    _log(canonical_json(query.to_dict()), count)
    return result


def _log(query: str, count: int | None) -> None:
    try:
        log_search(query, SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit_contract(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    summary: str,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"{summary} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(f"{summary}: {result.status.value} ({len(result.records)} records)")
    for row in result.records:
        if row.get("record_kind") == "recorded_instrument":
            parties = ", ".join(
                list(row.get("grantors", ()))
                + list(row.get("grantees", ()))
            )
            print(
                f"- {row['file_number']} | {row.get('file_date_raw') or ''} "
                f"| {row.get('instrument_type_code') or ''}"
            )
            if parties:
                print(f"  {parties}")
            print(f"  {row['source_url']}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def cmd_search(args: argparse.Namespace) -> int:
    result = execute(args)
    _emit_contract(result, args, "Harris recorder search")
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


def cmd_products(args: argparse.Namespace) -> int:
    result = execute(args)
    _emit_contract(
        result,
        args,
        "Harris recorder access and bulk products",
    )
    return 0 if result.status == ResultStatus.OK else 1


def run_sentinel(client: HarrisRecorderClient | None = None) -> dict[str, Any]:
    """Verify the anonymous index, registered image boundary, and bulk page."""
    client = client or HarrisRecorderClient()
    checks: list[dict[str, Any]] = []
    sentinel_record: dict[str, Any] | None = None

    try:
        search = client.search({"file_number": SENTINEL_FILE_NUMBER})
        sentinel_record = next(
            (
                row
                for row in search["results"]
                if row["file_number"] == SENTINEL_FILE_NUMBER
            ),
            None,
        )
        if sentinel_record is None:
            raise HarrisRecorderSourceChanged(
                "known file number is missing from exact search"
            )
        expected = {
            "file_date_raw": SENTINEL_FILE_DATE,
            "instrument_type_code": SENTINEL_INSTRUMENT_TYPE,
        }
        for field, value in expected.items():
            if sentinel_record.get(field) != value:
                raise HarrisRecorderSourceChanged(
                    f"sentinel {field} changed from {value!r}"
                )
        if SENTINEL_GRANTOR not in sentinel_record["grantors"]:
            raise HarrisRecorderSourceChanged("sentinel grantor is missing")
        if SENTINEL_GRANTEE not in sentinel_record["grantees"]:
            raise HarrisRecorderSourceChanged("sentinel grantee is missing")
        descriptions = [
            item.get("description")
            for item in sentinel_record["legal_descriptions"]
        ]
        if SENTINEL_DESCRIPTION not in descriptions:
            raise HarrisRecorderSourceChanged(
                "sentinel legal description is missing"
            )
        checks.append({
            "name": "anonymous_exact_index",
            "status": "ok",
            "file_number": sentinel_record["file_number"],
            "file_date": sentinel_record["file_date"],
            "instrument_type_code": sentinel_record["instrument_type_code"],
            "source_url": sentinel_record["source_url"],
        })
    except HarrisRecorderError as exc:
        checks.append({
            "name": "anonymous_exact_index",
            "status": "error",
            "error": str(exc),
        })

    try:
        document_url = (
            sentinel_record
            and sentinel_record["document_access"]["document_url"]
        )
        if not document_url:
            raise HarrisRecorderSourceChanged(
                "sentinel no longer exposes a document-image link"
            )
        access = client.probe_document_access(document_url)
        if access["anonymous_status"] != "login_required":
            raise HarrisRecorderSourceChanged(
                "document-image route no longer redirects anonymous users to login"
            )
        checks.append({
            "name": "registered_document_boundary",
            "status": "ok",
            **access,
        })
    except HarrisRecorderError as exc:
        checks.append({
            "name": "registered_document_boundary",
            "status": "error",
            "error": str(exc),
        })

    try:
        response = client.get(PUBLIC_RECORDS_URL)
        page_text = _clean_text(BeautifulSoup(response.text, "html.parser"))
        markers = {
            "pipe_delimited_index": "pipe delimited" in page_text.casefold(),
            "tiff_images": "tiff" in page_text.casefold(),
            "daily_ftp": "ftp access" in page_text.casefold(),
            "data_sales": "data sales" in page_text.casefold(),
        }
        if not all(markers.values()):
            raise HarrisRecorderSourceChanged(
                "official bulk-data page is missing a verified product marker"
            )
        checks.append({
            "name": "official_bulk_products",
            "status": "ok",
            "source_url": response.url,
            "markers": markers,
        })
    except HarrisRecorderError as exc:
        checks.append({
            "name": "official_bulk_products",
            "status": "error",
            "error": str(exc),
        })

    ok = all(check["status"] == "ok" for check in checks)
    return {
        "source": SOURCE,
        "status": "ok" if ok else "unavailable",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "exact_urls": {
            "search": SEARCH_URL,
            "help": HELP_URL,
            "instrument_codes": CODE_URL,
            "registration": REGISTRATION_URL,
            "bulk_data_sales": PUBLIC_RECORDS_URL,
        },
    }


def cmd_sentinel(args: argparse.Namespace) -> int:
    result = execute(args)
    _emit_contract(result, args, "Harris recorder live sentinel")
    return 0 if result.status == ResultStatus.OK else 1


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file-number")
    parser.add_argument("--film-code")
    parser.add_argument(
        "--from-date",
        help="Inclusive file date (YYYY-MM-DD or MM/DD/YYYY)",
    )
    parser.add_argument(
        "--to-date",
        help="Inclusive file date (YYYY-MM-DD or MM/DD/YYYY)",
    )
    parser.add_argument("--grantor")
    parser.add_argument("--grantee")
    parser.add_argument("--trustee")
    parser.add_argument("--description", help="Subdivision or legal description")
    parser.add_argument("--instrument-type", help="Source-native instrument code")
    parser.add_argument("--volume")
    parser.add_argument("--page")
    parser.add_argument("--section")
    parser.add_argument("--lot")
    parser.add_argument("--block")
    parser.add_argument("--unit")
    parser.add_argument("--abstract")
    parser.add_argument("--outlot")
    parser.add_argument("--tract")
    parser.add_argument("--reserve")


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(TIMEOUT),
        help=f"HTTP timeout in seconds (default: {TIMEOUT})",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=REQUEST_DELAY,
        help=(
            "Minimum seconds between source requests "
            f"(default: {REQUEST_DELAY})"
        ),
    )
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search the Harris County Clerk real-property index"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Submit native selectors to the anonymous Clerk index",
    )
    _add_search_arguments(search)
    search.add_argument(
        "--limit",
        type=int,
        help="Optional user-requested output limit; no default adapter cap",
    )
    _add_runtime_arguments(search)
    search.set_defaults(func=cmd_search)

    products = subparsers.add_parser(
        "products",
        help="Show verified account, copy-fee, and bulk-data routes",
    )
    _add_runtime_arguments(products)
    products.set_defaults(func=cmd_products)

    sentinel = subparsers.add_parser(
        "sentinel",
        help="Verify index parsing, image login boundary, and bulk products",
    )
    _add_runtime_arguments(sentinel)
    sentinel.set_defaults(func=cmd_sentinel)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0 or args.minimum_interval < 0:
        parser.error("--timeout must be positive and --minimum-interval non-negative")
    try:
        return args.func(args)
    except HarrisRecorderError as exc:
        payload = {
            "source": SOURCE,
            "status": "error",
            "error": str(exc),
            "results": [],
        }
        if getattr(args, "output", None):
            write_output(payload, args, summary="Harris recorder request failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
