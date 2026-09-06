#!/usr/bin/env python3
"""Query Oregon's official court and judge directory family.

The Oregon Judicial Department renders these directories from classic
SharePoint lists.  The live page first establishes an anonymous browser
session, then posts SOAP ``GetListItems`` requests without a ``SOAPAction``
header.  This adapter reproduces that source-native flow and keeps the four
published components distinct.

Examples:
    uv run python tools/query_oregon_court_directories.py sources --json
    uv run python tools/query_oregon_court_directories.py views \
        --source us-or-state-judge-directory --output /tmp/or-judge-views.json
    uv run python tools/query_oregon_court_directories.py list \
        --source us-or-local-court-registry --limit 50 \
        --output /tmp/or-local-courts.json
    uv run python tools/query_oregon_court_directories.py search "Deschutes" \
        --source us-or-state-court-directory --output /tmp/or-courts.json
    uv run python tools/query_oregon_court_directories.py discovery \
        --query Bend --output /tmp/or-local-court-source-candidates.json
    uv run python tools/query_oregon_court_directories.py probe \
        --source us-or-local-judge-registry --output /tmp/or-judge-probe.json
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

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


STATE_CODE = "OR"
STATE_GEOID = "41"
AUTHORITY = "Oregon Judicial Department"
PLATFORM_FAMILY = "sharepoint_soap_lists"
BASE_URL = "https://www.courts.oregon.gov/courts"
LISTS_URL = f"{BASE_URL}/_vti_bin/Lists.asmx"
VIEWS_URL = f"{BASE_URL}/_vti_bin/Views.asmx"
LOCATIONS_PAGE_URL = f"{BASE_URL}/Pages/locations.aspx"
JUDGES_PAGE_URL = f"{BASE_URL}/Pages/judges.aspx"
OTHER_COURTS_PAGE_URL = f"{BASE_URL}/Pages/other-courts.aspx"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.1
DEFAULT_MAX_ATTEMPTS = 3
CURSOR_PREFIX = "or-directory:v1:"
CURSOR_VERSION = 1
SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
SHAREPOINT_NAMESPACE = "http://schemas.microsoft.com/sharepoint/soap/"
ROWSET_NAMESPACE = "urn:schemas-microsoft-com:rowset"
ROW_NAMESPACE = "#RowsetSchema"

STATE_COURT_SOURCE_ID = "us-or-state-court-directory"
STATE_JUDGE_SOURCE_ID = "us-or-state-judge-directory"
LOCAL_COURT_SOURCE_ID = "us-or-local-court-registry"
LOCAL_JUDGE_SOURCE_ID = "us-or-local-judge-registry"
SOURCE_IDS = (
    STATE_COURT_SOURCE_ID,
    STATE_JUDGE_SOURCE_ID,
    LOCAL_COURT_SOURCE_ID,
    LOCAL_JUDGE_SOURCE_ID,
)

COUNTY_FIPS = {
    "baker": "41001",
    "benton": "41003",
    "clackamas": "41005",
    "clatsop": "41007",
    "columbia": "41009",
    "coos": "41011",
    "crook": "41013",
    "curry": "41015",
    "deschutes": "41017",
    "douglas": "41019",
    "gilliam": "41021",
    "grant": "41023",
    "harney": "41025",
    "hood river": "41027",
    "jackson": "41029",
    "jefferson": "41031",
    "josephine": "41033",
    "klamath": "41035",
    "lake": "41037",
    "lane": "41039",
    "lincoln": "41041",
    "linn": "41043",
    "malheur": "41045",
    "marion": "41047",
    "morrow": "41049",
    "multnomah": "41051",
    "polk": "41053",
    "sherman": "41055",
    "tillamook": "41057",
    "umatilla": "41059",
    "union": "41061",
    "wallowa": "41063",
    "wasco": "41065",
    "washington": "41067",
    "wheeler": "41069",
    "yamhill": "41071",
}

SOURCE_WARNINGS = (
    "Directory entries are a current source snapshot; Created and Modified "
    "timestamps are preserved for temporal context.",
    "Municipal and justice court registry information is supplied to OJD by "
    "the corresponding city or county.",
    "A directory record identifies a court, official, or assignment; it is "
    "not a case filing or register of actions.",
)


@dataclass(frozen=True)
class ViewDefinition:
    """One configured official SharePoint view."""

    key: str
    view_id: str
    display_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "view_id": self.view_id,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class SourceDefinition:
    """One independently addressable directory component."""

    source_id: str
    name: str
    source_role: str
    page_url: str
    list_name: str
    default_view_key: str
    views: tuple[ViewDefinition, ...]
    record_kind: str
    description: str

    @property
    def configured_views(self) -> Mapping[str, ViewDefinition]:
        return {view.key: view for view in self.views}

    @property
    def default_view(self) -> ViewDefinition:
        return self.configured_views[self.default_view_key]

    @property
    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.page_url,
            dataset_id=f"oregon-ojd-sharepoint:{self.list_name}",
            metadata={
                "authority": AUTHORITY,
                "state_code": STATE_CODE,
                "authentication": "anonymous_cookie_session",
                "platform_family": PLATFORM_FAMILY,
                "list_name": self.list_name,
                "default_view": self.default_view.to_dict(),
                "configured_views": [view.to_dict() for view in self.views],
                "soap_endpoints": {
                    "lists": LISTS_URL,
                    "views": VIEWS_URL,
                },
            },
        )

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Oregon",
            state_code=STATE_CODE,
            metadata={"scope": "statewide_directory"},
        )


SOURCE_DEFINITIONS = (
    SourceDefinition(
        source_id=STATE_COURT_SOURCE_ID,
        name="Oregon State Court Location and Administrator Directory",
        source_role="state_court_location_and_administrator_directory",
        page_url=LOCATIONS_PAGE_URL,
        list_name="TCA-Locations",
        default_view_key="circuit-court-locations",
        views=(
            ViewDefinition(
                "circuit-court-locations",
                "{0192E39C-B0C9-42BF-AB9B-41736025D844}",
                "Circuit Court Locations and Contacts",
            ),
            ViewDefinition(
                "trial-court-administrators",
                "{0E71FA80-8638-49A9-A9BA-4344664B26AB}",
                "Trial Court Administrators",
            ),
            ViewDefinition(
                "circuit-other-locations",
                "{1594D1D8-9F8E-4118-AB9D-FE63A6FC1FCA}",
                "Circuit Courts Other Locations",
            ),
            ViewDefinition(
                "statewide-locations",
                "{D2980D29-A37B-4C8C-8841-9323C2A51399}",
                "Statewide Courts Locations and Contacts",
            ),
            ViewDefinition(
                "statewide-other-locations",
                "{9874A59E-D439-4807-9D25-656467512756}",
                "Statewide Courts Other Locations",
            ),
        ),
        record_kind="state_court_directory_entry",
        description=(
            "Circuit and statewide court locations, contact information, "
            "alternate locations, and trial court administrators."
        ),
    ),
    SourceDefinition(
        source_id=STATE_JUDGE_SOURCE_ID,
        name="Oregon State Judge Directory",
        source_role="state_judge_directory",
        page_url=JUDGES_PAGE_URL,
        list_name="Judges",
        default_view_key="judges",
        views=(
            ViewDefinition(
                "judges",
                "{C4B238D3-A4D0-4728-A8F4-D6691300285E}",
                "Judges",
            ),
            ViewDefinition(
                "presiding-judges",
                "{E8A4544E-E274-4E5A-B1DF-6C7077B0294B}",
                "Presiding Judges",
            ),
            ViewDefinition(
                "supreme",
                "{5B91361C-C281-4E28-8897-78AE1DDD0BC7}",
                "Supreme",
            ),
            ViewDefinition(
                "court-of-appeals",
                "{DA08776C-A48E-49AD-B0C0-1A931D55DBB6}",
                "COA",
            ),
            ViewDefinition(
                "tax-regular",
                "{A93D783D-A85E-4621-8CC1-F33DE81DD6B4}",
                "Tax-Regular",
            ),
            ViewDefinition(
                "tax",
                "{EA0AAAE1-E911-47A8-B7AF-7BB66D9C4CD2}",
                "Tax",
            ),
            ViewDefinition(
                "tax-magistrate",
                "{039741C1-B763-4D9C-8440-1D38D1805524}",
                "Tax-Magistrate",
            ),
        ),
        record_kind="state_judge_directory_entry",
        description=(
            "Circuit, appellate, Supreme, and Tax Court judges, titles, "
            "terms, districts, and official contact information."
        ),
    ),
    SourceDefinition(
        source_id=LOCAL_COURT_SOURCE_ID,
        name="Oregon Municipal and Justice Court Registry",
        source_role="municipal_and_justice_court_registry",
        page_url=OTHER_COURTS_PAGE_URL,
        list_name="Municipal & Justice Court Registry",
        default_view_key="court-registry",
        views=(
            ViewDefinition(
                "court-registry",
                "{9DFB7517-70A9-4D79-B6EB-0CF31F83E107}",
                "Court Registry By Court",
            ),
            ViewDefinition(
                "justice-court-boundaries",
                "{7C13B09F-9D8B-463F-844C-DBFE43083389}",
                "Justice Court Boundaries",
            ),
        ),
        record_kind="local_court_registry_entry",
        description=(
            "Municipal and justice court identity, court type, address, "
            "contact, certification date, and local official website."
        ),
    ),
    SourceDefinition(
        source_id=LOCAL_JUDGE_SOURCE_ID,
        name="Oregon Municipal and Justice Court Judge Registry",
        source_role="municipal_and_justice_judge_registry",
        page_url=OTHER_COURTS_PAGE_URL,
        list_name="Municipal & Justice Court Judge Registry",
        default_view_key="judge-registry",
        views=(
            ViewDefinition(
                "judge-registry",
                "{EC246A05-AC23-447B-9F69-8DC35CAC8E33}",
                "Judge Registry By Judge Name",
            ),
        ),
        record_kind="local_judge_assignment",
        description=(
            "Municipal and justice judge assignments, status, OSB number, "
            "term dates, court lookup, county, and certification date."
        ),
    ),
)
SOURCES_BY_ID = {source.source_id: source for source in SOURCE_DEFINITIONS}


@dataclass(frozen=True)
class SharePointView:
    """One view returned by SharePoint ``GetViewCollection``."""

    view_id: str
    display_name: str
    url: str | None
    view_type: str | None
    default_view: bool
    attributes: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "view_id": self.view_id,
            "display_name": self.display_name,
            "url": self.url,
            "view_type": self.view_type,
            "default_view": self.default_view,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class SharePointListSchema:
    """Stable fields observed from SharePoint ``GetList``."""

    list_id: str | None
    title: str | None
    item_count: int | None
    fields: tuple[Mapping[str, Any], ...]
    attributes: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class SharePointViewSchema:
    """Stable view details observed from SharePoint ``GetView``."""

    view_id: str
    display_name: str | None
    fields: tuple[str, ...]
    attributes: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class SharePointItemBatch:
    """One complete view response before local filtering and pagination."""

    source: SourceDefinition
    view: ViewDefinition
    rows: tuple[Mapping[str, str], ...]
    reported_count: int
    next_page_token: str | None
    schema_fingerprint: str

    @property
    def complete_response(self) -> bool:
        return self.next_page_token is None and self.reported_count == len(self.rows)


@dataclass(frozen=True)
class CursorState:
    """Opaque local continuation bound to query, snapshot, and boundary."""

    source_id: str
    query_fingerprint: str
    snapshot_fingerprint: str
    offset: int
    anchor: str


class OregonDirectorySelectionError(ValueError):
    """A requested source, view, filter, or cursor is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _source_from_args(args: argparse.Namespace) -> SourceDefinition:
    source_id = getattr(args, "source", None)
    if args.command == "discovery" and source_id is None:
        source_id = LOCAL_COURT_SOURCE_ID
    if args.command == "sources" and source_id is None:
        return SOURCES_BY_ID[STATE_COURT_SOURCE_ID]
    if source_id not in SOURCES_BY_ID:
        raise OregonDirectorySelectionError(
            "unknown_source",
            f"unknown Oregon court directory source: {source_id!r}",
            details={"available_source_ids": list(SOURCE_IDS)},
        )
    return SOURCES_BY_ID[str(source_id)]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _soap_envelope(
    operation: str,
    values: Sequence[tuple[str, Any]],
    *,
    raw_parameter_names: frozenset[str] = frozenset(),
) -> str:
    """Serialize the same default-namespace envelope emitted by OJD's page."""

    parameters: list[str] = []
    for name, value in values:
        text = "" if value is None else str(value)
        if name not in raw_parameter_names:
            text = html.escape(text, quote=False)
        parameters.append(f"<{name}>{text}</{name}>")
    return (
        '<soap:Envelope xmlns:soap="'
        f'{SOAP_NAMESPACE}" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        f'<soap:Body><{operation} xmlns="{SHAREPOINT_NAMESPACE}">'
        f"{''.join(parameters)}</{operation}></soap:Body></soap:Envelope>"
    )


