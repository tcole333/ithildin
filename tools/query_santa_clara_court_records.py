#!/usr/bin/env python3
"""Query Santa Clara Superior Court's open publication complements.

The interactive public portal currently presents reCAPTCHA on case and
calendar searches.  Separately, the court publishes department-level
tentative-ruling PDFs and official civil and criminal case-index product
descriptions with request artifacts.  This adapter keeps those components
distinct and queryable.

Examples:
    uv run python tools/query_santa_clara_court_records.py sources --json
    uv run python tools/query_santa_clara_court_records.py departments --json
    uv run python tools/query_santa_clara_court_records.py rulings \
        --department 1 --output /tmp/sc-rulings.json
    uv run python tools/query_santa_clara_court_records.py products --json
    uv run python tools/query_santa_clara_court_records.py download \
        https://santaclara.courts.ca.gov/system/files/tentative-ruling/dept-1-tues.pdf \
        /tmp/dept-1-tues.pdf --json
    uv run python tools/query_santa_clara_court_records.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


STATE_CODE = "CA"
COUNTY_GEOID = "06085"
COURT_ID = "ca-santa-clara-superior-court"
COURT_NAME = "Superior Court of California, County of Santa Clara"
BASE_URL = "https://santaclara.courts.ca.gov"
PORTAL_URL = "https://portal.scscourt.org/"
PORTAL_SEARCH_URL = f"{PORTAL_URL}search"
TENTATIVE_URL = f"{BASE_URL}/online-services/tentative-rulings"
CASE_INFO_URL = f"{BASE_URL}/online-services/case-information-online"
CIVIL_PRODUCT_URL = (
    f"{CASE_INFO_URL}/requesting-cd-civil-case-index"
)
CRIMINAL_PRODUCT_URL = (
    f"{CASE_INFO_URL}/criminal-case-index-cd-request"
)
REQUEST_FORM_URL = f"{BASE_URL}/system/files/forms/ad-1000.pdf"
TERMS_URL = f"{BASE_URL}/system/files/general/cdterms.pdf"
CRIMINAL_INFO_URL = (
    f"{BASE_URL}/system/files/general/criminalindexsearchinfo.pdf"
)

FAMILY_SOURCE_ID = "us-ca-santa-clara-court-publications"
TENTATIVE_SOURCE_ID = "us-ca-santa-clara-tentative-rulings"
CIVIL_INDEX_SOURCE_ID = "us-ca-santa-clara-civil-case-index-product"
CRIMINAL_INDEX_SOURCE_ID = (
    "us-ca-santa-clara-criminal-case-index-product"
)
PORTAL_SOURCE_ID = "us-ca-santa-clara-public-case-portal"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
DEPARTMENT_HEADERS = (
    "Department",
    "Judge",
    "Rulings",
    "Scheduled Hearings",
)
EXPECTED_DEPARTMENTS = frozenset({1, 2, 6, 10, 11, 12, 13, 16, 19, 22})
_DEPARTMENT_RE = re.compile(r"\bDept(?:artment)?\.?\s*(\d+)\b", re.I)

SOURCE_METADATA = {
    FAMILY_SOURCE_ID: SourceMetadata(
        source_id=FAMILY_SOURCE_ID,
        name="Santa Clara Superior Court Public Record Publications",
        source_role="official_county_court_publication_family",
        base_url=CASE_INFO_URL,
        dataset_id="santa-clara-court-publications",
        metadata={
            "authority": COURT_NAME,
            "county_geoid": COUNTY_GEOID,
            "component_source_ids": [
                TENTATIVE_SOURCE_ID,
                CIVIL_INDEX_SOURCE_ID,
                CRIMINAL_INDEX_SOURCE_ID,
                PORTAL_SOURCE_ID,
            ],
        },
    ),
    TENTATIVE_SOURCE_ID: SourceMetadata(
        source_id=TENTATIVE_SOURCE_ID,
        name="Santa Clara Superior Court Tentative Rulings",
        source_role="official_tentative_ruling_index_and_documents",
        base_url=TENTATIVE_URL,
        dataset_id="santa-clara-tentative-rulings",
        metadata={
            "authority": COURT_NAME,
            "county_geoid": COUNTY_GEOID,
            "authentication": "none",
            "publication_state": "current_until_replaced",
            "observed_departments": sorted(EXPECTED_DEPARTMENTS),
        },
    ),
    CIVIL_INDEX_SOURCE_ID: SourceMetadata(
        source_id=CIVIL_INDEX_SOURCE_ID,
        name="Santa Clara Civil Case Index Product",
        source_role="official_quarterly_civil_case_index_product",
        base_url=CIVIL_PRODUCT_URL,
        dataset_id="santa-clara-civil-case-index",
        metadata={
            "authority": COURT_NAME,
            "county_geoid": COUNTY_GEOID,
            "delivery_format": "tab_delimited_ascii",
            "update_cadence": "quarterly",
            "acquisition": "court_request",
        },
    ),
    CRIMINAL_INDEX_SOURCE_ID: SourceMetadata(
        source_id=CRIMINAL_INDEX_SOURCE_ID,
        name="Santa Clara Criminal Case Index Product",
        source_role="official_quarterly_criminal_case_index_product",
        base_url=CRIMINAL_PRODUCT_URL,
        dataset_id="santa-clara-criminal-case-index",
        metadata={
            "authority": COURT_NAME,
            "county_geoid": COUNTY_GEOID,
            "delivery_format": "tab_delimited_ascii",
            "acquisition": "court_request",
        },
    ),
    PORTAL_SOURCE_ID: SourceMetadata(
        source_id=PORTAL_SOURCE_ID,
        name="Santa Clara Superior Court Public Portal",
        source_role="official_interactive_case_and_calendar_portal",
        base_url=PORTAL_URL,
        dataset_id="santa-clara-public-portal",
        metadata={
            "authority": COURT_NAME,
            "county_geoid": COUNTY_GEOID,
            "authentication": "none",
            "observed_operation_states": {
                "case_number_search": "recaptcha",
                "party_search": "recaptcha",
                "business_search": "recaptcha",
                "filing_date_search": "recaptcha",
                "calendar_selection": "recaptcha",
            },
        },
    ),
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Santa Clara County",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
)

SOURCE_WARNINGS = (
    "Tentative rulings are current court publications that remain available until replaced; retain fetched artifacts for historical use.",
    "The civil and criminal case-index products are reference datasets rather than the official court record.",
    "The interactive public portal's reCAPTCHA observation applies to the specific search and calendar forms observed there, not to the court's open publication pages or PDFs.",
)

_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


class SantaClaraCourtError(RuntimeError):
    """One query, transport, access, or source-schema error."""

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


class SantaClaraSelectionError(SantaClaraCourtError):
    """The caller selected an unknown source-native value."""

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


class SantaClaraSourceChangedError(SantaClaraCourtError):
    """An official page or artifact no longer has its verified structure."""

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
class DepartmentDirectory:
    """Current department publication routes from the official index."""

    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class RulingArtifactIndex:
    """Current PDF links published on one department page."""

    department: int
    artifacts: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ProductPage:
    """Validated source page and its official request artifacts."""

    product_kind: str
    source_id: str
    source_url: str
    artifacts: tuple[Mapping[str, Any], ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class PDFArtifact:
    """Validated official PDF bytes."""

    source_url: str
    content: bytes
    media_type: str
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _official_url(value: str, *, require_pdf: bool = False) -> str:
    url = urljoin(BASE_URL, value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "santaclara.courts.ca.gov":
        raise SantaClaraSelectionError(
            "invalid_official_url",
            "URL must identify an official santaclara.courts.ca.gov resource",
            details={"url": value},
        )
    if require_pdf and (
        not parsed.path.startswith("/system/files/")
        or not parsed.path.casefold().endswith(".pdf")
    ):
        raise SantaClaraSelectionError(
            "invalid_pdf_url",
            "PDF URL must identify an official court system/files artifact",
            details={"url": value},
        )
    return url


def _schema_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _expected_table(soup: BeautifulSoup) -> Any:
    observed: list[tuple[str, ...]] = []
    for table in soup.select("main table"):
        headers = tuple(
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in table.select("thead th")
        )
        observed.append(headers)
        if headers == DEPARTMENT_HEADERS:
            return table
    raise SantaClaraSourceChangedError(
        "department_table_missing",
        "Santa Clara tentative-ruling page lacks its department table",
        details={
            "expected_headers": list(DEPARTMENT_HEADERS),
            "observed_headers": [list(value) for value in observed],
        },
    )


def parse_departments(
    html_text: str,
    *,
    source_url: str = TENTATIVE_URL,
    require_complete: bool = True,
) -> DepartmentDirectory:
    """Parse the official tentative-ruling department directory."""

    soup = BeautifulSoup(html_text, "html.parser")
    table = _expected_table(soup)
    schema = _schema_fingerprint(
        {
            "headers": DEPARTMENT_HEADERS,
            "table_classes": sorted(table.get("class", [])),
        }
    )
    records: list[Mapping[str, Any]] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(DEPARTMENT_HEADERS):
            raise SantaClaraSourceChangedError(
                "department_row_width_changed",
                "Santa Clara department row does not have four columns",
                details={"observed_columns": len(cells)},
            )
        department_text = _text(cells[0].get_text(" ", strip=True))
        match = (
            _DEPARTMENT_RE.search(department_text)
            if department_text is not None
            else None
        )
        judge_link = cells[1].find("a", href=True)
        if match is None or judge_link is None:
            raise SantaClaraSourceChangedError(
                "department_identity_missing",
                "Santa Clara department row lacks department or detail route",
            )
        department = int(match.group(1))
        page_url = _official_url(str(judge_link["href"]))
        canonical_ref = (
            f"SCC-TENTATIVE-DEPARTMENT:{department}"
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": TENTATIVE_SOURCE_ID,
                "record_kind": "tentative_ruling_department",
                "department": department,
                "judge": _text(judge_link.get_text(" ", strip=True)),
                "ruling_calendar": _text(
                    cells[2].get_text(" ", strip=True)
                ),
                "scheduled_hearings": _text(
                    cells[3].get_text(" ", strip=True)
                ),
                "department_url": page_url,
                "source_url": source_url,
                "court": {
                    "court_id": COURT_ID,
                    "name": COURT_NAME,
                    "state_code": STATE_CODE,
                    "county_fips": COUNTY_GEOID,
                },
                "provenance": {
                    "source_id": TENTATIVE_SOURCE_ID,
                    "source_url": source_url,
                    "response_schema_fingerprint": schema,
                },
            }
        )
    departments = [int(record["department"]) for record in records]
    if len(departments) != len(set(departments)):
        raise SantaClaraSourceChangedError(
            "duplicate_departments",
            "Santa Clara tentative-ruling directory repeats a department",
        )
    if require_complete and set(departments) != EXPECTED_DEPARTMENTS:
        raise SantaClaraSourceChangedError(
            "department_coverage_changed",
            "Santa Clara tentative-ruling department coverage changed",
            details={
                "expected": sorted(EXPECTED_DEPARTMENTS),
                "observed": sorted(departments),
            },
        )
    return DepartmentDirectory(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=schema,
    )


def parse_ruling_artifacts(
    html_text: str,
    *,
    department: int,
    source_url: str,
) -> RulingArtifactIndex:
    """Parse the currently linked tentative-ruling PDFs for one department."""

    soup = BeautifulSoup(html_text, "html.parser")
    heading = soup.select_one("main h1")
    heading_text = _text(heading.get_text(" ", strip=True)) if heading else None
    if (
        heading_text is None
        or str(department) not in heading_text
        or "Tentative Rulings" not in heading_text
    ):
        raise SantaClaraSourceChangedError(
            "department_heading_changed",
            "Santa Clara department page lacks its expected heading",
            details={"department": department, "heading": heading_text},
        )
    artifacts: list[Mapping[str, Any]] = []
    seen_urls: set[str] = set()
    for link in soup.select("main a[href]"):
        href = str(link.get("href"))
        resolved = urljoin(source_url, href)
        parsed = urlparse(resolved)
        if (
            parsed.hostname != "santaclara.courts.ca.gov"
            or not parsed.path.startswith("/system/files/tentative-ruling/")
            or not parsed.path.casefold().endswith(".pdf")
        ):
            continue
        pdf_url = _official_url(resolved, require_pdf=True)
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)
        label = _text(link.get_text(" ", strip=True))
        artifact_id = hashlib.sha256(pdf_url.encode("utf-8")).hexdigest()[:24]
        canonical_ref = (
            f"SCC-TENTATIVE-PDF:{department}:{artifact_id}"
        )
        artifacts.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": TENTATIVE_SOURCE_ID,
                "record_kind": "document_artifact",
                "document_type": "tentative_rulings",
                "department": department,
                "label": label,
                "source_url": pdf_url,
                "index_url": source_url,
                "mime_type": "application/pdf",
                "publication_state": "current_until_replaced",
                "access_state": "public",
            }
        )
    schema = _schema_fingerprint(
        {
            "heading": heading_text,
            "artifact_path": "/system/files/tentative-ruling/*.pdf",
            "artifact_count": len(artifacts),
        }
    )
    return RulingArtifactIndex(
        department=department,
        artifacts=tuple(artifacts),
        source_url=source_url,
        schema_fingerprint=schema,
    )


PRODUCT_DEFINITIONS = {
    "civil": {
        "source_id": CIVIL_INDEX_SOURCE_ID,
        "url": CIVIL_PRODUCT_URL,
        "title": "Civil Case Index",
        "required_markers": (
            "Civil Case Index (CD-ROM)",
            "tab delimited ASCII text format",
            "last complete quarter",
            "data dictionary",
        ),
        "fields": (
            "case_number",
            "case_title",
            "file_date",
            "disposition_date",
            "status",
            "case_type",
            "associated_cases",
            "party_name_and_type",
            "counsel_name_and_address",
            "motion_document_order_information",
            "scheduled_event_information",
        ),
        "cadence": "quarterly",
    },
    "criminal": {
        "source_id": CRIMINAL_INDEX_SOURCE_ID,
        "url": CRIMINAL_PRODUCT_URL,
        "title": "Criminal Case Index",
        "required_markers": (
            "Criminal Case Index CD Request",
            "tab delimited ASCII text format",
            "Case number",
            "Filing date",
            "Party name",
        ),
        "fields": (
            "case_number",
            "filing_date",
            "party_name",
        ),
        "cadence": "source_information_sheet",
    },
}


def parse_product_page(
    html_text: str,
    *,
    product_kind: str,
    source_url: str | None = None,
) -> ProductPage:
    """Validate one case-index product page and retain request artifacts."""

    if product_kind not in PRODUCT_DEFINITIONS:
        raise SantaClaraSelectionError(
            "unknown_product",
            f"unknown Santa Clara case-index product: {product_kind!r}",
        )
    definition = PRODUCT_DEFINITIONS[product_kind]
    page_url = source_url or str(definition["url"])
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.select_one("main")
    main_text = _text(main.get_text(" ", strip=True)) if main else None
    if main_text is None:
        raise SantaClaraSourceChangedError(
            "product_content_missing",
            "Santa Clara case-index product page lacks main content",
            details={"product_kind": product_kind},
        )
    missing = [
        marker
        for marker in definition["required_markers"]
        if str(marker).casefold() not in main_text.casefold()
    ]
    if missing:
        raise SantaClaraSourceChangedError(
            "product_markers_changed",
            "Santa Clara case-index product description changed",
            details={"product_kind": product_kind, "missing": missing},
        )
    artifact_urls = {
        REQUEST_FORM_URL: "case_index_request_form",
        TERMS_URL: "case_index_terms",
    }
    if product_kind == "criminal":
        artifact_urls[CRIMINAL_INFO_URL] = "criminal_index_information_sheet"
    available_links = {
        _official_url(str(link["href"]), require_pdf=True)
        for link in main.select("a[href]")
        if urlparse(urljoin(page_url, str(link["href"]))).hostname
        == "santaclara.courts.ca.gov"
        and urlparse(urljoin(page_url, str(link["href"]))).path.casefold().endswith(
            ".pdf"
        )
    }
    missing_artifacts = sorted(set(artifact_urls) - available_links)
    if missing_artifacts:
        raise SantaClaraSourceChangedError(
            "product_artifacts_changed",
            "Santa Clara case-index product page lacks an official artifact",
            details={
                "product_kind": product_kind,
                "missing_urls": missing_artifacts,
            },
        )
    artifacts = tuple(
        {
            "source_id": str(definition["source_id"]),
            "record_kind": "document_artifact",
            "document_type": document_type,
            "source_url": artifact_url,
            "mime_type": "application/pdf",
            "access_state": "public",
        }
        for artifact_url, document_type in artifact_urls.items()
    )
    schema = _schema_fingerprint(
        {
            "product_kind": product_kind,
            "required_markers": definition["required_markers"],
            "artifact_types": sorted(artifact_urls.values()),
        }
    )
    return ProductPage(
        product_kind=product_kind,
        source_id=str(definition["source_id"]),
        source_url=page_url,
        artifacts=artifacts,
        schema_fingerprint=schema,
    )


def _product_record(page: ProductPage) -> dict[str, Any]:
    definition = PRODUCT_DEFINITIONS[page.product_kind]
    canonical_ref = (
        f"SCC-CASE-INDEX-PRODUCT:{page.product_kind}"
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": page.source_id,
        "record_kind": "court_data_product",
        "product_kind": page.product_kind,
        "name": definition["title"],
        "source_url": page.source_url,
        "delivery_format": "tab_delimited_ascii",
        "included_fields": list(definition["fields"]),
        "update_cadence": definition["cadence"],
        "acquisition": {
            "route": "court_request",
            "request_form_url": REQUEST_FORM_URL,
            "fee_basis": "actual_production_and_administrative_cost",
            "delivery": "cd_rom",
            "source_stated_request_frequency": "once_per_calendar_quarter",
        },
        "artifacts": list(page.artifacts),
        "portal_complement": {
            "source_id": PORTAL_SOURCE_ID,
            "url": PORTAL_URL,
            "observed_search_state": "recaptcha",
        },
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "state_code": STATE_CODE,
            "county_fips": COUNTY_GEOID,
        },
        "provenance": {
            "source_id": page.source_id,
            "source_url": page.source_url,
            "response_schema_fingerprint": page.schema_fingerprint,
        },
    }


class SantaClaraCourtClient:
    """Paced, retrying client for the official HTML and PDF publications."""

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
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/pdf;q=0.9,*/*;q=0.5"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def _get(self, url: str) -> Any:
        response = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise SantaClaraCourtError(
                        "transport_error",
                        f"Santa Clara court request failed: {error}",
                        retryable=True,
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 200:
                return response
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise SantaClaraCourtError(
                    "rate_limited",
                    "Santa Clara court publication returned HTTP 429",
                    status=ResultStatus.RATE_LIMITED,
                    category="transport",
                    retryable=True,
                )
            if status_code in {401, 403}:
                raise SantaClaraCourtError(
                    "access_response",
                    f"Santa Clara court publication returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                )
            raise SantaClaraCourtError(
                "http_error",
                f"Santa Clara court publication returned HTTP {status_code}",
                category="transport",
                details={"status_code": status_code, "url": url},
            )
        raise AssertionError("Santa Clara request ended without a response")

    def text(self, url: str) -> tuple[str, str]:
        safe_url = _official_url(url)
        response = self._get(safe_url)
        final_url = _official_url(str(getattr(response, "url", safe_url)))
        text = str(response.text)
        lowered = text.casefold()
        if any(marker in lowered for marker in _CHALLENGE_MARKERS):
            raise SantaClaraCourtError(
                "human_verification",
                "Santa Clara publication returned a verification page",
                status=ResultStatus.HUMAN_REQUIRED,
                category="access",
            )
        return text, final_url

    def departments(self) -> DepartmentDirectory:
        html_text, source_url = self.text(TENTATIVE_URL)
        return parse_departments(
            html_text,
            source_url=source_url,
            require_complete=True,
        )

    def ruling_artifacts(
        self,
        department_record: Mapping[str, Any],
    ) -> RulingArtifactIndex:
        page_url = str(department_record["department_url"])
        html_text, source_url = self.text(page_url)
        return parse_ruling_artifacts(
            html_text,
            department=int(department_record["department"]),
            source_url=source_url,
        )

    def product(self, product_kind: str) -> ProductPage:
        definition = PRODUCT_DEFINITIONS[product_kind]
        html_text, source_url = self.text(str(definition["url"]))
        return parse_product_page(
            html_text,
            product_kind=product_kind,
            source_url=source_url,
        )

    def pdf(self, url: str) -> PDFArtifact:
        safe_url = _official_url(url, require_pdf=True)
        response = self._get(safe_url)
        final_url = _official_url(
            str(getattr(response, "url", safe_url)),
            require_pdf=True,
        )
        content = bytes(response.content)
        media_type = str(
            getattr(response, "headers", {}).get(
                "Content-Type",
                "application/pdf",
            )
        ).split(";", 1)[0].strip().casefold()
        if not content.startswith(b"%PDF-"):
            raise SantaClaraSourceChangedError(
                "pdf_signature_missing",
                "Santa Clara court artifact is not a PDF",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size": len(content),
                },
            )
        return PDFArtifact(
            source_url=final_url,
            content=content,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _source_for_args(args: argparse.Namespace) -> SourceMetadata:
    if args.command in {"departments", "rulings"}:
        return SOURCE_METADATA[TENTATIVE_SOURCE_ID]
    if args.command == "products":
        kind = getattr(args, "kind", "all")
        if kind == "civil":
            return SOURCE_METADATA[CIVIL_INDEX_SOURCE_ID]
        if kind == "criminal":
            return SOURCE_METADATA[CRIMINAL_INDEX_SOURCE_ID]
    if args.command == "download":
        url = str(getattr(args, "url", ""))
        if "/tentative-ruling/" in url:
            return SOURCE_METADATA[TENTATIVE_SOURCE_ID]
    return SOURCE_METADATA[FAMILY_SOURCE_ID]


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for field_name in ("department", "kind", "url", "destination"):
        value = getattr(args, field_name, None)
        if value is not None:
            parameters[field_name] = str(value) if isinstance(value, Path) else value
    return PublicRecordsQuery(
        source=_source_for_args(args),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
        ),
    )


def _sources() -> list[dict[str, Any]]:
    return [
        {
            "source_id": TENTATIVE_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[TENTATIVE_SOURCE_ID].name,
            "official_url": TENTATIVE_URL,
            "operations": ["departments", "rulings", "download"],
            "contribution": (
                "Current department assignments, schedules, and court-hosted "
                "tentative-ruling PDFs"
            ),
        },
        {
            "source_id": CIVIL_INDEX_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[CIVIL_INDEX_SOURCE_ID].name,
            "official_url": CIVIL_PRODUCT_URL,
            "operations": ["products", "download"],
            "contribution": (
                "Quarterly tab-delimited civil case, party, counsel, "
                "document/order, ruling, relationship, and event index fields"
            ),
        },
        {
            "source_id": CRIMINAL_INDEX_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[CRIMINAL_INDEX_SOURCE_ID].name,
            "official_url": CRIMINAL_PRODUCT_URL,
            "operations": ["products", "download"],
            "contribution": (
                "Tab-delimited criminal case number, filing date, and party "
                "name index fields"
            ),
        },
        {
            "source_id": PORTAL_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[PORTAL_SOURCE_ID].name,
            "official_url": PORTAL_URL,
            "operations": [
                {
                    "name": "case_number_search",
                    "observed_state": "recaptcha",
                },
                {
                    "name": "party_search",
                    "observed_state": "recaptcha",
                },
                {
                    "name": "business_search",
                    "observed_state": "recaptcha",
                },
                {
                    "name": "filing_date_search",
                    "observed_state": "recaptcha",
                },
                {
                    "name": "calendar_selection",
                    "observed_state": "recaptcha",
                },
            ],
            "open_alternatives": [
                TENTATIVE_SOURCE_ID,
                CIVIL_INDEX_SOURCE_ID,
                CRIMINAL_INDEX_SOURCE_ID,
            ],
        },
    ]


def _failure(
    query: PublicRecordsQuery,
    error: SantaClaraCourtError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _department(
    directory: DepartmentDirectory,
    department: int,
) -> Mapping[str, Any]:
    match = next(
        (
            record
            for record in directory.records
            if int(record["department"]) == department
        ),
        None,
    )
    if match is None:
        raise SantaClaraSelectionError(
            "unknown_department",
            f"department {department} does not publish through this index",
            details={
                "available_departments": [
                    record["department"] for record in directory.records
                ]
            },
        )
    return match


def execute(
    args: argparse.Namespace,
    *,
    client: SantaClaraCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(args)
    own_client = client is None
    source_client = client or SantaClaraCourtClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _sources(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "departments":
            directory = source_client.departments()
            result = PublicRecordsResult.success(
                query,
                directory.records,
                raw_artifact_refs=[directory.source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "rulings":
            directory = source_client.departments()
            selected = _department(directory, args.department)
            index = source_client.ruling_artifacts(selected)
            result = PublicRecordsResult.success(
                query,
                index.artifacts,
                raw_artifact_refs=[
                    directory.source_url,
                    index.source_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "products":
            product_kinds = (
                tuple(PRODUCT_DEFINITIONS)
                if args.kind == "all"
                else (args.kind,)
            )
            pages = tuple(
                source_client.product(kind) for kind in product_kinds
            )
            result = PublicRecordsResult.success(
                query,
                [_product_record(page) for page in pages],
                raw_artifact_refs=[page.source_url for page in pages],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            pdf = source_client.pdf(args.url)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            args.destination.write_bytes(pdf.content)
            record = {
                "canonical_ref": f"SCC-PDF:{pdf.sha256}",
                "evidence_ref": f"SCC-PDF:{pdf.sha256}",
                "source_id": query.source.source_id,
                "record_kind": "document_artifact",
                "source_url": pdf.source_url,
                "local_path": str(args.destination),
                "mime_type": pdf.media_type,
                "size_bytes": len(pdf.content),
                "sha256": pdf.sha256,
                "access_state": "public",
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[str(args.destination)],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            directory = source_client.departments()
            department = _department(directory, 1)
            ruling_index = source_client.ruling_artifacts(department)
            if not ruling_index.artifacts:
                raise SantaClaraSourceChangedError(
                    "probe_ruling_artifact_missing",
                    "Santa Clara Department 1 has no linked ruling artifact",
                )
            pdf = source_client.pdf(
                str(ruling_index.artifacts[0]["source_url"])
            )
            civil = source_client.product("civil")
            criminal = source_client.product("criminal")
            record = {
                "source_id": FAMILY_SOURCE_ID,
                "record_kind": "source_probe",
                "department_count": len(directory.records),
                "departments": [
                    record["department"] for record in directory.records
                ],
                "department_schema_fingerprint": (
                    directory.schema_fingerprint
                ),
                "ruling_artifact_count": len(ruling_index.artifacts),
                "ruling_pdf": {
                    "source_url": pdf.source_url,
                    "sha256": pdf.sha256,
                    "size_bytes": len(pdf.content),
                    "media_type": pdf.media_type,
                },
                "products": [
                    {
                        "source_id": page.source_id,
                        "product_kind": page.product_kind,
                        "artifact_count": len(page.artifacts),
                        "schema_fingerprint": page.schema_fingerprint,
                    }
                    for page in (civil, criminal)
                ],
                "portal_operation_observation": {
                    "source_id": PORTAL_SOURCE_ID,
                    "search_and_calendar_forms": "recaptcha",
                    "alternative_source_ids": [
                        TENTATIVE_SOURCE_ID,
                        CIVIL_INDEX_SOURCE_ID,
                        CRIMINAL_INDEX_SOURCE_ID,
                    ],
                },
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[
                    directory.source_url,
                    ruling_index.source_url,
                    pdf.source_url,
                    civil.source_url,
                    criminal.source_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise SantaClaraSelectionError(
                "unknown_command",
                f"unknown Santa Clara court command: {args.command}",
            )
    except SantaClaraCourtError as error:
        result = _failure(query, error)
    finally:
        if own_client:
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
        log_search(
            canonical_json(result.query.to_dict()),
            result.query.source.source_id,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Santa Clara court tentative rulings and case-index products"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe the publication family and portal alternatives",
    )
    _add_runtime_and_output(sources)

    departments = subparsers.add_parser(
        "departments",
        help="List tentative-ruling departments and publication routes",
    )
    _add_runtime_and_output(departments)

    rulings = subparsers.add_parser(
        "rulings",
        help="List current tentative-ruling PDFs for one department",
    )
    rulings.add_argument("--department", type=int, required=True)
    _add_runtime_and_output(rulings)

    products = subparsers.add_parser(
        "products",
        help="Describe official civil and criminal case-index products",
    )
    products.add_argument(
        "--kind",
        choices=("all", "civil", "criminal"),
        default="all",
    )
    _add_runtime_and_output(products)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one official court PDF",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify directory, ruling PDF, and both product pages",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Santa Clara court {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Santa Clara court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('department') or record.get('product_kind') or record.get('record_kind') or '?'} | "
            f"{record.get('source_url') or record.get('official_url') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
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
