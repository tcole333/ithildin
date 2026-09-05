"""Shared, manifest-driven mechanics for Oregon Aumentum AscendWeb tenants.

The counties expose closely related ASP.NET applications, but their native
contracts are not identical.  This module shares only behavior verified across
multiple live tenants: bounded HTTP transport, redirect/session validation,
ASP.NET hidden-state replay, complete native result-table parsing, declared
result-count checks, and optional installment postbacks.  County adapters own
their explicit host, root path, form aliases, table identifiers, labels,
versions, sentinels, and normalization.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from tools.public_records_contract import sha256_fingerprint
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        system_trust_session,
    )
except ImportError:
    from public_records_contract import sha256_fingerprint
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TransportError,
        system_trust_session,
    )


DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
DEFAULT_MAXIMUM_ERROR_BYTES = 8 * 1024
DEFAULT_USER_AGENT = "Ithildin-Public-Records/1.0"
REQUIRED_HIDDEN_FIELDS = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
)


@dataclass(frozen=True)
class AscendTenantManifest:
    """Explicit native contract for one verified AscendWeb tenant."""

    source_id: str
    jurisdiction: str
    county_geoid: str
    root_url: str
    home_path: str
    detail_path: str
    observed_versions: tuple[str, ...]
    form_aliases: Mapping[str, str]
    submit_value: str
    result_table_id: str
    result_headers: tuple[str, ...]
    result_columns: tuple[str, ...]
    result_count_selectors: tuple[str, ...]
    result_count_pattern: str
    detail_link_parameter: str
    detail_table_ids: Mapping[str, str]
    identity_mode: str
    identity_account_label: str
    identity_account_id: str | None = None
    identity_address_id: str | None = None
    identity_table_id: str | None = None
    form_action_suffixes: tuple[str, ...] = ()
    session_path_pattern: str | None = r"/\(S\([^/()]+\)\)"
    installment_link_id: str | None = None
    installment_event_target: str | None = None
    installment_year_field: str | None = None
    maximum_html_bytes: int = DEFAULT_MAXIMUM_HTML_BYTES
    maximum_error_bytes: int = DEFAULT_MAXIMUM_ERROR_BYTES

    def __post_init__(self) -> None:
        parsed = urlparse(self.root_url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("root_url must be an unauthenticated HTTPS URL")
        if not parsed.path.endswith("/"):
            raise ValueError("root_url path must end with '/'")
        if not self.observed_versions:
            raise ValueError("observed_versions must retain at least one observation")
        if len(self.result_headers) != len(self.result_columns):
            raise ValueError("result_headers and result_columns must have equal length")
        if "account" not in self.form_aliases:
            raise ValueError("form_aliases must include account")
        if self.identity_mode not in {"table", "elements"}:
            raise ValueError("identity_mode must be 'table' or 'elements'")
        if self.identity_mode == "table" and not self.identity_table_id:
            raise ValueError("table identity requires identity_table_id")
        if self.identity_mode == "elements" and (
            not self.identity_account_id or not self.identity_address_id
        ):
            raise ValueError(
                "element identity requires account and address element IDs"
            )
        if self.maximum_html_bytes < 1 or self.maximum_error_bytes < 1:
            raise ValueError("response bounds must be positive")

    @property
    def hostname(self) -> str:
        parsed = urlparse(self.root_url)
        assert parsed.hostname is not None
        return parsed.hostname

    @property
    def root_path(self) -> str:
        return urlparse(self.root_url).path

    @property
    def home_url(self) -> str:
        return canonical_url(self, urljoin(self.root_url, self.home_path))

    @property
    def detail_url(self) -> str:
        return canonical_url(self, urljoin(self.root_url, self.detail_path))

    def contract_record(self) -> dict[str, Any]:
        """Return stable native details for source catalogs and probes."""

        return {
            "source_id": self.source_id,
            "jurisdiction": self.jurisdiction,
            "county_geoid": self.county_geoid,
            "tenant_host": self.hostname,
            "tenant_root_path": self.root_path,
            "home_path": self.home_path,
            "detail_path": self.detail_path,
            "observed_versions": list(self.observed_versions),
            "form_aliases": dict(self.form_aliases),
            "submit_value": self.submit_value,
            "form_action_suffixes": list(self.form_action_suffixes),
            "result_table_id": self.result_table_id,
            "result_headers": list(self.result_headers),
            "result_columns": list(self.result_columns),
            "result_count_selectors": list(self.result_count_selectors),
            "result_count_pattern": self.result_count_pattern,
            "detail_link_parameter": self.detail_link_parameter,
            "detail_table_ids": dict(self.detail_table_ids),
            "identity": {
                "mode": self.identity_mode,
                "account_label": self.identity_account_label,
                "account_id": self.identity_account_id,
                "address_id": self.identity_address_id,
                "table_id": self.identity_table_id,
            },
            "cookieless_session_pattern": self.session_path_pattern,
            "installment": {
                "link_id": self.installment_link_id,
                "event_target": self.installment_event_target,
                "year_field": self.installment_year_field,
            },
            "maximum_html_bytes": self.maximum_html_bytes,
            "maximum_error_bytes": self.maximum_error_bytes,
        }


@dataclass(frozen=True)
class HTMLPage:
    html: str
    source_url: str
    request_url: str
    body_bytes: int | None = None


@dataclass(frozen=True)
class AscendHomeContract:
    form_fields: tuple[str, ...]
    hidden_fields: tuple[str, ...]
    version: str
    form_action: str
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class AscendSearchPage:
    records: tuple[Mapping[str, Any], ...]
    total_count: int
    schema_fingerprint: str
    snapshot_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class AscendCursorState:
    source_id: str
    criteria_fingerprint: str
    schema_fingerprint: str
    snapshot_fingerprint: str
    offset: int


@dataclass(frozen=True)
class AscendSearchSlice:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    offset: int
    total_count: int


def clean(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    if not text or text == "-":
        return None
    return text


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (clean(value) or "").casefold()).strip(
        "_"
    )


def number(value: Any) -> int | float | None:
    text = clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[$,%\s]", "", text).replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def date_iso(value: Any) -> str | None:
    text = clean(value)
    if text is None:
        return None
    text = re.sub(r"\s+00:00:00$", "", text)
    for pattern in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def table_rows(table: Tag | None) -> list[list[str]]:
    if table is None:
        return []
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [
            clean(cell) or ""
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        if cells:
            rows.append(cells)
    return rows


def key_value_table(soup: BeautifulSoup, table_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in table_rows(soup.select_one(f"#{table_id}")):
        if len(row) < 2:
            continue
        key = slug(row[0])
        if key:
            result[key] = clean(row[1])
    return result


def row_table(soup: BeautifulSoup, table_id: str) -> list[dict[str, Any]]:
    rows = table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) < 2:
        return []
    headers = [slug(value) or f"column_{index}" for index, value in enumerate(rows[0])]
    return [
        {
            header: clean(row[index]) if index < len(row) else None
            for index, header in enumerate(headers)
        }
        for row in rows[1:]
        if any(clean(value) for value in row)
    ]


def row_table_or_message(
    soup: BeautifulSoup,
    table_id: str,
) -> list[dict[str, Any]]:
    rows = table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) == 1 and len(rows[0]) == 1:
        message = clean(rows[0][0])
        return [{"message": message}] if message else []
    return row_table(soup, table_id)


def canonical_url(manifest: AscendTenantManifest, value: str) -> str:
    """Validate an emitted URL and remove only the declared session segment."""

    parsed = urlparse(value)
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != manifest.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError(
            f"unexpected {manifest.jurisdiction} AscendWeb response host"
        )
    path = parsed.path
    if manifest.session_path_pattern:
        path = re.sub(manifest.session_path_pattern, "", path, flags=re.I)
    root = manifest.root_path.casefold()
    if not path.casefold().startswith(root):
        raise ValueError(
            f"unexpected {manifest.jurisdiction} AscendWeb response path"
        )
    return parsed._replace(path=path, fragment="").geturl()


def request_url(manifest: AscendTenantManifest, path_or_url: str) -> str:
    """Validate a request URL while retaining a live cookieless session."""

    expanded = urljoin(manifest.root_url, path_or_url)
    canonical_url(manifest, expanded)
    return urlparse(expanded)._replace(fragment="").geturl()


def _form_action(
    manifest: AscendTenantManifest,
    soup: BeautifulSoup,
    *,
    base_url: str,
) -> tuple[str, str]:
    form = soup.select_one("form")
    if form is None:
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb form is missing",
            url=canonical_url(manifest, base_url),
        )
    native_action = str(form.get("action") or "")
    target = request_url(manifest, urljoin(base_url, native_action or base_url))
    if manifest.form_action_suffixes and not any(
        urlparse(target).path.casefold().endswith(suffix.casefold())
        for suffix in manifest.form_action_suffixes
    ):
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb form action changed",
            url=canonical_url(manifest, base_url),
            details={"form_action": native_action, "target_url": canonical_url(manifest, target)},
        )
    return native_action, target


def parse_home(
    manifest: AscendTenantManifest,
    html: str,
    *,
    source_url: str | None = None,
) -> AscendHomeContract:
    """Validate the tenant's anonymous ASP.NET form and version observation."""

    source_url = source_url or manifest.home_url
    soup = BeautifulSoup(html, "lxml")
    fields = tuple(
        str(element.get("name"))
        for element in soup.select("input[name]")
        if element.get("name")
    )
    hidden = tuple(
        sorted(
            {
                str(element.get("name"))
                for element in soup.select("input[type=hidden][name]")
            }
        )
    )
    required_form = set(manifest.form_aliases.values())
    missing = sorted(required_form - set(fields))
    missing_hidden = sorted(set(REQUIRED_HIDDEN_FIELDS) - set(hidden))
    version_match = re.search(r"\bVersion\s+([0-9]+(?:\.[0-9]+){2,})", html, re.I)
    version = version_match.group(1) if version_match else ""
    native_action, _ = _form_action(manifest, soup, base_url=source_url)
    if missing or missing_hidden or not version:
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb search form contract changed",
            url=canonical_url(manifest, source_url),
            details={
                "missing_form_fields": missing,
                "missing_hidden_fields": missing_hidden,
                "version": version or None,
            },
        )
    shape = {
        "form_fields": sorted(set(fields)),
        "hidden_fields": list(hidden),
        "version": version,
        "form_action": native_action,
        "tenant_root_path": manifest.root_path,
    }
    return AscendHomeContract(
        form_fields=tuple(sorted(set(fields))),
        hidden_fields=hidden,
        version=version,
        form_action=native_action,
        schema_fingerprint=sha256_fingerprint(shape),
        source_url=canonical_url(manifest, source_url),
    )


