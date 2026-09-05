from __future__ import annotations

import os

import pytest

from tools import query_ny_statewide_parcels as ny


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client(component_key: str) -> ny.NYParcelClient:
    return ny.NYParcelClient(
        ny.COMPONENTS[component_key],
        page_size=10,
        timeout=20,
        minimum_interval=0,
        retry_attempts=2,
    )


def test_live_centroid_probe_returns_current_all_county_assessment_record():
    args = ny.build_parser().parse_args(
        ["probe", "--geometry", "--minimum-interval", "0"]
    )

    result = ny.execute(args, client=_client("centroids"))

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["component"] == "centroids"
    assert record["geometry_role"] == ("mathematically_derived_point_within_parcel")
    assert record["source_snapshot"]["assessment_year"] >= 2025
    assert record["source_snapshot"]["reported_total_matches"] > 5_000_000
    assert record["parcel_identifiers"]["swis_sbl_id"]
    assert record["parcel_identifiers"]["municipal_parcel_id"]


def test_live_join_key_links_centroid_public_and_state_owned_components():
    seed = _client("state-owned").fetch_page(
        where="OBJECTID > 0",
        record_count=1,
        return_geometry=False,
        spatial_parameters={},
    )
    join_key = seed[0]["attributes"]["SWIS_SBL_ID"]
    assert join_key

    joined = {}
    for component_key in ("centroids", "public-parcels", "state-owned"):
        matches = _client(component_key).fetch_page(
            where=f"SWIS_SBL_ID='{join_key}'",
            record_count=5,
            return_geometry=True,
            spatial_parameters={},
        )
        assert matches
        joined[component_key] = matches[0]

    assert {record["attributes"]["SWIS_SBL_ID"] for record in joined.values()} == {
        join_key
    }
    assert {"x", "y"} <= set(joined["centroids"]["geometry"])
    assert "rings" in joined["public-parcels"]["geometry"]
    assert joined["state-owned"]["attributes"]["NYS_NAME"]


def test_live_nonpublic_polygon_county_retains_centroid_and_state_routes():
    where = "COUNTY_NAME='Dutchess'"
    centroid_count = _client("centroids").fetch_count(
        where,
        spatial_parameters={},
    )
    public_count = _client("public-parcels").fetch_count(
        where,
        spatial_parameters={},
    )
    state_owned_count = _client("state-owned").fetch_count(
        where,
        spatial_parameters={},
    )

    assert centroid_count > 100_000
    assert public_count == 0
    assert state_owned_count > 0
    routes = {route["route_id"]: route for route in ny._alternative_routes()}
    assert routes["county-parcel-resource-directory"]["url"] == ny.LANDING_URL


def test_live_coverage_reports_all_components_and_public_counties():
    args = ny.build_parser().parse_args(["coverage", "--minimum-interval", "0"])

    result = ny.execute(args)

    assert result.status.value == "ok"
    summary = result.records[0]
    counts = {
        row["component"]: row["record_count"] for row in summary["component_counts"]
    }
    assert counts["centroids"] > 5_000_000
    assert counts["public-parcels"] > 3_500_000
    assert counts["state-owned"] > 30_000
    public = summary["public_polygon_county_coverage"]
    assert public["county_count"] >= 38
    assert public["county_count"] == len(public["counties"])
    assert summary["centroid_county_coverage"]["county_count"] == 62
    assert summary["state_owned_county_coverage"]["county_count"] == 62
