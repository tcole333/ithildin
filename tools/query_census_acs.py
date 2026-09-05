#!/usr/bin/env python3
"""Query ACS 5-year demographic denominators by Census geography.

The Census Bureau's aggregate API currently requires a free API key for data
queries while leaving dataset and variable metadata public. This adapter uses
the official API when ``CENSUS_API_KEY`` is present and can use Census
Reporter's public ACS mirror as a keyless acquisition route for the same
underlying release. Every record identifies the acquisition backend and the
underlying Census release so the mirror is not mistaken for corroboration.

Examples:
    uv run python tools/query_census_acs.py county --state 24
    uv run python tools/query_census_acs.py tract \
        --state 24 --county 005 --profile race-ethnicity
    uv run python tools/query_census_acs.py block-group \
        --state 24 --county 005 --tract 400101
    uv run python tools/query_census_acs.py zcta --zcta 21201
    uv run python tools/query_census_acs.py variables B03002 --contains Asian
    uv run python tools/query_census_acs.py probe
    uv run python tools/query_census_acs.py routes --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

try:
    from tools.env_loader import load_env_file
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
    from env_loader import load_env_file
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


SOURCE_ID = "us-census-acs5-demographics"
DEFAULT_YEAR = 2024
MINIMUM_YEAR = 2009
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
OFFICIAL_VARIABLE_CHUNK_SIZE = 24
REPORTER_TABLE_CHUNK_SIZE = 8
CURSOR_PREFIX = "acs5:v1:"
CURSOR_VERSION = 1
OUTPUT_SCHEMA_VERSION = "census-acs5-demographics/1.0"

OFFICIAL_API_ROOT = "https://api.census.gov/data"
OFFICIAL_DATASET_PAGE = "https://api.census.gov/data.html"
OFFICIAL_USER_GUIDE_URL = (
    "https://www.census.gov/data/developers/guidance/api-user-guide.html"
)
OFFICIAL_KEY_URL = "https://api.census.gov/data/key_signup.html"
SUMMARY_FILE_PAGE = "https://www.census.gov/programs-surveys/acs/data/summary-file.html"
SUMMARY_FILE_ROOT = "https://www2.census.gov/programs-surveys/acs/summary_file"
TIGERWEB_URL = "https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_apps.html"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/"
CENSUS_REPORTER_URL = "https://api.censusreporter.org"
CENSUS_REPORTER_DOCS_URL = (
    "https://github.com/censusreporter/census-api/blob/master/API.md"
)
DEFAULT_USER_AGENT = (
    "Ithildin-OSINT/1.0 public-records-research (ACS demographic denominator adapter)"
)

VARIABLE_RE = re.compile(r"^[A-Z]\d{5}[A-Z]?_\d{3}E$")
GROUP_RE = re.compile(r"^[A-Z]\d{5}[A-Z]?$")
FULL_GEOID_RE = re.compile(r"^(?P<sumlevel>\d{3})00US(?P<body>\d+)$")

SUMLEVELS = {
    "state": "040",
    "county": "050",
    "tract": "140",
    "block-group": "150",
    "place": "160",
    "zcta": "860",
}
GEOGRAPHY_COLUMNS = {
    "state": ("state",),
    "county": ("state", "county"),
    "tract": ("state", "county", "tract"),
    "block-group": ("state", "county", "tract", "block group"),
    "place": ("state", "place"),
    "zcta": ("zip code tabulation area",),
}
GEO_CODE_WIDTHS = {
    "state": 2,
    "county": 3,
    "tract": 6,
    "block_group": 1,
    "place": 5,
    "zcta": 5,
}


@dataclass(frozen=True)
class Metric:
    key: str
    estimate_variable: str
    label: str
    concept: str
    unit: str

    @property
    def margin_variable(self) -> str:
        return self.estimate_variable[:-1] + "M"

    @property
    def table_id(self) -> str:
        return self.estimate_variable.split("_", 1)[0]

    @property
    def reporter_column(self) -> str:
        return self.estimate_variable.replace("_", "")[:-1]


KNOWN_METRICS: tuple[Metric, ...] = (
    Metric(
        "population_total",
        "B01003_001E",
        "Total population",
        "Total Population",
        "people",
    ),
    Metric(
        "median_age",
        "B01002_001E",
        "Median age",
        "Median Age by Sex",
        "years",
    ),
    Metric(
        "population_under_18",
        "B09001_001E",
        "Population under 18 years",
        "Population Under 18 Years by Age",
        "people",
    ),
    Metric(
        "population_65_plus",
        "B09020_001E",
        "Population 65 years and over",
        (
            "Relationship by Household Type (Including Living Alone) for "
            "the Population 65 Years and Over"
        ),
        "people",
    ),
    Metric(
        "race_ethnicity_total",
        "B03002_001E",
        "Population in race and ethnicity universe",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "white_non_hispanic",
        "B03002_003E",
        "Not Hispanic or Latino, White alone",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "black_non_hispanic",
        "B03002_004E",
        "Not Hispanic or Latino, Black or African American alone",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "aian_non_hispanic",
        "B03002_005E",
        ("Not Hispanic or Latino, American Indian and Alaska Native alone"),
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "asian_non_hispanic",
        "B03002_006E",
        "Not Hispanic or Latino, Asian alone",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "nhpi_non_hispanic",
        "B03002_007E",
        ("Not Hispanic or Latino, Native Hawaiian and Other Pacific Islander alone"),
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "other_race_non_hispanic",
        "B03002_008E",
        "Not Hispanic or Latino, some other race alone",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "multiracial_non_hispanic",
        "B03002_009E",
        "Not Hispanic or Latino, two or more races",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "hispanic_latino",
        "B03002_012E",
        "Hispanic or Latino",
        "Hispanic or Latino Origin by Race",
        "people",
    ),
    Metric(
        "poverty_status_universe",
        "B17001_001E",
        "Population for whom poverty status is determined",
        "Poverty Status in the Past 12 Months by Sex by Age",
        "people",
    ),
    Metric(
        "below_poverty",
        "B17001_002E",
        "Income below poverty level in the past 12 months",
        "Poverty Status in the Past 12 Months by Sex by Age",
        "people",
    ),
    Metric(
        "median_household_income",
        "B19013_001E",
        "Median household income in vintage-year inflation-adjusted dollars",
        ("Median Household Income in the Past 12 Months (Inflation-Adjusted Dollars)"),
        "USD",
    ),
    Metric(
        "per_capita_income",
        "B19301_001E",
        "Per capita income in vintage-year inflation-adjusted dollars",
        ("Per Capita Income in the Past 12 Months (Inflation-Adjusted Dollars)"),
        "USD",
    ),
    Metric(
        "housing_units",
        "B25001_001E",
        "Housing units",
        "Housing Units",
        "housing_units",
    ),
    Metric(
        "occupied_housing_units",
        "B25003_001E",
        "Occupied housing units",
        "Tenure",
        "housing_units",
    ),
    Metric(
        "owner_occupied_housing_units",
        "B25003_002E",
        "Owner-occupied housing units",
        "Tenure",
        "housing_units",
    ),
    Metric(
        "renter_occupied_housing_units",
        "B25003_003E",
        "Renter-occupied housing units",
        "Tenure",
        "housing_units",
    ),
    Metric(
        "median_home_value",
        "B25077_001E",
        "Median value of owner-occupied housing units",
        "Median Value (Dollars)",
        "USD",
    ),
)
METRIC_BY_KEY = {metric.key: metric for metric in KNOWN_METRICS}
METRIC_BY_VARIABLE = {metric.estimate_variable: metric for metric in KNOWN_METRICS}
PROFILES: Mapping[str, tuple[str, ...]] = {
    "core": tuple(metric.key for metric in KNOWN_METRICS),
    "population-age": (
        "population_total",
        "median_age",
        "population_under_18",
        "population_65_plus",
    ),
    "race-ethnicity": (
        "population_total",
        "race_ethnicity_total",
        "white_non_hispanic",
        "black_non_hispanic",
        "aian_non_hispanic",
        "asian_non_hispanic",
        "nhpi_non_hispanic",
        "other_race_non_hispanic",
        "multiracial_non_hispanic",
        "hispanic_latino",
    ),
    "income-poverty": (
        "population_total",
        "poverty_status_universe",
        "below_poverty",
        "median_household_income",
        "per_capita_income",
    ),
    "housing": (
        "housing_units",
        "occupied_housing_units",
        "owner_occupied_housing_units",
        "renter_occupied_housing_units",
        "median_home_value",
    ),
    "none": (),
}


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="US Census Bureau ACS 5-Year Demographic Denominators",
    source_role="census_geography_demographic_denominator",
    base_url=OFFICIAL_DATASET_PAGE,
    dataset_id="acs/acs5",
    metadata={
        "authority": "United States Census Bureau",
        "program": "American Community Survey",
        "estimate_type": "5-year",
        "geographies": list(SUMLEVELS),
        "acquisition_backends": [
            "census_api",
            "census_reporter",
        ],
        "stable_join_keys": [
            "acs_vintage",
            "full_geoid",
            "state_fips",
            "county_fips",
            "tract_geoid",
            "block_group_geoid",
            "place_geoid",
            "zcta",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us",
    name="United States",
)

BASE_WARNINGS = (
    "ACS values are survey estimates for a five-year period; retain each "
    "published margin of error when comparing places or computing rates.",
    "The Census Reporter backend mirrors the same Census Bureau ACS release "
    "and is an acquisition fallback, not an independent corroborating source.",
    "Derived percentages in this output use point estimates and do not "
    "propagate sampling uncertainty; numerator and denominator observations "
    "remain available for a method-appropriate calculation.",
)


class ACSDataError(RuntimeError):
    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False
    code = "acs_data_error"

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


class ACSSelectionError(ACSDataError):
    category = "query"
    code = "invalid_selection"


class ACSTransportError(ACSDataError):
    category = "transport"
    retryable = True
    code = "transport_error"


class ACSRateLimitedError(ACSDataError):
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True
    code = "rate_limited"


class ACSRestrictedError(ACSDataError):
    status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class ACSAPIKeyRequiredError(ACSRestrictedError):
    code = "census_api_key_required"


class ACSRepresentationUnavailableError(ACSDataError):
    category = "coverage"
    code = "representation_unavailable"


class ACSSourceChangedError(ACSDataError):
    status = ResultStatus.SOURCE_CHANGED
    category = "schema"
    code = "source_changed"


class ACSCursorError(ACSDataError):
    category = "cursor"
    code = "stale_or_invalid_cursor"


@dataclass(frozen=True)
class GeographyCriteria:
    kind: str
    state: str | None = None
    county: str | None = None
    tract: str | None = None
    block_group: str | None = None
    place: str | None = None
    zcta: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in SUMLEVELS:
            raise ACSSelectionError(f"Unsupported ACS geography: {self.kind}")
        values = {
            "state": self.state,
            "county": self.county,
            "tract": self.tract,
            "block_group": self.block_group,
            "place": self.place,
            "zcta": self.zcta,
        }
        for field, value in values.items():
            if value is None:
                continue
            if value == "*":
                continue
            width = GEO_CODE_WIDTHS[field]
            if not value.isdigit() or len(value) != width:
                raise ACSSelectionError(
                    f"{field.replace('_', ' ')} must be {width} digits or *"
                )
        if self.kind in {"county", "tract", "block-group", "place"}:
            if self.state is None:
                raise ACSSelectionError(
                    f"{self.kind} queries require a state FIPS code"
                )
        if self.kind == "tract" and self.state == "*":
            raise ACSSelectionError("Tract queries require a specific state FIPS code")
        if self.kind == "block-group":
            if self.state == "*":
                raise ACSSelectionError(
                    "Block-group queries require a specific state FIPS code"
                )
            if self.tract not in {None, "*"} and self.county in {None, "*"}:
                raise ACSSelectionError(
                    "An exact tract requires a specific county FIPS code"
                )
            if self.block_group not in {None, "*"} and (
                self.county in {None, "*"} or self.tract in {None, "*"}
            ):
                raise ACSSelectionError(
                    "An exact block group requires exact county and tract codes"
                )
        if self.kind == "county" and self.county not in {None, "*"}:
            if self.state == "*":
                raise ACSSelectionError(
                    "An exact county requires a specific state FIPS code"
                )
        if self.kind == "place" and self.place not in {None, "*"}:
            if self.state == "*":
                raise ACSSelectionError(
                    "An exact place requires a specific state FIPS code"
                )
        if self.kind == "zcta" and self.zcta is None:
            raise ACSSelectionError("ZCTA queries require a ZCTA code or *")

    def parameters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "geography": self.kind,
                "state": self.state,
                "county": self.county,
                "tract": self.tract,
                "block_group": self.block_group,
                "place": self.place,
                "zcta": self.zcta,
            }.items()
            if value is not None
        }

    def official_params(self) -> list[tuple[str, str]]:
        if self.kind == "state":
            return [("for", f"state:{self.state or '*'}")]
        if self.kind == "county":
            return [
                ("for", f"county:{self.county or '*'}"),
                ("in", f"state:{self.state}"),
            ]
        if self.kind == "tract":
            return [
                ("for", f"tract:{self.tract or '*'}"),
                (
                    "in",
                    f"state:{self.state} county:{self.county or '*'}",
                ),
            ]
        if self.kind == "block-group":
            return [
                ("for", f"block group:{self.block_group or '*'}"),
                (
                    "in",
                    (
                        f"state:{self.state} county:{self.county or '*'} "
                        f"tract:{self.tract or '*'}"
                    ),
                ),
            ]
        if self.kind == "place":
            return [
                ("for", f"place:{self.place or '*'}"),
                ("in", f"state:{self.state}"),
            ]
        return [
            (
                "for",
                f"zip code tabulation area:{self.zcta or '*'}",
            )
        ]

    def reporter_geo_ids(self) -> str:
        if self.kind == "state":
            if self.state in {None, "*"}:
                return "040|01000US"
            return f"04000US{self.state}"
        if self.kind == "county":
            if self.county in {None, "*"}:
                parent = "01000US" if self.state == "*" else f"04000US{self.state}"
                return f"050|{parent}"
            return f"05000US{self.state}{self.county}"
        if self.kind == "tract":
            if self.tract in {None, "*"}:
                parent = (
                    f"05000US{self.state}{self.county}"
                    if self.county not in {None, "*"}
                    else f"04000US{self.state}"
                )
                return f"140|{parent}"
            return f"14000US{self.state}{self.county}{self.tract}"
        if self.kind == "block-group":
            if self.block_group in {None, "*"}:
                if self.tract not in {None, "*"}:
                    parent = f"14000US{self.state}{self.county}{self.tract}"
                elif self.county not in {None, "*"}:
                    parent = f"05000US{self.state}{self.county}"
                else:
                    parent = f"04000US{self.state}"
                return f"150|{parent}"
            return f"15000US{self.state}{self.county}{self.tract}{self.block_group}"
        if self.kind == "place":
            if self.place in {None, "*"}:
                parent = "01000US" if self.state == "*" else f"04000US{self.state}"
                return f"160|{parent}"
            return f"16000US{self.state}{self.place}"
        if self.zcta == "*":
            return "860|01000US"
        return f"86000US{self.zcta}"


@dataclass(frozen=True)
class Observation:
    estimate: int | float | None
    margin_of_error: int | float | None
    estimate_raw: Any
    margin_of_error_raw: Any
    estimate_annotation: str | None = None
    margin_annotation: str | None = None


@dataclass
class AcquiredRow:
    full_geoid: str
    name: str
    geography_codes: dict[str, str]
    values: dict[str, Observation]


@dataclass(frozen=True)
class AcquisitionPayload:
    backend: str
    release_id: str
    release_name: str
    period: str
    dataset_modified: str | None
    rows: tuple[AcquiredRow, ...]
    source_urls: tuple[str, ...]
    response_schema_fingerprint: str
    data_fingerprint: str
    unavailable_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    backend: str
    release_id: str
    response_schema_fingerprint: str
    data_fingerprint: str
    total_count: int
    offset: int


def _stable_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() != "key"
    ]
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=True),
            "",
        )
    )


def _chunks(values: Sequence[Any], size: int) -> list[Sequence[Any]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        text = str(value).strip()
        if not text or text.casefold() in {"null", "none", "nan"}:
            return None
        try:
            numeric = float(text)
        except ValueError:
            return None
    if numeric <= -222222222:
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _special_annotation(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return {
        "-222222222": "estimate_cannot_be_calculated",
        "-333333333": "median_falls_in_lowest_interval",
        "-555555555": "controlled_estimate_no_sampling_error",
        "-666666666": "insufficient_sample_observations",
        "-888888888": "not_applicable_or_not_available",
        "-999999999": "value_not_computed",
    }.get(text)


def _full_geoid(kind: str, codes: Mapping[str, str]) -> str:
    if kind == "state":
        body = codes["state"]
    elif kind == "county":
        body = codes["state"] + codes["county"]
    elif kind == "tract":
        body = codes["state"] + codes["county"] + codes["tract"]
    elif kind == "block-group":
        body = codes["state"] + codes["county"] + codes["tract"] + codes["block group"]
    elif kind == "place":
        body = codes["state"] + codes["place"]
    else:
        body = codes["zip code tabulation area"]
    return f"{SUMLEVELS[kind]}00US{body}"


def _geography_codes(full_geoid: str) -> dict[str, str]:
    match = FULL_GEOID_RE.fullmatch(full_geoid)
    if not match:
        raise ACSSourceChangedError(
            "ACS backend returned an invalid full GEOID",
            details={"full_geoid": full_geoid},
        )
    sumlevel = match.group("sumlevel")
    body = match.group("body")
    if sumlevel == "040" and len(body) == 2:
        return {"state": body}
    if sumlevel == "050" and len(body) == 5:
        return {"state": body[:2], "county": body[2:]}
    if sumlevel == "140" and len(body) == 11:
        return {
            "state": body[:2],
            "county": body[2:5],
            "tract": body[5:],
        }
    if sumlevel == "150" and len(body) == 12:
        return {
            "state": body[:2],
            "county": body[2:5],
            "tract": body[5:11],
            "block group": body[11:],
        }
    if sumlevel == "160" and len(body) == 7:
        return {"state": body[:2], "place": body[2:]}
    if sumlevel == "860" and len(body) == 5:
        return {"zip code tabulation area": body}
    raise ACSSourceChangedError(
        "ACS backend returned a GEOID with an unexpected shape",
        details={"full_geoid": full_geoid},
    )


def _custom_metric(variable: str) -> Metric:
    normalized = variable.strip().upper()
    if not VARIABLE_RE.fullmatch(normalized):
        raise ACSSelectionError(
            "Custom ACS variables must be Detailed Table estimate IDs such "
            "as B01003_001E",
            details={"variable": variable},
        )
    known = METRIC_BY_VARIABLE.get(normalized)
    if known:
        return known
    return Metric(
        key=normalized,
        estimate_variable=normalized,
        label=normalized,
        concept=f"ACS Detailed Table {normalized.split('_', 1)[0]}",
        unit="published_value",
    )


def metrics_for_args(args: argparse.Namespace) -> tuple[Metric, ...]:
    selected = [METRIC_BY_KEY[key] for key in PROFILES[args.profile]]
    if args.variables:
        selected.extend(
            _custom_metric(value)
            for value in args.variables.split(",")
            if value.strip()
        )
    deduped: dict[str, Metric] = {}
    for metric in selected:
        deduped.setdefault(metric.estimate_variable, metric)
    if not deduped:
        raise ACSSelectionError("Select a metric profile or provide --variables")
    return tuple(deduped.values())


class _JSONTransport:
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
            self.session.headers.setdefault("Accept", "application/json")
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def get_json(
        self,
        url: str,
        *,
        params: Sequence[tuple[str, str]] | Mapping[str, str] | None = None,
    ) -> tuple[Any, str]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=params,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            response_url = str(getattr(response, "url", None) or url)
            status = int(response.status_code)
            if status == 429:
                raise ACSRateLimitedError(
                    "ACS acquisition source returned HTTP 429",
                    url=response_url,
                )
            if status in {401, 403}:
                raise ACSRestrictedError(
                    f"ACS acquisition source returned HTTP {status}",
                    url=response_url,
                )
            if status in self.retry_policy.retry_statuses:
                last_error = ACSTransportError(
                    f"ACS acquisition source returned HTTP {status}",
                    url=response_url,
                )
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status == 204:
                return None, _stable_url(response_url)
            text = str(getattr(response, "text", ""))
            content = getattr(response, "content", text.encode())
            if len(content) > DEFAULT_MAX_RESPONSE_BYTES:
                raise ACSSourceChangedError(
                    "ACS response exceeded the adapter response-size bound",
                    url=response_url,
                    details={
                        "size_bytes": len(content),
                        "max_bytes": DEFAULT_MAX_RESPONSE_BYTES,
                    },
                )
            if "Missing Key" in text and "<html" in text.casefold():
                raise ACSAPIKeyRequiredError(
                    "The Census Data API requires a free API key for data queries",
                    url=response_url,
                    details={
                        "key_signup_url": OFFICIAL_KEY_URL,
                        "key_env": "CENSUS_API_KEY",
                        "keyless_fallback": "census_reporter",
                    },
                )
            if (
                status == 400
                and "None of the releases had the requested geo_ids" in text
            ):
                raise ACSRepresentationUnavailableError(
                    "The requested ACS table/geography representation is "
                    "not published by this acquisition backend",
                    url=response_url,
                    details={"response_excerpt": text[:300]},
                )
            if status >= 400:
                raise ACSTransportError(
                    f"ACS acquisition source returned HTTP {status}",
                    url=response_url,
                    details={
                        "status_code": status,
                        "response_excerpt": text[:300],
                    },
                )
            try:
                return response.json(), _stable_url(response_url)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ACSSourceChangedError(
                    "ACS acquisition source did not return JSON",
                    url=response_url,
                    details={"response_excerpt": text[:300]},
                ) from exc
        if isinstance(last_error, ACSDataError):
            raise last_error
        raise ACSTransportError(
            "Could not reach the ACS acquisition source",
            url=url,
            details={"reason": str(last_error or "request failed")},
        ) from last_error


class CensusACSClient:
    """Dual-route ACS client with official metadata and data acquisition."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if api_key is None:
            load_env_file()
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY")
        self.transport = _JSONTransport(
            session=session,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=retry_policy,
            sleeper=sleeper,
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        self.transport.close()

    @staticmethod
    def dataset_url(year: int) -> str:
        return f"{OFFICIAL_API_ROOT}/{year}/acs/acs5"

    def dataset_metadata(self, year: int) -> tuple[Mapping[str, Any], str]:
        payload, url = self.transport.get_json(f"{self.dataset_url(year)}.json")
        if not isinstance(payload, Mapping):
            raise ACSSourceChangedError(
                "Official ACS dataset metadata shape changed", url=url
            )
        datasets = payload.get("dataset")
        if not isinstance(datasets, list):
            raise ACSSourceChangedError(
                "Official ACS dataset metadata lacks a dataset catalog",
                url=url,
            )
        matches = [
            dataset
            for dataset in datasets
            if isinstance(dataset, Mapping)
            and int(dataset.get("c_vintage", -1)) == year
            and list(dataset.get("c_dataset") or []) == ["acs", "acs5"]
        ]
        if len(matches) != 1:
            raise ACSSourceChangedError(
                "Official ACS catalog lacks one exact acs/acs5 aggregate record",
                url=url,
                details={"matching_records": len(matches)},
            )
        dataset = matches[0]
        if (
            not isinstance(dataset, Mapping)
            or int(dataset.get("c_vintage", -1)) != year
            or list(dataset.get("c_dataset") or []) != ["acs", "acs5"]
            or dataset.get("c_isAvailable") is not True
        ):
            raise ACSSourceChangedError(
                "Official ACS dataset identity changed",
                url=url,
                details={"observed": dataset},
            )
        return dataset, url

    def group_metadata(self, year: int, group_id: str) -> tuple[Mapping[str, Any], str]:
        if not GROUP_RE.fullmatch(group_id):
            raise ACSSelectionError("ACS group must look like B03002 or B01001A")
        url = f"{self.dataset_url(year)}/groups/{group_id}.json"
        payload, source_url = self.transport.get_json(url)
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("variables"), Mapping
        ):
            raise ACSSourceChangedError(
                "Official ACS group metadata shape changed",
                url=source_url,
            )
        return payload, source_url

    def acquire(
        self,
        criteria: GeographyCriteria,
        metrics: Sequence[Metric],
        *,
        year: int,
        backend: str,
    ) -> AcquisitionPayload:
        if backend == "census_api":
            return self._acquire_official(criteria, metrics, year=year)
        if backend == "census_reporter":
            return self._acquire_reporter(criteria, metrics, year=year)
        raise ACSSelectionError(f"Unknown ACS backend: {backend}")

    def _acquire_official(
        self,
        criteria: GeographyCriteria,
        metrics: Sequence[Metric],
        *,
        year: int,
    ) -> AcquisitionPayload:
        if not self.api_key:
            raise ACSAPIKeyRequiredError(
                "The Census Data API backend needs CENSUS_API_KEY",
                url=self.dataset_url(year),
                details={
                    "key_signup_url": OFFICIAL_KEY_URL,
                    "keyless_fallback": "census_reporter",
                },
            )
        dataset, metadata_url = self.dataset_metadata(year)
        rows: dict[str, AcquiredRow] = {}
        source_urls = [metadata_url]
        schemas: list[Mapping[str, Any]] = []
        for chunk in _chunks(metrics, OFFICIAL_VARIABLE_CHUNK_SIZE):
            variables = [
                variable
                for metric in chunk
                for variable in (
                    metric.estimate_variable,
                    metric.margin_variable,
                )
            ]
            params: list[tuple[str, str]] = [
                ("get", ",".join(["NAME", *variables])),
                *criteria.official_params(),
                ("key", self.api_key),
            ]
            payload, source_url = self.transport.get_json(
                self.dataset_url(year), params=params
            )
            source_urls.append(source_url)
            if payload is None:
                continue
            if (
                not isinstance(payload, list)
                or not payload
                or not isinstance(payload[0], list)
            ):
                raise ACSSourceChangedError(
                    "Official ACS data matrix shape changed", url=source_url
                )
            header = [str(value) for value in payload[0]]
            if len(header) != len(set(header)):
                raise ACSSourceChangedError(
                    "Official ACS response has duplicate columns",
                    url=source_url,
                )
            expected = {
                "NAME",
                *variables,
                *GEOGRAPHY_COLUMNS[criteria.kind],
            }
            if set(header) != expected:
                raise ACSSourceChangedError(
                    "Official ACS response columns changed",
                    url=source_url,
                    details={
                        "missing": sorted(expected - set(header)),
                        "extra": sorted(set(header) - expected),
                    },
                )
            schemas.append({"columns": header})
            for raw_row in payload[1:]:
                if not isinstance(raw_row, list) or len(raw_row) != len(header):
                    raise ACSSourceChangedError(
                        "Official ACS response row width changed",
                        url=source_url,
                    )
                values = dict(zip(header, raw_row, strict=True))
                codes = {
                    column: str(values[column])
                    for column in GEOGRAPHY_COLUMNS[criteria.kind]
                }
                full_geoid = _full_geoid(criteria.kind, codes)
                row = rows.get(full_geoid)
                if row is None:
                    row = AcquiredRow(
                        full_geoid=full_geoid,
                        name=str(values["NAME"]),
                        geography_codes=codes,
                        values={},
                    )
                    rows[full_geoid] = row
                elif row.name != str(values["NAME"]) or row.geography_codes != codes:
                    raise ACSSourceChangedError(
                        "Official ACS chunk join changed geography identity",
                        url=source_url,
                        details={"full_geoid": full_geoid},
                    )
                for metric in chunk:
                    estimate_raw = values[metric.estimate_variable]
                    margin_raw = values[metric.margin_variable]
                    row.values[metric.estimate_variable] = Observation(
                        estimate=_number(estimate_raw),
                        margin_of_error=_number(margin_raw),
                        estimate_raw=estimate_raw,
                        margin_of_error_raw=margin_raw,
                        estimate_annotation=_special_annotation(estimate_raw),
                        margin_annotation=_special_annotation(margin_raw),
                    )
        ordered = tuple(rows[key] for key in sorted(rows))
        return _payload(
            backend="census_api",
            year=year,
            dataset_modified=(
                str(dataset.get("modified"))
                if dataset.get("modified") is not None
                else None
            ),
            rows=ordered,
            source_urls=source_urls,
            schemas=schemas,
        )

    def _acquire_reporter(
        self,
        criteria: GeographyCriteria,
        metrics: Sequence[Metric],
        *,
        year: int,
    ) -> AcquisitionPayload:
        release_id = f"acs{year}_5yr"
        requested_tables = sorted({metric.table_id for metric in metrics})
        metrics_by_table: dict[str, list[Metric]] = {}
        for metric in metrics:
            metrics_by_table.setdefault(metric.table_id, []).append(metric)
        combined_data: dict[str, dict[str, Any]] = {}
        geography: dict[str, Mapping[str, Any]] = {}
        table_metadata: dict[str, Mapping[str, Any]] = {}
        source_urls: list[str] = []
        unavailable_tables: set[str] = set()
        release: Mapping[str, Any] | None = None

        def fetch_tables(
            table_chunk: Sequence[str],
        ) -> tuple[
            Mapping[str, Mapping[str, Any]],
            Mapping[str, Mapping[str, Any]],
            Mapping[str, Mapping[str, Any]],
        ]:
            nonlocal release
            url = f"{CENSUS_REPORTER_URL}/1.0/data/show/{release_id}"
            payload, source_url = self.transport.get_json(
                url,
                params={
                    "table_ids": ",".join(table_chunk),
                    "geo_ids": criteria.reporter_geo_ids(),
                },
            )
            source_urls.append(source_url)
            if not isinstance(payload, Mapping):
                raise ACSSourceChangedError(
                    "Census Reporter response shape changed", url=source_url
                )
            observed_release = payload.get("release")
            if (
                not isinstance(observed_release, Mapping)
                or observed_release.get("id") != release_id
            ):
                raise ACSSourceChangedError(
                    "Census Reporter returned a different ACS release",
                    url=source_url,
                    details={"observed_release": observed_release},
                )
            if release is None:
                release = observed_release
            elif release != observed_release:
                raise ACSSourceChangedError(
                    "Census Reporter release changed between table chunks",
                    url=source_url,
                )
            chunk_tables = payload.get("tables")
            chunk_data = payload.get("data")
            chunk_geography = payload.get("geography")
            if not all(
                isinstance(value, Mapping)
                for value in (chunk_tables, chunk_data, chunk_geography)
            ):
                raise ACSSourceChangedError(
                    "Census Reporter data sections changed", url=source_url
                )
            missing_tables = set(table_chunk) - set(chunk_tables)
            if missing_tables:
                raise ACSSourceChangedError(
                    "Census Reporter omitted requested ACS tables",
                    url=source_url,
                    details={"missing_tables": sorted(missing_tables)},
                )

            selected_metadata: dict[str, Mapping[str, Any]] = {}
            for table_id in table_chunk:
                metadata = chunk_tables[table_id]
                if not isinstance(metadata, Mapping):
                    raise ACSSourceChangedError(
                        "Census Reporter table metadata shape changed",
                        url=source_url,
                        details={"table": table_id},
                    )
                columns = metadata.get("columns")
                if not isinstance(columns, Mapping):
                    raise ACSSourceChangedError(
                        "Census Reporter table column metadata changed",
                        url=source_url,
                        details={"table": table_id},
                    )
                missing_columns = {
                    metric.reporter_column
                    for metric in metrics_by_table.get(table_id, ())
                    if metric.reporter_column not in columns
                }
                if missing_columns:
                    raise ACSSourceChangedError(
                        "Census Reporter omitted requested ACS columns from "
                        "table metadata",
                        url=source_url,
                        details={
                            "table": table_id,
                            "missing_columns": sorted(missing_columns),
                        },
                    )
                selected_metadata[table_id] = metadata

            selected_data: dict[str, Mapping[str, Any]] = {}
            for geoid, table_values in chunk_data.items():
                if not isinstance(table_values, Mapping):
                    raise ACSSourceChangedError(
                        "Census Reporter geography data shape changed",
                        url=source_url,
                    )
                selected_data[str(geoid)] = {
                    table_id: table_values[table_id]
                    for table_id in table_chunk
                    if table_id in table_values
                }
            selected_geography = {
                str(geoid): value
                for geoid, value in chunk_geography.items()
                if isinstance(value, Mapping)
            }
            return selected_metadata, selected_data, selected_geography

        try:
            (
                anchor_metadata,
                anchor_data,
                anchor_geography,
            ) = fetch_tables(("B01003",))
        except ACSRepresentationUnavailableError as exc:
            if exc.url:
                source_urls.append(_stable_url(exc.url))
            return _payload(
                backend="census_reporter",
                year=year,
                dataset_modified=None,
                rows=(),
                source_urls=source_urls,
                schemas=[
                    {
                        "release": None,
                        "tables": {},
                        "geography_anchor": "B01003",
                    }
                ],
                release_name=f"ACS {year} 5-year",
                period=f"{year - 4}-{year}",
            )

        table_metadata.update(anchor_metadata)
        geography.update(anchor_geography)
        for full_geoid, table_values in anchor_data.items():
            anchor_table = table_values.get("B01003")
            if not isinstance(anchor_table, Mapping):
                raise ACSSourceChangedError(
                    "Census Reporter omitted geography-anchor table data",
                    details={
                        "full_geoid": full_geoid,
                        "table": "B01003",
                    },
                )
            combined_data[full_geoid] = {"B01003": anchor_table}

        anchor_geoids = set(combined_data)

        def acquire_optional_tables(table_chunk: Sequence[str]) -> None:
            if not table_chunk:
                return
            try:
                (
                    chunk_metadata,
                    chunk_data,
                    chunk_geography,
                ) = fetch_tables(table_chunk)
            except ACSRepresentationUnavailableError as exc:
                if exc.url:
                    source_urls.append(_stable_url(exc.url))
                if len(table_chunk) == 1:
                    unavailable_tables.add(table_chunk[0])
                    return
                midpoint = len(table_chunk) // 2
                acquire_optional_tables(table_chunk[:midpoint])
                acquire_optional_tables(table_chunk[midpoint:])
                return

            extra_geoids = set(chunk_data) - anchor_geoids
            if extra_geoids:
                raise ACSSourceChangedError(
                    "Census Reporter table query returned geographies outside "
                    "the anchor result set",
                    details={"extra_geoids": sorted(extra_geoids)},
                )
            table_metadata.update(chunk_metadata)
            geography.update(chunk_geography)
            observed_tables: set[str] = set()
            for full_geoid, table_values in chunk_data.items():
                existing = combined_data[full_geoid]
                overlap = set(existing) & set(table_values)
                if overlap:
                    raise ACSSourceChangedError(
                        "Census Reporter repeated a table across chunks",
                        details={"tables": sorted(overlap)},
                    )
                existing.update(table_values)
                observed_tables.update(table_values)
            for table_id in table_chunk:
                if table_id not in observed_tables:
                    unavailable_tables.add(table_id)

        remaining_tables = [
            table_id for table_id in requested_tables if table_id != "B01003"
        ]
        for table_chunk in _chunks(remaining_tables, REPORTER_TABLE_CHUNK_SIZE):
            acquire_optional_tables(table_chunk)

        rows: list[AcquiredRow] = []
        for full_geoid in sorted(combined_data):
            geo = geography.get(full_geoid)
            if not isinstance(geo, Mapping) or not str(geo.get("name", "")).strip():
                raise ACSSourceChangedError(
                    "Census Reporter omitted a geography label",
                    details={"full_geoid": full_geoid},
                )
            codes = _geography_codes(full_geoid)
            values: dict[str, Observation] = {}
            raw_tables = combined_data[full_geoid]
            for metric in metrics:
                table = raw_tables.get(metric.table_id)
                if not isinstance(table, Mapping):
                    values[metric.estimate_variable] = Observation(
                        estimate=None,
                        margin_of_error=None,
                        estimate_raw=None,
                        margin_of_error_raw=None,
                        estimate_annotation=("not_published_for_geography"),
                        margin_annotation=("not_published_for_geography"),
                    )
                    continue
                estimates = table.get("estimate")
                errors = table.get("error")
                if not isinstance(estimates, Mapping) or not isinstance(
                    errors, Mapping
                ):
                    raise ACSSourceChangedError(
                        "Census Reporter estimate/error shape changed",
                        details={"table": metric.table_id},
                    )
                column = metric.reporter_column
                if column not in estimates or column not in errors:
                    raise ACSSourceChangedError(
                        "Census Reporter omitted a requested ACS column",
                        details={
                            "table": metric.table_id,
                            "column": column,
                        },
                    )
                estimate_raw = estimates[column]
                margin_raw = errors[column]
                values[metric.estimate_variable] = Observation(
                    estimate=_number(estimate_raw),
                    margin_of_error=_number(margin_raw),
                    estimate_raw=estimate_raw,
                    margin_of_error_raw=margin_raw,
                )
            rows.append(
                AcquiredRow(
                    full_geoid=full_geoid,
                    name=str(geo["name"]),
                    geography_codes=codes,
                    values=values,
                )
            )
        schemas = [
            {
                "release": release,
                "tables": {
                    table_id: {
                        "title": metadata.get("title"),
                        "universe": metadata.get("universe"),
                        "columns": sorted((metadata.get("columns") or {}).keys()),
                    }
                    for table_id, metadata in sorted(table_metadata.items())
                },
                "geography_anchor": "B01003",
                "unavailable_tables": sorted(unavailable_tables),
            }
        ]
        return _payload(
            backend="census_reporter",
            year=year,
            dataset_modified=None,
            rows=tuple(rows),
            source_urls=source_urls,
            schemas=schemas,
            release_name=str((release or {}).get("name") or f"ACS {year} 5-year"),
            period=str((release or {}).get("years") or f"{year - 4}-{year}"),
            unavailable_tables=tuple(sorted(unavailable_tables)),
        )


