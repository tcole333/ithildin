from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from tools import query_census_acs as acs


FIXTURE_DIR = Path("tests/fixtures/public_records/census_acs")
DATASET = json.loads((FIXTURE_DIR / "dataset.json").read_text())
GROUP = json.loads((FIXTURE_DIR / "group_b03002.json").read_text())
OFFICIAL = json.loads((FIXTURE_DIR / "official_counties.json").read_text())
REPORTER = json.loads((FIXTURE_DIR / "reporter_counties.json").read_text())
REPORTER_EMPTY = json.loads((FIXTURE_DIR / "reporter_empty.json").read_text())
MISSING_KEY = (FIXTURE_DIR / "missing_key.html").read_text()
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _allowed() -> dict[str, Any]:
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {},
    }


def _args(*values: str) -> Any:
    return acs.build_parser().parse_args(list(values))


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(acs, "log_search", lambda *args, **kwargs: None)


class FakeResponse:
    def __init__(
        self,
        payload: Any,
        url: str,
        *,
        status_code: int = 200,
        text: str | None = None,
    ) -> None:
        self.payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.content = self.text.encode()
        self.url = url
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        return copy.deepcopy(self.payload)


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Sequence[tuple[str, str]] | Mapping[str, str] | None,
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def _fixture_payload(
    metrics: Sequence[acs.Metric] | None = None,
    *,
    rows: int = 2,
    backend: str = "census_reporter",
) -> acs.AcquisitionPayload:
    selected = tuple(metrics or acs.KNOWN_METRICS)
    acquired: list[acs.AcquiredRow] = []
    for full_geoid, tables in sorted(REPORTER["data"].items())[:rows]:
        values: dict[str, acs.Observation] = {}
        for metric in selected:
            table = tables[metric.table_id]
            estimate = table["estimate"][metric.reporter_column]
            margin = table["error"][metric.reporter_column]
            values[metric.estimate_variable] = acs.Observation(
                estimate=acs._number(estimate),
                margin_of_error=acs._number(margin),
                estimate_raw=estimate,
                margin_of_error_raw=margin,
            )
        acquired.append(
            acs.AcquiredRow(
                full_geoid=full_geoid,
                name=REPORTER["geography"][full_geoid]["name"],
                geography_codes=acs._geography_codes(full_geoid),
                values=values,
            )
        )
    return acs._payload(
        backend=backend,
        year=2024,
        dataset_modified=("2025-09-02 17:33:50.0" if backend == "census_api" else None),
        rows=tuple(acquired),
        source_urls=("https://api.censusreporter.org/1.0/data/show/acs2024_5yr",),
        schemas=[{"fixture": True, "backend": backend}],
        release_name="ACS 2024 5-year",
        period="2020-2024",
    )


class FixtureClient:
    def __init__(
        self,
        payload: acs.AcquisitionPayload | None = None,
        *,
        has_api_key: bool = False,
    ) -> None:
        self.payload = payload or _fixture_payload()
        self.has_api_key = has_api_key
        self.acquire_calls: list[dict[str, Any]] = []
        self.group_calls: list[tuple[int, str]] = []
        self.dataset_calls: list[int] = []

    def acquire(
        self,
        criteria: acs.GeographyCriteria,
        metrics: Sequence[acs.Metric],
        *,
        year: int,
        backend: str,
    ) -> acs.AcquisitionPayload:
        self.acquire_calls.append(
            {
                "criteria": criteria,
                "variables": [metric.estimate_variable for metric in metrics],
                "year": year,
                "backend": backend,
            }
        )
        return self.payload

    def dataset_metadata(self, year: int) -> tuple[Mapping[str, Any], str]:
        self.dataset_calls.append(year)
        return next(
            dataset
            for dataset in DATASET["dataset"]
            if dataset["c_dataset"] == ["acs", "acs5"]
        ), (f"https://api.census.gov/data/{year}/acs/acs5.json")

    def group_metadata(self, year: int, group_id: str) -> tuple[Mapping[str, Any], str]:
        self.group_calls.append((year, group_id))
        return GROUP, (
            f"https://api.census.gov/data/{year}/acs/acs5/groups/{group_id}.json"
        )