def build_get_list_envelope(list_name: str) -> str:
    """Build the source-native ``GetList`` body."""

    return _soap_envelope("GetList", (("listName", list_name),))


def build_get_list_items_envelope(
    list_name: str,
    view_id: str,
    *,
    paging_token: str | None = None,
) -> str:
    """Build the browser-equivalent ``GetListItems`` body."""

    options = [
        "<QueryOptions>",
        "<IncludeAttachmentUrls>TRUE</IncludeAttachmentUrls>",
    ]
    if paging_token:
        options.append(
            "<Paging ListItemCollectionPositionNext="
            f'"{html.escape(paging_token, quote=True)}" />'
        )
    options.append("</QueryOptions>")
    query_options = "".join(options)
    return _soap_envelope(
        "GetListItems",
        (
            ("listName", list_name),
            ("viewName", view_id),
            ("queryOptions", query_options),
        ),
        raw_parameter_names=frozenset({"queryOptions"}),
    )


def build_get_view_collection_envelope(list_name: str) -> str:
    """Build a ``GetViewCollection`` body."""

    return _soap_envelope(
        "GetViewCollection",
        (("listName", list_name),),
    )


def build_get_view_envelope(list_name: str, view_id: str) -> str:
    """Build a ``GetView`` body."""

    return _soap_envelope(
        "GetView",
        (("listName", list_name), ("viewName", view_id)),
    )


def _parse_xml(xml_text: str, *, url: str) -> ET.Element:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise SourceSchemaError(
            "Oregon directory SOAP response is not valid XML",
            url=url,
            details={"parse_error": str(error)},
        ) from error
    fault = next(
        (element for element in root.iter() if _local_name(element.tag) == "Fault"),
        None,
    )
    if fault is not None:
        fault_code = next(
            (
                _text(element.text)
                for element in fault.iter()
                if _local_name(element.tag) == "faultcode"
            ),
            None,
        )
        fault_string = next(
            (
                _text(element.text)
                for element in fault.iter()
                if _local_name(element.tag) == "faultstring"
            ),
            None,
        )
        raise SourceResponseError(
            fault_string or "Oregon directory SharePoint returned a SOAP fault",
            url=url,
            details={"fault_code": fault_code},
        )
    return root


def parse_view_collection_xml(xml_text: str) -> tuple[SharePointView, ...]:
    """Parse and validate ``GetViewCollection`` XML."""

    root = _parse_xml(xml_text, url=VIEWS_URL)
    views: list[SharePointView] = []
    for element in root.iter():
        if _local_name(element.tag) != "View":
            continue
        view_id = _text(element.get("Name"))
        display_name = _text(element.get("DisplayName"))
        if view_id is None or display_name is None:
            raise SourceSchemaError(
                "Oregon directory view collection contains an unnamed view",
                url=VIEWS_URL,
            )
        attributes = {
            str(key): str(value) for key, value in sorted(element.attrib.items())
        }
        views.append(
            SharePointView(
                view_id=view_id,
                display_name=display_name,
                url=_text(element.get("Url")),
                view_type=_text(element.get("Type")),
                default_view=(
                    str(element.get("DefaultView") or "").casefold() == "true"
                ),
                attributes=attributes,
            )
        )
    if not views:
        raise SourceSchemaError(
            "Oregon directory view collection contains no views",
            url=VIEWS_URL,
        )
    return tuple(views)


