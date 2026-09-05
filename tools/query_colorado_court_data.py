#!/usr/bin/env python3
"""Discover Colorado Judicial court-data reports and request workflows.

The Colorado Judicial Branch publishes several useful alternatives to a direct
case-management-system bulk feed:

* annual statistical report PDFs and current Power BI reports;
* case/party-without-representation report PDFs;
* the public eviction-filings Power BI dashboard; and
* CJD 05-01 plus Addendum A for compiled or aggregate data requests.

Dashboard records are discovery records.  The adapter downloads only artifacts
whose official catalog entry resolves to a PDF.

Examples:
    uv run python tools/query_colorado_court_data.py catalog --json
    uv run python tools/query_colorado_court_data.py search eviction \
        --output /tmp/colorado-court-data.json
    uv run python tools/query_colorado_court_data.py download \
        annual-statistical-report-fy-2024 \
        --destination /tmp/FY2024-Annual-Statistical-Report.pdf
    uv run python tools/query_colorado_court_data.py probe --json
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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
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
        sha256_fingerprint,
    )
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
        sha256_fingerprint,
    )
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-co-judicial-data-reports"
COMPILED_REQUEST_SOURCE_ID = (
    "us-co-judicial-compiled-aggregate-data-requests"
)
ANNUAL_REPORTS_SOURCE_ID = "us-co-judicial-annual-statistical-reports"
SELF_REPRESENTED_SOURCE_ID = (
    "us-co-judicial-case-parties-without-representation"
)
EVICTION_DASHBOARD_SOURCE_ID = (
    "us-co-judicial-eviction-filings-dashboard"
)
COMPONENT_SOURCE_IDS = (
    COMPILED_REQUEST_SOURCE_ID,
    ANNUAL_REPORTS_SOURCE_ID,
    SELF_REPRESENTED_SOURCE_ID,
    EVICTION_DASHBOARD_SOURCE_ID,
)

BASE_URL = "https://www.coloradojudicial.gov"
ANNUAL_REPORTS_URL = f"{BASE_URL}/annual-statistical-reports?language=en"
SELF_REPRESENTED_URL = (
    f"{BASE_URL}/case-parties-without-representation"
)
EVICTION_DASHBOARD_URL = f"{BASE_URL}/eviction-filings?language=en"
CJD_INDEX_URL = (
    f"{BASE_URL}/supreme-court/chief-justice-directives"
    "?search_api_fulltext=&search_api_fulltext_1=05-01"
)
RESEARCH_DATA_URL = f"{BASE_URL}/court-services/research-and-data"
ACCESS_GUIDE_URL = f"{BASE_URL}/access-guide-public-records"
ADDENDUM_A_URL = f"{BASE_URL}/media/4320"
DATA_REQUEST_EMAIL = "courtdatarequests@judicial.state.co.us"
DENVER_DATA_REQUEST_EMAIL = "coradatarequests@denvercountycourt.org"

TIMEOUT = 45.0
REQUEST_DELAY = 0.2
MAX_RETRIES = 2
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

ADDENDUM_ARTIFACT_ID = (
    "addendum-a-compiled-aggregate-data-request"
)
WORKFLOW_ARTIFACT_ID = "compiled-aggregate-data-request-workflow"
EVICTION_ARTIFACT_ID = "eviction-filings-dashboard"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Colorado Judicial Data Reports and Request Workflows",
    source_role="statewide_court_data_publications_and_request_directory",
    base_url=ANNUAL_REPORTS_URL,
    dataset_id="colorado-judicial-data-reports",
    metadata={
        "authority": "Colorado Judicial Branch",
        "state_code": "CO",
        "state_geoid": "08",
        "component_source_ids": COMPONENT_SOURCE_IDS,
        "catalog_pagination": "unpaginated_official_landing_pages",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="08",
    name="Colorado",
    state_code="CO",
    metadata={"jurisdiction_level": "state"},
)

SOURCE_WARNINGS = (
    (
        "Each record identifies the specific Colorado Judicial publication or "
        "request-program component that supplied it."
    ),
    (
        "Power BI records preserve the public dashboard link; this adapter "
        "does not claim a dashboard export route."
    ),
    (
        "The compiled/aggregate request program is distinct from direct bulk "
        "distribution of the court case-management system."
    ),
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "record_fields": [
            "adapter_source_id",
            "source_id",
            "component_source_id",
            "record_kind",
            "artifact_kind",
            "artifact_id",
            "canonical_ref",
            "native_document_id",
            "title",
            "report_type",
            "fiscal_year",
            "effective_date",
            "format",
            "access_mode",
            "downloadable_by_adapter",
            "landing_page_url",
            "landing_url",
            "source_url",
            "artifact_url",
            "dashboard_url",
            "description",
            "coverage",
            "metadata",
        ],
        "commands": ["catalog", "list", "search", "download", "probe"],
    }
)

_COLORADO_HOSTS = frozenset(
    {"coloradojudicial.gov", "www.coloradojudicial.gov"}
)
_POWER_BI_HOST = "app.powerbigov.us"
_FY_PATTERN = re.compile(r"\bFY\s*(20\d{2})\b", re.IGNORECASE)
_EFFECTIVE_PATTERN = re.compile(
    r"\bAmended,\s*Effective\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
    re.IGNORECASE,
)


class ColoradoCourtDataError(RuntimeError):
    """Base error for official Colorado court-data discovery and retrieval."""


class ColoradoCourtDataSourceChanged(ColoradoCourtDataError):
    """An official source no longer matches the verified catalog shape."""


class ColoradoCourtDataNotFound(ColoradoCourtDataError):
    """An artifact selector is not a member of the live catalog."""


class ColoradoCourtDataNotDownloadable(ColoradoCourtDataError):
    """A live catalog record is discoverable but has no verified download."""


class ColoradoCourtDataTransportError(ColoradoCourtDataError):
    """The source remained unreachable after bounded retries."""


class ColoradoCourtDataRateLimited(ColoradoCourtDataError):
    """The source returned HTTP 429 after bounded retries."""


class ColoradoCourtDataHTTPError(ColoradoCourtDataError):
    """The source returned a non-success HTTP response."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(
            f"Colorado Judicial source returned HTTP {status_code} for {url}"
        )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", text).strip()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not normalized:
        raise ColoradoCourtDataSourceChanged(
            "official catalog supplied an empty artifact title"
        )
    return normalized