def test_curated_profiles_and_custom_variables_are_deduplicated() -> None:
    args = _args(
        "county",
        "--state",
        "24",
        "--profile",
        "population-age",
        "--variables",
        "B01003_001E,B25077_001E",
    )
    metrics = acs.metrics_for_args(args)
    assert [metric.key for metric in metrics] == [
        "population_total",
        "median_age",
        "population_under_18",
        "population_65_plus",
        "median_home_value",
    ]
    custom = acs.metrics_for_args(
        _args(
            "county",
            "--state",
            "24",
            "--profile",
            "none",
            "--variables",
            "B15003_001E",
        )
    )
    assert custom[0].key == "B15003_001E"
    assert custom[0].margin_variable == "B15003_001M"
    assert custom[0].reporter_column == "B15003001"
    with pytest.raises(acs.ACSSelectionError):
        acs.metrics_for_args(
            _args(
                "county",
                "--state",
                "24",
                "--profile",
                "none",
                "--variables",
                "not-a-variable",
            )
        )


def test_geography_criteria_build_official_and_reporter_queries() -> None:
    county = acs.GeographyCriteria(kind="county", state="24", county="*")
    assert county.official_params() == [
        ("for", "county:*"),
        ("in", "state:24"),
    ]
    assert county.reporter_geo_ids() == "050|04000US24"

    tract = acs.GeographyCriteria(kind="tract", state="24", county="005", tract="*")
    assert tract.reporter_geo_ids() == "140|05000US24005"
    assert tract.official_params()[-1] == (
        "in",
        "state:24 county:005",
    )

    block = acs.GeographyCriteria(
        kind="block-group",
        state="24",
        county="005",
        tract="400101",
        block_group="1",
    )
    assert block.reporter_geo_ids() == "15000US240054001011"
    zcta = acs.GeographyCriteria(kind="zcta", zcta="21201")
    assert zcta.reporter_geo_ids() == "86000US21201"


def test_geography_criteria_reject_invalid_hierarchies() -> None:
    with pytest.raises(acs.ACSSelectionError):
        acs.GeographyCriteria(kind="county", state="2", county="001")
    with pytest.raises(acs.ACSSelectionError):
        acs.GeographyCriteria(kind="tract", state="*", tract="*")
    with pytest.raises(acs.ACSSelectionError):
        acs.GeographyCriteria(
            kind="block-group",
            state="24",
            county="*",
            tract="400101",
        )
    with pytest.raises(acs.ACSSelectionError):
        acs.GeographyCriteria(
            kind="place",
            state="*",
            place="51000",
        )


def test_dataset_and_group_metadata_validate_official_identity() -> None:
    session = QueueSession(
        [
            FakeResponse(
                DATASET,
                "https://api.census.gov/data/2024/acs/acs5.json",
            ),
            FakeResponse(
                GROUP,
                ("https://api.census.gov/data/2024/acs/acs5/groups/B03002.json"),
            ),
        ]
    )
    client = acs.CensusACSClient(
        api_key="test-key",
        session=session,
        minimum_interval=0,
    )
    dataset, _ = client.dataset_metadata(2024)
    group, _ = client.group_metadata(2024, "B03002")
    assert dataset["identifier"].endswith("ACSDT5Y2024")
    assert "B03002_006E" in group["variables"]
    assert session.calls[0]["params"] is None


def test_transport_recognizes_http_200_missing_key_page() -> None:
    session = QueueSession(
        [
            FakeResponse(
                ValueError("not json"),
                "https://api.census.gov/data/2024/acs/acs5",
                text=MISSING_KEY,
            )
        ]
    )
    transport = acs._JSONTransport(session=session, minimum_interval=0)
    with pytest.raises(acs.ACSAPIKeyRequiredError):
        transport.get_json(
            "https://api.census.gov/data/2024/acs/acs5",
            params={"get": "NAME,B01003_001E"},
        )


