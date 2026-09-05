#!/usr/bin/env python3
"""Query official Supreme Court of Georgia decision publications.

The Court publishes several adjacent annual collections with different
publication contracts:

* opinions and noteworthy-opinion summary packets (2017-2026);
* certiorari grants with Supreme Court PDFs and Court of Appeals crosswalks;
* certiorari denial lists, which are primarily HTML-only entries; and
* discretionary/interlocutory application-grant order PDFs.

Examples:
    uv run python tools/query_georgia_supreme_publications.py sources --json
    uv run python tools/query_georgia_supreme_publications.py search Miller \
        --source us-ga-supreme-court-opinions --year 2026 --json
    uv run python tools/query_georgia_supreme_publications.py search S26G0537 \
        --source us-ga-supreme-court-certiorari-grants --json
    uv run python tools/query_georgia_supreme_publications.py detail PUB_ID \
        --source us-ga-supreme-court-opinions --year 2026 --json
    uv run python tools/query_georgia_supreme_publications.py download PDF_URL \
        /tmp/georgia-supreme-publication.pdf --json
    uv run python tools/query_georgia_supreme_publications.py probe \
        --source us-ga-supreme-court-application-grant-orders --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urljoin, urlsplit

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
        sha256_fingerprint,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


OPINION_SOURCE_ID = "us-ga-supreme-court-opinions"
CERT_GRANT_SOURCE_ID = "us-ga-supreme-court-certiorari-grants"
CERT_DENIAL_SOURCE_ID = "us-ga-supreme-court-certiorari-denials"
APPLICATION_GRANT_SOURCE_ID = (
    "us-ga-supreme-court-application-grant-orders"
)
COURT_ID = "us-ga-supreme-court"
STATE_CODE = "GA"
STATE_GEOID = "13"

BASE_URL = "https://www.gasupreme.us"
PUBLIC_DOCKET_URL = "https://pubdoc.gasupreme.gov/ui/"
CALENDAR_URL = f"{BASE_URL}/calendar-list/"
CASE_ANNOUNCEMENTS_URL = f"{BASE_URL}/2026-case-announcements/"

VERIFIED_THROUGH_YEAR = 2026
OPINION_YEARS = tuple(range(2017, VERIFIED_THROUGH_YEAR + 1))
ADJACENT_PUBLICATION_YEARS = tuple(
    range(2022, VERIFIED_THROUGH_YEAR + 1)
)

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_PDF_BYTES = 160 * 1024 * 1024
CURSOR_PREFIX = "ga-supreme-publications:v1:"
OUTPUT_SCHEMA_VERSION = "georgia-supreme-publications/1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

OPINION_VERSION_NOTICE = (
    "NOTICE: These opinions are subject to modification resulting from "
    "motions for reconsideration under Supreme Court Rule 27, the Court’s "
    "reconsideration, and editorial revisions by the Reporter of Decisions. "
    "The versions of the opinions published in the Advance Sheets for the "
    "Georgia Reports, designated here as the “Final Copy,” will replace any "
    "prior versions on the Court’s website and docket. The bound volumes of "
    "the Georgia Reports will contain the final and official text of the "
    "opinions."
)

SOURCE_METADATA = {
    OPINION_SOURCE_ID: SourceMetadata(
        source_id=OPINION_SOURCE_ID,
        name="Supreme Court of Georgia Opinions and Summaries",
        source_role="official_supreme_court_opinions_and_summary_packets",
        base_url=f"{BASE_URL}/2026-opinions/",
        dataset_id="georgia-supreme-court-opinions",
        metadata={
            "authority": "Supreme Court of Georgia",
            "coverage_years": list(OPINION_YEARS),
            "publication_components": [
                "opinion_pdf",
                "noteworthy_opinion_summary_packet",
            ],
            "authentication": "none",
        },
    ),
    CERT_GRANT_SOURCE_ID: SourceMetadata(
        source_id=CERT_GRANT_SOURCE_ID,
        name="Supreme Court of Georgia Certiorari Grants",
        source_role=(
            "official_certiorari_grant_orders_and_appellate_crosswalks"
        ),
        base_url=f"{BASE_URL}/2026-granted/",
        dataset_id="georgia-supreme-court-certiorari-grants",
        metadata={
            "authority": "Supreme Court of Georgia",
            "coverage_years": list(ADJACENT_PUBLICATION_YEARS),
            "publication_components": [
                "supreme_court_grant_pdf",
                "court_of_appeals_case_and_pdf_crosswalk",
            ],
            "authentication": "none",
        },
    ),
    CERT_DENIAL_SOURCE_ID: SourceMetadata(
        source_id=CERT_DENIAL_SOURCE_ID,
        name="Supreme Court of Georgia Certiorari Denials",
        source_role="official_certiorari_denial_annual_lists",
        base_url=f"{BASE_URL}/2026-denied/",
        dataset_id="georgia-supreme-court-certiorari-denials",
        metadata={
            "authority": "Supreme Court of Georgia",
            "coverage_years": list(ADJACENT_PUBLICATION_YEARS),
            "publication_components": [
                "html_denial_list_entry",
                "occasional_linked_supplement",
            ],
            "authentication": "none",
        },
    ),
    APPLICATION_GRANT_SOURCE_ID: SourceMetadata(
        source_id=APPLICATION_GRANT_SOURCE_ID,
        name="Supreme Court of Georgia Application Grant Orders",
        source_role=(
            "official_discretionary_and_interlocutory_application_grant_orders"
        ),
        base_url=f"{BASE_URL}/2026-discretionary/",
        dataset_id="georgia-supreme-court-application-grant-orders",
        metadata={
            "authority": "Supreme Court of Georgia",
            "coverage_years": list(ADJACENT_PUBLICATION_YEARS),
            "publication_components": [
                "discretionary_application_grant_order",
                "interlocutory_application_grant_order",
            ],
            "authentication": "none",
        },
    ),
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"court": "Supreme Court of Georgia"},
)

COMMON_WARNINGS = (
    "These are decision-publication collections, not a complete case docket "
    "or collection of the parties’ underlying filings.",
    "Each record retains its collection-specific source_id; entries in "
    "adjacent collections are not independent corroboration.",
)
SOURCE_WARNINGS = {
    OPINION_SOURCE_ID: COMMON_WARNINGS
    + (
        "Website opinion versions may change. Final Copy advance-sheet "
        "versions replace prior website and docket copies; bound Georgia "
        "Reports contain the final official text.",
    ),
    CERT_GRANT_SOURCE_ID: COMMON_WARNINGS
    + (
        "A Court of Appeals PDF linked beside a Supreme Court grant is an "
        "appellate-chain crosswalk, not a second source for the grant.",
    ),
    CERT_DENIAL_SOURCE_ID: COMMON_WARNINGS
    + (
        "The denial collection is primarily an official HTML list and usually "
        "does not publish a PDF for each entry.",
    ),
    APPLICATION_GRANT_SOURCE_ID: COMMON_WARNINGS
    + (
        "Discretionary and interlocutory grants share one order-publication "
        "contract but retain their application_type.",
    ),
}

_OFFICIAL_HOSTS = frozenset({"www.gasupreme.us", "gasupreme.us"})
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
    "cf-chl-",
)
_CASE_RE = re.compile(r"\bS\d{2}[A-Z]\d{4}\b", re.IGNORECASE)
_LOWER_CASE_RE = re.compile(r"\bA\d{2}[A-Z]\d{4}\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December"
    r")\s+(\d{1,2}),\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(
    r"\b((?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12]\d|3[01])-(?:\d{2}|\d{4}))\b"
)
_SUMMARY_RE = re.compile(
    r"summaries?\s+(?:of|for)\s+noteworthy\s+opinions",
    re.IGNORECASE,
)
_PAGE_PATH_RE = re.compile(
    r"^/((?:19|20)\d{2})-"
    r"(opinions|granted|denied|discretionary|interlocutory)/?$",
    re.IGNORECASE,
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
class ParsedPage:
    source_id: str
    publication_component: str
    publication_year: int
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    source_document_sha256: str
    source_document_bytes: int
    page_updated_at: str | None
    schema_fingerprint: str
    snapshot_fingerprint: str
    authority_notice: str | None = None


class GeorgiaSupremePublicationsError(RuntimeError):
    """Transport, access, schema, or selection failure."""

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


def _required(value: Any, field: str) -> str:
    result = _clean(value)
    if result is None:
        raise GeorgiaSupremePublicationsError(
            "source_field_missing",
            f"Georgia Supreme Court publication {field} is blank",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"field": field},
        )
    return result


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


def _official_url(value: str, *, document: bool = False) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS:
        raise GeorgiaSupremePublicationsError(
            "unrecognized_official_url",
            "Publication URL must use the Supreme Court of Georgia HTTPS host",
            category="selection",
            details={"url": value},
        )
    if document:
        if (
            not parsed.path.startswith("/wp-content/uploads/")
            or not parsed.path.casefold().endswith(".pdf")
        ):
            raise GeorgiaSupremePublicationsError(
                "unrecognized_document_url",
                "Publication document is not on the verified official PDF route",
                category="selection",
                details={"url": value},
            )
    elif _PAGE_PATH_RE.fullmatch(parsed.path) is None:
        raise GeorgiaSupremePublicationsError(
            "unrecognized_index_url",
            "Publication page is not a verified annual collection route",
            category="selection",
            details={"url": value},
        )
    return value


def _page_url(
    source_id: str,
    year: int,
    *,
    application_type: str | None = None,
) -> str:
    if source_id == OPINION_SOURCE_ID:
        slug = "opinions"
    elif source_id == CERT_GRANT_SOURCE_ID:
        slug = "granted"
    elif source_id == CERT_DENIAL_SOURCE_ID:
        slug = "denied"
    elif source_id == APPLICATION_GRANT_SOURCE_ID:
        if application_type not in {"discretionary", "interlocutory"}:
            raise GeorgiaSupremePublicationsError(
                "application_type_required",
                "Application-grant pages require discretionary or interlocutory",
                category="selection",
            )
        slug = application_type
    else:
        raise GeorgiaSupremePublicationsError(
            "unknown_source",
            "Unknown Georgia Supreme Court publication source",
            category="selection",
            details={"source_id": source_id},
        )
    return f"{BASE_URL}/{year}-{slug}/"


def _supported_years(source_id: str) -> tuple[int, ...]:
    if source_id == OPINION_SOURCE_ID:
        return OPINION_YEARS
    if source_id in SOURCE_METADATA:
        return ADJACENT_PUBLICATION_YEARS
    raise GeorgiaSupremePublicationsError(
        "unknown_source",
        "Unknown Georgia Supreme Court publication source",
        category="selection",
        details={"source_id": source_id},
    )


def _validate_year(source_id: str, year: int) -> None:
    if year not in _supported_years(source_id):
        supported = _supported_years(source_id)
        raise GeorgiaSupremePublicationsError(
            "unsupported_publication_year",
            f"{source_id} has verified annual pages for "
            f"{supported[0]}-{supported[-1]}",
            category="selection",
            details={
                "source_id": source_id,
                "year": year,
                "supported_years": list(supported),
            },
        )


class GeorgiaSupremePublicationsClient:
    """Bounded, rate-limited client with injectable transport."""

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
        document: bool = False,
    ) -> Artifact:
        _official_url(url, document=document)
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
                raise GeorgiaSupremePublicationsError(
                    "transport_error",
                    str(error),
                    category="transport",
                    retryable=True,
                    details={"url": url},
                ) from error

            status_code = int(getattr(response, "status_code", 0))
            transient = (
                status_code in self.retry_policy.retry_statuses
                or status_code == 403
            )
            if transient and attempt < self.retry_policy.max_attempts:
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            if status_code == 429:
                raise GeorgiaSupremePublicationsError(
                    "rate_limited",
                    "Publication site rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise GeorgiaSupremePublicationsError(
                    "access_restricted",
                    f"Publication site returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    retryable=status_code == 403,
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise GeorgiaSupremePublicationsError(
                    "http_status",
                    f"Publication site returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise GeorgiaSupremePublicationsError(
                    "response_too_large",
                    "Publication response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            response_url = str(getattr(response, "url", None) or url)
            _official_url(response_url, document=document)
            return Artifact(
                content=content,
                source_url=response_url,
                media_type=_media_type(response),
                headers={
                    str(key).casefold(): str(value)
                    for key, value in getattr(response, "headers", {}).items()
                },
            )
        raise GeorgiaSupremePublicationsError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": url},
        )

    def index(
        self,
        source_id: str,
        year: int,
        *,
        application_type: str | None = None,
    ) -> Artifact:
        _validate_year(source_id, year)
        return self.get(
            _page_url(
                source_id,
                year,
                application_type=application_type,
            )
        )

    def document(self, url: str) -> Artifact:
        artifact = self.get(
            _official_url(url, document=True),
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
            document=True,
        )
        if (
            artifact.media_type not in {None, "application/pdf"}
            or not artifact.content.startswith(b"%PDF-")
        ):
            raise GeorgiaSupremePublicationsError(
                "unexpected_document_response",
                "Official publication document was not a PDF",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={
                    "url": artifact.source_url,
                    "media_type": artifact.media_type,
                    "signature_hex": artifact.content[:8].hex(),
                },
            )
        return artifact


def _case_numbers(text: str, *, lower: bool = False) -> list[str]:
    pattern = _LOWER_CASE_RE if lower else _CASE_RE
    values: list[str] = []
    for match in pattern.finditer(text):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _publication_date(text: str) -> str | None:
    match = _DATE_RE.search(text)
    if match is None:
        return None
    try:
        parsed = datetime.strptime(
            " ".join(match.groups()),
            "%B %d %Y",
        )
    except ValueError:
        return None
    return parsed.date().isoformat()


def _nearest_publication_date(node: Any, root: Any) -> str:
    for candidate in node.find_all_previous(["p", "h2", "h3", "h4"]):
        if root not in candidate.parents:
            break
        value = _publication_date(candidate.get_text(" ", strip=True))
        if value:
            return value
    raise GeorgiaSupremePublicationsError(
        "publication_date_missing",
        "Publication entry has no preceding official release date",
        status=ResultStatus.SOURCE_CHANGED,
        category="source_schema",
        details={"entry": _clean(node.get_text(" ", strip=True))},
    )


def _page_root(
    artifact: Artifact,
    *,
    year: int,
    title_marker: str,
) -> tuple[BeautifulSoup, Any, str | None]:
    if artifact.media_type and "html" not in artifact.media_type:
        raise GeorgiaSupremePublicationsError(
            "unexpected_index_media_type",
            "Annual publication route did not return HTML",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    folded = page_text.casefold()
    if any(marker in folded for marker in _CHALLENGE_MARKERS):
        raise GeorgiaSupremePublicationsError(
            "human_verification",
            "Publication site returned an interactive verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    title = _clean(
        soup.select_one("h1.entry-title").get_text(" ", strip=True)
        if soup.select_one("h1.entry-title")
        else soup.title.get_text(" ", strip=True)
        if soup.title
        else None
    )
    if title is None or str(year) not in title or title_marker not in title:
        raise GeorgiaSupremePublicationsError(
            "page_marker_missing",
            "Annual publication page lacks its expected title marker",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "expected_year": year,
                "expected_marker": title_marker,
                "observed_title": title,
            },
        )
    root = soup.select_one(".post-content")
    if root is None:
        raise GeorgiaSupremePublicationsError(
            "publication_content_missing",
            "Annual publication page lacks its post-content container",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    updated = soup.select_one(".updated")
    return (
        soup,
        root,
        _clean(updated.get_text(" ", strip=True)) if updated else None,
    )


def _document_url(anchor: Any, source_url: str) -> str:
    return _official_url(
        urljoin(source_url, _required(anchor.get("href"), "document URL")),
        document=True,
    )


def _document_id(url: str) -> str:
    path = unquote(urlsplit(url).path).strip("/")
    return path


def _caption(text: str, case_numbers: Sequence[str]) -> str | None:
    if not case_numbers:
        return _clean(text)
    last = None
    for match in _CASE_RE.finditer(text):
        if match.group(0).upper() in case_numbers:
            last = match
    if last is None:
        return _clean(text)
    value = text[last.end() :].lstrip(" \t.,:;-–—")
    value = re.sub(
        r"\s*\((?:A\d{2}[A-Z]\d{4}(?:\s*,\s*)?)+\)"
        r"(?:\s*[–—-].*)?$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return _clean(value)


def _publication_identity(
    *,
    source_id: str,
    publication_type: str,
    publication_year: int,
    publication_date: str,
    case_numbers: Sequence[str],
    document_url: str | None,
    title: str | None,
) -> str:
    digest = sha256_fingerprint(
        {
            "source_id": source_id,
            "publication_type": publication_type,
            "publication_year": publication_year,
            "publication_date": publication_date,
            "case_numbers": list(case_numbers),
            "document_url": document_url,
            "title": title,
        }
    )[:20]
    prefix = {
        "opinion": "op",
        "noteworthy_summary": "summary",
        "certiorari_grant": "cert-grant",
        "certiorari_denial": "cert-denial",
        "discretionary_application_grant": "disc-grant",
        "interlocutory_application_grant": "int-grant",
    }[publication_type]
    return f"ga-sc-{prefix}-{publication_year}-{digest}"


def _case_refs(source_id: str, case_numbers: Sequence[str]) -> list[str]:
    return [
        canonical_court_ref(source_id, COURT_ID, case_number)
        for case_number in case_numbers
    ]


def _base_record(
    *,
    source_id: str,
    publication_type: str,
    record_kind: str,
    publication_year: int,
    publication_date: str,
    case_numbers: Sequence[str],
    title: str | None,
    document_url: str | None,
    artifact: Artifact,
    page_updated_at: str | None,
) -> dict[str, Any]:
    publication_id = _publication_identity(
        source_id=source_id,
        publication_type=publication_type,
        publication_year=publication_year,
        publication_date=publication_date,
        case_numbers=case_numbers,
        document_url=document_url,
        title=title,
    )
    identity_case = (
        case_numbers[0] if case_numbers else f"release-{publication_date}"
    )
    canonical_ref = canonical_court_ref(
        source_id,
        COURT_ID,
        identity_case,
        record_kind,
        publication_id,
    )
    refs = _case_refs(source_id, case_numbers)
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "publication_id": publication_id,
        "source_id": source_id,
        "record_kind": record_kind,
        "publication_type": publication_type,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "published_title": title,
        "case_numbers": list(case_numbers),
        "primary_case_number": case_numbers[0] if case_numbers else None,
        "case_count": len(case_numbers),
        "multi_case_publication": len(case_numbers) > 1,
        "case_canonical_refs": refs,
        "case_canonical_ref": refs[0] if refs else None,
        "document_url": document_url,
        "source_url": artifact.source_url,
        "index_url": artifact.source_url,
        "court": {
            "court_id": COURT_ID,
            "name": "Supreme Court of Georgia",
            "state_code": STATE_CODE,
            "court_level": "state_supreme",
            "official_url": BASE_URL,
        },
        "page_updated_at": page_updated_at,
        "source_document_sha256": artifact.sha256,
        "source_document_bytes": len(artifact.content),
        "projection": {
            "projectable_as_case": False,
            "scope": "official_decision_publication_occurrence",
        },
    }


def _revision_events(note: str | None) -> list[dict[str, Any]]:
    if note is None:
        return []
    folded = note.casefold()
    event_types = []
    if "substitute opinion" in folded:
        event_types.append("substitute_opinion_issued")
    if "reinstatement" in folded:
        event_types.append("reinstatement_issued")
    if "concurral" in folded or "concurrence" in folded:
        event_types.append("concurrence_issued")
    if "revised" in folded:
        event_types.append("revised")
    numeric_dates = _NUMERIC_DATE_RE.findall(note)
    return [
        {
            "event_type": event_type,
            "source_note_raw": note,
            "date_texts": numeric_dates,
        }
        for event_type in event_types
    ]


def _page_result(
    *,
    source_id: str,
    component: str,
    year: int,
    records: list[Mapping[str, Any]],
    artifact: Artifact,
    page_updated_at: str | None,
    authority_notice: str | None = None,
) -> ParsedPage:
    if not records:
        raise GeorgiaSupremePublicationsError(
            "publication_entries_missing",
            "Annual publication page contains no recognized entries",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "source_id": source_id,
                "component": component,
                "year": year,
                "url": artifact.source_url,
            },
        )
    document_route_shapes = set()
    for record in records:
        document_url = record.get("document_url")
        if not document_url:
            continue
        parts = urlsplit(str(document_url)).path.strip("/").split("/")
        if (
            len(parts) == 5
            and parts[:2] == ["wp-content", "uploads"]
            and parts[2].isdigit()
            and parts[3].isdigit()
        ):
            document_route_shapes.add(
                f"/wp-content/uploads/{{year}}/{{month}}/"
                f"{{filename{Path(parts[-1]).suffix.casefold()}}}"
            )
        else:
            document_route_shapes.add(urlsplit(str(document_url)).path)
    schema = {
        "component": component,
        "record_kinds": sorted(
            {str(record["record_kind"]) for record in records}
        ),
        "publication_types": sorted(
            {str(record["publication_type"]) for record in records}
        ),
        "document_route_shapes": sorted(document_route_shapes),
    }
    snapshot = [
        {
            "canonical_ref": record["canonical_ref"],
            "publication_date": record["publication_date"],
            "document_url": record.get("document_url"),
            "revision_note_raw": record.get("revision_note_raw"),
        }
        for record in records
    ]
    return ParsedPage(
        source_id=source_id,
        publication_component=component,
        publication_year=year,
        records=tuple(records),
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
        source_document_bytes=len(artifact.content),
        page_updated_at=page_updated_at,
        schema_fingerprint=sha256_fingerprint(schema),
        snapshot_fingerprint=sha256_fingerprint(snapshot),
        authority_notice=authority_notice,
    )


def parse_opinions_page(artifact: Artifact, *, year: int) -> ParsedPage:
    """Parse one official annual opinion and summary-packet page."""
    _, root, updated = _page_root(
        artifact,
        year=year,
        title_marker="Opinion",
    )
    notice_node = next(
        (
            node
            for node in root.find_all("p")
            if "Final Copy" in node.get_text(" ", strip=True)
            and "bound volumes" in node.get_text(" ", strip=True)
        ),
        None,
    )
    if notice_node is None:
        raise GeorgiaSupremePublicationsError(
            "opinion_version_notice_missing",
            "Opinion page lacks its official version-status notice",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    authority_notice = _required(
        notice_node.get_text(" ", strip=True),
        "version notice",
    )
    records: list[Mapping[str, Any]] = []
    for node in root.find_all(["p", "li"]):
        if node.name == "p":
            summary_anchor = next(
                (
                    anchor
                    for anchor in node.find_all("a", href=True)
                    if _SUMMARY_RE.search(
                        anchor.get_text(" ", strip=True)
                    )
                ),
                None,
            )
            if summary_anchor is None:
                continue
            publication_date = _publication_date(
                node.get_text(" ", strip=True)
            )
            if publication_date is None:
                publication_date = _nearest_publication_date(node, root)
            document_url = _document_url(
                summary_anchor,
                artifact.source_url,
            )
            title = _required(
                summary_anchor.get_text(" ", strip=True),
                "summary title",
            )
            record = _base_record(
                source_id=OPINION_SOURCE_ID,
                publication_type="noteworthy_summary",
                record_kind="noteworthy_opinion_summary_packet",
                publication_year=year,
                publication_date=publication_date,
                case_numbers=[],
                title=title,
                document_url=document_url,
                artifact=artifact,
                page_updated_at=updated,
            )
            record.update(
                {
                    "document": {
                        "native_document_id": _document_id(document_url),
                        "document_type": "noteworthy_opinion_summary_packet",
                        "source_url": document_url,
                        "mime_type": "application/pdf",
                        "publisher": "Supreme Court of Georgia",
                    },
                    "version_notice": authority_notice,
                    "version_state": "website_publication",
                }
            )
            records.append(record)
            continue

        anchor = next(
            (
                candidate
                for candidate in node.find_all("a", href=True)
                if _case_numbers(candidate.get_text(" ", strip=True))
            ),
            None,
        )
        if anchor is None:
            continue
        anchor_text = _required(
            anchor.get_text(" ", strip=True),
            "opinion title",
        )
        case_numbers = _case_numbers(anchor_text)
        publication_date = _nearest_publication_date(node, root)
        document_url = _document_url(anchor, artifact.source_url)
        row_text = _required(node.get_text(" ", strip=True), "opinion row")
        note = _clean(
            row_text[len(anchor_text) :]
            if row_text.startswith(anchor_text)
            else row_text.replace(anchor_text, "", 1)
        )
        record = _base_record(
            source_id=OPINION_SOURCE_ID,
            publication_type="opinion",
            record_kind="supreme_court_opinion_publication",
            publication_year=year,
            publication_date=publication_date,
            case_numbers=case_numbers,
            title=anchor_text,
            document_url=document_url,
            artifact=artifact,
            page_updated_at=updated,
        )
        record.update(
            {
                "caption": _caption(anchor_text, case_numbers),
                "revision_note_raw": note,
                "revision_events": _revision_events(note),
                "version_notice": authority_notice,
                "version_state": (
                    "website_publication_with_revision_note"
                    if note
                    else "website_publication"
                ),
                "document": {
                    "native_document_id": _document_id(document_url),
                    "document_type": "supreme_court_opinion",
                    "source_url": document_url,
                    "mime_type": "application/pdf",
                    "publisher": "Supreme Court of Georgia",
                },
            }
        )
        records.append(record)
    return _page_result(
        source_id=OPINION_SOURCE_ID,
        component="opinions_and_summaries",
        year=year,
        records=records,
        artifact=artifact,
        page_updated_at=updated,
        authority_notice=authority_notice,
    )


def _lower_appellate_documents(
    node: Any,
    *,
    source_url: str,
) -> list[dict[str, Any]]:
    by_case: dict[str, dict[str, Any]] = {}
    for case_number in _case_numbers(
        node.get_text(" ", strip=True),
        lower=True,
    ):
        by_case[case_number] = {
            "case_number": case_number,
            "document_url": None,
            "native_document_id": None,
            "document_type": "court_of_appeals_opinion_crosswalk",
            "originating_court": "Court of Appeals of Georgia",
            "republication_context": (
                "linked by the Supreme Court on its certiorari publication"
            ),
        }
    for anchor in node.find_all("a", href=True):
        anchor_cases = _case_numbers(
            anchor.get_text(" ", strip=True),
            lower=True,
        )
        if not anchor_cases:
            continue
        document_url = _document_url(anchor, source_url)
        for case_number in anchor_cases:
            by_case[case_number].update(
                {
                    "document_url": document_url,
                    "native_document_id": _document_id(document_url),
                }
            )
    return list(by_case.values())


def parse_certiorari_grants_page(
    artifact: Artifact,
    *,
    year: int,
) -> ParsedPage:
    """Parse linked certiorari grants and Court of Appeals crosswalks."""
    _, root, updated = _page_root(
        artifact,
        year=year,
        title_marker="Granted",
    )
    records: list[Mapping[str, Any]] = []
    for node in root.find_all("li"):
        supreme_anchor = next(
            (
                anchor
                for anchor in node.find_all("a", href=True)
                if _case_numbers(anchor.get_text(" ", strip=True))
            ),
            None,
        )
        if supreme_anchor is None:
            continue
        title = _required(
            supreme_anchor.get_text(" ", strip=True),
            "certiorari grant title",
        )
        case_numbers = _case_numbers(title)
        document_url = _document_url(supreme_anchor, artifact.source_url)
        publication_date = _nearest_publication_date(node, root)
        lower_documents = _lower_appellate_documents(
            node,
            source_url=artifact.source_url,
        )
        record = _base_record(
            source_id=CERT_GRANT_SOURCE_ID,
            publication_type="certiorari_grant",
            record_kind="supreme_court_certiorari_grant_publication",
            publication_year=year,
            publication_date=publication_date,
            case_numbers=case_numbers,
            title=title,
            document_url=document_url,
            artifact=artifact,
            page_updated_at=updated,
        )
        record.update(
            {
                "caption": _caption(title, case_numbers),
                "disposition": "granted",
                "supreme_court_document": {
                    "native_document_id": _document_id(document_url),
                    "document_type": "certiorari_grant_order",
                    "source_url": document_url,
                    "mime_type": "application/pdf",
                    "publisher": "Supreme Court of Georgia",
                },
                "lower_appellate_cases": lower_documents,
                "appellate_chain": {
                    "supreme_court_case_numbers": case_numbers,
                    "court_of_appeals_case_numbers": [
                        item["case_number"] for item in lower_documents
                    ],
                },
            }
        )
        records.append(record)
    return _page_result(
        source_id=CERT_GRANT_SOURCE_ID,
        component="certiorari_grants",
        year=year,
        records=records,
        artifact=artifact,
        page_updated_at=updated,
    )


def parse_certiorari_denials_page(
    artifact: Artifact,
    *,
    year: int,
) -> ParsedPage:
    """Parse the official annual HTML certiorari-denial list."""
    _, root, updated = _page_root(
        artifact,
        year=year,
        title_marker="Denied",
    )
    records: list[Mapping[str, Any]] = []
    for node in root.find_all("li"):
        row_text = _clean(node.get_text(" ", strip=True))
        if row_text is None:
            continue
        case_numbers = _case_numbers(row_text)
        if not case_numbers:
            continue
        publication_date = _nearest_publication_date(node, root)
        lower_documents = _lower_appellate_documents(
            node,
            source_url=artifact.source_url,
        )
        supreme_anchor = next(
            (
                anchor
                for anchor in node.find_all("a", href=True)
                if _case_numbers(anchor.get_text(" ", strip=True))
            ),
            None,
        )
        document_url = (
            _document_url(supreme_anchor, artifact.source_url)
            if supreme_anchor is not None
            else None
        )
        note_match = re.search(r"\s+[–—-]\s+(.+)$", row_text)
        note = _clean(note_match.group(1)) if note_match else None
        record = _base_record(
            source_id=CERT_DENIAL_SOURCE_ID,
            publication_type="certiorari_denial",
            record_kind="supreme_court_certiorari_denial_list_entry",
            publication_year=year,
            publication_date=publication_date,
            case_numbers=case_numbers,
            title=row_text,
            document_url=document_url,
            artifact=artifact,
            page_updated_at=updated,
        )
        record.update(
            {
                "caption": _caption(row_text, case_numbers),
                "disposition": "denied",
                "list_entry_has_document": document_url is not None,
                "supplemental_document": (
                    {
                        "native_document_id": _document_id(document_url),
                        "document_type": "denial_related_publication",
                        "source_url": document_url,
                        "mime_type": "application/pdf",
                        "publisher": "Supreme Court of Georgia",
                    }
                    if document_url
                    else None
                ),
                "lower_appellate_cases": lower_documents,
                "appellate_chain": {
                    "supreme_court_case_numbers": case_numbers,
                    "court_of_appeals_case_numbers": [
                        item["case_number"] for item in lower_documents
                    ],
                },
                "revision_note_raw": note,
                "revision_events": _revision_events(note),
            }
        )
        records.append(record)
    return _page_result(
        source_id=CERT_DENIAL_SOURCE_ID,
        component="certiorari_denials",
        year=year,
        records=records,
        artifact=artifact,
        page_updated_at=updated,
    )


def parse_application_grants_page(
    artifact: Artifact,
    *,
    year: int,
    application_type: str,
) -> ParsedPage:
    """Parse discretionary or interlocutory application-grant PDFs."""
    marker = (
        "Discretionary"
        if application_type == "discretionary"
        else "Interlocutory"
        if application_type == "interlocutory"
        else None
    )
    if marker is None:
        raise GeorgiaSupremePublicationsError(
            "invalid_application_type",
            "Application type must be discretionary or interlocutory",
            category="selection",
        )
    _, root, updated = _page_root(
        artifact,
        year=year,
        title_marker=marker,
    )
    records: list[Mapping[str, Any]] = []
    for node in root.find_all("li"):
        anchor = next(
            (
                candidate
                for candidate in node.find_all("a", href=True)
                if _case_numbers(candidate.get_text(" ", strip=True))
            ),
            None,
        )
        if anchor is None:
            continue
        title = _required(
            anchor.get_text(" ", strip=True),
            f"{application_type} grant title",
        )
        case_numbers = _case_numbers(title)
        publication_date = _nearest_publication_date(node, root)
        document_url = _document_url(anchor, artifact.source_url)
        publication_type = f"{application_type}_application_grant"
        record = _base_record(
            source_id=APPLICATION_GRANT_SOURCE_ID,
            publication_type=publication_type,
            record_kind="supreme_court_application_grant_order",
            publication_year=year,
            publication_date=publication_date,
            case_numbers=case_numbers,
            title=title,
            document_url=document_url,
            artifact=artifact,
            page_updated_at=updated,
        )
        record.update(
            {
                "caption": _caption(title, case_numbers),
                "application_type": application_type,
                "disposition": "granted",
                "document": {
                    "native_document_id": _document_id(document_url),
                    "document_type": (
                        f"{application_type}_application_grant_order"
                    ),
                    "source_url": document_url,
                    "mime_type": "application/pdf",
                    "publisher": "Supreme Court of Georgia",
                },
            }
        )
        records.append(record)
    return _page_result(
        source_id=APPLICATION_GRANT_SOURCE_ID,
        component=f"{application_type}_application_grants",
        year=year,
        records=records,
        artifact=artifact,
        page_updated_at=updated,
    )


def parse_index_page(
    artifact: Artifact,
    *,
    source_id: str,
    year: int,
    application_type: str | None = None,
) -> ParsedPage:
    """Dispatch one verified annual page to its component parser."""
    _validate_year(source_id, year)
    expected_url = _page_url(
        source_id,
        year,
        application_type=application_type,
    )
    expected_path = urlsplit(expected_url).path
    if urlsplit(artifact.source_url).path != expected_path:
        raise GeorgiaSupremePublicationsError(
            "annual_route_mismatch",
            "Annual publication response URL does not match the requested route",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "requested_url": expected_url,
                "response_url": artifact.source_url,
            },
        )
    if source_id == OPINION_SOURCE_ID:
        return parse_opinions_page(artifact, year=year)
    if source_id == CERT_GRANT_SOURCE_ID:
        return parse_certiorari_grants_page(artifact, year=year)
    if source_id == CERT_DENIAL_SOURCE_ID:
        return parse_certiorari_denials_page(artifact, year=year)
    return parse_application_grants_page(
        artifact,
        year=year,
        application_type=_required(
            application_type,
            "application type",
        ),
    )


def _source_inventory_record(source_id: str) -> dict[str, Any]:
    source = SOURCE_METADATA[source_id]
    years = _supported_years(source_id)
    if source_id == OPINION_SOURCE_ID:
        publication_types = ["opinion", "noteworthy_summary"]
        routes = ["/{year}-opinions/"]
        document_contract = "direct_official_pdf"
    elif source_id == CERT_GRANT_SOURCE_ID:
        publication_types = ["certiorari_grant"]
        routes = ["/{year}-granted/"]
        document_contract = "supreme_pdf_plus_appellate_crosswalk_pdf"
    elif source_id == CERT_DENIAL_SOURCE_ID:
        publication_types = ["certiorari_denial"]
        routes = ["/{year}-denied/"]
        document_contract = "html_list_with_occasional_linked_supplement"
    else:
        publication_types = [
            "discretionary_application_grant",
            "interlocutory_application_grant",
        ]
        routes = [
            "/{year}-discretionary/",
            "/{year}-interlocutory/",
        ]
        document_contract = "direct_official_order_pdf"
    return {
        "record_kind": "source_manifest",
        "source_id": source_id,
        "name": source.name,
        "source_role": source.source_role,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "authority": "Supreme Court of Georgia",
        "verified_coverage": {
            "first_year": years[0],
            "through_year": years[-1],
            "years": list(years),
        },
        "annual_routes": routes,
        "publication_types": publication_types,
        "document_contract": document_contract,
        "operations": [
            "manifest",
            "search",
            "detail",
            "download",
            "probe",
        ],
        "opinion_version_notice": (
            OPINION_VERSION_NOTICE
            if source_id == OPINION_SOURCE_ID
            else None
        ),
        "separate_attribution": {
            "constituent_source_ids": sorted(SOURCE_METADATA),
            "cross_collection_matches_are_not_independent_corroboration": True,
        },
        "complements": [
            {
                "source_id": "us-ga-supreme-court-public-docket",
                "url": PUBLIC_DOCKET_URL,
                "adds": "recent case, filing, judgment, and attorney metadata",
            },
            {
                "name": "Supreme Court oral argument calendars",
                "url": CALENDAR_URL,
                "adds": "scheduled argument context",
                "separate_publication_contract": True,
            },
            {
                "name": "Supreme Court case announcements",
                "url": CASE_ANNOUNCEMENTS_URL,
                "adds": "argument and decision announcement context",
                "separate_publication_contract": True,
            },
        ],
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
        "destination",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = getattr(args, "source", OPINION_SOURCE_ID)
    return PublicRecordsQuery(
        source=SOURCE_METADATA[source_id],
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
    error: GeorgiaSupremePublicationsError,
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
        warnings=SOURCE_WARNINGS[query.source.source_id],
    )


def _requested_years(args: argparse.Namespace) -> list[int]:
    values = list(getattr(args, "year", None) or [VERIFIED_THROUGH_YEAR])
    years = sorted(set(values), reverse=True)
    for year in years:
        _validate_year(args.source, year)
    return years


def _application_types(args: argparse.Namespace) -> tuple[str, ...]:
    if args.source != APPLICATION_GRANT_SOURCE_ID:
        return ()
    value = getattr(args, "application_type", "both")
    if value == "both":
        return ("discretionary", "interlocutory")
    return (value,)


def _fetch_snapshot(
    client: GeorgiaSupremePublicationsClient | Any,
    args: argparse.Namespace,
) -> tuple[list[Mapping[str, Any]], list[ParsedPage], str]:
    pages: list[ParsedPage] = []
    for year in _requested_years(args):
        if args.source == APPLICATION_GRANT_SOURCE_ID:
            for application_type in _application_types(args):
                artifact = client.index(
                    args.source,
                    year,
                    application_type=application_type,
                )
                pages.append(
                    parse_index_page(
                        artifact,
                        source_id=args.source,
                        year=year,
                        application_type=application_type,
                    )
                )
        else:
            artifact = client.index(args.source, year)
            pages.append(
                parse_index_page(
                    artifact,
                    source_id=args.source,
                    year=year,
                )
            )
    records = [
        record for page in pages for record in page.records
    ]
    records.sort(
        key=lambda record: (
            str(record["publication_date"]),
            str(record["canonical_ref"]),
        ),
        reverse=True,
    )
    snapshot_fingerprint = sha256_fingerprint(
        [
            {
                "source_url": page.source_url,
                "snapshot_fingerprint": page.snapshot_fingerprint,
            }
            for page in pages
        ]
    )
    return records, pages, snapshot_fingerprint


def _filter_records(
    records: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> list[Mapping[str, Any]]:
    query = _clean(getattr(args, "query", None))
    case_number = _clean(getattr(args, "case_number", None))
    publication_types = set(
        getattr(args, "publication_type", None) or []
    )
    date_from = _clean(getattr(args, "date_from", None))
    date_to = _clean(getattr(args, "date_to", None))
    filtered: list[Mapping[str, Any]] = []
    for record in records:
        if publication_types and record["publication_type"] not in publication_types:
            continue
        if date_from and str(record["publication_date"]) < date_from:
            continue
        if date_to and str(record["publication_date"]) > date_to:
            continue
        all_cases = [
            *record.get("case_numbers", []),
            *[
                item["case_number"]
                for item in record.get("lower_appellate_cases", [])
            ],
        ]
        if case_number and case_number.upper() not in {
            str(value).upper() for value in all_cases
        }:
            continue
        if query not in {None, "*"}:
            searchable = canonical_json(
                {
                    "title": record.get("published_title"),
                    "caption": record.get("caption"),
                    "case_numbers": all_cases,
                    "revision_note": record.get("revision_note_raw"),
                    "publication_type": record.get("publication_type"),
                }
            ).casefold()
            if query.casefold() not in searchable:
                continue
        filtered.append(record)
    return filtered


def _query_identity(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "source": args.source,
        "years": _requested_years(args),
        "application_types": list(_application_types(args)),
        "query": _clean(getattr(args, "query", None)),
        "case_number": _clean(getattr(args, "case_number", None)),
        "publication_types": sorted(
            getattr(args, "publication_type", None) or []
        ),
        "date_from": _clean(getattr(args, "date_from", None)),
        "date_to": _clean(getattr(args, "date_to", None)),
    }


def _encode_cursor(
    *,
    query_key: str,
    snapshot_fingerprint: str,
    offset: int,
    boundary_ref: str,
) -> str:
    payload = canonical_json(
        {
            "query_key": query_key,
            "snapshot_fingerprint": snapshot_fingerprint,
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
    snapshot_fingerprint: str,
    records: Sequence[Mapping[str, Any]],
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise GeorgiaSupremePublicationsError(
            "invalid_cursor",
            "Georgia Supreme publication cursor prefix is invalid",
            category="selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeorgiaSupremePublicationsError(
            "invalid_cursor",
            "Georgia Supreme publication cursor is malformed",
            category="selection",
        ) from error
    if not isinstance(payload, Mapping):
        raise GeorgiaSupremePublicationsError(
            "invalid_cursor",
            "Georgia Supreme publication cursor payload is invalid",
            category="selection",
        )
    if payload.get("query_key") != query_key:
        raise GeorgiaSupremePublicationsError(
            "cursor_query_mismatch",
            "Georgia Supreme publication cursor belongs to another query",
            category="selection",
        )
    if payload.get("snapshot_fingerprint") != snapshot_fingerprint:
        raise GeorgiaSupremePublicationsError(
            "cursor_source_changed",
            "Annual publication snapshot changed after cursor issue",
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
        raise GeorgiaSupremePublicationsError(
            "invalid_cursor",
            "Georgia Supreme publication cursor offset is invalid",
            category="selection",
        )
    if payload.get("boundary_ref") != records[offset - 1]["canonical_ref"]:
        raise GeorgiaSupremePublicationsError(
            "cursor_boundary_changed",
            "Annual publication cursor boundary changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return offset


def _page_records(
    records: Sequence[Mapping[str, Any]],
    *,
    args: argparse.Namespace,
    snapshot_fingerprint: str,
) -> tuple[list[Mapping[str, Any]], str | None]:
    query_key = sha256_fingerprint(_query_identity(args))
    offset = _decode_cursor(
        getattr(args, "cursor", None),
        query_key=query_key,
        snapshot_fingerprint=snapshot_fingerprint,
        records=records,
    )
    selected = list(records[offset : offset + args.limit])
    next_offset = offset + len(selected)
    next_cursor = None
    if selected and next_offset < len(records):
        next_cursor = _encode_cursor(
            query_key=query_key,
            snapshot_fingerprint=snapshot_fingerprint,
            offset=next_offset,
            boundary_ref=str(selected[-1]["canonical_ref"]),
        )
    return selected, next_cursor


def _find_detail(
    records: Sequence[Mapping[str, Any]],
    identifier: str,
) -> Mapping[str, Any]:
    exact = [
        record
        for record in records
        if identifier
        in {
            record["publication_id"],
            record["canonical_ref"],
            record.get("document_url"),
        }
    ]
    if len(exact) == 1:
        return exact[0]
    folded = identifier.casefold()
    by_case = [
        record
        for record in records
        if folded
        in {
            str(value).casefold()
            for value in [
                *record.get("case_numbers", []),
                *[
                    item["case_number"]
                    for item in record.get("lower_appellate_cases", [])
                ],
            ]
        }
    ]
    if len(by_case) == 1:
        return by_case[0]
    if len(by_case) > 1:
        raise GeorgiaSupremePublicationsError(
            "ambiguous_publication_identifier",
            "Case number matches more than one publication occurrence",
            category="selection",
            details={
                "identifier": identifier,
                "publication_ids": [
                    record["publication_id"] for record in by_case
                ],
            },
        )
    raise GeorgiaSupremePublicationsError(
        "publication_not_found",
        "No publication matches the exact identifier in the selected snapshot",
        status=ResultStatus.NO_RESULTS,
        category="selection",
        details={"identifier": identifier},
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    status_value = str(
        decision.get("result_status")
        or decision.get("status")
        or (
            ResultStatus.HUMAN_REQUIRED.value
            if decision.get("automation_disposition") == "human_required"
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
        warnings=SOURCE_WARNINGS[query.source.source_id],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: GeorgiaSupremePublicationsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    source_id = query.source.source_id
    warnings = SOURCE_WARNINGS[source_id]
    if access_decision is not None and not access_decision.get(
        "allowed",
        False,
    ):
        result = _decision_failure(query, access_decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), source_id, None)
        return result

    source_client = client or GeorgiaSupremePublicationsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                [
                    _source_inventory_record(item)
                    for item in sorted(SOURCE_METADATA)
                ],
                warnings=warnings,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_source_inventory_record(args.source)],
                warnings=warnings,
            )
        elif args.command in {"search", "detail"}:
            records, pages, snapshot_fingerprint = _fetch_snapshot(
                source_client,
                args,
            )
            filtered = _filter_records(records, args)
            raw_refs = [page.source_url for page in pages]
            if args.command == "search":
                selected, next_cursor = _page_records(
                    filtered,
                    args=args,
                    snapshot_fingerprint=snapshot_fingerprint,
                )
                result = PublicRecordsResult.success(
                    query,
                    selected,
                    next_cursor=next_cursor,
                    raw_artifact_refs=raw_refs,
                    warnings=warnings,
                )
            else:
                detail = _find_detail(filtered, args.identifier)
                result = PublicRecordsResult.success(
                    query,
                    [detail],
                    raw_artifact_refs=raw_refs,
                    warnings=warnings,
                )
        elif args.command == "download":
            artifact = source_client.document(args.document_url)
            destination: Path | None = None
            if args.destination:
                destination = Path(args.destination).expanduser()
                if destination.exists() and not args.overwrite:
                    raise GeorgiaSupremePublicationsError(
                        "destination_exists",
                        f"destination exists; pass --overwrite: {destination}",
                        category="local_io",
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(artifact.content)
            document_id = _document_id(artifact.source_url)
            canonical_ref = canonical_court_ref(
                source_id,
                COURT_ID,
                f"document-{hashlib.sha256(artifact.source_url.encode()).hexdigest()[:16]}",
                "publication_document",
                artifact.sha256,
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": canonical_ref,
                        "evidence_ref": canonical_ref,
                        "source_id": source_id,
                        "record_kind": "publication_document_download",
                        "native_document_id": document_id,
                        "document_url": artifact.source_url,
                        "source_file_name": Path(
                            unquote(urlsplit(artifact.source_url).path)
                        ).name,
                        "mime_type": "application/pdf",
                        "byte_count": len(artifact.content),
                        "sha256": artifact.sha256,
                        "storage_path": (
                            str(destination.resolve())
                            if destination
                            else None
                        ),
                        "download_status": (
                            "saved" if destination else "verified"
                        ),
                    }
                ],
                raw_artifact_refs=(
                    [str(destination.resolve())] if destination else []
                ),
                warnings=warnings,
            )
        elif args.command == "probe":
            _, pages, _ = _fetch_snapshot(source_client, args)
            probes = []
            for page in pages:
                document_record = next(
                    (
                        record
                        for record in page.records
                        if record.get("document_url")
                    ),
                    None,
                )
                document_probe = None
                if document_record is not None:
                    document = source_client.document(
                        str(document_record["document_url"])
                    )
                    document_probe = {
                        "document_url": document.source_url,
                        "mime_type": document.media_type,
                        "byte_count": len(document.content),
                        "sha256": document.sha256,
                    }
                probes.append(
                    {
                        "record_kind": "source_probe",
                        "source_id": source_id,
                        "status": "ok",
                        "publication_component": (
                            page.publication_component
                        ),
                        "publication_year": page.publication_year,
                        "record_count": len(page.records),
                        "document_record_count": sum(
                            1
                            for record in page.records
                            if record.get("document_url")
                        ),
                        "source_url": page.source_url,
                        "source_document_sha256": (
                            page.source_document_sha256
                        ),
                        "schema_fingerprint": page.schema_fingerprint,
                        "snapshot_fingerprint": (
                            page.snapshot_fingerprint
                        ),
                        "page_updated_at": page.page_updated_at,
                        "document_probe": document_probe,
                        "requests_made": (
                            2 if document_probe is not None else 1
                        ),
                    }
                )
            result = PublicRecordsResult.success(
                query,
                probes,
                raw_artifact_refs=[
                    page.source_url for page in pages
                ],
                warnings=warnings,
            )
        else:
            raise ValueError(
                f"unsupported Georgia Supreme publication command "
                f"{args.command!r}"
            )
    except GeorgiaSupremePublicationsError as error:
        if error.status == ResultStatus.NO_RESULTS:
            result = PublicRecordsResult.success(
                query,
                [],
                warnings=warnings,
            )
        else:
            result = _failure(query, error)
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
        if client is None:
            source_client.close()

    if log_results:
        log_search(
            canonical_json(query.to_dict()),
            source_id,
            len(result.records),
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


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_METADATA),
        default=OPINION_SOURCE_ID,
    )


def _add_snapshot_selection(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        help="Annual page year; repeat to combine snapshots (default: 2026)",
    )
    parser.add_argument(
        "--application-type",
        choices=("both", "discretionary", "interlocutory"),
        default="both",
    )
    parser.add_argument(
        "--publication-type",
        action="append",
        choices=(
            "opinion",
            "noteworthy_summary",
            "certiorari_grant",
            "certiorari_denial",
            "discretionary_application_grant",
            "interlocutory_application_grant",
        ),
    )
    parser.add_argument("--case-number")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Supreme Court of Georgia opinions, certiorari "
            "lists, and application-grant order publications"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the separately attributed publication components",
    )
    sources.set_defaults(source=OPINION_SOURCE_ID)
    _add_runtime(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Describe one annual publication contract",
    )
    _add_source(manifest)
    _add_runtime(manifest)

    search = sub.add_parser(
        "search",
        help="Search and page over selected parsed annual snapshots",
    )
    search.add_argument("query", nargs="?", default="*")
    _add_snapshot_selection(search)
    search.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    search.add_argument("--cursor")
    _add_runtime(search)

    detail = sub.add_parser(
        "detail",
        help="Return exact metadata for one publication identity",
    )
    detail.add_argument("identifier")
    detail.set_defaults(query="*")
    _add_snapshot_selection(detail)
    _add_runtime(detail)

    download = sub.add_parser(
        "download",
        help="Verify or save one exact official publication PDF",
    )
    download.add_argument("document_url")
    download.add_argument("destination", nargs="?")
    download.add_argument("--overwrite", action="store_true")
    _add_source(download)
    _add_runtime(download)

    probe = sub.add_parser(
        "probe",
        help="Validate bounded annual index and representative PDF routes",
    )
    _add_snapshot_selection(probe)
    _add_runtime(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Georgia Supreme publications {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Georgia Supreme publications {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    for value in (
        getattr(args, "date_from", None),
        getattr(args, "date_to", None),
    ):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                parser.error("date filters must use YYYY-MM-DD")
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        sys.exit(1)


if __name__ == "__main__":
    main()