def _official_url(
    value: str,
    *,
    base: str = BASE_URL,
    allow_power_bi: bool = False,
) -> str:
    candidate = urljoin(base, value.strip())
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"}:
        raise ColoradoCourtDataSourceChanged(
            f"official catalog supplied a non-HTTP URL: {candidate}"
        )
    if host in _COLORADO_HOSTS:
        netloc = "www.coloradojudicial.gov"
    elif allow_power_bi and host == _POWER_BI_HOST:
        netloc = _POWER_BI_HOST
    else:
        raise ColoradoCourtDataSourceChanged(
            f"official catalog supplied an unexpected host: {candidate}"
        )
    return urlunparse(
        ("https", netloc, parsed.path, "", parsed.query, "")
    )


def _fiscal_year(label: str) -> int:
    match = _FY_PATTERN.search(label)
    if match is None:
        raise ColoradoCourtDataSourceChanged(
            f"report link lacks a fiscal-year label: {label!r}"
        )
    return int(match.group(1))


def _iso_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError as exc:
        raise ColoradoCourtDataSourceChanged(
            f"could not parse CJD effective date: {value!r}"
        ) from exc


def _annual_dashboard_type(title: str) -> str:
    normalized = title.casefold()
    if "supreme" in normalized:
        return "supreme_court_statistics"
    if "appeal" in normalized or normalized.startswith("coa"):
        return "court_of_appeals_statistics"
    if "trial" in normalized:
        return "trial_court_statistics"
    if "financial" in normalized:
        return "judicial_branch_financial_information"
    if "probation" in normalized:
        return "probation_statistics"
    return f"annual_statistics_{_slug(title).replace('-', '_')}"


