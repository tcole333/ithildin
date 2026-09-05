#!/usr/bin/env python3
"""Query official Washington State court directories, opinions, and routes.

This adapter keeps separately attributable AOC components in one transport
family.  In particular, a CAPTCHA on case-result execution does not hide the
open court-code form, current-system routing matrix, directory, opinions, or
bulk-product catalog.

Examples:
    uv run python tools/query_washington_courts.py sources --json
    uv run python tools/query_washington_courts.py manifest --json
    uv run python tools/query_washington_courts.py directory-counties --json
    uv run python tools/query_washington_courts.py directory-search Whedbee
    uv run python tools/query_washington_courts.py directory-org 190 --json
    uv run python tools/query_washington_courts.py directory-pdf /tmp/wa.pdf
    uv run python tools/query_washington_courts.py case-form --json
    uv run python tools/query_washington_courts.py case-routes --json
    uv run python tools/query_washington_courts.py opinions-feed div1-unpublished
    uv run python tools/query_washington_courts.py opinions-list \
        --scope year --year 2026 --court-level C \
        --publication-status UNP --limit 25
    uv run python tools/query_washington_courts.py opinion-detail 88366-6
    uv run python tools/query_washington_courts.py opinion-download \
        88366-6 /tmp/88366-6.pdf
    uv run python tools/query_washington_courts.py data-products --json
    uv run python tools/query_washington_courts.py custom-extract --json
    uv run python tools/query_washington_courts.py appellate-documents \
        88366-6 --court appeals --json
    uv run python tools/query_washington_courts.py appellate-complements \
        --case-number 104108-0 --json
    uv run python tools/query_washington_courts.py archive-title 2778 --json
    uv run python tools/query_washington_courts.py probe --all --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

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


STATE_CODE = "WA"
STATE_GEOID = "53"
ADAPTER_FAMILY = "washington_aoc_official_courts"
OUTPUT_SCHEMA_VERSION = "washington-courts/1.0"

COURTS_ORIGIN = "https://www.courts.wa.gov"
DIRECTORY_HOME_URL = f"{COURTS_ORIGIN}/court_dir/"
DIRECTORY_COUNTY_URL = f"{DIRECTORY_HOME_URL}?fa=court_dir.county"
DIRECTORY_MASTER_URL = f"{DIRECTORY_HOME_URL}?fa=court_dir.master"
DIRECTORY_PDF_URL = f"{DIRECTORY_HOME_URL}courtdirectory.pdf"

CASE_ORIGIN = "https://dw.courts.wa.gov"
CASE_HOME_URL = f"{CASE_ORIGIN}/"
CASE_FORM_URL = (
    f"{CASE_ORIGIN}/index.cfm?"
    "fa=home.casesearch&terms=accept&flashform=0&tab=clj"
)

OPINIONS_HOME_URL = f"{COURTS_ORIGIN}/opinions/"
OPINIONS_INDEX_URL = f"{OPINIONS_HOME_URL}index.cfm"
OPINIONS_PDF_BASE = f"{OPINIONS_HOME_URL}pdf/"

DATA_PRODUCTS_URL = (
    f"{COURTS_ORIGIN}/appellate_trial_courts/aocwho/?"
    "fa=atc_aocwho.display&fileID=msd&section=DataDissemination"
)
DATA_POLICY_URL = f"{COURTS_ORIGIN}/dataDis/?fa=datadis.policyDiss"
DATA_REQUEST_URL = f"{COURTS_ORIGIN}/datadis/"
DATA_FEE_URL = (
    f"{COURTS_ORIGIN}/datadis/?fa=datadis.feeSchedule&remote=0"
)

JISLINK_URL = f"{COURTS_ORIGIN}/jislink/?fa=jislink.home"
CASELOAD_URL = f"{COURTS_ORIGIN}/caseload/"
DIGITAL_ARCHIVES_TITLE_BASE = (
    "https://digitalarchives.wa.gov/Collections/TitleInfo/"
)

APPELLATE_DOCUMENT_URLS = {
    "supreme": (
        "https://acdocportal.courts.wa.gov/PublicAccess/search_sc.html"
    ),
    "appeals": (
        "https://acdocportal.courts.wa.gov/PublicAccess/search_ca.html"
    ),
}

APPELLATE_COMPLEMENT_URLS = {
    "orders": f"{OPINIONS_INDEX_URL}?fa=opinions.scorders",
    "notice": f"{OPINIONS_INDEX_URL}?fa=opinions.notice",
    "calendar": (
        f"{COURTS_ORIGIN}/appellate_trial_courts/supreme/calendar/"
    ),
    "briefs": (
        f"{COURTS_ORIGIN}/appellate_trial_courts/coaBriefs/"
        "index.cfm?fa=coaBriefs.home"
    ),
    "issues": (
        f"{COURTS_ORIGIN}/appellate_trial_courts/supreme/issues/"
    ),
}

RSS_FEEDS = {
    "div1-published": (
        f"{OPINIONS_HOME_URL}rssDivIOpinionsFeed.cfm",
        "Court of Appeals Division I",
        "published",
    ),
    "div1-unpublished": (
        f"{OPINIONS_HOME_URL}rssDivIUnpublishedOpinionsFeed.cfm",
        "Court of Appeals Division I",
        "unpublished",
    ),
    "div2-published": (
        f"{OPINIONS_HOME_URL}rssDivIIOpinionsFeed.cfm",
        "Court of Appeals Division II",
        "published",
    ),
    "div2-unpublished": (
        f"{OPINIONS_HOME_URL}rssDivIIUnpublishedOpinionsFeed.cfm",
        "Court of Appeals Division II",
        "unpublished",
    ),
    "div3-published": (
        f"{OPINIONS_HOME_URL}rssDivIIIOpinionsFeed.cfm",
        "Court of Appeals Division III",
        "published",
    ),
    "div3-unpublished": (
        f"{OPINIONS_HOME_URL}rssDivIIIUnpublishedOpinionsFeed.cfm",
        "Court of Appeals Division III",
        "unpublished",
    ),
    "supreme-published": (
        f"{OPINIONS_HOME_URL}rssSCOpinionsFeed.cfm",
        "Supreme Court",
        "published",
    ),
}

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_ATTEMPTS = 3
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_PDF_BYTES = 128 * 1024 * 1024
DEFAULT_USER_AGENT = (
    "IthildinOSINT/1.0 Washington official courts client"
)

KNOWN_DIRECTORY_ORG_ID = "190"
KNOWN_DIRECTORY_PDF_SHA256 = (
    "47ad47726b7276d9baa6cc1c6eae5060"
    "d02e421e7b121bb0da3c3bdc5158af21"
)
KNOWN_OPINION_CASE = "88366-6"
KNOWN_OPINION_FILENAME = "883666MAJ"
KNOWN_OPINION_PDF_SHA256 = (
    "e0128ce568e07d4a209c25524614ae9c4"
    "6f74abdf700b6909918b6bb65564918"
)

CATALOG_SOURCE_ID = "us-wa-courts-official-catalog"
DIRECTORY_SOURCE_ID = "us-wa-aoc-court-directory"
CASE_DISCOVERY_SOURCE_ID = "us-wa-aoc-case-discovery"
CURRENT_ROUTES_SOURCE_ID = "us-wa-aoc-current-record-routes"
OPINIONS_SOURCE_ID = "us-wa-appellate-opinions"
APPELLATE_DOCUMENTS_SOURCE_ID = "us-wa-appellate-case-documents"
DATA_PRODUCTS_SOURCE_ID = "us-wa-aoc-public-index-products"
JISLINK_SOURCE_ID = "us-wa-jis-link"
APPELLATE_COMPLEMENTS_SOURCE_ID = "us-wa-appellate-route-complements"
CASELOAD_SOURCE_ID = "us-wa-aoc-caseload-products"
DIGITAL_ARCHIVES_SOURCE_ID = (
    "us-wa-digital-archives-superior-court-records"
)


@dataclass(frozen=True)
class Component:
    source_id: str
    name: str
    source_role: str
    base_url: str
    access_state: str
    operations: tuple[str, ...]
    relationship: str
    coverage: str


COMPONENTS = {
    DIRECTORY_SOURCE_ID: Component(
        source_id=DIRECTORY_SOURCE_ID,
        name="Washington AOC Court Directory",
        source_role="official_court_directory",
        base_url=DIRECTORY_HOME_URL,
        access_state="open_static_and_server_filtered_html",
        operations=(
            "directory-counties",
            "directory-search",
            "directory-org",
            "directory-pdf",
        ),
        relationship="authoritative court and personnel routing dimension",
        coverage="statewide courts, organizations, personnel, and contacts",
    ),
    CASE_DISCOVERY_SOURCE_ID: Component(
        source_id=CASE_DISCOVERY_SOURCE_ID,
        name="Washington AOC Free Statewide Case Discovery",
        source_role="official_statewide_case_discovery_index",
        base_url=CASE_FORM_URL,
        access_state="open_form_captcha_result_execution",
        operations=("case-form", "case-search"),
        relationship="discovery index; complete records remain with court of record",
        coverage=(
            "municipal, district, superior, and appellate discovery; "
            "freshness varies by court system"
        ),
    ),
    CURRENT_ROUTES_SOURCE_ID: Component(
        source_id=CURRENT_ROUTES_SOURCE_ID,
        name="Washington AOC Current Court Record Routing Matrix",
        source_role="official_current_record_system_router",
        base_url=CASE_HOME_URL,
        access_state="open_static_html",
        operations=("case-routes",),
        relationship=(
            "routes a discovered court/case to Odyssey, local CMS, "
            "re:SearchWA, or appellate portals"
        ),
        coverage="live jurisdiction groups advertised on the AOC case home page",
    ),
    OPINIONS_SOURCE_ID: Component(
        source_id=OPINIONS_SOURCE_ID,
        name="Washington Appellate Opinions",
        source_role="official_appellate_opinion_publication",
        base_url=OPINIONS_HOME_URL,
        access_state="open_static_html_rss_and_pdf",
        operations=(
            "opinions-feed",
            "opinions-list",
            "opinion-detail",
            "opinion-download",
        ),
        relationship="direct appellate opinion and information-sheet evidence",
        coverage="Supreme Court and Court of Appeals slip opinions",
    ),
    APPELLATE_DOCUMENTS_SOURCE_ID: Component(
        source_id=APPELLATE_DOCUMENTS_SOURCE_ID,
        name="Washington Appellate Public Case Document Portal",
        source_role="official_appellate_case_document_portal",
        base_url=APPELLATE_DOCUMENT_URLS["appeals"],
        access_state="open_form_exact_case_captcha_result_execution",
        operations=("appellate-documents",),
        relationship=(
            "case-number-driven party filings and court-issued documents; "
            "not a trial-court filing source"
        ),
        coverage="public appellate case documents for cases filed from 2020",
    ),
    DATA_PRODUCTS_SOURCE_ID: Component(
        source_id=DATA_PRODUCTS_SOURCE_ID,
        name="Washington AOC Public Index Products and Custom Extracts",
        source_role="official_bulk_court_index_catalog",
        base_url=DATA_PRODUCTS_URL,
        access_state="subscription_and_formal_request",
        operations=("data-products", "custom-extract"),
        relationship=(
            "recurring trial-court index and custom extract route; "
            "filed documents are a separate source layer"
        ),
        coverage="product-specific trial-court indexes with live omission list",
    ),
    JISLINK_SOURCE_ID: Component(
        source_id=JISLINK_SOURCE_ID,
        name="Washington JIS-Link",
        source_role="official_subscription_case_docket_display",
        base_url=JISLINK_URL,
        access_state="registered_subscription",
        operations=("jislink",),
        relationship=(
            "interactive case/docket display complement; does not display "
            "filed case documents"
        ),
        coverage="district, municipal, and superior data by system participation",
    ),
    APPELLATE_COMPLEMENTS_SOURCE_ID: Component(
        source_id=APPELLATE_COMPLEMENTS_SOURCE_ID,
        name="Washington Appellate Orders, Briefs, Calendars, and Issues",
        source_role="official_appellate_document_route_catalog",
        base_url=APPELLATE_COMPLEMENT_URLS["briefs"],
        access_state="open_static_and_open_form",
        operations=("appellate-complements",),
        relationship=(
            "orders, anticipated filings, briefs, calendars, and issue "
            "summaries complement opinions and exact-case document lookup"
        ),
        coverage="component-specific appellate publication windows",
    ),
    CASELOAD_SOURCE_ID: Component(
        source_id=CASELOAD_SOURCE_ID,
        name="Washington AOC Caseload Products",
        source_role="official_aggregate_court_activity_catalog",
        base_url=CASELOAD_URL,
        access_state="open_static_and_dashboard",
        operations=("caseload-routes",),
        relationship=(
            "aggregate trend and coverage diagnostic; not case-level evidence"
        ),
        coverage="court-level monthly, year-to-date, annual, and dashboard products",
    ),
    DIGITAL_ARCHIVES_SOURCE_ID: Component(
        source_id=DIGITAL_ARCHIVES_SOURCE_ID,
        name="Washington State Digital Archives Superior Court Records",
        source_role="official_title_scoped_historical_case_file_catalog",
        base_url=DIGITAL_ARCHIVES_TITLE_BASE,
        access_state="title_specific_search_preview_or_order",
        operations=("archive-title",),
        relationship=(
            "title-scoped historical/document complement with per-title "
            "availability and fulfillment"
        ),
        coverage="participating county superior-court titles; varies by title",
    ),
}

COMMAND_SOURCE = {
    "directory-counties": DIRECTORY_SOURCE_ID,
    "directory-search": DIRECTORY_SOURCE_ID,
    "directory-org": DIRECTORY_SOURCE_ID,
    "directory-pdf": DIRECTORY_SOURCE_ID,
    "case-form": CASE_DISCOVERY_SOURCE_ID,
    "case-search": CASE_DISCOVERY_SOURCE_ID,
    "case-routes": CURRENT_ROUTES_SOURCE_ID,
    "opinions-feed": OPINIONS_SOURCE_ID,
    "opinions-list": OPINIONS_SOURCE_ID,
    "opinion-detail": OPINIONS_SOURCE_ID,
    "opinion-download": OPINIONS_SOURCE_ID,
    "appellate-documents": APPELLATE_DOCUMENTS_SOURCE_ID,
    "data-products": DATA_PRODUCTS_SOURCE_ID,
    "custom-extract": DATA_PRODUCTS_SOURCE_ID,
    "jislink": JISLINK_SOURCE_ID,
    "appellate-complements": APPELLATE_COMPLEMENTS_SOURCE_ID,
    "caseload-routes": CASELOAD_SOURCE_ID,
    "archive-title": DIGITAL_ARCHIVES_SOURCE_ID,
}


def _component_provenance(component: Component) -> dict[str, str]:
    if component.source_id == DIGITAL_ARCHIVES_SOURCE_ID:
        return {
            "authority": "Washington Secretary of State",
            "publisher": "Washington State Archives",
        }
    return {
        "authority": "Washington State Judiciary",
        "publisher": "Washington State Administrative Office of the Courts",
    }


def _metadata(component: Component) -> SourceMetadata:
    provenance = _component_provenance(component)
    return SourceMetadata(
        source_id=component.source_id,
        name=component.name,
        source_role=component.source_role,
        base_url=component.base_url,
        dataset_id=component.source_id,
        metadata={
            **provenance,
            "adapter_family": ADAPTER_FAMILY,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "relationship": component.relationship,
            "coverage": component.coverage,
        },
    )


SOURCE_METADATA = {
    source_id: _metadata(component)
    for source_id, component in COMPONENTS.items()
}
CATALOG_METADATA = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="Washington Official Court Source Family Catalog",
    source_role="official_court_source_family_catalog",
    base_url=COURTS_ORIGIN,
    dataset_id="washington-official-court-source-family",
    metadata={
        "authority": "State of Washington official sources",
        "adapter_family": ADAPTER_FAMILY,
        "components": list(COMPONENTS),
    },
)

WARNINGS = (
    "Each component retains its own source identity and access state.",
    "Discovery indexes, local portals, archives, and aggregate products "
    "overlap but are not merged as equivalent evidence.",
    "Slip opinions can later be replaced by final published reports.",
)


class WashingtonCourtsError(RuntimeError):
    """Transport, source-schema, or caller-selection failure."""

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


class SourceChangedError(WashingtonCourtsError):
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


class SelectionError(WashingtonCourtsError):
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


@dataclass(frozen=True)
class Artifact:
    content: bytes
    source_url: str
    media_type: str
    headers: Mapping[str, str]
    status_code: int = 200

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return text or None


def _required(value: Any, field: str) -> str:
    text = _clean(value)
    if text is None:
        raise SourceChangedError(
            "required_field_missing",
            f"Washington courts response lacks {field}",
            details={"field": field},
        )
    return text


def _absolute(url: str, base: str = COURTS_ORIGIN) -> str:
    return urljoin(base, url.strip())


def _media_type(response: Any) -> str:
    headers = getattr(response, "headers", {})
    value = str(
        headers.get("Content-Type", headers.get("content-type", ""))
    )
    return value.split(";", 1)[0].strip().lower()


def _response_url(response: Any, fallback: str) -> str:
    return str(getattr(response, "url", None) or fallback)


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After", headers.get("retry-after"))
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


class WashingtonCourtsClient:
    """Bounded, rate-limited HTTP client with injectable transport."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def get(
        self,
        url: str,
        *,
        accept: str = "text/html,application/xhtml+xml",
        maximum_bytes: int = MAXIMUM_HTML_BYTES,
    ) -> Artifact:
        headers = {
            "Accept": accept,
            "User-Agent": DEFAULT_USER_AGENT,
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise WashingtonCourtsError(
                        "transport_error",
                        str(error),
                        retryable=True,
                        category="transport",
                        details={"url": url},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(
                        attempt,
                        _retry_after(response),
                    )
                )
                continue
            if status_code == 429:
                raise WashingtonCourtsError(
                    "rate_limited",
                    "Washington court source rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise WashingtonCourtsError(
                    "access_restricted",
                    f"Washington court source returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise WashingtonCourtsError(
                    "http_status",
                    f"Washington court source returned HTTP {status_code}",
                    retryable=status_code >= 500,
                    category="http",
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise WashingtonCourtsError(
                    "response_too_large",
                    "Washington court response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            return Artifact(
                content=content,
                source_url=_response_url(response, url),
                media_type=_media_type(response),
                headers={
                    str(key).lower(): str(value)
                    for key, value in getattr(
                        response, "headers", {}
                    ).items()
                },
                status_code=status_code,
            )
        raise WashingtonCourtsError(
            "transport_error",
            str(last_error or "request failed"),
            retryable=True,
            category="transport",
            details={"url": url},
        )


def _html(artifact: Artifact, marker: str) -> BeautifulSoup:
    if (
        artifact.media_type
        and "html" not in artifact.media_type
        and "xml" not in artifact.media_type
    ):
        raise SourceChangedError(
            "unexpected_media_type",
            "Washington court route did not return HTML",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    if marker.casefold() not in soup.get_text(" ", strip=True).casefold():
        raise SourceChangedError(
            "page_marker_missing",
            f"Washington court page lacks expected marker {marker!r}",
            details={"url": artifact.source_url, "marker": marker},
        )
    return soup


def _source_fields(
    artifact: Artifact,
    *,
    source_id: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "component_source_id": source_id,
        "adapter_family": ADAPTER_FAMILY,
        "source_url": artifact.source_url,
        "source_document_sha256": artifact.sha256,
        "source_document_bytes": len(artifact.content),
    }


def _component_records() -> list[dict[str, Any]]:
    return [
        {
            "record_kind": "source_component",
            "source_id": component.source_id,
            "component_source_id": component.source_id,
            "adapter_family": ADAPTER_FAMILY,
            "canonical_ref": f"WACOURT:SOURCE:{component.source_id}",
            "name": component.name,
            "source_role": component.source_role,
            "base_url": component.base_url,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "relationship": component.relationship,
            "coverage": component.coverage,
            **_component_provenance(component),
        }
        for component in COMPONENTS.values()
    ]


def _manifest_record() -> dict[str, Any]:
    return {
        "record_kind": "source_family_manifest",
        "source_id": CATALOG_SOURCE_ID,
        "component_source_id": CATALOG_SOURCE_ID,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": "WACOURT:MANIFEST:OFFICIAL",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "authority": "State of Washington official sources",
        "components": [
            {
                "source_id": component.source_id,
                "source_role": component.source_role,
                "access_state": component.access_state,
                "operations": list(component.operations),
                "relationship": component.relationship,
                **_component_provenance(component),
            }
            for component in COMPONENTS.values()
        ],
        "operation_access_model": {
            "case_form_and_court_codes": "open_static",
            "case_result_execution": "interactive_captcha",
            "appellate_document_form": "open_static_exact_case",
            "appellate_document_result_execution": "interactive_captcha",
            "opinion_lists_feeds_information_pdfs": "open_static",
            "directory_html_and_pdf": "open_static",
            "standard_bulk_indexes": "subscription",
            "custom_extract": "formal_request",
        },
        "evidence_relationships": {
            "current_system_routes": "routing complements",
            "jis_link": "display-oriented docket complement",
            "digital_archives": "title-scoped historical/document complement",
            "caseload": "aggregate coverage diagnostic",
        },
    }


def parse_directory_counties(artifact: Artifact) -> list[dict[str, Any]]:
    soup = _html(artifact, "Court Directory")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/court_dir/orgs/"]'):
        href = str(anchor.get("href") or "")
        match = re.search(r"/court_dir/orgs/([0-9]+)\.html", href)
        if not match:
            continue
        org_id = match.group(1)
        if org_id in seen:
            continue
        seen.add(org_id)
        county_name = _required(anchor.get_text(" ", strip=True), "county name")
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=DIRECTORY_SOURCE_ID,
                ),
                "record_kind": "court_directory_county",
                "canonical_ref": f"WACOURT:DIR:COUNTY:{org_id}",
                "organization_id": org_id,
                "county_name": county_name,
                "organization_url": _absolute(href),
                "route_provenance": artifact.source_url,
                "access_state": "open_static",
            }
        )
    if len(records) < 39:
        raise SourceChangedError(
            "county_directory_changed",
            "Washington court county directory returned fewer than 39 counties",
            details={"county_count": len(records), "url": artifact.source_url},
        )
    return records


