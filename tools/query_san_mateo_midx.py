#!/usr/bin/env python3
"""Query San Mateo Superior Court's public MIDX case index.

MIDX is an anonymous, server-rendered index covering appeals, civil, criminal,
family law, probate, and small claims cases. It supports exact case-number,
person, business, and five-calendar-day filing-date searches. The separate
Odyssey portal provides fuller case information.

Examples:
    uv run python tools/query_san_mateo_midx.py case PRO116668-B --json
    uv run python tools/query_san_mateo_midx.py search \
        --first-name Frank --last-name Creer --output creer.json
    uv run python tools/query_san_mateo_midx.py search \
        --filed-from 2026-07-20 --filed-to 2026-07-24 --limit 100
    uv run python tools/query_san_mateo_midx.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ca-san-mateo-midx"
STATE_CODE = "CA"
COUNTY_GEOID = "06081"
COURT_ID = "ca-san-mateo-superior-court"
COURT_NAME = "Superior Court of California, County of San Mateo"
BASE_URL = "https://web.sanmateocourt.org"
LANDING_URL = f"{BASE_URL}/midx/"
LOOKUP_URL = f"{BASE_URL}/midx/lookup.php"
ODYSSEY_URL = "https://odyportal-ext.sanmateocourt.org/portal-external"
PROBE_CASE_NUMBER = "PRO116668-B"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
BROWSER_HELPER_PATH = Path(__file__).with_name(
    "_san_mateo_midx_browser_helper.js"
)

SOURCE_WARNINGS = (
    "MIDX provides index information rather than the official court record.",
    "The separate Odyssey portal provides additional public case information.",
    "For criminal cases filed before 1993, the court directs researchers to "
    "the criminal clerk's office.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="San Mateo Superior Court MIDX",
    source_role="county_superior_court_case_and_party_index",
    base_url=LANDING_URL,
    dataset_id="san-mateo-midx",
    metadata={
        "authority": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_id": COURT_ID,
        "authentication": "none",
        "platform_family": "san_mateo_midx",
        "coverage": [
            "appeals",
            "civil",
            "criminal",
            "family_law",
            "probate",
            "small_claims",
        ],
        "lookup_url": LOOKUP_URL,
        "odyssey_url": ODYSSEY_URL,
        "native_date_range_days": 5,
        "native_result_ceiling": None,
    },
)


class MIDXError(RuntimeError):
    """Source, transport, or query error with result-envelope semantics."""

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


class MIDXSelectionError(MIDXError):
    """The requested selector does not match MIDX's native search contract."""

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


class MIDXSourceChangedError(MIDXError):
    """The official page no longer matches the verified HTML contract."""

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
class MIDXForm:
    name: str
    action_url: str
    method: str
    search_type: str
    hidden_values: Mapping[str, str]
    visible_fields: tuple[str, ...]


@dataclass(frozen=True)
class MIDXBootstrap:
    forms: Mapping[str, MIDXForm]
    current_as_of: str | None
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class MIDXRow:
    case_number: str
    party_name: str
    party_type: str | None
    filing_date: str | None
    filing_date_raw: str | None
    index_info_url: str | None
    source_url: str
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "party_name": self.party_name,
            "party_type": self.party_type,
            "filing_date": self.filing_date,
            "filing_date_raw": self.filing_date_raw,
            "index_info_url": self.index_info_url,
            "source_url": self.source_url,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class MIDXPage:
    rows: tuple[MIDXRow, ...]
    total_reported: int
    current_page: int
    total_pages: int
    next_url: str | None
    authoritative_empty: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class MIDXSearchResult:
    rows: tuple[MIDXRow, ...]
    total_reported: int
    source_total_pages: int
    pages_fetched: int
    current_as_of: str | None
    schema_fingerprint: str
    source_url: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise MIDXSourceChangedError(
            "required_field_missing",
            f"MIDX result lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _iso_date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    raise MIDXSourceChangedError(
        "filing_date_format_changed",
        f"MIDX returned an unrecognized filing date: {normalized}",
        details={"value": normalized},
    )


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (_text(value) or "").casefold())