def _payload(
    *,
    backend: str,
    year: int,
    dataset_modified: str | None,
    rows: tuple[AcquiredRow, ...],
    source_urls: Sequence[str],
    schemas: Sequence[Mapping[str, Any]],
    release_name: str | None = None,
    period: str | None = None,
    unavailable_tables: Sequence[str] = (),
) -> AcquisitionPayload:
    release_id = f"acs{year}_5yr"
    normalized_unavailable_tables = tuple(sorted(set(unavailable_tables)))
    schema_fp = sha256_fingerprint(
        {
            "schemas": list(schemas),
            "unavailable_tables": normalized_unavailable_tables,
        }
    )
    data_fp = sha256_fingerprint(
        {
            "release_id": release_id,
            "unavailable_tables": normalized_unavailable_tables,
            "rows": [
                {
                    "full_geoid": row.full_geoid,
                    "name": row.name,
                    "codes": row.geography_codes,
                    "values": {
                        variable: {
                            "estimate": observation.estimate_raw,
                            "margin": observation.margin_of_error_raw,
                            "estimate_annotation": (observation.estimate_annotation),
                            "margin_annotation": (observation.margin_annotation),
                        }
                        for variable, observation in sorted(row.values.items())
                    },
                }
                for row in rows
            ],
        }
    )
    return AcquisitionPayload(
        backend=backend,
        release_id=release_id,
        release_name=release_name or f"ACS {year} 5-year",
        period=period or f"{year - 4}-{year}",
        dataset_modified=dataset_modified,
        rows=rows,
        source_urls=tuple(dict.fromkeys(source_urls)),
        response_schema_fingerprint=schema_fp,
        data_fingerprint=data_fp,
        unavailable_tables=normalized_unavailable_tables,
    )