def parse_list_schema_xml(xml_text: str) -> SharePointListSchema:
    """Parse stable list and field declarations from ``GetList``."""

    root = _parse_xml(xml_text, url=LISTS_URL)
    list_element = next(
        (element for element in root.iter() if _local_name(element.tag) == "List"),
        None,
    )
    if list_element is None:
        raise SourceSchemaError(
            "Oregon directory GetList response lacks a List element",
            url=LISTS_URL,
        )
    fields: list[dict[str, Any]] = []
    for element in list_element.iter():
        if _local_name(element.tag) != "Field":
            continue
        field = {
            key: element.get(key)
            for key in (
                "Name",
                "StaticName",
                "DisplayName",
                "Type",
                "Required",
                "ReadOnly",
                "Hidden",
            )
            if element.get(key) is not None
        }
        fields.append(field)
    fields.sort(
        key=lambda value: str(value.get("StaticName") or value.get("Name") or "")
    )
    attributes = {
        str(key): str(value) for key, value in sorted(list_element.attrib.items())
    }
    stable_schema = {
        "list_attributes": {
            key: attributes.get(key)
            for key in ("ID", "Title", "BaseType", "ServerTemplate")
        },
        "fields": fields,
    }
    raw_count = list_element.get("ItemCount")
    return SharePointListSchema(
        list_id=_text(list_element.get("ID")),
        title=_text(list_element.get("Title")),
        item_count=int(raw_count) if raw_count and raw_count.isdigit() else None,
        fields=tuple(fields),
        attributes=attributes,
        schema_fingerprint=schema_fingerprint(stable_schema),
    )


def parse_view_schema_xml(xml_text: str) -> SharePointViewSchema:
    """Parse stable view details from ``GetView``."""

    root = _parse_xml(xml_text, url=VIEWS_URL)
    view = next(
        (element for element in root.iter() if _local_name(element.tag) == "View"),
        None,
    )
    if view is None:
        raise SourceSchemaError(
            "Oregon directory GetView response lacks a View element",
            url=VIEWS_URL,
        )
    view_id = _text(view.get("Name"))
    if view_id is None:
        raise SourceSchemaError(
            "Oregon directory GetView response lacks a view ID",
            url=VIEWS_URL,
        )
    fields = tuple(
        field_name
        for element in view.iter()
        if _local_name(element.tag) == "FieldRef"
        and (field_name := _text(element.get("Name"))) is not None
    )
    attributes = {str(key): str(value) for key, value in sorted(view.attrib.items())}
    stable_schema = {
        "view_id": view_id,
        "display_name": view.get("DisplayName"),
        "fields": list(fields),
    }
    return SharePointViewSchema(
        view_id=view_id,
        display_name=_text(view.get("DisplayName")),
        fields=fields,
        attributes=attributes,
        schema_fingerprint=schema_fingerprint(stable_schema),
    )


def parse_list_items_xml(
    xml_text: str,
    *,
    source: SourceDefinition,
    view: ViewDefinition,
) -> SharePointItemBatch:
    """Parse one SharePoint rowset while preserving every source field."""

    root = _parse_xml(xml_text, url=LISTS_URL)
    data = next(
        (element for element in root.iter() if _local_name(element.tag) == "data"),
        None,
    )
    if data is None:
        raise SourceSchemaError(
            "Oregon directory GetListItems response lacks rowset data",
            url=LISTS_URL,
            details={
                "source_id": source.source_id,
                "view_id": view.view_id,
            },
        )
    raw_count = data.get("ItemCount")
    if raw_count is None or not raw_count.isdigit():
        raise SourceSchemaError(
            "Oregon directory rowset lacks a numeric ItemCount",
            url=LISTS_URL,
            details={"reported_item_count": raw_count},
        )
    rows: list[dict[str, str]] = []
    for element in data:
        if _local_name(element.tag) != "row":
            continue
        rows.append(
            {str(key): str(value) for key, value in sorted(element.attrib.items())}
        )
    stable_schema = {
        "source_id": source.source_id,
        "view_id": view.view_id,
        "row_fields": sorted({key for row in rows for key in row}),
    }
    return SharePointItemBatch(
        source=source,
        view=view,
        rows=tuple(rows),
        reported_count=int(raw_count),
        next_page_token=_text(data.get("ListItemCollectionPositionNext")),
        schema_fingerprint=schema_fingerprint(stable_schema),
    )


class OregonCourtDirectoryClient:
    """Cookie-preserving client for the official SharePoint SOAP lists."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.retry_policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff_initial=retry_backoff,
        )
        self.sleeper = sleeper
        self._bootstrapped_pages: set[str] = set()

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _status_error(
        self,
        status_code: int,
        *,
        url: str,
        response_text: str,
    ) -> PublicRecordsHTTPError:
        if status_code in {401, 403}:
            return RestrictedHTTPError(
                status_code,
                url=url,
                response_text=response_text,
            )
        if status_code == 429:
            return RateLimitedHTTPError(
                status_code,
                url=url,
                response_text=response_text,
            )
        if status_code in {404, 410}:
            return SourceChangedHTTPError(
                status_code,
                url=url,
                response_text=response_text,
            )
        return HTTPStatusError(
            status_code,
            url=url,
            response_text=response_text,
        )

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        last_error: PublicRecordsHTTPError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
            except requests.RequestException as error:
                last_error = TransportError(
                    f"Oregon directory transport failed: {error}",
                    url=url,
                )
            except (OSError, RuntimeError) as error:
                last_error = TransportError(
                    f"Oregon directory transport failed: {error}",
                    url=url,
                )
            else:
                status_code = int(response.status_code)
                if 200 <= status_code < 300:
                    return response
                last_error = self._status_error(
                    status_code,
                    url=url,
                    response_text=str(getattr(response, "text", "")),
                )
                if not last_error.retryable:
                    raise last_error
            if attempt < self.retry_policy.max_attempts:
                self.sleeper(self.retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error

    def bootstrap(self, source: SourceDefinition) -> None:
        """Establish the anonymous cookie session used by the page scripts."""

        if source.page_url in self._bootstrapped_pages:
            return
        response = self._request(
            "GET",
            source.page_url,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                ),
                "User-Agent": "Ithildin public-record directory client",
            },
        )
        page_text = _text(getattr(response, "text", ""))
        if page_text is None:
            raise SourceSchemaError(
                "Oregon directory bootstrap page is empty",
                url=source.page_url,
            )
        self._bootstrapped_pages.add(source.page_url)

    def _soap(
        self,
        source: SourceDefinition,
        *,
        url: str,
        body: str,
    ) -> str:
        self.bootstrap(source)
        response = self._request(
            "POST",
            url,
            data=body.encode("utf-8"),
            headers={
                "Accept": "text/xml, */*; q=0.01",
                "Content-Type": "text/xml; charset=utf-8",
                "Referer": source.page_url,
                "User-Agent": "Ithildin public-record directory client",
            },
        )
        return str(response.text)

    def list_schema(self, source: SourceDefinition) -> SharePointListSchema:
        xml_text = self._soap(
            source,
            url=LISTS_URL,
            body=build_get_list_envelope(source.list_name),
        )
        return parse_list_schema_xml(xml_text)

    def views(self, source: SourceDefinition) -> tuple[SharePointView, ...]:
        xml_text = self._soap(
            source,
            url=VIEWS_URL,
            body=build_get_view_collection_envelope(source.list_name),
        )
        return parse_view_collection_xml(xml_text)

    def view_schema(
        self,
        source: SourceDefinition,
        view: ViewDefinition,
    ) -> SharePointViewSchema:
        xml_text = self._soap(
            source,
            url=VIEWS_URL,
            body=build_get_view_envelope(source.list_name, view.view_id),
        )
        return parse_view_schema_xml(xml_text)

    def items(
        self,
        source: SourceDefinition,
        view: ViewDefinition,
    ) -> SharePointItemBatch:
        xml_text = self._soap(
            source,
            url=LISTS_URL,
            body=build_get_list_items_envelope(
                source.list_name,
                view.view_id,
            ),
        )
        return parse_list_items_xml(
            xml_text,
            source=source,
            view=view,
        )

    def probe(
        self,
        source: SourceDefinition,
        view: ViewDefinition,
    ) -> Mapping[str, Any]:
        list_schema = self.list_schema(source)
        views = self.views(source)
        live_view = next(
            (
                candidate
                for candidate in views
                if candidate.view_id.casefold() == view.view_id.casefold()
            ),
            None,
        )
        if live_view is None:
            raise SourceSchemaError(
                "Configured Oregon directory view is absent from SharePoint",
                url=VIEWS_URL,
                details={
                    "source_id": source.source_id,
                    "configured_view_id": view.view_id,
                    "live_view_ids": [candidate.view_id for candidate in views],
                },
            )
        view_schema = self.view_schema(source, view)
        batch = self.items(source, view)
        return {
            "list_schema": list_schema,
            "views": views,
            "live_view": live_view,
            "view_schema": view_schema,
            "batch": batch,
        }


_INTERNAL_NAME_PATTERN = re.compile(r"_x([0-9A-Fa-f]{4})_")
_URL_PATTERN = re.compile(r"https?://[^\s,<>'\"]+", re.IGNORECASE)


def decode_internal_field_name(value: str) -> str:
    """Decode SharePoint's ``_xNNNN_`` internal-name escapes."""

    return _INTERNAL_NAME_PATTERN.sub(
        lambda match: chr(int(match.group(1), 16)),
        value,
    )


