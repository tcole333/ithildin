from __future__ import annotations

import os

import pytest

from tools import query_washington_parcels as washington


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_WASHINGTON_PARCELS") != "1",
    reason="set RUN_LIVE_WASHINGTON_PARCELS=1 to run official live probes",
)


def _args(*values: str):
    return washington.build_parser().parse_args(list(values))


def test_live_operation_probe_and_optional_wisaard_parity() -> None:
    result = washington.execute(
        _args(
            "probe",
            "--operation",
            "all",
            "--representation",
            "all",
            "--include-wisaard",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    metadata_probes = {
        record["representation"]: record
        for record in result.records
        if record["record_kind"] == "source_probe"
    }
    assert metadata_probes.keys() == {"ecology", "dnr", "wisaard"}
    assert all(
        not record["operations"]["metadata"]["owner_fields_detected"]
        for record in metadata_probes.values()
    )
    assert metadata_probes["ecology"]["operations"]["count"]["count"] > 3_000_000
    assert (
        metadata_probes["ecology"]["operations"]["count"]["count"]
        == metadata_probes["dnr"]["operations"]["count"]["count"]
    )
    parity = next(
        record
        for record in result.records
        if record["record_kind"] == "parcel_representation_parity"
    )
    comparisons = {
        comparison["candidate"]: comparison
        for comparison in parity["comparisons"]
    }
    assert comparisons["dnr"]["health"] == "aligned"
    assert comparisons["wisaard"]["health"] in {
        "lagging",
        "different_snapshot",
    }


def test_live_point_bbox_and_cross_boundary_export() -> None:
    point = washington.execute(
        _args(
            "point",
            "-117.97",
            "47.255",
            "--limit",
            "5",
            "--no-enrich",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    )
    bbox = washington.execute(
        _args(
            "bbox",
            "-117.983",
            "47.250",
            "-117.960",
            "47.261",
            "--limit",
            "5",
            "--no-enrich",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    )
    export = washington.execute(
        _args(
            "export",
            "--county",
            "Adams",
            "--limit",
            "2001",
            "--page-size",
            "2000",
            "--no-enrich",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    )

    assert point.status.value == "ok"
    assert point.records
    assert all(record["geometry_crs"] == "EPSG:4326" for record in point.records)
    assert bbox.status.value == "ok"
    assert bbox.records
    assert len(export.records) == 2_001
    object_ids = [record["object_id"] for record in export.records]
    assert object_ids == sorted(object_ids)
    assert len(object_ids) == len(set(object_ids))
