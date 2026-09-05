#!/usr/bin/env python3
"""Query Washington State Archives Digital Archives recorded-land indexes.

The Digital Archives aggregates county-auditor recorded-land indexes under
record series 14.  This adapter preserves the archive's title and record
identifiers, native party/date/addition search controls, result paging and
counts, record-detail provenance, and observed document-image state.

Examples:
    uv run python tools/query_washington_digital_archives_land.py sources
    uv run python tools/query_washington_digital_archives_land.py inventory
    uv run python tools/query_washington_digital_archives_land.py metadata \
        --county adams --refresh
    uv run python tools/query_washington_digital_archives_land.py instruments \
        --county adams
    uv run python tools/query_washington_digital_archives_land.py search \
        --county adams --last-name SMITH --start-year 2020 --end-year 2020
    uv run python tools/query_washington_digital_archives_land.py browse \
        --county skamania --limit 50
    uv run python tools/query_washington_digital_archives_land.py detail \
        64742C2528B8C19D43FCC54D20DC97D0
    uv run python tools/query_washington_digital_archives_land.py alternatives
    uv run python tools/query_washington_digital_archives_land.py probe
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass
from html import unescape
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

try:
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
        utc_now_iso,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
except ImportError:
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
        utc_now_iso,
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )


BASE_URL = "https://digitalarchives.wa.gov"
RECORD_SERIES_ID = 14
RECORD_SERIES_NAME = "Land Records"
SOURCE_ID = "us-wa-state-archives-digital-recorded-land"
OUTPUT_SCHEMA_VERSION = "washington-digital-archives-land/1.0"
PROBE_SCHEMA_VERSION = "washington-digital-archives-land-probe/1.0"
CURSOR_PREFIX = "washington-digital-archives-land:v2:"
CURSOR_VERSION = 2
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PAGE_SIZE = 50
NATIVE_PAGE_SIZES = (50, 100, 200)
DEFAULT_USER_AGENT = "Ithildin-Public-Records/1.0"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
INVENTORY_OBSERVED_AT = "2026-07-30"
INVENTORY_RETRIEVED_AT = "2026-07-30T00:00:00Z"
EVIDENCE_LINEAGE = "county_auditor_recorded_instrument_archive"

TITLE_LIST_PATH = f"/Collections/GetTitles?recordSeriesID={RECORD_SERIES_ID}"
TITLE_PATH = "/Collections/TitleInfo/{title_id}"
SEARCH_PATH = "/Collections/Search"
RESULTS_PATH = "/Search/ResultsTable/"
DETAIL_PATH = "/Record/View/{record_id}"
DIGITAL_OBJECT_QUEUE_PATH = "/DigitalObject/QueueStatus"

SORT_COLUMNS: Mapping[str, int] = {
    "last_name": 0,
    "first_name": 1,
    "party_type": 2,
    "document_type": 3,
    "year": 4,
    "county": 5,
    "legal_description": 6,
    "image_exists": 7,
}


@dataclass(frozen=True)
class TitleConfig:
    """One verified county-auditor title in record series 14."""

    key: str
    county: str
    county_geoid: str
    title_id: int
    title: str
    record_count: int
    image_availability: str
    sentinel_record_id: str | None = None
    sentinel_last_name: str | None = None
    sentinel_first_name: str | None = None
    sentinel_year: int | None = None

    @property
    def county_name(self) -> str:
        return f"{self.county} County"

    @property
    def coverage_label(self) -> str | None:
        prefix = f"{self.county} County Auditor, Recorded Land Records"
        suffix = self.title.removeprefix(prefix).lstrip(", ").strip()
        return suffix or None

    @property
    def title_url(self) -> str:
        return urljoin(BASE_URL, TITLE_PATH.format(title_id=self.title_id))

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=self.county_geoid,
            name=f"{self.county_name}, Washington",
            state_code="WA",
            county_fips=self.county_geoid[-3:],
            locality=self.county_name,
            metadata={"state_fips": "53"},
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "stable_id": f"WSDA:LAND:TITLE:{self.title_id}",
            "record_kind": "recorded_land_title",
            "record_series_id": RECORD_SERIES_ID,
            "record_series_name": RECORD_SERIES_NAME,
            "title_id": self.title_id,
            "title": self.title,
            "county_key": self.key,
            "county": self.county_name,
            "county_geoid": self.county_geoid,
            "coverage_label": self.coverage_label,
            "record_count": self.record_count,
            "image_availability": self.image_availability,
            "title_url": self.title_url,
            "evidence_lineage": EVIDENCE_LINEAGE,
            "evidence_scope": (
                "archived county-auditor recorded-instrument index and any "
                "archive-hosted images"
            ),
            "related_property_lineage": (
                "assessor parcel ownership, valuation, and tax records are "
                "separate official representations"
            ),
            "inventory_observed_at": INVENTORY_OBSERVED_AT,
            "provenance": {
                "source_id": SOURCE_ID,
                "source_url": self.title_url,
                "record_series_id": RECORD_SERIES_ID,
                "title_id": self.title_id,
                "retrieved_at": INVENTORY_RETRIEVED_AT,
            },
        }


TITLES = (
    TitleConfig(
        "adams",
        "Adams",
        "53001",
        93,
        "Adams County Auditor, Recorded Land Records, 1988-2026",
        89823,
        "some_images",
        sentinel_record_id="64742C2528B8C19D43FCC54D20DC97D0",
        sentinel_last_name="SMITH",
        sentinel_first_name="AMOS",
        sentinel_year=2020,
    ),
    TitleConfig(
        "benton",
        "Benton",
        "53005",
        1877,
        "Benton County Auditor, Recorded Land Records, 1969-2026",
        1341078,
        "some_images",
    ),
    TitleConfig(
        "chelan",
        "Chelan",
        "53007",
        35,
        "Chelan County Auditor, Recorded Land Records, 1888-2026",
        769202,
        "some_images",
    ),
    TitleConfig(
        "clallam",
        "Clallam",
        "53009",
        1069,
        "Clallam County Auditor, Recorded Land Records, 1985-2024",
        505734,
        "some_images",
    ),
    TitleConfig(
        "clark",
        "Clark",
        "53011",
        1241,
        "Clark County Auditor, Recorded Land Records, 1998-2021",
        2674808,
        "images_not_available",
    ),
    TitleConfig(
        "cowlitz",
        "Cowlitz",
        "53015",
        1285,
        "Cowlitz County Auditor, Recorded Land Records, 1986-2026",
        748090,
        "some_images",
    ),
    TitleConfig(
        "franklin",
        "Franklin",
        "53021",
        197,
        "Franklin County Auditor, Recorded Land Records, 1989-2026",
        532693,
        "some_images",
    ),
    TitleConfig(
        "grays_harbor",
        "Grays Harbor",
        "53027",
        281,
        "Grays Harbor County Auditor, Recorded Land Records, 1981-Present",
        254605,
        "images_not_available",
    ),
    TitleConfig(
        "island",
        "Island",
        "53029",
        2162,
        "Island County Auditor, Recorded Land Records, 2001-2023",
        491862,
        "some_images",
    ),
    TitleConfig(
        "jefferson",
        "Jefferson",
        "53031",
        15,
        "Jefferson County Auditor, Recorded Land Records, 1981-2026",
        546564,
        "some_images",
    ),
    TitleConfig(
        "kitsap",
        "Kitsap",
        "53035",
        248,
        "Kitsap County Auditor, Recorded Land Records, 1987-2007",
        1244515,
        "some_images",
    ),
    TitleConfig(
        "klickitat",
        "Klickitat",
        "53039",
        48,
        "Klickitat County Auditor, Recorded Land Records, 1988-2026",
        140924,
        "some_images",
    ),
    TitleConfig(
        "lewis",
        "Lewis",
        "53041",
        1545,
        "Lewis County Auditor, Recorded Land Records, 1965-2026",
        300821,
        "images_not_available",
    ),
    TitleConfig(
        "mason",
        "Mason",
        "53045",
        56,
        "Mason County Auditor, Recorded Land Records, 1985-2026",
        625352,
        "images_not_available",
    ),
    TitleConfig(
        "okanogan",
        "Okanogan",
        "53047",
        1778,
        "Okanogan County Auditor, Recorded Land Records, 1993-2023",
        285294,
        "images_not_available",
    ),
    TitleConfig(
        "pacific",
        "Pacific",
        "53049",
        64,
        "Pacific County Auditor, Recorded Land Records, 1996-2026",
        187803,
        "images_not_available",
    ),
    TitleConfig(
        "pend_oreille",
        "Pend Oreille",
        "53051",
        1861,
        "Pend Oreille County Auditor, Recorded Land Records, 1996-2026",
        94747,
        "some_images",
    ),
    TitleConfig(
        "pierce",
        "Pierce",
        "53053",
        27,
        "Pierce County Auditor, Recorded Land Records, 1984-2026",
        8054502,
        "images_not_available",
    ),
    TitleConfig(
        "skamania",
        "Skamania",
        "53059",
        1188,
        (
            "Skamania County Auditor, Recorded Land Records, "
            "2008-2013; 2016-Present"
        ),
        14665,
        "some_images",
    ),
    TitleConfig(
        "snohomish",
        "Snohomish",
        "53061",
        2883,
        "Snohomish County Auditor, Recorded Land Records",
        5762575,
        "some_images",
    ),
    TitleConfig(
        "spokane",
        "Spokane",
        "53063",
        4,
        "Spokane County Auditor, Recorded Land Records, 1960-2026",
        4390453,
        "some_images",
    ),
    TitleConfig(
        "thurston",
        "Thurston",
        "53067",
        316,
        "Thurston County Auditor, Recorded Land Records, 1979-2026",
        2123002,
        "some_images",
    ),
    TitleConfig(
        "walla_walla",
        "Walla Walla",
        "53071",
        242,
        "Walla Walla County Auditor, Recorded Land Records, 1986-2026",
        436461,
        "some_images",
    ),
    TitleConfig(
        "whatcom",
        "Whatcom",
        "53073",
        2249,
        "Whatcom County Auditor, Recorded Land Records",
        382718,
        "images_not_available",
    ),
    TitleConfig(
        "whitman",
        "Whitman",
        "53075",
        2107,
        "Whitman County Auditor, Recorded Land Records, 1987-2026",
        233563,
        "some_images",
    ),
    TitleConfig(
        "yakima",
        "Yakima",
        "53077",
        22,
        "Yakima County Auditor, Recorded Land Records, 1993-2008",
        460751,
        "some_images",
    ),
)

TITLES_BY_KEY = {title.key: title for title in TITLES}
TITLES_BY_ID = {title.title_id: title for title in TITLES}


@dataclass(frozen=True)
class RecorderAlternative:
    """Official county recorder path for a county absent from series 14."""

    key: str
    county: str
    county_geoid: str
    authority: str
    landing_url: str
    operation_url: str | None
    platform: str
    operations: tuple[str, ...]
    observed_access_state: str
    notes: tuple[str, ...] = ()
    complementary_sources: tuple[Mapping[str, Any], ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "stable_id": f"WA:RECORDER-ALTERNATIVE:{self.county_geoid}",
            "record_kind": "county_recorder_alternative",
            "county_key": self.key,
            "county": f"{self.county} County",
            "county_geoid": self.county_geoid,
            "authority": self.authority,
            "landing_url": self.landing_url,
            "operation_url": self.operation_url,
            "platform": self.platform,
            "operations": list(self.operations),
            "observed_access_state": self.observed_access_state,
            "notes": list(self.notes),
            "complementary_sources": [
                dict(source) for source in self.complementary_sources
            ],
            "relationship_to_archive": (
                "official county recorder path for a county with no title in "
                "the verified record-series-14 inventory"
            ),
            "evidence_lineage": "county_auditor_recorded_instrument",
            "verified_at": INVENTORY_OBSERVED_AT,
        }


RECORDER_ALTERNATIVES = (
    RecorderAlternative(
        "asotin",
        "Asotin",
        "53003",
        "Asotin County Auditor",
        "https://asotincountywa.gov/547/Digital-Research-Room",
        "http://pras.asotincountywa.gov/digitalresearchroom/",
        "Asotin Digital Research Room",
        ("recorded_document_index_search", "recorded_document_image_retrieval"),
        "county_redirect_verified_portal_probe_timeout",
        notes=(
            "The county landing page currently redirects to the PRAS Digital "
            "Research Room; the downstream body timed out during the bounded probe.",
        ),
    ),
    RecorderAlternative(
        "columbia",
        "Columbia",
        "53013",
        "Columbia County Auditor Recording Department",
        "https://columbiaco.com/580/Obtain-Recorded-Documents",
        "https://www.idocmarket.com/",
        "iDocMarket",
        ("recorded_document_search", "recorded_document_copy_order"),
        "county_link_to_provider_verified",
    ),
    RecorderAlternative(
        "douglas",
        "Douglas",
        "53017",
        "Douglas County Auditor",
        "https://douglascountywa.gov/217/Recording",
        "https://edocs.douglascountywa.gov/AcclaimWeb",
        "Harris AcclaimWeb",
        (
            "simple_search",
            "party_name_search",
            "auditor_file_number_search",
            "document_type_search",
            "record_date_search",
            "legal_description_search",
            "parcel_search",
            "consideration_search",
            "book_page_search",
            "excise_number_search",
            "remarks_search",
        ),
        "portal_home_live_verified",
    ),
    RecorderAlternative(
        "ferry",
        "Ferry",
        "53019",
        "Ferry County Auditor",
        "https://www.ferry-county.com/departments/auditor/recording.php",
        (
            "https://cms5.revize.com/revize/ferry/Document%20Center/"
            "Department/Auditor/Auditor%20Public%20Records/Forms/"
            "Request%20for%20Searches%20or%20Copy%20of%20Public%20Records.pdf"
        ),
        "county search/copy request",
        ("record_search_request", "recorded_document_copy_request"),
        "official_request_form_verified",
        complementary_sources=(
            {
                "kind": "assessor_parcel_search",
                "url": "https://ferrywa-taxsifter.publicaccessnow.com/",
                "relationship": (
                    "parcel, owner, assessment, sale, and tax pivot; separate "
                    "from recorded-instrument evidence"
                ),
            },
        ),
    ),
    RecorderAlternative(
        "garfield",
        "Garfield",
        "53023",
        "Garfield County Auditor",
        "https://www.garfieldcountywa.gov/auditor/page/recording",
        "https://garfieldcountywa-web.tylerhost.net/web/",
        "Tyler Self-Service",
        (
            "official_record_search",
            "party_search",
            "auditor_file_number_search",
            "recorded_document_copy_request",
        ),
        "county_link_to_portal_verified",
    ),
    RecorderAlternative(
        "grant",
        "Grant",
        "53025",
        "Grant County Auditor",
        "https://www.grantcountywa.gov/272/Recording",
        "https://grantcountywa-recorder.tylerhost.net/grantrecorder/web/",
        "Tyler EagleWeb",
        ("recorded_document_index_search", "indexed_record_view"),
        "portal_home_live_verified",
    ),
    RecorderAlternative(
        "king",
        "King",
        "53033",
        "King County Recorder's Office",
        (
            "https://kingcounty.gov/en/dept/executive-services/"
            "certificates-permits-licenses/records-licensing/"
            "recorders-office/records-search"
        ),
        "https://recordsearch.kingcounty.gov/LandmarkWeb",
        "LandmarkWeb",
        (
            "party_name_search",
            "document_type_search",
            "book_page_search",
            "consideration_search",
            "parcel_search",
            "recording_date_search",
            "recording_number_search",
            "legal_description_search",
            "torrens_number_search",
        ),
        "portal_home_live_verified",
        notes=("Online collection begins with most documents recorded 1991-08-01.",),
    ),
    RecorderAlternative(
        "kittitas",
        "Kittitas",
        "53037",
        "Kittitas County Auditor",
        "https://www.co.kittitas.wa.us/auditor/recording.aspx",
        "https://aur.co.kittitas.wa.us/web/",
        "Tyler Self-Service",
        ("official_record_search", "recorded_document_copy_request"),
        "portal_disclaimer_live_verified",
    ),
    RecorderAlternative(
        "lincoln",
        "Lincoln",
        "53043",
        "Lincoln County Auditor",
        "https://www.lincolncountywa.com/325/Recording",
        "https://lincolncountywa-web.tylerhost.net/web",
        "Tyler Self-Service",
        ("official_record_search", "recorded_document_copy_request"),
        "county_link_to_portal_verified",
    ),
    RecorderAlternative(
        "san_juan",
        "San Juan",
        "53055",
        "San Juan County Auditor",
        "https://www.sanjuancountywa.gov/168/Recording-Division",
        "https://apps.sanjuancountywa.gov/Auditor/DigitalResearchRoom/",
        "Helion Digital Research Room",
        ("recorded_document_index_search", "recorded_document_image_view"),
        "portal_disclaimer_live_verified",
    ),
    RecorderAlternative(
        "skagit",
        "Skagit",
        "53057",
        "Skagit County Auditor",
        "https://www.skagitcountywa.gov/Departments/Auditor",
        "https://www.skagitcounty.net/Search/Recording/default.aspx",
        "Skagit Recorded Document Search",
        (
            "auditor_file_number_search",
            "party_name_search",
            "document_type_search",
            "filed_date_range_search",
            "recorded_document_image_view",
        ),
        "search_form_live_verified",
        notes=("Current-document search states 1973-present.",),
    ),
    RecorderAlternative(
        "stevens",
        "Stevens",
        "53065",
        "Stevens County Auditor",
        "https://www.stevenscountywa.gov/20913/recording",
        "https://selfservice.stevenscountywa.gov/web",
        "Tyler Self-Service",
        (
            "official_record_search",
            "recorded_document_image_view",
            "recorded_document_copy_order",
        ),
        "portal_disclaimer_live_verified",
        notes=(
            "The county describes the self-service collection as 1990-present "
            "and routes older known AFN or book/page requests to the Auditor.",
        ),
    ),
    RecorderAlternative(
        "wahkiakum",
        "Wahkiakum",
        "53069",
        "Wahkiakum County Auditor",
        "https://www.co.wahkiakum.wa.us/589/Auditors-Records",
        None,
        "county public search station",
        ("onsite_record_index_search", "county_copy_request"),
        "county_page_live_no_online_search",
        notes=(
            "The county states that records before 1986 are at Washington State "
            "Archives and provides an in-office public search computer.",
        ),
        complementary_sources=(
            {
                "kind": "historical_record_handoff",
                "url": "https://www.sos.wa.gov/archives",
                "relationship": "county-stated location for pre-1986 records",
            },
        ),
    ),
)

ALTERNATIVES_BY_KEY = {
    alternative.key: alternative for alternative in RECORDER_ALTERNATIVES
}


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name="Washington State Archives Digital Archives — Recorded Land",
        source_role="official_state_archive_county_auditor_recorded_instrument_index",
        base_url=BASE_URL,
        dataset_id=f"record-series-{RECORD_SERIES_ID}",
        metadata={
            "authority": "Washington Secretary of State, Washington State Archives",
            "record_series_id": RECORD_SERIES_ID,
            "record_series_name": RECORD_SERIES_NAME,
            "evidence_lineage": EVIDENCE_LINEAGE,
            "inventory_observed_at": INVENTORY_OBSERVED_AT,
            "inventory": {
                "title_count": len(TITLES),
                "covered_county_count": len(TITLES),
                "record_count": sum(title.record_count for title in TITLES),
                "some_image_title_count": sum(
                    title.image_availability == "some_images" for title in TITLES
                ),
                "image_unavailable_title_count": sum(
                    title.image_availability == "images_not_available"
                    for title in TITLES
                ),
                "county_gap_count": len(RECORDER_ALTERNATIVES),
            },
            "title_discovery": {
                "method": "GET",
                "path": TITLE_LIST_PATH,
                "title_detail_path": TITLE_PATH,
            },
            "native_search": {
                "method": "POST",
                "path": SEARCH_PATH,
                "selectors": [
                    "TitleID",
                    "LastName",
                    "FirstName",
                    "MiddleName",
                    "PartyType",
                    "UseSoundex",
                    "Keywords",
                    "StartYear",
                    "EndYear",
                ],
                "party_roles": ["Grantor", "Grantee"],
                "keywords_label": "Addition Name",
                "instrument_vocabulary": (
                    "title detail Document Types field; document type is also "
                    "returned by result and detail operations"
                ),
            },
            "transport": {
                "search_state": "ASP.NET session-local search ID",
                "results_method": "GET",
                "results_path": RESULTS_PATH,
                "page_numbering": "one_based",
                "native_page_sizes": list(NATIVE_PAGE_SIZES),
                "adapter_minimum_interval_seconds": DEFAULT_MINIMUM_INTERVAL,
                "detail_path": DETAIL_PATH,
            },
            "observed_access": {
                "title_inventory": "open_without_login",
                "title_detail": "open_without_login",
                "search_and_results": "open_session_without_login",
                "record_detail": "open_without_login",
                "document_generation": {
                    "state": "site_recaptcha_queue",
                    "queue_path": DIGITAL_OBJECT_QUEUE_PATH,
                    "captcha_action": "generateDocument",
                },
            },
            "interpretation": {
                "archive_record": (
                    "evidence of a county-auditor recorded-instrument index "
                    "entry and, when present, its archived image"
                ),
                "assessor_record": (
                    "current parcel ownership, assessment, valuation, and tax "
                    "data come from a separate official lineage"
                ),
            },
            "gap_alternatives": [
                alternative.to_record() for alternative in RECORDER_ALTERNATIVES
            ],
        },
    )


STATEWIDE_JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="53",
    name="Washington",
    state_code="WA",
    metadata={"state_fips": "53"},
)


@dataclass(frozen=True)
class SourceResponse:
    """One retrieved source response with request provenance."""

    url: str
    status_code: int
    text: str
    retrieved_at: str


@dataclass(frozen=True)
class SearchHandle:
    """Session-local search identifier returned by the archive."""

    search_id: int
    source_url: str
    retrieved_at: str


@dataclass(frozen=True)
class ResultPage:
    """One native result page."""

    records: tuple[Mapping[str, Any], ...]
    total_count: int
    page: int
    page_count: int
    page_size: int
    first_record: int | None
    last_record: int | None
    source_url: str
    retrieved_at: str
    schema_fingerprint: str


@dataclass(frozen=True)
class CursorState:
    """A continuation position bound to one observed native result page."""

    page: int
    row_offset: int
    native_total_count: int
    schema_fingerprint: str
    page_fingerprint: str


def _clean_text(value: Tag | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Tag):
        text = value.get_text(" ", strip=True)
    else:
        text = re.sub(r"<[^>]+>", " ", unescape(value))
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return text or None


def _snake_label(value: str) -> str:
    value = value.strip().rstrip(":").strip()
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def _digits(value: str | None) -> int | None:
    if not value:
        return None
    candidate = re.sub(r"\D", "", value)
    return int(candidate) if candidate else None


def _schema_fingerprint(headers: Sequence[str], row_widths: Sequence[int]) -> str:
    return sha256_fingerprint(
        {"headers": list(headers), "row_widths": sorted(set(row_widths))}
    )


def _indexed_party_identity(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the source-published fields that identify one indexed party row."""

    return {
        "record_id": record.get("native_record_id") or record.get("record_id"),
        "last_name": record.get("last_name"),
        "first_name": record.get("first_name"),
        "party_type": record.get("party_type"),
        "document_type": record.get("document_type"),
        "year": record.get("year"),
        "county": record.get("county"),
        "legal_description": record.get("legal_description"),
    }