def _canonical_ref(year: int, full_geoid: str) -> str:
    return f"USCENSUS:ACS5:{year}:{full_geoid}"


def _ratio(
    metrics: Mapping[str, Mapping[str, Any]],
    numerator: str,
    denominator: str,
) -> Mapping[str, Any] | None:
    numerator_value = metrics.get(numerator, {}).get("estimate")
    denominator_value = metrics.get(denominator, {}).get("estimate")
    if not isinstance(numerator_value, (int, float)):
        return None
    if not isinstance(denominator_value, (int, float)) or denominator_value <= 0:
        return None
    ratio = numerator_value / denominator_value
    return {
        "ratio": ratio,
        "percent": ratio * 100,
        "numerator_metric": numerator,
        "denominator_metric": denominator,
        "uncertainty_propagated": False,
    }


def _normalize_row(
    row: AcquiredRow,
    metrics: Sequence[Metric],
    payload: AcquisitionPayload,
    *,
    year: int,
) -> dict[str, Any]:
    metric_values: dict[str, Mapping[str, Any]] = {}
    raw_variables: dict[str, Any] = {}
    for metric in metrics:
        observation = row.values.get(metric.estimate_variable)
        if observation is None:
            raise ACSSourceChangedError(
                "ACS acquisition payload lacks a selected variable",
                details={
                    "full_geoid": row.full_geoid,
                    "variable": metric.estimate_variable,
                },
            )
        metric_values[metric.key] = {
            "estimate": observation.estimate,
            "margin_of_error": observation.margin_of_error,
            "estimate_variable": metric.estimate_variable,
            "margin_variable": metric.margin_variable,
            "label": metric.label,
            "concept": metric.concept,
            "unit": metric.unit,
            "estimate_annotation": observation.estimate_annotation,
            "margin_annotation": observation.margin_annotation,
        }
        raw_variables[metric.estimate_variable] = observation.estimate_raw
        raw_variables[metric.margin_variable] = observation.margin_of_error_raw

    derived_specs = {
        "population_under_18_share": (
            "population_under_18",
            "population_total",
        ),
        "population_65_plus_share": (
            "population_65_plus",
            "population_total",
        ),
        "poverty_rate": (
            "below_poverty",
            "poverty_status_universe",
        ),
        "owner_occupancy_rate": (
            "owner_occupied_housing_units",
            "occupied_housing_units",
        ),
        "renter_occupancy_rate": (
            "renter_occupied_housing_units",
            "occupied_housing_units",
        ),
        "white_non_hispanic_share": (
            "white_non_hispanic",
            "race_ethnicity_total",
        ),
        "black_non_hispanic_share": (
            "black_non_hispanic",
            "race_ethnicity_total",
        ),
        "aian_non_hispanic_share": (
            "aian_non_hispanic",
            "race_ethnicity_total",
        ),
        "asian_non_hispanic_share": (
            "asian_non_hispanic",
            "race_ethnicity_total",
        ),
        "nhpi_non_hispanic_share": (
            "nhpi_non_hispanic",
            "race_ethnicity_total",
        ),
        "other_race_non_hispanic_share": (
            "other_race_non_hispanic",
            "race_ethnicity_total",
        ),
        "multiracial_non_hispanic_share": (
            "multiracial_non_hispanic",
            "race_ethnicity_total",
        ),
        "hispanic_latino_share": (
            "hispanic_latino",
            "race_ethnicity_total",
        ),
    }
    derived = {
        key: value
        for key, (numerator, denominator) in derived_specs.items()
        if (value := _ratio(metric_values, numerator, denominator)) is not None
    }
    codes = row.geography_codes
    geography = {
        "name": row.name,
        "type": next(
            key
            for key, sumlevel in SUMLEVELS.items()
            if row.full_geoid.startswith(sumlevel)
        ),
        "summary_level": row.full_geoid[:3],
        "full_geoid": row.full_geoid,
        "geoid": row.full_geoid.split("US", 1)[1],
        "state_fips": codes.get("state"),
        "county_code": codes.get("county"),
        "county_fips": (
            f"{codes.get('state')}{codes.get('county')}"
            if codes.get("state") and codes.get("county")
            else None
        ),
        "tract": codes.get("tract"),
        "tract_geoid": (
            f"{codes.get('state')}{codes.get('county')}{codes.get('tract')}"
            if codes.get("state") and codes.get("county") and codes.get("tract")
            else None
        ),
        "block_group": codes.get("block group"),
        "block_group_geoid": (
            (
                f"{codes.get('state')}{codes.get('county')}"
                f"{codes.get('tract')}{codes.get('block group')}"
            )
            if codes.get("state")
            and codes.get("county")
            and codes.get("tract")
            and codes.get("block group")
            else None
        ),
        "place_code": codes.get("place"),
        "place_geoid": (
            f"{codes.get('state')}{codes.get('place')}"
            if codes.get("state") and codes.get("place")
            else None
        ),
        "zcta": codes.get("zip code tabulation area"),
    }
    canonical_ref = _canonical_ref(year, row.full_geoid)
    return {
        "source_id": SOURCE_ID,
        "record_kind": "acs5_demographic_denominator",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "acs_vintage": year,
        "acs_period": payload.period,
        "release_id": payload.release_id,
        "release_name": payload.release_name,
        "geography": geography,
        "metrics": metric_values,
        "derived_point_estimate_indicators": derived,
        "join_keys": {
            "census_geography": {
                "full_geoid": row.full_geoid,
                "summary_level": row.full_geoid[:3],
                "vintage": year,
            },
            "property_and_court_geography": {
                "state_fips": geography["state_fips"],
                "county_fips": geography["county_fips"],
                "tract_geoid": geography["tract_geoid"],
                "block_group_geoid": geography["block_group_geoid"],
                "place_geoid": geography["place_geoid"],
                "zcta": geography["zcta"],
            },
        },
        "acquisition": {
            "backend": payload.backend,
            "operator": (
                "United States Census Bureau"
                if payload.backend == "census_api"
                else "Census Reporter"
            ),
            "underlying_authority": "United States Census Bureau",
            "underlying_dataset": "ACS 5-Year Detailed Tables",
            "derivative_mirror": payload.backend == "census_reporter",
            "independent_corroboration": False,
            "unavailable_tables": list(payload.unavailable_tables),
        },
        "source_snapshot": {
            "release_id": payload.release_id,
            "period": payload.period,
            "dataset_modified": payload.dataset_modified,
            "data_fingerprint": payload.data_fingerprint,
        },
        "official_dataset_url": (f"{OFFICIAL_API_ROOT}/{year}/acs/acs5.html"),
        "official_summary_file_url": (
            f"{SUMMARY_FILE_ROOT}/{year}/table-based-SF/data/5YRData/"
        ),
        "source_urls": list(payload.source_urls),
        "response_schema_fingerprint": (payload.response_schema_fingerprint),
        "raw_variables": raw_variables,
    }


