from __future__ import annotations

import os

import pytest

from tools import query_montana_cadastral as mt


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded Montana MSL probes",
)


def test_live_metadata_validates_statewide_layer_and_nullable_join_identity():
    result = mt.execute(
        mt.build_parser().parse_args(
            ["metadata", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    snapshot = record["source_snapshot"]
    assert record["layer_name"] == "Montana Parcels"
    assert snapshot["total_features"] > 800_000
    assert snapshot["features_with_parcel_id"] > 800_000
    assert snapshot["features_without_parcel_id"] > 0
    assert snapshot["native_page_size"] == 2000
    assert record["identity_contract"]["parcel_join_key"] == "PARCELID"


def test_live_probe_returns_wgs84_geometry_and_source_occurrence_keys():
    result = mt.execute(
        mt.build_parser().parse_args(
            ["probe", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["identity"]["object_id"] > 0
    assert record["identity"]["parcel_id"]
    assert record["identity"]["transport_cursor_key"] == "OBJECTID"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry"]["rings"]


def test_live_county_groups_reconcile_to_all_56_orion_prefixes():
    result = mt.execute(
        mt.build_parser().parse_args(
            ["counties", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 56
    assert {record["orion_county_prefix"] for record in result.records} == set(
        range(1, 57)
    )
    assert sum(record["feature_count"] for record in result.records) > 800_000


def test_live_release_discovery_and_small_county_archive_probe():
    discovery = mt.execute(
        mt.build_parser().parse_args(
            ["releases", "--minimum-interval", "0"]
        ),
        log_results=False,
    )
    probe = mt.execute(
        mt.build_parser().parse_args(
            [
                "artifact-probe",
                "--dataset",
                "parcel-shp",
                "--county",
                "Petroleum",
                "--range-bytes",
                "32",
                "--minimum-interval",
                "0",
            ]
        ),
        log_results=False,
    )

    assert discovery.status.value == "ok"
    release = discovery.records[0]
    assert release["parcel_county_directory_count"] == 56
    assert release["orion_county_archive_count"] == 56
    assert list(release["missing_parcel_county_directories"]) == []
    assert list(release["missing_orion_county_prefixes"]) == []

    assert probe.status.value == "ok"
    artifact = probe.records[0]["selected_artifact"]
    assert artifact["filename"] == "Petroleum_SHP.zip"
    assert artifact["expected_size"] > 1_000_000
    assert probe.records[0]["probe"]["format_hint"] == "zip"
    assert probe.records[0]["probe"]["sample_size"] == 32