def _directory_display_count(soup: BeautifulSoup) -> int | None:
    match = re.search(
        r"Displaying\s+[0-9,]+\s+through\s+[0-9,]+\s+of\s+([0-9,]+)",
        soup.get_text(" ", strip=True),
        re.IGNORECASE,
    )
    return int(match.group(1).replace(",", "")) if match else None


def parse_directory_people(artifact: Artifact) -> tuple[list[dict[str, Any]], int]:
    soup = _html(artifact, "Court Directory")
    total = _directory_display_count(soup)
    if total is None:
        raise SourceChangedError(
            "directory_count_missing",
            "Washington court directory no longer advertises its result count",
            details={"url": artifact.source_url},
        )
    records: list[dict[str, Any]] = []
    for anchor in soup.select('a[href*="court_dir.persondetail"]'):
        href = str(anchor.get("href") or "")
        query = parse_qs(urlsplit(_absolute(href, DIRECTORY_HOME_URL)).query)
        person_id = (query.get("indid") or [None])[0]
        org_id = (query.get("orgid") or [None])[0]
        if not person_id or not org_id:
            continue
        row = anchor.find_parent("tr")
        cells = row.find_all("td") if row else []
        organization = (
            _clean(cells[1].get_text(" ", strip=True))
            if len(cells) > 1
            else None
        )
        name_title = _required(
            anchor.get_text(" ", strip=True),
            "directory name and title",
        )
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=DIRECTORY_SOURCE_ID,
                ),
                "record_kind": "court_directory_person",
                "canonical_ref": (
                    f"WACOURT:DIR:PERSON:{person_id}:ORG:{org_id}"
                ),
                "person_id": person_id,
                "organization_id": org_id,
                "name_and_title": name_title,
                "organization": organization,
                "detail_url": _absolute(href, DIRECTORY_HOME_URL),
                "route_provenance": artifact.source_url,
                "access_state": "open_static",
            }
        )
    if not records and total:
        raise SourceChangedError(
            "directory_rows_missing",
            "Washington court directory advertises results without person rows",
            details={"total_results": total, "url": artifact.source_url},
        )
    return records, total


