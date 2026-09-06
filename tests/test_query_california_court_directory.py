from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_california_court_directory as directory
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "california_court_directory"
)
DIRECTORY_HTML = (FIXTURE_DIR / "directory.html").read_text(encoding="utf-8")
SOURCE_CHANGED_HTML = (FIXTURE_DIR / "source_changed.html").read_text(
    encoding="utf-8"
)


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = DIRECTORY_HTML
    url: str = directory.DIRECTORY_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=UTF-8"}
    )


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected California directory request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, page: directory.CaliforniaCourtDirectoryPage) -> None:
        self.page = page
        self.calls = 0

    def fetch(self) -> directory.CaliforniaCourtDirectoryPage:
        self.calls += 1
        return self.page


def parse_args(*values: str) -> argparse.Namespace:
    return directory.build_parser().parse_args(list(values))


def fixture_page() -> directory.CaliforniaCourtDirectoryPage:
    return directory.parse_directory_page(
        DIRECTORY_HTML,
        require_complete=False,
    )


def full_page() -> directory.CaliforniaCourtDirectoryPage:
    records = []
    for county, county_fips in directory.COUNTY_FIPS.items():
        district = 2 if county == "Los Angeles" else 1
        if county not in {"Los Angeles", "San Mateo"}:
            district = 3
        record = dict(fixture_page().records[0])
        record.update(
            {
                "canonical_ref": f"CA-COURT-DIRECTORY:{county_fips}",
                "county": county,
                "county_fips": county_fips,
                "appellate_district": district,
                "official_url": f"https://{county_fips}.example.test/",
            }
        )
        records.append(record)
    base = fixture_page()
    return directory.CaliforniaCourtDirectoryPage(
        records=tuple(records),
        source_url=base.source_url,
        schema_fingerprint=base.schema_fingerprint,
        snapshot_fingerprint=base.snapshot_fingerprint,
    )


def test_county_mapping_is_complete_and_unique() -> None:
    assert len(directory.COUNTY_FIPS) == 58
    assert len(set(directory.COUNTY_FIPS.values())) == 58
    assert directory.COUNTY_FIPS["Los Angeles"] == "06037"
    assert directory.COUNTY_FIPS["San Mateo"] == "06081"
    assert directory.COUNTY_FIPS["Yuba"] == "06115"


def test_parser_preserves_source_published_routes_and_districts() -> None:
    page = fixture_page()

    assert len(page.records) == 3
    los_angeles = page.records[0]
    assert los_angeles["record_kind"] == "superior_court_directory_entry"
    assert los_angeles["county"] == "Los Angeles"
    assert los_angeles["county_fips"] == "06037"
    assert los_angeles["appellate_district"] == 2
    assert los_angeles["routes"]["superior_court"] == {
        "label": "Los Angeles",
        "published_url": "http://www.lacourt.org/",
        "url": "http://www.lacourt.org/",
        "host": "www.lacourt.org",
    }
    assert (
        los_angeles["routes"]["courthouses"]["url"]
        == "https://courts.ca.gov/find-my-court.htm?query=Los%20Angeles"
    )
    assert los_angeles["source_scope"]["case_index"] is False
    assert "case_search" in los_angeles["discovery_seed"]["candidate_categories"]
    assert len(page.schema_fingerprint) == 64
    assert len(page.snapshot_fingerprint) == 64


def test_full_coverage_validation_reports_missing_counties() -> None:
    with pytest.raises(
        directory.CaliforniaCourtDirectoryChangedError
    ) as raised:
        directory.parse_directory_page(DIRECTORY_HTML)

    assert raised.value.code == "directory_coverage_changed"
    assert raised.value.details["observed_count"] == 3
    assert "Alameda" in raised.value.details["missing_counties"]