def _indexed_party_key(record: Mapping[str, Any]) -> str:
    """Hash an indexed-party tuple without claiming that it is unique."""

    return sha256_fingerprint(_indexed_party_identity(record))


def _result_page_fingerprint(page: ResultPage) -> str:
    """Fingerprint the ordered native rows without session-local metadata."""

    return sha256_fingerprint(
        {
            "page": page.page,
            "page_size": page.page_size,
            "first_record": page.first_record,
            "last_record": page.last_record,
            "row_keys": [_indexed_party_key(record) for record in page.records],
        }
    )


def parse_title_list(
    html: str,
    *,
    source_url: str = urljoin(BASE_URL, TITLE_LIST_PATH),
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Parse the official record-series title fragment."""

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    for anchor in soup.select(
        'a[href*="/Collections/TitleInfo/"], a[href*="Collections/TitleInfo/"]'
    ):
        href = str(anchor.get("href", ""))
        match = re.search(r"/Collections/TitleInfo/(\d+)", href)
        title = _clean_text(anchor)
        if not match or not title or "Recorded Land Records" not in title:
            continue
        title_id = int(match.group(1))
        if title_id in seen:
            continue
        seen.add(title_id)
        county_match = re.match(r"(.+?) County Auditor,", title)
        county = county_match.group(1) if county_match else None
        known = TITLES_BY_ID.get(title_id)
        records.append(
            {
                "stable_id": f"WSDA:LAND:TITLE:{title_id}",
                "record_kind": "recorded_land_title_discovery",
                "record_series_id": RECORD_SERIES_ID,
                "title_id": title_id,
                "title": title,
                "county": f"{county} County" if county else None,
                "county_key": known.key if known else None,
                "title_url": urljoin(source_url, href),
                "known_inventory_title": known is not None,
                "label_matches_inventory": (
                    known.title == title if known is not None else None
                ),
                "provenance": {
                    "source_id": SOURCE_ID,
                    "source_url": source_url,
                    "retrieved_at": retrieved_at or utc_now_iso(),
                    "record_series_id": RECORD_SERIES_ID,
                },
            }
        )
    if not records:
        raise SourceSchemaError(
            "Recorded-land title links were not found in the title response",
            url=source_url,
        )
    return records


def _table_field_rows(table: Tag) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for row in table.find_all("tr", recursive=False):
        label_cell = row.find("th")
        value_cell = row.find("td")
        label = _clean_text(label_cell)
        value = _clean_text(value_cell)
        if label is not None:
            rows.append((label.rstrip(":").strip(), value or ""))
    return rows


def _image_statement(description: str | None) -> str:
    lowered = (description or "").lower()
    if "some images" in lowered or "images are available" in lowered:
        return "some_images"
    if (
        "images are not available" in lowered
        or "images are unavailable" in lowered
        or "no images" in lowered
    ):
        return "images_not_available"
    return "not_stated"


def parse_title_detail(
    html: str,
    *,
    source_url: str,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Parse one official title page and its native operation schema."""

    soup = BeautifulSoup(html, "html.parser")
    title_id_input = soup.select_one('input[name="TitleID"]')
    series_input = soup.select_one('input[name="RecordSeriesID"]')
    if title_id_input is None or series_input is None:
        raise SourceSchemaError(
            "Title identity controls were not found on the title page",
            url=source_url,
        )
    try:
        title_id = int(str(title_id_input.get("value", "")))
        series_id = int(str(series_input.get("value", "")))
    except ValueError as error:
        raise SourceSchemaError(
            "Title identity controls were not numeric",
            url=source_url,
        ) from error
    if series_id != RECORD_SERIES_ID:
        raise SourceSchemaError(
            f"Expected record series {RECORD_SERIES_ID}, observed {series_id}",
            url=source_url,
        )

    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        label_cell = row.find("th")
        value_cell = row.find("td")
        label = _clean_text(label_cell)
        value = _clean_text(value_cell)
        if label and value is not None:
            fields[_snake_label(label)] = value

    known = TITLES_BY_ID.get(title_id)
    title_text = (
        known.title
        if known is not None
        else _clean_text(soup.select_one("div.sectionTitle"))
    )
    description = fields.get("description")
    form = soup.select_one('form[action="/Collections/Search"]')
    if form is None:
        raise SourceSchemaError(
            "Recorded-land search form was not found on the title page",
            url=source_url,
        )
    input_names = sorted(
        {
            str(control.get("name"))
            for control in form.select("[name]")
            if control.get("name")
        }
    )
    party_roles = [
        _clean_text(option)
        for option in form.select('select[name="PartyType"] option')
        if option.get("value")
    ]
    retrieved = retrieved_at or utc_now_iso()
    return {
        "stable_id": f"WSDA:LAND:TITLE:{title_id}",
        "record_kind": "recorded_land_title",
        "record_series_id": series_id,
        "record_series_name": RECORD_SERIES_NAME,
        "title_id": title_id,
        "title": title_text,
        "county_key": known.key if known else None,
        "county": known.county_name if known else None,
        "county_geoid": known.county_geoid if known else None,
        "record_creator": fields.get("record_creator"),
        "description": description,
        "document_types_text": fields.get("document_types"),
        "record_count": _digits(fields.get("record_count")),
        "image_availability": _image_statement(description),
        "access_restriction_notes": fields.get("access_restriction_notes"),
        "sources_of_transfer": (
            fields.get("sources_of_transfer") or fields.get("source_of_transfer")
        ),
        "preferred_citation": fields.get("preferred_citation"),
        "related_records": fields.get("related_records"),
        "search_operation": {
            "method": "POST",
            "path": SEARCH_PATH,
            "record_series_id": series_id,
            "title_id": title_id,
            "input_names": input_names,
            "party_roles": [role for role in party_roles if role],
            "supports_browse": "TitleInfo.Browse" in html,
            "keywords_label": "Addition Name",
            "result_document_type_field": "Doc Type",
        },
        "instrument_vocabulary": {
            "representation": "source_text",
            "text": fields.get("document_types"),
            "source_field": "Document Types",
        },
        "evidence_lineage": EVIDENCE_LINEAGE,
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "retrieved_at": retrieved,
            "record_series_id": series_id,
            "title_id": title_id,
            "schema_fingerprint": sha256_fingerprint(
                {
                    "field_names": sorted(fields),
                    "search_input_names": input_names,
                }
            ),
        },
    }