def _criteria_fingerprint(
    criteria: GeographyCriteria,
    metrics: Sequence[Metric],
    *,
    year: int,
) -> str:
    return sha256_fingerprint(
        {
            "year": year,
            "geography": criteria.parameters(),
            "variables": [metric.estimate_variable for metric in metrics],
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "backend": state.backend,
        "release": state.release_id,
        "schema": state.response_schema_fingerprint,
        "data": state.data_fingerprint,
        "total": state.total_count,
        "offset": state.offset,
    }
    encoded = (
        base64.urlsafe_b64encode(canonical_json(payload).encode()).decode().rstrip("=")
    )
    return CURSOR_PREFIX + encoded


def _decode_cursor(value: str) -> CursorState:
    if not value.startswith(CURSOR_PREFIX):
        raise ACSCursorError("Continuation cursor format is invalid")
    token = value[len(CURSOR_PREFIX) :]
    try:
        padded = token + ("=" * (-len(token) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ACSCursorError("Continuation cursor could not be decoded") from exc
    required = {
        "v",
        "criteria",
        "backend",
        "release",
        "schema",
        "data",
        "total",
        "offset",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ACSCursorError("Continuation cursor payload is invalid")
    if payload["v"] != CURSOR_VERSION:
        raise ACSCursorError("Continuation cursor version is unsupported")
    try:
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            backend=str(payload["backend"]),
            release_id=str(payload["release"]),
            response_schema_fingerprint=str(payload["schema"]),
            data_fingerprint=str(payload["data"]),
            total_count=int(payload["total"]),
            offset=int(payload["offset"]),
        )
    except (TypeError, ValueError) as exc:
        raise ACSCursorError("Continuation cursor values are invalid") from exc
    if (
        state.backend not in {"census_api", "census_reporter"}
        or state.total_count < 1
        or state.offset < 1
        or state.offset >= state.total_count
    ):
        raise ACSCursorError("Continuation cursor position is invalid")
    return state


def _resolve_backend(
    requested: str,
    *,
    has_api_key: bool,
    cursor: CursorState | None,
) -> str:
    requested = requested.replace("-", "_")
    if cursor:
        if requested != "auto" and requested != cursor.backend:
            raise ACSCursorError(
                "Continuation cursor belongs to a different acquisition backend"
            )
        if cursor.backend == "census_api" and not has_api_key:
            raise ACSAPIKeyRequiredError(
                "This cursor was issued by the Census API backend and needs "
                "CENSUS_API_KEY to resume",
                url=OFFICIAL_DATASET_PAGE,
                details={"key_signup_url": OFFICIAL_KEY_URL},
            )
        return cursor.backend
    if requested == "auto":
        return "census_api" if has_api_key else "census_reporter"
    if requested == "census_api" and not has_api_key:
        raise ACSAPIKeyRequiredError(
            "The Census API backend needs CENSUS_API_KEY; use the automatic "
            "keyless mirror route or configure the free key",
            url=OFFICIAL_DATASET_PAGE,
            details={
                "key_signup_url": OFFICIAL_KEY_URL,
                "keyless_fallback": "census_reporter",
            },
        )
    return requested


def _source_warnings(
    backend: str,
    unavailable_tables: Sequence[str] = (),
) -> tuple[str, ...]:
    coverage_warning: tuple[str, ...] = ()
    if unavailable_tables:
        coverage_warning = (
            "ACS tables not published for this requested geography via the "
            "selected release: "
            f"{', '.join(sorted(unavailable_tables))}; affected metrics are "
            "null with not_published_for_geography annotations.",
        )
    if backend == "census_reporter":
        return (
            *BASE_WARNINGS,
            "This result was acquired through Census Reporter because the "
            "official Data API key was not configured; "
            "official Census metadata and bulk summary files remain linked.",
            *coverage_warning,
        )
    return (*BASE_WARNINGS, *coverage_warning)


def _data_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    criteria: GeographyCriteria,
    metrics: Sequence[Metric],
    client: CensusACSClient | Any,
    *,
    backend: str,
    retrieved_at: str,
) -> PublicRecordsResult:
    payload = client.acquire(
        criteria,
        metrics,
        year=args.year,
        backend=backend,
    )
    if payload.backend != backend:
        raise ACSSourceChangedError(
            "ACS client returned a different acquisition backend"
        )
    cursor = _decode_cursor(args.cursor) if args.cursor else None
    criteria_fp = _criteria_fingerprint(criteria, metrics, year=args.year)
    if cursor:
        if cursor.criteria_fingerprint != criteria_fp:
            raise ACSCursorError(
                "Continuation cursor belongs to different ACS criteria"
            )
        comparisons = {
            "backend": (cursor.backend, payload.backend),
            "release": (cursor.release_id, payload.release_id),
            "schema": (
                cursor.response_schema_fingerprint,
                payload.response_schema_fingerprint,
            ),
            "data": (cursor.data_fingerprint, payload.data_fingerprint),
            "total": (cursor.total_count, len(payload.rows)),
        }
        changed = {
            key: {"cursor": values[0], "current": values[1]}
            for key, values in comparisons.items()
            if values[0] != values[1]
        }
        if changed:
            raise ACSCursorError(
                "ACS release or result representation changed since the "
                "cursor was issued",
                details={"changed": changed},
            )
        offset = cursor.offset
    else:
        offset = 0
    if not payload.rows:
        if cursor:
            raise ACSCursorError("Continuation cursor no longer points to ACS results")
        return PublicRecordsResult.success(
            query,
            [],
            retrieved_at=retrieved_at,
            raw_artifact_refs=payload.source_urls,
            warnings=_source_warnings(backend, payload.unavailable_tables),
        )
    remaining = len(payload.rows) - offset
    wanted = remaining if args.limit is None else min(args.limit, remaining)
    selected = payload.rows[offset : offset + wanted]
    records = [
        _normalize_row(
            row,
            metrics,
            payload,
            year=args.year,
        )
        for row in selected
    ]
    next_offset = offset + len(records)
    next_cursor = None
    if next_offset < len(payload.rows):
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria_fp,
                backend=payload.backend,
                release_id=payload.release_id,
                response_schema_fingerprint=(payload.response_schema_fingerprint),
                data_fingerprint=payload.data_fingerprint,
                total_count=len(payload.rows),
                offset=next_offset,
            )
        )
    warnings = (
        *_source_warnings(backend, payload.unavailable_tables),
        f"Authoritative release result count for this geography query: "
        f"{len(payload.rows)}.",
    )
    if next_cursor:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="caller_result_limit",
                    message=(
                        "More geography rows are available; continue with "
                        "the returned release-and-data-bound cursor."
                    ),
                    category="pagination",
                    retryable=False,
                    details={
                        "source_total": len(payload.rows),
                        "emitted_through": next_offset,
                        "backend": backend,
                    },
                )
            ],
            records=records,
            next_cursor=next_cursor,
            retrieved_at=retrieved_at,
            raw_artifact_refs=payload.source_urls,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        raw_artifact_refs=payload.source_urls,
        warnings=warnings,
    )


