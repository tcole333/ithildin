#!/usr/bin/env python3
"""Query Michigan's official statewide county tax-parcel directory.

Michigan DTMB publishes a complete 83-county routing table after explaining
that counties maintain parcel layers and that the MGF statewide parcel layer is
not available through the open-data portal.  This adapter preserves those
published routes as a discovery catalog and keeps the directory's declared
parcel-layer role separate from capabilities that must be verified at each
destination.

Examples:
    uv run python tools/query_michigan_property_directories.py list --json
    uv run python tools/query_michigan_property_directories.py list \
        --county Oakland --json
    uv run python tools/query_michigan_property_directories.py search bsaonline
    uv run python tools/query_michigan_property_directories.py platforms --json
    uv run python tools/query_michigan_property_directories.py discovery \
        --platform bsa_online --json
    uv run python tools/query_michigan_property_directories.py manifest --json
    uv run python tools/query_michigan_property_directories.py alternatives --json
    uv run python tools/query_michigan_property_directories.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

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


SOURCE_ID = "us-mi-dtmb-tax-parcel-directory"
STATE_CODE = "MI"
STATE_GEOID = "26"
DIRECTORY_URL = (
    "https://www.michigan.gov/dtmb/services/maps/mgf-data-hub/"
    "boundaries-and-mgf/tax-parcels"
)
REGISTER_OF_DEEDS_DIRECTORY_URL = (
    "https://www.michigan.gov/en/taxes/collections/register-of-deeds"
)
TREASURY_CONTACT_URL = "https://www.michigan.gov/en/treasury/contact-us"
PROPERTY_TAX_ESTIMATOR_URL = (
    "https://www.michigan.gov/en/taxes/property/estimator"
)
FORECLOSING_GOVERNMENTAL_UNITS_URL = (
    "https://www.michigan.gov/taxes/property/forfeiture-foreclosure/"
    "taxpayer-resources/foreclosing-governmental-units"
)
LARA_PLAT_GUIDANCE_URL = (
    "https://www.michigan.gov/lara/bureau-list/bcc/sections/"
    "land-survey/subdivisions/subdivisions"
)
LARA_PLAT_SEARCH_URL = (
    "https://aca-prod.accela.com/LARA/Cap/CapHome.aspx?module=OLSR"
)
MI_PLATS_IMAGE_SERVICE_URL = (
    "https://imagery.michigan.gov/server/rest/services/MI_Plats/ImageServer"
)
DNR_LOTS_URL = (
    "https://services3.arcgis.com/Jdnp1TjADvSDxMAX/ArcGIS/rest/services/"
    "DNRLOTSParcelsOPENDATA/FeatureServer"
)
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
CURSOR_PREFIX = "mi-property-directory:v1:"

# Michigan's county FIPS codes are the odd sequence 001..165 in alphabetical
# county order.  Keeping the names explicit makes source-coverage drift
# observable while deriving the standard GEOIDs without duplicating 83 values.
COUNTY_NAMES = (
    "Alcona",
    "Alger",
    "Allegan",
    "Alpena",
    "Antrim",
    "Arenac",
    "Baraga",
    "Barry",
    "Bay",
    "Benzie",
    "Berrien",
    "Branch",
    "Calhoun",
    "Cass",
    "Charlevoix",
    "Cheboygan",
    "Chippewa",
    "Clare",
    "Clinton",
    "Crawford",
    "Delta",
    "Dickinson",
    "Eaton",
    "Emmet",
    "Genesee",
    "Gladwin",
    "Gogebic",
    "Grand Traverse",
    "Gratiot",
    "Hillsdale",
    "Houghton",
    "Huron",
    "Ingham",
    "Ionia",
    "Iosco",
    "Iron",
    "Isabella",
    "Jackson",
    "Kalamazoo",
    "Kalkaska",
    "Kent",
    "Keweenaw",
    "Lake",
    "Lapeer",
    "Leelanau",
    "Lenawee",
    "Livingston",
    "Luce",
    "Mackinac",
    "Macomb",
    "Manistee",
    "Marquette",
    "Mason",
    "Mecosta",
    "Menominee",
    "Midland",
    "Missaukee",
    "Monroe",
    "Montcalm",
    "Montmorency",
    "Muskegon",
    "Newaygo",
    "Oakland",
    "Oceana",
    "Ogemaw",
    "Ontonagon",
    "Osceola",
    "Oscoda",
    "Otsego",
    "Ottawa",
    "Presque Isle",
    "Roscommon",
    "Saginaw",
    "St. Clair",
    "St. Joseph",
    "Sanilac",
    "Schoolcraft",
    "Shiawassee",
    "Tuscola",
    "Van Buren",
    "Washtenaw",
    "Wayne",
    "Wexford",
)
COUNTY_FIPS = {
    name: f"26{index * 2 + 1:03d}"
    for index, name in enumerate(COUNTY_NAMES)
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Michigan DTMB Tax Parcel Directory",
    source_role="official_statewide_county_tax_parcel_discovery_directory",
    base_url=DIRECTORY_URL,
    dataset_id="michigan-dtmb-tax-parcels-directory",
    metadata={
        "authority": (
            "Michigan Department of Technology, Management and Budget"
        ),
        "operator": "State of Michigan",
        "authentication": "none",
        "coverage": "all_83_michigan_counties",
        "publisher_declared_role": "county_tax_parcel_layer_routes",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Michigan",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_county_property_source_directory"},
)

SOURCE_WARNINGS = (
    "The DTMB publication is a county route directory, not a statewide parcel query API.",
    "The directory identifies tax-parcel layer routes; assessment-roll, tax-payment, and recorded-title capabilities remain destination-specific.",
    "Published destination URLs and route signals are preserved separately so stale links and role mismatches remain visible.",
)
DECLARED_ROLE_QUOTE = (
    "Parcel layers are available on individual county websites (listed below)."
)
_SEMANTIC_MARKERS = (
    "parcels are maintained by individual counties",
    "statewide parcel layer",
    "not available in the open data portal",
    "parcel layers are available on individual county websites",
)
_ACCESS_DENIED_MARKERS = (
    "<title>access denied</title>",
    "you don't have permission to access",
    "errors.edgesuite.net",
)
_HUMAN_MARKERS = (
    "enable javascript and cookies to continue",
    "performing security verification",
    "captcha",
)
_COUNTY_SUFFIX_RE = re.compile(r"\s+County$", flags=re.IGNORECASE)


class MichiganPropertyDirectoryError(RuntimeError):
    """One source/query error represented in the common result envelope."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class MichiganPropertyDirectorySelectionError(MichiganPropertyDirectoryError):
    """A requested county or platform does not exist in this directory."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=status,
            category=category,
            details=details,
        )


class MichiganPropertyDirectoryChangedError(MichiganPropertyDirectoryError):
    """The live page no longer has the verified publication semantics."""

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
class MichiganPropertyDirectoryPage:
    """One validated snapshot of the statewide county routing table."""

    records: tuple[Mapping[str, Any], ...]
    source_url: str
    source_statement: str
    schema_fingerprint: str
    snapshot_fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _canonical_route_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query, "")
    )


def _platform_family(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    path = parts.path.casefold()
    if host == "bsaonline.com" or host.endswith(".bsaonline.com"):
        return "bsa_online"
    if host == "app.fetchgis.com":
        return "fetchgis"
    if host == "beacon.schneidercorp.com":
        return "schneider_beacon"
    if host.endswith(".hub.arcgis.com"):
        return "arcgis_hub"
    if host.endswith(".arcgis.com"):
        return "arcgis_online"
    if host == "colligogis.com":
        return "colligo_gis"
    if host == "mangomap.com":
        return "mangomap"
    if "geocortex" in path:
        return "geocortex"
    return "county_or_local_web"


def _route_signals(url: str) -> tuple[str, ...]:
    """Return URL/platform triage signals, not verified capabilities."""

    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    value = f"{host}{parts.path}".casefold()
    signals: list[str] = []
    if "register_of_deeds" in value or "register-of-deeds" in value:
        signals.append("recording_office")
    if "treasurer" in value or "property-tax" in value or "property_tax" in value:
        signals.append("tax_information")
    if "equalization" in value or "equal.php" in value:
        signals.append("assessment_equalization")
    parcel_map_markers = (
        "map",
        "parcel",
        "fetchgis",
        "arcgis",
        "beacon.schneidercorp",
        "colligogis",
        "mangomap",
    )
    gis_route = (
        host.startswith("gis.")
        or ".gis." in host
        or "/gis/" in parts.path.casefold()
        or parts.path.casefold().startswith("/gis")
        or "_gis" in parts.path.casefold()
        or "-gis" in parts.path.casefold()
    )
    if gis_route or any(marker in value for marker in parcel_map_markers):
        signals.append("parcel_map_or_gis")
    if "bsaonline.com" in host:
        signals.append("multi_role_property_platform")
    if not signals:
        signals.append("generic_county_page")
    return tuple(dict.fromkeys(signals))


def _review_flags(
    *,
    route_url: str,
    route_signals: Sequence[str],
    coverage_note: str | None,
) -> tuple[str, ...]:
    flags: list[str] = []
    if "recording_office" in route_signals:
        flags.append("declared_parcel_role_destination_signal_mismatch")
    if "generic_county_page" in route_signals:
        flags.append("destination_capabilities_need_review")
    if coverage_note is not None:
        flags.append("publisher_reports_partial_coverage")
    parts = urlsplit(route_url)
    if parts.fragment:
        flags.append("published_url_contains_fragment")
    if _platform_family(route_url) not in {"county_or_local_web"}:
        flags.append("hosted_platform_route")
    return tuple(flags)


def _record_from_row(
    cells: Sequence[Any],
    *,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != 2:
        raise MichiganPropertyDirectoryChangedError(
            "directory_row_width_changed",
            "Michigan tax-parcel directory row does not have two columns",
            details={"expected_columns": 2, "observed_columns": len(cells)},
        )
    county_label = _text(cells[0].get_text(" ", strip=True))
    if county_label is None:
        raise MichiganPropertyDirectoryChangedError(
            "county_name_missing",
            "Michigan tax-parcel directory row lacks a county name",
        )
    county = _COUNTY_SUFFIX_RE.sub("", county_label).strip()
    if county not in COUNTY_FIPS:
        raise MichiganPropertyDirectoryChangedError(
            "unknown_county",
            "Michigan tax-parcel directory contains an unknown county",
            details={"county_label": county_label},
        )
    links = cells[1].find_all("a", href=True)
    if not links:
        raise MichiganPropertyDirectoryChangedError(
            "county_route_missing",
            "Michigan tax-parcel directory row lacks a published route",
            details={"county": county},
        )
    published_links: list[dict[str, Any]] = []
    resolved_urls: list[str] = []
    for link in links:
        published_url = _text(link.get("href"))
        if published_url is None:
            continue
        resolved_url = urljoin(source_url, published_url)
        parts = urlsplit(resolved_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise MichiganPropertyDirectoryChangedError(
                "invalid_published_route",
                "Michigan tax-parcel directory contains a non-HTTP(S) route",
                details={"county": county, "published_url": published_url},
            )
        published_links.append(
            {
                "label_fragment": _text(link.get_text(" ", strip=True)),
                "published_url": published_url,
                "resolved_url": resolved_url,
            }
        )
        resolved_urls.append(resolved_url)
    unique_urls = tuple(dict.fromkeys(resolved_urls))
    if not unique_urls:
        raise MichiganPropertyDirectoryChangedError(
            "county_route_missing",
            "Michigan tax-parcel directory row lacks a usable route",
            details={"county": county},
        )
    route_url = unique_urls[0]
    platform = _platform_family(route_url)
    signals = _route_signals(route_url)
    row_text = _text(cells[1].get_text(" ", strip=True)) or ""
    coverage_note = (
        "partial coverage"
        if "partial coverage" in row_text.casefold()
        else None
    )
    county_fips = COUNTY_FIPS[county]
    canonical_ref = f"MI-DTMB-TAX-PARCEL-DIRECTORY:{county_fips}"
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "record_kind": "county_tax_parcel_route",
        "county": county,
        "county_label": county_label,
        "county_fips": county_fips,
        "state_code": STATE_CODE,
        "official_url": route_url,
        "route": {
            "published_label": row_text,
            "published_links": published_links,
            "published_unique_urls": list(unique_urls),
            "url": route_url,
            "canonical_url_without_fragment": _canonical_route_url(route_url),
            "host": urlsplit(route_url).hostname,
            "platform_family": platform,
        },
        "publisher_declared_role": {
            "role": "parcel_geometry",
            "description": "county_tax_parcel_layer_route",
            "source_quote": DECLARED_ROLE_QUOTE,
            "coverage_note": coverage_note,
        },
        "destination_triage": {
            "route_signals": list(signals),
            "signals_are_verified_capabilities": False,
            "review_flags": list(
                _review_flags(
                    route_url=route_url,
                    route_signals=signals,
                    coverage_note=coverage_note,
                )
            ),
        },
        "role_separation": {
            "parcel_geometry": "publisher_declared",
            "assessment_roll": "not_established_by_directory",
            "tax_collection": "not_established_by_directory",
            "land_records_index": "not_established_by_directory",
            "current_title_or_ownership": "not_established_by_directory",
        },
        "discovery_seed": {
            "jurisdiction_key": county_fips,
            "platform_family": platform,
            "candidate_categories": [
                "parcel_geometry",
                "assessment_roll",
                "tax_collection",
                "sales_history",
                "bulk_or_download",
            ],
        },
        "source_url": source_url,
        "provenance": {
            "source_id": SOURCE_ID,
            "publisher": (
                "Michigan Department of Technology, Management and Budget"
            ),
            "source_url": source_url,
            "transport": "direct_official_html",
            "response_schema_fingerprint": schema_fingerprint,
            "published_values_preserved": True,
        },
    }


def parse_directory_page(
    html_text: str,
    *,
    source_url: str = DIRECTORY_URL,
    require_complete: bool = True,
) -> MichiganPropertyDirectoryPage:
    """Parse and validate the official 83-county tax-parcel directory."""

    lowered = html_text.casefold()
    if any(marker in lowered for marker in _ACCESS_DENIED_MARKERS):
        raise MichiganPropertyDirectoryError(
            "access_denied",
            "Michigan DTMB returned an access-denied page",
            status=ResultStatus.RESTRICTED,
            category="access",
        )
    if any(marker in lowered for marker in _HUMAN_MARKERS):
        raise MichiganPropertyDirectoryError(
            "human_verification",
            "Michigan DTMB returned a human-verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
        )
    soup = BeautifulSoup(html_text, "html.parser")
    statement_node = next(
        (
            node
            for node in soup.find_all("p")
            if "statewide parcel layer"
            in (_text(node.get_text(" ", strip=True)) or "").casefold()
        ),
        None,
    )
    source_statement = (
        _text(statement_node.get_text(" ", strip=True))
        if statement_node is not None
        else None
    )
    missing_markers = [
        marker
        for marker in _SEMANTIC_MARKERS
        if source_statement is None
        or marker not in source_statement.casefold()
    ]
    if missing_markers:
        raise MichiganPropertyDirectoryChangedError(
            "directory_semantics_changed",
            "Michigan DTMB page lacks the verified parcel-directory statement",
            details={"missing_markers": missing_markers},
        )
    tables: list[tuple[Any, list[Any]]] = []
    for table in soup.find_all("table"):
        matching_rows = []
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            first_text = (
                _text(cells[0].get_text(" ", strip=True))
                if cells
                else None
            )
            if (
                len(cells) == 2
                and first_text is not None
                and _COUNTY_SUFFIX_RE.search(first_text)
                and cells[1].find("a", href=True) is not None
            ):
                matching_rows.append(row)
        if matching_rows:
            tables.append((table, matching_rows))
    if not tables:
        raise MichiganPropertyDirectoryChangedError(
            "directory_table_missing",
            "Michigan DTMB page lacks a county tax-parcel route table",
        )
    table, rows = max(tables, key=lambda value: len(value[1]))
    schema_fingerprint = hashlib.sha256(
        canonical_json(
            {
                "table_classes": sorted(table.get("class", [])),
                "row_width": 2,
                "semantic_markers": list(_SEMANTIC_MARKERS),
                "record_kind": "county_tax_parcel_route",
            }
        ).encode("utf-8")
    ).hexdigest()
    records = tuple(
        _record_from_row(
            row.find_all("td", recursive=False),
            source_url=source_url,
            schema_fingerprint=schema_fingerprint,
        )
        for row in rows
    )
    observed_counties = [str(record["county"]) for record in records]
    duplicate_counties = sorted(
        county
        for county, count in Counter(observed_counties).items()
        if count > 1
    )
    if duplicate_counties:
        raise MichiganPropertyDirectoryChangedError(
            "duplicate_counties",
            "Michigan tax-parcel directory repeats one or more counties",
            details={"counties": duplicate_counties},
        )
    expected = set(COUNTY_NAMES)
    observed = set(observed_counties)
    if require_complete and observed != expected:
        raise MichiganPropertyDirectoryChangedError(
            "directory_coverage_changed",
            "Michigan tax-parcel directory no longer contains exactly 83 counties",
            details={
                "expected_count": len(COUNTY_NAMES),
                "observed_count": len(records),
                "missing_counties": sorted(expected - observed),
                "unexpected_counties": sorted(observed - expected),
            },
        )
    snapshot_fingerprint = hashlib.sha256(
        canonical_json(
            [
                {
                    "county_fips": record["county_fips"],
                    "published_unique_urls": record["route"][
                        "published_unique_urls"
                    ],
                    "coverage_note": record["publisher_declared_role"][
                        "coverage_note"
                    ],
                }
                for record in records
            ]
        ).encode("utf-8")
    ).hexdigest()
    return MichiganPropertyDirectoryPage(
        records=records,
        source_url=source_url,
        source_statement=source_statement or "",
        schema_fingerprint=schema_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )


class MichiganPropertyDirectoryClient:
    """Paced, retrying anonymous client for the official DTMB page."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.5"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def fetch(self) -> MichiganPropertyDirectoryPage:
        response = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    DIRECTORY_URL,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise MichiganPropertyDirectoryError(
                        "transport_error",
                        f"Michigan DTMB directory request failed: {error}",
                        retryable=True,
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 200:
                break
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise MichiganPropertyDirectoryError(
                    "rate_limited",
                    "Michigan DTMB directory returned HTTP 429",
                    status=ResultStatus.RATE_LIMITED,
                    category="transport",
                    retryable=True,
                )
            if status_code in {401, 403}:
                raise MichiganPropertyDirectoryError(
                    "access_response",
                    f"Michigan DTMB directory returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                )
            raise MichiganPropertyDirectoryError(
                "http_error",
                f"Michigan DTMB directory returned HTTP {status_code}",
                category="transport",
                details={"status_code": status_code},
            )
        if response is None:
            raise AssertionError("directory request ended without a response")
        final_url = str(getattr(response, "url", DIRECTORY_URL))
        content_type = str(
            getattr(response, "headers", {}).get("Content-Type", "")
        )
        if content_type and "html" not in content_type.casefold():
            raise MichiganPropertyDirectoryChangedError(
                "unexpected_content_type",
                "Michigan DTMB directory did not return HTML",
                details={"content_type": content_type},
            )
        return parse_directory_page(
            str(response.text),
            source_url=final_url,
            require_complete=True,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": f"MI-DTMB-TAX-PARCEL-DIRECTORY:{STATE_GEOID}",
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "name": SOURCE_METADATA.name,
        "official_url": DIRECTORY_URL,
        "authority": (
            "Michigan Department of Technology, Management and Budget"
        ),
        "coverage": {
            "county_count": len(COUNTY_NAMES),
            "county_geoids": list(COUNTY_FIPS.values()),
            "statewide_data_download": False,
            "statewide_directory": True,
        },
        "publisher_declared_role": "county_tax_parcel_layer_routes",
        "operations": [
            "list",
            "search",
            "platforms",
            "discovery",
            "probe",
            "manifest",
            "alternatives",
        ],
        "role_boundaries": {
            "parcel_geometry": "directory_routes_published",
            "assessment_roll": "local_source_required",
            "tax_collection": "local_treasurer_source_required",
            "land_records_index": "county_register_of_deeds_source_required",
        },
    }


def _manifest_record() -> dict[str, Any]:
    return {
        "canonical_ref": f"MI-DTMB-TAX-PARCEL-MANIFEST:{STATE_GEOID}",
        "source_id": SOURCE_ID,
        "record_kind": "source_manifest",
        "source": _source_record(),
        "operations": {
            "network_free": ["sources", "manifest", "alternatives"],
            "official_directory_fetch": [
                "list",
                "search",
                "platforms",
                "discovery",
                "probe",
            ],
        },
        "role_matrix": {
            "parcel_geometry": {
                "primary_route": SOURCE_ID,
                "evidence": "publisher_declared_county_parcel_layer_routes",
                "statewide_query_service": False,
            },
            "assessment_roll": {
                "primary_route": "local_assessing_unit",
                "directory_capability": "not_established",
            },
            "tax_collection": {
                "primary_route": "local_treasurer",
                "directory_capability": "not_established",
            },
            "land_records_index": {
                "primary_route": "county_register_of_deeds",
                "directory_capability": "not_established",
            },
        },
        "official_alternatives": list(_alternatives()),
    }


def _alternatives() -> tuple[Mapping[str, Any], ...]:
    """Return complementary official routes without performing network calls."""

    return (
        {
            "canonical_ref": "MI-PROPERTY-ALT:LOCAL-ASSESSOR",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-local-assessor-records",
            "roles": ["assessment_roll"],
            "official_url": TREASURY_CONTACT_URL,
            "authority": "Michigan Department of Treasury",
            "coverage": "local_city_or_township_assessing_unit",
            "use": (
                "Treasury states that individual-property records are kept "
                "by the local assessor rather than Treasury or the State Tax "
                "Commission."
            ),
            "not_equivalent_to": ["parcel_geometry", "recorded_title"],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:REGISTER-OF-DEEDS",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-treasury-register-of-deeds-directory",
            "roles": ["land_records_office_directory"],
            "official_url": REGISTER_OF_DEEDS_DIRECTORY_URL,
            "authority": "Michigan Department of Treasury",
            "coverage": "county_registers_of_deeds",
            "use": (
                "Routes to the county recording offices that maintain deeds "
                "and other recorded land instruments."
            ),
            "not_equivalent_to": [
                "statewide_land_records_index",
                "parcel_assessment",
            ],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:LARA-PLATS",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-lara-subdivision-plat-search",
            "roles": ["subdivision_plat_search", "plat_attachments"],
            "official_url": LARA_PLAT_SEARCH_URL,
            "guidance_url": LARA_PLAT_GUIDANCE_URL,
            "authority": (
                "Michigan Department of Licensing and Regulatory Affairs"
            ),
            "coverage": "state_copies_of_plats_for_all_83_counties",
            "access": "complimentary_search",
            "use": (
                "Search subdivision plat records and available attachments; "
                "county registers of deeds remain the source for original "
                "recorded plats."
            ),
            "not_equivalent_to": ["deed_index", "current_title"],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:MI-PLATS-IMAGERY",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-dtmb-mi-plats-imagery",
            "roles": ["scanned_plat_imagery", "historical_ownership_context"],
            "official_url": MI_PLATS_IMAGE_SERVICE_URL,
            "authority": "State of Michigan",
            "coverage": "statewide_scanned_plat_map_imagery",
            "access": "anonymous_arcgis_image_service",
            "not_equivalent_to": ["current_tax_parcel_layer", "current_title"],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:DNR-LOTS",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-dnr-lots-parcels",
            "roles": [
                "state_land_parcels",
                "state_land_rights",
                "state_land_leases",
            ],
            "official_url": DNR_LOTS_URL,
            "authority": "Michigan Department of Natural Resources",
            "coverage": "dnr_land_ownership_tracking_system",
            "access": "anonymous_arcgis_feature_service",
            "update_frequency": "weekly",
            "not_equivalent_to": ["statewide_private_tax_parcels"],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:TAX-ESTIMATOR",
            "record_kind": "official_alternative",
            "alternative_id": "us-mi-treasury-property-tax-estimator",
            "roles": ["millage_rates", "property_tax_estimates"],
            "official_url": PROPERTY_TAX_ESTIMATOR_URL,
            "authority": "Michigan Department of Treasury",
            "coverage": "statewide_local_unit_rate_comparison",
            "not_equivalent_to": [
                "parcel_tax_bill",
                "payment_status",
                "delinquency",
            ],
        },
        {
            "canonical_ref": "MI-PROPERTY-ALT:FGU-DIRECTORY",
            "record_kind": "official_alternative",
            "alternative_id": (
                "us-mi-treasury-foreclosing-governmental-units"
            ),
            "roles": ["delinquent_tax_foreclosure_office_directory"],
            "official_url": FORECLOSING_GOVERNMENTAL_UNITS_URL,
            "authority": "Michigan Department of Treasury",
            "coverage": "county_or_state_foreclosing_governmental_units",
            "not_equivalent_to": ["current_tax_collection_ledger"],
        },
    )


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in ("county", "platform", "query"):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    requested_limit = getattr(args, "limit", None)
    if requested_limit is not None and (
        isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or requested_limit <= 0
    ):
        parameters["invalid_limit"] = requested_limit
        requested_limit = None
    cursor = getattr(args, "cursor", None)
    query_cursor = cursor if _text(cursor) is not None else None
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=query_cursor,
        ),
    )