_PAGE_SUMMARY_RE = re.compile(
    r"Page\s+(?P<page>\d+)\s+of\s+(?P<pages>\d+),\s*"
    r"Records\s+(?P<first>\d+)-(?P<last>\d+)\s+of\s+(?P<total>\d+)",
    re.I,
)


def parse_results_page(
    html: str,
    *,
    source_url: str,
    requested_page_size: int,
    retrieved_at: str | None = None,
) -> ResultPage:
    """Parse one native result fragment, including authoritative emptiness."""

    retrieved = retrieved_at or utc_now_iso()
    soup = BeautifulSoup(html, "html.parser")
    no_results = soup.select_one("div.noSearchResults")
    if no_results is not None and "No search results found" in (
        _clean_text(no_results) or ""
    ):
        return ResultPage(
            records=(),
            total_count=0,
            page=1,
            page_count=0,
            page_size=requested_page_size,
            first_record=None,
            last_record=None,
            source_url=source_url,
            retrieved_at=retrieved,
            schema_fingerprint=sha256_fingerprint(
                {"state": "no_search_results"}
            ),
        )

    table = soup.select_one("table#searchResultTable")
    if table is None:
        raise SourceSchemaError(
            "Search result table or no-result marker was not found",
            url=source_url,
        )
    header_row = table.select_one("thead tr")
    headers = (
        [_clean_text(cell) or "" for cell in header_row.find_all("th")]
        if header_row is not None
        else []
    )
    expected_headers = [
        "Last Name",
        "First Name",
        "Party Type",
        "Doc Type",
        "Year",
        "County",
        "Legal Description",
        "Image Exists",
    ]
    if headers[:8] != expected_headers:
        raise SourceSchemaError(
            f"Unexpected recorded-land result columns: {headers[:8]!r}",
            url=source_url,
            details={"headers": headers[:8]},
        )

    summary = _clean_text(table.select_one("#pageSummary"))
    match = _PAGE_SUMMARY_RE.search(summary or "")
    if match is None:
        raise SourceSchemaError(
            f"Native page summary was not recognized: {summary!r}",
            url=source_url,
        )
    parsed = {key: int(value) for key, value in match.groupdict().items()}

    records: list[dict[str, Any]] = []
    row_widths: list[int] = []
    for native_index, row in enumerate(table.select("tbody tr"), start=1):
        cells = row.find_all("td", recursive=False)
        row_widths.append(len(cells))
        if len(cells) < 8:
            continue
        anchor = cells[0].find("a", href=True)
        href = str(anchor.get("href", "")) if anchor else ""
        id_match = re.search(r"/Record/View/([A-Fa-f0-9]{32})", href)
        if id_match is None:
            raise SourceSchemaError(
                "A result row did not contain a stable archive record link",
                url=source_url,
            )
        record_id = id_match.group(1).upper()
        values = [_clean_text(cell) for cell in cells[:7]]
        image = cells[7].find("img")
        image_alt = _clean_text(str(image.get("alt", ""))) if image else None
        image_exists = bool(image_alt and "image available" in image_alt.lower())
        native_result_ordinal = parsed["first"] + native_index - 1
        row_identity = {
            "record_id": record_id,
            "last_name": values[0],
            "first_name": values[1],
            "party_type": values[2],
            "document_type": values[3],
            "year": int(values[4]) if values[4] and values[4].isdigit() else None,
            "county": values[5],
            "legal_description": values[6],
        }
        indexed_party_key = sha256_fingerprint(row_identity)
        ordinal_occurrence_hash = sha256_fingerprint(
            {
                "indexed_party_key": indexed_party_key,
                "native_result_ordinal": native_result_ordinal,
            }
        )
        records.append(
            {
                "ordinal_occurrence_key": (
                    "WSDA:LAND:QUERY-RELATIVE-ORDINAL:"
                    f"{ordinal_occurrence_hash}"
                ),
                "indexed_party_key": (
                    f"WSDA:LAND:INDEXED-PARTY:{indexed_party_key}"
                ),
                "record_kind": "recorded_land_search_result",
                "native_record_id": record_id,
                "record_url": urljoin(BASE_URL, href),
                "native_row_index": native_index,
                "native_result_ordinal": native_result_ordinal,
                **row_identity,
                "image_exists": image_exists,
                "image_state": "available" if image_exists else "not_listed",
                "evidence_lineage": EVIDENCE_LINEAGE,
                "provenance": {
                    "source_id": SOURCE_ID,
                    "source_url": source_url,
                    "record_url": urljoin(BASE_URL, href),
                    "retrieved_at": retrieved,
                    "record_series_id": RECORD_SERIES_ID,
                    "native_record_id": record_id,
                },
            }
        )

    expected_row_count = parsed["last"] - parsed["first"] + 1
    if len(records) != expected_row_count:
        raise SourceSchemaError(
            "Native page summary did not match the parsed result-row count",
            url=source_url,
            details={
                "expected_rows": expected_row_count,
                "parsed_rows": len(records),
            },
        )

    per_page = table.select_one("#RecordsPerPage option[selected]")
    page_size_text = _clean_text(per_page)
    page_size = (
        int(page_size_text)
        if page_size_text and page_size_text.isdigit()
        else requested_page_size
    )
    return ResultPage(
        records=tuple(records),
        total_count=parsed["total"],
        page=parsed["page"],
        page_count=parsed["pages"],
        page_size=page_size,
        first_record=parsed["first"],
        last_record=parsed["last"],
        source_url=source_url,
        retrieved_at=retrieved,
        schema_fingerprint=_schema_fingerprint(headers[:8], row_widths),
    )