@dataclass(frozen=True)
class CourtDataArtifact:
    """One exact report, dashboard, policy, form, or request workflow."""

    component_source_id: str
    artifact_kind: str
    artifact_id: str
    title: str
    report_type: str
    format: str
    access_mode: str
    landing_page_url: str
    source_url: str
    downloadable: bool
    fiscal_year: int | None = None
    effective_date: str | None = None
    coverage: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def canonical_ref(self) -> str:
        return (
            f"COURT-DATA:{self.component_source_id}/{self.artifact_id}"
        )

    @property
    def suggested_filename(self) -> str:
        source_name = Path(urlparse(self.source_url).path).name
        if source_name.casefold().endswith(".pdf"):
            return source_name
        return f"{self.artifact_id}.pdf"

    def to_record(self) -> dict[str, Any]:
        if self.artifact_kind == "request_workflow":
            description = (
                "Official route for requesting publicly accessible compiled "
                "or aggregate Colorado court data under CJD 05-01 Section 4.40."
            )
        elif self.artifact_kind == "interactive_dashboard":
            description = (
                "Official public interactive dashboard linked by the "
                "Colorado Judicial Branch."
            )
        elif self.artifact_kind == "request_form":
            description = (
                "Official Addendum A form for a compiled or aggregate "
                "electronic court-data request."
            )
        elif self.artifact_kind == "policy_document":
            description = (
                "Current Colorado Judicial public-access policy document "
                "governing court records and data requests."
            )
        else:
            description = (
                "Official Colorado Judicial fiscal-year statistical report."
            )
        return {
            "adapter_source_id": SOURCE_ID,
            "source_id": self.component_source_id,
            "component_source_id": self.component_source_id,
            "record_kind": "court_data_source_record",
            "record_scope": "colorado_state_courts",
            "artifact_kind": self.artifact_kind,
            "artifact_id": self.artifact_id,
            "canonical_ref": self.canonical_ref,
            "evidence_ref": self.canonical_ref,
            "native_document_id": self.artifact_id,
            "title": self.title,
            "report_type": self.report_type,
            "fiscal_year": self.fiscal_year,
            "effective_date": self.effective_date,
            "format": self.format,
            "access_mode": self.access_mode,
            "downloadable_by_adapter": self.downloadable,
            "landing_page_url": self.landing_page_url,
            "landing_url": self.landing_page_url,
            "source_url": self.source_url,
            "artifact_url": self.source_url,
            "dashboard_url": (
                self.source_url if self.format == "power_bi" else None
            ),
            "description": description,
            "coverage": dict(self.coverage),
            "metadata": dict(self.metadata),
            "projection": {
                "projectable_as_case": False,
                "scope": "publication_or_request_workflow",
                "reason": (
                    "the record describes a report, dashboard, policy "
                    "artifact, or data-request workflow"
                ),
            },
        }


@dataclass(frozen=True)
class CatalogSnapshot:
    artifacts: tuple[CourtDataArtifact, ...]
    source_pages: Mapping[str, str]


def parse_annual_reports(
    html: str,
    source_url: str = ANNUAL_REPORTS_URL,
) -> tuple[CourtDataArtifact, ...]:
    """Parse every current dashboard and archived PDF on the annual index."""
    soup = BeautifulSoup(html, "html.parser")
    artifacts: list[CourtDataArtifact] = []
    seen_dashboard_urls: set[str] = set()
    for frame in soup.find_all("iframe"):
        raw_url = str(frame.get("src") or "").strip()
        if not raw_url:
            continue
        candidate_host = (
            urlparse(urljoin(source_url, raw_url)).hostname or ""
        ).casefold()
        if candidate_host != _POWER_BI_HOST:
            continue
        dashboard_url = _official_url(
            raw_url,
            base=source_url,
            allow_power_bi=True,
        )
        if dashboard_url in seen_dashboard_urls:
            continue
        seen_dashboard_urls.add(dashboard_url)
        title = _clean_text(frame.get("title")) or "Annual Statistics Dashboard"
        artifacts.append(
            CourtDataArtifact(
                component_source_id=ANNUAL_REPORTS_SOURCE_ID,
                artifact_kind="interactive_dashboard",
                artifact_id=f"annual-dashboard-{_slug(title)}",
                title=title,
                report_type=_annual_dashboard_type(title),
                format="power_bi",
                access_mode="public_interactive_dashboard",
                landing_page_url=_official_url(source_url),
                source_url=dashboard_url,
                downloadable=False,
                coverage={
                    "basis": "source_defined_interactive_report",
                    "period": "current_source_dashboard",
                },
                metadata={
                    "dashboard_title": title,
                    "machine_artifact_route": None,
                },
            )
        )

    heading = soup.find(
        lambda tag: (
            tag.name in {"h2", "h3", "h4"}
            and _clean_text(tag).casefold() == "previous fiscal year reports"
        )
    )
    report_list = (
        heading.parent.find("ul") if heading is not None else None
    )
    if report_list is None:
        raise ColoradoCourtDataSourceChanged(
            "annual report page lacks its fiscal-year report list"
        )
    for anchor in report_list.find_all("a", href=True):
        label = _clean_text(anchor)
        year = _fiscal_year(label)
        artifact_url = _official_url(
            str(anchor["href"]),
            base=source_url,
        )
        artifacts.append(
            CourtDataArtifact(
                component_source_id=ANNUAL_REPORTS_SOURCE_ID,
                artifact_kind="statistical_report",
                artifact_id=f"annual-statistical-report-fy-{year}",
                title=f"Colorado Judicial Annual Statistical Report FY {year}",
                report_type="annual_statistical_report",
                format="pdf",
                access_mode="direct_download",
                landing_page_url=_official_url(source_url),
                source_url=artifact_url,
                downloadable=True,
                fiscal_year=year,
                coverage={
                    "basis": "fiscal_year",
                    "fiscal_year": year,
                    "fiscal_year_start_month": 7,
                    "fiscal_year_end_month": 6,
                },
                metadata={"source_label": label},
            )
        )
    if not seen_dashboard_urls:
        raise ColoradoCourtDataSourceChanged(
            "annual report page lacks its public dashboards"
        )
    return tuple(artifacts)


