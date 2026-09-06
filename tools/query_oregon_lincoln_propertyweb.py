#!/usr/bin/env python3
"""Query Lincoln County, Oregon PropertyWeb assessment and tax records.

PropertyWeb publishes an anonymous JSON property search, rich server-rendered
account details, historical tax statements, and four PDF generators. Generated
documents are retrieved through the same anonymous cookie session that created
their filename.

Examples:
    uv run python tools/query_oregon_lincoln_propertyweb.py sources
    uv run python tools/query_oregon_lincoln_propertyweb.py search R452940 \
        --output /tmp/lincoln-search.json
    uv run python tools/query_oregon_lincoln_propertyweb.py detail \
        R452940 O0064958 --output /tmp/lincoln-detail.json
    uv run python tools/query_oregon_lincoln_propertyweb.py document \
        tax-statement 61623 208038 2025 \
        --destination /tmp/lincoln-tax-statement.pdf \
        --output /tmp/lincoln-tax-statement.json
    uv run python tools/query_oregon_lincoln_propertyweb.py probe \
        --output /tmp/lincoln-probe.json
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
from urllib.parse import quote, urljoin, urlparse

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
        SourceResponseError,
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
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-or-lincoln-propertyweb"
SOURCE_NAME = "Lincoln County Oregon PropertyWeb"
COUNTY_NAME = "Lincoln County, Oregon"
COUNTY_GEOID = "41041"
STATE_CODE = "OR"
STATE_FIPS = "41"
PUBLISHER = "Lincoln County Assessment and Taxation"
TAXLOT_WFS_SOURCE_ID = "us-or-lincoln-county-taxlots-wfs"
RECORDER_SOURCE_ID = "us-or-lincoln-helion-recorder"

BASE_URL = "https://propertyweb.co.lincoln.or.us"
HOME_URL = f"{BASE_URL}/Home"
SEARCH_URL = f"{BASE_URL}/Proxy/Search/Properties/"
DETAIL_ROUTE = (
    "/Property-Detail/PropertyQuickRefID/{property_quick_ref}/"
    "PartyQuickRefID/{party_quick_ref}/"
)
GENERATED_DOCUMENT_URL = f"{BASE_URL}/Proxy/documents/pdf"
HISTORICAL_STATEMENT_ROUTE = "/TaxStatements/{tax_year}/{property_quick_ref}.pdf"

DOCUMENT_GENERATORS = {
    "tax-statement": f"{BASE_URL}/Proxy/tax/TaxStatement",
    "receipt": f"{BASE_URL}/Proxy/tax/Receipt",
    "appraisal-card": f"{BASE_URL}/Proxy/properties/AppraisalCard",
    "account-summary": f"{BASE_URL}/Proxy/tax/AccountSummary",
}

DEFAULT_PROPERTY_TYPES = ("RP", "PP", "MH", "NR", "O")
PROPERTY_TYPE_LABELS = {
    "RP": "real_property",
    "PP": "personal_property",
    "MH": "manufactured_home",
    "NR": "non_real_property",
    "O": "other",
}
SORT_TYPES = {
    "property_id": 0,
    "situs": 3,
    "legal": 5,
    "neighborhood": 6,
    "abstract": 7,
    "subdivision": 8,
    "property_type": 9,
    "map_number": 11,
}
SORT_ORDERS = {"asc": 0, "desc": 1}
NATIVE_PAGE_SIZE = 25
CURSOR_PREFIX = "oregon-lincoln-propertyweb:v1:"
CURSOR_VERSION = 1

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.3
DEFAULT_MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

PROBE_PROPERTY_QUICK_REF = "R452940"
PROBE_PARTY_QUICK_REF = "O0064958"
PROBE_TAX_YEAR = 2026
PROBE_PROPERTY_ID = "61623"
PROBE_INTERNAL_PARTY_ID = "208038"
APPRAISAL_REPORT_FORMAT_ID = "502405"

SEARCH_ROOT_FIELDS = (
    "ResultList",
    "HasMoreData",
    "TotalPageCount",
    "CurrentPage",
    "RecordCount",
    "SearchText",
    "PagingHandledByCaller",
    "TaxYear",
    "PropertyValueTaxYear",
)
SEARCH_RECORD_FIELDS = (
    "PropertyQuickRefID",
    "PartyQuickRefID",
    "OwnerQuickRefID",
    "LegacyID",
    "PropertyNumber",
    "OwnerName",
    "OwnerFullAddress",
    "SitusAddress",
    "PropertyValue",
    "AssessedValue",
    "MarketValue",
    "LegalDescription",
    "NeighborhoodCode",
    "Abstract",
    "Subdivision",
    "PropertyType",
    "AltAccountNo",
    "CustomID",
    "MapNumber",
    "ParcelID",
    "PropertyClass",
    "ID",
    "Text",
    "TaxYear",
    "PropertyValueTaxYear",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="official_county_property_assessment_tax_and_payment_records",
    base_url=HOME_URL,
    dataset_id="lincoln-county-propertyweb",
    metadata={
        "publisher": PUBLISHER,
        "county_geoid": COUNTY_GEOID,
        "platform_family": "tyler_propertyweb_dnn",
        "access_observation": {
            "search": "anonymous_json",
            "detail": "anonymous_server_rendered_html",
            "historical_statements": "anonymous_direct_pdf",
            "current_documents": "anonymous_session_bound_filename_then_pdf",
            "observed_at": "2026-07-29",
        },
        "native_page_size_observed": NATIVE_PAGE_SIZE,
        "joins": {
            TAXLOT_WFS_SOURCE_ID: ["map_number", "taxlot"],
            RECORDER_SOURCE_ID: [
                "sale_instrument",
                "party_name",
                "sale_date",
            ],
        },
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Lincoln County",
    metadata={"state_fips": STATE_FIPS},
)


@dataclass(frozen=True)
class HomeContract:
    tax_year: int
    source_url: str
    source_html_sha256: str
    schema_fingerprint: str


@dataclass(frozen=True)
class HTMLPage:
    html: str
    source_url: str


@dataclass(frozen=True)
class SearchPage:
    raw_records: tuple[Mapping[str, Any], ...]
    source_url: str
    current_page: int
    total_pages: int
    record_count: int
    has_more: bool
    search_text: str
    tax_year: int
    property_value_tax_year: int
    schema_fingerprint: str
    snapshot_fingerprint: str


@dataclass(frozen=True)
class PDFArtifact:
    content: bytes
    source_url: str
    media_type: str
    generated_filename: str | None
    generator_url: str | None
    generation_parameters: Mapping[str, Any]
    retrieval_mode: str


class PropertyWebSelectionError(ValueError):
    """A selector or cursor does not match the source-native contract."""

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
    if not text or text == "-":
        return None
    return text


def _lines(value: Tag | None) -> list[str]:
    if value is None:
        return []
    return [
        text
        for text in (
            re.sub(r"\s+", " ", item).strip()
            for item in value.get_text("\n", strip=True).splitlines()
        )
        if text and text != "-"
    ]


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (_clean(value) or "").casefold()).strip("_")


def _integer(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[^\d-]", "", text)
    if not normalized or normalized == "-":
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def _number(value: Any) -> int | float | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[$,%\s]", "", text).replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    if not normalized or normalized == "-":
        return None
    try:
        number = float(normalized)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _iso_date(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for pattern in ("%m-%d-%Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _response_header(response: Any, name: str) -> str | None:
    for key, value in getattr(response, "headers", {}).items():
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


def _source_url(path_or_url: str) -> str:
    url = urljoin(BASE_URL, path_or_url)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "propertyweb.co.lincoln.or.us"
        or parsed.username
        or parsed.password
    ):
        raise ValueError("PropertyWeb URL must remain on the official HTTPS host")
    return url


def _body_bytes(response: Any) -> bytes:
    value = getattr(response, "content", b"")
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    text = getattr(response, "text", "")
    return str(text).encode("utf-8")


def parse_home_contract(html: str, source_url: str = HOME_URL) -> HomeContract:
    """Extract the current published tax year from the official Home page."""

    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []
    for element in soup.select("input[id$='_TaxYear'], input[name$='$TaxYear']"):
        value = _clean(element.get("value"))
        if value:
            candidates.append(value)
    candidates.extend(
        re.findall(
            r"\btaxYear\s*=\s*(?:\$\([^)]*\)\.val\(\)|[\"'](\d{4})[\"'])",
            html,
            flags=re.I,
        )
    )
    tax_year = next(
        (
            int(value)
            for value in candidates
            if value and re.fullmatch(r"20\d{2}", value)
        ),
        None,
    )
    if tax_year is None:
        raise SourceSchemaError(
            "Lincoln PropertyWeb Home no longer publishes a current tax year",
            url=source_url,
        )
    contract_shape = {
        "tax_year_input_ids": sorted(
            {
                str(element.get("id"))
                for element in soup.select("input[id$='_TaxYear']")
                if element.get("id")
            }
        ),
        "search_proxy_published": any(
            _clean(element.get("value")) == "/Proxy/"
            for element in soup.select("input[id$='_ProxyAddressQuickSearch']")
        ),
        "quick_search_route_published": "Search/Properties/quick/" in html,
        "detail_route_published": "/Property-Detail/PropertyQuickRefID/" in html,
    }
    if not all(
        contract_shape[key]
        for key in (
            "search_proxy_published",
            "quick_search_route_published",
            "detail_route_published",
        )
    ):
        raise SourceSchemaError(
            "Lincoln PropertyWeb Home search route contract changed",
            url=source_url,
            details=contract_shape,
        )
    return HomeContract(
        tax_year=tax_year,
        source_url=source_url,
        source_html_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        schema_fingerprint=sha256_fingerprint(contract_shape),
    )


def _search_schema(payload: Mapping[str, Any]) -> str:
    records = payload.get("ResultList")
    result_keys: set[str] = set()
    if isinstance(records, list):
        for record in records:
            if isinstance(record, Mapping):
                result_keys.update(str(key) for key in record)
    return sha256_fingerprint(
        {
            "root_keys": sorted(str(key) for key in payload),
            "result_keys": sorted(result_keys or SEARCH_RECORD_FIELDS),
        }
    )


def parse_search_page(
    payload: Mapping[str, Any],
    *,
    source_url: str,
    requested_page: int,
) -> SearchPage:
    """Validate one native PropertyWeb JSON result page."""

    missing = [field for field in SEARCH_ROOT_FIELDS if field not in payload]
    if missing:
        raise SourceSchemaError(
            "Lincoln PropertyWeb search metadata changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    raw_records = payload.get("ResultList")
    if not isinstance(raw_records, list) or not all(
        isinstance(record, Mapping) for record in raw_records
    ):
        raise SourceSchemaError(
            "Lincoln PropertyWeb ResultList is no longer an array of records",
            url=source_url,
        )
    for index, record in enumerate(raw_records):
        missing_record = [
            field
            for field in ("PropertyQuickRefID", "PartyQuickRefID")
            if field not in record
        ]
        if missing_record:
            raise SourceSchemaError(
                "Lincoln PropertyWeb search record identity changed",
                url=source_url,
                details={"index": index, "missing_fields": missing_record},
            )
    try:
        current_page = int(payload["CurrentPage"])
        total_pages = int(payload["TotalPageCount"])
        record_count = int(payload["RecordCount"])
        tax_year = int(payload["TaxYear"])
        property_value_tax_year = int(payload["PropertyValueTaxYear"])
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Lincoln PropertyWeb paging metadata is not numeric",
            url=source_url,
        ) from error
    if requested_page < 1:
        raise ValueError("requested page must be positive")
    if current_page != requested_page:
        raise SourceSchemaError(
            "Lincoln PropertyWeb returned a different native page",
            url=source_url,
            details={
                "requested_page": requested_page,
                "returned_page": current_page,
            },
        )
    if len(raw_records) > NATIVE_PAGE_SIZE:
        raise SourceSchemaError(
            "Lincoln PropertyWeb native page size changed",
            url=source_url,
            details={
                "observed_rows": len(raw_records),
                "expected_maximum": NATIVE_PAGE_SIZE,
            },
        )
    has_more = payload["HasMoreData"]
    if not isinstance(has_more, bool):
        raise SourceSchemaError(
            "Lincoln PropertyWeb HasMoreData is no longer boolean",
            url=source_url,
        )
    search_text = str(payload["SearchText"])
    schema = _search_schema(payload)
    return SearchPage(
        raw_records=tuple(dict(record) for record in raw_records),
        source_url=source_url,
        current_page=current_page,
        total_pages=total_pages,
        record_count=record_count,
        has_more=has_more,
        search_text=search_text,
        tax_year=tax_year,
        property_value_tax_year=property_value_tax_year,
        schema_fingerprint=schema,
        snapshot_fingerprint=sha256_fingerprint(raw_records),
    )


def normalize_search_record(
    raw: Mapping[str, Any],
    *,
    source_url: str,
    native_page: int,
    native_position: int,
    schema_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one search result while retaining every source-native field."""

    property_quick_ref = _clean(raw.get("PropertyQuickRefID"))
    party_quick_ref = _clean(raw.get("PartyQuickRefID"))
    if property_quick_ref is None or party_quick_ref is None:
        raise SourceSchemaError(
            "Lincoln PropertyWeb result lacks stable property/party identity",
            url=source_url,
        )
    detail_url = _source_url(
        DETAIL_ROUTE.format(
            property_quick_ref=quote(property_quick_ref, safe=""),
            party_quick_ref=quote(party_quick_ref, safe=""),
        )
    )
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "property_account",
        property_quick_ref,
    )
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "record_kind": "property_account_search_result",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous",
        "property_quick_ref": property_quick_ref,
        "party_quick_ref": party_quick_ref,
        "owner_quick_ref": _clean(raw.get("OwnerQuickRefID")),
        "legacy_id": _clean(raw.get("LegacyID")),
        "property_number": _clean(raw.get("PropertyNumber")),
        "owner_name": _clean(raw.get("OwnerName")),
        "owner_full_address": _clean(raw.get("OwnerFullAddress")),
        "situs_address": _clean(raw.get("SitusAddress")),
        "legal_description": _clean(raw.get("LegalDescription")),
        "map_number": _clean(raw.get("MapNumber")),
        "parcel_id": _clean(raw.get("ParcelID")),
        "alternate_account_number": _clean(raw.get("AltAccountNo")),
        "custom_id": _clean(raw.get("CustomID")),
        "neighborhood_code": _clean(raw.get("NeighborhoodCode")),
        "abstract": _clean(raw.get("Abstract")),
        "subdivision": _clean(raw.get("Subdivision")),
        "property_type": _clean(raw.get("PropertyType")),
        "property_class": _clean(raw.get("PropertyClass")),
        "property_value": _number(raw.get("PropertyValue")),
        "assessed_value": _number(raw.get("AssessedValue")),
        "market_value": _number(raw.get("MarketValue")),
        "tax_year": _integer(raw.get("TaxYear")),
        "property_value_tax_year": _integer(raw.get("PropertyValueTaxYear")),
        "detail_url": detail_url,
        "native_page": native_page,
        "native_position": native_position,
        "source_response_schema_fingerprint": schema_fingerprint,
        "native_fields": dict(raw),
        "join_candidates": {
            TAXLOT_WFS_SOURCE_ID: {
                "map_number": _clean(raw.get("MapNumber")),
                "relationship": "parcel_geometry_and_owner_complement",
            }
        },
    }


