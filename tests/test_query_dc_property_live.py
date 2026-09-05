from __future__ import annotations

import os

import pytest

from tools import query_dc_property as dc


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


@pytest.mark.parametrize(
    ("component", "expected_source"),
    [
        ("assessment", dc.ITSPE_SOURCE_ID),
        ("geometry", dc.OWNER_POLYGON_SOURCE_ID),
        ("sales", dc.SALES_SOURCE_ID),
        ("surveys", dc.SURVEY_SOURCE_ID),
    ],
)
def test_live_component_sentinel(component, expected_source):
    args = dc.build_parser().parse_args(["probe", component])
    client = dc.DCArcGISClient(
        dc.COMPONENTS[component].layer_url,
        page_size=1,
        max_records=1,
        timeout=30.0,
        minimum_interval=0.0,
    )
    result = dc.execute(
        args,
        access_decision={"allowed": True, "limits": {"maximum_page_size": 1}},
        client=client,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["source_id"] == expected_source


@pytest.mark.parametrize(
    ("component", "minimum"),
    [
        ("assessment", 200_000),
        ("geometry", 120_000),
        ("sales", 400_000),
        ("surveys", 170_000),
    ],
)
def test_live_component_count(component, minimum):
    args = dc.build_parser().parse_args(["count", component])
    client = dc.DCArcGISClient(
        dc.COMPONENTS[component].layer_url,
        page_size=1,
        max_records=1,
        timeout=30.0,
        minimum_interval=0.0,
    )
    result = dc.execute(
        args,
        access_decision={"allowed": True},
        client=client,
    )
    assert result.status.value == "ok"
    assert result.records[0]["count"] >= minimum


def test_live_sales_date_bounds_use_the_advertised_standardized_query():
    args = dc.build_parser().parse_args(
        [
            "sales",
            dc.PROBE_SSL,
            "--start-date",
            "2003-01-01",
            "--end-date",
            "2003-12-31",
            "--limit",
            "5",
        ]
    )
    client = dc.DCArcGISClient(
        dc.SALES.layer_url,
        page_size=5,
        max_records=5,
        timeout=30.0,
        minimum_interval=0.0,
    )
    result = dc.execute(
        args,
        access_decision={"allowed": True},
        client=client,
    )
    assert result.status.value == "ok"
    assert result.records[0]["native_parcel_id"] == dc.PROBE_SSL
    assert result.records[0]["sale"]["sale_date"].startswith("2003-")


def test_live_point_query_returns_the_expected_common_ownership_polygon():
    args = dc.build_parser().parse_args(
        [
            "point",
            "-76.9927",
            "38.9176",
            "--limit",
            "5",
            "--out-sr",
            "4326",
        ]
    )
    client = dc.DCArcGISClient(
        dc.OWNER_POLYGONS.layer_url,
        page_size=5,
        max_records=5,
        timeout=30.0,
        minimum_interval=0.0,
    )
    result = dc.execute(
        args,
        access_decision={"allowed": True},
        client=client,
    )
    assert result.status.value == "ok"
    assert any(
        record["native_parcel_id"] == dc.PROBE_SSL
        for record in result.records
    )
    assert all(record["geometry_crs"] == "EPSG:4326" for record in result.records)


def test_live_collapsed_survey_ssl_matches_source_padded_ssl():
    args = dc.build_parser().parse_args(
        [
            "surveys",
            "1653E 0024",
            "--field",
            "ssl",
            "--limit",
            "5",
        ]
    )
    client = dc.DCArcGISClient(
        dc.SURVEYS.layer_url,
        page_size=5,
        max_records=5,
        timeout=30.0,
        minimum_interval=0.0,
    )
    result = dc.execute(
        args,
        access_decision={"allowed": True},
        client=client,
    )
    assert result.status.value == "ok"
    assert any(
        record["native_id"] == dc.PROBE_SURVEY_GUID
        for record in result.records
    )