def parse_self_represented_reports(
    html: str,
    source_url: str = SELF_REPRESENTED_URL,
) -> tuple[CourtDataArtifact, ...]:
    """Parse all fiscal-year reports from the official pro-se report index."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(
        lambda tag: (
            tag.name in {"h2", "h3", "h4"}
            and "without attorney representation"
            in _clean_text(tag).casefold()
        )
    )
    report_list = (
        heading.parent.find("ul") if heading is not None else None
    )
    if report_list is None:
        raise ColoradoCourtDataSourceChanged(
            "case/party representation page lacks its fiscal-year report list"
        )

    artifacts: list[CourtDataArtifact] = []
    for anchor in report_list.find_all("a", href=True):
        label = _clean_text(anchor)
        year = _fiscal_year(label)
        artifacts.append(
            CourtDataArtifact(
                component_source_id=SELF_REPRESENTED_SOURCE_ID,
                artifact_kind="statistical_report",
                artifact_id=(
                    "case-parties-without-representation-"
                    f"fy-{year}"
                ),
                title=(
                    "Colorado Cases and Parties Without Attorney "
                    f"Representation FY {year}"
                ),
                report_type="case_parties_without_representation",
                format="pdf",
                access_mode="direct_download",
                landing_page_url=_official_url(source_url),
                source_url=_official_url(
                    str(anchor["href"]),
                    base=source_url,
                ),
                downloadable=True,
                fiscal_year=year,
                coverage={
                    "basis": "fiscal_year",
                    "fiscal_year": year,
                    "measure_scope": (
                        "cases_and_parties_without_attorney_representation"
                    ),
                    "denver_county_court_included": False,
                },
                metadata={"source_label": label},
            )
        )
    if not artifacts:
        raise ColoradoCourtDataSourceChanged(
            "case/party representation report list is empty"
        )
    return tuple(artifacts)


def parse_eviction_dashboard(
    html: str,
    source_url: str = EVICTION_DASHBOARD_URL,
) -> CourtDataArtifact:
    """Parse the official FED dashboard link without inventing an export URL."""
    soup = BeautifulSoup(html, "html.parser")
    frame = soup.find(
        "iframe",
        attrs={"title": re.compile(r"FED[_ ]Filings", re.IGNORECASE)},
    )
    if frame is None or not frame.get("src"):
        raise ColoradoCourtDataSourceChanged(
            "eviction page lacks the FED filings dashboard"
        )
    dashboard_url = _official_url(
        str(frame["src"]),
        base=source_url,
        allow_power_bi=True,
    )
    return CourtDataArtifact(
        component_source_id=EVICTION_DASHBOARD_SOURCE_ID,
        artifact_kind="interactive_dashboard",
        artifact_id=EVICTION_ARTIFACT_ID,
        title="Colorado Eviction Filings (FED) Dashboard",
        report_type="eviction_filings",
        format="power_bi",
        access_mode="public_interactive_dashboard",
        landing_page_url=_official_url(source_url),
        source_url=dashboard_url,
        downloadable=False,
        coverage={
            "case_type": "forcible_entry_and_detainer",
            "courts": [
                "Colorado state courts",
                "Denver County Court",
            ],
            "period": "source_defined_interactive_dashboard",
        },
        metadata={
            "dashboard_title": _clean_text(frame.get("title")),
            "state_court_data_contact": DATA_REQUEST_EMAIL,
            "denver_county_court_data_contact": DENVER_DATA_REQUEST_EMAIL,
            "machine_artifact_route": None,
        },
    )


def parse_cjd_05_01(
    html: str,
    source_url: str = CJD_INDEX_URL,
) -> CourtDataArtifact:
    """Discover the current CJD 05-01 policy PDF from its official index."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(
        lambda tag: (
            tag.name in {"h2", "h3", "h4"}
            and _clean_text(tag).casefold().startswith(
                "05-01 access to court records"
            )
        )
    )
    article = heading.find_parent("article") if heading is not None else None
    if article is None:
        raise ColoradoCourtDataSourceChanged(
            "Chief Justice Directive index lacks CJD 05-01"
        )
    policy_anchor = article.find(
        "a",
        href=lambda value: bool(
            value and ".pdf" in str(value).casefold()
        ),
    )
    if policy_anchor is None:
        raise ColoradoCourtDataSourceChanged(
            "CJD 05-01 entry lacks its current policy PDF"
        )
    policy_text = _clean_text(article)
    effective_match = _EFFECTIVE_PATTERN.search(policy_text)
    if effective_match is None:
        raise ColoradoCourtDataSourceChanged(
            "CJD 05-01 entry lacks its current effective date"
        )
    effective_date = _iso_date(effective_match.group(1).title())
    return CourtDataArtifact(
        component_source_id=COMPILED_REQUEST_SOURCE_ID,
        artifact_kind="policy_document",
        artifact_id=f"cjd-05-01-effective-{effective_date}",
        title="CJD 05-01: Access to Court Records",
        report_type="compiled_aggregate_data_request_policy",
        format="pdf",
        access_mode="direct_download",
        landing_page_url=_official_url(source_url),
        source_url=_official_url(
            str(policy_anchor["href"]),
            base=source_url,
        ),
        downloadable=True,
        effective_date=effective_date,
        coverage={
            "policy_sections": ["4.30", "4.40"],
            "policy_effective_date": effective_date,
        },
        metadata={
            "source_label": _clean_text(policy_anchor),
            "directive": "CJD 05-01",
        },
    )


