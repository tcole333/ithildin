#!/usr/bin/env python3
"""Query Washington County, Oregon casefile and permit record components.

Washington County publishes related planning and building records through a
family of public applications.  This adapter keeps each representation
attributable while exposing the native joins among casefiles, taxlots,
activities, projects, permits, inspections, reviews, and Accela documents.

Examples:
    uv run python tools/query_oregon_washington_case_permits.py sources
    uv run python tools/query_oregon_washington_case_permits.py case-detail L2500106
    uv run python tools/query_oregon_washington_case_permits.py case-search \
        taxlot 2N2330002700 --limit 25
    uv run python tools/query_oregon_washington_case_permits.py case-review
    uv run python tools/query_oregon_washington_case_permits.py case-decisions
    uv run python tools/query_oregon_washington_case_permits.py taxlot-activity \
        2N2330002700 --collection projects
    uv run python tools/query_oregon_washington_case_permits.py building-search \
        taxlot 2N2330002700
    uv run python tools/query_oregon_washington_case_permits.py permit-report \
        project P0138681
    uv run python tools/query_oregon_washington_case_permits.py accela-record \
        L2500106
    uv run python tools/query_oregon_washington_case_permits.py accela-document \
        L2500106 628906
    uv run python tools/query_oregon_washington_case_permits.py document-routes \
        L2500106
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urlencode, urljoin

from bs4 import BeautifulSoup

try:
    from tools.date_normalize import normalize_date
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from tools.query_oregon_jackson_accela import (
        parse_document_detail as parse_accela_document_detail,
        parse_record_detail as parse_accela_record_detail,
    )
    from tools.query_oregon_washington_property import (
        DEFAULT_MAX_DOCUMENT_BYTES,
        ResponseArtifact,
        WashingtonClient,
    )
except ImportError:
    from date_normalize import normalize_date
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_http import (
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from query_oregon_jackson_accela import (
        parse_document_detail as parse_accela_document_detail,
        parse_record_detail as parse_accela_record_detail,
    )
    from query_oregon_washington_property import (
        DEFAULT_MAX_DOCUMENT_BYTES,
        ResponseArtifact,
        WashingtonClient,
    )


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41067"
COUNTY_NAME = "Washington County, Oregon"

CASEFILE_SOURCE_ID = "us-or-washington-county-casefiles"
TAXLOT_ACTIVITY_SOURCE_ID = "us-or-washington-county-taxlot-project-activity"
BUILDING_SOURCE_ID = "us-or-washington-county-building-permits"
PERMIT_REPORT_SOURCE_ID = "us-or-washington-county-permit-reports"
ACCELA_SOURCE_ID = "us-or-washington-county-accela-current-planning"
DOCUMENT_ROUTE_SOURCE_ID = "us-or-washington-county-land-use-document-routes"

API_BASE_URL = "https://api.washingtoncountyor.gov/v1"
WEBAPPS_ORIGIN = "https://webapps.washingtoncountyor.gov"
CASEFILE_APP_URL = f"{WEBAPPS_ORIGIN}/casefile-report/"
PROJECTS_REVIEW_APP_URL = f"{WEBAPPS_ORIGIN}/projects-review/"
DECISIONS_APP_URL = f"{WEBAPPS_ORIGIN}/notices-of-decision/"
TAXLOT_REPORT_APP_URL = f"{WEBAPPS_ORIGIN}/permits/"
PROJECT_REPORT_APP_URL = f"{WEBAPPS_ORIGIN}/project-report/"
BUILDING_APP_URL = f"{WEBAPPS_ORIGIN}/bps/"

CASEFILE_SEARCH_URL = f"{API_BASE_URL}/services/casefiles/search/"
CASEFILE_REVIEW_URL = f"{API_BASE_URL}/services/casefiles/review/"
CASEFILE_DECISION_URL = f"{API_BASE_URL}/services/casefiles/decision/"
STAFF_URL = f"{API_BASE_URL}/services/staff/all"
TAXLOT_ACTIVITY_URL = f"{API_BASE_URL}/services/taxlots/search/"
BUILDING_SEARCH_URL = f"{API_BASE_URL}/services/building_permit/search/"
BUILDING_TYPES_URL = f"{API_BASE_URL}/services/building_permit/types"
PERMIT_REPORT_URL = f"{API_BASE_URL}/services/permits/search/"

ACCELA_ROOT_URL = "https://permits.washingtoncountyor.gov/CitizenAccess/"
ACCELA_DETAIL_URL = f"{ACCELA_ROOT_URL}Cap/CapDetail.aspx"
ACCELA_DOCUMENT_DETAIL_URL = f"{ACCELA_ROOT_URL}FileUpload/DocumentDetail.aspx"
ACCELA_AGENCY_CODE = "WASHCOOR"
ACCELA_MODULE = "CurrentPlanning"

DEVELOPMENT_PROGRESS_URL = (
    "https://www.washingtoncountyor.gov/current-planning/"
    "development-applications-progress"
)
FREQUENTLY_DISCUSSED_URL = (
    "https://www.washingtoncountyor.gov/current-planning/"
    "frequently-discussed-development-applications"
)
PUBLIC_HEARINGS_URL = (
    "https://www.washingtoncountyor.gov/lut/public-hearings-agendas"
)
CIVICWEB_LAND_USE_URL = (
    "https://washingtoncounty.civicweb.net/Portal/MeetingInformation.aspx?Id=13501"
)
PERMIT_RECORDS_URL = (
    "https://www.washingtoncountyor.gov/lut/building-services/"
    "permit-records-reports"
)
LEGACY_LASERFICHE_URL = (
    "http://pwebnut1.co.washington.or.us/lf/lflink.html"
)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_MAX_JSON_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_HTML_BYTES = 16 * 1024 * 1024
CURSOR_PREFIX = "oregon-washington-case-permits:v1:"
CURSOR_VERSION = 1
USER_AGENT = "IthildinOSINT/1.0 Washington County case and permit client"

PROBE_CASEFILE = "L2500106"
PROBE_TAXLOT = "2N2330002700"
PROBE_PROJECT = "P0138681"
PROBE_ACTIVITY = "HR25-0008"
PROBE_PERMIT = "05214429"

API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": WEBAPPS_ORIGIN,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

ACCELA_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    ),
    "User-Agent": USER_AGENT,
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Washington County",
    metadata={"state_fips": STATE_FIPS},
)


def _source(
    source_id: str,
    name: str,
    role: str,
    base_url: str,
    dataset_id: str,
    *,
    metadata: Mapping[str, Any],
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name=name,
        source_role=role,
        base_url=base_url,
        dataset_id=dataset_id,
        metadata={
            "publisher": "Washington County, Oregon",
            "county_geoid": COUNTY_GEOID,
            **dict(metadata),
        },
    )


SOURCES: dict[str, SourceMetadata] = {
    CASEFILE_SOURCE_ID: _source(
        CASEFILE_SOURCE_ID,
        "Washington County Development Casefiles",
        "official_county_planning_casefile_index",
        CASEFILE_APP_URL,
        "washington-county-casefiles",
        metadata={
            "api_routes": {
                "search": CASEFILE_SEARCH_URL,
                "applications_under_review": CASEFILE_REVIEW_URL,
                "recent_decisions": CASEFILE_DECISION_URL,
                "staff_vocabulary": STAFF_URL,
            },
            "native_identifiers": [
                "NUMBER_KEY",
                "SubmittalNo",
                "B1_ALT_ID",
                "PARCEL_NO",
                "ID1",
                "ID2",
                "ID3",
            ],
            "operations": {
                "case_search": "anonymous",
                "case_detail": "anonymous",
                "applications_under_review": "anonymous",
                "recent_decisions": "anonymous",
                "staff_vocabulary": "anonymous",
            },
        },
    ),
    TAXLOT_ACTIVITY_SOURCE_ID: _source(
        TAXLOT_ACTIVITY_SOURCE_ID,
        "Washington County Taxlot Project and Activity Report",
        "official_county_taxlot_project_activity_index",
        TAXLOT_REPORT_APP_URL,
        "washington-county-taxlot-project-activity",
        metadata={
            "api_route": TAXLOT_ACTIVITY_URL,
            "native_identifiers": [
                "Parcel_No",
                "ParcelNo",
                "Project_No",
                "PDevelop_No",
                "APermit_No",
            ],
            "operations": {"taxlot_project_activity": "anonymous"},
        },
    ),
    BUILDING_SOURCE_ID: _source(
        BUILDING_SOURCE_ID,
        "Washington County Building Permit Search",
        "official_county_building_permit_index",
        BUILDING_APP_URL,
        "washington-county-building-permit-search",
        metadata={
            "api_routes": {
                "search": BUILDING_SEARCH_URL,
                "permit_types": BUILDING_TYPES_URL,
            },
            "native_identifiers": ["PermitNO", "Project", "ParcelNo"],
            "operation_access": {
                "taxlot_search": "anonymous",
                "permit_types": "anonymous",
                "permit_number_search": "source_challenge_observed",
                "type_date_address_search": "source_challenge_observed",
                "individual_detail": "source_challenge_observed",
            },
            "interactive_route_retained": True,
        },
    ),
    PERMIT_REPORT_SOURCE_ID: _source(
        PERMIT_REPORT_SOURCE_ID,
        "Washington County Permit and Project Reports",
        "official_county_project_activity_people_inspection_review_reports",
        PROJECT_REPORT_APP_URL,
        "washington-county-permit-project-reports",
        metadata={
            "api_route": PERMIT_REPORT_URL,
            "report_types": [
                "project",
                "activity",
                "people",
                "inspection",
                "review",
            ],
            "native_identifiers": [
                "NUMBER_KEY",
                "Activity_No",
                "PermitNo",
                "Number_Key",
                "PROJECT",
            ],
            "operations": {"all_report_types": "anonymous"},
        },
    ),
    ACCELA_SOURCE_ID: _source(
        ACCELA_SOURCE_ID,
        "Washington County Accela Current Planning",
        "official_county_current_planning_record_and_document_detail",
        ACCELA_ROOT_URL,
        "washington-county-accela-current-planning",
        metadata={
            "platform": "Accela Citizen Access",
            "agency_code": ACCELA_AGENCY_CODE,
            "module": ACCELA_MODULE,
            "native_identifiers": [
                "casefile_number",
                "capID1",
                "capID2",
                "capID3",
                "document_number",
            ],
            "operations": {
                "exact_record_detail": "anonymous",
                "session_bound_attachment_list": "anonymous",
                "document_metadata": "anonymous",
                "listed_document_binary": "anonymous_postback",
            },
        },
    ),
    DOCUMENT_ROUTE_SOURCE_ID: _source(
        DOCUMENT_ROUTE_SOURCE_ID,
        "Washington County Land Use Document Publication Routes",
        "official_county_complementary_casefile_document_routes",
        DEVELOPMENT_PROGRESS_URL,
        "washington-county-land-use-document-routes",
        metadata={
            "route_types": [
                "development_in_progress",
                "frequently_discussed_application",
                "recent_notice_of_decision",
                "public_hearing_exhibits",
                "civicweb_land_use_hearings",
                "legacy_laserfiche_casefile",
                "public_records_request",
            ],
            "lookup_key": "casefile_number",
        },
    ),
}


@dataclass(frozen=True)
class SearchKind:
    key: str
    searchby: str
    query_parameter: str | None
    referer: str


CASE_SEARCH_KINDS: dict[str, SearchKind] = {
    "casefile": SearchKind(
        "casefile", "search-account", "account", CASEFILE_APP_URL
    ),
    "submittal": SearchKind(
        "submittal", "search-submittal", "submittal", CASEFILE_APP_URL
    ),
    "taxlot": SearchKind("taxlot", "search-taxlot", "tlno", CASEFILE_APP_URL),
    "activity": SearchKind(
        "activity", "search-activity", "comp_type", CASEFILE_APP_URL
    ),
    "other": SearchKind("other", "search-other", None, CASEFILE_APP_URL),
}

BUILDING_SEARCH_KINDS: dict[str, SearchKind] = {
    "permit": SearchKind(
        "permit", "search-number", "permitno", BUILDING_APP_URL
    ),
    "taxlot": SearchKind(
        "taxlot", "search-taxlot", "tlno", BUILDING_APP_URL
    ),
    "type": SearchKind("type", "search-type", "type", BUILDING_APP_URL),
    "date": SearchKind("date", "search-date", "year", BUILDING_APP_URL),
    "address": SearchKind(
        "address", "search-address", "streetname", BUILDING_APP_URL
    ),
}

CASE_FILTER_FIELDS = frozenset(
    {
        "submittal",
        "account",
        "tlno",
        "comp_type",
        "projyear",
        "projstatus",
        "sub_type",
        "projclass",
        "zoning",
        "projcpo",
        "insp_area",
    }
)
BUILDING_FILTER_FIELDS = frozenset(
    {
        "permitno",
        "tlno",
        "status",
        "type",
        "month",
        "day",
        "year",
        "streetnum",
        "streetname",
        "cf-turnstile-response",
    }
)
REPORT_KINDS = frozenset(
    {"project", "activity", "people", "inspection", "review"}
)


class ChallengeRequiredError(PublicRecordsHTTPError):
    """The public application requested its interactive challenge for this operation."""

    result_status = ResultStatus.HUMAN_REQUIRED
    category = "source_access"
    retryable = False
    code = "source_challenge_required"


class SelectionError(SourceSchemaError):
    """A filter, cursor, or source selection is inconsistent with the contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        url: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, url=url, details=details)
        self.code = code