def test_source_changed_header_is_explicit() -> None:
    with pytest.raises(
        directory.CaliforniaCourtDirectoryChangedError
    ) as raised:
        directory.parse_directory_page(
            SOURCE_CHANGED_HTML,
            require_complete=False,
        )

    assert raised.value.code == "directory_table_missing"
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_client_retries_transient_status_and_uses_browser_headers() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse(text=DIRECTORY_HTML),
        ]
    )
    delays: list[float] = []
    client = directory.CaliforniaCourtDirectoryClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=2, backoff_initial=0.01),
        sleeper=delays.append,
    )

    with pytest.raises(directory.CaliforniaCourtDirectoryChangedError):
        client.fetch()

    assert len(session.calls) == 2
    assert delays == [0.01]
    assert session.headers["User-Agent"] == directory.DEFAULT_USER_AGENT


def test_list_fetches_the_complete_directory_without_an_adapter_cap() -> None:
    page = full_page()
    result = directory.execute(
        parse_args("list"),
        client=FakeClient(page),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 58
    assert result.next_cursor is None
    assert "limit" not in result.query.query.parameters
    validate_envelope(result.to_dict())


def test_county_and_district_filters_preserve_complete_source_records() -> None:
    client = FakeClient(full_page())
    county = directory.execute(
        parse_args("list", "--county", "san mateo"),
        client=client,
        log_results=False,
    )
    district = directory.execute(
        parse_args("list", "--appellate-district", "2"),
        client=client,
        log_results=False,
    )

    assert [record["county"] for record in county.records] == ["San Mateo"]
    assert [record["county"] for record in district.records] == ["Los Angeles"]


def test_search_matches_routes_and_returns_authoritative_empty() -> None:
    page = fixture_page()
    matched = directory.execute(
        parse_args("search", "lacourt.org"),
        client=FakeClient(page),
        log_results=False,
    )
    empty = directory.execute(
        parse_args("search", "no-such-court-route.example"),
        client=FakeClient(page),
        log_results=False,
    )

    assert [record["county"] for record in matched.records] == ["Los Angeles"]
    assert empty.status is ResultStatus.NO_RESULTS
    assert empty.records == ()


def test_unknown_county_is_structured_query_error() -> None:
    result = directory.execute(
        parse_args("list", "--county", "Atlantis"),
        client=FakeClient(fixture_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "unknown_county"
    assert result.errors[0].category == "query_selection"


def test_sources_does_not_fetch_and_describes_directory_semantics() -> None:
    client = FakeClient(fixture_page())
    result = directory.execute(
        parse_args("sources"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert client.calls == 0
    assert result.records[0]["coverage"]["county_superior_courts"] == 58
    assert result.records[0]["not_a_case_index"] is True


def test_discovery_emits_stable_county_candidates_and_alternate_routes() -> None:
    result = directory.execute(
        parse_args("discovery", "--query", "San Mateo"),
        client=FakeClient(fixture_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    candidate = result.records[0]
    assert candidate["record_kind"] == "source_discovery_candidate"
    assert candidate["candidate_kind"] == (
        "official_county_superior_court_website"
    )
    assert candidate["registry_identity"]["county_fips"] == "06081"
    assert candidate["court"]["appellate_district"] == 1
    assert candidate["published_routes"]["contact"]["url"].startswith("https://")
    assert "tentative_rulings" in candidate["assessment_fields"]
    assert candidate["infra_request_created"] is False


def test_probe_verifies_58_counties_and_two_stable_sentinels() -> None:
    result = directory.execute(
        parse_args("probe"),
        client=FakeClient(full_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert result.records[0]["county_count"] == 58
    assert result.records[0]["sentinels"]["Los Angeles"]["appellate_district"] == 2
    assert result.records[0]["sentinels"]["San Mateo"]["county_fips"] == "06081"


def test_human_verification_is_not_misparsed_as_an_empty_directory() -> None:
    with pytest.raises(directory.CaliforniaCourtDirectoryError) as raised:
        directory.parse_directory_page(
            "<html>Enable JavaScript and cookies to continue</html>",
            require_complete=False,
        )

    assert raised.value.code == "human_verification"
    assert raised.value.status is ResultStatus.HUMAN_REQUIRED