def test_official_backend_parses_matrix_special_values_and_hides_key() -> None:
    data_url = (
        "https://api.census.gov/data/2024/acs/acs5?"
        "get=NAME%2CB01003_001E%2CB01003_001M"
        "&for=county%3A%2A&in=state%3A24&key=secret"
    )
    session = QueueSession(
        [
            FakeResponse(
                DATASET,
                "https://api.census.gov/data/2024/acs/acs5.json",
            ),
            FakeResponse(OFFICIAL, data_url),
        ]
    )
    client = acs.CensusACSClient(
        api_key="secret",
        session=session,
        minimum_interval=0,
    )
    metrics = (
        acs.METRIC_BY_KEY["population_total"],
        acs.METRIC_BY_KEY["median_household_income"],
    )
    payload = client.acquire(
        acs.GeographyCriteria(kind="county", state="24", county="*"),
        metrics,
        year=2024,
        backend="census_api",
    )
    assert payload.backend == "census_api"
    assert len(payload.rows) == 2
    first = payload.rows[0]
    assert first.full_geoid == "05000US24001"
    population = first.values["B01003_001E"]
    assert population.estimate == 67452
    assert population.margin_of_error is None
    assert population.margin_annotation == ("controlled_estimate_no_sampling_error")
    assert all("secret" not in url for url in payload.source_urls)
    params = dict(session.calls[1]["params"])
    assert params["key"] == "secret"
    assert "B19013_001M" in params["get"]


def test_reporter_backend_normalizes_exact_release_estimates_and_errors() -> None:
    session = QueueSession(
        [
            FakeResponse(
                REPORTER,
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
            ),
            FakeResponse(
                REPORTER,
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
            ),
        ]
    )
    client = acs.CensusACSClient(
        api_key=None,
        session=session,
        minimum_interval=0,
    )
    metrics = (
        acs.METRIC_BY_KEY["population_total"],
        acs.METRIC_BY_KEY["race_ethnicity_total"],
        acs.METRIC_BY_KEY["asian_non_hispanic"],
    )
    payload = client.acquire(
        acs.GeographyCriteria(kind="county", state="24", county="*"),
        metrics,
        year=2024,
        backend="census_reporter",
    )
    assert payload.release_id == "acs2024_5yr"
    assert payload.period == "2020-2024"
    assert [row.full_geoid for row in payload.rows] == [
        "05000US24001",
        "05000US24003",
    ]
    first = payload.rows[0]
    assert first.values["B03002_006E"].estimate == 708
    assert first.values["B03002_006E"].margin_of_error == 110
    assert [call["params"]["table_ids"] for call in session.calls] == [
        "B01003",
        "B03002",
    ]
    assert all(call["params"]["geo_ids"] == "050|04000US24" for call in session.calls)


def test_reporter_backend_preserves_authoritative_empty() -> None:
    session = QueueSession(
        [
            FakeResponse(
                REPORTER_EMPTY,
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
            )
        ]
    )
    payload = acs.CensusACSClient(session=session, minimum_interval=0).acquire(
        acs.GeographyCriteria(kind="county", state="24", county="999"),
        (acs.METRIC_BY_KEY["population_total"],),
        year=2024,
        backend="census_reporter",
    )
    assert payload.rows == ()


def test_reporter_backend_detects_missing_requested_column() -> None:
    broken = copy.deepcopy(REPORTER)
    del broken["data"]["05000US24001"]["B03002"]["error"]["B03002006"]
    session = QueueSession(
        [
            FakeResponse(
                REPORTER,
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
            ),
            FakeResponse(
                broken,
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
            ),
        ]
    )
    with pytest.raises(acs.ACSSourceChangedError):
        acs.CensusACSClient(session=session, minimum_interval=0).acquire(
            acs.GeographyCriteria(kind="county", state="24", county="*"),
            (acs.METRIC_BY_KEY["asian_non_hispanic"],),
            year=2024,
            backend="census_reporter",
        )


def test_reporter_backend_recovers_available_tables_when_batch_is_unsupported() -> None:
    unsupported = json.dumps(
        {"error": ("None of the releases had the requested geo_ids and table_ids")}
    )
    url = "https://api.censusreporter.org/1.0/data/show/acs2024_5yr"
    session = QueueSession(
        [
            FakeResponse(REPORTER, url),
            FakeResponse({}, url, status_code=400, text=unsupported),
            FakeResponse(REPORTER, url),
            FakeResponse({}, url, status_code=400, text=unsupported),
        ]
    )
    metrics = (
        acs.METRIC_BY_KEY["population_total"],
        acs.METRIC_BY_KEY["median_age"],
        acs.METRIC_BY_KEY["population_under_18"],
    )
    payload = acs.CensusACSClient(session=session, minimum_interval=0).acquire(
        acs.GeographyCriteria(kind="block-group", state="24", county="005"),
        metrics,
        year=2024,
        backend="census_reporter",
    )
    assert [call["params"]["table_ids"] for call in session.calls] == [
        "B01003",
        "B01002,B09001",
        "B01002",
        "B09001",
    ]
    assert payload.unavailable_tables == ("B09001",)
    first = payload.rows[0]
    assert first.values["B01002_001E"].estimate == 41.2
    unavailable = first.values["B09001_001E"]
    assert unavailable.estimate is None
    assert unavailable.margin_of_error is None
    assert unavailable.estimate_annotation == ("not_published_for_geography")
    record = acs._normalize_row(first, metrics, payload, year=2024)
    assert record["acquisition"]["unavailable_tables"] == ["B09001"]


