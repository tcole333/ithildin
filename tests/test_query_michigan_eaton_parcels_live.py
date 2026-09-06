from __future__ import annotations

import os

import pytest

from tools import query_michigan_eaton_parcels as eaton
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_MI_EATON_PARCELS") != "1",
    reason="set RUN_LIVE_MI_EATON_PARCELS=1 for live Eaton parcel checks",
)


def _args(*argv: str):
    return eaton.build_parser().parse_args(list(argv))


def test_live_item_metadata_contract():
    result = eaton.execute(_args("metadata"), log_results=False)

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["item"]["id"] == eaton.ITEM_ID
    assert record["item"]["type"] == "Shapefile"
    assert record["item"]["access"] == "public"
    assert record["item"]["size"] > 0
    assert record["license"]["published_text"]


def test_live_bounded_download_probe():
    result = eaton.execute(
        _args("probe", "--sample-bytes", "64"),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.records[0]["artifact_probe"]
    assert probe["format_hint"] == "zip"
    assert probe["sample_size"] == 64