def _raw_field(row: Mapping[str, str], name: str) -> str | None:
    return _text(row.get(f"ows_{name}"))


def _strip_lookup_prefix(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.startswith("string;#"):
        return _text(normalized[len("string;#") :])
    if ";#" in normalized:
        prefix, remainder = normalized.split(";#", 1)
        if prefix.isdigit():
            return _text(remainder)
    return normalized


def _choices(value: str | None) -> list[str]:
    normalized = _text(value)
    if normalized is None:
        return []
    if ";#" not in normalized:
        return [normalized]
    return [
        item
        for piece in normalized.split(";#")
        if (item := _text(piece)) is not None and not item.isdigit()
    ]


def _lookup(value: str | None) -> tuple[str | None, str | None]:
    normalized = _text(value)
    if normalized is None:
        return None, None
    if ";#" not in normalized:
        return None, normalized
    native_id, label = normalized.split(";#", 1)
    return _text(native_id), _text(label)


def _html_text(value: str | None) -> str | None:
    normalized = _strip_lookup_prefix(value)
    if normalized is None:
        return None
    decoded = html.unescape(normalized)
    if "<" not in decoded:
        return _text(decoded)
    return _text(BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True))


def _source_date(value: str | None) -> str | None:
    normalized = _strip_lookup_prefix(value)
    if normalized is None:
        return None
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[ T].*)?", normalized)
    return match.group(1) if match else normalized


def _sharepoint_unique_id(value: str | None) -> str | None:
    normalized = _strip_lookup_prefix(value)
    if normalized is None:
        return None
    return normalized.strip("{}").upper() or None


def _district(value: str | None) -> str | None:
    normalized = _strip_lookup_prefix(value)
    if normalized is None:
        return None
    try:
        return str(int(float(normalized)))
    except ValueError:
        return normalized


def _website_urls(value: str | None) -> list[str]:
    normalized = _text(value)
    if normalized is None:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for match in _URL_PATTERN.findall(normalized):
        candidate = match.rstrip(".,;)")
        parsed = urlparse(candidate)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
            continue
        key = candidate.casefold().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        urls.append(candidate)
    return urls


def _source_provenance(
    batch: SharePointItemBatch,
    row: Mapping[str, str],
) -> dict[str, Any]:
    decoded = {
        decode_internal_field_name(key.removeprefix("ows_")): value
        for key, value in row.items()
    }
    return {
        "source_id": batch.source.source_id,
        "source_url": batch.source.page_url,
        "source_list": {
            "name": batch.source.list_name,
        },
        "source_view": batch.view.to_dict(),
        "sharepoint_item_id": _strip_lookup_prefix(_raw_field(row, "ID")),
        "sharepoint_unique_id": _sharepoint_unique_id(_raw_field(row, "UniqueId")),
        "created_at_source": _strip_lookup_prefix(_raw_field(row, "Created")),
        "modified_at_source": _strip_lookup_prefix(_raw_field(row, "Modified")),
        "schema_fingerprint": batch.schema_fingerprint,
        "raw_sharepoint_fields": dict(row),
        "decoded_sharepoint_fields": decoded,
    }


def _person_name(
    first: str | None,
    middle: str | None,
    last: str | None,
) -> str | None:
    return _text(" ".join(value for value in (first, middle, last) if value))


def _canonical_ref(
    source: SourceDefinition,
    row: Mapping[str, str],
    *,
    semantic_fallback: Mapping[str, Any],
) -> str:
    unique_id = _sharepoint_unique_id(_raw_field(row, "UniqueId"))
    item_id = _strip_lookup_prefix(_raw_field(row, "ID"))
    native_id = unique_id or item_id or sha256_fingerprint(semantic_fallback)
    return f"ORCOURTDIR:{source.source_id}:{native_id}"


def _normalize_state_court(
    batch: SharePointItemBatch,
    row: Mapping[str, str],
) -> dict[str, Any]:
    county = _strip_lookup_prefix(_raw_field(row, "County"))
    first = _strip_lookup_prefix(_raw_field(row, "FirstName"))
    middle = _strip_lookup_prefix(_raw_field(row, "Middle_x0020_Initial"))
    last = _strip_lookup_prefix(_raw_field(row, "Title"))
    court_name = _strip_lookup_prefix(_raw_field(row, "Company_x0020_Name"))
    district = _district(
        _raw_field(row, "Judicial_x0020_District") or _raw_field(row, "District")
    )
    semantic_identity = {
        "court_name": court_name,
        "county": county,
        "judicial_district": district,
    }
    return {
        "canonical_ref": _canonical_ref(
            batch.source,
            row,
            semantic_fallback=semantic_identity,
        ),
        "record_kind": batch.source.record_kind,
        "semantic_identity": semantic_identity,
        "court_name": court_name,
        "court_level": (
            "circuit" if court_name and "circuit" in court_name.casefold() else "state"
        ),
        "county": county,
        "county_fips": COUNTY_FIPS.get((county or "").casefold()),
        "judicial_district": district,
        "physical_address": {
            "name": _strip_lookup_prefix(_raw_field(row, "AddressTitle")),
            "line1": _strip_lookup_prefix(_raw_field(row, "Address1")),
            "line2": None,
            "city": _strip_lookup_prefix(_raw_field(row, "City")),
            "state": _strip_lookup_prefix(_raw_field(row, "State")),
            "zip": _strip_lookup_prefix(_raw_field(row, "Zip")),
            "formatted": _html_text(_raw_field(row, "Location")),
        },
        "mailing_address": {
            "line1": _strip_lookup_prefix(_raw_field(row, "Address2")),
            "city": _strip_lookup_prefix(_raw_field(row, "MailingCity")),
            "zip": _strip_lookup_prefix(_raw_field(row, "MailingZip")),
            "formatted": _html_text(_raw_field(row, "MailingAddress")),
        },
        "administrator": {
            "full_name": _person_name(first, middle, last),
            "first_name": first,
            "middle_name": middle,
            "last_name": last,
            "title": _strip_lookup_prefix(_raw_field(row, "Job_x0020_Title")),
            "phone": _strip_lookup_prefix(_raw_field(row, "Office_x0020_Phone")),
        },
        "information_phone": _strip_lookup_prefix(_raw_field(row, "Info_x0020_Phone")),
        "fax": _strip_lookup_prefix(_raw_field(row, "Office_x0020_Fax")),
        "phone_summary": _html_text(_raw_field(row, "PhoneNumbers")),
        "alternate_locations": [
            value
            for name in (
                "Alternate_x0020_Locations",
                "Alternate_x0020_Location_x0020_1",
                "Alternate_x0020_Location_x0020_2",
                "Alternate_x0020_Location_x0020_3",
                "Alternate_x0020_Location_x0020_4",
            )
            if (value := _html_text(_raw_field(row, name))) is not None
            and value.casefold() != "none"
        ],
        **_source_provenance(batch, row),
    }