def addendum_a_artifact() -> CourtDataArtifact:
    return CourtDataArtifact(
        component_source_id=COMPILED_REQUEST_SOURCE_ID,
        artifact_kind="request_form",
        artifact_id=ADDENDUM_ARTIFACT_ID,
        title="Addendum A: Compiled or Aggregate Data Request",
        report_type="compiled_aggregate_data_request_form",
        format="pdf",
        access_mode="direct_download",
        landing_page_url=RESEARCH_DATA_URL,
        source_url=ADDENDUM_A_URL,
        downloadable=True,
        coverage={
            "request_type": "compiled_or_aggregate_electronic_court_data",
            "governing_policy_section": "CJD 05-01 Section 4.40",
        },
        metadata={
            "submission_email": DATA_REQUEST_EMAIL,
            "stable_media_alias": ADDENDUM_A_URL,
        },
    )


def compiled_request_workflow_artifact(
    policy: CourtDataArtifact,
) -> CourtDataArtifact:
    """Return the structured request route described by current CJD 05-01."""
    return CourtDataArtifact(
        component_source_id=COMPILED_REQUEST_SOURCE_ID,
        artifact_kind="request_workflow",
        artifact_id=WORKFLOW_ARTIFACT_ID,
        title="Colorado Compiled or Aggregate Court Data Request",
        report_type="compiled_aggregate_data_request_workflow",
        format="request_workflow",
        access_mode="request",
        landing_page_url=RESEARCH_DATA_URL,
        source_url=ACCESS_GUIDE_URL,
        downloadable=False,
        coverage={
            "requestable_data": (
                "publicly accessible compiled or aggregate data derived "
                "from the Judicial Department case-management system and "
                "not already available remotely or in an existing report"
            ),
            "monthly_civil_judgment_report": {
                "availability": (
                    "available from the State Court Administrator's Office "
                    "upon request and payment of applicable fees"
                ),
                "fields": [
                    "case number",
                    "creditor name",
                    "creditor address when entered",
                    "debtor name",
                    "debtor address when entered",
                    "judgment date",
                    "total judgment amount",
                    "satisfaction date when applicable",
                ],
            },
        },
        metadata={
            "submission_email": DATA_REQUEST_EMAIL,
            "request_form_artifact_id": ADDENDUM_ARTIFACT_ID,
            "policy_artifact_id": policy.artifact_id,
            "policy_url": policy.source_url,
            "policy_sections": {
                "4.30": (
                    "defines bulk data as the entire CMS or a substantial "
                    "subset and states that Department policy is not to "
                    "release bulk data"
                ),
                "4.40": (
                    "provides the Addendum A route for publicly accessible "
                    "compiled or aggregate data requests"
                ),
            },
            "request_elements": [
                "identify the compiled or aggregate data sought",
                "describe the purpose of the request",
                "explain measures for secure protection of the data",
            ],
        },
    )


def _validate_catalog(
    artifacts: Sequence[CourtDataArtifact],
) -> tuple[CourtDataArtifact, ...]:
    seen: set[tuple[str, str]] = set()
    for artifact in artifacts:
        identity = (artifact.component_source_id, artifact.artifact_id)
        if identity in seen:
            raise ColoradoCourtDataSourceChanged(
                f"live catalog contains duplicate artifact identity {identity}"
            )
        seen.add(identity)
    return tuple(artifacts)


