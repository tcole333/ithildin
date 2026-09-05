from __future__ import annotations

import os

import pytest

from tools import query_wisconsin_court_directory as directory


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for official Wisconsin live probes",
)


def test_live_probe_covers_all_official_directory_components() -> None:
    args = directory.build_parser().parse_args(["probe"])
    result = directory.execute(args, log_results=False)

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["component_count"] == 6
    assert probe["record_count"] >= 246
    assert probe["county_coverage"]["complete_components"] == (
        directory.CIRCUIT_COMPONENT,
        directory.CLERK_COMPONENT,
        directory.JUDGE_COMPONENT,
    )
    assert probe["components"][directory.DISTRICT_COMPONENT]["coverage"][
        "county_count"
    ] == 72
    assert probe["components"][directory.APPEALS_COMPONENT]["coverage"][
        "county_count"
    ] == 72
