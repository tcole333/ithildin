#!/usr/bin/env python3
"""Query Georgia AOC aggregate caseload and workload publications.

The Office of Research and Data Analysis publishes six aggregate caseload
dashboards, an official dashboard-export request route, and annual Superior
Court workload-assessment PDFs. These sources contain aggregate counts and
workload context rather than individual case records.

Examples:
    uv run python tools/query_georgia_court_data.py sources --json
    uv run python tools/query_georgia_court_data.py dashboards Superior --json
    uv run python tools/query_georgia_court_data.py workloads --year 2024 --json
    uv run python tools/query_georgia_court_data.py handoff --json
    uv run python tools/query_georgia_court_data.py document 2024 \
        --artifact-output /tmp/ga-superior-workload-2024.pdf --json
    uv run python tools/query_georgia_court_data.py probe \
        --source us-ga-superior-court-workload-assessments --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urljoin, urlsplit

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


DASHBOARD_SOURCE_ID = "us-ga-aoc-caseload-dashboards"
WORKLOAD_SOURCE_ID = "us-ga-superior-court-workload-assessments"
STATE_GEOID = "13"
STATE_CODE = "GA"

DATA_URL = "https://research.georgiacourts.gov/data-and-statistics/"
EXPORT_REQUEST_URL = (
    "https://research.georgiacourts.gov/dashboard-export-request/"
)
RESOURCE_LIBRARY_URL = "https://research.georgiacourts.gov/resource-library/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_PDF_BYTES = 64 * 1024 * 1024
CURSOR_PREFIX = "ga-court-data:v1:"
OUTPUT_SCHEMA_VERSION = "georgia-court-data/1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

COURT_CLASSES = (
    "Superior Court",
    "State Court",
    "Magistrate Court",
    "Probate Court",
    "Juvenile Court",
    "Municipal Court",
)
BASELINE_WORKLOAD_YEARS = frozenset(range(2018, 2025))
_OFFICIAL_HOST = "research.georgiacourts.gov"
_POWER_BI_HOST = "app.powerbigov.us"
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "captcha",
)

DASHBOARD_SOURCE = SourceMetadata(
    source_id=DASHBOARD_SOURCE_ID,
    name="Georgia AOC Caseload Data Dashboards",
    source_role="official_aggregate_court_caseload_dashboards",
    base_url=DATA_URL,
    dataset_id="georgia-aoc-caseload-dashboards",
    metadata={
        "authority": "Judicial Council of Georgia, Administrative Office of the Courts",
        "operator": "Office of Research and Data Analysis",
        "record_grain": "aggregate_self_reported_case_counts",
        "individual_case_records": False,
    },
)
WORKLOAD_SOURCE = SourceMetadata(
    source_id=WORKLOAD_SOURCE_ID,
    name="Georgia Superior Court Workload Assessments",
    source_role="official_annual_superior_court_workload_publications",
    base_url=DATA_URL,
    dataset_id="georgia-superior-court-workload-assessments",
    metadata={
        "authority": "Judicial Council of Georgia, Administrative Office of the Courts",
        "operator": "Office of Research and Data Analysis",
        "record_grain": "annual_aggregate_circuit_workload_publication",
        "individual_case_records": False,
    },
)
SOURCE_BY_ID = {
    DASHBOARD_SOURCE_ID: DASHBOARD_SOURCE,
    WORKLOAD_SOURCE_ID: WORKLOAD_SOURCE,
}
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_aggregate_court_data"},
)

DASHBOARD_WARNINGS = (
    "AOC describes these data as self-reported counts supplied by Georgia courts.",
    "The Research Office states that it does not collect individual-case data.",
)
WORKLOAD_WARNINGS = (
    "Workload assessments are aggregate annual publications, not case-level records.",
)


@dataclass(frozen=True)
class Artifact:
    content: bytes
    source_url: str
    media_type: str | None
    headers: Mapping[str, str]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class ParsedCatalog:
    dashboards: tuple[Mapping[str, Any], ...]
    workloads: tuple[Mapping[str, Any], ...]
    dashboard_user_guide_url: str
    export_request_url: str
    source_url: str
    source_document_sha256: str


class GeorgiaCourtDataError(RuntimeError):
    """Transport, schema, access, or selector failure."""

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


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).replace("\x00", "").split()).strip()
    return result or None


def _media_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Content-Type", headers.get("content-type"))
    return (
        str(value).split(";", 1)[0].strip().casefold()
        if value
        else None
    )


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After", headers.get("retry-after"))
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _official_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != _OFFICIAL_HOST:
        raise GeorgiaCourtDataError(
            "unrecognized_official_url",
            "Georgia court-data retrieval requires its verified official HTTPS host",
            category="selection",
            details={"url": url},
        )
    return url


class GeorgiaCourtDataClient:
    """Bounded retrying client with an injectable requests-like session."""

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
        _official_url(url)
        headers = {
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
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
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise GeorgiaCourtDataError(
                    "transport_error",
                    str(error),
                    category="transport",
                    retryable=True,
                    details={"url": url},
                ) from error

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
                raise GeorgiaCourtDataError(
                    "rate_limited",
                    "Georgia court-data source rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise GeorgiaCourtDataError(
                    "access_restricted",
                    f"Georgia court-data source returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise GeorgiaCourtDataError(
                    "http_status",
                    f"Georgia court-data source returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise GeorgiaCourtDataError(
                    "response_too_large",
                    "Georgia court-data response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            response_url = str(getattr(response, "url", None) or url)
            _official_url(response_url)
            return Artifact(
                content=content,
                source_url=response_url,
                media_type=_media_type(response),
                headers={
                    str(key).casefold(): str(value)
                    for key, value in getattr(
                        response,
                        "headers",
                        {},
                    ).items()
                },
            )
        raise GeorgiaCourtDataError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": url},
        )


def _html_soup(artifact: Artifact, *, marker: str) -> BeautifulSoup:
    if artifact.media_type and "html" not in artifact.media_type:
        raise GeorgiaCourtDataError(
            "unexpected_media_type",
            "Georgia court-data page did not return HTML",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    text = soup.get_text(" ", strip=True)
    folded = text.casefold()
    if any(value in folded for value in _CHALLENGE_MARKERS):
        raise GeorgiaCourtDataError(
            "human_verification",
            "Georgia court-data source returned a verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    if marker.casefold() not in folded:
        raise GeorgiaCourtDataError(
            "source_marker_missing",
            f"Georgia court-data page lacks expected marker {marker!r}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url, "marker": marker},
        )
    return soup


def _direct_pdf_url(viewer_url: str) -> str:
    parsed = urlsplit(viewer_url)
    query = parse_qs(parsed.query)
    values = query.get("file")
    if not values:
        raise GeorgiaCourtDataError(
            "dashboard_guide_url_changed",
            "Caseload dashboard guide viewer does not expose its PDF URL",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"viewer_url": viewer_url},
        )
    return _official_url(values[0])


def parse_data_catalog(artifact: Artifact) -> ParsedCatalog:
    """Parse aggregate dashboards, guide, and annual workload publications."""

    soup = _html_soup(artifact, marker="Data & Statistics")
    page_text = _clean(soup.get_text(" ", strip=True)) or ""
    required_scope_markers = (
        "self-reported data by Georgia Courts",
        "only consists of counts of cases",
        "does not collect data on individual cases",
    )
    missing_scope = [
        marker
        for marker in required_scope_markers
        if marker.casefold() not in page_text.casefold()
    ]
    if missing_scope:
        raise GeorgiaCourtDataError(
            "aggregate_scope_changed",
            "Georgia AOC aggregate-data scope markers changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"missing_markers": missing_scope},
        )

    export_anchor = soup.find(
        "a",
        href=lambda value: isinstance(value, str)
        and "dashboard-export-request" in value,
    )
    if export_anchor is None:
        raise GeorgiaCourtDataError(
            "export_route_missing",
            "Georgia AOC dashboard export route is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    export_url = _official_url(
        urljoin(artifact.source_url, str(export_anchor["href"]))
    )

    dashboards = []
    for panel in soup.select(".fusion-panel"):
        heading = panel.select_one(".fusion-toggle-heading")
        iframe = panel.select_one("iframe[src]")
        title = _clean(
            heading.get_text(" ", strip=True) if heading else None
        )
        if not title or not title.endswith(" Court Dashboard"):
            continue
        if iframe is None:
            raise GeorgiaCourtDataError(
                "dashboard_embed_missing",
                f"Georgia AOC {title} lacks an embedded dashboard",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        court_class = title.removesuffix(" Dashboard")
        dashboard_url = str(iframe["src"])
        parsed_url = urlsplit(dashboard_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != _POWER_BI_HOST
            or parsed_url.path != "/view"
            or "r" not in parse_qs(parsed_url.query)
        ):
            raise GeorgiaCourtDataError(
                "dashboard_route_changed",
                f"Georgia AOC {title} uses an unexpected dashboard route",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"url": dashboard_url},
            )
        dashboards.append(
            {
                "canonical_ref": (
                    "GA-AOC-CASELOAD-DASHBOARD:"
                    + re.sub(
                        r"[^A-Z0-9]+",
                        "-",
                        court_class.upper(),
                    ).strip("-")
                ),
                "source_id": DASHBOARD_SOURCE_ID,
                "record_kind": "aggregate_caseload_dashboard",
                "court_class": court_class,
                "dashboard_title": title,
                "dashboard_url": dashboard_url,
                "platform_family": "microsoft_power_bi_government",
                "data_scope": {
                    "record_grain": "aggregate_case_counts",
                    "reporting": "self_reported_by_georgia_courts",
                    "individual_case_records": False,
                },
                "export_request_url": export_url,
                "source_url": artifact.source_url,
                "source_document_sha256": artifact.sha256,
                "projection": {
                    "projectable_as_case_record": False,
                    "scope": "aggregate_caseload_context",
                },
            }
        )
    observed_classes = {str(record["court_class"]) for record in dashboards}
    if observed_classes != set(COURT_CLASSES):
        raise GeorgiaCourtDataError(
            "dashboard_classes_changed",
            "Georgia AOC dashboard class set changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "expected": list(COURT_CLASSES),
                "observed": sorted(observed_classes),
            },
        )
    dashboards.sort(
        key=lambda record: COURT_CLASSES.index(str(record["court_class"]))
    )

    guide_panel = next(
        (
            panel
            for panel in soup.select(".fusion-panel")
            if "Caseload Dashboard User Guide"
            in panel.get_text(" ", strip=True)
        ),
        None,
    )
    guide_iframe = (
        guide_panel.select_one("iframe[src]")
        if guide_panel is not None
        else None
    )
    if guide_iframe is None:
        raise GeorgiaCourtDataError(
            "dashboard_guide_missing",
            "Georgia AOC caseload dashboard guide is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    guide_url = _direct_pdf_url(
        urljoin(artifact.source_url, str(guide_iframe["src"]))
    )

    workloads = []
    for anchor in soup.select("a[href]"):
        title = _clean(anchor.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(20\d{2}) Superior Court Workload Assessment",
            title or "",
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        year = int(match.group(1))
        pdf_url = _official_url(
            urljoin(artifact.source_url, str(anchor["href"]))
        )
        if not urlsplit(pdf_url).path.casefold().endswith(".pdf"):
            raise GeorgiaCourtDataError(
                "workload_document_route_changed",
                f"Georgia AOC {year} workload assessment is not a PDF route",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"url": pdf_url},
            )
        parent_text = _clean(
            anchor.parent.get_text(" ", strip=True)
            if anchor.parent is not None
            else None
        )
        updated_match = re.search(
            r"last updated\s+([^)]+)",
            parent_text or "",
            flags=re.IGNORECASE,
        )
        workloads.append(
            {
                "canonical_ref": (
                    f"GA-AOC-SUPERIOR-WORKLOAD-ASSESSMENT:{year}"
                ),
                "source_id": WORKLOAD_SOURCE_ID,
                "record_kind": (
                    "annual_superior_court_workload_assessment"
                ),
                "publication_year": year,
                "title": title,
                "pdf_url": pdf_url,
                "published_update_note": (
                    updated_match.group(1).strip()
                    if updated_match
                    else None
                ),
                "data_scope": {
                    "record_grain": (
                        "aggregate_circuit_and_statewide_workload_tables"
                    ),
                    "individual_case_records": False,
                },
                "source_url": artifact.source_url,
                "source_document_sha256": artifact.sha256,
                "projection": {
                    "projectable_as_case_record": False,
                    "scope": "aggregate_workload_publication",
                },
            }
        )
    years = {int(record["publication_year"]) for record in workloads}
    if not BASELINE_WORKLOAD_YEARS <= years:
        raise GeorgiaCourtDataError(
            "workload_archive_incomplete",
            "Georgia AOC workload archive no longer includes its verified baseline",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "required_years": sorted(BASELINE_WORKLOAD_YEARS),
                "observed_years": sorted(years),
            },
        )
    workloads.sort(
        key=lambda record: int(record["publication_year"]),
        reverse=True,
    )
    return ParsedCatalog(
        dashboards=tuple(dashboards),
        workloads=tuple(workloads),
        dashboard_user_guide_url=guide_url,
        export_request_url=export_url,
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
    )


def parse_export_handoff(artifact: Artifact) -> dict[str, Any]:
    """Parse the official dashboard-export request fields without submitting."""

    soup = _html_soup(artifact, marker="Dashboard Export Request")
    form = soup.select_one("form#gform_1")
    if form is None:
        raise GeorgiaCourtDataError(
            "export_form_missing",
            "Georgia AOC dashboard-export request form is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    action_url = _official_url(
        urljoin(artifact.source_url, str(form.get("action") or ""))
    )
    court_classes = tuple(
        str(node.get("value"))
        for node in form.select("#field_1_19 input[value]")
    )
    years = tuple(
        int(str(node.get("value")))
        for node in form.select("#field_1_20 input[value]")
        if str(node.get("value")).isdigit()
    )
    if set(court_classes) != set(COURT_CLASSES) or not years:
        raise GeorgiaCourtDataError(
            "export_form_options_changed",
            "Georgia AOC dashboard-export request options changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "court_classes": list(court_classes),
                "years": list(years),
            },
        )
    required_fields = []
    for field in form.select(".gfield_contains_required"):
        label = field.select_one(
            ".gfield_label, .gform-field-label, legend"
        )
        value = _clean(
            label.get_text(" ", strip=True) if label else None
        )
        if value:
            required_fields.append(
                re.sub(
                    r"\s*\(Required\)\s*$",
                    "",
                    value,
                    flags=re.IGNORECASE,
                )
            )
    return {
        "canonical_ref": "GA-AOC-CASELOAD-DASHBOARD-EXPORT:13",
        "source_id": DASHBOARD_SOURCE_ID,
        "record_kind": "aggregate_dashboard_export_acquisition_handoff",
        "request_url": artifact.source_url,
        "form_action_url": action_url,
        "available_court_classes": court_classes,
        "available_years": years,
        "required_request_fields": tuple(dict.fromkeys(required_fields)),
        "requested_data_dimensions": [
            "court_class",
            "date_range",
            "desired_data_format",
            "filers",
            "case_types",
            "special_requirements",
        ],
        "submission_performed": False,
        "source_url": artifact.source_url,
        "source_document_sha256": artifact.sha256,
        "projection": {
            "projectable_as_case_record": False,
            "scope": "verified_aggregate_data_acquisition_handoff",
        },
    }


def parse_pdf_artifact(
    artifact: Artifact,
    publication: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one selected official workload PDF and preserve its digest."""

    if artifact.media_type and artifact.media_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise GeorgiaCourtDataError(
            "unexpected_document_media_type",
            "Georgia workload publication did not return a PDF media type",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    if not artifact.content.startswith(b"%PDF-"):
        raise GeorgiaCourtDataError(
            "invalid_pdf_signature",
            "Georgia workload publication lacks a PDF signature",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    return {
        **dict(publication),
        "record_kind": "annual_superior_court_workload_pdf",
        "artifact_url": artifact.source_url,
        "artifact_media_type": artifact.media_type or "application/pdf",
        "artifact_byte_length": len(artifact.content),
        "artifact_sha256": artifact.sha256,
        "source_document_sha256": artifact.sha256,
    }


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": DASHBOARD_SOURCE_ID,
            "record_kind": "source_description",
            "name": DASHBOARD_SOURCE.name,
            "official_url": DATA_URL,
            "operations": ["dashboards", "handoff", "probe"],
            "record_grain": "aggregate_self_reported_case_counts",
        },
        {
            "source_id": WORKLOAD_SOURCE_ID,
            "record_kind": "source_description",
            "name": WORKLOAD_SOURCE.name,
            "official_url": DATA_URL,
            "operations": ["workloads", "document", "probe"],
            "record_grain": "annual_aggregate_workload_publication",
        },
    ]


