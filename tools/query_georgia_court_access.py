#!/usr/bin/env python3
"""Query Georgia AOC's e-access and e-filing court directories.

The two official pages are complementary routing snapshots:

* e-access maps courts to account-backed case-search providers;
* e-file maps courts to filing providers and their published state.

Neither directory operation performs a case search or initiates a filing.

Examples:
    uv run python tools/query_georgia_court_access.py sources --json
    uv run python tools/query_georgia_court_access.py manifest \
        --source us-ga-aoc-eaccess-court-records-directory --json
    uv run python tools/query_georgia_court_access.py search Fulton \
        --source us-ga-aoc-eaccess-court-records-directory --json
    uv run python tools/query_georgia_court_access.py search "*" \
        --source us-ga-aoc-efile-court-records-directory \
        --provider odyssey_efilega --published-state mandatory --json
    uv run python tools/query_georgia_court_access.py providers \
        --source us-ga-aoc-efile-court-records-directory --json
    uv run python tools/query_georgia_court_access.py probe \
        --source us-ga-aoc-eaccess-court-records-directory --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

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
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from tools.query_georgia_property_sources import (
        COUNTY_GEOIDS as GEORGIA_COUNTY_GEOIDS,
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
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from query_georgia_property_sources import (
        COUNTY_GEOIDS as GEORGIA_COUNTY_GEOIDS,
    )


EACCESS_SOURCE_ID = "us-ga-aoc-eaccess-court-records-directory"
EFILE_SOURCE_ID = "us-ga-aoc-efile-court-records-directory"
SOURCE_IDS = (EACCESS_SOURCE_ID, EFILE_SOURCE_ID)
STATE_CODE = "GA"
STATE_GEOID = "13"
AUTHORITY = (
    "Judicial Council of Georgia, Administrative Office of the Courts"
)

EACCESS_URL = "https://georgiacourts.gov/eaccess-court-records/"
EFILE_URL = "https://georgiacourts.gov/efile-court-records/"
EACCESS_VENDOR_PUBLISHED_URL = (
    "https://georgiacourts.gov/e-access-to-court-records/vendors/"
)
EACCESS_VENDOR_URL = (
    "https://georgiacourts.gov/eaccess-court-records/vendors/"
)
LOCAL_COURT_DIRECTORY_URL = (
    "https://georgiacourts.gov/georgia-courts-directory/"
)
GSCCCA_URL = "https://www.gsccca.org/"

PEACHCOURT_URL = "https://peachcourt.com/Account/Access"
RESEARCHGA_URL = (
    "https://researchga.tylerhost.net/CourtRecordsSearch/Home#!/home"
)
ODYSSEY_EFILEGA_URL = (
    "http://efilega.tylertech.cloud/OfsEfsp/ui/landing"
)
GREENFILING_URL = "https://georgia.greenfiling.com/ga/"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_LIMIT = 100
DEFAULT_MAX_ATTEMPTS = 3
MAX_HTML_BYTES = 5_000_000
CURSOR_VERSION = "v1"
CURSOR_RE = re.compile(
    r"^ga-aoc-court-access:v1:source:(?P<source>[a-z0-9-]+):"
    r"query:(?P<query>[0-9a-f]{16}):"
    r"snapshot:(?P<snapshot>[0-9a-f]{16}):"
    r"offset:(?P<offset>[0-9]+)$"
)

COUNTY_GEOIDS = dict(GEORGIA_COUNTY_GEOIDS)
COURT_LABEL_RE = re.compile(
    r"^(?P<county>.+?) (?P<court_class>State|Superior)"
    r"(?: (?P<division>.+))?$"
)

PROVIDER_DEFINITIONS: Mapping[str, Mapping[str, str]] = {
    "peachcourt": {
        "label": "Peach Court",
        "url": PEACHCOURT_URL,
    },
    "researchga": {
        "label": "reSearchGA",
        "url": RESEARCHGA_URL,
    },
    "odyssey_efilega": {
        "label": "Odyssey eFileGA",
        "url": ODYSSEY_EFILEGA_URL,
    },
    "greenfiling_infotrack": {
        "label": "GreenFiling/InfoTrack",
        "url": GREENFILING_URL,
    },
}
EFILE_PROVIDER_IDS_BY_LABEL = {
    "Odyssey eFileGA": "odyssey_efilega",
    "Peach Court": "peachcourt",
    "GreenFiling/InfoTrack": "greenfiling_infotrack",
}
KNOWN_PROVIDER_IDS = tuple(PROVIDER_DEFINITIONS)
KNOWN_PUBLISHED_STATES = (
    "account_required",
    "mandatory",
    "available",
    "not_listed",
)

SOURCE_METADATA_BY_ID = {
    EACCESS_SOURCE_ID: SourceMetadata(
        source_id=EACCESS_SOURCE_ID,
        name="Georgia AOC E-Access Court Records Directory",
        source_role="official_statewide_case_access_provider_directory",
        base_url=EACCESS_URL,
        dataset_id="ga-aoc:eaccess-court-records-directory",
        metadata={
            "authority": AUTHORITY,
            "access": "anonymous_directory_account_backed_destinations",
            "coverage": "current_directory_snapshot",
            "case_search_completed": False,
        },
    ),
    EFILE_SOURCE_ID: SourceMetadata(
        source_id=EFILE_SOURCE_ID,
        name="Georgia AOC E-File Court Records Directory",
        source_role="official_statewide_efile_provider_directory",
        base_url=EFILE_URL,
        dataset_id="ga-aoc:efile-court-records-directory",
        metadata={
            "authority": AUTHORITY,
            "access": "anonymous_directory_account_backed_destinations",
            "coverage": "current_directory_snapshot",
            "filing_initiated": False,
            "case_evidence": False,
        },
    ),
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_court_provider_directories"},
)

SOURCE_WARNINGS = {
    EACCESS_SOURCE_ID: (
        "The e-access page is a current provider directory and acquisition "
        "handoff; it does not contain case-search results.",
        "The page states that a provider account is required to search court "
        "records.",
        "Some rows point to a provider-selection page whose published heading "
        "says e-Filing Vendor even though the parent directory is e-access.",
        "Two current Chatham routes use source-published HTTP while the other "
        "reSearchGA routes use HTTPS; exact published URLs are retained.",
        "Local courts and clerks remain separate custodians and alternatives.",
    ),
    EFILE_SOURCE_ID: (
        "The e-file page is a current filing-provider map and does not contain "
        "case evidence or prove that a filing occurred.",
        "The page states that an account is required to initiate a new case "
        "filing.",
        "Blank provider cells mean no route is listed in this snapshot; they "
        "are not treated as a failed or unavailable provider.",
        "Published Mandatory and Available labels are retained per provider.",
        "Odyssey eFileGA links currently use source-published HTTP and are not "
        "rewritten by the adapter.",
        "The page prose mentions voluntary and mandatory dates, but the "
        "current table publishes state labels without date fields.",
    ),
}


class GeorgiaCourtAccessSelectionError(ValueError):
    """Structured caller selection or cursor error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class HTMLArtifact:
    """One retrieved official HTML artifact."""

    content: bytes
    source_url: str
    status_code: int
    headers: Mapping[str, str]

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class SourceSnapshot:
    """Parsed records plus artifacts for one directory snapshot."""

    source_id: str
    records: tuple[Mapping[str, Any], ...]
    artifacts: tuple[HTMLArtifact, ...]
    requests_made: int
    snapshot_sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("\xa0", " ").split())
    return cleaned or None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unknown"