def _normalize_county_selector(value: str | None) -> str | None:
    selector = _text(value)
    if selector is None:
        return None
    selector = _COUNTY_SUFFIX_RE.sub("", selector).strip()
    by_casefold = {name.casefold(): name for name in COUNTY_NAMES}
    if selector.casefold() in by_casefold:
        return by_casefold[selector.casefold()]
    if selector.isdigit():
        normalized = selector.zfill(5)
        by_fips = {fips: name for name, fips in COUNTY_FIPS.items()}
        if normalized in by_fips:
            return by_fips[normalized]
        if len(selector) <= 3:
            candidate = f"26{int(selector):03d}"
            if candidate in by_fips:
                return by_fips[candidate]
    raise MichiganPropertyDirectorySelectionError(
        "unknown_county",
        f"unknown Michigan county selector: {value!r}",
        details={"available_counties": list(COUNTY_NAMES)},
    )


def _selected_records(
    records: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> tuple[Mapping[str, Any], ...]:
    county = _normalize_county_selector(getattr(args, "county", None))
    platform = _text(getattr(args, "platform", None))
    query_text = _text(getattr(args, "query", None))
    available_platforms = sorted(
        {
            str(record["route"]["platform_family"])
            for record in records
        }
    )
    if (
        platform is not None
        and platform.casefold()
        not in {value.casefold() for value in available_platforms}
    ):
        raise MichiganPropertyDirectorySelectionError(
            "unknown_platform",
            f"unknown platform family: {platform!r}",
            details={"available_platforms": available_platforms},
        )
    selected = []
    for record in records:
        if county is not None and record["county"] != county:
            continue
        record_platform = str(record["route"]["platform_family"])
        if (
            platform is not None
            and record_platform.casefold() != platform.casefold()
        ):
            continue
        if (
            query_text is not None
            and query_text.casefold()
            not in canonical_json(
                {
                    "county": record["county"],
                    "county_fips": record["county_fips"],
                    "route": record["route"],
                    "destination_triage": record["destination_triage"],
                }
            ).casefold()
        ):
            continue
        selected.append(record)
    return tuple(selected)


def _platform_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["route"]["platform_family"])].append(record)
    output = []
    for platform, members in grouped.items():
        hosts = sorted(
            {
                str(member["route"]["host"])
                for member in members
                if member["route"]["host"] is not None
            }
        )
        flags = Counter(
            flag
            for member in members
            for flag in member["destination_triage"]["review_flags"]
        )
        output.append(
            {
                "canonical_ref": f"MI-DTMB-TAX-PARCEL-PLATFORM:{platform}",
                "source_id": SOURCE_ID,
                "record_kind": "county_route_platform_summary",
                "platform_family": platform,
                "county_count": len(members),
                "counties": [
                    str(member["county"]) for member in members
                ],
                "hosts": hosts,
                "review_flag_counts": dict(sorted(flags.items())),
                "publisher_declared_role": "parcel_geometry",
                "destination_capabilities_verified": False,
            }
        )
    return tuple(
        sorted(
            output,
            key=lambda record: (
                -int(record["county_count"]),
                str(record["platform_family"]),
            ),
        )
    )


