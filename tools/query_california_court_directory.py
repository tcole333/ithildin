#!/usr/bin/env python3
"""Query California's official 58-county superior-court directory.

The Judicial Branch publishes one row for each county, with official superior
court, courthouse, contact, jury, traffic, self-help, and appellate-district
routes.  The publication is a discovery source: trial-case records continue to
live in the individual county court systems.

Examples:
    uv run python tools/query_california_court_directory.py list --json
    uv run python tools/query_california_court_directory.py list \
        --county "Los Angeles" --output /tmp/ca-la-court-route.json
    uv run python tools/query_california_court_directory.py search "San Mateo"
    uv run python tools/query_california_court_directory.py list \
        --appellate-district 4 --json
    uv run python tools/query_california_court_directory.py discovery \
        --query "Santa Clara" --json
    uv run python tools/query_california_court_directory.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlparse

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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


SOURCE_ID = "us-ca-superior-court-directory"
STATE_CODE = "CA"
STATE_GEOID = "06"
BASE_URL = "https://courts.ca.gov"
DIRECTORY_URL = f"{BASE_URL}/find-your-court"
PUBLIC_RECORDS_URL = f"{BASE_URL}/policy-administration/public-records"
ELECTRONIC_RECORDS_URL = (
    f"{PUBLIC_RECORDS_URL}/who-where-how-viewing-courts-electronic-case-records"
)
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
EXPECTED_HEADERS = (
    "Superior Court",
    "Courthouses",
    "Contact",
    "Jury Info",
    "Traffic",
    "Self-Help",
    "Court of Appeal",
)
ROUTE_FIELDS = (
    ("superior_court", 0),
    ("courthouses", 1),
    ("contact", 2),
    ("jury_information", 3),
    ("traffic", 4),
    ("self_help", 5),
    ("court_of_appeal", 6),
)

COUNTY_FIPS = {
    "Alameda": "06001",
    "Alpine": "06003",
    "Amador": "06005",
    "Butte": "06007",
    "Calaveras": "06009",
    "Colusa": "06011",
    "Contra Costa": "06013",
    "Del Norte": "06015",
    "El Dorado": "06017",
    "Fresno": "06019",
    "Glenn": "06021",
    "Humboldt": "06023",
    "Imperial": "06025",
    "Inyo": "06027",
    "Kern": "06029",
    "Kings": "06031",
    "Lake": "06033",
    "Lassen": "06035",
    "Los Angeles": "06037",
    "Madera": "06039",
    "Marin": "06041",
    "Mariposa": "06043",
    "Mendocino": "06045",
    "Merced": "06047",
    "Modoc": "06049",
    "Mono": "06051",
    "Monterey": "06053",
    "Napa": "06055",
    "Nevada": "06057",
    "Orange": "06059",
    "Placer": "06061",
    "Plumas": "06063",
    "Riverside": "06065",
    "Sacramento": "06067",
    "San Benito": "06069",
    "San Bernardino": "06071",
    "San Diego": "06073",
    "San Francisco": "06075",
    "San Joaquin": "06077",
    "San Luis Obispo": "06079",
    "San Mateo": "06081",
    "Santa Barbara": "06083",
    "Santa Clara": "06085",
    "Santa Cruz": "06087",
    "Shasta": "06089",
    "Sierra": "06091",
    "Siskiyou": "06093",
    "Solano": "06095",
    "Sonoma": "06097",
    "Stanislaus": "06099",
    "Sutter": "06101",
    "Tehama": "06103",
    "Trinity": "06105",
    "Tulare": "06107",
    "Tuolumne": "06109",
    "Ventura": "06111",
    "Yolo": "06113",
    "Yuba": "06115",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="California Judicial Branch Superior Court Directory",
    source_role="official_statewide_trial_court_discovery_directory",
    base_url=DIRECTORY_URL,
    dataset_id="california-find-your-court",
    metadata={
        "authority": "Judicial Council of California",
        "operator": "Judicial Branch of California",
        "authentication": "none",
        "coverage": "all_58_county_superior_courts",
        "published_route_types": [
            field_name for field_name, _index in ROUTE_FIELDS
        ],
        "public_records_guidance": PUBLIC_RECORDS_URL,
        "electronic_records_guidance": ELECTRONIC_RECORDS_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="California",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_court_directory"},
)

SOURCE_WARNINGS = (
    "This publication routes to California's 58 county superior courts; it is not a statewide trial-case index.",
    "Each county court separately determines which case indexes, calendars, rulings, filings, images, and copy workflows it publishes.",
    "Published route URLs are preserved as source data so redirects and county-site migrations can be evaluated independently.",
)

_DISTRICT_RE = re.compile(r"\bDistrict\s+([1-6])\b", flags=re.IGNORECASE)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


class CaliforniaCourtDirectoryError(RuntimeError):
    """One source or query error represented in the common result envelope."""

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


class CaliforniaCourtDirectorySelectionError(CaliforniaCourtDirectoryError):
    """The caller supplied a directory selection the source cannot resolve."""

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


class CaliforniaCourtDirectoryChangedError(CaliforniaCourtDirectoryError):
    """The official directory no longer matches the observed publication."""

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
class CaliforniaCourtDirectoryPage:
    """One complete snapshot of the official county directory."""

    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    snapshot_fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _published_route(cell: Any, *, source_url: str) -> dict[str, Any] | None:
    link = cell.find("a", href=True)
    if link is None:
        return None
    raw_url = _text(link.get("href"))
    if raw_url is None:
        return None
    resolved_url = urljoin(source_url, raw_url)
    parsed = urlparse(resolved_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CaliforniaCourtDirectoryChangedError(
            "invalid_published_route",
            "California court directory contains a route that is not HTTP(S)",
            details={"published_url": raw_url},
        )
    return {
        "label": _text(link.get_text(" ", strip=True)),
        "published_url": raw_url,
        "url": resolved_url,
        "host": parsed.hostname,
    }


def _record_from_row(
    cells: Sequence[Any],
    *,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != len(EXPECTED_HEADERS):
        raise CaliforniaCourtDirectoryChangedError(
            "directory_row_width_changed",
            "California court directory row does not have seven columns",
            details={
                "expected_columns": len(EXPECTED_HEADERS),
                "observed_columns": len(cells),
            },
        )
    court_link = cells[0].find("a", href=True)
    county = (
        _text(court_link.get_text(" ", strip=True))
        if court_link is not None
        else _text(cells[0].get_text(" ", strip=True))
    )
    if county not in COUNTY_FIPS:
        raise CaliforniaCourtDirectoryChangedError(
            "unknown_county",
            "California court directory contains an unknown county",
            details={"county": county},
        )
    routes = {
        field_name: _published_route(cells[index], source_url=source_url)
        for field_name, index in ROUTE_FIELDS
    }
    superior_route = routes["superior_court"]
    if superior_route is None:
        raise CaliforniaCourtDirectoryChangedError(
            "superior_court_route_missing",
            "California court directory row lacks its superior-court route",
            details={"county": county},
        )
    appellate_label = (
        routes["court_of_appeal"]["label"]
        if routes["court_of_appeal"] is not None
        else None
    )
    district_match = (
        _DISTRICT_RE.search(appellate_label)
        if appellate_label is not None
        else None
    )
    if district_match is None:
        raise CaliforniaCourtDirectoryChangedError(
            "appellate_district_missing",
            "California court directory row lacks a recognized appellate district",
            details={"county": county, "label": appellate_label},
        )
    county_fips = COUNTY_FIPS[county]
    court_id = f"ca-{county.lower().replace(' ', '-')}-superior"
    canonical_ref = f"CA-COURT-DIRECTORY:{county_fips}"
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "record_kind": "superior_court_directory_entry",
        "court_id": court_id,
        "court_name": (
            f"Superior Court of California, County of {county}"
        ),
        "county": county,
        "county_fips": county_fips,
        "state_code": STATE_CODE,
        "appellate_district": int(district_match.group(1)),
        "routes": routes,
        "official_url": superior_route["url"],
        "source_url": source_url,
        "source_scope": {
            "court_and_service_routes": True,
            "case_index": False,
            "case_docket": False,
            "filing_documents": False,
        },
        "discovery_seed": {
            "jurisdiction_key": county_fips,
            "candidate_categories": [
                "case_search",
                "court_calendars",
                "tentative_rulings",
                "register_of_actions",
                "document_images",
                "records_requests",
            ],
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "response_schema_fingerprint": schema_fingerprint,
            "published_route_values_preserved": True,
        },
    }


def parse_directory_page(
    html_text: str,
    *,
    source_url: str = DIRECTORY_URL,
    require_complete: bool = True,
) -> CaliforniaCourtDirectoryPage:
    """Parse and validate the official superior-court directory table."""

    lowered = html_text.casefold()
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise CaliforniaCourtDirectoryError(
            "human_verification",
            "California court directory returned a verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
        )
    soup = BeautifulSoup(html_text, "html.parser")
    table = None
    observed_headers: list[tuple[str, ...]] = []
    for candidate in soup.find_all("table"):
        headers = tuple(
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in candidate.select("thead th")
        )
        observed_headers.append(headers)
        if headers == EXPECTED_HEADERS:
            table = candidate
            break
    if table is None:
        raise CaliforniaCourtDirectoryChangedError(
            "directory_table_missing",
            "California Find Your Court page lacks the expected directory table",
            details={
                "expected_headers": list(EXPECTED_HEADERS),
                "observed_headers": [
                    list(headers) for headers in observed_headers
                ],
            },
        )
    schema_fingerprint = hashlib.sha256(
        canonical_json(
            {
                "headers": EXPECTED_HEADERS,
                "table_classes": sorted(table.get("class", [])),
                "route_fields": [name for name, _index in ROUTE_FIELDS],
            }
        ).encode("utf-8")
    ).hexdigest()
    records = tuple(
        _record_from_row(
            row.find_all("td", recursive=False),
            source_url=source_url,
            schema_fingerprint=schema_fingerprint,
        )
        for row in table.select("tbody tr")
    )
    county_names = [str(record["county"]) for record in records]
    duplicate_counties = sorted(
        county
        for county in set(county_names)
        if county_names.count(county) > 1
    )
    if duplicate_counties:
        raise CaliforniaCourtDirectoryChangedError(
            "duplicate_counties",
            "California court directory repeats one or more counties",
            details={"counties": duplicate_counties},
        )
    if require_complete and set(county_names) != set(COUNTY_FIPS):
        raise CaliforniaCourtDirectoryChangedError(
            "directory_coverage_changed",
            "California court directory no longer contains exactly 58 counties",
            details={
                "expected_count": len(COUNTY_FIPS),
                "observed_count": len(records),
                "missing_counties": sorted(set(COUNTY_FIPS) - set(county_names)),
                "unexpected_counties": sorted(set(county_names) - set(COUNTY_FIPS)),
            },
        )
    snapshot_fingerprint = hashlib.sha256(
        canonical_json(
            [
                {
                    "county_fips": record["county_fips"],
                    "appellate_district": record["appellate_district"],
                    "routes": record["routes"],
                }
                for record in records
            ]
        ).encode("utf-8")
    ).hexdigest()
    return CaliforniaCourtDirectoryPage(
        records=records,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )


class CaliforniaCourtDirectoryClient:
    """Paced, retrying anonymous client for the official directory."""

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
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.5",
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def fetch(self) -> CaliforniaCourtDirectoryPage:
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
                    raise CaliforniaCourtDirectoryError(
                        "transport_error",
                        f"California court directory request failed: {error}",
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
                raise CaliforniaCourtDirectoryError(
                    "rate_limited",
                    "California court directory returned HTTP 429",
                    status=ResultStatus.RATE_LIMITED,
                    category="transport",
                    retryable=True,
                )
            if status_code in {401, 403}:
                raise CaliforniaCourtDirectoryError(
                    "access_response",
                    f"California court directory returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                )
            raise CaliforniaCourtDirectoryError(
                "http_error",
                f"California court directory returned HTTP {status_code}",
                category="transport",
                details={"status_code": status_code},
            )
        if response is None:
            raise AssertionError("directory request ended without a response")
        final_url = str(getattr(response, "url", DIRECTORY_URL))
        return parse_directory_page(
            str(response.text),
            source_url=final_url,
            require_complete=True,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in ("county", "appellate_district", "query"):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
        ),
    )


def _source_record() -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "name": SOURCE_METADATA.name,
        "official_url": DIRECTORY_URL,
        "authority": "Judicial Council of California",
        "coverage": {
            "county_superior_courts": len(COUNTY_FIPS),
            "jurisdiction_geoids": list(COUNTY_FIPS.values()),
        },
        "published_route_types": [
            field_name for field_name, _index in ROUTE_FIELDS
        ],
        "operations": ["list", "search", "discovery", "probe"],
        "use": (
            "Statewide discovery and routing into county-specific court "
            "record systems"
        ),
        "not_a_case_index": True,
        "related_guidance": {
            "public_records": PUBLIC_RECORDS_URL,
            "electronic_case_records": ELECTRONIC_RECORDS_URL,
        },
    }


def _discovery_candidates(
    records: Sequence[Mapping[str, Any]],
    *,
    query: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    query_key = (query or "").casefold()
    candidates: list[Mapping[str, Any]] = []
    for record in records:
        if query_key and query_key not in canonical_json(record).casefold():
            continue
        county_fips = str(record["county_fips"])
        official_url = str(record["official_url"])
        parsed = urlparse(official_url)
        identity = {
            "source_id": SOURCE_ID,
            "county_fips": county_fips,
            "court_id": record["court_id"],
        }
        registry_candidate_key = (
            "CA-COURT-DISCOVERY:"
            + hashlib.sha256(
                canonical_json(identity).encode("utf-8")
            ).hexdigest()
        )
        candidates.append(
            {
                "canonical_ref": registry_candidate_key,
                "source_id": SOURCE_ID,
                "record_kind": "source_discovery_candidate",
                "candidate_kind": "official_county_superior_court_website",
                "candidate_url": official_url,
                "candidate_host": parsed.hostname,
                "registry_candidate_key": registry_candidate_key,
                "registry_identity": identity,
                "court": {
                    "canonical_ref": record["canonical_ref"],
                    "native_id": county_fips,
                    "name": record["court_name"],
                    "court_types": ["Superior Court"],
                    "counties": [record["county"]],
                    "county_fips": [county_fips],
                    "appellate_district": record["appellate_district"],
                },
                "published_routes": record["routes"],
                "assessment_fields": [
                    "case_search",
                    "calendars",
                    "registers_dockets",
                    "opinions_orders",
                    "tentative_rulings",
                    "document_images",
                    "request_routes",
                    "bulk_products",
                    "vendor_family",
                ],
                "discovered_from": {
                    "source_id": SOURCE_ID,
                    "source_url": record["source_url"],
                    "county_fips": county_fips,
                    "schema_fingerprint": record["provenance"][
                        "response_schema_fingerprint"
                    ],
                    "published_route_values_preserved": True,
                },
                "infra_request_created": False,
            }
        )
    return tuple(candidates)


def _selected_records(
    records: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> tuple[Mapping[str, Any], ...]:
    county = _text(getattr(args, "county", None))
    if county is not None and county.casefold() not in {
        value.casefold() for value in COUNTY_FIPS
    }:
        raise CaliforniaCourtDirectorySelectionError(
            "unknown_county",
            f"unknown California county: {county!r}",
            details={"available_counties": sorted(COUNTY_FIPS)},
        )
    district = getattr(args, "appellate_district", None)
    query_text = _text(getattr(args, "query", None))
    selected: list[Mapping[str, Any]] = []
    for record in records:
        if county is not None and str(record["county"]).casefold() != county.casefold():
            continue
        if district is not None and record["appellate_district"] != district:
            continue
        if query_text is not None:
            haystack = canonical_json(
                {
                    "county": record["county"],
                    "court_name": record["court_name"],
                    "county_fips": record["county_fips"],
                    "appellate_district": record["appellate_district"],
                    "routes": record["routes"],
                }
            ).casefold()
            if query_text.casefold() not in haystack:
                continue
        selected.append(record)
    return tuple(selected)


def _failure(
    query: PublicRecordsQuery,
    error: CaliforniaCourtDirectoryError,
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
    client: CaliforniaCourtDirectoryClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(args)
    own_client = client is None
    source_client = client or CaliforniaCourtDirectoryClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            page = source_client.fetch()
            if args.command == "probe":
                by_county = {
                    str(record["county"]): record
                    for record in page.records
                }
                sentinels = {
                    "Los Angeles": (2, "06037"),
                    "San Mateo": (1, "06081"),
                }
                mismatches = {
                    county: {
                        "expected_district": district,
                        "expected_fips": fips,
                        "observed": by_county.get(county),
                    }
                    for county, (district, fips) in sentinels.items()
                    if county not in by_county
                    or by_county[county]["appellate_district"] != district
                    or by_county[county]["county_fips"] != fips
                }
                if len(page.records) != len(COUNTY_FIPS) or mismatches:
                    raise CaliforniaCourtDirectoryChangedError(
                        "probe_sentinel_changed",
                        "California court directory sentinel did not match",
                        details={
                            "record_count": len(page.records),
                            "mismatches": mismatches,
                        },
                    )
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "source_url": page.source_url,
                    "county_count": len(page.records),
                    "appellate_districts": sorted(
                        {
                            int(item["appellate_district"])
                            for item in page.records
                        }
                    ),
                    "schema_fingerprint": page.schema_fingerprint,
                    "snapshot_fingerprint": page.snapshot_fingerprint,
                    "sentinels": {
                        county: {
                            "county_fips": by_county[county]["county_fips"],
                            "appellate_district": (
                                by_county[county]["appellate_district"]
                            ),
                            "official_url": by_county[county]["official_url"],
                        }
                        for county in sentinels
                    },
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "discovery":
                candidates = _discovery_candidates(
                    page.records,
                    query=_text(getattr(args, "query", None)),
                )
                result = PublicRecordsResult.success(
                    query,
                    candidates,
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                selected = _selected_records(page.records, args)
                result = PublicRecordsResult.success(
                    query,
                    selected,
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
    except CaliforniaCourtDirectoryError as error:
        result = _failure(query, error)
    finally:
        if own_client:
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


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county")
    parser.add_argument(
        "--appellate-district",
        type=int,
        choices=range(1, 7),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query California's official 58-county court directory"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe coverage, route types, and source semantics",
    )
    _add_runtime_and_output(sources)

    listing = subparsers.add_parser(
        "list",
        help="List the complete directory or select a county or district",
    )
    _add_filters(listing)
    _add_runtime_and_output(listing)

    search = subparsers.add_parser(
        "search",
        help="Search county names, identifiers, district, and published routes",
    )
    search.add_argument("query")
    _add_filters(search)
    _add_runtime_and_output(search)

    discovery = subparsers.add_parser(
        "discovery",
        help="Emit county court websites as capability-assessment candidates",
    )
    discovery.add_argument("--query")
    _add_runtime_and_output(discovery)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the 58-county publication and stable sentinels",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"California court directory {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"California court directory {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('county') or record.get('record_kind') or '?'} | "
            f"{record.get('official_url') or record.get('source_url') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
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