def test_reporter_backend_preserves_anchor_row_when_table_omits_one_geography() -> None:
    partial = copy.deepcopy(REPORTER)
    del partial["data"]["05000US24003"]["B03002"]
    url = "https://api.censusreporter.org/1.0/data/show/acs2024_5yr"
    session = QueueSession(
        [
            FakeResponse(REPORTER, url),
            FakeResponse(partial, url),
        ]
    )
    metrics = (
        acs.METRIC_BY_KEY["population_total"],
        acs.METRIC_BY_KEY["asian_non_hispanic"],
    )
    payload = acs.CensusACSClient(session=session, minimum_interval=0).acquire(
        acs.GeographyCriteria(kind="county", state="24", county="*"),
        metrics,
        year=2024,
        backend="census_reporter",
    )
    assert len(payload.rows) == 2
    assert payload.unavailable_tables == ()
    missing = payload.rows[1].values["B03002_006E"]
    assert missing.estimate is None
    assert missing.estimate_annotation == ("not_published_for_geography")


def test_normalized_record_has_moe_geo_joins_rates_and_provenance() -> None:
    payload = _fixture_payload()
    record = acs._normalize_row(
        payload.rows[0],
        acs.KNOWN_METRICS,
        payload,
        year=2024,
    )
    assert record["canonical_ref"] == ("USCENSUS:ACS5:2024:05000US24001")
    assert record["acs_period"] == "2020-2024"
    assert record["geography"]["county_fips"] == "24001"
    assert record["metrics"]["median_household_income"] == {
        "estimate": 59603,
        "margin_of_error": 2750,
        "estimate_variable": "B19013_001E",
        "margin_variable": "B19013_001M",
        "label": ("Median household income in vintage-year inflation-adjusted dollars"),
        "concept": (
            "Median Household Income in the Past 12 Months (Inflation-Adjusted Dollars)"
        ),
        "unit": "USD",
        "estimate_annotation": None,
        "margin_annotation": None,
    }
    poverty = record["derived_point_estimate_indicators"]["poverty_rate"]
    assert poverty["percent"] == pytest.approx(16.8526, rel=1e-4)
    assert poverty["uncertainty_propagated"] is False
    assert record["acquisition"]["derivative_mirror"] is True
    assert record["acquisition"]["independent_corroboration"] is False


def test_execute_auto_uses_keyless_fallback_and_returns_partial_cursor() -> None:
    client = FixtureClient(has_api_key=False)
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--limit",
            "1",
        ),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.next_cursor
    assert client.acquire_calls[0]["backend"] == "census_reporter"
    assert result.records[0]["acquisition"]["backend"] == ("census_reporter")
    assert any("key" in warning.casefold() for warning in result.warnings)


def test_execute_auto_prefers_official_backend_when_key_is_present() -> None:
    client = FixtureClient(
        payload=_fixture_payload(backend="census_api"),
        has_api_key=True,
    )
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--profile",
            "population-age",
        ),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.OK
    assert client.acquire_calls[0]["backend"] == "census_api"
    assert result.records[0]["acquisition"]["derivative_mirror"] is False


def test_explicit_official_backend_without_key_is_restricted_with_route() -> None:
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--backend",
            "census-api",
        ),
        access_decision=_allowed(),
        client=FixtureClient(has_api_key=False),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.RESTRICTED
    assert result.errors[0].code == "census_api_key_required"
    assert result.errors[0].details["keyless_fallback"] == ("census_reporter")