def _variable_records(
    payload: Mapping[str, Any],
    *,
    year: int,
    group_id: str,
    contains: str | None,
    include_companions: bool,
) -> list[dict[str, Any]]:
    variables = payload["variables"]
    needle = (contains or "").casefold()
    records: list[dict[str, Any]] = []
    for variable_id, metadata in sorted(variables.items()):
        if not isinstance(metadata, Mapping):
            continue
        if not str(variable_id).startswith(f"{group_id}_"):
            continue
        if not include_companions and not str(variable_id).endswith("E"):
            continue
        searchable = " ".join(
            str(metadata.get(key) or "")
            for key in ("label", "concept", "predicateType")
        ).casefold()
        if needle and needle not in searchable:
            continue
        canonical_ref = f"USCENSUS:ACS5:{year}:VARIABLE:{variable_id}"
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "acs_variable_definition",
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "acs_vintage": year,
                "group_id": group_id,
                "variable_id": variable_id,
                "label": metadata.get("label"),
                "concept": metadata.get("concept"),
                "predicate_type": metadata.get("predicateType"),
                "predicate_only": metadata.get("predicateOnly"),
                "limit": metadata.get("limit"),
                "group": metadata.get("group"),
                "attributes": metadata.get("attributes"),
                "source_url": (
                    f"{OFFICIAL_API_ROOT}/{year}/acs/acs5/groups/{group_id}.html"
                ),
            }
        )
    return records