def _normalize_state_judge(
    batch: SharePointItemBatch,
    row: Mapping[str, str],
) -> dict[str, Any]:
    first = _strip_lookup_prefix(_raw_field(row, "FirstName"))
    middle = _strip_lookup_prefix(_raw_field(row, "Middle_x0020_Initial"))
    last = _strip_lookup_prefix(_raw_field(row, "Title"))
    full_name = _person_name(first, middle, last)
    county = _strip_lookup_prefix(_raw_field(row, "County"))
    category = _strip_lookup_prefix(_raw_field(row, "Category"))
    title = _strip_lookup_prefix(_raw_field(row, "Job_x0020_Title"))
    district = _district(
        _raw_field(row, "Judicial_x0020_District") or _raw_field(row, "District")
    )
    semantic_identity = {
        "full_name": full_name,
        "category": category,
        "judicial_district": district,
    }
    return {
        "canonical_ref": _canonical_ref(
            batch.source,
            row,
            semantic_fallback=semantic_identity,
        ),
        "record_kind": batch.source.record_kind,
        "semantic_identity": semantic_identity,
        "full_name": full_name,
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "vacant": (last or "").casefold() == "vacant",
        "court_category": category,
        "title": title,
        "presiding": bool(title and "presiding" in title.casefold()),
        "county": county,
        "county_fips": COUNTY_FIPS.get((county or "").casefold()),
        "judicial_district": district,
        "position": _strip_lookup_prefix(_raw_field(row, "Position")),
        "term_expires": _source_date(_raw_field(row, "Term_x0020_Expires")),
        "email": _strip_lookup_prefix(_raw_field(row, "Email")),
        "phone": _strip_lookup_prefix(_raw_field(row, "Office_x0020_Phone")),
        "court_address": {
            "name": _strip_lookup_prefix(_raw_field(row, "AddressTitle")),
            "line1": _strip_lookup_prefix(_raw_field(row, "Address1")),
            "line2": _strip_lookup_prefix(_raw_field(row, "Address2")),
            "city": _strip_lookup_prefix(_raw_field(row, "City")),
            "state": _strip_lookup_prefix(_raw_field(row, "State")),
            "zip": _strip_lookup_prefix(_raw_field(row, "Zip")),
            "formatted": _html_text(
                _raw_field(row, "Court_x0020_Mailing_x0020_Addres")
            ),
        },
        **_source_provenance(batch, row),
    }


def _normalize_local_court(
    batch: SharePointItemBatch,
    row: Mapping[str, str],
) -> dict[str, Any]:
    court_name = _strip_lookup_prefix(
        _raw_field(row, "LinkTitleNoMenu")
    ) or _strip_lookup_prefix(_raw_field(row, "Title"))
    court_types = _choices(_raw_field(row, "Court_x0020_Type"))
    counties = _choices(_raw_field(row, "County"))
    city = _strip_lookup_prefix(_raw_field(row, "City"))
    websites = _website_urls(_raw_field(row, "Website"))
    semantic_identity = {
        "court_name": court_name,
        "court_types": court_types,
        "city": city,
        "counties": counties,
    }
    record_kind = (
        "justice_court_boundary_entry"
        if batch.view.key == "justice-court-boundaries"
        else batch.source.record_kind
    )
    return {
        "canonical_ref": _canonical_ref(
            batch.source,
            row,
            semantic_fallback=semantic_identity,
        ),
        "record_kind": record_kind,
        "semantic_identity": semantic_identity,
        "court_name": court_name,
        "court_types": court_types,
        "counties": counties,
        "county_fips": [
            fips
            for county in counties
            if (fips := COUNTY_FIPS.get(county.casefold())) is not None
        ],
        "phone": _strip_lookup_prefix(_raw_field(row, "Phone_x0020_Number")),
        "physical_address": {
            "line1": _strip_lookup_prefix(_raw_field(row, "Street_x0020_Address")),
            "city": city,
            "state": STATE_CODE,
            "zip": _strip_lookup_prefix(_raw_field(row, "Zip_x0020_Code")),
        },
        "mailing_address": _strip_lookup_prefix(
            _raw_field(row, "Mailing_x0020_Address")
        ),
        "website_urls": websites,
        "website_source_value": _raw_field(row, "Website"),
        "contact": {
            "name": _strip_lookup_prefix(_raw_field(row, "Court_x0020_Contact")),
            "title": _strip_lookup_prefix(_raw_field(row, "Contact_x0020_Title")),
            "email": _strip_lookup_prefix(_raw_field(row, "Contact_x0020_Email")),
        },
        "certified_date": _source_date(_raw_field(row, "Certified_x0020_Date")),
        **_source_provenance(batch, row),
    }


def _normalize_local_judge(
    batch: SharePointItemBatch,
    row: Mapping[str, str],
) -> dict[str, Any]:
    first = _strip_lookup_prefix(_raw_field(row, "Judge_x0020_First_x0020_Name"))
    last = _strip_lookup_prefix(
        _raw_field(row, "LinkTitleNoMenu")
    ) or _strip_lookup_prefix(_raw_field(row, "Title"))
    full_name = _person_name(first, None, last)
    court_id, court_name = _lookup(_raw_field(row, "Name_x0020_of_x0020_Court"))
    _, court_phone = _lookup(_raw_field(row, "Name_x0020_of_x0020_Court_x003a_0"))
    _, court_city = _lookup(_raw_field(row, "Name_x0020_of_x0020_Court_x003a_"))
    counties = _choices(_raw_field(row, "Court_x0020_County"))
    statuses = _choices(_raw_field(row, "Status_x0020_of_x0020_Judge"))
    semantic_identity = {
        "full_name": full_name,
        "court_native_id": court_id,
        "court_name": court_name,
        "term_began": _source_date(_raw_field(row, "Term_x0020_Began")),
    }
    return {
        "canonical_ref": _canonical_ref(
            batch.source,
            row,
            semantic_fallback=semantic_identity,
        ),
        "record_kind": batch.source.record_kind,
        "semantic_identity": semantic_identity,
        "full_name": full_name,
        "first_name": first,
        "last_name": last,
        "court": {
            "native_id": court_id,
            "name": court_name,
            "phone": court_phone,
            "city": court_city,
            "counties": counties,
            "county_fips": [
                fips
                for county in counties
                if (fips := COUNTY_FIPS.get(county.casefold())) is not None
            ],
        },
        "appointment_statuses": statuses,
        "oregon_state_bar_number": _strip_lookup_prefix(
            _raw_field(row, "Judge_x0020_OSB_x0020__x0023_")
        ),
        "term_length": _strip_lookup_prefix(
            _raw_field(row, "Length_x0020_of_x0020_Term")
        ),
        "term_began": _source_date(_raw_field(row, "Term_x0020_Began")),
        "term_ends": _source_date(_raw_field(row, "Term_x0020_Ends")),
        "certified_date": _source_date(_raw_field(row, "Certified_x0020_Date")),
        **_source_provenance(batch, row),
    }


