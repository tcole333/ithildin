#!/usr/bin/env python3
"""Fetch Jackson County, Oregon Accela record and document representations.

Jackson County's ArcGIS permit layers publish Accela record-detail links.  This
adapter follows those official links for Building and Planning records while
preserving the source-native identifiers and each fetched representation.

Examples:
    uv run python tools/query_oregon_jackson_accela.py sources --json
    uv run python tools/query_oregon_jackson_accela.py record \
        building 26CAP-00000-006GM --output /tmp/jackson-building.json
    uv run python tools/query_oregon_jackson_accela.py record-url \
        'https://aca-oregon.accela.com/oregon/Cap/CapDetail.aspx?...'
    uv run python tools/query_oregon_jackson_accela.py document \
        building 16767279 --output /tmp/jackson-document.json
    uv run python tools/query_oregon_jackson_accela.py download \
        building 26CAP-00000-006GM 16767279 \
        --destination /tmp/building-permit.pdf \
        --output /tmp/building-permit-manifest.json
    uv run python tools/query_oregon_jackson_accela.py probe --all
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
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

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
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
COUNTY_GEOID = "41029"
COUNTY_NAME = "Jackson County, Oregon"
AGENCY_CODE = "JACKSON_CO"
PUBLISHER = "Jackson County Development Services"
PLATFORM_FAMILY = "accela_citizen_access"
ROOT_URL = "https://aca-oregon.accela.com"
TENANT_ROOT = f"{ROOT_URL}/oregon/"
RECORD_DETAIL_URL = f"{TENANT_ROOT}Cap/CapDetail.aspx"
ATTACHMENT_LIST_URL = f"{TENANT_ROOT}FileUpload/AttachmentsList.aspx"
DOCUMENT_DETAIL_URL = f"{TENANT_ROOT}FileUpload/DocumentDetail.aspx"
RECORDS_REQUEST_URL = (
    "https://jacksoncountyor.gov/Document%20Center/Departments/Counsel/"
    "Public%20Records%20Request.pdf"
)
BUILDING_ARCGIS_URL = (
    "https://jcportal.jacksoncountyor.gov/server/rest/services/"
    "Property/Permits_Building/FeatureServer/1"
)
PLANNING_ARCGIS_URL = (
    "https://jcportal.jacksoncountyor.gov/server/rest/services/"
    "Property/Permits_LandUse/FeatureServer/0"
)
CODE_ARCGIS_URL = (
    "https://jcportal.jacksoncountyor.gov/server/rest/services/"
    "Property/Permits_CodeCompliance/FeatureServer/2"
)
CODE_PORTLET_URL = (
    "https://av-oregon.accela.com/portlets/gis/general.do?"
    "mode=showAccelaRecordDetail&module=CodeCompliance&gisFromPage=CAPList&"
    "entityKey=26CAP-00000-006IG$*$APPLICATION"
)

OUTPUT_SCHEMA_VERSION = "oregon-jackson-accela/1.0"
PROBE_SCHEMA_VERSION = "oregon-jackson-accela-probe/1.0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_RESPONSE_BYTES = 128 * 1024 * 1024
USER_AGENT = "Ithildin Jackson County public-record client"

BUILDING_SOURCE_ID = "us-or-jackson-county-accela-building-details"
PLANNING_SOURCE_ID = "us-or-jackson-county-accela-planning-details"
CODE_SOURCE_ID = "us-or-jackson-county-code-compliance"

INSPECTION_EVENT_TARGET = "ctl00$PlaceHolderMain$InspectionList$btnRefreshGridView"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _element_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return _clean(" ".join(element.stripped_strings))


def _response_bytes(
    response: Any,
    *,
    maximum_bytes: int,
    request_url: str,
) -> bytes:
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")

    headers = dict(getattr(response, "headers", {}) or {})
    declared_length = _header(headers, "Content-Length")
    if declared_length is not None:
        try:
            content_length = int(declared_length)
        except (TypeError, ValueError):
            content_length = None
        if content_length is not None and content_length > maximum_bytes:
            close = getattr(response, "close", None)
            if callable(close):
                close()
            raise SourceResponseError(
                "Jackson County Accela response exceeds the configured byte bound",
                url=request_url,
                details={
                    "content_length": content_length,
                    "maximum_bytes": maximum_bytes,
                },
            )

    chunks: list[bytes] = []
    observed_bytes = 0
    try:
        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            raw_chunks = iterator(chunk_size=64 * 1024)
        else:
            content = getattr(response, "content", None)
            if isinstance(content, bytes):
                raw_chunks = (content,)
            else:
                raw_chunks = (str(getattr(response, "text", "")).encode("utf-8"),)
        for chunk in raw_chunks:
            if not chunk:
                continue
            encoded = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8")
            observed_bytes += len(encoded)
            if observed_bytes > maximum_bytes:
                raise SourceResponseError(
                    "Jackson County Accela response exceeds the configured byte bound",
                    url=request_url,
                    details={
                        "observed_bytes": observed_bytes,
                        "maximum_bytes": maximum_bytes,
                    },
                )
            chunks.append(encoded)
        return b"".join(chunks)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _response_url(response: Any, requested_url: str) -> str:
    return str(getattr(response, "url", "") or requested_url)


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


@dataclass(frozen=True)
class AccelaTenant:
    """Reusable Accela Citizen Access tenant contract."""

    agency_code: str
    tenant_root: str
    record_detail_url: str
    attachment_list_url: str
    document_detail_url: str

    @property
    def origin(self) -> str:
        parsed = urlparse(self.tenant_root)
        return f"{parsed.scheme}://{parsed.netloc}"


TENANT = AccelaTenant(
    agency_code=AGENCY_CODE,
    tenant_root=TENANT_ROOT,
    record_detail_url=RECORD_DETAIL_URL,
    attachment_list_url=ATTACHMENT_LIST_URL,
    document_detail_url=DOCUMENT_DETAIL_URL,
)


@dataclass(frozen=True)
class SourceDefinition:
    """One verified Jackson County Accela module."""

    key: str
    module: str
    source_id: str
    name: str
    source_role: str
    record_kind: str
    arcgis_source_id: str
    arcgis_url: str
    sample_cap_key: str

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=TENANT.record_detail_url,
            dataset_id=f"{TENANT.agency_code}:{self.module}",
            metadata={
                "publisher": PUBLISHER,
                "platform_family": PLATFORM_FAMILY,
                "agency_code": TENANT.agency_code,
                "module": self.module,
                "record_kind": self.record_kind,
                "county_geoid": COUNTY_GEOID,
                "arcgis_complement": {
                    "source_id": self.arcgis_source_id,
                    "url": self.arcgis_url,
                },
                "records_request_url": RECORDS_REQUEST_URL,
            },
        )


BUILDING = SourceDefinition(
    key="building",
    module="Building",
    source_id=BUILDING_SOURCE_ID,
    name="Jackson County Accela Building Record Details",
    source_role="county_building_permit_detail",
    record_kind="building_permit_detail",
    arcgis_source_id="us-or-jackson-county-building-permits",
    arcgis_url=BUILDING_ARCGIS_URL,
    sample_cap_key="26CAP-00000-006GM",
)
PLANNING = SourceDefinition(
    key="planning",
    module="Planning",
    source_id=PLANNING_SOURCE_ID,
    name="Jackson County Accela Planning Record Details",
    source_role="county_land_use_permit_detail",
    record_kind="land_use_permit_detail",
    arcgis_source_id="us-or-jackson-county-land-use-permits",
    arcgis_url=PLANNING_ARCGIS_URL,
    sample_cap_key="14HIS-00000-03BD6",
)
SOURCES = {source.key: source for source in (BUILDING, PLANNING)}
MODULE_SOURCES = {source.module.casefold(): source for source in SOURCES.values()}


@dataclass(frozen=True)
class RecordKey:
    """The three source-native Accela CAP identity components."""

    source: SourceDefinition
    cap_id1: str
    cap_id2: str
    cap_id3: str

    def __post_init__(self) -> None:
        for field_name in ("cap_id1", "cap_id2", "cap_id3"):
            value = str(getattr(self, field_name)).strip()
            if not value or not re.fullmatch(r"[A-Za-z0-9]+", value):
                raise ValueError(f"{field_name} must be an alphanumeric Accela ID")
            object.__setattr__(self, field_name, value)

    @property
    def compact(self) -> str:
        return f"{self.cap_id1}-{self.cap_id2}-{self.cap_id3}"

    @property
    def detail_parameters(self) -> dict[str, str]:
        return {
            "Module": self.source.module,
            "TabName": self.source.module,
            "capID1": self.cap_id1,
            "capID2": self.cap_id2,
            "capID3": self.cap_id3,
            "agencyCode": TENANT.agency_code,
            "IsToShowInspection": "",
        }

    @property
    def detail_url(self) -> str:
        return f"{TENANT.record_detail_url}?{urlencode(self.detail_parameters)}"

    def to_dict(self) -> dict[str, str]:
        return {
            "module": self.source.module,
            "cap_id1": self.cap_id1,
            "cap_id2": self.cap_id2,
            "cap_id3": self.cap_id3,
            "compact": self.compact,
        }


def parse_cap_key(source: SourceDefinition, value: str) -> RecordKey:
    parts = str(value).strip().split("-", 2)
    if len(parts) != 3:
        raise ValueError("CAP key must contain capID1-capID2-capID3")
    return RecordKey(source, *parts)


def parse_record_url(value: str) -> RecordKey:
    parsed = urlparse(str(value).strip())
    if parsed.scheme.casefold() != "https":
        raise ValueError("record URL must use HTTPS")
    if parsed.netloc.casefold() != "aca-oregon.accela.com":
        raise ValueError("record URL is not the Oregon Accela tenant")
    if parsed.path.casefold() != "/oregon/cap/capdetail.aspx":
        raise ValueError("record URL is not an Accela record-detail route")
    query = parse_qs(parsed.query, keep_blank_values=True)
    agency = _clean((query.get("agencyCode") or [""])[0])
    if agency != TENANT.agency_code:
        raise ValueError("record URL does not identify Jackson County")
    module = _clean((query.get("Module") or [""])[0])
    source = MODULE_SOURCES.get((module or "").casefold())
    if source is None:
        raise ValueError(f"no verified Jackson County detail module for {module!r}")
    return RecordKey(
        source,
        (query.get("capID1") or [""])[0],
        (query.get("capID2") or [""])[0],
        (query.get("capID3") or [""])[0],
    )


@dataclass(frozen=True)
class FetchedRepresentation:
    """A fetched source representation and its exact response identity."""

    kind: str
    method: str
    request_url: str
    response_url: str
    status_code: int
    headers: Mapping[str, Any]
    body: bytes
    request_parameters: Mapping[str, Any] | None = None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "method": self.method,
            "request_url": self.request_url,
            "response_url": self.response_url,
            "status_code": self.status_code,
            "content_type": _header(self.headers, "Content-Type"),
            "content_disposition": _header(self.headers, "Content-Disposition"),
            "byte_length": len(self.body),
            "sha256": hashlib.sha256(self.body).hexdigest(),
            "request_parameters": dict(self.request_parameters or {}),
        }


def _representation(
    kind: str,
    method: str,
    request_url: str,
    response: Any,
    *,
    maximum_bytes: int,
    request_parameters: Mapping[str, Any] | None = None,
) -> FetchedRepresentation:
    response_url = _response_url(response, request_url)
    headers = dict(getattr(response, "headers", {}) or {})
    return FetchedRepresentation(
        kind=kind,
        method=method,
        request_url=request_url,
        response_url=response_url,
        status_code=int(response.status_code),
        headers=headers,
        body=_response_bytes(
            response,
            maximum_bytes=maximum_bytes,
            request_url=response_url,
        ),
        request_parameters=request_parameters,
    )


def _status_error(
    status_code: int,
    *,
    url: str,
    response_text: str,
) -> PublicRecordsHTTPError:
    if status_code in {401, 403}:
        return RestrictedHTTPError(status_code, url=url, response_text=response_text)
    if status_code == 429:
        return RateLimitedHTTPError(status_code, url=url, response_text=response_text)
    if status_code in {404, 410}:
        return SourceChangedHTTPError(status_code, url=url, response_text=response_text)
    return HTTPStatusError(status_code, url=url, response_text=response_text)


def _hidden_fields(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    values: dict[str, str] = {}
    for element in soup.select("form input[type='hidden'][name]"):
        name = _clean(element.get("name"))
        if name:
            values[name] = str(element.get("value") or "")
    return values


class JacksonAccelaClient:
    """Cookie-preserving client for Jackson County's Accela tenant."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        retry_backoff: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval, sleeper=sleeper
        )
        self.retry_policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff_initial=retry_backoff,
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: PublicRecordsHTTPError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            kwargs.setdefault("stream", True)
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
            except requests.RequestException as error:
                last_error = TransportError(
                    f"Jackson County Accela transport failed: {error}",
                    url=url,
                )
            except (OSError, RuntimeError) as error:
                last_error = TransportError(
                    f"Jackson County Accela transport failed: {error}",
                    url=url,
                )
            else:
                status_code = int(response.status_code)
                if 200 <= status_code < 300:
                    return response
                response_url = _response_url(response, url)
                response_encoding = (
                    _clean(getattr(response, "encoding", None)) or "utf-8"
                )
                response_text = _response_bytes(
                    response,
                    maximum_bytes=self.max_response_bytes,
                    request_url=response_url,
                ).decode(response_encoding, errors="replace")
                last_error = _status_error(
                    status_code,
                    url=response_url,
                    response_text=response_text,
                )
                if not last_error.retryable:
                    raise last_error
            if attempt < self.retry_policy.max_attempts:
                self.sleeper(self.retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error

    def fetch_record_page(self, key: RecordKey) -> FetchedRepresentation:
        response = self._request(
            "GET",
            key.detail_url,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                ),
                "User-Agent": USER_AGENT,
            },
        )
        representation = _representation(
            "record_detail",
            "GET",
            key.detail_url,
            response,
            maximum_bytes=self.max_response_bytes,
        )
        _validate_record_page(representation, key)
        return representation

    def fetch_attachment_list(
        self,
        key: RecordKey,
        *,
        referer: str,
    ) -> FetchedRepresentation:
        parameters = {
            "iframeid": "ctl00_PlaceHolderMain_attachmentEdit",
            "module": key.source.module,
            "isInConfirm": "False",
            "isdetail": "True",
            "isaccountmanager": "False",
            "isAdmin": "False",
            "isPeopleDocument": "",
            "agencyCode": TENANT.agency_code,
            "isForConditionDocument": "N",
        }
        request_url = f"{TENANT.attachment_list_url}?{urlencode(parameters)}"
        response = self._request(
            "GET",
            request_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Referer": referer,
                "User-Agent": USER_AGENT,
            },
        )
        representation = _representation(
            "attachment_list",
            "GET",
            request_url,
            response,
            maximum_bytes=self.max_response_bytes,
            request_parameters=parameters,
        )
        if "attachmentList_gdvAttachmentList" not in representation.text:
            empty_marker = "No records found." in representation.text
            if not empty_marker:
                raise SourceSchemaError(
                    "Accela attachment-list representation is missing its grid",
                    url=representation.response_url,
                )
        return representation

    def fetch_document_detail(
        self,
        source: SourceDefinition,
        document_number: str,
    ) -> FetchedRepresentation:
        document_number = _require_document_number(document_number)
        parameters = {
            "Module": source.module,
            "isPeopleDocument": "False",
            "agencyCode": TENANT.agency_code,
            "documentNo": document_number,
            "specificEntity": "",
        }
        request_url = f"{TENANT.document_detail_url}?{urlencode(parameters)}"
        response = self._request(
            "GET",
            request_url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": USER_AGENT,
            },
        )
        representation = _representation(
            "document_detail",
            "GET",
            request_url,
            response,
            maximum_bytes=self.max_response_bytes,
            request_parameters=parameters,
        )
        if "docdetailpage" not in representation.text:
            raise SourceSchemaError(
                "Accela document-detail representation is missing its fields",
                url=representation.response_url,
            )
        return representation

    def fetch_page_method(
        self,
        key: RecordKey,
        method_name: str,
        parameters: Mapping[str, Any],
        *,
        referer: str,
    ) -> FetchedRepresentation:
        request_url = f"{TENANT.record_detail_url}/{method_name}"
        response = self._request(
            "POST",
            request_url,
            json=dict(parameters),
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json; charset=UTF-8",
                "Origin": TENANT.origin,
                "Referer": referer,
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        representation = _representation(
            method_name,
            "POST",
            request_url,
            response,
            maximum_bytes=self.max_response_bytes,
            request_parameters=parameters,
        )
        try:
            payload = json.loads(representation.text)
        except json.JSONDecodeError as error:
            raise SourceResponseError(
                f"Accela {method_name} returned invalid JSON: {error}",
                url=representation.response_url,
            ) from error
        if not isinstance(payload, Mapping) or not isinstance(payload.get("d"), str):
            raise SourceSchemaError(
                f"Accela {method_name} response is missing its HTML payload",
                url=representation.response_url,
            )
        return representation

    def fetch_inspections(
        self,
        key: RecordKey,
        record_page: FetchedRepresentation,
    ) -> FetchedRepresentation:
        form = _hidden_fields(record_page.text)
        form["__EVENTTARGET"] = INSPECTION_EVENT_TARGET
        form["__EVENTARGUMENT"] = ""
        response = self._request(
            "POST",
            record_page.response_url,
            data=form,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Origin": TENANT.origin,
                "Referer": record_page.response_url,
                "User-Agent": USER_AGENT,
            },
        )
        representation = _representation(
            "inspections",
            "POST",
            record_page.response_url,
            response,
            maximum_bytes=self.max_response_bytes,
            request_parameters={"__EVENTTARGET": INSPECTION_EVENT_TARGET},
        )
        _validate_record_page(representation, key)
        return representation

    def download_attachment(
        self,
        listing: FetchedRepresentation,
        event_target: str,
    ) -> FetchedRepresentation:
        form = _hidden_fields(listing.text)
        form["__EVENTTARGET"] = event_target
        form["__EVENTARGUMENT"] = ""
        response = self._request(
            "POST",
            listing.response_url,
            data=form,
            headers={
                "Accept": "*/*",
                "Origin": TENANT.origin,
                "Referer": listing.response_url,
                "User-Agent": USER_AGENT,
            },
        )
        representation = _representation(
            "document_binary",
            "POST",
            listing.response_url,
            response,
            maximum_bytes=self.max_response_bytes,
            request_parameters={"__EVENTTARGET": event_target},
        )
        content_type = (
            _header(representation.headers, "Content-Type") or ""
        ).casefold()
        disposition = (
            _header(representation.headers, "Content-Disposition") or ""
        ).casefold()
        if "html" in content_type or (
            "attachment" not in disposition
            and representation.body.lstrip().startswith(b"<")
        ):
            raise SourceResponseError(
                "Accela attachment postback did not return a binary document",
                url=representation.response_url,
            )
        return representation