def related_source_routes(year: int = DEFAULT_YEAR) -> list[dict[str, Any]]:
    return [
        {
            "source_id": SOURCE_ID,
            "name": "Census Data API — ACS 5-Year Detailed Tables",
            "url": f"{OFFICIAL_API_ROOT}/{year}/acs/acs5.html",
            "record_role": "official_selective_demographic_query",
            "adds": (
                "official estimates, margins of error, annotations, variable "
                "metadata, and Census geography codes"
            ),
            "access_observation": (
                "Current data queries require a free Census API key"
            ),
            "join_keys": [
                "acs_vintage",
                "full_geoid",
                "state_fips",
                "county_fips",
                "tract_geoid",
                "block_group_geoid",
            ],
        },
        {
            "source_id": "us-census-acs-summary-files",
            "name": "ACS Table-Based Summary Files",
            "url": (f"{SUMMARY_FILE_ROOT}/{year}/table-based-SF/data/5YRData/"),
            "information_url": SUMMARY_FILE_PAGE,
            "record_role": "official_keyless_bulk_detailed_tables",
            "adds": (
                "one bulk file per detailed table with estimates and margins "
                "of error for every published geography"
            ),
            "join_keys": [
                "acs_vintage",
                "GEO_ID",
                "geography_file",
                "table_id",
            ],
        },
        {
            "source_id": "us-census-reporter-acs-api",
            "name": "Census Reporter ACS API",
            "url": CENSUS_REPORTER_URL,
            "information_url": CENSUS_REPORTER_DOCS_URL,
            "record_role": "keyless_selective_acs_mirror",
            "adds": (
                "keyless selective retrieval of Census ACS estimates and "
                "margins of error by full GEOID"
            ),
            "provenance_note": (
                "Derivative representation of Census ACS; redundancy, not "
                "independent corroboration"
            ),
            "join_keys": ["acs_release_id", "full_geoid", "table_id"],
        },
        {
            "source_id": "us-census-geocoder",
            "name": "Census Geocoder",
            "url": GEOCODER_URL,
            "record_role": "address_to_census_geography_crosswalk",
            "adds": (
                "address and coordinate matches to state, county, tract, "
                "block, and block-group join keys"
            ),
            "join_keys": [
                "normalized_address",
                "state_fips",
                "county_fips",
                "tract_geoid",
                "block_group_geoid",
            ],
        },
        {
            "source_id": "us-census-tigerweb",
            "name": "Census TIGERweb",
            "url": TIGERWEB_URL,
            "record_role": "census_geography_boundaries_and_spatial_join",
            "adds": (
                "official tract, block-group, place, county, and ZCTA "
                "boundaries for spatial joins"
            ),
            "join_keys": [
                "tiger_vintage",
                "full_geoid",
                "state_fips",
                "county_fips",
            ],
        },
    ]