class PropertyWebClient:
    """Bounded, retrying client that retains one anonymous cookie session."""

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
        self._home_contract: HomeContract | None = None
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
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        accept: str,
        stream: bool = False,
    ) -> Any:
        official_url = _source_url(url)
        last_error: requests.RequestException | None = None
        headers = {**self.headers, "Accept": accept}
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    official_url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=stream,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for redirect in [*getattr(response, "history", ()), response]:
                _source_url(str(getattr(redirect, "url", official_url)))
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                response.close()
                self.sleeper(self.retry_policy.delay(attempt, _retry_after(response)))
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
            "Lincoln PropertyWeb request failed",
            url=official_url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def _text_response(
        self,
        response: Any,
        *,
        expected_type: str,
        maximum_bytes: int,
    ) -> str:
        try:
            content_type = (_response_header(response, "content-type") or "").casefold()
            if content_type and expected_type not in content_type:
                raise SourceSchemaError(
                    f"Lincoln PropertyWeb returned non-{expected_type} content",
                    url=str(getattr(response, "url", BASE_URL)),
                    details={"content_type": content_type},
                )
            body = _body_bytes(response)
            if len(body) > maximum_bytes:
                raise SourceResponseError(
                    "Lincoln PropertyWeb response exceeded the adapter bound",
                    url=str(getattr(response, "url", BASE_URL)),
                    details={
                        "size_bytes": len(body),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            encoding = getattr(response, "encoding", None) or "utf-8"
            return body.decode(encoding, errors="replace")
        finally:
            response.close()

    def home_contract(self, *, refresh: bool = False) -> HomeContract:
        if self._home_contract is not None and not refresh:
            return self._home_contract
        response = self._request(
            "GET",
            HOME_URL,
            accept="text/html,application/xhtml+xml",
        )
        html = self._text_response(
            response,
            expected_type="html",
            maximum_bytes=MAX_HTML_BYTES,
        )
        self._home_contract = parse_home_contract(
            html,
            str(getattr(response, "url", HOME_URL)),
        )
        return self._home_contract

    def search_page(
        self,
        *,
        term: str,
        tax_year: int,
        property_value_tax_year: int,
        page: int,
        sort_type: int,
        sort_order: int,
        property_types: Sequence[str],
    ) -> SearchPage:
        response = self._request(
            "GET",
            SEARCH_URL,
            params={
                "f": term,
                "ty": tax_year,
                "pvty": property_value_tax_year,
                "pn": page,
                "st": sort_type,
                "so": sort_order,
                "pt": ";".join(property_types),
            },
            accept="application/json,text/json,*/*;q=0.8",
        )
        body = _body_bytes(response)
        if len(body) > MAX_JSON_BYTES:
            raise SourceResponseError(
                "Lincoln PropertyWeb search response exceeded the adapter bound",
                url=str(getattr(response, "url", SEARCH_URL)),
                details={"size_bytes": len(body), "maximum_bytes": MAX_JSON_BYTES},
            )
        try:
            try:
                payload = response.json()
            except (TypeError, ValueError) as error:
                raise SourceSchemaError(
                    "Lincoln PropertyWeb search response is not JSON",
                    url=str(getattr(response, "url", SEARCH_URL)),
                ) from error
        finally:
            response.close()
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Lincoln PropertyWeb search response is not an object",
                url=str(getattr(response, "url", SEARCH_URL)),
            )
        return parse_search_page(
            payload,
            source_url=str(getattr(response, "url", SEARCH_URL)),
            requested_page=page,
        )

    def detail(
        self,
        property_quick_ref: str,
        party_quick_ref: str,
        *,
        effective_date: str | None = None,
    ) -> HTMLPage:
        route = DETAIL_ROUTE.format(
            property_quick_ref=quote(property_quick_ref, safe=""),
            party_quick_ref=quote(party_quick_ref, safe=""),
        )
        if effective_date:
            route += (
                f"EffectiveDate/{quote(effective_date.replace('/', '-'), safe='-')}/"
                "DefaultTab/1"
            )
        response = self._request(
            "GET",
            route,
            accept="text/html,application/xhtml+xml",
        )
        html = self._text_response(
            response,
            expected_type="html",
            maximum_bytes=MAX_HTML_BYTES,
        )
        return HTMLPage(
            html=html,
            source_url=str(getattr(response, "url", _source_url(route))),
        )

    def _read_pdf(
        self,
        response: Any,
        *,
        maximum_bytes: int,
        source_url: str,
    ) -> tuple[bytes, str]:
        declared_length = _integer(_response_header(response, "content-length"))
        if declared_length is not None and declared_length > maximum_bytes:
            response.close()
            raise SourceResponseError(
                "Lincoln PropertyWeb PDF exceeds the requested byte bound",
                url=source_url,
                details={
                    "content_length": declared_length,
                    "maximum_bytes": maximum_bytes,
                },
            )
        chunks: list[bytes] = []
        size = 0
        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            for chunk in iterator(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > maximum_bytes:
                    response.close()
                    raise SourceResponseError(
                        "Lincoln PropertyWeb PDF exceeded the requested byte bound",
                        url=source_url,
                        details={
                            "observed_bytes": size,
                            "maximum_bytes": maximum_bytes,
                        },
                    )
                chunks.append(bytes(chunk))
            content = b"".join(chunks)
        else:
            content = _body_bytes(response)
            if len(content) > maximum_bytes:
                response.close()
                raise SourceResponseError(
                    "Lincoln PropertyWeb PDF exceeded the requested byte bound",
                    url=source_url,
                    details={
                        "observed_bytes": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
        content_type = (_response_header(response, "content-type") or "").split(";", 1)[
            0
        ]
        response.close()
        if not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "Lincoln PropertyWeb document response is not a PDF",
                url=source_url,
                details={
                    "content_type": content_type,
                    "body_prefix_hex": content[:16].hex(),
                },
            )
        return content, content_type or "application/pdf"

    def fetch_document(
        self,
        kind: str,
        *,
        parameters: Mapping[str, Any],
        maximum_bytes: int,
    ) -> PDFArtifact:
        """Generate/fetch one source-native PDF in this client's cookie session."""

        self.home_contract()
        if kind == "historical-tax-statement":
            route = HISTORICAL_STATEMENT_ROUTE.format(
                tax_year=quote(str(parameters["TaxYear"]), safe=""),
                property_quick_ref=quote(
                    str(parameters["PropertyQuickRefID"]), safe=""
                ),
            )
            response = self._request(
                "GET",
                route,
                accept="application/pdf,*/*;q=0.8",
                stream=True,
            )
            source_url = str(getattr(response, "url", _source_url(route)))
            content, media_type = self._read_pdf(
                response,
                maximum_bytes=maximum_bytes,
                source_url=source_url,
            )
            return PDFArtifact(
                content=content,
                source_url=source_url,
                media_type=media_type,
                generated_filename=None,
                generator_url=None,
                generation_parameters=dict(parameters),
                retrieval_mode="direct_historical_pdf",
            )
        generator_url = DOCUMENT_GENERATORS[kind]
        generation = self._request(
            "POST",
            generator_url,
            data=parameters,
            accept="application/json,text/json,*/*;q=0.8",
        )
        try:
            try:
                filename = generation.json()
            except (TypeError, ValueError) as error:
                raise SourceSchemaError(
                    "Lincoln PropertyWeb document generator did not return JSON",
                    url=str(getattr(generation, "url", generator_url)),
                ) from error
        finally:
            generation.close()
        if (
            not isinstance(filename, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+\.pdf", filename, flags=re.I)
            or Path(filename).name != filename
        ):
            raise SourceSchemaError(
                "Lincoln PropertyWeb document filename contract changed",
                url=str(getattr(generation, "url", generator_url)),
                details={"filename": filename},
            )
        document_url = f"{GENERATED_DOCUMENT_URL}/{quote(filename, safe='')}/"
        response = self._request(
            "GET",
            document_url,
            accept="application/pdf,*/*;q=0.8",
            stream=True,
        )
        source_url = str(getattr(response, "url", document_url))
        content, media_type = self._read_pdf(
            response,
            maximum_bytes=maximum_bytes,
            source_url=source_url,
        )
        return PDFArtifact(
            content=content,
            source_url=source_url,
            media_type=media_type,
            generated_filename=filename,
            generator_url=generator_url,
            generation_parameters=dict(parameters),
            retrieval_mode="same_session_filename_generation_then_pdf",
        )


def _table_rows(table: Tag | None) -> list[tuple[list[str], list[Tag]]]:
    """Return direct rows/cells so nested tables remain distinct components."""

    if table is None:
        return []
    rows: list[tuple[list[str], list[Tag]]] = []
    for row in table.find_all("tr", recursive=False):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        rows.append(
            (
                [
                    re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()
                    for cell in cells
                ],
                cells,
            )
        )
    return rows


def _records_from_table(table: Tag | None) -> list[dict[str, Any]]:
    rows = _table_rows(table)
    if len(rows) < 2:
        return []
    headers = [
        _slug(value) or f"column_{index + 1}" for index, value in enumerate(rows[0][0])
    ]
    records: list[dict[str, Any]] = []
    for values, _cells in rows[1:]:
        if not any(_clean(value) for value in values):
            continue
        records.append(
            {
                headers[index]: values[index] if index < len(values) else None
                for index in range(len(headers))
            }
        )
    return records


def _pair_table(table: Tag | None) -> dict[str, str | None]:
    pairs: dict[str, str | None] = {}
    for values, cells in _table_rows(table):
        if len(values) != 2:
            continue
        label = _slug(values[0])
        if not label or "title" in (cells[0].get("class") or []):
            continue
        pairs[label] = _clean(values[1])
    return pairs


def _tag_value(soup: BeautifulSoup, element_id: str) -> str | None:
    element = soup.find(id=element_id)
    if not isinstance(element, Tag):
        return None
    direct_link = element.find("a", recursive=False)
    if isinstance(direct_link, Tag):
        return _clean(direct_link)
    return _clean(element)


def _extract_first(patterns: Sequence[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return _clean(match.group(1))
    return None


def _ui_link_exposed(
    soup: BeautifulSoup,
    html: str,
    button_id: str,
) -> bool:
    if soup.find(id=button_id) is not None:
        return True
    marker = re.escape(button_id)
    conditional = re.search(
        r"if\s*\((?P<condition>[^)]*)\)\s*\{?\s*"
        r"[^;]{0,500}?" + marker,
        html,
        flags=re.I | re.S,
    )
    if conditional:
        comparisons = re.findall(
            r'["\'](True|False)["\']\s*==\s*["\']True["\']',
            conditional.group("condition"),
            flags=re.I,
        )
        if comparisons:
            return all(value.casefold() == "true" for value in comparisons)
    return bool(re.search(marker, html, flags=re.I))


def _structural_table_contract(soup: BeautifulSoup) -> list[dict[str, Any]]:
    contract: list[dict[str, Any]] = []
    for table in soup.find_all("table", id=True):
        table_id = str(table.get("id"))
        rows = _table_rows(table)
        headers = rows[0][0] if rows else []
        contract.append(
            {
                "id": table_id,
                "headers": headers,
                "classes": sorted(str(value) for value in table.get("class", [])),
            }
        )
    return contract


def _parse_taxing_districts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    container = soup.find(id="divTaxingUnits")
    if not isinstance(container, Tag):
        return []
    table = container.find("table", class_="datatable")
    return [
        {
            "code": _clean(record.get("code")),
            "description": _clean(record.get("description")),
            "raw_fields": record,
        }
        for record in _records_from_table(table)
    ]


def _parse_related_properties(
    soup: BeautifulSoup,
) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    table = soup.find(id="tblRelatedProperties")
    if not isinstance(table, Tag):
        return [], {}
    pairs = _pair_table(table)
    records: list[dict[str, Any]] = []
    for link in table.find_all("a", href=True):
        native_href = str(link["href"])
        href = (
            _source_url(native_href)
            if native_href.startswith(("/", BASE_URL))
            else None
        )
        property_match = re.search(
            r"/PropertyQuickRefID/([^/]+)",
            href or native_href,
            re.I,
        )
        party_match = re.search(
            r"/PartyQuickRefID/([^/]+)",
            href or native_href,
            re.I,
        )
        records.append(
            {
                "label": _clean(link),
                "source_url": href,
                "native_href": native_href,
                "property_quick_ref": (
                    property_match.group(1) if property_match else None
                ),
                "party_quick_ref": party_match.group(1) if party_match else None,
            }
        )
    return records, pairs


def _parse_improvements(soup: BeautifulSoup) -> list[dict[str, Any]]:
    improvements: list[dict[str, Any]] = []
    for summary_table in soup.select("table[id^='tblImprovementTable']"):
        suffix = str(summary_table.get("id", "")).removeprefix("tblImprovementTable")
        rows = _table_rows(summary_table)
        if len(rows) < 2:
            continue
        headers = [_slug(value) or "expansion_state" for value in rows[0][0]]
        values = rows[1][0]
        source_fields = {
            headers[index]: _clean(values[index]) if index < len(values) else None
            for index in range(len(headers))
        }
        segment_table = soup.find(id=f"tblSegmentTable{suffix}")
        segments: list[dict[str, Any]] = []
        if isinstance(segment_table, Tag):
            segment_rows = _table_rows(segment_table)
            segment_headers = (
                [_slug(value) for value in segment_rows[0][0]] if segment_rows else []
            )
            for row in segment_table.find_all("tr", recursive=False)[1:]:
                wrapper = row.find("table", class_="fullWidthTable")
                if not isinstance(wrapper, Tag):
                    continue
                direct_rows = _table_rows(wrapper)
                if not direct_rows:
                    continue
                segment_values = direct_rows[0][0]
                segment_fields = {
                    segment_headers[index]: (
                        _clean(segment_values[index])
                        if index < len(segment_values)
                        else None
                    )
                    for index in range(len(segment_headers))
                    if segment_headers[index]
                }
                detail_fields: dict[str, str | None] = {}
                detail_table = wrapper.find("table", class_="segmentDetailsTable")
                if isinstance(detail_table, Tag):
                    for detail_values, _detail_cells in _table_rows(detail_table):
                        for index in range(0, len(detail_values) - 1, 2):
                            label = _slug(detail_values[index])
                            if label:
                                detail_fields[label] = _clean(detail_values[index + 1])
                segments.append(
                    {
                        "segment_id": _clean(segment_fields.get("id")),
                        "segment_type": _clean(segment_fields.get("segment_type")),
                        "segment_class": _clean(segment_fields.get("segment_class")),
                        "year_built": _integer(segment_fields.get("year_built")),
                        "area": _number(segment_fields.get("area")),
                        "details": detail_fields,
                        "raw_fields": segment_fields,
                    }
                )
        improvement_number = _clean(source_fields.get("improvement_1"))
        for key, value in source_fields.items():
            if key.startswith("improvement_") and value:
                improvement_number = value
                break
        improvements.append(
            {
                "improvement_number": improvement_number,
                "improvement_type": _clean(source_fields.get("improvement_type")),
                "bedrooms": _integer(source_fields.get("beds")),
                "segments": segments,
                "raw_fields": source_fields,
            }
        )
    return improvements


def _parse_land(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table = soup.find(id=re.compile(r"_tblLandSegmentsData$"))
    records: list[dict[str, Any]] = []
    for raw in _records_from_table(table if isinstance(table, Tag) else None):
        state_code = _clean(raw.get("state_code"))
        if state_code and state_code.casefold() == "totals":
            continue
        size = _clean(raw.get("land_size"))
        size_match = re.search(
            r"-?\d[\d,]*(?:\.\d+)?",
            size or "",
        )
        records.append(
            {
                "state_code": state_code,
                "segment_type": _clean(raw.get("segment_type")),
                "land_size": size,
                "land_size_value": (
                    _number(size_match.group(0)) if size_match else None
                ),
                "land_size_unit": (
                    "acres" if size and "acre" in size.casefold() else None
                ),
                "raw_fields": raw,
            }
        )
    return records


def _parse_values(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table = soup.find(id=re.compile(r"_tblValueHistoryData"))
    records: list[dict[str, Any]] = []
    for raw in _records_from_table(table if isinstance(table, Tag) else None):
        year_label = _clean(raw.get("year"))
        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", year_label or "")
        records.append(
            {
                "tax_year": int(year_match.group(1)) if year_match else None,
                "year_label": year_label,
                "value_state": (
                    "in_process"
                    if year_label and "in process" in year_label.casefold()
                    else "certified"
                ),
                "improvement_value": _number(raw.get("improvements")),
                "land_value": _number(raw.get("land")),
                "real_market_value": _number(raw.get("rmv")),
                "special_use_value": _number(raw.get("special_use")),
                "assessed_value": _number(raw.get("assessed_value")),
                "raw_fields": raw,
            }
        )
    return records


def _recorder_instrument(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    compact = re.sub(r"\D", "", raw_value)
    if not re.fullmatch(r"(?:19|20)\d{7,8}", compact):
        return None
    return f"{compact[:4]}-{compact[4:].zfill(6)}"


def _parse_sales(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table = soup.find(id=re.compile(r"_tblSalesHistoryData$"))
    records: list[dict[str, Any]] = []
    for raw in _records_from_table(table if isinstance(table, Tag) else None):
        instrument = _clean(raw.get("inst"))
        if instrument is None:
            instrument = _clean(raw.get("inst_"))
        normalized_instrument = _recorder_instrument(instrument)
        records.append(
            {
                "sale_date": _iso_date(raw.get("sale_date")),
                "sale_date_raw": _clean(raw.get("sale_date")),
                "seller": _clean(raw.get("seller")),
                "buyer": _clean(raw.get("buyer")),
                "instrument_number": instrument,
                "sale_price": _number(raw.get("sale_price")),
                "instrument_type": _clean(raw.get("inst_type")),
                "recorder_join_candidate": (
                    {
                        "source_id": "us-or-lincoln-helion-recorder",
                        "instrument_number": normalized_instrument,
                        "raw_instrument_number": instrument,
                    }
                    if normalized_instrument
                    else None
                ),
                "raw_fields": raw,
            }
        )
    return records


def _parse_statement_document(
    cell: Tag,
    *,
    property_quick_ref: str,
) -> dict[str, Any] | None:
    link = cell.find("a")
    if not isinstance(link, Tag):
        return None
    tax_year = _integer(link)
    if tax_year is None:
        return None
    onclick = str(link.get("onclick") or "")
    generated = re.search(
        r"OpenTaxStatementPDF\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
        r"['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        onclick,
        flags=re.I,
    )
    if generated:
        property_id, party_id, generated_year = generated.groups()
        return {
            "document_kind": "tax_statement",
            "tax_year": int(generated_year),
            "retrieval_mode": "same_session_filename_generation_then_pdf",
            "generator_url": DOCUMENT_GENERATORS["tax-statement"],
            "generation_parameters": {
                "PropertyID": property_id,
                "PartyID": party_id,
                "TaxYear": generated_year,
                "EffectiveDate": f"11-15-{generated_year}",
            },
        }
    href = _clean(link.get("href"))
    if href:
        return {
            "document_kind": "tax_statement",
            "tax_year": tax_year,
            "retrieval_mode": "direct_historical_pdf",
            "source_url": _source_url(href),
            "generation_parameters": {
                "PropertyQuickRefID": property_quick_ref,
                "TaxYear": tax_year,
            },
        }
    return None


def _parse_bills(
    soup: BeautifulSoup,
    *,
    property_quick_ref: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table = soup.find(id="tblBillsTable")
    rows = _table_rows(table if isinstance(table, Tag) else None)
    if len(rows) < 2:
        return [], []
    headers = [_slug(value) for value in rows[0][0]]
    bills: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    active_bill: dict[str, Any] | None = None
    for values, cells in rows[1:]:
        raw = {
            headers[index]: values[index] if index < len(values) else None
            for index in range(len(headers))
            if headers[index]
        }
        first = _clean(values[0] if values else None)
        if first is None:
            continue
        if first.casefold().startswith("installment"):
            installment = {
                "installment": first,
                "total_billed": _number(raw.get("total_billed")),
                "interest": _number(raw.get("interest")),
                "date_paid": _iso_date(raw.get("date_paid")),
                "date_paid_raw": _clean(raw.get("date_paid")),
                "total_owed": _number(raw.get("total_owed")),
                "raw_fields": raw,
            }
            if active_bill is not None:
                active_bill["installments"].append(installment)
            continue
        tax_year = _integer(first)
        active_bill = {
            "tax_year": tax_year,
            "total_billed": _number(raw.get("total_billed")),
            "ad_valorem": _number(raw.get("ad_valorem")),
            "special_assessment": _number(raw.get("special_asmt")),
            "principal": _number(raw.get("principal")),
            "interest": _number(raw.get("interest")),
            "date_paid": _iso_date(raw.get("date_paid")),
            "date_paid_raw": _clean(raw.get("date_paid")),
            "total_owed": _number(raw.get("total_owed")),
            "installments": [],
            "raw_fields": raw,
        }
        bills.append(active_bill)
        statement = _parse_statement_document(
            cells[0],
            property_quick_ref=property_quick_ref,
        )
        if statement:
            documents.append(statement)
    return bills, documents


def _parse_payments(
    soup: BeautifulSoup,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table = soup.find(id="tblPaymentHistoryTable")
    rows = _table_rows(table if isinstance(table, Tag) else None)
    if len(rows) < 2:
        return [], []
    headers = [_slug(value) for value in rows[0][0]]
    payments: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    for values, cells in rows[1:]:
        raw = {
            headers[index]: values[index] if index < len(values) else None
            for index in range(len(headers))
            if headers[index]
        }
        year_link = cells[0].find("a", recursive=False)
        year_value = _clean(year_link if isinstance(year_link, Tag) else values[0])
        receipt_link = cells[1].find("a") if len(cells) > 1 else None
        receipt_number = _clean(
            receipt_link if isinstance(receipt_link, Tag) else raw.get("receipt_number")
        )
        onclick = (
            str(receipt_link.get("onclick") or "")
            if isinstance(receipt_link, Tag)
            else ""
        )
        receipt_match = re.search(
            r"OpenReceiptPDF\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
            r"['\"]([^'\"]+)['\"]\s*\)",
            onclick,
            flags=re.I,
        )
        quick_ref = receipt_match.group(1) if receipt_match else None
        transaction_id = receipt_match.group(2) if receipt_match else None
        payments.append(
            {
                "tax_year": _integer(year_value),
                "tax_year_label": year_value,
                "receipt_number": receipt_number,
                "transaction_id": transaction_id,
                "transaction_date": _iso_date(raw.get("transaction_date")),
                "transaction_date_raw": _clean(raw.get("transaction_date")),
                "payment_amount": _number(raw.get("payment_amount")),
                "raw_fields": raw,
            }
        )
        if quick_ref and transaction_id:
            documents.append(
                {
                    "document_kind": "payment_receipt",
                    "receipt_number": receipt_number,
                    "transaction_id": transaction_id,
                    "retrieval_mode": ("same_session_filename_generation_then_pdf"),
                    "generator_url": DOCUMENT_GENERATORS["receipt"],
                    "generation_parameters": {
                        "QuickRefID": quick_ref,
                        "TransactionID": transaction_id,
                    },
                }
            )
    return payments, documents


def _keyword_sections(
    soup: BeautifulSoup,
    keyword: str,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        title_cell = table.find(class_="sectionHeader")
        title = _clean(title_cell)
        if title is None or keyword.casefold() not in title.casefold():
            continue
        nested = table.find("table", class_="datatable")
        sections.append(
            {
                "title": title,
                "table_id": _clean(table.get("id")),
                "records": _records_from_table(
                    nested if isinstance(nested, Tag) else table
                ),
            }
        )
    return sections


def parse_detail_page(
    html: str,
    source_url: str,
    *,
    expected_property_quick_ref: str | None = None,
    expected_party_quick_ref: str | None = None,
) -> dict[str, Any]:
    """Parse the public PropertyWeb detail page and document representations."""

    soup = BeautifulSoup(html, "lxml")
    header = soup.find(id="tblPropertyHeaderInfo")
    general_table = soup.find(id="tblGeneralInformation")
    if not isinstance(header, Tag) or not isinstance(general_table, Tag):
        raise SourceSchemaError(
            "Lincoln PropertyWeb detail tables changed",
            url=source_url,
        )
    property_quick_ref = _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdPropertyID")
    if property_quick_ref is None:
        property_quick_ref = _extract_first(
            [r"/PropertyQuickRefID/([^/\"']+)"], source_url
        )
    route_party = _extract_first([r"/PartyQuickRefID/([^/\"']+)"], source_url)
    party_quick_ref = route_party or _extract_first(
        [r'link\.replace\(/\{PartyQuickRef\}/g,\s*"([^"]+)"\)'],
        html,
    )
    if property_quick_ref is None or party_quick_ref is None:
        raise SourceSchemaError(
            "Lincoln PropertyWeb detail identity changed",
            url=source_url,
        )
    if (
        expected_property_quick_ref
        and property_quick_ref.casefold() != expected_property_quick_ref.casefold()
    ):
        raise SourceSchemaError(
            "Lincoln PropertyWeb returned a different property account",
            url=source_url,
            details={
                "requested": expected_property_quick_ref,
                "returned": property_quick_ref,
            },
        )
    if (
        expected_party_quick_ref
        and party_quick_ref.casefold() != expected_party_quick_ref.casefold()
    ):
        raise SourceSchemaError(
            "Lincoln PropertyWeb returned a different owner-party context",
            url=source_url,
            details={
                "requested": expected_party_quick_ref,
                "returned": party_quick_ref,
            },
        )

    property_id = _extract_first(
        [
            r'link\.replace\(/\{PropertyID\}/g,\s*"([^"]+)"\)',
            r"\bPropertyID\s*:\s*[\"']([^\"']+)[\"']",
        ],
        html,
    )
    property_owner_id = _extract_first(
        [r'link\.replace\(/\{PropertyOwnerID\}/g,\s*"([^"]+)"\)'],
        html,
    )
    internal_party_id = _extract_first(
        [
            r"\bPartyID\s*:\s*[\"']([^\"']+)[\"']",
            r"OpenTaxStatementPDF\(\s*['\"][^'\"]+['\"]\s*,\s*"
            r"['\"]([^'\"]+)['\"]",
        ],
        html,
    )
    appraisal_format = _extract_first(
        [r"\bReportFormatID\s*:\s*[\"']([^\"']+)[\"']"],
        html,
    )
    effective_year = _extract_first([r"\bvar\s+effYear\s*=\s*(\d{4})"], html)
    effective_month = _extract_first([r"\bvar\s+effMonth\s*=\s*(\d{1,2})"], html)
    effective_day = _extract_first([r"\bvar\s+effDay\s*=\s*(\d{1,2})"], html)
    effective_date = None
    if effective_year and effective_month and effective_day:
        effective_date = (
            f"{int(effective_year):04d}-{int(effective_month):02d}-"
            f"{int(effective_day):02d}"
        )

    header_rows = _table_rows(header)
    header_values = header_rows[1][0] if len(header_rows) > 1 else []
    owner_name = _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdOwnerName")
    situs_address = _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdPropertyAddress")
    current_display_value = _number(
        _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdTotalAssessedValue")
    )
    general = _pair_table(general_table)
    owner_table = soup.find(id="tblOwnerInformation")
    owner = _pair_table(owner_table if isinstance(owner_table, Tag) else None)
    mailing_tag = soup.find(id="dnn_ctr425_JosephineGuestView_tdOIMailingAddress")
    mailing_lines = _lines(mailing_tag if isinstance(mailing_tag, Tag) else None)
    taxing_districts = _parse_taxing_districts(soup)
    related_properties, related_raw = _parse_related_properties(soup)
    improvements = _parse_improvements(soup)
    land_segments = _parse_land(soup)
    value_history = _parse_values(soup)
    sales = _parse_sales(soup)
    bills, statement_documents = _parse_bills(
        soup,
        property_quick_ref=property_quick_ref,
    )
    payments, receipt_documents = _parse_payments(soup)
    exemptions = _keyword_sections(soup, "exempt")
    tax_due_summary = {
        "effective_date": effective_date,
        "current_year_due": _number(
            _tag_value(
                soup,
                "dnn_ctr425_JosephineGuestView_tdPMCurrentAmountDue",
            )
        ),
        "past_years_due": _number(
            _tag_value(
                soup,
                "dnn_ctr425_JosephineGuestView_tdPMPastYearsDue",
            )
        ),
        "total_due": _number(
            _tag_value(
                soup,
                "dnn_ctr425_JosephineGuestView_tdPMTotalDue",
            )
        ),
    }

    tax_year = _integer(_tag_value(soup, "dnn_ctr425_JosephineGuestView_tdGITitle"))
    if tax_year is None and value_history:
        tax_year = value_history[0].get("tax_year")
    map_number = _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdGIMapNumber")
    levy_code = _tag_value(soup, "dnn_ctr425_JosephineGuestView_tdGITaxingUnitGroup")
    map_url = (
        "https://maps.co.lincoln.or.us/?service=search-Taxlots&"
        f"field:parcelid={quote(map_number, safe='')}"
        if map_number
        else None
    )

    documents: list[dict[str, Any]] = [
        {
            "document_kind": "property_detail_html",
            "retrieval_mode": "anonymous_server_rendered_html",
            "retrieval_state": "retrieved",
            "source_url": source_url,
            "media_type": "text/html",
            "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "size_bytes": len(html.encode("utf-8")),
        }
    ]
    if map_url:
        documents.append(
            {
                "document_kind": "taxlot_map",
                "retrieval_mode": "external_official_map_link",
                "retrieval_state": "link_available",
                "source_url": map_url,
                "map_number": map_number,
            }
        )
    if property_id and tax_year:
        documents.append(
            {
                "document_kind": "appraisal_card",
                "retrieval_mode": ("same_session_filename_generation_then_pdf"),
                "retrieval_state": "generator_contract_published",
                "generator_url": DOCUMENT_GENERATORS["appraisal-card"],
                "generation_parameters": {
                    "PropertyID": property_id,
                    "TaxYear": str(tax_year),
                    "ReportFormatID": (appraisal_format or APPRAISAL_REPORT_FORMAT_ID),
                },
                "ui_exposed": _ui_link_exposed(
                    soup,
                    html,
                    "btnAppraisalCard",
                ),
            }
        )
    if property_id and internal_party_id and tax_year and effective_date:
        documents.append(
            {
                "document_kind": "account_summary",
                "retrieval_mode": ("same_session_filename_generation_then_pdf"),
                "retrieval_state": "generator_contract_published",
                "generator_url": DOCUMENT_GENERATORS["account-summary"],
                "generation_parameters": {
                    "PropertyID": property_id,
                    "TaxYear": str(tax_year),
                    "EffectiveDate": datetime.fromisoformat(effective_date).strftime(
                        "%-m/%-d/%Y"
                    ),
                    "PartyID": internal_party_id,
                },
                "ui_exposed": _ui_link_exposed(
                    soup,
                    html,
                    "btnAccountSummary",
                ),
            }
        )
    documents.extend(statement_documents)
    documents.extend(receipt_documents)

    table_contract = _structural_table_contract(soup)
    stable_table_ids = {
        "tblPropertyHeaderInfo",
        "tblGeneralInformation",
        "tblOwnerInformation",
        "tblBillsTable",
        "tblPaymentHistoryTable",
    }
    structural_contract = {
        "county_title": _clean(
            soup.find(id="dnn_ctr425_JosephineGuestView_tdDistrictTitle")
        ),
        "required_table_contract": [
            item for item in table_contract if item["id"] in stable_table_ids
        ],
        "generators": sorted(
            key for key, endpoint in DOCUMENT_GENERATORS.items() if endpoint in html
        ),
        "detail_identity_fields": {
            "property_quick_ref": property_quick_ref is not None,
            "party_quick_ref": party_quick_ref is not None,
            "property_id": property_id is not None,
            "property_owner_id": property_owner_id is not None,
            "party_id": internal_party_id is not None,
        },
    }
    source_html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "property_account",
        property_quick_ref,
    )
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": source_url,
        "record_kind": "property_account_detail",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous",
        "property_quick_ref": property_quick_ref,
        "party_quick_ref": party_quick_ref,
        "property_id": property_id,
        "property_owner_id": property_owner_id,
        "party_id": internal_party_id,
        "native_ids": {
            "property_quick_ref": property_quick_ref,
            "party_quick_ref": party_quick_ref,
            "property_id": property_id,
            "property_owner_id": property_owner_id,
            "party_id": internal_party_id,
        },
        "tax_year": tax_year,
        "effective_date": effective_date,
        "owner_name": owner_name,
        "situs_address": situs_address,
        "mailing_address_lines": mailing_lines,
        "current_display_value": current_display_value,
        "header_values": header_values,
        "property_status": _clean(general.get("property_status")),
        "property_type": _clean(general.get("property_type")),
        "legal_description": _clean(general.get("legal_description")),
        "alternate_account_number": _clean(general.get("alternate_account_number")),
        "neighborhood": _clean(general.get("neighborhood")),
        "map_number": map_number,
        "property_use": _clean(general.get("property_use")),
        "levy_code_area": levy_code,
        "zoning": _clean(general.get("zoning")),
        "general_information": general,
        "owner_information": owner,
        "taxing_districts": taxing_districts,
        "related_properties": related_properties,
        "related_properties_raw": related_raw,
        "exemptions": exemptions,
        "improvements": improvements,
        "land_segments": land_segments,
        "value_history": value_history,
        "sales_history": sales,
        "tax_due_summary": tax_due_summary,
        "bills": bills,
        "payment_history": payments,
        "document_representations": documents,
        "join_candidates": {
            TAXLOT_WFS_SOURCE_ID: {
                "map_number": map_number,
                "relationship": "parcel_geometry_and_owner_complement",
            },
            RECORDER_SOURCE_ID: [
                record["recorder_join_candidate"]
                for record in sales
                if record["recorder_join_candidate"]
            ],
        },
        "source_html_sha256": source_html_sha256,
        "source_html_size_bytes": len(html.encode("utf-8")),
        "response_schema_fingerprint": sha256_fingerprint(structural_contract),
        "source_table_contract": table_contract,
    }


def _property_types(value: str) -> tuple[str, ...]:
    requested = tuple(
        dict.fromkeys(item.strip().upper() for item in value.split(",") if item.strip())
    )
    unknown = sorted(set(requested) - set(PROPERTY_TYPE_LABELS))
    if unknown:
        raise argparse.ArgumentTypeError(
            "unknown PropertyWeb property type(s): " + ", ".join(unknown)
        )
    if not requested:
        raise argparse.ArgumentTypeError(
            "at least one PropertyWeb property type is required"
        )
    return requested


def _criteria_payload(
    *,
    term: str,
    tax_year: int,
    property_value_tax_year: int,
    sort_type: int,
    sort_order: int,
    property_types: Sequence[str],
) -> dict[str, Any]:
    return {
        "term": term,
        "tax_year": tax_year,
        "property_value_tax_year": property_value_tax_year,
        "sort_type": sort_type,
        "sort_order": sort_order,
        "property_types": list(property_types),
    }


def _encode_cursor(state: Mapping[str, Any]) -> str:
    payload = {"v": CURSOR_VERSION, **dict(state)}
    token = base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    )
    return CURSOR_PREFIX + token.rstrip("=")


def _decode_cursor(value: str) -> dict[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise PropertyWebSelectionError(
            "cursor_source_mismatch",
            "Continuation belongs to another source or adapter version",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PropertyWebSelectionError(
            "cursor_invalid",
            "Continuation is not valid Lincoln PropertyWeb cursor data",
        ) from error
    required = {
        "v",
        "criteria",
        "tax_year",
        "property_value_tax_year",
        "page",
        "offset",
        "guard_page",
        "guard_snapshot",
        "schema",
        "record_count",
        "total_pages",
    }
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise PropertyWebSelectionError(
            "cursor_invalid",
            "Continuation is missing Lincoln PropertyWeb paging state",
        )
    if payload["v"] != CURSOR_VERSION:
        raise PropertyWebSelectionError(
            "cursor_version_changed",
            "Continuation uses an unsupported Lincoln PropertyWeb cursor version",
        )
    for field in (
        "tax_year",
        "property_value_tax_year",
        "page",
        "offset",
        "guard_page",
        "record_count",
        "total_pages",
    ):
        if isinstance(payload[field], bool) or not isinstance(payload[field], int):
            raise PropertyWebSelectionError(
                "cursor_invalid",
                f"Continuation field {field} is not an integer",
            )
    for field in ("criteria", "guard_snapshot", "schema"):
        if not isinstance(payload[field], str) or not re.fullmatch(
            r"[0-9a-f]{64}", payload[field]
        ):
            raise PropertyWebSelectionError(
                "cursor_invalid",
                f"Continuation field {field} is not a fingerprint",
            )
    if payload["page"] < 1 or payload["guard_page"] < 1 or payload["offset"] < 0:
        raise PropertyWebSelectionError(
            "cursor_invalid",
            "Continuation contains an invalid page or offset",
        )
    return payload


def _search_query(
    *,
    term: str,
    tax_year: int,
    property_value_tax_year: int,
    sort_name: str,
    sort_order_name: str,
    property_types: Sequence[str],
    limit: int,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation="search",
            parameters={
                "term": term,
                "tax_year": tax_year,
                "property_value_tax_year": property_value_tax_year,
                "sort": sort_name,
                "sort_order": sort_order_name,
                "property_types": list(property_types),
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "native_page_size": NATIVE_PAGE_SIZE,
                "continuation": ("query_bound_native_page_offset_with_snapshot_guard"),
            },
        ),
    )


def _assert_page_contract(
    page: SearchPage,
    *,
    term: str,
    tax_year: int,
    property_value_tax_year: int,
    expected_schema: str | None,
    expected_record_count: int | None,
    expected_total_pages: int | None,
) -> None:
    if page.search_text.casefold() != term.casefold():
        raise SourceSchemaError(
            "Lincoln PropertyWeb echoed a different search term",
            url=page.source_url,
            details={"requested": term, "returned": page.search_text},
        )
    if page.tax_year != tax_year:
        raise SourceSchemaError(
            "Lincoln PropertyWeb returned a different tax year",
            url=page.source_url,
            details={"requested": tax_year, "returned": page.tax_year},
        )
    if page.property_value_tax_year not in {0, property_value_tax_year}:
        raise SourceSchemaError(
            "Lincoln PropertyWeb returned a different property-value tax year",
            url=page.source_url,
            details={
                "requested": property_value_tax_year,
                "returned": page.property_value_tax_year,
            },
        )
    if expected_schema and page.schema_fingerprint != expected_schema:
        raise PropertyWebSelectionError(
            "cursor_schema_changed",
            "Lincoln PropertyWeb search schema changed since the continuation",
            details={
                "expected": expected_schema,
                "observed": page.schema_fingerprint,
            },
        )
    if expected_record_count is not None and page.record_count != expected_record_count:
        raise PropertyWebSelectionError(
            "cursor_result_set_changed",
            "Lincoln PropertyWeb result count changed since the continuation",
            details={
                "expected": expected_record_count,
                "observed": page.record_count,
            },
        )
    if expected_total_pages is not None and page.total_pages != expected_total_pages:
        raise PropertyWebSelectionError(
            "cursor_result_set_changed",
            "Lincoln PropertyWeb page count changed since the continuation",
            details={
                "expected": expected_total_pages,
                "observed": page.total_pages,
            },
        )


def execute_search(
    args: argparse.Namespace,
    *,
    client: PropertyWebClient | Any,
) -> PublicRecordsResult:
    term = args.term.strip()
    cursor_state = _decode_cursor(args.cursor) if args.cursor else None
    if args.tax_year is not None:
        tax_year = args.tax_year
    elif cursor_state is not None:
        tax_year = cursor_state["tax_year"]
    else:
        tax_year = client.home_contract().tax_year
    if args.property_value_tax_year is not None:
        property_value_tax_year = args.property_value_tax_year
    elif cursor_state is not None:
        property_value_tax_year = cursor_state["property_value_tax_year"]
    else:
        property_value_tax_year = tax_year
    sort_type = SORT_TYPES[args.sort]
    sort_order = SORT_ORDERS[args.sort_order]
    criteria = _criteria_payload(
        term=term,
        tax_year=tax_year,
        property_value_tax_year=property_value_tax_year,
        sort_type=sort_type,
        sort_order=sort_order,
        property_types=args.property_types,
    )
    criteria_fingerprint = sha256_fingerprint(criteria)
    query = _search_query(
        term=term,
        tax_year=tax_year,
        property_value_tax_year=property_value_tax_year,
        sort_name=args.sort,
        sort_order_name=args.sort_order,
        property_types=args.property_types,
        limit=args.limit,
        cursor=args.cursor,
    )
    if cursor_state and cursor_state["criteria"] != criteria_fingerprint:
        raise PropertyWebSelectionError(
            "cursor_query_mismatch",
            "Continuation belongs to a different Lincoln PropertyWeb query",
        )

    page_number = cursor_state["page"] if cursor_state else 1
    offset = cursor_state["offset"] if cursor_state else 0
    expected_schema = cursor_state["schema"] if cursor_state else None
    expected_record_count = cursor_state["record_count"] if cursor_state else None
    expected_total_pages = cursor_state["total_pages"] if cursor_state else None
    guard_page: SearchPage | None = None
    if cursor_state:
        guard_page = client.search_page(
            term=term,
            tax_year=tax_year,
            property_value_tax_year=property_value_tax_year,
            page=cursor_state["guard_page"],
            sort_type=sort_type,
            sort_order=sort_order,
            property_types=args.property_types,
        )
        _assert_page_contract(
            guard_page,
            term=term,
            tax_year=tax_year,
            property_value_tax_year=property_value_tax_year,
            expected_schema=expected_schema,
            expected_record_count=expected_record_count,
            expected_total_pages=expected_total_pages,
        )
        if guard_page.snapshot_fingerprint != cursor_state["guard_snapshot"]:
            raise PropertyWebSelectionError(
                "cursor_snapshot_changed",
                "Lincoln PropertyWeb page contents changed since the continuation",
                details={"guard_page": cursor_state["guard_page"]},
            )

    normalized: list[dict[str, Any]] = []
    current: SearchPage | None = None
    next_cursor: str | None = None
    while len(normalized) < args.limit:
        if guard_page is not None and guard_page.current_page == page_number:
            current = guard_page
            guard_page = None
        else:
            current = client.search_page(
                term=term,
                tax_year=tax_year,
                property_value_tax_year=property_value_tax_year,
                page=page_number,
                sort_type=sort_type,
                sort_order=sort_order,
                property_types=args.property_types,
            )
        _assert_page_contract(
            current,
            term=term,
            tax_year=tax_year,
            property_value_tax_year=property_value_tax_year,
            expected_schema=expected_schema,
            expected_record_count=expected_record_count,
            expected_total_pages=expected_total_pages,
        )
        if expected_schema is None:
            expected_schema = current.schema_fingerprint
            expected_record_count = current.record_count
            expected_total_pages = current.total_pages
        if offset > len(current.raw_records):
            raise PropertyWebSelectionError(
                "cursor_offset_changed",
                "Lincoln PropertyWeb continuation offset exceeds its native page",
                details={
                    "offset": offset,
                    "page_rows": len(current.raw_records),
                },
            )
        available = current.raw_records[offset:]
        remaining = args.limit - len(normalized)
        selected = available[:remaining]
        for index, raw in enumerate(selected, start=offset + 1):
            normalized.append(
                normalize_search_record(
                    raw,
                    source_url=current.source_url,
                    native_page=page_number,
                    native_position=index,
                    schema_fingerprint=current.schema_fingerprint,
                )
            )
        consumed_offset = offset + len(selected)
        if len(normalized) >= args.limit:
            if consumed_offset < len(current.raw_records):
                next_page = page_number
                next_offset = consumed_offset
            elif current.has_more:
                next_page = page_number + 1
                next_offset = 0
            else:
                break
            next_cursor = _encode_cursor(
                {
                    "criteria": criteria_fingerprint,
                    "tax_year": tax_year,
                    "property_value_tax_year": property_value_tax_year,
                    "page": next_page,
                    "offset": next_offset,
                    "guard_page": page_number,
                    "guard_snapshot": current.snapshot_fingerprint,
                    "schema": current.schema_fingerprint,
                    "record_count": current.record_count,
                    "total_pages": current.total_pages,
                }
            )
            break
        if not current.has_more:
            break
        page_number += 1
        offset = 0
    return PublicRecordsResult.success(
        query,
        normalized,
        next_cursor=next_cursor,
    )


def _basic_query(
    operation: str,
    parameters: Mapping[str, Any],
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(operation=operation, parameters=parameters),
    )


def execute_detail(
    args: argparse.Namespace,
    *,
    client: PropertyWebClient | Any,
) -> PublicRecordsResult:
    query = _basic_query(
        "detail",
        {
            "property_quick_ref": args.property_quick_ref,
            "party_quick_ref": args.party_quick_ref,
            "effective_date": args.effective_date,
        },
    )
    page = client.detail(
        args.property_quick_ref,
        args.party_quick_ref,
        effective_date=args.effective_date,
    )
    record = parse_detail_page(
        page.html,
        page.source_url,
        expected_property_quick_ref=args.property_quick_ref,
        expected_party_quick_ref=args.party_quick_ref,
    )
    return PublicRecordsResult.success(query, [record])


def _document_parameters(args: argparse.Namespace) -> dict[str, Any]:
    kind = args.document_kind
    if kind == "tax-statement":
        effective_date = args.effective_date or f"11-15-{args.tax_year}"
        return {
            "PropertyID": args.property_id,
            "PartyID": args.party_id,
            "TaxYear": str(args.tax_year),
            "EffectiveDate": effective_date,
        }
    if kind == "receipt":
        return {
            "QuickRefID": args.property_quick_ref,
            "TransactionID": args.transaction_id,
        }
    if kind == "appraisal-card":
        return {
            "PropertyID": args.property_id,
            "TaxYear": str(args.tax_year),
            "ReportFormatID": args.report_format_id,
        }
    if kind == "account-summary":
        return {
            "PropertyID": args.property_id,
            "TaxYear": str(args.tax_year),
            "EffectiveDate": args.effective_date,
            "PartyID": args.party_id,
        }
    return {
        "PropertyQuickRefID": args.property_quick_ref,
        "TaxYear": str(args.tax_year),
    }


def _document_native_id(
    kind: str,
    parameters: Mapping[str, Any],
) -> str:
    values = ":".join(str(value) for value in parameters.values())
    return f"{kind}:{values}"


def _atomic_binary_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def execute_document(
    args: argparse.Namespace,
    *,
    client: PropertyWebClient | Any,
) -> PublicRecordsResult:
    parameters = _document_parameters(args)
    query = _basic_query(
        "document",
        {
            "document_kind": args.document_kind,
            "parameters": parameters,
            "maximum_bytes": args.max_bytes,
        },
    )
    artifact = client.fetch_document(
        args.document_kind,
        parameters=parameters,
        maximum_bytes=args.max_bytes,
    )
    destination: Path | None = None
    if args.destination:
        destination = Path(args.destination).expanduser().resolve()
        _atomic_binary_write(destination, artifact.content)
    digest = hashlib.sha256(artifact.content).hexdigest()
    native_document_id = _document_native_id(
        args.document_kind,
        parameters,
    )
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "document",
        native_document_id,
    )
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": artifact.source_url,
        "record_kind": "document_artifact",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous",
        "document_kind": args.document_kind,
        "native_document_id": native_document_id,
        "artifact_format": "pdf",
        "media_type": artifact.media_type,
        "retrieval_state": "retrieved",
        "retrieval_mode": artifact.retrieval_mode,
        "generator_url": artifact.generator_url,
        "generated_filename": artifact.generated_filename,
        "generation_parameters": dict(artifact.generation_parameters),
        "sha256": digest,
        "size_bytes": len(artifact.content),
        "local_path": str(destination) if destination else None,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination)] if destination else (),
    )


def execute_probe(
    args: argparse.Namespace,
    *,
    client: PropertyWebClient | Any,
) -> PublicRecordsResult:
    query = _basic_query(
        "probe",
        {
            "property_quick_ref": PROBE_PROPERTY_QUICK_REF,
            "party_quick_ref": PROBE_PARTY_QUICK_REF,
            "with_document": args.with_document,
        },
    )
    home = client.home_contract(refresh=True)
    search = client.search_page(
        term=PROBE_PROPERTY_QUICK_REF,
        tax_year=home.tax_year,
        property_value_tax_year=home.tax_year,
        page=1,
        sort_type=SORT_TYPES["property_id"],
        sort_order=SORT_ORDERS["asc"],
        property_types=DEFAULT_PROPERTY_TYPES,
    )
    match = next(
        (
            raw
            for raw in search.raw_records
            if _clean(raw.get("PropertyQuickRefID")) == PROBE_PROPERTY_QUICK_REF
        ),
        None,
    )
    if match is None:
        raise SourceSchemaError(
            "Lincoln PropertyWeb search sentinel no longer resolves",
            url=search.source_url,
        )
    detail_page = client.detail(
        PROBE_PROPERTY_QUICK_REF,
        PROBE_PARTY_QUICK_REF,
    )
    detail = parse_detail_page(
        detail_page.html,
        detail_page.source_url,
        expected_property_quick_ref=PROBE_PROPERTY_QUICK_REF,
        expected_party_quick_ref=PROBE_PARTY_QUICK_REF,
    )
    document_probe: dict[str, Any] | None = None
    if args.with_document:
        property_id = detail.get("property_id") or PROBE_PROPERTY_ID
        tax_year = detail.get("tax_year") or home.tax_year
        artifact = client.fetch_document(
            "appraisal-card",
            parameters={
                "PropertyID": property_id,
                "TaxYear": str(tax_year),
                "ReportFormatID": APPRAISAL_REPORT_FORMAT_ID,
            },
            maximum_bytes=args.max_bytes,
        )
        document_probe = {
            "document_kind": "appraisal-card",
            "source_url": artifact.source_url,
            "generated_filename": artifact.generated_filename,
            "retrieval_mode": artifact.retrieval_mode,
            "size_bytes": len(artifact.content),
            "sha256": hashlib.sha256(artifact.content).hexdigest(),
        }
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": HOME_URL,
        "record_kind": "source_probe",
        "access_state": "public_anonymous",
        "home": {
            "tax_year": home.tax_year,
            "source_url": home.source_url,
            "source_html_sha256": home.source_html_sha256,
            "schema_fingerprint": home.schema_fingerprint,
        },
        "search": {
            "source_url": search.source_url,
            "record_count": search.record_count,
            "sentinel_found": True,
            "schema_fingerprint": search.schema_fingerprint,
            "snapshot_fingerprint": search.snapshot_fingerprint,
        },
        "detail": {
            "source_url": detail["source_url"],
            "property_quick_ref": detail["property_quick_ref"],
            "party_quick_ref": detail["party_quick_ref"],
            "property_id": detail["property_id"],
            "property_owner_id": detail["property_owner_id"],
            "party_id": detail["party_id"],
            "map_number": detail["map_number"],
            "source_html_sha256": detail["source_html_sha256"],
            "response_schema_fingerprint": detail["response_schema_fingerprint"],
        },
        "document": document_probe,
    }
    return PublicRecordsResult.success(query, [record])


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": "oregon-lincoln-propertyweb-sources/1.0",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "observed_contract": {
            "home": {
                "url": HOME_URL,
                "current_tax_year": "derived_from_published_hidden_input",
            },
            "search": {
                "url": SEARCH_URL,
                "method": "GET",
                "native_page_size": NATIVE_PAGE_SIZE,
                "property_types": dict(PROPERTY_TYPE_LABELS),
                "sort_types": dict(SORT_TYPES),
                "sort_orders": dict(SORT_ORDERS),
            },
            "detail": {
                "route": DETAIL_ROUTE,
                "method": "GET",
                "representation": "server_rendered_html",
            },
            "documents": {
                "generators": dict(DOCUMENT_GENERATORS),
                "generated_retrieval": (f"{GENERATED_DOCUMENT_URL}/{{filename}}/"),
                "historical_route": HISTORICAL_STATEMENT_ROUTE,
                "session_lineage": (
                    "filename generation and PDF fetch use one cookie session"
                ),
            },
        },
        "complements": [
            {
                "kind": "lincoln_taxlot_wfs",
                "source_id": TAXLOT_WFS_SOURCE_ID,
                "relationship": "parcel_geometry_and_owner_complement",
                "join_keys": ["map_number", "taxlot"],
            },
            {
                "source_id": RECORDER_SOURCE_ID,
                "relationship": "recorded_instrument_complement",
                "join_keys": [
                    "sale_instrument",
                    "party_name",
                    "sale_date",
                ],
            },
        ],
    }


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


def _client(args: argparse.Namespace) -> PropertyWebClient:
    return PropertyWebClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        rate_limiter=MinimumIntervalRateLimiter(args.minimum_interval),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: PropertyWebClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, search, detail, document, or probe."""

    if args.command == "sources":
        return _sources_payload()
    active_client = client or _client(args)
    owns_client = client is None
    query: PublicRecordsQuery | None = None
    try:
        if args.command == "search":
            result = execute_search(args, client=active_client)
        elif args.command == "detail":
            result = execute_detail(args, client=active_client)
        elif args.command == "document":
            result = execute_document(args, client=active_client)
        else:
            result = execute_probe(args, client=active_client)
        query = result.query
    except PropertyWebSelectionError as error:
        if args.command == "search":
            cursor_state = None
            if args.cursor:
                try:
                    cursor_state = _decode_cursor(args.cursor)
                except PropertyWebSelectionError:
                    cursor_state = None
            tax_year = args.tax_year or (
                cursor_state["tax_year"] if cursor_state else PROBE_TAX_YEAR
            )
            property_value_tax_year = args.property_value_tax_year or (
                cursor_state["property_value_tax_year"] if cursor_state else tax_year
            )
            query = _search_query(
                term=args.term,
                tax_year=tax_year,
                property_value_tax_year=property_value_tax_year,
                sort_name=args.sort,
                sort_order_name=args.sort_order,
                property_types=args.property_types,
                limit=args.limit,
                cursor=args.cursor,
            )
        elif query is None:
            query = _basic_query(
                args.command,
                {"error_context": "selection_before_source_request"},
            )
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        if query is None:
            query = _basic_query(
                args.command,
                {"error_context": "source_request"},
            )
        result = failure_result(query, error)
    except (KeyError, TypeError, ValueError) as error:
        if query is None:
            query = _basic_query(
                args.command,
                {"error_context": "normalization"},
            )
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
    if log_results:
        _best_effort_log(result.query, result)
    return result


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_document_transport(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
        help="Maximum PDF bytes to read for this retrieval",
    )
    parser.add_argument(
        "--destination",
        help="Optionally save the validated PDF artifact at this path",
    )
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Lincoln County PropertyWeb assessment and tax records"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe verified search, detail, document, and complement routes",
    )
    add_output_args(sources)

    search = sub.add_parser(
        "search",
        help="Search the official PropertyWeb JSON property index",
    )
    search.add_argument("term")
    search.add_argument("--tax-year", type=int)
    search.add_argument("--property-value-tax-year", type=int)
    search.add_argument(
        "--property-types",
        type=_property_types,
        default=DEFAULT_PROPERTY_TYPES,
        metavar="TYPE[,TYPE...]",
    )
    search.add_argument("--sort", choices=tuple(SORT_TYPES), default="property_id")
    search.add_argument(
        "--sort-order",
        choices=tuple(SORT_ORDERS),
        default="asc",
    )
    search.add_argument("--limit", type=int, default=NATIVE_PAGE_SIZE)
    search.add_argument(
        "--cursor",
        help="Query-bound continuation returned by an earlier search",
    )
    _add_transport_arguments(search)

    detail = sub.add_parser(
        "detail",
        help="Fetch one public account detail in its owner-party context",
    )
    detail.add_argument("property_quick_ref")
    detail.add_argument("party_quick_ref")
    detail.add_argument(
        "--effective-date",
        help="Optional source effective date (MM/DD/YYYY or MM-DD-YYYY)",
    )
    _add_transport_arguments(detail)

    document = sub.add_parser(
        "document",
        help="Retrieve and validate one PropertyWeb PDF representation",
    )
    document_sub = document.add_subparsers(
        dest="document_kind",
        required=True,
    )

    tax_statement = document_sub.add_parser("tax-statement")
    tax_statement.add_argument("property_id")
    tax_statement.add_argument("party_id")
    tax_statement.add_argument("tax_year", type=int)
    tax_statement.add_argument(
        "--effective-date",
        help="Generator effective date; defaults to 11-15-TAX_YEAR",
    )
    _add_document_transport(tax_statement)

    receipt = document_sub.add_parser("receipt")
    receipt.add_argument("property_quick_ref")
    receipt.add_argument("transaction_id")
    _add_document_transport(receipt)

    appraisal = document_sub.add_parser("appraisal-card")
    appraisal.add_argument("property_id")
    appraisal.add_argument("tax_year", type=int)
    appraisal.add_argument(
        "--report-format-id",
        default=APPRAISAL_REPORT_FORMAT_ID,
    )
    _add_document_transport(appraisal)

    account = document_sub.add_parser("account-summary")
    account.add_argument("property_id")
    account.add_argument("party_id")
    account.add_argument("tax_year", type=int)
    account.add_argument("--effective-date", required=True)
    _add_document_transport(account)

    historical = document_sub.add_parser("historical-tax-statement")
    historical.add_argument("property_quick_ref")
    historical.add_argument("tax_year", type=int)
    _add_document_transport(historical)

    probe = sub.add_parser(
        "probe",
        help="Verify Home, JSON search, detail, and optionally one generated PDF",
    )
    probe.add_argument(
        "--with-document",
        action="store_true",
        help="Also generate and validate the appraisal-card sentinel",
    )
    probe.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_transport_arguments(probe)
    return parser


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    records = payload.get("records")
    count = len(records) if isinstance(records, list) else 1
    if write_output(
        payload,
        args,
        summary=f"Lincoln PropertyWeb {args.command}",
        result_count=count,
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"{SOURCE_NAME}: search, detail, and five PDF representations")
        return
    print(
        f"Lincoln PropertyWeb {args.command}: {payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for field in ("timeout", "retry_attempts"):
        if getattr(args, field, 1) <= 0:
            parser.error(f"--{field.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "max_bytes", 1) <= 0:
        parser.error("--max-bytes must be positive")
    if hasattr(args, "term") and not args.term.strip():
        parser.error("search term must not be blank")
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