def _same_origin(first: str, second: str) -> bool:
    first_url = urlparse(first)
    second_url = urlparse(second)
    return (
        first_url.scheme.casefold(),
        first_url.netloc.casefold(),
    ) == (
        second_url.scheme.casefold(),
        second_url.netloc.casefold(),
    )


def parse_bootstrap(
    html: str,
    *,
    source_url: str = LANDING_URL,
) -> MIDXBootstrap:
    """Parse the four tokenized MIDX search forms."""

    soup = BeautifulSoup(html, "html.parser")
    expected = {
        "casenumber": {"casenumber"},
        "partyname": {"firstname", "lastname"},
        "businessname": {"businessname"},
        "filedate": {"df", "dt"},
    }
    forms: dict[str, MIDXForm] = {}
    for form_tag in soup.find_all("form"):
        if not isinstance(form_tag, Tag):
            continue
        search_type_input = form_tag.find(
            "input",
            attrs={"name": "searchtype"},
        )
        if not isinstance(search_type_input, Tag):
            continue
        search_type = _text(search_type_input.get("value"))
        if search_type not in expected:
            continue
        name = _text(form_tag.get("name") or form_tag.get("id"))
        method = (_text(form_tag.get("method")) or "get").lower()
        action_url = urljoin(
            source_url,
            _text(form_tag.get("action")) or source_url,
        )
        hidden: dict[str, str] = {}
        visible: list[str] = []
        for input_tag in form_tag.find_all("input"):
            if not isinstance(input_tag, Tag):
                continue
            field_name = _text(input_tag.get("name"))
            if field_name is None:
                continue
            field_type = (
                _text(input_tag.get("type")) or "text"
            ).casefold()
            if field_type == "hidden":
                hidden[field_name] = _text(input_tag.get("value")) or ""
            elif field_type not in {"submit", "reset", "button"}:
                visible.append(field_name)
        missing_fields = expected[search_type] - set(visible)
        if (
            name is None
            or method != "post"
            or "ct" not in hidden
            or missing_fields
            or not _same_origin(LANDING_URL, action_url)
        ):
            raise MIDXSourceChangedError(
                "search_form_changed",
                f"MIDX {search_type} form no longer matches its contract",
                details={
                    "form_name": name,
                    "method": method,
                    "action_url": action_url,
                    "hidden_fields": sorted(hidden),
                    "visible_fields": sorted(visible),
                    "missing_fields": sorted(missing_fields),
                },
            )
        forms[search_type] = MIDXForm(
            name=name,
            action_url=action_url,
            method=method,
            search_type=search_type,
            hidden_values=hidden,
            visible_fields=tuple(sorted(set(visible))),
        )

    missing_forms = sorted(set(expected) - set(forms))
    if missing_forms:
        raise MIDXSourceChangedError(
            "search_forms_missing",
            "MIDX landing page lacks one or more verified search forms",
            details={"missing_search_types": missing_forms},
        )

    page_text = soup.get_text(" ", strip=True)
    current_match = re.search(
        r"information\s+provided\s+is\s+current\s+as\s+of\s+"
        r"(.+?(?:AM|PM))\b",
        page_text,
        flags=re.IGNORECASE,
    )
    current_as_of = _text(current_match.group(1)) if current_match else None
    schema = {
        search_type: {
            "name": form.name,
            "method": form.method,
            "action_path": urlparse(form.action_url).path,
            "hidden_fields": sorted(form.hidden_values),
            "visible_fields": list(form.visible_fields),
        }
        for search_type, form in sorted(forms.items())
    }
    return MIDXBootstrap(
        forms=forms,
        current_as_of=current_as_of,
        schema_fingerprint=schema_fingerprint(schema),
        source_url=source_url,
    )


_HEADER_ALIASES = {
    "casenumber": "case_number",
    "partyname": "party_name",
    "type": "party_type",
    "filingdate": "filing_date",
    "indexinfo": "index_info",
    "moreinfo": "index_info",
}