class CasePermitClient(WashingtonClient):
    """Washington County case/permit client using the shared bounded transport."""

    def api_json(
        self,
        url: str,
        *,
        parameters: Mapping[str, Any],
        referer: str,
    ) -> tuple[Mapping[str, Any], ResponseArtifact]:
        payload, artifact = self.json(
            url,
            params=dict(parameters),
            headers={**API_HEADERS, "Referer": referer},
            maximum_bytes=DEFAULT_MAX_JSON_BYTES,
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Washington County API response is not an object",
                url=artifact.source_url,
            )
        _raise_api_error(payload, artifact.source_url)
        return payload, artifact

    def accela_detail(
        self,
        cap_parts: Sequence[str],
    ) -> tuple[str, ResponseArtifact]:
        parameters = {
            "Module": ACCELA_MODULE,
            "TabName": ACCELA_MODULE,
            "capID1": cap_parts[0],
            "capID2": cap_parts[1],
            "capID3": cap_parts[2],
            "agencyCode": ACCELA_AGENCY_CODE,
        }
        text, artifact = self.text(
            ACCELA_DETAIL_URL,
            params=parameters,
            headers=ACCELA_HEADERS,
            maximum_bytes=DEFAULT_MAX_HTML_BYTES,
        )
        if "ctl00_PlaceHolderMain_lblPermitNumber" not in text:
            raise SourceSchemaError(
                "Accela detail is missing its record-number field",
                url=artifact.source_url,
            )
        return text, artifact

    def accela_attachment_list(
        self,
        attachment_url: str,
        *,
        referer: str,
    ) -> tuple[str, ResponseArtifact]:
        text, artifact = self.text(
            attachment_url,
            headers={**ACCELA_HEADERS, "Referer": referer},
            maximum_bytes=DEFAULT_MAX_HTML_BYTES,
        )
        if (
            "attachmentList_gdvAttachmentList" not in text
            and "No records found." not in text
        ):
            raise SourceSchemaError(
                "Accela attachment representation is missing its list marker",
                url=artifact.source_url,
            )
        return text, artifact

    def accela_document_detail(
        self,
        document_number: str,
        *,
        referer: str,
    ) -> tuple[str, ResponseArtifact]:
        parameters = {
            "Module": ACCELA_MODULE,
            "isPeopleDocument": "False",
            "agencyCode": ACCELA_AGENCY_CODE,
            "documentNo": document_number,
            "specificEntity": "",
        }
        text, artifact = self.text(
            ACCELA_DOCUMENT_DETAIL_URL,
            params=parameters,
            headers={**ACCELA_HEADERS, "Referer": referer},
            maximum_bytes=DEFAULT_MAX_HTML_BYTES,
        )
        if "docdetailpage" not in text:
            raise SourceSchemaError(
                "Accela document detail is missing its public field container",
                url=artifact.source_url,
            )
        return text, artifact

    def accela_download(
        self,
        listing: ResponseArtifact,
        event_target: str,
        *,
        maximum_bytes: int,
    ) -> ResponseArtifact:
        html = listing.content.decode("utf-8", errors="replace")
        form = _hidden_fields(html)
        form["__EVENTTARGET"] = event_target
        form["__EVENTARGUMENT"] = ""
        artifact = self.request(
            "POST",
            listing.source_url,
            data=form,
            headers={
                "Accept": "*/*",
                "Origin": "https://permits.washingtoncountyor.gov",
                "Referer": listing.source_url,
                "User-Agent": USER_AGENT,
            },
            maximum_bytes=maximum_bytes,
        )
        content_type = artifact.media_type.casefold()
        disposition = str(
            artifact.headers.get("content-disposition", "")
        ).casefold()
        if "html" in content_type or (
            "attachment" not in disposition
            and artifact.content.lstrip().startswith(b"<")
        ):
            raise SourceResponseError(
                "Accela attachment postback did not return a binary document",
                url=artifact.source_url,
            )
        return artifact