class ColoradoCourtDataClient:
    """HTTP client for the official report and policy landing pages."""

    def __init__(
        self,
        session: requests.Session | Any | None = None,
        *,
        timeout: float = TIMEOUT,
        minimum_interval: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/pdf;"
                        "q=0.9,*/*;q=0.7"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)

    def _request(
        self,
        url: str,
        *,
        allow_power_bi: bool = False,
        stream: bool = False,
    ) -> Any:
        safe_url = _official_url(
            url,
            allow_power_bi=allow_power_bi,
        )
        for attempt in range(self.max_retries + 1):
            self._wait()
            self._last_request_at = time.monotonic()
            try:
                response = self.session.request(
                    "GET",
                    safe_url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=stream,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise ColoradoCourtDataTransportError(
                    f"official source request failed: {exc}"
                ) from exc

            final_url = _official_url(
                str(getattr(response, "url", safe_url)),
                allow_power_bi=allow_power_bi,
            )
            status_code = int(getattr(response, "status_code", 0))
            if status_code == 429 or status_code >= 500:
                if attempt < self.max_retries:
                    response.close()
                    time.sleep(0.5 * (2**attempt))
                    continue
            if status_code == 429:
                response.close()
                raise ColoradoCourtDataRateLimited(
                    f"official source rate-limited {final_url}"
                )
            if status_code != 200:
                response.close()
                raise ColoradoCourtDataHTTPError(status_code, final_url)
            return response
        raise ColoradoCourtDataTransportError(
            "official source request exhausted retries"
        )

    def get_text(
        self,
        url: str,
        *,
        allow_power_bi: bool = False,
    ) -> str:
        response = self._request(
            url,
            allow_power_bi=allow_power_bi,
        )
        try:
            content_type = str(
                response.headers.get("Content-Type", "")
            ).casefold()
            if "html" not in content_type:
                raise ColoradoCourtDataSourceChanged(
                    f"expected HTML at {response.url}, got {content_type!r}"
                )
            return str(response.text)
        finally:
            response.close()

    def catalog(self) -> CatalogSnapshot:
        pages = {
            "annual_reports": ANNUAL_REPORTS_URL,
            "case_parties_without_representation": SELF_REPRESENTED_URL,
            "eviction_filings": EVICTION_DASHBOARD_URL,
            "cjd_05_01": CJD_INDEX_URL,
        }
        annual = parse_annual_reports(
            self.get_text(ANNUAL_REPORTS_URL),
            ANNUAL_REPORTS_URL,
        )
        self_represented = parse_self_represented_reports(
            self.get_text(SELF_REPRESENTED_URL),
            SELF_REPRESENTED_URL,
        )
        eviction = parse_eviction_dashboard(
            self.get_text(EVICTION_DASHBOARD_URL),
            EVICTION_DASHBOARD_URL,
        )
        policy = parse_cjd_05_01(
            self.get_text(CJD_INDEX_URL),
            CJD_INDEX_URL,
        )
        artifacts = _validate_catalog(
            (
                *annual,
                *self_represented,
                eviction,
                policy,
                addendum_a_artifact(),
                compiled_request_workflow_artifact(policy),
            )
        )
        return CatalogSnapshot(artifacts=artifacts, source_pages=pages)

    def _stream_pdf(
        self,
        artifact: CourtDataArtifact,
        handle: Any | None = None,
    ) -> dict[str, Any]:
        if not artifact.downloadable or artifact.format != "pdf":
            raise ColoradoCourtDataNotDownloadable(
                f"{artifact.artifact_id} is a discoverable "
                f"{artifact.access_mode} record, not a verified PDF artifact"
            )
        response = self._request(artifact.source_url, stream=True)
        digest = hashlib.sha256()
        sample = bytearray()
        byte_count = 0
        try:
            for chunk in response.iter_content(1024 * 1024):
                if not chunk:
                    continue
                if len(sample) < 8:
                    sample.extend(chunk[: 8 - len(sample)])
                digest.update(chunk)
                byte_count += len(chunk)
                if handle is not None:
                    handle.write(chunk)
            content_type = str(
                response.headers.get("Content-Type", "")
            ).casefold()
            if not bytes(sample).startswith(b"%PDF-"):
                raise ColoradoCourtDataSourceChanged(
                    f"{artifact.artifact_id} did not return a PDF signature"
                )
            if "application/pdf" not in content_type:
                raise ColoradoCourtDataSourceChanged(
                    f"{artifact.artifact_id} returned {content_type!r}, not PDF"
                )
            raw_length = response.headers.get("Content-Length")
            if (
                raw_length
                and str(raw_length).isdigit()
                and int(raw_length) != byte_count
            ):
                raise ColoradoCourtDataSourceChanged(
                    f"{artifact.artifact_id} byte count differs from "
                    "Content-Length"
                )
            return {
                "size": byte_count,
                "sha256": digest.hexdigest(),
                "content_type": response.headers.get("Content-Type"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "requested_url": artifact.source_url,
                "final_url": _official_url(str(response.url)),
            }
        finally:
            response.close()

    def inspect(self, artifact: CourtDataArtifact) -> dict[str, Any]:
        """Read and hash one complete verified PDF without retaining it."""
        return self._stream_pdf(artifact)

    def download(
        self,
        artifact: CourtDataArtifact,
        destination: str | Path,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if not artifact.downloadable or artifact.format != "pdf":
            raise ColoradoCourtDataNotDownloadable(
                f"{artifact.artifact_id} is a discoverable "
                f"{artifact.access_mode} record, not a verified PDF artifact"
            )
        destination_path = Path(destination).expanduser()
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / artifact.suggested_filename
        elif str(destination).endswith(os.sep):
            destination_path = destination_path / artifact.suggested_filename
        if destination_path.exists() and not overwrite:
            raise OSError(
                f"destination exists; pass --overwrite: {destination_path}"
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination_path.name}.",
                suffix=".part",
                dir=destination_path.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                receipt = self._stream_pdf(artifact, handle)
            temporary_path.replace(destination_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return {
            **receipt,
            "path": str(destination_path.resolve()),
        }

    def probe_dashboard(self, artifact: CourtDataArtifact) -> dict[str, Any]:
        if artifact.format != "power_bi":
            raise ColoradoCourtDataError(
                f"{artifact.artifact_id} is not a Power BI dashboard"
            )
        html = self.get_text(
            artifact.source_url,
            allow_power_bi=True,
        )
        lowered = html.casefold()
        if "microsoft power bi" not in lowered and "power bi report" not in lowered:
            raise ColoradoCourtDataSourceChanged(
                f"{artifact.artifact_id} no longer resolves to Power BI"
            )
        return {
            "source_url": artifact.source_url,
            "content_kind": "power_bi_html_shell",
            "anonymous_get": "http_200",
        }


def resolve_artifact(
    artifacts: Sequence[CourtDataArtifact],
    selector: str,
) -> CourtDataArtifact:
    candidate = selector.strip()
    matches = [
        artifact
        for artifact in artifacts
        if candidate
        in {
            artifact.artifact_id,
            artifact.canonical_ref,
            artifact.source_url,
        }
    ]
    if not matches:
        raise ColoradoCourtDataNotFound(
            f"artifact is not an exact member of the live catalog: {selector}"
        )
    if len(matches) > 1:
        raise ColoradoCourtDataSourceChanged(
            f"artifact selector is ambiguous in the live catalog: {selector}"
        )
    return matches[0]


def filter_artifacts(
    artifacts: Sequence[CourtDataArtifact],
    *,
    query: str | None = None,
    component_source_id: str | None = None,
    report_type: str | None = None,
    fiscal_year: int | None = None,
) -> tuple[CourtDataArtifact, ...]:
    """Filter the complete live catalog without an adapter-defined cap."""
    needle = query.casefold().strip() if query else None
    selected: list[CourtDataArtifact] = []
    for artifact in artifacts:
        if (
            component_source_id
            and artifact.component_source_id != component_source_id
        ):
            continue
        if report_type and artifact.report_type != report_type:
            continue
        if fiscal_year is not None and artifact.fiscal_year != fiscal_year:
            continue
        if needle:
            haystack = json.dumps(
                artifact.to_record(),
                sort_keys=True,
            ).casefold()
            if needle not in haystack:
                continue
        selected.append(artifact)
    return tuple(selected)


def run_probe(
    client: ColoradoCourtDataClient | Any | None = None,
) -> dict[str, Any]:
    source_client = client or ColoradoCourtDataClient()
    snapshot = source_client.catalog()
    addendum = resolve_artifact(
        snapshot.artifacts,
        ADDENDUM_ARTIFACT_ID,
    )
    addendum_receipt = source_client.inspect(addendum)
    eviction = resolve_artifact(
        snapshot.artifacts,
        EVICTION_ARTIFACT_ID,
    )
    dashboard_receipt = source_client.probe_dashboard(eviction)

    component_counts: dict[str, int] = {}
    for artifact in snapshot.artifacts:
        component_counts[artifact.component_source_id] = (
            component_counts.get(artifact.component_source_id, 0) + 1
        )
    catalog_identity = sha256_fingerprint(
        [
            {
                "component_source_id": artifact.component_source_id,
                "artifact_id": artifact.artifact_id,
                "source_url": artifact.source_url,
            }
            for artifact in sorted(
                snapshot.artifacts,
                key=lambda item: (
                    item.component_source_id,
                    item.artifact_id,
                ),
            )
        ]
    )
    return {
        "adapter_source_id": SOURCE_ID,
        "source_id": SOURCE_ID,
        "record_kind": "source_health_check",
        "artifact_kind": "live_probe",
        "artifact_id": "source-health-live-probe",
        "native_document_id": "source-health-live-probe",
        "source_url": ANNUAL_REPORTS_URL,
        "canonical_ref": (
            f"COURT-DATA:{SOURCE_ID}/source-health-live-probe"
        ),
        "status": "ok",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result_count": len(snapshot.artifacts),
        "component_counts": component_counts,
        "source_pages": dict(snapshot.source_pages),
        "artifact_identity": catalog_identity,
        "schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "sentinels": {
            "addendum_a": {
                "artifact_id": addendum.artifact_id,
                **addendum_receipt,
            },
            "eviction_dashboard": {
                "artifact_id": eviction.artifact_id,
                **dashboard_receipt,
            },
        },
    }


def _selector_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in (
        "query",
        "component_source",
        "report_type",
        "fiscal_year",
        "artifact",
        "destination",
    ):
        value = getattr(args, name, None)
        if value is not None:
            values[name] = str(value) if isinstance(value, Path) else value
    return values


def build_query(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_selector_parameters(args),
            metadata={"access_decision": dict(access_decision or {})},
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _access_failure(
    args: argparse.Namespace,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = dict(error.decision)
        status = ResultStatus(acquisition_result_status(decision))
        code = str(
            decision.get("reason_code")
            or "machine_acquisition_unavailable"
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
    error: ColoradoCourtDataError,
) -> PublicRecordsResult:
    if isinstance(error, ColoradoCourtDataSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, ColoradoCourtDataRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
        retryable = True
    elif isinstance(error, ColoradoCourtDataTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    elif isinstance(error, ColoradoCourtDataHTTPError):
        status = (
            ResultStatus.RESTRICTED
            if error.status_code in {401, 403}
            else (
                ResultStatus.SOURCE_CHANGED
                if error.status_code in {404, 410}
                else ResultStatus.UNAVAILABLE
            )
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


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: ColoradoCourtDataClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one adapter command through the shared public-record contract."""
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
        if log_results:
            _log(result.query, None)
        return result
    if not decision.get("allowed", False):
        result = _access_failure(
            args,
            AcquisitionUnavailableError(decision),
        )
        if log_results:
            _log(result.query, None)
        return result

    query = build_query(args, access_decision=decision)
    source_client = client or ColoradoCourtDataClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )
    raw_refs: tuple[str, ...] = ()
    try:
        if args.command in {"catalog", "list", "search"}:
            snapshot = source_client.catalog()
            selected = filter_artifacts(
                snapshot.artifacts,
                query=getattr(args, "query", None),
                component_source_id=getattr(
                    args,
                    "component_source",
                    None,
                ),
                report_type=getattr(args, "report_type", None),
                fiscal_year=getattr(args, "fiscal_year", None),
            )
            result = PublicRecordsResult.success(
                query,
                [artifact.to_record() for artifact in selected],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            snapshot = source_client.catalog()
            artifact = resolve_artifact(
                snapshot.artifacts,
                args.artifact,
            )
            receipt = source_client.download(
                artifact,
                args.destination,
                overwrite=args.overwrite,
            )
            record = artifact.to_record()
            record["artifact_receipt"] = receipt
            raw_refs = (receipt["path"],)
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=raw_refs,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            probe = run_probe(source_client)
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise ColoradoCourtDataError(
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
    except ColoradoCourtDataError as error:
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
    if log_results:
        _log(query, count)
    return result


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Colorado court data {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Colorado court data {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "court_data_source_record":
            year = (
                f" | FY {record['fiscal_year']}"
                if record.get("fiscal_year")
                else ""
            )
            print(
                f"- {record['artifact_id']}{year} | "
                f"{record['title']}"
            )
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--component-source",
        choices=COMPONENT_SOURCE_IDS,
    )
    parser.add_argument("--report-type")
    parser.add_argument("--fiscal-year", type=int)


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
        description=(
            "Discover Colorado Judicial court-data reports, dashboards, "
            "and compiled/aggregate request materials"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog")
    _add_filters(catalog)
    _add_runtime_args(catalog)

    listing = subparsers.add_parser("list")
    _add_filters(listing)
    _add_runtime_args(listing)

    search = subparsers.add_parser("search")
    search.add_argument("query")
    _add_filters(search)
    _add_runtime_args(search)

    download = subparsers.add_parser("download")
    download.add_argument("artifact")
    download.add_argument("--destination", type=Path, required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_args(download)

    probe = subparsers.add_parser("probe")
    _add_runtime_args(probe)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0 or args.minimum_interval < 0:
        parser.error(
            "--timeout must be positive and --minimum-interval non-negative"
        )
    if getattr(args, "fiscal_year", None) is not None:
        if args.fiscal_year < 1900:
            parser.error("--fiscal-year must be 1900 or later")
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