def _record_id_from_detail_path(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(
        r"/Record/View/([A-Fa-f0-9]{32})(?:[/?#]|$)",
        value,
    )
    return match.group(1).upper() if match else None


def _county_identity(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+COUNTY$", "", value.strip(), flags=re.I).casefold()


def parse_record_detail(
    html: str,
    *,
    record_id: str,
    source_url: str,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Parse one archive record detail and its digital-object inventory."""

    record_id = record_id.upper()
    if not re.fullmatch(r"[A-F0-9]{32}", record_id):
        raise SourceSchemaError(
            "Requested archive record identifier was not 32 hexadecimal characters",
            url=source_url,
            details={"record_id": record_id},
        )
    response_record_id = _record_id_from_detail_path(source_url)
    if response_record_id != record_id:
        raise SourceSchemaError(
            "Archive detail response URL did not match the requested record",
            url=source_url,
            details={
                "requested_record_id": record_id,
                "response_record_id": response_record_id,
            },
        )
    retrieved = retrieved_at or utc_now_iso()
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.viewRecord")
    if container is None:
        raise SourceSchemaError(
            "Recorded-land detail container was not found",
            url=source_url,
        )
    tables = container.select("table.recordMetaData")
    if len(tables) < 2:
        raise SourceSchemaError(
            "Recorded-land detail metadata tables were not found",
            url=source_url,
        )

    identity_rows = dict(_table_field_rows(tables[0]))
    field_rows = _table_field_rows(tables[1])
    fields: dict[str, Any] = {}
    parties: list[dict[str, Any]] = []
    current_party: dict[str, Any] | None = None
    for label, value in field_rows:
        key = _snake_label(label)
        if key == "party_type":
            current_party = {
                "sequence_no": len(parties) + 1,
                "party_type": value or None,
            }
            parties.append(current_party)
            continue
        if current_party is not None and key in {
            "first_name",
            "middle_name",
            "last_name",
        }:
            current_party[key] = value or None
            continue
        current_party = None
        if key in fields:
            existing = fields[key]
            if not isinstance(existing, list):
                existing = [existing]
            existing.append(value or None)
            fields[key] = existing
        else:
            fields[key] = value or None

    collection_anchor = tables[0].find("a", href=re.compile(r"/Collections/TitleInfo/"))
    title_id_match = (
        re.search(r"/Collections/TitleInfo/(\d+)", str(collection_anchor.get("href")))
        if collection_anchor is not None
        else None
    )
    title_id = int(title_id_match.group(1)) if title_id_match else None
    known = TITLES_BY_ID.get(title_id) if title_id is not None else None
    if title_id is None:
        raise SourceSchemaError(
            "Recorded-land detail did not identify its collection title",
            url=source_url,
        )
    record_series_name = identity_rows.get("Record Series")
    if (record_series_name or "").strip().casefold() != RECORD_SERIES_NAME.casefold():
        raise SourceSchemaError(
            "Archive detail did not identify the recorded-land record series",
            url=source_url,
            details={
                "expected_record_series": RECORD_SERIES_NAME,
                "observed_record_series": record_series_name,
            },
        )
    if known is not None and _county_identity(identity_rows.get("County")) != (
        _county_identity(known.county)
    ):
        raise SourceSchemaError(
            "Archive detail county did not match its collection title",
            url=source_url,
            details={
                "title_id": title_id,
                "expected_county": known.county,
                "observed_county": identity_rows.get("County"),
            },
        )

    digital_objects: list[dict[str, Any]] = []
    for item in soup.select("div[data-download][data-id]"):
        object_id = str(item.get("data-id", "")).strip()
        object_format = str(item.get("data-format", "")).strip() or None
        if not object_id:
            continue
        digital_objects.append(
            {
                "stable_id": f"WSDA:DIGITAL-OBJECT:{object_id}",
                "native_digital_object_id": object_id,
                "format": object_format,
                "availability": "available_for_site_generation",
                "delivery_operation": {
                    "method": "POST",
                    "path": DIGITAL_OBJECT_QUEUE_PATH,
                    "state": "site_recaptcha_queue",
                    "captcha_action": "generateDocument",
                },
            }
        )

    preferred_citation = _clean_text(soup.select_one("#preferredCitation"))
    source_of_transfer = _clean_text(soup.select_one("#sourceOfTransfer"))
    related_records = _clean_text(soup.select_one("#relatedRecords"))
    source_path = _clean_text(soup.select_one("table.viewRecordSource td"))
    page_record_id = _record_id_from_detail_path(source_path)
    if page_record_id != record_id:
        raise SourceSchemaError(
            "Archive detail source path did not match the requested record",
            url=source_url,
            details={
                "requested_record_id": record_id,
                "page_record_id": page_record_id,
                "source_path": source_path,
            },
        )
    field_names = [label for label, _value in field_rows]
    return {
        "stable_id": f"WSDA:LAND:RECORD:{record_id}",
        "record_kind": "recorded_land_record",
        "native_record_id": record_id,
        "record_url": source_url,
        "record_series_id": RECORD_SERIES_ID,
        "record_series_name": record_series_name,
        "title_id": title_id,
        "collection": identity_rows.get("Collection"),
        "county_key": known.key if known else None,
        "county": identity_rows.get("County"),
        "county_geoid": known.county_geoid if known else None,
        "reference_number": fields.get("reference_number"),
        "recording_date": fields.get("recording_date"),
        "document_type": fields.get("document_type"),
        "number_pages": _digits(str(fields.get("numberpages") or "")),
        "related_document_number": fields.get("related_document_number"),
        "document_id": fields.get("documentid"),
        "modification_date": fields.get("modification_date"),
        "return": fields.get("return"),
        "return_2": fields.get("return2"),
        "parties": parties,
        "legal": {
            "legal_description": fields.get("legal_description"),
            "parcel": fields.get("parcel"),
            "plss_legal": fields.get("plsslegal"),
            "platted_legal": fields.get("platted_legal"),
            "book_page": fields.get("bookpage"),
            "related_book_page": fields.get("related_book_page"),
            "mineral_rights": fields.get("mineral_rights"),
        },
        "fields": fields,
        "image_availability": (
            "available" if digital_objects else "not_listed_on_detail"
        ),
        "digital_objects": digital_objects,
        "document_delivery": {
            "state": (
                "site_recaptcha_queue" if digital_objects else "no_object_listed"
            ),
            "queue_path": (
                DIGITAL_OBJECT_QUEUE_PATH if digital_objects else None
            ),
            "direct_download_url": None,
        },
        "preferred_citation": preferred_citation,
        "source_of_transfer": source_of_transfer,
        "related_records": related_records,
        "evidence_lineage": EVIDENCE_LINEAGE,
        "evidence_scope": (
            "county-auditor recorded-instrument archive detail and listed "
            "digital objects"
        ),
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "source_path": source_path,
            "retrieved_at": retrieved,
            "record_series_id": RECORD_SERIES_ID,
            "title_id": title_id,
            "native_record_id": record_id,
            "schema_fingerprint": sha256_fingerprint(
                {
                    "identity_fields": sorted(identity_rows),
                    "detail_field_sequence": field_names,
                    "digital_object_formats": sorted(
                        str(item["format"]) for item in digital_objects
                    ),
                }
            ),
        },
    }


class DigitalArchivesClient:
    """Session-aware client for the archive's open title/search/detail flow."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    ) -> SourceResponse:
        url = urljoin(BASE_URL, path)
        last_error: PublicRecordsHTTPError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = TransportError(str(error), url=url)
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise last_error from error
            except OSError as error:
                last_error = TransportError(str(error), url=url)
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise last_error from error

            status_code = int(response.status_code)
            response_url = str(getattr(response, "url", url))
            text = str(getattr(response, "text", ""))
            if status_code in self.retry_policy.retry_statuses:
                if status_code == 429:
                    last_error = RateLimitedHTTPError(
                        status_code,
                        url=response_url,
                        response_text=text,
                    )
                else:
                    last_error = HTTPStatusError(
                        status_code,
                        url=response_url,
                        response_text=text,
                    )
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise last_error
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=response_url,
                    response_text=text,
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=response_url,
                    response_text=text,
                )
            if len(text.encode("utf-8", errors="replace")) > MAX_RESPONSE_BYTES:
                raise SourceSchemaError(
                    "Archive response exceeded the adapter response bound",
                    url=response_url,
                    details={"maximum_bytes": MAX_RESPONSE_BYTES},
                )
            return SourceResponse(
                url=response_url,
                status_code=status_code,
                text=text,
                retrieved_at=utc_now_iso(),
            )
        if last_error is not None:
            raise last_error
        raise TransportError("Archive request did not execute", url=url)

    def fetch_title_list(self) -> list[dict[str, Any]]:
        response = self._request("GET", TITLE_LIST_PATH)
        return parse_title_list(
            response.text,
            source_url=response.url,
            retrieved_at=response.retrieved_at,
        )

    def fetch_title(self, title_id: int) -> dict[str, Any]:
        response = self._request("GET", TITLE_PATH.format(title_id=title_id))
        return parse_title_detail(
            response.text,
            source_url=response.url,
            retrieved_at=response.retrieved_at,
        )

    def start_search(self, payload: Mapping[str, Any]) -> SearchHandle:
        response = self._request("POST", SEARCH_PATH, data=payload)
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise SourceSchemaError(
                "Archive search did not return its search identifier JSON",
                url=response.url,
                details={"response_prefix": response.text[:300]},
            ) from error
        redirect = data.get("Redirect") if isinstance(data, Mapping) else None
        if (
            not isinstance(data, Mapping)
            or data.get("Result") is not True
            or not isinstance(redirect, int)
            or redirect <= 0
        ):
            raise SourceSchemaError(
                "Archive search response did not contain a valid search identifier",
                url=response.url,
                details={"response": data if isinstance(data, Mapping) else None},
            )
        return SearchHandle(
            search_id=redirect,
            source_url=response.url,
            retrieved_at=response.retrieved_at,
        )

    def fetch_results(
        self,
        search_id: int,
        *,
        page: int,
        page_size: int,
        sort_column: int = -1,
        direction: str = "null",
    ) -> ResultPage:
        response = self._request(
            "GET",
            RESULTS_PATH,
            params={
                "id": search_id,
                "sortColumn": sort_column,
                "direction": direction,
                "pageSize": page_size,
                "page": page,
            },
        )
        return parse_results_page(
            response.text,
            source_url=response.url,
            requested_page_size=page_size,
            retrieved_at=response.retrieved_at,
        )

    def fetch_detail(self, record_id: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            DETAIL_PATH.format(record_id=record_id.upper()),
        )
        return parse_record_detail(
            response.text,
            record_id=record_id,
            source_url=response.url,
            retrieved_at=response.retrieved_at,
        )


def build_search_payload(
    title: TitleConfig,
    *,
    search_type: str,
    last_name: str | None = None,
    first_name: str | None = None,
    middle_name: str | None = None,
    party_role: str | None = None,
    addition: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    soundex: bool = False,
) -> dict[str, Any]:
    """Build the archive's native recorded-land search form payload."""

    role = (
        {"grantor": "Grantor", "grantee": "Grantee"}.get(party_role.lower())
        if party_role
        else ""
    )
    if party_role and role is None:
        raise ValueError("party_role must be grantor or grantee")
    return {
        "RecordSeriesID": RECORD_SERIES_ID,
        "TitleID": title.title_id,
        "SearchType": search_type,
        "LastName": last_name or "",
        "FirstName": first_name or "",
        "MiddleName": middle_name or "",
        "PartyType": role or "",
        "Keywords": addition or "",
        "StartYear": str(start_year) if start_year is not None else "",
        "EndYear": str(end_year) if end_year is not None else "",
        "UseSoundex": "true" if soundex else "false",
    }


def _cursor_fingerprint(
    title: TitleConfig,
    *,
    search_type: str,
    payload: Mapping[str, Any],
    page_size: int,
    sort: str | None,
    direction: str | None,
) -> str:
    return sha256_fingerprint(
        {
            "title_id": title.title_id,
            "search_type": search_type,
            "payload": dict(payload),
            "page_size": page_size,
            "sort": sort,
            "direction": direction,
        }
    )


def encode_cursor(
    *,
    fingerprint: str,
    page: int,
    row_offset: int,
    native_total_count: int,
    schema_fingerprint: str,
    page_fingerprint: str,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "fingerprint": fingerprint,
        "page": page,
        "row_offset": row_offset,
        "native_total_count": native_total_count,
        "schema_fingerprint": schema_fingerprint,
        "page_fingerprint": page_fingerprint,
    }
    payload["check"] = sha256_fingerprint(payload)[:16]
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode()).decode()
    return CURSOR_PREFIX + encoded.rstrip("=")


def decode_cursor(cursor: str, *, expected_fingerprint: str) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise ValueError("cursor does not belong to this adapter")
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("cursor payload is not an object")
        supplied_check = str(payload.pop("check"))
        expected_check = sha256_fingerprint(payload)[:16]
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("cursor is not valid encoded JSON") from error
    except KeyError as error:
        raise ValueError("cursor checksum is missing") from error
    if supplied_check != expected_check:
        raise ValueError("cursor checksum is invalid")
    if (
        not isinstance(payload, Mapping)
        or payload.get("version") != CURSOR_VERSION
        or payload.get("fingerprint") != expected_fingerprint
    ):
        raise ValueError("cursor does not match this query")
    page = payload.get("page")
    row_offset = payload.get("row_offset")
    native_total_count = payload.get("native_total_count")
    schema_fingerprint = payload.get("schema_fingerprint")
    page_fingerprint = payload.get("page_fingerprint")
    if (
        not isinstance(page, int)
        or isinstance(page, bool)
        or page < 1
        or not isinstance(row_offset, int)
        or isinstance(row_offset, bool)
        or row_offset < 0
        or not isinstance(native_total_count, int)
        or isinstance(native_total_count, bool)
        or native_total_count < 0
        or not isinstance(schema_fingerprint, str)
        or not re.fullmatch(r"[a-f0-9]{64}", schema_fingerprint)
        or not isinstance(page_fingerprint, str)
        or not re.fullmatch(r"[a-f0-9]{64}", page_fingerprint)
    ):
        raise ValueError("cursor snapshot state is invalid")
    return CursorState(
        page=page,
        row_offset=row_offset,
        native_total_count=native_total_count,
        schema_fingerprint=schema_fingerprint,
        page_fingerprint=page_fingerprint,
    )


def _build_query(
    *,
    title: TitleConfig | None,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=title.jurisdiction if title is not None else STATEWIDE_JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata=metadata or {},
        ),
    )