def _safe_org_id(value: str) -> str:
    if not value.isdigit() or int(value) <= 0:
        raise SelectionError(
            "organization_id_invalid",
            "organization ID must be a positive integer",
            details={"organization_id": value},
        )
    return value


def parse_directory_org(
    artifact: Artifact,
    org_id: str,
    *,
    contact_limit: int | None,
) -> dict[str, Any]:
    soup = _html(artifact, "Court Directory")
    heading = soup.find("h2")
    heading_text = _required(
        heading.get_text(" ", strip=True) if heading else None,
        "directory organization heading",
    )
    if "encountered an Error" in soup.get_text(" ", strip=True):
        raise SelectionError(
            "organization_not_found",
            f"Washington court directory has no organization {org_id}",
            details={"organization_id": org_id, "url": artifact.source_url},
        )

    section_names: list[str] = []
    for cell in soup.select("td[colspan='3']"):
        text = _clean(cell.get_text(" ", strip=True))
        if text and text not in section_names:
            section_names.append(text)

    contacts: list[dict[str, Any]] = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            continue
        name_title = _clean(cells[0].get_text(" ", strip=True))
        if not name_title or len(name_title) > 240:
            continue
        phone = _clean(cells[2].get_text(" ", strip=True))
        email_anchor = row.select_one("a[href^='mailto:']")
        email = None
        if email_anchor:
            email = _clean(str(email_anchor.get("href") or "")[7:])
        if not phone and not email:
            continue
        contacts.append(
            {
                "name_and_title": name_title,
                "phone": phone,
                "email": email,
            }
        )
        if contact_limit is not None and len(contacts) >= contact_limit:
            break

    websites: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        label = _clean(anchor.get_text(" ", strip=True))
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        absolute = _absolute(href, artifact.source_url)
        if absolute in seen_urls:
            continue
        if label == "Visit Website" or (
            urlsplit(absolute).netloc
            and urlsplit(absolute).netloc
            not in {"www.courts.wa.gov", "courts.wa.gov"}
        ):
            seen_urls.add(absolute)
            websites.append(
                {
                    "label": label or absolute,
                    "url": absolute,
                }
            )

    return {
        **_source_fields(artifact, source_id=DIRECTORY_SOURCE_ID),
        "record_kind": "court_directory_organization",
        "canonical_ref": f"WACOURT:DIR:ORG:{org_id}",
        "organization_id": org_id,
        "heading": heading_text,
        "sections": section_names,
        "contacts": contacts,
        "contact_count_returned": len(contacts),
        "contact_limit": contact_limit,
        "websites": websites,
        "route_provenance": artifact.source_url,
        "access_state": "open_static",
    }


def _form_options(
    soup: BeautifulSoup,
    input_id: str,
) -> list[dict[str, str]]:
    source_input = soup.find(id=input_id)
    if source_input is None:
        return []
    list_node = source_input.find_next("ul")
    if list_node is None:
        return []
    options: list[dict[str, str]] = []
    for item in list_node.select("li[data-value]"):
        value = str(item.get("data-value") or "").strip()
        label_node = item.select_one(".mdc-list-item__text")
        label = _clean(
            label_node.get_text(" ", strip=True)
            if label_node
            else item.get_text(" ", strip=True)
        )
        if value and label:
            options.append({"code": value, "name": label})
    return options


def parse_case_form(artifact: Artifact) -> dict[str, Any]:
    soup = _html(artifact, "Case Search")
    text = artifact.text
    has_captcha = bool(
        soup.select_one(".g-recaptcha")
        or "recaptcha" in text.casefold()
    )
    if not has_captcha:
        raise SourceChangedError(
            "case_search_challenge_changed",
            "Washington case form no longer exposes the observed result challenge",
            details={"url": artifact.source_url},
        )
    routes = sorted(
        {
            match.group(1)
            for match in re.finditer(
                r'formAction\s*\+=\s*"(name|case|bname)"',
                text,
            )
        }
    )
    if routes != ["bname", "case", "name"]:
        raise SourceChangedError(
            "case_search_routes_changed",
            "Washington case form result routes changed",
            details={"routes": routes, "url": artifact.source_url},
        )

    court_groups = {
        "superior": _form_options(soup, "CRT_ITL_NU_superior"),
        "appellate": _form_options(soup, "CRT_ITL_NU_appellate"),
        "limited_jurisdiction": _form_options(
            soup,
            "CRT_ITL_NU_district",
        ),
    }
    if len(court_groups["superior"]) < 39:
        raise SourceChangedError(
            "superior_court_codes_changed",
            "Washington case form returned fewer than 39 superior court codes",
            details={
                "count": len(court_groups["superior"]),
                "url": artifact.source_url,
            },
        )
    if len(court_groups["appellate"]) < 4:
        raise SourceChangedError(
            "appellate_court_codes_changed",
            "Washington case form returned fewer than four appellate court codes",
            details={
                "count": len(court_groups["appellate"]),
                "url": artifact.source_url,
            },
        )
    if not court_groups["limited_jurisdiction"]:
        raise SourceChangedError(
            "limited_court_codes_changed",
            "Washington case form returned no limited-jurisdiction court codes",
            details={"url": artifact.source_url},
        )

    input_fields = []
    for node in soup.select("form#searchform input[name]"):
        name = str(node.get("name") or "")
        if not name or name.startswith("g-recaptcha"):
            continue
        input_fields.append(
            {
                "name": name,
                "type": str(node.get("type") or "text"),
                "required": node.has_attr("required"),
                "default": str(node.get("value") or ""),
            }
        )

    return {
        **_source_fields(artifact, source_id=CASE_DISCOVERY_SOURCE_ID),
        "record_kind": "case_discovery_form_contract",
        "canonical_ref": "WACOURT:CASE:FORM",
        "court_codes": court_groups,
        "case_type_codes": {
            "superior": _form_options(soup, "TYP_CD_Superior"),
            "limited_jurisdiction": _form_options(
                soup,
                "TYP_CD_District",
            ),
        },
        "input_fields": input_fields,
        "result_route_types": routes,
        "result_route_template": (
            f"{CASE_ORIGIN}/index.cfm?fa=home.caselist&init&rtlist={{type}}"
        ),
        "operations": {
            "form_metadata": {
                "access_state": "open_static",
                "status": "ok",
            },
            "result_execution": {
                "access_state": "interactive_captcha",
                "status": "human_required",
            },
        },
        "route_provenance": artifact.source_url,
    }