def _manifest_record(source_id: str) -> dict[str, Any]:
    if source_id == DASHBOARD_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "operations": ["dashboards", "handoff", "probe"],
            "coverage": {
                "court_classes": list(COURT_CLASSES),
                "record_grain": "aggregate_self_reported_case_counts",
                "individual_case_records": False,
                "official_export_handoff": True,
            },
            "stable_identity": ["canonical_ref"],
            "complementary_source_ids": [
                WORKLOAD_SOURCE_ID,
                "us-ga-aoc-court-personnel-directory",
            ],
        }
    if source_id == WORKLOAD_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "operations": ["workloads", "document", "probe"],
            "coverage": {
                "baseline_years": sorted(BASELINE_WORKLOAD_YEARS),
                "record_grain": "annual_aggregate_workload_publication",
                "individual_case_records": False,
            },
            "stable_identity": ["canonical_ref"],
            "complementary_source_ids": [DASHBOARD_SOURCE_ID],
        }
    raise ValueError(f"unknown Georgia court-data source {source_id}")


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
        "artifact_output",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = getattr(args, "source", None)
    if source_id is None:
        source_id = (
            WORKLOAD_SOURCE_ID
            if args.command in {"workloads", "document"}
            else DASHBOARD_SOURCE_ID
        )
    return PublicRecordsQuery(
        source=SOURCE_BY_ID[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: GeorgiaCourtDataError,
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=warnings,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    status_value = str(
        decision.get("result_status")
        or decision.get("status")
        or (
            ResultStatus.HUMAN_REQUIRED.value
            if decision.get("automation_disposition")
            == "human_required"
            else ResultStatus.RESTRICTED.value
        )
    )
    try:
        status = ResultStatus(status_value)
    except ValueError:
        status = ResultStatus.RESTRICTED
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=warnings,
    )


def _encode_cursor(
    *,
    query_key: str,
    source_sha256: str,
    offset: int,
    boundary_ref: str,
) -> str:
    payload = canonical_json(
        {
            "query_key": query_key,
            "source_sha256": source_sha256,
            "offset": offset,
            "boundary_ref": boundary_ref,
        }
    ).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return CURSOR_PREFIX + token


def _decode_cursor(
    cursor: str | None,
    *,
    query_key: str,
    source_sha256: str,
    records: list[Mapping[str, Any]],
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise GeorgiaCourtDataError(
            "invalid_cursor",
            "Georgia court-data cursor prefix is invalid",
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeorgiaCourtDataError(
            "invalid_cursor",
            "Georgia court-data cursor is malformed",
            category="query_selection",
        ) from error
    if not isinstance(payload, Mapping):
        raise GeorgiaCourtDataError(
            "invalid_cursor",
            "Georgia court-data cursor payload is invalid",
            category="query_selection",
        )
    if payload.get("query_key") != query_key:
        raise GeorgiaCourtDataError(
            "cursor_query_mismatch",
            "Georgia court-data cursor belongs to another query",
            category="query_selection",
        )
    if payload.get("source_sha256") != source_sha256:
        raise GeorgiaCourtDataError(
            "cursor_source_changed",
            "Georgia court-data source changed after cursor issue",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    offset = payload.get("offset")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 1
        or offset > len(records)
    ):
        raise GeorgiaCourtDataError(
            "invalid_cursor",
            "Georgia court-data cursor offset is invalid",
            category="query_selection",
        )
    previous = records[offset - 1]
    if payload.get("boundary_ref") != previous.get("canonical_ref"):
        raise GeorgiaCourtDataError(
            "cursor_boundary_changed",
            "Georgia court-data cursor boundary changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return offset


def _page_records(
    records: list[Mapping[str, Any]],
    *,
    query_identity: Mapping[str, Any],
    source_sha256: str,
    limit: int,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    query_key = sha256_fingerprint(query_identity)
    offset = _decode_cursor(
        cursor,
        query_key=query_key,
        source_sha256=source_sha256,
        records=records,
    )
    selected = records[offset : offset + limit]
    next_offset = offset + len(selected)
    next_cursor = None
    if selected and next_offset < len(records):
        next_cursor = _encode_cursor(
            query_key=query_key,
            source_sha256=source_sha256,
            offset=next_offset,
            boundary_ref=str(selected[-1]["canonical_ref"]),
        )
    return selected, next_cursor


def _filter_dashboards(
    parsed: ParsedCatalog,
    query: str,
) -> list[Mapping[str, Any]]:
    needle = _clean(query)
    if needle in {None, "*"}:
        return list(parsed.dashboards)
    folded = needle.casefold()
    return [
        record
        for record in parsed.dashboards
        if folded
        in " ".join(
            str(record.get(field) or "")
            for field in (
                "court_class",
                "dashboard_title",
                "dashboard_url",
            )
        ).casefold()
    ]


def _publication_for_year(
    parsed: ParsedCatalog,
    year: int,
) -> Mapping[str, Any]:
    for record in parsed.workloads:
        if int(record["publication_year"]) == year:
            return record
    raise GeorgiaCourtDataError(
        "publication_not_found",
        f"Georgia AOC does not list a {year} workload assessment",
        status=ResultStatus.NO_RESULTS,
        category="query_selection",
        details={
            "year": year,
            "available_years": [
                record["publication_year"]
                for record in parsed.workloads
            ],
        },
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: GeorgiaCourtDataClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    warnings = (
        DASHBOARD_WARNINGS
        if query.source.source_id == DASHBOARD_SOURCE_ID
        else WORKLOAD_WARNINGS
    )
    if access_decision is not None and not access_decision.get(
        "allowed",
        False,
    ):
        result = _decision_failure(
            query,
            access_decision,
            warnings=warnings,
        )
        if log_results:
            log_search(
                canonical_json(query.to_dict()),
                query.source.source_id,
                None,
            )
        return result

    network_command = args.command in {
        "dashboards",
        "workloads",
        "handoff",
        "document",
        "probe",
    }
    source_client = client
    if network_command and source_client is None:
        source_client = GeorgiaCourtDataClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _source_records(),
                warnings=DASHBOARD_WARNINGS,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_manifest_record(args.source)],
                warnings=warnings,
            )
        elif args.command in {"dashboards", "workloads"}:
            parsed = parse_data_catalog(source_client.get(DATA_URL))
            if args.command == "dashboards":
                records = _filter_dashboards(parsed, args.query)
                identity = {
                    "command": "dashboards",
                    "query": args.query,
                }
            else:
                records = [
                    record
                    for record in parsed.workloads
                    if args.year is None
                    or int(record["publication_year"]) == args.year
                ]
                identity = {
                    "command": "workloads",
                    "year": args.year,
                }
            selected, next_cursor = _page_records(
                records,
                query_identity=identity,
                source_sha256=parsed.source_document_sha256,
                limit=args.limit,
                cursor=args.cursor,
            )
            result = PublicRecordsResult.success(
                query,
                selected,
                next_cursor=next_cursor,
                warnings=warnings,
            )
        elif args.command == "handoff":
            record = parse_export_handoff(
                source_client.get(EXPORT_REQUEST_URL)
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=DASHBOARD_WARNINGS,
            )
        elif args.command == "document":
            parsed = parse_data_catalog(source_client.get(DATA_URL))
            publication = _publication_for_year(parsed, args.year)
            artifact = source_client.get(
                str(publication["pdf_url"]),
                accept="application/pdf,application/octet-stream",
                maximum_bytes=MAXIMUM_PDF_BYTES,
            )
            record = parse_pdf_artifact(artifact, publication)
            if args.artifact_output:
                output_path = Path(args.artifact_output)
                output_path.write_bytes(artifact.content)
                record["artifact_storage_path"] = str(
                    output_path.resolve()
                )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=WORKLOAD_WARNINGS,
            )
        elif args.command == "probe":
            parsed = parse_data_catalog(source_client.get(DATA_URL))
            if args.source == DASHBOARD_SOURCE_ID:
                record = {
                    "source_id": DASHBOARD_SOURCE_ID,
                    "record_kind": "source_probe",
                    "status": "ok",
                    "dashboard_count": len(parsed.dashboards),
                    "court_classes": [
                        record["court_class"]
                        for record in parsed.dashboards
                    ],
                    "dashboard_user_guide_url": (
                        parsed.dashboard_user_guide_url
                    ),
                    "export_request_url": parsed.export_request_url,
                    "individual_case_records": False,
                    "source_document_sha256": (
                        parsed.source_document_sha256
                    ),
                    "stable_schema_sha256": sha256_fingerprint(
                        {
                            "dashboard_fields": sorted(
                                parsed.dashboards[0]
                            ),
                            "court_classes": list(COURT_CLASSES),
                            "record_grain": "aggregate_case_counts",
                        }
                    ),
                }
            else:
                publication = parsed.workloads[0]
                artifact = source_client.get(
                    str(publication["pdf_url"]),
                    accept=(
                        "application/pdf,application/octet-stream"
                    ),
                    maximum_bytes=MAXIMUM_PDF_BYTES,
                )
                document = parse_pdf_artifact(
                    artifact,
                    publication,
                )
                record = {
                    "source_id": WORKLOAD_SOURCE_ID,
                    "record_kind": "source_probe",
                    "status": "ok",
                    "publication_count": len(parsed.workloads),
                    "publication_years": [
                        item["publication_year"]
                        for item in parsed.workloads
                    ],
                    "latest_publication_year": (
                        document["publication_year"]
                    ),
                    "latest_artifact_url": document["artifact_url"],
                    "latest_artifact_sha256": (
                        document["artifact_sha256"]
                    ),
                    "latest_artifact_byte_length": (
                        document["artifact_byte_length"]
                    ),
                    "source_document_sha256": (
                        parsed.source_document_sha256
                    ),
                    "stable_schema_sha256": sha256_fingerprint(
                        {
                            "publication_fields": sorted(
                                parsed.workloads[0]
                            ),
                            "baseline_years": sorted(
                                BASELINE_WORKLOAD_YEARS
                            ),
                            "document_fields": sorted(document),
                        }
                    ),
                }
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=warnings,
            )
        else:
            raise ValueError(
                f"unsupported Georgia court-data command {args.command!r}"
            )
    except GeorgiaCourtDataError as error:
        result = _failure(query, error, warnings=warnings)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_artifact",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )
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
            warnings=warnings,
        )
    finally:
        if network_command and client is None and source_client is not None:
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


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Georgia AOC aggregate caseload dashboards, export "
            "handoff, and annual Superior Court workload publications"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the complementary aggregate source identities",
    )
    sources.set_defaults(source=DASHBOARD_SOURCE_ID)
    _add_runtime(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Describe one aggregate source contract",
    )
    manifest.add_argument(
        "--source",
        choices=sorted(SOURCE_BY_ID),
        default=DASHBOARD_SOURCE_ID,
    )
    _add_runtime(manifest)

    dashboards = sub.add_parser(
        "dashboards",
        help="List or filter the six aggregate caseload dashboards",
    )
    dashboards.add_argument("query", nargs="?", default="*")
    dashboards.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    dashboards.add_argument("--cursor")
    dashboards.set_defaults(source=DASHBOARD_SOURCE_ID)
    _add_runtime(dashboards)

    workloads = sub.add_parser(
        "workloads",
        help="List annual Superior Court workload-assessment PDFs",
    )
    workloads.add_argument("--year", type=int)
    workloads.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    workloads.add_argument("--cursor")
    workloads.set_defaults(source=WORKLOAD_SOURCE_ID)
    _add_runtime(workloads)

    handoff = sub.add_parser(
        "handoff",
        help="Inspect the official dashboard-export request route",
    )
    handoff.set_defaults(source=DASHBOARD_SOURCE_ID)
    _add_runtime(handoff)

    document = sub.add_parser(
        "document",
        help="Fetch and validate one annual workload-assessment PDF",
    )
    document.add_argument("year", type=int)
    document.add_argument(
        "--artifact-output",
        help="Optional path for the validated PDF bytes",
    )
    document.set_defaults(source=WORKLOAD_SOURCE_ID)
    _add_runtime(document)

    probe = sub.add_parser(
        "probe",
        help="Run one bounded aggregate-source sentinel",
    )
    probe.add_argument(
        "--source",
        choices=sorted(SOURCE_BY_ID),
        default=DASHBOARD_SOURCE_ID,
    )
    _add_runtime(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Georgia court data {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Georgia court data {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
