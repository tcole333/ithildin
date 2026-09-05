from __future__ import annotations

import os

import pytest

from tools import query_mason_county_tax_parcels as mason


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_MASON_COUNTY_TAX_PARCELS") != "1",
    reason=(
        "set RUN_LIVE_MASON_COUNTY_TAX_PARCELS=1 to run the official "
        "Mason ArcGIS sentinels"
    ),
)


def _args(*values: str):
    return mason.build_parser().parse_args(list(values))


def test_live_complete_id_snapshot_and_exact_fid_zero_sentinel() -> None:
    access_contract = {"allowed": True, "limits": {}}

    probe = mason.execute(
        _args("probe"),
        access_contract=access_contract,
        log_results=False,
    )
    sentinel = mason.execute(
        _args("objectid", "0", "--limit", "1"),
        access_contract=access_contract,
        log_results=False,
    )

    assert probe.status.value == "ok"
    assert probe.records[0]["smallest_object_id"] == 0
    assert probe.records[0]["feature_count"] > 0
    assert sentinel.status.value == "ok"
    assert sentinel.records[0]["source_occurrence_id"] == "FID:0"
    assert sentinel.records[0]["parcel_identifiers"]["pin"] == "219010090013"
    assert sentinel.records[0]["parcel_identifiers"]["terra_pin"] == ("21901-00-90013")
    assert sentinel.records[0]["parcel_identifiers"]["taxlot"] == "0090013"