def _log_result(query: PublicRecordsQuery, result: PublicRecordsResult) -> None:
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), query.source.source_id, result_count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _new_client(args: argparse.Namespace) -> DigitalArchivesClient:
    return DigitalArchivesClient(
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
        retry_policy=RetryPolicy(
            max_attempts=getattr(args, "retry_attempts", 3)
        ),
    )


def _static_sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source": _source_metadata().to_dict(),
        "inventory_observed_at": INVENTORY_OBSERVED_AT,
        "title_count": len(TITLES),
        "covered_county_count": len(TITLES),
        "record_count": sum(title.record_count for title in TITLES),
        "some_image_title_count": sum(
            title.image_availability == "some_images" for title in TITLES
        ),
        "image_unavailable_title_count": sum(
            title.image_availability == "images_not_available" for title in TITLES
        ),
        "titles": [title.to_record() for title in TITLES],
        "county_gap_count": len(RECORDER_ALTERNATIVES),
        "county_gaps": [
            alternative.to_record() for alternative in RECORDER_ALTERNATIVES
        ],
    }


def _inventory_payload(
    args: argparse.Namespace,
    *,
    client: DigitalArchivesClient,
) -> dict[str, Any]:
    discovered = client.fetch_title_list()
    discovered_ids = {record["title_id"] for record in discovered}
    expected_ids = set(TITLES_BY_ID)
    records = []
    for record in discovered:
        known = TITLES_BY_ID.get(record["title_id"])
        merged = dict(record)
        if known is not None:
            merged["verified_inventory"] = known.to_record()
        records.append(merged)

    details: list[dict[str, Any]] = []
    if getattr(args, "details", False):
        requested_maximum = getattr(args, "max_titles", None)
        maximum = (
            len(discovered)
            if requested_maximum is None
            else min(requested_maximum, len(discovered))
        )
        for record in discovered[:maximum]:
            details.append(client.fetch_title(int(record["title_id"])))
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "ok",
        "source_id": SOURCE_ID,
        "record_series_id": RECORD_SERIES_ID,
        "discovered_title_count": len(discovered),
        "expected_title_count": len(TITLES),
        "missing_verified_title_ids": sorted(expected_ids - discovered_ids),
        "new_title_ids": sorted(discovered_ids - expected_ids),
        "title_label_change_count": sum(
            record.get("label_matches_inventory") is False for record in discovered
        ),
        "titles": records,
        "details": details,
        "county_gaps": [
            alternative.to_record() for alternative in RECORDER_ALTERNATIVES
        ],
    }


