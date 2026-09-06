#!/usr/bin/env python3
"""Query official D.C. Courts directories and data-publication routes.

The D.C. Courts publish current Superior Court and Court of Appeals judge
directories as server-rendered HTML.  They also publish a data-request program
for aggregate or case-level extracts and a long-running PDF report catalog.
Those are complementary sources, so this adapter retains a separate source
identity for each court and publication role.

Examples:
    uv run python tools/query_dc_court_directory_data.py sources --json
    uv run python tools/query_dc_court_directory_data.py manifest --json
    uv run python tools/query_dc_court_directory_data.py directory \
        --court superior --query Becker --json
    uv run python tools/query_dc_court_directory_data.py directory \
        --court appeals --role senior --json
    uv run python tools/query_dc_court_directory_data.py contacts \
        --court all --json
    uv run python tools/query_dc_court_directory_data.py assignments --json
    uv run python tools/query_dc_court_directory_data.py data-request --json
    uv run python tools/query_dc_court_directory_data.py reports \
        --section annual-reports --year 2025 --json
    uv run python tools/query_dc_court_directory_data.py download \
        --collection reports \
        "2025 Annual Report - Statistical Summary" /tmp/dc-2025.pdf --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode, urljoin, urlsplit

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


STATE_CODE = "DC"
STATE_GEOID = "11"
ADAPTER_FAMILY = "dc_courts_directory_and_data_publications"
OUTPUT_SCHEMA_VERSION = "dc-court-directory-data/1.0"

BASE_URL = "https://www.dccourts.gov"
SUPERIOR_DIRECTORY_URL = (
    f"{BASE_URL}/superior-court/superior-court-judges"
)
APPEALS_DIRECTORY_URL = (
    f"{BASE_URL}/court-of-appeals/court-of-appeals-judges"
)
DATA_REQUEST_URL = f"{BASE_URL}/dc-courts/data-requests"
REPORTS_URL = (
    f"{BASE_URL}/dc-courts/strategic-plan/annual-reports"
)

CATALOG_SOURCE_ID = "us-dc-courts-directory-data-catalog"
SUPERIOR_DIRECTORY_SOURCE_ID = (
    "us-dc-superior-court-judicial-directory"
)
APPEALS_DIRECTORY_SOURCE_ID = (
    "us-dc-court-of-appeals-judicial-directory"
)
DATA_REQUEST_SOURCE_ID = "us-dc-courts-data-request-program"
REPORTS_SOURCE_ID = "us-dc-courts-reports-publication-catalog"

SUPERIOR_COURT_ID = "us-dc-superior-court"
APPEALS_COURT_ID = "us-dc-court-of-appeals"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_ATTEMPTS = 3
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_PDF_BYTES = 160 * 1024 * 1024
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

SUPERIOR_VIEW_ID = "superior_court_judges"
APPEALS_VIEW_ID = "all_court_of_appeals_judges"
ROLE_BY_DISPLAY = {
    "block_chief_judges": "chief",
    "block_associate_judge": "associate",
    "block_magistrate_judge": "magistrate",
    "block_senior_judge": "senior",
}
SUPERIOR_PAGER_SLOT = {
    "chief": 0,
    "associate": 1,
    "magistrate": 2,
    "senior": 3,
}
COURT_CONFIG = {
    "superior": {
        "source_id": SUPERIOR_DIRECTORY_SOURCE_ID,
        "court_id": SUPERIOR_COURT_ID,
        "court_name": "District of Columbia Superior Court",
        "url": SUPERIOR_DIRECTORY_URL,
        "view_id": SUPERIOR_VIEW_ID,
        "page_marker": "Superior Court Judges",
    },
    "appeals": {
        "source_id": APPEALS_DIRECTORY_SOURCE_ID,
        "court_id": APPEALS_COURT_ID,
        "court_name": "District of Columbia Court of Appeals",
        "url": APPEALS_DIRECTORY_URL,
        "view_id": APPEALS_VIEW_ID,
        "page_marker": "Court of Appeals Judges",
    },
}

COMPLEMENTARY_SOURCE_IDS = (
    "us-dc-court-of-appeals-case-search",
    "us-dc-court-of-appeals-opinions-mojs",
    "us-dc-superior-court-today-calendar",
    "us-dc-superior-court-criminal-calendar",
    "us-dc-superior-court-tax-calendars",
    "us-dc-court-of-appeals-calendars",
    "us-dc-superior-eaccess",
    "us-dc-superior-court-portal",
)

_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_TOTAL_RE = re.compile(
    r"\bTotal\s+([\d,]+)\s+items?\b",
    flags=re.IGNORECASE,
)
_PAGE_RE = re.compile(r"\bPage\s+(\d+)\b", flags=re.IGNORECASE)
_EMAIL_RE = re.compile(
    r"\bsmddata\s*(?:@|\[\s*at\s*\])\s*"
    r"([a-z0-9.-]+\.[a-z]{2,})\b",
    flags=re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


@dataclass(frozen=True)
class Component:
    source_id: str
    name: str
    source_role: str
    base_url: str
    access_state: str
    operations: tuple[str, ...]
    coverage: str
    relationship: str


COMPONENTS = {
    SUPERIOR_DIRECTORY_SOURCE_ID: Component(
        source_id=SUPERIOR_DIRECTORY_SOURCE_ID,
        name="D.C. Superior Court Judicial Directory",
        source_role="official_trial_court_judicial_directory",
        base_url=SUPERIOR_DIRECTORY_URL,
        access_state="open_server_rendered_html",
        operations=("directory", "contacts", "assignments"),
        coverage=(
            "current chief, associate, magistrate, and senior judges; "
            "calendar, courtroom, phone, profile, leadership, and court contact"
        ),
        relationship="current personnel and assignment discovery",
    ),
    APPEALS_DIRECTORY_SOURCE_ID: Component(
        source_id=APPEALS_DIRECTORY_SOURCE_ID,
        name="D.C. Court of Appeals Judicial Directory",
        source_role="official_appellate_court_judicial_directory",
        base_url=APPEALS_DIRECTORY_URL,
        access_state="open_server_rendered_html",
        operations=("directory", "contacts"),
        coverage=(
            "current chief, associate, and senior judges; phone, profile, "
            "leadership, locations, hours, and court contact"
        ),
        relationship="current appellate personnel and clerk-office discovery",
    ),
    DATA_REQUEST_SOURCE_ID: Component(
        source_id=DATA_REQUEST_SOURCE_ID,
        name="D.C. Courts Data Request Program",
        source_role="official_aggregate_and_case_level_data_request_program",
        base_url=DATA_REQUEST_URL,
        access_state="published_request_process_and_fillable_forms",
        operations=("data-request", "download"),
        coverage=(
            "aggregate data, individual or case-level data, and interview, "
            "survey, or focus-group requests"
        ),
        relationship=(
            "request route for data not supplied through the public case "
            "indexes and publication catalogs"
        ),
    ),
    REPORTS_SOURCE_ID: Component(
        source_id=REPORTS_SOURCE_ID,
        name="D.C. Courts Reports Publication Catalog",
        source_role="official_aggregate_court_statistics_and_reports_catalog",
        base_url=REPORTS_URL,
        access_state="open_html_catalog_and_pdf_artifacts",
        operations=("reports", "download"),
        coverage=(
            "annual statistical and narrative reports, Family Court reports, "
            "budget justifications, strategic plans, and operational reports"
        ),
        relationship=(
            "machine-accessible aggregate substitute for a direct case-level "
            "bulk feed"
        ),
    ),
}


def _component_metadata(component: Component) -> SourceMetadata:
    return SourceMetadata(
        source_id=component.source_id,
        name=component.name,
        source_role=component.source_role,
        base_url=component.base_url,
        dataset_id=component.source_id,
        metadata={
            "authority": "District of Columbia Courts",
            "operator": "District of Columbia Courts",
            "authentication": "none",
            "adapter_family": ADAPTER_FAMILY,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "coverage": component.coverage,
            "relationship": component.relationship,
        },
    )


SOURCE_METADATA = {
    source_id: _component_metadata(component)
    for source_id, component in COMPONENTS.items()
}
CATALOG_METADATA = SourceMetadata(
    source_id=CATALOG_SOURCE_ID,
    name="D.C. Courts Directory and Data Publication Catalog",
    source_role="official_court_source_family_catalog",
    base_url=BASE_URL,
    dataset_id="dc-courts-directory-data-publications",
    metadata={
        "authority": "District of Columbia Courts",
        "adapter_family": ADAPTER_FAMILY,
        "components": list(COMPONENTS),
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="District of Columbia",
    state_code=STATE_CODE,
    locality="Washington",
)

WARNINGS = (
    "Each court directory and publication role retains its own source identity.",
    "The report catalog provides aggregate statistics; case-level extracts use "
    "the separately published data-request process.",
    "Catalog anomalies are returned as source observations rather than silently "
    "rewritten.",
)


class DCCourtDirectoryDataError(RuntimeError):
    """Transport, source-schema, or selection failure."""

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


class SourceChangedError(DCCourtDirectoryDataError):
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


class SelectionError(DCCourtDirectoryDataError):
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


@dataclass(frozen=True)
class DirectoryPage:
    records: tuple[Mapping[str, Any], ...]
    advertised_totals: Mapping[str, int]
    page_counts: Mapping[str, int]
    current_pages: Mapping[str, int]
    source_url: str
    source_sha256: str


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required(value: Any, field: str) -> str:
    cleaned = _clean(value)
    if cleaned is None:
        raise SourceChangedError(
            "required_field_missing",
            f"D.C. Courts response lacks {field}",
            details={"field": field},
        )
    return cleaned


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _absolute(value: str, base: str = BASE_URL) -> str:
    return urljoin(base, value.strip())


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


class DCCourtDirectoryDataClient:
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
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"www.dccourts.gov", "dccourts.gov"}
        ):
            raise SelectionError(
                "unrecognized_artifact_host",
                "D.C. Courts artifact URL must use the official HTTPS host",
                details={"url": url},
            )
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
                if attempt >= self.retry_policy.max_attempts:
                    raise DCCourtDirectoryDataError(
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
                raise DCCourtDirectoryDataError(
                    "rate_limited",
                    "D.C. Courts rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise DCCourtDirectoryDataError(
                    "access_restricted",
                    f"D.C. Courts returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise DCCourtDirectoryDataError(
                    "http_status",
                    f"D.C. Courts returned HTTP {status_code}",
                    retryable=status_code >= 500,
                    category="http",
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise DCCourtDirectoryDataError(
                    "response_too_large",
                    "D.C. Courts response exceeds the configured bound",
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
        raise DCCourtDirectoryDataError(
            "transport_error",
            str(last_error or "request failed"),
            retryable=True,
            category="transport",
            details={"url": url},
        )


def _html(artifact: Artifact, marker: str) -> BeautifulSoup:
    if artifact.media_type and "html" not in artifact.media_type:
        raise SourceChangedError(
            "unexpected_media_type",
            "D.C. Courts route did not return HTML",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    folded = page_text.casefold()
    if any(value in folded for value in _CHALLENGE_MARKERS):
        raise DCCourtDirectoryDataError(
            "human_verification",
            "D.C. Courts returned an interactive verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    if marker.casefold() not in folded:
        raise SourceChangedError(
            "page_marker_missing",
            f"D.C. Courts page lacks expected marker {marker!r}",
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


def _view_display_id(view: Any) -> str | None:
    for class_name in view.get("class") or []:
        if class_name.startswith("view-display-id-"):
            return class_name.removeprefix("view-display-id-")
    return None


def _page_number(view: Any) -> int:
    active = view.select_one(".pager__item.active")
    if active is None:
        return 1
    text = _clean(active.get_text(" ", strip=True)) or ""
    match = _PAGE_RE.search(text)
    if match:
        return int(match.group(1))
    visible = active.select_one("span[aria-hidden='true']")
    value = _clean(visible.get_text(" ", strip=True)) if visible else None
    return int(value) if value and value.isdigit() else 1


def _page_count(view: Any, total: int, observed_rows: int) -> int:
    last = view.select_one(".pager__item--last")
    if last is not None:
        text = _clean(last.get_text(" ", strip=True)) or ""
        match = _PAGE_RE.search(text)
        if match:
            return int(match.group(1))
        visible = last.select_one("span[aria-hidden='true']")
        value = _clean(visible.get_text(" ", strip=True)) if visible else None
        if value and value.isdigit():
            return int(value)
    if observed_rows and total > observed_rows:
        return math.ceil(total / observed_rows)
    return 1


def _judge_record(
    row: Any,
    *,
    artifact: Artifact,
    court: str,
    role: str,
    page_number: int,
) -> dict[str, Any]:
    config = COURT_CONFIG[court]
    name_cell = row.select_one("td.views-field-title")
    if name_cell is None:
        raise SourceChangedError(
            "judge_name_column_missing",
            "D.C. Courts directory row lacks its judge-name column",
            details={"court": court, "role": role},
        )
    profile = name_cell.find("a", href=True)
    published_name = _required(
        (
            profile.get_text(" ", strip=True)
            if profile is not None
            else name_cell.get_text(" ", strip=True)
        ),
        "judge name",
    )
    profile_url = (
        _absolute(str(profile.get("href")), artifact.source_url)
        if profile is not None
        else None
    )
    phone_cell = row.select_one("td.views-field-field-phone-number")
    calendar_cell = row.select_one("td.views-field-field-calendar")
    courtroom_cell = row.select_one("td.views-field-field-courtroom-1")
    meeting = (
        courtroom_cell.find("a", href=True)
        if courtroom_cell is not None
        else None
    )
    stable_key = profile_url or f"{role}:{published_name}"
    native_id = hashlib.sha256(stable_key.encode()).hexdigest()[:20]
    canonical_ref = (
        f"DC-COURT-DIRECTORY:{config['court_id']}:{native_id}"
    )
    return {
        **_source_fields(
            artifact,
            source_id=str(config["source_id"]),
        ),
        "record_kind": "court_directory_judge",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_person_id": native_id,
        "court_id": config["court_id"],
        "court_name": config["court_name"],
        "judicial_role": role,
        "published_name": published_name,
        "phone": (
            _clean(phone_cell.get_text(" ", strip=True))
            if phone_cell is not None
            else None
        ),
        "calendar": (
            _clean(calendar_cell.get_text(" ", strip=True))
            if calendar_cell is not None
            else None
        ),
        "courtroom": (
            _clean(courtroom_cell.get_text(" ", strip=True))
            if courtroom_cell is not None
            else None
        ),
        "remote_hearing_url": (
            _absolute(str(meeting.get("href")), artifact.source_url)
            if meeting is not None
            else None
        ),
        "profile_url": profile_url,
        "directory_page_number": page_number,
        "projection": {
            "projectable_as_case": False,
            "scope": "current_directory_snapshot",
        },
    }


def parse_directory_page(
    artifact: Artifact,
    *,
    court: str,
) -> DirectoryPage:
    """Parse all judicial-role views present on one source page."""

    if court not in COURT_CONFIG:
        raise SelectionError(
            "unknown_court",
            f"unknown D.C. directory court {court!r}",
        )
    config = COURT_CONFIG[court]
    soup = _html(artifact, str(config["page_marker"]))
    views = soup.select(f"div.view-id-{config['view_id']}")
    if not views:
        raise SourceChangedError(
            "judge_views_missing",
            "D.C. Courts directory no longer exposes the expected judge views",
            details={"court": court, "url": artifact.source_url},
        )

    records: list[Mapping[str, Any]] = []
    advertised_totals: dict[str, int] = {}
    page_counts: dict[str, int] = {}
    current_pages: dict[str, int] = {}
    for view in views:
        display_id = _view_display_id(view)
        role = ROLE_BY_DISPLAY.get(display_id or "")
        if role is None:
            continue
        headers = [
            _clean(node.get_text(" ", strip=True))
            for node in view.select("table thead th")
        ]
        if not headers or headers[:2] != ["Judge", "Phone number"]:
            raise SourceChangedError(
                "judge_table_headers_changed",
                "D.C. Courts directory judge table headers changed",
                details={
                    "court": court,
                    "role": role,
                    "headers": headers,
                },
            )
        page_number = _page_number(view)
        rows = view.select("table tbody tr")
        for row in rows:
            records.append(
                _judge_record(
                    row,
                    artifact=artifact,
                    court=court,
                    role=role,
                    page_number=page_number,
                )
            )
        total_node = view.select_one(".pagination-total")
        total_match = (
            _TOTAL_RE.search(total_node.get_text(" ", strip=True))
            if total_node is not None
            else None
        )
        total = (
            int(total_match.group(1).replace(",", ""))
            if total_match
            else len(rows)
        )
        if total < len(rows):
            raise SourceChangedError(
                "judge_total_invalid",
                "D.C. Courts directory total is smaller than its visible rows",
                details={"court": court, "role": role, "total": total},
            )
        advertised_totals[role] = total
        page_counts[role] = _page_count(view, total, len(rows))
        current_pages[role] = page_number

    if not records:
        raise SourceChangedError(
            "judge_rows_missing",
            "D.C. Courts directory contains no judge rows",
            details={"court": court, "url": artifact.source_url},
        )
    return DirectoryPage(
        records=tuple(records),
        advertised_totals=advertised_totals,
        page_counts=page_counts,
        current_pages=current_pages,
        source_url=artifact.source_url,
        source_sha256=artifact.sha256,
    )


def _superior_page_url(
    page_index: int,
    page_counts: Mapping[str, int],
) -> str:
    values = [0, 0, 0, 0]
    for role, slot in SUPERIOR_PAGER_SLOT.items():
        if page_index < page_counts.get(role, 1):
            values[slot] = page_index
    return (
        f"{SUPERIOR_DIRECTORY_URL}?"
        + urlencode({"page": ",".join(str(value) for value in values)})
    )


def collect_directory(
    client: DCCourtDirectoryDataClient | Any,
    *,
    court: str,
) -> list[dict[str, Any]]:
    """Fetch and completeness-check one current judicial directory."""

    config = COURT_CONFIG[court]
    first = parse_directory_page(
        client.get(str(config["url"])),
        court=court,
    )
    pages = [first]
    if court == "superior":
        maximum_page_count = max(first.page_counts.values(), default=1)
        for page_index in range(1, maximum_page_count):
            pages.append(
                parse_directory_page(
                    client.get(
                        _superior_page_url(
                            page_index,
                            first.page_counts,
                        )
                    ),
                    court=court,
                )
            )

    by_ref: dict[str, dict[str, Any]] = {}
    for page in pages:
        for raw_record in page.records:
            record = dict(raw_record)
            by_ref.setdefault(str(record["canonical_ref"]), record)
    records = list(by_ref.values())

    observed: dict[str, int] = {}
    for record in records:
        role = str(record["judicial_role"])
        observed[role] = observed.get(role, 0) + 1
    if observed != dict(first.advertised_totals):
        raise SourceChangedError(
            "directory_traversal_incomplete",
            "D.C. Courts directory traversal did not match advertised totals",
            details={
                "court": court,
                "advertised_totals": dict(first.advertised_totals),
                "observed_totals": observed,
                "page_counts": dict(first.page_counts),
            },
        )
    return records


def _contact_article(soup: BeautifulSoup, court: str) -> Any:
    expected = (
        "Superior Court"
        if court == "superior"
        else "Court of Appeals"
    )
    for article in soup.select(
        ".paragraph--type--contact-info-block article"
    ):
        heading = article.find(["h2", "h3"])
        if heading and _clean(heading.get_text(" ", strip=True)) == expected:
            return article
    raise SourceChangedError(
        "court_contact_block_missing",
        "D.C. Courts directory lacks its court contact block",
        details={"court": court},
    )


def parse_contact_record(
    artifact: Artifact,
    *,
    court: str,
) -> dict[str, Any]:
    config = COURT_CONFIG[court]
    soup = _html(artifact, str(config["page_marker"]))
    article = _contact_article(soup, court)
    leadership = []
    for block in article.select(
        ".paragraph--type--contact-info-leadership"
    ):
        title_node = block.select_one(".field-name--field-title")
        name_node = block.select_one(".field-name--field-name")
        title = (
            _clean(title_node.get_text(" ", strip=True))
            if title_node is not None
            else None
        )
        name = (
            _clean(name_node.get_text(" ", strip=True))
            if name_node is not None
            else None
        )
        if title and name:
            leadership.append({"title": title, "name": name})

    locations = []
    for block in article.select(
        ".paragraph--type--contact-info-location"
    ):
        def field_text(class_name: str) -> str | None:
            node = block.select_one(f".field-name--{class_name}")
            return (
                _clean(node.get_text(" ", strip=True))
                if node is not None
                else None
            )

        location_name = (
            field_text("field-name")
            or field_text("field-subheading")
        )
        address = field_text("field-address")
        city = field_text("field-city")
        state = field_text("field-state")
        zip_code = field_text("field-zip-code")
        direction = block.select_one(".field-name--field-url a[href]")
        if any((location_name, address, city, state, zip_code)):
            locations.append(
                {
                    "name": location_name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "directions_url": (
                        _absolute(
                            str(direction.get("href")),
                            artifact.source_url,
                        )
                        if direction is not None
                        else None
                    ),
                }
            )

    hours = []
    for block in article.select(
        ".paragraph--type--contact-info-hours-of-operation"
    ):
        subheading_node = block.select_one(".field-name--field-subheading")
        subheading = (
            _clean(subheading_node.get_text(" ", strip=True))
            if subheading_node is not None
            else None
        )
        schedules = []
        for row in block.select(".office-hours__item"):
            label = row.select_one(".office-hours__item-label")
            slots = row.select_one(".office-hours__item-slots")
            if label is not None and slots is not None:
                schedules.append(
                    {
                        "days": _clean(label.get_text(" ", strip=True)),
                        "hours": _clean(slots.get_text(" ", strip=True)),
                    }
                )
        if schedules:
            hours.append(
                {
                    "office": subheading,
                    "schedule": schedules,
                }
            )

    contacts = []
    for block in article.select(
        ".paragraph--type--contact-info-contacts"
    ):
        label_node = block.select_one(
            ":scope > .field-name--field-name"
        )
        label = (
            _clean(label_node.get_text(" ", strip=True))
            if label_node is not None
            else None
        )
        values = []
        for item in block.select(".paragraph--type--contact-item"):
            contact_type_node = item.select_one(
                ".field-name--field-contact-type"
            )
            value_node = item.select_one(".field-name--field-title")
            value = (
                _clean(value_node.get_text(" ", strip=True))
                if value_node is not None
                else None
            )
            if value:
                values.append(
                    {
                        "type": (
                            _clean(
                                contact_type_node.get_text(
                                    " ",
                                    strip=True,
                                )
                            )
                            if contact_type_node is not None
                            else None
                        ),
                        "value": value,
                    }
                )
        if values:
            contacts.append({"label": label, "values": values})

    if not leadership or not locations:
        raise SourceChangedError(
            "court_contact_fields_missing",
            "D.C. Courts contact block lacks leadership or location data",
            details={"court": court},
        )
    canonical_ref = f"DC-COURT-CONTACT:{config['court_id']}"
    return {
        **_source_fields(
            artifact,
            source_id=str(config["source_id"]),
        ),
        "record_kind": "court_directory_contact",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "court_id": config["court_id"],
        "court_name": config["court_name"],
        "leadership": leadership,
        "locations": locations,
        "hours": hours,
        "contacts": contacts,
        "projection": {
            "projectable_as_case": False,
            "scope": "current_directory_snapshot",
        },
    }


def parse_assignment_publications(
    artifact: Artifact,
) -> list[dict[str, Any]]:
    soup = _html(artifact, "Superior Court Judges")
    patterns = (
        "judicial assignments",
        "committees of the superior court",
        "handling matters for retired judges",
    )
    records = []
    for anchor in soup.select("a[href]"):
        label = _clean(anchor.get_text(" ", strip=True))
        if label is None or not any(
            pattern in label.casefold() for pattern in patterns
        ):
            continue
        url = _absolute(str(anchor.get("href")), artifact.source_url)
        year_match = _YEAR_RE.search(label)
        native_id = hashlib.sha256(url.encode()).hexdigest()[:20]
        canonical_ref = f"DC-COURT-ASSIGNMENT:{native_id}"
        records.append(
            {
                **_source_fields(
                    artifact,
                    source_id=SUPERIOR_DIRECTORY_SOURCE_ID,
                ),
                "record_kind": "court_assignment_publication",
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "native_document_id": native_id,
                "court_id": SUPERIOR_COURT_ID,
                "title": label,
                "publication_year": (
                    int(year_match.group(1)) if year_match else None
                ),
                "artifact_url": url,
                "media_type": "application/pdf",
                "projection": {
                    "projectable_as_case": False,
                    "scope": "court_assignment_publication",
                },
            }
        )
    if not records:
        raise SourceChangedError(
            "assignment_publications_missing",
            "D.C. Superior Court directory lacks assignment publications",
            details={"url": artifact.source_url},
        )
    return records


def _published_emails(text: str) -> list[str]:
    return sorted(
        {
            f"smddata@{match.group(1).casefold()}"
            for match in _EMAIL_RE.finditer(text)
        }
    )


def _data_request_asset_kind(label: str) -> str:
    folded = label.casefold()
    if "faq" in folded or "instruction" in folded:
        return "faq_and_instructions"
    if "form a" in folded:
        return "public_request_form"
    if "form b" in folded:
        return "government_or_court_partner_form"
    return "supporting_document"


def parse_data_request_program(
    artifact: Artifact,
) -> dict[str, Any]:
    soup = _html(artifact, "Requesting Data from the DC Courts")
    tabs = soup.select(".vertical-tab-pane")
    if len(tabs) < 4:
        raise SourceChangedError(
            "data_request_sections_missing",
            "D.C. Courts data-request page lacks its expected sections",
            details={"section_count": len(tabs)},
        )
    sections = []
    for tab in tabs:
        heading = tab.find(["h2", "h3"])
        title = (
            _clean(heading.get_text(" ", strip=True))
            if heading is not None
            else _clean(tab.get("id"))
        )
        body = _clean(tab.get_text(" ", strip=True))
        if title and body:
            sections.append({"title": title, "text": body})

    assets = []
    seen_urls: set[str] = set()
    for anchor in soup.select(".vertical-tab-pane a[href]"):
        raw_url = str(anchor.get("href") or "")
        if "/sites/default/files/" not in raw_url:
            continue
        label = _required(
            anchor.get_text(" ", strip=True),
            "data-request artifact label",
        )
        url = _absolute(raw_url, artifact.source_url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        native_id = hashlib.sha256(url.encode()).hexdigest()[:20]
        assets.append(
            {
                "record_kind": "court_data_request_artifact_route",
                "native_document_id": native_id,
                "artifact_kind": _data_request_asset_kind(label),
                "title": label,
                "artifact_url": url,
                "media_type": "application/pdf",
            }
        )
    required_asset_kinds = {
        "faq_and_instructions",
        "public_request_form",
        "government_or_court_partner_form",
    }
    observed_asset_kinds = {
        str(asset["artifact_kind"]) for asset in assets
    }
    if not required_asset_kinds.issubset(observed_asset_kinds):
        raise SourceChangedError(
            "data_request_artifacts_missing",
            "D.C. Courts data-request page lacks a required published form",
            details={
                "missing": sorted(
                    required_asset_kinds - observed_asset_kinds
                )
            },
        )

    page_text = soup.get_text(" ", strip=True)
    emails = _published_emails(page_text)
    phones = sorted(set(_PHONE_RE.findall(page_text)))
    last_updated_node = soup.select_one(".field-last-update")
    last_updated = (
        _clean(last_updated_node.get_text(" ", strip=True))
        if last_updated_node is not None
        else None
    )
    canonical_ref = "DC-COURT-DATA-REQUEST:PROGRAM"
    return {
        **_source_fields(
            artifact,
            source_id=DATA_REQUEST_SOURCE_ID,
        ),
        "record_kind": "court_data_request_program",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "last_updated": last_updated,
        "requestable_data_types": [
            "aggregate_data",
            "individual_or_case_level_data",
            "interviews_surveys_or_focus_groups",
        ],
        "requestor_tracks": [
            "public_non_government",
            "government_or_court_partner",
        ],
        "delivery_model": "submitted_request_review_and_fulfillment",
        "sections": sections,
        "artifacts": assets,
        "published_email_variants": emails,
        "published_phone_variants": phones,
        "catalog_observations": (
            [
                {
                    "kind": "inconsistent_published_contact",
                    "field": "email",
                    "values": emails,
                }
            ]
            if len(emails) > 1
            else []
        ),
        "aggregate_publication_complement": REPORTS_URL,
        "projection": {
            "projectable_as_case": False,
            "scope": "data_request_program_snapshot",
        },
    }


def _section_key(title: str) -> str:
    return _slug(title)


def _report_kind(section: str, title: str) -> str:
    folded = f"{section} {title}".casefold()
    if "statistical summary" in folded:
        return "statistical_summary"
    if "budget justification" in folded or "budget request" in folded:
        return "budget_justification"
    if "strategic plan" in folded:
        return "strategic_plan"
    if "annual report to congress" in folded:
        return "family_court_annual_report_to_congress"
    if "state of the judiciary" in folded:
        return "state_of_the_judiciary"
    if "performance report" in folded:
        return "performance_report"
    if "shutdown plan" in folded:
        return "shutdown_plan"
    if "narrative" in folded:
        return "annual_report_narrative"
    if "annual report" in folded:
        return "annual_report"
    return "court_report"


def parse_report_catalog(
    artifact: Artifact,
) -> list[dict[str, Any]]:
    soup = _html(artifact, "Annual Reports")
    occurrences: list[dict[str, Any]] = []
    for accordion in soup.select(
        ".paragraph--type--accordion.accordion-item"
    ):
        title_node = accordion.select_one(
            ".accordion-title-text .field-name--field-title"
        )
        section_title = (
            _clean(title_node.get_text(" ", strip=True))
            if title_node is not None
            else None
        )
        if section_title is None:
            continue
        section = _section_key(section_title)
        for ordinal, anchor in enumerate(
            accordion.select(
                ".paragraph--type--link-list-item a[href]"
            ),
            start=1,
        ):
            label = _clean(anchor.get_text(" ", strip=True))
            raw_url = _clean(anchor.get("href"))
            if label is None or raw_url is None:
                continue
            url = _absolute(raw_url, artifact.source_url)
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname
                not in {"www.dccourts.gov", "dccourts.gov"}
            ):
                continue
            year_match = _YEAR_RE.search(label)
            occurrence_basis = (
                f"{section}\0{ordinal}\0{label}\0{url}"
            )
            occurrence_id = hashlib.sha256(
                occurrence_basis.encode()
            ).hexdigest()[:20]
            canonical_ref = (
                f"DC-COURT-REPORT:{section}:{occurrence_id}"
            )
            occurrences.append(
                {
                    **_source_fields(
                        artifact,
                        source_id=REPORTS_SOURCE_ID,
                    ),
                    "record_kind": "court_report_catalog_occurrence",
                    "canonical_ref": canonical_ref,
                    "evidence_ref": canonical_ref,
                    "native_document_id": occurrence_id,
                    "catalog_section": section,
                    "catalog_section_title": section_title,
                    "catalog_ordinal": ordinal,
                    "title": label,
                    "publication_year": (
                        int(year_match.group(1)) if year_match else None
                    ),
                    "report_kind": _report_kind(
                        section_title,
                        label,
                    ),
                    "artifact_url": url,
                    "media_type": (
                        "application/pdf"
                        if parsed.path.casefold().endswith(".pdf")
                        else None
                    ),
                    "projection": {
                        "projectable_as_case": False,
                        "scope": "aggregate_report_catalog",
                    },
                }
            )
    if not occurrences:
        raise SourceChangedError(
            "report_catalog_empty",
            "D.C. Courts reports page contains no publication links",
            details={"url": artifact.source_url},
        )

    by_url: dict[str, list[dict[str, Any]]] = {}
    for record in occurrences:
        by_url.setdefault(str(record["artifact_url"]), []).append(record)
    for records in by_url.values():
        if len(records) == 1:
            records[0]["same_url_occurrence_count"] = 1
            records[0]["catalog_observations"] = []
            continue
        titles = sorted({str(record["title"]) for record in records})
        observation_kind = (
            "same_artifact_url_multiple_labels"
            if len(titles) > 1
            else "duplicate_catalog_occurrence"
        )
        for record in records:
            record["same_url_occurrence_count"] = len(records)
            record["catalog_observations"] = [
                {
                    "kind": observation_kind,
                    "artifact_url": record["artifact_url"],
                    "advertised_titles": titles,
                    "occurrence_count": len(records),
                }
            ]
    return occurrences


def _filter_directory(
    records: Sequence[Mapping[str, Any]],
    *,
    role: str,
    query_text: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    result = []
    query_tokens = (
        [
            token
            for token in re.split(
                r"\s+",
                query_text.strip().casefold(),
            )
            if token
        ]
        if query_text
        else []
    )
    for raw_record in records:
        record = dict(raw_record)
        if role != "all" and record.get("judicial_role") != role:
            continue
        if query_tokens:
            haystack = canonical_json(
                {
                    key: record.get(key)
                    for key in (
                        "published_name",
                        "phone",
                        "calendar",
                        "courtroom",
                        "court_name",
                    )
                }
            ).casefold()
            if not all(token in haystack for token in query_tokens):
                continue
        result.append(record)
        if limit is not None and len(result) >= limit:
            break
    return result


def _filter_reports(
    records: Sequence[Mapping[str, Any]],
    *,
    section: str | None,
    year: int | None,
    query_text: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    result = []
    query_folded = (
        query_text.strip().casefold() if query_text else None
    )
    for raw_record in records:
        record = dict(raw_record)
        if (
            section is not None
            and record.get("catalog_section") != section
        ):
            continue
        if year is not None and record.get("publication_year") != year:
            continue
        if query_folded:
            haystack = " ".join(
                str(record.get(key) or "")
                for key in (
                    "title",
                    "catalog_section_title",
                    "report_kind",
                    "artifact_url",
                )
            ).casefold()
            if query_folded not in haystack:
                continue
        result.append(record)
        if limit is not None and len(result) >= limit:
            break
    return result


def _resolve_artifact(
    records: Sequence[Mapping[str, Any]],
    selector: str,
) -> tuple[str, list[dict[str, Any]]]:
    selected = selector.strip()
    matches = [
        dict(record)
        for record in records
        if selected
        in {
            str(record.get("native_document_id") or ""),
            str(record.get("title") or ""),
            str(record.get("artifact_url") or ""),
        }
    ]
    if not matches:
        raise SelectionError(
            "artifact_not_found",
            f"no exact live D.C. Courts artifact matches {selector!r}",
        )
    urls = {str(record["artifact_url"]) for record in matches}
    if len(urls) > 1:
        raise SelectionError(
            "artifact_ambiguous",
            f"artifact selector {selector!r} matches multiple URLs",
            details={"artifact_urls": sorted(urls)},
        )
    return urls.pop(), matches


def _require_pdf(artifact: Artifact) -> None:
    if not artifact.content.startswith(b"%PDF-"):
        raise SourceChangedError(
            "pdf_signature_missing",
            "D.C. Courts artifact does not have a PDF signature",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )


def _write_artifact(
    artifact: Artifact,
    destination: Path,
    *,
    overwrite: bool,
) -> Path:
    destination = destination.expanduser()
    if destination.exists() and not overwrite:
        raise OSError(
            f"destination exists; pass --overwrite: {destination}"
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
    return destination.resolve()


def _download_record(
    artifact: Artifact,
    *,
    source_id: str,
    route_records: Sequence[Mapping[str, Any]],
    destination: Path,
    overwrite: bool,
) -> dict[str, Any]:
    _require_pdf(artifact)
    path = _write_artifact(
        artifact,
        destination,
        overwrite=overwrite,
    )
    canonical_ref = f"DC-COURT-ARTIFACT:{artifact.sha256}"
    return {
        **_source_fields(artifact, source_id=source_id),
        "record_kind": "court_publication_pdf_artifact",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_document_id": artifact.sha256,
        "artifact_path": str(path),
        "artifact_url": artifact.source_url,
        "media_type": artifact.media_type or "application/pdf",
        "byte_length": len(artifact.content),
        "sha256": artifact.sha256,
        "catalog_occurrences": [
            {
                key: record.get(key)
                for key in (
                    "native_document_id",
                    "record_kind",
                    "title",
                    "artifact_kind",
                    "catalog_section",
                    "publication_year",
                    "report_kind",
                )
                if record.get(key) is not None
            }
            for record in route_records
        ],
        "projection": {
            "projectable_as_case": False,
            "scope": "downloaded_publication_artifact",
        },
    }


def _component_records() -> list[dict[str, Any]]:
    return [
        {
            "record_kind": "source_component",
            "source_id": component.source_id,
            "component_source_id": component.source_id,
            "adapter_family": ADAPTER_FAMILY,
            "canonical_ref": (
                f"DC-COURTS:SOURCE:{component.source_id}"
            ),
            "name": component.name,
            "source_role": component.source_role,
            "base_url": component.base_url,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "coverage": component.coverage,
            "relationship": component.relationship,
            "authority": "District of Columbia Courts",
        }
        for component in COMPONENTS.values()
    ]


def _manifest_record() -> dict[str, Any]:
    return {
        "record_kind": "source_family_manifest",
        "source_id": CATALOG_SOURCE_ID,
        "component_source_id": CATALOG_SOURCE_ID,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": "DC-COURTS:MANIFEST:DIRECTORY-DATA",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "authority": "District of Columbia Courts",
        "components": [
            {
                "source_id": component.source_id,
                "source_role": component.source_role,
                "access_state": component.access_state,
                "operations": list(component.operations),
                "relationship": component.relationship,
            }
            for component in COMPONENTS.values()
        ],
        "operation_access_model": {
            "judicial_directories_and_contacts": (
                "open_server_rendered_html"
            ),
            "assignment_and_report_artifacts": "open_pdf",
            "aggregate_and_case_level_extracts": (
                "published_request_process"
            ),
        },
        "evidence_relationships": {
            "directories": "current personnel and assignment context",
            "data_request_program": (
                "request route for tailored aggregate or case-level data"
            ),
            "reports": "aggregate statistical and institutional context",
            "case_indexes_opinions_and_calendars": (
                "separately attributable case and proceeding evidence"
            ),
        },
        "complementary_source_ids": list(COMPLEMENTARY_SOURCE_IDS),
    }


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
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def _command_source_id(args: argparse.Namespace) -> str:
    if args.command in {"sources", "manifest", "probe"}:
        return CATALOG_SOURCE_ID
    if args.command in {"directory", "contacts"}:
        if args.court == "superior":
            return SUPERIOR_DIRECTORY_SOURCE_ID
        if args.court == "appeals":
            return APPEALS_DIRECTORY_SOURCE_ID
        return CATALOG_SOURCE_ID
    if args.command == "assignments":
        return SUPERIOR_DIRECTORY_SOURCE_ID
    if args.command == "data-request":
        return DATA_REQUEST_SOURCE_ID
    if args.command == "reports":
        return REPORTS_SOURCE_ID
    if args.command == "download":
        return {
            "assignments": SUPERIOR_DIRECTORY_SOURCE_ID,
            "data-request": DATA_REQUEST_SOURCE_ID,
            "reports": REPORTS_SOURCE_ID,
        }[args.collection]
    raise SelectionError(
        "unsupported_command",
        f"unsupported D.C. Courts command {args.command!r}",
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = _command_source_id(args)
    source = (
        CATALOG_METADATA
        if source_id == CATALOG_SOURCE_ID
        else SOURCE_METADATA[source_id]
    )
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
        ),
    )


def _public_error(
    error: DCCourtDirectoryDataError,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _client(args: argparse.Namespace) -> DCCourtDirectoryDataClient:
    return DCCourtDirectoryDataClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )


def _directory_courts(selection: str) -> tuple[str, ...]:
    return (
        ("superior", "appeals")
        if selection == "all"
        else (selection,)
    )


def _artifact_routes(
    args: argparse.Namespace,
    client: DCCourtDirectoryDataClient | Any,
) -> tuple[str, list[dict[str, Any]]]:
    if args.collection == "assignments":
        artifact = client.get(SUPERIOR_DIRECTORY_URL)
        return (
            SUPERIOR_DIRECTORY_SOURCE_ID,
            parse_assignment_publications(artifact),
        )
    if args.collection == "data-request":
        artifact = client.get(DATA_REQUEST_URL)
        program = parse_data_request_program(artifact)
        return DATA_REQUEST_SOURCE_ID, [
            dict(record) for record in program["artifacts"]
        ]
    artifact = client.get(REPORTS_URL)
    return REPORTS_SOURCE_ID, parse_report_catalog(artifact)


def _probe_component(
    source_id: str,
    client: DCCourtDirectoryDataClient | Any,
) -> dict[str, Any]:
    if source_id in {
        SUPERIOR_DIRECTORY_SOURCE_ID,
        APPEALS_DIRECTORY_SOURCE_ID,
    }:
        court = (
            "superior"
            if source_id == SUPERIOR_DIRECTORY_SOURCE_ID
            else "appeals"
        )
        records = collect_directory(client, court=court)
        contact = parse_contact_record(
            client.get(str(COURT_CONFIG[court]["url"])),
            court=court,
        )
        role_counts: dict[str, int] = {}
        for record in records:
            role = str(record["judicial_role"])
            role_counts[role] = role_counts.get(role, 0) + 1
        return {
            "record_kind": "source_health_check",
            "source_id": source_id,
            "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
            "status": "ok",
            "record_count": len(records),
            "role_counts": role_counts,
            "leadership_count": len(contact["leadership"]),
            "location_count": len(contact["locations"]),
        }
    if source_id == DATA_REQUEST_SOURCE_ID:
        record = parse_data_request_program(client.get(DATA_REQUEST_URL))
        return {
            "record_kind": "source_health_check",
            "source_id": source_id,
            "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
            "status": "ok",
            "artifact_kinds": sorted(
                artifact["artifact_kind"]
                for artifact in record["artifacts"]
            ),
            "published_email_variants": record[
                "published_email_variants"
            ],
        }
    if source_id == REPORTS_SOURCE_ID:
        records = parse_report_catalog(client.get(REPORTS_URL))
        return {
            "record_kind": "source_health_check",
            "source_id": source_id,
            "canonical_ref": f"DC-COURTS:PROBE:{source_id}",
            "status": "ok",
            "publication_count": len(records),
            "section_counts": {
                section: sum(
                    record["catalog_section"] == section
                    for record in records
                )
                for section in sorted(
                    {
                        str(record["catalog_section"])
                        for record in records
                    }
                )
            },
            "catalog_observation_count": sum(
                bool(record["catalog_observations"])
                for record in records
            ),
        }
    raise SelectionError(
        "unknown_component",
        f"unknown D.C. Courts component {source_id!r}",
    )


def _execute(
    args: argparse.Namespace,
    client: DCCourtDirectoryDataClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        return PublicRecordsResult.success(
            query,
            _component_records(),
            warnings=WARNINGS,
        )
    if args.command == "manifest":
        return PublicRecordsResult.success(
            query,
            [_manifest_record()],
            warnings=WARNINGS,
        )
    if args.command == "directory":
        records = []
        for court in _directory_courts(args.court):
            records.extend(
                _filter_directory(
                    collect_directory(client, court=court),
                    role=args.role,
                    query_text=args.query,
                    limit=None,
                )
            )
        if args.limit is not None:
            records = records[: args.limit]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )
    if args.command == "contacts":
        records = [
            parse_contact_record(
                client.get(str(COURT_CONFIG[court]["url"])),
                court=court,
            )
            for court in _directory_courts(args.court)
        ]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )
    if args.command == "assignments":
        records = parse_assignment_publications(
            client.get(SUPERIOR_DIRECTORY_URL)
        )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )
    if args.command == "data-request":
        return PublicRecordsResult.success(
            query,
            [parse_data_request_program(client.get(DATA_REQUEST_URL))],
            warnings=WARNINGS,
        )
    if args.command == "reports":
        records = _filter_reports(
            parse_report_catalog(client.get(REPORTS_URL)),
            section=args.section,
            year=args.year,
            query_text=args.query,
            limit=args.limit,
        )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )
    if args.command == "download":
        source_id, route_records = _artifact_routes(args, client)
        artifact_url, occurrences = _resolve_artifact(
            route_records,
            args.selector,
        )
        artifact = client.get(
            artifact_url,
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        record = _download_record(
            artifact,
            source_id=source_id,
            route_records=occurrences,
            destination=args.destination,
            overwrite=args.overwrite,
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[record["artifact_path"]],
            warnings=WARNINGS,
        )
    if args.command == "probe":
        selected = (
            list(COMPONENTS)
            if args.all or not args.component
            else list(args.component)
        )
        records = []
        errors = []
        statuses = []
        for source_id in selected:
            try:
                records.append(_probe_component(source_id, client))
            except DCCourtDirectoryDataError as error:
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
        return PublicRecordsResult.success(
            query,
            records,
            warnings=WARNINGS,
        )
    raise SelectionError(
        "unsupported_command",
        f"unsupported D.C. Courts command {args.command!r}",
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DCCourtDirectoryDataClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-scoped D.C. Courts operation."""

    query = build_query(args)
    source_client = client or _client(args)
    owns_client = client is None
    try:
        result = _execute(args, source_client, query)
    except DCCourtDirectoryDataError as error:
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
    if parsed < 1970 or parsed > 2200:
        raise argparse.ArgumentTypeError(
            "year is outside the D.C. Courts publication range"
        )
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
            "Query D.C. Courts directories, data-request routes, and "
            "aggregate report publications"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("sources", "List separately attributable source components"),
        ("manifest", "Show source roles and complementary record routes"),
    ):
        command = sub.add_parser(name, help=help_text)
        _add_runtime(command)

    command = sub.add_parser(
        "directory",
        help="List or search the current judicial directories",
    )
    command.add_argument(
        "--court",
        choices=("superior", "appeals", "all"),
        default="all",
    )
    command.add_argument(
        "--role",
        choices=("all", "chief", "associate", "magistrate", "senior"),
        default="all",
    )
    command.add_argument("--query")
    command.add_argument("--limit", type=_positive_int)
    _add_runtime(command)

    command = sub.add_parser(
        "contacts",
        help="Return court leadership, clerk, location, hours, and contacts",
    )
    command.add_argument(
        "--court",
        choices=("superior", "appeals", "all"),
        default="all",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "assignments",
        help="List current Superior Court assignment publications",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "data-request",
        help="Return the aggregate and case-level data request program",
    )
    _add_runtime(command)

    command = sub.add_parser(
        "reports",
        help="List aggregate statistics and report artifacts",
    )
    command.add_argument("--section")
    command.add_argument("--year", type=_year)
    command.add_argument("--query")
    command.add_argument("--limit", type=_positive_int)
    _add_runtime(command)

    command = sub.add_parser(
        "download",
        help="Resolve an exact live artifact and download its PDF",
    )
    command.add_argument(
        "--collection",
        choices=("assignments", "data-request", "reports"),
        required=True,
    )
    command.add_argument("selector")
    command.add_argument("destination", type=Path)
    command.add_argument("--overwrite", action="store_true")
    _add_runtime(command)

    command = sub.add_parser(
        "probe",
        help="Run source-component acceptance checks",
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
            f"D.C. Courts {args.command} ({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"D.C. Courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        identity = (
            record.get("published_name")
            or record.get("title")
            or record.get("court_name")
            or record.get("source_id")
        )
        label = (
            record.get("judicial_role")
            or record.get("report_kind")
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
