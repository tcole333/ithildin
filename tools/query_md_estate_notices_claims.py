#!/usr/bin/env python3
"""Query Maryland Register of Wills estate notices and filed claims.

The two official applications are separate ASP.NET WebForms sources:

* Legal Notices publishes complete notice text and a native notice occurrence
  identifier.
* Claim Search publishes an indexed claim occurrence and an exact detail page.

Both adapters discover the current form state and pager targets from live
responses. Continuation cursors replay a fresh search and bind to the effective
query, result schema, source count, and a source-specific snapshot marker.

Examples:
    uv run python tools/query_md_estate_notices_claims.py notices \
        --county Montgomery --party-type decedent --last-name Taylor
    uv run python tools/query_md_estate_notices_claims.py claims \
        --role decedent --last-name Smith --claim-status OPEN
    uv run python tools/query_md_estate_notices_claims.py claims \
        --role claimant --corporation "Bank of America"
    uv run python tools/query_md_estate_notices_claims.py claim-detail \
        270350434
    uv run python tools/query_md_estate_notices_claims.py sources
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

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
        utc_now_iso,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
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
        utc_now_iso,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


NOTICE_SOURCE_ID = "us-md-estate-legal-notices"
CLAIM_SOURCE_ID = "us-md-estate-claims"
SOURCE_IDS = (NOTICE_SOURCE_ID, CLAIM_SOURCE_ID)
STATE_CODE = "MD"
STATE_GEOID = "24"

NOTICE_SEARCH_URL = (
    "https://registers.maryland.gov/LegalNotice/Notices/NoticeSearch.aspx"
)
CLAIM_SEARCH_URL = (
    "https://registers.maryland.gov/RowNetWeb/Claims/frmClaimSearch.aspx"
)
CLAIM_DETAIL_URL = (
    "https://registers.maryland.gov/RowNetWeb/Claims/frmClaimDetail.aspx"
)
ESTATE_SEARCH_URL = "https://registers.maryland.gov/main/search.html"
OFFICE_DIRECTORY_URL = "https://registers.maryland.gov/main/directory.html"
LAND_RECORDS_URL = "https://mdlandrec.net/"
SDAT_PROPERTY_URL = (
    "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.0
DEFAULT_LIMIT: int | None = None
NATIVE_PAGE_SIZE = 20
CURSOR_PREFIX = "md-estate-supplement:v1:"
CURSOR_VERSION = 1
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
PROBE_CLAIM_LAST_NAME = "Smith"

STATUS_RE = re.compile(
    r"Viewing\s+Page\s+(?P<page>[\d,]+)\s+of\s+"
    r"(?P<pages>[\d,]+)\s*\((?P<total>[\d,]+)\s+"
    r"RECORDS?\s+TOTAL\)",
    re.I,
)
NO_RESULTS_RE = re.compile(
    r"Search\s+Criteria\s+Returned\s+No\s+Results", re.I
)
POSTBACK_RE = re.compile(
    r"__doPostBack\(\s*['\"](?P<target>[^'\"]+)['\"]\s*,\s*"
    r"['\"](?P<argument>[^'\"]*)['\"]\s*\)",
    re.I,
)
REFRESH_RE = re.compile(
    r"(?P<stamp>\d{1,2}/\d{1,2}/\d{4}\s+"
    r"\d{1,2}:\d{2}:\d{2}\s+[AP]M)"
    r"(?:\s*\((?P<instance>[^)]+)\))?",
    re.I,
)
NOTICE_ID_RE = re.compile(r"^\d+$")
CLAIM_RECORD_ID_RE = re.compile(r"^\d+$")

NOTICE_EXPECTED_FORM_IDS = {
    "county": "cboCountyId",
    "published_from": "txtDoPFrom",
    "published_to": "txtDoPTo",
    "death_month": "txtDODM",
    "death_day": "txtDODD",
    "death_year": "txtDODY",
    "party_type": "PartyType",
    "last_name": "txtLN",
    "first_name": "txtFN",
    "middle_name": "txtMN",
    "sort": "ddlSortField",
    "submit": "cmdSearch",
}
CLAIM_EXPECTED_FORM_IDS = {
    "role": "rblSearchNameBy",
    "last_name": "txtLN",
    "exact_last_name": "chkExactMatchLastName",
    "first_name": "txtFN",
    "middle_name": "txtMN",
    "surname": "txtSN",
    "corporation": "txtCorpName",
    "estate_number": "txtEstateNo",
    "filed_date": "txtDOF",
    "county": "cboCountyId",
    "claim_type": "cboType",
    "claim_status": "cboStatus",
    "linked": "rblLinkedToEstate",
    "migrated": "rblMigratedToEstate",
    "submit": "cmdSearch",
}
CLAIM_RESULT_HEADERS = (
    "County",
    "Date Filed",
    "Claim Status",
    "Estate No",
    "Decedent",
    "Corporation",
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)
NOTICE_SOURCE_METADATA = SourceMetadata(
    source_id=NOTICE_SOURCE_ID,
    name="Maryland Register of Wills Legal Notices",
    source_role="statewide_estate_publication_occurrences",
    base_url=NOTICE_SEARCH_URL,
    dataset_id="rownet-legal-notices",
    metadata={
        "authority": "Maryland Registers of Wills",
        "coverage": "all Maryland counties and Baltimore City",
        "native_page_size": NATIVE_PAGE_SIZE,
        "record_grain": "published_notice_occurrence",
    },
)
CLAIM_SOURCE_METADATA = SourceMetadata(
    source_id=CLAIM_SOURCE_ID,
    name="Maryland Register of Wills Claim Search",
    source_role="statewide_estate_claim_occurrences",
    base_url=CLAIM_SEARCH_URL,
    dataset_id="rownet-estate-claims",
    metadata={
        "authority": "Maryland Registers of Wills",
        "coverage": "all Maryland counties and Baltimore City",
        "native_page_size": NATIVE_PAGE_SIZE,
        "record_grain": "filed_claim_occurrence",
    },
)

NOTICE_WARNINGS = (
    "The record is the source-published notice occurrence and its full text; "
    "it is not the final estate docket or a current adjudicative status.",
    "County, estate number, decedent, and representative values are pivots to "
    "the separately attributable estate index and official office file.",
)
CLAIM_WARNINGS = (
    "A filed or indexed claim does not establish that the claim was allowed "
    "or adjudicated; preserve and interpret only the source-reported status.",
    "The claim RecordId identifies the occurrence. Estate number, decedent, "
    "and claimant values are pivots and do not replace that identity.",
)

RELATED_ROUTES: tuple[Mapping[str, Any], ...] = (
    {
        "source_id": NOTICE_SOURCE_ID,
        "record_role": "estate_publication_occurrence",
        "url": NOTICE_SEARCH_URL,
        "join_keys": [
            "county",
            "estate_number",
            "decedent_name",
            "personal_representative_name",
        ],
    },
    {
        "source_id": CLAIM_SOURCE_ID,
        "record_role": "filed_estate_claim_occurrence",
        "url": CLAIM_SEARCH_URL,
        "join_keys": [
            "county",
            "estate_number",
            "decedent_name",
            "claimant_name",
        ],
    },
    {
        "source_id": "us-md-estate-search",
        "record_role": "estate_case_party_status_and_docket_index",
        "url": ESTATE_SEARCH_URL,
        "join_keys": ["county", "estate_number", "decedent_name"],
    },
    {
        "source_id": "us-md-register-of-wills-offices",
        "record_role": "official_estate_file_and_copy_route",
        "url": OFFICE_DIRECTORY_URL,
        "join_keys": ["county", "estate_number", "decedent_name"],
    },
    {
        "source_id": "us-md-land-records",
        "record_role": "estate_real_property_instruments",
        "url": LAND_RECORDS_URL,
        "join_keys": [
            "county",
            "decedent_name",
            "personal_representative_name",
            "property_address",
        ],
    },
    {
        "source_id": "us-md-sdat-real-property",
        "record_role": "parcel_assessment_and_deed_reference",
        "url": SDAT_PROPERTY_URL,
        "join_keys": ["county", "owner_name", "property_address"],
    },
)


class MarylandEstateSupplementError(RuntimeError):
    """Source error with explicit public-record result semantics."""

    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False
    code = "maryland_estate_supplement_error"

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = dict(self.details)
        if self.url:
            details["url"] = _stable_url(self.url)
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class MarylandEstateSupplementSelectionError(MarylandEstateSupplementError):
    category = "query"
    code = "invalid_selection"


class MarylandEstateSupplementTransportError(MarylandEstateSupplementError):
    category = "transport"
    retryable = True
    code = "transport_error"


class MarylandEstateSupplementRestrictedError(MarylandEstateSupplementError):
    status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class MarylandEstateSupplementRateLimitedError(MarylandEstateSupplementError):
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True
    code = "rate_limited"


class MarylandEstateSupplementSourceChangedError(
    MarylandEstateSupplementError
):
    status = ResultStatus.SOURCE_CHANGED
    category = "schema"
    code = "source_changed"


class MarylandEstateSupplementCursorError(MarylandEstateSupplementError):
    category = "cursor"
    code = "stale_or_invalid_cursor"


@dataclass(frozen=True)
class RefreshMarker:
    raw: str
    timestamp: str
    instance: str | None


@dataclass(frozen=True)
class NoticeFormState:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    field_names: Mapping[str, str]
    county_values: Mapping[str, str]
    party_values: Mapping[str, str]
    sort_values: Mapping[str, str]
    default_published_from_raw: str | None
    default_published_to_raw: str | None
    schema_fingerprint: str


@dataclass(frozen=True)
class NoticeCriteria:
    county: str | None = None
    published_from: str | None = None
    published_to: str | None = None
    death_date: str | None = None
    party_type: str = "decedent"
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    sort: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.published_from,
            self.published_to,
            self.death_date,
        ):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise MarylandEstateSupplementSelectionError(
                        "Notice dates must use YYYY-MM-DD"
                    ) from exc
        if (
            self.published_from
            and self.published_to
            and self.published_from > self.published_to
        ):
            raise MarylandEstateSupplementSelectionError(
                "Publication-date start cannot be after publication-date end"
            )

    @property
    def has_overrides(self) -> bool:
        return any(
            value not in {None, ""}
            for value in (
                self.county,
                self.published_from,
                self.published_to,
                self.death_date,
                self.last_name,
                self.first_name,
                self.middle_name,
                self.sort,
            )
        ) or self.party_type != "decedent"

    def parameters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "county": _clean(self.county),
                "published_from": self.published_from,
                "published_to": self.published_to,
                "death_date": self.death_date,
                "party_type": self.party_type,
                "last_name": _clean(self.last_name),
                "first_name": _clean(self.first_name),
                "middle_name": _clean(self.middle_name),
                "sort": _clean(self.sort),
            }.items()
            if value not in {None, ""}
        }

    def form_data(self, form: NoticeFormState) -> dict[str, str]:
        data = dict(form.hidden_fields)
        data["__EVENTTARGET"] = ""
        data["__EVENTARGUMENT"] = ""
        death = date.fromisoformat(self.death_date) if self.death_date else None
        values = {
            "county": _resolve_option(
                self.county, form.county_values, "county"
            ),
            "published_from": (
                _source_date(self.published_from)
                if self.published_from
                else (form.default_published_from_raw or "")
            ),
            "published_to": (
                _source_date(self.published_to)
                if self.published_to
                else (form.default_published_to_raw or "")
            ),
            "death_month": f"{death.month:02d}" if death else "",
            "death_day": f"{death.day:02d}" if death else "",
            "death_year": str(death.year) if death else "",
            "party_type": _resolve_option(
                self.party_type, form.party_values, "party type"
            ),
            "last_name": _clean(self.last_name) or "",
            "first_name": _clean(self.first_name) or "",
            "middle_name": _clean(self.middle_name) or "",
            "sort": _resolve_option(self.sort, form.sort_values, "sort"),
            "submit": "Search",
        }
        for semantic, value in values.items():
            data[form.field_names[semantic]] = value
        return data


@dataclass(frozen=True)
class NoticeRow:
    notice_id: str
    county: str
    publication_date_raw: str
    notice_title: str | None
    full_notice_text: str
    full_notice_html: str
    source_page: int


@dataclass(frozen=True)
class NoticeResultsPage:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    current_page: int
    total_pages: int
    total_count: int
    rows: tuple[NoticeRow, ...]
    page_targets: Mapping[int, str]
    forward_target: str | None
    effective_parameters: Mapping[str, Any]
    snapshot_marker: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ClaimFormState:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    field_names: Mapping[str, str]
    county_values: Mapping[str, str]
    role_values: Mapping[str, str]
    type_values: Mapping[str, str]
    status_values: Mapping[str, str]
    linked_values: Mapping[str, str]
    migrated_values: Mapping[str, str]
    refresh: RefreshMarker
    schema_fingerprint: str


@dataclass(frozen=True)
class ClaimCriteria:
    role: str = "decedent"
    last_name: str | None = None
    exact_last_name: bool = False
    first_name: str | None = None
    middle_name: str | None = None
    surname: str | None = None
    corporation: str | None = None
    estate_number: str | None = None
    filed_date: str | None = None
    county: str | None = None
    claim_type: str | None = None
    claim_status: str | None = None
    linked_to_estate: bool | None = None
    migrated_to_estate: bool | None = None

    def __post_init__(self) -> None:
        if self.filed_date:
            try:
                date.fromisoformat(self.filed_date)
            except ValueError as exc:
                raise MarylandEstateSupplementSelectionError(
                    "Claim filing date must use YYYY-MM-DD"
                ) from exc

    def parameters(self) -> dict[str, Any]:
        parameters = {
            key: value
            for key, value in {
                "role": self.role,
                "last_name": _clean(self.last_name),
                "exact_last_name": self.exact_last_name,
                "first_name": _clean(self.first_name),
                "middle_name": _clean(self.middle_name),
                "surname": _clean(self.surname),
                "corporation": _clean(self.corporation),
                "estate_number": _clean(self.estate_number),
                "filed_date": self.filed_date,
                "county": _clean(self.county),
                "claim_type": _clean(self.claim_type),
                "claim_status": _clean(self.claim_status),
            }.items()
            if value not in {None, "", False}
        }
        if self.linked_to_estate is not None:
            parameters["linked_to_estate"] = self.linked_to_estate
        if self.migrated_to_estate is not None:
            parameters["migrated_to_estate"] = self.migrated_to_estate
        return parameters

    def form_data(self, form: ClaimFormState) -> dict[str, str]:
        data = dict(form.hidden_fields)
        data["__EVENTTARGET"] = ""
        data["__EVENTARGUMENT"] = ""
        values = {
            "role": _resolve_option(self.role, form.role_values, "claim role"),
            "last_name": _clean(self.last_name) or "",
            "first_name": _clean(self.first_name) or "",
            "middle_name": _clean(self.middle_name) or "",
            "surname": _clean(self.surname) or "",
            "corporation": _clean(self.corporation) or "",
            "estate_number": _clean(self.estate_number) or "",
            "filed_date": _source_date(self.filed_date),
            "county": _resolve_option(
                self.county, form.county_values, "county"
            ),
            "claim_type": _resolve_option(
                self.claim_type, form.type_values, "claim type"
            ),
            "claim_status": _resolve_option(
                self.claim_status, form.status_values, "claim status"
            ),
            "submit": "Search",
        }
        for semantic, value in values.items():
            data[form.field_names[semantic]] = value
        if self.exact_last_name:
            data[form.field_names["exact_last_name"]] = "on"
        else:
            data.pop(form.field_names["exact_last_name"], None)
        if self.linked_to_estate is not None:
            data[form.field_names["linked"]] = _resolve_option(
                "yes" if self.linked_to_estate else "no",
                form.linked_values,
                "linked-to-estate",
            )
        if self.migrated_to_estate is not None:
            data[form.field_names["migrated"]] = _resolve_option(
                "yes" if self.migrated_to_estate else "no",
                form.migrated_values,
                "migrated-to-estate",
            )
        return data


@dataclass(frozen=True)
class ClaimRow:
    county: str
    filed_date_raw: str
    claim_status: str
    estate_number: str | None
    decedent_name: str
    corporation_name: str | None
    record_id: str
    source_partition: str
    detail_url: str
    source_page: int


@dataclass(frozen=True)
class ClaimResultsPage:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    current_page: int
    total_pages: int
    total_count: int
    rows: tuple[ClaimRow, ...]
    page_targets: Mapping[int, str]
    forward_target: str | None
    refresh: RefreshMarker
    effective_parameters: Mapping[str, Any]
    snapshot_marker: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ClaimDetail:
    record: Mapping[str, Any]
    url: str
    refresh: RefreshMarker
    schema_fingerprint: str


@dataclass(frozen=True)
class CursorState:
    source_id: str
    effective_criteria_fingerprint: str
    schema_fingerprint: str
    snapshot_marker: str
    total_count: int
    total_pages: int
    page_number: int
    row_offset: int
    emitted_count: int


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Tag):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    normalized = " ".join(text.replace("\xa0", " ").split())
    return normalized or None


def _stable_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qs(parts.query).items()), doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _official_url(base_url: str, candidate: str) -> str:
    resolved = urljoin(base_url, candidate)
    parts = urlsplit(resolved)
    allowed = (
        "/legalnotice/notices/",
        "/rownetweb/claims/",
    )
    if (
        parts.scheme != "https"
        or parts.hostname != "registers.maryland.gov"
        or not parts.path.casefold().startswith(allowed)
    ):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement points outside its verified official routes",
            url=resolved,
        )
    return resolved


def _source_date(value: str | None) -> str:
    if not value:
        return ""
    return date.fromisoformat(value).strftime("%m/%d/%Y")


def _parse_date(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    candidate = cleaned.rstrip(".,")
    for fmt in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(candidate.title(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _form(soup: BeautifulSoup, *, url: str) -> Tag:
    form = soup.select_one("form#form1")
    if not isinstance(form, Tag):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement form is missing",
            url=url,
        )
    return form


def _hidden_fields(form: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in form.select("input[type='hidden'][name]"):
        name = _clean(node.get("name"))
        if name:
            values[name] = str(node.get("value") or "")
    if "__VIEWSTATE" not in values:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement ViewState is missing"
        )
    return values


def _field_name(
    form: Tag,
    element_id: str,
    *,
    url: str,
    radio_group: bool = False,
) -> str:
    if radio_group:
        node = form.select_one(
            f"#{element_id} input[name], input#{element_id}[name]"
        )
        if not isinstance(node, Tag):
            node = form.select_one(f"input[name='{element_id}']")
    else:
        node = form.select_one(f"#{element_id}[name]")
    name = _clean(node.get("name")) if isinstance(node, Tag) else None
    if not name:
        raise MarylandEstateSupplementSourceChangedError(
            f"Maryland estate supplement field {element_id} is missing",
            url=url,
        )
    return name


def _option_values(select: Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for option in select.select("option"):
        label = _clean(option) or ""
        value = str(option.get("value") or "")
        for key in {label.casefold(), value.casefold()}:
            values[key] = value
        if label and label.casefold() != "baltimore city":
            values[f"{label.casefold()} county"] = value
    values[""] = ""
    return values


def _radio_values(
    form: Tag,
    element_id: str,
    aliases: Mapping[str, str],
    *,
    url: str,
) -> dict[str, str]:
    nodes = form.select(f"#{element_id} input[value], input#{element_id}[value]")
    observed = {str(node.get("value") or "") for node in nodes}
    if not observed:
        raise MarylandEstateSupplementSourceChangedError(
            f"Maryland estate supplement radio group {element_id} is missing",
            url=url,
        )
    values = {value.casefold(): value for value in observed}
    for alias, native in aliases.items():
        if native in observed:
            values[alias.casefold()] = native
    return values


def _resolve_option(
    wanted: Any,
    options: Mapping[str, str],
    label: str,
) -> str:
    cleaned = _clean(wanted)
    if not cleaned:
        return options.get("", "")
    value = options.get(cleaned.casefold())
    if value is None and cleaned.casefold().endswith(" county"):
        value = options.get(cleaned.casefold().removesuffix(" county"))
    if value is None:
        raise MarylandEstateSupplementSelectionError(
            f"Unknown Maryland {label}: {cleaned}",
            details={"available_values": sorted(set(options.values()))},
        )
    return value


def _selected_value(form: Tag, element_id: str) -> str:
    node = form.select_one(f"#{element_id} option[selected]")
    if not isinstance(node, Tag):
        node = form.select_one(f"#{element_id} option")
    return str(node.get("value") or "") if isinstance(node, Tag) else ""


def _input_value(form: Tag, element_id: str) -> str:
    node = form.select_one(f"#{element_id}")
    return str(node.get("value") or "") if isinstance(node, Tag) else ""


def _checked_value(form: Tag, name: str) -> str:
    node = form.select_one(f"input[name='{name}'][checked]")
    if not isinstance(node, Tag):
        node = form.select_one(f"input[name='{name}']")
    return str(node.get("value") or "") if isinstance(node, Tag) else ""


def _refresh_marker(soup: BeautifulSoup, *, url: str) -> RefreshMarker:
    raw = _clean(soup.select_one("#lblLatestDataDateTime"))
    match = REFRESH_RE.search(raw or "")
    if not match:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim data-refresh marker is missing or changed",
            url=url,
            details={"observed": raw},
        )
    local = datetime.strptime(
        match.group("stamp"), "%m/%d/%Y %I:%M:%S %p"
    ).replace(tzinfo=ZoneInfo("America/New_York"))
    return RefreshMarker(
        raw=raw or "",
        timestamp=local.astimezone(ZoneInfo("UTC")).isoformat().replace(
            "+00:00", "Z"
        ),
        instance=_clean(match.group("instance")),
    )


def _postback_target(href: str, *, url: str) -> str:
    decoded = href.replace("&#39;", "'")
    match = POSTBACK_RE.search(decoded)
    if not match:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement pager postback changed",
            url=url,
            details={"href": href},
        )
    return match.group("target")


def _pager(
    table: Tag,
    *,
    current_page: int,
    url: str,
) -> tuple[dict[int, str], str | None]:
    page_targets: dict[int, str] = {}
    ellipsis: list[str] = []
    for link in table.select("a[href*='__doPostBack']"):
        label = _clean(link) or ""
        target = _postback_target(str(link.get("href", "")), url=url)
        if label.isdigit():
            page_targets[int(label)] = target
        elif label == "...":
            ellipsis.append(target)
    forward = None
    if ellipsis:
        visible_pages = sorted(page_targets)
        if not visible_pages or max(visible_pages) >= current_page:
            forward = ellipsis[-1]
    return page_targets, forward


def _page_status(
    soup: BeautifulSoup,
    *,
    url: str,
) -> tuple[int, int, int] | None:
    status_text = _clean(soup.select_one("#litStatus"))
    if not status_text:
        status_text = _clean(soup.select_one("#tblStatus"))
    page_match = STATUS_RE.search(status_text or "")
    if page_match:
        return tuple(
            int(page_match.group(name).replace(",", ""))
            for name in ("page", "pages", "total")
        )
    if NO_RESULTS_RE.search(_clean(soup) or ""):
        return None
    raise MarylandEstateSupplementSourceChangedError(
        "Maryland estate supplement result-count banner changed",
        url=url,
        details={"observed": status_text},
    )


def _validate_page_count(total_pages: int, total_count: int, *, url: str) -> None:
    if total_pages != math.ceil(total_count / NATIVE_PAGE_SIZE):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement page count conflicts with its native page size",
            url=url,
            details={
                "total_pages": total_pages,
                "total_count": total_count,
                "native_page_size": NATIVE_PAGE_SIZE,
            },
        )


def parse_notice_form(
    html: str,
    page_url: str = NOTICE_SEARCH_URL,
) -> NoticeFormState:
    """Discover the current legal-notice form contract."""

    safe_url = _official_url(NOTICE_SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or NOTICE_SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    field_names = {
        semantic: _field_name(
            form,
            element_id,
            url=safe_url,
            radio_group=(semantic == "party_type"),
        )
        for semantic, element_id in NOTICE_EXPECTED_FORM_IDS.items()
    }
    county_node = form.select_one("#cboCountyId")
    sort_node = form.select_one("#ddlSortField")
    if not isinstance(county_node, Tag) or not isinstance(sort_node, Tag):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland notice selectors are missing",
            url=safe_url,
        )
    counties = _option_values(county_node)
    if len({value for value in counties.values() if value}) != 24:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland notice county selector no longer exposes 24 jurisdictions",
            url=safe_url,
        )
    parties = _radio_values(
        form,
        "PartyTypeDecedent",
        {
            "decedent": "Decedent",
            "personal representative": "PersonalRepresentative",
            "personal_representative": "PersonalRepresentative",
            "representative": "PersonalRepresentative",
        },
        url=safe_url,
    )
    if "PersonalRepresentative" not in set(parties.values()):
        parties = _radio_values(
            form,
            "PartyTypePR",
            {
                "decedent": "Decedent",
                "personal representative": "PersonalRepresentative",
                "personal_representative": "PersonalRepresentative",
                "representative": "PersonalRepresentative",
            },
            url=safe_url,
        ) | parties
    sorts = _option_values(sort_node)
    declared = {
        "field_names": field_names,
        "county_values": sorted(set(counties.values())),
        "party_values": sorted(set(parties.values())),
        "sort_values": sorted(set(sorts.values())),
        "hidden_fields": sorted(hidden),
    }
    return NoticeFormState(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        field_names=field_names,
        county_values=counties,
        party_values=parties,
        sort_values=sorts,
        default_published_from_raw=_clean(_input_value(form, "txtDoPFrom")),
        default_published_to_raw=_clean(_input_value(form, "txtDoPTo")),
        schema_fingerprint=sha256_fingerprint(declared),
    )


def _notice_effective_parameters(form: Tag) -> dict[str, Any]:
    death_parts = (
        _input_value(form, "txtDODM"),
        _input_value(form, "txtDODD"),
        _input_value(form, "txtDODY"),
    )
    death_raw = "/".join(death_parts) if all(death_parts) else None
    return {
        "county_value": _selected_value(form, "cboCountyId"),
        "published_from_raw": _clean(_input_value(form, "txtDoPFrom")),
        "published_to_raw": _clean(_input_value(form, "txtDoPTo")),
        "death_date_raw": death_raw,
        "party_type": _checked_value(form, "PartyType"),
        "last_name": _clean(_input_value(form, "txtLN")),
        "first_name": _clean(_input_value(form, "txtFN")),
        "middle_name": _clean(_input_value(form, "txtMN")),
        "sort": _selected_value(form, "ddlSortField"),
    }


def _notice_title(card: Tag) -> str | None:
    for paragraph in card.select("p"):
        text = _clean(paragraph)
        if text and "NOTICE" in text.upper() and len(text) <= 240:
            return text
    for strong in card.select("strong"):
        text = _clean(strong)
        if text and ("NOTICE" in text.upper() or "CAVEAT" in text.upper()):
            return text
    return None


def parse_notice_results_page(
    html: str,
    page_url: str = NOTICE_SEARCH_URL,
) -> NoticeResultsPage:
    """Parse one legal-notice result page, including complete notice bodies."""

    safe_url = _official_url(NOTICE_SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or NOTICE_SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    effective = _notice_effective_parameters(form)
    page_state = _page_status(soup, url=safe_url)
    if page_state is None:
        marker = sha256_fingerprint(
            {"effective": effective, "total": 0, "empty": True}
        )
        return NoticeResultsPage(
            html=html,
            url=safe_url,
            action_url=action_url,
            hidden_fields=hidden,
            current_page=1,
            total_pages=0,
            total_count=0,
            rows=(),
            page_targets={},
            forward_target=None,
            effective_parameters=effective,
            snapshot_marker=marker,
            schema_fingerprint=sha256_fingerprint(
                {
                    "record_kind": "estate_legal_notice",
                    "native_id": "card-body-id",
                    "valid_empty": True,
                }
            ),
        )
    current_page, total_pages, total_count = page_state
    _validate_page_count(total_pages, total_count, url=safe_url)
    table = soup.select_one("#dgSearchResults")
    if not isinstance(table, Tag):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland notice result table is missing",
            url=safe_url,
        )
    rows: list[NoticeRow] = []
    for card in table.select("div.card-body[id]"):
        notice_id = _clean(card.get("id"))
        if not notice_id or not NOTICE_ID_RE.fullmatch(notice_id):
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland notice result lacks a numeric notice ID",
                url=safe_url,
            )
        strong_values = [
            value
            for node in card.select(".d-flex.justify-content-between strong")
            for value in [_clean(node)]
            if value
        ]
        county = next(
            (value for value in strong_values if "County" in value),
            None,
        )
        publication = next(
            (
                value.removeprefix("Published on ").strip()
                for value in strong_values
                if value.startswith("Published on ")
            ),
            None,
        )
        body = card.select_one("div.small span")
        if not county or not publication or not isinstance(body, Tag):
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland notice card header or body changed",
                url=safe_url,
                details={"notice_id": notice_id},
            )
        body_text = _clean(body) or ""
        if not body_text:
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland notice body is empty",
                url=safe_url,
                details={"notice_id": notice_id},
            )
        rows.append(
            NoticeRow(
                notice_id=notice_id,
                county=county,
                publication_date_raw=publication,
                notice_title=_notice_title(card),
                full_notice_text=body_text,
                full_notice_html=body.decode_contents(),
                source_page=current_page,
            )
        )
    if not rows:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland notice result page contains no notice cards",
            url=safe_url,
        )
    page_targets, forward = _pager(
        table, current_page=current_page, url=safe_url
    )
    declared = {
        "record_fields": list(NoticeRow.__dataclass_fields__),
        "native_id": "card-body-id",
        "pager": "aspnet_gridview_dynamic_postback",
        "body": "full_source_html_and_text",
    }
    marker = sha256_fingerprint(
        {
            "total": total_count,
            "effective": effective,
            "first_notice_id": rows[0].notice_id if current_page == 1 else None,
            "last_notice_id": rows[-1].notice_id if current_page == 1 else None,
            "first_publication": (
                rows[0].publication_date_raw if current_page == 1 else None
            ),
        }
    )
    return NoticeResultsPage(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        current_page=current_page,
        total_pages=total_pages,
        total_count=total_count,
        rows=tuple(rows),
        page_targets=page_targets,
        forward_target=forward,
        effective_parameters=effective,
        snapshot_marker=marker,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def parse_claim_form(
    html: str,
    page_url: str = CLAIM_SEARCH_URL,
) -> ClaimFormState:
    """Discover the current estate-claim form contract."""

    safe_url = _official_url(CLAIM_SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or CLAIM_SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    radio_semantics = {"role", "linked", "migrated"}
    field_names = {
        semantic: _field_name(
            form,
            element_id,
            url=safe_url,
            radio_group=(semantic in radio_semantics),
        )
        for semantic, element_id in CLAIM_EXPECTED_FORM_IDS.items()
    }
    selects: dict[str, Tag] = {}
    for semantic, element_id in (
        ("county", "cboCountyId"),
        ("claim_type", "cboType"),
        ("claim_status", "cboStatus"),
    ):
        node = form.select_one(f"#{element_id}")
        if not isinstance(node, Tag):
            raise MarylandEstateSupplementSourceChangedError(
                f"Maryland claim selector {element_id} is missing",
                url=safe_url,
            )
        selects[semantic] = node
    counties = _option_values(selects["county"])
    if len({value for value in counties.values() if value}) != 24:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim county selector no longer exposes 24 jurisdictions",
            url=safe_url,
        )
    roles = _radio_values(
        form,
        "rblSearchNameBy",
        {
            "decedent": "Decedent",
            "claimant": "Filed By",
            "filed by": "Filed By",
            "filed_by": "Filed By",
        },
        url=safe_url,
    )
    linked = _radio_values(
        form,
        "rblLinkedToEstate",
        {"yes": "yes", "no": "no"},
        url=safe_url,
    )
    migrated = _radio_values(
        form,
        "rblMigratedToEstate",
        {"yes": "yes", "no": "no"},
        url=safe_url,
    )
    types = _option_values(selects["claim_type"])
    statuses = _option_values(selects["claim_status"])
    refresh = _refresh_marker(soup, url=safe_url)
    declared = {
        "field_names": field_names,
        "county_values": sorted(set(counties.values())),
        "role_values": sorted(set(roles.values())),
        "type_values": sorted(set(types.values())),
        "status_values": sorted(set(statuses.values())),
        "linked_values": sorted(set(linked.values())),
        "migrated_values": sorted(set(migrated.values())),
        "hidden_fields": sorted(hidden),
    }
    return ClaimFormState(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        field_names=field_names,
        county_values=counties,
        role_values=roles,
        type_values=types,
        status_values=statuses,
        linked_values=linked,
        migrated_values=migrated,
        refresh=refresh,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def _claim_effective_parameters(form: Tag) -> dict[str, Any]:
    return {
        "role": _checked_value(form, "rblSearchNameBy"),
        "last_name": _clean(_input_value(form, "txtLN")),
        "exact_last_name": (
            form.select_one("#chkExactMatchLastName[checked]") is not None
        ),
        "first_name": _clean(_input_value(form, "txtFN")),
        "middle_name": _clean(_input_value(form, "txtMN")),
        "surname": _clean(_input_value(form, "txtSN")),
        "corporation": _clean(_input_value(form, "txtCorpName")),
        "estate_number": _clean(_input_value(form, "txtEstateNo")),
        "filed_date_raw": _clean(_input_value(form, "txtDOF")),
        "county_value": _selected_value(form, "cboCountyId"),
        "claim_type": _selected_value(form, "cboType"),
        "claim_status": _selected_value(form, "cboStatus"),
        "linked_to_estate": _clean(
            _checked_value(form, "rblLinkedToEstate")
        ),
        "migrated_to_estate": _clean(
            _checked_value(form, "rblMigratedToEstate")
        ),
    }


def _county_label(value: str) -> str:
    cleaned = _clean(value) or ""
    if cleaned == "Baltimore City" or cleaned.endswith(" County"):
        return cleaned
    return f"{cleaned} County"


def _claim_locator(
    href: str,
    *,
    page_url: str,
) -> tuple[str, str, str]:
    detail_url = _official_url(page_url, href)
    values = parse_qs(urlsplit(detail_url).query)
    record_id = _clean((values.get("RecordId") or [None])[0])
    partition = _clean((values.get("src") or [None])[0])
    if not record_id or not CLAIM_RECORD_ID_RE.fullmatch(record_id):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim link lacks a numeric RecordId",
            url=detail_url,
        )
    if not partition:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim link lacks its source partition",
            url=detail_url,
        )
    return record_id, partition, detail_url


def parse_claim_results_page(
    html: str,
    page_url: str = CLAIM_SEARCH_URL,
    *,
    effective_parameters: Mapping[str, Any] | None = None,
) -> ClaimResultsPage:
    """Parse one claim result page and its dynamic postback targets."""

    safe_url = _official_url(CLAIM_SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or CLAIM_SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    refresh = _refresh_marker(soup, url=safe_url)
    effective = (
        dict(effective_parameters)
        if effective_parameters is not None
        else _claim_effective_parameters(form)
    )
    page_state = _page_status(soup, url=safe_url)
    if page_state is None:
        marker = sha256_fingerprint(
            {
                "refresh": refresh.raw,
                "effective": effective,
                "total": 0,
                "empty": True,
            }
        )
        return ClaimResultsPage(
            html=html,
            url=safe_url,
            action_url=action_url,
            hidden_fields=hidden,
            current_page=1,
            total_pages=0,
            total_count=0,
            rows=(),
            page_targets={},
            forward_target=None,
            refresh=refresh,
            effective_parameters=effective,
            snapshot_marker=marker,
            schema_fingerprint=sha256_fingerprint(
                {
                    "headers": CLAIM_RESULT_HEADERS,
                    "valid_empty": True,
                }
            ),
        )
    current_page, total_pages, total_count = page_state
    _validate_page_count(total_pages, total_count, url=safe_url)
    table = soup.select_one("#dgSearchResults")
    if not isinstance(table, Tag):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim result table is missing",
            url=safe_url,
        )
    header_seen = False
    rows: list[ClaimRow] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        values = tuple(_clean(cell) or "" for cell in cells)
        if values == CLAIM_RESULT_HEADERS:
            header_seen = True
            continue
        link = row.select_one("a[href*='RecordId']")
        if link is None:
            continue
        if len(cells) != len(CLAIM_RESULT_HEADERS):
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland claim result row width changed",
                url=safe_url,
            )
        record_id, partition, detail_url = _claim_locator(
            str(link.get("href") or ""),
            page_url=safe_url,
        )
        county, filed, status, estate_number, decedent, corporation = values
        if not county or not filed or not status or not decedent:
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland claim result row is missing identity fields",
                url=safe_url,
                details={"record_id": record_id},
            )
        rows.append(
            ClaimRow(
                county=_county_label(county),
                filed_date_raw=filed,
                claim_status=status,
                estate_number=estate_number or None,
                decedent_name=decedent,
                corporation_name=corporation or None,
                record_id=record_id,
                source_partition=partition,
                detail_url=detail_url,
                source_page=current_page,
            )
        )
    if not header_seen:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim result columns changed",
            url=safe_url,
            details={"expected_headers": list(CLAIM_RESULT_HEADERS)},
        )
    if not rows:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim result page contains no claim rows",
            url=safe_url,
        )
    page_targets, forward = _pager(
        table, current_page=current_page, url=safe_url
    )
    declared = {
        "headers": CLAIM_RESULT_HEADERS,
        "record_fields": list(ClaimRow.__dataclass_fields__),
        "pager": "aspnet_gridview_dynamic_postback",
        "detail_locator": ["src", "RecordId"],
    }
    marker = sha256_fingerprint(
        {
            "refresh": refresh.raw,
            "total": total_count,
            "effective": effective,
            "first_record_id": rows[0].record_id if current_page == 1 else None,
            "last_record_id": rows[-1].record_id if current_page == 1 else None,
        }
    )
    return ClaimResultsPage(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        current_page=current_page,
        total_pages=total_pages,
        total_count=total_count,
        rows=tuple(rows),
        page_targets=page_targets,
        forward_target=forward,
        refresh=refresh,
        effective_parameters=effective,
        snapshot_marker=marker,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def parse_claim_detail(
    html: str,
    page_url: str,
    *,
    expected_record_id: str | None = None,
    expected_partition: str | None = None,
) -> ClaimDetail:
    """Parse one exact claim detail while preserving person and organization."""

    safe_url = _official_url(CLAIM_DETAIL_URL, page_url)
    query = parse_qs(urlsplit(safe_url).query)
    record_id = _clean((query.get("RecordId") or [None])[0])
    partition = _clean((query.get("src") or [None])[0])
    if (
        not record_id
        or not CLAIM_RECORD_ID_RE.fullmatch(record_id)
        or not partition
    ):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim detail URL lacks its source identity",
            url=safe_url,
        )
    if expected_record_id and record_id != expected_record_id:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim detail RecordId does not match the requested record",
            url=safe_url,
        )
    if expected_partition and partition != expected_partition:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim detail partition does not match the requested record",
            url=safe_url,
        )
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblClaimData")
    if not isinstance(table, Tag):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim detail table is missing",
            url=safe_url,
        )
    refresh = _refresh_marker(soup, url=safe_url)
    heading = _clean(soup.select_one(".RECORDHEADER")) or ""
    county_match = re.search(r"\((?P<county>[^)]+)\)", heading)
    county = (
        _county_label(county_match.group("county"))
        if county_match
        else None
    )
    fields = {
        "filed_date_raw": _clean(soup.select_one("#lblFileDate")),
        "estate_number": _clean(soup.select_one("#lblEstateNumber")),
        "decedent_name": _clean(soup.select_one("#lblDecedent")),
        "claimant_organization_name": _clean(soup.select_one("#lblCorp")),
        "claimant_phone": _clean(soup.select_one("#lblPhone")),
        "claimant_person_name": _clean(soup.select_one("#lblClaimant")),
        "claim_amount_raw": _clean(soup.select_one("#lblAMT")),
        "claim_type": _clean(soup.select_one("#lblType")),
        "claim_status": _clean(soup.select_one("#lblStatus")),
        "remarks": _clean(soup.select_one("#lblRemarks")),
    }
    required = (
        fields["filed_date_raw"],
        fields["decedent_name"],
        fields["claim_type"],
        fields["claim_status"],
    )
    if not county or any(value is None for value in required):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim detail identity fields changed",
            url=safe_url,
            details={"record_id": record_id},
        )
    declared = {
        "table_id": "tblClaimData",
        "field_ids": [
            "lblFileDate",
            "lblEstateNumber",
            "lblDecedent",
            "lblCorp",
            "lblPhone",
            "lblClaimant",
            "lblAMT",
            "lblType",
            "lblStatus",
            "lblRemarks",
        ],
    }
    return ClaimDetail(
        record={
            "record_id": record_id,
            "source_partition": partition,
            "county": county,
            **fields,
        },
        url=safe_url,
        refresh=refresh,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def _extract_notice_fields(text: str) -> dict[str, Any]:
    estate_match = re.search(
        r"\bESTATE\s+NO\.?\s+(?P<number>[A-Z0-9-]+)",
        text,
        re.I,
    )
    decedent_match = re.search(
        r"(?:IN\s+THE\s+ESTATE\s+OF|ESTATE\s+OF)\s+"
        r"(?P<name>.+?)\s+ESTATE\s+NO\.?",
        text,
        re.I,
    )
    representative_match = re.search(
        r"NOTICE\s+IS\s+GIVEN\s+THAT:\s*(?P<value>.+?)\s+"
        r"WAS\s+ON\s+.+?\s+APPOINTED\s+PERSONAL\s+REPRESENTATIVE",
        text,
        re.I,
    )
    petitioner_match = re.search(
        r"(?:PETITION|PETITION\s+TO\s+CAVEAT).{0,80}?"
        r"(?:FILED\s+BY|HAS\s+BEEN\s+FILED\s+BY)\s+"
        r"(?P<value>.+?)\s+(?:FOR|CHALLENGING)",
        text,
        re.I,
    )
    death_match = re.search(
        r"WHO\s+DIED\s+ON\s+(?P<date>.+?)\s+"
        r"(?:WITH|WITHOUT)\s+A\s+WILL",
        text,
        re.I,
    )
    hearing_match = re.search(
        r"A\s+HEARING\s+WILL\s+BE\s+HELD\s+AT\s+"
        r"(?P<value>.+?)(?:\.\s|$)",
        text,
        re.I,
    )
    decedent_display = _clean(
        decedent_match.group("name") if decedent_match else None
    )
    decedent_name = decedent_display
    aliases: list[str] = []
    if decedent_display:
        alias_parts = re.split(r"\s+AKA:?\s+", decedent_display, flags=re.I)
        decedent_name = _clean(alias_parts[0])
        aliases = [
            alias
            for value in alias_parts[1:]
            for fragment in value.split(",")
            for alias in [_clean(fragment)]
            if alias
        ]
    return {
        "estate_number": _clean(
            estate_match.group("number") if estate_match else None
        ),
        "decedent_name": decedent_name,
        "decedent_display": decedent_display,
        "decedent_aliases": aliases,
        "personal_representative_text": _clean(
            representative_match.group("value")
            if representative_match
            else None
        ),
        "petitioner_text": _clean(
            petitioner_match.group("value") if petitioner_match else None
        ),
        "date_of_death_raw": _clean(
            death_match.group("date") if death_match else None
        ),
        "hearing_text": _clean(
            hearing_match.group("value") if hearing_match else None
        ),
    }


def _notice_variant(title: str | None) -> str | None:
    cleaned = _clean(title)
    if not cleaned:
        return None
    value = re.sub(r"[^a-z0-9]+", "_", cleaned.casefold()).strip("_")
    return value or None


def normalize_notice_row(
    row: NoticeRow,
    *,
    page: NoticeResultsPage,
) -> dict[str, Any]:
    extracted = _extract_notice_fields(row.full_notice_text)
    canonical_ref = (
        f"STATECOURT:{NOTICE_SOURCE_ID}/notice/{quote(row.notice_id, safe='')}"
    )
    return {
        "source_id": NOTICE_SOURCE_ID,
        "record_identity_source_id": NOTICE_SOURCE_ID,
        "record_kind": "estate_legal_notice",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_internal_id": row.notice_id,
        "notice_id": row.notice_id,
        "occurrence_identity": {
            "source_id": NOTICE_SOURCE_ID,
            "notice_id": row.notice_id,
        },
        "county": row.county,
        "publication_date": _parse_date(row.publication_date_raw),
        "publication_date_raw": row.publication_date_raw,
        "notice_title": row.notice_title,
        "notice_variant": _notice_variant(row.notice_title),
        "full_notice_text": row.full_notice_text,
        "full_notice_html": row.full_notice_html,
        **extracted,
        "date_of_death": _parse_date(extracted["date_of_death_raw"]),
        "source_page": row.source_page,
        "source_url": NOTICE_SEARCH_URL,
        "source_result_marker": page.snapshot_marker,
        "response_schema_fingerprint": page.schema_fingerprint,
        "estate_join": {
            "county": row.county,
            "estate_number": extracted["estate_number"],
            "decedent_name": extracted["decedent_name"],
            "personal_representative_text": extracted[
                "personal_representative_text"
            ],
        },
        "interpretation": {
            "source_grain": "published_notice_occurrence",
            "not_final_docket_or_legal_status": True,
        },
    }


def _claim_amount(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    numeric = re.sub(r"[^0-9.-]", "", cleaned)
    return numeric or None


def normalize_claim_row(
    row: ClaimRow,
    *,
    criteria: ClaimCriteria,
    page: ClaimResultsPage,
    detail: ClaimDetail,
) -> dict[str, Any]:
    values = dict(detail.record)
    if (
        values.get("record_id") != row.record_id
        or values.get("source_partition") != row.source_partition
    ):
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland claim result and detail identities differ",
            url=detail.url,
        )
    for field_name, summary_value, detail_value in (
        ("county", row.county, values.get("county")),
        ("claim_status", row.claim_status, values.get("claim_status")),
        ("decedent_name", row.decedent_name, values.get("decedent_name")),
    ):
        if _clean(summary_value) != _clean(detail_value):
            raise MarylandEstateSupplementSourceChangedError(
                f"Maryland claim {field_name} differs between result and detail",
                url=detail.url,
                details={"record_id": row.record_id},
            )
    canonical_ref = (
        f"STATECOURT:{CLAIM_SOURCE_ID}/claim/"
        f"{quote(row.source_partition, safe='')}/{quote(row.record_id, safe='')}"
    )
    organization = _clean(values.get("claimant_organization_name"))
    person = _clean(values.get("claimant_person_name"))
    estate_number = _clean(values.get("estate_number"))
    if criteria.linked_to_estate is not None:
        linked = criteria.linked_to_estate
        linked_basis = "source_query_filter"
    else:
        linked = None
        linked_basis = "not_published"
    migrated = criteria.migrated_to_estate
    migrated_basis = (
        "source_query_filter" if migrated is not None else "not_published"
    )
    entity_types = []
    if person:
        entity_types.append("person")
    if organization:
        entity_types.append("organization")
    return {
        "source_id": CLAIM_SOURCE_ID,
        "record_identity_source_id": CLAIM_SOURCE_ID,
        "record_kind": "estate_claim_index_entry",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_internal_id": row.record_id,
        "record_id": row.record_id,
        "source_partition": row.source_partition,
        "claim_identity": {
            "source_id": CLAIM_SOURCE_ID,
            "source_partition": row.source_partition,
            "record_id": row.record_id,
        },
        "county": row.county,
        "estate_number": estate_number,
        "decedent_name": _clean(values.get("decedent_name")),
        "filed_date": _parse_date(_clean(values.get("filed_date_raw"))),
        "filed_date_raw": _clean(values.get("filed_date_raw")),
        "claimant_person_name": person,
        "claimant_organization_name": organization,
        "claimant_entity_types": entity_types,
        "claimant_phone": _clean(values.get("claimant_phone")),
        "claim_amount": _claim_amount(_clean(values.get("claim_amount_raw"))),
        "claim_amount_raw": _clean(values.get("claim_amount_raw")),
        "claim_type": _clean(values.get("claim_type")),
        "claim_status": _clean(values.get("claim_status")),
        "source_reported_claim_status": _clean(values.get("claim_status")),
        "remarks": _clean(values.get("remarks")),
        "linked_to_estate": linked,
        "linked_to_estate_basis": linked_basis,
        "migrated_to_estate": migrated,
        "migrated_to_estate_basis": migrated_basis,
        "queried_role": criteria.role,
        "source_latest_data_raw": detail.refresh.raw,
        "source_latest_data_at": detail.refresh.timestamp,
        "application_instance": detail.refresh.instance,
        "source_page": row.source_page,
        "source_url": detail.url,
        "source_result_marker": page.snapshot_marker,
        "response_schema_fingerprint": sha256_fingerprint(
            {
                "result": page.schema_fingerprint,
                "detail": detail.schema_fingerprint,
            }
        ),
        "estate_join": {
            "county": row.county,
            "estate_number": estate_number,
            "decedent_name": _clean(values.get("decedent_name")),
        },
        "interpretation": {
            "source_grain": "filed_claim_occurrence",
            "filing_is_not_allowance_or_adjudication": True,
            "status_basis": "source_reported_claim_status",
        },
    }


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": state.source_id,
        "criteria": state.effective_criteria_fingerprint,
        "schema": state.schema_fingerprint,
        "snapshot": state.snapshot_marker,
        "total": state.total_count,
        "pages": state.total_pages,
        "page": state.page_number,
        "offset": state.row_offset,
        "emitted": state.emitted_count,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode()
    ).decode().rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(value: str) -> CursorState:
    if not value.startswith(CURSOR_PREFIX):
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor format is invalid"
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        padded = token + ("=" * (-len(token) % 4))
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode()).decode()
        )
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor could not be decoded"
        ) from exc
    required = {
        "v",
        "source",
        "criteria",
        "schema",
        "snapshot",
        "total",
        "pages",
        "page",
        "offset",
        "emitted",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor payload is invalid"
        )
    if payload["v"] != CURSOR_VERSION:
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor version is unsupported"
        )
    try:
        state = CursorState(
            source_id=str(payload["source"]),
            effective_criteria_fingerprint=str(payload["criteria"]),
            schema_fingerprint=str(payload["schema"]),
            snapshot_marker=str(payload["snapshot"]),
            total_count=int(payload["total"]),
            total_pages=int(payload["pages"]),
            page_number=int(payload["page"]),
            row_offset=int(payload["offset"]),
            emitted_count=int(payload["emitted"]),
        )
    except (TypeError, ValueError) as exc:
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor values are invalid"
        ) from exc
    expected_emitted = (
        (state.page_number - 1) * NATIVE_PAGE_SIZE + state.row_offset
    )
    if (
        state.source_id not in SOURCE_IDS
        or state.total_count < 1
        or state.total_pages < 1
        or state.page_number < 1
        or state.page_number > state.total_pages
        or state.row_offset < 0
        or state.row_offset >= NATIVE_PAGE_SIZE
        or state.emitted_count < 0
        or state.emitted_count >= state.total_count
        or state.emitted_count != expected_emitted
    ):
        raise MarylandEstateSupplementCursorError(
            "Continuation cursor position is invalid"
        )
    return state


class MarylandEstateSupplementClient:
    """Stateful client for the two official ASP.NET applications."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self._owns_session = session is None
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    data=dict(data) if data is not None else None,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 429:
                raise MarylandEstateSupplementRateLimitedError(
                    "Maryland Register of Wills returned HTTP 429",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise MarylandEstateSupplementRestrictedError(
                    f"Maryland Register of Wills returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code in self.retry_policy.retry_statuses:
                last_error = MarylandEstateSupplementTransportError(
                    f"Maryland Register of Wills returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code >= 400:
                raise MarylandEstateSupplementTransportError(
                    f"Maryland Register of Wills returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
            return response
        if isinstance(last_error, MarylandEstateSupplementError):
            raise last_error
        raise MarylandEstateSupplementTransportError(
            "Could not reach the Maryland Register of Wills source",
            url=url,
            details={"reason": str(last_error or "request failed")},
        ) from last_error

    @staticmethod
    def _text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text is not None:
            return str(text)
        return bytes(response.content).decode("utf-8", errors="replace")

    @staticmethod
    def _url(response: Any, fallback: str) -> str:
        return str(getattr(response, "url", None) or fallback)

    def search_notices(
        self,
        criteria: NoticeCriteria,
    ) -> NoticeResultsPage:
        response = self._request("GET", NOTICE_SEARCH_URL)
        html = self._text(response)
        response_url = self._url(response, NOTICE_SEARCH_URL)
        form = parse_notice_form(html, response_url)
        if not criteria.has_overrides:
            return parse_notice_results_page(html, response_url)
        response = self._request(
            "POST",
            form.action_url,
            data=criteria.form_data(form),
        )
        return parse_notice_results_page(
            self._text(response),
            self._url(response, form.action_url),
        )

    def postback_notices(
        self,
        page: NoticeResultsPage,
        target: str,
    ) -> NoticeResultsPage:
        data = dict(page.hidden_fields)
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = ""
        response = self._request("POST", page.action_url, data=data)
        return parse_notice_results_page(
            self._text(response),
            self._url(response, page.action_url),
        )

    def search_claims(
        self,
        criteria: ClaimCriteria,
    ) -> ClaimResultsPage:
        response = self._request("GET", CLAIM_SEARCH_URL)
        form = parse_claim_form(
            self._text(response),
            self._url(response, CLAIM_SEARCH_URL),
        )
        response = self._request(
            "POST",
            form.action_url,
            data=criteria.form_data(form),
        )
        return parse_claim_results_page(
            self._text(response),
            self._url(response, form.action_url),
            effective_parameters=criteria.parameters(),
        )

    def postback_claims(
        self,
        page: ClaimResultsPage,
        target: str,
    ) -> ClaimResultsPage:
        data = dict(page.hidden_fields)
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = ""
        response = self._request("POST", page.action_url, data=data)
        return parse_claim_results_page(
            self._text(response),
            self._url(response, page.action_url),
            effective_parameters=page.effective_parameters,
        )

    def claim_detail(
        self,
        record_id: str,
        source_partition: str = "row",
    ) -> ClaimDetail:
        wanted = _clean(record_id)
        partition = _clean(source_partition)
        if not wanted or not CLAIM_RECORD_ID_RE.fullmatch(wanted):
            raise MarylandEstateSupplementSelectionError(
                "Maryland claim RecordId must contain only digits"
            )
        if not partition or not re.fullmatch(r"[A-Za-z0-9_-]+", partition):
            raise MarylandEstateSupplementSelectionError(
                "Maryland claim source partition is invalid"
            )
        url = (
            f"{CLAIM_DETAIL_URL}?"
            f"{urlencode({'src': partition, 'RecordId': wanted})}"
        )
        response = self._request("GET", url)
        return parse_claim_detail(
            self._text(response),
            self._url(response, url),
            expected_record_id=wanted,
            expected_partition=partition,
        )


def _effective_fingerprint(page: Any) -> str:
    return sha256_fingerprint(dict(page.effective_parameters))


def _same_snapshot(
    page: Any,
    first: Any,
    *,
    source_id: str,
    cursor: CursorState | None = None,
) -> None:
    if page.schema_fingerprint != first.schema_fingerprint:
        raise MarylandEstateSupplementSourceChangedError(
            "Maryland estate supplement schema changed during traversal",
            url=page.url,
        )
    if (
        page.total_count != first.total_count
        or page.total_pages != first.total_pages
    ):
        raise MarylandEstateSupplementCursorError(
            "Maryland estate supplement result count changed during traversal",
            url=page.url,
        )
    if _effective_fingerprint(page) != _effective_fingerprint(first):
        raise MarylandEstateSupplementCursorError(
            "Maryland estate supplement effective query changed during traversal",
            url=page.url,
        )
    if source_id == CLAIM_SOURCE_ID and page.refresh.raw != first.refresh.raw:
        raise MarylandEstateSupplementCursorError(
            "Maryland claim data refreshed during traversal",
            url=page.url,
        )
    if cursor is not None:
        if cursor.source_id != source_id:
            raise MarylandEstateSupplementCursorError(
                "Continuation cursor belongs to a different Maryland source"
            )
        if cursor.schema_fingerprint != first.schema_fingerprint:
            raise MarylandEstateSupplementCursorError(
                "Maryland estate supplement schema changed since cursor issuance"
            )
        if cursor.snapshot_marker != first.snapshot_marker:
            raise MarylandEstateSupplementCursorError(
                "Maryland estate supplement result snapshot changed since cursor issuance"
            )
        if (
            cursor.total_count != first.total_count
            or cursor.total_pages != first.total_pages
        ):
            raise MarylandEstateSupplementCursorError(
                "Maryland estate supplement result count changed since cursor issuance"
            )
        if (
            cursor.effective_criteria_fingerprint
            != _effective_fingerprint(first)
        ):
            raise MarylandEstateSupplementCursorError(
                "Maryland estate supplement effective query changed since cursor issuance"
            )


def _navigate(
    client: MarylandEstateSupplementClient | Any,
    first: Any,
    target_page: int,
    *,
    source_id: str,
) -> tuple[Any, list[str]]:
    current = first
    artifacts = [first.url]
    method_name = (
        "postback_notices"
        if source_id == NOTICE_SOURCE_ID
        else "postback_claims"
    )
    while current.current_page < target_page:
        target = current.page_targets.get(target_page)
        visible_max = max(
            current.page_targets,
            default=current.current_page,
        )
        if (
            target is None
            and target_page > visible_max
            and current.forward_target is not None
        ):
            target = current.forward_target
        if target is None:
            target = current.page_targets.get(current.current_page + 1)
        if target is None:
            target = current.forward_target
        if target is None:
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland estate supplement pager cannot reach requested page",
                url=current.url,
                details={
                    "current_page": current.current_page,
                    "target_page": target_page,
                    "visible_pages": sorted(current.page_targets),
                },
            )
        next_page = getattr(client, method_name)(current, target)
        _same_snapshot(next_page, first, source_id=source_id)
        if (
            next_page.current_page <= current.current_page
            or next_page.current_page > target_page
        ):
            raise MarylandEstateSupplementSourceChangedError(
                "Maryland estate supplement pager advanced unexpectedly",
                url=next_page.url,
            )
        current = next_page
        artifacts.append(current.url)
    return current, artifacts


def _cursor_for_position(
    *,
    source_id: str,
    first: Any,
    emitted_count: int,
) -> str:
    page_number = (emitted_count // NATIVE_PAGE_SIZE) + 1
    row_offset = emitted_count % NATIVE_PAGE_SIZE
    return _encode_cursor(
        CursorState(
            source_id=source_id,
            effective_criteria_fingerprint=_effective_fingerprint(first),
            schema_fingerprint=first.schema_fingerprint,
            snapshot_marker=first.snapshot_marker,
            total_count=first.total_count,
            total_pages=first.total_pages,
            page_number=page_number,
            row_offset=row_offset,
            emitted_count=emitted_count,
        )
    )


def _run_notice_search(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    criteria: NoticeCriteria,
    client: MarylandEstateSupplementClient | Any,
    *,
    retrieved_at: str,
) -> PublicRecordsResult:
    first = client.search_notices(criteria)
    if first.total_count == 0:
        if args.cursor:
            raise MarylandEstateSupplementCursorError(
                "Continuation cursor no longer points to matching notices"
            )
        return PublicRecordsResult.success(
            query,
            [],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[first.url],
            warnings=NOTICE_WARNINGS,
        )
    cursor = _decode_cursor(args.cursor) if args.cursor else None
    if cursor:
        _same_snapshot(
            first,
            first,
            source_id=NOTICE_SOURCE_ID,
            cursor=cursor,
        )
        page_number = cursor.page_number
        row_offset = cursor.row_offset
        emitted_before = cursor.emitted_count
    else:
        page_number = 1
        row_offset = 0
        emitted_before = 0
    current, artifacts = _navigate(
        client,
        first,
        page_number,
        source_id=NOTICE_SOURCE_ID,
    )
    remaining = first.total_count - emitted_before
    wanted = remaining if args.limit is None else min(args.limit, remaining)
    records: list[dict[str, Any]] = []
    while len(records) < wanted:
        available = current.rows[row_offset:]
        take = min(len(available), wanted - len(records))
        records.extend(
            normalize_notice_row(row, page=first)
            for row in available[:take]
        )
        row_offset += take
        if len(records) >= wanted:
            break
        if row_offset < len(current.rows):
            continue
        next_page_number = current.current_page + 1
        current, page_artifacts = _navigate(
            client,
            current,
            next_page_number,
            source_id=NOTICE_SOURCE_ID,
        )
        _same_snapshot(current, first, source_id=NOTICE_SOURCE_ID)
        artifacts.extend(page_artifacts[1:])
        row_offset = 0
    emitted_after = emitted_before + len(records)
    next_cursor = (
        _cursor_for_position(
            source_id=NOTICE_SOURCE_ID,
            first=first,
            emitted_count=emitted_after,
        )
        if emitted_after < first.total_count
        else None
    )
    return _search_result(
        query,
        records,
        source_total=first.total_count,
        emitted_through=emitted_after,
        retrieved_at=retrieved_at,
        raw_artifact_refs=list(dict.fromkeys(artifacts)),
        next_cursor=next_cursor,
        warnings=NOTICE_WARNINGS,
    )


def _run_claim_search(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    criteria: ClaimCriteria,
    client: MarylandEstateSupplementClient | Any,
    *,
    retrieved_at: str,
) -> PublicRecordsResult:
    first = client.search_claims(criteria)
    if first.total_count == 0:
        if args.cursor:
            raise MarylandEstateSupplementCursorError(
                "Continuation cursor no longer points to matching claims"
            )
        return PublicRecordsResult.success(
            query,
            [],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[first.url],
            warnings=CLAIM_WARNINGS,
        )
    cursor = _decode_cursor(args.cursor) if args.cursor else None
    if cursor:
        _same_snapshot(
            first,
            first,
            source_id=CLAIM_SOURCE_ID,
            cursor=cursor,
        )
        page_number = cursor.page_number
        row_offset = cursor.row_offset
        emitted_before = cursor.emitted_count
    else:
        page_number = 1
        row_offset = 0
        emitted_before = 0
    current, artifacts = _navigate(
        client,
        first,
        page_number,
        source_id=CLAIM_SOURCE_ID,
    )
    remaining = first.total_count - emitted_before
    wanted = remaining if args.limit is None else min(args.limit, remaining)
    records: list[dict[str, Any]] = []
    while len(records) < wanted:
        available = current.rows[row_offset:]
        take = min(len(available), wanted - len(records))
        for row in available[:take]:
            detail = client.claim_detail(
                row.record_id,
                row.source_partition,
            )
            if detail.refresh.raw != first.refresh.raw:
                raise MarylandEstateSupplementCursorError(
                    "Maryland claim data refreshed between search and detail",
                    url=detail.url,
                )
            records.append(
                normalize_claim_row(
                    row,
                    criteria=criteria,
                    page=first,
                    detail=detail,
                )
            )
            artifacts.append(detail.url)
        row_offset += take
        if len(records) >= wanted:
            break
        if row_offset < len(current.rows):
            continue
        next_page_number = current.current_page + 1
        current, page_artifacts = _navigate(
            client,
            current,
            next_page_number,
            source_id=CLAIM_SOURCE_ID,
        )
        _same_snapshot(current, first, source_id=CLAIM_SOURCE_ID)
        artifacts.extend(page_artifacts[1:])
        row_offset = 0
    emitted_after = emitted_before + len(records)
    next_cursor = (
        _cursor_for_position(
            source_id=CLAIM_SOURCE_ID,
            first=first,
            emitted_count=emitted_after,
        )
        if emitted_after < first.total_count
        else None
    )
    return _search_result(
        query,
        records,
        source_total=first.total_count,
        emitted_through=emitted_after,
        retrieved_at=retrieved_at,
        raw_artifact_refs=list(dict.fromkeys(artifacts)),
        next_cursor=next_cursor,
        warnings=CLAIM_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    records: list[dict[str, Any]],
    *,
    source_total: int,
    emitted_through: int,
    retrieved_at: str,
    raw_artifact_refs: list[str],
    next_cursor: str | None,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    """An explicit caller limit leaves incomplete source coverage to resume."""
    if next_cursor:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [PublicRecordsError(
                code="caller_result_limit",
                message=(
                    "More source rows are available; continue with the "
                    "returned snapshot-bound cursor."
                ),
                category="pagination",
                retryable=False,
                details={
                    "source_total": source_total,
                    "emitted_through": emitted_through,
                },
            )],
            records=records,
            next_cursor=next_cursor,
            retrieved_at=retrieved_at,
            raw_artifact_refs=raw_artifact_refs,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        raw_artifact_refs=raw_artifact_refs,
        warnings=warnings,
    )


def source_records() -> list[dict[str, Any]]:
    """Return independently attributable manifests and complement routes."""

    return [
        {
            "source_id": NOTICE_SOURCE_ID,
            "record_kind": "source_manifest",
            "name": NOTICE_SOURCE_METADATA.name,
            "url": NOTICE_SEARCH_URL,
            "implemented_operations": ["notices", "probe-notices", "sources"],
            "coverage": {
                "jurisdictions": "all 23 Maryland counties and Baltimore City",
                "record_grain": "published notice occurrence",
                "published_fields": [
                    "notice_id",
                    "county",
                    "publication_date",
                    "notice_title",
                    "full_notice_text",
                    "full_notice_html",
                ],
                "variants": (
                    "source-published title retained without a closed enum, "
                    "including appointment/creditor, small-estate, judicial-"
                    "probate/hearing, caveat, and future source variants"
                ),
            },
            "identity": {
                "notice_occurrence": ["notice_id"],
                "estate_pivot": ["county", "estate_number"],
            },
            "bounds": {
                "native_page_size": NATIVE_PAGE_SIZE,
                "default_query": "source-defined rolling 30-day publication window",
                "caller_limit": "optional; all native pages are traversed by default",
            },
            "complementary_source_ids": [
                route["source_id"]
                for route in RELATED_ROUTES
                if route["source_id"] != NOTICE_SOURCE_ID
            ],
        },
        {
            "source_id": CLAIM_SOURCE_ID,
            "record_kind": "source_manifest",
            "name": CLAIM_SOURCE_METADATA.name,
            "url": CLAIM_SEARCH_URL,
            "detail_url": CLAIM_DETAIL_URL,
            "implemented_operations": [
                "claims",
                "claim-detail",
                "probe-claims",
                "sources",
            ],
            "coverage": {
                "jurisdictions": "all 23 Maryland counties and Baltimore City",
                "record_grain": "filed claim occurrence",
                "published_fields": [
                    "RecordId",
                    "county",
                    "date_filed",
                    "estate_number",
                    "decedent",
                    "claimant_person",
                    "claimant_organization",
                    "amount",
                    "type",
                    "status",
                    "remarks",
                ],
            },
            "identity": {
                "claim_occurrence": ["source_partition", "RecordId"],
                "estate_pivot": ["county", "estate_number"],
            },
            "bounds": {
                "native_page_size": NATIVE_PAGE_SIZE,
                "caller_limit": "optional; all native pages are traversed by default",
                "detail_enrichment": "one exact source detail per emitted claim",
            },
            "complementary_source_ids": [
                route["source_id"]
                for route in RELATED_ROUTES
                if route["source_id"] != CLAIM_SOURCE_ID
            ],
        },
        *[
            {"record_kind": "complementary_source", **dict(route)}
            for route in RELATED_ROUTES
        ],
    ]


def _query(
    source_id: str,
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    metadata = (
        NOTICE_SOURCE_METADATA
        if source_id == NOTICE_SOURCE_ID
        else CLAIM_SOURCE_METADATA
    )
    return PublicRecordsQuery(
        source=metadata,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "ordering": "native source ordering",
                "pagination": "fresh_webforms_replay_and_snapshot_bound_cursor",
            },
        ),
    )


def _source_for_command(command: str) -> str:
    if command in {"notices", "probe-notices", "sources"}:
        return NOTICE_SOURCE_ID
    return CLAIM_SOURCE_ID


def _access_contract(
    args: argparse.Namespace,
    source_id: str,
) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        source_id,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(source_id)


def _new_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> MarylandEstateSupplementClient:
    limits = access_contract.get("limits") or {}
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return MarylandEstateSupplementClient(
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "acquisition_route_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="access",
            retryable=False,
            details=decision,
        )
    else:
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [public_error],
        warnings=warnings,
    )


def _notice_criteria_from_args(args: argparse.Namespace) -> NoticeCriteria:
    return NoticeCriteria(
        county=args.county,
        published_from=args.published_from,
        published_to=args.published_to,
        death_date=args.death_date,
        party_type=args.party_type,
        last_name=args.last_name,
        first_name=args.first_name,
        middle_name=args.middle_name,
        sort=args.sort,
    )


def _claim_criteria_from_args(args: argparse.Namespace) -> ClaimCriteria:
    return ClaimCriteria(
        role=args.role,
        last_name=args.last_name,
        exact_last_name=args.exact_last_name,
        first_name=args.first_name,
        middle_name=args.middle_name,
        surname=args.surname,
        corporation=args.corporation,
        estate_number=args.estate_number,
        filed_date=args.filed_date,
        county=args.county,
        claim_type=args.claim_type,
        claim_status=args.claim_status,
        linked_to_estate=args.linked_to_estate,
        migrated_to_estate=args.migrated_to_estate,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: MarylandEstateSupplementClient | Any | None = None,
    retrieved_at: str | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one notice or claim operation."""

    retrieved_at = retrieved_at or utc_now_iso()
    source_id = _source_for_command(args.command)
    warnings = (
        NOTICE_WARNINGS if source_id == NOTICE_SOURCE_ID else CLAIM_WARNINGS
    )
    if args.command == "sources":
        query = _query(
            NOTICE_SOURCE_ID,
            "sources",
            {"source_ids": list(SOURCE_IDS)},
        )
        records = source_records()
        result = PublicRecordsResult.success(
            query,
            records,
            retrieved_at=retrieved_at,
            raw_artifact_refs=[NOTICE_SEARCH_URL, CLAIM_SEARCH_URL],
            warnings=NOTICE_WARNINGS + CLAIM_WARNINGS,
        )
        if log_results:
            log_search(canonical_json(query.to_dict()), NOTICE_SOURCE_ID, len(records))
        return result

    query = _query(source_id, args.command, {})
    owns_client = False
    try:
        if args.command == "notices":
            criteria = _notice_criteria_from_args(args)
            query = _query(
                source_id,
                "notices",
                criteria.parameters(),
                limit=args.limit,
                cursor=args.cursor,
            )
        elif args.command == "claims":
            criteria = _claim_criteria_from_args(args)
            query = _query(
                source_id,
                "claims",
                criteria.parameters(),
                limit=args.limit,
                cursor=args.cursor,
            )
        elif args.command == "claim-detail":
            record_id = _clean(args.record_id)
            partition = _clean(args.source_partition) or "row"
            query = _query(
                source_id,
                "claim-detail",
                {
                    "record_id": record_id,
                    "source_partition": partition,
                },
            )
        elif args.command == "probe-notices":
            query = _query(source_id, "probe-notices", {})
        elif args.command == "probe-claims":
            query = _query(
                source_id,
                "probe-claims",
                {"last_name": PROBE_CLAIM_LAST_NAME},
                limit=1,
            )
        else:
            raise MarylandEstateSupplementSelectionError(
                f"Unsupported operation: {args.command}"
            )

        contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args, source_id)
        )
        source_client = client or _new_client(args, contract)
        owns_client = client is None

        if args.command == "notices":
            result = _run_notice_search(
                args,
                query,
                criteria,
                source_client,
                retrieved_at=retrieved_at,
            )
        elif args.command == "claims":
            result = _run_claim_search(
                args,
                query,
                criteria,
                source_client,
                retrieved_at=retrieved_at,
            )
        elif args.command == "claim-detail":
            detail = source_client.claim_detail(record_id, partition)
            row = ClaimRow(
                county=str(detail.record["county"]),
                filed_date_raw=str(detail.record["filed_date_raw"]),
                claim_status=str(detail.record["claim_status"]),
                estate_number=_clean(detail.record.get("estate_number")),
                decedent_name=str(detail.record["decedent_name"]),
                corporation_name=_clean(
                    detail.record.get("claimant_organization_name")
                ),
                record_id=str(detail.record["record_id"]),
                source_partition=str(detail.record["source_partition"]),
                detail_url=detail.url,
                source_page=1,
            )
            synthetic_page = ClaimResultsPage(
                html="",
                url=detail.url,
                action_url=CLAIM_SEARCH_URL,
                hidden_fields={},
                current_page=1,
                total_pages=1,
                total_count=1,
                rows=(row,),
                page_targets={},
                forward_target=None,
                refresh=detail.refresh,
                effective_parameters={
                    "record_id": row.record_id,
                    "source_partition": row.source_partition,
                },
                snapshot_marker=sha256_fingerprint(
                    {
                        "record_id": row.record_id,
                        "source_partition": row.source_partition,
                        "refresh": detail.refresh.raw,
                    }
                ),
                schema_fingerprint=detail.schema_fingerprint,
            )
            record = normalize_claim_row(
                row,
                criteria=ClaimCriteria(),
                page=synthetic_page,
                detail=detail,
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                retrieved_at=retrieved_at,
                raw_artifact_refs=[detail.url],
                warnings=CLAIM_WARNINGS,
            )
        elif args.command == "probe-notices":
            first = source_client.search_notices(NoticeCriteria())
            if not first.rows:
                raise MarylandEstateSupplementSourceChangedError(
                    "Maryland notice probe returned no current notices",
                    url=first.url,
                )
            page_two = None
            if first.total_pages > 1:
                target = first.page_targets.get(2) or first.forward_target
                if not target:
                    raise MarylandEstateSupplementSourceChangedError(
                        "Maryland notice probe cannot reach page two",
                        url=first.url,
                    )
                page_two = source_client.postback_notices(first, target)
                _same_snapshot(
                    page_two,
                    first,
                    source_id=NOTICE_SOURCE_ID,
                )
            titles = sorted(
                {
                    title
                    for row in first.rows
                    for title in [row.notice_title]
                    if title
                }
            )
            probe_ref = (
                f"STATECOURT:{NOTICE_SOURCE_ID}/probe/"
                f"{first.schema_fingerprint}"
            )
            probe_record = {
                "source_id": NOTICE_SOURCE_ID,
                "record_kind": "source_probe",
                "canonical_ref": probe_ref,
                "evidence_ref": probe_ref,
                "status": "ok",
                "operation_states": {
                    "default_rolling_search": "available",
                    "full_notice_text": "available",
                    "native_notice_identity": "available",
                    "dynamic_native_pagination": (
                        "available" if page_two else "not_needed"
                    ),
                    "county_publication_death_party_filters": "available",
                },
                "search_result_count": first.total_count,
                "current_page_count": len(first.rows),
                "sample_notice_id": first.rows[0].notice_id,
                "sample_notice_title": first.rows[0].notice_title,
                "observed_notice_titles": titles,
                "effective_parameters": dict(first.effective_parameters),
                "source_result_marker": first.snapshot_marker,
                "result_schema_fingerprint": first.schema_fingerprint,
            }
            refs = [first.url]
            if page_two:
                refs.append(page_two.url)
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                retrieved_at=retrieved_at,
                raw_artifact_refs=refs,
                warnings=NOTICE_WARNINGS,
            )
        else:
            probe_criteria = ClaimCriteria(
                role="decedent",
                last_name=PROBE_CLAIM_LAST_NAME,
            )
            first = source_client.search_claims(probe_criteria)
            if not first.rows:
                raise MarylandEstateSupplementSourceChangedError(
                    "Maryland claim probe returned no sentinel claims",
                    url=first.url,
                )
            page_two = None
            if first.total_pages > 1:
                target = first.page_targets.get(2) or first.forward_target
                if not target:
                    raise MarylandEstateSupplementSourceChangedError(
                        "Maryland claim probe cannot reach page two",
                        url=first.url,
                    )
                page_two = source_client.postback_claims(first, target)
                _same_snapshot(
                    page_two,
                    first,
                    source_id=CLAIM_SOURCE_ID,
                )
            sample = first.rows[0]
            detail = source_client.claim_detail(
                sample.record_id,
                sample.source_partition,
            )
            normalized = normalize_claim_row(
                sample,
                criteria=probe_criteria,
                page=first,
                detail=detail,
            )
            probe_ref = (
                f"STATECOURT:{CLAIM_SOURCE_ID}/probe/"
                f"{first.schema_fingerprint}"
            )
            probe_record = {
                "source_id": CLAIM_SOURCE_ID,
                "record_kind": "source_probe",
                "canonical_ref": probe_ref,
                "evidence_ref": probe_ref,
                "status": "ok",
                "operation_states": {
                    "claimant_and_decedent_roles": "available",
                    "person_and_corporation_fields": "available",
                    "claim_detail": "available",
                    "dynamic_native_pagination": (
                        "available" if page_two else "not_needed"
                    ),
                    "linked_and_migrated_filters": "available",
                },
                "search_result_count": first.total_count,
                "sample_record_id": sample.record_id,
                "sample_source_partition": sample.source_partition,
                "sample_claim_type": normalized["claim_type"],
                "sample_claim_status": normalized["claim_status"],
                "source_latest_data_raw": first.refresh.raw,
                "source_latest_data_at": first.refresh.timestamp,
                "application_instance": first.refresh.instance,
                "source_result_marker": first.snapshot_marker,
                "result_schema_fingerprint": first.schema_fingerprint,
                "detail_schema_fingerprint": detail.schema_fingerprint,
            }
            refs = [first.url, detail.url]
            if page_two:
                refs.insert(1, page_two.url)
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                retrieved_at=retrieved_at,
                raw_artifact_refs=refs,
                warnings=CLAIM_WARNINGS,
            )
    except (CatalogError, AcquisitionUnavailableError) as exc:
        result = _access_failure(query, exc, warnings=warnings)
    except MarylandEstateSupplementError as exc:
        result = PublicRecordsResult.failure(
            query,
            exc.status,
            [exc.to_contract_error()],
            retrieved_at=retrieved_at,
            warnings=warnings,
        )
    finally:
        if owns_client:
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
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def _add_page_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Optional emitted-record limit; omitted traverses all native pages",
    )
    parser.add_argument("--cursor")
    _add_runtime(parser)


def _optional_boolean(
    parser: argparse.ArgumentParser,
    name: str,
    help_text: str,
) -> None:
    parser.add_argument(
        name,
        choices=("yes", "no"),
        help=help_text,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Maryland estate legal notices and filed claims"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    notices = subparsers.add_parser(
        "notices",
        help="Search complete source-published estate notice occurrences",
    )
    notices.add_argument("--county")
    notices.add_argument("--published-from", help="YYYY-MM-DD")
    notices.add_argument("--published-to", help="YYYY-MM-DD")
    notices.add_argument("--death-date", help="Exact death date, YYYY-MM-DD")
    notices.add_argument(
        "--party-type",
        default="decedent",
        help="Decedent or personal representative",
    )
    notices.add_argument("--last-name")
    notices.add_argument("--first-name")
    notices.add_argument("--middle-name")
    notices.add_argument(
        "--sort",
        help="Source sort label or native value",
    )
    _add_page_args(notices)

    claims = subparsers.add_parser(
        "claims",
        help="Search filed claim occurrences and enrich exact details",
    )
    claims.add_argument(
        "--role",
        default="decedent",
        help="Decedent or claimant/filed-by search role",
    )
    claims.add_argument("--last-name")
    claims.add_argument("--exact-last-name", action="store_true")
    claims.add_argument("--first-name")
    claims.add_argument("--middle-name")
    claims.add_argument("--surname")
    claims.add_argument("--corporation")
    claims.add_argument("--estate-number")
    claims.add_argument("--filed-date", help="YYYY-MM-DD")
    claims.add_argument("--county")
    claims.add_argument("--claim-type")
    claims.add_argument("--claim-status")
    _optional_boolean(
        claims,
        "--linked-to-estate",
        "Use the source's linked-to-estate filter",
    )
    _optional_boolean(
        claims,
        "--migrated-to-estate",
        "Use the source's migrated-to-estate filter",
    )
    _add_page_args(claims)

    detail = subparsers.add_parser(
        "claim-detail",
        help="Fetch one exact claim detail by native RecordId",
    )
    detail.add_argument("record_id")
    detail.add_argument("--source-partition", default="row")
    _add_runtime(detail)

    probe_notices = subparsers.add_parser(
        "probe-notices",
        help="Verify notice form, text, identity, and native paging",
    )
    _add_runtime(probe_notices)

    probe_claims = subparsers.add_parser(
        "probe-claims",
        help="Verify claim roles, paging, detail, and freshness marker",
    )
    _add_runtime(probe_claims)

    sources = subparsers.add_parser(
        "sources",
        help="Show both source manifests and their official complements",
    )
    add_output_args(sources)
    return parser


def _normalize_boolean_args(args: argparse.Namespace) -> None:
    for name in ("linked_to_estate", "migrated_to_estate"):
        if not hasattr(args, name):
            continue
        value = getattr(args, name)
        if value == "yes":
            setattr(args, name, True)
        elif value == "no":
            setattr(args, name, False)


def _validate_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    _normalize_boolean_args(args)
    for name in ("timeout", "max_attempts"):
        if hasattr(args, name) and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in ("minimum_interval", "retry_backoff"):
        if hasattr(args, name) and getattr(args, name) < 0:
            parser.error(
                f"--{name.replace('_', '-')} must not be negative"
            )
    if hasattr(args, "limit") and args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Maryland estate supplements {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Maryland estate supplements {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            f"{record.get('notice_id') or record.get('record_id') or record.get('source_id')}"
            f" | {record.get('record_kind')}"
            f" | {record.get('decedent_name') or record.get('name') or ''}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