def normalize_batch(batch: SharePointItemBatch) -> list[dict[str, Any]]:
    """Normalize all rows from one configured component and view."""

    normalizer = {
        STATE_COURT_SOURCE_ID: _normalize_state_court,
        STATE_JUDGE_SOURCE_ID: _normalize_state_judge,
        LOCAL_COURT_SOURCE_ID: _normalize_local_court,
        LOCAL_JUDGE_SOURCE_ID: _normalize_local_judge,
    }[batch.source.source_id]
    records = [normalizer(batch, row) for row in batch.rows]
    records.sort(
        key=lambda record: (
            canonical_json(record.get("semantic_identity") or {}).casefold(),
            str(record["canonical_ref"]),
        )
    )
    return records


def _source_record(source: SourceDefinition) -> dict[str, Any]:
    return {
        "canonical_ref": f"ORCOURTDIR-SOURCE:{source.source_id}",
        "source_id": source.source_id,
        "record_kind": "source_metadata",
        "name": source.name,
        "description": source.description,
        "authority": AUTHORITY,
        "page_url": source.page_url,
        "platform_family": PLATFORM_FAMILY,
        "authentication": "anonymous_cookie_session",
        "list_name": source.list_name,
        "default_view": source.default_view.to_dict(),
        "configured_views": [view.to_dict() for view in source.views],
        "capabilities": [
            "view_discovery",
            "list",
            "local_filter_search",
            "snapshot_bound_local_pagination",
            "probe",
            *(
                ["local_website_source_discovery"]
                if source.source_id == LOCAL_COURT_SOURCE_ID
                else []
            ),
        ],
    }


def _configured_view_key(
    source: SourceDefinition,
    live_view: SharePointView,
) -> str | None:
    return next(
        (
            view.key
            for view in source.views
            if view.view_id.casefold() == live_view.view_id.casefold()
        ),
        None,
    )


def _view_record(
    source: SourceDefinition,
    live_view: SharePointView,
) -> dict[str, Any]:
    return {
        "canonical_ref": (f"ORCOURTDIR-VIEW:{source.source_id}:{live_view.view_id}"),
        "source_id": source.source_id,
        "record_kind": "source_view",
        "source_url": source.page_url,
        "list_name": source.list_name,
        "configured_key": _configured_view_key(source, live_view),
        "configured": _configured_view_key(source, live_view) is not None,
        **live_view.to_dict(),
    }