def _source_prefix(source_id: str) -> str:
    if source_id == EACCESS_SOURCE_ID:
        return "GA-AOC-EACCESS"
    if source_id == EFILE_SOURCE_ID:
        return "GA-AOC-EFILE"
    raise ValueError(f"unknown Georgia court-access source {source_id}")


def _court_identity(native_label: str) -> dict[str, Any]:
    label = _text(native_label)
    if not label:
        raise SourceSchemaError("Georgia court directory row has no court label")
    without_suffix = (
        label[: -len(" Court")] if label.endswith(" Court") else label
    )
    match = COURT_LABEL_RE.fullmatch(without_suffix)
    if match is None:
        raise SourceSchemaError(
            "Georgia court directory label cannot be classified",
            details={"native_label": label},
        )
    county_name = match.group("county")
    county_geoid = COUNTY_GEOIDS.get(county_name)
    if county_geoid is None:
        raise SourceSchemaError(
            "Georgia court directory row names an unknown county",
            details={"native_label": label, "county_name": county_name},
        )
    court_class = match.group("court_class").casefold()
    division = _text(match.group("division"))
    court_id = f"GA-COURT:{county_geoid}:{court_class}"
    return {
        "court_id": court_id,
        "native_label": label,
        "canonical_label": (
            f"{county_name} {court_class.title()} Court"
        ),
        "county_name": county_name,
        "county_geoid": county_geoid,
        "court_class": court_class,
        "division": division.casefold() if division else None,
    }


def _provider_definition(
    provider_id: str,
    *,
    published_label: str | None = None,
    published_url: str | None = None,
) -> dict[str, Any]:
    definition = PROVIDER_DEFINITIONS.get(provider_id, {})
    return {
        "provider_id": provider_id,
        "provider_label": (
            published_label or definition.get("label") or provider_id
        ),
        "provider_url": published_url or definition.get("url"),
    }


def _provider_id_for_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    if host == "peachcourt.com":
        return "peachcourt"
    if host == "researchga.tylerhost.net":
        return "researchga"
    if host == "efilega.tylertech.cloud":
        return "odyssey_efilega"
    if host == "georgia.greenfiling.com":
        return "greenfiling_infotrack"
    return f"provider-{_slug(host or url)}"


def _provider_id_for_efile_label(label: str) -> str:
    return EFILE_PROVIDER_IDS_BY_LABEL.get(label, _slug(label))


def _published_state(label: str | None) -> tuple[str, bool]:
    if label is None:
        return "not_listed", True
    normalized = label.casefold()
    if normalized == "mandatory":
        return "mandatory", True
    if normalized == "available":
        return "available", True
    return _slug(label), False


def _route_descriptor(url: str, *, route_kind: str) -> dict[str, Any]:
    parsed = urlparse(url)
    return {
        "url": url,
        "scheme": parsed.scheme.casefold(),
        "host": parsed.netloc.casefold(),
        "route_kind": route_kind,
        "source_published_http": parsed.scheme.casefold() == "http",
    }


def _official_alternatives(source_id: str) -> list[dict[str, Any]]:
    counterpart = (
        EFILE_SOURCE_ID
        if source_id == EACCESS_SOURCE_ID
        else EACCESS_SOURCE_ID
    )
    counterpart_url = (
        EFILE_URL if counterpart == EFILE_SOURCE_ID else EACCESS_URL
    )
    return [
        {
            "source_id": "us-ga-aoc-court-personnel-directory",
            "name": "Georgia AOC Court Personnel Directory",
            "url": LOCAL_COURT_DIRECTORY_URL,
            "role": (
                "official local court and clerk contact and site discovery"
            ),
            "dataset_equivalent": False,
        },
        {
            "source_id": counterpart,
            "name": (
                "Georgia AOC complementary provider directory"
            ),
            "url": counterpart_url,
            "role": (
                "filing-provider routing"
                if counterpart == EFILE_SOURCE_ID
                else "account-backed case-access routing"
            ),
            "dataset_equivalent": False,
        },
        {
            "source_id": "us-ga-gsccca-real-estate-index",
            "name": (
                "Georgia Superior Court Clerks' Cooperative Authority"
            ),
            "url": GSCCCA_URL,
            "role": "separate clerk-administered indices and services",
            "dataset_equivalent": False,
        },
    ]


def _soup(artifact: HTMLArtifact, *, expected_heading: str) -> BeautifulSoup:
    soup = BeautifulSoup(artifact.text, "html.parser")
    heading = soup.find("h1")
    if heading is None or expected_heading.casefold() not in (
        heading.get_text(" ", strip=True).casefold()
    ):
        raise SourceSchemaError(
            "Georgia AOC page heading changed",
            url=artifact.source_url,
            details={
                "expected_heading": expected_heading,
                "observed_heading": (
                    heading.get_text(" ", strip=True)
                    if heading is not None
                    else None
                ),
            },
        )
    return soup