def _validate_record_page(
    representation: FetchedRepresentation, key: RecordKey
) -> None:
    final_path = urlparse(representation.response_url).path.casefold()
    text = representation.text
    has_record_marker = "ctl00_PlaceHolderMain_lblPermitNumber" in text
    if final_path.endswith("/error.aspx"):
        raise SourceResponseError(
            f"Accela did not expose the {key.source.module} record detail",
            url=representation.response_url,
            details={"cap_key": key.compact, "module": key.source.module},
        )
    if not has_record_marker:
        if "technical difficulties" in text.casefold():
            raise SourceResponseError(
                f"Accela did not expose the {key.source.module} record detail",
                url=representation.response_url,
                details={"cap_key": key.compact, "module": key.source.module},
            )
        raise SourceSchemaError(
            "Accela record detail is missing its record-number field",
            url=representation.response_url,
            details={"cap_key": key.compact, "module": key.source.module},
        )


def _parse_record_details(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    table = soup.select_one(
        "#ctl00_PlaceHolderMain_PermitDetailList1_TBPermitDetailTest"
    )
    if table is None:
        return []
    details: list[dict[str, str | None]] = []
    for cell in table.select("td.td_parent_left"):
        heading = cell.find(["h1", "h2"])
        label = (_element_text(heading) or "").rstrip(":").strip()
        if not label:
            continue
        content = BeautifulSoup(str(cell), "html.parser")
        for candidate in content.find_all(["h1", "h2"]):
            candidate.decompose()
        for candidate in content.select("a[id='link_licenseProfessional'], a[title]"):
            candidate.decompose()
        details.append(
            {
                "label": label,
                "value": _element_text(content),
                "raw_text": _element_text(cell),
            }
        )
    return details


def _parse_additional_information(
    soup: BeautifulSoup,
) -> list[dict[str, str | None]]:
    container = soup.select_one("#trADIList")
    if container is None:
        return []
    items: list[dict[str, str | None]] = []
    for column in container.select(".MoreDetail_ItemCol"):
        heading = column.find("h2")
        if heading is None:
            continue
        label = (_element_text(heading) or "").rstrip(":").strip()
        value = column.select_one(".ACA_SmLabel")
        if label:
            items.append(
                {
                    "label": label,
                    "value": _element_text(value),
                    "raw_text": _element_text(column),
                }
            )
    return items


def _parse_application_information(
    soup: BeautifulSoup,
) -> list[dict[str, Any]]:
    container = soup.select_one("#trASIList")
    if container is None:
        return []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"section": None, "fields": []}
    for element in container.select(".MoreDetail_ItemTitle, .ACA_SmLabelBolder"):
        classes = set(element.get("class") or [])
        if "MoreDetail_ItemTitle" in classes:
            if current["fields"]:
                sections.append(current)
            current = {
                "section": _element_text(element),
                "fields": [],
            }
            continue
        label = (_element_text(element) or "").rstrip(":").strip()
        value_element = element.find_next_sibling(
            class_=lambda value: value and "ACA_SmLabel" in value
        )
        parent = element.parent
        if value_element is None and isinstance(parent, Tag):
            value_element = next(
                (
                    candidate
                    for candidate in parent.select(".ACA_SmLabel")
                    if candidate is not element
                    and "ACA_SmLabelBolder" not in (candidate.get("class") or [])
                ),
                None,
            )
        if value_element is None and isinstance(parent, Tag):
            sibling = parent.find_next_sibling()
            if isinstance(sibling, Tag):
                value_element = sibling.select_one(".ACA_SmLabel")
        if label:
            current["fields"].append(
                {
                    "label": label,
                    "value": _element_text(value_element),
                    "raw_text": _element_text(element.parent),
                }
            )
    if current["fields"]:
        sections.append(current)
    return sections


