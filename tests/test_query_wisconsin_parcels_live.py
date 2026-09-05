from __future__ import annotations

import os

import pytest

from tools import query_wisconsin_parcels as wisconsin


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def test_live_owner_query_exhausts_every_match_across_pages():
    args = wisconsin.build_parser().parse_args(
        ["owner", "EPSTEIN", "--page-size", "10"]
    )
    client = wisconsin.WisconsinParcelClient(
        page_size=10,
        minimum_interval=0,
    )

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.records
    snapshot = result.records[0]["source_snapshot"]
    assert snapshot["reported_total_matches"] == len(result.records)
    assert snapshot["pages_fetched"] >= 2
    assert result.next_cursor is None
    assert all(
        record["source_snapshot"]["dataset_release"]
        == snapshot["dataset_release"]
        for record in result.records
    )


def test_live_coverage_reconciles_statewide_and_contributor_counts():
    args = wisconsin.build_parser().parse_args(["coverage"])
    client = wisconsin.WisconsinParcelClient(minimum_interval=0)

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    summary = result.records[0]
    assert summary["county_contributor_count"] == 72
    assert summary["special_source_count"] >= 1
    assert sum(
        row["record_count"] for row in summary["contributors"]
    ) == summary["statewide_record_count"]
    visibility = summary["owner_visibility"]
    assert sum(visibility.values()) == summary["statewide_record_count"]


def test_live_parcel_lookup_returns_exact_id_and_polygon():
    state_id = "001008015540000"
    args = wisconsin.build_parser().parse_args(
        ["parcel", state_id, "--geometry"]
    )
    client = wisconsin.WisconsinParcelClient(
        page_size=10,
        minimum_interval=0,
    )

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    assert any(
        record["state_parcel_id"] == state_id for record in result.records
    )
    assert all(record["geometry_crs"] == "EPSG:4326" for record in result.records)
