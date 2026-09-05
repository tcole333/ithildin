from __future__ import annotations

import os

import pytest

from tools import query_philadelphia_property as phila


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def test_live_owner_query_exhausts_more_than_one_transport_page():
    args = phila.build_parser().parse_args(
        ["owner", "EPSTEIN", "--page-size", "10"]
    )
    client = phila.PhiladelphiaArcGISClient(
        phila.OPA_MANIFEST,
        page_size=10,
        minimum_interval=0,
    )

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "ok"
    assert len(result.records) >= 10
    snapshot = result.records[0]["source_snapshot"]
    assert snapshot["reported_total_matches"] == len(result.records)
    assert snapshot["pages_fetched"] >= 2
    assert result.next_cursor is None


def test_live_assessment_history_returns_full_sentinel_series():
    args = phila.build_parser().parse_args(
        ["history", phila.PROBE_PARCEL_NUMBER, "--page-size", "5"]
    )
    client = phila.PhiladelphiaCartoClient(
        page_size=5,
        minimum_interval=0,
    )

    result = phila.execute(args, history_client=client)

    assert result.status.value == "ok"
    years = {record["assessment_year"] for record in result.records}
    assert "2015" in years
    assert len(years) >= 10
    assert result.records[0]["source_snapshot"][
        "reported_total_matches"
    ] == len(result.records)


def test_live_opa_registry_joins_to_dor_polygon():
    args = phila.build_parser().parse_args(
        [
            "parcel-shape",
            phila.PROBE_REGISTRY_NUMBER,
            "--by",
            "registry",
        ]
    )
    client = phila.PhiladelphiaArcGISClient(
        phila.DOR_MANIFEST,
        page_size=10,
        minimum_interval=0,
    )

    result = phila.execute(args, dor_client=client)

    assert result.status.value == "ok"
    assert any(
        record["map_registry_number"] == phila.PROBE_REGISTRY_NUMBER
        and record["pin"] == phila.PROBE_PIN
        for record in result.records
    )
    assert all(record["geometry_role"] for record in result.records)