def _parse_related_contacts(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    container = soup.select_one("#trRCList")
    if container is None:
        return []
    contacts: list[dict[str, str | None]] = []
    for item in container.select(".MoreDetail_ItemCol"):
        heading = item.find("h2")
        if heading is None:
            continue
        clone = BeautifulSoup(str(item), "html.parser")
        clone_heading = clone.find("h2")
        if clone_heading is not None:
            clone_heading.decompose()
        contacts.append(
            {
                "role": _element_text(heading),
                "value": _element_text(clone),
                "raw_text": _element_text(item),
            }
        )
    return contacts


def _parse_parcels(soup: BeautifulSoup) -> list[dict[str, Any]]:
    container = soup.select_one("#trParcelList")
    if container is None:
        return []
    parcels: list[dict[str, Any]] = []
    for item in container.select(".MoreDetail_ItemCol2"):
        if item.find("h2", recursive=False) is None:
            continue
        text = _element_text(item)
        if not text or "Parcel Number:" not in text:
            continue
        parcel_match = re.search(r"Parcel Number:\s*([A-Za-z0-9-]+)", text, re.I)
        block_match = re.search(r"\bBlock:\s*([^ ]+)", text, re.I)
        lot_match = re.search(r"\bLot:\s*([^ ]+)", text, re.I)
        subdivision_match = re.search(
            r"\bSubdivision:\s*([^:]+?)(?=\s+[A-Z][A-Z ]+:|$)",
            text,
        )
        attributes = []
        for row in item.select("tr"):
            row_text = _element_text(row)
            if not row_text or ":" not in row_text:
                continue
            if any(
                marker in row_text
                for marker in (
                    "Parcel Number:",
                    "Block:",
                    "Lot:",
                    "Subdivision:",
                )
            ):
                continue
            label, value = row_text.split(":", 1)
            normalized_label = _clean(label)
            normalized_value = _clean(value)
            if normalized_label and normalized_value:
                attributes.append(
                    {
                        "label": normalized_label,
                        "value": normalized_value,
                    }
                )
        parcels.append(
            {
                "parcel_number": (parcel_match.group(1) if parcel_match else None),
                "block": block_match.group(1) if block_match else None,
                "lot": lot_match.group(1) if lot_match else None,
                "subdivision": (
                    _clean(subdivision_match.group(1)) if subdivision_match else None
                ),
                "attributes": attributes,
                "raw_text": text,
            }
        )
    return parcels


def _parse_conditions(soup: BeautifulSoup) -> dict[str, Any]:
    notice = _element_text(
        soup.select_one("#ctl00_PlaceHolderMain_capConditions_lblNotice")
    )
    items: list[dict[str, str | None]] = []
    table = soup.select_one(
        "#ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList"
    )
    if table is not None:
        for info in table.select("[id$='_lblGeneralConditionsInfo']"):
            row = info.find_parent("tr")
            group = (
                row.select_one("[id$='_lblGeneralConditionsGroupName']")
                if row
                else None
            )
            condition_type = (
                row.select_one("[id$='_lblGeneralConditionsType']") if row else None
            )
            info_parts = [
                _clean(value) for value in info.stripped_strings if _clean(value)
            ]
            items.append(
                {
                    "group": _element_text(group),
                    "condition_type": _element_text(condition_type),
                    "name": info_parts[0] if info_parts else None,
                    "description": (info_parts[1] if len(info_parts) > 1 else None),
                    "status": (info_parts[2] if len(info_parts) > 2 else None),
                    "raw_text": _element_text(row or info),
                }
            )
    return {"notice": notice, "items": items}


def parse_record_detail(html: str) -> dict[str, Any]:
    """Parse the server-rendered Accela record-detail representation."""

    soup = BeautifulSoup(html, "html.parser")
    record_number = _element_text(
        soup.select_one("#ctl00_PlaceHolderMain_lblPermitNumber")
    )
    if not record_number:
        raise ValueError("record detail does not contain a record number")
    application_sections = _parse_application_information(soup)
    schema = {
        "summary_fields": [
            "record_number",
            "record_type",
            "record_status",
            "expiration_date",
            "work_location",
        ],
        "record_detail_labels": [item["label"] for item in _parse_record_details(soup)],
        "additional_information_labels": [
            item["label"] for item in _parse_additional_information(soup)
        ],
        "application_information": [
            {
                "section": section["section"],
                "labels": [item["label"] for item in section["fields"]],
            }
            for section in application_sections
        ],
    }
    return {
        "record_number": record_number,
        "record_type": _element_text(
            soup.select_one("#ctl00_PlaceHolderMain_lblPermitType")
        ),
        "record_status": _element_text(
            soup.select_one("#ctl00_PlaceHolderMain_lblRecordStatus")
        ),
        "expiration_date": _element_text(
            soup.select_one("#ctl00_PlaceHolderMain_lblExpirtionDate")
        ),
        "work_location": _element_text(
            soup.select_one("#ctl00_PlaceHolderMain_workLocation_TBPermitDetailTest")
        ),
        "record_details": _parse_record_details(soup),
        "related_contacts": _parse_related_contacts(soup),
        "additional_information": _parse_additional_information(soup),
        "application_information": application_sections,
        "parcels": _parse_parcels(soup),
        "conditions": _parse_conditions(soup),
        "schema": schema,
        "schema_fingerprint": schema_fingerprint(schema),
    }


def _document_detail_url(source: SourceDefinition, document_number: str) -> str:
    parameters = {
        "Module": source.module,
        "isPeopleDocument": "False",
        "agencyCode": TENANT.agency_code,
        "documentNo": document_number,
        "specificEntity": "",
    }
    return f"{TENANT.document_detail_url}?{urlencode(parameters)}"


def _postback_target(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"__doPostBack\(['\"]([^'\"]+)", value)
    if not match:
        match = re.search(r"__doPostBack\(&#39;([^&]+)", value)
    return match.group(1) if match else None


def parse_attachment_list(
    html: str,
    source: SourceDefinition,
    listing_url: str,
) -> list[dict[str, Any]]:
    """Parse attachment metadata, stable detail URLs, and postback targets."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#attachmentList_gdvAttachmentList")
    if table is None:
        return []
    documents: list[dict[str, Any]] = []
    for row in table.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        action = row.find("a", attrs={"onclick": re.compile(r"ViewDocumentDetails")})
        document_match = (
            re.search(
                r"ViewDocumentDetails\([^,]+,\s*['\"](\d+)['\"]",
                str(action.get("onclick")),
            )
            if action
            else None
        )
        document_number = document_match.group(1) if document_match else None
        if not document_number:
            continue

        def suffix_text(suffix: str) -> str | None:
            return _element_text(row.select_one(f"[id$='{suffix}']"))

        filename_link = row.select_one("a[id$='_lnkFileName']")
        event_target = _postback_target(
            str(filename_link.get("href")) if filename_link else None
        )
        filename = suffix_text("_lblName") or suffix_text("_lblFileName")
        documents.append(
            {
                "document_number": document_number,
                "description": suffix_text("_lblDescription"),
                "file_name": filename,
                "document_type": suffix_text("_lblType"),
                "virtual_folders": suffix_text("_lblVirtualFolders"),
                "file_size": suffix_text("_lblSize"),
                "latest_update": suffix_text("_lblDate"),
                "document_status": suffix_text("_lblDocumentStatus"),
                "document_detail_url": _document_detail_url(source, document_number),
                "listing_url": listing_url,
                "download_event_target": event_target,
                "binary_download_available": event_target is not None,
                "raw_text": _element_text(row),
            }
        )
    return documents


def parse_document_detail(html: str) -> dict[str, Any]:
    """Parse one independently addressable Accela document-detail page."""

    soup = BeautifulSoup(html, "html.parser")
    fields: list[dict[str, str | None]] = []
    for label_element in soup.select(".docdetailpage .fieldlabel"):
        label = (_element_text(label_element) or "").rstrip(":").strip()
        element_id = _clean(label_element.get("id"))
        value = soup.select_one(f"#{element_id}_value") if element_id else None
        if label:
            fields.append(
                {
                    "label": label,
                    "value": _element_text(value),
                }
            )
    if not fields:
        raise ValueError("document detail does not contain public fields")
    schema = {"field_labels": [field["label"] for field in fields]}
    return {
        "fields": fields,
        "field_map": {field["label"]: field["value"] for field in fields},
        "schema": schema,
        "schema_fingerprint": schema_fingerprint(schema),
    }


def _page_method_html(representation: FetchedRepresentation) -> str:
    payload = json.loads(representation.text)
    return str(payload["d"])


def parse_processing(html: str) -> list[dict[str, Any]]:
    """Parse current and historic Accela processing steps."""

    soup = BeautifulSoup(html, "html.parser")
    steps: list[dict[str, Any]] = []
    for row in soup.select("tr"):
        detail_id = _clean(row.get("id"))
        if detail_id:
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        icon = cells[0].find("img", attrs={"title": True})
        task_name = _element_text(cells[-1])
        expand = cells[0].find("a", attrs={"onclick": re.compile("ControlDisplay")})
        if not icon or not task_name or expand is None:
            continue
        detail_match = re.search(
            r'\$get\(["\']([^"\']+)["\']\)', str(expand.get("onclick"))
        )
        detail_row = soup.find("tr", id=detail_match.group(1)) if detail_match else None
        detail_text = _element_text(detail_row)
        history: list[dict[str, str | None]] = []
        if detail_row is not None:
            for history_row in detail_row.select(
                "tr.ACA_TabRow_Bold, tr.ACA_TabRow_Italic"
            ):
                text = _element_text(history_row)
                if not text:
                    continue
                match = re.search(
                    r"Due on (.*?), assigned to (.*?)(?: Marked as "
                    r"(.*?) on (.*?) by (.*))?$",
                    text,
                )
                history.append(
                    {
                        "due_date": (_clean(match.group(1)) if match else None),
                        "assigned_to": (_clean(match.group(2)) if match else None),
                        "marked_status": (
                            _clean(match.group(3)) if match and match.group(3) else None
                        ),
                        "marked_date": (
                            _clean(match.group(4)) if match and match.group(4) else None
                        ),
                        "marked_by": (
                            _clean(match.group(5)) if match and match.group(5) else None
                        ),
                        "raw_text": text,
                    }
                )
        steps.append(
            {
                "task_name": task_name,
                "state": _clean(icon.get("title")) or _clean(icon.get("alt")),
                "detail_id": (detail_match.group(1) if detail_match else None),
                "history": history,
                "raw_text": detail_text,
            }
        )
    return steps


def _table_rows(html: str) -> tuple[list[str], list[dict[str, str | None]]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return [], []
    headers = [
        _element_text(header) or f"column_{index + 1}"
        for index, header in enumerate(table.find_all("th"))
    ]
    rows: list[dict[str, str | None]] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        values = [_element_text(cell) for cell in cells]
        if headers and len(values) >= len(headers):
            rows.append(
                {
                    headers[index]: values[index]
                    for index in range(len(headers))
                    if headers[index]
                }
            )
    return headers, rows


def parse_related_records(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tableCapTreeList")
    if table is None:
        return []
    records: list[dict[str, Any]] = []
    for row in table.select("tr[id]"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        record_number = _element_text(cells[0])
        if not record_number:
            continue
        records.append(
            {
                "record_number": record_number,
                "record_type": _element_text(cells[1]),
                "project_name": _element_text(cells[2]),
                "opened_date": _element_text(cells[3]),
                "tree_node_id": _clean(row.get("id")),
                "raw_text": _element_text(row),
            }
        )
    return records


def parse_fees(html: str) -> dict[str, Any]:
    headers, rows = _table_rows(html)
    text = _clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    total_match = re.search(r"Total [^:]+:\s*(\$[\d,.]+)", text or "", re.I)
    schema = {"headers": headers}
    return {
        "rows": rows,
        "total": total_match.group(1) if total_match else None,
        "raw_text": text,
        "schema": schema,
        "schema_fingerprint": schema_fingerprint(schema),
    }


def parse_inspections(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    groups: list[dict[str, Any]] = []
    selectors = (
        (
            "upcoming",
            "#ctl00_PlaceHolderMain_InspectionList_gvListUpcoming",
        ),
        (
            "completed",
            "#ctl00_PlaceHolderMain_InspectionList_gvListCompleted",
        ),
    )
    for group_name, selector in selectors:
        table = soup.select_one(selector)
        if table is None:
            continue
        entries: list[dict[str, Any]] = []
        for row in table.select("tr.InspectionListRow"):
            text = _element_text(row)
            detail_link = row.find(
                "a", attrs={"onclick": re.compile("InspectionDetails.aspx")}
            )
            detail_url = None
            if detail_link is not None:
                match = re.search(
                    r"showInspectionPopupDialog\(['\"]([^'\"]+)",
                    str(detail_link.get("onclick")),
                )
                if match:
                    detail_url = urljoin(TENANT.tenant_root, match.group(1))
            status_match = re.match(r"([A-Za-z ]+)\s+(.+?)\s+\((\d+)\)", text or "")
            result_match = re.search(
                r"Result by:\s*(.*?)\s+on\s+(.*?)\s+at\s+(.*?)(?: View Details)?$",
                text or "",
            )
            entries.append(
                {
                    "status": (_clean(status_match.group(1)) if status_match else None),
                    "inspection_name": (
                        _clean(status_match.group(2)) if status_match else None
                    ),
                    "inspection_id": (status_match.group(3) if status_match else None),
                    "result_by": (
                        _clean(result_match.group(1)) if result_match else None
                    ),
                    "result_date": (
                        _clean(result_match.group(2)) if result_match else None
                    ),
                    "result_time": (
                        _clean(result_match.group(3)) if result_match else None
                    ),
                    "detail_url": detail_url,
                    "raw_text": text,
                }
            )
        groups.append({"group": group_name, "entries": entries})
    return {"groups": groups}


def _require_document_number(value: str) -> str:
    document_number = str(value).strip()
    if not re.fullmatch(r"\d+", document_number):
        raise ValueError("document number must contain only digits")
    return document_number


def _source(value: str) -> SourceDefinition:
    try:
        return SOURCES[str(value).casefold()]
    except KeyError as error:
        raise ValueError(f"unknown Jackson County Accela source {value!r}") from error


def _query(
    source: SourceDefinition,
    operation: str,
    parameters: Mapping[str, Any],
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source.source_metadata(),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=f"US-OR-{COUNTY_GEOID}",
            name=COUNTY_NAME,
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
            locality="Jackson County",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            metadata={"platform_family": PLATFORM_FAMILY},
        ),
    )


def _field_map(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        str(item["label"]): item.get("value") for item in items if item.get("label")
    }


def _record_output(
    key: RecordKey,
    record_page: FetchedRepresentation,
    attachment_list: FetchedRepresentation,
    processing: FetchedRepresentation,
    related: FetchedRepresentation,
    fees_unpaid: FetchedRepresentation,
    fees_paid: FetchedRepresentation,
    inspections: FetchedRepresentation,
) -> dict[str, Any]:
    record = parse_record_detail(record_page.text)
    documents = parse_attachment_list(
        attachment_list.text,
        key.source,
        attachment_list.response_url,
    )
    processing_steps = parse_processing(_page_method_html(processing))
    related_records = parse_related_records(_page_method_html(related))
    unpaid = parse_fees(_page_method_html(fees_unpaid))
    paid = parse_fees(_page_method_html(fees_paid))
    inspection_records = parse_inspections(inspections.text)
    detail_map = _field_map(record["record_details"])
    representations = {
        value.kind: value.snapshot()
        for value in (
            record_page,
            attachment_list,
            processing,
            related,
            fees_unpaid,
            fees_paid,
            inspections,
        )
    }
    return {
        "canonical_ref": canonical_property_ref(
            key.source.source_id,
            COUNTY_GEOID,
            key.source.record_kind,
            record["record_number"],
        ),
        "source_id": key.source.source_id,
        "record_kind": key.source.record_kind,
        "platform_family": PLATFORM_FAMILY,
        "agency_code": TENANT.agency_code,
        "module": key.source.module,
        "record_key": key.to_dict(),
        "native_record_id": record["record_number"],
        "record_type": record["record_type"],
        "status": record["record_status"],
        "expiration_date": record["expiration_date"],
        "work_location": record["work_location"],
        "record_details": record["record_details"],
        "record_detail_map": detail_map,
        "participants": {
            "applicant": detail_map.get("Applicant"),
            "owner": detail_map.get("Owner"),
            "licensed_professional": detail_map.get("Licensed Professional"),
        },
        "project_description": detail_map.get("Project Description"),
        "related_contacts": record["related_contacts"],
        "additional_information": record["additional_information"],
        "application_information": record["application_information"],
        "parcels": record["parcels"],
        "conditions": record["conditions"],
        "documents": documents,
        "processing_steps": processing_steps,
        "related_records": related_records,
        "fees": {"unpaid": unpaid, "paid": paid},
        "inspections": inspection_records,
        "source_urls": {
            "record_detail": record_page.response_url,
            "arcgis_index": key.source.arcgis_url,
            "records_request": RECORDS_REQUEST_URL,
        },
        "representations": representations,
        "field_provenance": {
            "record_identity_and_detail": "record_detail",
            "documents": "attachment_list",
            "processing_steps": "GetProcessingData",
            "related_records": "GetBuildCapTree",
            "fees_unpaid": "DisplayFeeNoPaid",
            "fees_paid": "DisplayFeePaid",
            "inspections": "inspections",
        },
        "schema": record["schema"],
        "schema_fingerprint": record["schema_fingerprint"],
        "document_representation_summary": {
            "listing_complete": True,
            "document_details_fetched": False,
            "binary_documents_fetched": False,
            "detail_and_binary_commands_available": True,
        },
        "snapshot_complete": True,
    }


def fetch_record(client: JacksonAccelaClient, key: RecordKey) -> dict[str, Any]:
    record_page = client.fetch_record_page(key)
    referer = record_page.response_url
    attachment_list = client.fetch_attachment_list(key, referer=referer)
    processing = client.fetch_page_method(
        key,
        "GetProcessingData",
        {
            "agencyCode": TENANT.agency_code,
            "moduleName": key.source.module,
        },
        referer=referer,
    )
    related = client.fetch_page_method(
        key,
        "GetBuildCapTree",
        {"moduleName": key.source.module, "isShowAll": "false"},
        referer=referer,
    )
    fees_unpaid = client.fetch_page_method(
        key,
        "DisplayFeeNoPaid",
        {"pageNum": "1", "moduleName": key.source.module},
        referer=referer,
    )
    fees_paid = client.fetch_page_method(
        key,
        "DisplayFeePaid",
        {
            "pageNum": "1",
            "moduleName": key.source.module,
            "reportName": "",
            "receiptNbr": "0",
            "reportID": "0",
            "displayReceiptReport": "False",
        },
        referer=referer,
    )
    inspections = client.fetch_inspections(key, record_page)
    return _record_output(
        key,
        record_page,
        attachment_list,
        processing,
        related,
        fees_unpaid,
        fees_paid,
        inspections,
    )


def fetch_document(
    client: JacksonAccelaClient,
    source: SourceDefinition,
    document_number: str,
) -> dict[str, Any]:
    representation = client.fetch_document_detail(source, document_number)
    parsed = parse_document_detail(representation.text)
    field_map = parsed["field_map"]
    native_record_id = field_map.get("Record Number")
    native_id = (
        f"{native_record_id}:{document_number}" if native_record_id else document_number
    )
    return {
        "canonical_ref": canonical_property_ref(
            source.source_id,
            COUNTY_GEOID,
            "accela_document_detail",
            native_id,
        ),
        "source_id": source.source_id,
        "record_kind": "accela_document_detail",
        "platform_family": PLATFORM_FAMILY,
        "agency_code": TENANT.agency_code,
        "module": source.module,
        "document_number": document_number,
        "fields": parsed["fields"],
        "field_map": field_map,
        "document_detail_url": representation.response_url,
        "representation": representation.snapshot(),
        "schema": parsed["schema"],
        "schema_fingerprint": parsed["schema_fingerprint"],
    }


def fetch_download(
    client: JacksonAccelaClient,
    key: RecordKey,
    document_number: str,
    destination: Path,
) -> dict[str, Any]:
    document_number = _require_document_number(document_number)
    record_page = client.fetch_record_page(key)
    listing = client.fetch_attachment_list(key, referer=record_page.response_url)
    documents = parse_attachment_list(listing.text, key.source, listing.response_url)
    document = next(
        (item for item in documents if item["document_number"] == document_number),
        None,
    )
    if document is None:
        raise SourceResponseError(
            f"document {document_number} is not listed on record {key.compact}",
            url=listing.response_url,
        )
    event_target = document.get("download_event_target")
    if not event_target:
        raise SourceResponseError(
            f"document {document_number} has metadata but no binary postback",
            url=listing.response_url,
            details={"document_detail_url": document["document_detail_url"]},
        )
    binary = client.download_attachment(listing, str(event_target))
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary.body)
    return {
        "source_id": key.source.source_id,
        "record_kind": "accela_document_binary",
        "platform_family": PLATFORM_FAMILY,
        "agency_code": TENANT.agency_code,
        "module": key.source.module,
        "record_key": key.to_dict(),
        "document_number": document_number,
        "document": document,
        "destination": str(destination),
        "representation": binary.snapshot(),
        "record_detail_representation": record_page.snapshot(),
        "attachment_list_representation": listing.snapshot(),
    }


def _code_compliance_component() -> dict[str, Any]:
    return {
        "source_id": CODE_SOURCE_ID,
        "name": "Jackson County Code Compliance Events",
        "detail_representation_available": False,
        "verified_route_observation": (
            "The official GIS record link resolves to Accela sign-on, and the "
            "analogous anonymous Citizen Access detail route resolves to the "
            "tenant error page."
        ),
        "complements": [
            {
                "kind": "official_arcgis_event_layer",
                "source_id": CODE_SOURCE_ID,
                "url": CODE_ARCGIS_URL,
            },
            {
                "kind": "county_records_request",
                "url": RECORDS_REQUEST_URL,
            },
        ],
        "observed_official_portlet_url": CODE_PORTLET_URL,
    }


def sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": PLATFORM_FAMILY,
        "tenant": {
            "agency_code": TENANT.agency_code,
            "tenant_root": TENANT.tenant_root,
            "record_detail_url": TENANT.record_detail_url,
            "attachment_list_url": TENANT.attachment_list_url,
            "document_detail_url": TENANT.document_detail_url,
        },
        "sources": [
            {
                **source.source_metadata().to_dict(),
                "module_key": source.key,
                "sample_cap_key": source.sample_cap_key,
                "representations": [
                    "record_detail",
                    "attachment_list",
                    "document_detail",
                    "document_binary",
                    "processing_status",
                    "related_records",
                    "fees",
                    "inspections",
                ],
            }
            for source in SOURCES.values()
        ],
        "code_compliance": _code_compliance_component(),
        "process_learnings": [
            {
                "scope": "accela_tenant_contract",
                "learning": (
                    "Tenant root, agency code, module, three CAP components, "
                    "record-session pages, and stable document numbers form a "
                    "reusable Accela Citizen Access source contract."
                ),
            },
            {
                "scope": "representation_identity",
                "learning": (
                    "ArcGIS event rows, Accela record details, attachment "
                    "listings, stable document details, and binary postbacks "
                    "remain distinct representations joined by native IDs."
                ),
            },
            {
                "scope": "session_and_postback_discovery",
                "learning": (
                    "Record-bound iframe and page-method discovery should occur "
                    "after a detail bootstrap; stable document-detail URLs can "
                    "be fetched independently by document number."
                ),
            },
            {
                "scope": "source_shell_validation",
                "learning": (
                    "Accela's shared page shell can contain generic error copy "
                    "on valid pages; health checks should combine the final "
                    "route with required record markers."
                ),
            },
            {
                "scope": "alternative_source_triage",
                "learning": (
                    "When a module lacks an anonymous detail route, retain the "
                    "official structured index and records-request path instead "
                    "of treating an analogous route as verified."
                ),
            },
        ],
    }


def _best_effort_log(
    query: PublicRecordsQuery,
    source_id: str,
    result: PublicRecordsResult,
) -> None:
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
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception:
        pass


def execute_record(
    client: JacksonAccelaClient,
    key: RecordKey,
    *,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(
        key.source,
        "record",
        {"record_key": key.to_dict(), "record_url": key.detail_url},
    )
    try:
        result = PublicRecordsResult.success(query, [fetch_record(client, key)])
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="accela_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
        )
    if log_results:
        _best_effort_log(query, key.source.source_id, result)
    return result


def execute_document(
    client: JacksonAccelaClient,
    source: SourceDefinition,
    document_number: str,
    *,
    log_results: bool = True,
) -> PublicRecordsResult:
    document_number = _require_document_number(document_number)
    query = _query(
        source,
        "document",
        {"document_number": document_number},
    )
    try:
        result = PublicRecordsResult.success(
            query, [fetch_document(client, source, document_number)]
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError, KeyError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="accela_document_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
        )
    if log_results:
        _best_effort_log(query, source.source_id, result)
    return result


def execute_download(
    client: JacksonAccelaClient,
    key: RecordKey,
    document_number: str,
    destination: Path,
    *,
    log_results: bool = True,
) -> PublicRecordsResult:
    document_number = _require_document_number(document_number)
    query = _query(
        key.source,
        "download",
        {
            "record_key": key.to_dict(),
            "document_number": document_number,
            "destination": str(destination),
        },
    )
    try:
        result = PublicRecordsResult.success(
            query,
            [fetch_download(client, key, document_number, destination)],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    if log_results:
        _best_effort_log(query, key.source.source_id, result)
    return result


def probe_source(
    client: JacksonAccelaClient,
    source: SourceDefinition,
    *,
    log_results: bool = True,
) -> PublicRecordsResult:
    key = parse_cap_key(source, source.sample_cap_key)
    query = _query(
        source,
        "probe",
        {"record_key": key.to_dict(), "record_url": key.detail_url},
    )
    try:
        record_page = client.fetch_record_page(key)
        parsed = parse_record_detail(record_page.text)
        attachments = client.fetch_attachment_list(
            key, referer=record_page.response_url
        )
        documents = parse_attachment_list(
            attachments.text, source, attachments.response_url
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": source.source_id,
                    "module": source.module,
                    "native_record_id": parsed["record_number"],
                    "record_status": parsed["record_status"],
                    "document_count": len(documents),
                    "schema_fingerprint": parsed["schema_fingerprint"],
                    "record_detail_representation": record_page.snapshot(),
                    "attachment_list_representation": attachments.snapshot(),
                    "arcgis_complement": {
                        "source_id": source.arcgis_source_id,
                        "url": source.arcgis_url,
                    },
                }
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError, KeyError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="accela_probe_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
        )
    if log_results:
        _best_effort_log(query, source.source_id, result)
    return result


def probe_payload(
    client: JacksonAccelaClient,
    selected: Sequence[SourceDefinition],
    *,
    log_results: bool = True,
) -> dict[str, Any]:
    components = [
        probe_source(client, source, log_results=log_results).to_dict()
        for source in selected
    ]
    successful = sum(
        component["status"] in {"ok", "no_results"} for component in components
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": (
            "ok"
            if successful == len(components)
            else "partial"
            if successful
            else "unavailable"
        ),
        "components": components,
        "code_compliance": _code_compliance_component(),
    }


def _client(args: argparse.Namespace) -> JacksonAccelaClient:
    return JacksonAccelaClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=args.retry_attempts,
        max_response_bytes=args.max_response_bytes,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: JacksonAccelaClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    if args.command == "sources":
        return sources_payload()
    active_client = client or _client(args)
    owns_client = client is None
    try:
        if args.command == "record":
            key = parse_cap_key(_source(args.module), args.cap_key)
            return execute_record(active_client, key, log_results=log_results)
        if args.command == "record-url":
            key = parse_record_url(args.url)
            return execute_record(active_client, key, log_results=log_results)
        if args.command == "document":
            return execute_document(
                active_client,
                _source(args.module),
                args.document_number,
                log_results=log_results,
            )
        if args.command == "download":
            key = parse_cap_key(_source(args.module), args.cap_key)
            return execute_download(
                active_client,
                key,
                args.document_number,
                Path(args.destination),
                log_results=log_results,
            )
        if args.command == "probe":
            selected = (
                list(SOURCES.values()) if args.all_sources else [_source(args.module)]
            )
            return probe_payload(active_client, selected, log_results=log_results)
        raise ValueError(f"unknown command {args.command!r}")
    finally:
        if owns_client:
            active_client.close()


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
        help="Maximum bytes accepted for any one HTML, JSON, or document response",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Fetch official Jackson County Accela record and document details")
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List verified modules and routes")
    add_output_args(sources)

    record = sub.add_parser(
        "record", help="Fetch a Building or Planning record by CAP key"
    )
    record.add_argument("module", choices=sorted(SOURCES))
    record.add_argument("cap_key", help="capID1-capID2-capID3")
    _add_transport_arguments(record)

    record_url = sub.add_parser(
        "record-url", help="Fetch an official Jackson County Accela detail URL"
    )
    record_url.add_argument("url")
    _add_transport_arguments(record_url)

    document = sub.add_parser(
        "document", help="Fetch stable document metadata by document number"
    )
    document.add_argument("module", choices=sorted(SOURCES))
    document.add_argument("document_number")
    _add_transport_arguments(document)

    download = sub.add_parser(
        "download", help="Fetch a listed binary document representation"
    )
    download.add_argument("module", choices=sorted(SOURCES))
    download.add_argument("cap_key", help="capID1-capID2-capID3")
    download.add_argument("document_number")
    download.add_argument("--destination", required=True)
    _add_transport_arguments(download)

    probe = sub.add_parser("probe", help="Run bounded live source probes")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--module", choices=sorted(SOURCES))
    selection.add_argument("--all", action="store_true", dest="all_sources")
    probe.set_defaults(all_sources=False)
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
    if write_output(
        payload,
        args,
        summary=f"Jackson County Accela {args.command}",
        result_count=(
            len(payload.get("records", []))
            if "records" in payload
            else len(payload.get("components", payload.get("sources", [])))
        ),
    ):
        return
    if args.command == "sources":
        print(f"Jackson County Accela modules: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['module_key']} | {source['source_id']} | "
                f"{source['metadata']['module']}"
            )
        print("  code compliance | ArcGIS and records-request complements")
        return
    if args.command == "probe":
        print(f"Jackson County Accela probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | {component['status']}"
            )
        return
    records = payload.get("records", [])
    print(
        f"Jackson County Accela {args.command}: "
        f"{payload.get('status')} ({len(records)} records)"
    )
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    if getattr(args, "max_response_bytes", 1) <= 0:
        parser.error("--max-response-bytes must be positive")
    try:
        value = execute(args)
    except ValueError as error:
        parser.error(str(error))
    _emit(value, args)


if __name__ == "__main__":
    main()