def _title_result(
    args: argparse.Namespace,
    title: TitleConfig,
    *,
    client: DigitalArchivesClient,
    instruments_only: bool = False,
) -> PublicRecordsResult:
    operation = "instruments" if instruments_only else "metadata"
    query = _build_query(
        title=title,
        operation=operation,
        parameters={"title_id": title.title_id, "refresh": True},
        requested_limit=1,
    )
    try:
        detail = client.fetch_title(title.title_id)
    except PublicRecordsHTTPError as error:
        return failure_result(query, error)
    if instruments_only:
        record = {
            "stable_id": f"WSDA:LAND:INSTRUMENT-VOCABULARY:{title.title_id}",
            "record_kind": "recorded_land_instrument_vocabulary",
            "record_series_id": RECORD_SERIES_ID,
            "title_id": title.title_id,
            "county_key": title.key,
            "county": title.county_name,
            "document_types_text": detail["document_types_text"],
            "representation": "source_text",
            "result_field": "Doc Type",
            "detail_field": "Document Type",
            "provenance": detail["provenance"],
        }
    else:
        record = detail
    return PublicRecordsResult.success(query, [record])


def _metadata_result(
    args: argparse.Namespace,
    title: TitleConfig,
    *,
    client: DigitalArchivesClient,
) -> PublicRecordsResult:
    if getattr(args, "refresh", False):
        return _title_result(args, title, client=client)
    query = _build_query(
        title=title,
        operation="metadata",
        parameters={"title_id": title.title_id, "refresh": False},
        requested_limit=1,
    )
    return PublicRecordsResult.success(query, [title.to_record()])


