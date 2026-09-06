from __future__ import annotations

import os

import pytest

from tools import query_michigan_property_directories as directory
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_MI_PROPERTY_DIRECTORY") != "1",
    reason="set RUN_LIVE_MI_PROPERTY_DIRECTORY=1 for official live probes",
)


def test_live_directory_has_all_83_counties_and_stable_sentinels() -> None:
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
    assert probe["county_count"] == 83
    assert probe["county_fips_count"] == 83
    assert probe["sentinels"]["Arenac"]["platform_family"] == "bsa_online"
    assert "recording_office" in probe["sentinels"]["Genesee"][
        "route_signals"
    ]
    assert probe["sentinels"]["Wayne"]["county_fips"] == "26163"


def test_live_exact_county_returns_published_route_and_role_boundaries() -> None:
    result = directory.execute(
        directory.build_parser().parse_args(
            [
                "list",
                "--county",
                "Oakland",
                "--minimum-interval",
                "0",
                "--max-attempts",
                "2",
            ]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    record = result.records[0]
    assert record["county_fips"] == "26125"
    assert record["official_url"].startswith("https://gis.oakgov.com/")
    assert record["publisher_declared_role"]["role"] == "parcel_geometry"
    assert (
        record["role_separation"]["land_records_index"]
        == "not_established_by_directory"
    )