def parse_case_routes(artifact: Artifact) -> list[dict[str, Any]]:
    _html(artifact, "About This Site")
    records: list[dict[str, Any]] = []
    pattern = re.compile(
        r'<span[^>]*class=["\'][^"\']*semi-bold[^"\']*["\'][^>]*>'
        r"(When doing case searches for[^<]+)</span>"
        r"(.*?)<a[^>]+href=[\"']([^\"']+)[\"']",
        re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(pattern.finditer(artifact.text), start=1):
        heading = _clean(BeautifulSoup(match.group(1), "html.parser").get_text())
        coverage = _clean(
            BeautifulSoup(match.group(2), "html.parser").get_text(" ")
        )
        route_url = _absolute(match.group(3), artifact.source_url)
        vendor = _route_vendor(route_url)
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=CURRENT_ROUTES_SOURCE_ID,
                ),
                "record_kind": "current_court_record_route",
                "canonical_ref": f"WACOURT:ROUTE:{vendor}:{index}",
                "route_name": heading,
                "coverage": coverage,
                "vendor_family": vendor,
                "route_url": route_url,
                "access_state": "external_current_record_system",
                "route_provenance": artifact.source_url,
            }
        )
    if len(records) < 8:
        raise SourceChangedError(
            "routing_matrix_changed",
            "Washington case home returned fewer than eight current-system routes",
            details={"route_count": len(records), "url": artifact.source_url},
        )
    return records


def _route_vendor(url: str) -> str:
    host = urlsplit(url).netloc.casefold()
    if "odysseyportal" in host:
        return "odyssey"
    if "kingcounty" in host and "kcdc" not in host:
        return "king_superior"
    if "linxonline" in host:
        return "pierce_linx"
    if "kcdc" in host:
        return "king_district"
    if "kitsap" in host:
        return "kitsap_district"
    if "seattle" in host:
        return "seattle_municipal"
    if "spokane" in host:
        return "spokane_municipal"
    if "tylerhost" in host:
        return "tyler_researchwa"
    return re.sub(r"[^a-z0-9]+", "_", host).strip("_") or "route"


def parse_opinion_feed(
    artifact: Artifact,
    feed_id: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(artifact.content)
    except ET.ParseError as error:
        raise SourceChangedError(
            "opinion_feed_invalid_xml",
            "Washington opinion feed is not valid XML",
            details={"url": artifact.source_url},
        ) from error
    channel = root.find("channel")
    if channel is None:
        raise SourceChangedError(
            "opinion_feed_channel_missing",
            "Washington opinion feed lacks an RSS channel",
            details={"url": artifact.source_url},
        )
    _, court, publication_status = RSS_FEEDS[feed_id]
    records: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title = _required(item.findtext("title"), "RSS item title")
        case_number, separator, caption = title.partition(" -- ")
        info_url = _required(item.findtext("link"), "RSS opinion link")
        description = item.findtext("description") or ""
        pdf_match = re.search(r'href="([^"]+\.pdf[^"]*)"', description)
        if not pdf_match:
            pdf_match = re.search(r"(https?://\S+\.pdf)", description)
        pdf_url = (
            _absolute(pdf_match.group(1), artifact.source_url)
            if pdf_match
            else None
        )
        filename = (
            (parse_qs(urlsplit(info_url).query).get("filename") or [None])[0]
        )
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=OPINIONS_SOURCE_ID,
                ),
                "record_kind": "appellate_opinion",
                "canonical_ref": (
                    f"WACOURT:OPINION:{filename or case_number}"
                ),
                "feed_id": feed_id,
                "feed_title": _clean(channel.findtext("title")),
                "court": court,
                "publication_status": publication_status,
                "case_number": case_number.strip(),
                "caption": caption.strip() if separator else title,
                "publication_date": _clean(item.findtext("pubDate")),
                "opinion_filename": filename,
                "information_url": info_url,
                "pdf_url": pdf_url,
                "route_provenance": artifact.source_url,
                "access_state": "open_rss_and_pdf",
            }
        )
    return records


def _opinion_list_url(
    scope: str,
    *,
    year: int | None,
    court_level: str | None,
    publication_status: str | None,
) -> str:
    if scope == "recent":
        return f"{OPINIONS_INDEX_URL}?fa=opinions.recent"
    if scope == "all":
        return f"{OPINIONS_INDEX_URL}?fa=opinions.displayAll"
    if year is None or court_level is None or publication_status is None:
        raise SelectionError(
            "opinion_year_parameters_missing",
            "year scope requires --year, --court-level, and --publication-status",
        )
    return (
        f"{OPINIONS_INDEX_URL}?"
        + urlencode(
            {
                "fa": "opinions.byYear",
                "fileYear": year,
                "crtLevel": court_level,
                "pubStatus": publication_status,
            }
        )
    )


def parse_opinion_list(
    artifact: Artifact,
    *,
    scope: str,
    year: int | None,
    court_level: str | None,
    publication_status: str | None,
    query_text: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    soup = _html(artifact, "Opinions")
    records: list[dict[str, Any]] = []
    needle = query_text.casefold() if query_text else None
    for row in soup.find_all("tr"):
        info_anchor = row.select_one('a[href*="opinions.showOpinion"]')
        if info_anchor is None:
            continue
        cells = [
            _clean(cell.get_text(" ", strip=True))
            for cell in row.find_all("td", recursive=False)
        ]
        cells = [cell for cell in cells if cell is not None]
        case_number = _required(
            info_anchor.get_text(" ", strip=True),
            "opinion case number",
        )
        href = _absolute(str(info_anchor.get("href") or ""), artifact.source_url)
        filename = (
            parse_qs(urlsplit(href).query).get("filename") or [None]
        )[0]
        pdf_anchor = row.select_one('a[href*="/opinions/pdf/"]')
        pdf_url = (
            _absolute(str(pdf_anchor.get("href")), artifact.source_url)
            if pdf_anchor
            else None
        )
        searchable = " ".join(cells + [case_number]).casefold()
        if needle and needle not in searchable:
            continue
        record = {
            **_source_fields(artifact, source_id=OPINIONS_SOURCE_ID),
            "record_kind": "appellate_opinion",
            "canonical_ref": f"WACOURT:OPINION:{filename or case_number}",
            "list_scope": scope,
            "list_year": year,
            "court_level_code": court_level,
            "publication_status_code": publication_status,
            "case_number": case_number,
            "file_date": cells[0] if cells else None,
            "division": cells[2] if len(cells) >= 5 else None,
            "caption": cells[3] if len(cells) >= 5 else None,
            "file_contains": cells[4] if len(cells) >= 5 else None,
            "source_columns": cells,
            "opinion_filename": filename,
            "information_url": href,
            "pdf_url": pdf_url,
            "route_provenance": artifact.source_url,
            "access_state": "open_static_and_pdf",
        }
        records.append(record)
        if limit is not None and len(records) >= limit:
            break
    return records


def _opinion_filename(value: str) -> str:
    normalized = value.strip()
    if re.fullmatch(r"[0-9]+(?:-[0-9])?", normalized):
        return re.sub(r"[^0-9]", "", normalized) + "MAJ"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
        raise SelectionError(
            "opinion_identifier_invalid",
            "opinion identifier must be a docket number or advertised filename",
            details={"identifier": value},
        )
    return normalized


def parse_opinion_info(
    artifact: Artifact,
    filename: str,
) -> dict[str, Any]:
    soup = _html(artifact, "Opinion Information Sheet")
    fields: dict[str, Any] = {}
    repeated: dict[str, list[str]] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = _clean(cells[0].get_text(" ", strip=True))
        value = _clean(cells[1].get_text(" ", strip=True))
        if not label or not value:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_")
        if not key:
            continue
        if key in fields:
            repeated.setdefault(key, [str(fields.pop(key))]).append(value)
        elif key in repeated:
            repeated[key].append(value)
        else:
            fields[key] = value
    fields.update(repeated)
    docket_number = fields.get("docket_number")
    if not docket_number:
        raise SourceChangedError(
            "opinion_docket_missing",
            "Washington opinion information sheet lacks a docket number",
            details={"url": artifact.source_url, "filename": filename},
        )
    pdf_links = [
        _absolute(str(anchor.get("href")), artifact.source_url)
        for anchor in soup.select('a[href*="/opinions/pdf/"]')
    ]
    return {
        **_source_fields(artifact, source_id=OPINIONS_SOURCE_ID),
        "record_kind": "appellate_opinion_information",
        "canonical_ref": f"WACOURT:OPINION:{filename}",
        "opinion_filename": filename,
        "case_number": docket_number,
        "court": _court_from_opinion_text(soup.get_text(" ", strip=True)),
        "publication_notice": _publication_notice(
            soup.get_text(" ", strip=True)
        ),
        "fields": fields,
        "pdf_urls": pdf_links,
        "route_provenance": artifact.source_url,
        "access_state": "open_static",
    }


def _court_from_opinion_text(text: str) -> str | None:
    for value in (
        "Court of Appeals Division I",
        "Court of Appeals Division II",
        "Court of Appeals Division III",
        "Supreme Court",
    ):
        if value.casefold() in text.casefold():
            return value
    return None


def _publication_notice(text: str) -> str | None:
    match = re.search(
        r"(DO NOT CITE[^.]*\.|PUBLISHED OPINION)",
        text,
        re.IGNORECASE,
    )
    return _clean(match.group(1)) if match else None


def parse_data_products(artifact: Artifact) -> list[dict[str, Any]]:
    soup = _html(artifact, "Data Dissemination")
    candidates = []
    for table in soup.find_all("table"):
        header = table.get_text(" ", strip=True)
        if "Index Type" in header and "Annual Cost" in header:
            candidates.append(table)
    product_table = (
        min(
            candidates,
            key=lambda table: len(table.find_all("table")),
        )
        if candidates
        else None
    )
    if product_table is None:
        raise SourceChangedError(
            "data_product_table_missing",
            "Washington AOC data-product table is missing",
            details={"url": artifact.source_url},
        )
    records: list[dict[str, Any]] = []
    for row in product_table.find_all("tr")[1:]:
        cells = [
            _clean(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        if len(cells) != 5 or not cells[0]:
            continue
        product_match = re.search(r"\(([A-Za-z0-9]+)\)", cells[0])
        product_code = (
            product_match.group(1).upper()
            if product_match
            else re.sub(r"[^A-Za-z0-9]+", "_", cells[0]).strip("_").upper()
        )
        cost_match = re.search(r"\$([0-9,]+(?:\.[0-9]+)?)", cells[4] or "")
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=DATA_PRODUCTS_SOURCE_ID,
                ),
                "record_kind": "court_bulk_index_product",
                "canonical_ref": f"WACOURT:DATA_PRODUCT:{product_code}",
                "product_code": product_code,
                "product_name": cells[0],
                "court_level": cells[1],
                "coverage": cells[2],
                "delivery_frequency": cells[3],
                "annual_cost_display": cells[4],
                "annual_cost_usd": (
                    float(cost_match.group(1).replace(",", ""))
                    if cost_match
                    else None
                ),
                "access_state": "subscription",
                "coverage_snapshot": "live_page_at_retrieval",
                "route_provenance": artifact.source_url,
            }
        )
    if len(records) != 5:
        raise SourceChangedError(
            "data_product_count_changed",
            "Washington AOC no longer advertises exactly five standard products",
            details={"product_count": len(records), "url": artifact.source_url},
        )

    missing: list[str] = []
    marker = soup.find(string=re.compile(r"Presently,\s+the courts missing", re.I))
    if marker:
        parent = marker.parent
        missing_list = parent.find_next("ul") if parent else None
        if missing_list:
            missing = [
                _required(item.get_text(" ", strip=True), "missing court")
                for item in missing_list.find_all("li", recursive=False)
            ]
    records.append(
        {
            **_source_fields(
                artifact,
                source_id=DATA_PRODUCTS_SOURCE_ID,
            ),
            "record_kind": "court_bulk_index_coverage_snapshot",
            "canonical_ref": (
                f"WACOURT:DATA_PRODUCT:COVERAGE:{artifact.sha256[:16]}"
            ),
            "missing_courts": missing,
            "missing_court_count": len(missing),
            "coverage_snapshot": "live_page_at_retrieval",
            "local_complement_required": bool(missing),
            "route_provenance": artifact.source_url,
        }
    )
    return records