def source_records(year: int = DEFAULT_YEAR) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "source_id": SOURCE_ID,
            "record_kind": "source_manifest",
            "name": SOURCE_METADATA.name,
            "url": f"{OFFICIAL_API_ROOT}/{year}/acs/acs5.html",
            "implemented_operations": [
                *SUMLEVELS,
                "variables",
                "probe",
                "routes",
            ],
            "profiles": {name: list(keys) for name, keys in PROFILES.items()},
            "coverage": {
                "release": f"ACS {year} 5-year",
                "period": f"{year - 4}-{year}",
                "geographies": list(SUMLEVELS),
                "metrics": [
                    {
                        "key": metric.key,
                        "estimate_variable": metric.estimate_variable,
                        "margin_variable": metric.margin_variable,
                        "unit": metric.unit,
                    }
                    for metric in KNOWN_METRICS
                ],
                "custom_variables": (
                    "additional Detailed Table estimate variables via --variables"
                ),
            },
            "acquisition": {
                "preferred": ("census_api when CENSUS_API_KEY is configured"),
                "keyless_fallback": "census_reporter",
                "official_bulk_fallback": "table_based_summary_files",
                "maximum_official_variables_per_call": 50,
                "adapter_metrics_per_official_chunk": (OFFICIAL_VARIABLE_CHUNK_SIZE),
            },
            "identity": {
                "observation": [
                    "acs_vintage",
                    "full_geoid",
                ],
                "metric": [
                    "estimate_variable",
                    "margin_variable",
                ],
            },
        }
    ]
    records.extend(
        {"record_kind": "complementary_source", **route}
        for route in related_source_routes(year)
    )
    return records


def _routes_record(year: int) -> dict[str, Any]:
    routes = related_source_routes(year)
    canonical_ref = "USCENSUS:ACS5:ROUTES:" + sha256_fingerprint(routes)
    return {
        "source_id": SOURCE_ID,
        "record_kind": "public_record_route_map",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "coverage_strategy": (
            "Acquire selective ACS denominators through the credentialed "
            "official API or the keyless release mirror, use official summary "
            "files for bulk/reproducible tables, and generate GEOID joins from "
            "addresses or coordinates with the Geocoder and TIGERweb."
        ),
        "routes": routes,
        "strongest_join_keys": [
            "ACS vintage and full GEOID",
            "state and county FIPS",
            "tract GEOID",
            "block-group GEOID",
            "place GEOID",
            "ZCTA",
        ],
    }


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata=metadata or {},
        ),
    )