def _discovery_candidates(
    records: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    candidates = []
    for record in records:
        county_fips = str(record["county_fips"])
        identity = {
            "source_id": SOURCE_ID,
            "county_fips": county_fips,
            "candidate_url": record["route"][
                "canonical_url_without_fragment"
            ],
        }
        candidate_key = (
            "MI-PROPERTY-DISCOVERY:"
            + hashlib.sha256(
                canonical_json(identity).encode("utf-8")
            ).hexdigest()
        )
        candidates.append(
            {
                "canonical_ref": candidate_key,
                "source_id": SOURCE_ID,
                "record_kind": "source_discovery_candidate",
                "candidate_kind": "official_county_tax_parcel_route",
                "candidate_url": record["official_url"],
                "candidate_host": record["route"]["host"],
                "platform_family": record["route"]["platform_family"],
                "registry_candidate_key": candidate_key,
                "registry_identity": identity,
                "jurisdiction": {
                    "state_code": STATE_CODE,
                    "county": record["county"],
                    "county_fips": county_fips,
                },
                "capability_evidence": {
                    "publisher_declared_roles": ["parcel_geometry"],
                    "destination_verified_roles": [],
                    "route_signals": record["destination_triage"][
                        "route_signals"
                    ],
                    "review_flags": record["destination_triage"][
                        "review_flags"
                    ],
                },
                "assessment_fields": [
                    "parcel_id_and_format",
                    "owner_and_mailing_address",
                    "situs_address",
                    "assessed_state_equalized_and_taxable_values",
                    "property_class_and_exemptions",
                    "sales_and_transfer_history",
                    "tax_bill_balance_payment_and_delinquency",
                    "parcel_geometry_and_spatial_reference",
                    "bulk_download_or_query_api",
                    "source_freshness_and_update_cadence",
                    "fees_authentication_and_terms",
                ],
                "discovered_from": {
                    "source_id": SOURCE_ID,
                    "source_url": record["source_url"],
                    "county_route_ref": record["canonical_ref"],
                    "schema_fingerprint": record["provenance"][
                        "response_schema_fingerprint"
                    ],
                },
                "infra_request_created": False,
            }
        )
    return tuple(candidates)


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = (
        base64.urlsafe_b64encode(
            canonical_json(payload).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{encoded}"


def _decode_cursor(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise MichiganPropertyDirectorySelectionError(
            "invalid_cursor",
            "Michigan property-directory cursor has an unknown prefix",
            category="pagination",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise MichiganPropertyDirectorySelectionError(
            "invalid_cursor",
            "Michigan property-directory cursor is malformed",
            category="pagination",
        ) from error
    if not isinstance(payload, Mapping):
        raise MichiganPropertyDirectorySelectionError(
            "invalid_cursor",
            "Michigan property-directory cursor payload is not an object",
            category="pagination",
        )
    required = {"v", "source_id", "query", "snapshot", "offset", "anchor"}
    if set(payload) != required or payload.get("v") != 1:
        raise MichiganPropertyDirectorySelectionError(
            "invalid_cursor",
            "Michigan property-directory cursor fields are invalid",
            category="pagination",
        )
    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset <= 0:
        raise MichiganPropertyDirectorySelectionError(
            "invalid_cursor",
            "Michigan property-directory cursor offset is invalid",
            category="pagination",
        )
    for field in ("source_id", "query", "snapshot", "anchor"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise MichiganPropertyDirectorySelectionError(
                "invalid_cursor",
                f"Michigan property-directory cursor {field} is invalid",
                category="pagination",
            )
    return payload


def _paginate(
    records: Sequence[Mapping[str, Any]],
    *,
    args: argparse.Namespace,
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    limit = getattr(args, "limit", None)
    cursor_value = getattr(args, "cursor", None)
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise MichiganPropertyDirectorySelectionError(
            "invalid_limit",
            "Michigan property-directory limit must be a positive integer",
            category="pagination",
        )
    query_identity = {
        "operation": args.command,
        "county": getattr(args, "county", None),
        "platform": getattr(args, "platform", None),
        "query": getattr(args, "query", None),
    }
    query_fingerprint = sha256_fingerprint(query_identity)
    snapshot_fingerprint = sha256_fingerprint(list(records))
    offset = 0
    if cursor_value is not None:
        cursor = _decode_cursor(cursor_value)
        if cursor["source_id"] != SOURCE_ID:
            raise MichiganPropertyDirectorySelectionError(
                "cursor_source_mismatch",
                "Michigan property-directory cursor belongs to another source",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        if cursor["query"] != query_fingerprint:
            raise MichiganPropertyDirectorySelectionError(
                "cursor_query_mismatch",
                "Michigan property-directory cursor belongs to another query",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        if cursor["snapshot"] != snapshot_fingerprint:
            raise MichiganPropertyDirectorySelectionError(
                "cursor_snapshot_changed",
                "Michigan property-directory records changed after the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        offset = int(cursor["offset"])
        if offset >= len(records):
            raise MichiganPropertyDirectorySelectionError(
                "cursor_offset_out_of_range",
                "Michigan property-directory cursor is beyond the result set",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
        prior_ref = str(records[offset - 1].get("canonical_ref") or "")
        if prior_ref != cursor["anchor"]:
            raise MichiganPropertyDirectorySelectionError(
                "cursor_anchor_changed",
                "Michigan property-directory cursor boundary changed",
                status=ResultStatus.SOURCE_CHANGED,
                category="pagination",
            )
    end = len(records) if limit is None else min(len(records), offset + limit)
    page = tuple(records[offset:end])
    next_cursor = None
    if end < len(records):
        anchor = str(records[end - 1].get("canonical_ref") or "")
        if not anchor:
            raise MichiganPropertyDirectoryChangedError(
                "missing_cursor_anchor",
                "Michigan property-directory row lacks a continuation identity",
            )
        next_cursor = _encode_cursor(
            {
                "v": 1,
                "source_id": SOURCE_ID,
                "query": query_fingerprint,
                "snapshot": snapshot_fingerprint,
                "offset": end,
                "anchor": anchor,
            }
        )
    return page, next_cursor


def _probe_record(page: MichiganPropertyDirectoryPage) -> Mapping[str, Any]:
    by_county = {
        str(record["county"]): record for record in page.records
    }
    sentinels = {
        "Alcona": ("26001", "county_or_local_web"),
        "Arenac": ("26011", "bsa_online"),
        "Genesee": ("26049", "county_or_local_web"),
        "Oakland": ("26125", "county_or_local_web"),
        "Wayne": ("26163", "county_or_local_web"),
        "Wexford": ("26165", "county_or_local_web"),
    }
    mismatches: dict[str, Any] = {}
    for county, (county_fips, platform) in sentinels.items():
        observed = by_county.get(county)
        if (
            observed is None
            or observed["county_fips"] != county_fips
            or observed["route"]["platform_family"] != platform
        ):
            mismatches[county] = {
                "expected_county_fips": county_fips,
                "expected_platform": platform,
                "observed": observed,
            }
    if len(page.records) != len(COUNTY_NAMES) or mismatches:
        raise MichiganPropertyDirectoryChangedError(
            "probe_sentinel_changed",
            "Michigan tax-parcel directory sentinel did not match",
            details={
                "record_count": len(page.records),
                "mismatches": mismatches,
            },
        )
    platform_counts = Counter(
        str(record["route"]["platform_family"])
        for record in page.records
    )
    flag_counts = Counter(
        flag
        for record in page.records
        for flag in record["destination_triage"]["review_flags"]
    )
    return {
        "canonical_ref": f"MI-DTMB-TAX-PARCEL-PROBE:{STATE_GEOID}",
        "source_id": SOURCE_ID,
        "record_kind": "source_probe",
        "source_url": page.source_url,
        "county_count": len(page.records),
        "county_fips_count": len(
            {str(record["county_fips"]) for record in page.records}
        ),
        "platform_counts": dict(sorted(platform_counts.items())),
        "review_flag_counts": dict(sorted(flag_counts.items())),
        "partial_coverage_count": sum(
            1
            for record in page.records
            if record["publisher_declared_role"]["coverage_note"]
            == "partial coverage"
        ),
        "schema_fingerprint": page.schema_fingerprint,
        "snapshot_fingerprint": page.snapshot_fingerprint,
        "sentinels": {
            county: {
                "county_fips": by_county[county]["county_fips"],
                "official_url": by_county[county]["official_url"],
                "platform_family": by_county[county]["route"][
                    "platform_family"
                ],
                "route_signals": by_county[county][
                    "destination_triage"
                ]["route_signals"],
            }
            for county in sentinels
        },
    }


def _failure(
    query: PublicRecordsQuery,
    error: MichiganPropertyDirectoryError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: MichiganPropertyDirectoryClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(args)
    source_client = client
    own_client = False
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_manifest_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(
                query,
                _alternatives(),
                warnings=SOURCE_WARNINGS,
            )
        else:
            if source_client is None:
                source_client = MichiganPropertyDirectoryClient(
                    timeout=args.timeout,
                    minimum_interval=args.minimum_interval,
                    retry_policy=RetryPolicy(
                        max_attempts=args.max_attempts,
                        backoff_initial=args.retry_backoff,
                    ),
                )
                own_client = True
            page = source_client.fetch()
            if args.command == "probe":
                records: Sequence[Mapping[str, Any]] = (
                    _probe_record(page),
                )
                next_cursor = None
            else:
                selected = _selected_records(page.records, args)
                if args.command == "platforms":
                    records = _platform_records(selected)
                elif args.command == "discovery":
                    records = _discovery_candidates(selected)
                else:
                    records = selected
                records, next_cursor = _paginate(records, args=args)
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                raw_artifact_refs=[page.source_url],
                warnings=SOURCE_WARNINGS,
            )
    except MichiganPropertyDirectoryError as error:
        result = _failure(query, error)
    finally:
        if own_client and source_client is not None:
            source_client.close()
    if log_results:
        result_count = (
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
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def _add_filters(
    parser: argparse.ArgumentParser,
    *,
    include_query: bool = False,
) -> None:
    parser.add_argument("--county")
    parser.add_argument("--platform")
    if include_query:
        parser.add_argument("--query")


def _add_pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int)
    parser.add_argument("--cursor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Michigan DTMB's official 83-county tax-parcel directory"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe source coverage and role boundaries",
    )
    _add_runtime_and_output(sources)

    listing = subparsers.add_parser(
        "list",
        help="List all county routes or select a county/platform",
    )
    _add_filters(listing)
    _add_pagination(listing)
    _add_runtime_and_output(listing)

    search = subparsers.add_parser(
        "search",
        help="Search county names, FIPS, platforms, URLs, and route signals",
    )
    search.add_argument("query")
    search.add_argument("--county")
    search.add_argument("--platform")
    _add_pagination(search)
    _add_runtime_and_output(search)

    platforms = subparsers.add_parser(
        "platforms",
        help="Summarize destination platform families for integration triage",
    )
    _add_filters(platforms, include_query=True)
    _add_pagination(platforms)
    _add_runtime_and_output(platforms)

    discovery = subparsers.add_parser(
        "discovery",
        help="Emit county routes as capability-assessment candidates",
    )
    _add_filters(discovery, include_query=True)
    _add_pagination(discovery)
    _add_runtime_and_output(discovery)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Show complementary official property-record routes without I/O",
    )
    _add_runtime_and_output(alternatives)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source operations, role boundaries, and alternatives without I/O",
    )
    _add_runtime_and_output(manifest)

    probe = subparsers.add_parser(
        "probe",
        help="Verify 83-county coverage, sentinels, and schema fingerprints",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Michigan property directory {args.command} "
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
        f"Michigan property directory {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("county")
            or record.get("platform_family")
            or record.get("alternative_id")
            or record.get("record_kind")
            or "?"
        )
        url = record.get("official_url") or ""
        print(f"  {label} | {url}".rstrip())
    for error in result.errors:
        print(f"  ERROR {error.code}: {error.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