def test_cursor_resume_binds_criteria_backend_release_schema_and_data() -> None:
    client = FixtureClient()
    first = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--limit",
            "1",
        ),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert first.next_cursor
    resumed = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--limit",
            "5",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert resumed.status == acs.ResultStatus.OK
    assert [record["geography"]["full_geoid"] for record in resumed.records] == [
        "05000US24003"
    ]

    mismatched = acs.execute(
        _args(
            "county",
            "--state",
            "06",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert mismatched.status == acs.ResultStatus.UNAVAILABLE
    assert mismatched.errors[0].code == "stale_or_invalid_cursor"

    changed_payload = replace(
        _fixture_payload(),
        data_fingerprint="f" * 64,
    )
    changed = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(payload=changed_payload),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert changed.status == acs.ResultStatus.UNAVAILABLE
    assert "representation changed" in changed.errors[0].message


def test_cursor_does_not_switch_acquisition_backend() -> None:
    first = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--limit",
            "1",
        ),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--backend",
            "census-api",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(has_api_key=True),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.UNAVAILABLE
    assert "different acquisition backend" in result.errors[0].message


def test_execute_empty_is_authoritative_no_results() -> None:
    empty = acs._payload(
        backend="census_reporter",
        year=2024,
        dataset_modified=None,
        rows=(),
        source_urls=("https://api.censusreporter.org/1.0/data/show/acs2024_5yr",),
        schemas=[{"empty": True}],
    )
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--county",
            "999",
            "--profile",
            "population-age",
        ),
        access_decision=_allowed(),
        client=FixtureClient(payload=empty),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_variables_uses_public_official_dictionary_and_filter() -> None:
    client = FixtureClient()
    result = acs.execute(
        _args(
            "variables",
            "B03002",
            "--contains",
            "Asian",
        ),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.OK
    assert [record["variable_id"] for record in result.records] == ["B03002_006E"]
    assert result.records[0]["concept"] == ("Hispanic or Latino Origin by Race")
    assert client.group_calls == [(2024, "B03002")]


def test_probe_checks_official_metadata_and_available_backend() -> None:
    one = _fixture_payload(
        (acs.METRIC_BY_KEY["population_total"],),
        rows=1,
    )
    client = FixtureClient(payload=one, has_api_key=False)
    result = acs.execute(
        _args("probe"),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.OK
    probe = result.records[0]
    assert probe["backend"] == "census_reporter"
    assert probe["release_id"] == "acs2024_5yr"
    assert probe["sentinel_full_geoid"] == "05000US24001"
    assert probe["sentinel_population"] == 67452
    assert probe["operation_states"]["official_data_query"] == ("free_api_key_needed")
    assert any(
        "official Data API key was not configured" in warning
        for warning in result.warnings
    )
    assert all("official 2026" not in warning for warning in result.warnings)
    assert client.dataset_calls == [2024]
    assert client.group_calls == [(2024, "B01003")]


def test_routes_cover_bulk_mirror_geocoder_and_spatial_alternatives() -> None:
    records = acs.source_records(2024)
    manifest = records[0]
    assert manifest["acquisition"]["maximum_official_variables_per_call"] == 50
    assert manifest["identity"]["observation"] == [
        "acs_vintage",
        "full_geoid",
    ]
    roles = {record["record_role"] for record in records[1:]}
    assert {
        "official_selective_demographic_query",
        "official_keyless_bulk_detailed_tables",
        "keyless_selective_acs_mirror",
        "address_to_census_geography_crosswalk",
        "census_geography_boundaries_and_spatial_join",
    } == roles
    mirror = next(
        record
        for record in records
        if record.get("source_id") == "us-census-reporter-acs-api"
    )
    assert "not independent corroboration" in mirror["provenance_note"]


def test_http_rate_limit_is_not_no_results() -> None:
    session = QueueSession(
        [
            FakeResponse(
                {},
                ("https://api.censusreporter.org/1.0/data/show/acs2024_5yr"),
                status_code=429,
            )
        ]
    )
    result = acs.execute(
        _args(
            "county",
            "--state",
            "24",
            "--profile",
            "population-age",
        ),
        access_decision=_allowed(),
        client=acs.CensusACSClient(
            session=session,
            minimum_interval=0,
        ),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == acs.ResultStatus.RATE_LIMITED
    assert result.records == ()
    assert result.errors[0].code == "rate_limited"


def test_stable_url_never_retains_api_key() -> None:
    assert acs._stable_url(
        "https://api.census.gov/data/2024/acs/acs5?"
        "get=NAME&key=super-secret&for=state%3A24"
    ) == ("https://api.census.gov/data/2024/acs/acs5?get=NAME&for=state%3A24")