def _criteria_from_args(args: argparse.Namespace) -> GeographyCriteria:
    if args.command == "probe":
        return GeographyCriteria(kind="county", state="24", county="005")
    return GeographyCriteria(
        kind=args.command,
        state=getattr(args, "state", None),
        county=getattr(args, "county", None),
        tract=getattr(args, "tract", None),
        block_group=getattr(args, "block_group", None),
        place=getattr(args, "place", None),
        zcta=getattr(args, "zcta", None),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _new_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> CensusACSClient:
    limits = access_contract.get("limits") or {}
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return CensusACSClient(
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def _access_failure(query: PublicRecordsQuery, error: Exception) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(decision.get("reason_code") or "acquisition_route_unavailable"),
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
        query, status, [public_error], warnings=BASE_WARNINGS
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: CensusACSClient | Any | None = None,
    retrieved_at: str | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one ACS denominator operation."""

    retrieved_at = retrieved_at or utc_now_iso()
    if args.command == "routes":
        query = _query("routes", {"year": args.year})
        result = PublicRecordsResult.success(
            query,
            [_routes_record(args.year)],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[
                f"{OFFICIAL_API_ROOT}/{args.year}/acs/acs5.html",
                SUMMARY_FILE_PAGE,
            ],
            warnings=BASE_WARNINGS,
        )
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, 1)
        return result

    query = _query(args.command, {"year": args.year})
    owns_client = False
    try:
        if args.command == "variables":
            group_id = args.group.upper()
            query = _query(
                "variables",
                {
                    "year": args.year,
                    "group_id": group_id,
                    "contains": args.contains,
                    "include_companions": args.include_companions,
                },
                limit=args.limit,
            )
        else:
            criteria = _criteria_from_args(args)
            metrics = (
                (METRIC_BY_KEY["population_total"],)
                if args.command == "probe"
                else metrics_for_args(args)
            )
            cursor = _decode_cursor(args.cursor) if args.cursor else None
            parameters = {
                "year": args.year,
                **criteria.parameters(),
                "profile": args.profile,
                "variables": [metric.estimate_variable for metric in metrics],
                "backend_requested": args.backend,
            }
            query = _query(
                args.command,
                parameters,
                limit=(1 if args.command == "probe" else args.limit),
                cursor=args.cursor,
                metadata={
                    "estimate_type": "ACS 5-year",
                    "margins_of_error": "included",
                },
            )
        contract = (
            access_decision if access_decision is not None else _access_contract(args)
        )
        source_client = client or _new_client(args, contract)
        owns_client = client is None
        if args.command == "variables":
            metadata, source_url = source_client.group_metadata(args.year, group_id)
            records = _variable_records(
                metadata,
                year=args.year,
                group_id=group_id,
                contains=args.contains,
                include_companions=args.include_companions,
            )
            if args.limit is not None:
                records = records[: args.limit]
            result = PublicRecordsResult.success(
                query,
                records,
                retrieved_at=retrieved_at,
                raw_artifact_refs=[source_url],
                warnings=BASE_WARNINGS,
            )
        else:
            backend = _resolve_backend(
                args.backend,
                has_api_key=source_client.has_api_key,
                cursor=cursor,
            )
            if args.command == "probe":
                dataset, metadata_url = source_client.dataset_metadata(args.year)
                group, group_url = source_client.group_metadata(args.year, "B01003")
                payload = source_client.acquire(
                    criteria,
                    metrics,
                    year=args.year,
                    backend=backend,
                )
                if len(payload.rows) != 1:
                    raise ACSSourceChangedError(
                        "ACS probe county did not return one geography",
                        details={"observed_count": len(payload.rows)},
                    )
                normalized = _normalize_row(
                    payload.rows[0],
                    metrics,
                    payload,
                    year=args.year,
                )
                probe_ref = "USCENSUS:ACS5:PROBE:" + sha256_fingerprint(
                    {
                        "dataset": dataset.get("identifier"),
                        "group": sorted(group["variables"]),
                        "backend": backend,
                        "data": payload.data_fingerprint,
                    }
                )
                probe = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "canonical_ref": probe_ref,
                    "evidence_ref": probe_ref,
                    "status": "ok",
                    "operation_states": {
                        "official_dataset_metadata": "available",
                        "official_variable_metadata": "available",
                        "official_data_query": (
                            "available"
                            if source_client.has_api_key
                            else "free_api_key_needed"
                        ),
                        "keyless_census_reporter_fallback": (
                            "available" if backend == "census_reporter" else "not_used"
                        ),
                        "official_bulk_summary_files": "available",
                    },
                    "backend": backend,
                    "credential_present": source_client.has_api_key,
                    "release_id": payload.release_id,
                    "period": payload.period,
                    "dataset_identifier": dataset.get("identifier"),
                    "dataset_modified": dataset.get("modified"),
                    "sentinel_full_geoid": normalized["geography"]["full_geoid"],
                    "sentinel_name": normalized["geography"]["name"],
                    "sentinel_population": normalized["metrics"]["population_total"][
                        "estimate"
                    ],
                    "response_schema_fingerprint": (
                        payload.response_schema_fingerprint
                    ),
                    "data_fingerprint": payload.data_fingerprint,
                }
                result = PublicRecordsResult.success(
                    query,
                    [probe],
                    retrieved_at=retrieved_at,
                    raw_artifact_refs=[
                        metadata_url,
                        group_url,
                        *payload.source_urls,
                    ],
                    warnings=_source_warnings(backend),
                )
            else:
                result = _data_result(
                    args,
                    query,
                    criteria,
                    metrics,
                    source_client,
                    backend=backend,
                    retrieved_at=retrieved_at,
                )
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error)
    except ACSDataError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            retrieved_at=retrieved_at,
            warnings=BASE_WARNINGS,
        )
    finally:
        if owns_client:
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
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
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


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="core",
        help="Curated metric set; custom variables can be added separately",
    )
    parser.add_argument(
        "--variables",
        help="Comma-separated ACS Detailed Table estimate IDs",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "census-api", "census-reporter"),
        default="auto",
        help="Acquisition route; auto uses the official API when keyed",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional local result-page size; omitted returns every geography",
    )
    parser.add_argument("--cursor")
    _add_runtime(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query ACS 5-year demographic denominators"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    state = subparsers.add_parser("state", help="Query states")
    state.add_argument("--state", default="*")
    _add_data_args(state)

    county = subparsers.add_parser("county", help="Query counties")
    county.add_argument("--state", required=True)
    county.add_argument("--county", default="*")
    _add_data_args(county)

    tract = subparsers.add_parser("tract", help="Query census tracts")
    tract.add_argument("--state", required=True)
    tract.add_argument("--county", default="*")
    tract.add_argument("--tract", default="*")
    _add_data_args(tract)

    block_group = subparsers.add_parser("block-group", help="Query census block groups")
    block_group.add_argument("--state", required=True)
    block_group.add_argument("--county", default="*")
    block_group.add_argument("--tract", default="*")
    block_group.add_argument("--block-group", default="*")
    _add_data_args(block_group)

    place = subparsers.add_parser("place", help="Query Census places")
    place.add_argument("--state", required=True)
    place.add_argument("--place", default="*")
    _add_data_args(place)

    zcta = subparsers.add_parser("zcta", help="Query ZIP Code Tabulation Areas")
    zcta.add_argument("--zcta", required=True)
    _add_data_args(zcta)

    variables = subparsers.add_parser(
        "variables", help="Inspect official variables in one Detailed Table"
    )
    variables.add_argument("group")
    variables.add_argument("--contains")
    variables.add_argument("--include-companions", action="store_true")
    variables.add_argument("--limit", type=int)
    _add_runtime(variables)

    probe = subparsers.add_parser(
        "probe",
        help="Verify official metadata and one available data backend",
    )
    probe.set_defaults(
        profile="population-age",
        variables=None,
        backend="auto",
        limit=1,
        cursor=None,
    )
    _add_runtime(probe)

    routes = subparsers.add_parser(
        "routes",
        help="Show selective, bulk, mirror, geocoder, and boundary routes",
    )
    routes.add_argument("--year", type=int, default=DEFAULT_YEAR)
    add_output_args(routes)
    return parser


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    current_year = datetime.now().year
    if args.year < MINIMUM_YEAR or args.year > current_year:
        parser.error(f"--year must be between {MINIMUM_YEAR} and {current_year}")
    for name in ("timeout", "max_attempts"):
        if hasattr(args, name) and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in ("minimum_interval", "retry_backoff"):
        if hasattr(args, name) and getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must not be negative")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "backend"):
        args.backend = args.backend.replace("-", "_")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(f"Census ACS 5-year {args.command} ({result.status.value})"),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Census ACS 5-year {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        geography = record.get("geography") or {}
        print(
            f"  {geography.get('full_geoid') or record.get('variable_id') or '?'}"
            f" | {geography.get('name') or record.get('label') or '?'}"
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