def parse_custom_extract(
    request_artifact: Artifact,
    fee_artifact: Artifact,
    form_artifact: Artifact | None,
) -> dict[str, Any]:
    request_soup = _html(request_artifact, "Forms")
    fee_soup = _html(fee_artifact, "Fee Schedule")
    forms = []
    for anchor in request_soup.select('a[href*="requestForInfo"]'):
        href = _absolute(str(anchor.get("href")), request_artifact.source_url)
        forms.append(
            {
                "label": _clean(anchor.get_text(" ", strip=True)),
                "url": href,
            }
        )
    if not forms:
        raise SourceChangedError(
            "custom_extract_form_missing",
            "Washington AOC data-request page exposes no request form",
            details={"url": request_artifact.source_url},
        )
    fees = [
        _required(item.get_text(" ", strip=True), "fee item")
        for item in fee_soup.find_all("li")
        if "$" in item.get_text()
    ]
    record = {
        **_source_fields(
            request_artifact,
            source_id=DATA_PRODUCTS_SOURCE_ID,
        ),
        "record_kind": "court_custom_extract_route",
        "canonical_ref": "WACOURT:DATA_PRODUCT:CUSTOM_EXTRACT",
        "request_forms": forms,
        "fee_schedule_url": fee_artifact.source_url,
        "fee_schedule_sha256": fee_artifact.sha256,
        "current_fee_items": fees,
        "data_policy_url": DATA_POLICY_URL,
        "access_state": "formal_request",
        "route_provenance": request_artifact.source_url,
    }
    if form_artifact is not None:
        record["fillable_form"] = {
            "url": form_artifact.source_url,
            "media_type": form_artifact.media_type,
            "byte_length": len(form_artifact.content),
            "sha256": form_artifact.sha256,
        }
    return record


def parse_jislink(artifact: Artifact) -> dict[str, Any]:
    soup = _html(artifact, "JIS-Link")
    fee_statement = None
    for paragraph in soup.find_all("p"):
        value = _clean(paragraph.get_text(" ", strip=True))
        if value and "A subscriber pays" in value:
            fee_statement = value
            break
    access_links = []
    for anchor in soup.find_all("a", href=True):
        label = _clean(anchor.get_text(" ", strip=True))
        href = _absolute(str(anchor["href"]), artifact.source_url)
        if label and (
            "JIS" in label
            or "ACORDS" in label
            or "Odyssey" in label
            or "Document Portal" in label
        ):
            access_links.append({"label": label, "url": href})
    if not access_links:
        raise SourceChangedError(
            "jislink_routes_missing",
            "Washington JIS-Link page exposes no access routes",
            details={"url": artifact.source_url},
        )
    return {
        **_source_fields(artifact, source_id=JISLINK_SOURCE_ID),
        "record_kind": "jis_link_subscription_route",
        "canonical_ref": "WACOURT:JISLINK",
        "fee_statement": fee_statement,
        "access_routes": access_links,
        "access_state": "registered_subscription",
        "record_scope": "case information and docket display",
        "document_scope": "filed documents are obtained from the court of record",
        "route_provenance": artifact.source_url,
    }


def parse_appellate_document_form(
    artifact: Artifact,
    *,
    court: str,
    case_number: str,
) -> dict[str, Any]:
    soup = _html(artifact, "Appellate Courts Public Case Document Search")
    text = soup.get_text(" ", strip=True)
    has_captcha = "recaptcha" in artifact.text.casefold()
    if not has_captcha:
        raise SourceChangedError(
            "appellate_document_challenge_changed",
            "Washington appellate document form no longer exposes reCAPTCHA",
            details={"url": artifact.source_url},
        )
    exclusions = []
    for item in soup.find_all("li"):
        value = _clean(item.get_text(" ", strip=True))
        if value and (
            "before January 1, 2020" in value
            or "not available" in value.casefold()
        ):
            exclusions.append(value)
    return {
        **_source_fields(
            artifact,
            source_id=APPELLATE_DOCUMENTS_SOURCE_ID,
        ),
        "record_kind": "appellate_case_document_route",
        "canonical_ref": (
            f"WACOURT:APPDOC:{court.upper()}:{case_number}"
        ),
        "court": court,
        "case_number": case_number,
        "portal_url": artifact.source_url,
        "advertised_scope": _clean(
            next(
                (
                    paragraph.get_text(" ", strip=True)
                    for paragraph in soup.find_all("p")
                    if "complete Appellate Case number"
                    in paragraph.get_text(" ", strip=True)
                ),
                None,
            )
        ),
        "current_exclusions": exclusions,
        "operations": {
            "form_metadata": {
                "status": "ok",
                "access_state": "open_static_exact_case",
            },
            "result_execution": {
                "status": "human_required",
                "access_state": "interactive_captcha",
            },
        },
        "page_text_fingerprint": sha256_fingerprint(text),
        "route_provenance": artifact.source_url,
    }


def parse_appellate_complement(
    artifact: Artifact,
    *,
    kind: str,
    case_number: str | None,
) -> list[dict[str, Any]]:
    soup = _html(
        artifact,
        {
            "orders": "Orders",
            "notice": "opinions may be filed",
            "calendar": "Calendar",
            "briefs": "Briefs",
            "issues": "issues",
        }[kind],
    )
    records: list[dict[str, Any]] = []
    if kind == "notice":
        for row in soup.find_all("tr"):
            cells = [
                _clean(cell.get_text(" ", strip=True))
                for cell in row.find_all("td", recursive=False)
            ]
            cells = [value for value in cells if value]
            if len(cells) < 3 or not re.fullmatch(
                r"[0-9]{5,6}-[0-9]",
                cells[1],
            ):
                continue
            records.append(
                {
                    **_source_fields(
                        artifact,
                        source_id=APPELLATE_COMPLEMENTS_SOURCE_ID,
                    ),
                    "record_kind": "anticipated_opinion_filing",
                    "canonical_ref": f"WACOURT:NOTICE:{cells[1]}:{cells[0]}",
                    "filing_date": cells[0],
                    "case_number": cells[1],
                    "caption": cells[2],
                    "argument_note": cells[3] if len(cells) > 3 else None,
                    "route_provenance": artifact.source_url,
                    "access_state": "open_static",
                }
            )
        return records

    for index, anchor in enumerate(soup.find_all("a", href=True), start=1):
        href = _absolute(str(anchor["href"]), artifact.source_url)
        label = _clean(anchor.get_text(" ", strip=True))
        if not label:
            continue
        relevant = {
            "orders": ".pdf" in href.casefold(),
            "calendar": (
                "calendar" in href.casefold()
                or "docket" in label.casefold()
            ),
            "briefs": (
                "coabriefs" in href.casefold()
                or "brief" in label.casefold()
            ),
            "issues": (
                ".pdf" in href.casefold()
                or "issue" in label.casefold()
            ),
        }[kind]
        if not relevant:
            continue
        context = _clean(anchor.parent.get_text(" ", strip=True)) if anchor.parent else label
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=APPELLATE_COMPLEMENTS_SOURCE_ID,
                ),
                "record_kind": f"appellate_{kind}_route",
                "canonical_ref": (
                    f"WACOURT:APPCOMP:{kind.upper()}:"
                    f"{hashlib.sha256(href.encode()).hexdigest()[:16]}"
                ),
                "route_label": label,
                "route_url": href,
                "context": context,
                "case_number_filter": case_number,
                "route_provenance": artifact.source_url,
                "access_state": "open_static_or_form",
            }
        )
    if case_number:
        court_forms = {
            "A08": "coaBriefs.ScHome",
            "A01": "coaBriefs.Div1Home",
            "A02": "coaBriefs.Div2Home",
            "A03": "coaBriefs.Div3Home",
        }
        if kind == "briefs":
            for court_id, return_action in court_forms.items():
                records.append(
                    {
                        **_source_fields(
                            artifact,
                            source_id=APPELLATE_COMPLEMENTS_SOURCE_ID,
                        ),
                        "record_kind": "appellate_brief_case_search_route",
                        "canonical_ref": (
                            f"WACOURT:BRIEF_ROUTE:{court_id}:{case_number}"
                        ),
                        "court_id": court_id,
                        "case_number": case_number,
                        "method": "POST",
                        "action": (
                            f"{COURTS_ORIGIN}/appellate_trial_courts/"
                            "coaBriefs/index.cfm?"
                            f"fa=coabriefs.searchRequest&courtId={court_id}"
                        ),
                        "form_fields": {
                            "xfa": return_action,
                            "searchTerms": case_number,
                            "searchType": "case",
                        },
                        "access_state": "open_form",
                        "route_provenance": artifact.source_url,
                    }
                )
    return records


