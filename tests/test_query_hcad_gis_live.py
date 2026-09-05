from __future__ import annotations

import os

import pytest

from tools import query_hcad_gis as hcad_gis


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _args(*argv: str):
    return hcad_gis.build_parser().parse_args(list(argv))


def test_live_hcad_manifest_parcel_probe_and_mapserver_feature():
    contract = {
        "allowed": True,
        "limits": {
            "maximum_page_size": 25,
            "minimum_interval_seconds": 0.1,
        },
    }
    releases = hcad_gis.execute(
        _args("releases"),
        access_contract=contract,
        log_results=False,
    )
    probe = hcad_gis.execute(
        _args("probe", "--sample-bytes", "256"),
        access_contract=contract,
        log_results=False,
    )
    feature = hcad_gis.execute(
        _args("objectid", "1", "--limit", "1"),
        access_contract=contract,
        log_results=False,
    )

    assert releases.status.value == "ok"
    assert releases.records[0]["component_artifact_count"] >= 20
    assert probe.status.value == "ok"
    assert probe.records[0]["probe"]["format_hint"] == "zip"
    assert feature.status.value == "ok"
    assert feature.records[0]["feature_occurrence"]["object_id"] == 1
    assert feature.records[0]["parcel_identifiers"]["hcad_num"]