def parse_eaccess_vendor_options(
    artifact: HTMLArtifact,
) -> tuple[dict[str, Any], ...]:
    """Parse provider choices from the official selection-page handoff."""

    soup = _soup(artifact, expected_heading="Vendors")
    selection_copy = next(
        (
            text
            for node in soup.find_all(["h2", "h3", "p"])
            if (text := _text(node.get_text(" ", strip=True)))
            and "vendor" in text.casefold()
        ),
        None,
    )
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        provider_id = _provider_id_for_url(href)
        if provider_id not in {"peachcourt", "researchga"}:
            continue
        if provider_id in seen:
            continue
        seen.add(provider_id)
        image = anchor.find("img")
        source_label = (
            _text(image.get("alt")) if isinstance(image, Tag) else None
        )
        description = _text(
            anchor.get("aria-label")
            or anchor.get("aira-label")
            or (
                anchor.parent.get("aria-label")
                if isinstance(anchor.parent, Tag)
                else None
            )
        )
        definition = _provider_definition(
            provider_id,
            published_label=source_label,
            published_url=href,
        )
        options.append(
            {
                **definition,
                "description": description,
                "source_url": artifact.source_url,
                "route_relationship": "provider_selection_option",
                "account_required": True,
                "source_page_copy": selection_copy,
            }
        )
    if not options:
        raise SourceSchemaError(
            "Georgia e-access vendor page has no provider options",
            url=artifact.source_url,
        )
    return tuple(options)


def parse_eaccess_directory(
    artifact: HTMLArtifact,
    *,
    vendor_options: Sequence[Mapping[str, Any]],
    vendor_artifact: HTMLArtifact,
) -> tuple[dict[str, Any], ...]:
    """Parse the current account-backed case-access routing table."""

    soup = _soup(artifact, expected_heading="E-Access to Court Records")
    page_text = soup.get_text(" ", strip=True)
    if (
        "must have an account to search court records"
        not in page_text.casefold()
    ):
        raise SourceSchemaError(
            "Georgia e-access account notice changed",
            url=artifact.source_url,
        )
    tables = [
        table
        for table in soup.find_all("table")
        if table.find("a", href=True) is not None
    ]
    if len(tables) != 1:
        raise SourceSchemaError(
            "Georgia e-access directory table count changed",
            url=artifact.source_url,
            details={"table_count": len(tables)},
        )

    records: list[dict[str, Any]] = []
    seen_courts: set[str] = set()
    ordinal = 0
    for row_index, row in enumerate(tables[0].find_all("tr"), start=1):
        cells = row.find_all("td", recursive=False)
        if not cells:
            cells = row.find_all("td")
        for column_index, cell in enumerate(cells, start=1):
            anchors = cell.find_all("a", href=True)
            if not anchors:
                continue
            if len(anchors) != 1:
                raise SourceSchemaError(
                    "Georgia e-access court cell has multiple routes",
                    url=artifact.source_url,
                    details={
                        "table_row": row_index,
                        "table_column": column_index,
                    },
                )
            anchor = anchors[0]
            native_label = _text(anchor.get_text(" ", strip=True))
            published_url = str(anchor["href"]).strip()
            court = _court_identity(native_label or "")
            court_id = str(court["court_id"])
            if court_id in seen_courts:
                raise SourceSchemaError(
                    "Georgia e-access directory repeats a canonical court",
                    url=artifact.source_url,
                    details={"court_id": court_id},
                )
            seen_courts.add(court_id)
            ordinal += 1

            parsed_route = urlparse(published_url)
            selection_page = (
                parsed_route.netloc.casefold() == "georgiacourts.gov"
                and parsed_route.path.rstrip("/").endswith(
                    "court-records/vendors"
                )
            )
            if selection_page:
                provider_routes = [
                    {
                        **dict(option),
                        "published_state": "account_required",
                        "published_label": "Account required",
                        "route_listed": True,
                    }
                    for option in vendor_options
                ]
                route_kind = "provider_selection_page"
            else:
                provider_id = _provider_id_for_url(published_url)
                provider = _provider_definition(
                    provider_id,
                    published_url=published_url,
                )
                provider_routes = [
                    {
                        **provider,
                        "description": None,
                        "source_url": artifact.source_url,
                        "route_relationship": "direct_directory_route",
                        "account_required": True,
                        "published_state": "account_required",
                        "published_label": "Account required",
                        "route_listed": True,
                    }
                ]
                route_kind = "direct_provider"

            canonical_ref = (
                f"{_source_prefix(EACCESS_SOURCE_ID)}:{court_id}"
            )
            records.append(
                {
                    "canonical_ref": canonical_ref,
                    "source_id": EACCESS_SOURCE_ID,
                    "record_kind": "case_access_acquisition_handoff",
                    "court": court,
                    "published_route": _route_descriptor(
                        published_url,
                        route_kind=route_kind,
                    ),
                    "provider_routes": provider_routes,
                    "access": {
                        "account_required": True,
                        "directory_handoff": True,
                        "case_search_completed": False,
                    },
                    "snapshot_only": True,
                    "source_url": artifact.source_url,
                    "source_document_sha256": artifact.sha256,
                    "provider_directory_source_url": (
                        vendor_artifact.source_url
                        if selection_page
                        else None
                    ),
                    "provider_directory_sha256": (
                        vendor_artifact.sha256 if selection_page else None
                    ),
                    "official_alternatives": _official_alternatives(
                        EACCESS_SOURCE_ID
                    ),
                    "projection": {
                        "projectable_as_case": False,
                        "projectable_as_filing": False,
                    },
                    "raw": {
                        "native_label": native_label,
                        "published_url": published_url,
                        "directory_ordinal": ordinal,
                        "table_row": row_index,
                        "table_column": column_index,
                    },
                }
            )
    if not records:
        raise SourceSchemaError(
            "Georgia e-access directory has no court rows",
            url=artifact.source_url,
        )
    return tuple(records)


