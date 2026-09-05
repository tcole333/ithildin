from __future__ import annotations

import os

import pytest

from tools import query_california_court_directory as directory
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_CA_COURT_DIRECTORY") != "1",
    reason="set RUN_LIVE_CA_COURT_DIRECTORY=1 for official live probes",
)


def test_live_directory_has_all_counties_and_stable_sentinels() -> None:
    result = directory.execute(
        directory.build_parser().parse_args(
            [
                "probe",
                "--minimum-interval",
                "0",
                "--max-attempts",
                "2",
            ]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["county_count"] == 58
    assert probe["appellate_districts"] == (1, 2, 3, 4, 5, 6)
    assert probe["sentinels"]["Los Angeles"]["appellate_district"] == 2
    assert probe["sentinels"]["San Mateo"]["appellate_district"] == 1


def test_live_exact_county_returns_official_route_bundle() -> None:
    result = directory.execute(
        directory.build_parser().parse_args(
            [
                "list",
                "--county",
                "Santa Clara",
                "--minimum-interval",
                "0",
            ]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    record = result.records[0]
    assert record["county_fips"] == "06085"
    assert record["appellate_district"] == 6
    assert record["routes"]["superior_court"]["url"].startswith("http")