def _raise_api_error(payload: Mapping[str, Any], source_url: str) -> None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return
    error = data.get("error")
    if not isinstance(error, Mapping):
        return
    code = error.get("code")
    status = str(error.get("status") or "source error")
    if code == 429 or "captcha" in status.casefold() or "turnstile" in status.casefold():
        raise ChallengeRequiredError(
            f"Washington County requested its interactive challenge: {status}",
            url=source_url,
            details={
                "source_error": dict(error),
                "interactive_route": BUILDING_APP_URL,
                "available_related_operations": [
                    "building permit taxlot search",
                    "building permit type vocabulary",
                    "permit project/activity reports",
                    "casefile search",
                ],
            },
        )
    raise SourceResponseError(
        f"Washington County API returned an error: {status}",
        url=source_url,
        details={"source_error": dict(error)},
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _element_text(element: Any) -> str | None:
    if element is None:
        return None
    return _clean(" ".join(element.stripped_strings))


def _date_value(value: Any) -> dict[str, Any]:
    raw: str | None
    timezone_name: str | None = None
    if isinstance(value, Mapping):
        raw = _clean(value.get("date"))
        timezone_name = _clean(value.get("timezone"))
    else:
        raw = _clean(value)
    normalized_input = raw[:10] if raw and re.match(r"^\d{4}-\d{2}-\d{2}", raw) else raw
    iso_date, precision = normalize_date(normalized_input)
    return {
        "raw": raw,
        "iso_date": iso_date,
        "precision": precision,
        "source_timezone": timezone_name,
    }


def _artifact_snapshot(artifact: ResponseArtifact) -> dict[str, Any]:
    return {
        "source_url": artifact.source_url,
        "status_code": artifact.status_code,
        "media_type": artifact.media_type,
        "content_bytes": len(artifact.content),
        "content_sha256": hashlib.sha256(artifact.content).hexdigest(),
    }


def _native_ref(source_id: str, record_kind: str, native_id: str) -> str:
    return (
        f"{source_id}:{COUNTY_GEOID}:{record_kind}:"
        f"{quote(str(native_id), safe='')}"
    )


def _parse_filters(
    values: Sequence[str],
    allowed: frozenset[str],
    *,
    url: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SelectionError(
                "invalid_filter",
                f"filter must be NAME=VALUE: {value!r}",
                url=url,
            )
        name, raw = value.split("=", 1)
        name = name.strip()
        raw = raw.strip()
        if name not in allowed:
            raise SelectionError(
                "unknown_filter",
                f"unsupported source-native filter: {name}",
                url=url,
                details={"allowed_fields": sorted(allowed)},
            )
        if not raw:
            raise SelectionError(
                "empty_filter",
                f"filter {name} must have a value",
                url=url,
            )
        result[name] = raw
    return result


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    return sha256_fingerprint(dict(record))


def _sort_token(values: Sequence[Any]) -> list[str]:
    return [
        canonical_json(value) if isinstance(value, (Mapping, list, tuple)) else str(value or "")
        for value in values
    ]


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    raw = canonical_json(payload).encode("utf-8")
    return CURSOR_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _cursor_decode(cursor: str, *, url: str) -> Mapping[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise SelectionError(
            "cursor_invalid",
            "cursor does not belong to this source family",
            url=url,
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise SelectionError(
            "cursor_invalid",
            "cursor payload is invalid",
            url=url,
        ) from exc
    if not isinstance(payload, Mapping) or payload.get("version") != CURSOR_VERSION:
        raise SelectionError(
            "cursor_invalid",
            "cursor version is unsupported",
            url=url,
        )
    return payload


def _page_records(
    records: Sequence[Mapping[str, Any]],
    *,
    sort_function: Callable[[Mapping[str, Any]], Sequence[Any]],
    criteria: str,
    source_key: str,
    limit: int | None,
    cursor: str | None,
    url: str,
) -> tuple[list[Mapping[str, Any]], str | None, str]:
    sorted_records = sorted(
        records,
        key=lambda record: _sort_token(
            [*sort_function(record), _record_fingerprint(record)]
        ),
    )
    fingerprints = [_record_fingerprint(record) for record in sorted_records]
    snapshot = sha256_fingerprint(fingerprints)
    remaining = sorted_records
    if cursor:
        state = _cursor_decode(cursor, url=url)
        expected = {
            "source_key": source_key,
            "criteria": criteria,
            "snapshot": snapshot,
            "total": len(sorted_records),
        }
        for key, value in expected.items():
            if state.get(key) != value:
                raise SelectionError(
                    "cursor_snapshot_changed",
                    "cursor does not match the current query snapshot",
                    url=url,
                    details={
                        "field": key,
                        "cursor_value": state.get(key),
                        "current_value": value,
                    },
                )
        last_sort = state.get("last_sort")
        if not isinstance(last_sort, list):
            raise SelectionError(
                "cursor_invalid",
                "cursor is missing its stable sort tuple",
                url=url,
            )
        last_token = _sort_token(last_sort)
        remaining = [
            record
            for record in sorted_records
            if _sort_token(
                [*sort_function(record), _record_fingerprint(record)]
            )
            > last_token
        ]
    selected = remaining if limit is None else remaining[:limit]
    next_cursor = None
    if limit is not None and len(remaining) > limit and selected:
        last_record = selected[-1]
        next_cursor = _cursor_encode(
            {
                "version": CURSOR_VERSION,
                "source_key": source_key,
                "criteria": criteria,
                "snapshot": snapshot,
                "total": len(sorted_records),
                "last_sort": [
                    *sort_function(last_record),
                    _record_fingerprint(last_record),
                ],
            }
        )
    return list(selected), next_cursor, snapshot


def _rows(
    payload: Mapping[str, Any],
    artifact: ResponseArtifact,
    *,
    component: str,
) -> list[Mapping[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list) or not all(
        isinstance(item, Mapping) for item in data
    ):
        raise SourceSchemaError(
            f"{component} data is not a record list",
            url=artifact.source_url,
        )
    total = payload.get("total")
    if isinstance(total, bool) or not isinstance(total, int):
        raise SourceSchemaError(
            f"{component} total is not an integer",
            url=artifact.source_url,
        )
    if total != len(data):
        raise SourceSchemaError(
            f"{component} total does not match returned records",
            url=artifact.source_url,
            details={"total": total, "records": len(data)},
        )
    return [dict(item) for item in data]


def _query(
    source_id: str,
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCES[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            requested_limit=limit,
            cursor=cursor,
            metadata=dict(metadata or {}),
        ),
    )


def _schema_bundle(raw_records: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    schema = inferred_schema(raw_records)
    return schema, schema_fingerprint(schema)


def _hidden_fields(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        str(item.get("name")): str(item.get("value") or "")
        for item in soup.select("input[type='hidden'][name]")
    }


def _case_sort(record: Mapping[str, Any]) -> Sequence[Any]:
    return (
        record.get("NUMBER_KEY"),
        record.get("SubmittalNo"),
        record.get("DATA_STATUS"),
    )


def _case_record(
    raw: Mapping[str, Any],
    *,
    source_url: str,
    operation: str,
    schema: Mapping[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    casefile = _clean(raw.get("NUMBER_KEY"))
    cap_parts = [
        _clean(raw.get("ID1")),
        _clean(raw.get("ID2")),
        _clean(raw.get("ID3")),
    ]
    cap_id = "-".join(part for part in cap_parts if part)
    parcels = [
        value
        for value in (
            [_clean(item) for item in raw.get("PARCEL_NO", [])]
            if isinstance(raw.get("PARCEL_NO"), list)
            else [_clean(raw.get("PARCEL_NO"))]
        )
        if value
    ]
    activities = [
        value
        for value in (
            [_clean(item) for item in raw.get("B1_ALT_ID", [])]
            if isinstance(raw.get("B1_ALT_ID"), list)
            else [_clean(raw.get("B1_ALT_ID"))]
        )
        if value
    ]
    dates = {
        "submitted": _date_value(raw.get("DATE_A")),
        "accepted": _date_value(raw.get("DATE_B")),
        "decision": _date_value(raw.get("DATE_C")),
        "entered": _date_value(raw.get("ENTERED_DATE")),
    }
    accela_url = None
    if len(cap_parts) == 3 and all(cap_parts):
        accela_parameters = {
            "Module": ACCELA_MODULE,
            "TabName": ACCELA_MODULE,
            "capID1": cap_parts[0],
            "capID2": cap_parts[1],
            "capID3": cap_parts[2],
            "agencyCode": ACCELA_AGENCY_CODE,
        }
        accela_url = f"{ACCELA_DETAIL_URL}?{urlencode(accela_parameters)}"
    return {
        "canonical_ref": _native_ref(
            CASEFILE_SOURCE_ID,
            "planning_casefile",
            casefile or _record_fingerprint(raw),
        ),
        "source_id": CASEFILE_SOURCE_ID,
        "record_kind": "planning_casefile",
        "native_record_id": casefile,
        "native_ids": {
            "casefile_number": casefile,
            "submittal_number": _clean(raw.get("SubmittalNo")),
            "accela_cap_id": cap_id or None,
            "accela_cap_parts": cap_parts if all(cap_parts) else [],
        },
        "status": _clean(raw.get("DATA_STATUS")),
        "case_type": _clean(raw.get("COMP_TYPE")),
        "case_subtype": _clean(raw.get("SUB_TYPE")),
        "description": _clean(raw.get("Description")),
        "applicant": _clean(raw.get("NAME")),
        "staff": {
            "name": _clean(raw.get("StaffName")),
            "email": _clean(raw.get("StaffEmail")),
            "native_initials": _clean(raw.get("INSP_AREA")),
        },
        "land_context": {
            "urban_rural": _clean(raw.get("URBANRURAL")),
            "cpo": _clean(raw.get("OCC")),
            "zoning": _clean(raw.get("ZONING")),
        },
        "dates": dates,
        "joins": {
            "taxlots": parcels,
            "activities": activities,
            "submittal_number": _clean(raw.get("SubmittalNo")),
            "accela_cap_id": cap_id or None,
        },
        "source_urls": {
            "api_representation": source_url,
            "interactive_casefile": (
                f"{CASEFILE_APP_URL}?searchby=search-account&account="
                f"{quote(casefile or '')}"
            ),
            "accela_detail": accela_url,
        },
        "retrieved_via": operation,
        "field_provenance": {
            "identity_status_description": "casefile_api",
            "applicant_staff": "casefile_api",
            "dates": "casefile_api",
            "taxlot_activity_joins": "casefile_api",
            "accela_cap_join": "casefile_api",
        },
        "schema": schema,
        "schema_fingerprint": fingerprint,
        "source_native": dict(raw),
    }


def search_casefiles(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    kind = CASE_SEARCH_KINDS[args.kind]
    filters = _parse_filters(
        getattr(args, "filter", []),
        CASE_FILTER_FIELDS,
        url=CASEFILE_SEARCH_URL,
    )
    query_value = _clean(getattr(args, "query", None))
    if kind.query_parameter and query_value:
        filters[kind.query_parameter] = query_value
    if kind.query_parameter and not filters.get(kind.query_parameter):
        raise SelectionError(
            "missing_query",
            f"{kind.key} search requires a query value",
            url=CASEFILE_SEARCH_URL,
        )
    if kind.key == "other" and not filters:
        raise SelectionError(
            "missing_query",
            "other casefile search requires at least one --filter",
            url=CASEFILE_SEARCH_URL,
        )
    parameters = {"searchby": kind.searchby, **filters}
    query = _query(
        CASEFILE_SOURCE_ID,
        "case_search",
        {"kind": kind.key, "filters": filters},
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "transport_profile": "browser_equivalent_public_app_request",
            "sort_tuple": [
                "NUMBER_KEY",
                "SubmittalNo",
                "DATA_STATUS",
                "record_fingerprint",
            ],
        },
    )
    payload, artifact = client.api_json(
        CASEFILE_SEARCH_URL,
        parameters=parameters,
        referer=kind.referer,
    )
    raw_records = _rows(payload, artifact, component="casefile search")
    criteria = sha256_fingerprint(parameters)
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=_case_sort,
        criteria=criteria,
        source_key=f"case-search:{kind.key}",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = [
        _case_record(
            item,
            source_url=artifact.source_url,
            operation="case_search",
            schema=schema,
            fingerprint=fingerprint,
        )
        for item in selected
    ]
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def case_detail(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    casefile = _require_casefile(args.casefile)
    query = _query(
        CASEFILE_SOURCE_ID,
        "case_detail",
        {"casefile": casefile},
    )
    parameters = {"searchby": "search-account", "account": casefile}
    payload, artifact = client.api_json(
        CASEFILE_SEARCH_URL,
        parameters=parameters,
        referer=CASEFILE_APP_URL,
    )
    raw_records = _rows(payload, artifact, component="casefile detail")
    exact = [
        item
        for item in raw_records
        if _clean(item.get("NUMBER_KEY")) == casefile
    ]
    if not exact:
        return PublicRecordsResult.success(
            query,
            [],
            raw_artifact_refs=[artifact.source_url],
        )
    if len(exact) != 1:
        raise SourceSchemaError(
            "exact casefile search returned multiple matching records",
            url=artifact.source_url,
            details={"casefile": casefile, "matching_records": len(exact)},
        )
    schema, fingerprint = _schema_bundle(raw_records)
    return PublicRecordsResult.success(
        query,
        [
            _case_record(
                exact[0],
                source_url=artifact.source_url,
                operation="case_detail",
                schema=schema,
                fingerprint=fingerprint,
            )
        ],
        raw_artifact_refs=[artifact.source_url],
    )


def _listing_sort(
    operation: str,
) -> Callable[[Mapping[str, Any]], Sequence[Any]]:
    if operation == "applications_under_review":
        return lambda item: (
            item.get("NUMBER_KEY"),
            item.get("DATE_B"),
            item.get("STATUS"),
        )
    return lambda item: (
        item.get("ID"),
        item.get("Decision"),
        item.get("STATUS"),
    )


def _case_listing_record(
    raw: Mapping[str, Any],
    *,
    operation: str,
    source_url: str,
    schema: Mapping[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    under_review = operation == "applications_under_review"
    casefile = _clean(raw.get("NUMBER_KEY" if under_review else "ID"))
    applicant = _clean(raw.get("NAME" if under_review else "Applicant"))
    parcel = _clean(raw.get("PARCEL_NO"))
    accepted = _date_value(raw.get("DATE_B")) if under_review else _date_value(None)
    decision = _date_value(raw.get("Decision"))
    hearing = _date_value(raw.get("HearingDate"))
    return {
        "canonical_ref": _native_ref(
            CASEFILE_SOURCE_ID,
            operation,
            casefile or _record_fingerprint(raw),
        ),
        "source_id": CASEFILE_SOURCE_ID,
        "record_kind": operation,
        "native_record_id": casefile,
        "status": _clean(raw.get("STATUS")),
        "procedure_type": _clean(raw.get("TYPE")),
        "application_name": _clean(raw.get("APPNAME")),
        "applicant": applicant,
        "staff": _clean(raw.get("INSP_AREA" if under_review else "Staff")),
        "urban_rural": _clean(
            raw.get("URBAN" if under_review else "UrbanRural")
        ),
        "cpo": _clean(raw.get("OCC" if under_review else "CPO")),
        "taxlot": parcel,
        "situs_address": _clean(raw.get("SitusAddress")),
        "dates": {
            "accepted": accepted,
            "decision": decision,
            "hearing": hearing,
        },
        "joins": {"casefile_number": casefile, "taxlot": parcel},
        "source_urls": {
            "api_representation": source_url,
            "casefile_detail": (
                f"{CASEFILE_APP_URL}?searchby=search-account&account="
                f"{quote(casefile or '')}"
            ),
        },
        "field_provenance": {
            "listing_fields": operation,
            "casefile_detail_join": "NUMBER_KEY" if under_review else "ID",
        },
        "schema": schema,
        "schema_fingerprint": fingerprint,
        "source_native": dict(raw),
    }


def case_listing(
    args: argparse.Namespace,
    client: CasePermitClient,
    *,
    operation: str,
) -> PublicRecordsResult:
    if operation == "applications_under_review":
        url = CASEFILE_REVIEW_URL
        referer = PROJECTS_REVIEW_APP_URL
    else:
        url = CASEFILE_DECISION_URL
        referer = DECISIONS_APP_URL
    parameters = {"searchby": "projects"}
    query = _query(
        CASEFILE_SOURCE_ID,
        operation,
        {},
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "scope": (
                "current applications under review"
                if operation == "applications_under_review"
                else "land-use notices of decision published by the current app"
            )
        },
    )
    payload, artifact = client.api_json(
        url,
        parameters=parameters,
        referer=referer,
    )
    raw_records = _rows(payload, artifact, component=operation)
    sort_function = _listing_sort(operation)
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=sort_function,
        criteria=sha256_fingerprint(parameters),
        source_key=operation,
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = [
        _case_listing_record(
            item,
            operation=operation,
            source_url=artifact.source_url,
            schema=schema,
            fingerprint=fingerprint,
        )
        for item in selected
    ]
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def staff_vocabulary(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    query = _query(
        CASEFILE_SOURCE_ID,
        "staff_vocabulary",
        {},
        limit=args.limit,
        cursor=args.cursor,
    )
    payload, artifact = client.api_json(
        STAFF_URL,
        parameters={},
        referer=CASEFILE_APP_URL,
    )
    raw_records = _rows(payload, artifact, component="staff vocabulary")
    def sort_function(item: Mapping[str, Any]) -> Sequence[Any]:
        return (
            item.get("LastName"),
            item.get("FirstName"),
            item.get("PP_Initials"),
        )
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=sort_function,
        criteria=sha256_fingerprint({}),
        source_key="casefile-staff",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = [
        {
            "canonical_ref": _native_ref(
                CASEFILE_SOURCE_ID,
                "staff_vocabulary",
                _clean(item.get("PP_Initials")) or _record_fingerprint(item),
            ),
            "source_id": CASEFILE_SOURCE_ID,
            "record_kind": "casefile_staff_vocabulary",
            "native_record_id": _clean(item.get("PP_Initials")),
            "name": _clean(
                f"{item.get('FirstName') or ''} {item.get('LastName') or ''}"
            ),
            "group": _clean(item.get("PP_Group")),
            "source_url": artifact.source_url,
            "schema": schema,
            "schema_fingerprint": fingerprint,
            "source_native": dict(item),
        }
        for item in selected
    ]
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def _require_casefile(value: str) -> str:
    casefile = _clean(value)
    if not casefile or not re.fullmatch(r"L\d{7}", casefile, re.IGNORECASE):
        raise SelectionError(
            "invalid_casefile",
            "casefile must use the county L-number form, for example L2500106",
            url=CASEFILE_APP_URL,
        )
    return casefile.upper()


def _taxlot_collection(
    payload: Mapping[str, Any],
    artifact: ResponseArtifact,
    collection: str,
) -> list[Mapping[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise SourceSchemaError(
            "taxlot project/activity response data is not an object",
            url=artifact.source_url,
        )
    selected = data.get(collection)
    if selected is None:
        return []
    if isinstance(selected, Mapping):
        selected = selected.get("data")
    if not isinstance(selected, list) or not all(
        isinstance(item, Mapping) for item in selected
    ):
        raise SourceSchemaError(
            f"taxlot {collection} representation is not a record list",
            url=artifact.source_url,
        )
    return [dict(item) for item in selected]


def _taxlot_record(
    raw: Mapping[str, Any],
    *,
    collection: str,
    taxlot: str,
    source_url: str,
    schema: Mapping[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    is_activity = collection == "activity"
    project_number = _clean(raw.get("Project_No"))
    casefile = _clean(raw.get("PDevelop_No"))
    activity_or_permit = _clean(raw.get("APermit_No"))
    native_id = (
        activity_or_permit
        if is_activity
        else casefile or project_number or _record_fingerprint(raw)
    )
    return {
        "canonical_ref": _native_ref(
            TAXLOT_ACTIVITY_SOURCE_ID,
            f"taxlot_{collection}",
            str(native_id),
        ),
        "source_id": TAXLOT_ACTIVITY_SOURCE_ID,
        "record_kind": f"taxlot_{collection}",
        "native_record_id": native_id,
        "taxlot": _clean(raw.get("ParcelNo") or raw.get("Parcel_No")) or taxlot,
        "project": {
            "number": project_number,
            "casefile_or_development_number": casefile,
            "status": _clean(raw.get("PData_Status")),
            "type": _clean(raw.get("PComp_Type")),
            "description": _clean(raw.get("PDescription")),
        },
        "activity": (
            {
                "number": activity_or_permit,
                "status": _clean(raw.get("AData_Status")),
                "type": _clean(raw.get("AComp_Type")),
                "description": _clean(raw.get("ADescription")),
            }
            if is_activity
            else None
        ),
        "conditions": {
            "type": _clean(raw.get("CondType")),
            "lock_comments": _clean(raw.get("LockComments")),
        },
        "joins": {
            "taxlot": _clean(raw.get("ParcelNo") or raw.get("Parcel_No"))
            or taxlot,
            "project_number": project_number,
            "casefile_or_development_number": casefile,
            "activity_or_permit_number": activity_or_permit,
        },
        "source_urls": {
            "api_representation": source_url,
            "interactive_taxlot_report": (
                f"{TAXLOT_REPORT_APP_URL}?searchby=taxlot&tlno={quote(taxlot)}"
            ),
        },
        "field_provenance": {
            "project_fields": "taxlot_project_activity_api.projects",
            "activity_fields": (
                "taxlot_project_activity_api.activity" if is_activity else None
            ),
        },
        "schema": schema,
        "schema_fingerprint": fingerprint,
        "source_native": dict(raw),
    }


def taxlot_activity(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    taxlot = _clean(args.taxlot)
    if not taxlot:
        raise SelectionError(
            "missing_taxlot",
            "taxlot must be non-empty",
            url=TAXLOT_ACTIVITY_URL,
        )
    collection = args.collection
    query = _query(
        TAXLOT_ACTIVITY_SOURCE_ID,
        "taxlot_project_activity",
        {"taxlot": taxlot, "collection": collection},
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "available_collections": ["projects", "activity"],
            "sort_tuple": [
                "collection",
                "Project_No",
                "PDevelop_No",
                "APermit_No",
                "record_fingerprint",
            ],
        },
    )
    payload, artifact = client.api_json(
        TAXLOT_ACTIVITY_URL,
        parameters={"tlno": taxlot},
        referer=TAXLOT_REPORT_APP_URL,
    )
    collections = ["projects", "activity"] if collection == "all" else [collection]
    raw_tagged: list[dict[str, Any]] = []
    raw_by_collection: dict[str, list[Mapping[str, Any]]] = {}
    for collection_name in collections:
        records = _taxlot_collection(payload, artifact, collection_name)
        raw_by_collection[collection_name] = records
        raw_tagged.extend(
            {"_collection": collection_name, **dict(item)} for item in records
        )
    def sort_function(item: Mapping[str, Any]) -> Sequence[Any]:
        return (
            item.get("_collection"),
            item.get("Project_No"),
            item.get("PDevelop_No"),
            item.get("APermit_No"),
        )
    selected, next_cursor, _snapshot = _page_records(
        raw_tagged,
        sort_function=sort_function,
        criteria=sha256_fingerprint(
            {"taxlot": taxlot, "collection": collection}
        ),
        source_key="taxlot-project-activity",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schemas = {
        name: {
            "schema": _schema_bundle(items)[0],
            "schema_fingerprint": _schema_bundle(items)[1],
        }
        for name, items in raw_by_collection.items()
    }
    records: list[dict[str, Any]] = []
    for tagged in selected:
        collection_name = str(tagged["_collection"])
        raw = {key: value for key, value in tagged.items() if key != "_collection"}
        component_schema = schemas[collection_name]
        records.append(
            _taxlot_record(
                raw,
                collection=collection_name,
                taxlot=taxlot,
                source_url=artifact.source_url,
                schema=component_schema["schema"],
                fingerprint=component_schema["schema_fingerprint"],
            )
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def _building_sort(
    kind: str,
) -> Callable[[Mapping[str, Any]], Sequence[Any]]:
    if kind == "types":
        return lambda item: (
            item.get("RecordAlias"),
            item.get("RecordType"),
            item.get("RecordSubType"),
        )
    return lambda item: (
        item.get("PermitNO") or item.get("PermitNo"),
        item.get("Project"),
        item.get("ParcelNo"),
    )


def _building_record(
    raw: Mapping[str, Any],
    *,
    kind: str,
    source_url: str,
    schema: Mapping[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    if kind == "types":
        native_id = "|".join(
            _clean(raw.get(field)) or ""
            for field in ("RecordType", "RecordSubType", "RecordCategory")
        )
        return {
            "canonical_ref": _native_ref(
                BUILDING_SOURCE_ID, "building_permit_type", native_id
            ),
            "source_id": BUILDING_SOURCE_ID,
            "record_kind": "building_permit_type",
            "native_record_id": native_id,
            "record_type": _clean(raw.get("RecordType")),
            "record_subtype": _clean(raw.get("RecordSubType")),
            "record_category": _clean(raw.get("RecordCategory")),
            "record_alias": _clean(raw.get("RecordAlias")),
            "source_url": source_url,
            "schema": schema,
            "schema_fingerprint": fingerprint,
            "source_native": dict(raw),
        }
    permit_number = _clean(raw.get("PermitNO") or raw.get("PermitNo"))
    return {
        "canonical_ref": _native_ref(
            BUILDING_SOURCE_ID,
            "building_permit_index",
            permit_number or _record_fingerprint(raw),
        ),
        "source_id": BUILDING_SOURCE_ID,
        "record_kind": "building_permit_index",
        "native_record_id": permit_number,
        "permit_number": permit_number,
        "project_number": _clean(raw.get("Project")),
        "taxlot": _clean(raw.get("ParcelNo")),
        "address": _clean(raw.get("Address")),
        "joins": {
            "permit_number": permit_number,
            "project_number": _clean(raw.get("Project")),
            "taxlot": _clean(raw.get("ParcelNo")),
        },
        "source_urls": {
            "api_representation": source_url,
            "interactive_permit_search": BUILDING_APP_URL,
        },
        "field_provenance": {
            "permit_project_taxlot_address": "building_permit_search_api"
        },
        "schema": schema,
        "schema_fingerprint": fingerprint,
        "source_native": dict(raw),
    }


def building_types(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    query = _query(
        BUILDING_SOURCE_ID,
        "building_permit_types",
        {},
        limit=args.limit,
        cursor=args.cursor,
    )
    payload, artifact = client.api_json(
        BUILDING_TYPES_URL,
        parameters={},
        referer=BUILDING_APP_URL,
    )
    raw_records = _rows(payload, artifact, component="building permit types")
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=_building_sort("types"),
        criteria=sha256_fingerprint({}),
        source_key="building-types",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = [
        _building_record(
            item,
            kind="types",
            source_url=artifact.source_url,
            schema=schema,
            fingerprint=fingerprint,
        )
        for item in selected
    ]
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def building_search(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    kind = BUILDING_SEARCH_KINDS[args.kind]
    filters = _parse_filters(
        getattr(args, "filter", []),
        BUILDING_FILTER_FIELDS,
        url=BUILDING_SEARCH_URL,
    )
    query_value = _clean(getattr(args, "query", None))
    if kind.query_parameter and query_value:
        filters[kind.query_parameter] = query_value
    if kind.query_parameter and not filters.get(kind.query_parameter):
        raise SelectionError(
            "missing_query",
            f"{kind.key} building search requires a query value or matching --filter",
            url=BUILDING_SEARCH_URL,
        )
    parameters = {"searchby": kind.searchby, **filters}
    query = _query(
        BUILDING_SOURCE_ID,
        "building_permit_search",
        {"kind": kind.key, "filters": filters},
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "operation_access_is_source_defined": True,
            "interactive_route": BUILDING_APP_URL,
        },
    )
    payload, artifact = client.api_json(
        BUILDING_SEARCH_URL,
        parameters=parameters,
        referer=BUILDING_APP_URL,
    )
    raw_records = _rows(payload, artifact, component="building permit search")
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=_building_sort(kind.key),
        criteria=sha256_fingerprint(parameters),
        source_key=f"building-search:{kind.key}",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = [
        _building_record(
            item,
            kind=kind.key,
            source_url=artifact.source_url,
            schema=schema,
            fingerprint=fingerprint,
        )
        for item in selected
    ]
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def _report_sort(
    kind: str,
) -> Callable[[Mapping[str, Any]], Sequence[Any]]:
    fields = {
        "project": ("NUMBER_KEY", "DATE_A"),
        "activity": ("Activity_No", "Entered_Date"),
        "people": ("Name", "Relationship"),
        "inspection": ("Number_Key", "Insp_Date", "Insp_ID"),
        "review": ("PermitNo", "TaskDate", "Task"),
    }[kind]
    return lambda item: tuple(item.get(field) for field in fields)


def _report_native_id(kind: str, raw: Mapping[str, Any]) -> str:
    if kind == "project":
        return _clean(raw.get("NUMBER_KEY")) or _record_fingerprint(raw)
    if kind == "activity":
        return _clean(raw.get("Activity_No")) or _record_fingerprint(raw)
    if kind == "people":
        parts = (_clean(raw.get("Name")), _clean(raw.get("Relationship")))
    elif kind == "inspection":
        parts = (
            _clean(raw.get("Number_Key")),
            _clean(raw.get("Insp_ID")),
            _date_value(raw.get("Insp_Date")).get("iso_date"),
        )
    else:
        parts = (
            _clean(raw.get("PermitNo")),
            _clean(raw.get("Task")),
            _clean(raw.get("TaskDate")),
        )
    native_id = "|".join(str(value or "") for value in parts)
    return native_id if native_id.strip("|") else _record_fingerprint(raw)


def _report_joins(kind: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "project":
        activities = raw.get("ACTIVITIES")
        activity_numbers = [
            _clean(item.get("NUMBER_KEY"))
            for item in activities
            if isinstance(item, Mapping) and _clean(item.get("NUMBER_KEY"))
        ] if isinstance(activities, list) else []
        return {
            "project_number": _clean(raw.get("NUMBER_KEY")),
            "taxlot": _clean(raw.get("PARCEL_NO")),
            "activity_or_permit_numbers": activity_numbers,
            "accela_cap_id": "-".join(
                str(raw.get(field) or "")
                for field in ("B1_PER_ID1", "B1_PER_ID2", "B1_PER_ID3")
            ),
        }
    if kind == "activity":
        parcels = raw.get("Parcel_No")
        return {
            "activity_number": _clean(raw.get("Activity_No")),
            "project_or_casefile": _clean(raw.get("Project")),
            "taxlots": (
                [_clean(item) for item in parcels if _clean(item)]
                if isinstance(parcels, list)
                else [_clean(parcels)] if _clean(parcels) else []
            ),
        }
    if kind in {"inspection", "review"}:
        return {
            "permit_number": _clean(
                raw.get("Number_Key") or raw.get("PermitNo")
            )
        }
    return {}


def _report_dates(kind: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "project":
        return {
            "opened": _date_value(raw.get("DATE_A")),
            "completed": _date_value(raw.get("DATE_B")),
        }
    if kind == "activity":
        return {
            label: _date_value(raw.get(field))
            for label, field in (
                ("entered", "Entered_Date"),
                ("accepted", "Acc_Date"),
                ("submitted", "Sub_Date"),
                ("issued", "IssuedDate"),
                ("final", "FinalDate"),
                ("expires", "Exp_Date"),
            )
        }
    if kind == "inspection":
        return {"inspection": _date_value(raw.get("Insp_Date"))}
    if kind == "review":
        return {"task": _date_value(raw.get("TaskDate"))}
    return {}


def permit_report(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    kind = args.kind
    identifier = _clean(args.identifier)
    if not identifier:
        raise SelectionError(
            "missing_identifier",
            "report identifier must be non-empty",
            url=PERMIT_REPORT_URL,
        )
    parameters = {"searchby": kind, "activitynum": identifier}
    query = _query(
        PERMIT_REPORT_SOURCE_ID,
        "permit_report",
        {"kind": kind, "identifier": identifier},
        limit=args.limit,
        cursor=args.cursor,
    )
    payload, artifact = client.api_json(
        PERMIT_REPORT_URL,
        parameters=parameters,
        referer=(
            PROJECT_REPORT_APP_URL if kind == "project" else TAXLOT_REPORT_APP_URL
        ),
    )
    raw_records = _rows(payload, artifact, component=f"{kind} report")
    selected, next_cursor, _snapshot = _page_records(
        raw_records,
        sort_function=_report_sort(kind),
        criteria=sha256_fingerprint(parameters),
        source_key=f"permit-report:{kind}",
        limit=args.limit,
        cursor=args.cursor,
        url=artifact.source_url,
    )
    schema, fingerprint = _schema_bundle(raw_records)
    records = []
    for raw in selected:
        native_id = _report_native_id(kind, raw)
        records.append(
            {
                "canonical_ref": _native_ref(
                    PERMIT_REPORT_SOURCE_ID,
                    f"{kind}_report",
                    native_id,
                ),
                "source_id": PERMIT_REPORT_SOURCE_ID,
                "record_kind": f"{kind}_report",
                "native_record_id": native_id,
                "status": _clean(
                    raw.get("DATA_STATUS")
                    or raw.get("Data_Status")
                    or raw.get("Insp_Result")
                    or raw.get("TaskStatus")
                ),
                "type": _clean(
                    raw.get("TITLE_TYPE")
                    or raw.get("Type_Title")
                    or raw.get("AComp_Type")
                    or raw.get("Insp_ID")
                    or raw.get("Type")
                    or raw.get("Relationship")
                ),
                "description": _clean(
                    raw.get("DESCRIPTION")
                    or raw.get("Description")
                    or raw.get("Insp_Comments")
                    or raw.get("Comment")
                ),
                "dates": _report_dates(kind, raw),
                "joins": _report_joins(kind, raw),
                "source_urls": {
                    "api_representation": artifact.source_url,
                    "interactive_report": (
                        f"{PROJECT_REPORT_APP_URL if kind == 'project' else TAXLOT_REPORT_APP_URL}"
                        f"?searchby={quote(kind)}&activitynum={quote(identifier)}"
                    ),
                },
                "field_provenance": {"report_fields": f"permit_api.{kind}"},
                "schema": schema,
                "schema_fingerprint": fingerprint,
                "source_native": dict(raw),
            }
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=[artifact.source_url],
    )


def _resolve_case_cap(
    client: CasePermitClient,
    casefile: str,
) -> tuple[Mapping[str, Any], ResponseArtifact, tuple[str, str, str]]:
    payload, artifact = client.api_json(
        CASEFILE_SEARCH_URL,
        parameters={"searchby": "search-account", "account": casefile},
        referer=CASEFILE_APP_URL,
    )
    raw_records = _rows(payload, artifact, component="casefile Accela join")
    exact = [
        item
        for item in raw_records
        if _clean(item.get("NUMBER_KEY")) == casefile
    ]
    if not exact:
        raise SourceResponseError(
            f"casefile {casefile} was not found in the county casefile index",
            url=artifact.source_url,
        )
    if len(exact) != 1:
        raise SourceSchemaError(
            "casefile Accela join returned multiple exact matches",
            url=artifact.source_url,
            details={"casefile": casefile, "matching_records": len(exact)},
        )
    cap_parts = tuple(_clean(exact[0].get(field)) for field in ("ID1", "ID2", "ID3"))
    if len(cap_parts) != 3 or not all(cap_parts):
        raise SourceSchemaError(
            "casefile does not expose a complete Accela CAP key",
            url=artifact.source_url,
            details={"casefile": casefile, "cap_parts": list(cap_parts)},
        )
    return exact[0], artifact, (cap_parts[0], cap_parts[1], cap_parts[2])


def _attachment_url(record_html: str, record_url: str) -> str:
    soup = BeautifulSoup(record_html, "html.parser")
    iframe = soup.select_one("iframe[id$='iframeAttachmentList']")
    source = _clean(iframe.get("src")) if iframe is not None else None
    if not source or "AttachmentsList.aspx" not in source:
        raise SourceSchemaError(
            "Accela record does not publish its attachment-list iframe",
            url=record_url,
        )
    return urljoin(record_url, source)


def _postback_target(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"__doPostBack\(['\"]([^'\"]+)", value)
    if not match:
        match = re.search(r"__doPostBack\(&#39;([^&]+)", value)
    return match.group(1) if match else None


def _accela_document_detail_url(document_number: str) -> str:
    parameters = {
        "Module": ACCELA_MODULE,
        "isPeopleDocument": "False",
        "agencyCode": ACCELA_AGENCY_CODE,
        "documentNo": document_number,
        "specificEntity": "",
    }
    return f"{ACCELA_DOCUMENT_DETAIL_URL}?{urlencode(parameters)}"


def parse_accela_attachments(
    html: str,
    listing_url: str,
) -> list[dict[str, Any]]:
    """Parse source-listed Accela attachment metadata and postback identities."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#attachmentList_gdvAttachmentList")
    if table is None:
        return []
    documents: list[dict[str, Any]] = []
    # Accela nests responsive/mobile renderings inside a desktop row.  Only the
    # grid's direct rows represent source documents; recursive selection repeats
    # the same document number for each rendering.
    for row in table.find_all("tr", recursive=False):
        action = row.find("a", attrs={"onclick": re.compile("ViewDocumentDetails")})
        match = (
            re.search(
                r"ViewDocumentDetails\([^,]+,\s*['\"](\d+)['\"]",
                str(action.get("onclick")),
            )
            if action
            else None
        )
        document_number = match.group(1) if match else None
        if not document_number:
            continue

        def suffix_text(suffix: str) -> str | None:
            return _element_text(row.select_one(f"[id$='{suffix}']"))

        file_link = row.select_one("a[id$='_lnkFileName']")
        event_target = _postback_target(
            str(file_link.get("href")) if file_link else None
        )
        document = {
            "canonical_ref": _native_ref(
                ACCELA_SOURCE_ID,
                "accela_document",
                document_number,
            ),
            "document_number": document_number,
            "file_name": suffix_text("_lblName")
            or suffix_text("_lblFileName"),
            "record_number": suffix_text("_lblRecordNumber"),
            "record_type": suffix_text("_lblRecordType"),
            "document_type": suffix_text("_lblType"),
            "description": suffix_text("_lblDescription"),
            "file_size": suffix_text("_lblSize"),
            "latest_update": _date_value(suffix_text("_lblDate")),
            "document_status": suffix_text("_lblDocumentStatus"),
            "document_detail_url": _accela_document_detail_url(
                document_number
            ),
            "listing_url": listing_url,
            "download_event_target": event_target,
            "binary_download_available": event_target is not None,
            "source_native_text": _element_text(row),
        }
        documents.append(document)
    documents.sort(
        key=lambda item: (
            str(item.get("record_number") or ""),
            str(item.get("document_number") or ""),
        )
    )
    return documents


def _accela_bundle(
    client: CasePermitClient,
    casefile: str,
) -> tuple[
    Mapping[str, Any],
    ResponseArtifact,
    tuple[str, str, str],
    Mapping[str, Any],
    ResponseArtifact,
    list[dict[str, Any]],
    ResponseArtifact,
]:
    case_raw, case_artifact, cap_parts = _resolve_case_cap(client, casefile)
    record_html, record_artifact = client.accela_detail(cap_parts)
    try:
        parsed_record = parse_accela_record_detail(record_html)
    except ValueError as exc:
        raise SourceSchemaError(
            f"Accela record detail could not be parsed: {exc}",
            url=record_artifact.source_url,
        ) from exc
    if _clean(parsed_record.get("record_number")) != casefile:
        raise SourceSchemaError(
            "Accela record number does not match the casefile join",
            url=record_artifact.source_url,
            details={
                "expected_casefile": casefile,
                "accela_record_number": parsed_record.get("record_number"),
            },
        )
    listing_url = _attachment_url(record_html, record_artifact.source_url)
    listing_html, listing_artifact = client.accela_attachment_list(
        listing_url,
        referer=record_artifact.source_url,
    )
    documents = parse_accela_attachments(
        listing_html,
        listing_artifact.source_url,
    )
    return (
        case_raw,
        case_artifact,
        cap_parts,
        parsed_record,
        record_artifact,
        documents,
        listing_artifact,
    )


def accela_record(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    casefile = _require_casefile(args.casefile)
    query = _query(
        ACCELA_SOURCE_ID,
        "accela_record",
        {"casefile": casefile},
        metadata={
            "join_source_id": CASEFILE_SOURCE_ID,
            "document_listing_is_session_bound": True,
        },
    )
    (
        case_raw,
        case_artifact,
        cap_parts,
        parsed_record,
        record_artifact,
        documents,
        listing_artifact,
    ) = _accela_bundle(client, casefile)
    record_details = parsed_record.get("record_details", [])
    detail_map = {
        str(item.get("label")): item.get("value")
        for item in record_details
        if isinstance(item, Mapping) and item.get("label")
    }
    record = {
        "canonical_ref": _native_ref(
            ACCELA_SOURCE_ID, "current_planning_record", casefile
        ),
        "source_id": ACCELA_SOURCE_ID,
        "record_kind": "current_planning_record",
        "native_record_id": casefile,
        "native_ids": {
            "casefile_number": casefile,
            "accela_cap_parts": list(cap_parts),
            "accela_cap_id": "-".join(cap_parts),
        },
        "record_type": parsed_record.get("record_type"),
        "status": parsed_record.get("record_status"),
        "expiration_date": parsed_record.get("expiration_date"),
        "work_location": parsed_record.get("work_location"),
        "project_description": detail_map.get("Project Description"),
        "record_details": record_details,
        "record_detail_map": detail_map,
        "related_contacts": parsed_record.get("related_contacts", []),
        "additional_information": parsed_record.get(
            "additional_information", []
        ),
        "application_information": parsed_record.get(
            "application_information", []
        ),
        "parcels": parsed_record.get("parcels", []),
        "conditions": parsed_record.get("conditions", {}),
        "documents": documents,
        "joins": {
            "casefile_number": casefile,
            "casefile_taxlots": list(case_raw.get("PARCEL_NO") or []),
            "casefile_activities": list(case_raw.get("B1_ALT_ID") or []),
            "accela_cap_id": "-".join(cap_parts),
        },
        "source_urls": {
            "record_detail": record_artifact.source_url,
            "attachment_list": listing_artifact.source_url,
            "casefile_api_representation": case_artifact.source_url,
        },
        "representations": {
            "casefile_join": _artifact_snapshot(case_artifact),
            "record_detail": _artifact_snapshot(record_artifact),
            "attachment_list": _artifact_snapshot(listing_artifact),
        },
        "field_provenance": {
            "cap_join": "casefile_api",
            "record_fields": "accela_record_detail",
            "documents": "accela_attachment_list",
        },
        "schema": parsed_record.get("schema"),
        "schema_fingerprint": parsed_record.get("schema_fingerprint"),
        "document_representation_summary": {
            "listing_complete": True,
            "documents_listed": len(documents),
            "document_details_fetched": False,
            "binary_documents_fetched": False,
        },
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[
            case_artifact.source_url,
            record_artifact.source_url,
            listing_artifact.source_url,
        ],
    )


def accela_document(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    casefile = _require_casefile(args.casefile)
    document_number = _require_document_number(args.document_number)
    query = _query(
        ACCELA_SOURCE_ID,
        "accela_document_detail",
        {"casefile": casefile, "document_number": document_number},
    )
    (
        _case_raw,
        case_artifact,
        cap_parts,
        _parsed_record,
        record_artifact,
        documents,
        listing_artifact,
    ) = _accela_bundle(client, casefile)
    listed = next(
        (
            item
            for item in documents
            if item.get("document_number") == document_number
        ),
        None,
    )
    if listed is None:
        return PublicRecordsResult.success(
            query,
            [],
            raw_artifact_refs=[
                case_artifact.source_url,
                record_artifact.source_url,
                listing_artifact.source_url,
            ],
        )
    detail_html, detail_artifact = client.accela_document_detail(
        document_number,
        referer=listing_artifact.source_url,
    )
    try:
        parsed = parse_accela_document_detail(detail_html)
    except ValueError as exc:
        raise SourceSchemaError(
            f"Accela document detail could not be parsed: {exc}",
            url=detail_artifact.source_url,
        ) from exc
    field_map = parsed["field_map"]
    record = {
        "canonical_ref": _native_ref(
            ACCELA_SOURCE_ID,
            "accela_document_detail",
            f"{casefile}:{document_number}",
        ),
        "source_id": ACCELA_SOURCE_ID,
        "record_kind": "accela_document_detail",
        "native_record_id": document_number,
        "casefile_number": casefile,
        "accela_cap_id": "-".join(cap_parts),
        "document_number": document_number,
        "listing_metadata": listed,
        "fields": parsed["fields"],
        "field_map": field_map,
        "source_urls": {
            "document_detail": detail_artifact.source_url,
            "attachment_list": listing_artifact.source_url,
            "record_detail": record_artifact.source_url,
        },
        "representations": {
            "document_detail": _artifact_snapshot(detail_artifact),
            "attachment_list": _artifact_snapshot(listing_artifact),
        },
        "field_provenance": {
            "listing_metadata": "accela_attachment_list",
            "document_fields": "accela_document_detail",
        },
        "schema": parsed["schema"],
        "schema_fingerprint": parsed["schema_fingerprint"],
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[
            case_artifact.source_url,
            record_artifact.source_url,
            listing_artifact.source_url,
            detail_artifact.source_url,
        ],
    )


def accela_download(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> PublicRecordsResult:
    casefile = _require_casefile(args.casefile)
    document_number = _require_document_number(args.document_number)
    destination = Path(args.destination).expanduser()
    query = _query(
        ACCELA_SOURCE_ID,
        "accela_document_binary",
        {"casefile": casefile, "document_number": document_number},
    )
    (
        _case_raw,
        case_artifact,
        cap_parts,
        _parsed_record,
        record_artifact,
        documents,
        listing_artifact,
    ) = _accela_bundle(client, casefile)
    listed = next(
        (
            item
            for item in documents
            if item.get("document_number") == document_number
        ),
        None,
    )
    if listed is None:
        return PublicRecordsResult.success(
            query,
            [],
            raw_artifact_refs=[
                case_artifact.source_url,
                record_artifact.source_url,
                listing_artifact.source_url,
            ],
        )
    event_target = _clean(listed.get("download_event_target"))
    if not event_target:
        raise SourceResponseError(
            f"document {document_number} is listed without a binary postback",
            url=listing_artifact.source_url,
            details={"document_detail_url": listed.get("document_detail_url")},
        )
    binary = client.accela_download(
        listing_artifact,
        event_target,
        maximum_bytes=args.max_document_bytes,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary.content)
    record = {
        "canonical_ref": _native_ref(
            ACCELA_SOURCE_ID,
            "accela_document_binary",
            f"{casefile}:{document_number}",
        ),
        "source_id": ACCELA_SOURCE_ID,
        "record_kind": "accela_document_binary",
        "native_record_id": document_number,
        "casefile_number": casefile,
        "accela_cap_id": "-".join(cap_parts),
        "document": listed,
        "destination": str(destination),
        "binary_representation": _artifact_snapshot(binary),
        "field_provenance": {
            "document_identity": "accela_attachment_list",
            "binary": "accela_attachment_postback",
        },
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[
            case_artifact.source_url,
            record_artifact.source_url,
            listing_artifact.source_url,
            binary.source_url,
        ],
    )


def _require_document_number(value: str) -> str:
    document_number = _clean(value)
    if not document_number or not re.fullmatch(r"\d+", document_number):
        raise SelectionError(
            "invalid_document_number",
            "Accela document number must contain digits only",
            url=ACCELA_ROOT_URL,
        )
    return document_number


def document_routes(args: argparse.Namespace) -> PublicRecordsResult:
    casefile = _require_casefile(args.casefile)
    legacy_key = casefile[1:] if casefile.upper().startswith("L") else casefile
    legacy_parameters = {
        "searchtype": "casefiles",
        "searchstring": legacy_key,
    }
    legacy_url = f"{LEGACY_LASERFICHE_URL}?{urlencode(legacy_parameters)}"
    query = _query(
        DOCUMENT_ROUTE_SOURCE_ID,
        "casefile_document_routes",
        {"casefile": casefile},
    )
    routes = [
        {
            "route_id": "development_applications_under_review",
            "name": "Development applications under review",
            "url": PROJECTS_REVIEW_APP_URL,
            "lookup": "current listing keyed by casefile number",
            "potential_material": [
                "application status",
                "applicant",
                "parcel",
                "accepted date",
                "hearing date",
            ],
            "structured_adapter_operation": "case-review",
        },
        {
            "route_id": "frequently_discussed_development_applications",
            "name": "Frequently discussed development applications",
            "url": FREQUENTLY_DISCUSSED_URL,
            "lookup": f"search page text and linked packets for {casefile}",
            "potential_material": [
                "application packets",
                "updates",
                "staff reports",
                "appeal documents",
            ],
        },
        {
            "route_id": "recent_notices_of_decision",
            "name": "Land-use notices of decision",
            "url": DECISIONS_APP_URL,
            "lookup": "current county decision listing keyed by casefile number",
            "potential_material": [
                "decision date",
                "status",
                "applicant",
                "parcel",
            ],
            "structured_adapter_operation": "case-decisions",
        },
        {
            "route_id": "public_hearing_exhibits",
            "name": "Public hearing agendas, exhibits, and decisions",
            "url": PUBLIC_HEARINGS_URL,
            "lookup": f"find {casefile} in headings, exhibit lists, and filenames",
            "potential_material": [
                "application materials",
                "staff reports",
                "public comments",
                "appeal filings",
                "hearing exhibits",
                "final decisions",
            ],
        },
        {
            "route_id": "civicweb_land_use_hearings",
            "name": "CivicWeb land-use hearings",
            "url": CIVICWEB_LAND_USE_URL,
            "lookup": f"search meeting packets and exhibits for {casefile}",
            "potential_material": [
                "meeting packets",
                "agendas",
                "attachments",
                "recordings",
            ],
        },
        {
            "route_id": "development_applications_hub",
            "name": "Development applications in progress hub",
            "url": DEVELOPMENT_PROGRESS_URL,
            "lookup": "links the current review, casefile, decision, and hearing routes",
            "potential_material": ["current publication route discovery"],
        },
        {
            "route_id": "legacy_laserfiche_casefile",
            "name": "Legacy Laserfiche casefile route",
            "url": legacy_url,
            "lookup": "source-native legacy casefile key without the leading L",
            "potential_material": ["older casefile documents"],
            "route_provenance": "published by the county casefile application",
        },
        {
            "route_id": "permit_records_and_public_request",
            "name": "Permit records, retention guidance, and records request",
            "url": PERMIT_RECORDS_URL,
            "lookup": f"identify the request with casefile {casefile}",
            "potential_material": [
                "records not present in the public applications",
                "retained building plans",
                "casefile documents",
            ],
        },
    ]
    record = {
        "canonical_ref": _native_ref(
            DOCUMENT_ROUTE_SOURCE_ID, "casefile_document_routes", casefile
        ),
        "source_id": DOCUMENT_ROUTE_SOURCE_ID,
        "record_kind": "casefile_document_routes",
        "native_record_id": casefile,
        "casefile_number": casefile,
        "routes": routes,
        "routing_principle": (
            "Use the casefile number across current listings and separately "
            "published packets; use the records-request route for material not "
            "published through those surfaces."
        ),
        "schema": {
            "kind": "declared",
            "route_fields": [
                "route_id",
                "name",
                "url",
                "lookup",
                "potential_material",
            ],
        },
    }
    record["schema_fingerprint"] = schema_fingerprint(record["schema"])
    return PublicRecordsResult.success(query, [record])


def source_manifest() -> dict[str, Any]:
    return {
        "schema_version": "oregon-washington-case-permits-sources/1.0",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [
            SOURCES[source_id].to_dict()
            for source_id in (
                CASEFILE_SOURCE_ID,
                TAXLOT_ACTIVITY_SOURCE_ID,
                BUILDING_SOURCE_ID,
                PERMIT_REPORT_SOURCE_ID,
                ACCELA_SOURCE_ID,
                DOCUMENT_ROUTE_SOURCE_ID,
            )
        ],
        "join_graph": [
            {
                "from": CASEFILE_SOURCE_ID,
                "to": TAXLOT_ACTIVITY_SOURCE_ID,
                "fields": ["PARCEL_NO -> Parcel_No/ParcelNo"],
            },
            {
                "from": CASEFILE_SOURCE_ID,
                "to": PERMIT_REPORT_SOURCE_ID,
                "fields": [
                    "B1_ALT_ID -> Activity_No",
                    "NUMBER_KEY -> Project",
                ],
            },
            {
                "from": CASEFILE_SOURCE_ID,
                "to": ACCELA_SOURCE_ID,
                "fields": ["ID1/ID2/ID3 -> capID1/capID2/capID3"],
            },
            {
                "from": BUILDING_SOURCE_ID,
                "to": PERMIT_REPORT_SOURCE_ID,
                "fields": [
                    "Project -> NUMBER_KEY",
                    "PermitNO -> Number_Key/PermitNo",
                ],
            },
            {
                "from": CASEFILE_SOURCE_ID,
                "to": DOCUMENT_ROUTE_SOURCE_ID,
                "fields": ["NUMBER_KEY -> casefile number in packets/pages"],
            },
        ],
        "operation_triage": [
            {
                "operation": "casefile search/detail/review/decision/staff",
                "access": "anonymous public API",
                "adapter_commands": [
                    "case-search",
                    "case-detail",
                    "case-review",
                    "case-decisions",
                    "case-staff",
                ],
            },
            {
                "operation": "taxlot project/activity report",
                "access": "anonymous public API",
                "adapter_commands": ["taxlot-activity"],
            },
            {
                "operation": "building permit taxlot search and type vocabulary",
                "access": "anonymous public API",
                "adapter_commands": ["building-search taxlot", "building-types"],
            },
            {
                "operation": "building permit number/type/date/address and detail",
                "access": "source challenge may be requested by these operations",
                "adapter_commands": ["building-search", "interactive BPS route"],
                "related_anonymous_routes": [
                    "taxlot search",
                    "permit types",
                    "permit reports",
                    "casefile reports",
                ],
            },
            {
                "operation": "project/activity/people/inspection/review reports",
                "access": "anonymous public API",
                "adapter_commands": ["permit-report"],
            },
            {
                "operation": "exact CurrentPlanning detail and documents",
                "access": "anonymous session-bound Accela representations",
                "adapter_commands": [
                    "accela-record",
                    "accela-document",
                    "accela-download",
                ],
            },
            {
                "operation": "separately published casefile documents",
                "access": "official web pages, packets, legacy route, or request",
                "adapter_commands": ["document-routes"],
            },
        ],
        "sentinel_joins": {
            "casefile": PROBE_CASEFILE,
            "accela_cap_id": "25PLN-00000-00371",
            "activity": PROBE_ACTIVITY,
            "taxlot": PROBE_TAXLOT,
            "project": PROBE_PROJECT,
            "permit": PROBE_PERMIT,
        },
    }


def probe_sources(
    args: argparse.Namespace,
    client: CasePermitClient,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    def record_probe(
        source_id: str,
        operation: str,
        function: Callable[[], Mapping[str, Any]],
    ) -> None:
        try:
            detail = dict(function())
        except PublicRecordsHTTPError as exc:
            results.append(
                {
                    "source_id": source_id,
                    "operation": operation,
                    "status": exc.result_status.value,
                    "error": exc.to_contract_error().to_dict(),
                }
            )
        else:
            results.append(
                {
                    "source_id": source_id,
                    "operation": operation,
                    "status": "ok",
                    "detail": detail,
                }
            )

    def api_count(
        url: str,
        parameters: Mapping[str, Any],
        referer: str,
        component: str,
    ) -> Mapping[str, Any]:
        payload, artifact = client.api_json(
            url,
            parameters=parameters,
            referer=referer,
        )
        records = _rows(payload, artifact, component=component)
        return {"source_url": artifact.source_url, "record_count": len(records)}

    record_probe(
        CASEFILE_SOURCE_ID,
        "exact_casefile",
        lambda: api_count(
            CASEFILE_SEARCH_URL,
            {"searchby": "search-account", "account": PROBE_CASEFILE},
            CASEFILE_APP_URL,
            "casefile probe",
        ),
    )
    record_probe(
        CASEFILE_SOURCE_ID,
        "taxlot_casefiles",
        lambda: api_count(
            CASEFILE_SEARCH_URL,
            {"searchby": "search-taxlot", "tlno": PROBE_TAXLOT},
            CASEFILE_APP_URL,
            "casefile taxlot probe",
        ),
    )
    record_probe(
        CASEFILE_SOURCE_ID,
        "applications_under_review",
        lambda: api_count(
            CASEFILE_REVIEW_URL,
            {"searchby": "projects"},
            PROJECTS_REVIEW_APP_URL,
            "review probe",
        ),
    )
    record_probe(
        CASEFILE_SOURCE_ID,
        "recent_decisions",
        lambda: api_count(
            CASEFILE_DECISION_URL,
            {"searchby": "projects"},
            DECISIONS_APP_URL,
            "decision probe",
        ),
    )

    def taxlot_probe() -> Mapping[str, Any]:
        payload, artifact = client.api_json(
            TAXLOT_ACTIVITY_URL,
            parameters={"tlno": PROBE_TAXLOT},
            referer=TAXLOT_REPORT_APP_URL,
        )
        return {
            "source_url": artifact.source_url,
            "project_count": len(
                _taxlot_collection(payload, artifact, "projects")
            ),
            "activity_count": len(
                _taxlot_collection(payload, artifact, "activity")
            ),
        }

    record_probe(
        TAXLOT_ACTIVITY_SOURCE_ID,
        "taxlot_project_activity",
        taxlot_probe,
    )
    record_probe(
        BUILDING_SOURCE_ID,
        "building_taxlot",
        lambda: api_count(
            BUILDING_SEARCH_URL,
            {"searchby": "search-taxlot", "tlno": PROBE_TAXLOT},
            BUILDING_APP_URL,
            "building taxlot probe",
        ),
    )
    record_probe(
        BUILDING_SOURCE_ID,
        "building_types",
        lambda: api_count(
            BUILDING_TYPES_URL,
            {},
            BUILDING_APP_URL,
            "building type probe",
        ),
    )
    for report_kind, identifier in (
        ("project", PROBE_PROJECT),
        ("activity", PROBE_ACTIVITY),
        ("people", PROBE_ACTIVITY),
        ("inspection", PROBE_PERMIT),
        ("review", PROBE_PERMIT),
    ):
        record_probe(
            PERMIT_REPORT_SOURCE_ID,
            f"{report_kind}_report",
            lambda kind=report_kind, value=identifier: api_count(
                PERMIT_REPORT_URL,
                {"searchby": kind, "activitynum": value},
                (
                    PROJECT_REPORT_APP_URL
                    if kind == "project"
                    else TAXLOT_REPORT_APP_URL
                ),
                f"{kind} report probe",
            ),
        )

    def accela_probe() -> Mapping[str, Any]:
        (
            _case_raw,
            _case_artifact,
            cap_parts,
            parsed_record,
            record_artifact,
            documents,
            listing_artifact,
        ) = _accela_bundle(client, PROBE_CASEFILE)
        return {
            "record_url": record_artifact.source_url,
            "attachment_list_url": listing_artifact.source_url,
            "record_number": parsed_record.get("record_number"),
            "cap_id": "-".join(cap_parts),
            "document_count": len(documents),
        }

    record_probe(ACCELA_SOURCE_ID, "record_and_attachments", accela_probe)
    return {
        "schema_version": "oregon-washington-case-permits-probe/1.0",
        "jurisdiction": JURISDICTION.to_dict(),
        "results": results,
    }


def _log_result(
    result: PublicRecordsResult,
    *,
    log_results: bool,
) -> None:
    if log_results:
        log_search(
            canonical_json(result.query.to_dict()),
            result.query.source.source_id,
            len(result.records),
        )


def _source_for_command(args: argparse.Namespace) -> str:
    if args.command in {
        "case-search",
        "case-detail",
        "case-review",
        "case-decisions",
        "case-staff",
    }:
        return CASEFILE_SOURCE_ID
    if args.command == "taxlot-activity":
        return TAXLOT_ACTIVITY_SOURCE_ID
    if args.command in {"building-search", "building-types"}:
        return BUILDING_SOURCE_ID
    if args.command == "permit-report":
        return PERMIT_REPORT_SOURCE_ID
    if args.command.startswith("accela-"):
        return ACCELA_SOURCE_ID
    return DOCUMENT_ROUTE_SOURCE_ID


def _failure_parameters(args: argparse.Namespace) -> dict[str, Any]:
    excluded = {
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
        "destination",
        "max_document_bytes",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in excluded and value is not None
    }


def execute(
    args: argparse.Namespace,
    *,
    client: CasePermitClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    if args.command == "sources":
        return source_manifest()
    if args.command == "document-routes":
        result = document_routes(args)
        _log_result(result, log_results=log_results)
        return result
    owns_client = client is None
    active_client = client or CasePermitClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    try:
        if args.command == "case-search":
            result = search_casefiles(args, active_client)
        elif args.command == "case-detail":
            result = case_detail(args, active_client)
        elif args.command == "case-review":
            result = case_listing(
                args,
                active_client,
                operation="applications_under_review",
            )
        elif args.command == "case-decisions":
            result = case_listing(
                args,
                active_client,
                operation="recent_decisions",
            )
        elif args.command == "case-staff":
            result = staff_vocabulary(args, active_client)
        elif args.command == "taxlot-activity":
            result = taxlot_activity(args, active_client)
        elif args.command == "building-search":
            result = building_search(args, active_client)
        elif args.command == "building-types":
            result = building_types(args, active_client)
        elif args.command == "permit-report":
            result = permit_report(args, active_client)
        elif args.command == "accela-record":
            result = accela_record(args, active_client)
        elif args.command == "accela-document":
            result = accela_document(args, active_client)
        elif args.command == "accela-download":
            result = accela_download(args, active_client)
        elif args.command == "probe":
            return probe_sources(args, active_client)
        else:
            raise ValueError(f"unknown command {args.command!r}")
        _log_result(result, log_results=log_results)
        return result
    except PublicRecordsHTTPError as exc:
        query = _query(
            _source_for_command(args),
            args.command,
            _failure_parameters(args),
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )
        result = failure_result(query, exc)
        _log_result(result, log_results=log_results)
        return result
    finally:
        if owns_client:
            active_client.close()


def _add_transport(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    _add_transport(parser)
    add_output_args(parser)


def _add_page(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted returns the complete response",
    )
    parser.add_argument("--cursor")
    _add_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Washington County Oregon planning casefiles, building "
            "permits, permit reports, and CurrentPlanning documents"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe source components, operation access, joins, and alternatives",
    )
    add_output_args(sources)

    case_search = sub.add_parser(
        "case-search",
        help="Search development casefiles by a source-native mode",
    )
    case_search.add_argument("kind", choices=sorted(CASE_SEARCH_KINDS))
    case_search.add_argument("query", nargs="?")
    case_search.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Add a source-native casefile filter",
    )
    _add_page(case_search)

    detail = sub.add_parser(
        "case-detail",
        help="Fetch an exact casefile and its Accela CAP join",
    )
    detail.add_argument("casefile")
    _add_output(detail)

    review = sub.add_parser(
        "case-review",
        help="List current development applications under review",
    )
    _add_page(review)

    decisions = sub.add_parser(
        "case-decisions",
        help="List decisions published by the current notice application",
    )
    _add_page(decisions)

    staff = sub.add_parser(
        "case-staff",
        help="List the casefile application's staff search vocabulary",
    )
    _add_page(staff)

    taxlot = sub.add_parser(
        "taxlot-activity",
        help="Fetch taxlot-linked projects and activities",
    )
    taxlot.add_argument("taxlot")
    taxlot.add_argument(
        "--collection",
        choices=("all", "projects", "activity"),
        default="all",
    )
    _add_page(taxlot)

    building_search_parser = sub.add_parser(
        "building-search",
        help="Use a building-permit search operation",
    )
    building_search_parser.add_argument(
        "kind", choices=sorted(BUILDING_SEARCH_KINDS)
    )
    building_search_parser.add_argument("query", nargs="?")
    building_search_parser.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Add a source-native building search field",
    )
    _add_page(building_search_parser)

    types = sub.add_parser(
        "building-types",
        help="List the public building-permit type vocabulary",
    )
    _add_page(types)

    report = sub.add_parser(
        "permit-report",
        help="Fetch a project, activity, people, inspection, or review report",
    )
    report.add_argument("kind", choices=sorted(REPORT_KINDS))
    report.add_argument("identifier")
    _add_page(report)

    accela_record_parser = sub.add_parser(
        "accela-record",
        help="Fetch exact CurrentPlanning detail and its attachment list",
    )
    accela_record_parser.add_argument("casefile")
    _add_output(accela_record_parser)

    accela_document_parser = sub.add_parser(
        "accela-document",
        help="Fetch metadata for a document listed on an exact record",
    )
    accela_document_parser.add_argument("casefile")
    accela_document_parser.add_argument("document_number")
    _add_output(accela_document_parser)

    download = sub.add_parser(
        "accela-download",
        help="Download a listed Accela document through its source postback",
    )
    download.add_argument("casefile")
    download.add_argument("document_number")
    download.add_argument("--destination", required=True)
    download.add_argument(
        "--max-document-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_output(download)

    routes = sub.add_parser(
        "document-routes",
        help="Return official case-number document alternatives",
    )
    routes.add_argument("casefile")
    add_output_args(routes)

    probe = sub.add_parser(
        "probe",
        help="Run bounded sentinel probes for this source family",
    )
    _add_output(probe)
    return parser


def _validate_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "timeout", 1.0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0.0) < 0:
        parser.error("--minimum-interval cannot be negative")
    if getattr(args, "retry_attempts", 1) < 1:
        parser.error("--retry-attempts must be at least 1")
    if getattr(args, "max_document_bytes", 1) <= 0:
        parser.error("--max-document-bytes must be positive")


def _result_count(payload: PublicRecordsResult | Mapping[str, Any]) -> int:
    if isinstance(payload, PublicRecordsResult):
        return len(payload.records)
    results = payload.get("results")
    return len(results) if isinstance(results, list) else 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
    payload = execute(args)
    serialized = (
        payload.to_dict()
        if isinstance(payload, PublicRecordsResult)
        else payload
    )
    if write_output(
        serialized,
        args,
        summary=f"Washington County {args.command}",
        result_count=_result_count(payload),
    ):
        return
    print(json.dumps(serialized, indent=2, default=str))


if __name__ == "__main__":
    main()