def _search_result(
    args: argparse.Namespace,
    title: TitleConfig,
    *,
    client: DigitalArchivesClient,
    log_results: bool,
) -> PublicRecordsResult:
    search_type = "Browse" if args.command == "browse" else "DetailedSearch"
    payload = build_search_payload(
        title,
        search_type=search_type,
        last_name=getattr(args, "last_name", None),
        first_name=getattr(args, "first_name", None),
        middle_name=getattr(args, "middle_name", None),
        party_role=getattr(args, "party_role", None),
        addition=getattr(args, "addition", None),
        start_year=getattr(args, "start_year", None),
        end_year=getattr(args, "end_year", None),
        soundex=getattr(args, "soundex", False),
    )
    page_size = getattr(args, "page_size", DEFAULT_PAGE_SIZE)
    sort = getattr(args, "sort", None)
    direction_arg = getattr(args, "direction", None)
    direction = direction_arg.upper() if direction_arg else "null"
    sort_column = SORT_COLUMNS[sort] if sort else -1
    fingerprint = _cursor_fingerprint(
        title,
        search_type=search_type,
        payload=payload,
        page_size=page_size,
        sort=sort,
        direction=direction_arg,
    )
    page = 1
    row_offset = 0
    cursor = getattr(args, "cursor", None)
    cursor_state: CursorState | None = None
    if cursor:
        cursor_state = decode_cursor(
            cursor,
            expected_fingerprint=fingerprint,
        )
        page = cursor_state.page
        row_offset = cursor_state.row_offset

    public_parameters = {
        "record_series_id": RECORD_SERIES_ID,
        "title_id": title.title_id,
        "county": title.key,
        "search_type": search_type,
        "last_name": payload["LastName"] or None,
        "first_name": payload["FirstName"] or None,
        "middle_name": payload["MiddleName"] or None,
        "party_role": payload["PartyType"] or None,
        "addition": payload["Keywords"] or None,
        "start_year": int(payload["StartYear"]) if payload["StartYear"] else None,
        "end_year": int(payload["EndYear"]) if payload["EndYear"] else None,
        "soundex": payload["UseSoundex"] == "true",
        "sort": sort,
        "direction": direction_arg,
        "page_size": page_size,
    }
    query = _build_query(
        title=title,
        operation=args.command,
        parameters=public_parameters,
        requested_limit=args.limit,
        cursor=cursor,
        metadata={
            "transport": {
                "page_numbering": "one_based",
                "native_page_size": page_size,
                "search_session_recreated_for_cursor": bool(cursor),
            }
        },
    )

    records: list[Mapping[str, Any]] = []
    next_cursor: str | None = None
    failure_cursor: str | None = None
    native_total: int | None = (
        cursor_state.native_total_count if cursor_state is not None else None
    )
    native_schema_fingerprint: str | None = (
        cursor_state.schema_fingerprint if cursor_state is not None else None
    )
    cursor_snapshot_validated = cursor_state is None
    source_urls: list[str] = []
    try:
        handle = client.start_search(payload)
        while args.limit is None or len(records) < args.limit:
            result_page = client.fetch_results(
                handle.search_id,
                page=page,
                page_size=page_size,
                sort_column=sort_column,
                direction=direction,
            )
            source_urls.append(result_page.source_url)
            if result_page.page != page:
                raise SourceSchemaError(
                    "Archive returned a different native page than requested",
                    url=result_page.source_url,
                    details={"requested_page": page, "observed_page": result_page.page},
                )
            page_fingerprint = _result_page_fingerprint(result_page)
            if cursor_state is not None and not cursor_snapshot_validated:
                drift: dict[str, Any] = {}
                if result_page.total_count != cursor_state.native_total_count:
                    drift["native_total_count"] = {
                        "cursor": cursor_state.native_total_count,
                        "observed": result_page.total_count,
                    }
                if (
                    result_page.schema_fingerprint
                    != cursor_state.schema_fingerprint
                ):
                    drift["schema_fingerprint"] = {
                        "cursor": cursor_state.schema_fingerprint,
                        "observed": result_page.schema_fingerprint,
                    }
                if page_fingerprint != cursor_state.page_fingerprint:
                    drift["page_fingerprint"] = {
                        "cursor": cursor_state.page_fingerprint,
                        "observed": page_fingerprint,
                    }
                if row_offset > len(result_page.records):
                    drift["row_offset"] = {
                        "cursor": row_offset,
                        "observed_row_count": len(result_page.records),
                    }
                if drift:
                    raise SourceSchemaError(
                        "Native search snapshot changed before cursor resumption",
                        url=result_page.source_url,
                        details={
                            "cursor_page": cursor_state.page,
                            "drift": drift,
                        },
                    )
                cursor_snapshot_validated = True
            if native_total is None:
                native_total = result_page.total_count
            elif result_page.total_count != native_total:
                raise SourceSchemaError(
                    "Native result count changed while paging one search session",
                    url=result_page.source_url,
                    details={
                        "initial_total": native_total,
                        "observed_total": result_page.total_count,
                    },
                )
            if native_schema_fingerprint is None:
                native_schema_fingerprint = result_page.schema_fingerprint
            elif result_page.schema_fingerprint != native_schema_fingerprint:
                raise SourceSchemaError(
                    "Native result schema changed while paging one search session",
                    url=result_page.source_url,
                    details={
                        "initial_schema_fingerprint": native_schema_fingerprint,
                        "observed_schema_fingerprint": (
                            result_page.schema_fingerprint
                        ),
                    },
                )
            if result_page.total_count == 0:
                break
            available = list(
                enumerate(
                    result_page.records[row_offset:],
                    start=row_offset,
                )
            )
            remaining = (
                len(available)
                if args.limit is None
                else args.limit - len(records)
            )
            selected = available[:remaining]
            for page_offset, record in selected:
                native_result_ordinal = (
                    (result_page.first_record or 1) + page_offset
                )
                indexed_party_key = _indexed_party_key(record)
                ordinal_occurrence_hash = sha256_fingerprint(
                    {
                        "indexed_party_key": indexed_party_key,
                        "native_result_ordinal": native_result_ordinal,
                    }
                )
                query_occurrence_hash = sha256_fingerprint(
                    {
                        "query_fingerprint": fingerprint,
                        "indexed_party_key": indexed_party_key,
                        "native_result_ordinal": native_result_ordinal,
                    }
                )
                occurrence_id = (
                    "WSDA:LAND:SEARCH-OCCURRENCE:"
                    f"{query_occurrence_hash}"
                )
                enriched = dict(record)
                enriched.update(
                    {
                        "stable_id": occurrence_id,
                        "source_occurrence_id": occurrence_id,
                        "query_occurrence_id": occurrence_id,
                        "ordinal_occurrence_key": (
                            "WSDA:LAND:QUERY-RELATIVE-ORDINAL:"
                            f"{ordinal_occurrence_hash}"
                        ),
                        "indexed_party_key": (
                            f"WSDA:LAND:INDEXED-PARTY:{indexed_party_key}"
                        ),
                        "native_row_index": page_offset + 1,
                        "native_result_ordinal": native_result_ordinal,
                    }
                )
                enriched["search_context"] = {
                    "query_fingerprint": fingerprint,
                    "native_total_count": result_page.total_count,
                    "native_page": result_page.page,
                    "native_page_count": result_page.page_count,
                    "native_page_size": result_page.page_size,
                    "native_search_id": handle.search_id,
                }
                records.append(enriched)
            consumed_offset = row_offset + len(selected)
            has_more_on_page = consumed_offset < len(result_page.records)
            has_more_pages = page < result_page.page_count
            current_continuation: str | None = None
            if has_more_on_page or has_more_pages:
                current_continuation = encode_cursor(
                    fingerprint=fingerprint,
                    page=page,
                    row_offset=consumed_offset,
                    native_total_count=result_page.total_count,
                    schema_fingerprint=result_page.schema_fingerprint,
                    page_fingerprint=page_fingerprint,
                )
                failure_cursor = current_continuation
            if args.limit is not None and len(records) >= args.limit:
                next_cursor = current_continuation
                break
            if has_more_pages:
                page += 1
                row_offset = 0
                continue
            break
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            records=records,
            next_cursor=next_cursor or failure_cursor,
        )
        if log_results:
            _log_result(query, result)
        return result

    warnings = (
        "Native result counts describe matching index rows; multiple party rows "
        "can reference the same recorded instrument.",
    )
    result = PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        raw_artifact_refs=tuple(source_urls),
        warnings=warnings,
    )
    if log_results:
        _log_result(query, result)
    return result


def _detail_result(
    args: argparse.Namespace,
    *,
    client: DigitalArchivesClient,
    log_results: bool,
) -> PublicRecordsResult:
    record_id = args.record_id.upper()
    state_query = _build_query(
        title=None,
        operation="detail",
        parameters={"record_id": record_id},
        requested_limit=1,
    )
    try:
        record = client.fetch_detail(record_id)
    except PublicRecordsHTTPError as error:
        query = state_query
        result = failure_result(query, error)
    else:
        title_id = record.get("title_id")
        title = (
            TITLES_BY_ID.get(title_id)
            if isinstance(title_id, int) and not isinstance(title_id, bool)
            else None
        )
        query = _build_query(
            title=title,
            operation="detail",
            parameters={"record_id": record_id},
            requested_limit=1,
            metadata={
                "jurisdiction_resolved_from_record_title": title is not None,
                "title_id": title_id,
            },
        )
        result = PublicRecordsResult.success(query, [record])
    if log_results:
        _log_result(query, result)
    return result