def parse_efile_directory(
    artifact: HTMLArtifact,
) -> tuple[dict[str, Any], ...]:
    """Parse the current court-by-provider e-filing table."""

    soup = _soup(artifact, expected_heading="E-File Court Records")
    page_text = soup.get_text(" ", strip=True)
    if (
        "must have an account to initiate a new case filing"
        not in page_text.casefold()
    ):
        raise SourceSchemaError(
            "Georgia e-file account notice changed",
            url=artifact.source_url,
        )
    tables = [
        table
        for table in soup.find_all("table")
        if "Court by County" in table.get_text(" ", strip=True)
    ]
    if len(tables) != 1:
        raise SourceSchemaError(
            "Georgia e-file directory table count changed",
            url=artifact.source_url,
            details={"table_count": len(tables)},
        )
    rows = tables[0].find_all("tr")
    if not rows:
        raise SourceSchemaError(
            "Georgia e-file directory table has no rows",
            url=artifact.source_url,
        )
    headers = [
        _text(cell.get_text(" ", strip=True))
        for cell in rows[0].find_all(["th", "td"])
    ]
    if not headers or headers[0] != "Court by County":
        raise SourceSchemaError(
            "Georgia e-file directory headers changed",
            url=artifact.source_url,
            details={"headers": headers},
        )
    provider_labels = [
        str(label) for label in headers[1:] if label is not None
    ]
    if not provider_labels:
        raise SourceSchemaError(
            "Georgia e-file directory has no provider columns",
            url=artifact.source_url,
        )

    records: list[dict[str, Any]] = []
    seen_courts: set[str] = set()
    for ordinal, row in enumerate(rows[1:], start=1):
        cells = row.find_all("td")
        if not cells:
            continue
        if len(cells) != len(headers):
            raise SourceSchemaError(
                "Georgia e-file row width changed",
                url=artifact.source_url,
                details={
                    "directory_ordinal": ordinal,
                    "cell_count": len(cells),
                    "header_count": len(headers),
                },
            )
        native_label = _text(cells[0].get_text(" ", strip=True))
        court = _court_identity(native_label or "")
        court_id = str(court["court_id"])
        if court_id in seen_courts:
            raise SourceSchemaError(
                "Georgia e-file directory repeats a canonical court",
                url=artifact.source_url,
                details={"court_id": court_id},
            )
        seen_courts.add(court_id)

        provider_states: list[dict[str, Any]] = []
        provider_routes: list[dict[str, Any]] = []
        raw_cells: list[dict[str, Any]] = []
        for label, cell in zip(provider_labels, cells[1:], strict=True):
            provider_id = _provider_id_for_efile_label(label)
            anchor = cell.find("a", href=True)
            published_label = _text(cell.get_text(" ", strip=True))
            provider_url = (
                str(anchor["href"]).strip()
                if isinstance(anchor, Tag)
                else None
            )
            state, recognized = _published_state(published_label)
            provider = _provider_definition(
                provider_id,
                published_label=label,
                published_url=provider_url,
            )
            entry = {
                **provider,
                "published_state": state,
                "published_label": published_label,
                "recognized_state": recognized,
                "route_listed": provider_url is not None,
                "account_required": (
                    True if provider_url is not None else None
                ),
                "source_published_http": (
                    bool(
                        provider_url
                        and urlparse(provider_url).scheme.casefold()
                        == "http"
                    )
                ),
            }
            provider_states.append(entry)
            if provider_url is not None:
                provider_routes.append(dict(entry))
            raw_cells.append(
                {
                    "provider_label": label,
                    "published_label": published_label,
                    "published_url": provider_url,
                }
            )

        canonical_ref = f"{_source_prefix(EFILE_SOURCE_ID)}:{court_id}"
        records.append(
            {
                "canonical_ref": canonical_ref,
                "source_id": EFILE_SOURCE_ID,
                "record_kind": "efile_provider_directory_entry",
                "court": court,
                "provider_states": provider_states,
                "provider_routes": provider_routes,
                "filing": {
                    "account_required_to_initiate": True,
                    "filing_initiated": False,
                    "case_evidence": False,
                },
                "snapshot_only": True,
                "source_url": artifact.source_url,
                "source_document_sha256": artifact.sha256,
                "official_alternatives": _official_alternatives(
                    EFILE_SOURCE_ID
                ),
                "projection": {
                    "projectable_as_case": False,
                    "projectable_as_filing": False,
                },
                "raw": {
                    "native_label": native_label,
                    "directory_ordinal": ordinal,
                    "provider_cells": raw_cells,
                },
            }
        )
    if not records:
        raise SourceSchemaError(
            "Georgia e-file directory has no court rows",
            url=artifact.source_url,
        )
    return tuple(records)


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return _text(value)
    return None