def _pagination(
    soup: BeautifulSoup,
    *,
    source_url: str,
) -> tuple[int, int, str | None]:
    pager: Tag | None = None
    for candidate in soup.find_all(["ul", "nav", "div"]):
        if not isinstance(candidate, Tag):
            continue
        candidate_text = _text(candidate.get_text(" ", strip=True)) or ""
        if candidate_text.casefold().startswith("page"):
            pager = candidate
            break
    if pager is None:
        return 1, 1, None

    pager_text = _text(pager.get_text(" ", strip=True)) or ""
    total_match = re.search(
        r"last\s+of\s+([\d,]+)",
        pager_text,
        flags=re.IGNORECASE,
    )
    current_page: int | None = None
    for node in pager.find_all(["li", "span", "strong"]):
        if not isinstance(node, Tag) or node.find("a") is not None:
            continue
        node_text = _text(node.get_text(" ", strip=True))
        if node_text and node_text.isdigit():
            current_page = int(node_text)
            if "current" in {
                str(value).casefold()
                for value in (node.get("class") or [])
            }:
                break
    if current_page is None:
        current_match = re.search(r"\bpage\s*:?\s*(\d+)\b", pager_text, re.I)
        current_page = int(current_match.group(1)) if current_match else 1

    numeric_links: dict[int, str] = {}
    next_url: str | None = None
    numeric_pages = [current_page]
    for link in pager.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        label = _text(link.get_text(" ", strip=True)) or ""
        target = urljoin(source_url, str(link.get("href")))
        if label.isdigit():
            page_number = int(label)
            numeric_pages.append(page_number)
            numeric_links[page_number] = target
        elif label.casefold() in {">>", "next", "next >", "next »", "»"}:
            next_url = target

    total_pages = (
        int(total_match.group(1).replace(",", ""))
        if total_match
        else max(numeric_pages)
    )
    direct_next = numeric_links.get(current_page + 1)
    if direct_next is not None:
        next_url = direct_next
    return current_page, total_pages, next_url


