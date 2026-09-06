#!/usr/bin/env python3
"""Query Los Angeles County property-tax payment and tax-sale records.

This adapter keeps three official representations separate:

* the Assessor parcel layer, used to verify an AIN and route a parcel;
* Treasurer and Tax Collector (TTC) payment history, queried by exact AIN; and
* TTC auction schedules and sale/excess-proceeds publications.

The records share an Assessor Identification Number (AIN), but the adapter does
not merge facts from one representation into another.

Examples:
    uv run python tools/query_los_angeles_ttc.py sources --json
    uv run python tools/query_los_angeles_ttc.py route 2004-001-003 --json
    uv run python tools/query_los_angeles_ttc.py history 2004001003 --json
    uv run python tools/query_los_angeles_ttc.py auctions --json
    uv run python tools/query_los_angeles_ttc.py publications --cycle 2025C
    uv run python tools/query_los_angeles_ttc.py sale-results 2025C --json
    uv run python tools/query_los_angeles_ttc.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

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
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
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
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "CA"
COUNTY_GEOID = "06037"
COUNTY_NAME = "Los Angeles County, California"

ASSESSOR_SOURCE_ID = "us-ca-los-angeles-county-assessor-parcels"
PAYMENT_SOURCE_ID = "us-ca-los-angeles-county-ttc-payment-history"
SALE_SOURCE_ID = "us-ca-los-angeles-county-ttc-tax-sale"

ASSESSOR_PORTAL_URL = "https://portal.assessor.lacounty.gov/"
ASSESSOR_LAYER_URL = (
    "https://public.gis.lacounty.gov/public/rest/services/"
    "LACounty_Cache/LACounty_Parcel/MapServer/0"
)
ASSESSOR_QUERY_URL = f"{ASSESSOR_LAYER_URL}/query"

TTC_BASE_URL = "https://ttc.lacounty.gov/"
PAYMENT_HISTORY_URL = f"{TTC_BASE_URL}property-tax-payment-history/"
PAYMENT_AJAX_URL = f"{TTC_BASE_URL}wp-admin/admin-ajax.php"
AUCTION_SCHEDULE_URL = f"{TTC_BASE_URL}schedule-of-upcoming-auctions/"
AUCTION_CONTACT_URL = f"{TTC_BASE_URL}auction-contact-us/"
AUCTION_NOTICE_URL = f"{TTC_BASE_URL}notice-of-auction-or-sale/"
EXCESS_PROCEEDS_URL = f"{TTC_BASE_URL}notice-of-excess-proceeds/"
TAX_BILL_URL = f"{TTC_BASE_URL}request-duplicate-bill/"
MULTIPLE_PARCELS_URL = (
    f"{TTC_BASE_URL}secured-property-tax-information-request-multiple-parcels/"
)
ANNUAL_BILL_URL = (
    "https://propertytax.lacounty.gov/Home/AnnualSecuredProperty"
)

PAYMENT_ACTION = "phf_fetch_data"
PROBE_AIN = "2004001003"
INVALID_PROBE_AIN = "0000000000"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024

AIN_DIGITS_RE = re.compile(r"^\d{10}$")
AIN_FORMATTED_RE = re.compile(r"^\d{4}-\d{3}-\d{3}$")
HISTORY_CURSOR_RE = re.compile(
    r"^la-ttc:history:(?P<ain>\d{10}):page:(?P<page>[1-9]\d*)$"
)
SALE_CURSOR_RE = re.compile(
    r"^la-ttc:sale:(?P<cycle>\d{4}[A-Z]):offset:(?P<offset>\d+)$"
)
SALE_CYCLE_RE = re.compile(r"\b(?P<cycle>20\d{2}[A-Z])\b", re.I)
SALE_ROW_RE = re.compile(
    r"^\s*(?P<ain>\d{4}-\d{3}-\d{3})\s+"
    r"(?P<item>\d+)\s+\$(?P<purchase>[\d,]+\.\d{2})"
    r"(?:\s+(?P<follow_up>X))?\s+\$(?P<excess>[\d,]+\.\d{2})\s*$"
)

SOURCE_WARNINGS = (
    "Assessor, TTC payment, and TTC tax-sale facts retain separate provenance.",
    "Payment history is not a current-balance or tax-default-status assertion.",
    "A sale publication records the source-published sale result; individual "
    "redemption, removal, and claim status may require the linked TTC route.",
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
)

ASSESSOR_METADATA = SourceMetadata(
    source_id=ASSESSOR_SOURCE_ID,
    name="Los Angeles County Assessor Parcel Data",
    source_role="assessment_parcel_ain_situs_routing",
    base_url=ASSESSOR_PORTAL_URL,
    dataset_id="los-angeles-county-assessor-parcel-layer",
    metadata={
        "authority": "Los Angeles County Assessor",
        "operator": "County of Los Angeles",
        "county_geoid": COUNTY_GEOID,
        "parcel_layer_url": ASSESSOR_LAYER_URL,
        "parcel_query_url": ASSESSOR_QUERY_URL,
        "native_key": "AIN",
    },
)

PAYMENT_METADATA = SourceMetadata(
    source_id=PAYMENT_SOURCE_ID,
    name="Los Angeles County Property Tax Payment History",
    source_role="treasurer_tax_collector_parcel_payment_history",
    base_url=PAYMENT_HISTORY_URL,
    dataset_id="ttc-payment-history",
    metadata={
        "authority": "Los Angeles County Treasurer and Tax Collector",
        "operator": "County of Los Angeles",
        "county_geoid": COUNTY_GEOID,
        "landing_url": PAYMENT_HISTORY_URL,
        "operation_url": PAYMENT_AJAX_URL,
        "operation_action": PAYMENT_ACTION,
        "native_key": "AIN",
        "native_pagination": ["page", "totalPages", "totalRecords"],
        "source_freshness_field": "lastUpdated",
    },
)

SALE_METADATA = SourceMetadata(
    source_id=SALE_SOURCE_ID,
    name="Los Angeles County Tax-Defaulted Property Sales",
    source_role=(
        "treasurer_tax_collector_tax_default_auction_sale_result_redemption_"
        "excess_proceeds_publications"
    ),
    base_url=AUCTION_SCHEDULE_URL,
    dataset_id="ttc-tax-defaulted-property-sales",
    metadata={
        "authority": "Los Angeles County Treasurer and Tax Collector",
        "operator": "County of Los Angeles",
        "county_geoid": COUNTY_GEOID,
        "auction_schedule_url": AUCTION_SCHEDULE_URL,
        "publication_index_url": AUCTION_CONTACT_URL,
        "auction_notice_url": AUCTION_NOTICE_URL,
        "excess_proceeds_url": EXCESS_PROCEEDS_URL,
        "native_keys": ["auction_cycle", "sale_phase", "item", "AIN"],
    },
)

SOURCE_METADATA_BY_ID = {
    ASSESSOR_SOURCE_ID: ASSESSOR_METADATA,
    PAYMENT_SOURCE_ID: PAYMENT_METADATA,
    SALE_SOURCE_ID: SALE_METADATA,
}


class LATTCQueryError(ValueError):
    """A structured caller-input or source-selection error."""

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


class DocumentExtractionUnavailable(PublicRecordsHTTPError):
    """The official artifact is available but no local text extractor is present."""

    result_status = ResultStatus.HUMAN_REQUIRED
    category = "document_extraction"
    code = "pdf_text_extractor_unavailable"


@dataclass(frozen=True)
class ResponseArtifact:
    content: bytes
    source_url: str
    headers: Mapping[str, str]
    status_code: int


@dataclass(frozen=True)
class PaymentBootstrap:
    ajax_url: str
    nonce: str
    script_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class PaymentPage:
    rows: tuple[Mapping[str, Any], ...]
    meta: Mapping[str, Any]
    native_page: int
    no_result: bool
    native_state: Mapping[str, Any] | None
    schema_fingerprint: str


@dataclass(frozen=True)
class PublicationArtifact:
    kind: str
    cycle: str
    label: str
    url: str
    index_url: str
    phase_coverage: tuple[str, ...]
    wordpress_upload_month: str | None

    def to_record(self) -> dict[str, Any]:
        native_id = hashlib.sha256(self.url.encode("utf-8")).hexdigest()
        return {
            "canonical_ref": canonical_property_ref(
                SALE_SOURCE_ID,
                COUNTY_GEOID,
                "tax_sale_publication",
                f"{self.kind}:{self.cycle}:{native_id}",
            ),
            "source_id": SALE_SOURCE_ID,
            "record_kind": "tax_sale_publication",
            "native_ids": {
                "auction_cycle": self.cycle,
                "artifact_sha256_of_url": native_id,
            },
            "auction_cycle": self.cycle,
            "publication_kind": self.kind,
            "label": self.label,
            "phase_coverage": list(self.phase_coverage),
            "publication_date": None,
            "publication_date_basis": None,
            "wordpress_upload_month": self.wordpress_upload_month,
            "source_url": self.url,
            "publication_index_url": self.index_url,
            "operation_state": "official_artifact_indexed",
            "join_candidates": {
                "parcel_key": {
                    "field": "ain",
                    "available_after_document_extraction": True,
                    "target_source_ids": [
                        ASSESSOR_SOURCE_ID,
                        PAYMENT_SOURCE_ID,
                    ],
                }
            },
        }


@dataclass(frozen=True)
class SaleResultRow:
    formatted_ain: str
    ain: str
    item: str
    purchase_price_raw: str
    purchase_price: str
    excess_proceeds_raw: str
    excess_proceeds: str
    phase: str


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip()
    return cleaned or None


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return _clean_text(value)
    return None


def normalize_ain(value: str) -> str:
    """Return the exact ten-digit TTC AIN accepted by the official operation."""

    candidate = str(value).strip()
    if AIN_DIGITS_RE.fullmatch(candidate):
        return candidate
    if AIN_FORMATTED_RE.fullmatch(candidate):
        return candidate.replace("-", "")
    raise LATTCQueryError(
        "invalid_ain",
        "AIN must contain ten digits, optionally formatted as ####-###-###",
        details={"value": candidate},
    )


def format_ain(value: str) -> str:
    ain = normalize_ain(value)
    return f"{ain[:4]}-{ain[4:7]}-{ain[7:]}"


def _decimal_text(value: Any, field_name: str) -> str:
    raw = _clean_text(value)
    if raw is None:
        raise ValueError(f"{field_name} is blank")
    try:
        parsed = Decimal(raw.replace(",", "").replace("$", ""))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} is not a decimal amount: {raw!r}") from error
    if not parsed.is_finite():
        raise ValueError(f"{field_name} is not finite")
    return format(parsed, "f")


def _source_date(value: Any, field_name: str) -> str:
    raw = _clean_text(value)
    if raw is None:
        raise ValueError(f"{field_name} is blank")
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(f"{field_name} has an unexpected date: {raw!r}") from error


def _source_schema_error(
    message: str,
    *,
    url: str,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=url, details=details)


def _checked_status(response: Any, *, url: str) -> None:
    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")
    text = text if isinstance(text, str) else str(text)
    if status_code == 429:
        raise RateLimitedHTTPError(status_code, url=url, response_text=text)
    if status_code in {401, 403}:
        raise RestrictedHTTPError(status_code, url=url, response_text=text)
    if status_code == 451:
        raise TermsBlockedHTTPError(status_code, url=url, response_text=text)
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(status_code, url=url, response_text=text)
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(status_code, url=url, response_text=text)


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    value = _header(headers, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class LosAngelesTTCClient:
    """Same-session TTC/Assessor client with bounded retries and rate limiting."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.headers = {
            "Accept": "text/html,application/json,application/pdf;q=0.9,*/*;q=0.8",
            "User-Agent": "Ithildin public-record source adapter",
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
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        response: Any | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    params=dict(params or {}),
                    data=dict(data or {}),
                    headers={**self.headers, **dict(headers or {})},
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Los Angeles County public-record request failed",
                        url=url,
                        details={"error": str(error), "attempts": attempt},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code not in self.retry_policy.retry_statuses
                or attempt >= self.retry_policy.max_attempts
            ):
                break
            self.sleeper(
                self.retry_policy.delay(attempt, _retry_after(response))
            )
        if response is None:
            raise TransportError(
                "Los Angeles County public-record request produced no response",
                url=url,
            )
        _checked_status(response, url=url)
        return response

    def html(self, url: str) -> str:
        response = self._request("GET", url)
        headers = getattr(response, "headers", {})
        content_type = (
            _header(headers, "content-type")
            if isinstance(headers, Mapping)
            else None
        )
        if content_type and "html" not in content_type.casefold():
            raise _source_schema_error(
                "Official Los Angeles County page returned non-HTML content",
                url=url,
                details={"content_type": content_type},
            )
        text = getattr(response, "text", "")
        return text if isinstance(text, str) else str(text)

    def json_get(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        response = self._request("GET", url, params=params)
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise _source_schema_error(
                "Official Los Angeles County endpoint returned invalid JSON",
                url=url,
            ) from error
        if not isinstance(payload, Mapping):
            raise _source_schema_error(
                "Official Los Angeles County JSON root changed",
                url=url,
                details={"root_type": type(payload).__name__},
            )
        return payload

    def json_post(
        self,
        url: str,
        *,
        data: Mapping[str, Any],
        referer: str,
    ) -> Mapping[str, Any]:
        response = self._request(
            "POST",
            url,
            data=data,
            headers={
                "Accept": "application/json",
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise _source_schema_error(
                "TTC payment operation returned invalid JSON",
                url=url,
            ) from error
        if not isinstance(payload, Mapping):
            raise _source_schema_error(
                "TTC payment JSON root changed",
                url=url,
                details={"root_type": type(payload).__name__},
            )
        return payload

    def bytes(
        self,
        url: str,
        *,
        max_bytes: int,
    ) -> ResponseArtifact:
        response = self._request("GET", url)
        headers_raw = getattr(response, "headers", {})
        headers = {
            str(key): str(value)
            for key, value in (
                headers_raw.items()
                if isinstance(headers_raw, Mapping)
                else ()
            )
        }
        length = _header(headers, "content-length")
        if length is not None:
            try:
                if int(length) > max_bytes:
                    raise SourceResponseError(
                        "Official TTC artifact exceeds the configured byte bound",
                        url=url,
                        details={
                            "content_length": int(length),
                            "max_bytes": max_bytes,
                        },
                    )
            except ValueError:
                pass
        content = getattr(response, "content", b"")
        if not isinstance(content, bytes):
            content = bytes(content)
        if len(content) > max_bytes:
            raise SourceResponseError(
                "Official TTC artifact exceeds the configured byte bound",
                url=url,
                details={"size": len(content), "max_bytes": max_bytes},
            )
        return ResponseArtifact(
            content=content,
            source_url=str(getattr(response, "url", url)),
            headers=headers,
            status_code=int(getattr(response, "status_code", 0)),
        )

    def assessor_exact(self, ain: str) -> Mapping[str, Any] | None:
        normalized = normalize_ain(ain)
        payload = self.json_get(
            ASSESSOR_QUERY_URL,
            params={
                "f": "json",
                "where": f"AIN = '{normalized}'",
                "outFields": (
                    "OBJECTID,AIN,APN,SitusHouseNo,SitusFraction,"
                    "SitusDirection,SitusUnit,SitusStreet,SitusAddress,"
                    "SitusCity,SitusZIP,SitusFullAddress,UseCode,UseType,"
                    "UseDescription,Roll_Year,LegalDescription,CENTER_LAT,"
                    "CENTER_LON"
                ),
                "returnGeometry": "false",
                "resultRecordCount": 2,
            },
        )
        if payload.get("error"):
            raise SourceResponseError(
                "Los Angeles County Assessor returned an ArcGIS error",
                url=ASSESSOR_QUERY_URL,
                details={"error": payload.get("error")},
            )
        features = payload.get("features")
        if not isinstance(features, list):
            raise _source_schema_error(
                "Los Angeles County Assessor feature collection changed",
                url=ASSESSOR_QUERY_URL,
            )
        if not features:
            return None
        if len(features) != 1:
            raise _source_schema_error(
                "Exact Los Angeles County Assessor AIN resolved ambiguously",
                url=ASSESSOR_QUERY_URL,
                details={"ain": normalized, "feature_count": len(features)},
            )
        feature = features[0]
        attributes = (
            feature.get("attributes")
            if isinstance(feature, Mapping)
            else None
        )
        if not isinstance(attributes, Mapping):
            raise _source_schema_error(
                "Los Angeles County Assessor feature lacks attributes",
                url=ASSESSOR_QUERY_URL,
            )
        observed = normalize_ain(str(attributes.get("AIN") or ""))
        if observed != normalized:
            raise _source_schema_error(
                "Los Angeles County Assessor returned a different AIN",
                url=ASSESSOR_QUERY_URL,
                details={"requested_ain": normalized, "observed_ain": observed},
            )
        return dict(attributes)

    def payment_bootstrap(self) -> PaymentBootstrap:
        return parse_payment_bootstrap_html(self.html(PAYMENT_HISTORY_URL))

    def payment_page(
        self,
        ain: str,
        page: int,
        *,
        bootstrap: PaymentBootstrap,
    ) -> PaymentPage:
        payload = self.json_post(
            bootstrap.ajax_url,
            data={
                "action": PAYMENT_ACTION,
                "ain": normalize_ain(ain),
                "page": page,
                "nonce": bootstrap.nonce,
            },
            referer=PAYMENT_HISTORY_URL,
        )
        return parse_payment_response(
            payload,
            expected_ain=ain,
            native_page=page,
        )


def parse_payment_bootstrap_html(html: str) -> PaymentBootstrap:
    """Extract the current same-session TTC AJAX operation contract."""

    match = re.search(
        r"\bvar\s+phf_ajax\s*=\s*(\{.*?\})\s*;",
        str(html),
        re.S,
    )
    if match is None:
        raise _source_schema_error(
            "TTC payment-history bootstrap configuration is missing",
            url=PAYMENT_HISTORY_URL,
        )
    try:
        config = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise _source_schema_error(
            "TTC payment-history bootstrap configuration is invalid",
            url=PAYMENT_HISTORY_URL,
        ) from error
    ajax_url = _clean_text(config.get("ajax_url"))
    nonce = _clean_text(config.get("nonce"))
    if ajax_url != PAYMENT_AJAX_URL or nonce is None:
        raise _source_schema_error(
            "TTC payment-history bootstrap fields changed",
            url=PAYMENT_HISTORY_URL,
            details={"ajax_url": ajax_url, "nonce_present": nonce is not None},
        )
    soup = BeautifulSoup(str(html), "html.parser")
    script = soup.find("script", id="phf-script-js")
    script_url = (
        urljoin(PAYMENT_HISTORY_URL, str(script.get("src")))
        if isinstance(script, Tag) and script.get("src")
        else ""
    )
    if "/PaymentHistory/phf-script.js" not in script_url:
        raise _source_schema_error(
            "TTC payment-history client script is missing",
            url=PAYMENT_HISTORY_URL,
        )
    contract = {
        "ajax_url": ajax_url,
        "script_path": urlsplit(script_url).path,
        "action": PAYMENT_ACTION,
        "input_fields": ["action", "ain", "page", "nonce"],
    }
    return PaymentBootstrap(
        ajax_url=ajax_url,
        nonce=nonce,
        script_url=script_url,
        schema_fingerprint=schema_fingerprint(contract),
    )


def parse_payment_response(
    payload: Mapping[str, Any],
    *,
    expected_ain: str,
    native_page: int,
) -> PaymentPage:
    """Parse one native TTC page, including its structured not-found state."""

    normalized_ain = normalize_ain(expected_ain)
    if payload.get("success") is not True:
        raise SourceResponseError(
            "TTC payment operation reported failure",
            url=PAYMENT_AJAX_URL,
            details={"payload": dict(payload)},
        )
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise _source_schema_error(
            "TTC payment response data changed",
            url=PAYMENT_AJAX_URL,
        )
    if data.get("status") == 404:
        native_state = {
            key: data.get(key)
            for key in ("type", "title", "status", "traceId")
            if data.get(key) is not None
        }
        return PaymentPage(
            rows=(),
            meta={},
            native_page=native_page,
            no_result=True,
            native_state=native_state,
            schema_fingerprint=schema_fingerprint(
                {
                    "state": "not_found",
                    "fields": sorted(native_state),
                }
            ),
        )

    rows = data.get("data")
    meta = data.get("meta")
    if not isinstance(rows, list) or not isinstance(meta, Mapping):
        raise _source_schema_error(
            "TTC payment rows or pagination metadata changed",
            url=PAYMENT_AJAX_URL,
            details={
                "rows_type": type(rows).__name__,
                "meta_type": type(meta).__name__,
            },
        )
    required_row_fields = {
        "payment_id",
        "ain",
        "effective_date",
        "installment_key",
        "group_number",
        "tax_paid",
        "penalty_paid",
        "cost_paid",
        "total_paid",
        "tax_year",
        "sequence",
        "group_description",
    }
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise _source_schema_error(
                "TTC payment row is not an object",
                url=PAYMENT_AJAX_URL,
                details={"row_index": index},
            )
        missing = sorted(required_row_fields - set(row))
        if missing:
            raise _source_schema_error(
                "TTC payment row fields changed",
                url=PAYMENT_AJAX_URL,
                details={"row_index": index, "missing_fields": missing},
            )
        if normalize_ain(str(row.get("ain") or "")) != normalized_ain:
            raise _source_schema_error(
                "TTC payment row AIN differs from the requested AIN",
                url=PAYMENT_AJAX_URL,
                details={"row_index": index, "observed_ain": row.get("ain")},
            )
        normalized_rows.append(dict(row))
    for field_name in ("totalRecords", "totalPages"):
        value = meta.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise _source_schema_error(
                "TTC payment pagination metadata changed",
                url=PAYMENT_AJAX_URL,
                details={"field": field_name, "value": value},
            )
    if int(meta["totalPages"]) < native_page and rows:
        raise _source_schema_error(
            "TTC payment page exceeds reported totalPages",
            url=PAYMENT_AJAX_URL,
            details={
                "native_page": native_page,
                "totalPages": meta["totalPages"],
            },
        )
    shape = {
        "row_fields": sorted(required_row_fields),
        "meta_fields": sorted(str(key) for key in meta),
    }
    return PaymentPage(
        rows=tuple(normalized_rows),
        meta=dict(meta),
        native_page=native_page,
        no_result=False,
        native_state=None,
        schema_fingerprint=schema_fingerprint(shape),
    )


def _route_record(attributes: Mapping[str, Any]) -> dict[str, Any]:
    ain = normalize_ain(str(attributes.get("AIN") or ""))
    native_id = ain
    return {
        "canonical_ref": canonical_property_ref(
            ASSESSOR_SOURCE_ID,
            COUNTY_GEOID,
            "parcel_route",
            native_id,
        ),
        "source_id": ASSESSOR_SOURCE_ID,
        "record_kind": "parcel_route",
        "native_ids": {
            "ain": ain,
            "apn": _clean_text(attributes.get("APN")),
            "objectid": attributes.get("OBJECTID"),
            "roll_year": _clean_text(attributes.get("Roll_Year")),
        },
        "native_parcel_id": ain,
        "parcel_id": ain,
        "ain": ain,
        "formatted_ain": format_ain(ain),
        "situs_address": {
            "raw": _clean_text(attributes.get("SitusFullAddress"))
            or _clean_text(attributes.get("SitusAddress")),
            "street": _clean_text(attributes.get("SitusAddress")),
            "city_state": _clean_text(attributes.get("SitusCity")),
            "postal_code": _clean_text(attributes.get("SitusZIP")),
        },
        "property_classification": {
            "use_code": _clean_text(attributes.get("UseCode")),
            "use_type": _clean_text(attributes.get("UseType")),
            "use_description": _clean_text(attributes.get("UseDescription")),
        },
        "legal_description": _clean_text(attributes.get("LegalDescription")),
        "centroid": {
            "latitude": attributes.get("CENTER_LAT"),
            "longitude": attributes.get("CENTER_LON"),
        },
        "source_url": ASSESSOR_QUERY_URL,
        "operation_state": "assessor_ain_verified",
        "join_candidates": {
            "ain": {
                "value": ain,
                "target_source_ids": [PAYMENT_SOURCE_ID, SALE_SOURCE_ID],
            }
        },
        "next_operations": [
            {
                "source_id": PAYMENT_SOURCE_ID,
                "operation": "history",
                "ain": ain,
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
            {
                "source_id": SALE_SOURCE_ID,
                "operation": "sale-results",
                "join_field": "ain",
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
        ],
        "raw": dict(attributes),
    }


def _payment_record(
    row: Mapping[str, Any],
    meta: Mapping[str, Any],
    *,
    native_page: int,
    schema: str,
) -> dict[str, Any]:
    ain = normalize_ain(str(row.get("ain") or ""))
    payment_id = str(row.get("payment_id"))
    tax_year = int(row["tax_year"])
    installment_key = str(row["installment_key"])
    native_id = f"{ain}:{payment_id}"
    amount_fields = ("tax_paid", "penalty_paid", "cost_paid", "total_paid")
    return {
        "canonical_ref": canonical_property_ref(
            PAYMENT_SOURCE_ID,
            COUNTY_GEOID,
            "property_tax_payment",
            native_id,
        ),
        "source_id": PAYMENT_SOURCE_ID,
        "record_kind": "property_tax_payment",
        "native_ids": {
            "ain": ain,
            "payment_id": payment_id,
            "group_number": str(row["group_number"]),
            "sequence": str(row["sequence"]),
        },
        "native_parcel_id": ain,
        "parcel_id": ain,
        "ain": ain,
        "formatted_ain": format_ain(ain),
        "tax_year": tax_year,
        "installment_key": installment_key,
        "effective_date": _source_date(
            row["effective_date"],
            "effective_date",
        ),
        "effective_date_raw": str(row["effective_date"]),
        "amounts": {
            "currency": "USD",
            **{
                field_name: _decimal_text(row[field_name], field_name)
                for field_name in amount_fields
            },
        },
        "amounts_raw": {
            field_name: str(row[field_name])
            for field_name in amount_fields
        },
        "payment_channel_description": _clean_text(
            row.get("group_description")
        ),
        "account_snapshot": {
            "street_address": _clean_text(meta.get("street_address")),
            "city_state_zip": _clean_text(meta.get("city_state_zip")),
            "source_last_updated": _clean_text(meta.get("lastUpdated")),
            "source_total_records": meta.get("totalRecords"),
            "source_total_pages": meta.get("totalPages"),
            "native_page": native_page,
        },
        "tax_default_status": {
            "status": "not_asserted_by_payment_history",
            "official_route": AUCTION_NOTICE_URL,
        },
        "source_url": PAYMENT_HISTORY_URL,
        "operation_url": PAYMENT_AJAX_URL,
        "operation_state": "official_payment_row",
        "schema_fingerprint": schema,
        "join_candidates": {
            "ain": {
                "value": ain,
                "target_source_ids": [ASSESSOR_SOURCE_ID, SALE_SOURCE_ID],
            }
        },
        "raw": dict(row),
    }


def _parse_official_datetime(value: str) -> dict[str, str | None]:
    raw = _clean_text(value) or ""
    candidate = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+",
        "",
        raw,
        flags=re.I,
    )
    candidate = re.sub(r"\b([AP])\.M\.", r"\1M", candidate, flags=re.I)
    candidate = candidate.replace("Pacific Time", "").strip()
    for pattern in (
        "%B %d, %Y at %I:%M %p",
        "%B %d %Y at %I:%M %p",
        "%B %d, %Y",
        "%B %d %Y",
    ):
        try:
            parsed = datetime.strptime(candidate, pattern)
        except ValueError:
            continue
        if "%I" in pattern:
            parsed = parsed.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
            normalized = parsed.isoformat()
        else:
            normalized = parsed.date().isoformat()
        return {"raw": raw, "normalized": normalized}
    return {"raw": raw, "normalized": None}


def _section_route(section: Tag, label_fragment: str) -> dict[str, Any]:
    fragment = label_fragment.casefold()
    for anchor in section.find_all("a", href=True):
        label = _clean_text(anchor.get_text(" ", strip=True)) or ""
        if fragment in label.casefold():
            return {
                "label": label,
                "url": urljoin(AUCTION_SCHEDULE_URL, str(anchor["href"])),
                "state": "official_schedule_link",
            }
    return {
        "label": label_fragment,
        "url": None,
        "state": "not_linked_on_current_official_schedule",
    }


def parse_auction_schedule_html(html: str) -> list[dict[str, Any]]:
    """Parse source-published auction and redemption schedule entries."""

    soup = BeautifulSoup(str(html), "html.parser")
    general_vendor_url = None
    for anchor in soup.find_all("a", href=True):
        href = urljoin(AUCTION_SCHEDULE_URL, str(anchor["href"]))
        if urlsplit(href).hostname == "liveauctions.govease.com":
            general_vendor_url = href
            break
    records: list[dict[str, Any]] = []
    for heading in soup.find_all(["h1", "h2", "h3"]):
        heading_text = _clean_text(heading.get_text(" ", strip=True)) or ""
        match = re.search(
            r"(?P<follow>Follow-Up\s+)?Online Auction\s*\((?P<cycle>\d{4}[A-Z])\)",
            heading_text,
            re.I,
        )
        if match is None:
            continue
        section = heading.find_parent("section")
        if not isinstance(section, Tag):
            raise _source_schema_error(
                "TTC auction heading is outside its schedule section",
                url=AUCTION_SCHEDULE_URL,
                details={"heading": heading_text},
            )
        cycle = match.group("cycle").upper()
        phase = "follow_up" if match.group("follow") else "initial"
        fields: dict[str, dict[str, str | None]] = {}
        for paragraph in section.find_all("p"):
            strong = paragraph.find("strong")
            if not isinstance(strong, Tag):
                continue
            label = (_clean_text(strong.get_text(" ", strip=True)) or "").casefold()
            full_text = _clean_text(paragraph.get_text(" ", strip=True)) or ""
            strong_text = _clean_text(strong.get_text(" ", strip=True)) or ""
            raw_value = full_text[len(strong_text) :].strip(" :-")
            if not raw_value:
                continue
            if label == "start":
                fields["start"] = _parse_official_datetime(raw_value)
            elif label == "end":
                fields["end"] = _parse_official_datetime(raw_value)
            elif "last day to redeem" in label:
                fields["last_day_to_redeem"] = _parse_official_datetime(raw_value)
            elif "first day to register" in label:
                fields["first_day_to_register"] = _parse_official_datetime(raw_value)
            elif "last day to register" in label:
                fields["last_day_to_register"] = _parse_official_datetime(raw_value)
            elif "deposit funds" in label:
                fields["deposit_deadline"] = _parse_official_datetime(raw_value)
            elif "pay-off" in label or "payoff" in label:
                fields["payoff_deadline"] = _parse_official_datetime(raw_value)
        required = {"start", "end", "last_day_to_redeem"}
        missing = sorted(required - set(fields))
        if missing:
            raise _source_schema_error(
                "TTC auction schedule fields changed",
                url=AUCTION_SCHEDULE_URL,
                details={
                    "auction_cycle": cycle,
                    "phase": phase,
                    "missing_fields": missing,
                },
            )
        native_id = f"{cycle}:{phase}"
        records.append(
            {
                "canonical_ref": canonical_property_ref(
                    SALE_SOURCE_ID,
                    COUNTY_GEOID,
                    "tax_sale_auction_schedule",
                    native_id,
                ),
                "source_id": SALE_SOURCE_ID,
                "record_kind": "tax_sale_auction_schedule",
                "native_ids": {
                    "auction_cycle": cycle,
                    "sale_phase": phase,
                },
                "auction_cycle": cycle,
                "sale_phase": phase,
                "sale_status": "scheduled_as_published",
                "schedule": fields,
                "redemption": {
                    "last_day_to_redeem": fields["last_day_to_redeem"],
                    "state": "source_published_cycle_deadline",
                    "individual_property_status_route": AUCTION_NOTICE_URL,
                },
                "routes": {
                    "property_list": _section_route(section, "PROPERTY LIST"),
                    "remaining_properties": _section_route(
                        section,
                        "PROPERTIES REMAINING FOR SALE",
                    ),
                    "bidder_registration": _section_route(
                        section,
                        "BIDDER REGISTRATION",
                    ),
                    "terms_and_conditions": _section_route(
                        section,
                        "TERMS AND CONDITIONS",
                    ),
                    "general_vendor_route": {
                        "url": general_vendor_url,
                        "state": (
                            "officially_routed_vendor"
                            if general_vendor_url
                            else "not_linked_on_current_official_schedule"
                        ),
                    },
                },
                "source_url": AUCTION_SCHEDULE_URL,
                "operation_state": "official_schedule_entry",
            }
        )
    if not records:
        raise _source_schema_error(
            "No TTC auction schedule entries were recognized",
            url=AUCTION_SCHEDULE_URL,
        )
    return records


def _publication_month(url: str) -> str | None:
    match = re.search(r"/uploads/(?P<year>\d{4})/(?P<month>\d{2})/", url)
    return f"{match.group('year')}-{match.group('month')}" if match else None


def parse_publications_html(html: str) -> list[PublicationArtifact]:
    """Parse TTC's official sale-result and sold-parcel publication indexes."""

    soup = BeautifulSoup(str(html), "html.parser")
    artifacts: list[PublicationArtifact] = []
    seen_urls: set[str] = set()
    headings = {
        "sold properties and excess proceeds lists": (
            "sale_results_excess_proceeds"
        ),
        "sold parcels": "sold_parcels",
    }
    for heading in soup.find_all(["h1", "h2", "h3"]):
        heading_text = (_clean_text(heading.get_text(" ", strip=True)) or "").casefold()
        kind = headings.get(heading_text)
        if kind is None:
            continue
        container = heading.parent
        if not isinstance(container, Tag):
            continue
        for anchor in container.find_all("a", href=True):
            label = _clean_text(anchor.get_text(" ", strip=True)) or ""
            href = urljoin(AUCTION_CONTACT_URL, str(anchor["href"]))
            if href in seen_urls or not href.casefold().endswith(".pdf"):
                continue
            cycle_match = SALE_CYCLE_RE.search(f"{label} {href}")
            if cycle_match is None:
                continue
            if urlsplit(href).hostname != "ttc.lacounty.gov":
                continue
            seen_urls.add(href)
            phases = (
                ("initial", "follow_up")
                if "follow" in f"{label} {href}".casefold()
                else ("initial",)
            )
            artifacts.append(
                PublicationArtifact(
                    kind=kind,
                    cycle=cycle_match.group("cycle").upper(),
                    label=label,
                    url=href,
                    index_url=AUCTION_CONTACT_URL,
                    phase_coverage=phases,
                    wordpress_upload_month=_publication_month(href),
                )
            )
    if not artifacts:
        raise _source_schema_error(
            "No TTC tax-sale publications were recognized",
            url=AUCTION_CONTACT_URL,
        )
    return artifacts


def parse_sale_results_text(
    text: str,
    *,
    expected_cycle: str,
) -> tuple[list[SaleResultRow], dict[str, str]]:
    """Parse parcel sale results from TTC's layout-preserving PDF text."""

    cycle = str(expected_cycle).strip().upper()
    if not re.fullmatch(r"\d{4}[A-Z]", cycle):
        raise LATTCQueryError(
            "invalid_auction_cycle",
            "auction cycle must use the source format YYYY plus one letter",
            details={"cycle": expected_cycle},
        )
    sale_windows: dict[str, str] = {}
    for raw_line in str(text).splitlines():
        line = _clean_text(raw_line)
        if line is None:
            continue
        match = re.search(
            rf"\b{re.escape(cycle)}\s+(?P<follow>Follow-up\s+)?"
            r"Online Auction\s*\((?P<window>[^)]+)\)?",
            line,
            re.I,
        )
        if match:
            phase = "follow_up" if match.group("follow") else "initial"
            sale_windows.setdefault(phase, match.group("window").strip())
    rows: list[SaleResultRow] = []
    for raw_line in str(text).splitlines():
        match = SALE_ROW_RE.match(raw_line)
        if match is None:
            continue
        formatted = match.group("ain")
        rows.append(
            SaleResultRow(
                formatted_ain=formatted,
                ain=normalize_ain(formatted),
                item=match.group("item"),
                purchase_price_raw=match.group("purchase"),
                purchase_price=_decimal_text(
                    match.group("purchase"),
                    "purchase_price",
                ),
                excess_proceeds_raw=match.group("excess"),
                excess_proceeds=_decimal_text(
                    match.group("excess"),
                    "excess_proceeds",
                ),
                phase="follow_up" if match.group("follow_up") else "initial",
            )
        )
    if not rows:
        raise _source_schema_error(
            "TTC sale-result document contains no recognized parcel rows",
            url=AUCTION_CONTACT_URL,
            details={"auction_cycle": cycle},
        )
    duplicate_keys: set[tuple[str, str, str]] = set()
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.ain, row.item, row.phase)
        if key in seen:
            duplicate_keys.add(key)
        seen.add(key)
    if duplicate_keys:
        raise _source_schema_error(
            "TTC sale-result document contains duplicate native sale IDs",
            url=AUCTION_CONTACT_URL,
            details={"duplicates": sorted(":".join(key) for key in duplicate_keys)},
        )
    return rows, sale_windows


def extract_pdf_text(
    artifact: ResponseArtifact,
    *,
    executable: str | None = None,
) -> str:
    """Extract layout-preserving text from a verified official PDF artifact."""

    if not artifact.content.startswith(b"%PDF-"):
        raise _source_schema_error(
            "TTC sale-result artifact is not a PDF",
            url=artifact.source_url,
            details={"signature": artifact.content[:8].hex()},
        )
    command = executable or shutil.which("pdftotext")
    if command is None:
        raise DocumentExtractionUnavailable(
            "The official TTC PDF is available; install pdftotext or inspect it directly",
            url=artifact.source_url,
            details={"artifact_size": len(artifact.content)},
        )
    with tempfile.TemporaryDirectory(
        prefix="osint-la-ttc-",
        dir="/private/tmp",
    ) as workdir:
        pdf_path = Path(workdir).resolve() / "source.pdf"
        text_path = Path(workdir).resolve() / "source.txt"
        pdf_path.write_bytes(artifact.content)
        completed = subprocess.run(
            [command, "-layout", str(pdf_path), str(text_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0 or not text_path.exists():
            raise SourceResponseError(
                "pdftotext could not extract the official TTC artifact",
                url=artifact.source_url,
                details={
                    "returncode": completed.returncode,
                    "stderr": completed.stderr[-500:],
                },
            )
        text = text_path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise SourceResponseError(
            "The official TTC PDF yielded empty text",
            url=artifact.source_url,
        )
    return text


def _publication_date(headers: Mapping[str, str]) -> tuple[str | None, str | None]:
    last_modified = _header(headers, "last-modified")
    if last_modified is None:
        return None, None
    try:
        parsed = parsedate_to_datetime(last_modified)
    except (TypeError, ValueError, OverflowError):
        return None, "http_last_modified_unparseable"
    return parsed.date().isoformat(), "http_last_modified"


def _sale_result_record(
    row: SaleResultRow,
    *,
    cycle: str,
    artifact: PublicationArtifact,
    artifact_receipt: Mapping[str, Any],
    sale_windows: Mapping[str, str],
) -> dict[str, Any]:
    sale_id = f"{cycle}:{row.phase}:{row.item}:{row.ain}"
    return {
        "canonical_ref": canonical_property_ref(
            SALE_SOURCE_ID,
            COUNTY_GEOID,
            "property_tax_sale_result",
            sale_id,
        ),
        "source_id": SALE_SOURCE_ID,
        "record_kind": "property_tax_sale_result",
        "native_ids": {
            "ain": row.ain,
            "item": row.item,
            "auction_cycle": cycle,
            "sale_phase": row.phase,
            "sale_id": sale_id,
        },
        "native_parcel_id": row.ain,
        "parcel_id": row.ain,
        "ain": row.ain,
        "formatted_ain": row.formatted_ain,
        "sale_id": sale_id,
        "auction_cycle": cycle,
        "sale_phase": row.phase,
        "sale_window_raw": sale_windows.get(row.phase),
        "status": "sold_as_published",
        "amounts": {
            "currency": "USD",
            "purchase_price": row.purchase_price,
            "excess_proceeds": row.excess_proceeds,
        },
        "amounts_raw": {
            "purchase_price": row.purchase_price_raw,
            "excess_proceeds": row.excess_proceeds_raw,
        },
        "publication_date": artifact_receipt.get("publication_date"),
        "publication_date_basis": artifact_receipt.get(
            "publication_date_basis"
        ),
        "publication": {
            "kind": artifact.kind,
            "label": artifact.label,
            "wordpress_upload_month": artifact.wordpress_upload_month,
            "artifact_sha256": artifact_receipt["sha256"],
            "artifact_size": artifact_receipt["size"],
            "http_last_modified": artifact_receipt.get("http_last_modified"),
        },
        "source_url": artifact.url,
        "publication_index_url": artifact.index_url,
        "operation_state": "official_sale_result_row",
        "redemption_state": {
            "status": "sale_result_only",
            "individual_route": AUCTION_NOTICE_URL,
        },
        "excess_proceeds_state": {
            "status": (
                "positive_amount_published"
                if Decimal(row.excess_proceeds) > 0
                else "zero_amount_published"
            ),
            "claim_route": EXCESS_PROCEEDS_URL,
        },
        "join_candidates": {
            "ain": {
                "value": row.ain,
                "target_source_ids": [ASSESSOR_SOURCE_ID, PAYMENT_SOURCE_ID],
            }
        },
        "raw": {
            "formatted_ain": row.formatted_ain,
            "item": row.item,
            "purchase_price": row.purchase_price_raw,
            "follow_up_marker": "X" if row.phase == "follow_up" else None,
            "excess_proceeds": row.excess_proceeds_raw,
        },
    }


def source_manifest() -> dict[str, Any]:
    """Return source components, operation states, joins, and useful routes."""

    return {
        "schema_version": "public-record-source-family/1.0",
        "family_id": "us-ca-los-angeles-county-property-tax-and-sales",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [
            ASSESSOR_METADATA.to_dict(),
            PAYMENT_METADATA.to_dict(),
            SALE_METADATA.to_dict(),
        ],
        "joins": [
            {
                "field": "ain",
                "normalization": "ten_digits",
                "formatted_example": "1234-567-890",
                "source_ids": [
                    ASSESSOR_SOURCE_ID,
                    PAYMENT_SOURCE_ID,
                    SALE_SOURCE_ID,
                ],
                "relation": "candidate_join_not_merged_provenance",
            }
        ],
        "operations": {
            "route": {
                "source_id": ASSESSOR_SOURCE_ID,
                "state": "machine_query",
                "query": "exact_ain",
            },
            "history": {
                "source_id": PAYMENT_SOURCE_ID,
                "state": "machine_query",
                "query": "exact_ain",
                "pagination": "native_page",
                "freshness": "source_lastUpdated",
            },
            "auctions": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_page_parse",
                "includes": [
                    "sale_windows",
                    "redemption_deadlines",
                    "registration_and_payoff_deadlines",
                    "current_official_links",
                ],
            },
            "publications": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_artifact_index",
            },
            "sale-results": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_pdf_extraction",
                "includes": [
                    "sold_parcel",
                    "sale_item",
                    "purchase_price",
                    "phase",
                    "excess_proceeds",
                ],
            },
            "tax-default-status": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_route",
                "url": AUCTION_NOTICE_URL,
            },
            "individual-redemption-or-removal": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_route",
                "url": AUCTION_NOTICE_URL,
            },
            "excess-proceeds-claim": {
                "source_id": SALE_SOURCE_ID,
                "state": "official_route",
                "url": EXCESS_PROCEEDS_URL,
            },
        },
        "complementary_routes": [
            {
                "name": "Annual Secured Property Tax Bill",
                "url": ANNUAL_BILL_URL,
                "use": "current bill and tax information",
                "authority": "Los Angeles County",
            },
            {
                "name": "View or request a property tax bill",
                "url": TAX_BILL_URL,
                "use": "bill route when payment history is insufficient",
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
            {
                "name": "Secured Property Tax Information Request",
                "url": MULTIPLE_PARCELS_URL,
                "use": "multi-parcel or request-based tax information",
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
            {
                "name": "Notice of Auction or Sale",
                "url": AUCTION_NOTICE_URL,
                "use": "tax-default, sale, redemption, and removal information",
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
            {
                "name": "Notice of Excess Proceeds",
                "url": EXCESS_PROCEEDS_URL,
                "use": "claim instructions and source-published notices",
                "authority": "Los Angeles County Treasurer and Tax Collector",
            },
            {
                "name": "Current auction vendor",
                "url": "https://www.govease.com/los-angeles",
                "use": "current inventory and bidder workflow when routed by TTC",
                "authority": "third-party vendor linked by TTC",
            },
        ],
        "warnings": list(SOURCE_WARNINGS),
    }


def _source_for_command(command: str) -> SourceMetadata:
    if command == "route":
        return ASSESSOR_METADATA
    if command == "history":
        return PAYMENT_METADATA
    return SALE_METADATA


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    if args.command in {"route", "history"}:
        parameters = {"ain": args.ain}
        if args.command == "history" and args.max_pages is not None:
            parameters["max_pages"] = args.max_pages
    elif args.command == "publications":
        parameters = {"kind": args.kind, "cycle": args.cycle}
        requested_limit = None
    elif args.command == "sale-results":
        parameters = {
            "cycle": args.cycle,
            "max_document_bytes": args.max_document_bytes,
        }
    elif args.command == "probe":
        parameters = {
            "positive_ain": PROBE_AIN,
            "negative_ain": INVALID_PROBE_AIN,
            "max_document_bytes": args.max_document_bytes,
        }
        requested_limit = 1
        cursor = None
    else:
        parameters = {}
        requested_limit = None
        cursor = None
    return PublicRecordsQuery(
        source=_source_for_command(args.command),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _query_failure(
    query: PublicRecordsQuery,
    error: LATTCQueryError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _history_start_page(cursor: str | None, ain: str) -> int:
    if cursor is None:
        return 1
    match = HISTORY_CURSOR_RE.fullmatch(cursor)
    if match is None or match.group("ain") != ain:
        raise LATTCQueryError(
            "invalid_history_cursor",
            "history cursor does not match the requested AIN",
            details={"cursor": cursor, "ain": ain},
        )
    return int(match.group("page"))


def _execute_history(
    args: argparse.Namespace,
    client: LosAngelesTTCClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    ain = normalize_ain(args.ain)
    page_number = _history_start_page(args.cursor, ain)
    bootstrap = client.payment_bootstrap()
    records: list[dict[str, Any]] = []
    pages_fetched = 0
    total_pages: int | None = None
    last_fetched_page = page_number - 1
    while args.max_pages is None or pages_fetched < args.max_pages:
        page = client.payment_page(
            ain,
            page_number,
            bootstrap=bootstrap,
        )
        if page.no_result:
            if not records:
                return PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            raise _source_schema_error(
                "TTC pagination returned not-found after earlier payment rows",
                url=PAYMENT_AJAX_URL,
                details={"ain": ain, "native_page": page_number},
            )
        reported_total_pages = int(page.meta["totalPages"])
        if total_pages is None:
            total_pages = reported_total_pages
        elif total_pages != reported_total_pages:
            raise _source_schema_error(
                "TTC totalPages changed within one paginated query",
                url=PAYMENT_AJAX_URL,
                details={
                    "initial_total_pages": total_pages,
                    "observed_total_pages": reported_total_pages,
                },
            )
        records.extend(
            _payment_record(
                row,
                page.meta,
                native_page=page_number,
                schema=page.schema_fingerprint,
            )
            for row in page.rows
        )
        pages_fetched += 1
        last_fetched_page = page_number
        if page_number >= reported_total_pages:
            break
        page_number += 1
    if total_pages is not None and last_fetched_page < total_pages:
        next_cursor = (
            f"la-ttc:history:{ain}:page:{last_fetched_page + 1}"
        )
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=SOURCE_WARNINGS,
    )


def _filter_publications(
    artifacts: Sequence[PublicationArtifact],
    *,
    kind: str,
    cycle: str | None,
) -> list[PublicationArtifact]:
    normalized_cycle = cycle.upper() if cycle else None
    return [
        artifact
        for artifact in artifacts
        if (kind == "all" or artifact.kind == kind)
        and (normalized_cycle is None or artifact.cycle == normalized_cycle)
    ]


def _sale_offset(cursor: str | None, cycle: str) -> int:
    if cursor is None:
        return 0
    match = SALE_CURSOR_RE.fullmatch(cursor)
    if match is None or match.group("cycle") != cycle:
        raise LATTCQueryError(
            "invalid_sale_cursor",
            "sale-results cursor does not match the requested auction cycle",
            details={"cursor": cursor, "cycle": cycle},
        )
    return int(match.group("offset"))


def _execute_sale_results(
    args: argparse.Namespace,
    client: LosAngelesTTCClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    cycle = str(args.cycle).strip().upper()
    if not re.fullmatch(r"\d{4}[A-Z]", cycle):
        raise LATTCQueryError(
            "invalid_auction_cycle",
            "auction cycle must use the source format YYYY plus one letter",
            details={"cycle": args.cycle},
        )
    artifacts = parse_publications_html(client.html(AUCTION_CONTACT_URL))
    candidates = [
        artifact
        for artifact in artifacts
        if artifact.kind == "sale_results_excess_proceeds"
        and artifact.cycle == cycle
    ]
    if not candidates:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    if len(candidates) != 1:
        raise _source_schema_error(
            "TTC publication index has multiple sale-result artifacts for one cycle",
            url=AUCTION_CONTACT_URL,
            details={"cycle": cycle, "urls": [item.url for item in candidates]},
        )
    publication = candidates[0]
    artifact = client.bytes(
        publication.url,
        max_bytes=args.max_document_bytes,
    )
    text = extract_pdf_text(artifact)
    rows, sale_windows = parse_sale_results_text(
        text,
        expected_cycle=cycle,
    )
    publication_date, publication_date_basis = _publication_date(
        artifact.headers
    )
    receipt = {
        "sha256": hashlib.sha256(artifact.content).hexdigest(),
        "size": len(artifact.content),
        "http_last_modified": _header(
            artifact.headers,
            "last-modified",
        ),
        "publication_date": publication_date,
        "publication_date_basis": publication_date_basis,
    }
    offset = _sale_offset(args.cursor, cycle)
    if offset > len(rows):
        raise LATTCQueryError(
            "sale_cursor_out_of_range",
            "sale-results cursor offset exceeds the current document",
            details={"offset": offset, "row_count": len(rows)},
        )
    end = len(rows) if args.limit is None else min(len(rows), offset + args.limit)
    selected = rows[offset:end]
    records = [
        _sale_result_record(
            row,
            cycle=cycle,
            artifact=publication,
            artifact_receipt=receipt,
            sale_windows=sale_windows,
        )
        for row in selected
    ]
    next_cursor = (
        f"la-ttc:sale:{cycle}:offset:{end}"
        if end < len(rows)
        else None
    )
    status = ResultStatus.PARTIAL if next_cursor else (
        ResultStatus.OK if records else ResultStatus.NO_RESULTS
    )
    return PublicRecordsResult(
        query=query,
        status=status,
        records=records,
        next_cursor=next_cursor,
        raw_artifact_refs=(
            publication.url,
            f"sha256:{receipt['sha256']}",
        ),
        warnings=SOURCE_WARNINGS,
    )


def _probe_record(
    client: LosAngelesTTCClient | Any,
    *,
    max_document_bytes: int,
) -> dict[str, Any]:
    assessor = client.assessor_exact(PROBE_AIN)
    if assessor is None:
        raise _source_schema_error(
            "Los Angeles County Assessor probe AIN stopped resolving",
            url=ASSESSOR_QUERY_URL,
        )
    bootstrap = client.payment_bootstrap()
    positive = client.payment_page(
        PROBE_AIN,
        1,
        bootstrap=bootstrap,
    )
    negative = client.payment_page(
        INVALID_PROBE_AIN,
        1,
        bootstrap=bootstrap,
    )
    if positive.no_result or not positive.rows or not negative.no_result:
        raise _source_schema_error(
            "TTC positive/negative payment probe contract changed",
            url=PAYMENT_AJAX_URL,
        )
    schedules = parse_auction_schedule_html(client.html(AUCTION_SCHEDULE_URL))
    publications = parse_publications_html(client.html(AUCTION_CONTACT_URL))
    result_publications = [
        item
        for item in publications
        if item.kind == "sale_results_excess_proceeds"
    ]
    latest = max(result_publications, key=lambda item: item.cycle)
    artifact = client.bytes(latest.url, max_bytes=max_document_bytes)
    document_state: dict[str, Any]
    try:
        rows, windows = parse_sale_results_text(
            extract_pdf_text(artifact),
            expected_cycle=latest.cycle,
        )
        document_state = {
            "state": "official_pdf_parsed",
            "cycle": latest.cycle,
            "row_count": len(rows),
            "sale_phases": sorted({row.phase for row in rows}),
            "sale_windows": windows,
        }
    except DocumentExtractionUnavailable:
        document_state = {
            "state": "official_pdf_available_extractor_missing",
            "cycle": latest.cycle,
            "artifact_url": latest.url,
        }
    return {
        "canonical_ref": canonical_property_ref(
            SALE_SOURCE_ID,
            COUNTY_GEOID,
            "source_family_probe",
            "los-angeles-ttc",
        ),
        "source_id": SALE_SOURCE_ID,
        "record_kind": "source_family_probe",
        "operation_states": {
            "assessor_route": {
                "state": "verified",
                "ain": normalize_ain(str(assessor["AIN"])),
            },
            "payment_history": {
                "state": "verified",
                "row_count_page_one": len(positive.rows),
                "total_records": positive.meta["totalRecords"],
                "total_pages": positive.meta["totalPages"],
                "source_last_updated": positive.meta.get("lastUpdated"),
                "schema_fingerprint": positive.schema_fingerprint,
            },
            "payment_no_result": {
                "state": "verified",
                "native_state": dict(negative.native_state or {}),
            },
            "auction_schedule": {
                "state": "verified",
                "entry_count": len(schedules),
                "cycles": sorted({row["auction_cycle"] for row in schedules}),
            },
            "publication_index": {
                "state": "verified",
                "artifact_count": len(publications),
                "latest_sale_result_cycle": latest.cycle,
            },
            "sale_results": document_state,
            "tax_default_status": {
                "state": "official_route",
                "url": AUCTION_NOTICE_URL,
            },
            "individual_redemption_or_removal": {
                "state": "official_route",
                "url": AUCTION_NOTICE_URL,
            },
            "excess_proceeds_claim": {
                "state": "official_route",
                "url": EXCESS_PROCEEDS_URL,
            },
        },
        "source_urls": {
            "assessor": ASSESSOR_QUERY_URL,
            "payment_landing": PAYMENT_HISTORY_URL,
            "payment_operation": bootstrap.ajax_url,
            "auction_schedule": AUCTION_SCHEDULE_URL,
            "publication_index": AUCTION_CONTACT_URL,
            "latest_sale_result": latest.url,
        },
    }


def _execute_command(
    args: argparse.Namespace,
    client: LosAngelesTTCClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "route":
        ain = normalize_ain(args.ain)
        attributes = client.assessor_exact(ain)
        return PublicRecordsResult.success(
            query,
            [_route_record(attributes)] if attributes else [],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "history":
        return _execute_history(args, client, query)
    if args.command == "auctions":
        return PublicRecordsResult.success(
            query,
            parse_auction_schedule_html(client.html(AUCTION_SCHEDULE_URL)),
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "publications":
        artifacts = parse_publications_html(client.html(AUCTION_CONTACT_URL))
        selected = _filter_publications(
            artifacts,
            kind=args.kind,
            cycle=args.cycle,
        )
        return PublicRecordsResult.success(
            query,
            [artifact.to_record() for artifact in selected],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "sale-results":
        return _execute_sale_results(args, client, query)
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            [
                _probe_record(
                    client,
                    max_document_bytes=args.max_document_bytes,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Los Angeles TTC command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: LosAngelesTTCClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute one source-family operation."""

    if args.command == "sources":
        return source_manifest()
    query = build_query(args)
    source_client = client or LosAngelesTTCClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except LATTCQueryError as error:
        result = _query_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _add_transport_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Los Angeles County Assessor routing, TTC payment "
            "history, and TTC tax-sale publications"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe source components, joins, operations, and related routes",
    )
    add_output_args(sources)

    route = subparsers.add_parser(
        "route",
        help="Verify an exact Assessor AIN and expose TTC follow-on operations",
    )
    route.add_argument("ain")
    _add_transport_output(route)

    history = subparsers.add_parser(
        "history",
        help="Fetch TTC property-tax payment history by exact AIN",
    )
    history.add_argument("ain")
    history.add_argument(
        "--cursor",
        help="Native-page cursor returned by an earlier history query",
    )
    history.add_argument(
        "--max-pages",
        type=_positive_int,
        help=(
            "Optional caller-selected native TTC page bound; omitted fetches "
            "all reported pages"
        ),
    )
    _add_transport_output(history)

    auctions = subparsers.add_parser(
        "auctions",
        help="Fetch official auction, redemption, registration, and payoff dates",
    )
    _add_transport_output(auctions)

    publications = subparsers.add_parser(
        "publications",
        help="List official TTC sale-result and sold-parcel PDF artifacts",
    )
    publications.add_argument(
        "--kind",
        choices=("all", "sale_results_excess_proceeds", "sold_parcels"),
        default="all",
    )
    publications.add_argument("--cycle")
    _add_transport_output(publications)

    sale_results = subparsers.add_parser(
        "sale-results",
        help="Extract parcel sale and excess-proceeds rows for one auction cycle",
    )
    sale_results.add_argument("cycle")
    sale_results.add_argument("--limit", type=_positive_int)
    sale_results.add_argument("--cursor")
    sale_results.add_argument(
        "--max-document-bytes",
        type=_positive_int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_transport_output(sale_results)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded positive, negative, schedule, index, and PDF probes",
    )
    probe.add_argument(
        "--max-document-bytes",
        type=_positive_int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_transport_output(probe)
    return parser


def _result_count(payload: PublicRecordsResult | Mapping[str, Any]) -> int | None:
    return len(payload.records) if isinstance(payload, PublicRecordsResult) else None


def _emit(
    payload: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    serialized = (
        payload.to_dict()
        if isinstance(payload, PublicRecordsResult)
        else dict(payload)
    )
    if write_output(
        serialized,
        args,
        summary=f"Los Angeles County TTC {args.command}",
        result_count=_result_count(payload),
    ):
        return
    print(json.dumps(serialized, indent=2, sort_keys=True))
    if isinstance(payload, PublicRecordsResult):
        for error in payload.errors:
            print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 1.0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0.0) < 0:
        parser.error("--minimum-interval cannot be negative")
    if getattr(args, "cycle", None):
        args.cycle = str(args.cycle).strip().upper()
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