def _retry_after(response: Any) -> float | None:
    value = _response_header(response, "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _checked_status(response: Any, *, url: str) -> None:
    status_code = int(getattr(response, "status_code", 0))
    response_text = str(getattr(response, "text", ""))
    if status_code == 429:
        raise RateLimitedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {401, 403}:
        raise RestrictedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code == 451:
        raise TermsBlockedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(
            status_code,
            url=url,
            response_text=response_text,
        )
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(
            status_code,
            url=url,
            response_text=response_text,
        )


class GeorgiaCourtAccessClient:
    """Paced client for the official Georgia AOC directory pages."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.request_count = 0
        self.headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Ithildin public-record source adapter",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def page(self, url: str) -> HTMLArtifact:
        response: Any | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    "GET",
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Georgia AOC directory request failed",
                        url=url,
                        details={"error": str(error), "attempts": attempt},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            _checked_status(response, url=url)
            raw_content = getattr(response, "content", None)
            if isinstance(raw_content, bytes):
                content = raw_content
            else:
                content = str(getattr(response, "text", "")).encode()
            if not content:
                raise SourceSchemaError(
                    "Georgia AOC directory returned an empty document",
                    url=url,
                )
            if len(content) > MAX_HTML_BYTES:
                raise SourceSchemaError(
                    "Georgia AOC directory document exceeds the adapter bound",
                    url=url,
                    details={
                        "byte_length": len(content),
                        "maximum": MAX_HTML_BYTES,
                    },
                )
            return HTMLArtifact(
                content=content,
                source_url=str(getattr(response, "url", url)),
                status_code=status_code,
                headers=dict(getattr(response, "headers", {}) or {}),
            )
        raise TransportError(
            "Georgia AOC directory request produced no response",
            url=url,
        )


def load_source_snapshot(
    client: GeorgiaCourtAccessClient | Any,
    source_id: str,
) -> SourceSnapshot:
    """Fetch and parse one source with its bounded supporting artifacts."""

    before = int(getattr(client, "request_count", 0))
    if source_id == EACCESS_SOURCE_ID:
        main = client.page(EACCESS_URL)
        vendors = client.page(EACCESS_VENDOR_PUBLISHED_URL)
        options = parse_eaccess_vendor_options(vendors)
        records = parse_eaccess_directory(
            main,
            vendor_options=options,
            vendor_artifact=vendors,
        )
        artifacts = (main, vendors)
    elif source_id == EFILE_SOURCE_ID:
        main = client.page(EFILE_URL)
        records = parse_efile_directory(main)
        artifacts = (main,)
    else:
        raise GeorgiaCourtAccessSelectionError(
            "unknown_source",
            f"unknown Georgia AOC directory source {source_id}",
        )
    requests_made = int(getattr(client, "request_count", 0)) - before
    base_requests = 2 if source_id == EACCESS_SOURCE_ID else 1
    snapshot_sha256 = sha256_fingerprint(
        {
            "source_id": source_id,
            "artifacts": [
                {
                    "source_url": artifact.source_url,
                    "sha256": artifact.sha256,
                }
                for artifact in artifacts
            ],
        }
    )
    return SourceSnapshot(
        source_id=source_id,
        records=records,
        artifacts=artifacts,
        requests_made=requests_made or base_requests,
        snapshot_sha256=snapshot_sha256,
    )


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "canonical_ref": f"STATECOURT:{EACCESS_SOURCE_ID}/source",
            "source_id": EACCESS_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA_BY_ID[EACCESS_SOURCE_ID].name,
            "authority": AUTHORITY,
            "official_url": EACCESS_URL,
            "operations": ["manifest", "search", "providers", "probe"],
            "record_grain": "court_case_access_acquisition_handoff",
            "case_search_completed": False,
        },
        {
            "canonical_ref": f"STATECOURT:{EFILE_SOURCE_ID}/source",
            "source_id": EFILE_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA_BY_ID[EFILE_SOURCE_ID].name,
            "authority": AUTHORITY,
            "official_url": EFILE_URL,
            "operations": ["manifest", "search", "providers", "probe"],
            "record_grain": "court_efile_provider_directory_entry",
            "filing_initiated": False,
            "case_evidence": False,
        },
    ]


def source_manifest(source_id: str) -> dict[str, Any]:
    """Describe one verified directory contract and its complements."""

    common = {
        "canonical_ref": f"STATECOURT:{source_id}/manifest",
        "source_id": source_id,
        "record_kind": "source_manifest",
        "source": SOURCE_METADATA_BY_ID[source_id].to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "authority": AUTHORITY,
        "operations": {
            "search": {
                "filters": [
                    "query",
                    "county",
                    "court_class",
                    "provider",
                    "published_state",
                ],
                "pagination": (
                    "source-query-and-snapshot-bound local cursor"
                ),
            },
            "providers": {
                "result_grain": "source_provider_summary",
            },
            "probe": {
                "artifact_requests_per_attempt": (
                    2 if source_id == EACCESS_SOURCE_ID else 1
                ),
                "default_retry_bound": (
                    (2 if source_id == EACCESS_SOURCE_ID else 1)
                    * DEFAULT_MAX_ATTEMPTS
                ),
            },
        },
        "stable_identity": ["canonical_ref"],
        "court_identity": {
            "fields": ["county_geoid", "court_class"],
            "format": "GA-COURT:<county_geoid>:<court_class>",
            "native_label_preserved": True,
            "division_preserved_separately": True,
        },
        "snapshot_semantics": {
            "snapshot_only": True,
            "case_projection": False,
            "filing_projection": False,
        },
        "official_complements": _official_alternatives(source_id),
        "coverage_notes": list(SOURCE_WARNINGS[source_id]),
    }
    if source_id == EACCESS_SOURCE_ID:
        return {
            **common,
            "published_pages": {
                "directory": EACCESS_URL,
                "provider_selection_published_url": (
                    EACCESS_VENDOR_PUBLISHED_URL
                ),
                "provider_selection_canonical_url": EACCESS_VENDOR_URL,
            },
            "record_kind_emitted": "case_access_acquisition_handoff",
            "access_contract": {
                "account_required": True,
                "case_search_completed": False,
            },
            "providers": [
                _provider_definition("peachcourt"),
                _provider_definition("researchga"),
            ],
            "observed_source_anomalies": [
                {
                    "observation": (
                        "provider-selection page copy says e-Filing Vendor "
                        "inside the e-access route"
                    ),
                    "preserved_fields": [
                        "published_route",
                        "provider_routes",
                    ],
                },
                {
                    "observation": (
                        "source publishes HTTP for two current Chatham "
                        "reSearchGA routes and HTTPS for the others"
                    ),
                    "preserved_field": (
                        "published_route.source_published_http"
                    ),
                },
            ],
        }
    if source_id == EFILE_SOURCE_ID:
        return {
            **common,
            "published_pages": {"directory": EFILE_URL},
            "record_kind_emitted": "efile_provider_directory_entry",
            "filing_contract": {
                "account_required_to_initiate": True,
                "filing_initiated": False,
                "case_evidence": False,
            },
            "provider_columns": [
                _provider_definition(provider_id)
                for provider_id in (
                    "odyssey_efilega",
                    "peachcourt",
                    "greenfiling_infotrack",
                )
            ],
            "published_states": [
                "mandatory",
                "available",
                "not_listed",
            ],
            "observed_source_anomalies": [
                {
                    "observation": (
                        "blank provider cells are source non-listings, not "
                        "provider failures"
                    ),
                    "adapter_state": "not_listed",
                },
                {
                    "observation": (
                        "Odyssey eFileGA destinations are published as HTTP"
                    ),
                    "preserved_field": "source_published_http",
                },
                {
                    "observation": (
                        "page prose mentions voluntary and mandatory dates "
                        "but current rows publish state labels without dates"
                    ),
                    "date_fields_emitted": False,
                },
                {
                    "observation": (
                        "Chatham Superior is labeled Chatham Superior Civil "
                        "Court"
                    ),
                    "identity": (
                        "same canonical superior-court ID with civil division"
                    ),
                },
            ],
        }
    raise GeorgiaCourtAccessSelectionError(
        "unknown_source",
        f"unknown Georgia AOC directory source {source_id}",
    )


def _provider_summary_records(
    snapshot: SourceSnapshot,
) -> list[dict[str, Any]]:
    records = list(snapshot.records)
    provider_ids = sorted(
        {
            str(provider["provider_id"])
            for record in records
            for provider in record.get(
                (
                    "provider_states"
                    if snapshot.source_id == EFILE_SOURCE_ID
                    else "provider_routes"
                ),
                (),
            )
        }
    )
    summaries: list[dict[str, Any]] = []
    for provider_id in provider_ids:
        state_counts: Counter[str] = Counter()
        relationship_counts: Counter[str] = Counter()
        listed_courts: set[str] = set()
        provider_urls: set[str] = set()
        provider_label: str | None = None
        for record in records:
            entries = record.get(
                (
                    "provider_states"
                    if snapshot.source_id == EFILE_SOURCE_ID
                    else "provider_routes"
                ),
                (),
            )
            for entry in entries:
                if entry.get("provider_id") != provider_id:
                    continue
                provider_label = (
                    provider_label or entry.get("provider_label")
                )
                state_counts[str(entry.get("published_state"))] += 1
                relationship = entry.get("route_relationship")
                if relationship:
                    relationship_counts[str(relationship)] += 1
                if entry.get("route_listed") is not False:
                    listed_courts.add(record["court"]["court_id"])
                if entry.get("provider_url"):
                    provider_urls.add(str(entry["provider_url"]))
        summaries.append(
            {
                "canonical_ref": (
                    f"{_source_prefix(snapshot.source_id)}:"
                    f"PROVIDER:{provider_id}"
                ),
                "source_id": snapshot.source_id,
                "record_kind": "court_provider_summary",
                "provider_id": provider_id,
                "provider_label": (
                    provider_label
                    or _provider_definition(provider_id)["provider_label"]
                ),
                "listed_court_count": len(listed_courts),
                "state_counts": dict(sorted(state_counts.items())),
                "route_relationship_counts": dict(
                    sorted(relationship_counts.items())
                ),
                "provider_urls": sorted(provider_urls),
                "snapshot_only": True,
                "source_url": SOURCE_METADATA_BY_ID[
                    snapshot.source_id
                ].base_url,
                "source_snapshot_sha256": snapshot.snapshot_sha256,
                "projection": {
                    "projectable_as_case": False,
                    "projectable_as_filing": False,
                },
            }
        )
    return summaries


def _selection_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "query": _text(getattr(args, "query_text", None)) or "*",
        "county": _text(getattr(args, "county", None)),
        "court_class": getattr(args, "court_class", None),
        "provider": getattr(args, "provider", None),
        "published_state": getattr(args, "published_state", None),
    }


def _query_fingerprint(
    source_id: str,
    parameters: Mapping[str, Any],
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "source_id": source_id,
                "parameters": dict(parameters),
            }
        ).encode()
    ).hexdigest()[:16]


def _cursor_offset(
    cursor: str | None,
    *,
    source_id: str,
    parameters: Mapping[str, Any],
    snapshot_sha256: str,
) -> int:
    if cursor is None:
        return 0
    match = CURSOR_RE.fullmatch(cursor)
    if match is None:
        raise GeorgiaCourtAccessSelectionError(
            "invalid_cursor",
            "cursor does not match the Georgia court-access cursor format",
        )
    if match.group("source") != source_id:
        raise GeorgiaCourtAccessSelectionError(
            "cursor_source_mismatch",
            "cursor belongs to a different Georgia directory source",
        )
    if match.group("query") != _query_fingerprint(
        source_id,
        parameters,
    ):
        raise GeorgiaCourtAccessSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Georgia directory filters",
        )
    if match.group("snapshot") != snapshot_sha256[:16]:
        raise GeorgiaCourtAccessSelectionError(
            "cursor_snapshot_mismatch",
            "Georgia directory snapshot changed after the cursor was issued",
        )
    return int(match.group("offset"))


def _cursor(
    *,
    source_id: str,
    parameters: Mapping[str, Any],
    snapshot_sha256: str,
    offset: int,
) -> str:
    return (
        f"ga-aoc-court-access:{CURSOR_VERSION}:"
        f"source:{source_id}:"
        f"query:{_query_fingerprint(source_id, parameters)}:"
        f"snapshot:{snapshot_sha256[:16]}:offset:{offset}"
    )


def _record_matches(
    record: Mapping[str, Any],
    parameters: Mapping[str, Any],
) -> bool:
    court = record["court"]
    county = parameters.get("county")
    if county and str(court["county_name"]).casefold() != str(
        county
    ).casefold():
        return False
    court_class = parameters.get("court_class")
    if court_class and court.get("court_class") != court_class:
        return False

    entries = record.get(
        "provider_states",
        record.get("provider_routes", ()),
    )
    provider_id = parameters.get("provider")
    published_state = parameters.get("published_state")
    if provider_id:
        matching_entries = [
            entry
            for entry in entries
            if entry.get("provider_id") == provider_id
        ]
        if not matching_entries:
            return False
        if published_state:
            if not any(
                entry.get("published_state") == published_state
                for entry in matching_entries
            ):
                return False
        elif not any(
            entry.get("route_listed") is not False
            for entry in matching_entries
        ):
            return False
    elif published_state and not any(
        entry.get("published_state") == published_state
        for entry in entries
    ):
        return False

    query_text = str(parameters.get("query") or "*").strip()
    if query_text in {"", "*"}:
        return True
    needle = query_text.casefold()
    haystack = " ".join(
        [
            str(court.get("native_label") or ""),
            str(court.get("canonical_label") or ""),
            str(court.get("county_name") or ""),
            *[
                " ".join(
                    [
                        str(entry.get("provider_id") or ""),
                        str(entry.get("provider_label") or ""),
                        str(entry.get("published_state") or ""),
                    ]
                )
                for entry in entries
            ],
        ]
    ).casefold()
    return needle in haystack


def _search_records(
    snapshot: SourceSnapshot,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    parameters = _selection_parameters(args)
    matched = [
        record
        for record in snapshot.records
        if _record_matches(record, parameters)
    ]
    offset = _cursor_offset(
        args.cursor,
        source_id=snapshot.source_id,
        parameters=parameters,
        snapshot_sha256=snapshot.snapshot_sha256,
    )
    if offset > len(matched):
        raise GeorgiaCourtAccessSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the matching Georgia directory rows",
            details={"offset": offset, "match_count": len(matched)},
        )
    limit = None if args.all else args.limit
    selected = matched[offset:] if limit is None else matched[offset : offset + limit]
    next_offset = offset + len(selected)
    next_cursor = (
        _cursor(
            source_id=snapshot.source_id,
            parameters=parameters,
            snapshot_sha256=snapshot.snapshot_sha256,
            offset=next_offset,
        )
        if next_offset < len(matched)
        else None
    )
    records: list[dict[str, Any]] = []
    observation = {
        "source_record_count": len(snapshot.records),
        "matching_record_count": len(matched),
        "offset": offset,
        "returned_record_count": len(selected),
        "requests_made": snapshot.requests_made,
        "source_snapshot_sha256": snapshot.snapshot_sha256,
    }
    for record in selected:
        records.append(
            {
                **dict(record),
                "selection_context": dict(parameters),
                "query_observation": observation,
            }
        )
    return records, next_cursor


def _superior_coverage(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    published = {
        str(record["court"]["county_name"])
        for record in records
        if record["court"]["court_class"] == "superior"
    }
    return {
        "published_superior_county_count": len(published),
        "missing_superior_counties": sorted(
            set(COUNTY_GEOIDS) - published
        ),
        "unexpected_superior_counties": sorted(
            published - set(COUNTY_GEOIDS)
        ),
    }


def _probe_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    records = list(snapshot.records)
    class_counts = Counter(
        str(record["court"]["court_class"]) for record in records
    )
    coverage = _superior_coverage(records)
    schema_contract: dict[str, Any] = {
        "record_fields": sorted(
            {
                field
                for record in records
                for field in record
            }
        ),
        "court_fields": sorted(
            {
                field
                for record in records
                for field in record["court"]
            }
        ),
        "stable_identity": ["canonical_ref"],
        "snapshot_only": True,
        "case_projection": False,
        "filing_projection": False,
    }
    stable_contract: dict[str, Any] = {
        "source": SOURCE_METADATA_BY_ID[snapshot.source_id].to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "court_identity": {
            "fields": ["county_geoid", "court_class"],
            "format": "GA-COURT:<county_geoid>:<court_class>",
        },
        "record_kind": records[0]["record_kind"],
        "stable_identity": ["canonical_ref"],
        "snapshot_semantics": {
            "snapshot_only": True,
            "case_projection": False,
            "filing_projection": False,
        },
    }
    rolling: dict[str, Any] = {
        "record_count": len(records),
        "court_class_counts": dict(sorted(class_counts.items())),
        **coverage,
        "canonical_court_identity_sha256": sha256_fingerprint(
            sorted(record["court"]["court_id"] for record in records)
        ),
        "source_artifacts": [
            {
                "source_url": artifact.source_url,
                "sha256": artifact.sha256,
                "byte_length": len(artifact.content),
            }
            for artifact in snapshot.artifacts
        ],
    }

    if snapshot.source_id == EACCESS_SOURCE_ID:
        schema_contract.update(
            {
                "published_route_fields": sorted(
                    {
                        field
                        for record in records
                        for field in record["published_route"]
                    }
                ),
                "provider_route_fields": sorted(
                    {
                        field
                        for record in records
                        for route in record["provider_routes"]
                        for field in route
                    }
                ),
                "access_fields": sorted(
                    {
                        field
                        for record in records
                        for field in record["access"]
                    }
                ),
            }
        )
        stable_contract.update(
            {
                "access": {
                    "account_required": True,
                    "directory_handoff": True,
                    "case_search_completed": False,
                },
                "provider_selection_page": {
                    "published_url": EACCESS_VENDOR_PUBLISHED_URL,
                    "canonical_url": EACCESS_VENDOR_URL,
                },
            }
        )
        route_kind_counts = Counter(
            str(record["published_route"]["route_kind"])
            for record in records
        )
        provider_counts = Counter(
            str(provider["provider_id"])
            for record in records
            for provider in record["provider_routes"]
        )
        http_routes = [
            {
                "court_id": record["court"]["court_id"],
                "native_label": record["court"]["native_label"],
                "url": record["published_route"]["url"],
            }
            for record in records
            if record["published_route"]["source_published_http"]
        ]
        selection_copy = sorted(
            {
                str(provider["source_page_copy"])
                for record in records
                for provider in record["provider_routes"]
                if provider.get("source_page_copy")
            }
        )
        rolling.update(
            {
                "published_route_kind_counts": dict(
                    sorted(route_kind_counts.items())
                ),
                "provider_candidate_counts": dict(
                    sorted(provider_counts.items())
                ),
                "source_published_http_routes": http_routes,
                "provider_selection_copy": selection_copy,
            }
        )
    else:
        schema_contract.update(
            {
                "provider_state_fields": sorted(
                    {
                        field
                        for record in records
                        for entry in record["provider_states"]
                        for field in entry
                    }
                ),
                "provider_ids": sorted(
                    {
                        entry["provider_id"]
                        for record in records
                        for entry in record["provider_states"]
                    }
                ),
                "filing_fields": sorted(
                    {
                        field
                        for record in records
                        for field in record["filing"]
                    }
                ),
            }
        )
        stable_contract.update(
            {
                "filing": {
                    "account_required_to_initiate": True,
                    "filing_initiated": False,
                    "case_evidence": False,
                },
                "blank_cell_semantics": "not_listed",
            }
        )
        provider_state_counts: dict[str, Counter[str]] = {}
        unexpected_states: set[str] = set()
        for record in records:
            for entry in record["provider_states"]:
                provider_id = str(entry["provider_id"])
                provider_state_counts.setdefault(
                    provider_id,
                    Counter(),
                )[str(entry["published_state"])] += 1
                if not entry["recognized_state"]:
                    unexpected_states.add(str(entry["published_state"]))
        rolling.update(
            {
                "provider_state_counts": {
                    provider_id: dict(sorted(counts.items()))
                    for provider_id, counts in sorted(
                        provider_state_counts.items()
                    )
                },
                "listed_provider_route_count": sum(
                    len(record["provider_routes"]) for record in records
                ),
                "source_published_http_route_count": sum(
                    bool(entry["source_published_http"])
                    for record in records
                    for entry in record["provider_routes"]
                ),
                "unexpected_published_states": sorted(unexpected_states),
                "division_qualified_labels": [
                    {
                        "court_id": record["court"]["court_id"],
                        "native_label": record["court"]["native_label"],
                        "division": record["court"]["division"],
                    }
                    for record in records
                    if record["court"]["division"]
                ],
                "published_provider_dates_present": False,
            }
        )

    return {
        "canonical_ref": f"STATECOURT:{snapshot.source_id}/probe",
        "source_id": snapshot.source_id,
        "record_kind": "source_probe",
        "status": "ok",
        "source_url": SOURCE_METADATA_BY_ID[
            snapshot.source_id
        ].base_url,
        "snapshot_only": True,
        "stable_contract": stable_contract,
        "schema_contract": schema_contract,
        "stable_schema_sha256": sha256_fingerprint(schema_contract),
        "rolling_observation": rolling,
        "source_snapshot_sha256": snapshot.snapshot_sha256,
        "requests_made": snapshot.requests_made,
    }


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
        "retry_backoff",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = getattr(args, "source", EACCESS_SOURCE_ID)
    return PublicRecordsQuery(
        source=SOURCE_METADATA_BY_ID[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=(
                None
                if getattr(args, "all", False)
                else getattr(args, "limit", None)
            ),
            cursor=getattr(args, "cursor", None),
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: GeorgiaCourtAccessClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one isolated source-specific directory operation."""

    query = build_query(args)
    source_id = query.source.source_id
    warnings = SOURCE_WARNINGS[source_id]
    source_client = client
    owns_client = False
    network_command = args.command in {"search", "providers", "probe"}
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _source_records(),
                warnings=warnings,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [source_manifest(source_id)],
                warnings=warnings,
            )
        else:
            if source_client is None:
                source_client = GeorgiaCourtAccessClient(
                    timeout=args.timeout,
                    minimum_interval=args.minimum_interval,
                    retry_policy=RetryPolicy(
                        max_attempts=args.max_attempts,
                        backoff_initial=args.retry_backoff,
                    ),
                )
                owns_client = True
            snapshot = load_source_snapshot(source_client, source_id)
            if args.command == "search":
                records, next_cursor = _search_records(snapshot, args)
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    raw_artifact_refs=[
                        artifact.source_url
                        for artifact in snapshot.artifacts
                    ],
                    warnings=warnings,
                )
            elif args.command == "providers":
                result = PublicRecordsResult.success(
                    query,
                    _provider_summary_records(snapshot),
                    raw_artifact_refs=[
                        artifact.source_url
                        for artifact in snapshot.artifacts
                    ],
                    warnings=warnings,
                )
            elif args.command == "probe":
                result = PublicRecordsResult.success(
                    query,
                    [_probe_record(snapshot)],
                    raw_artifact_refs=[
                        artifact.source_url
                        for artifact in snapshot.artifacts
                    ],
                    warnings=warnings,
                )
            else:
                raise ValueError(
                    f"unsupported Georgia court-access command {args.command}"
                )
    except GeorgiaCourtAccessSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [error.to_contract_error()],
            warnings=warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
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
        if network_command and owns_client and source_client is not None:
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
            source_id,
            count,
        )
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Georgia AOC court access {args.command} "
            f"({result.status.value})"
        ),
        result_count=(
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Georgia AOC court access {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            (record.get("court") or {}).get("native_label")
            or record.get("provider_label")
            or record.get("source_id")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_positive_float,
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
    parser.add_argument(
        "--retry-backoff",
        type=_nonnegative_float,
        default=0.5,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Georgia AOC e-access and e-filing provider directories"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the two complementary source identities",
    )
    sources.set_defaults(source=EACCESS_SOURCE_ID)
    _add_runtime_and_output(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Describe one directory contract and its complements",
    )
    manifest.add_argument(
        "--source",
        choices=SOURCE_IDS,
        default=EACCESS_SOURCE_ID,
    )
    _add_runtime_and_output(manifest)

    search = sub.add_parser(
        "search",
        help="Search one current court-provider directory snapshot",
    )
    search.add_argument("query_text", nargs="?", default="*")
    search.add_argument(
        "--source",
        choices=SOURCE_IDS,
        default=EACCESS_SOURCE_ID,
    )
    search.add_argument("--county")
    search.add_argument(
        "--court-class",
        choices=("state", "superior"),
    )
    search.add_argument(
        "--provider",
        choices=KNOWN_PROVIDER_IDS,
    )
    search.add_argument(
        "--published-state",
        choices=KNOWN_PUBLISHED_STATES,
    )
    limit = search.add_mutually_exclusive_group()
    limit.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_LIMIT,
    )
    limit.add_argument("--all", action="store_true")
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    providers = sub.add_parser(
        "providers",
        help="Summarize providers and published court/state counts",
    )
    providers.add_argument(
        "--source",
        choices=SOURCE_IDS,
        default=EACCESS_SOURCE_ID,
    )
    _add_runtime_and_output(providers)

    probe = sub.add_parser(
        "probe",
        help="Run a bounded source-specific directory sentinel",
    )
    probe.add_argument(
        "--source",
        choices=SOURCE_IDS,
        default=EACCESS_SOURCE_ID,
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