def parse_results_page(
    html: str,
    *,
    source_url: str = LOOKUP_URL,
) -> MIDXPage:
    """Parse one MIDX result page and its opaque continuation link."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    no_results = bool(
        re.search(r"\bno\s+record(?:s)?\s+found\b", page_text, re.I)
    )
    count_match = re.search(
        r"\b([\d,]+)\s+records?\s+found\b",
        page_text,
        flags=re.IGNORECASE,
    )
    if no_results:
        return MIDXPage(
            rows=(),
            total_reported=0,
            current_page=1,
            total_pages=1,
            next_url=None,
            authoritative_empty=True,
            schema_fingerprint=schema_fingerprint({"headers": []}),
            source_url=source_url,
        )
    if count_match is None:
        raise MIDXSourceChangedError(
            "result_count_missing",
            "MIDX response did not identify a result count",
        )
    total_reported = int(count_match.group(1).replace(",", ""))

    result_table: Tag | None = None
    headers: list[str] = []
    header_row: Tag | None = None
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        for row in table.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = row.find_all(["th", "td"], recursive=False)
            candidate_headers = [
                _header_key(cell.get_text(" ", strip=True)) for cell in cells
            ]
            if "casenumber" in candidate_headers and "partyname" in candidate_headers:
                result_table = table
                headers = candidate_headers
                header_row = row
                break
        if result_table is not None:
            break
    if result_table is None or header_row is None:
        raise MIDXSourceChangedError(
            "result_table_missing",
            "MIDX reported records but its index table was not found",
            details={"total_reported": total_reported},
        )

    canonical_headers = [
        _HEADER_ALIASES.get(header, header or f"column_{index}")
        for index, header in enumerate(headers)
    ]
    if "filing_date" not in canonical_headers:
        raise MIDXSourceChangedError(
            "result_headers_changed",
            "MIDX result table lacks its filing-date column",
            details={"headers": headers},
        )

    rows: list[MIDXRow] = []
    for row_tag in result_table.find_all("tr"):
        if not isinstance(row_tag, Tag) or row_tag is header_row:
            continue
        cells = row_tag.find_all("td", recursive=False)
        if not cells:
            continue
        values: dict[str, str | None] = {}
        for index, header in enumerate(canonical_headers):
            cell = cells[index] if index < len(cells) else None
            values[header] = (
                _text(cell.get_text(" ", strip=True))
                if isinstance(cell, Tag)
                else None
            )
        info_url: str | None = None
        info_index = (
            canonical_headers.index("index_info")
            if "index_info" in canonical_headers
            else None
        )
        if info_index is not None and info_index < len(cells):
            link = cells[info_index].find("a", href=True)
            if isinstance(link, Tag):
                info_url = urljoin(source_url, str(link.get("href")))
        raw_values = {
            headers[index]: (
                _text(cells[index].get_text(" ", strip=True))
                if index < len(cells)
                else None
            )
            for index in range(len(headers))
        }
        rows.append(
            MIDXRow(
                case_number=_required_text(
                    values.get("case_number"),
                    "case number",
                ),
                party_name=_required_text(
                    values.get("party_name"),
                    "party name",
                ),
                party_type=_text(values.get("party_type")),
                filing_date=_iso_date(values.get("filing_date")),
                filing_date_raw=_text(values.get("filing_date")),
                index_info_url=info_url,
                source_url=source_url,
                raw=raw_values,
            )
        )
    if not rows:
        raise MIDXSourceChangedError(
            "result_rows_missing",
            "MIDX reported records but returned no parseable index rows",
            details={"total_reported": total_reported},
        )
    if total_reported < len(rows):
        raise MIDXSourceChangedError(
            "result_count_inconsistent",
            "MIDX result count is smaller than the returned row count",
            details={
                "total_reported": total_reported,
                "rows_on_page": len(rows),
            },
        )

    current_page, total_pages, next_url = _pagination(
        soup,
        source_url=source_url,
    )
    page_schema = inferred_schema([row.to_dict() for row in rows])
    return MIDXPage(
        rows=tuple(rows),
        total_reported=total_reported,
        current_page=current_page,
        total_pages=total_pages,
        next_url=next_url,
        authoritative_empty=False,
        schema_fingerprint=schema_fingerprint(page_schema),
        source_url=source_url,
    )


def _retry_after_seconds(value: Any) -> float | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return max(0.0, float(normalized))
    except ValueError:
        return None


def _run_browser_helper(
    selection: Mapping[str, Any],
    *,
    limit: int | None,
    offset: int,
    timeout: float,
    minimum_interval: float,
    max_attempts: int,
) -> Mapping[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise MIDXError(
            "browser_runtime_missing",
            "Node.js is required for the MIDX browser transport",
            category="runtime",
        )
    if not BROWSER_HELPER_PATH.is_file():
        raise MIDXError(
            "browser_helper_missing",
            f"MIDX browser helper not found: {BROWSER_HELPER_PATH}",
            category="runtime",
        )
    command = [
        node,
        str(BROWSER_HELPER_PATH),
        canonical_json(selection),
        "null" if limit is None else str(limit),
        str(offset),
        str(timeout),
        str(minimum_interval),
        str(max_attempts),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise MIDXError(
            "browser_helper_timeout",
            "MIDX browser acquisition did not complete",
            category="transport",
            retryable=True,
        ) from error
    except OSError as error:
        raise MIDXError(
            "browser_helper_failed",
            f"Could not start the MIDX browser helper: {error}",
            category="runtime",
        ) from error
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MIDXError(
            "browser_helper_invalid",
            "MIDX browser helper did not return JSON",
            category="runtime",
            details={
                "return_code": completed.returncode,
                "stderr": completed.stderr[-1000:],
            },
        ) from error
    if not isinstance(payload, Mapping):
        raise MIDXError(
            "browser_helper_invalid",
            "MIDX browser helper returned a non-object payload",
            category="runtime",
        )
    if payload.get("ok") is not True:
        error_payload = payload.get("error")
        details = (
            dict(error_payload)
            if isinstance(error_payload, Mapping)
            else {}
        )
        status_value = details.pop("status", ResultStatus.UNAVAILABLE.value)
        try:
            status = ResultStatus(str(status_value))
        except ValueError:
            status = ResultStatus.UNAVAILABLE
        raise MIDXError(
            str(details.pop("code", "browser_helper_failed")),
            str(details.pop("message", "MIDX browser acquisition failed")),
            status=status,
            category=str(details.pop("category", "transport")),
            retryable=bool(details.pop("retryable", False)),
            details=details,
        )
    return payload


class MIDXClient:
    """Session-aware client for the official San Mateo MIDX portal."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
        browser_runner: Any | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0
        self._browser_mode = session is None or browser_runner is not None
        self._browser_runner = browser_runner or _run_browser_helper

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        referer: str | None = None,
    ) -> Any:
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }
        if referer is not None:
            headers["Referer"] = referer
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise MIDXError(
                    "transport_error",
                    f"MIDX request failed after {attempt} attempts: {error}",
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt, "url": url},
                ) from error

            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(
                            attempt,
                            _retry_after_seconds(
                                response.headers.get("Retry-After")
                            ),
                        )
                    )
                    continue
                raise MIDXError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"MIDX returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit" if status_code == 429 else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise MIDXError(
                    "source_access_failed",
                    f"MIDX returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code >= 400:
                raise MIDXError(
                    "http_status_error",
                    f"MIDX returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            return response
        raise AssertionError("retry loop exhausted without returning or raising")

    def bootstrap(self) -> MIDXBootstrap:
        response = self._request("GET", LANDING_URL)
        response_url = _text(getattr(response, "url", None)) or LANDING_URL
        return parse_bootstrap(response.text, source_url=response_url)

    def search(
        self,
        selection: Mapping[str, Any],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> MIDXSearchResult:
        if offset < 0:
            raise ValueError("offset must not be negative")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")
        if self._browser_mode:
            return self._browser_search(
                selection,
                limit=limit,
                offset=offset,
            )
        bootstrap = self.bootstrap()
        search_type = str(selection["search_type"])
        try:
            form = bootstrap.forms[search_type]
        except KeyError as error:
            raise MIDXSourceChangedError(
                "search_form_missing",
                f"MIDX no longer exposes its {search_type} form",
            ) from error

        payload = dict(form.hidden_values)
        for field_name in form.visible_fields:
            value = selection.get(field_name)
            if value is not None:
                payload[field_name] = str(value)
        payload["Submit"] = "Submit"
        response = self._request(
            "POST",
            form.action_url,
            data=payload,
            referer=bootstrap.source_url,
        )
        response_url = _text(getattr(response, "url", None)) or form.action_url
        page = parse_results_page(response.text, source_url=response_url)

        collected: list[MIDXRow] = []
        pages_fetched = 0
        first_total = page.total_reported
        source_total_pages = page.total_pages
        page_fingerprints: set[str] = set()
        seen_urls: set[str] = set()
        while True:
            pages_fetched += 1
            collected.extend(page.rows)
            page_fingerprints.add(page.schema_fingerprint)
            enough = (
                limit is not None
                and len(collected) >= offset + limit
            )
            if enough:
                break
            if page.total_pages > page.current_page and page.next_url is None:
                raise MIDXSourceChangedError(
                    "pagination_link_missing",
                    "MIDX indicates more pages without a continuation link",
                    details={
                        "current_page": page.current_page,
                        "total_pages": page.total_pages,
                    },
                )
            if page.next_url is None:
                break
            next_url = page.next_url
            if not _same_origin(LANDING_URL, next_url):
                raise MIDXSourceChangedError(
                    "pagination_origin_changed",
                    "MIDX pagination link points outside the official host",
                    details={"next_url": next_url},
                )
            if next_url in seen_urls:
                raise MIDXSourceChangedError(
                    "pagination_loop",
                    "MIDX returned a repeated continuation link",
                    details={"next_url": next_url},
                )
            seen_urls.add(next_url)
            response = self._request(
                "GET",
                next_url,
                referer=page.source_url,
            )
            response_url = _text(getattr(response, "url", None)) or next_url
            page = parse_results_page(response.text, source_url=response_url)
            source_total_pages = max(source_total_pages, page.total_pages)

        selected = (
            collected[offset:]
            if limit is None
            else collected[offset : offset + limit]
        )
        combined_schema = schema_fingerprint(
            {
                "bootstrap": bootstrap.schema_fingerprint,
                "result_pages": sorted(page_fingerprints),
            }
        )
        return MIDXSearchResult(
            rows=tuple(selected),
            total_reported=first_total,
            source_total_pages=source_total_pages,
            pages_fetched=pages_fetched,
            current_as_of=bootstrap.current_as_of,
            schema_fingerprint=combined_schema,
            source_url=response_url,
        )

    def _browser_search(
        self,
        selection: Mapping[str, Any],
        *,
        limit: int | None,
        offset: int,
    ) -> MIDXSearchResult:
        payload = self._browser_runner(
            selection,
            limit=limit,
            offset=offset,
            timeout=self.timeout,
            minimum_interval=self._rate_limiter.minimum_interval,
            max_attempts=self.retry_policy.max_attempts,
        )
        raw_rows = payload.get("rows")
        if not isinstance(raw_rows, list):
            raise MIDXSourceChangedError(
                "browser_rows_missing",
                "MIDX browser result lacks its row array",
            )
        rows: list[MIDXRow] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                raise MIDXSourceChangedError(
                    "browser_row_invalid",
                    "MIDX browser result contains a non-object row",
                )
            filing_date_raw = _text(raw_row.get("filing_date"))
            rows.append(
                MIDXRow(
                    case_number=_required_text(
                        raw_row.get("case_number"),
                        "case number",
                    ),
                    party_name=_required_text(
                        raw_row.get("party_name"),
                        "party name",
                    ),
                    party_type=_text(raw_row.get("party_type")),
                    filing_date=_iso_date(filing_date_raw),
                    filing_date_raw=filing_date_raw,
                    index_info_url=_text(raw_row.get("index_info_url")),
                    source_url=_text(raw_row.get("source_url")) or LOOKUP_URL,
                    raw=dict(raw_row),
                )
            )
        result_schema = inferred_schema([row.to_dict() for row in rows])
        return MIDXSearchResult(
            rows=tuple(rows),
            total_reported=int(payload.get("total_reported", len(rows))),
            source_total_pages=int(payload.get("source_total_pages", 1)),
            pages_fetched=int(payload.get("pages_fetched", 1)),
            current_as_of=_text(payload.get("current_as_of")),
            schema_fingerprint=schema_fingerprint(
                {
                    "transport": "playwright",
                    "result": result_schema,
                }
            ),
            source_url=_text(payload.get("source_url")) or LOOKUP_URL,
        )

    def probe(self) -> MIDXSearchResult:
        return self.search(
            {
                "search_type": "casenumber",
                "casenumber": PROBE_CASE_NUMBER,
            },
            limit=1,
        )


def _selector_length(value: str) -> int:
    candidate = value[:-1] if value.endswith("*") else value
    return len(candidate.strip())


def _source_date(value: str, option: str) -> tuple[date, str]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise MIDXSelectionError(
            "invalid_filing_date",
            f"{option} must be an ISO calendar date",
            details={"value": value},
        ) from error
    return parsed, parsed.strftime("%m/%d/%Y")


def search_selection(args: argparse.Namespace) -> dict[str, Any]:
    """Validate one native MIDX selector and build its POST fields."""

    case_number = _text(getattr(args, "case_number", None))
    first_name = _text(getattr(args, "first_name", None))
    last_name = _text(getattr(args, "last_name", None))
    business_name = _text(getattr(args, "business_name", None))
    filed_from = _text(getattr(args, "filed_from", None))
    filed_to = _text(getattr(args, "filed_to", None))

    modes = [
        case_number is not None,
        first_name is not None or last_name is not None,
        business_name is not None,
        filed_from is not None or filed_to is not None,
    ]
    if sum(modes) != 1:
        raise MIDXSelectionError(
            "search_selector_required",
            "search requires exactly one case, person, business, or filing-date selector",
        )
    if case_number is not None:
        alphanumeric_count = len(re.sub(r"[^A-Za-z0-9]", "", case_number))
        if alphanumeric_count < 5:
            raise MIDXSelectionError(
                "case_number_too_short",
                "MIDX case-number search requires at least 5 alphanumeric characters",
            )
        return {
            "search_type": "casenumber",
            "casenumber": case_number,
        }
    if first_name is not None or last_name is not None:
        if first_name is None or last_name is None:
            raise MIDXSelectionError(
                "incomplete_person_name",
                "MIDX person search requires both first and last name",
            )
        if _selector_length(first_name) < 2 or _selector_length(last_name) < 2:
            raise MIDXSelectionError(
                "person_name_too_short",
                "MIDX person search requires at least 2 characters in each field",
            )
        return {
            "search_type": "partyname",
            "firstname": first_name,
            "lastname": last_name,
        }
    if business_name is not None:
        if _selector_length(business_name) < 3:
            raise MIDXSelectionError(
                "business_name_too_short",
                "MIDX business search requires at least 3 characters",
            )
        return {
            "search_type": "businessname",
            "businessname": business_name,
        }

    if filed_from is None or filed_to is None:
        raise MIDXSelectionError(
            "incomplete_filing_date_range",
            "MIDX filing-date search requires both range endpoints",
        )
    start, source_start = _source_date(filed_from, "--filed-from")
    end, source_end = _source_date(filed_to, "--filed-to")
    if end < start:
        raise MIDXSelectionError(
            "invalid_filing_date_range",
            "--filed-from must not be later than --filed-to",
        )
    if (end - start).days > 4:
        raise MIDXSelectionError(
            "filing_date_range_too_wide",
            "MIDX accepts a maximum of 5 calendar days per filing-date search",
            details={"calendar_days": (end - start).days + 1},
        )
    return {
        "search_type": "filedate",
        "df": source_start,
        "dt": source_end,
    }


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "san-mateo-superior-court",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "county_superior",
        "official_url": "https://sanmateo.courts.ca.gov/",
    }


def _source_scope() -> dict[str, Any]:
    return {
        "record_type": "case_party_index",
        "fields": [
            "case_number",
            "party_name",
            "native_party_type",
            "filing_date",
            "index_info_url",
        ],
        "caption_available": False,
        "case_type_available": False,
        "case_status_available": False,
        "docket_available": False,
        "documents_available": False,
        "additional_case_information_url": ODYSSEY_URL,
    }


def _identity(value: str | None) -> str:
    return (_text(value) or "").casefold()


def normalize_records(
    search_result: MIDXSearchResult,
    *,
    selection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Group MIDX index rows into deterministic case records."""

    grouped: dict[str, list[MIDXRow]] = {}
    case_variants: dict[str, set[str]] = {}
    for row in search_result.rows:
        key = _identity(row.case_number)
        grouped.setdefault(key, []).append(row)
        case_variants.setdefault(key, set()).add(row.case_number)

    records: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = sorted(
            grouped[key],
            key=lambda row: (
                _identity(row.party_name),
                _identity(row.party_type),
                row.filing_date or "",
                row.index_info_url or "",
            ),
        )
        case_number = sorted(
            case_variants[key],
            key=lambda value: (value.casefold(), value),
        )[0]
        identity_counts: dict[str, int] = {}
        parties: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for sequence_no, row in enumerate(rows):
            identity_basis = {
                "case_number": _identity(row.case_number).upper(),
                "party_name": _identity(row.party_name),
                "native_party_type": row.party_type,
                "filing_date": row.filing_date,
                "index_info_url": row.index_info_url,
            }
            basis_json = canonical_json(identity_basis)
            identity_counts[basis_json] = identity_counts.get(basis_json, 0) + 1
            occurrence = identity_counts[basis_json]
            digest = hashlib.sha256(
                canonical_json(
                    {
                        "identity_basis": identity_basis,
                        "occurrence": occurrence,
                    }
                ).encode("utf-8")
            ).hexdigest()
            parties.append(
                {
                    "native_party_id": f"midx-party:{digest}",
                    "sequence_no": sequence_no,
                    "raw_name": row.party_name,
                    "normalized_name": None,
                    "role": "unknown",
                    "native_role": row.party_type,
                    "access_state": "public",
                    "identity_kind": "source_fields_sha256_with_occurrence",
                    "identity_basis": identity_basis,
                    "occurrence": occurrence,
                }
            )
            raw_rows.append(row.to_dict())

        filing_dates = sorted(
            {row.filing_date for row in rows if row.filing_date is not None}
        )
        info_urls = sorted(
            {
                row.index_info_url
                for row in rows
                if row.index_info_url is not None
            }
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case",
                "court": _court_payload(),
                "raw_case_number": case_number,
                "display_case_number": case_number,
                "source_internal_id": None,
                "caption": None,
                "case_type": None,
                "filing_date": (
                    filing_dates[0] if len(filing_dates) == 1 else None
                ),
                "filing_date_variants": filing_dates,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": LANDING_URL,
                "parties": parties,
                "docket_entries": [],
                "documents": [],
                "index_info_urls": info_urls,
                "source_scope": _source_scope(),
                "search_metadata": {
                    "selection": dict(selection),
                    "source_total_index_rows": search_result.total_reported,
                    "source_total_pages": search_result.source_total_pages,
                    "pages_fetched": search_result.pages_fetched,
                    "current_as_of": search_result.current_as_of,
                },
                "schema_fingerprint": search_result.schema_fingerprint,
                "raw": {"index_rows": raw_rows},
            }
        )
    return records


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters = {
            "case_number": getattr(args, "case_number", None),
            "first_name": getattr(args, "first_name", None),
            "last_name": getattr(args, "last_name", None),
            "business_name": getattr(args, "business_name", None),
            "filed_from": getattr(args, "filed_from", None),
            "filed_to": getattr(args, "filed_to", None),
            "offset": getattr(args, "offset", 0),
        }
        requested_limit = getattr(args, "limit", None)
        cursor = f"midx:offset:{getattr(args, 'offset', 0)}"
    elif args.command == "case":
        parameters = {"case_number": getattr(args, "case_number", None)}
    elif args.command == "probe":
        parameters = {"case_number": PROBE_CASE_NUMBER}
        requested_limit = 1
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="San Mateo County, California",
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
            locality="San Mateo County",
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _make_client(args: argparse.Namespace) -> MIDXClient:
    return MIDXClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: MIDXError,
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
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: MIDXClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    """Execute one official MIDX operation."""

    del access_decision
    query = build_query(args)
    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        if args.command == "search":
            selection = search_selection(args)
            search_result = source_client.search(
                selection,
                limit=args.limit,
                offset=args.offset,
            )
        elif args.command == "case":
            selection = search_selection(args)
            search_result = source_client.search(selection)
        elif args.command == "probe":
            selection = {
                "search_type": "casenumber",
                "casenumber": PROBE_CASE_NUMBER,
            }
            search_result = source_client.probe()
        else:
            raise MIDXSelectionError(
                "unsupported_command",
                f"unsupported MIDX command: {args.command}",
            )
        records = normalize_records(search_result, selection=selection)
        next_cursor = None
        if (
            args.command == "search"
            and args.limit is not None
            and args.offset + len(search_result.rows)
            < search_result.total_reported
        ):
            next_cursor = f"midx:offset:{args.offset + len(search_result.rows)}"
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except MIDXError as error:
        result = _failure_result(query, error)
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

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"San Mateo MIDX {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"San Mateo MIDX {args.command}: {result.status.value} "
        f"({len(result.records)} cases)"
    )
    for record in result.records:
        print(
            f"  {record.get('raw_case_number') or '?'} | "
            f"{record.get('filing_date') or '?'} | "
            f"{len(record.get('parties') or [])} index rows"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query San Mateo Superior Court's official MIDX case index"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search by one native MIDX selector",
    )
    search.add_argument("--case-number")
    search.add_argument("--first-name")
    search.add_argument("--last-name")
    search.add_argument("--business-name")
    search.add_argument("--filed-from", help="ISO start date")
    search.add_argument("--filed-to", help="ISO end date")
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Maximum native index rows to return; defaults to all pages",
    )
    search.add_argument(
        "--offset",
        type=_nonnegative_int,
        default=0,
        help="Native index rows to skip",
    )
    _add_runtime_and_output(search)

    case = subparsers.add_parser(
        "case",
        help="Search the index by case number",
    )
    case.add_argument("case_number")
    _add_runtime_and_output(case)

    probe = subparsers.add_parser(
        "probe",
        help="Verify forms, tokenized POST, and result parsing",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
