from __future__ import annotations

import os

import pytest

from tools import query_virginia_parcels as va


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded VGIN probes",
)


def test_live_metadata_resolves_current_official_item():
    result = va.execute(
        va.build_parser().parse_args(
            ["metadata", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["resolved_layer_url"].endswith(
        "/VA_Base_Layers/VA_Parcels/FeatureServer/0"
    )
    assert record["dataset_statistics"]["row_count"] > 4_000_000
    assert record["identity_contract"]["durable_source_key"] == "VGIN_QPID"


def test_live_probe_returns_exact_qpid_and_wgs84_polygon():
    result = va.execute(
        va.build_parser().parse_args(
            ["probe", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["vgin_qpid"] == va.PROBE_VGIN_QPID
    assert record["jurisdiction"]["source_locality_code"] == (
        va.PROBE_LOCALITY_FIPS
    )
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry"]["rings"]


def test_live_identity_and_locality_coverage_audits():
    identity = va.execute(
        va.build_parser().parse_args(
            ["identity-audit", "--minimum-interval", "0"]
        ),
        log_results=False,
    )
    coverage = va.execute(
        va.build_parser().parse_args(
            ["localities", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert identity.status.value == "ok"
    assert identity.records[0][
        "vgin_qpid_unique_and_complete_in_observed_release"
    ] is True
    assert coverage.status.value == "ok"
    record = coverage.records[0]
    assert record["source_locality_group_count"] >= 130
    assert record["statewide_parcel_count"] > 4_000_000
    assert list(record["missing_county_equivalent_geoids"]) == ["51157"]
    assert record["incorporated_town_code_count"] == 4