def _probe_payload(
    args: argparse.Namespace,
    *,
    client: DigitalArchivesClient,
) -> dict[str, Any]:
    title = TITLES_BY_KEY[args.county]
    requested = {
        operation.strip().lower()
        for operation in args.operations.split(",")
        if operation.strip()
    }
    components: list[dict[str, Any]] = []

    def capture(operation: str, callback: Callable[[], Any]) -> None:
        try:
            value = callback()
        except PublicRecordsHTTPError as error:
            components.append(
                {
                    "operation": operation,
                    "status": error.result_status.value,
                    "error": error.to_contract_error().to_dict(),
                }
            )
        else:
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                count = len(value)
            else:
                count = 1
            components.append(
                {"operation": operation, "status": "ok", "result_count": count}
            )

    if "inventory" in requested:
        capture("inventory", client.fetch_title_list)
    if "title" in requested:
        capture("title", lambda: client.fetch_title(title.title_id))
    if "all_titles" in requested or getattr(args, "all_titles", False):
        for candidate in TITLES:
            capture(
                f"title:{candidate.key}",
                lambda candidate=candidate: client.fetch_title(candidate.title_id),
            )
    if "search" in requested:
        if title.sentinel_last_name is None:
            components.append(
                {
                    "operation": "search",
                    "status": "not_configured",
                    "county": title.key,
                }
            )
        else:
            payload = build_search_payload(
                title,
                search_type="DetailedSearch",
                last_name=title.sentinel_last_name,
                first_name=title.sentinel_first_name,
                start_year=title.sentinel_year,
                end_year=title.sentinel_year,
            )

            def sentinel_search() -> Sequence[Mapping[str, Any]]:
                handle = client.start_search(payload)
                return client.fetch_results(
                    handle.search_id,
                    page=1,
                    page_size=DEFAULT_PAGE_SIZE,
                ).records

            capture("search", sentinel_search)
    if "detail" in requested:
        if title.sentinel_record_id is None:
            components.append(
                {
                    "operation": "detail",
                    "status": "not_configured",
                    "county": title.key,
                }
            )
        else:
            capture(
                "detail",
                lambda: client.fetch_detail(str(title.sentinel_record_id)),
            )

    statuses = {component["status"] for component in components}
    overall = (
        "ok"
        if statuses <= {"ok", "not_configured"}
        else ("partial" if "ok" in statuses else "unavailable")
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": overall,
        "county": title.key,
        "record_series_id": RECORD_SERIES_ID,
        "requested_operations": sorted(requested),
        "components": components,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: DigitalArchivesClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source discovery, metadata, search, detail, or probes."""

    if args.command == "sources":
        return _static_sources_payload()
    if args.command == "alternatives":
        selected = (
            [ALTERNATIVES_BY_KEY[args.county]]
            if getattr(args, "county", None)
            else list(RECORDER_ALTERNATIVES)
        )
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "record_series_id": RECORD_SERIES_ID,
            "archive_gap_count": len(selected),
            "alternatives": [alternative.to_record() for alternative in selected],
        }

    selected_client = client or _new_client(args)
    if args.command == "inventory":
        if not getattr(args, "refresh", False):
            return _static_sources_payload()
        try:
            return _inventory_payload(args, client=selected_client)
        except PublicRecordsHTTPError as error:
            return {
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "status": error.result_status.value,
                "source_id": SOURCE_ID,
                "errors": [error.to_contract_error().to_dict()],
                "titles": [],
            }
    if args.command in {"metadata", "instruments"}:
        title = TITLES_BY_KEY[args.county]
        if args.command == "instruments":
            return _title_result(
                args,
                title,
                client=selected_client,
                instruments_only=True,
            )
        return _metadata_result(args, title, client=selected_client)
    if args.command in {"search", "browse"}:
        return _search_result(
            args,
            TITLES_BY_KEY[args.county],
            client=selected_client,
            log_results=log_results,
        )
    if args.command == "detail":
        return _detail_result(
            args,
            client=selected_client,
            log_results=log_results,
        )
    if args.command == "probe":
        return _probe_payload(args, client=selected_client)
    raise ValueError(f"unknown command: {args.command}")


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    rows = payload.get("records")
    if isinstance(rows, list):
        result_count = len(rows)
    else:
        candidate = (
            payload.get("titles")
            or payload.get("alternatives")
            or payload.get("components")
            or []
        )
        result_count = len(candidate) if isinstance(candidate, list) else 0
    if write_output(
        payload,
        args,
        summary=f"Washington Digital Archives land {args.command}",
        result_count=result_count,
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command in {"sources", "inventory"} and "title_count" in payload:
        print(
            "Washington Digital Archives recorded land: "
            f"{payload['title_count']} titles, "
            f"{payload['record_count']:,} index records, "
            f"{payload['county_gap_count']} county alternatives"
        )
        return
    if args.command == "alternatives":
        for record in payload["alternatives"]:
            print(
                f"{record['county_key']} | {record['platform']} | "
                f"{record['observed_access_state']}"
            )
        return
    if args.command == "probe":
        print(f"Washington Digital Archives probe: {payload['status']}")
        for component in payload["components"]:
            print(f"  {component['operation']} | {component['status']}")
        return
    print(
        f"Washington Digital Archives {args.command}: "
        f"{payload.get('status', 'ok')} ({result_count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county", required=True, choices=sorted(TITLES_BY_KEY))
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Optional caller-selected result bound; omitted exhausts the "
            "native result pages"
        ),
    )
    parser.add_argument("--cursor")
    parser.add_argument(
        "--page-size",
        type=int,
        choices=NATIVE_PAGE_SIZES,
        default=DEFAULT_PAGE_SIZE,
    )
    parser.add_argument("--sort", choices=sorted(SORT_COLUMNS))
    parser.add_argument("--direction", choices=("asc", "desc"))
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Washington State Archives Digital Archives recorded-land "
            "indexes, title metadata, and record details"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Show the verified series inventory and county recorder alternatives",
    )
    add_output_args(sources)

    inventory = sub.add_parser(
        "inventory",
        help="Show or refresh the official record-series title inventory",
    )
    inventory.add_argument("--refresh", action="store_true")
    inventory.add_argument(
        "--details",
        action="store_true",
        help="Fetch title-detail metadata for the refreshed title list",
    )
    inventory.add_argument(
        "--max-titles",
        type=int,
        help=(
            "Optional caller-selected title-detail bound; omitted fetches "
            "every discovered title when --details is used"
        ),
    )
    _add_transport_args(inventory)

    metadata = sub.add_parser(
        "metadata",
        help="Show one county title and its search/document operation metadata",
    )
    metadata.add_argument("--county", required=True, choices=sorted(TITLES_BY_KEY))
    metadata.add_argument("--refresh", action="store_true")
    _add_transport_args(metadata)

    instruments = sub.add_parser(
        "instruments",
        help="Fetch the title's official Document Types vocabulary",
    )
    instruments.add_argument(
        "--county",
        required=True,
        choices=sorted(TITLES_BY_KEY),
    )
    _add_transport_args(instruments)

    alternatives = sub.add_parser(
        "alternatives",
        help="Show official recorder paths for counties absent from series 14",
    )
    alternatives.add_argument("--county", choices=sorted(ALTERNATIVES_BY_KEY))
    add_output_args(alternatives)

    search = sub.add_parser(
        "search",
        help="Search a county title by native party, addition, and year controls",
    )
    search.add_argument("--last-name")
    search.add_argument("--first-name")
    search.add_argument("--middle-name")
    search.add_argument("--party-role", choices=("grantor", "grantee"))
    search.add_argument("--addition")
    search.add_argument("--start-year", type=int)
    search.add_argument("--end-year", type=int)
    search.add_argument("--soundex", action="store_true")
    _add_search_args(search)

    browse = sub.add_parser(
        "browse",
        help="Browse one county title through the archive's native Browse operation",
    )
    _add_search_args(browse)

    detail = sub.add_parser(
        "detail",
        help="Fetch one stable archive record detail and digital-object state",
    )
    detail.add_argument("record_id")
    _add_transport_args(detail)

    probe = sub.add_parser(
        "probe",
        help="Run bounded inventory, title, search, and detail sentinels",
    )
    probe.add_argument("--county", choices=sorted(TITLES_BY_KEY), default="adams")
    probe.add_argument(
        "--operations",
        default="inventory,title,search,detail",
        help="Comma-separated inventory,title,search,detail,all_titles",
    )
    probe.add_argument("--all-titles", action="store_true")
    _add_transport_args(probe)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    if (
        getattr(args, "limit", None) is not None
        and args.limit <= 0
    ):
        parser.error("--limit must be positive")
    if (
        getattr(args, "max_titles", None) is not None
        and args.max_titles <= 0
    ):
        parser.error("--max-titles must be positive")
    if args.command == "search":
        selectors = (
            args.last_name,
            args.first_name,
            args.middle_name,
            args.party_role,
            args.addition,
            args.start_year,
            args.end_year,
        )
        if not any(value is not None and value != "" for value in selectors):
            parser.error("search needs a party, addition, role, or year selector")
    start_year = getattr(args, "start_year", None)
    end_year = getattr(args, "end_year", None)
    for label, year in (("start", start_year), ("end", end_year)):
        if year is not None and not 1000 <= year <= 9999:
            parser.error(f"--{label}-year must be a four-digit year")
    if start_year is not None and end_year is not None and start_year > end_year:
        parser.error("--start-year must not be after --end-year")
    record_id = getattr(args, "record_id", None)
    if record_id is not None and not re.fullmatch(r"[A-Fa-f0-9]{32}", record_id):
        parser.error("record_id must be the 32-character archive record identifier")
    operations = getattr(args, "operations", "")
    if operations:
        allowed = {"inventory", "title", "search", "detail", "all_titles"}
        selected = {
            operation.strip().lower()
            for operation in operations.split(",")
            if operation.strip()
        }
        unknown = selected - allowed
        if unknown:
            parser.error(f"unknown probe operations: {', '.join(sorted(unknown))}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    try:
        value = execute(args)
    except ValueError as error:
        parser.error(str(error))
    _emit(value, args)


if __name__ == "__main__":
    main()