def _discovery_candidates(
    records: Sequence[Mapping[str, Any]],
    *,
    query: str | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    query_key = (query or "").casefold()
    for record in records:
        if record.get("record_kind") != "local_court_registry_entry":
            continue
        if query_key and query_key not in canonical_json(record).casefold():
            continue
        registry_identity = {
            "source_id": LOCAL_COURT_SOURCE_ID,
            "list_name": (record.get("source_list") or {}).get("name"),
            "sharepoint_unique_id": record.get("sharepoint_unique_id"),
            "sharepoint_item_id": record.get("sharepoint_item_id"),
            "court_canonical_ref": record.get("canonical_ref"),
        }
        registry_candidate_key = (
            f"ORCOURTDIR-DISCOVERY-COURT:{sha256_fingerprint(registry_identity)}"
        )
        for candidate_url in record.get("website_urls") or []:
            host = urlparse(str(candidate_url)).netloc.casefold()
            identity = {
                "court_ref": record.get("canonical_ref"),
                "candidate_url": str(candidate_url).casefold().rstrip("/"),
            }
            candidates.append(
                {
                    "canonical_ref": (
                        f"ORCOURTDIR-DISCOVERY:{sha256_fingerprint(identity)}"
                    ),
                    "source_id": LOCAL_COURT_SOURCE_ID,
                    "record_kind": "source_discovery_candidate",
                    "candidate_kind": "official_local_court_website",
                    "candidate_url": candidate_url,
                    "candidate_host": host,
                    "registry_candidate_key": registry_candidate_key,
                    "registry_identity": registry_identity,
                    "court": {
                        "canonical_ref": record.get("canonical_ref"),
                        "native_id": record.get("sharepoint_item_id"),
                        "name": record.get("court_name"),
                        "court_types": record.get("court_types"),
                        "counties": record.get("counties"),
                        "city": (record.get("physical_address") or {}).get("city"),
                    },
                    "discovered_from": {
                        "source_id": LOCAL_COURT_SOURCE_ID,
                        "source_url": record.get("source_url"),
                        "list_name": ((record.get("source_list") or {}).get("name")),
                        "view_id": ((record.get("source_view") or {}).get("view_id")),
                        "sharepoint_item_id": record.get("sharepoint_item_id"),
                        "sharepoint_unique_id": record.get("sharepoint_unique_id"),
                        "website_source_value": record.get("website_source_value"),
                        "created_at_source": record.get("created_at_source"),
                        "modified_at_source": record.get("modified_at_source"),
                        "schema_fingerprint": record.get("schema_fingerprint"),
                    },
                    "infra_request_created": False,
                }
            )
    candidates.sort(
        key=lambda value: (
            str((value.get("court") or {}).get("name") or "").casefold(),
            str(value.get("candidate_url") or "").casefold(),
        )
    )
    return candidates


def _resolve_configured_view(
    source: SourceDefinition,
    selector: str | None,
) -> ViewDefinition:
    if selector is None:
        return source.default_view
    key = selector.casefold()
    matches = [
        view
        for view in source.views
        if key
        in {
            view.key.casefold(),
            view.view_id.casefold(),
            view.display_name.casefold(),
        }
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise OregonDirectorySelectionError(
            "ambiguous_view",
            f"Oregon directory view selector is ambiguous: {selector!r}",
            details={"matching_view_ids": [view.view_id for view in matches]},
        )
    if re.fullmatch(
        r"\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}",
        selector,
    ):
        normalized_id = selector.upper()
        return ViewDefinition(
            key=f"live-view-{normalized_id.strip('{}').casefold()}",
            view_id=normalized_id,
            display_name=normalized_id,
        )
    raise OregonDirectorySelectionError(
        "unknown_view",
        f"unknown configured view for {source.source_id}: {selector!r}",
        details={
            "available_views": [view.to_dict() for view in source.views],
        },
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": state.source_id,
        "q": state.query_fingerprint,
        "snapshot": state.snapshot_fingerprint,
        "offset": state.offset,
        "anchor": state.anchor,
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise OregonDirectorySelectionError(
            "invalid_cursor",
            "Oregon directory cursor has an unknown prefix",
            category="pagination",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise OregonDirectorySelectionError(
            "invalid_cursor",
            "Oregon directory cursor is malformed",
            category="pagination",
        ) from error
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or payload.get("source_id") not in SOURCE_IDS
        or not isinstance(payload.get("q"), str)
        or not isinstance(payload.get("snapshot"), str)
        or not isinstance(payload.get("anchor"), str)
        or isinstance(payload.get("offset"), bool)
        or not isinstance(payload.get("offset"), int)
        or payload["offset"] <= 0
    ):
        raise OregonDirectorySelectionError(
            "invalid_cursor",
            "Oregon directory cursor fields are invalid",
            category="pagination",
        )
    return CursorState(
        source_id=str(payload["source_id"]),
        query_fingerprint=str(payload["q"]),
        snapshot_fingerprint=str(payload["snapshot"]),
        offset=int(payload["offset"]),
        anchor=str(payload["anchor"]),
    )


def _record_snapshot(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_fingerprint(
        [
            {
                "canonical_ref": record.get("canonical_ref"),
                "modified_at_source": record.get("modified_at_source"),
                "record_fingerprint": sha256_fingerprint(record),
            }
            for record in records
        ]
    )


def _paginate(
    records: Sequence[Mapping[str, Any]],
    *,
    source_id: str,
    query_identity: Mapping[str, Any],
    limit: int | None,
    cursor_value: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise OregonDirectorySelectionError(
            "invalid_limit",
            "Oregon directory result limit must be a positive integer",
        )
    query_fingerprint = sha256_fingerprint(query_identity)
    snapshot_fingerprint = _record_snapshot(records)
    cursor = _decode_cursor(cursor_value)
    offset = 0
    if cursor is not None:
        if cursor.source_id != source_id:
            raise OregonDirectorySelectionError(
                "cursor_source_mismatch",
                "Oregon directory cursor belongs to another source component",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
            )
        if cursor.query_fingerprint != query_fingerprint:
            raise OregonDirectorySelectionError(
                "cursor_query_mismatch",
                "Oregon directory cursor belongs to another query",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
            )
        if cursor.snapshot_fingerprint != snapshot_fingerprint:
            raise OregonDirectorySelectionError(
                "cursor_snapshot_changed",
                "Oregon directory records changed since the cursor was issued",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
                details={
                    "cursor_snapshot": cursor.snapshot_fingerprint,
                    "current_snapshot": snapshot_fingerprint,
                },
            )
        offset = cursor.offset
        if offset >= len(records):
            raise OregonDirectorySelectionError(
                "cursor_offset_out_of_range",
                "Oregon directory cursor is beyond the current result set",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
            )
        prior = records[offset - 1]
        if prior.get("canonical_ref") != cursor.anchor:
            raise OregonDirectorySelectionError(
                "cursor_anchor_changed",
                "Oregon directory cursor boundary no longer matches",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
            )
    end = len(records) if limit is None else min(len(records), offset + limit)
    selected = list(records[offset:end])
    next_cursor = None
    if end < len(records):
        anchor = str(records[end - 1].get("canonical_ref") or "")
        if not anchor:
            raise OregonDirectorySelectionError(
                "missing_cursor_anchor",
                "Oregon directory record lacks a continuation identity",
                category="pagination",
                status=ResultStatus.SOURCE_CHANGED,
            )
        next_cursor = _encode_cursor(
            CursorState(
                source_id=source_id,
                query_fingerprint=query_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                offset=end,
                anchor=anchor,
            )
        )
    return selected, next_cursor


SEARCH_FIELDS = (
    "all",
    "name",
    "court",
    "judge",
    "county",
    "city",
    "bar",
    "website",
)


def _search_haystack(
    record: Mapping[str, Any],
    field: str,
) -> str:
    if field == "all":
        return canonical_json(record)
    if field == "name":
        values = (
            record.get("full_name"),
            record.get("court_name"),
            (record.get("administrator") or {}).get("full_name"),
        )
    elif field == "court":
        values = (
            record.get("court_name"),
            (record.get("court") or {}).get("name"),
            record.get("court_category"),
        )
    elif field == "judge":
        values = (record.get("full_name"), record.get("title"))
    elif field == "county":
        values = (
            record.get("county"),
            *(record.get("counties") or []),
            *((record.get("court") or {}).get("counties") or []),
        )
    elif field == "city":
        values = (
            (record.get("physical_address") or {}).get("city"),
            (record.get("court_address") or {}).get("city"),
            (record.get("court") or {}).get("city"),
        )
    elif field == "bar":
        values = (record.get("oregon_state_bar_number"),)
    elif field == "website":
        values = tuple(record.get("website_urls") or [])
    else:
        raise OregonDirectorySelectionError(
            "invalid_search_field",
            f"unknown Oregon directory search field: {field!r}",
            details={"available_fields": list(SEARCH_FIELDS)},
        )
    return " ".join(str(value) for value in values if value is not None)


def _filter_records(
    records: Sequence[Mapping[str, Any]],
    *,
    query: str,
    fields: Sequence[str],
) -> list[Mapping[str, Any]]:
    needle = _text(query)
    if needle is None:
        raise OregonDirectorySelectionError(
            "empty_query",
            "Oregon directory search query must not be blank",
        )
    selected_fields = tuple(fields) or ("all",)
    needle_key = needle.casefold()
    return [
        record
        for record in records
        if any(
            needle_key in _search_haystack(record, field).casefold()
            for field in selected_fields
        )
    ]


def _view_records(
    source: SourceDefinition,
    views: Sequence[SharePointView],
) -> list[dict[str, Any]]:
    records = [_view_record(source, view) for view in views]
    records.sort(
        key=lambda value: (
            str(value.get("display_name") or "").casefold(),
            str(value.get("view_id") or ""),
        )
    )
    return records


def _probe_record(
    source: SourceDefinition,
    view: ViewDefinition,
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    list_schema: SharePointListSchema = probe["list_schema"]
    live_views: Sequence[SharePointView] = probe["views"]
    view_schema: SharePointViewSchema = probe["view_schema"]
    batch: SharePointItemBatch = probe["batch"]
    configured_ids = {candidate.view_id.casefold() for candidate in source.views}
    return {
        "canonical_ref": (f"ORCOURTDIR-PROBE:{source.source_id}:{view.view_id}"),
        "source_id": source.source_id,
        "record_kind": "probe",
        "source_url": source.page_url,
        "checks": {
            "anonymous_page_bootstrap": True,
            "cookie_bound_soap_request": True,
            "soap_action_header_required": False,
            "list_schema_available": True,
            "view_collection_available": True,
            "configured_view_present": True,
            "view_schema_available": True,
            "rowset_available": True,
            "reported_item_count": batch.reported_count,
            "parsed_item_count": len(batch.rows),
            "complete_response": batch.complete_response,
            "next_page_token_present": batch.next_page_token is not None,
            "live_view_count": len(live_views),
            "configured_view_count": len(source.views),
            "unconfigured_live_view_count": sum(
                candidate.view_id.casefold() not in configured_ids
                for candidate in live_views
            ),
        },
        "list": {
            "requested_name": source.list_name,
            "source_list_id": list_schema.list_id,
            "source_title": list_schema.title,
            "source_reported_item_count": list_schema.item_count,
            "declared_field_count": len(list_schema.fields),
            "schema_fingerprint": list_schema.schema_fingerprint,
        },
        "view": {
            **view.to_dict(),
            "live_display_name": view_schema.display_name,
            "declared_fields": list(view_schema.fields),
            "schema_fingerprint": view_schema.schema_fingerprint,
        },
        "rowset_schema_fingerprint": batch.schema_fingerprint,
        "live_views": [_view_record(source, candidate) for candidate in live_views],
    }


def _batch_result(
    query: PublicRecordsQuery,
    batch: SharePointItemBatch,
    records: Sequence[Mapping[str, Any]],
    *,
    limit: int | None,
    cursor: str | None,
    query_identity: Mapping[str, Any],
) -> PublicRecordsResult:
    selected, next_cursor = _paginate(
        records,
        source_id=batch.source.source_id,
        query_identity=query_identity,
        limit=limit,
        cursor_value=cursor,
    )
    if not batch.complete_response:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="sharepoint_rowset_incomplete",
                    message=(
                        "The SharePoint rowset reports an incomplete response; "
                        "returned rows are preserved."
                    ),
                    category="completeness",
                    retryable=True,
                    details={
                        "reported_count": batch.reported_count,
                        "parsed_count": len(batch.rows),
                        "next_page_token": batch.next_page_token,
                    },
                )
            ],
            records=selected,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _decision_metadata(
    decision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if decision is None:
        return {"mode": "direct_public_route", "allowed": True}
    return {
        key: decision[key]
        for key in (
            "source_id",
            "allowed",
            "access_class",
            "automation_disposition",
            "reason_code",
            "limits",
        )
        if key in decision
    }


def build_query(
    args: argparse.Namespace,
    *,
    source: SourceDefinition,
    view: ViewDefinition | None = None,
    decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {
        "platform_family": PLATFORM_FAMILY,
        "list_name": source.list_name,
    }
    if args.command == "sources":
        parameters["listed_source_ids"] = (
            [args.source] if getattr(args, "source", None) else list(SOURCE_IDS)
        )
    if view is not None:
        parameters["view"] = view.to_dict()
    if args.command in {"search", "discovery"}:
        parameters["query"] = getattr(args, "query", None)
        parameters["fields"] = list(getattr(args, "fields", None) or ["all"])
    requested_limit = getattr(args, "limit", None)
    if (
        isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or requested_limit <= 0
    ):
        requested_limit = None
    return PublicRecordsQuery(
        source=source.source_metadata,
        jurisdiction=source.jurisdiction,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
            metadata={"access_decision": _decision_metadata(decision)},
        ),
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    disposition = str(
        decision.get("automation_disposition") or decision.get("disposition") or ""
    ).casefold()
    status = {
        "human_required": ResultStatus.HUMAN_REQUIRED,
        "manual_only": ResultStatus.HUMAN_REQUIRED,
        "restricted": ResultStatus.RESTRICTED,
        "subscription": ResultStatus.RESTRICTED,
        "terms_blocked": ResultStatus.TERMS_BLOCKED,
        "prohibited": ResultStatus.TERMS_BLOCKED,
    }.get(disposition, ResultStatus.UNAVAILABLE)
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code") or "machine_acquisition_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "The supplied access decision does not allow this route."
                ),
                category="source_access",
                retryable=False,
                details={"access_decision": dict(decision)},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: OregonDirectorySelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    *,
    source: SourceDefinition,
    view: ViewDefinition | None,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        selected_sources = (
            [SOURCES_BY_ID[args.source]]
            if getattr(args, "source", None)
            else list(SOURCE_DEFINITIONS)
        )
        return PublicRecordsResult.success(
            query,
            [_source_record(candidate) for candidate in selected_sources],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "views":
        records = _view_records(source, client.views(source))
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )
    assert view is not None
    if args.command in {"list", "search", "discovery"}:
        batch = client.items(source, view)
        records: Sequence[Mapping[str, Any]] = normalize_batch(batch)
        query_term = getattr(args, "query", None)
        if args.command == "search":
            records = _filter_records(
                records,
                query=str(query_term or ""),
                fields=getattr(args, "fields", None) or ("all",),
            )
        elif args.command == "discovery":
            records = _discovery_candidates(
                records,
                query=_text(query_term),
            )
        return _batch_result(
            query,
            batch,
            records,
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            query_identity={
                "source_id": source.source_id,
                "operation": args.command,
                "view": view.to_dict(),
                "query": query_term,
                "fields": list(getattr(args, "fields", None) or ("all",)),
            },
        )
    if args.command == "probe":
        probe = client.probe(source, view)
        return PublicRecordsResult.success(
            query,
            [_probe_record(source, view, probe)],
            warnings=SOURCE_WARNINGS,
        )
    raise OregonDirectorySelectionError(
        "unsupported_command",
        f"unsupported Oregon directory command: {args.command}",
    )


def _log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
    source_id: str,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:
        print(
            f"Warning: could not log Oregon directory search: {error}", file=sys.stderr
        )


def _make_client(
    args: argparse.Namespace,
    decision: Mapping[str, Any] | None,
) -> OregonCourtDirectoryClient:
    limits = (
        decision.get("limits")
        if decision is not None and isinstance(decision.get("limits"), Mapping)
        else {}
    )
    reviewed_interval = float((limits or {}).get("minimum_interval_seconds") or 0)
    return OregonCourtDirectoryClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=max(
            float(
                getattr(
                    args,
                    "minimum_interval",
                    DEFAULT_MINIMUM_INTERVAL,
                )
            ),
            reviewed_interval,
        ),
        max_attempts=int(getattr(args, "max_attempts", DEFAULT_MAX_ATTEMPTS)),
        retry_backoff=float(getattr(args, "retry_backoff", 0.25)),
    )


def execute(
    args: argparse.Namespace,
    *,
    catalog_decision: Mapping[str, Any] | None = None,
    access_decision: Mapping[str, Any] | None = None,
    client: OregonCourtDirectoryClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one directory operation with injectable access and transport."""

    if catalog_decision is not None and access_decision is not None:
        raise ValueError("pass catalog_decision or access_decision, not both")
    decision = catalog_decision if catalog_decision is not None else access_decision
    try:
        source = _source_from_args(args)
        view = (
            None
            if args.command in {"sources", "views"}
            else _resolve_configured_view(
                source,
                getattr(args, "view", None),
            )
        )
        query = build_query(
            args,
            source=source,
            view=view,
            decision=decision,
        )
    except OregonDirectorySelectionError as error:
        fallback_source = SOURCES_BY_ID[STATE_COURT_SOURCE_ID]
        query = build_query(
            args,
            source=fallback_source,
            decision=decision,
        )
        result = _selection_failure(query, error)
        if log_results:
            _log(query, result, fallback_source.source_id)
        return result

    decision_source_id = decision.get("source_id") if decision is not None else None
    if decision_source_id is not None and decision_source_id != source.source_id:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message=(
                        "Catalog decision belongs to another Oregon directory component"
                    ),
                    category="source_access",
                    retryable=False,
                    details={
                        "decision_source_id": decision_source_id,
                        "query_source_id": source.source_id,
                    },
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
        if log_results:
            _log(query, result, source.source_id)
        return result
    if decision is not None and not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        if log_results:
            _log(query, result, source.source_id)
        return result

    source_client = client or _make_client(args, decision)
    owns_client = client is None
    try:
        result = _execute_command(
            args,
            source=source,
            view=view,
            client=source_client,
            query=query,
        )
    except OregonDirectorySelectionError as error:
        result = _selection_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=SOURCE_WARNINGS,
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
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            source_client.close()
    if log_results:
        _log(query, result, source.source_id)
    return result


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    *,
    output_writer: Callable[..., bool] = write_output,
) -> None:
    payload = result.to_dict()
    if output_writer(
        payload,
        args,
        summary=(f"Oregon court directory {args.command} ({result.status.value})"),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Oregon court directory {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("court_name")
            or record.get("full_name")
            or record.get("display_name")
            or record.get("name")
            or record.get("candidate_url")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_source(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument(
        "--source",
        choices=SOURCE_IDS,
        required=required,
    )


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
    parser.add_argument("--retry-backoff", type=float, default=0.25)
    add_output_args(parser)


def _add_pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Local page size; omitted returns the complete source response",
    )
    parser.add_argument("--cursor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query Oregon's official state and local court directory family")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List the four distinct official directory components",
    )
    _add_source(sources, required=False)
    _add_runtime(sources)

    views = subparsers.add_parser(
        "views",
        help="Discover the live SharePoint views for one component",
    )
    _add_source(views)
    _add_runtime(views)

    list_parser = subparsers.add_parser(
        "list",
        help="List and normalize one configured component view",
    )
    _add_source(list_parser)
    list_parser.add_argument(
        "--view",
        help="Configured view key, display name, or SharePoint view ID",
    )
    _add_pagination(list_parser)
    _add_runtime(list_parser)

    search = subparsers.add_parser(
        "search",
        help="Filter one complete official view locally",
    )
    search.add_argument("query")
    _add_source(search)
    search.add_argument(
        "--view",
        help="Configured view key, display name, or SharePoint view ID",
    )
    search.add_argument(
        "--field",
        dest="fields",
        action="append",
        choices=SEARCH_FIELDS,
        help="Repeat to search selected semantic fields; defaults to all",
    )
    _add_pagination(search)
    _add_runtime(search)

    discovery = subparsers.add_parser(
        "discovery",
        help=(
            "Emit deduplicated official local-court website candidates "
            "without creating infrastructure requests"
        ),
    )
    discovery.add_argument("--query")
    _add_source(discovery, required=False)
    discovery.set_defaults(source=LOCAL_COURT_SOURCE_ID)
    discovery.add_argument(
        "--view",
        default="court-registry",
        help="Configured local-court registry view",
    )
    _add_pagination(discovery)
    _add_runtime(discovery)

    probe = subparsers.add_parser(
        "probe",
        help="Verify page bootstrap, list, view, and rowset contracts",
    )
    _add_source(probe)
    probe.add_argument(
        "--view",
        help="Configured view key, display name, or SharePoint view ID",
    )
    _add_runtime(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")
    if args.retry_backoff < 0:
        parser.error("--retry-backoff must not be negative")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