def parse_search(
    manifest: AscendTenantManifest,
    html: str,
    *,
    source_url: str,
) -> AscendSearchPage:
    """Parse and validate the tenant's complete native result table."""

    canonical_source = canonical_url(manifest, source_url)
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(f"#{manifest.result_table_id}")
    rows = table_rows(table)
    if table is None or not rows or tuple(rows[0]) != manifest.result_headers:
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb result table contract changed",
            url=canonical_source,
            details={"headers": rows[0] if rows else []},
        )
    records: list[dict[str, Any]] = []
    for position, row_element in enumerate(table.find_all("tr")[1:], start=1):
        cells = row_element.find_all(["th", "td"], recursive=False)
        if len(cells) != len(manifest.result_columns):
            raise SourceSchemaError(
                f"{manifest.jurisdiction} AscendWeb result row shape changed",
                url=canonical_source,
                details={"position": position, "cell_count": len(cells)},
            )
        values = {
            name: clean(cells[index])
            for index, name in enumerate(manifest.result_columns)
        }
        account = values.get("account_number")
        link = cells[0].find("a", href=True)
        if account is None or link is None:
            raise SourceSchemaError(
                f"{manifest.jurisdiction} AscendWeb result lacks account identity",
                url=canonical_source,
                details={"position": position},
            )
        href = str(link.get("href"))
        query = parse_qs(urlparse(urljoin(source_url, href)).query)
        linked_values = query.get(manifest.detail_link_parameter, [])
        if linked_values != [account]:
            raise SourceSchemaError(
                f"{manifest.jurisdiction} AscendWeb result link identity changed",
                url=canonical_source,
                details={
                    "position": position,
                    "href": href,
                    "linked_values": linked_values,
                },
            )
        records.append(
            {
                **values,
                "native_position": position,
                "detail_url": (
                    f"{manifest.detail_url}?{manifest.detail_link_parameter}="
                    f"{requests.utils.quote(account, safe='')}"
                ),
            }
        )
    message = " ".join(
        filter(
            None,
            (clean(soup.select_one(selector)) for selector in manifest.result_count_selectors),
        )
    )
    count_match = re.search(manifest.result_count_pattern, message, re.I)
    if not count_match:
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb result count message changed",
            url=canonical_source,
            details={"message": message},
        )
    total_count = int(count_match.group(1).replace(",", ""))
    if total_count != len(records):
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb result table is incomplete",
            url=canonical_source,
            details={"declared_count": total_count, "parsed_count": len(records)},
        )
    schema_value = sha256_fingerprint(
        {
            "headers": list(manifest.result_headers),
            "columns": list(manifest.result_columns),
            "detail_parameter": manifest.detail_link_parameter,
            "count_pattern": manifest.result_count_pattern,
        }
    )
    return AscendSearchPage(
        records=tuple(records),
        total_count=total_count,
        schema_fingerprint=schema_value,
        snapshot_fingerprint=sha256_fingerprint(
            [
                [record.get(column) for column in manifest.result_columns]
                + [record["native_position"]]
                for record in records
            ]
        ),
        source_url=canonical_source,
    )