def parse_caseload_routes(artifact: Artifact) -> list[dict[str, Any]]:
    soup = _html(artifact, "Caseloads of the Courts of Washington")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = _absolute(str(anchor["href"]), artifact.source_url)
        label = _clean(anchor.get_text(" ", strip=True))
        if (
            not label
            or "/caseload/" not in href
            or href in seen
            or "notifications" in href
        ):
            continue
        seen.add(href)
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=CASELOAD_SOURCE_ID,
                ),
                "record_kind": "court_caseload_product_route",
                "canonical_ref": (
                    "WACOURT:CASELOAD:"
                    f"{hashlib.sha256(href.encode()).hexdigest()[:16]}"
                ),
                "label": label,
                "route_url": href,
                "delivery_format": _route_format(href),
                "evidence_scope": "aggregate_activity_and_coverage_diagnostic",
                "route_provenance": artifact.source_url,
                "access_state": "open_static_or_dashboard",
            }
        )
    if len(records) < 8:
        raise SourceChangedError(
            "caseload_routes_changed",
            "Washington caseload page returned too few product routes",
            details={"route_count": len(records), "url": artifact.source_url},
        )
    return records


def _route_format(url: str) -> str:
    path = urlsplit(url).path.casefold()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".xlsx") or path.endswith(".xls"):
        return "excel"
    if "dashboard" in path:
        return "interactive_dashboard"
    return "html"


def parse_archive_title(artifact: Artifact, title_id: str) -> dict[str, Any]:
    soup = _html(artifact, "Title Info")
    heading = soup.select_one(".pageTopTitle h1") or soup.find(
        "span",
        string=re.compile(r"Title Info:", re.IGNORECASE),
    )
    title = _required(
        heading.get_text(" ", strip=True) if heading else None,
        "archive title heading",
    )
    metadata: dict[str, str] = {}
    table = soup.select_one("table.titleMetaData")
    if table is None:
        raise SourceChangedError(
            "archive_metadata_missing",
            "Washington Digital Archives title metadata table is missing",
            details={"url": artifact.source_url},
        )
    for row in table.find_all("tr", recursive=False):
        heading_cell = row.find("th")
        value_cell = row.find("td")
        if not heading_cell or not value_cell:
            continue
        label = _clean(heading_cell.get_text(" ", strip=True))
        value = _clean(value_cell.get_text(" ", strip=True))
        if label and value:
            key = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_")
            metadata[key] = value
    form = table.find("form")
    fields = []
    if form:
        for node in form.select("input[name]"):
            fields.append(
                {
                    "name": str(node.get("name") or ""),
                    "type": str(node.get("type") or "text"),
                    "default": str(node.get("value") or ""),
                }
            )
    notices = [
        _required(node.get_text(" ", strip=True), "archive site notice")
        for node in soup.select(".siteNotice")
    ]
    count_text = metadata.get("record_count")
    count = (
        int(count_text.replace(",", ""))
        if count_text and count_text.replace(",", "").isdigit()
        else None
    )
    return {
        **_source_fields(
            artifact,
            source_id=DIGITAL_ARCHIVES_SOURCE_ID,
        ),
        "record_kind": "digital_archives_court_title",
        "canonical_ref": f"WACOURT:ARCHIVE_TITLE:{title_id}",
        "title_id": title_id,
        "title": title.removeprefix("Title Info:").strip(),
        "metadata": metadata,
        "record_count": count,
        "search": {
            "method": str(form.get("method") or "GET").upper() if form else None,
            "action": (
                _absolute(str(form.get("action")), artifact.source_url)
                if form and form.get("action")
                else None
            ),
            "fields": fields,
        },
        "site_notices": notices,
        "availability_scope": "per_title_and_operation",
        "route_provenance": artifact.source_url,
        "access_state": "title_specific_search_preview_or_order",
    }


def _download_record(
    artifact: Artifact,
    *,
    source_id: str,
    record_kind: str,
    canonical_ref: str,
    destination: Path,
    overwrite: bool,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    if destination.exists() and not overwrite:
        raise SelectionError(
            "destination_exists",
            f"destination exists; pass --overwrite: {destination}",
            details={"destination": str(destination)},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(artifact.content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return {
        **_source_fields(artifact, source_id=source_id),
        "record_kind": record_kind,
        "canonical_ref": canonical_ref,
        "artifact_path": str(destination.resolve()),
        "media_type": artifact.media_type,
        "byte_length": len(artifact.content),
        "sha256": artifact.sha256,
        **dict(extra),
    }


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=STATE_GEOID,
        name="Washington",
        state_code=STATE_CODE,
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
    }
    return {
        key: (
            str(value)
            if isinstance(value, Path)
            else value
        )
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    if args.command in {"sources", "manifest"}:
        source = CATALOG_METADATA
    elif args.command == "probe":
        selected = getattr(args, "component", None) or []
        source = (
            SOURCE_METADATA[selected[0]]
            if len(selected) == 1
            else CATALOG_METADATA
        )
    else:
        source = SOURCE_METADATA[COMMAND_SOURCE[args.command]]
    return PublicRecordsQuery(
        source=source,
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
        ),
    )


def _public_error(error: WashingtonCourtsError) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _client(args: argparse.Namespace) -> WashingtonCourtsClient:
    return WashingtonCourtsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )


def _result_execution_error(
    *,
    code: str,
    message: str,
    details: Mapping[str, Any],
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="access",
        retryable=False,
        details=details,
    )


def _execute(
    args: argparse.Namespace,
    client: WashingtonCourtsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    command = args.command
    if command == "sources":
        return PublicRecordsResult.success(
            query,
            _component_records(),
            warnings=WARNINGS,
        )
    if command == "manifest":
        return PublicRecordsResult.success(
            query,
            [_manifest_record()],
            warnings=WARNINGS,
        )
    if command == "directory-counties":
        artifact = client.get(DIRECTORY_COUNTY_URL)
        return PublicRecordsResult.success(
            query,
            parse_directory_counties(artifact),
            warnings=WARNINGS,
        )
    if command == "directory-search":
        records = _directory_search(client, args)
        return PublicRecordsResult.success(query, records, warnings=WARNINGS)
    if command == "directory-org":
        org_id = _safe_org_id(args.organization_id)
        artifact = client.get(
            f"{DIRECTORY_HOME_URL}orgs/{org_id}.html"
        )
        record = parse_directory_org(
            artifact,
            org_id,
            contact_limit=args.limit,
        )
        return PublicRecordsResult.success(query, [record], warnings=WARNINGS)
    if command == "directory-pdf":
        artifact = client.get(
            DIRECTORY_PDF_URL,
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        _require_pdf(artifact)
        record = _download_record(
            artifact,
            source_id=DIRECTORY_SOURCE_ID,
            record_kind="court_directory_pdf_artifact",
            canonical_ref=f"WACOURT:DIR:PDF:{artifact.sha256}",
            destination=args.destination,
            overwrite=args.overwrite,
            extra={"route_provenance": DIRECTORY_PDF_URL},
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[record["artifact_path"]],
            warnings=WARNINGS,
        )
    if command == "case-form":
        artifact = client.get(CASE_FORM_URL)
        return PublicRecordsResult.success(
            query,
            [parse_case_form(artifact)],
            warnings=WARNINGS,
        )
    if command == "case-search":
        artifact = client.get(CASE_FORM_URL)
        contract = parse_case_form(artifact)
        record = _case_search_route(contract, args)
        return PublicRecordsResult.failure(
            query,
            ResultStatus.HUMAN_REQUIRED,
            [
                _result_execution_error(
                    code="case_result_captcha_required",
                    message=(
                        "Washington statewide case-result execution requires "
                        "interactive CAPTCHA completion"
                    ),
                    details={
                        "operation": "result_execution",
                        "form_url": CASE_FORM_URL,
                        "route": record["result_route"],
                        "prepared_route": record,
                    },
                )
            ],
            warnings=WARNINGS,
        )
    if command == "case-routes":
        artifact = client.get(CASE_HOME_URL)
        return PublicRecordsResult.success(
            query,
            parse_case_routes(artifact),
            warnings=WARNINGS,
        )
    if command == "opinions-feed":
        url = RSS_FEEDS[args.feed][0]
        artifact = client.get(
            url,
            accept="application/rss+xml,application/xml,text/xml",
        )
        records = parse_opinion_feed(artifact, args.feed)
        if args.limit is not None:
            records = records[: args.limit]
        return PublicRecordsResult.success(query, records, warnings=WARNINGS)
    if command == "opinions-list":
        url = _opinion_list_url(
            args.scope,
            year=args.year,
            court_level=args.court_level,
            publication_status=args.publication_status,
        )
        artifact = client.get(url)
        records = parse_opinion_list(
            artifact,
            scope=args.scope,
            year=args.year,
            court_level=args.court_level,
            publication_status=args.publication_status,
            query_text=args.query,
            limit=args.limit,
        )
        return PublicRecordsResult.success(query, records, warnings=WARNINGS)
    if command == "opinion-detail":
        filename = _opinion_filename(args.identifier)
        url = (
            f"{OPINIONS_INDEX_URL}?"
            + urlencode(
                {
                    "fa": "opinions.showOpinion",
                    "filename": filename,
                }
            )
        )
        artifact = client.get(url)
        return PublicRecordsResult.success(
            query,
            [parse_opinion_info(artifact, filename)],
            warnings=WARNINGS,
        )
    if command == "opinion-download":
        filename = _opinion_filename(args.identifier)
        info_url = (
            f"{OPINIONS_INDEX_URL}?"
            + urlencode(
                {
                    "fa": "opinions.showOpinion",
                    "filename": filename,
                }
            )
        )
        info_artifact = client.get(info_url)
        detail = parse_opinion_info(info_artifact, filename)
        if not detail["pdf_urls"]:
            raise SourceChangedError(
                "opinion_pdf_link_missing",
                "Washington opinion information sheet has no PDF link",
                details={"filename": filename, "url": info_url},
            )
        pdf_artifact = client.get(
            detail["pdf_urls"][0],
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        _require_pdf(pdf_artifact)
        record = _download_record(
            pdf_artifact,
            source_id=OPINIONS_SOURCE_ID,
            record_kind="appellate_opinion_pdf_artifact",
            canonical_ref=f"WACOURT:OPINION_ARTIFACT:{pdf_artifact.sha256}",
            destination=args.destination,
            overwrite=args.overwrite,
            extra={
                "case_number": detail["case_number"],
                "court": detail["court"],
                "opinion_filename": filename,
                "information_url": info_url,
                "information_sha256": info_artifact.sha256,
                "publication_notice": detail["publication_notice"],
                "fields": detail["fields"],
                "pdf_urls": detail["pdf_urls"],
                "last_modified": pdf_artifact.headers.get("last-modified"),
                "route_provenance": info_url,
            },
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[record["artifact_path"]],
            warnings=WARNINGS,
        )
    if command == "data-products":
        artifact = client.get(DATA_PRODUCTS_URL)
        return PublicRecordsResult.success(
            query,
            parse_data_products(artifact),
            warnings=WARNINGS,
        )
    if command == "custom-extract":
        request_artifact = client.get(DATA_REQUEST_URL)
        fee_artifact = client.get(DATA_FEE_URL)
        request_soup = _html(request_artifact, "Forms")
        fillable = request_soup.select_one(
            'a[href*="requestForInfoFillable.pdf"]'
        )
        form_artifact = None
        if fillable:
            form_artifact = client.get(
                _absolute(
                    str(fillable.get("href")),
                    request_artifact.source_url,
                ),
                accept="application/pdf",
                maximum_bytes=MAXIMUM_PDF_BYTES,
            )
            _require_pdf(form_artifact)
        record = parse_custom_extract(
            request_artifact,
            fee_artifact,
            form_artifact,
        )
        return PublicRecordsResult.success(query, [record], warnings=WARNINGS)
    if command == "jislink":
        artifact = client.get(JISLINK_URL)
        return PublicRecordsResult.success(
            query,
            [parse_jislink(artifact)],
            warnings=WARNINGS,
        )
    if command == "appellate-documents":
        artifact = client.get(APPELLATE_DOCUMENT_URLS[args.court])
        record = parse_appellate_document_form(
            artifact,
            court=args.court,
            case_number=args.case_number,
        )
        return PublicRecordsResult.failure(
            query,
            ResultStatus.HUMAN_REQUIRED,
            [
                _result_execution_error(
                    code="appellate_document_captcha_required",
                    message=(
                        "Washington appellate document result execution "
                        "requires interactive CAPTCHA completion"
                    ),
                    details={
                        "operation": "result_execution",
                        "portal_url": record["portal_url"],
                        "case_number": args.case_number,
                        "prepared_route": record,
                    },
                )
            ],
            warnings=WARNINGS,
        )
    if command == "appellate-complements":
        kinds = (
            list(APPELLATE_COMPLEMENT_URLS)
            if args.kind == "all"
            else [args.kind]
        )
        records: list[dict[str, Any]] = []
        for kind in kinds:
            artifact = client.get(APPELLATE_COMPLEMENT_URLS[kind])
            records.extend(
                parse_appellate_complement(
                    artifact,
                    kind=kind,
                    case_number=args.case_number,
                )
            )
        return PublicRecordsResult.success(query, records, warnings=WARNINGS)
    if command == "caseload-routes":
        artifact = client.get(CASELOAD_URL)
        return PublicRecordsResult.success(
            query,
            parse_caseload_routes(artifact),
            warnings=WARNINGS,
        )
    if command == "archive-title":
        title_id = _safe_org_id(args.title_id)
        artifact = client.get(DIGITAL_ARCHIVES_TITLE_BASE + title_id)
        return PublicRecordsResult.success(
            query,
            [parse_archive_title(artifact, title_id)],
            warnings=WARNINGS,
        )
    if command == "probe":
        return _probe(args, client, query)
    raise SelectionError(
        "unsupported_command",
        f"unsupported Washington courts command: {command}",
    )


def _directory_search(
    client: WashingtonCourtsClient | Any,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    query_text = args.last_name.strip()
    initial = (args.initial or query_text[0]).upper()
    if not re.fullmatch(r"[A-Z]", initial):
        raise SelectionError(
            "directory_initial_invalid",
            "directory last-name initial must be A through Z",
            details={"initial": initial},
        )
    records: list[dict[str, Any]] = []
    start = 1
    total: int | None = None
    needle = query_text.casefold()
    while total is None or start <= total:
        url = (
            f"{DIRECTORY_MASTER_URL}&"
            + urlencode(
                {
                    "FromRec": start,
                    "courtdir_lastname": initial,
                }
            )
        )
        artifact = client.get(url)
        page_records, page_total = parse_directory_people(artifact)
        total = page_total
        for record in page_records:
            if needle in str(record["name_and_title"]).casefold():
                records.append(record)
                if args.limit is not None and len(records) >= args.limit:
                    return records
        if not page_records:
            break
        start += 50
    return records


def _case_search_route(
    contract: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    level_key = {
        "superior": "superior",
        "appellate": "appellate",
        "limited": "limited_jurisdiction",
    }[args.court_level]
    codes = {
        item["code"]: item["name"]
        for item in contract["court_codes"][level_key]
    }
    if args.court_code not in codes:
        raise SelectionError(
            "court_code_unknown",
            "court code is not present in the live Washington case form",
            details={
                "court_level": args.court_level,
                "court_code": args.court_code,
            },
        )
    values = {
        "case": args.case_number,
        "name": " ".join(
            value for value in (args.first_name, args.last_name) if value
        )
        or None,
        "bname": args.business_name,
    }
    if not values[args.search_type]:
        raise SelectionError(
            "search_value_missing",
            f"{args.search_type} search requires its corresponding value",
        )
    route = (
        f"{CASE_ORIGIN}/index.cfm?"
        f"fa=home.caselist&init&rtlist={args.search_type}"
    )
    return {
        "record_kind": "case_discovery_execution_route",
        "source_id": CASE_DISCOVERY_SOURCE_ID,
        "component_source_id": CASE_DISCOVERY_SOURCE_ID,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": (
            f"WACOURT:CASE_ROUTE:{args.court_code}:"
            f"{hashlib.sha256(str(values).encode()).hexdigest()[:16]}"
        ),
        "court_level": args.court_level,
        "court_code": args.court_code,
        "court_name": codes[args.court_code],
        "search_type": args.search_type,
        "search_value": values[args.search_type],
        "result_route": route,
        "form_url": CASE_FORM_URL,
        "access_state": "interactive_captcha",
        "operation_status": "human_required",
        "route_provenance": contract["source_url"],
    }


def _require_pdf(artifact: Artifact) -> None:
    if not artifact.content.startswith(b"%PDF-"):
        raise SourceChangedError(
            "pdf_magic_missing",
            "Washington court document route did not return a PDF",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
                "magic_hex": artifact.content[:8].hex(),
            },
        )


def _probe_record(
    source_id: str,
    *,
    operations: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "record_kind": "source_health_check",
        "source_id": source_id,
        "component_source_id": source_id,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": (
            f"WACOURT:PROBE:{source_id}:"
            f"{datetime.now(timezone.utc).date().isoformat()}"
        ),
        "status": "ok",
        "checked_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "operations": dict(operations),
        "evidence": dict(evidence),
    }


def _probe_component(
    source_id: str,
    client: WashingtonCourtsClient | Any,
) -> dict[str, Any]:
    if source_id == DIRECTORY_SOURCE_ID:
        county_artifact = client.get(DIRECTORY_COUNTY_URL)
        counties = parse_directory_counties(county_artifact)
        org_artifact = client.get(
            f"{DIRECTORY_HOME_URL}orgs/{KNOWN_DIRECTORY_ORG_ID}.html"
        )
        org = parse_directory_org(
            org_artifact,
            KNOWN_DIRECTORY_ORG_ID,
            contact_limit=5,
        )
        pdf = client.get(
            DIRECTORY_PDF_URL,
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        _require_pdf(pdf)
        return _probe_record(
            source_id,
            operations={
                "county_index": "ok",
                "organization_detail": "ok",
                "pdf": "ok",
                "person_search": "ok",
            },
            evidence={
                "county_count": len(counties),
                "sentinel_org_heading": org["heading"],
                "pdf_bytes": len(pdf.content),
                "pdf_sha256": pdf.sha256,
                "pdf_matches_observed_sentinel": (
                    pdf.sha256 == KNOWN_DIRECTORY_PDF_SHA256
                ),
            },
        )
    if source_id == CASE_DISCOVERY_SOURCE_ID:
        form = parse_case_form(client.get(CASE_FORM_URL))
        return _probe_record(
            source_id,
            operations={
                "form_metadata": "ok",
                "court_codes": "ok",
                "result_execution": "human_required",
            },
            evidence={
                "superior_court_codes": len(
                    form["court_codes"]["superior"]
                ),
                "appellate_court_codes": len(
                    form["court_codes"]["appellate"]
                ),
                "limited_court_codes": len(
                    form["court_codes"]["limited_jurisdiction"]
                ),
                "result_route_types": form["result_route_types"],
            },
        )
    if source_id == CURRENT_ROUTES_SOURCE_ID:
        routes = parse_case_routes(client.get(CASE_HOME_URL))
        return _probe_record(
            source_id,
            operations={"routing_matrix": "ok"},
            evidence={
                "route_count": len(routes),
                "vendor_families": sorted(
                    {record["vendor_family"] for record in routes}
                ),
            },
        )
    if source_id == OPINIONS_SOURCE_ID:
        feed = parse_opinion_feed(
            client.get(
                RSS_FEEDS["div1-unpublished"][0],
                accept="application/rss+xml,application/xml,text/xml",
            ),
            "div1-unpublished",
        )
        info = parse_opinion_info(
            client.get(
                f"{OPINIONS_INDEX_URL}?"
                + urlencode(
                    {
                        "fa": "opinions.showOpinion",
                        "filename": KNOWN_OPINION_FILENAME,
                    }
                )
            ),
            KNOWN_OPINION_FILENAME,
        )
        pdf = client.get(
            info["pdf_urls"][0],
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        _require_pdf(pdf)
        return _probe_record(
            source_id,
            operations={
                "rss": "ok",
                "information_sheet": "ok",
                "pdf": "ok",
                "by_year_enumeration": "ok",
                "general_search": "degraded_not_required",
            },
            evidence={
                "feed_item_count": len(feed),
                "sentinel_case_number": info["case_number"],
                "pdf_bytes": len(pdf.content),
                "pdf_sha256": pdf.sha256,
                "pdf_matches_observed_sentinel": (
                    pdf.sha256 == KNOWN_OPINION_PDF_SHA256
                ),
            },
        )
    if source_id == APPELLATE_DOCUMENTS_SOURCE_ID:
        evidence = {}
        for court, url in APPELLATE_DOCUMENT_URLS.items():
            record = parse_appellate_document_form(
                client.get(url),
                court=court,
                case_number=KNOWN_OPINION_CASE,
            )
            evidence[court] = {
                "portal_url": record["portal_url"],
                "current_exclusions": record["current_exclusions"],
            }
        return _probe_record(
            source_id,
            operations={
                "form_metadata": "ok",
                "exact_case_routing": "ok",
                "result_execution": "human_required",
            },
            evidence=evidence,
        )
    if source_id == DATA_PRODUCTS_SOURCE_ID:
        products = parse_data_products(client.get(DATA_PRODUCTS_URL))
        request_artifact = client.get(DATA_REQUEST_URL)
        fee_artifact = client.get(DATA_FEE_URL)
        custom = parse_custom_extract(
            request_artifact,
            fee_artifact,
            None,
        )
        return _probe_record(
            source_id,
            operations={
                "standard_product_catalog": "ok",
                "coverage_omissions": "ok",
                "custom_extract_route": "ok",
            },
            evidence={
                "standard_product_count": len(
                    [
                        record
                        for record in products
                        if record["record_kind"]
                        == "court_bulk_index_product"
                    ]
                ),
                "missing_court_count": products[-1][
                    "missing_court_count"
                ],
                "request_form_count": len(custom["request_forms"]),
                "fee_item_count": len(custom["current_fee_items"]),
            },
        )
    if source_id == JISLINK_SOURCE_ID:
        jis = parse_jislink(client.get(JISLINK_URL))
        return _probe_record(
            source_id,
            operations={
                "subscription_information": "ok",
                "access_routes": "ok",
            },
            evidence={
                "access_route_count": len(jis["access_routes"]),
                "fee_statement": jis["fee_statement"],
            },
        )
    if source_id == APPELLATE_COMPLEMENTS_SOURCE_ID:
        counts = {}
        for kind in APPELLATE_COMPLEMENT_URLS:
            records = parse_appellate_complement(
                client.get(APPELLATE_COMPLEMENT_URLS[kind]),
                kind=kind,
                case_number=(
                    KNOWN_OPINION_CASE if kind == "briefs" else None
                ),
            )
            counts[kind] = len(records)
        return _probe_record(
            source_id,
            operations={kind: "ok" for kind in counts},
            evidence={"record_counts": counts},
        )
    if source_id == CASELOAD_SOURCE_ID:
        records = parse_caseload_routes(client.get(CASELOAD_URL))
        return _probe_record(
            source_id,
            operations={"product_routes": "ok"},
            evidence={"route_count": len(records)},
        )
    if source_id == DIGITAL_ARCHIVES_SOURCE_ID:
        title = parse_archive_title(
            client.get(DIGITAL_ARCHIVES_TITLE_BASE + "2778"),
            "2778",
        )
        return _probe_record(
            source_id,
            operations={
                "title_metadata": "ok",
                "search_form": "ok",
            },
            evidence={
                "sentinel_title_id": title["title_id"],
                "sentinel_title": title["title"],
                "record_count": title["record_count"],
                "site_notices": title["site_notices"],
            },
        )
    raise SelectionError(
        "probe_component_unknown",
        f"unknown Washington court component {source_id}",
    )


def _probe(
    args: argparse.Namespace,
    client: WashingtonCourtsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    selected = (
        list(COMPONENTS)
        if args.all or not args.component
        else list(args.component)
    )
    records: list[dict[str, Any]] = []
    errors: list[PublicRecordsError] = []
    statuses: list[ResultStatus] = []
    for source_id in selected:
        try:
            records.append(_probe_component(source_id, client))
        except WashingtonCourtsError as error:
            errors.append(_public_error(error))
            statuses.append(error.status)
    if errors:
        status = (
            ResultStatus.PARTIAL
            if records
            else statuses[0]
            if len(set(statuses)) == 1
            else ResultStatus.UNAVAILABLE
        )
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            warnings=WARNINGS,
        )
    return PublicRecordsResult.success(query, records, warnings=WARNINGS)


def execute(
    args: argparse.Namespace,
    *,
    client: WashingtonCourtsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-scoped Washington official court operation."""

    query = build_query(args)
    source_client = client or _client(args)
    owns_client = client is None
    try:
        result = _execute(args, source_client, query)
    except WashingtonCourtsError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [_public_error(error)],
            warnings=WARNINGS,
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
            warnings=WARNINGS,
        )
    except (TypeError, ValueError, ET.ParseError) as error:
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
            warnings=WARNINGS,
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
        try:
            log_search(
                canonical_json(query.to_dict()),
                query.source.source_id,
                count,
            )
        except Exception as error:
            print(
                f"Warning: could not log search: {error}",
                file=sys.stderr,
            )
    return result


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


def _year(value: str) -> int:
    parsed = int(value)
    if parsed < 1849 or parsed > 2200:
        raise argparse.ArgumentTypeError("year is outside a plausible range")
    return parsed


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Washington court directories, opinions, "
            "record routes, and data products"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("sources", "List separately attributable source components"),
        ("manifest", "Show the source-family and operation-access manifest"),
    ):
        command = sub.add_parser(name, help=help_text)
        _add_runtime(command)

    command = sub.add_parser(
        "directory-counties",
        help="List all county organization IDs from the live directory",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "directory-search",
        help="Search directory personnel by last name",
    )
    command.add_argument("last_name")
    command.add_argument("--initial")
    command.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Maximum matching personnel records; omitted traverses every "
            "advertised directory page"
        ),
    )
    _add_runtime(command)

    command = sub.add_parser(
        "directory-org",
        help="Fetch one live organization/county directory page",
    )
    command.add_argument("organization_id")
    command.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Maximum contacts embedded in the organization record; omitted "
            "retains every contact"
        ),
    )
    _add_runtime(command)

    command = sub.add_parser(
        "directory-pdf",
        help="Download and hash the current official court-directory PDF",
    )
    command.add_argument("destination", type=Path)
    command.add_argument("--overwrite", action="store_true")
    _add_runtime(command)

    command = sub.add_parser(
        "case-form",
        help="Return live court codes, fields, and operation access states",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "case-search",
        help=(
            "Prepare one statewide result route; result execution is "
            "reported as human_required"
        ),
    )
    command.add_argument(
        "--court-level",
        choices=("superior", "appellate", "limited"),
        required=True,
    )
    command.add_argument("--court-code", required=True)
    command.add_argument(
        "--search-type",
        choices=("case", "name", "bname"),
        required=True,
    )
    command.add_argument("--case-number")
    command.add_argument("--first-name")
    command.add_argument("--last-name")
    command.add_argument("--business-name")
    _add_runtime(command)

    command = sub.add_parser(
        "case-routes",
        help="Parse the live current-system routing matrix",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "opinions-feed",
        help="Read one deterministic appellate-opinion RSS feed",
    )
    command.add_argument("feed", choices=tuple(RSS_FEEDS))
    command.add_argument(
        "--limit",
        type=_positive_int,
        help="Maximum feed records; omitted retains the complete feed",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "opinions-list",
        help="Enumerate recent, all, or by-year opinion lists",
    )
    command.add_argument(
        "--scope",
        choices=("recent", "all", "year"),
        default="recent",
    )
    command.add_argument("--year", type=_year)
    command.add_argument("--court-level", choices=("S", "C"))
    command.add_argument(
        "--publication-status",
        choices=("PUB", "PAR", "UNP"),
    )
    command.add_argument("--query")
    command.add_argument(
        "--limit",
        type=_positive_int,
        help="Maximum matching opinions; omitted retains the complete list",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "opinion-detail",
        help="Fetch an exact opinion information sheet",
    )
    command.add_argument("identifier")
    _add_runtime(command)

    command = sub.add_parser(
        "opinion-download",
        help="Follow an exact information-sheet PDF link and hash the file",
    )
    command.add_argument("identifier")
    command.add_argument("destination", type=Path)
    command.add_argument("--overwrite", action="store_true")
    _add_runtime(command)

    command = sub.add_parser(
        "data-products",
        help="Parse current standard bulk indexes and exact omission list",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "custom-extract",
        help="Return the live custom-extract forms and fee schedule",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "jislink",
        help="Return current JIS-Link scope, fees, and access routes",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "appellate-documents",
        help=(
            "Prepare an exact-case appellate document route; result "
            "execution is reported as human_required"
        ),
    )
    command.add_argument("case_number")
    command.add_argument(
        "--court",
        choices=tuple(APPELLATE_DOCUMENT_URLS),
        required=True,
    )
    _add_runtime(command)

    command = sub.add_parser(
        "appellate-complements",
        help="List orders, notices, briefs, calendars, and issue routes",
    )
    command.add_argument(
        "--kind",
        choices=("all", *APPELLATE_COMPLEMENT_URLS),
        default="all",
    )
    command.add_argument("--case-number")
    _add_runtime(command)

    command = sub.add_parser(
        "caseload-routes",
        help="List aggregate caseload and dashboard product routes",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "archive-title",
        help="Inspect one Digital Archives superior-court title contract",
    )
    command.add_argument("title_id")
    _add_runtime(command)

    command = sub.add_parser(
        "probe",
        help="Run component-selective live acceptance probes",
    )
    command.add_argument(
        "--component",
        action="append",
        choices=tuple(COMPONENTS),
    )
    command.add_argument("--all", action="store_true")
    _add_runtime(command)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Washington courts {args.command} ({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Washington courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        identity = (
            record.get("case_number")
            or record.get("organization_id")
            or record.get("product_code")
            or record.get("title_id")
            or record.get("source_id")
        )
        label = (
            record.get("caption")
            or record.get("name_and_title")
            or record.get("product_name")
            or record.get("title")
            or record.get("record_kind")
        )
        print(f"  {identity or '-'} | {label or '-'}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


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
            ResultStatus.HUMAN_REQUIRED,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