def _encode_cursor(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).decode("ascii")
    return f"{prefix}{encoded.rstrip('=')}"


def _decode_cursor(prefix: str, cursor: str) -> Mapping[str, Any]:
    if not cursor.startswith(prefix):
        raise ValueError("continuation cursor belongs to a different adapter")
    value = cursor[len(prefix) :]
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("continuation cursor is malformed") from exc
    if not isinstance(payload, Mapping) or payload.get("v") != 1:
        raise ValueError("continuation cursor version is unsupported")
    return payload


def slice_complete_search(
    manifest: AscendTenantManifest,
    page: AscendSearchPage,
    *,
    cursor_prefix: str,
    criteria: Mapping[str, Any],
    limit: int,
    cursor: str | None,
) -> AscendSearchSlice:
    """Slice a complete native table with a query/schema/snapshot-bound cursor."""

    if limit < 1:
        raise ValueError("limit must be positive")
    criteria_fingerprint = sha256_fingerprint(
        {"source_id": manifest.source_id, **dict(criteria)}
    )
    state: AscendCursorState | None = None
    if cursor is not None:
        payload = _decode_cursor(cursor_prefix, cursor)
        try:
            state = AscendCursorState(
                source_id=str(payload["source"]),
                criteria_fingerprint=str(payload["criteria"]),
                schema_fingerprint=str(payload["schema"]),
                snapshot_fingerprint=str(payload["snapshot"]),
                offset=int(payload["offset"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("continuation cursor values are malformed") from exc
        if state.offset < 0:
            raise ValueError("continuation cursor offset is invalid")
        if (
            state.source_id != manifest.source_id
            or state.criteria_fingerprint != criteria_fingerprint
        ):
            raise ValueError("continuation cursor belongs to different criteria")
        if (
            state.schema_fingerprint != page.schema_fingerprint
            or state.snapshot_fingerprint != page.snapshot_fingerprint
        ):
            raise SourceSchemaError(
                f"{manifest.jurisdiction} AscendWeb result snapshot changed "
                "after the continuation was issued",
                url=page.source_url,
            )
    offset = state.offset if state else 0
    records = tuple(page.records[offset : offset + limit])
    next_offset = offset + len(records)
    next_cursor = None
    if next_offset < page.total_count:
        next_cursor = _encode_cursor(
            cursor_prefix,
            {
                "v": 1,
                "source": manifest.source_id,
                "criteria": criteria_fingerprint,
                "schema": page.schema_fingerprint,
                "snapshot": page.snapshot_fingerprint,
                "offset": next_offset,
            },
        )
    return AscendSearchSlice(
        records=records,
        next_cursor=next_cursor,
        offset=offset,
        total_count=page.total_count,
    )


def parse_identity(
    manifest: AscendTenantManifest,
    soup: BeautifulSoup,
    *,
    source_url: str,
) -> tuple[str, str | None, tuple[str, ...]]:
    """Return account, address, and source-native identity labels."""

    if manifest.identity_mode == "elements":
        assert manifest.identity_account_id
        assert manifest.identity_address_id
        account_label_id = manifest.identity_account_id.replace(
            "mParcelNumber", "mParcelNumberLabel"
        )
        label = clean(soup.select_one(f"#{account_label_id}"))
        account = clean(soup.select_one(f"#{manifest.identity_account_id}"))
        address = clean(soup.select_one(f"#{manifest.identity_address_id}"))
        labels = (label or "", "Property Address")
    else:
        assert manifest.identity_table_id
        rows = table_rows(soup.select_one(f"#{manifest.identity_table_id}"))
        if not rows or len(rows[0]) < 4:
            raise SourceSchemaError(
                f"{manifest.jurisdiction} AscendWeb identity table changed",
                url=source_url,
            )
        identity = rows[0]
        label = clean(identity[0])
        account = clean(identity[1])
        address = clean(identity[3])
        labels = tuple(identity[::2])
    if slug(label) != slug(manifest.identity_account_label):
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb account label changed",
            url=source_url,
            details={"label": label},
        )
    if account is None:
        raise SourceSchemaError(
            f"{manifest.jurisdiction} AscendWeb detail lacks account identity",
            url=source_url,
        )
    return account, address, labels


def response_header(response: Any, name: str) -> str | None:
    for key, value in getattr(response, "headers", {}).items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def retry_after(response: Any) -> float | None:
    raw = response_header(response, "retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


class AscendWebClient:
    """Bounded client that follows one tenant's native anonymous session."""

    def __init__(
        self,
        manifest: AscendTenantManifest,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.manifest = manifest
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
            clock=clock,
        )
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.sleeper = sleeper
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.8",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    @staticmethod
    def _stream_bytes(
        response: Any,
        *,
        maximum_bytes: int,
        source_url: str,
        error_message: str,
    ) -> tuple[bytes, bool]:
        body = bytearray()
        truncated = False
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                remaining = maximum_bytes - len(body)
                if remaining <= 0:
                    truncated = True
                    break
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
            return bytes(body), truncated
        except requests.RequestException as exc:
            raise TransportError(
                error_message,
                url=source_url,
                details={"error": str(exc)},
            ) from exc

    def _error_excerpt(self, response: Any, *, source_url: str) -> str:
        try:
            body, truncated = self._stream_bytes(
                response,
                maximum_bytes=self.manifest.maximum_error_bytes,
                source_url=source_url,
                error_message=(
                    f"{self.manifest.jurisdiction} AscendWeb error response "
                    "failed while streaming"
                ),
            )
            encoding = getattr(response, "encoding", None) or "utf-8"
            text = body.decode(str(encoding), errors="replace")
            return f"{text}{'…' if truncated else ''}"
        finally:
            response.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> Any:
        official_url = request_url(self.manifest, url)
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    official_url,
                    params=params,
                    data=data,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for hop in [*getattr(response, "history", ()), response]:
                canonical_url(
                    self.manifest,
                    str(getattr(hop, "url", official_url)),
                )
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                delay = self.retry_policy.delay(attempt, retry_after(response))
                response.close()
                self.sleeper(delay)
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
                excerpt = self._error_excerpt(response, source_url=official_url)
                raise HTTPStatusError(
                    status,
                    url=official_url,
                    response_text=excerpt,
                )
            return response
        raise TransportError(
            f"{self.manifest.jurisdiction} AscendWeb request failed",
            url=official_url,
            details={"error": str(last_error or "retry attempts exhausted")},
        )

    def _read_html(self, response: Any) -> tuple[str, int]:
        source_url = canonical_url(self.manifest, str(response.url))
        content_type = (response_header(response, "content-type") or "").casefold()
        content_length = response_header(response, "content-length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                declared_bytes = None
            if (
                declared_bytes is not None
                and declared_bytes > self.manifest.maximum_html_bytes
            ):
                response.close()
                raise SourceSchemaError(
                    f"{self.manifest.jurisdiction} AscendWeb response exceeds "
                    "its declared adapter bound",
                    url=source_url,
                    details={
                        "declared_bytes": declared_bytes,
                        "maximum_bytes": self.manifest.maximum_html_bytes,
                    },
                )
        if content_type and not any(
            media_type in content_type
            for media_type in ("text/html", "application/xhtml+xml")
        ):
            response.close()
            raise SourceSchemaError(
                f"{self.manifest.jurisdiction} AscendWeb returned non-HTML",
                url=source_url,
                details={"content_type": content_type},
            )
        try:
            body, truncated = self._stream_bytes(
                response,
                maximum_bytes=self.manifest.maximum_html_bytes + 1,
                source_url=source_url,
                error_message=(
                    f"{self.manifest.jurisdiction} AscendWeb response failed "
                    "while streaming"
                ),
            )
            if truncated or len(body) > self.manifest.maximum_html_bytes:
                raise SourceSchemaError(
                    f"{self.manifest.jurisdiction} AscendWeb response exceeded "
                    "its adapter bound while streaming",
                    url=source_url,
                    details={
                        "bytes_read": len(body),
                        "maximum_bytes": self.manifest.maximum_html_bytes,
                    },
                )
            encoding = getattr(response, "encoding", None) or "utf-8"
            return body.decode(str(encoding), errors="replace"), len(body)
        finally:
            response.close()

    def _page(self, response: Any) -> HTMLPage:
        native_url = str(response.url)
        emitted_url = canonical_url(self.manifest, native_url)
        html, body_bytes = self._read_html(response)
        return HTMLPage(
            html=html,
            source_url=emitted_url,
            request_url=native_url,
            body_bytes=body_bytes,
        )

    def fetch_home(self) -> HTMLPage:
        return self._page(self._request("GET", self.manifest.home_url))

    def search(
        self,
        *,
        account: str = "",
        alternate: str = "",
        address: str = "",
        city: str = "",
        state: str = "",
        postal_code: str = "",
    ) -> HTMLPage:
        home = self.fetch_home()
        parse_home(self.manifest, home.html, source_url=home.source_url)
        soup = BeautifulSoup(home.html, "lxml")
        form_data = {
            str(element["name"]): str(element.get("value", ""))
            for element in soup.select("input[type=hidden][name]")
        }
        values = {
            "account": account,
            "alternate": alternate,
            "address": address,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "submit": self.manifest.submit_value,
        }
        for logical_name, native_name in self.manifest.form_aliases.items():
            form_data[native_name] = values.get(logical_name, "")
        if alternate and "alternate" not in self.manifest.form_aliases:
            raise ValueError(
                f"{self.manifest.jurisdiction} has no verified alternate-account "
                "search field"
            )
        _, target = _form_action(
            self.manifest,
            soup,
            base_url=home.request_url,
        )
        return self._page(self._request("POST", target, data=form_data))

    def detail(
        self,
        account_number: str,
        *,
        tax_year: int | None = None,
    ) -> tuple[HTMLPage, HTMLPage | None]:
        response = self._request(
            "GET",
            self.manifest.detail_url,
            params={self.manifest.detail_link_parameter: account_number},
        )
        detail = self._page(response)
        installment: HTMLPage | None = None
        if tax_year is not None:
            link_id = self.manifest.installment_link_id
            event_target = self.manifest.installment_event_target
            year_field = self.manifest.installment_year_field
            if not all((link_id, event_target, year_field)):
                raise ValueError(
                    f"{self.manifest.jurisdiction} has no verified installment "
                    "postback contract"
                )
            soup = BeautifulSoup(detail.html, "lxml")
            form_data = {
                str(element["name"]): str(element.get("value", ""))
                for element in soup.select("input[type=hidden][name]")
            }
            missing = sorted(set(REQUIRED_HIDDEN_FIELDS) - set(form_data))
            if missing or soup.select_one(f"#{link_id}") is None:
                raise SourceSchemaError(
                    f"{self.manifest.jurisdiction} AscendWeb installment "
                    "postback contract changed",
                    url=detail.source_url,
                    details={"missing_fields": missing, "link_id": link_id},
                )
            form_data.update(
                {
                    "__EVENTTARGET": event_target,
                    "__EVENTARGUMENT": "",
                    str(year_field): str(tax_year),
                }
            )
            installment = self._page(
                self._request("POST", detail.request_url, data=form_data)
            )
        return detail, installment
